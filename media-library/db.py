import contextlib
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import uuid
import unicodedata
from urllib.parse import urlsplit
from search import compile_query, CATEGORIES
from source_identity import normalize_url

ROOT = Path(__file__).resolve().parent
PATH = Path(os.environ.get('MEDIA_DB', str(ROOT / 'data' / 'library.sqlite3')))
OWNER = 'local'
SYMBOLS = ['Star','Heart','Circle','Diamond','Square','Triangle','Flower','Sun','Moon','Sparkle']
def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def uid(): return uuid.uuid4().hex
def metadata_key(value):
    # Width/case-insensitive Latin ordering; kana variants share gojuon order.
    text = unicodedata.normalize('NFKC', value or '').casefold()
    text = ''.join(chr(ord(ch)-0x60) if '\u30a1' <= ch <= '\u30f6' else ch for ch in text)
    return unicodedata.normalize('NFD', text)
def connect():
    PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.create_function('fold',1,lambda s:(s or '').casefold(), deterministic=True)
    c.create_function('metadata_key',1,metadata_key, deterministic=True)
    import tag_policy
    c.create_function('entity_key',1,tag_policy.key, deterministic=True)
    c.create_function('shuffle',2,lambda i,seed:hashlib.sha256((str(seed)+i).encode()).hexdigest(), deterministic=True)
    return c
@contextlib.contextmanager
def transaction():
    c = connect()
    try:
        with c: yield c
    finally:
        c.close()
def init():
    with transaction() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript('''
        CREATE TABLE IF NOT EXISTS migrations(version INTEGER PRIMARY KEY, applied_at TEXT);
        CREATE TABLE IF NOT EXISTS owners(id TEXT PRIMARY KEY, next_rating INTEGER NOT NULL DEFAULT 1);
        INSERT OR IGNORE INTO owners(id) VALUES('local');
        CREATE TABLE IF NOT EXISTS works(id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES owners(id), title TEXT NOT NULL COLLATE BINARY, cover TEXT DEFAULT '', category TEXT DEFAULT '', language TEXT DEFAULT '', pages INTEGER CHECK(pages>=0), review TEXT DEFAULT '', bought INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL, updated TEXT NOT NULL, opened TEXT, UNIQUE(owner,title));
        CREATE INDEX IF NOT EXISTS works_created ON works(owner,created);
        CREATE INDEX IF NOT EXISTS works_opened ON works(owner,opened);
        CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES owners(id), kind TEXT NOT NULL, name TEXT NOT NULL COLLATE BINARY, gender TEXT NOT NULL DEFAULT 'neutral', UNIQUE(owner,kind,name,gender));
        CREATE INDEX IF NOT EXISTS entities_kind ON entities(owner,kind);
        CREATE TABLE IF NOT EXISTS aliases(entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE, name TEXT NOT NULL, PRIMARY KEY(entity_id,name));
        CREATE TABLE IF NOT EXISTS work_entities(work_id TEXT REFERENCES works(id) ON DELETE CASCADE, entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE, PRIMARY KEY(work_id,entity_id));
        CREATE INDEX IF NOT EXISTS entity_works ON work_entities(entity_id,work_id);
        CREATE TABLE IF NOT EXISTS links(id TEXT PRIMARY KEY, work_id TEXT REFERENCES works(id) ON DELETE CASCADE, url TEXT NOT NULL, label TEXT DEFAULT '', position INTEGER NOT NULL, is_primary INTEGER NOT NULL, UNIQUE(work_id,url));
        CREATE INDEX IF NOT EXISTS link_url ON links(url);
        CREATE TABLE IF NOT EXISTS dimensions(id TEXT PRIMARY KEY, owner TEXT REFERENCES owners(id), number INTEGER NOT NULL, name TEXT NOT NULL, maximum INTEGER NOT NULL CHECK(maximum BETWEEN 2 AND 10), symbol TEXT NOT NULL, gallery INTEGER NOT NULL DEFAULT 0, UNIQUE(owner,number));
        CREATE TABLE IF NOT EXISTS scores(work_id TEXT REFERENCES works(id) ON DELETE CASCADE, dimension_id TEXT REFERENCES dimensions(id) ON DELETE CASCADE, value INTEGER NOT NULL CHECK(value>=1), PRIMARY KEY(work_id,dimension_id));
        CREATE INDEX IF NOT EXISTS scores_dim ON scores(dimension_id,value);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, owner TEXT REFERENCES owners(id), status TEXT NOT NULL, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS job_items(id TEXT PRIMARY KEY, job_id TEXT REFERENCES jobs(id) ON DELETE CASCADE, url TEXT NOT NULL, label TEXT DEFAULT '', folder TEXT DEFAULT '', status TEXT NOT NULL, title TEXT DEFAULT '', message TEXT DEFAULT '', work_id TEXT, attempts INTEGER DEFAULT 0);
        CREATE INDEX IF NOT EXISTS job_state ON job_items(job_id,status);
        INSERT OR IGNORE INTO migrations VALUES(1,datetime('now'));
        ''')
        columns={r['name'] for r in c.execute('PRAGMA table_info(entities)')}
        if 'display_alias' not in columns:
            c.execute("ALTER TABLE entities ADD COLUMN display_alias TEXT NOT NULL DEFAULT ''")
        if 'created' not in columns:
            # Older releases did not record metadata creation times.
            c.execute('ALTER TABLE entities ADD COLUMN created TEXT')
        if 'sort_reading' not in columns:
            c.execute("ALTER TABLE entities ADD COLUMN sort_reading TEXT NOT NULL DEFAULT ''")
        c.execute('INSERT OR IGNORE INTO migrations VALUES(2,?)',(now(),))
        c.execute("UPDATE job_items SET status='pending' WHERE status='running'")
    migrate_imports()
    import features
    with transaction() as c: features.init(c)
    import marks
    with transaction() as c: marks.init(c)
    import tag_policy
    with transaction() as c: tag_policy.init(c)
    import import_jobs
    with transaction() as c: import_jobs.init(c)

def migrate_imports():
    """Rebuild works with foreign keys disabled only on this migration connection."""
    c=connect()
    try:
        if c.execute('SELECT 1 FROM migrations WHERE version=3').fetchone(): return
        if c.execute('SELECT 1 FROM works LIMIT 1').fetchone():
            backup(PATH.parent/'migration-backups')
        c.execute('PRAGMA foreign_keys=OFF'); c.execute('BEGIN IMMEDIATE')
        c.execute("CREATE TABLE works_new(id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES owners(id), title TEXT NOT NULL COLLATE BINARY, cover TEXT DEFAULT '', category TEXT DEFAULT '', language TEXT DEFAULT '', pages INTEGER CHECK(pages>=0), review TEXT DEFAULT '', bought INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL, updated TEXT NOT NULL, opened TEXT)")
        c.execute('INSERT INTO works_new SELECT id,owner,title,cover,category,language,pages,review,bought,created,updated,opened FROM works')
        c.execute('DROP TABLE works'); c.execute('ALTER TABLE works_new RENAME TO works')
        for name,column in [('works_created','created'),('works_opened','opened'),('works_title','title')]:
            c.execute(f'CREATE INDEX {name} ON works(owner,{column})')
        c.execute("ALTER TABLE links ADD COLUMN url_key TEXT NOT NULL DEFAULT ''")
        for r in c.execute('SELECT id,url FROM links').fetchall():
            c.execute('UPDATE links SET url_key=? WHERE id=?',(normalize_url(r['url']),r['id']))
        c.execute('CREATE INDEX link_key ON links(url_key,work_id)')
        c.execute('CREATE TABLE source_claims(owner TEXT NOT NULL REFERENCES owners(id), url_key TEXT NOT NULL, work_id TEXT NOT NULL REFERENCES works(id) ON DELETE CASCADE, PRIMARY KEY(owner,url_key))')
        c.execute('INSERT INTO source_claims SELECT w.owner,l.url_key,min(w.id) FROM links l JOIN works w ON w.id=l.work_id GROUP BY w.owner,l.url_key')
        c.execute("ALTER TABLE jobs ADD COLUMN title_mode TEXT NOT NULL DEFAULT 'source'")
        c.execute("ALTER TABLE job_items ADD COLUMN warnings_json TEXT NOT NULL DEFAULT '{}'")
        c.execute("CREATE TABLE work_imports(id TEXT PRIMARY KEY, work_id TEXT NOT NULL REFERENCES works(id) ON DELETE CASCADE, item_id TEXT UNIQUE, source_url TEXT NOT NULL, bookmark_name TEXT NOT NULL, source_title TEXT NOT NULL DEFAULT '', folder TEXT NOT NULL DEFAULT '', title_mode TEXT NOT NULL, imported_at TEXT NOT NULL)")
        c.execute('CREATE INDEX work_import_history ON work_imports(work_id)')
        c.execute("INSERT INTO work_imports SELECT i.id,i.work_id,i.id,i.url,i.label,i.title,i.folder,'source',j.created FROM job_items i JOIN jobs j ON j.id=i.job_id JOIN works w ON w.id=i.work_id WHERE i.status='added' AND trim(i.label)<>''")
        if c.execute('PRAGMA foreign_key_check').fetchone() or c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            raise ValueError('Import migration integrity check failed')
        c.execute('INSERT INTO migrations VALUES(3,?)',(now(),)); c.commit()
    except Exception:
        c.rollback(); raise
    finally: c.close()

def url(value):
    value = str(value or '').strip()
    if not value: return ''
    normalize_url(value)
    return value

class DuplicateSource(ValueError):
    def __init__(self,matches):
        super().__init__('Source URL already registered'); self.matches=matches

def work_summary(c,row):
    out=dict(row)
    primary=c.execute('SELECT url FROM links WHERE work_id=? ORDER BY is_primary DESC,position LIMIT 1',(out['id'],)).fetchone()
    out['primary_url']=primary[0] if primary else ''
    out['authors']=[r[0] for r in c.execute("SELECT COALESCE(NULLIF(e.display_alias,''),e.name) FROM entities e JOIN work_entities we ON we.entity_id=e.id WHERE we.work_id=? AND e.kind='author' ORDER BY e.name",(out['id'],))]
    return out

def title_matches(c,title,exclude=''):
    import import_matching
    return import_matching.title_matches(c,[title],exclude)

def exact_sources(c,value,exclude=''):
    key=normalize_url(value)
    if not key: return []
    rows=c.execute('SELECT w.id,w.title,w.deleted_at,min(l.url) AS source_url FROM links l JOIN works w ON w.id=l.work_id WHERE w.owner=? AND l.url_key=? AND w.id<>? GROUP BY w.id ORDER BY w.title,w.id',(OWNER,key,exclude))
    return [work_summary(c,r) for r in rows]

def dimensions(c):
    return [dict(r) for r in c.execute('SELECT * FROM dimensions WHERE owner=? ORDER BY number',(OWNER,))]

def source_matches(c,value):
    """Read-only lookup across every source link; never fetch the source."""
    import importer
    value=url(value)
    if len(value)>4096: raise ValueError('Source URL is too long')
    identity=importer.source_identity(value)
    if not identity: raise ValueError('Use a Hitomi, nhentai or momon-ga work URL')
    gid=identity[1]
    exact={r['id']:r for r in exact_sources(c,value)}; related={}
    for row in c.execute('SELECT w.id,w.title,w.deleted_at,l.url FROM works w JOIN links l ON l.work_id=w.id WHERE w.owner=? AND instr(l.url,?)>0 ORDER BY w.title,w.id,l.position',(OWNER,gid)):
        if importer.source_identity(row['url'])!=identity: continue
        item=work_summary(c,{'id':row['id'],'title':row['title'],'source_url':row['url'],'deleted_at':row['deleted_at']})
        related[row['id']]=item
    return {'url':value,'match':'exact' if exact else 'gallery' if related else 'none','matches':list((exact or related).values())}

def entity_data(c,row):
    out=dict(row)
    out['aliases']=[a[0] for a in c.execute('SELECT name FROM aliases WHERE entity_id=? ORDER BY name',(out['id'],))]
    out['display_name']=out['display_alias'] or out['name']
    return out

def entity_list(c,kind=None,q='',sort='name_asc',offset=0,limit=300,paged=False):
    where='e.owner=?'
    args=[OWNER]
    if kind: where+=' AND e.kind=?'; args.append(kind)
    if q:
        where+=' AND (instr(fold(e.name),?)>0 OR EXISTS(SELECT 1 FROM aliases a WHERE a.entity_id=e.id AND instr(fold(a.name),?)>0))'
        args += [q.casefold(),q.casefold()]
    sort_name="metadata_key(COALESCE(NULLIF(e.sort_reading,''),display_name))"
    order={'name_asc':sort_name+' ASC','name_desc':sort_name+' DESC',
           'uses_desc':'uses DESC','uses_asc':'uses ASC',
           'newest':'e.created IS NULL ASC,e.created DESC,e.rowid DESC',
           'oldest':'e.created IS NOT NULL ASC,e.created ASC,e.rowid ASC'}.get(sort)
    if not order: raise ValueError('Invalid metadata sort')
    sql="SELECT e.*, COALESCE(NULLIF(e.display_alias,''),e.name) AS display_name, (SELECT count(*) FROM work_entities we JOIN works w ON w.id=we.work_id WHERE we.entity_id=e.id AND w.deleted_at IS NULL) AS uses FROM entities e WHERE "+where
    rows=[entity_data(c,r) for r in c.execute(sql+' ORDER BY '+order+',metadata_key(display_name),e.gender,e.id LIMIT ? OFFSET ?',args+[min(300,max(1,limit)),max(0,offset)])]
    if paged:
        return {'items':rows,'total':c.execute('SELECT count(*) FROM entities e WHERE '+where,args).fetchone()[0]}
    return rows

def save_entity(c,data,eid=None):
    kind=data.get('kind'); name=str(data.get('name','')).strip(); gender=data.get('gender','neutral') if kind=='tag' else 'neutral'
    if kind not in ('tag','author','circle','series','character') or not name: raise ValueError('Metadata needs a name and valid type')
    if gender == 'none': gender = 'neutral'
    if gender not in ('male','female','neutral'): raise ValueError('Invalid tag gender')
    eid=eid or uid()
    old=c.execute('SELECT * FROM entities WHERE id=? AND owner=?',(eid,OWNER)).fetchone()
    if old and old['kind']!=kind: raise ValueError('Metadata type cannot change')
    aliases=set(str(a).strip() for a in data.get('aliases',[]) if str(a).strip())
    display_alias=str(data.get('display_alias',old['display_alias'] if old else '')).strip()
    if display_alias and display_alias not in aliases:
        if 'display_alias' in data: raise ValueError('Choose a display alias from the aliases')
        display_alias=''
    sort_reading=str(data.get('sort_reading',old['sort_reading'] if old else '')).strip()
    c.execute('INSERT INTO entities(id,owner,kind,name,gender,display_alias,created,sort_reading) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,gender=excluded.gender,display_alias=excluded.display_alias,sort_reading=excluded.sort_reading',(eid,OWNER,kind,name,gender,display_alias,now(),sort_reading))
    c.execute('DELETE FROM aliases WHERE entity_id=?',(eid,))
    for a in aliases:
        c.execute('INSERT INTO aliases VALUES(?,?)',(eid,a))
    return eid

def resolve(c,kind,item):
    if isinstance(item,str): item={'name':item}
    import tag_policy
    if item.get('id'):
        item = dict(item, id=tag_policy.entity_id(c,item['id']))
        row=c.execute('SELECT * FROM entities WHERE id=? AND owner=? AND kind=?',(item['id'],OWNER,kind)).fetchone()
        if not row: raise ValueError('Unknown metadata item')
        return row['id']
    name=str(item.get('name','')).strip()
    if not name or name.casefold()=='n/a': return None
    gender=item.get('gender','neutral') if kind=='tag' else 'neutral'
    if gender == 'none': gender = 'neutral'
    if kind=='tag' and not item.get('literal_name'):
        choices=tag_policy.matches(c,name,gender)
        if len(choices)>1: raise ValueError('Ambiguous alias: '+name)
        if choices: return choices[0]['id']
        return save_entity(c,dict(item,kind=kind,gender=gender))
    row=c.execute('SELECT id FROM entities WHERE owner=? AND kind=? AND name=? AND gender=?',(OWNER,kind,name,gender)).fetchone()
    if row: return row[0]
    rows=[] if item.get('literal_name') else c.execute('SELECT DISTINCT e.id FROM entities e JOIN aliases a ON a.entity_id=e.id WHERE e.owner=? AND e.kind=? AND e.gender=? AND a.name=?',(OWNER,kind,gender,name)).fetchall()
    if len(rows)>1: raise ValueError('Ambiguous alias: '+name)
    if rows: return rows[0][0]
    return save_entity(c,dict(item,kind=kind))

def get_work(c,wid,opened=False,include_deleted=False):
    r=c.execute('SELECT * FROM works WHERE id=? AND owner=?',(wid,OWNER)).fetchone()
    if not r or r['deleted_at'] and not include_deleted: raise ValueError('Entry not found; check Trash')
    if opened:
        c.execute('UPDATE works SET opened=? WHERE id=?',(now(),wid))
        r=c.execute('SELECT * FROM works WHERE id=?',(wid,)).fetchone()
    out=dict(r)
    import marks
    out['marks']=marks.numbers(out['mark_bits'])
    for kind in ('author','circle','tag','series','character'):
        out[kind]=[entity_data(c,e) for e in c.execute("SELECT e.* FROM entities e JOIN work_entities we ON we.entity_id=e.id WHERE we.work_id=? AND e.kind=? ORDER BY metadata_key(COALESCE(NULLIF(display_alias,''),name)),e.gender,e.id",(wid,kind))]
    out['links']=[dict(l) for l in c.execute('SELECT * FROM links WHERE work_id=? ORDER BY position',(wid,))]
    out['ratings']={r['dimension_id']:r['value'] for r in c.execute('SELECT * FROM scores WHERE work_id=?',(wid,))}
    out['bookmark_names']=[r[0] for r in c.execute("SELECT DISTINCT bookmark_name FROM work_imports WHERE work_id=? AND trim(bookmark_name)<>'' ORDER BY bookmark_name",(wid,))]
    out['source_titles']=[r[0] for r in c.execute('SELECT title FROM work_titles WHERE work_id=? ORDER BY title',(wid,))] if c.execute("SELECT 1 FROM sqlite_master WHERE name='work_titles'").fetchone() else []
    return out

def save_work(c,data,wid=None):
    if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
    title=str(data.get('title','')).strip()
    if not title: raise ValueError('Title is required')
    wid=wid or uid(); stamp=now()
    previous_keys={r[0] for r in c.execute('SELECT url_key FROM links WHERE work_id=?',(wid,))}
    previous_urls={r[0] for r in c.execute('SELECT url FROM links WHERE work_id=?',(wid,))}
    prepared=[]; seen=set(); seen_raw=set()
    for l in data.get('links',[]):
        u=url(l.get('url'))
        if not u: continue
        key=normalize_url(u)
        if u in seen_raw or key in seen and u not in previous_urls: raise ValueError('Repeated source URL within entry')
        seen.add(key); seen_raw.add(u)
        matches=exact_sources(c,u,wid)
        if matches and key not in previous_keys: raise DuplicateSource(matches)
        prepared.append((l,u,key))
    if data.get('category','') not in ('',*CATEGORIES): raise ValueError('Invalid category')
    pages=data.get('pages')
    if pages is not None and (type(pages)!=int or pages<0): raise ValueError('Pages must be a nonnegative integer')
    import marks
    previous=c.execute('SELECT mark_bits FROM works WHERE id=?',(wid,)).fetchone()
    previous=previous[0] if previous else 0
    selected_marks=marks.bits(data['marks']) if 'marks' in data else (previous & 30) | int(bool(data.get('bought'))) if 'bought' in data else previous
    c.execute('INSERT INTO works(id,owner,title,cover,category,language,pages,review,bought,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,cover=excluded.cover,category=excluded.category,language=excluded.language,pages=excluded.pages,review=excluded.review,bought=excluded.bought,updated=excluded.updated',
        (wid,OWNER,title,url(data.get('cover')),data.get('category',''),str(data.get('language','')),pages,str(data.get('review','')),selected_marks & 1,stamp,stamp))
    c.execute('UPDATE works SET mark_bits=? WHERE id=?',(selected_marks,wid))
    c.execute('DELETE FROM work_entities WHERE work_id=?',(wid,))
    for kind in ('author','circle','tag','series','character'):
        for item in data.get(kind,[]):
            eid=resolve(c,kind,item)
            if eid: c.execute('INSERT OR IGNORE INTO work_entities VALUES(?,?)',(wid,eid))
    existing_link_ids={r[0] for r in c.execute('SELECT id FROM links WHERE work_id=?',(wid,))}
    c.execute('DELETE FROM links WHERE work_id=?',(wid,))
    selected=next((i for i,(l,u,key) in enumerate(prepared) if l.get('is_primary')),0)
    c.execute('DELETE FROM source_claims WHERE owner=? AND work_id=?',(OWNER,wid))
    for i,(l,u,key) in enumerate(prepared):
        lid=l.get('id') if l.get('id') in existing_link_ids else uid()
        c.execute('INSERT INTO links(id,work_id,url,label,position,is_primary,url_key) VALUES(?,?,?,?,?,?,?)',(lid,wid,u,str(l.get('label','')),i,int(i==selected),key))
        c.execute('INSERT OR IGNORE INTO source_claims VALUES(?,?,?)',(OWNER,key,wid))
    for key in previous_keys-seen:
        row=c.execute('SELECT min(w.id) FROM links l JOIN works w ON w.id=l.work_id WHERE w.owner=? AND l.url_key=?',(OWNER,key)).fetchone()
        if row[0]: c.execute('INSERT OR IGNORE INTO source_claims VALUES(?,?,?)',(OWNER,key,row[0]))
    if seen and not c.execute('SELECT 1 FROM links WHERE work_id=? AND is_primary=1',(wid,)).fetchone():
        c.execute('UPDATE links SET is_primary=1 WHERE id=(SELECT id FROM links WHERE work_id=? ORDER BY position LIMIT 1)',(wid,))
    c.execute('DELETE FROM scores WHERE work_id=?',(wid,))
    dims={d['id']:d for d in dimensions(c)}
    for did,value in data.get('ratings',{}).items():
        if value is None: continue
        if did not in dims or type(value)!=int or not 1<=value<=dims[did]['maximum']: raise ValueError('Invalid rating score')
        c.execute('INSERT INTO scores VALUES(?,?,?)',(wid,did,value))
    import import_matching
    if c.execute("SELECT 1 FROM sqlite_master WHERE name='work_titles'").fetchone():
        import_matching.record_titles(c,wid,[title])
        # A browser may retain title variants only alongside a supported source.
        import importer
        if any(importer.source_identity(u) for _,u,_ in prepared):
            import_matching.record_titles(c,wid,data.get('source_titles',[]))
    return dict(get_work(c,wid),warnings=[])

def record_bookmark(c,wid,item,source_title,mode):
    c.execute('INSERT OR IGNORE INTO work_imports VALUES(?,?,?,?,?,?,?,?,?)',(uid(),wid,item['id'],item['url'],str(item.get('label','')),source_title,str(item.get('folder','')),mode,now()))

def purge_work(c,wid):
    if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
    keys=[r[0] for r in c.execute('SELECT url_key FROM links WHERE work_id=?',(wid,))]
    c.execute('DELETE FROM works WHERE id=? AND owner=?',(wid,OWNER))
    for key in keys:
        row=c.execute('SELECT min(w.id) FROM links l JOIN works w ON w.id=l.work_id WHERE w.owner=? AND l.url_key=?',(OWNER,key)).fetchone()
        if row[0]: c.execute('INSERT OR IGNORE INTO source_claims VALUES(?,?,?)',(OWNER,key,row[0]))

def list_works(c,q='',sort='newest',offset=0,limit=40,seed='0',random_one=False):
    dims={d['number']:d for d in dimensions(c)}
    condition,args=compile_query(q,dims,OWNER)
    where='w.owner=? AND w.deleted_at IS NULL AND '+condition; args=[OWNER]+args
    total=c.execute('SELECT count(*) FROM works w WHERE '+where,args).fetchone()[0]
    order={'newest':'w.created DESC','oldest':'w.created ASC','recent':'w.opened IS NULL,w.opened DESC','least':'w.opened IS NOT NULL,w.opened ASC','random':'shuffle(w.id,?)'}.get(sort,'w.created DESC')
    sortargs=[]
    if sort=='random': sortargs=[seed]
    if sort.startswith('rating') and sort[6:].isdigit() and int(sort[6:]) in dims:
        order='(SELECT value FROM scores WHERE work_id=w.id AND dimension_id=?) DESC'
        sortargs=[dims[int(sort[6:])]['id']]
    if random_one:
        import secrets
        if not total: return {'total':0,'items':[]}
        offset=secrets.randbelow(total); limit=1; order='w.id'; sortargs=[]
    ids=[r[0] for r in c.execute('SELECT w.id FROM works w WHERE '+where+' ORDER BY '+order+',w.id LIMIT ? OFFSET ?',args+sortargs+[limit,offset])]
    return {'total':total,'items':[get_work(c,i) for i in ids]}

def convert_score(value,old_maximum,new_maximum):
    """Keep 1 and full marks; exact half ties round down, using integers."""
    if old_maximum==new_maximum: return value
    if value==old_maximum: return new_maximum
    whole,remainder=divmod((value-1)*(new_maximum-1),old_maximum-1)
    return min(new_maximum-1,1+whole+int(2*remainder>old_maximum-1))

def dimension_preview(c,did,maximum):
    if type(maximum)!=int or not 2<=maximum<=10: raise ValueError('Invalid rating dimension')
    dimension=c.execute('SELECT * FROM dimensions WHERE id=? AND owner=?',(did,OWNER)).fetchone()
    if not dimension: raise ValueError('Dimension not found')
    counts={r['value']:r['count'] for r in c.execute('SELECT value,count(*) AS count FROM scores WHERE dimension_id=? GROUP BY value',(did,))}
    old=dimension['maximum']
    rows=[{'old':value,'new':convert_score(value,old,maximum),'count':counts.get(value,0)} for value in range(1,old+1)]
    signature=hashlib.sha256(json.dumps([did,old,maximum,rows],sort_keys=True).encode()).hexdigest()
    return {'old_maximum':old,'maximum':maximum,'rows':rows,'rated':sum(counts.values()),
            'changed':sum(r['count'] for r in rows if r['old']!=r['new']),'signature':signature}

def save_dimension(c,data,did=None):
    name=str(data.get('name','')).strip(); maximum=data.get('maximum'); symbol=data.get('symbol','Star')
    if not name or type(maximum)!=int or not 2<=maximum<=10 or symbol not in SYMBOLS: raise ValueError('Invalid rating dimension')
    if did:
        # Reserve the write transaction before reading the scale or scores.
        if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
        preview=dimension_preview(c,did,maximum)
        expected=data.get('conversion_signature')
        if expected is not None and expected!=preview['signature']:
            raise ValueError('Rating scores or scale changed; preview the conversion again')
        if preview['old_maximum']!=maximum:
            if expected is None: raise ValueError('Preview the rating conversion before saving')
            # A single CASE update avoids converting already-updated values twice.
            cases=' '.join('WHEN ? THEN ?' for r in preview['rows'])
            args=[v for r in preview['rows'] for v in (r['old'],r['new'])]
            c.execute('UPDATE scores SET value=CASE value '+cases+' ELSE value END WHERE dimension_id=?',args+[did])
        c.execute('UPDATE dimensions SET name=?,maximum=?,symbol=?,gallery=? WHERE id=?',(name,maximum,symbol,int(bool(data.get('gallery'))),did))
    else:
        did=uid(); number=c.execute('SELECT next_rating FROM owners WHERE id=?',(OWNER,)).fetchone()[0]
        c.execute('UPDATE owners SET next_rating=next_rating+1 WHERE id=?',(OWNER,))
        c.execute('INSERT INTO dimensions VALUES(?,?,?,?,?,?,?)',(did,OWNER,number,name,maximum,symbol,int(bool(data.get('gallery')))))
    return did

def merge(c,source,target):
    import tag_policy
    return tag_policy.merge(c,source,target)

def backup(destination=None):
    dest=Path(destination or os.environ.get('MEDIA_BACKUPS',str(ROOT/'backups'))); dest.mkdir(parents=True,exist_ok=True)
    path=dest/('library-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.sqlite3')
    source=connect(); target=sqlite3.connect(path)
    try: source.backup(target)
    finally: target.close(); source.close()
    for p in sorted(dest.glob('library-*.sqlite3'))[:-7]: p.unlink()
    return path


def delete_work(c,wid):
    import features
    features.trash(c,wid)
