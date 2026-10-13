"""Attribute policy and explainable cross-source candidates. No fuzzy auto-merge."""
import json
import re
import unicodedata
import db
import importer
import features

def key(value):
    return ' '.join(unicodedata.normalize('NFKC',str(value or '')).casefold().split())

def title_key(value):
    """Ignore leading source credit blocks, never rewrite the displayed title.

    Keep chapter/volume/edition qualifiers and bracket-only titles intact.
    This is candidate evidence, not permission to merge works automatically.
    """
    title=key(value)
    protected=r'(?:\d+(?:[\s._-]*\d+)*|(?:chapter|chap|ch|volume|vol|part|episode|ep|book|season)[\s.:#_-]*[0-9ivxlcdm]+(?:[\s._-]*[0-9ivxlcdm]+)*|第.+[話巻章集]|[上下前後]編|[上下]巻|(?:english|japanese|chinese|korean|spanish|french|german)(?: translation)?|translated|translation|uncensored|censored|digital|revised|complete|日本語|英語|中国語|韓国語|翻訳|修正|無修正|総集編)'
    while True:
        block=re.match(r'^\[([^\[\]]+)\]\s*(.+)$',title)
        if not block or re.fullmatch(protected,block[1].strip()): break
        title=block[2].strip()
    return title

def record_titles(c,wid,titles):
    if not isinstance(titles,list) or len(titles)>30: raise ValueError('Too many source title variants')
    for title in titles:
        title=str(title).strip()
        if title and len(title)<=4096:
            c.execute('INSERT OR IGNORE INTO work_titles VALUES(?,?,?)',(wid,title,title_key(title)))

def title_matches(c,titles,exclude=''):
    keys={title_key(t) for t in titles if title_key(t)}
    if not keys: return []
    placeholders=','.join('?' for _ in keys)
    rows=c.execute(f'SELECT DISTINCT w.id,w.title,w.pages,w.language FROM works w JOIN work_titles t ON t.work_id=w.id WHERE w.owner=? AND w.deleted_at IS NULL AND w.id<>? AND t.title_key IN ({placeholders}) ORDER BY w.created,w.id LIMIT 100',(db.OWNER,exclude,*keys))
    return [db.work_summary(c,r) for r in rows]

def candidate_evidence(c,work,data):
    incoming={key(n) for a in data.get('author',[]) for n in [a['name'],*a.get('aliases',[])]}
    names=set()
    for author in c.execute("SELECT e.id,e.name FROM entities e JOIN work_entities we ON we.entity_id=e.id WHERE we.work_id=? AND e.kind='author'",(work['id'],)):
        names.add(key(author['name']))
        names.update(key(r[0]) for r in c.execute('SELECT name FROM aliases WHERE entity_id=?',(author['id'],)))
    overlap=bool(names & incoming)
    return {'title':True,'author':overlap,'author_conflict':bool(names and incoming and not overlap),'language':not work['language'] or not data.get('language') or key(work['language'])==key(data['language']),'pages':work['pages'] is None or data.get('pages') is None or work['pages']==data['pages']}

def tag_snapshot(c):
    rows=c.execute("SELECT e.id,e.name,e.gender,count(w.id) AS uses FROM entities e LEFT JOIN work_entities we ON we.entity_id=e.id LEFT JOIN works w ON w.id=we.work_id AND w.deleted_at IS NULL WHERE e.owner=? AND e.kind='tag' GROUP BY e.id",(db.OWNER,)).fetchall()
    aliases={}
    for r in c.execute("SELECT a.entity_id,a.name FROM aliases a JOIN entities e ON e.id=a.entity_id WHERE e.owner=? AND e.kind='tag'",(db.OWNER,)):
        aliases.setdefault(r['entity_id'],[]).append(r['name'])
    by_name={}
    for row in rows:
        item=dict(row)
        for name in {key(row['name']),*(key(n) for n in aliases.get(row['id'],[]))}:
            by_name.setdefault(name,[]).append(item)
    return by_name

def apply_tags(c,data,mode='neutral',snapshot=None):
    if mode not in ('neutral','frequency'): raise ValueError('Invalid nhentai tag policy')
    names=snapshot if snapshot is not None else tag_snapshot(c)
    result=[]
    for item in data.get('tag',[]):
        choices=names.get(key(item['name']),[])
        selected=None
        # More than one entity within one gender is an ambiguous alias.
        counts={g:sum(1 for r in choices if r['gender']==g) for g in ('neutral','male','female')}
        if mode=='frequency' and choices and all(n<=1 for n in counts.values()):
            maximum=max(r['uses'] for r in choices)
            winners=[r for r in choices if r['uses']==maximum]
            if len(winners)==1 and maximum>0: selected=winners[0]
        if not selected:
            neutral=[r for r in choices if r['gender']=='neutral']
            if len(neutral)==1: selected=neutral[0]
        if selected:
            import tag_policy
            resolved=tag_policy.entity_id(c,selected['id'])
            row=c.execute("SELECT * FROM entities WHERE id=? AND owner=? AND kind='tag'",(resolved,db.OWNER)).fetchone()
            if row: result.append(db.entity_data(c,row)); continue
        # Preserve the default no-attribute policy, but do not hide ambiguous aliases.
        result.append(dict(item,gender='neutral'))
    data['tag']=result
    return data

def candidates(c,data,value,exclude=''):
    identity=importer.source_identity(value)
    if not identity: return []
    titles={title_key(t) for t in [data.get('title',''),*data.get('source_titles',[])] if title_key(t)}
    if not titles: return []
    placeholders=','.join('?' for _ in titles)
    rows=c.execute(f'SELECT DISTINCT w.id,w.title,w.pages,w.language FROM works w JOIN work_titles t ON t.work_id=w.id WHERE w.owner=? AND w.deleted_at IS NULL AND w.id<>? AND t.title_key IN ({placeholders}) ORDER BY w.created,w.id',(db.OWNER,exclude,*titles)).fetchall()
    found=[]
    for row in rows:
        sources=[importer.source_identity(r[0]) for r in c.execute('SELECT url FROM links WHERE work_id=?',(row['id'],))]
        # This workflow compares different providers, not intentional pages on one provider.
        if not any(s and s[0]!=identity[0] for s in sources): continue
        evidence=candidate_evidence(c,row,data)
        if evidence['author_conflict']: continue
        result=db.work_summary(c,row)
        result['evidence']=evidence
        found.append(result)
        if len(found)>=100: break
    return found

def attach(c,wid,value,titles=()):
    if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
    matches=db.exact_sources(c,value)
    if matches: raise db.DuplicateSource(matches)
    work=db.get_work(c,wid)
    before=features.state(c,wid)
    position=c.execute('SELECT COALESCE(max(position),-1)+1 FROM links WHERE work_id=?',(wid,)).fetchone()[0]
    # Do not turn a new secondary source into the primary source, even on a linkless work.
    c.execute('INSERT INTO links VALUES(?,?,?,?,?,?,?)',(db.uid(),wid,db.url(value),'nhentai' if importer.source_identity(value)[0]=='nhentai' else 'Hitomi',position,0,db.normalize_url(value)))
    c.execute('INSERT INTO source_claims VALUES(?,?,?)',(db.OWNER,db.normalize_url(value),wid))
    c.execute('UPDATE works SET updated=? WHERE id=?',(db.now(),wid))
    record_titles(c,wid,list(titles))
    features.record(c,'edit',{'works':{wid:features.changes(before,features.state(c,wid))},'titles':[work['title']]})
    return db.get_work(c,wid)
