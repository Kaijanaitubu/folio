import json
from io import BytesIO
import zipfile
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from unittest.mock import patch
import db,server

class BackupDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=db.ROOT/'test-output')
        self.root=Path(self.temp.name)
        self.path=patch.object(db,'PATH',self.root/'library.sqlite3');self.path.start()
        self.env=patch.dict('os.environ',{'MEDIA_BACKUPS':str(self.root/'backups')});self.env.start()
        db.init()
        with db.transaction() as c:
            self.work=db.save_work(c,{'title':'Synthetic download','tag':[{'name':'test-tag','gender':'neutral'}]})
        self.http=server.LibraryHTTPServer(('127.0.0.1',0),server.Handler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.env.stop();self.path.stop();self.temp.cleanup()
    def request(self,method='POST',token=True,origin=None):
        headers={'Content-Type':'application/json'}
        if token: headers['X-Library-Token']=server.TOKEN
        if origin: headers['Origin']=origin
        return urlopen(Request(f'http://127.0.0.1:{self.http.server_address[1]}/api/backup/download',data=b'{}' if method=='POST' else None,headers=headers,method=method),timeout=10)
    def test_download_is_complete_restorable_and_not_cached(self):
        with self.request() as response:
            self.assertEqual(response.headers['Cache-Control'],'no-store')
            self.assertIn('attachment;',response.headers['Content-Disposition'])
            raw=response.read();self.assertEqual(len(raw),int(response.headers['Content-Length']))
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            self.assertEqual(len(archive.namelist()),1)
            raw=archive.read(archive.namelist()[0])
        self.assertTrue(raw.startswith(b'SQLite format 3\x00'))
        path=self.root/'downloaded.sqlite3';path.write_bytes(raw)
        connection=db.connect(path)
        try:
            self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(connection.execute('SELECT title FROM works').fetchone()[0],'Synthetic download')
            self.assertEqual(connection.execute('SELECT count(*) FROM entities').fetchone()[0],1)
        finally:connection.close()
    def test_requires_token_origin_and_post(self):
        for kwargs,status in (({'token':False},403),({'origin':'https://other.example'},403),({'method':'GET'},405)):
            with self.assertRaises(HTTPError) as error:self.request(**kwargs)
            self.assertEqual(error.exception.code,status)
        self.assertFalse((self.root/'backups').exists())

if __name__=='__main__':unittest.main()
