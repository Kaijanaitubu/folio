"""Migration, all 32 mark combinations, quick saves and recovery."""
from pathlib import Path
import sqlite3
import tempfile
import unittest
import db
import features
import marks

class MarkTests(unittest.TestCase):
    def setUp(self):
        (db.ROOT/'test-output').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=db.ROOT/'test-output'); self.old=db.PATH
        db.PATH=Path(self.temp.name)/'fixture.sqlite3'; db.init()
    def tearDown(self): db.PATH=self.old; self.temp.cleanup()
    def test_every_combination_and_search(self):
        with db.transaction() as c:
            for b in range(32): db.save_work(c,{'title':str(b),'marks':marks.numbers(b)})
            expected={'mark:124':4,'mark:421':4,'mark:1124':4,'mark:=124':1,'mark:none':1,'mark:any':31,'-mark:2':16,'mark:1/mark:4':24,'bought:yes':16,'mark1:no':16,'mark:=12345':1,'mark:124 -mark:3':2}
            for q,total in expected.items():
                self.assertEqual(db.list_works(c,q)['total'],total,q)
                self.assertEqual(len(features.batch_targets(c,{'all':True,'query':q})),total)
            for q in ('mark:0','mark:6','mark:=','mark:11010','mark:abc','mark:=none'):
                with self.assertRaises(ValueError): db.list_works(c,q)
    def test_quick_save_is_scoped_idempotent_guarded_and_undoable(self):
        with db.transaction() as c:
            w=db.save_work(c,{'title':'Work','review':'Keep','marks':[1,4]})
            saved=marks.toggle(c,w['id'],{'number':2,'value':True,'expected':[1,4]})
            self.assertEqual(saved['marks'],[1,2,4]);self.assertEqual(saved['review'],'Keep')
            count=len(features.history(c))
            marks.toggle(c,w['id'],{'number':2,'value':True,'expected':[]})
            self.assertEqual(len(features.history(c)),count)
            with self.assertRaises(ValueError): marks.toggle(c,w['id'],{'number':5,'value':True,'expected':[1]})
            features.undo(c,features.history(c)[0]['id'],True)
            self.assertEqual(db.get_work(c,w['id'])['marks'],[1,4])
            features.trash(c,w['id'])
            with self.assertRaises(ValueError): marks.toggle(c,w['id'],{'number':3,'value':True,'expected':[1,4]})
    def test_legacy_purchase_writes_and_histories_preserve_other_marks(self):
        with db.transaction() as c:
            w=db.save_work(c,{'title':'Work','marks':[4,5]})
            c.execute('UPDATE works SET bought=1 WHERE id=?',(w['id'],))
            self.assertEqual(db.get_work(c,w['id'])['marks'],[1,4,5])
            hid=features.record(c,'edit',{'works':{w['id']:{'bought':{'before':0,'after':1}}},'titles':['Work']})
            features.undo(c,hid,True)
            self.assertEqual(db.get_work(c,w['id'])['marks'],[4,5])
            old=db.get_work(c,w['id']);old.pop('marks');old['bought']=True
            self.assertEqual(db.save_work(c,old,w['id'])['marks'],[1,4,5])
            self.assertEqual(db.save_work(c,{'title':'Rename'},w['id'])['marks'],[1,4,5])
    def test_batch_preview_apply_and_undo(self):
        with db.transaction() as c:
            a=db.save_work(c,{'title':'A','marks':[1,4]}); b=db.save_work(c,{'title':'B','marks':[4]})
            p=features.batch_preview(c,{'ids':[a['id'],b['id']],'patch':{'marks':{'mode':'add','items':[1,2]}}})
            self.assertEqual(p['changed'],2)
            r=features.batch_apply(c,p['id']);self.assertEqual(r['changed'],2)
            features.undo(c,r['operation'],True)
            self.assertEqual(db.get_work(c,b['id'])['marks'],[4])
            p=features.batch_preview(c,{'ids':[a['id']],'patch':{'marks':{'mode':'clear'}}})
            features.batch_apply(c,p['id']);self.assertEqual(db.get_work(c,a['id'])['bought'],0)
    def test_labels_are_fixed_five_owner_scoped_and_checked(self):
        with db.transaction() as c:
            self.assertEqual([d['number'] for d in marks.definitions(c)],[1,2,3,4,5])
            labels=['Purchased','Read','Later','Favorite','Review']
            marks.save_labels(c,{'expected':['']*5,'labels':labels})
            self.assertEqual([d['label'] for d in marks.definitions(c)],labels)
            with self.assertRaises(ValueError): marks.save_labels(c,{'expected':['']*5,'labels':labels})
            for data in ([1],[True],['1'],[6],None):
                if data==[1]: continue
                with self.assertRaises(ValueError): marks.bits(data)
    def test_migration_preserves_purchase_and_is_idempotent(self):
        with db.transaction() as c:
            w=db.save_work(c,{'title':'Purchased','bought':True})
            c.executescript('DROP TRIGGER purchase_to_mark;DROP TRIGGER mark_to_purchase;DROP TRIGGER purchase_mark_insert;DROP TABLE mark_labels;DELETE FROM migrations WHERE version=8;ALTER TABLE works DROP COLUMN mark_bits;')
        db.init();db.init()
        with db.transaction() as c:
            self.assertEqual(db.get_work(c,w['id'])['marks'],[1])
            self.assertEqual(c.execute('SELECT count(*) FROM mark_labels').fetchone()[0],5)
            self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok')

if __name__=='__main__': unittest.main()
