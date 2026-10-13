"""Official v2 fixtures, durable large imports, explicit matching and key isolation."""
import copy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch,Mock
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import db
import importer
import import_jobs as jobs
import import_matching as matching
import nhentai
import nhentai_credentials as credentials
import server
import cover_relay
import features

GALLERY={'id':101,'media_id':'999','title':{'japanese':'試験作品','english':'Test work','pretty':'Test'},'cover':{'path':'galleries/999/cover.jpg'},'num_pages':2,'pages':[{'number':1,'thumbnail':'galleries/999/1t.jpg'},{'number':2,'thumbnail':'galleries/999/2t.png'}],'tags':[{'type':kind,'name':name} for kind,name in [('artist','Alice'),('group','Circle'),('parody','Series'),('character','Character'),('tag','Digital'),('category','doujinshi'),('language','japanese'),('language','translated')]]}
KEY='synthetic-api-key-not-a-real-secret'

class AdapterTests(unittest.TestCase):
    def test_url_boundaries_and_pages(self):
        self.assertEqual(nhentai.location('http://www.nhentai.net/g/123/4/?utm=x'),('123',4))
        for value in ('https://nhentai.net.evil/g/1/','https://nhentai.net:444/g/1/','https://user@nhentai.net/g/1/','file:///g/1/','https://nhentai.net/g/1/0/','https://nhentai.net/api/v2/galleries/1'):
            self.assertIsNone(nhentai.location(value))
        self.assertEqual(db.normalize_url('http://www.nhentai.net/g/123?utm=a#x'),db.normalize_url('https://nhentai.net/g/123/'))
        self.assertNotEqual(db.normalize_url('https://nhentai.net/g/123/'),db.normalize_url('https://nhentai.net/g/123/1/'))
        self.assertNotEqual(db.normalize_url('https://nhentai.net/g/123/1/'),db.normalize_url('https://nhentai.net/g/123/2/'))
    def test_metadata_and_title_fallback(self):
        data=nhentai.parse_gallery(GALLERY,2)
        self.assertEqual(data['title'],'試験作品'); self.assertEqual(data['language'],'japanese');self.assertEqual(data['category'],'doujinshi')
        self.assertEqual(data['tag'],[{'name':'Digital','gender':'neutral'}]);self.assertEqual(data['author'][0]['name'],'Alice')
        self.assertTrue(data['cover'].endswith('/2t.png'));self.assertEqual(data['source_titles'],['試験作品','Test work','Test'])
        changed=copy.deepcopy(GALLERY);changed['title']['japanese']='';self.assertEqual(nhentai.parse_gallery(changed)['title'],'Test work')
        self.assertTrue(nhentai.parse_gallery(GALLERY,99)['warnings'])
    def test_bookmarks_support_both_providers(self):
        items=importer.bookmarks('<DL><A HREF="https://nhentai.net/g/101/">A</A><A HREF="http://www.nhentai.net/g/101?">B</A><A HREF="https://hitomi.la/reader/1.html">C</A></DL>')
        self.assertTrue(all(i['supported'] for i in items));self.assertTrue(items[1]['duplicate'])
    def test_fixed_image_paths_and_memory_cache(self):
        value=nhentai.image_url('galleries/9/cover.jpg')
        for url in ('https://t.nhentai.net/../evil','https://t.nhentai.net/galleries/9/cover.jpg?next=http://localhost','https://t.nhentai.net.evil/galleries/9/cover.jpg','https://i.nhentai.net/galleries/9/1.jpg'):
            self.assertFalse(nhentai.valid_image(url))
        with patch('cover_relay.CACHE',cover_relay.MemoryCache()),patch('cover_relay.fetch_image',return_value=('image/jpeg',b'fixture')) as fetch:
            cover_relay.load(value);cover_relay.load(value);fetch.assert_called_once_with(value)
    def test_favorites_schema_and_malformed_response(self):
        fixture={'result':[{'id':12,'japanese_title':'日本語','english_title':'English'}],'num_pages':100,'total':None}
        with patch('nhentai.request',return_value=fixture) as request:
            result=nhentai.favorites(3,'artist:alice',key=KEY)
            self.assertIsNone(result['total']);self.assertEqual(result['items'][0]['url'],'https://nhentai.net/g/12/');self.assertIn('page=3',request.call_args[0][0])
        with patch('nhentai.request',return_value={'result':[{'id':'bad'}],'num_pages':1}),self.assertRaises(ValueError):nhentai.favorites(key=KEY)
    def test_network_auth_status_and_limit(self):
        response=Mock();response.status=429;response.getheader.return_value='120'
        connection=Mock();connection.getresponse.return_value=response;raw=Mock();tls=Mock();context=Mock();context.wrap_socket.return_value=tls
        address=(2,1,6,'',('8.8.8.8',443))
        with patch('nhentai._next',{'favorites':0,'details':0}),patch('nhentai.socket.getaddrinfo',return_value=[address]),patch('nhentai.socket.socket',return_value=raw),patch('nhentai.ssl.create_default_context',return_value=context),patch('nhentai.http.client.HTTPSConnection',return_value=connection):
            with self.assertRaises(nhentai.ApiError) as error:nhentai.request('/api/v2/favorites?page=1',KEY)
            self.assertEqual(error.exception.retry_after,120);self.assertNotIn(KEY,str(error.exception))
            self.assertEqual(connection.request.call_args.kwargs['headers']['Authorization'],'Key '+KEY)
    def test_cancel_before_network(self):
        with patch('nhentai.socket.getaddrinfo') as network,self.assertRaises(nhentai.Cancelled):nhentai.request('/api/v2/galleries/1',key='',cancelled=lambda:True)
        network.assert_not_called()

class ImportTests(unittest.TestCase):
    def setUp(self):
        (db.ROOT/'test-output').mkdir(exist_ok=True);self.temp=tempfile.TemporaryDirectory(dir=db.ROOT/'test-output')
        self.old=db.PATH;db.PATH=Path(self.temp.name)/'library.sqlite3';db.init()
        self.key_patch=patch.object(credentials,'PATH',Path(self.temp.name)/'private'/'key.dpapi');self.key_patch.start()
        self.ram_patch=patch.object(credentials,'_key',KEY);self.ram_patch.start()
    def tearDown(self):self.ram_patch.stop();self.key_patch.stop();db.PATH=self.old;self.temp.cleanup()
    def save(self,data):
        with db.transaction() as c:return db.save_work(c,data)
    def new_job(self,items=(),**options):
        data=dict(options)
        if items or options.get('kind')!='favorites': data['items']=list(items)
        with db.transaction() as c:return jobs.create(c,data)['id']
    def process(self,jid,title='Test work',source_id=None):
        with db.transaction() as c:
            item=dict(c.execute("SELECT * FROM job_items WHERE job_id=? AND status='pending' ORDER BY rowid LIMIT 1",(jid,)).fetchone())
            c.execute("UPDATE job_items SET status='running',attempts=attempts+1 WHERE id=?",(item['id'],))
        data=nhentai.parse_gallery(GALLERY);data['title']=title;data['source_titles']=[title]
        with patch('importer.import_url',return_value=data):jobs.process_item(item)
        with db.transaction() as c:return dict(c.execute('SELECT * FROM job_items WHERE id=?',(item['id'],)).fetchone())
    def test_frequency_alias_tie_trash_and_freeze(self):
        female=self.save({'title':'F1','tag':[{'name':'digital','gender':'female','aliases':['Digital alias']} ]})
        self.save({'title':'F2','tag':[{'name':'digital','gender':'female'}]})
        male=self.save({'title':'M1','tag':[{'name':'digital','gender':'male'}]})
        with db.transaction() as c:
            snapshot=matching.tag_snapshot(c)
            self.assertEqual(matching.apply_tags(c,{'tag':[{'name':'DIGITAL'}]},'frequency',snapshot)['tag'][0]['gender'],'female')
            self.assertEqual(matching.apply_tags(c,{'tag':[{'name':'Digital alias'}]},'frequency',snapshot)['tag'][0]['id'],female['tag'][0]['id'])
            self.assertEqual(matching.apply_tags(c,{'tag':[{'name':'DIGITAL'}]},'neutral')['tag'][0]['gender'],'neutral')
            db.delete_work(c,female['id'])
            current=matching.tag_snapshot(c)
            self.assertEqual(matching.apply_tags(c,{'tag':[{'name':'digital'}]},'frequency',current)['tag'][0]['gender'],'neutral')
            self.assertEqual(matching.apply_tags(c,{'tag':[{'name':'digital'}]},'frequency',snapshot)['tag'][0]['gender'],'female')
    def test_ambiguous_alias_neutral_fallback_requires_choice(self):
        with db.transaction() as c:
            for name in ('A','B'):db.save_entity(c,{'kind':'tag','name':name,'aliases':['ambiguous']})
            data=matching.apply_tags(c,{'title':'literal','tag':[{'name':'ambiguous'}]},'frequency')
            import tag_policy
            conflicts=tag_policy.resolve_tags(c,data)
            self.assertEqual(len(conflicts[0]['choices']),2)
            with self.assertRaisesRegex(ValueError,'Ambiguous'): db.resolve(c,'tag',data['tag'][0])
    def test_candidates_require_cross_provider_and_author_compatibility(self):
        a=self.save({'title':'Test work','author':[{'name':'Alice','aliases':['アリス']}],'links':[{'url':'https://hitomi.la/reader/555.html'}]})
        self.save({'title':'Test work','author':['Bob'],'links':[{'url':'https://hitomi.la/reader/556.html'}]})
        self.save({'title':'Test work','author':['Alice'],'links':[{'url':'https://nhentai.net/g/102/'}]})
        with db.transaction() as c:
            found=matching.candidates(c,{'title':'ＴＥＳＴ work','author':[{'name':'アリス'}]},'https://nhentai.net/g/101/')
            self.assertEqual([i['id'] for i in found],[a['id']])
    def test_secondary_attach_preserves_personal_data_and_undo(self):
        a=self.save({'title':'Test work','author':['Alice'],'tag':[{'name':'personal','gender':'male'}],'cover':'https://example.org/cover.jpg','review':'my review','bought':True,'links':[{'url':'https://hitomi.la/reader/555.html','is_primary':True}]})
        with db.transaction() as c:
            result=matching.attach(c,a['id'],'https://nhentai.net/g/101/',['Original title'])
            for k in ('title','author','tag','cover','review','bought','ratings'):self.assertEqual(result[k],a[k])
            self.assertEqual(result['links'][0]['is_primary'],1);self.assertEqual(result['links'][1]['is_primary'],0)
            history=features.history(c)[0];features.undo(c,history['id'],True)
            self.assertEqual(len(db.get_work(c,a['id'])['links']),1)
    def test_apply_all_unique_and_future_matches_preserves_ambiguity(self):
        first=self.save({'title':'One','author':['Alice'],'links':[{'url':'https://hitomi.la/reader/1.html'}]})
        for i in (2,3):self.save({'title':'Many','author':['Alice'],'links':[{'url':f'https://hitomi.la/reader/{i}.html'}]})
        jid=self.new_job([{'url':f'https://nhentai.net/g/{i}/'} for i in (101,102,103)])
        item=self.process(jid,'One');self.assertEqual(item['status'],'match_review')
        other=self.process(jid,'Many');self.assertEqual(other['status'],'match_review')
        with db.transaction() as c:
            result=jobs.decide(c,jid,{'item_id':item['id'],'action':'attach','target':first['id'],'apply_all':True})
            self.assertEqual(result['resolved'],1);self.assertEqual(result['ambiguous'],1)
            self.assertEqual(c.execute('SELECT status FROM job_items WHERE id=?',(other['id'],)).fetchone()[0],'match_review')
        last=self.process(jid,'One');self.assertEqual(last['status'],'linked')
        with db.transaction() as c:
            result=jobs.decide(c,jid,{'item_id':other['id'],'action':'new','apply_all':True});self.assertEqual(result['resolved'],1)
            self.assertEqual(jobs.job(c,jid)['match_policy'],'new')
    def test_2500_favorites_durable_pagination_dedup_restart(self):
        jid=self.new_job(kind='favorites')
        for page in range(1,101):
            values=[{'url':f'https://nhentai.net/g/{i}/','title':f'Fixture {i}'} for i in range((page-1)*25+1,page*25+1)]
            with patch('nhentai.favorites',return_value={'items':values,'num_pages':100,'total':2500}):jobs.enumerate_page(jid)
            if page==50:db.init()
        with db.transaction() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM job_items WHERE job_id=?',(jid,)).fetchone()[0],2500)
            self.assertEqual(jobs.job(c,jid)['enumeration_done'],1);self.assertEqual(jobs.job(c,jid)['enumeration_page'],101)
            returned=server.jobs(c,jid);self.assertNotIn('credential_id',returned);self.assertNotIn('tag_snapshot',returned)
        backup=db.backup(Path(self.temp.name)/'backup');self.assertNotIn(KEY.encode(),backup.read_bytes())
    def test_repeated_pages_do_not_duplicate_and_registered_secondary_skips(self):
        self.save({'title':'known','links':[{'url':'https://hitomi.la/reader/1.html'},{'url':'https://nhentai.net/g/101/'}]})
        jid=self.new_job(kind='favorites')
        values=[{'url':'https://nhentai.net/g/101/'},{'url':'https://nhentai.net/g/102/'}]
        with patch('nhentai.favorites',return_value={'items':values,'num_pages':2,'total':None}):jobs.enumerate_page(jid);jobs.enumerate_page(jid)
        with db.transaction() as c:
            rows=c.execute('SELECT status FROM job_items WHERE job_id=?',(jid,)).fetchall();self.assertCountEqual([r[0] for r in rows],['duplicate_url','pending'])
    def test_disconnect_requires_original_key_and_resume(self):
        jid=self.new_job(kind='favorites');credentials.forget()
        with patch('nhentai.favorites') as remote:jobs.enumerate_page(jid);remote.assert_not_called()
        with db.transaction() as c:self.assertEqual(jobs.job(c,jid)['status'],'awaiting_key')
        credentials.set_key(KEY+'other')
        with db.transaction() as c,self.assertRaises(ValueError):jobs.control(c,jid,'resume',{})
        credentials.set_key(KEY)
        with db.transaction() as c:jobs.control(c,jid,'resume',{});self.assertEqual(jobs.job(c,jid)['status'],'running')
    def test_rate_limit_retry_and_pause(self):
        jid=self.new_job(kind='favorites')
        jobs.failure(jid,nhentai.ApiError(429,80))
        with db.transaction() as c:
            current=jobs.job(c,jid);self.assertEqual(current['status'],'running');self.assertGreater(current['next_run'],0)
            jobs.control(c,jid,'pause',{});self.assertEqual(jobs.job(c,jid)['status'],'paused')
    def test_cancel_during_fetch_does_not_save(self):
        jid=self.new_job([{'url':'https://nhentai.net/g/101/'}])
        with db.transaction() as c:item=dict(c.execute('SELECT * FROM job_items WHERE job_id=?',(jid,)).fetchone())
        def fetch(value):
            with db.transaction() as c:jobs.control(c,jid,'cancel',{})
            return nhentai.parse_gallery(GALLERY)
        with patch('importer.import_url',side_effect=fetch):jobs.process_item(item)
        with db.transaction() as c:self.assertEqual(c.execute('SELECT count(*) FROM works').fetchone()[0],0)
    def test_manual_sources_migration_preserves_entries_and_rekeys_claims(self):
        work=self.save({'title':'Old manual source','links':[{'url':'http://www.nhentai.net/g/101?utm=old'}]})
        old='https://nhentai.net/g/101?utm=old'
        with db.transaction() as c:
            c.execute('UPDATE links SET url_key=? WHERE work_id=?',(old,work['id']))
            c.execute('DELETE FROM source_claims WHERE work_id=?',(work['id'],))
            c.execute('INSERT INTO source_claims VALUES(?,?,?)',(db.OWNER,old,work['id']))
            c.execute('DELETE FROM migrations WHERE version=5')
        db.init()
        with db.transaction() as c:
            self.assertEqual(db.exact_sources(c,'https://nhentai.net/g/101/')[0]['id'],work['id'])
            self.assertEqual(db.get_work(c,work['id'])['links'][0]['url'],'http://www.nhentai.net/g/101?utm=old')
            self.assertEqual(c.execute('SELECT url_key FROM source_claims').fetchone()[0],'https://nhentai.net/g/101/')
    @unittest.skipUnless(os.name=='nt','DPAPI requires Windows')
    def test_windows_key_roundtrip_and_forget(self):
        state=credentials.set_key(KEY,True);self.assertTrue(state['remembered']);self.assertNotIn(KEY.encode(),credentials.PATH.read_bytes())
        with patch.object(credentials,'_key',''):self.assertEqual(credentials.get(),KEY)
        credentials.forget();self.assertFalse(credentials.PATH.exists());self.assertEqual(credentials.get(),'')

class HttpTests(unittest.TestCase):
    save=ImportTests.save
    def setUp(self):
        ImportTests.setUp(self);self.http=server.LibraryHTTPServer(('127.0.0.1',0),server.Handler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):self.http.shutdown();self.http.server_close();ImportTests.tearDown(self)
    def request(self,path,data=None,token=True):
        headers={'Content-Type':'application/json'}
        if token:headers['X-Library-Token']=server.TOKEN
        request=Request(f'http://127.0.0.1:{self.http.server_address[1]}/api/'+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        try:
            with urlopen(request,timeout=15) as r:return r.status,json.load(r)
        except HTTPError as e:return e.code,json.load(e)
    def test_connect_is_readonly_and_key_not_returned(self):
        fixture={'items':[{'id':101,'url':'https://nhentai.net/g/101/','title':'Fixture'}],'num_pages':1,'total':1}
        with patch('nhentai.favorites',return_value=fixture):
            status,result=self.request('nhentai/connect',{'key':KEY});self.assertEqual(status,200);self.assertNotIn(KEY,json.dumps(result))
        with db.transaction() as c:self.assertEqual(c.execute('SELECT count(*) FROM works').fetchone()[0],0)
        self.assertEqual(self.request('nhentai/connect',{'key':KEY},token=False)[0],403)
    def test_interactive_and_secondary_url_open_readonly(self):
        data=nhentai.parse_gallery(GALLERY)
        with patch('importer.import_url',return_value=data):
            status,incoming=self.request('import',{'url':'https://nhentai.net/g/101/'});self.assertEqual(status,200);self.assertEqual(incoming['title'],'試験作品')
        work=self.save(dict(data,links=[{'url':'https://hitomi.la/reader/111.html'}]))
        status,result=self.request('source-attach',{'url':'https://nhentai.net/g/101/','target':work['id']});self.assertEqual(status,200)
        with patch('importer.import_url') as remote:
            status,lookup=self.request('source-check',{'url':'http://www.nhentai.net/g/101?utm=x'});self.assertEqual(status,200);self.assertEqual(lookup['match'],'exact');remote.assert_not_called()
            self.assertEqual(self.request('import',{'url':'https://nhentai.net/g/101/'})[0],409);remote.assert_not_called()

if __name__=='__main__':unittest.main()
