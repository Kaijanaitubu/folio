"""Dependency-free LAN application server; run with Python 3.11+."""
import argparse
import json
import mimetypes
import os
import secrets
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import db
import features
import importer
import cover_relay
import nhentai
import nhentai_credentials
import import_jobs
import import_matching
import tag_policy
from search import CATEGORIES

TOKEN=secrets.token_urlsafe(32)
STATIC=Path(__file__).parent/'static'
STOP=threading.Event()

class LibraryHTTPServer(ThreadingHTTPServer):
    # Prevent two servers from binding this port under Windows SO_REUSEADDR.
    allow_reuse_address=False

def jobs(c,jid=None):
    rows=[dict(r) for r in c.execute('SELECT * FROM jobs WHERE owner=?'+(' AND id=?' if jid else '')+' ORDER BY created DESC',([db.OWNER,jid] if jid else [db.OWNER]))]
    for r in rows:
        r['counts']={s['status']:s['n'] for s in c.execute('SELECT status,count(*) n FROM job_items WHERE job_id=? GROUP BY status',(r['id'],))}
        if jid:
            r['items']=[dict(i) for i in c.execute('SELECT * FROM job_items WHERE job_id=? ORDER BY rowid',(jid,))]
            for item in r['items']:
                item['warnings']=json.loads(item.pop('warnings_json'))
                payload=json.loads(item.pop('payload','{}'))
                if item['status']=='match_review': item['review_data']={k:payload.get(k) for k in ('title','author','language','pages')}
        for field in ('tag_snapshot','credential_id'): r.pop(field,None)
    return rows[0] if jid and rows else rows

def process_import_item(item):
    return import_jobs.process_item(item)

def worker():
    last_backup=0; last_cleanup=0
    while not STOP.is_set():
        cover_relay.CACHE.prune()
        if time.time()-last_backup>86400:
            try: db.backup(); last_backup=time.time()
            except Exception: last_backup=time.time()-86340
        with db.transaction() as c:
            if time.time()-last_cleanup>3600:
                features.cleanup(c); last_cleanup=time.time()
            enumeration=c.execute("SELECT id FROM jobs WHERE status='running' AND enumeration_done=0 AND next_run<=? ORDER BY created LIMIT 1",(time.time(),)).fetchone()
            item=None
            if not enumeration:
                item=c.execute("SELECT i.* FROM job_items i JOIN jobs j ON j.id=i.job_id WHERE j.status='running' AND i.status='pending' AND i.next_run<=? ORDER BY j.created,i.rowid LIMIT 1",(time.time(),)).fetchone()
                if item:
                    item=dict(item); c.execute("UPDATE job_items SET status='running',attempts=attempts+1 WHERE id=?",(item['id'],))
                else:
                    for row in c.execute("SELECT id FROM jobs WHERE status='running'").fetchall(): import_jobs.settle(c,row['id'])
        if enumeration:
            try: import_jobs.enumerate_page(enumeration['id'])
            except Exception as e: import_jobs.failure(enumeration['id'],e)
        elif item:
            try: process_import_item(item)
            except Exception as e: import_jobs.failure(item['job_id'],e,item)
        else: STOP.wait(1); continue
        STOP.wait(.2)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def send_json(self,data,status=200):
        raw=json.dumps(data,ensure_ascii=False).encode(); self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(raw))); self.end_headers()
        if self.command!='HEAD': self.wfile.write(raw)
    def send_cover(self,ident):
        origin=self.headers.get('Origin')
        if self.headers.get('Sec-Fetch-Site')=='cross-site' or (origin and urlsplit(origin).netloc!=self.headers.get('Host')):
            self.send_json({'error':'Cross-site cover request rejected'},403); return
        with db.transaction() as c:
            row=c.execute('SELECT cover FROM works WHERE id=? AND owner=?',(ident,db.OWNER)).fetchone()
        if not row or not row['cover']:
            self.send_json({'error':'Cover not found'},404); return
        if not cover_relay.SLOTS.acquire(timeout=25):
            self.send_json({'error':'Cover relay is busy; try again'},503); return
        try:
            mime,raw=cover_relay.load(row['cover'])
            self.send_response(200)
            self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store, max-age=0')
            self.send_header('Pragma','no-cache'); self.send_header('Expires','0')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Cross-Origin-Resource-Policy','same-origin')
            self.end_headers()
            if self.command!='HEAD':
                self.connection.settimeout(30)
                self.wfile.write(raw)
        finally:
            cover_relay.SLOTS.release()
    def body(self):
        size=int(self.headers.get('Content-Length','0'))
        if size>16*1024*1024: raise ValueError('Request exceeds 16 MB')
        return json.loads(self.rfile.read(size) or '{}')
    def dispatch(self):
        u=urlsplit(self.path); path=u.path; query=parse_qs(u.query)
        g=lambda k,default='':query.get(k,[default])[0]
        if self.command not in ('GET','HEAD'):
            origin=self.headers.get('Origin')
            if self.headers.get('X-Library-Token')!=TOKEN or (origin and urlsplit(origin).netloc!=self.headers.get('Host')):
                self.send_json({'error':'Request origin or token rejected'},403); return
        if not path.startswith('/api/'):
            if self.command not in ('GET','HEAD'): raise ValueError('Invalid request')
            name=path.lstrip('/') if '.' in path else 'index.html'
            file=(STATIC/name).resolve()
            if not file.is_relative_to(STATIC.resolve()) or not file.is_file(): self.send_error(404); return
            raw=file.read_bytes(); self.send_response(200)
            self.send_header('Content-Type',(mimetypes.guess_type(str(file))[0] or 'application/octet-stream')+'; charset=utf-8')
            self.send_header('Content-Length',str(len(raw))); self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' http: https: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            if self.command!='HEAD': self.wfile.write(raw)
            return
        parts=path.strip('/').split('/')[1:]; action=parts[0]; ident=parts[1] if len(parts)>1 else None
        if action=='works' and ident and len(parts)==3 and parts[2]=='cover':
            if self.command not in ('GET','HEAD'): raise ValueError('Invalid cover request')
            self.send_cover(ident); return
        data=self.body() if self.command in ('POST','PUT') else {}
        if action=='covers' and ident=='preview' and self.command=='POST':
            if not cover_relay.SLOTS.acquire(timeout=25): raise ValueError('Cover relay is busy; try again')
            try:
                mime,raw=cover_relay.load(data.get('url',''))
                self.send_response(200); self.send_header('Content-Type',mime)
                self.send_header('Content-Length',str(len(raw))); self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(raw)
            finally: cover_relay.SLOTS.release()
            return
        if action=='nhentai':
            if self.command=='GET' and ident=='status':
                with db.transaction() as c: result=dict(nhentai_credentials.status(),tag_mode=import_jobs.default_tag_mode(c))
            elif self.command=='POST' and ident=='connect':
                key=nhentai_credentials.validate(data.get('key')) if data.get('key') else nhentai_credentials.get()
                if not key: raise nhentai.ApiError(401)
                preview=nhentai.favorites(1,data.get('query',''),key=key)
                if data.get('key'): nhentai_credentials.set_key(key,bool(data.get('remember')))
                result=dict(nhentai_credentials.status(),preview=preview)
            elif self.command=='POST' and ident=='disconnect': result=nhentai_credentials.forget()
            elif self.command=='POST' and ident=='settings':
                mode=data.get('tag_mode')
                if mode not in ('neutral','frequency'): raise ValueError('Invalid nhentai tag policy')
                with db.transaction() as c: c.execute('INSERT INTO import_settings VALUES(?,?) ON CONFLICT(owner) DO UPDATE SET tag_mode=excluded.tag_mode',(db.OWNER,mode))
                result={'tag_mode':mode}
            else: raise ValueError('Invalid nhentai request')
            self.send_json(result); return
        if action=='source-attach' and self.command=='POST':
            with db.transaction() as c:
                c.execute('BEGIN IMMEDIATE')
                if not importer.source_identity(data.get('url','')): raise ValueError('Unsupported source URL')
                result=import_matching.attach(c,data.get('target'),data['url'],data.get('source_titles',[]))
            self.send_json(result); return
        incoming=None
        if action=='import' and self.command=='POST':
            with db.transaction() as c:
                matches=db.exact_sources(c,data['url'],data.get('exclude',''))
                if matches: raise db.DuplicateSource(matches)
            incoming=importer.import_url(data['url'])
        with db.transaction() as c:
            if action=='config': result={'token':TOKEN,'dimensions':db.dimensions(c),'symbols':db.SYMBOLS,'categories':CATEGORIES}
            elif action=='works':
                if self.command=='GET':
                    if ident: result=db.get_work(c,ident)
                    elif g('ids')=='1': result={'ids':features.batch_targets(c,{'all':True,'query':g('q')})}
                    else: result=db.list_works(c,g('q'),g('sort','newest'),max(0,int(g('offset','0'))),min(100,max(1,int(g('limit','40')))),g('seed','0'),g('random')=='1')
                elif self.command=='POST' and ident and len(parts)>2 and parts[2]=='open': result=db.get_work(c,ident,True)
                elif self.command in ('POST','PUT'):
                    if ident and not c.execute('SELECT 1 FROM works WHERE id=? AND owner=?',(ident,db.OWNER)).fetchone(): raise ValueError('Entry not found')
                    result=features.save_work(c,data,ident)
                elif self.command=='DELETE': db.delete_work(c,ident); result={'ok':True}
            elif action=='trash':
                if self.command=='GET': result=features.trash_list(c)
                elif self.command=='POST' and ident=='restore-preview': result=features.restore_preview(c,data.get('ids',[]))
                elif self.command=='POST' and ident=='restore': result=features.restore(c,data.get('ids',[]),data.get('signature'))
                elif self.command=='DELETE':
                    if not c.in_transaction: c.execute('BEGIN IMMEDIATE')
                    ids=[ident] if ident else [r['id'] for r in c.execute('SELECT id FROM works WHERE owner=? AND deleted_at IS NOT NULL',(db.OWNER,))]
                    for wid in ids:
                        w=db.get_work(c,wid,include_deleted=True)
                        if not w['deleted_at']: raise ValueError('Entry is not in Trash')
                    for wid in ids: db.purge_work(c,wid)
                    result={'ok':True}
                else: raise ValueError('Invalid Trash request')
            elif action=='history':
                if self.command=='GET': result=features.history(c)
                elif self.command=='POST' and ident: result=features.undo(c,ident,len(parts)>2 and parts[2]=='undo')
                else: raise ValueError('Invalid history request')
            elif action=='saved-searches':
                if self.command=='GET': result=features.searches(c)
                elif self.command=='POST' and ident=='reorder': result=features.reorder_searches(c,data.get('ids'))
                elif self.command in ('POST','PUT'): result=features.save_search(c,data,ident)
                elif self.command=='DELETE': c.execute('DELETE FROM saved_searches WHERE id=? AND owner=?',(ident,db.OWNER)); result={'ok':True}
                else: raise ValueError('Invalid saved search request')
            elif action=='batch' and self.command=='POST':
                result=features.batch_apply(c,data.get('id')) if ident=='apply' else features.batch_preview(c,data) if ident=='preview' else None
                if result is None: raise ValueError('Invalid batch request')
            elif action=='entities':
                if self.command=='GET':
                    if ident:
                        row=c.execute('SELECT e.*, (SELECT count(*) FROM work_entities WHERE entity_id=e.id) AS uses FROM entities e WHERE e.id=? AND owner=?',(tag_policy.entity_id(c,ident),db.OWNER)).fetchone()
                        if not row: raise ValueError('Metadata not found')
                        result=db.entity_data(c,row)
                    else: result=db.entity_list(c,g('kind') or None,g('q'),g('sort','name_asc'),max(0,int(g('offset','0'))),min(300,max(1,int(g('limit','300')))),g('paged')=='1')
                elif self.command=='POST' and len(parts)>2 and parts[2]=='merge-preview': result=tag_policy.merge_preview(c,ident,data['target'])
                elif self.command=='POST' and len(parts)>2 and parts[2]=='merge': result=tag_policy.merge(c,ident,data['target'],data.get('signature'),data.get('metadata'))
                elif self.command=='POST' and ident=='attribute': result=[e for e in tag_policy.matches(c,data.get('name',''),data.get('gender','neutral')) if tag_policy.key(e['name'])==tag_policy.key(data.get('name',''))]
                elif self.command=='POST' and ident=='check': result={'conflicts':tag_policy.check(c,data,data.get('exclude'))}
                elif self.command in ('POST','PUT'): result={'id':tag_policy.save(c,data,ident)}
                elif self.command=='DELETE': c.execute('DELETE FROM entities WHERE id=? AND owner=?',(ident,db.OWNER)); result={'ok':True}
            elif action=='dimensions':
                if self.command=='POST' and ident and len(parts)==3 and parts[2]=='preview': result=db.dimension_preview(c,ident,data.get('maximum'))
                elif self.command=='GET': result=db.dimensions(c)
                elif self.command in ('POST','PUT'): result={'id':features.save_dimension(c,data,ident)}
                elif self.command=='DELETE': c.execute('DELETE FROM dimensions WHERE id=? AND owner=?',(ident,db.OWNER)); result={'ok':True}
            elif action=='suggestions':
                text=g('q'); field=g('field')
                if field=='none': field='neutral'
                kind=field if field in ('author','circle','tag','series','character') else 'tag' if field in ('female','male','neutral') else None
                result=[]
                for e in db.entity_list(c,kind,text)[:25]:
                    if field in ('female','male','neutral') and e['gender']!=field: continue
                    f=e['gender'] if e['kind']=='tag' and e['gender']!='neutral' else e['kind']
                    result.append({'label':e['display_name'],'field':f,'value':e['name'],'detail':e['kind']+' / '+e['gender'] if e['kind']=='tag' and e['gender']!='neutral' else e['kind']})
                for d in db.dimensions(c):
                    if text.casefold() in d['name'].casefold() or text.casefold() in 'rating'+str(d['number']): result.append({'label':d['name'],'field':'rating'+str(d['number']),'value':'>=1','detail':f'1–{d["maximum"]}'})
            elif action=='source-check' and self.command=='POST':
                if data.get('generic'):
                    value=db.url(data.get('url','')); result={'url':value,'matches':db.exact_sources(c,value)}
                else: result=db.source_matches(c,data.get('url',''))
            elif action=='import' and self.command=='POST':
                matches=db.exact_sources(c,data['url'],data.get('exclude',''))
                if matches: raise db.DuplicateSource(matches)
                result=incoming
                if nhentai.location(data['url']): import_matching.apply_tags(c,result,data.get('tag_mode',import_jobs.default_tag_mode(c)))
                result['cross_candidates']=import_matching.candidates(c,result,data['url'],data.get('exclude',''))
                title=result.get('title','').strip()
                result['title_matches']=import_matching.title_matches(c,[title,*result.get('source_titles',[])],data.get('exclude','')) if title else []
                for match in result['title_matches']: match['evidence']=import_matching.candidate_evidence(c,match,result)
                result['related_matches']=[r for r in db.source_matches(c,data['url'])['matches'] if r['id']!=data.get('exclude','')]
                result['ambiguities']=tag_policy.resolve_tags(c,result)
                for kind in ('tag','author','circle','series','character'):
                    if kind=='tag': continue
                    for item in result.get(kind,[]):
                        exact=c.execute('SELECT * FROM entities WHERE owner=? AND kind=? AND gender=? AND name=?',(db.OWNER,kind,item.get('gender','neutral'),item['name'])).fetchone()
                        if exact:
                            item.update(db.entity_data(c,exact)); continue
                        if item.get('literal_name'): continue
                        rows=c.execute('SELECT DISTINCT e.* FROM entities e JOIN aliases a ON a.entity_id=e.id WHERE e.owner=? AND e.kind=? AND e.gender=? AND a.name=?',(db.OWNER,kind,item.get('gender','neutral'),item['name'])).fetchall()
                        if len(rows)==1: item.update(db.entity_data(c,rows[0]))
                        if len(rows)>1: result['ambiguities'].append({'kind':kind,'name':item['name'],'gender':item.get('gender','neutral'),'choices':[db.entity_data(c,r) for r in rows]})
            elif action=='bookmarks' and self.command=='POST':
                result=importer.bookmarks(data['html'])
                for item in result:
                    if item['supported']:
                        lookup=db.source_matches(c,item['url'])
                        item['registered']=lookup['match']=='exact'
                        item['duplicate']=item['duplicate'] or item['registered']
                        item['related']=lookup['matches'] if lookup['match']=='gallery' else []
            elif action=='covers' and ident=='resolve' and self.command=='POST': result={'url':importer.resolve_thumbnail_url(data['url'])}
            elif action=='jobs':
                if self.command=='GET': result=jobs(c,ident)
                elif self.command=='POST' and ident:
                    if len(parts)!=3: raise ValueError('Invalid import job action')
                    if parts[2]=='tags': result=import_jobs.decide_tags(c,ident,data)
                    elif parts[2]=='decide': result=import_jobs.decide(c,ident,data)
                    else:
                        import_jobs.control(c,ident,parts[2],data); result=jobs(c,ident)
                elif self.command=='POST': result=import_jobs.create(c,data)
                else: raise ValueError('Invalid import job request')
            elif action=='backup' and self.command=='POST': result={'file':str(db.backup())}
            else: raise ValueError('Unknown API request')
        self.send_json(result)
    def run(self):
        try: self.dispatch()
        except cover_relay.RelayError as e: self.send_json({'error':str(e)},502)
        except tag_policy.Conflict as e: self.send_json({'error':str(e),'tag_conflicts':e.conflicts,'signature':e.signature},409)
        except db.DuplicateSource as e: self.send_json({'error':str(e),'matches':e.matches},409)
        except sqlite3.IntegrityError as e:
            msg='Duplicate title' if 'works.owner, works.title' in str(e) else 'Duplicate metadata name or invalid association'
            self.send_json({'error':msg},409)
        except (ValueError,KeyError,TypeError) as e: self.send_json({'error':str(e)},400)
        except (BrokenPipeError,ConnectionResetError,TimeoutError): pass
        except Exception as e:
            print('Request failed:',type(e).__name__,flush=True)
            self.send_json({'error':'Server operation failed; your draft has been retained'},500)
    do_GET=run; do_POST=run; do_PUT=run; do_DELETE=run; do_HEAD=run

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--host',default=os.environ.get('MEDIA_HOST','0.0.0.0')); parser.add_argument('--port',type=int,default=int(os.environ.get('MEDIA_PORT','8765'))); parser.add_argument('--backup',action='store_true'); parser.add_argument('--restore')
    args=parser.parse_args()
    if args.restore:
        source=sqlite3.connect(args.restore); check=source.execute('PRAGMA integrity_check').fetchone()[0]
        if check!='ok': raise ValueError('Backup integrity check failed')
        if db.PATH.exists(): db.backup()
        db.PATH.parent.mkdir(parents=True,exist_ok=True); target=sqlite3.connect(db.PATH); source.backup(target); target.close(); source.close()
        print('Restored. Start the server normally.'); return
    db.init()
    if args.backup: print(db.backup()); return
    threading.Thread(target=worker,daemon=True).start()
    server=LibraryHTTPServer((args.host,args.port),Handler)
    print(f'Personal Media Library ready: http://localhost:{args.port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: STOP.set(); server.server_close()

if __name__=='__main__': main()
