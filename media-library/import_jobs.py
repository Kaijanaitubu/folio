"""Durable bookmark/Favorites jobs and explicit cross-site review decisions."""
import hashlib
import json
import time
import db
import importer
import nhentai
import nhentai_credentials as credentials
import import_matching as matching

def init(c):
    columns={r['name'] for r in c.execute('PRAGMA table_info(jobs)')}
    additions={'kind':"TEXT NOT NULL DEFAULT 'bookmarks'",'tag_mode':"TEXT NOT NULL DEFAULT 'neutral'",'tag_snapshot':"TEXT NOT NULL DEFAULT '{}'",'match_policy':"TEXT NOT NULL DEFAULT 'ask'",'favorite_query':"TEXT NOT NULL DEFAULT ''",'enumeration_page':'INTEGER NOT NULL DEFAULT 1','enumeration_done':'INTEGER NOT NULL DEFAULT 1','enumeration_pages':'INTEGER','enumeration_total':'INTEGER','enumeration_attempts':'INTEGER NOT NULL DEFAULT 0','next_run':'REAL NOT NULL DEFAULT 0','message':"TEXT NOT NULL DEFAULT ''",'credential_id':"TEXT NOT NULL DEFAULT ''"}
    for name,definition in additions.items():
        if name not in columns: c.execute(f'ALTER TABLE jobs ADD COLUMN {name} {definition}')
    columns={r['name'] for r in c.execute('PRAGMA table_info(job_items)')}
    for name,definition in {'payload':"TEXT NOT NULL DEFAULT '{}'",'next_run':'REAL NOT NULL DEFAULT 0'}.items():
        if name not in columns: c.execute(f'ALTER TABLE job_items ADD COLUMN {name} {definition}')
    c.executescript('''
    CREATE TABLE IF NOT EXISTS import_settings(owner TEXT PRIMARY KEY, tag_mode TEXT NOT NULL DEFAULT 'neutral');
    CREATE TABLE IF NOT EXISTS work_titles(work_id TEXT REFERENCES works(id) ON DELETE CASCADE, title TEXT NOT NULL, title_key TEXT NOT NULL, PRIMARY KEY(work_id,title));
    CREATE INDEX IF NOT EXISTS work_title_key ON work_titles(title_key,work_id);
    CREATE INDEX IF NOT EXISTS job_item_url ON job_items(job_id,url);
    ''')
    if not c.execute('SELECT 1 FROM migrations WHERE version=4').fetchone():
        for row in c.execute('SELECT id,title FROM works').fetchall(): matching.record_titles(c,row['id'],[row['title']])
        for row in c.execute('SELECT work_id,source_title FROM work_imports').fetchall(): matching.record_titles(c,row['work_id'],[row['source_title']])
        c.execute('INSERT INTO migrations VALUES(4,?)',(db.now(),))
    c.execute("UPDATE jobs SET status='awaiting_review' WHERE status='review'")
    if not c.execute('SELECT 1 FROM migrations WHERE version=5').fetchone():
        # Previously saved manual nhentai sources used generic comparison keys.
        # Preserve their URLs and separate works, rebuilding only affected claims.
        affected=set()
        for row in c.execute('SELECT l.id,l.url,l.url_key,w.owner FROM links l JOIN works w ON w.id=l.work_id').fetchall():
            if not nhentai.location(row['url']): continue
            normalized=db.normalize_url(row['url'])
            affected.update(((row['owner'],row['url_key']),(row['owner'],normalized)))
            c.execute('UPDATE links SET url_key=? WHERE id=?',(normalized,row['id']))
        for owner,value in affected:
            c.execute('DELETE FROM source_claims WHERE owner=? AND url_key=?',(owner,value))
            work=c.execute('SELECT min(w.id) FROM links l JOIN works w ON w.id=l.work_id WHERE w.owner=? AND l.url_key=?',(owner,value)).fetchone()[0]
            if work: c.execute('INSERT INTO source_claims VALUES(?,?,?)',(owner,value,work))
        c.execute('INSERT INTO migrations VALUES(5,?)',(db.now(),))

def default_tag_mode(c):
    row=c.execute('SELECT tag_mode FROM import_settings WHERE owner=?',(db.OWNER,)).fetchone()
    return row[0] if row else 'neutral'

def fingerprint():
    value=credentials.get()
    return hashlib.sha256(value.encode()).hexdigest() if value else ''

def job(c,jid):
    row=c.execute('SELECT * FROM jobs WHERE id=? AND owner=?',(jid,db.OWNER)).fetchone()
    if not row: raise ValueError('Import job not found')
    return dict(row)

def insert_item(c,jid,item,seen=None,keep_repeats=False):
    value=db.url(item['url'])
    if not value or len(value)>4096: raise ValueError('Invalid source URL')
    normalized=db.normalize_url(value)
    repeated=seen is not None and normalized in seen
    if seen is not None:
        if repeated and not keep_repeats: return
        seen.add(normalized)
    status='pending' if importer.source_identity(value) else 'unsupported'
    if repeated or db.exact_sources(c,value): status='duplicate_url'
    c.execute('INSERT INTO job_items(id,job_id,url,label,folder,status,title) VALUES(?,?,?,?,?,?,?)',(db.uid(),jid,value,str(item.get('label',''))[:4096],str(item.get('folder',''))[:4096],status,str(item.get('title',''))[:4096]))

def create(c,data):
    kind=data.get('kind','bookmarks'); mode=data.get('title_mode','source'); tags=data.get('tag_mode','neutral')
    if kind not in ('bookmarks','favorites') or mode not in ('source','bookmark') or tags not in ('neutral','frequency'): raise ValueError('Invalid import options')
    if kind=='favorites' and not credentials.get(): raise nhentai.ApiError(401)
    if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
    jid=db.uid()
    c.execute('INSERT INTO jobs(id,owner,status,created,title_mode,kind,tag_mode,tag_snapshot,favorite_query,enumeration_done,credential_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(jid,db.OWNER,'running',db.now(),mode,kind,tags,json.dumps(matching.tag_snapshot(c),ensure_ascii=False),str(data.get('query',''))[:1000],int(kind!='favorites' or bool(data.get('items'))),fingerprint() if kind=='favorites' else ''))
    items=data.get('items',[])
    if not isinstance(items,list) or len(items)>100000: raise ValueError('Select at most 100,000 import items')
    if kind=='favorites' and 'items' in data and not items: raise ValueError('Select at least one Favorite, or import all matching Favorites')
    seen=set()
    for item in items:
        if kind=='favorites' and not nhentai.location(item.get('url','')): raise ValueError('Favorites require nhentai URLs')
        insert_item(c,jid,item,seen,keep_repeats=True)
    return {'id':jid}

def stopped(jid):
    with db.transaction() as c: return job(c,jid)['status']!='running'

def enumerate_page(jid):
    with db.transaction() as c: current=job(c,jid)
    if current['status']!='running' or current['enumeration_done']: return
    if not fingerprint() or fingerprint()!=current['credential_id']:
        with db.transaction() as c: c.execute("UPDATE jobs SET status='awaiting_key',message=? WHERE id=?",('Reconnect the API key used to start this Favorites job, then resume',jid))
        return
    result=nhentai.favorites(current['enumeration_page'],current['favorite_query'],cancelled=lambda:stopped(jid))
    with db.transaction() as c:
        c.execute('BEGIN IMMEDIATE'); current=job(c,jid)
        if current['status']!='running': return
        if fingerprint()!=current['credential_id']:
            c.execute("UPDATE jobs SET status='awaiting_key',message=? WHERE id=?",('API key changed during Favorites enumeration; reconnect the original key',jid)); return
        # Keep enumeration page and inserted URLs in the same commit; restarts cannot lose a page.
        seen={db.normalize_url(r[0]) for r in c.execute('SELECT url FROM job_items WHERE job_id=?',(jid,))}
        for item in result['items']: insert_item(c,jid,item,seen)
        count=c.execute('SELECT count(*) FROM job_items WHERE job_id=?',(jid,)).fetchone()[0]
        if count>100000: raise ValueError('Favorites exceed 100,000 works; narrow the Favorites search')
        done=current['enumeration_page']>=result['num_pages']
        c.execute('UPDATE jobs SET enumeration_page=enumeration_page+1,enumeration_pages=?,enumeration_total=?,enumeration_done=?,enumeration_attempts=0,next_run=0,message=? WHERE id=?',(result['num_pages'],result['total'],int(done),'',jid))

def finish_item(c,item,data,current,action='new',target=None):
    exact=db.exact_sources(c,item['url'])
    if exact:
        c.execute("UPDATE job_items SET status='duplicate_url',warnings_json=?,payload='{}' WHERE id=?",(json.dumps({'sources':exact},ensure_ascii=False),item['id'])); return
    source_title=str(data.get('_source_title',data.get('title','')))
    if action=='attach':
        result=matching.attach(c,target,item['url'],data.get('source_titles',[source_title])); status='linked'
    else:
        result=db.save_work(c,data); status='added'
    db.record_bookmark(c,result['id'],item,source_title,current['title_mode'])
    warnings={'titles':db.title_matches(c,data['title'],result['id']),'related':[r for r in db.source_matches(c,item['url'])['matches'] if r['id']!=result['id']]}
    c.execute('UPDATE job_items SET status=?,title=?,message=?,work_id=?,warnings_json=?,payload=? WHERE id=?',(status,data['title'],'; '.join(data.get('warnings',[])),result['id'],json.dumps(warnings,ensure_ascii=False),'{}',item['id']))

def process_item(item):
    with db.transaction() as c:
        current=job(c,item['job_id']); matches=db.exact_sources(c,item['url'])
        if matches:
            c.execute("UPDATE job_items SET status='duplicate_url',warnings_json=? WHERE id=?",(json.dumps({'sources':matches},ensure_ascii=False),item['id'])); return
        if current['kind']=='favorites' and fingerprint()!=current['credential_id']:
            c.execute("UPDATE jobs SET status='awaiting_key',message=? WHERE id=?",('Reconnect the API key used to start this Favorites job, then resume',current['id']))
            c.execute("UPDATE job_items SET status='pending' WHERE id=?",(item['id'],)); return
    # No SQLite transaction is held while waiting for rate limits or network responses.
    token=nhentai.CANCEL.set(lambda:stopped(item['job_id']))
    try: data=importer.import_url(item['url'])
    finally: nhentai.CANCEL.reset(token)
    source_title=str(data.get('title') or '').strip(); bookmark=str(item.get('label') or '').strip()
    title=(bookmark or source_title) if current['title_mode']=='bookmark' else (source_title or bookmark)
    if not title: raise ValueError('No title retrieved; retry or add manually')
    data.update(title=title,_source_title=source_title,links=[{'url':item['url'],'is_primary':True}])
    data['source_titles']=list(dict.fromkeys([source_title,*data.get('source_titles',[])]))
    with db.transaction() as c:
        c.execute('BEGIN IMMEDIATE'); current=job(c,item['job_id'])
        if current['status']!='running':
            c.execute('UPDATE job_items SET status=? WHERE id=?',('cancelled' if current['status']=='cancelled' else 'pending',item['id'])); return
        if nhentai.location(item['url']): matching.apply_tags(c,data,current['tag_mode'],json.loads(current['tag_snapshot']))
        options=matching.candidates(c,data,item['url'])
        if options:
            policy=current['match_policy']
            if policy=='new': finish_item(c,item,data,current)
            elif policy=='attach_unique' and len(options)==1: finish_item(c,item,data,current,'attach',options[0]['id'])
            else:
                c.execute("UPDATE job_items SET status='match_review',title=?,payload=?,warnings_json=? WHERE id=?",(title,json.dumps(data,ensure_ascii=False),json.dumps({'candidates':options},ensure_ascii=False),item['id']))
        else: finish_item(c,item,data,current)

def decide(c,jid,data):
    if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
    current=job(c,jid); action=data.get('action'); apply_all=bool(data.get('apply_all'))
    if action not in ('new','attach'): raise ValueError('Choose secondary link or separate work')
    selected=c.execute("SELECT * FROM job_items WHERE id=? AND job_id=? AND status='match_review'",(data.get('item_id'),jid)).fetchone()
    if not selected: raise ValueError('Import review changed; refresh the job')
    items=c.execute("SELECT * FROM job_items WHERE job_id=? AND status='match_review' ORDER BY rowid",(jid,)).fetchall() if apply_all else [selected]
    resolved=0; ambiguous=0
    for row in items:
        item=dict(row); payload=json.loads(item['payload']); options=matching.candidates(c,payload,item['url'])
        target=data.get('target') if row['id']==selected['id'] else options[0]['id'] if len(options)==1 else None
        if action=='attach':
            if not target: ambiguous+=1; continue
            # Selected manual targets are allowed; active work is validated in attach.
            if row['id']!=selected['id'] and len(options)!=1: ambiguous+=1; continue
        try: finish_item(c,item,payload,current,action,target)
        except db.DuplicateSource as e:
            c.execute("UPDATE job_items SET status='duplicate_url',payload='{}',warnings_json=? WHERE id=?",(json.dumps({'sources':e.matches}),item['id']))
        resolved+=1
    if apply_all:
        c.execute('UPDATE jobs SET match_policy=? WHERE id=?',('attach_unique' if action=='attach' else 'new',jid))
    settle(c,jid)
    return {'resolved':resolved,'ambiguous':ambiguous,'policy':'attach_unique' if action=='attach' else 'new'}

def settle(c,jid):
    current=job(c,jid)
    if current['status'] not in ('running','awaiting_review','complete'): return
    active=c.execute("SELECT 1 FROM job_items WHERE job_id=? AND status IN ('running','pending') LIMIT 1",(jid,)).fetchone()
    if current['enumeration_done'] and not active:
        review=c.execute("SELECT 1 FROM job_items WHERE job_id=? AND status='match_review' LIMIT 1",(jid,)).fetchone()
        c.execute('UPDATE jobs SET status=? WHERE id=?',('awaiting_review' if review else 'complete',jid))

def control(c,jid,command,data):
    if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
    current=job(c,jid)
    if command in ('cancel','pause'):
        c.execute('UPDATE jobs SET status=? WHERE id=?',('cancelled' if command=='cancel' else 'paused',jid))
        if command=='cancel': c.execute("UPDATE job_items SET status='cancelled' WHERE job_id=? AND status='pending'",(jid,))
    elif command in ('retry','resume'):
        if current['kind']=='favorites' and fingerprint()!=current['credential_id']: raise ValueError('Reconnect the original API key before resuming this job')
        if command=='retry': c.execute("UPDATE job_items SET status='pending',attempts=0,next_run=0 WHERE job_id=? AND status IN ('failed','needs_review','cancelled')",(jid,))
        c.execute("UPDATE jobs SET status='running',enumeration_attempts=0,next_run=0,message='' WHERE id=?",(jid,))
    elif command=='policy':
        if data.get('policy') not in ('ask','new','attach_unique'): raise ValueError('Invalid matching policy')
        c.execute('UPDATE jobs SET match_policy=? WHERE id=?',(data['policy'],jid))
    else: raise ValueError('Invalid import job action')

def failure(jid,error,item=None):
    with db.transaction() as c:
        current=job(c,jid)
        if current['status']!='running':
            if item: c.execute("UPDATE job_items SET status=? WHERE id=? AND status='running'",('cancelled' if current['status']=='cancelled' else 'pending',item['id']))
            return
        if isinstance(error,nhentai.ApiError) and error.status in (401,403):
            c.execute("UPDATE jobs SET status='awaiting_key',message=? WHERE id=?",(str(error),jid))
            if item: c.execute("UPDATE job_items SET status='pending' WHERE id=?",(item['id'],))
            return
        attempts=c.execute('SELECT attempts FROM job_items WHERE id=?',(item['id'],)).fetchone()[0] if item else current['enumeration_attempts']+1
        transient=isinstance(error,nhentai.ApiError) and (error.status==429 or error.status>=500) or any(s in str(error).lower() for s in ('timed out','timeout','503','429'))
        retry=transient and attempts<4
        delay=max(getattr(error,'retry_after',0),min(60,2**attempts*3))
        if item:
            status='pending' if retry else 'duplicate_url' if isinstance(error,db.DuplicateSource) else 'needs_review' if 'Ambiguous alias' in str(error) else 'failed'
            c.execute('UPDATE job_items SET status=?,message=?,next_run=? WHERE id=?',(status,str(error),time.time()+delay if retry else 0,item['id']))
        else:
            c.execute('UPDATE jobs SET status=?,message=?,enumeration_attempts=?,next_run=? WHERE id=?',('running' if retry else 'paused',str(error),attempts,time.time()+delay if retry else 0,jid))
