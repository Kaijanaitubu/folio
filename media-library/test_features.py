"""Recovery and bulk operations are tested only with disposable databases."""
from pathlib import Path
import tempfile
import unittest
import db
import features as f

class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.old=db.PATH
        db.PATH=Path(self.temp.name)/'library.sqlite3'; db.init()
    def tearDown(self): db.PATH=self.old; self.temp.cleanup()
    def work(self,title='A',**values):
        with db.transaction() as c: return db.save_work(c,{'title':title,**values})
    def test_trash_excludes_search_counts_and_random_but_reserves_url(self):
        w=self.work(tag=['tag'],links=[{'url':'https://hitomi.la/reader/123.html'}])
        with db.transaction() as c:
            f.trash(c,w['id'])
            self.assertEqual(db.list_works(c)['total'],0)
            self.assertEqual(db.list_works(c,random_one=True)['items'],[])
            self.assertEqual(db.entity_list(c)[0]['uses'],0)
            self.assertTrue(db.exact_sources(c,w['links'][0]['url'])[0]['deleted_at'])
            self.assertRaises(ValueError,db.get_work,c,w['id'])
            self.assertRaises(db.DuplicateSource,db.save_work,c,{'title':'B','links':w['links']})
            f.restore(c,[w['id']]); self.assertEqual(db.get_work(c,w['id'])['tag'][0]['name'],'tag')
    def test_trash_missing_metadata_requires_review(self):
        w=self.work(tag=['tag'])
        with db.transaction() as c:
            f.trash(c,w['id']); c.execute('DELETE FROM entities WHERE id=?',(w['tag'][0]['id'],))
            preview=f.restore_preview(c,[w['id']]);self.assertEqual(preview['missing'][0]['names'],['tag'])
            self.assertRaises(ValueError,f.restore,c,[w['id']])
            f.restore(c,[w['id']],preview['signature'])
    def test_restore_race_does_not_apply(self):
        w=self.work()
        with db.transaction() as c:
            f.trash(c,w['id']); preview=f.restore_preview(c,[w['id']])
            c.execute('UPDATE works SET title=? WHERE id=?',('Changed',w['id']))
            self.assertRaises(ValueError,f.restore,c,[w['id']],preview['signature'])
            self.assertTrue(f.trash_list(c))
    def test_cleanup_only_expired_trash_and_preserves_active_entries(self):
        a=self.work('active'); b=self.work('expired'); d=self.work('recent')
        with db.transaction() as c:
            f.trash(c,b['id']); f.trash(c,d['id'])
            c.execute("UPDATE works SET deleted_at='2000-01-01' WHERE id=?",(b['id'],))
            f.cleanup(c)
            self.assertIsNotNone(db.get_work(c,a['id']))
            self.assertEqual([w['id'] for w in f.trash_list(c)],[d['id']])
    def test_undo_preserves_unrelated_later_edit(self):
        w=self.work(review='before')
        with db.transaction() as c:
            f.save_work(c,{**w,'review':'after'},w['id']); h=f.history(c)[0]['id']
            current=db.get_work(c,w['id']); f.save_work(c,{**current,'title':'Renamed'},w['id'])
            f.undo(c,h,True); result=db.get_work(c,w['id'])
            self.assertEqual(result['review'],'before'); self.assertEqual(result['title'],'Renamed')
            self.assertRaises(ValueError,f.undo,c,h,True)
    def test_undo_conflict_and_stale_edit_are_rejected(self):
        w=self.work(review='before')
        with db.transaction() as c: f.save_work(c,{**w,'review':'after'},w['id']);h=f.history(c)[0]['id']
        with db.transaction() as c:
            current=db.get_work(c,w['id']); f.save_work(c,{**current,'review':'later'},w['id'])
        with db.transaction() as c:
            self.assertRaises(ValueError,f.undo,c,h,True)
            self.assertRaises(ValueError,f.save_work,c,{**w,'title':'stale'},w['id'])
            self.assertEqual(db.get_work(c,w['id'])['review'],'later')
    def test_exact_scale_undo_including_trash(self):
        with db.transaction() as c: did=db.save_dimension(c,{'name':'Quality','maximum':5,'symbol':'Star'})
        a=self.work('A',ratings={did:4}); b=self.work('B',ratings={did:1})
        with db.transaction() as c:
            f.trash(c,b['id']); preview=db.dimension_preview(c,did,3)
            f.save_dimension(c,{'name':'Quality','maximum':3,'symbol':'Star','conversion_signature':preview['signature']},did)
            self.assertNotEqual(db.get_work(c,a['id'])['ratings'][did],4)
            f.undo(c,f.history(c)[0]['id'],True)
            self.assertEqual(db.get_work(c,a['id'])['ratings'][did],4)
            self.assertEqual(db.get_work(c,b['id'],include_deleted=True)['ratings'][did],1)
            self.assertEqual(db.dimensions(c)[0]['maximum'],5)
    def test_scale_undo_rejects_later_scores(self):
        with db.transaction() as c: did=db.save_dimension(c,{'name':'Q','maximum':5,'symbol':'Star'})
        w=self.work(ratings={did:4})
        with db.transaction() as c:
            preview=db.dimension_preview(c,did,3); f.save_dimension(c,{'name':'Q','maximum':3,'symbol':'Star','conversion_signature':preview['signature']},did)
            h=f.history(c)[0]['id']; c.execute('UPDATE scores SET value=1 WHERE work_id=?',(w['id'],))
            self.assertRaises(ValueError,f.undo,c,h,True)
    def test_batch_add_remove_replace_clear_and_undo(self):
        a=self.work('A',tag=[{'name':'same','gender':'female'}]); b=self.work('B',tag=[{'name':'same','gender':'male'}])
        female=a['tag'][0]; male=b['tag'][0]
        for mode,items,expected in [('add',[male],{female['id'],male['id']}),('remove',[female],{male['id']}),('replace',[female],{female['id']}),('clear',[],set())]:
            with db.transaction() as c:
                p=f.batch_preview(c,{'ids':[a['id']],'patch':{'tag':{'mode':mode,'items':items}}})
                r=f.batch_apply(c,p['id']); ids={e['id'] for e in db.get_work(c,a['id'])['tag']}
                self.assertEqual(ids,expected)
        with db.transaction() as c:
            f.undo(c,r['operation'],True);self.assertEqual(db.get_work(c,a['id'])['tag'][0]['id'],female['id'])
    def test_batch_unchanged_does_not_update_timestamp_or_history(self):
        w=self.work(bought=True)
        with db.transaction() as c:
            p=f.batch_preview(c,{'ids':[w['id']],'patch':{'bought':True}})
            self.assertEqual(p['changed'],0); r=f.batch_apply(c,p['id'])
            self.assertIsNone(r['operation']);self.assertEqual(db.get_work(c,w['id'])['updated'],w['updated'])
    def test_batch_conflict_cancels_all(self):
        a=self.work('A');b=self.work('B')
        with db.transaction() as c: p=f.batch_preview(c,{'ids':[a['id'],b['id']],'patch':{'bought':True}})
        with db.transaction() as c: c.execute('UPDATE works SET review=? WHERE id=?',('changed',b['id']))
        with db.transaction() as c:
            self.assertRaises(ValueError,f.batch_apply,c,p['id'])
            self.assertFalse(db.get_work(c,a['id'])['bought']);self.assertFalse(db.get_work(c,b['id'])['bought'])
    def test_batch_rollback_after_late_validation_failure(self):
        a=self.work('A'); b=self.work('B')
        with db.transaction() as c:
            did=db.save_dimension(c,{'name':'Q','maximum':5,'symbol':'Star'})
            p=f.batch_preview(c,{'ids':[a['id'],b['id']],'patch':{'ratings':{did:5}}})
        with db.transaction() as c: c.execute('DELETE FROM dimensions WHERE id=?',(did,))
        with self.assertRaises(ValueError):
            with db.transaction() as c: f.batch_apply(c,p['id'])
        with db.transaction() as c: self.assertFalse(db.get_work(c,a['id'])['ratings'])
    def test_all_results_selection_respects_query_and_trash(self):
        a=self.work('A'); b=self.work('B'); d=self.work('A')
        with db.transaction() as c:
            f.trash(c,d['id']);self.assertEqual(f.batch_targets(c,{'all':True,'query':'title:A'}),[a['id']])
    def test_saved_search_order_update_and_invalidated_dimension(self):
        with db.transaction() as c:
            did=db.save_dimension(c,{'name':'Q','maximum':5,'symbol':'Star'})
            a=f.save_search(c,{'name':'High','query':'rating1:>=4','sort':'rating1'})['id']
            b=f.save_search(c,{'name':'All'})['id']; f.reorder_searches(c,[b,a])
            self.assertEqual([r['id'] for r in f.searches(c)],[b,a])
            c.execute('DELETE FROM dimensions WHERE id=?',(did,))
            self.assertTrue(f.searches(c)[1]['error'])
            f.save_search(c,{'name':'Fixed','query':'','sort':'newest'},a)
            self.assertFalse(f.searches(c)[1]['error'])
    def test_batch_expiry_and_replay(self):
        w=self.work()
        with db.transaction() as c:
            p=f.batch_preview(c,{'ids':[w['id']],'patch':{'bought':True}})
            c.execute("UPDATE batch_previews SET created='2000-01-01' WHERE id=?",(p['id'],))
            self.assertRaises(ValueError,f.batch_apply,c,p['id'])
            p=f.batch_preview(c,{'ids':[w['id']],'patch':{'bought':True}}); f.batch_apply(c,p['id'])
            self.assertRaises(ValueError,f.batch_apply,c,p['id'])

if __name__=='__main__': unittest.main()
