import json
import unittest
from unittest.mock import patch
import test_feature_http as fixture
import db


class ImportListTests(unittest.TestCase):
    setUp=fixture.FeatureHTTPTests.setUp;tearDown=fixture.FeatureHTTPTests.tearDown
    request=fixture.FeatureHTTPTests.request;api=fixture.FeatureHTTPTests.api
    def preview(self,kind,text):return self.api('import-list','POST',{'kind':kind,'text':text})
    def test_kemono_posts_only_privacy_duplicates_and_no_automatic_registration(self):
        rows={'posts':[{'service':'fanbox','user':'12','id':'34','title':'Example','content':'private-body','attachments':[{'path':'private-file'}]},
                       {'service':'fanbox','user':12,'id':34},{'service':'patreon','user':'56','id':'78'},
                       {'service':'fantia','user':'1','id':'2'}],
              'artists':[{'service':'patreon','id':'999','name':'Private artist'}]}
        with patch('importer.import_url',side_effect=AssertionError('Preview must not fetch sources')):
            result=self.preview('kemono','\ufeff'+json.dumps(rows))
        self.assertEqual(result['summary'],{'input':4,'unsupported':1,'artists_ignored':1,'items':3,'registered':0,'duplicates':1,'selectable':2})
        self.assertEqual(result['items'][0]['url'],'https://pawchive.pw/fanbox/user/12/post/34')
        self.assertNotIn('private',json.dumps(result).lower())
        self.assertEqual(self.api('works')['total'],0);self.assertEqual(self.api('jobs'),[])
        job=self.api('jobs','POST',{'items':[i for i in result['items'] if not i['duplicate']],'include_original_links':True})
        self.assertEqual(len(self.api('jobs/'+job['id'])['items']),2)
    def test_registered_urls_and_different_purpose_filters(self):
        url='https://pawchive.pw/patreon/user/12/post/34'
        self.api('works','POST',{'title':'Existing','links':[{'url':url}]})
        html=f'<a href="{url}">Post</a><a href="https://www.dmm.co.jp/dc/doujin/-/detail/=/cid=d_123/">Comic</a><a href="https://example.com">Other</a>'
        favorites=self.preview('pawchive',html)
        self.assertEqual(len(favorites['items']),1);self.assertTrue(favorites['items'][0]['registered'])
        self.assertEqual(favorites['summary']['unsupported'],2)
        purchases=self.preview('fanza',html)
        self.assertEqual(len(purchases['items']),1);self.assertIn('d_123',purchases['items'][0]['url'])
        bookmarks=self.preview('bookmarks',html)
        self.assertEqual(len(bookmarks['items']),3);self.assertEqual(bookmarks['summary']['unsupported'],1)
    def test_bad_shape_ids_oversize_token_and_artist_export_are_rejected(self):
        cases=['not JSON','{}','{"artists":[]}',json.dumps([{'service':'fanbox','id':'1'}]),
               json.dumps([{'service':'fanbox','user':True,'id':'1'}]),
               json.dumps([{'service':'patreon','user':'12/evil','id':'1'}]),
               json.dumps([{'service':'fanbox','user':'12','id':'1','title':{'private':'data'}}])]
        for text in cases:self.assertEqual(self.request('/api/import-list','POST',{'kind':'kemono','text':text})[0],400)
        self.assertEqual(self.request('/api/import-list','POST',{'kind':'unsupported','text':'[]'})[0],400)
        self.assertEqual(self.request('/api/import-list','POST',{'kind':'kemono','text':'[]'},token=False)[0],403)
        import import_lists
        with db.transaction() as c,self.assertRaises(ValueError):import_lists.preview(c,{'kind':'kemono','text':' '*(12*1024*1024+1)})
        self.assertEqual(self.api('jobs'),[])
    def test_large_and_empty_supported_list(self):
        rows=[{'service':'fanbox','user':'12','id':str(i+1)} for i in range(2505)]
        result=self.preview('kemono',json.dumps(rows));self.assertEqual(result['summary']['selectable'],2505)
        empty=self.preview('kemono',json.dumps({'posts':[],'artists':[{}]}))
        self.assertEqual(empty['summary']['items'],0);self.assertEqual(empty['summary']['artists_ignored'],1)


if __name__=='__main__':unittest.main()
