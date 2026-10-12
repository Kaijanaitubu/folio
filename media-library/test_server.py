"""HTTP contract and durable job checks using an isolated test server."""
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from unittest.mock import patch
import db
import server
import cover_relay

class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (db.ROOT/'test-output').mkdir(exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(dir=db.ROOT/'test-output');cls.old=db.PATH;db.PATH=Path(cls.temp.name)/'http.sqlite3';db.init()
        cls.server=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.port=cls.server.server_address[1]
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();db.PATH=cls.old;cls.temp.cleanup()
    def request(self,path,method='GET',data=None,token=True,origin=None):
        headers={'Content-Type':'application/json'}
        if token:headers['X-Library-Token']=server.TOKEN
        if origin:headers['Origin']=origin
        r=Request(f'http://127.0.0.1:{self.port}/api/'+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers=headers)
        try:
            with urlopen(r,timeout=15) as response:return response.status,json.load(response)
        except HTTPError as e:return e.code,json.load(e)
    def test_csrf_and_origin(self):
        self.assertEqual(self.request('works','POST',{'title':'Rejected'},token=False)[0],403)
        self.assertEqual(self.request('works','POST',{'title':'Rejected'},origin='https://evil.test')[0],403)
    def test_rating_scale_preview_confirm_and_stale_http(self):
        data={'name':'HTTP scale','maximum':3,'symbol':'Star'}
        status,result=self.request('dimensions','POST',data);self.assertEqual(status,200);did=result['id']
        _,w=self.request('works','POST',{'title':'HTTP scale work','ratings':{did:2}})
        data['maximum']=5
        self.assertEqual(self.request('dimensions/'+did,'PUT',data)[0],400)
        self.assertEqual(self.request('dimensions/'+did+'/preview','POST',{'maximum':5},token=False)[0],403)
        status,preview=self.request('dimensions/'+did+'/preview','POST',{'maximum':5})
        self.assertEqual(status,200);self.assertEqual(preview['changed'],1)
        self.assertEqual(self.request('works/'+w['id'])[1]['ratings'][did],2)
        data['conversion_signature']=preview['signature']
        self.assertEqual(self.request('dimensions/'+did,'PUT',data)[0],200)
        self.assertEqual(self.request('works/'+w['id'])[1]['ratings'][did],3)
        self.assertEqual(self.request('dimensions/'+did,'PUT',data)[0],400)
        self.assertEqual(self.request('dimensions/'+did+'/preview','POST',{'maximum':11})[0],400)
        self.assertEqual(self.request('dimensions/missing/preview','POST',{'maximum':3})[0],400)
        self.request('works/'+w['id'],'DELETE');self.request('dimensions/'+did,'DELETE')
    def test_http_save_open_update_search_delete(self):
        status,w=self.request('works','POST',{'title':'HTTP test','links':[{'url':'https://example.org/a?q=1#two'}]})
        self.assertEqual(status,200);self.assertIsNone(w['opened']);wid=w['id']
        self.assertEqual(self.request('works','POST',{'title':'HTTP test'})[0],200)
        _,opened=self.request('works/'+wid+'/open','POST',{});self.assertIsNotNone(opened['opened'])
        status,w=self.request('works/'+wid,'PUT',{'title':'HTTP renamed','review':'hidden'});self.assertEqual(status,200)
        self.assertEqual(self.request('works?q=review:hidden')[1]['total'],1)
        self.assertEqual(self.request('works?q=hidden')[1]['total'],0)
        self.assertEqual(self.request('works/'+wid,'DELETE')[0],200)
    def test_interactive_duplicate_and_partial_fixture(self):
        self.request('works','POST',{'title':'Existing import'})
        with patch('importer.import_url',return_value={'title':'Existing import','author':[],'circle':[],'tag':[]}):
            status,result=self.request('import','POST',{'url':'https://hitomi.la/reader/1.html'})
            self.assertEqual(status,200);self.assertEqual(result['title_matches'][0]['title'],'Existing import')
        with patch('importer.import_url',return_value={'title':'Partial result','author':[],'circle':[],'tag':[],'pages':None}):
            status,r=self.request('import','POST',{'url':'https://hitomi.la/reader/1.html'})
            self.assertEqual(status,200);self.assertIsNone(r['pages']);self.assertEqual(r['ambiguities'],[])
    def test_source_check_is_read_only_and_requires_request_token(self):
        _,work=self.request('works','POST',{'title':'Source check fixture','links':[{'url':'https://hitomi.la/reader/54321.html#3'}]})
        with patch('importer.import_url') as fetch:
            status,result=self.request('source-check','POST',{'url':'https://hitomi.la/reader/54321.html#3'})
            self.assertEqual(status,200);self.assertEqual(result['match'],'exact');self.assertEqual(result['matches'][0]['id'],work['id'])
            self.assertEqual(self.request('source-check','POST',{'url':'https://hitomi.la/reader/54321.html#4'})[1]['match'],'gallery')
            self.assertEqual(self.request('source-check','POST',{'url':'https://example.org/reader/54321.html'})[0],400)
            self.assertEqual(self.request('source-check','POST',{'url':'https://hitomi.la/reader/54321.html'},token=False)[0],403)
            fetch.assert_not_called()
        self.assertIsNone(self.request('works/'+work['id'])[1]['opened'])
    def test_source_draft_duplicate_title_is_warned_and_can_be_saved(self):
        self.request('works','POST',{'title':'Source duplicate title'})
        fixture={'title':'Source duplicate title','author':[],'circle':[],'tag':[],'warnings':[],'cover':'https://example.org/cover.webp'}
        with patch('importer.import_url',return_value=fixture):
            status,result=self.request('import','POST',{'url':'https://hitomi.la/reader/1.html','allow_duplicate_title':True})
        self.assertEqual(status,200);self.assertEqual(result['cover'],fixture['cover']);self.assertEqual(result['title_matches'][0]['title'],fixture['title'])
        self.assertEqual(self.request('works','POST',result)[0],200)
    def test_worker_job_recovery_and_duplicate_skip(self):
        self.request('works','POST',{'title':'Job duplicate'})
        _,j=self.request('jobs','POST',{'items':[{'url':'https://hitomi.la/reader/101.html'},{'url':'https://hitomi.la/reader/102.html'},{'url':'https://example.org/unsupported'}]})
        jid=j['id']
        with db.transaction() as c:c.execute("UPDATE job_items SET status='running' WHERE job_id=? AND url LIKE '%101.html'",(jid,))
        db.init() # Simulate restart: in-flight item goes back to pending.
        server.STOP=threading.Event()
        def fixture(url):return {'title':'Job duplicate' if '101' in url else 'Job added','author':[],'circle':[],'tag':[],'warnings':[]}
        with patch('importer.import_url',side_effect=fixture),patch('db.backup'):
            worker=threading.Thread(target=server.worker,daemon=True);worker.start()
            deadline=time.time()+8
            while time.time()<deadline:
                r=self.request('jobs/'+jid)[1]
                if r['status']=='complete':break
                time.sleep(.05)
            server.STOP.set();worker.join(2)
        self.assertEqual(r['status'],'complete');self.assertEqual(r['counts']['added'],2);self.assertEqual(r['counts']['unsupported'],1)
        self.assertTrue(any(i['warnings'].get('titles') for i in r['items']))
        _,r=self.request('jobs/'+jid+'/cancel','POST',{});self.assertEqual(r['status'],'cancelled')
    def test_metadata_display_sort_and_suggestions(self):
        from urllib.parse import urlencode
        status,e=self.request('entities','POST',{'kind':'series','name':'QA canonical','aliases':['QA 表示'],'display_alias':'QA 表示'})
        self.assertEqual(status,200)
        item=self.request('entities/'+e['id'])[1]
        self.assertEqual(item['display_name'],'QA 表示');self.assertEqual(item['name'],'QA canonical')
        _,page=self.request('entities?'+urlencode({'kind':'series','q':'QA 表示','paged':1,'sort':'name_desc','limit':1}))
        self.assertEqual(page['total'],1);self.assertEqual(page['items'][0]['id'],e['id'])
        _,suggestions=self.request('suggestions?'+urlencode({'field':'series','q':'QA 表示'}))
        self.assertEqual(suggestions[0]['label'],'QA 表示');self.assertEqual(suggestions[0]['value'],'QA canonical')
        self.assertEqual(self.request('entities?sort=bad')[0],400)
    def test_import_draft_uses_existing_display_alias(self):
        self.request('entities','POST',{'kind':'tag','name':'Fixture tag','gender':'female','aliases':['表示タグ'],'display_alias':'表示タグ'})
        fixture={'title':'Unique alias draft','author':[],'circle':[],'tag':[{'name':'Fixture tag','gender':'female'}]}
        with patch('importer.import_url',return_value=fixture):
            status,r=self.request('import','POST',{'url':'https://hitomi.la/reader/1.html'})
        self.assertEqual(status,200);self.assertEqual(r['tag'][0]['display_name'],'表示タグ')
        self.assertEqual(r['tag'][0]['name'],'Fixture tag');self.assertTrue(r['tag'][0]['id'])
    def test_bookmark_preview_http(self):
        status,r=self.request('bookmarks','POST',{'html':'<DL><A HREF="https://hitomi.la/reader/1.html">Test</A></DL>'})
        self.assertEqual(status,200);self.assertTrue(r[0]['supported'])
    def test_registered_secondary_url_skips_fetch_and_self_reimport_is_allowed(self):
        source='https://hitomi.la/reader/700001.html#4'
        _,work=self.request('works','POST',{'title':'Registered source','author':['Registered author'],'links':[{'url':'https://example.org/700001','is_primary':True},{'url':source}]})
        with patch('importer.import_url',return_value={'title':'Imported self','tag':[]}) as fetch:
            status,r=self.request('import','POST',{'url':'http://www.hitomi.la/reader/700001.html?#04'})
            self.assertEqual(status,409);self.assertEqual(r['matches'][0]['authors'],['Registered author']);fetch.assert_not_called()
            self.assertEqual(self.request('import','POST',{'url':source,'exclude':work['id']})[0],200);self.assertEqual(fetch.call_count,1)
        self.assertEqual(self.request('works','POST',{'title':'Other','links':[{'url':source}]})[0],409)
    def test_bookmark_preview_and_job_normalized_duplicates(self):
        self.request('works','POST',{'title':'Preview known','links':[{'url':'https://hitomi.la/reader/700002.html#2'}]})
        urls=['http://www.hitomi.la/reader/700002.html?#02','https://hitomi.la/reader/700002.html#3','https://hitomi.la/reader/700003.html','http://www.hitomi.la/reader/700003.html?#01']
        html='<DL>'+''.join(f'<A HREF="{u}">Bookmark</A>' for u in urls)+'</DL>'
        status,items=self.request('bookmarks','POST',{'html':html})
        self.assertEqual(status,200);self.assertTrue(items[0]['registered']);self.assertTrue(items[0]['duplicate']);self.assertTrue(items[1]['related']);self.assertFalse(items[1]['duplicate']);self.assertTrue(items[3]['duplicate'])
        status,job=self.request('jobs','POST',{'items':items,'title_mode':'bookmark'})
        self.assertEqual(status,200)
        result=self.request('jobs/'+job['id'])[1]
        self.assertEqual(result['title_mode'],'bookmark');self.assertEqual(result['counts'],{'duplicate_url':2,'pending':2})
        self.assertEqual(self.request('jobs','POST',{'items':items,'title_mode':'invalid'})[0],400)
        self.request('jobs/'+job['id']+'/cancel','POST',{})
    def test_thumbnail_url_resolution_without_image_fetch(self):
        image_hash='0'*61+'123'
        old='https://tn.hitomi.la/webpbigtn/3/12/'+image_hash+'.webp'
        with patch('importer.thumbnail_routes',return_value=(1,{0x312},0)),patch('importer.fetch') as fetch:
            status,r=self.request('covers/resolve','POST',{'url':old})
            self.assertEqual(status,200)
            self.assertEqual(r['url'],'https://atn.gold-usergeneratedcontent.net/webpbigtn/3/12/'+image_hash+'.webp')
            self.assertEqual(self.request('covers/resolve','POST',{'url':'http://127.0.0.1/private'})[0],400)
            fetch.assert_not_called()
    def test_cover_relay_binary_cache_headers_and_no_persistence(self):
        image_hash='0'*61+'123'
        _,w=self.request('works','POST',{'title':'Volatile cover test','cover':'https://tn.hitomi.la/webpbigtn/3/12/'+image_hash+'.webp'})
        image=b'RIFF\x10\x00\x00\x00WEBPunique-volatile-payload-not-for-storage'
        with patch('cover_relay.CACHE',cover_relay.MemoryCache()),patch('importer.thumbnail_routes',return_value=(0,set(),0)),patch('cover_relay.fetch_image',return_value=('image/webp',image)) as fetch:
            path=f'http://127.0.0.1:{self.port}/api/works/'+w['id']+'/cover'
            for method in ('GET','GET','HEAD'):
                with urlopen(Request(path,method=method),timeout=10) as response:
                    self.assertEqual(response.status,200)
                    self.assertEqual(response.headers['Content-Type'],'image/webp')
                    self.assertIn('no-store',response.headers['Cache-Control'])
                    self.assertEqual(response.headers['Cross-Origin-Resource-Policy'],'same-origin')
                    self.assertEqual(response.read(),image if method=='GET' else b'')
            self.assertEqual(fetch.call_count,1)
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(path,headers={'Sec-Fetch-Site':'cross-site'}),timeout=10)
            self.assertEqual(error.exception.code,403)
            error.exception.close()
            self.assertEqual(self.request('works/'+w['id'])[1],{k:v for k,v in w.items() if k!='warnings'})
            backup=db.backup(Path(self.temp.name)/'backups')
            self.assertNotIn(image,backup.read_bytes())
            self.assertFalse(any(p.suffix in ('.webp','.avif','.jpg') for p in Path(self.temp.name).rglob('*')))
    def test_saved_cover_change_reaches_detail_gallery_and_relay(self):
        from urllib.parse import quote
        first='https://tn.hitomi.la/webpbigtn/3/12/'+'0'*61+'123.webp'
        second='https://tn.hitomi.la/webpbigtn/6/45/'+'0'*61+'456.webp'
        _,work=self.request('works','POST',{'title':'Changed cover fixture','cover':first})
        def fetch(url):
            return 'image/webp',b'new-cover' if '456.webp' in url else b'old-cover'
        def read_cover(revision):
            path=f'http://127.0.0.1:{self.port}/api/works/{work["id"]}/cover?v='+quote(revision,safe='')
            with urlopen(path,timeout=10) as response:
                self.assertIn('no-store',response.headers['Cache-Control'])
                return response.read()
        with patch('cover_relay.CACHE',cover_relay.MemoryCache()),patch('importer.thumbnail_routes',return_value=(0,set(),0)),patch('cover_relay.fetch_image',side_effect=fetch) as upstream:
            self.assertEqual(read_cover(first),b'old-cover')
            status,saved=self.request('works/'+work['id'],'PUT',{'title':work['title'],'cover':second})
            self.assertEqual(status,200);self.assertEqual(saved['cover'],second)
            self.assertEqual(self.request('works/'+work['id'])[1]['cover'],second)
            gallery=self.request('works?q=title:%22Changed%20cover%20fixture%22')[1]
            self.assertEqual(gallery['items'][0]['cover'],second)
            self.assertEqual(read_cover(second),b'new-cover')
            self.assertEqual(read_cover('https://evil.test/ignored'),b'new-cover')
            self.assertEqual(upstream.call_count,2) # Cached by actual saved image, not query.
    def test_relay_only_fetches_saved_supported_covers(self):
        _,w=self.request('works','POST',{'title':'Unsupported cover test','cover':'http://127.0.0.1/private'})
        with patch('cover_relay.fetch_image') as fetch,patch('importer.fetch') as metadata:
            self.assertEqual(self.request('works/'+w['id']+'/cover')[0],400)
            self.assertEqual(self.request('works/missing/cover')[0],404)
            fetch.assert_not_called(); metadata.assert_not_called()
        with patch('cover_relay.load',side_effect=cover_relay.RelayError('Unavailable')):
            self.assertEqual(self.request('works/'+w['id']+'/cover')[0],502)

if __name__=='__main__':unittest.main(verbosity=2)
