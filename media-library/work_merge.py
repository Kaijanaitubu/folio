"""Atomic all-link consolidation with explicitly selected metadata changes."""
import hashlib,json
import db,features,trash_sources

SCALARS=('title','cover','category','language','pages')
KINDS=features.KINDS


def clean_draft(data):
    if not isinstance(data,dict):raise ValueError('Invalid merge draft')
    links=data.get('links',[])
    if not isinstance(links,list) or len(links)>1000:raise ValueError('Invalid merge links')
    out={k:data.get(k,[] if k in KINDS else None if k=='pages' else '') for k in (*SCALARS,*KINDS)}
    out['links']=[]
    for link in links:
        if not isinstance(link,dict):raise ValueError('Invalid merge links')
        value=db.url(link.get('url',''))
        if value:out['links'].append({'url':value,'label':str(link.get('label') or ''),'is_primary':bool(link.get('is_primary'))})
    out['source_titles']=data.get('source_titles',[])
    if not isinstance(out['source_titles'],list):raise ValueError('Invalid source titles')
    for kind in KINDS:
        if not isinstance(out[kind],list):raise ValueError('Invalid merge metadata')
    return out


def _preview(c,a,b,source=None):
    if not a['links']:raise ValueError('Source entry has no source links')
    trash=[]
    for link in a['links']:
        matches=[w for w in db.exact_sources(c,link['url'],source or '') if w['id']!=b['id']]
        active=[w for w in matches if not w['deleted_at']]
        if active:raise db.DuplicateSource(active)
        if matches:trash.append(trash_sources.preview(c,link['url']))
    signature=hashlib.sha256(json.dumps([a,b,trash],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    keys={db.normalize_url(l['url']) for l in b['links']};links=[]
    for link in a['links']:
        key=db.normalize_url(link['url'])
        if key not in keys:links.append(link);keys.add(key)
    return {'source':a,'target':b,'links':links,'signature':signature,'trash_conflicts':trash}


def preview(c,source,target):
    if not isinstance(target,str) or source==target:raise ValueError('Choose another entry')
    return _preview(c,db.get_work(c,source),db.get_work(c,target),source)


def draft_preview(c,data,target):
    return _preview(c,clean_draft(data),db.get_work(c,target))


def apply_metadata(c,target,patch):
    """Only metadata may be changed; never accept ratings/reviews/marks/links."""
    if patch is None:return
    if not isinstance(patch,dict) or set(patch)-set((*SCALARS,*KINDS)):raise ValueError('Invalid merge metadata')
    for field,value in patch.items():
        if value is None or value=='' or value==[]:continue
        if field in KINDS:
            if not isinstance(value,list) or len(value)>2000 or any(not isinstance(item,(str,dict)) for item in value):raise ValueError('Invalid merge metadata')
            ids=sorted(eid for eid in {db.resolve(c,field,item) for item in value} if eid)
            old=sorted(r[0] for r in c.execute('SELECT we.entity_id FROM work_entities we JOIN entities e ON e.id=we.entity_id WHERE we.work_id=? AND e.kind=?',(target,field)))
            if not ids or ids==old:continue
            c.execute('DELETE FROM work_entities WHERE work_id=? AND entity_id IN (SELECT id FROM entities WHERE kind=?)',(target,field))
            c.executemany('INSERT OR IGNORE INTO work_entities VALUES(?,?)',[(target,eid) for eid in ids if eid])
        else:
            if field=='pages':
                if type(value)!=int or value<0:raise ValueError('Pages must be a nonnegative integer')
            elif not isinstance(value,str):raise ValueError('Invalid merge metadata')
            if field=='cover':value=db.url(value)
            if field=='category' and value not in db.CATEGORIES:raise ValueError('Invalid category')
            if field=='title':
                value=value.strip()
                if not value:continue
            if field=='language':value=db.language_name(value)
            c.execute('UPDATE works SET '+field+'=? WHERE id=?',(value,target))
            if field=='title':
                import import_matching
                import_matching.record_titles(c,target,[value])


def _apply(c,p,patch,source=None,consents=()):
    target=p['target']['id'];before=features.state(c,target)
    if p['trash_conflicts']:
        allowed=trash_sources.approved(c,consents,[l['url'] for l in p['source']['links']])
        required={w['id'] for conflict in p['trash_conflicts'] for w in conflict['works']}
        if not required<=allowed:raise db.DuplicateSource([w for conflict in p['trash_conflicts'] for w in conflict['works']])
        for wid in allowed:db.purge_work(c,wid)
    apply_metadata(c,target,patch)
    position=c.execute('SELECT COALESCE(max(position),-1)+1 FROM links WHERE work_id=?',(target,)).fetchone()[0]
    for i,link in enumerate(p['links']):
        key=db.normalize_url(link['url'])
        c.execute('INSERT INTO links(id,work_id,url,label,position,is_primary,url_key) VALUES(?,?,?,?,?,0,?)',(db.uid(),target,link['url'],link['label'],position+i,key))
        c.execute('INSERT INTO source_claims VALUES(?,?,?) ON CONFLICT(owner,url_key) DO UPDATE SET work_id=excluded.work_id',(db.OWNER,key,target))
    c.execute('UPDATE works SET updated=? WHERE id=?',(db.now(),target))
    delta=features.changes(before,features.state(c,target))
    if delta:features.record(c,'edit',{'works':{target:delta},'titles':[p['target']['title']]})
    if source:features.trash(c,source)
    for link in p['source']['links']:
        c.execute('INSERT INTO source_claims VALUES(?,?,?) ON CONFLICT(owner,url_key) DO UPDATE SET work_id=excluded.work_id',(db.OWNER,db.normalize_url(link['url']),target))
    if p['source'].get('source_titles'):
        import import_matching
        import_matching.record_titles(c,target,p['source']['source_titles'])
    return {'id':target,'added':len(p['links'])}


def apply(c,source,target,signature,metadata_patch=None):
    if not c.in_transaction:c.execute('BEGIN IMMEDIATE')
    p=preview(c,source,target)
    if not signature or signature!=p['signature']:raise ValueError('Entries changed; review the merge again')
    return _apply(c,p,metadata_patch,source)


def apply_draft(c,data,target,signature,metadata_patch=None,consents=()):
    if not c.in_transaction:c.execute('BEGIN IMMEDIATE')
    p=draft_preview(c,data,target)
    if not signature or signature!=p['signature']:raise ValueError('Entries changed; review the merge again')
    return _apply(c,p,metadata_patch,consents=consents)
