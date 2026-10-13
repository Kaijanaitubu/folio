"""Synthetic HTML, source boundary, tag policy, durable imports and RAM relay tests."""
from pathlib import Path
import tempfile
import unittest
import json
import threading
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from unittest.mock import Mock,patch
import db, importer, import_jobs, import_matching, momonga, cover_sources, cover_relay
import server

URL='https://momon-ga.com/fanzine/mo123/'
HTML='''<a href="/tag/not-this/" rel="tag">Sidebar</a>
<div id="post-data"><h1>日本語 &amp; タイトル <span>1</span></h1>
<div class="history" data-title="Fallback"></div><div id="post-number">2ページ</div>
<div id="post-tag"><a href="/cartoonist/alice/" rel="tag">Alice | Alias</a>
<a href="/group/circle/" rel="tag">Circle</a><a href="/parody/story/" rel="tag">Series</a>
<a href="/character/person/" rel="tag">Character</a><a href="/tag/digital/" rel="tag">Digital</a>
<a href="/tag/digital/" rel="tag">Digital</a><a href="https://evil.test/tag/x/" rel="tag">Bad</a></div>
<div id="post-hentai"><img src="https://z2.momon-ga.me/galleries/123/1.webp"><img src="https://z2.momon-ga.me/galleries/123/2.webp"></div></div>
<h1>Related work</h1><a href="/cartoonist/other/" rel="tag">Other</a>'''

class AdapterTests(unittest.TestCase):
    def test_main_content_scope_and_mapping(self):
        data=momonga.parse_page(HTML,URL)
        self.assertEqual(data['title'],'日本語 & タイトル 1')
        self.assertEqual(data['source_titles'],[data['title']])
        self.assertEqual(data['pages'],2); self.assertEqual(data['category'],'doujinshi')
        self.assertEqual(data['series'],[{'name':'Series'}]);self.assertEqual(data['author'],[{'name':'Alice | Alias'}])
        self.assertEqual(data['circle'],[{'name':'Circle'}]);self.assertEqual(data['character'],[{'name':'Character'}])
        self.assertEqual(data['tag'],[{'name':'Digital','gender':'neutral'}])
        self.assertEqual(data['cover'],'https://z2.momon-ga.me/galleries/123/1.webp')
        self.assertEqual(momonga.parse_page(HTML,URL.replace('fanzine','magazine'))['category'],'manga')
    def test_url_boundaries(self):
        self.assertEqual(importer.source_identity(URL),('momonga','123'))
        self.assertEqual(db.normalize_url('http://www.momon-ga.com/fanzine/mo123?utm=x'),URL)
        for u in ('https://momon-ga.com.evil/fanzine/mo123/','https://user@momon-ga.com/fanzine/mo123/','https://momon-ga.com:444/fanzine/mo123/','https://momon-ga.com/tag/x/','https://momon-ga.com/fanzine/mo0/','file:///fanzine/mo123/'):
            self.assertIsNone(momonga.location(u))
        self.assertTrue(importer.attribute_less_source(URL))
        self.assertFalse(importer.attribute_less_source('https://hitomi.la/reader/1.html'))
    def test_bookmarks_and_no_title_failure(self):
        rows=importer.bookmarks(f'<DL><A HREF="{URL}">Bookmark</A><A HREF="http://www.momon-ga.com/fanzine/mo123?">Duplicate</A></DL>')
        self.assertTrue(all(r['supported'] for r in rows));self.assertTrue(rows[1]['duplicate'])
        with self.assertRaises(ValueError):momonga.parse_page('<h1>Challenge</h1>',URL)
        self.assertTrue(momonga.parse_page(HTML.replace('/123/1.webp','/999/1.webp'),URL)['warnings'])
    def test_image_boundaries_and_memory_cache(self):
        data=momonga.parse_page(HTML.replace('z2.momon-ga.me','z3.momon-ga.me'),URL)
        self.assertEqual(data['cover'],'https://z3.momon-ga.me/galleries/123/1.webp')
        value='https://z2.momon-ga.me/galleries/123/1.webp'
        for bad in (value+'?x=1',value+'#x',value.replace('z2.','evil.'),value.replace('/1.webp','/../evil'),value.replace('https:','http:')):
            self.assertFalse(momonga.valid_image(bad))
        with patch.object(cover_relay,'CACHE',cover_relay.MemoryCache()),patch('momonga.fetch_image',return_value=('image/webp',b'fixture')) as fetch:
            self.assertEqual(cover_sources.load(value),('image/webp',b'fixture')); cover_sources.load(value);fetch.assert_called_once()
        with patch('momonga.response',return_value=('image/webp',b'<html>')):
            with self.assertRaises(ValueError):momonga.fetch_image(value)
        with patch.object(cover_relay,'CACHE',cover_relay.MemoryCache()),patch('momonga.fetch_image',return_value=('image/webp',b'fixture')) as fetch:
            cover_sources.load(data['cover']);fetch.assert_called_once_with(data['cover'])
    def test_network_rejects_private_address_and_status(self):
        with patch('momonga.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]),patch('momonga.socket.socket') as sock:
            with self.assertRaises(ValueError):momonga.response(URL,100)
            sock.assert_not_called()
        r=Mock();r.status=302
        conn=Mock();conn.getresponse.return_value=r
        ctx=Mock();ctx.wrap_socket.return_value=Mock()
        with patch('momonga.socket.getaddrinfo',return_value=[(2,1,6,'',('8.8.8.8',443))]),patch('momonga.socket.socket'),patch('momonga.ssl.create_default_context',return_value=ctx),patch('momonga.http.client.HTTPSConnection',return_value=conn):
            with self.assertRaisesRegex(ValueError,'302'):momonga.response(URL,100)
    def test_pause_before_network(self):
        token=momonga.CANCEL.set(lambda:True)
        try:
            with patch('momonga.response') as fetch:
                with self.assertRaises(ValueError):momonga.fetch(URL)
                fetch.assert_not_called()
        finally:momonga.CANCEL.reset(token)

class JobTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=db.ROOT/'test-output');self.old=db.PATH
        db.PATH=Path(self.temp.name)/'test.sqlite3';db.init()
    def tearDown(self): db.PATH=self.old;self.temp.cleanup()
    def test_existing_manual_link_key_migration_preserves_work(self):
        value='http://www.momon-ga.com/fanzine/mo123?utm=x'
        with db.transaction() as c:
            work=db.save_work(c,{'title':'Manual entry','links':[{'url':value,'is_primary':True}]})
            work=db.get_work(c,work['id'])
            old_key='https://momon-ga.com/fanzine/mo123?utm=x'
            c.execute('UPDATE links SET url_key=? WHERE work_id=?',(old_key,work['id']))
            c.execute('DELETE FROM source_claims');c.execute('INSERT INTO source_claims VALUES(?,?,?)',(db.OWNER,old_key,work['id']))
            c.execute('DELETE FROM migrations WHERE version=9')
        db.init();db.init()
        with db.transaction() as c:
            self.assertEqual(db.get_work(c,work['id']),work)
            self.assertEqual(db.exact_sources(c,URL)[0]['id'],work['id'])
            self.assertEqual(c.execute('SELECT count(*) FROM source_claims').fetchone()[0],1)
    def test_frequency_bookmark_title_duplicate_and_secondary(self):
        with db.transaction() as c:
            old=db.save_work(c,{'title':'Existing','tag':[{'name':'Digital','gender':'female'}]})
            jid=import_jobs.create(c,{'items':[{'url':URL,'label':'Bookmark title'}],'title_mode':'bookmark','tag_mode':'frequency'})['id']
            item=dict(c.execute('SELECT * FROM job_items WHERE job_id=?',(jid,)).fetchone())
        with patch('momonga.fetch',return_value=HTML):import_jobs.process_item(item)
        with db.transaction() as c:
            row=c.execute('SELECT * FROM job_items WHERE id=?',(item['id'],)).fetchone()
            self.assertEqual(row['status'],'added');work=db.get_work(c,row['work_id'])
            self.assertEqual(work['title'],'Bookmark title'); self.assertEqual(work['tag'][0]['gender'],'female')
            self.assertEqual(work['series'][0]['name'],'Series')
            self.assertEqual(db.source_matches(c,URL)['match'],'exact')
            dupe=import_jobs.create(c,{'items':[{'url':'http://www.momon-ga.com/fanzine/mo123?'}]})['id']
            self.assertEqual(c.execute('SELECT status FROM job_items WHERE job_id=?',(dupe,)).fetchone()[0],'duplicate_url')
            result=import_matching.attach(c,old['id'],'https://momon-ga.com/magazine/mo456/')
            self.assertEqual(result['title'],'Existing'); self.assertEqual(result['links'][-1]['label'],'momon-ga')
            self.assertFalse(result['links'][-1]['is_primary'])

class HttpTests(unittest.TestCase):
    def setUp(self):
        JobTests.setUp(self)
        self.http=server.LibraryHTTPServer(('127.0.0.1',0),server.Handler)
        threading.Thread(target=self.http.serve_forever,daemon=True).start()
    def tearDown(self):
        self.http.shutdown();self.http.server_close();JobTests.tearDown(self)
    def request(self,path,data):
        request=Request(f'http://127.0.0.1:{self.http.server_address[1]}/api/'+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json','X-Library-Token':server.TOKEN})
        try:
            with urlopen(request,timeout=10) as r:return r.status,json.load(r)
        except HTTPError as e:return e.code,json.load(e)
    def test_interactive_frequency_exact_open_and_reimport(self):
        with db.transaction() as c:
            db.save_work(c,{'title':'Female tag fixture','tag':[{'name':'Digital','gender':'female'}]})
        with patch('momonga.fetch',return_value=HTML):
            status,data=self.request('import',{'url':URL,'tag_mode':'frequency'})
            self.assertEqual(status,200);self.assertEqual(data['tag'][0]['gender'],'female')
            self.assertEqual(data['series'][0]['name'],'Series')
            with db.transaction() as c:
                work=db.save_work(c,dict(data,links=[{'url':URL,'is_primary':True}]))
            self.assertEqual(self.request('source-check',{'url':URL})[1]['match'],'exact')
            self.assertEqual(self.request('import',{'url':URL})[0],409)
            self.assertEqual(self.request('import',{'url':URL,'exclude':work['id']})[0],200)
    def test_cross_site_candidate_and_attach_preserves_existing_fields(self):
        incoming=momonga.parse_page(HTML,URL)
        with db.transaction() as c:
            work=db.save_work(c,dict(incoming,links=[{'url':'https://nhentai.net/g/987/','is_primary':True}],review='Keep this'))
        with patch('momonga.fetch',return_value=HTML):
            status,result=self.request('import',{'url':URL})
            self.assertEqual(status,200);self.assertEqual(result['cross_candidates'][0]['id'],work['id'])
        status,result=self.request('source-attach',{'url':URL,'target':work['id']})
        self.assertEqual(status,200);self.assertEqual(result['review'],'Keep this')
        self.assertEqual(result['links'][0]['url'],'https://nhentai.net/g/987/')
        self.assertEqual(result['links'][-1]['label'],'momon-ga')

if __name__=='__main__':unittest.main()
