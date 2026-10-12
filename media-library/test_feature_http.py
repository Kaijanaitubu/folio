import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import db
import server

class FeatureHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=db.PATH;db.PATH=Path(self.temp.name)/'test.sqlite3';db.init()
        self.http=server.LibraryHTTPServer(('127.0.0.1',0),server.Handler); self.base=f'http://127.0.0.1:{self.http.server_address[1]}'
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
    def tearDown(self): self.http.shutdown();self.http.server_close();db.PATH=self.old;self.temp.cleanup()
    def request(self,path,method='GET',data=None,token=True):
        headers={'Content-Type':'application/json'}
        if token: headers['X-Library-Token']=server.TOKEN
        req=Request(self.base+path,method=method,headers=headers,data=json.dumps(data).encode() if data is not None else None)
        try:
            with urlopen(req) as r: return r.status,dict(r.headers),r.read()
        except HTTPError as r: return r.code,dict(r.headers),r.read()
    def api(self,path,method='GET',data=None):
        code,headers,raw=self.request('/api/'+path,method,data)
        self.assertEqual(code,200,raw);return json.loads(raw)
    def test_edit_trash_url_lookup_and_restore_contract(self):
        w=self.api('works','POST',{'title':'A','links':[{'url':'https://hitomi.la/reader/123.html#2'}]})
        w['title']='B';self.api('works/'+w['id'],'PUT',w)
        self.assertEqual(self.api('history')[0]['kind'],'edit')
        self.api('works/'+w['id'],'DELETE')
        self.assertEqual(self.api('works')['total'],0)
        self.assertTrue(self.api('source-check','POST',{'url':w['links'][0]['url']})['matches'][0]['deleted_at'])
        preview=self.api('trash/restore-preview','POST',{'ids':[w['id']]})
        self.api('trash/restore','POST',{'ids':[w['id']],'signature':preview['signature']})
        self.assertEqual(self.api('works/'+w['id'])['title'],'B')
    def test_new_endpoints_require_mutation_token(self):
        for endpoint in ('batch/preview','saved-searches','trash/restore','history/missing/undo','covers/preview'):
            self.assertEqual(self.request('/api/'+endpoint,'POST',{},token=False)[0],403)
    def test_batch_selection_preview_apply_and_undo(self):
        a=self.api('works','POST',{'title':'A'});self.api('works','POST',{'title':'B'})
        ids=self.api('works?ids=1&q=title:A')['ids'];self.assertEqual(ids,[a['id']])
        preview=self.api('batch/preview','POST',{'ids':ids,'patch':{'bought':True}})
        result=self.api('batch/apply','POST',{'id':preview['id']});self.assertEqual(result['changed'],1)
        self.api('history/'+result['operation']+'/preview','POST',{})
        self.api('history/'+result['operation']+'/undo','POST',{})
        self.assertFalse(self.api('works/'+a['id'])['bought'])
    def test_preview_returns_uncached_image_and_rejects_general_proxy(self):
        with patch('cover_relay.load',return_value=('image/webp',b'fixture')) as load:
            code,headers,raw=self.request('/api/covers/preview','POST',{'url':'https://tn.hitomi.la/path.webp'})
            self.assertEqual(code,200);self.assertEqual(raw,b'fixture');self.assertEqual(headers['Cache-Control'],'no-store');load.assert_called_once()
        self.assertEqual(self.request('/api/covers/preview','POST',{'url':'http://127.0.0.1:1234/private'})[0],400)
    def test_manifest_share_route_and_worker_do_not_cache_library(self):
        code,headers,raw=self.request('/manifest.webmanifest');self.assertEqual(code,200)
        manifest=json.loads(raw);self.assertEqual(manifest['share_target']['action'],'/share-target')
        self.assertEqual(self.request('/share-target?text=https%3A%2F%2Fexample.com')[0],200)
        raw=self.request('/sw.js')[2];self.assertNotIn(b'caches.open',raw)
        self.assertIn('blob:',self.request('/')[1]['Content-Security-Policy'])
    def test_generic_shared_source_checks_all_links(self):
        w=self.api('works','POST',{'title':'A','links':[{'url':'https://example.com/art'}]})
        result=self.api('source-check','POST',{'url':'https://example.com/art','generic':True})
        self.assertEqual(result['matches'][0]['id'],w['id'])

if __name__=='__main__':unittest.main()
