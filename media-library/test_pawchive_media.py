"""Posts are eligible regardless of media; only supported cover images are read."""
import copy
import unittest
from unittest.mock import patch
import db
import import_jobs
import pawchive
import pixiv
import test_pawchive as fixtures

IMAGE = '/aa/aa/' + 'a' * 64 + '.jpg'
CASES = [[], [IMAGE], ['/clip.mp4'], [IMAGE, '/clip.webm'], ['/archive.zip'], ['/clip.mp4', '/archive.zip'], ['/unknown.xyz']]


class MediaTests(unittest.TestCase):
    def test_pawchive_accepts_all_media_without_downloading_attachments(self):
        for paths in CASES:
            with self.subTest(paths=paths), patch('pawchive.request') as request:
                data = dict(fixtures.POST, file=None, attachments=[{'path': path} for path in paths])
                out = pawchive.parse_post(data, fixtures.PROFILE, fixtures.URL)
                self.assertEqual(out['title'], data['title'])
                self.assertEqual(bool(out['cover']), IMAGE in paths)
                self.assertNotIn('media_kind', out)
                self.assertFalse(any('media type' in warning for warning in out['warnings']))
                request.assert_not_called()

    def test_fanbox_accepts_post_types_even_without_cover_or_body(self):
        for kind in ('image', 'article', 'text', 'video', 'file'):
            with self.subTest(kind=kind), patch('pixiv.request') as request:
                out = pixiv.parse_post({'post': {'id': '456', 'title': kind, 'user': {'name': 'Author'}, 'tags': [], 'type': kind, 'body': None}}, ('fanbox', '456'))
                self.assertEqual(out['title'], kind)
                self.assertEqual(out['cover'], '')
                request.assert_not_called()


class IntegrationTests(unittest.TestCase):
    setUp = fixtures.IntegrationTests.setUp
    tearDown = fixtures.IntegrationTests.tearDown
    request = fixtures.IntegrationTests.request

    def test_individual_pawchive_imports_single_image_video_mixed_and_archive(self):
        for paths in CASES:
            with self.subTest(paths=paths):
                post = dict(fixtures.POST, file=None, attachments=[{'path': path} for path in paths])
                def fetch(url): return copy.deepcopy(fixtures.PROFILE if url.endswith('/profile') else post)
                with patch('pawchive.fetch_json', side_effect=fetch):
                    status, data = self.request('import', {'url': fixtures.URL})
                self.assertEqual(status, 200)
                self.assertEqual(bool(data['cover']), IMAGE in paths)

    def test_batch_posts_are_added_instead_of_skipped(self):
        for index, paths in enumerate(CASES):
            with self.subTest(paths=paths):
                post_id = str(600 + index)
                url = 'https://pawchive.pw/fanbox/user/123/post/' + post_id
                post = dict(fixtures.POST, id=post_id, title='Media fixture ' + post_id, file=None, attachments=[{'path': path} for path in paths])
                with db.transaction() as c:
                    jid = import_jobs.create(c, {'items': [{'url': url}]})['id']
                    item = dict(c.execute('SELECT * FROM job_items WHERE job_id=?', (jid,)).fetchone())
                def fetch(url): return copy.deepcopy(fixtures.PROFILE if url.endswith('/profile') else post)
                with patch('pawchive.fetch_json', side_effect=fetch): import_jobs.process_item(item)
                with db.transaction() as c:
                    result = c.execute('SELECT * FROM job_items WHERE id=?', (item['id'],)).fetchone()
                    self.assertEqual(result['status'], 'added')
                    work = db.get_work(c, result['work_id'])
                    self.assertEqual(work['title'], post['title'])
                    self.assertEqual(bool(work['cover']), IMAGE in paths)

    def test_older_media_classification_does_not_block_batch_or_fanbox(self):
        for index, kind in enumerate(('mixed', 'uncertain', 'video')):
            with self.subTest(kind=kind):
                value = 'https://example-author.fanbox.cc/posts/' + str(900 + index)
                data = {'title': 'Old payload ' + kind, 'source_label': 'FANBOX', 'media_kind': kind, 'tag': [], 'author': [], 'cover': ''}
                with db.transaction() as c:
                    jid = import_jobs.create(c, {'items': [{'url': value}]})['id']
                    item = dict(c.execute('SELECT * FROM job_items WHERE job_id=?', (jid,)).fetchone())
                with patch('importer.import_url', return_value=data): import_jobs.process_item(item)
                with db.transaction() as c:
                    self.assertEqual(c.execute('SELECT status FROM job_items WHERE id=?', (item['id'],)).fetchone()[0], 'added')


if __name__ == '__main__': unittest.main()
