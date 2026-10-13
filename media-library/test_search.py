"""Search semantics and bounded dictionary work, using disposable libraries."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import db
import features


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_path = db.PATH
        db.PATH = Path(self.temp.name) / 'library.sqlite3'
        db.init()

    def tearDown(self):
        db.PATH = self.old_path
        self.temp.cleanup()

    def fixture(self, c):
        did = db.save_dimension(c, {'name': 'Quality', 'maximum': 5, 'symbol': 'Star'})
        a = db.save_work(c, {
            'title': 'First', 'author': [{'name': 'Alice', 'aliases': ['A. Smith']}],
            'circle': [{'name': 'Blue', 'aliases': ['青いサークル']}],
            'tag': [{'name': 'Same', 'gender': 'female', 'aliases': ['F Alias']},
                    {'name': 'Same', 'gender': 'neutral'}],
            'series': [{'name': 'Saga', 'aliases': ['物語']}],
            'character': [{'name': 'Hero', 'aliases': ['主人公']}],
            'ratings': {did: 5}, 'pages': 50,
        })
        b = db.save_work(c, {'title': 'Second', 'author': ['Bob'],
                            'tag': [{'name': 'Same', 'gender': 'female'}],
                            'ratings': {did: 4}})
        d = db.save_work(c, {'title': 'Third', 'author': ['Straße'],
                            'tag': [{'name': 'Same', 'gender': 'male'}],
                            'ratings': {did: 2}})
        e = db.save_work(c, {'title': 'Fourth', 'language': '日本語', 'category': 'manga',
                            'bought': True, 'review': 'hiddenword'})
        f = db.save_work(c, {'title': 'Empty'})
        trash = db.save_work(c, {'title': 'Trashed', 'author': ['Alice'],
                                'tag': [{'name': 'Same', 'gender': 'female'}]})
        features.trash(c, trash['id'])
        return a, b, d, e, f

    def test_metadata_aliases_attributes_and_boolean_semantics(self):
        with db.transaction() as c:
            a, b, d, e, f = self.fixture(c)
            cases = [
                ('author:"a. smith"', [a]), ('author:ALICE', [a]),
                ('group:青いサークル', [a]), ('circle:Blue', [a]),
                ('series:物語', [a]), ('character:主人公', [a]),
                ('female:"F Alias"', [a, b]), ('tag:Same', [a, b, d]),
                ('none:Same', [a]), ('neutral:Same', [a]), ('male:Same', [d]),
                ('tag:F', []), ('"F Ali"', [a, b]), ('STRASSE', [d]),
                ('same', [a, b, d]), ('-tag:Same', [e, f]),
                ('-none:Same', [b, d, e, f]), ('-tag:missing', [a, b, d, e, f]),
                ('author:Alice/author:Bob rating1:>=4', [a, b]),
                ('female:Same/male:Same -author:Bob', [a, d]),
                ('-female:Same/male:Same rating1:>=2', [d]),
                ('-rating1:>=4 -tag:missing', [d, e, f]),
                ('-pages:>=50', [b, d, e, f]),
                ('漫画', [e]), ('category:漫画 language:日本語 bought:yes', [e]),
                ('hiddenword', []), ('review:hiddenword', [e]),
                ("tag:\"Same' OR 1=1 --\"", []),
            ]
            for query, expected in cases:
                with self.subTest(query=query):
                    result = db.list_works(c, query)
                    ids = {w['id'] for w in expected}
                    self.assertEqual(result['total'], len(ids))
                    self.assertEqual({w['id'] for w in result['items']}, ids)
                    self.assertEqual(set(features.batch_targets(c, {'all': True, 'query': query})), ids)

    def test_owner_scoping_including_alias_candidates(self):
        with db.transaction() as c:
            a, *_ = self.fixture(c)
            c.execute("INSERT INTO owners(id) VALUES('other')")
            c.execute("INSERT INTO entities(id,owner,kind,name,gender) VALUES('foreign-tag','other','tag','Ghost','neutral')")
            c.execute("INSERT INTO aliases VALUES('foreign-tag','Foreign alias')")
            c.execute("INSERT INTO works(id,owner,title,created,updated) VALUES('foreign-work','other','Foreign work',?,?)", (db.now(), db.now()))
            c.execute("INSERT INTO work_entities VALUES('foreign-work','foreign-tag')")
            # Even an inconsistent cross-owner association must not expose that dictionary.
            c.execute("INSERT INTO work_entities VALUES(?,'foreign-tag')", (a['id'],))
            for query in ('tag:Ghost', 'tag:"Foreign alias"', 'Foreign'):
                self.assertEqual(db.list_works(c, query)['total'], 0)
            with patch.object(db, 'OWNER', 'other'):
                for query in ('tag:Ghost', 'tag:"Foreign alias"', 'Foreign'):
                    self.assertEqual(db.list_works(c, query)['items'][0]['id'], 'foreign-work')
                    self.assertEqual(features.batch_targets(c, {'all': True, 'query': query}), ['foreign-work'])

    def test_filtered_pagination_random_and_live_metadata_changes(self):
        with db.transaction() as c:
            a, b, d, *_ = self.fixture(c)
            query = 'tag:Same'
            first = db.list_works(c, query, sort='random', seed='fixed', limit=2)
            last = db.list_works(c, query, sort='random', seed='fixed', limit=2, offset=2)
            self.assertEqual(first['total'], 3)
            self.assertEqual(last['total'], 3)
            self.assertEqual({w['id'] for w in first['items'] + last['items']}, {a['id'], b['id'], d['id']})
            self.assertEqual(first, db.list_works(c, query, sort='random', seed='fixed', limit=2))
            with patch('secrets.randbelow', return_value=2):
                single = db.list_works(c, query, random_one=True)
            self.assertEqual(single['total'], 3)
            self.assertEqual(len(single['items']), 1)
            eid = a['tag'][0]['id']
            # Each statement sees current data; candidate sets are not a stale global cache.
            c.execute("INSERT INTO aliases VALUES(?,'New alias')", (eid,))
            self.assertEqual(db.list_works(c, 'tag:"New alias"')['total'], 2)
            c.execute('DELETE FROM work_entities WHERE work_id=? AND entity_id=?', (b['id'], eid))
            self.assertEqual(db.list_works(c, 'tag:"New alias"')['total'], 1)

    def test_no_match_dictionary_work_does_not_multiply_by_work_count(self):
        with db.transaction() as c:
            stamp = db.now()
            c.executemany("INSERT INTO works(id,owner,title,created,updated) VALUES(?,'local',?,?,?)",
                          [(f'w{i}', f'Work {i}', stamp, stamp) for i in range(100)])
            c.executemany("INSERT INTO entities(id,owner,kind,name,gender) VALUES(?,'local','tag',?,'neutral')",
                          [(f'e{i}', f'Tag {i}') for i in range(600)])
            c.executemany('INSERT INTO aliases VALUES(?,?)', [(f'e{i}', f'Alias {i}') for i in range(600)])
            # Count normalization calls rather than rely on a machine-specific time limit.
            calls = 0
            def counted_fold(value):
                nonlocal calls
                calls += 1
                return (value or '').casefold()
            c.create_function('fold', 1, counted_fold, deterministic=True)
            for query in ('tag:missing', 'missing', '-tag:missing'):
                calls = 0
                result = db.list_works(c, query)
                self.assertEqual(result['total'], 100 if query.startswith('-') else 0)
                # Two statements scan metadata/aliases once each, plus free-text work fields.
                self.assertLessEqual(calls, 2 * (600 + 600) + 6 * 100)


if __name__ == '__main__':
    unittest.main()
