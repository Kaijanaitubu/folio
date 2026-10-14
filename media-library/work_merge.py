"""Explicit link-only consolidation of two active library entries."""
import hashlib,json
import db,features

def preview(c,source,target):
    if not isinstance(target,str) or source==target:raise ValueError('Choose another entry')
    a=db.get_work(c,source);b=db.get_work(c,target)
    if not a['links']:raise ValueError('Source entry has no source links')
    for link in a['links']:
        matches=[w for w in db.exact_sources(c,link['url'],source) if w['id']!=target]
        if matches:raise db.DuplicateSource(matches)
    signature=hashlib.sha256(json.dumps([a,b],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    keys={db.normalize_url(l['url']) for l in b['links']}
    links=[]
    for l in a['links']:
        key=db.normalize_url(l['url'])
        if key not in keys:links.append(l);keys.add(key)
    return {'source':a,'target':b,'links':links,'signature':signature}

def apply(c,source,target,signature):
    if not c.in_transaction:c.execute('BEGIN IMMEDIATE')
    p=preview(c,source,target)
    if not signature or signature!=p['signature']:raise ValueError('Entries changed; review the merge again')
    before=features.state(c,target)
    position=c.execute('SELECT COALESCE(max(position),-1)+1 FROM links WHERE work_id=?',(target,)).fetchone()[0]
    for i,l in enumerate(p['links']):
        key=db.normalize_url(l['url'])
        c.execute('INSERT INTO links(id,work_id,url,label,position,is_primary,url_key) VALUES(?,?,?,?,?,0,?)',(db.uid(),target,l['url'],l['label'],position+i,key))
        c.execute('INSERT INTO source_claims VALUES(?,?,?) ON CONFLICT(owner,url_key) DO UPDATE SET work_id=excluded.work_id',(db.OWNER,key,target))
    c.execute('UPDATE works SET updated=? WHERE id=?',(db.now(),target))
    delta=features.changes(before,features.state(c,target))
    if delta:features.record(c,'edit',{'works':{target:delta},'titles':[p['target']['title']]})
    features.trash(c,source)
    for l in p['source']['links']:
        c.execute('INSERT INTO source_claims VALUES(?,?,?) ON CONFLICT(owner,url_key) DO UPDATE SET work_id=excluded.work_id',(db.OWNER,db.normalize_url(l['url']),target))
    return {'id':target,'added':len(p['links'])}
