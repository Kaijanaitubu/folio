"""Volatile cache, upstream response validation, and public-address pinning."""
from concurrent.futures import ThreadPoolExecutor
import io
import socket
import threading
import unittest
from unittest.mock import Mock, patch
import cover_relay as relay

HASH = '0' * 61 + '123'
URL = 'https://atn.gold-usergeneratedcontent.net/webpbigtn/3/12/' + HASH + '.webp'
IMAGE = b'RIFF' + b'\x10\x00\x00\x00' + b'WEBP' + b'volatile-test-payload'
SMALL_URL = URL.replace('/webpbigtn/', '/webpsmalltn/')
READER_URL = 'https://w1.gold-usergeneratedcontent.net/1791817202/786/' + HASH + '.webp'

class ReaderCoverTests(unittest.TestCase):
    def test_live_routing_shape_and_hash_shard(self):
        source = "gg = { m: function(g) { var o = 1; switch(g) { case 786: o = 0; break; } return o; }, s: function(h) { var m = /(..)(.)$/.exec(h); return parseInt(m[2]+m[1], 16).toString(10); }, b: '1791817202/' };"
        with patch('cover_relay._reader_routes', None), patch('cover_relay.importer.fetch', return_value=source) as fetch:
            self.assertEqual(relay.reader_image_url(HASH), READER_URL)
            self.assertEqual(relay.reader_image_url(HASH), READER_URL)
            fetch.assert_called_once_with('/gg.js')
        self.assertTrue(relay.valid_reader_path('/1791817202/786/' + HASH + '.webp'))
        self.assertFalse(relay.valid_reader_path('/1791817202/787/' + HASH + '.webp'))
        with patch('cover_relay._reader_routes', None), patch('cover_relay.importer.fetch', return_value=source.replace('16).toString(10)', '8).toString(10)')):
            with self.assertRaises(relay.RelayError): relay.reader_image_url(HASH)

    def test_existing_interior_url_uses_high_resolution_and_cache(self):
        with patch('cover_relay.CACHE', relay.MemoryCache()), patch('cover_relay.importer.thumbnail_routes', return_value=(0,set(),0)), patch('cover_relay.reader_image_url', return_value=READER_URL), patch('cover_relay.cover_resize.thumbnail', side_effect=lambda mime, data: (mime, data)), patch('cover_relay.fetch_image', return_value=('image/webp',IMAGE)) as fetch:
            self.assertEqual(relay.load(SMALL_URL)[1], IMAGE)
            self.assertEqual(relay.load(SMALL_URL)[1], IMAGE)
            fetch.assert_called_once_with(READER_URL)

    def test_failed_upgrade_falls_back_and_does_not_retry_every_view(self):
        with patch('cover_relay.CACHE', relay.MemoryCache()), patch('cover_relay.importer.thumbnail_routes', return_value=(0,set(),0)), patch('cover_relay.reader_image_url', return_value=READER_URL), patch('cover_relay.fetch_image', side_effect=[relay.RelayError('Unavailable'), ('image/webp',IMAGE)]) as fetch:
            self.assertEqual(relay.load(SMALL_URL)[1], IMAGE)
            self.assertEqual(relay.load(SMALL_URL)[1], IMAGE)
            self.assertEqual([c.args[0] for c in fetch.call_args_list], [READER_URL, SMALL_URL])
        with patch('cover_relay.CACHE', relay.MemoryCache()), patch('cover_relay.importer.thumbnail_routes', return_value=(0,set(),0)), patch('cover_relay.reader_image_url', side_effect=ValueError('Source changed')), patch('cover_relay.fetch_image', return_value=('image/webp',IMAGE)) as fetch:
            relay.load(SMALL_URL)
            fetch.assert_called_once_with(SMALL_URL)

    def test_regular_cover_stays_on_large_thumbnail(self):
        with patch('cover_relay.CACHE', relay.MemoryCache()), patch('cover_relay.importer.thumbnail_routes', return_value=(0,set(),0)), patch('cover_relay.reader_image_url') as reader, patch('cover_relay.fetch_image', return_value=('image/webp',IMAGE)) as fetch:
            relay.load(URL)
            reader.assert_not_called()
            fetch.assert_called_once_with(URL)

class CacheTests(unittest.TestCase):
    def test_lru_budget_and_expiry(self):
        now = [0]
        cache = relay.MemoryCache(limit=8, ttl=5, clock=lambda:now[0])
        loader = Mock(return_value=('image/webp',b'abcd'))
        cache.get('a',loader); cache.get('b',loader); cache.get('a',loader); cache.get('c',loader)
        self.assertEqual(list(cache.entries),['a','c']); self.assertEqual(cache.size,8)
        self.assertEqual(loader.call_count,3)
        now[0] = 5; cache.prune()
        self.assertEqual(cache.size,0); self.assertEqual(cache.entries,{})
        cache.get('a',loader); self.assertEqual(loader.call_count,4)
    def test_oversized_items_not_retained_and_restart_empty(self):
        cache = relay.MemoryCache(limit=2)
        self.assertEqual(cache.get('a',lambda:('image/webp',b'abc'))[1],b'abc')
        self.assertEqual(cache.size,0)
        with self.assertRaises(relay.RelayError):
            cache.get('large',lambda:('image/webp',b'x'*(relay.MAX_IMAGE_BYTES+1)))
        self.assertFalse(cache.loading)
        self.assertEqual(relay.MemoryCache().size,0)
    def test_concurrent_requests_share_fetch(self):
        cache = relay.MemoryCache(); entered=threading.Event(); release=threading.Event()
        def loader():
            entered.set(); self.assertTrue(release.wait(3)); return 'image/webp',IMAGE
        with ThreadPoolExecutor(max_workers=4) as pool:
            first=pool.submit(cache.get,'cover',loader); self.assertTrue(entered.wait(3))
            loader2=Mock(side_effect=AssertionError('Duplicate network fetch'))
            other=[pool.submit(cache.get,'cover',loader2) for _ in range(3)]
            release.set()
            self.assertEqual(first.result()[1],IMAGE)
            self.assertTrue(all(f.result()[1]==IMAGE for f in other)); loader2.assert_not_called()
    def test_failures_release_waiters_without_cache_entries(self):
        cache=relay.MemoryCache()
        with self.assertRaises(relay.RelayError): cache.get('bad',lambda:(_ for _ in ()).throw(relay.RelayError('Unavailable')))
        self.assertFalse(cache.entries); self.assertFalse(cache.loading)
        self.assertEqual(cache.get('bad',lambda:('image/webp',IMAGE))[1],IMAGE)

class FetchTests(unittest.TestCase):
    def fetch(self,body=IMAGE,status=200,mime='image/webp',declared='auto',url=URL):
        response=Mock(); response.status=status
        headers={'Content-Type':mime,'Content-Length':str(len(body)) if declared=='auto' else declared}
        response.getheader.side_effect=lambda name:headers.get(name)
        response.read1.side_effect=io.BytesIO(body).read1
        sock=Mock(); tls=Mock(); connection=Mock(); connection.getresponse.return_value=response
        address=(socket.AF_INET,socket.SOCK_STREAM,6,'',('8.8.8.8',443))
        with patch('cover_relay.socket.getaddrinfo',return_value=[address]),patch('cover_relay.socket.socket',return_value=sock),patch('cover_relay.ssl.create_default_context') as context,patch('cover_relay.http.client.HTTPSConnection',return_value=connection):
            context.return_value.wrap_socket.return_value=tls
            result=relay.fetch_image(url)
            sock.connect.assert_called_once_with(('8.8.8.8',443))
            self.assertEqual(connection.request.call_args.kwargs['headers']['Referer'],'https://hitomi.la/')
            connection.close.assert_called_once(); sock.close.assert_called_once()
            return result
    def test_binary_response_and_pinned_socket(self):
        self.assertEqual(self.fetch(),('image/webp',IMAGE))
        self.assertEqual(self.fetch(url=READER_URL),('image/webp',IMAGE))
    def test_redirect_mime_and_signature_rejected(self):
        for kwargs in ({'status':302},{'mime':'text/html'},{'body':b'not an image'}):
            with self.subTest(kwargs=kwargs),self.assertRaises(relay.RelayError): self.fetch(**kwargs)
    def test_declared_and_chunked_size_and_truncation_limits(self):
        for kwargs in ({'declared':str(relay.MAX_IMAGE_BYTES+1)},{'declared':'bad'},{'declared':str(len(IMAGE)+1)}):
            with self.subTest(kwargs=kwargs),self.assertRaises(relay.RelayError): self.fetch(**kwargs)
        with self.assertRaisesRegex(relay.RelayError,'2 MB'):
            self.fetch(body=IMAGE+b'x'*(relay.MAX_IMAGE_BYTES-len(IMAGE)+1),declared=None)
        self.assertEqual(self.fetch(declared=None)[1],IMAGE)
    def test_private_dns_and_unapproved_targets_rejected(self):
        with patch('cover_relay.socket.getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',443))]),patch('cover_relay.socket.socket') as sock:
            with self.assertRaises(relay.RelayError): relay.fetch_image(URL)
            sock.assert_not_called()
        with patch('cover_relay.socket.getaddrinfo') as dns:
            for url in ('https://example.org/a.webp','http://127.0.0.1/private',URL+'?target=private',URL.replace('atn.','user@atn.'), READER_URL.replace('w1.', 'w3.'), READER_URL.replace('/786/', '/787/'), READER_URL+'?target=private', READER_URL.replace('/1791817202/', '/../'), READER_URL.replace('.webp', '.jpg')):
                with self.subTest(url=url),self.assertRaises(relay.RelayError): relay.fetch_image(url)
            dns.assert_not_called()

if __name__=='__main__':unittest.main(verbosity=2)
