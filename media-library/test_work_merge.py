import unittest
from unittest.mock import patch
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
    def test_reimport_and_lookup_ignore_consolidated_trash_but_not_active_conflicts(self):
        url='https://hitomi.la/reader/123.html#2'
        a=self.work('Source',url);b=self.work('Target','https://example.com/target')
        p=self.api('works/'+a['id']+'/merge-preview','POST',{'target':b['id']})
        self.api('works/'+a['id']+'/merge-links','POST',{'target':b['id'],'signature':p['signature']})
        self.assertEqual([w['id'] for w in self.api('source-check','POST',{'url':url})['matches']],[b['id']])
        with patch('importer.import_url',return_value={'title':'Fetched','tag':[],'source_titles':[]}):
            self.api('import','POST',{'url':url,'exclude':b['id']})
        code,_,raw=self.request('/api/works','POST',{'title':'Duplicate','links':[{'url':url}]})
        self.assertEqual(code,409);self.assertNotIn(a['id'],raw.decode());self.assertIn(b['id'],raw.decode())
        self.assertEqual(self.api('trash')[0]['links'],a['links'])
        # Restoration deliberately makes this a real conflict between active works.
        self.api('trash/restore','POST',{'ids':[a['id']]})
        self.assertEqual(self.request('/api/import','POST',{'url':url,'exclude':b['id']})[0],409)
        self.api('works/'+a['id'],'DELETE')
        # Once the active destination releases the URL, the original Trash
        # confirmation is required again; no retained links were destroyed.
        target=self.api('works/'+b['id']);target['links']=[target['links'][0]]
        self.api('works/'+b['id'],'PUT',target)
        self.assertEqual(self.request('/api/import','POST',{'url':url,'exclude':b['id']})[0],409)
        self.assertEqual(self.api('trash-source/preview','POST',{'url':url})['works'][0]['id'],a['id'])
    def test_chained_consolidation_does_not_accumulate_trash_conflicts(self):
        url='https://nhentai.net/g/123/2/'
        a=self.work('A',url);b=self.work('B','https://example.com/b');c=self.work('C','https://example.com/c')
        for source,target in ((a,b),(b,c)):
            p=self.api('works/'+source['id']+'/merge-preview','POST',{'target':target['id']})
            self.api('works/'+source['id']+'/merge-links','POST',{'target':target['id'],'signature':p['signature']})
        with patch('importer.import_url',return_value={'title':'Fetched','tag':[],'source_titles':[]}):
            self.api('import','POST',{'url':url,'exclude':c['id']})
        self.assertEqual([w['id'] for w in self.api('source-check','POST',{'url':url})['matches']],[c['id']])
        self.assertEqual(len(self.api('trash')),2)
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

    def test_all_links_metadata_selection_and_personal_records(self):
        a=self.work('A','https://example.com/a');b=self.work('B','https://example.com/b')
        a['links'] += [{'url':'https://example.com/secondary','label':'Secondary'}]
        self.api('works/'+a['id'],'PUT',a)
        p=self.api('works/'+a['id']+'/merge-preview','POST',{'target':b['id']})
        self.assertEqual(len(p['links']),2)
        self.api('works/'+a['id']+'/merge-links','POST',{'target':b['id'],'signature':p['signature'],'metadata_patch':{'title':'A','tag':a['tag'],'author':[{'name':'New'}],'pages':42}})
        after=self.api('works/'+b['id'])
        self.assertEqual([l['label'] for l in after['links']],['B','A','Secondary'])
        self.assertEqual(after['title'],'A');self.assertEqual(after['tag'],a['tag']);self.assertEqual(after['pages'],42)
        for k in ('ratings','review','marks'):self.assertEqual(after[k],b[k])
        self.assertEqual(after['author'][0]['name'],'New')
        history=self.api('history')[0]
        self.api('history/'+history['id']+'/undo','POST',{})
        restored=self.api('works/'+b['id'])
        for k in ('title','tag','author','pages','ratings','review','marks'):self.assertEqual(restored[k],b[k])
        self.assertEqual([{k:v for k,v in l.items() if k!='id'} for l in restored['links']],[{k:v for k,v in l.items() if k!='id'} for l in b['links']])

    def test_metadata_failure_rolls_back_everything(self):
        a=self.work('A','https://example.com/a');b=self.work('B','https://example.com/b')
        p=self.api('works/'+a['id']+'/merge-preview','POST',{'target':b['id']})
        for patch in ({'title':'Changed','author':[{'name':'Created then rolled back'}],'tag':[{'id':'missing'}]}, {'review':'Forbidden'}):
            code,_,_=self.request('/api/works/'+a['id']+'/merge-links','POST',{'target':b['id'],'signature':p['signature'],'metadata_patch':patch})
            self.assertEqual(code,400)
            self.assertEqual(self.api('works/'+b['id']),{k:v for k,v in b.items() if k!='warnings'});self.assertEqual(self.api('trash'),[])
        self.assertEqual(self.api('entities?kind=author'),[])

    def test_draft_merge_keeps_every_link_and_guards_target(self):
        b=self.work('B','https://example.com/b')
        draft={'title':'Draft','tag':[{'name':'Incoming'}],'links':[{'url':'https://example.com/a','label':'Primary','is_primary':True},{'url':'https://example.com/extra','label':'Extra'},{'url':'https://example.com/b','label':'Already there'},{'url':'https://example.com/a','label':'Duplicate'}]}
        body={'draft':draft,'target':b['id']}
        p=self.api('draft-merge/preview','POST',body)
        self.assertEqual(len(p['links']),2);self.assertEqual(self.api('works/'+b['id']),{k:v for k,v in b.items() if k!='warnings'})
        self.api('draft-merge/apply','POST',dict(body,signature=p['signature']))
        after=self.api('works/'+b['id']);self.assertEqual(len(after['links']),3)
        self.assertEqual(after['tag'],b['tag']);self.assertEqual(self.api('trash'),[])
        self.assertEqual(self.request('/api/draft-merge/apply','POST',dict(body,signature=p['signature']))[0],400)

    def test_draft_trash_confirmation_and_third_active_conflict(self):
        b=self.work('B','https://example.com/b');a=self.work('A','https://example.com/a')
        body={'draft':{'title':'Draft','links':a['links']},'target':b['id']}
        self.assertEqual(self.request('/api/draft-merge/preview','POST',body)[0],409)
        self.api('works/'+a['id'],'DELETE')
        p=self.api('draft-merge/preview','POST',body)
        self.assertEqual(self.request('/api/draft-merge/apply','POST',dict(body,signature=p['signature']))[0],409)
        trash=self.api('trash-source/preview','POST',{'url':a['links'][0]['url']})
        consent={'url':a['links'][0]['url'],'signature':trash['signature']}
        self.assertEqual(self.request('/api/draft-merge/apply','POST',dict(body,signature=p['signature'],trash_sources=[consent],metadata_patch={'author':[{'id':'missing'}]}))[0],400)
        self.assertEqual(len(self.api('trash')),1);self.assertEqual(len(self.api('works/'+b['id'])['links']),1)
        self.api('draft-merge/apply','POST',dict(body,signature=p['signature'],trash_sources=[{'url':a['links'][0]['url'],'signature':trash['signature']}]))
        self.assertEqual(self.api('trash'),[]);self.assertEqual(len(self.api('works/'+b['id'])['links']),2)
