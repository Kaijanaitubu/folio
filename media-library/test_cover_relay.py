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
    def fetch(self,body=IMAGE,status=200,mime='image/webp',declared='auto'):
        response=Mock(); response.status=status
        headers={'Content-Type':mime,'Content-Length':str(len(body)) if declared=='auto' else declared}
        response.getheader.side_effect=lambda name:headers.get(name)
        response.read1.side_effect=io.BytesIO(body).read1
        sock=Mock(); tls=Mock(); connection=Mock(); connection.getresponse.return_value=response
        address=(socket.AF_INET,socket.SOCK_STREAM,6,'',('8.8.8.8',443))
        with patch('cover_relay.socket.getaddrinfo',return_value=[address]),patch('cover_relay.socket.socket',return_value=sock),patch('cover_relay.ssl.create_default_context') as context,patch('cover_relay.http.client.HTTPSConnection',return_value=connection):
            context.return_value.wrap_socket.return_value=tls
            result=relay.fetch_image(URL)
            sock.connect.assert_called_once_with(('8.8.8.8',443))
            self.assertEqual(connection.request.call_args.kwargs['headers']['Referer'],'https://hitomi.la/')
            connection.close.assert_called_once(); sock.close.assert_called_once()
            return result
    def test_binary_response_and_pinned_socket(self):
        self.assertEqual(self.fetch(),('image/webp',IMAGE))
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
            for url in ('https://example.org/a.webp','http://127.0.0.1/private',URL+'?target=private',URL.replace('atn.','user@atn.')):
                with self.subTest(url=url),self.assertRaises(relay.RelayError): relay.fetch_image(url)
            dns.assert_not_called()

if __name__=='__main__':unittest.main(verbosity=2)
