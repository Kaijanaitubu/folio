import unittest
import db
import test_feature_http as fixture

class WorkMergeTests(unittest.TestCase):
    setUp=fixture.FeatureHTTPTests.setUp
    tearDown=fixture.FeatureHTTPTests.tearDown
    api=fixture.FeatureHTTPTests.api
    request=fixture.FeatureHTTPTests.request
    def work(self,title,url):
        return self.api('works','POST',{'title':title,'tag':[title],'review':title,'marks':[2],'links':[{'url':url,'label':title,'is_primary':True}] if url else []})
    def test_links_only_and_recovery(self):
        a=self.work('Source','https://example.com/a');b=self.work('Target','https://example.com/b')
        p=self.api('works/'+a['id']+'/merge-preview','POST',{'target':b['id']})
        result=self.api('works/'+a['id']+'/merge-links','POST',{'target':b['id'],'signature':p['signature']})
        self.assertEqual(result['added'],1)
        after=self.api('works/'+b['id'])
        for k in ('title','tag','review','marks','ratings','cover'):self.assertEqual(after[k],b[k])
        self.assertTrue(after['links'][0]['is_primary']);self.assertFalse(after['links'][1]['is_primary'])
        self.assertEqual(self.api('trash')[0]['links'],a['links'])
        self.assertEqual(self.api('works?ids=1')['ids'],[b['id']])
        history=self.api('history')[0]
        self.api('history/'+history['id']+'/undo','POST',{})
        self.assertEqual(len(self.api('works/'+b['id'])['links']),1)
        self.api('trash/restore','POST',{'ids':[a['id']]})
        self.assertEqual(self.api('works/'+a['id'])['links'],a['links'])
    def test_no_primary_is_forced_on_linkless_target(self):
        a=self.work('A','https://example.com/a');b=self.work('B','')
        p=self.api('works/'+a['id']+'/merge-preview','POST',{'target':b['id']})
        self.api('works/'+a['id']+'/merge-links','POST',{'target':b['id'],'signature':p['signature']})
        self.assertFalse(self.api('works/'+b['id'])['links'][0]['is_primary'])
    def test_stale_and_missing_confirmation_are_atomic(self):
        a=self.work('A','https://example.com/a');b=self.work('B','https://example.com/b')
        p=self.api('works/'+a['id']+'/merge-preview','POST',{'target':b['id']})
        b['review']='Changed';self.api('works/'+b['id'],'PUT',b)
        for signature in (p['signature'],None):
            self.assertEqual(self.request('/api/works/'+a['id']+'/merge-links','POST',{'target':b['id'],'signature':signature})[0],400)
        self.assertEqual(self.api('trash'),[])
        self.assertEqual(len(self.api('works/'+b['id'])['links']),1)
    def test_invalid_selection(self):
        a=self.work('A','https://example.com/a');b=self.work('B','')
        for source,target in ((a['id'],a['id']),(b['id'],a['id']),(a['id'],'missing')):
            self.assertEqual(self.request('/api/works/'+source+'/merge-preview','POST',{'target':target})[0],400)
        self.api('works/'+a['id'],'DELETE')
        self.assertEqual(self.request('/api/works/'+b['id']+'/merge-preview','POST',{'target':a['id']})[0],400)
    def test_other_owners_are_not_accessible(self):
        a=self.work('A','https://example.com/a');b=self.work('B','https://example.com/b')
        with db.transaction() as c:
            c.execute("INSERT INTO owners(id) VALUES('other')")
            c.execute("UPDATE works SET owner='other' WHERE id=?",(b['id'],))
        self.assertEqual(self.request('/api/works/'+a['id']+'/merge-preview','POST',{'target':b['id']})[0],400)
