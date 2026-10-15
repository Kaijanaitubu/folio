"""Primary-name promotion and legacy migration use disposable collections."""
from pathlib import Path
import tempfile
import unittest
import db
import features
import primary_names
import tag_policy
import import_matching


class PrimaryNameTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.previous=db.PATH
        db.PATH=Path(self.temp.name)/'test.sqlite3';db.init()
    def tearDown(self):
        db.PATH=self.previous;self.temp.cleanup()
    def row(self,c,ident):
        return db.entity_data(c,c.execute('SELECT * FROM entities WHERE id=?',(ident,)).fetchone())
    def legacy(self,c,name,selected,kind='tag'):
        ident=db.save_entity(c,dict(kind=kind,name=name,aliases=[selected],sort_reading='reading'))
        c.execute('UPDATE entities SET display_alias=? WHERE id=?',(selected,ident))
        return ident
    def test_promote_each_kind_keeps_ids_associations_and_import_lookup(self):
        with db.transaction() as c:
            for kind in ('tag','author','circle','series','character'):
                ident=db.save_entity(c,dict(kind=kind,name='Original',aliases=['Alias','Third']))
                work=db.save_work(c,dict(title=kind,**{kind:[{'id':ident}]}))
                created=self.row(c,ident)['created']
                tag_policy.save(c,dict(kind=kind,name='Alias',aliases=['Original','Third']),ident)
                item=self.row(c,ident)
                self.assertEqual((item['name'],item['display_name'],item['display_alias']),('Alias','Alias',''))
                self.assertEqual(item['aliases'],['Original','Third'])
                self.assertEqual(item['created'],created)
                self.assertEqual(db.get_work(c,work['id'])[kind][0]['id'],ident)
                for name in ('Original','Alias','Third'):
                    self.assertEqual(db.resolve(c,kind,{'name':name}),ident)
                # Switch back via the older API contract as well.
                tag_policy.save(c,dict(item,display_alias='Original'),ident)
                self.assertEqual(self.row(c,ident)['name'],'Original')
                self.assertEqual(self.row(c,ident)['aliases'],['Alias','Third'])
    def test_promotion_checks_alias_collisions_before_writing_and_merge_keeps_names(self):
        with db.transaction() as c:
            a=db.save_entity(c,dict(kind='tag',name='Original',aliases=['Alias']))
            b=db.save_entity(c,dict(kind='tag',name='Alias'))
            value=dict(kind='tag',name='Original',aliases=['Alias','New'],display_alias='Alias')
            with self.assertRaises(tag_policy.Conflict):tag_policy.save(c,value,a)
            self.assertEqual(self.row(c,a)['name'],'Original')
            result=tag_policy.merge(c,a,b,data=value)
            self.assertEqual(self.row(c,b)['name'],'Alias')
            self.assertEqual(self.row(c,b)['aliases'],['New','Original'])
            features.undo(c,result['history_id'],True)
            self.assertEqual(self.row(c,a)['name'],'Original')
    def test_attribute_replacement_and_frequency_match_old_aliases(self):
        with db.transaction() as c:
            a=db.save_entity(c,dict(kind='tag',name='Original',aliases=['別名']))
            b=db.save_entity(c,dict(kind='tag',name='Original',gender='female'))
            tag_policy.save(c,dict(kind='tag',name='別名',aliases=['Original']),a)
            item=self.row(c,a)
            choices=tag_policy.attribute_matches(c,dict(item,gender='female'))
            self.assertEqual([e['id'] for e in choices],[b])
            imported=import_matching.apply_tags(c,{'tag':[{'name':'Original'}]},'neutral')
            self.assertEqual(imported['tag'][0]['id'],a)
            self.assertEqual(imported['tag'][0]['name'],'別名')
    def test_author_primary_collision_requires_confirmation_and_reversible_merge(self):
        with db.transaction() as c:
            source=self.legacy(c,'Original Author','別名作者','author')
            target=db.save_entity(c,dict(kind='author',name='別名作者'))
            work=db.save_work(c,dict(title='Example',author=[{'id':source}]))
            value=dict(self.row(c,source),name='別名作者',aliases=['Original Author'],display_alias='')
            with self.assertRaises(tag_policy.Conflict) as caught:tag_policy.save(c,value,source)
            self.assertEqual(caught.exception.conflicts[0]['choices'][0]['id'],target)
            self.assertEqual(self.row(c,source)['name'],'Original Author')
            result=tag_policy.merge(c,source,target,data=value)
            self.assertEqual(self.row(c,target)['aliases'],['Original Author'])
            self.assertEqual(db.get_work(c,work['id'])['author'][0]['id'],target)
            features.undo(c,result['history_id'],True)
            self.assertEqual(db.get_work(c,work['id'])['author'][0]['id'],source)
    def test_migration_swaps_names_preserves_trash_and_runs_once(self):
        with db.transaction() as c:
            a=self.legacy(c,'Original','Alias');b=self.legacy(c,'Alias','Original')
            work=db.save_work(c,{'title':'Trash','tag':[{'id':a},{'id':b}]});features.trash(c,work['id'])
            before=c.execute('SELECT count(*) FROM work_entities').fetchone()[0]
            created=self.row(c,a)['created']
            c.execute('DELETE FROM migrations WHERE version=14');primary_names.migrate(c)
            self.assertEqual(self.row(c,a)['name'],'Alias');self.assertEqual(self.row(c,b)['name'],'Original')
            self.assertEqual(self.row(c,a)['aliases'],['Original']);self.assertEqual(self.row(c,b)['aliases'],['Alias'])
            self.assertEqual(self.row(c,a)['sort_reading'],'reading');self.assertEqual(self.row(c,a)['created'],created)
            self.assertEqual(c.execute('SELECT count(*) FROM work_entities').fetchone()[0],before)
            self.assertEqual({t['id'] for t in db.get_work(c,work['id'],include_deleted=True)['tag']},{a,b})
            primary_names.migrate(c);self.assertEqual(self.row(c,a)['name'],'Alias')
    def test_migration_defers_conflicts_and_blocked_chains_without_merging(self):
        with db.transaction() as c:
            a=self.legacy(c,'A','Taken');b=self.legacy(c,'B','Taken');z=self.legacy(c,'Z','A')
            ok=self.legacy(c,'Safe','Chosen','author')
            c.execute('DELETE FROM migrations WHERE version=14');primary_names.migrate(c)
            for ident in (a,b,z):self.assertTrue(self.row(c,ident)['primary_name_pending'])
            self.assertEqual(self.row(c,a)['display_name'],'Taken')
            self.assertEqual(self.row(c,a)['aliases'],['A'])
            self.assertEqual(self.row(c,ok)['name'],'Chosen');self.assertEqual(self.row(c,ok)['aliases'],['Safe'])
            self.assertEqual(c.execute('SELECT count(*) FROM entities').fetchone()[0],4)
            with self.assertRaises(tag_policy.Conflict):tag_policy.save(c,dict(self.row(c,a),name='Taken',display_alias=''),a)
            # An explicit alternative primary name resolves a deferred record.
            tag_policy.save(c,dict(self.row(c,a),name='Unique',display_alias=''),a)
            self.assertFalse(self.row(c,a)['primary_name_pending'])


if __name__=='__main__':unittest.main(verbosity=2)
