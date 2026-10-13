"""Bounded, volatile Hitomi thumbnail relay. No image file or database writes."""
from collections import OrderedDict
import http.client
import ipaddress
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit
import importer
import nhentai

MAX_IMAGE_BYTES = 2 * 1024 * 1024
CACHE_BYTES = 32 * 1024 * 1024
CACHE_TTL = 300
REQUEST_SECONDS = 20
SLOTS = threading.BoundedSemaphore(4)
IMAGE_HOSTS = {'atn.gold-usergeneratedcontent.net', 'btn.gold-usergeneratedcontent.net'}

class RelayError(Exception):
    pass

class MemoryCache:
    def __init__(self, limit=CACHE_BYTES, ttl=CACHE_TTL, clock=time.monotonic):
        self.limit, self.ttl, self.clock = limit, ttl, clock
        self.entries = OrderedDict()
        self.size = 0
        self.loading = {}
        self.lock = threading.Lock()

    def _prune(self):
        now = self.clock()
        for key, (expires, _, data) in list(self.entries.items()):
            if expires <= now:
                self.size -= len(data)
                del self.entries[key]

    def prune(self):
        with self.lock:
            self._prune()

    def get(self, key, loader):
        while True:
            with self.lock:
                self._prune()
                item = self.entries.get(key)
                if item:
                    self.entries.move_to_end(key)
                    return item[1], item[2]
                pending = self.loading.get(key)
                if not pending:
                    pending = {'event':threading.Event(), 'error':None, 'result':None}
                    self.loading[key] = pending
                    break
            if not pending['event'].wait(REQUEST_SECONDS + 5):
                raise RelayError('Cover request timed out')
            if pending['error']:
                raise pending['error']
            return pending['result']
        try:
            mime, data = loader()
            if len(data) > MAX_IMAGE_BYTES:
                raise RelayError('Cover exceeds the 2 MB limit')
            with self.lock:
                self._prune()
                while self.entries and self.size + len(data) > self.limit:
                    _, (_, _, old) = self.entries.popitem(last=False)
                    self.size -= len(old)
                if len(data) <= self.limit:
                    self.entries[key] = (self.clock() + self.ttl, mime, data)
                    self.size += len(data)
            pending['result'] = (mime, data)
            return mime, data
        except Exception as e:
            pending['error'] = e
            raise
        finally:
            with self.lock:
                del self.loading[key]
                pending['event'].set()

CACHE = MemoryCache()

def fetch_image(url):
    """Fetch only a canonical thumbnail on a pinned public TLS address."""
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in IMAGE_HOSTS | nhentai.IMAGE_HOSTS or parsed.username or parsed.password or parsed.port not in (None, 443) or parsed.query or parsed.fragment:
        raise RelayError('Unsupported cover host')
    # Re-validate the path without another network lookup or JS execution.
    if parsed.hostname in nhentai.IMAGE_HOSTS:
        valid_path = nhentai.valid_image(url)
    else:
        valid_path = importer.resolve_thumbnail_url(url, (0, set(), 0)).split('.net/', 1)[1] == parsed.path.lstrip('/')
    if not valid_path:
        raise RelayError('Unsupported cover path')
    deadline = time.monotonic() + REQUEST_SECONDS
    addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise RelayError('Cover host does not resolve to public addresses')
    family, kind, proto, _, address = addresses[0]
    raw = socket.socket(family, kind, proto)
    connection = http.client.HTTPSConnection(parsed.hostname, timeout=REQUEST_SECONDS)
    deadline_timer = None
    def remaining_time():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RelayError('Cover request timed out')
        return remaining
    try:
        raw.settimeout(remaining_time())
        raw.connect(address)
        raw.settimeout(remaining_time())
        tls = ssl.create_default_context().wrap_socket(raw, server_hostname=parsed.hostname)
        connection.sock = tls
        tls.settimeout(remaining_time())
        def expire_socket():
            # Also interrupt slowly trickling HTTP headers/body, not only idle reads.
            try: tls.shutdown(socket.SHUT_RDWR)
            except OSError: pass
        deadline_timer = threading.Timer(remaining_time(), expire_socket)
        deadline_timer.daemon = True
        deadline_timer.start()
        connection.request('GET', parsed.path, headers={'User-Agent':'PersonalMediaLibrary/2.0', 'Referer':'https://nhentai.net/' if parsed.hostname in nhentai.IMAGE_HOSTS else 'https://hitomi.la/', 'Accept':'image/webp,image/avif,image/jpeg,image/png'})
        tls.settimeout(remaining_time())
        response = connection.getresponse()
        if response.status != 200:
            raise RelayError(f'Cover source returned HTTP {response.status}')
        mime = (response.getheader('Content-Type') or '').split(';')[0].strip().lower()
        expected = {'.webp':'image/webp', '.avif':'image/avif', '.jpg':'image/jpeg', '.jpeg':'image/jpeg', '.png':'image/png', '.gif':'image/gif'}
        extension = '.' + parsed.path.rsplit('.', 1)[-1]
        # nhentai negotiates WebP even for saved .jpg/.png paths. Validate
        # the actual MIME and signature below, rather than the filename suffix.
        if mime not in expected.values() or (parsed.hostname not in nhentai.IMAGE_HOSTS and mime != expected.get(extension)):
            raise RelayError('Cover source did not return the expected image format')
        declared = response.getheader('Content-Length')
        if declared is not None and (int(declared) < 0 or int(declared) > MAX_IMAGE_BYTES):
            raise RelayError('Cover exceeds the 2 MB limit')
        buffer = bytearray()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RelayError('Cover request timed out')
            tls.settimeout(remaining)
            chunk = response.read1(min(65536, MAX_IMAGE_BYTES + 1 - len(buffer)))
            if not chunk:
                break
            buffer.extend(chunk)
            if len(buffer) > MAX_IMAGE_BYTES:
                raise RelayError('Cover exceeds the 2 MB limit')
        if declared is not None and len(buffer) != int(declared):
            raise RelayError('Cover response was incomplete')
        valid = (mime == 'image/webp' and buffer[:4] == b'RIFF' and buffer[8:12] == b'WEBP') or (mime == 'image/jpeg' and buffer[:3] == b'\xff\xd8\xff') or (mime == 'image/avif' and buffer[4:8] == b'ftyp' and (b'avif' in buffer[8:64] or b'avis' in buffer[8:64]))
        valid = valid or (mime == 'image/png' and buffer[:8] == b'\x89PNG\r\n\x1a\n')
        valid = valid or (mime == 'image/gif' and buffer[:6] in (b'GIF87a',b'GIF89a'))
        if not valid:
            raise RelayError('Cover response is not a supported image')
        return mime, bytes(buffer)
    except (OSError, http.client.HTTPException, ValueError) as e:
        raise RelayError('Cover source could not be reached or returned invalid data') from e
    finally:
        if deadline_timer is not None:
            deadline_timer.cancel()
        connection.close()
        raw.close()

def load(saved_url):
    # The endpoint reads a saved work's URL, never accepts a client-supplied target.
    if nhentai.valid_image(saved_url):
        return CACHE.get(saved_url, lambda: fetch_image(saved_url))
    url = importer.resolve_thumbnail_url(saved_url)
    return CACHE.get(url, lambda: fetch_image(url))
