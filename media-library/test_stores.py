"""Store boundaries, scoped fields, URL claims and existing import workflows."""
import json,unittest,tempfile
from pathlib import Path
from unittest.mock import patch,Mock
import db,stores,importer,import_jobs,import_matching,cover_sources,cover_relay
import test_feature_http as fixture

DL='https://dlsharing.com/maniax-touch/work/=/product_id/RJ01097714.html'
BOOK='https://book.dmm.co.jp/product/123/book123/'
FANZA='https://www.dmm.co.jp/dc/doujin/-/detail/=/cid=d_123/'
DL_HTML='''<a>Sidebar</a><h1 id="work_name">作品 &amp; 第2巻</h1>
<div class="maker_name"><a>Circle</a></div><table id="work_outline">
<tr><th>作者</th><td><a>Alice / Smith</a><a>Bob</a></td></tr>
<tr><th>作品形式</th><td><a>マンガ</a></td></tr><tr><th>シリーズ名</th><td><a>Series</a></td></tr>
<tr><th>ジャンル</th><td><a>Digital</a><a>Digital</a><a>学校/学園</a></td></tr></table>
<table id="work_maker"><tr><th>出版社名</th><td><a>Do not import</a></td></tr></table>
<meta property="og:image" content="https://img.dlsite.jp/modpub/images2/work/doujin/RJ01098000/RJ01097714_img_main.jpg">
<h1>Recommended title</h1><dl><dt>ページ数</dt><dd>999</dd></dl>'''
FANZA_HTML='''<h1>作品 &amp; 第2巻</h1><div class="circleName"><a href="/dc/doujin/-/list/=/article=maker/id=1/">Circle</a></div>
<div class="productInformation__item"><dl><dt>作者</dt><dd><a>Alice / Smith</a><a>Bob</a></dd></dl></div>
<div class="productInformation__item"><dl><dt>作品形式</dt><dd><a>コミック</a></dd></dl></div>
<div class="productInformation__item"><dl><dt>ページ数</dt><dd>35ページ</dd></dl></div>
<div class="productInformation__item"><dl><dt>ジャンル</dt><dd><a>Digital</a></dd></dl></div>
<meta property="og:image" content="https://doujin-assets.dmm.co.jp/digital/comic/d_123/d_123pr.jpg">
<dl><dt>作者</dt><dd>Related Author</dd></dl>'''
BOOK_HTML='''<h1>Commercial title</h1><dl><dt>カテゴリー</dt><dd>漫画</dd></dl><dl><dt>シリーズ名</dt><dd><a>Series</a></dd></dl><dl><dt>ページ数</dt><dd>228 ページ</dd></dl>
<dl><dt>出版社</dt><dd>Publisher</dd></dl><dl><dt>掲載誌・レーベル</dt><dd>Magazine</dd></dl>
<script type="application/ld+json">{"@type":"Product","name":"Commercial title","subjectOf":{"author":{"name":["Author"]},"genre":["Tag"]}}</script>
<script type="application/ld+json">{"@type":"Product","name":"Recommended","subjectOf":{"author":{"name":["Wrong"]}}}</script>
<meta property="og:image" content="https://ebook-assets.dmm.co.jp/digital/e-book/book123/book123pl.jpg">'''

class AdapterTests(unittest.TestCase):
    def test_shared_touch_identity_and_boundaries(self):
        self.assertEqual(importer.source_identity(DL),('dlsite','RJ01097714'))
        self.assertEqual(db.normalize_url(DL+'?utm=x#sample'),db.normalize_url(stores.canonical(DL)))
        self.assertEqual(db.normalize_url(BOOK),db.normalize_url(BOOK.replace('.co.jp','.com').replace('/123/','/999/')))
        self.assertNotEqual(db.normalize_url(DL),db.normalize_url(DL.replace('01097714','01097715')))
        for value in (DL.replace('dlsharing.com','dlsharing.com.evil'),DL.replace('https://','https://x@'),DL.replace('dlsharing.com','dlsharing.com:444'),BOOK.replace('book123','latest'),FANZA.replace('d_123','d_0'),'file:///product/1/book/'):
            self.assertIsNone(stores.location(value),value)
        self.assertTrue(importer.attribute_less_source(DL));self.assertTrue(importer.attribute_less_source(BOOK))
    def test_dlsite_scoped_metadata_commercial_author_and_no_publisher(self):
        d=stores.parse_page(DL_HTML,DL)
        self.assertEqual(d['title'],'作品 & 第2巻');self.assertEqual(d['author'],[{'name':'Alice / Smith'},{'name':'Bob'}]);self.assertEqual(d['circle'],[{'name':'Circle'}])
        self.assertIsNone(d['pages']);self.assertEqual(d['series'],[{'name':'Series'}]);self.assertEqual(len(d['tag']),2)
        html=DL_HTML.replace('RJ01097714','BJ01309208').replace('doujin/RJ01098000','books/BJ01310000').replace('<th>出版社名</th>','<th>著者</th>')
        d=stores.parse_page(html,'https://www.dlsite.com/books/work/=/product_id/BJ01309208.html')
        self.assertEqual(d['circle'],[]);self.assertEqual(d['category'],'manga');self.assertIn({'name':'Do not import'},d['author'])
        with self.assertRaises(ValueError):stores.parse_page(DL_HTML.replace('マンガ','ASMR'),DL)
        with self.assertRaises(ValueError):stores.parse_page('<h1>Access challenge</h1>',DL)
    def test_fanza_scope_and_book_jsonld(self):
        d=stores.parse_page(FANZA_HTML,FANZA);self.assertEqual(d['pages'],35);self.assertEqual(len(d['author']),2);self.assertEqual(d['circle'],[{'name':'Circle'}])
        d=stores.parse_page(BOOK_HTML,BOOK);self.assertEqual(d['pages'],228);self.assertEqual(d['author'],[{'name':'Author'}]);self.assertEqual(d['circle'],[])
        self.assertEqual(d['tag'],[{'name':'Tag','gender':'neutral'}]);self.assertEqual(d['series'],[{'name':'Series'}])
        with self.assertRaises(ValueError):stores.parse_page(BOOK_HTML.replace('<dd>漫画</dd>','<dd>小説</dd>'),BOOK)
    def test_image_and_network_boundaries(self):
        value='https://doujin-assets.dmm.co.jp/digital/comic/d_123/d_123pr.jpg'
        for bad in (value+'?x=1',value+'#a',value.replace('https:','http:'),value.replace('co.jp','co.jp.evil'),value.replace('d_123pr','d_456pr'),value.replace('pr.jpg','jp-001.jpg')):self.assertFalse(stores.valid_image(bad))
        with patch('stores.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]),patch('stores.socket.socket') as sock:
            with self.assertRaises(ValueError):stores.request(stores.canonical(DL),stores.canonical(DL))
            sock.assert_not_called()
        with patch('stores.request',return_value=(200,[],'image/jpeg',b'<html>')):
            with self.assertRaises(ValueError):stores.fetch_image(value)
        with patch.object(cover_relay,'CACHE',cover_relay.MemoryCache()),patch('stores.fetch_image',return_value=('image/jpeg',b'fixture')) as fetch:
            self.assertEqual(cover_sources.load(value),('image/jpeg',b'fixture'));cover_sources.load(value);fetch.assert_called_once()
    def test_age_flow_only_fixed_return_target_and_no_login(self):
        target=stores.canonical(FANZA);gate='https://www.dmm.co.jp/age_check/=/?rurl='+__import__('urllib.parse',fromlist=['quote']).quote(target,safe='')
        yes=gate.replace('/age_check/=/','/age_check/=/declared=yes/')
        html='<script id="__NEXT_DATA__">'+json.dumps({'props':{'pageProps':{'yesButtonLink':yes}}})+'</script>'
        with patch('stores.request',side_effect=[(302,[('Location',gate)],'',b''),(200,[],'text/html',html.encode()),(302,[('Location',target),('Set-Cookie','age_check_done=1; Path=/')],'',b''),(200,[],'text/html',FANZA_HTML.encode())]),patch.dict(stores._next,clear=True),patch.object(stores,'_age_cookie',''):
            self.assertEqual(stores.import_url(FANZA)['pages'],35);self.assertEqual(stores._age_cookie,'1')
        with patch('stores.request',return_value=(302,[('Location','https://evil.test/')],'',b'')),patch.dict(stores._next,clear=True):
            with self.assertRaisesRegex(ValueError,'redirect'):stores.fetch(FANZA)
        self.assertFalse(stores.age_location(gate.replace('rurl=','rurl=https://evil.test/&x='),target))
    def test_cancel_and_bounded_parser(self):
        token=stores.CANCEL.set(lambda:True)
        try:
            with patch('stores.request') as fetch:
                with self.assertRaises(ValueError):stores.fetch(DL)
                fetch.assert_not_called()
        finally:stores.CANCEL.reset(token)
        with self.assertRaises(ValueError):stores.parse_page('<div>'*210,DL)

class WorkflowTests(unittest.TestCase):
    setUp=fixture.FeatureHTTPTests.setUp;tearDown=fixture.FeatureHTTPTests.tearDown;request=fixture.FeatureHTTPTests.request;api=fixture.FeatureHTTPTests.api
    def test_import_alias_duplicate_secondary_and_reimport(self):
        with patch('stores.fetch',return_value=DL_HTML):
            d=self.api('import','POST',{'url':DL});self.assertEqual(d['category'],'doujinshi')
            w=self.api('works','POST',dict(d,links=[{'url':DL,'is_primary':True}],review='Keep'))
            self.assertEqual(self.api('source-check','POST',{'url':stores.canonical(DL)})['matches'][0]['id'],w['id'])
            self.assertEqual(self.request('/api/import','POST',{'url':stores.canonical(DL)})[0],409)
            self.assertEqual(self.api('import','POST',{'url':DL,'exclude':w['id']})['title'],d['title'])
        with patch('stores.fetch',return_value=FANZA_HTML):
            d=self.api('import','POST',{'url':FANZA});self.assertEqual(d['cross_candidates'][0]['id'],w['id'])
        merged=self.api('source-attach','POST',{'url':FANZA,'target':w['id']});self.assertEqual(merged['review'],'Keep');self.assertEqual(merged['links'][-1]['label'],'FANZA同人');self.assertFalse(merged['links'][-1]['is_primary'])
    def test_job_and_migration_preserve_urls_and_work(self):
        with db.transaction() as c:
            w=db.save_work(c,{'title':'Manual','links':[{'url':DL,'is_primary':True}]});before=db.get_work(c,w['id'])
            c.execute('UPDATE links SET url_key=? WHERE work_id=?',('old-key',w['id']));c.execute('DELETE FROM source_claims');c.execute('INSERT INTO source_claims VALUES(?,?,?)',(db.OWNER,'old-key',w['id']));c.execute('DELETE FROM migrations WHERE version=10')
        db.init();db.init()
        with db.transaction() as c:
            self.assertEqual(db.get_work(c,w['id']),before);self.assertEqual(db.exact_sources(c,stores.canonical(DL))[0]['id'],w['id'])
            female=db.save_entity(c,{'name':'Digital','kind':'tag','gender':'female'});db.save_work(c,{'title':'Female','tag':[{'id':female}]})
            jid=import_jobs.create(c,{'items':[{'url':FANZA,'label':'Bookmark'}],'title_mode':'bookmark','tag_mode':'frequency'})['id'];item=dict(c.execute('SELECT * FROM job_items WHERE job_id=?',(jid,)).fetchone())
        with patch('stores.fetch',return_value=FANZA_HTML):import_jobs.process_item(item)
        with db.transaction() as c:
            row=c.execute('SELECT * FROM job_items WHERE id=?',(item['id'],)).fetchone();self.assertEqual(row['status'],'added');w=db.get_work(c,row['work_id']);self.assertEqual(w['title'],'Bookmark');self.assertEqual(w['tag'][0]['gender'],'female');self.assertEqual(w['links'][0]['label'],'FANZA同人')

if __name__=='__main__':unittest.main()
