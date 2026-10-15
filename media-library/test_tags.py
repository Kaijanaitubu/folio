"""Tag changes use disposable libraries, never the personal collection."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import db
import features
import tag_policy as tags
import import_jobs as jobs
import import_matching as matching


class TagTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=db.PATH
        db.PATH=Path(self.temp.name)/'test.sqlite3';db.init()
    def tearDown(self):
        db.PATH=self.old;self.temp.cleanup()
    def entity(self,c,name,gender='neutral',aliases=None):
        ident=db.save_entity(c,dict(kind='tag',name=name,gender=gender,aliases=aliases or []))
        return db.entity_data(c,c.execute('SELECT * FROM entities WHERE id=?',(ident,)).fetchone())
    def test_work_attribute_reuses_existing_and_deduplicates_only_this_work(self):
        with db.transaction() as c:
            none=self.entity(c,'sample'); female=self.entity(c,'sample','female')
            a=db.save_work(c,{'title':'A','tag':[none,female]});b=db.save_work(c,{'title':'B','tag':[none]})
            a['tag']=[female,female];a=features.save_work(c,a,a['id'])
            self.assertEqual([e['id'] for e in a['tag']],[female['id']])
            self.assertEqual(db.get_work(c,b['id'])['tag'][0]['id'],none['id'])
    def test_pending_attribute_tag_created_on_work_save_and_cancel_creates_nothing(self):
        with db.transaction() as c:
            none=self.entity(c,'sample',aliases=['example']);w=db.save_work(c,{'title':'A','tag':[none]})
            pending=dict(none,gender='male',literal_name=True);pending.pop('id')
            self.assertEqual(len(db.entity_list(c,'tag')),1)
            w['tag']=[pending];saved=features.save_work(c,w,w['id'])
            self.assertEqual(saved['tag'][0]['gender'],'male');self.assertEqual(saved['tag'][0]['aliases'],['example'])
            self.assertEqual(len(db.entity_list(c,'tag')),2)
    def test_normalized_name_alias_and_canonical_shadow_are_reviewed(self):
        with db.transaction() as c:
            a=self.entity(c,'Archive',aliases=[' Ｂｌｕｅ　Archive '])
            self.assertEqual(db.resolve(c,'tag',{'name':'blue archive'}),a['id'])
            b=self.entity(c,'BLUE ARCHIVE')
            with self.assertRaisesRegex(ValueError,'Ambiguous'): db.resolve(c,'tag',{'name':'blue archive'})
            conflicts=tags.resolve_tags(c,{'tag':[{'name':'blue archive'}]})
            self.assertEqual({e['id'] for e in conflicts[0]['choices']},{a['id'],b['id']})
            self.assertFalse(tags.matches(c,'blue archive','female'))
    def test_manual_collision_no_partial_write_and_acknowledgment_is_rechecked(self):
        with db.transaction() as c:
            a=self.entity(c,'Archive',aliases=['Blue'])
            value={'kind':'tag','name':'blue','aliases':[]}
            with self.assertRaises(tags.Conflict) as caught: tags.save(c,value)
            self.assertEqual(len(db.entity_list(c)),1)
            self.entity(c,'Other',aliases=['blue'])
            with self.assertRaises(tags.Conflict): tags.save(c,dict(value,allow_collision=True,collision_signature=caught.exception.signature))
            with self.assertRaises(tags.Conflict) as updated: tags.save(c,value)
            separate=tags.save(c,dict(value,allow_collision=True,collision_signature=updated.exception.signature))
            self.assertNotEqual(separate,a['id'])
    def test_alias_addition_proposes_merge_and_rename_to_old_alias_still_checks(self):
        with db.transaction() as c:
            a=self.entity(c,'Archive');b=self.entity(c,'Blue')
            with self.assertRaises(tags.Conflict): tags.save(c,dict(a,aliases=['Blue']),a['id'])
            db.save_entity(c,dict(a,aliases=['Blue']),a['id'])
            with self.assertRaises(tags.Conflict): tags.save(c,dict(a,name='Blue',aliases=[]),a['id'])
    def test_merge_same_name_different_attribute_trash_redirect_and_undo(self):
        with db.transaction() as c:
            a=self.entity(c,'sample',aliases=['source alias']);b=self.entity(c,'sample','female',['target alias'])
            db.save_entity(c,dict(b,display_alias='target alias',sort_reading='target reading'),b['id'])
            w=db.save_work(c,{'title':'Active','tag':[a,b]});trash=db.save_work(c,{'title':'Trash','tag':[a]});features.trash(c,trash['id'])
            preview=tags.merge_preview(c,a['id'],b['id']);result=tags.merge(c,a['id'],b['id'],preview['signature'])
            self.assertEqual(result['count'],2);self.assertEqual(tags.entity_id(c,a['id']),b['id'])
            merged=tags.entity_state(c,b['id']);self.assertEqual(merged['gender'],'female')
            self.assertEqual(merged['name'],'target alias');self.assertEqual(merged['display_alias'],'');self.assertEqual(merged['sort_reading'],'target reading')
            self.assertEqual(merged['aliases'],['sample','source alias'])
            self.assertEqual(len(db.get_work(c,w['id'])['tag']),1)
            self.assertFalse(features.restore_preview(c,[trash['id']])['missing'])
            self.assertEqual(db.resolve(c,'tag',a),b['id'])
            features.undo(c,result['history_id'],True)
            self.assertEqual(tags.entity_id(c,a['id']),a['id'])
            self.assertEqual(len(db.get_work(c,w['id'])['tag']),2)
            self.assertEqual(db.get_work(c,trash['id'],include_deleted=True)['tag'][0]['id'],a['id'])
            self.assertEqual(tags.entity_state(c,b['id'])['aliases'],['sample'])
    def test_merge_edited_attribute_collision_and_target_settings(self):
        with db.transaction() as c:
            a=self.entity(c,'same');b=self.entity(c,'same','female')
            result=tags.merge(c,a['id'],b['id'],data=dict(a,gender='female',aliases=['new alias']))
            self.assertEqual(tags.entity_state(c,b['id'])['aliases'],['new alias'])
            features.undo(c,result['history_id'],True)
            self.assertEqual(tags.entity_state(c,a['id'])['gender'],'neutral')
    def test_merge_preview_and_undo_reject_concurrent_changes(self):
        with db.transaction() as c:
            a=self.entity(c,'A');b=self.entity(c,'B');preview=tags.merge_preview(c,a['id'],b['id'])
            db.save_work(c,{'title':'Later','tag':[a]})
            with self.assertRaisesRegex(ValueError,'preview'): tags.merge(c,a['id'],b['id'],preview['signature'])
            result=tags.merge(c,a['id'],b['id']);db.save_work(c,{'title':'Another','tag':[b]})
            with self.assertRaisesRegex(ValueError,'changed'): features.undo(c,result['history_id'],True)
            self.assertEqual(tags.entity_id(c,a['id']),b['id'])
    def test_chained_merges_and_previous_work_history_resolve_old_ids(self):
        with db.transaction() as c:
            a=self.entity(c,'A');b=self.entity(c,'B');z=self.entity(c,'Z')
            w=db.save_work(c,{'title':'Work','tag':[a]});w['tag']=[b];features.save_work(c,w,w['id'])
            edit=features.history(c)[0]['id']
            first=tags.merge(c,a['id'],b['id']);second=tags.merge(c,b['id'],z['id'])
            self.assertEqual(tags.entity_id(c,a['id']),z['id']);self.assertEqual(tags.entity_id(c,b['id']),z['id'])
            features.undo(c,edit,True);self.assertEqual(db.get_work(c,w['id'])['tag'][0]['id'],z['id'])
            features.undo(c,second['history_id'],True);features.undo(c,first['history_id'],True)
            self.assertEqual(tags.entity_id(c,a['id']),a['id'])
    def test_frozen_import_snapshot_redirects_without_permanent_gender_rule(self):
        with db.transaction() as c:
            a=self.entity(c,'same');b=self.entity(c,'same','female');snapshot=matching.tag_snapshot(c)
            tags.merge(c,a['id'],b['id'])
            old={'tag':[{'name':'same'}]};matching.apply_tags(c,old,'neutral',snapshot)
            self.assertEqual(old['tag'][0]['id'],b['id'])
            fresh={'tag':[{'name':'same'}]};matching.apply_tags(c,fresh,'neutral')
            self.assertEqual(fresh['tag'][0]['gender'],'neutral');self.assertNotIn('id',fresh['tag'][0])
    def test_batch_reuses_alias_and_ambiguous_item_waits_without_stopping_others(self):
        with db.transaction() as c:
            a=self.entity(c,'Archive',aliases=['blue']);b=self.entity(c,'Other',aliases=['shared']);z=self.entity(c,'Third',aliases=['shared'])
            jid=jobs.create(c,{'items':[{'url':'https://hitomi.la/reader/123.html'},{'url':'https://hitomi.la/reader/456.html'}]})['id']
            items=[dict(r) for r in c.execute('SELECT * FROM job_items WHERE job_id=? ORDER BY rowid',(jid,))]
        with patch('importer.import_url',side_effect=[{'title':'Needs choice','tag':[{'name':'shared'}]},{'title':'Resolved','tag':[{'name':'BLUE'}]}]):
            for item in items: jobs.process_item(item)
        with db.transaction() as c:
            jobs.settle(c,jid);self.assertEqual(jobs.job(c,jid)['status'],'awaiting_review')
            row=c.execute('SELECT * FROM job_items WHERE id=?',(items[0]['id'],)).fetchone();self.assertEqual(row['status'],'tag_review');self.assertTrue(json.loads(row['payload']))
            self.assertEqual(db.list_works(c)['total'],1);self.assertEqual(db.list_works(c)['items'][0]['tag'][0]['id'],a['id'])
            with self.assertRaises(ValueError): jobs.decide_tags(c,jid,{'item_id':items[0]['id'],'choices':{'0':a['id']}})
            jobs.decide_tags(c,jid,{'item_id':items[0]['id'],'choices':{'0':b['id']}})
            self.assertEqual(jobs.job(c,jid)['status'],'complete');self.assertEqual(db.list_works(c)['total'],2)
    def test_none_search_matches_only_no_attribute_and_legacy_query_works(self):
        with db.transaction() as c:
            db.save_work(c,{'title':'None','tag':[{'name':'sample','gender':'none'}]})
            db.save_work(c,{'title':'Female','tag':[{'name':'sample','gender':'female'}]})
            self.assertEqual(db.list_works(c,'none:sample')['total'],1)
            self.assertEqual(db.list_works(c,'neutral:sample')['total'],1)
            self.assertEqual(db.list_works(c,'tag:sample')['total'],2)


if __name__=='__main__': unittest.main()
