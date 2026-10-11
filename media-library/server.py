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
import importer
import cover_relay
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
        if jid: r['items']=[dict(i) for i in c.execute('SELECT * FROM job_items WHERE job_id=? ORDER BY rowid',(jid,))]
    return rows[0] if jid and rows else rows

def worker():
    last_backup=0
    while not STOP.is_set():
        cover_relay.CACHE.prune()
        if time.time()-last_backup>86400:
            try: db.backup(); last_backup=time.time()
            except Exception: last_backup=time.time()-86340
        with db.transaction() as c:
            item=c.execute("SELECT i.* FROM job_items i JOIN jobs j ON j.id=i.job_id WHERE j.status='running' AND i.status='pending' ORDER BY j.created,i.rowid LIMIT 1").fetchone()
            if item:
                item=dict(item); c.execute("UPDATE job_items SET status='running',attempts=attempts+1 WHERE id=?",(item['id'],))
            else:
                c.execute("UPDATE jobs SET status='complete' WHERE status='running' AND NOT EXISTS(SELECT 1 FROM job_items WHERE job_id=jobs.id AND status IN ('pending','running'))")
        if not item: STOP.wait(1); continue
        status='failed'; title=''; message=''; wid=None
        try:
            data=importer.import_url(item['url']); title=data['title'].strip()
            if not title: raise ValueError('No title retrieved; retry or add manually')
            data['links']=[{'url':item['url'],'is_primary':True}]
            # Work and final item status are committed together; restart cannot duplicate a saved item.
            with db.transaction() as c:
                existing=c.execute('SELECT 1 FROM works WHERE owner=? AND title=?',(db.OWNER,title)).fetchone()
                if existing: status='duplicate_title'
                else:
                    result=db.save_work(c,data); wid=result['id']; status='added'
                    message='; '.join(data.get('warnings',[]))
                    if result['warnings']: message+=' Shared URL: '+', '.join(result['warnings'])
                c.execute('UPDATE job_items SET status=?,title=?,message=?,work_id=? WHERE id=?',(status,title,message,wid,item['id']))
        except Exception as e:
            message=str(e)
            status='needs_review' if 'Ambiguous alias' in message else 'failed'
            if 'UNIQUE constraint failed: works.owner, works.title' in message: status='duplicate_title'
            with db.transaction() as c:
                attempts=c.execute('SELECT attempts FROM job_items WHERE id=?',(item['id'],)).fetchone()[0]
                transient=any(s in message for s in ('429','503','timed out','Timeout'))
                if transient and attempts<3:
                    status='pending'
                c.execute('UPDATE job_items SET status=?,title=?,message=? WHERE id=?',(status,title,message,item['id']))
            if status=='pending': STOP.wait(min(30,2**attempts*2))
        STOP.wait(0.5)

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
            self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' http: https:; style-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            if self.command!='HEAD': self.wfile.write(raw)
            return
        parts=path.strip('/').split('/')[1:]; action=parts[0]; ident=parts[1] if len(parts)>1 else None
        if action=='works' and ident and len(parts)==3 and parts[2]=='cover':
            if self.command not in ('GET','HEAD'): raise ValueError('Invalid cover request')
            self.send_cover(ident); return
        data=self.body() if self.command in ('POST','PUT') else {}
        with db.transaction() as c:
            if action=='config': result={'token':TOKEN,'dimensions':db.dimensions(c),'symbols':db.SYMBOLS,'categories':CATEGORIES}
            elif action=='works':
                if self.command=='GET':
                    if ident: result=db.get_work(c,ident)
                    else: result=db.list_works(c,g('q'),g('sort','newest'),max(0,int(g('offset','0'))),min(100,max(1,int(g('limit','40')))),g('seed','0'),g('random')=='1')
                elif self.command=='POST' and ident and len(parts)>2 and parts[2]=='open': result=db.get_work(c,ident,True)
                elif self.command in ('POST','PUT'):
                    if ident and not c.execute('SELECT 1 FROM works WHERE id=? AND owner=?',(ident,db.OWNER)).fetchone(): raise ValueError('Entry not found')
                    result=db.save_work(c,data,ident)
                elif self.command=='DELETE': c.execute('DELETE FROM works WHERE id=? AND owner=?',(ident,db.OWNER)); result={'ok':True}
            elif action=='entities':
                if self.command=='GET':
                    if ident:
                        row=c.execute('SELECT e.*, (SELECT count(*) FROM work_entities WHERE entity_id=e.id) AS uses FROM entities e WHERE e.id=? AND owner=?',(ident,db.OWNER)).fetchone()
                        if not row: raise ValueError('Metadata not found')
                        result=db.entity_data(c,row)
                    else: result=db.entity_list(c,g('kind') or None,g('q'),g('sort','name_asc'),max(0,int(g('offset','0'))),min(300,max(1,int(g('limit','300')))),g('paged')=='1')
                elif self.command=='POST' and len(parts)>2 and parts[2]=='merge': db.merge(c,ident,data['target']); result={'ok':True}
                elif self.command in ('POST','PUT'): result={'id':db.save_entity(c,data,ident)}
                elif self.command=='DELETE': c.execute('DELETE FROM entities WHERE id=? AND owner=?',(ident,db.OWNER)); result={'ok':True}
            elif action=='dimensions':
                if self.command=='GET': result=db.dimensions(c)
                elif self.command in ('POST','PUT'): result={'id':db.save_dimension(c,data,ident)}
                elif self.command=='DELETE': c.execute('DELETE FROM dimensions WHERE id=? AND owner=?',(ident,db.OWNER)); result={'ok':True}
            elif action=='suggestions':
                text=g('q'); field=g('field')
                kind=field if field in ('author','circle','tag','series','character') else 'tag' if field in ('female','male','neutral') else None
                result=[]
                for e in db.entity_list(c,kind,text)[:25]:
                    if field in ('female','male','neutral') and e['gender']!=field: continue
                    f=e['gender'] if e['kind']=='tag' and e['gender']!='neutral' else e['kind']
                    result.append({'label':e['display_name'],'field':f,'value':e['name'],'detail':e['kind']+' / '+e['gender'] if e['kind']=='tag' else e['kind']})
                for d in db.dimensions(c):
                    if text.casefold() in d['name'].casefold() or text.casefold() in 'rating'+str(d['number']): result.append({'label':d['name'],'field':'rating'+str(d['number']),'value':'>=1','detail':f'1–{d["maximum"]}'})
            elif action=='import' and self.command=='POST':
                result=importer.import_url(data['url'])
                title=result.get('title','').strip()
                if title and c.execute('SELECT 1 FROM works WHERE owner=? AND title=? AND id<>?',(db.OWNER,title,data.get('exclude',''))).fetchone(): raise ValueError('Duplicate title; import skipped: '+title)
                result['ambiguities']=[]
                for kind in ('tag','author','circle','series','character'):
                    for item in result.get(kind,[]):
                        exact=c.execute('SELECT * FROM entities WHERE owner=? AND kind=? AND gender=? AND name=?',(db.OWNER,kind,item.get('gender','neutral'),item['name'])).fetchone()
                        if exact:
                            item.update(db.entity_data(c,exact)); continue
                        rows=c.execute('SELECT DISTINCT e.* FROM entities e JOIN aliases a ON a.entity_id=e.id WHERE e.owner=? AND e.kind=? AND e.gender=? AND a.name=?',(db.OWNER,kind,item.get('gender','neutral'),item['name'])).fetchall()
                        if len(rows)==1: item.update(db.entity_data(c,rows[0]))
                        if len(rows)>1: result['ambiguities'].append({'kind':kind,'name':item['name'],'gender':item.get('gender','neutral'),'choices':[db.entity_data(c,r) for r in rows]})
            elif action=='bookmarks' and self.command=='POST': result=importer.bookmarks(data['html'])
            elif action=='covers' and ident=='resolve' and self.command=='POST': result={'url':importer.resolve_thumbnail_url(data['url'])}
            elif action=='jobs':
                if self.command=='GET': result=jobs(c,ident)
                elif self.command=='POST' and ident:
                    if len(parts)>2 and parts[2]=='cancel':
                        c.execute("UPDATE jobs SET status='cancelled' WHERE id=? AND owner=?",(ident,db.OWNER)); c.execute("UPDATE job_items SET status='cancelled' WHERE job_id=? AND status='pending'",(ident,))
                    elif len(parts)>2 and parts[2]=='retry':
                        c.execute("UPDATE job_items SET status='pending',attempts=0 WHERE job_id=? AND status IN ('failed','needs_review','cancelled')",(ident,)); c.execute("UPDATE jobs SET status='running' WHERE id=? AND owner=?",(ident,db.OWNER))
                    result=jobs(c,ident)
                elif self.command=='POST':
                    ident=db.uid(); c.execute('INSERT INTO jobs VALUES(?,?,?,?)',(ident,db.OWNER,'running',db.now())); seen=set()
                    for item in data.get('items',[]):
                        u=db.url(item['url'])
                        if not u or u in seen: continue
                        seen.add(u); status='pending' if importer.gallery_id(u) else 'unsupported'
                        c.execute('INSERT INTO job_items(id,job_id,url,label,folder,status) VALUES(?,?,?,?,?,?)',(db.uid(),ident,u,str(item.get('label','')),str(item.get('folder','')),status))
                    result={'id':ident}
            elif action=='backup' and self.command=='POST': result={'file':str(db.backup())}
            else: raise ValueError('Unknown API request')
        self.send_json(result)
    def run(self):
        try: self.dispatch()
        except cover_relay.RelayError as e: self.send_json({'error':str(e)},502)
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
