"""Core behavioral regression checks; isolated disposable databases only."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import db
import importer
from search import parse

class LibraryTests(unittest.TestCase):
    def setUp(self):
        (db.ROOT/'test-output').mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=db.ROOT/'test-output'); self.old=db.PATH; db.PATH=Path(self.tmp.name)/'test.sqlite3'; db.init()
    def tearDown(self): db.PATH=self.old; self.tmp.cleanup()
    def save(self,data):
        with db.transaction() as c: return db.save_work(c,data)
    def search(self,q='',**kw):
        with db.transaction() as c: return db.list_works(c,q,**kw)
    def dimension(self,name='Quality',maximum=5):
        with db.transaction() as c:
            did=db.save_dimension(c,{'name':name,'maximum':maximum,'symbol':'Star'})
            return next(d for d in db.dimensions(c) if d['id']==did)
    def test_title_only_and_persistence(self):
        w=self.save({'title':'  First  '}); self.assertEqual(w['title'],'First'); self.assertIsNone(w['pages']); self.assertFalse(w['bought'])
        with db.transaction() as c: self.assertEqual(db.get_work(c,w['id'])['title'],'First')
    def test_identical_titles_are_separate_works(self):
        self.save({'title':'A'})
        self.save({'title':' A '})
        self.save({'title':'a'}); self.save({'title':'A!'}); self.save({'title':'A  B'})
        self.assertEqual(self.search()['total'],5)
    def test_empty_title(self):
        with self.assertRaises(ValueError): self.save({'title':'  '})
    def test_invalid_save_atomic(self):
        with self.assertRaises(ValueError): self.save({'title':'Failed','author':[{'name':'Temp'}],'ratings':{'missing':1}})
        self.assertEqual(self.search()['total'],0)
        with db.transaction() as c: self.assertEqual(len(db.entity_list(c)),0)
    def test_gender_identity_and_alias_search(self):
        self.save({'title':'One','tag':[{'name':'same','gender':'female','aliases':['alias']},{'name':'same','gender':'male'},{'name':'same','gender':'neutral'}]})
        self.assertEqual(self.search('female:alias')['total'],1)
        self.assertEqual(self.search('neutral:same')['total'],1)
        with db.transaction() as c:
            self.assertEqual(len(db.entity_list(c,'tag')),3)
            with self.assertRaises(sqlite3.IntegrityError): db.save_entity(c,{'kind':'tag','name':'same','gender':'female'})
    def test_ambiguous_alias(self):
        with db.transaction() as c:
            for name in ('A','B'): db.save_entity(c,{'kind':'author','name':name,'aliases':['shared']})
        with self.assertRaisesRegex(ValueError,'Ambiguous'): self.save({'title':'Work','author':['shared']})
        self.assertEqual(self.search()['total'],0)
    def test_or_precedes_and(self):
        d=self.dimension()
        self.save({'title':'A low','author':['alp'],'ratings':{d['id']:2}})
        self.save({'title':'A high','author':['alp'],'ratings':{d['id']:5}})
        self.save({'title':'B high','author':['bob'],'ratings':{d['id']:4}})
        self.assertEqual(self.search('author:alp/author:bob rating1:>=4')['total'],2)
    def test_review_explicit_and_free_fields(self):
        self.save({'title':'A','review':'hiddenword','language':'日本語','series':['Original']})
        self.assertEqual(self.search('hiddenword')['total'],0); self.assertEqual(self.search('review:hiddenword')['total'],1)
        self.assertEqual(self.search('日本')['total'],1); self.assertEqual(self.search('series:original')['total'],1)
    def test_quotes_unicode_and_escaping(self):
        self.save({'title':'A/B "story"','author':['Alice Smith']})
        self.assertEqual(self.search('author:"Alice Smith"')['total'],1)
        self.assertEqual(self.search('title:"A/B"')['total'],1)
        self.assertEqual(self.search('title:"\\"story\\""')['total'],1)
        self.save({'title':'Straße'}); self.assertEqual(self.search('STRASSE')['total'],1)
    def test_numeric_null_and_not(self):
        d=self.dimension();self.save({'title':'Known','pages':50,'ratings':{d['id']:4}});self.save({'title':'Unknown'})
        for q in ('pages:>=50','pages:<=50','pages:=50','pages:>49','pages:<51','pages:50'): self.assertEqual(self.search(q)['total'],1)
        self.assertEqual(self.search('-rating1:>=4')['total'],1);self.assertEqual(self.search('rating1:>=4')['total'],1)
    def test_bad_queries(self):
        for q in ('rating:>=4','wat:x','author:','title:"abc','a/','a//b','(a)','pages:abc','bought:maybe','rating99:1'):
            with self.subTest(q=q),self.assertRaises(ValueError): self.search(q)
    def test_rating_numbers_and_more_than_ten(self):
        dims=[self.dimension(str(i)) for i in range(12)]
        with db.transaction() as c: c.execute('DELETE FROM dimensions WHERE id=?',(dims[1]['id'],))
        self.assertEqual(self.dimension()['number'],13)
        with db.transaction() as c: self.assertEqual(db.dimensions(c)[1]['number'],3)
    def test_rating_max_and_delete(self):
        d=self.dimension();w=self.save({'title':'Rated','ratings':{d['id']:5}})
        with db.transaction() as c:
            preview=db.dimension_preview(c,d['id'],3)
            db.save_dimension(c,{'name':'Rename','maximum':3,'symbol':'Heart','conversion_signature':preview['signature']},d['id'])
            self.assertEqual(db.get_work(c,w['id'])['ratings'][d['id']],3)
            preview=db.dimension_preview(c,d['id'],6)
            db.save_dimension(c,{'name':'Rename','maximum':6,'symbol':'Heart','conversion_signature':preview['signature']},d['id'])
            self.assertEqual(db.get_work(c,w['id'])['ratings'][d['id']],6)
            c.execute('DELETE FROM dimensions WHERE id=?',(d['id'],))
            self.assertEqual(db.get_work(c,w['id'])['ratings'],{})
        with self.assertRaises(ValueError): self.save({'title':'Invalid','ratings':{d['id']:0}})
    def test_rating_conversion_examples_and_half_ties(self):
        self.assertEqual([db.convert_score(v,3,5) for v in range(1,4)],[1,3,5])
        self.assertEqual([db.convert_score(v,5,3) for v in range(1,6)],[1,1,2,2,3])
        self.assertEqual(db.convert_score(9,10,3),2)
        self.assertEqual(db.convert_score(10,10,3),3)
        self.assertEqual(db.convert_score(2,3,4),2) # 2.5 -> 2
        self.assertEqual(db.convert_score(3,4,5),4) # 3 + 2/3 -> 4
    def test_rating_conversion_every_scale_pair(self):
        from fractions import Fraction
        for old in range(2,11):
            for new in range(2,11):
                converted=[db.convert_score(v,old,new) for v in range(1,old+1)]
                self.assertEqual(converted,sorted(converted))
                self.assertEqual(converted[0],1);self.assertEqual(converted[-1],new)
                self.assertTrue(all(1<=v<new for v in converted[:-1]))
                for v,result in enumerate(converted,1):
                    if v==old: continue
                    raw=1+Fraction((v-1)*(new-1),old-1)
                    floor=raw.numerator//raw.denominator
                    expected=min(new-1,floor+int(raw-floor>Fraction(1,2)))
                    self.assertEqual(result,expected)
    def test_rating_preview_cancel_and_conversion_isolation(self):
        d=self.dimension(maximum=5);other=self.dimension('Other',10)
        works=[self.save({'title':f'Score {v}','review':'Keep','ratings':{d['id']:v,other['id']:9}}) for v in range(1,6)]
        unrated=self.save({'title':'Unrated'})
        with db.transaction() as c:
            preview=db.dimension_preview(c,d['id'],3)
            self.assertEqual(preview['rated'],5);self.assertEqual(preview['changed'],4)
            self.assertEqual([r['new'] for r in preview['rows']],[1,1,2,2,3])
            self.assertEqual([db.get_work(c,w['id'])['ratings'][d['id']] for w in works],list(range(1,6)))
            db.save_dimension(c,{'name':'Quality','maximum':3,'symbol':'Heart','conversion_signature':preview['signature']},d['id'])
            for w,score in zip(works,[1,1,2,2,3]):
                saved=db.get_work(c,w['id'])
                self.assertEqual(saved['ratings'],{d['id']:score,other['id']:9})
                for key in ('title','review','created','updated','opened'): self.assertEqual(saved[key],w[key])
            self.assertEqual(db.get_work(c,unrated['id'])['ratings'],{})
            self.assertEqual(db.dimensions(c)[0]['number'],d['number'])
        self.assertEqual(self.search('rating1:3')['total'],1)
    def test_rating_stale_preview_and_missing_confirmation(self):
        d=self.dimension();w=self.save({'title':'Changing','ratings':{d['id']:4}})
        with db.transaction() as c: preview=db.dimension_preview(c,d['id'],3)
        with db.transaction() as c: db.save_work(c,{'title':w['title'],'ratings':{d['id']:2}},w['id'])
        for signature in (None,preview['signature']):
            with self.assertRaises(ValueError),db.transaction() as c:
                db.save_dimension(c,{'name':'Changed','maximum':3,'symbol':'Star','conversion_signature':signature},d['id'])
        with db.transaction() as c:
            self.assertEqual(db.dimensions(c)[0]['maximum'],5)
            self.assertEqual(db.get_work(c,w['id'])['ratings'][d['id']],2)
            preview=db.dimension_preview(c,d['id'],3)
            with self.assertRaises(ValueError): db.dimension_preview(c,d['id'],True)
            with self.assertRaises(ValueError): db.dimension_preview(c,'missing',3)
            db.save_dimension(c,{'name':'Changed','maximum':3,'symbol':'Star','conversion_signature':preview['signature']},d['id'])
        with self.assertRaises(ValueError),db.transaction() as c:
            db.save_dimension(c,{'name':'Changed again','maximum':3,'symbol':'Star','conversion_signature':preview['signature']},d['id'])
    def test_rating_conversion_rollback_and_rename(self):
        d=self.dimension(maximum=3);w=self.save({'title':'Rollback','ratings':{d['id']:2}})
        with self.assertRaises(RuntimeError),db.transaction() as c:
            preview=db.dimension_preview(c,d['id'],5)
            db.save_dimension(c,{'name':'Changed','maximum':5,'symbol':'Star','conversion_signature':preview['signature']},d['id'])
            raise RuntimeError('abort')
        with db.transaction() as c:
            self.assertEqual(db.dimensions(c)[0]['maximum'],3)
            self.assertEqual(db.get_work(c,w['id'])['ratings'][d['id']],2)
            db.save_dimension(c,{'name':'Rename','maximum':3,'symbol':'Heart','gallery':True},d['id'])
            self.assertEqual(db.get_work(c,w['id'])['ratings'][d['id']],2)
    def test_links_and_duplicate_url_rejection(self):
        u='https://example.org/chapter?q=one#page3'; self.save({'title':'A','links':[{'url':u,'is_primary':True}]})
        with self.assertRaises(db.DuplicateSource): self.save({'title':'B','links':[{'url':u}]})
        w=self.save({'title':'B','links':[{'url':'https://example.org/three'},{'url':'https://example.org/two','is_primary':True}]})
        self.assertEqual(w['warnings'],[]);self.assertEqual(w['links'][1]['is_primary'],1)
        with db.transaction() as c:
            saved=db.save_work(c,w,w['id'])
            self.assertEqual([l['id'] for l in saved['links']],[l['id'] for l in w['links']])
        with self.assertRaises(ValueError): self.save({'title':'C','links':[{'url':u},{'url':u}]})
        for u in ('javascript:alert(1)','file:///test','http://user:secret@example.org'):
            with self.assertRaises(ValueError): self.save({'title':'Unsafe','cover':u})
    def test_source_lookup_all_links_and_related_pages_without_fetch(self):
        w=self.save({'title':'Linked','links':[{'url':'https://example.org/primary','is_primary':True},{'url':'https://hitomi.la/reader/123.html#7'}]})
        with db.transaction() as c,patch('importer.fetch') as fetch:
            for url in ('https://hitomi.la/reader/123.html#7','http://www.hitomi.la/reader/123.html#7'):
                result=db.source_matches(c,url)
                self.assertEqual(result['match'],'exact');self.assertEqual(result['matches'][0]['id'],w['id'])
            for url in ('https://hitomi.la/reader/123.html#8','https://hitomi.la/doujinshi/example-123.html','https://hitomi.la/galleries/123.html'):
                result=db.source_matches(c,url)
                self.assertEqual(result['match'],'gallery');self.assertEqual(result['matches'][0]['source_url'],'https://hitomi.la/reader/123.html#7')
            self.assertEqual(db.source_matches(c,'https://hitomi.la/reader/12.html')['matches'],[])
            fetch.assert_not_called()
            self.assertIsNone(db.get_work(c,w['id'])['opened'])
        other=self.save({'title':'Second registration','links':[{'url':'https://hitomi.la/reader/123.html#9'}]})
        with db.transaction() as c:
            self.assertEqual(len(db.source_matches(c,'https://hitomi.la/reader/123.html#1')['matches']),2)
            self.assertEqual(len(db.source_matches(c,'https://hitomi.la/reader/123.html#7')['matches']),1)
    def test_source_lookup_rejects_unsafe_or_unsupported_urls(self):
        with db.transaction() as c:
            for url in ('','javascript:alert(1)','https://hitomi.la.evil.test/reader/123.html','https://user:pass@hitomi.la/reader/123.html','https://hitomi.la/','https://hitomi.la:9999/reader/123.html','https://ltn.hitomi.la/galleries/123.html'):
                with self.subTest(url=url),self.assertRaises(ValueError): db.source_matches(c,url)
    def test_directory_merge_delete(self):
        a=self.save({'title':'A','author':[{'name':'Alpha','aliases':['A']} ]})
        b=self.save({'title':'B','author':[{'name':'Beta','aliases':['B']} ]})
        source=a['author'][0]['id']; target=b['author'][0]['id']
        with db.transaction() as c:
            db.merge(c,source,target);self.assertEqual(db.get_work(c,a['id'])['author'][0]['name'],'Beta')
            self.assertEqual(db.entity_list(c,'author')[0]['uses'],2)
            c.execute('DELETE FROM entities WHERE id=?',(target,))
            self.assertEqual(db.get_work(c,a['id'])['author'],[])
        self.assertEqual(self.search()['total'],2)
    def test_timestamp_and_delete(self):
        w=self.save({'title':'A','author':['Author']});self.assertIsNone(w['opened'])
        with db.transaction() as c:
            self.assertIsNotNone(db.get_work(c,w['id'],True)['opened']);c.execute('DELETE FROM works WHERE id=?',(w['id'],))
            self.assertEqual(c.execute('SELECT count(*) FROM work_entities').fetchone()[0],0);self.assertEqual(len(db.entity_list(c,'author')),1)
    def test_random_all_results_and_stable_sort(self):
        for i in range(60):self.save({'title':str(i),'tag':['included']})
        a=self.search(sort='random',seed='fixed',limit=30)['items'];b=self.search(sort='random',seed='fixed',offset=30,limit=30)['items']
        self.assertEqual(len({w['id'] for w in a+b}),60)
        self.assertEqual([w['id'] for w in a],[w['id'] for w in self.search(sort='random',seed='fixed',limit=30)['items']])
        for _ in range(5):self.assertEqual(self.search('tag:included',random_one=True)['total'],60)
    def test_bookmarks_nested(self):
        html='<DL><DT><H3>Folder</H3><DL><DT><A HREF="https://hitomi.la/reader/123.html#4">One</A><DT><H3>Nested</H3><DL><A HREF="https://example.org">Two</A></DL></DL><A HREF="https://hitomi.la/reader/123.html#4">Again</A></DL>'
        items=importer.bookmarks(html);self.assertEqual(items[0]['folder'],'Folder');self.assertEqual(items[1]['folder'],'Folder / Nested');self.assertEqual(items[2]['folder'],'');self.assertTrue(items[2]['duplicate']);self.assertFalse(items[1]['supported'])
    def test_importer_fixture_and_supported_urls(self):
        out=importer.parse_gallery('var galleryinfo = '+json.dumps({'title':'Title','type':'doujinshi','files':[{},{}],'artists':[{'artist':'Artist'}],'tags':[{'tag':'tag','female':'1','male':'1'}]})+';')
        self.assertEqual(out['pages'],2);self.assertEqual(out['category'],'doujinshi');self.assertEqual(len(out['tag']),2)
        self.assertEqual(importer.gallery_id('https://hitomi.la/doujinshi/title-12345.html'), '12345')
        self.assertEqual(importer.gallery_id('https://hitomi.la/reader/123.html#7'), '123')
        self.assertIsNone(importer.gallery_id('https://hitomi.la.evil.test/reader/123.html'))
    def test_original_japanese_title_and_fallback(self):
        out=importer.parse_gallery(json.dumps({'title':'Romanized title','japanese_title':'元の日本語タイトル'}))
        self.assertEqual(out['title'],'元の日本語タイトル')
        out=importer.parse_gallery(json.dumps({'title':'Original English title','japanese_title':None}))
        self.assertEqual(out['title'],'Original English title')
    def test_reader_page_cover_selection(self):
        hashes=[f'{n:064x}' for n in range(1,5)]
        fixture=json.dumps({'title':'Page fixture','files':[{'hash':h} for h in hashes]})
        for fragment,index in (('',0),('#1',0),('#3',2),('#3-4',2),('#3-',2),('#0002',1)):
            with self.subTest(fragment=fragment),patch('importer.fetch',return_value=fixture),patch('importer.thumbnail_routes',return_value=(0,set(),0)):
                out=importer.import_url('https://hitomi.la/reader/123.html'+fragment)
                self.assertIn(hashes[index],out['cover'])
                self.assertIn('/webpsmalltn/' if index else '/webpbigtn/',out['cover'])
                self.assertEqual(out['pages'],4);self.assertEqual(out['warnings'],[])
                self.assertNotIn('_cover_hash',out)
                self.assertNotIn('_cover_directory',out)
        # Non-reader links retain the ordinary first-page cover.
        with patch('importer.fetch',return_value=fixture),patch('importer.thumbnail_routes',return_value=(0,set(),0)):
            self.assertIn(hashes[0],importer.import_url('https://hitomi.la/galleries/123.html#3')['cover'])
    def test_reader_cover_invalid_page_and_missing_thumbnail_fallback(self):
        first='1'*64
        fixture=json.dumps({'title':'Fallback fixture','files':[{'hash':first},{},{'hash':'invalid'}]})
        for fragment in ('#0','#-1','#99','#abc','#2.5','#'+'9'*200,'#2','#3'):
            with self.subTest(fragment=fragment),patch('importer.fetch',return_value=fixture),patch('importer.thumbnail_routes',return_value=(0,set(),0)):
                out=importer.import_url('https://hitomi.la/reader/123.html'+fragment)
                self.assertIn(first,out['cover']);self.assertEqual(len(out['warnings']),1)
                self.assertIn('/webpbigtn/',out['cover'])
        with patch('importer.fetch',return_value='{"title":"Empty","files":[]}'):
            out=importer.import_url('https://hitomi.la/reader/123.html#7')
            self.assertEqual(out['cover'],'');self.assertEqual(len(out['warnings']),2)
    def test_clear_work_metadata_preserves_dictionary_and_other_works(self):
        kinds=('author','circle','tag','series','character')
        metadata={kind:[{'name':kind+' one'},{'name':kind+' two'}] for kind in kinds}
        edited=self.save(dict(metadata,title='Clear this work'))
        other=self.save(dict(metadata,title='Keep this work'))
        for kind in kinds:
            edited[kind]=[]
            with db.transaction() as c:
                edited=db.save_work(c,edited,edited['id'])
                self.assertEqual(db.get_work(c,edited['id'])[kind],[])
                self.assertEqual(len(db.get_work(c,other['id'])[kind]),2)
                self.assertEqual(len(db.entity_list(c,kind)),2)
    def test_thumbnail_routing_and_legacy_repair(self):
        routes=importer.parse_thumbnail_routes('gg = { m: function(g) { var o = 1; switch(g) { case 0: case 2921: o = 0; break; } return o; }}')
        h='0'*61+'69b'
        fixed=importer.thumbnail_url(h,routes)
        self.assertEqual(fixed,f'https://atn.gold-usergeneratedcontent.net/webpbigtn/b/69/{h}.webp')
        self.assertEqual(importer.resolve_thumbnail_url(f'https://tn.gold-usergeneratedcontent.net/webpbigtn/b/69/{h}.webp',routes),fixed)
        self.assertIn('btn.gold-',importer.thumbnail_url('0'*61+'001',routes))
        with self.assertRaises(ValueError):importer.parse_thumbnail_routes('eval(arbitrary_code)')
        with self.assertRaises(ValueError):importer.resolve_thumbnail_url('https://evil.test/a',routes)
    def test_display_alias_keeps_identity_and_search(self):
        for kind in ('tag','author','circle','series','character'):
            with self.subTest(kind=kind):
                w=self.save({'title':'Display '+kind,kind:[{'name':'blue archive','aliases':['ブルーアーカイブ'],'display_alias':'ブルーアーカイブ','gender':'female'}]})
                item=w[kind][0]
                self.assertEqual(item['name'],'ブルーアーカイブ');self.assertIn('blue archive',item['aliases'])
                self.assertEqual(item['display_name'],'ブルーアーカイブ')
                self.assertEqual(self.search(kind+':"blue archive"')['total'],1)
                self.assertEqual(self.search(kind+':ブルーアーカイブ')['total'],1)
                with db.transaction() as c:
                    self.assertEqual(db.resolve(c,kind,{'name':'blue archive','gender':'female'}),item['id'])
                    db.save_entity(c,dict(item,kind=kind,display_alias='blue archive'),item['id'])
                    self.assertEqual(db.get_work(c,w['id'])[kind][0]['display_name'],'blue archive')
    def test_display_alias_validation_and_removal(self):
        with self.assertRaises(ValueError),db.transaction() as c:
            db.save_entity(c,{'kind':'tag','name':'x','display_alias':'missing'})
        with db.transaction() as c:
            eid=db.save_entity(c,{'kind':'tag','name':'x','aliases':['別名'],'display_alias':'別名'})
            original=c.execute('SELECT created FROM entities WHERE id=?',(eid,)).fetchone()[0]
            db.save_entity(c,{'kind':'tag','name':'renamed','aliases':[]},eid)
            item=db.entity_list(c)[0]
            self.assertEqual(item['display_name'],'renamed');self.assertEqual(item['created'],original)
    def test_metadata_sort_pagination_and_kana(self):
        with db.transaction() as c:
            for name in ('Zulu','alpha','キ','あ'):
                db.save_entity(c,{'kind':'author','name':name})
            ids=[e['id'] for e in db.entity_list(c,'author')]
            self.assertEqual([e['name'] for e in db.entity_list(c,'author')],['alpha','Zulu','あ','キ'])
            desc=db.entity_list(c,'author',sort='name_desc')
            self.assertEqual([e['id'] for e in desc],list(reversed(ids)))
            page=db.entity_list(c,'author',limit=2,offset=2,paged=True)
            self.assertEqual(page['total'],4);self.assertEqual([e['id'] for e in page['items']],ids[2:])
            self.assertEqual(db.metadata_key('ｶﾞ'),db.metadata_key('が'))
            self.assertEqual([e['name'] for e in db.entity_list(c,'author',sort='oldest')],['Zulu','alpha','キ','あ'])
            self.assertEqual([e['name'] for e in db.entity_list(c,'author',sort='newest')],['あ','キ','alpha','Zulu'])
        self.save({'title':'Used once','author':['Zulu']})
        self.save({'title':'Used twice','author':['Zulu','alpha']})
        with db.transaction() as c:
            self.assertEqual(db.entity_list(c,'author',sort='uses_desc')[0]['uses'],2)
            self.assertEqual(db.entity_list(c,'author',sort='uses_asc')[0]['uses'],0)
            with self.assertRaises(ValueError):db.entity_list(c,sort='invalid')
    def test_existing_schema_migrates_without_changing_names(self):
        previous=db.PATH;db.PATH=Path(self.tmp.name)/'legacy.sqlite3'
        try:
            c=sqlite3.connect(db.PATH)
            c.execute("CREATE TABLE entities(id TEXT PRIMARY KEY,owner TEXT,kind TEXT,name TEXT,gender TEXT,UNIQUE(owner,kind,name,gender))")
            c.execute("INSERT INTO entities VALUES('old','local','tag','Original','female')")
            c.commit();c.close();db.init();db.init()
            with db.transaction() as c:
                old=db.entity_list(c)[0]
                self.assertEqual(old['id'],'old');self.assertEqual(old['name'],'Original')
                self.assertEqual(old['display_name'],'Original');self.assertIsNone(old['created'])
                self.assertEqual(c.execute('SELECT count(*) FROM migrations WHERE version=2').fetchone()[0],1)
        finally:db.PATH=previous
    def test_directory_reaches_items_beyond_old_limit(self):
        with db.transaction() as c:
            for n in range(305):db.save_entity(c,{'kind':'character','name':f'Person {n:03}'})
            collected=[]
            for offset in range(0,305,100):
                page=db.entity_list(c,'character',paged=True,limit=100,offset=offset)
                self.assertEqual(page['total'],305);collected.extend(e['id'] for e in page['items'])
            self.assertEqual(len(set(collected)),305)
    def test_kanji_sort_reading_retains_display_and_identity(self):
        with db.transaction() as c:
            db.save_entity(c,{'kind':'author','name':'さくら'})
            db.save_entity(c,{'kind':'author','name':'青木','sort_reading':'あおき'})
            db.save_entity(c,{'kind':'author','name':'東京','sort_reading':'とうきょう'})
            self.assertEqual([e['name'] for e in db.entity_list(c,'author')],['青木','さくら','東京'])
    def test_merge_keeps_target_display_choice(self):
        with db.transaction() as c:
            source=db.save_entity(c,{'kind':'author','name':'Source','aliases':['S'],'display_alias':'S'})
            target=db.save_entity(c,{'kind':'author','name':'Target','aliases':['T'],'display_alias':'T'})
            db.merge(c,source,target)
            entity=db.entity_list(c)[0]
            self.assertEqual(entity['display_name'],'T');self.assertIn('S',entity['aliases'])
    def test_backup_restore_roundtrip(self):
        d=self.dimension();w=self.save({'title':'Backup','tag':['tag'],'ratings':{d['id']:4},'links':[{'url':'https://example.org'}]})
        with db.transaction() as c:
            c.execute('INSERT INTO jobs(id,owner,status,created) VALUES(?,?,?,?)',('job','local','running',db.now()));c.execute('INSERT INTO job_items(id,job_id,url,status) VALUES(?,?,?,?)',('item','job','https://hitomi.la/reader/123.html','pending'))
        backup=db.backup(Path(self.tmp.name)/'backups'); restored=Path(self.tmp.name)/'restored.sqlite3'
        s=sqlite3.connect(backup);r=sqlite3.connect(restored);s.backup(r);s.close();r.close();db.PATH=restored
        with db.transaction() as c:
            self.assertEqual(db.get_work(c,w['id'])['ratings'][d['id']],4);self.assertEqual(c.execute('SELECT count(*) FROM job_items').fetchone()[0],1)

if __name__=='__main__':unittest.main(verbosity=2)
