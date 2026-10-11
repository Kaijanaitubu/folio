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

def url(value):
    value = str(value or '').strip()
    if not value: return ''
    try: u = urlsplit(value)
    except ValueError: raise ValueError('Invalid URL')
    if u.scheme not in ('http','https') or not u.hostname or u.username or u.password:
        raise ValueError('Use an HTTP or HTTPS URL without credentials')
    return value

def dimensions(c):
    return [dict(r) for r in c.execute('SELECT * FROM dimensions WHERE owner=? ORDER BY number',(OWNER,))]

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
    sql="SELECT e.*, COALESCE(NULLIF(e.display_alias,''),e.name) AS display_name, (SELECT count(*) FROM work_entities WHERE entity_id=e.id) AS uses FROM entities e WHERE "+where
    rows=[entity_data(c,r) for r in c.execute(sql+' ORDER BY '+order+',metadata_key(display_name),e.gender,e.id LIMIT ? OFFSET ?',args+[min(300,max(1,limit)),max(0,offset)])]
    if paged:
        return {'items':rows,'total':c.execute('SELECT count(*) FROM entities e WHERE '+where,args).fetchone()[0]}
    return rows

def save_entity(c,data,eid=None):
    kind=data.get('kind'); name=str(data.get('name','')).strip(); gender=data.get('gender','neutral') if kind=='tag' else 'neutral'
    if kind not in ('tag','author','circle','series','character') or not name: raise ValueError('Metadata needs a name and valid type')
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
    if item.get('id'):
        row=c.execute('SELECT * FROM entities WHERE id=? AND owner=? AND kind=?',(item['id'],OWNER,kind)).fetchone()
        if not row: raise ValueError('Unknown metadata item')
        return row['id']
    name=str(item.get('name','')).strip()
    if not name or name.casefold()=='n/a': return None
    gender=item.get('gender','neutral') if kind=='tag' else 'neutral'
    row=c.execute('SELECT id FROM entities WHERE owner=? AND kind=? AND name=? AND gender=?',(OWNER,kind,name,gender)).fetchone()
    if row: return row[0]
    rows=c.execute('SELECT DISTINCT e.id FROM entities e JOIN aliases a ON a.entity_id=e.id WHERE e.owner=? AND e.kind=? AND e.gender=? AND a.name=?',(OWNER,kind,gender,name)).fetchall()
    if len(rows)>1: raise ValueError('Ambiguous alias: '+name)
    if rows: return rows[0][0]
    return save_entity(c,dict(item,kind=kind))

def get_work(c,wid,opened=False):
    r=c.execute('SELECT * FROM works WHERE id=? AND owner=?',(wid,OWNER)).fetchone()
    if not r: raise ValueError('Entry not found')
    if opened:
        c.execute('UPDATE works SET opened=? WHERE id=?',(now(),wid))
        r=c.execute('SELECT * FROM works WHERE id=?',(wid,)).fetchone()
    out=dict(r)
    for kind in ('author','circle','tag','series','character'):
        out[kind]=[entity_data(c,e) for e in c.execute("SELECT e.* FROM entities e JOIN work_entities we ON we.entity_id=e.id WHERE we.work_id=? AND e.kind=? ORDER BY metadata_key(COALESCE(NULLIF(display_alias,''),name)),e.gender,e.id",(wid,kind))]
    out['links']=[dict(l) for l in c.execute('SELECT * FROM links WHERE work_id=? ORDER BY position',(wid,))]
    out['ratings']={r['dimension_id']:r['value'] for r in c.execute('SELECT * FROM scores WHERE work_id=?',(wid,))}
    return out

def save_work(c,data,wid=None):
    title=str(data.get('title','')).strip()
    if not title: raise ValueError('Title is required')
    wid=wid or uid(); stamp=now()
    if data.get('category','') not in ('',*CATEGORIES): raise ValueError('Invalid category')
    pages=data.get('pages')
    if pages is not None and (type(pages)!=int or pages<0): raise ValueError('Pages must be a nonnegative integer')
    c.execute('INSERT INTO works(id,owner,title,cover,category,language,pages,review,bought,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,cover=excluded.cover,category=excluded.category,language=excluded.language,pages=excluded.pages,review=excluded.review,bought=excluded.bought,updated=excluded.updated',
        (wid,OWNER,title,url(data.get('cover')),data.get('category',''),str(data.get('language','')),pages,str(data.get('review','')),int(bool(data.get('bought'))),stamp,stamp))
    c.execute('DELETE FROM work_entities WHERE work_id=?',(wid,))
    for kind in ('author','circle','tag','series','character'):
        for item in data.get(kind,[]):
            eid=resolve(c,kind,item)
            if eid: c.execute('INSERT OR IGNORE INTO work_entities VALUES(?,?)',(wid,eid))
    existing_link_ids={r[0] for r in c.execute('SELECT id FROM links WHERE work_id=?',(wid,))}
    c.execute('DELETE FROM links WHERE work_id=?',(wid,))
    links=data.get('links',[]); seen=set(); selected=next((i for i,l in enumerate(links) if l.get('is_primary')),0)
    for i,l in enumerate(links):
        u=url(l.get('url'))
        if not u: continue
        if u in seen: raise ValueError('Repeated source URL within entry')
        seen.add(u)
        lid=l.get('id') if l.get('id') in existing_link_ids else uid()
        c.execute('INSERT INTO links VALUES(?,?,?,?,?,?)',(lid,wid,u,str(l.get('label','')),i,int(i==selected)))
    if seen and not c.execute('SELECT 1 FROM links WHERE work_id=? AND is_primary=1',(wid,)).fetchone():
        c.execute('UPDATE links SET is_primary=1 WHERE id=(SELECT id FROM links WHERE work_id=? ORDER BY position LIMIT 1)',(wid,))
    c.execute('DELETE FROM scores WHERE work_id=?',(wid,))
    dims={d['id']:d for d in dimensions(c)}
    for did,value in data.get('ratings',{}).items():
        if value is None: continue
        if did not in dims or type(value)!=int or not 1<=value<=dims[did]['maximum']: raise ValueError('Invalid rating score')
        c.execute('INSERT INTO scores VALUES(?,?,?)',(wid,did,value))
    warnings=[r[0] for r in c.execute('SELECT DISTINCT w.title FROM links l JOIN works w ON w.id=l.work_id WHERE l.url IN (SELECT url FROM links WHERE work_id=?) AND w.id<>? AND w.owner=?',(wid,wid,OWNER))]
    return dict(get_work(c,wid),warnings=warnings)

def list_works(c,q='',sort='newest',offset=0,limit=40,seed='0',random_one=False):
    dims={d['number']:d for d in dimensions(c)}
    condition,args=compile_query(q,dims)
    where='w.owner=? AND '+condition; args=[OWNER]+args
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

def save_dimension(c,data,did=None):
    name=str(data.get('name','')).strip(); maximum=data.get('maximum'); symbol=data.get('symbol','Star')
    if not name or type(maximum)!=int or not 2<=maximum<=10 or symbol not in SYMBOLS: raise ValueError('Invalid rating dimension')
    if did:
        if not c.execute('SELECT 1 FROM dimensions WHERE id=? AND owner=?',(did,OWNER)).fetchone(): raise ValueError('Dimension not found')
        if c.execute('SELECT 1 FROM scores WHERE dimension_id=? AND value>?',(did,maximum)).fetchone(): raise ValueError('Clear or lower scores above the new maximum first')
        c.execute('UPDATE dimensions SET name=?,maximum=?,symbol=?,gallery=? WHERE id=?',(name,maximum,symbol,int(bool(data.get('gallery'))),did))
    else:
        did=uid(); number=c.execute('SELECT next_rating FROM owners WHERE id=?',(OWNER,)).fetchone()[0]
        c.execute('UPDATE owners SET next_rating=next_rating+1 WHERE id=?',(OWNER,))
        c.execute('INSERT INTO dimensions VALUES(?,?,?,?,?,?,?)',(did,OWNER,number,name,maximum,symbol,int(bool(data.get('gallery')))))
    return did

def merge(c,source,target):
    a=c.execute('SELECT * FROM entities WHERE id=? AND owner=?',(source,OWNER)).fetchone()
    b=c.execute('SELECT * FROM entities WHERE id=? AND owner=?',(target,OWNER)).fetchone()
    if not a or not b or source==target or (a['kind'],a['gender'])!=(b['kind'],b['gender']): raise ValueError('Choose different metadata of the same type and gender')
    c.execute('INSERT OR IGNORE INTO work_entities SELECT work_id,? FROM work_entities WHERE entity_id=?',(target,source))
    c.execute('INSERT OR IGNORE INTO aliases SELECT ?,name FROM aliases WHERE entity_id=?',(target,source))
    c.execute('INSERT OR IGNORE INTO aliases VALUES(?,?)',(target,a['name']))
    c.execute('DELETE FROM entities WHERE id=?',(source,))

def backup(destination=None):
    dest=Path(destination or os.environ.get('MEDIA_BACKUPS',str(ROOT/'backups'))); dest.mkdir(parents=True,exist_ok=True)
    path=dest/('library-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.sqlite3')
    source=connect(); target=sqlite3.connect(path)
    try: source.backup(target)
    finally: target.close(); source.close()
    for p in sorted(dest.glob('library-*.sqlite3'))[:-7]: p.unlink()
    return path
