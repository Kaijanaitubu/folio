"""Synthetic public-post fixtures, parser boundaries and real Folio HTTP contracts."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import db,importer,import_jobs,import_matching,pawchive,cover_sources,cover_relay,server

URL='https://pawchive.pw/fanbox/user/123/post/456'
SHORT='https://pawchive.pw/fanbox/post/456'
PATH='/aa/aa/'+'a'*64+'.jpg'
POST={'service':'fanbox','user':'123','id':'456','title':'日本語 投稿 & title','file':{'path':PATH},'attachments':[],'tags':'{digital,"tag, with comma","quote\\\"tag","back\\\\slash"}'}
PROFILE={'service':'fanbox','id':'123','name':'Synthetic Author'}

class AdapterTests(unittest.TestCase):
    def test_mapping_and_no_original_link_or_body(self):
        data=pawchive.parse_post(dict(POST,content='<p>Not library metadata</p>',origin='import'),PROFILE,URL)
        self.assertEqual(data['title'],POST['title']);self.assertEqual(data['author'],[{'name':PROFILE['name']}])
        self.assertEqual([t['name'] for t in data['tag']],['digital','tag, with comma','quote"tag','back\\slash'])
        self.assertTrue(all(t['gender']=='neutral' for t in data['tag']))
        self.assertEqual(data['cover'],'https://file.pawchive.pw/data'+PATH)
        self.assertEqual(data['source_label'],'Pawchive');self.assertEqual(data['category'],'')
        self.assertIsNone(data['pages']);self.assertNotIn('content',data);self.assertNotIn('links',data)
        self.assertEqual(data['circle'],[]);self.assertEqual(data['series'],[])
    def test_tag_arrays_and_invalid_format_warn_without_losing_metadata(self):
        for value,expected in ((None,[]),('{}',[]),(['digital','digital'],['digital']),('["one","two"]',['one','two']),('{one,two}',['one','two'])):
            self.assertEqual(pawchive.parse_tags(value),expected)
        for value in ('plain-text','{one,"unfinished}',{'tag':'one'},[123]):
            out=pawchive.parse_post(dict(POST,tags=value),PROFILE,URL)
            self.assertEqual(out['title'],POST['title']);self.assertEqual(out['tag'],[]);self.assertTrue(out['warnings'])
    def test_image_fallback_and_absent_metadata(self):
        out=pawchive.parse_post(dict(POST,file={'path':'/video.mp4'},attachments=[{'path':PATH}]),{},URL)
        self.assertTrue(out['cover']);self.assertEqual(out['author'],[]);self.assertTrue(out['warnings'])
        out=pawchive.parse_post(dict(POST,file=None,attachments=[{'path':'/archive.zip'}],tags=None),PROFILE,URL)
        self.assertEqual(out['cover'],'');self.assertTrue(out['warnings'])
        with self.assertRaises(ValueError):pawchive.parse_post(dict(POST,user='999'),PROFILE,URL)
        with self.assertRaises(ValueError):pawchive.parse_post(dict(POST,title=''),PROFILE,URL)
        self.assertEqual(pawchive.parse_post(POST,dict(PROFILE,id='999'),URL)['author'],[])
    def test_source_aliases_and_boundaries(self):
        alias='http://www.pawchive.pw/fanbox/user/123/post/456/?utm=x#image'
        self.assertEqual(pawchive.canonical(alias),URL)
        self.assertEqual(db.normalize_url(alias),SHORT);self.assertEqual(db.normalize_url(SHORT),SHORT)
        self.assertNotEqual(db.normalize_url(SHORT),db.normalize_url(SHORT.replace('fanbox','patreon')))
        self.assertTrue(importer.attribute_less_source(URL))
        self.assertEqual(importer.source_identity(URL),importer.source_identity(SHORT))
        for value in ('https://pawchive.pw.evil/fanbox/post/456','https://@pawchive.pw/fanbox/post/456','https://pawchive.pw:444/fanbox/post/456','https://pawchive.pw/discord/user/123/post/456','https://pawchive.pw/fanbox/user/123','https://pawchive.pw/fanbox/post/0'):
            self.assertIsNone(pawchive.location(value))
        rows=importer.bookmarks(f'<DL><A HREF="{URL}">First</A><A HREF="{SHORT}">Same</A></DL>')
        self.assertTrue(all(row['supported'] for row in rows));self.assertTrue(rows[1]['duplicate'])
    def test_short_redirect_is_validated_before_fetching_another_host(self):
        with patch('pawchive.fetch',return_value=(302,{'location':URL},'',b'')):
            self.assertEqual(pawchive.resolve(SHORT),URL)
        for destination in ('https://evil.test/fanbox/user/123/post/456',URL.replace('/456','/457'),URL.replace('fanbox','patreon'),URL+'?x=1',URL.replace('https:','http:')):
            with patch('pawchive.fetch',return_value=(302,{'location':destination},'',b'')) as fetch:
                with self.assertRaises(ValueError):pawchive.resolve(SHORT)
                fetch.assert_called_once()
    def test_profile_failure_is_only_a_warning(self):
        with patch('pawchive.fetch_json',side_effect=[POST,ValueError('profile unavailable')]):
            out=importer.import_url(URL)
        self.assertEqual(out['title'],POST['title']);self.assertEqual(out['author'],[])
        self.assertTrue(out['warnings'])
    def test_cover_signatures_ram_cache_and_thumbnail_fallback(self):
        cover='https://file.pawchive.pw/data'+PATH
        thumb='https://img.pawchive.pw/thumbnail/data'+PATH
        self.assertTrue(pawchive.valid_image(cover));self.assertTrue(pawchive.valid_image(thumb))
        for value in (cover+'?file=x',cover+'#x',cover.replace('file.','evil.'),cover.replace('/aa/aa/','/bb/aa/'),cover.replace('https:','http:'),cover.replace('.jpg','.zip')):
            self.assertFalse(pawchive.valid_image(value))
        webp=b'RIFF0000WEBPfixture'
        with patch('pawchive.request',side_effect=[ValueError('too large'),(200,{},'image/jpeg',webp)]) as request:
            self.assertEqual(pawchive.fetch_image(cover),('image/webp',webp))
            self.assertEqual(request.call_args.args[0],thumb)
        with patch.object(cover_relay,'CACHE',cover_relay.MemoryCache()),patch('pawchive.fetch_image',return_value=('image/webp',webp)) as fetch:
            cover_sources.load(cover);cover_sources.load(cover);fetch.assert_called_once()
        with patch('pawchive.request',return_value=(200,{},'image/jpeg',b'<html>')):
            with self.assertRaises(ValueError):pawchive.fetch_image(thumb)
    def test_private_dns_and_non_whitelisted_paths_are_rejected_before_socket(self):
        api='https://pawchive.pw/api/v1/fanbox/user/123/post/456'
        with patch('pawchive.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]),patch('pawchive.socket.socket') as socket:
            with self.assertRaises(ValueError):pawchive.request(api)
            socket.assert_not_called()
        with patch('pawchive.socket.getaddrinfo') as dns:
            for value in ('https://pawchive.pw/api/v1/account/favorites',api+'?x=1','https://evil.test'+PATH):
                with self.assertRaises(ValueError):pawchive.request(value)
            dns.assert_not_called()
    def test_response_status_and_size_are_bounded(self):
        api='https://pawchive.pw/api/v1/fanbox/user/123/post/456'
        response=Mock();response.status=200;response.getheaders.return_value=[('Content-Type','application/json'),('Content-Length',str(4*1024*1024+1))]
        conn=Mock();conn.getresponse.return_value=response;ctx=Mock();ctx.wrap_socket.return_value=Mock()
        with patch('pawchive.socket.getaddrinfo',return_value=[(2,1,6,'',('8.8.8.8',443))]),patch('pawchive.socket.socket'),patch('pawchive.ssl.create_default_context',return_value=ctx),patch('pawchive.http.client.HTTPSConnection',return_value=conn):
            with self.assertRaisesRegex(ValueError,'size limit'):pawchive.request(api)
            response.status=302;response.getheaders.return_value=[('Location','https://evil.test')]
            self.assertEqual(pawchive.request(api)[0],302)
            response.read1.assert_not_called()
    def test_cancel_prevents_network(self):
        token=pawchive.CANCEL.set(lambda:True)
        try:
            with patch('pawchive.request') as request:
                with self.assertRaisesRegex(ValueError,'paused'):pawchive.fetch(URL)
                request.assert_not_called()
        finally:pawchive.CANCEL.reset(token)

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=db.ROOT/'test-output')
        self.old=db.PATH;db.PATH=Path(self.temp.name)/'test.sqlite3';db.init()
        self.http=server.LibraryHTTPServer(('127.0.0.1',0),server.Handler)
        threading.Thread(target=self.http.serve_forever,daemon=True).start()
    def tearDown(self):
        self.http.shutdown();self.http.server_close();db.PATH=self.old;self.temp.cleanup()
    def request(self,path,data):
        request=Request(f'http://127.0.0.1:{self.http.server_address[1]}/api/'+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json','X-Library-Token':server.TOKEN})
        try:
            with urlopen(request,timeout=10) as response:return response.status,json.load(response)
        except HTTPError as e:return e.code,json.load(e)
    def test_individual_import_source_open_and_explicit_reimport(self):
        with db.transaction() as c:db.save_work(c,{'title':'Existing tag example','tag':[{'name':'digital','gender':'female'}]})
        with patch('pawchive.fetch_json',side_effect=lambda url:copy.deepcopy(PROFILE if url.endswith('/profile') else POST)):
            status,data=self.request('import',{'url':URL,'tag_mode':'frequency'})
            self.assertEqual(status,200);self.assertEqual(data['tag'][0]['gender'],'female')
            self.assertEqual(data['source_label'],'Pawchive')
            with db.transaction() as c:work=db.save_work(c,dict(data,links=[{'url':URL,'label':'Pawchive','is_primary':True}]))
            self.assertEqual(self.request('source-check',{'url':SHORT})[1]['match'],'exact')
            self.assertEqual(self.request('import',{'url':SHORT})[0],409)
            self.assertEqual(self.request('import',{'url':URL,'exclude':work['id']})[0],200)
    def test_bookmark_job_tag_policy_label_and_secondary_attachment(self):
        with db.transaction() as c:
            work=db.save_work(c,{'title':'Keep fields','review':'Keep review','tag':[{'name':'digital','gender':'female'}]})
            jid=import_jobs.create(c,{'items':[{'url':URL,'label':'Bookmark name'}],'title_mode':'bookmark','tag_mode':'frequency'})['id']
            item=dict(c.execute('SELECT * FROM job_items WHERE job_id=?',(jid,)).fetchone())
        with patch('pawchive.fetch_json',side_effect=lambda url:copy.deepcopy(PROFILE if url.endswith('/profile') else POST)):import_jobs.process_item(item)
        with db.transaction() as c:
            row=c.execute('SELECT * FROM job_items WHERE id=?',(item['id'],)).fetchone()
            self.assertEqual(row['status'],'added');added=db.get_work(c,row['work_id'])
            self.assertEqual(added['title'],'Bookmark name');self.assertEqual(next(t for t in added['tag'] if t['name']=='digital')['gender'],'female')
            self.assertEqual(added['links'][0]['label'],'Pawchive');self.assertEqual(len(added['links']),1)
            duplicate=import_jobs.create(c,{'items':[{'url':SHORT}]})['id']
            self.assertEqual(c.execute('SELECT status FROM job_items WHERE job_id=?',(duplicate,)).fetchone()[0],'duplicate_url')
            result=import_matching.attach(c,work['id'],URL.replace('/456','/789'))
            self.assertEqual(result['review'],'Keep review');self.assertEqual(result['links'][-1]['label'],'Pawchive')
    def test_old_manual_source_key_migration_preserves_library_fields(self):
        with db.transaction() as c:
            work=db.save_work(c,{'title':'Manual entry','links':[{'url':URL+'?tracking=1','is_primary':True}]})
            before=db.get_work(c,work['id']);old=URL+'?tracking=1'
            c.execute('UPDATE links SET url_key=? WHERE work_id=?',(old,work['id']))
            c.execute('DELETE FROM source_claims');c.execute('INSERT INTO source_claims VALUES(?,?,?)',(db.OWNER,old,work['id']))
            c.execute('DELETE FROM migrations WHERE version=12')
        db.init();db.init()
        with db.transaction() as c:
            self.assertEqual(db.get_work(c,work['id']),before)
            self.assertEqual(db.exact_sources(c,SHORT)[0]['id'],work['id'])
            self.assertEqual(c.execute('SELECT count(*) FROM source_claims').fetchone()[0],1)

if __name__=='__main__':unittest.main()
