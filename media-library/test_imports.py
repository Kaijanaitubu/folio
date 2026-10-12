"""Import identity, provenance, concurrency and v2 migration; disposable DBs."""
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
import db
import server
from source_identity import normalize_url

class ImportTests(unittest.TestCase):
    def setUp(self):
        (db.ROOT/'test-output').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=db.ROOT/'test-output'); self.old=db.PATH
        db.PATH=Path(self.temp.name)/'imports.sqlite3'; db.init()
    def tearDown(self): db.PATH=self.old; self.temp.cleanup()
    def save(self,data,wid=None):
        with db.transaction() as c: return db.save_work(c,data,wid)
    def item(self,url,label='',mode='source'):
        jid,iid=db.uid(),db.uid()
        with db.transaction() as c:
            c.execute('INSERT INTO jobs(id,owner,status,created,title_mode) VALUES(?,?,?,?,?)',(jid,db.OWNER,'running',db.now(),mode))
            c.execute("INSERT INTO job_items(id,job_id,url,label,status) VALUES(?,?,?,?,'running')",(iid,jid,url,label))
            return dict(c.execute('SELECT * FROM job_items WHERE id=?',(iid,)).fetchone())
    def test_normalization_and_distinct_pages(self):
        pairs=[(' HTTP://WWW.Example.org:80/a%62? # ', 'https://example.org/ab? #'),
               ('http://WWW.HITOMI.LA:443/reader/123.html?','https://hitomi.la/reader/123.html#01'),
               ('https://example.org','http://www.example.org/?#')]
        for a,b in pairs: self.assertEqual(normalize_url(a),normalize_url(b))
        for suffix in ('?q=1','?q=2','#2','#3','/'):
            self.assertNotEqual(normalize_url('https://hitomi.la/reader/123.html'+suffix),normalize_url('https://hitomi.la/reader/123.html'))
        self.assertNotEqual(normalize_url('https://example.org/A'),normalize_url('https://example.org/a'))
        self.assertNotEqual(normalize_url('https://example.org/a%2Fb'),normalize_url('https://example.org/a/b'))
        for bad in ('https://x:wrong','https://x:99999','http://user@x','javascript:a'):
            with self.assertRaises(ValueError): normalize_url(bad)
    def test_secondary_url_blocks_new_work_and_edit_rollback(self):
        u='https://hitomi.la/reader/123.html#2'
        a=self.save({'title':'Same','author':['Author A'],'links':[{'url':'https://example.org/a','is_primary':True},{'url':u}]})
        b=self.save({'title':'Same','links':[{'url':'https://hitomi.la/reader/123.html#3'}]})
        with self.assertRaises(db.DuplicateSource): self.save(dict(b,title='changed',links=[{'url':'http://www.hitomi.la/reader/123.html?#02'}]),b['id'])
        with db.transaction() as c:
            self.assertEqual(db.get_work(c,b['id'])['title'],'Same')
            matches=db.title_matches(c,'Same',b['id'])
            self.assertEqual(matches[0]['authors'],['Author A']); self.assertEqual(matches[0]['primary_url'],'https://example.org/a')
        self.save(a,a['id'])
    def test_concurrent_equivalent_url_has_one_winner(self):
        barrier=threading.Barrier(2); results=[]
        def save(url):
            barrier.wait()
            try: self.save({'title':'Same','links':[{'url':url}]}); results.append('added')
            except db.DuplicateSource: results.append('skipped')
        threads=[threading.Thread(target=save,args=(u,)) for u in ('https://hitomi.la/reader/999.html','http://www.hitomi.la/reader/999.html?#1')]
        for t in threads: t.start()
        for t in threads: t.join(10); self.assertFalse(t.is_alive())
        self.assertCountEqual(results,['added','skipped'])
    def test_title_modes_fallback_provenance_and_skip(self):
        for i,(mode,label,source,expected) in enumerate([('source','Bookmark','Source','Source'),('bookmark','Bookmark','Source','Bookmark'),('bookmark','  ','Source','Source'),('source','Bookmark','','Bookmark')]):
            item=self.item(f'https://hitomi.la/reader/{100+i}.html',label,mode)
            with patch('importer.import_url',return_value={'title':source,'tag':[{'name':'tag','gender':'female'}]}): server.process_import_item(item)
            with db.transaction() as c:
                final=c.execute('SELECT * FROM job_items WHERE id=?',(item['id'],)).fetchone()
                self.assertEqual(final['status'],'added'); work=db.get_work(c,final['work_id'])
                self.assertEqual(work['title'],expected)
                history=dict(c.execute('SELECT * FROM work_imports WHERE work_id=?',(work['id'],)).fetchone())
                self.assertEqual(history['bookmark_name'],label);self.assertEqual(history['source_title'],source)
            changed=dict(work,title='Edited',bookmark_names=['forged']); self.save(changed,work['id'])
            db.init()
            with db.transaction() as c:
                self.assertEqual(dict(c.execute('SELECT * FROM work_imports WHERE work_id=?',(work['id'],)).fetchone()),history)
            duplicate=self.item('http://www.hitomi.la/reader/'+str(100+i)+'.html?#01','Not stored','bookmark')
            with patch('importer.import_url') as fetch: server.process_import_item(duplicate); fetch.assert_not_called()
            with db.transaction() as c:
                self.assertEqual(c.execute('SELECT status FROM job_items WHERE id=?',(duplicate['id'],)).fetchone()[0],'duplicate_url')
                self.assertEqual(c.execute('SELECT count(*) FROM work_imports WHERE work_id=?',(work['id'],)).fetchone()[0],1)
    def test_empty_both_names_fails_without_work(self):
        item=self.item('https://hitomi.la/reader/888.html',' ')
        with patch('importer.import_url',return_value={'title':''}),self.assertRaisesRegex(ValueError,'No title'): server.process_import_item(item)
        with db.transaction() as c: self.assertEqual(c.execute('SELECT count(*) FROM works').fetchone()[0],0)
    def test_fetch_completion_after_cancel_does_not_save(self):
        item=self.item('https://hitomi.la/reader/444.html')
        def fetch(url):
            with db.transaction() as c: c.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(item['job_id'],))
            return {'title':'Cancelled'}
        with patch('importer.import_url',side_effect=fetch): server.process_import_item(item)
        with db.transaction() as c: self.assertEqual(c.execute('SELECT count(*) FROM works').fetchone()[0],0)
    def test_v2_migration_preserves_legacy_conflicts_scores_and_history(self):
        a=self.save({'title':'Old A','author':['Legacy'],'links':[{'url':'https://hitomi.la/reader/666.html'}]})
        b=self.save({'title':'Old B'})
        with db.transaction() as c:
            did=db.save_dimension(c,{'name':'Rating','maximum':5,'symbol':'Star'})
            c.execute('INSERT INTO scores VALUES(?,?,?)',(a['id'],did,4))
            c.execute('INSERT INTO links VALUES(?,?,?,?,?,?,?)',(db.uid(),b['id'],'http://www.hitomi.la/reader/666.html#1','legacy',0,1,normalize_url('https://hitomi.la/reader/666.html')))
            c.execute("INSERT INTO jobs(id,owner,status,created) VALUES('legacy-job','local','complete',?)",(db.now(),))
            c.execute("INSERT INTO job_items(id,job_id,url,label,status,title,work_id) VALUES('legacy-item','legacy-job',?,'Original bookmark','added','Old A',?)",(a['links'][0]['url'],a['id']))
        # Produce the previous schema, without depending on a Git checkout or private data.
        c=db.connect(); c.execute('PRAGMA foreign_keys=OFF')
        c.execute('DROP TABLE work_imports');c.execute('DROP TABLE source_claims')
        c.execute('DROP INDEX link_key');c.execute('ALTER TABLE links DROP COLUMN url_key')
        c.execute('ALTER TABLE jobs DROP COLUMN title_mode');c.execute('ALTER TABLE job_items DROP COLUMN warnings_json')
        schema=c.execute("SELECT sql FROM sqlite_master WHERE name='works'").fetchone()[0]
        schema=schema.replace('"works"','works_legacy',1).replace('CREATE TABLE works(', 'CREATE TABLE works_legacy(',1)
        c.execute(schema[:-1]+', UNIQUE(owner,title))');c.execute('INSERT INTO works_legacy SELECT * FROM works')
        c.execute('DROP TABLE works');c.execute('ALTER TABLE works_legacy RENAME TO works')
        c.execute('DELETE FROM migrations WHERE version=3');c.commit()
        tables=['works','links','scores','work_entities','entities','aliases','dimensions','jobs','job_items']
        before={name:[dict(r) for r in c.execute('SELECT * FROM '+name+' ORDER BY rowid')] for name in tables};c.close()
        db.init()
        with db.transaction() as c:
            for name,rows in before.items():
                after=[dict(r) for r in c.execute('SELECT * FROM '+name+' ORDER BY rowid')]
                self.assertEqual([{k:r[k] for k in rows[0]} for r in after] if rows else after,rows,name)
            self.assertEqual(len(db.exact_sources(c,'https://hitomi.la/reader/666.html')),2)
            self.assertEqual(db.get_work(c,a['id'])['bookmark_names'],['Original bookmark'])
            self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok');self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(),[])
        self.save(a,a['id']);self.save({'title':'Old A'})
        with self.assertRaises(db.DuplicateSource): self.save({'title':'New','links':[{'url':'https://hitomi.la/reader/666.html'}]})
        with db.transaction() as c:
            # Permanent deletion now releases claims; normal deletion reserves them in Trash.
            db.purge_work(c,a['id'])
            self.assertEqual(c.execute('SELECT work_id FROM source_claims WHERE url_key=?',(normalize_url('https://hitomi.la/reader/666.html'),)).fetchone()[0],b['id'])
        self.assertEqual(len(list((db.PATH.parent/'migration-backups').glob('*.sqlite3'))),1)

if __name__=='__main__': unittest.main()
