import copy,json
from unittest.mock import patch
import unittest
import db,features,import_jobs,import_matching,pawchive
import test_pawchive as fixtures
POST,PROFILE,URL,SHORT=fixtures.POST,fixtures.PROFILE,fixtures.URL,fixtures.SHORT

ORIGINAL='https://synthetic-author.fanbox.cc/posts/456'
ORIGINAL_PROFILE=dict(PROFILE,public_id='synthetic-author')

class OriginalAdapterTests(unittest.TestCase):
    def test_generated_links_and_url_aliases(self):
        self.assertEqual(pawchive.parse_post(POST,ORIGINAL_PROFILE,URL)['original_links'][0]['url'],ORIGINAL)
        self.assertEqual(pawchive.parse_post(POST,dict(PROFILE,public_id='bad.example'),URL)['original_links'],[])
        self.assertEqual(pawchive.original_candidates('patreon','123','456',{}),[{'url':'https://www.patreon.com/posts/456','label':'Patreon','verified':False}])
        self.assertEqual(db.normalize_url(ORIGINAL+'?track=1'),db.normalize_url('https://www.fanbox.cc/@synthetic-author/posts/456'))
        self.assertEqual(db.normalize_url('https://www.patreon.com/name/posts/title-456?track=1'),db.normalize_url('https://www.patreon.com/posts/456'))
        self.assertNotEqual(db.normalize_url(ORIGINAL),db.normalize_url('https://www.patreon.com/posts/456'))
        for value in ('https://www.patreon.com.evil/posts/456','https://user@www.patreon.com/posts/456','https://www.patreon.com:444/posts/456','https://evil.test/posts/456','https://www.fanbox.cc/@synthetic-author','https://www.patreon.com/posts/0'):
            self.assertIsNone(pawchive.original_comparison(value))
        self.assertEqual(pawchive.original_candidates('fanbox','123','456',dict(ORIGINAL_PROFILE,public_id='name_underscore'))[0]['url'],'https://www.fanbox.cc/@name_underscore/posts/456')

class OriginalIntegrationTests(unittest.TestCase):
    setUp=fixtures.IntegrationTests.setUp
    tearDown=fixtures.IntegrationTests.tearDown
    request=fixtures.IntegrationTests.request
    def fixture(self):return patch('pawchive.fetch_json',side_effect=lambda url:copy.deepcopy(ORIGINAL_PROFILE if url.endswith('/profile') else POST))
    def run_job(self,include=True):
        with db.transaction() as c:
            jid=import_jobs.create(c,{'items':[{'url':URL}],'include_original_links':include})['id']
            item=dict(c.execute('SELECT * FROM job_items WHERE job_id=?',(jid,)).fetchone())
        with self.fixture():import_jobs.process_item(item)
        return jid,item
    def test_job_adds_original_link_as_secondary_and_can_opt_out(self):
        jid,item=self.run_job()
        with db.transaction() as c:
            row=c.execute('SELECT * FROM job_items WHERE id=?',(item['id'],)).fetchone()
            self.assertEqual(row['status'],'added');work=db.get_work(c,row['work_id'])
            self.assertEqual([l['label'] for l in work['links']],['Pawchive','FANBOX'])
            self.assertEqual([bool(l['is_primary']) for l in work['links']],[True,False])
            features.trash(c,work['id']);db.purge_work(c,work['id'])
        _,item=self.run_job(False)
        with db.transaction() as c:
            row=c.execute('SELECT * FROM job_items WHERE id=?',(item['id'],)).fetchone()
            self.assertEqual(len(db.get_work(c,row['work_id'])['links']),1)
    def test_registered_original_is_candidate_even_with_another_title(self):
        with db.transaction() as c:old=db.save_work(c,{'title':'A custom title','links':[{'url':ORIGINAL,'is_primary':True}],'review':'Keep'})
        with self.fixture():status,data=self.request('import',{'url':URL})
        self.assertEqual(status,200);self.assertEqual(data['cross_candidates'][0]['id'],old['id'])
        self.assertTrue(data['cross_candidates'][0]['evidence']['original_source'])
        self.assertEqual(data['original_links'][0]['matches'][0]['id'],old['id'])
        status,result=self.request('source-attach',{'url':URL,'target':old['id'],'original_links':data['original_links']})
        self.assertEqual(status,200);self.assertEqual(result['review'],'Keep');self.assertEqual(len(result['links']),2)
        self.assertEqual(sum(l['is_primary'] for l in result['links']),1)
    def test_batch_keeps_conflicting_original_and_reports_skip(self):
        with db.transaction() as c:
            old=db.save_work(c,{'title':'Original already registered','links':[{'url':ORIGINAL,'is_primary':True}]})
            features.trash(c,old['id'])
        _,item=self.run_job()
        with db.transaction() as c:
            row=c.execute('SELECT * FROM job_items WHERE id=?',(item['id'],)).fetchone()
            self.assertEqual(row['status'],'added');self.assertTrue(json.loads(row['warnings_json'])['original_links'])
            self.assertEqual(len(db.get_work(c,row['work_id'])['links']),1)
            self.assertEqual(db.exact_sources(c,ORIGINAL)[0]['id'],old['id'])
            self.assertTrue(db.get_work(c,old['id'],include_deleted=True)['deleted_at'])
    def test_reimport_original_already_in_current_work_and_invalid_attach(self):
        with db.transaction() as c:work=db.save_work(c,{'title':POST['title'],'links':[{'url':URL,'is_primary':True},{'url':ORIGINAL,'is_primary':False}]})
        with self.fixture():status,data=self.request('import',{'url':URL,'exclude':work['id']})
        self.assertEqual(status,200);self.assertTrue(data['original_links'][0]['already_present'])
        with db.transaction() as c:other=db.save_work(c,{'title':'Untouched','review':'Keep'})
        self.assertEqual(self.request('source-attach',{'url':SHORT.replace('/456','/789'),'target':other['id'],'original_links':[{'url':'https://evil.test/'}]})[0],400)
        with db.transaction() as c:self.assertEqual(db.get_work(c,other['id'])['links'],[])
    def test_manual_original_keys_migrate_without_changing_works(self):
        legacy='https://www.patreon.com/creator/posts/title-456?track=1'
        with db.transaction() as c:
            work=db.save_work(c,{'title':'Manual','links':[{'url':legacy,'is_primary':True}]});before=db.get_work(c,work['id'])
            c.execute('UPDATE links SET url_key=? WHERE work_id=?',(legacy,work['id']))
            c.execute('DELETE FROM source_claims');c.execute('INSERT INTO source_claims VALUES(?,?,?)',(db.OWNER,legacy,work['id']))
            c.execute('DELETE FROM migrations WHERE version=13')
        db.init();db.init()
        with db.transaction() as c:
            self.assertEqual(db.get_work(c,work['id']),before)
            self.assertEqual(db.exact_sources(c,'https://www.patreon.com/posts/456')[0]['id'],work['id'])

if __name__=='__main__':unittest.main()
