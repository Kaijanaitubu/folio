import json,os,threading,unittest
from unittest.mock import patch
from urllib.request import urlopen,Request
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
import db,sharing,share_server
import test_feature_http as fixture

class SharingTests(unittest.TestCase):
    request=fixture.FeatureHTTPTests.request
    api=fixture.FeatureHTTPTests.api
    def setUp(self):
        fixture.FeatureHTTPTests.setUp(self)
        self.env=patch.dict(os.environ,{'FOLIO_SHARE_BASE':'https://share.example.com'});self.env.start()
        self.public=ThreadingHTTPServer(('127.0.0.1',0),share_server.Handler)
        self.thread2=threading.Thread(target=self.public.serve_forever,daemon=True);self.thread2.start()
        self.public_base='http://127.0.0.1:'+str(self.public.server_address[1])
        self.work=self.api('works','POST',{'title':'<script>test</script>','author':['Example'],'tag':['tag'],'review':'private personal note','marks':[2],'links':[{'url':'https://example.com/work','label':'Source'}]})
    def tearDown(self):
        self.public.shutdown();self.public.server_close();self.env.stop();fixture.FeatureHTTPTests.tearDown(self)
    def share(self,options=None):return self.api('shares/'+self.work['id'],'POST',{'expected_updated':self.work['updated'],'options':options or {}})
    def public_get(self,path,method='GET'):
        try:
            with urlopen(Request(self.public_base+path,method=method)) as r:return r.status,dict(r.headers),r.read()
        except HTTPError as e:return e.code,dict(e.headers),e.read()
    def test_snapshot_defaults_and_immutability(self):
        p=self.share();self.assertEqual(len(p['token']),32)
        code,headers,body=self.public_get('/s/'+p['token']);text=body.decode()
        self.assertEqual(code,200);self.assertIn('private personal note',text);self.assertIn('Mark 2',text)
        self.assertIn('&lt;script&gt;',text);self.assertNotIn('<script>',text)
        self.assertIn('noindex',headers['X-Robots-Tag']);self.assertEqual(headers['Referrer-Policy'],'no-referrer')
        self.work['review']='changed';self.work['title']='Changed';self.api('works/'+self.work['id'],'PUT',self.work)
        self.assertEqual(self.public_get('/s/'+p['token'])[2],body)
    def test_omit_private_fields_and_no_internal_data(self):
        p=self.share({'ratings':False,'review':False,'marks':False})
        page,_=share_server.get_page(p['token'])
        self.assertEqual(page['review'],'');self.assertEqual(page['ratings'],[]);self.assertEqual(page['marks'],[])
        self.assertFalse({'id','owner','bookmark_names','source_titles','updated'}&set(page))
    def test_revoke_html_and_cover_and_unknown(self):
        p=self.share();self.api('shares/'+self.work['id']+'/'+p['token'],'DELETE')
        for path in ('/s/'+p['token'],'/s/'+p['token']+'/cover','/s/'+'a'*32):self.assertEqual(self.public_get(path)[0],404)
    def test_public_server_has_no_private_routes(self):
        for path in ('/','/api/config','/api/works','/api/backup/download','/app.js','/s/../api/config'):
            self.assertEqual(self.public_get(path)[0],404,path)
        self.assertEqual(self.public_get('/api/works','POST')[0],404)
        self.assertIn(b'Disallow: /',self.public_get('/robots.txt')[2])
    def test_confirmation_and_options_and_auth(self):
        route='/api/shares/'+self.work['id']
        self.assertEqual(self.request(route,'POST',{'options':{}})[0],400)
        self.assertEqual(self.request(route,'POST',{'expected_updated':self.work['updated']},token=False)[0],403)
        self.assertEqual(self.request(route,'POST',{'expected_updated':self.work['updated'],'options':{'review':'false'}})[0],400)
    def test_trash_revokes_and_restore_does_not_republish(self):
        p=self.share();self.api('works/'+self.work['id'],'DELETE')
        self.assertIsNone(share_server.get_page(p['token']))
        self.api('trash/restore','POST',{'ids':[self.work['id']]})
        self.assertIsNone(share_server.get_page(p['token']))
    def test_other_owner_cannot_revoke(self):
        p=self.share()
        with db.transaction() as c:c.execute("UPDATE shared_pages SET owner='other' WHERE token=?",(p['token'],))
        self.assertEqual(self.request('/api/shares/'+self.work['id']+'/'+p['token'],'DELETE')[0],400)
