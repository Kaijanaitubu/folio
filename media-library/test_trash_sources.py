import unittest,json
from unittest.mock import patch
import test_feature_http as fixture
import db

class TrashSourceTests(unittest.TestCase):
    setUp=fixture.FeatureHTTPTests.setUp;tearDown=fixture.FeatureHTTPTests.tearDown;request=fixture.FeatureHTTPTests.request;api=fixture.FeatureHTTPTests.api
    def trashed(self):
        w=self.api('works','POST',{'title':'Old','tag':['old tag'],'review':'Old note','links':[{'url':'https://example.com/work','label':'Old label','is_primary':True}]})
        self.api('works/'+w['id'],'DELETE')
        return w
    def consent(self):
        p=self.api('trash-source/preview','POST',{'url':'https://example.com/work'})
        return {'url':p['url'],'signature':p['signature']}
    def test_replace_is_explicit_and_atomic(self):
        old=self.trashed();c=self.consent()
        data={'title':'New','links':old['links'],'trash_sources':[c]}
        self.assertEqual(self.request('/api/works','POST',dict(data,title=''))[0],400)
        self.assertEqual(self.api('trash')[0]['id'],old['id'])
        result=self.api('works','POST',data);self.assertNotEqual(result['id'],old['id']);self.assertEqual(self.api('trash'),[])
    def test_stale_foreign_and_unrelated_consents_rejected(self):
        old=self.trashed();c=self.consent()
        with db.transaction() as conn:conn.execute('UPDATE works SET title=? WHERE id=?',('Changed',old['id']))
        self.assertEqual(self.request('/api/works','POST',{'title':'New','links':old['links'],'trash_sources':[c]})[0],400)
        self.assertEqual(self.request('/api/works','POST',{'title':'New','links':[{'url':'https://example.com/other'}],'trash_sources':[self.consent()]})[0],400)
        with db.transaction() as conn:
            conn.execute("INSERT INTO owners(id) VALUES('other')");conn.execute("UPDATE works SET owner='other' WHERE id=?",(old['id'],))
        self.assertEqual(self.api('trash-source/preview','POST',{'url':'https://example.com/work'})['works'],[])
    def test_secondary_merge_preserves_primary_and_personal_fields(self):
        old=self.trashed();c=self.consent()
        target=self.api('works','POST',{'title':'Target','review':'Keep','marks':[4],'tag':['existing'],'links':[{'url':'https://example.com/main','is_primary':True}]})
        target['tag']+=old['tag'];target['links']+=[dict(old['links'][0],is_primary=False)];target['trash_sources']=[c]
        merged=self.api('works/'+target['id'],'PUT',target)
        self.assertEqual(merged['review'],'Keep');self.assertEqual(merged['marks'],[4]);self.assertEqual(len(merged['tag']),2)
        self.assertTrue(merged['links'][0]['is_primary']);self.assertFalse(merged['links'][1]['is_primary']);self.assertEqual(self.api('trash'),[])
    def test_active_url_and_unconfirmed_import_stay_blocked(self):
        active=self.api('works','POST',{'title':'Active','links':[{'url':'https://example.com/active','is_primary':True}]})
        self.assertEqual(self.request('/api/trash-source/preview','POST',{'url':active['links'][0]['url']})[0],409)
        self.assertEqual(self.request('/api/works','POST',{'title':'Other','links':active['links']})[0],409)
        old=self.trashed();c=self.consent();url='https://hitomi.la/reader/123.html'
        with db.transaction() as conn:conn.execute('UPDATE links SET url=?,url_key=? WHERE work_id=?',(url,db.normalize_url(url),old['id']))
        c=self.api('trash-source/preview','POST',{'url':url})
        self.assertEqual(self.request('/api/import','POST',{'url':url})[0],409)
        with patch('importer.import_url',return_value={'title':'Fetched','tag':[],'source_titles':[]}):
            self.assertEqual(self.request('/api/import','POST',{'url':url,'trash_sources':[{'url':url,'signature':c['signature']}]})[0],200)
        self.assertEqual(len(self.api('trash')),1)
    def test_link_search_all_links_quotes_or_not_trash(self):
        w=self.api('works','POST',{'title':'Links','links':[{'url':'https://hitomi.la/reader/1.html','is_primary':True},{'url':'https://nhentai.net/g/1/','label':'My Archive'}]})
        for q in ('source:nhentai','label:"my archive"','url:"https://nhentai.net/g/"','source:momon-ga/source:nhentai','-source:momon-ga'):
            self.assertEqual(self.api('works?q='+__import__('urllib.parse',fromlist=['quote']).quote(q))['total'],1,q)
        self.assertEqual(self.api('works?q=label:nhentai')['total'],0)
        self.api('works/'+w['id'],'DELETE');self.assertEqual(self.api('works?q=source:nhentai')['total'],0)
