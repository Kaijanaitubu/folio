"""Public-metadata fixtures, HTTP integration and URL/transport boundaries."""
import copy
import json
import unittest
from unittest.mock import Mock, patch
import cover_relay
import cover_sources
import db
import importer
import import_jobs
import pixiv
import test_pawchive as fixtures

URL = 'https://www.pixiv.net/artworks/123'
FANBOX = 'https://example-author.fanbox.cc/posts/456'
IMAGE = 'https://i.pximg.net/c/250x250_80_a2/img-master/img/2026/10/16/00/00/00/123_p0_master1200.jpg'
FAN_IMAGE = 'https://pixiv.pximg.net/c/1200x630_90_a2_g5/fanbox/public/images/post/456/cover/abc.jpeg'
POST = {'id': '123', 'title': '日本語タイトル', 'userName': '作者', 'tags': {'tags': [{'tag': 'digital'}, {'tag': '漫画'}, {'tag': 'digital'}]}, 'urls': {'regular': None}, 'userIllusts': {'123': {'id': '123', 'url': IMAGE}, '124': {'id': '124', 'url': IMAGE.replace('123_', '124_')}}}
FAN_POST = {'post': {'id': '456', 'title': 'FANBOX投稿', 'user': {'name': '作者'}, 'tags': ['digital'], 'coverImageUrl': FAN_IMAGE, 'isRestricted': True, 'body': None}}


class AdapterTests(unittest.TestCase):
    def test_url_variants_and_untrusted_destinations(self):
        for value in (URL, URL.replace('/artworks/', '/en/artworks/') + '?utm_source=test#x', 'http://pixiv.net/member_illust.php?mode=medium&illust_id=123'):
            self.assertEqual(pixiv.location(value), ('pixiv', '123'))
            self.assertEqual(db.normalize_url(value), URL)
        for value in (FANBOX, 'https://www.fanbox.cc/@example-author/posts/456?utm_source=test', 'https://www.fanbox.cc/posts/456'):
            self.assertEqual(pixiv.location(value), ('fanbox', '456'))
            self.assertEqual(db.normalize_url(value), 'https://www.fanbox.cc/posts/456')
        for value in ('https://pixiv.net.evil/artworks/123', 'https://evil.fanbox.cc.evil/posts/456', 'https://user@www.pixiv.net/artworks/123', URL.replace('net/', 'net:444/'), 'https://www.pixiv.net/novel/show.php?id=123', URL.replace('/123', '/0'), 'https://www.fanbox.cc/@author', 'https://www.pixiv.net/member_illust.php?illust_id=123&illust_id=456'):
            self.assertIsNone(pixiv.location(value), value)

    def test_four_fields_and_no_neighbor_cover(self):
        out = pixiv.parse_post(POST, ('pixiv', '123'))
        self.assertEqual(out['title'], POST['title']); self.assertEqual(out['cover'], IMAGE)
        self.assertEqual(out['author'], [{'name': '作者'}]); self.assertEqual([t['name'] for t in out['tag']], ['digital', '漫画'])
        self.assertTrue(all(t['gender'] == 'neutral' for t in out['tag']))
        changed = copy.deepcopy(POST); changed['userIllusts'].pop('123')
        self.assertEqual(pixiv.parse_post(changed, ('pixiv', '123'))['cover'], '')
        changed = copy.deepcopy(POST); changed['userIllusts']['123']['id'] = '124'
        self.assertEqual(pixiv.parse_post(changed, ('pixiv', '123'))['cover'], '')
        with self.assertRaisesRegex(ValueError, 'different post'): pixiv.parse_post(POST, ('pixiv', '124'))

    def test_restricted_fanbox_uses_public_fields_only_and_old_response(self):
        for post in (FAN_POST, FAN_POST['post']):
            out = pixiv.parse_post(post, ('fanbox', '456'))
            self.assertEqual(out['title'], 'FANBOX投稿'); self.assertEqual(out['cover'], FAN_IMAGE)
            self.assertEqual(out['source_label'], 'FANBOX'); self.assertTrue(out['warnings'])
        changed = copy.deepcopy(FAN_POST); changed['post']['coverImageUrl'] = FAN_IMAGE.replace('/public/', '/restricted/')
        self.assertEqual(pixiv.parse_post(changed, ('fanbox', '456'))['cover'], '')

    def test_fixed_fetch_targets(self):
        with patch('pixiv.fetch_json', return_value=POST) as fetch:
            self.assertEqual(importer.import_url(URL)['source_label'], 'Pixiv')
            fetch.assert_called_once_with('https://www.pixiv.net/ajax/illust/123?lang=ja')
        with patch('pixiv.fetch_json', return_value=FAN_POST) as fetch:
            importer.import_url(FANBOX + '?x=1')
            fetch.assert_called_once_with('https://api.fanbox.cc/post.info?postId=456')
        self.assertTrue(importer.attribute_less_source(FANBOX)); self.assertTrue(importer.attribute_less_source(URL))

    def test_image_hosts_paths_and_ram_cache(self):
        self.assertTrue(pixiv.valid_image(IMAGE)); self.assertTrue(pixiv.valid_image(FAN_IMAGE))
        for image in (IMAGE + '?x=1', IMAGE.replace('i.pximg.net', 'i.pximg.net.evil'), FAN_IMAGE.replace('/public/', '/restricted/'), 'https://i.pximg.net/user-profile/icon.jpg', 'https://user@i.pximg.net' + IMAGE.split('net')[1]):
            self.assertFalse(pixiv.valid_image(image), image)
        with patch.object(cover_relay, 'CACHE', cover_relay.MemoryCache()), patch('pixiv.fetch_image', return_value=('image/jpeg', b'jpeg')) as fetch:
            cover_sources.load(IMAGE); cover_sources.load(IMAGE); fetch.assert_called_once()
        with patch('pixiv.request', return_value=('image/jpeg', b'<html>')):
            with self.assertRaises(ValueError): pixiv.fetch_image(IMAGE)

    def test_nonpublic_addresses_and_invalid_fetch_paths_never_connect(self):
        with patch('pixiv.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 443))]), patch('pixiv.socket.socket') as sock:
            with self.assertRaises(ValueError): pixiv.request('https://www.pixiv.net/ajax/illust/123?lang=ja')
            sock.assert_not_called()
        with patch('pixiv.socket.getaddrinfo') as dns:
            for url in ('https://evil.test/ajax/illust/123?lang=ja', 'https://api.fanbox.cc/post.info?postId=123&x=1', 'https://www.pixiv.net/ajax/user/123?lang=ja'):
                with self.assertRaises(ValueError): pixiv.request(url)
            dns.assert_not_called()

    def test_redirect_size_mime_error_and_cancellation(self):
        response = Mock(); response.status = 302
        conn = Mock(); conn.getresponse.return_value = response
        with patch('pixiv.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('8.8.8.8', 443))]), patch('pixiv.socket.socket'), patch('pixiv.ssl.create_default_context'), patch('pixiv.http.client.HTTPSConnection', return_value=conn):
            with self.assertRaisesRegex(ValueError, 'HTTP 302'): pixiv.request('https://api.fanbox.cc/post.info?postId=456')
            response.read1.assert_not_called()
            response.status = 200; response.getheader.side_effect = lambda name: {'Content-Type': 'application/json', 'Content-Length': str(4*1024*1024+1)}.get(name)
            with self.assertRaisesRegex(ValueError, 'size limit'): pixiv.request('https://api.fanbox.cc/post.info?postId=456')
        with patch('pixiv.request', return_value=('application/json', b'{"error":true,"body":null}')):
            with self.assertRaisesRegex(ValueError, 'unavailable'): pixiv.fetch_json('https://api.fanbox.cc/post.info?postId=456')
        token = pixiv.CANCEL.set(lambda: True)
        try:
            with patch('pixiv.request') as fetch:
                with self.assertRaisesRegex(ValueError, 'paused'): pixiv.fetch_json('https://api.fanbox.cc/post.info?postId=456')
                fetch.assert_not_called()
        finally: pixiv.CANCEL.reset(token)


class IntegrationTests(unittest.TestCase):
    setUp = fixtures.IntegrationTests.setUp
    tearDown = fixtures.IntegrationTests.tearDown
    request = fixtures.IntegrationTests.request

    def test_individual_reimport_and_fanbox_equivalent_registered_links(self):
        with patch('pixiv.fetch_json', return_value=FAN_POST):
            status, data = self.request('import', {'url': FANBOX})
            self.assertEqual(status, 200); self.assertEqual(data['source_label'], 'FANBOX')
            with db.transaction() as c:
                work = db.save_work(c, dict(data, links=[{'url': FANBOX, 'label': 'FANBOX', 'is_primary': True}]))
            variant = 'https://www.fanbox.cc/posts/456'
            self.assertEqual(self.request('source-check', {'url': variant})[1]['match'], 'exact')
            self.assertEqual(self.request('import', {'url': variant})[0], 409)
            self.assertEqual(self.request('import', {'url': variant, 'exclude': work['id']})[0], 200)

    def test_bookmark_import_and_frequency_policy(self):
        entries = importer.bookmarks('<a href="' + URL + '">Bookmark</a><a href="' + FANBOX + '">FANBOX</a>')
        self.assertTrue(all(e['supported'] for e in entries))
        with db.transaction() as c:
            db.save_work(c, {'title': 'Existing tag', 'tag': [{'name': 'digital', 'gender': 'female'}]})
            jid = import_jobs.create(c, {'items': [entries[0]], 'title_mode': 'bookmark', 'tag_mode': 'frequency'})['id']
            item = dict(c.execute('SELECT * FROM job_items WHERE job_id=?', (jid,)).fetchone())
        with patch('pixiv.fetch_json', return_value=POST): import_jobs.process_item(item)
        with db.transaction() as c:
            row = c.execute('SELECT * FROM job_items WHERE id=?', (item['id'],)).fetchone()
            self.assertEqual(row['status'], 'added'); work = db.get_work(c, row['work_id'])
            self.assertEqual(work['title'], 'Bookmark'); self.assertEqual(work['links'][0]['label'], 'Pixiv')
            self.assertEqual(next(t for t in work['tag'] if t['name'] == 'digital')['gender'], 'female')

    def test_migration_preserves_saved_urls_and_rebuilds_claims(self):
        with db.transaction() as c:
            work = db.save_work(c, {'title': 'Original', 'review': 'Keep', 'links': [{'url': URL + '?old=1'}]})
            c.execute('UPDATE links SET url_key=? WHERE work_id=?', ('https://pixiv.net/old-key', work['id']))
            c.execute('UPDATE source_claims SET url_key=? WHERE work_id=?', ('https://pixiv.net/old-key', work['id']))
            c.execute('DELETE FROM migrations WHERE version=15')
        db.init(); db.init()
        with db.transaction() as c:
            after = db.get_work(c, work['id'])
            self.assertEqual(after['links'][0]['url'], URL + '?old=1'); self.assertEqual(after['review'], 'Keep')
            self.assertEqual(db.exact_sources(c, URL)[0]['id'], work['id'])
            self.assertIsNone(c.execute('PRAGMA foreign_key_check').fetchone())


if __name__ == '__main__': unittest.main()
