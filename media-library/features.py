"""Personal-library recovery, saved searches and atomic batch changes."""
import datetime as dt
import hashlib
import json
import db
import tag_policy
from search import compile_query

KINDS = ('author', 'circle', 'tag', 'series', 'character')
FIELDS = ('title', 'cover', 'category', 'language', 'pages', 'review', 'bought', 'marks', *KINDS, 'links', 'ratings')

def init(c):
    if 'deleted_at' not in {r['name'] for r in c.execute('PRAGMA table_info(works)')}:
        c.execute('ALTER TABLE works ADD COLUMN deleted_at TEXT')
    c.executescript('''
    CREATE INDEX IF NOT EXISTS works_deleted ON works(owner,deleted_at);
    CREATE TABLE IF NOT EXISTS operation_history(id TEXT PRIMARY KEY, owner TEXT NOT NULL, kind TEXT NOT NULL, created TEXT NOT NULL, payload TEXT NOT NULL, undone TEXT);
    CREATE TABLE IF NOT EXISTS saved_searches(id TEXT PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL, query TEXT NOT NULL, sort TEXT NOT NULL, position INTEGER NOT NULL, updated TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS batch_previews(id TEXT PRIMARY KEY, owner TEXT NOT NULL, created TEXT NOT NULL, payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS trash_snapshots(work_id TEXT PRIMARY KEY REFERENCES works(id) ON DELETE CASCADE, payload TEXT NOT NULL);
    ''')

def cleanup(c):
    if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
    cutoff=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=30)).isoformat()
    for row in c.execute('SELECT id FROM works WHERE owner=? AND deleted_at<?',(db.OWNER,cutoff)).fetchall():
        db.purge_work(c,row['id'])
    c.execute('DELETE FROM operation_history WHERE owner=? AND created<?',(db.OWNER,cutoff))
    c.execute('DELETE FROM batch_previews WHERE created<?',((dt.datetime.now(dt.timezone.utc)-dt.timedelta(minutes=15)).isoformat(),))

def state(c,wid):
    w=db.get_work(c,wid,include_deleted=True)
    out={k:w[k] for k in FIELDS}
    for k in KINDS: out[k]=sorted(e['id'] for e in out[k])
    out['links']=[{k:l[k] for k in ('url','label','is_primary')} for l in out['links']]
    out['deleted_at']=w['deleted_at']
    return out

def record(c,kind,payload):
    ident=db.uid()
    c.execute('INSERT INTO operation_history VALUES(?,?,?,?,?,NULL)',(ident,db.OWNER,kind,db.now(),json.dumps(payload,ensure_ascii=False)))
    return ident

def changes(before,after):
    delta={k:{'before':before[k],'after':after[k]} for k in before if before[k]!=after[k]}
    if 'marks' in delta: delta.pop('bought',None)
    return delta

def save_work(c,data,wid=None):
    if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
    before=state(c,wid) if wid else None
    if before and before['deleted_at']: raise ValueError('Restore this entry from Trash before editing')
    if wid and data.get('updated'):
        old=c.execute('SELECT updated FROM works WHERE id=?',(wid,)).fetchone()[0]
        if old!=data['updated']: raise ValueError('Entry changed on another device; reload before saving')
    result=db.save_work(c,data,wid)
    if before:
        delta=changes(before,state(c,wid))
        if delta: record(c,'edit',{'works':{wid:delta},'titles':[result['title']]})
    return result

def trash(c,wid):
    if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
    w=db.get_work(c,wid)
    c.execute('INSERT OR REPLACE INTO trash_snapshots VALUES(?,?)',(wid,json.dumps({'entities':{e['id']:e['name'] for k in KINDS for e in w[k]},'dimensions':{d['id']:d['name'] for d in db.dimensions(c) if d['id'] in w['ratings']}},ensure_ascii=False)))
    c.execute('UPDATE works SET deleted_at=?,updated=? WHERE id=?',(db.now(),db.now(),wid))

def batch_trash(c,data):
    """Move a frozen explicit selection to Trash, together or not at all."""
    ids=data.get('ids')
    if not isinstance(ids,list) or not ids or any(not isinstance(wid,str) or not wid for wid in ids):
        raise ValueError('Select at least one entry')
    ids=sorted(set(ids))
    if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
    active={r[0] for r in c.execute('SELECT id FROM works WHERE owner=? AND deleted_at IS NULL',(db.OWNER,))}
    if not set(ids)<=active: raise ValueError('Selected entries changed; reload before deleting')
    for wid in ids: trash(c,wid)
    return {'deleted':len(ids)}

def trash_list(c):
    return [db.get_work(c,r['id'],include_deleted=True) for r in c.execute('SELECT id FROM works WHERE owner=? AND deleted_at IS NOT NULL ORDER BY deleted_at DESC',(db.OWNER,))]

def restore_preview(c,ids):
    if not isinstance(ids,list) or not ids: raise ValueError('Select entries to restore')
    missing=[]; states=[]
    for wid in set(ids):
        w=db.get_work(c,wid,include_deleted=True)
        if not w['deleted_at']: raise ValueError('Entry is no longer in Trash')
        names=[]; row=c.execute('SELECT payload FROM trash_snapshots WHERE work_id=?',(wid,)).fetchone()
        if row:
            snapshot=json.loads(row[0])
            for table,key in [('entities','entities'),('dimensions','dimensions')]:
                for ident,name in snapshot[key].items():
                    if table=='entities': ident=tag_policy.entity_id(c,ident)
                    if not c.execute('SELECT 1 FROM '+table+' WHERE id=? AND owner=?',(ident,db.OWNER)).fetchone(): names.append(name)
        if names: missing.append({'id':wid,'title':w['title'],'names':names})
        states.append([wid,state(c,wid),names])
    signature=hashlib.sha256(json.dumps(sorted(states),sort_keys=True).encode()).hexdigest()
    return {'missing':missing,'signature':signature}

def restore(c,ids,signature=None):
    if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
    preview=restore_preview(c,ids)
    if signature is not None and signature!=preview['signature']: raise ValueError('Trash information changed; preview restore again')
    if preview['missing'] and signature is None: raise ValueError('Preview missing information before restoring')
    for wid in set(ids): c.execute('UPDATE works SET deleted_at=NULL,updated=? WHERE id=?',(db.now(),wid))
    for wid in set(ids): c.execute('DELETE FROM trash_snapshots WHERE work_id=?',(wid,))
    return {'restored':len(set(ids))}

def scale_state(c,did):
    d=c.execute('SELECT maximum FROM dimensions WHERE id=? AND owner=?',(did,db.OWNER)).fetchone()
    if not d: raise ValueError('Rating dimension no longer exists')
    return {'maximum':d[0],'scores':{r['work_id']:r['value'] for r in c.execute('SELECT * FROM scores WHERE dimension_id=? ORDER BY work_id',(did,))}}

def save_dimension(c,data,did=None):
    if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
    before=scale_state(c,did) if did else None
    result=db.save_dimension(c,data,did)
    if before and before['maximum']!=data['maximum']:
        record(c,'rating_scale',{'dimension':did,'before':before,'after':scale_state(c,did)})
    return result

def history(c):
    rows=[]
    for r in c.execute('SELECT id,kind,created,undone,payload FROM operation_history WHERE owner=? ORDER BY created DESC',(db.OWNER,)):
        item=dict(r); payload=json.loads(item.pop('payload'))
        item['count']=payload['before']['count'] if item['kind']=='metadata_merge' else len(payload.get('works',payload.get('before',{}).get('scores',{})))
        item['titles']=payload.get('titles',[])[:5]; item['dimension']=payload.get('dimension')
        if item['kind']=='metadata_merge': item['merge']={'source':payload['before']['source'],'target':payload['before']['target']}
        item['fields']=[payload['before']['source']['kind']] if item['kind']=='metadata_merge' else sorted({k for delta in payload.get('works',{}).values() for k in delta})
        if item['dimension']:
            d=c.execute('SELECT name,number FROM dimensions WHERE id=?',(item['dimension'],)).fetchone()
            item['scale']={'name':d['name'] if d else '', 'number':d['number'] if d else None,'before':payload['before']['maximum'],'after':payload['after']['maximum']}
        rows.append(item)
    return rows

def undo(c,ident,apply=False):
    if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
    r=c.execute('SELECT * FROM operation_history WHERE id=? AND owner=?',(ident,db.OWNER)).fetchone()
    if not r or r['undone']: raise ValueError('Operation is unavailable or already undone')
    p=json.loads(r['payload'])
    if r['kind']=='metadata_merge':
        result=tag_policy.undo_merge(c,p,apply)
        if apply: c.execute('UPDATE operation_history SET undone=? WHERE id=?',(db.now(),ident))
        return result
    if r['kind']=='rating_scale':
        if scale_state(c,p['dimension'])!=p['after']: raise ValueError('Ratings changed after this operation; undo was cancelled')
        if apply:
            c.execute('UPDATE dimensions SET maximum=? WHERE id=?',(p['before']['maximum'],p['dimension']))
            c.execute('DELETE FROM scores WHERE dimension_id=?',(p['dimension'],))
            c.executemany('INSERT INTO scores VALUES(?,?,?)',[(wid,p['dimension'],v) for wid,v in p['before']['scores'].items()])
    else:
        prepared=[]
        for wid,delta in p['works'].items():
            current=state(c,wid)
            if current['deleted_at']: raise ValueError('Restore affected entries from Trash before undoing')
            def canonical(k,value):
                return sorted({tag_policy.entity_id(c,eid) for eid in value}) if k in KINDS else value
            if any(current[k]!=canonical(k,v['after']) for k,v in delta.items()): raise ValueError('Affected fields changed after this operation; undo was cancelled')
            w=db.get_work(c,wid)
            for k,v in delta.items():
                value=v['before']
                if k in KINDS:
                    value=canonical(k,value)
                    for eid in value:
                        if not c.execute('SELECT 1 FROM entities WHERE id=? AND owner=?',(eid,db.OWNER)).fetchone(): raise ValueError('Required metadata was deleted; undo is unavailable')
                    value=[{'id':eid} for eid in value]
                w[k]=value
                if k=='bought' and 'marks' not in delta:
                    w['marks']=sorted((set(w['marks'])-{1})|({1} if value else set()))
            # Validates missing dimensions / changed scales before any writes.
            dims={d['id']:d['maximum'] for d in db.dimensions(c)}
            if any(did not in dims or not 1<=v<=dims[did] for did,v in w['ratings'].items()): raise ValueError('Rating scale changed; undo is unavailable')
            prepared.append((wid,w))
        if apply:
            for wid,w in prepared: db.save_work(c,w,wid)
    if apply: c.execute('UPDATE operation_history SET undone=? WHERE id=?',(db.now(),ident))
    details=[]
    for wid,delta in list(p.get('works',{}).items())[:20]:
        details.append({'title':db.get_work(c,wid)['title'],'fields':list(delta)})
    return {'ok':True,'kind':r['kind'],'count':len(p.get('works',p.get('before',{}).get('scores',{}))), 'details':details,'scale':{'before':p['before']['maximum'],'after':p['after']['maximum']} if r['kind']=='rating_scale' else None}

def searches(c):
    result=[]; dims={d['number']:d for d in db.dimensions(c)}
    for row in c.execute('SELECT * FROM saved_searches WHERE owner=? ORDER BY position,id',(db.OWNER,)):
        item=dict(row)
        try:
            compile_query(item['query'],dims,db.OWNER)
            valid_sort(item['sort'],dims)
            item['error']=''
        except ValueError as e: item['error']=str(e)
        result.append(item)
    return result

def valid_sort(sort,dims):
    if sort not in ('newest','oldest','recent','least','random') and sort not in {'rating'+str(n) for n in dims}: raise ValueError('Saved sort refers to an unavailable rating dimension')

def save_search(c,data,ident=None):
    name=str(data.get('name','')).strip(); query=str(data.get('query','')).strip(); sort=data.get('sort','newest')
    if not name or len(name)>200 or len(query)>4096: raise ValueError('Enter a search name (up to 200 characters) and a valid query')
    dims={d['number']:d for d in db.dimensions(c)}
    compile_query(query,dims,db.OWNER); valid_sort(sort,dims)
    old=c.execute('SELECT * FROM saved_searches WHERE id=? AND owner=?',(ident,db.OWNER)).fetchone() if ident else None
    if ident and not old: raise ValueError('Saved search not found')
    position=data.get('position',old['position'] if old else c.execute('SELECT COALESCE(max(position),0)+10 FROM saved_searches WHERE owner=?',(db.OWNER,)).fetchone()[0])
    if type(position)!=int: raise ValueError('Invalid search position')
    ident=ident or db.uid()
    c.execute('INSERT INTO saved_searches VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,query=excluded.query,sort=excluded.sort,position=excluded.position,updated=excluded.updated',(ident,db.OWNER,name,query,sort,position,db.now()))
    return {'id':ident}

def reorder_searches(c,ids):
    if not isinstance(ids,list): raise ValueError('Invalid saved search order')
    if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
    current={r[0] for r in c.execute('SELECT id FROM saved_searches WHERE owner=?',(db.OWNER,))}
    if len(set(ids))!=len(ids) or set(ids)!=current: raise ValueError('Saved searches changed; reload before reordering')
    for i,ident in enumerate(ids): c.execute('UPDATE saved_searches SET position=? WHERE id=? AND owner=?',(i*10,ident,db.OWNER))
    return {'ok':True}

def batch_targets(c,data):
    if data.get('all'):
        dims={d['number']:d for d in db.dimensions(c)}
        condition,args=compile_query(data.get('query',''),dims,db.OWNER)
        return [r[0] for r in c.execute('SELECT w.id FROM works w WHERE w.owner=? AND w.deleted_at IS NULL AND '+condition+' ORDER BY w.id',[db.OWNER]+args)]
    ids=data.get('ids',[])
    if not isinstance(ids,list): raise ValueError('Invalid selection')
    return sorted(set(ids))

def batch_values(c,w,patch):
    if not isinstance(patch,dict) or set(patch)-set((*KINDS,'ratings','bought','marks','category','language')): raise ValueError('Unsupported batch field')
    if 'marks' in patch and 'bought' in patch: raise ValueError('Choose marks or legacy purchase status, not both')
    for k,spec in patch.items():
        if k in KINDS:
            mode=spec.get('mode'); values=spec.get('items',[])
            if mode not in ('add','remove','replace','clear'): raise ValueError('Invalid metadata operation')
            ids=[]
            for item in values:
                eid=item.get('id') if isinstance(item,dict) else None
                if not eid or not c.execute('SELECT 1 FROM entities WHERE id=? AND owner=? AND kind=?',(eid,db.OWNER,k)).fetchone(): raise ValueError('Choose existing metadata for batch editing')
                ids.append(eid)
            current={e['id'] for e in w[k]}; selected=set(ids)
            result=current|selected if mode=='add' else current-selected if mode=='remove' else selected if mode=='replace' else set()
            w[k]=[{'id':eid} for eid in sorted(result)]
        elif k=='marks':
            import marks
            mode=spec.get('mode'); selected=set(marks.numbers(marks.bits(spec.get('items',[]))))
            if mode not in ('add','remove','replace','clear'): raise ValueError('Invalid mark operation')
            current=set(w['marks'])
            w['marks']=sorted(current|selected if mode=='add' else current-selected if mode=='remove' else selected if mode=='replace' else set())
            w['bought']=1 in w['marks']
        elif k=='ratings':
            if not isinstance(spec,dict): raise ValueError('Invalid ratings')
            dims={d['id']:d['maximum'] for d in db.dimensions(c)}
            for did,value in spec.items():
                if did not in dims or value is not None and (type(value)!=int or not 1<=value<=dims[did]): raise ValueError('Invalid rating score')
                if value is None: w['ratings'].pop(did,None)
                else: w['ratings'][did]=value
        else:
            if k=='bought' and type(spec)!=bool: raise ValueError('Invalid purchase status')
            if k=='category' and spec not in ('',*db.CATEGORIES): raise ValueError('Invalid category')
            if k=='language' and (not isinstance(spec,str) or len(spec)>100): raise ValueError('Invalid language')
            w[k]=spec
            if k=='bought': w['marks']=sorted((set(w['marks'])-{1})|({1} if spec else set()))
    return w

def batch_preview(c,data):
    if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
    ids=batch_targets(c,data)
    if not ids: raise ValueError('Select at least one entry')
    patch=data.get('patch',{}); before={}; changed=0
    for wid in ids:
        w=db.get_work(c,wid); snapshot=state(c,wid)
        before[wid]=snapshot
        after=batch_values(c,w,patch)
        normalized={**snapshot,**{k:after[k] for k in patch}}
        if 'marks' in patch or 'bought' in patch: normalized.update(marks=after['marks'],bought=after['bought'])
        for k in KINDS:
            if k in patch: normalized[k]=sorted(e['id'] for e in after[k])
        changed+=bool(changes(snapshot,normalized))
    ident=db.uid(); payload={'before':before,'patch':patch}
    c.execute('INSERT INTO batch_previews VALUES(?,?,?,?)',(ident,db.OWNER,db.now(),json.dumps(payload,ensure_ascii=False)))
    return {'id':ident,'total':len(ids),'changed':changed,'unchanged':len(ids)-changed,'patch':patch}

def batch_apply(c,ident):
    if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
    row=c.execute('SELECT * FROM batch_previews WHERE id=? AND owner=?',(ident,db.OWNER)).fetchone()
    cutoff=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(minutes=15)).isoformat()
    if not row or row['created']<cutoff: raise ValueError('Batch preview expired; preview again')
    p=json.loads(row['payload']); deltas={}; titles=[]
    for wid,before in p['before'].items():
        if 'marks' not in before: before['marks']=[1] if before['bought'] else []
        if state(c,wid)!=before: raise ValueError('Selected entries changed; preview again')
    for wid,before in p['before'].items():
        w=batch_values(c,db.get_work(c,wid),p['patch'])
        normalized={**before,**{k:w[k] for k in p['patch']}}
        if 'marks' in p['patch'] or 'bought' in p['patch']: normalized.update(marks=w['marks'],bought=w['bought'])
        for k in KINDS:
            if k in p['patch']: normalized[k]=sorted(e['id'] for e in w[k])
        if not changes(before,normalized): continue
        db.save_work(c,w,wid); deltas[wid]=changes(before,state(c,wid)); titles.append(w['title'])
    operation=record(c,'batch',{'works':deltas,'titles':titles[:5]}) if deltas else None
    c.execute('DELETE FROM batch_previews WHERE id=?',(ident,))
    return {'changed':len(deltas),'unchanged':len(p['before'])-len(deltas),'operation':operation}
