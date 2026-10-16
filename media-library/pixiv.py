"""Public Pixiv/FANBOX metadata; no login cookies, restricted media or disk images."""
import contextvars
import http.client
import ipaddress
import json
import re
import socket
import ssl
import threading
import time
from urllib.parse import parse_qs, urlsplit

ID = r'[1-9][0-9]{0,19}'
CANCEL = contextvars.ContextVar('pixiv_cancel', default=lambda: False)
_lock = threading.Lock()
_next = {}


def location(value):
    try:
        u = urlsplit(value)
        if u.scheme not in ('http', 'https') or u.port not in (None, 80, 443) or u.username is not None or u.password is not None:
            return None
        if u.hostname in ('pixiv.net', 'www.pixiv.net'):
            m = re.fullmatch(r'/(?:[a-z]{2}/)?artworks/(' + ID + r')/?', u.path)
            if m: return 'pixiv', m[1]
            if u.path == '/member_illust.php':
                values = parse_qs(u.query).get('illust_id', [])
                if len(values) == 1 and re.fullmatch(ID, values[0]): return 'pixiv', values[0]
        if u.hostname in ('fanbox.cc', 'www.fanbox.cc'):
            m = re.fullmatch(r'/(?:@[a-zA-Z0-9_-]{1,64}/)?posts/(' + ID + r')/?', u.path)
        elif re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.fanbox\.cc', u.hostname or ''):
            m = re.fullmatch(r'/posts/(' + ID + r')/?', u.path)
        else: m = None
        if m: return 'fanbox', m[1]
    except (ValueError, TypeError): pass
    return None


def canonical(value):
    loc = location(value)
    if not loc: raise ValueError('Use a Pixiv artwork or FANBOX post URL')
    return 'https://www.pixiv.net/artworks/' + loc[1] if loc[0] == 'pixiv' else 'https://www.fanbox.cc/posts/' + loc[1]


def valid_image(value):
    try:
        u = urlsplit(value)
        if u.scheme != 'https' or u.port not in (None, 443) or u.username is not None or u.password is not None or u.query or u.fragment:
            return False
        prefix = r'(?:/c/[a-zA-Z0-9_]+)?'
        if u.hostname == 'i.pximg.net':
            return bool(re.fullmatch(prefix + r'/(?:img-master|img-original|custom-thumb)/img/(?:[0-9]{2,4}/){6}[a-zA-Z0-9_-]{1,180}\.(?:jpg|jpeg|png|webp)', u.path))
        if u.hostname == 'pixiv.pximg.net':
            return bool(re.fullmatch(prefix + r'/fanbox/public/images/post/' + ID + r'/(?:cover|image)/[a-zA-Z0-9_-]{1,180}\.(?:jpg|jpeg|png|webp)', u.path))
    except (ValueError, TypeError): pass
    return False


def request(value, image=False):
    u = urlsplit(value)
    if image:
        if not valid_image(value): raise ValueError('Unsupported Pixiv image URL')
    elif not (u.scheme == 'https' and u.port in (None, 443) and u.username is None and u.password is None and not u.fragment and (
        u.hostname == 'www.pixiv.net' and re.fullmatch(r'/ajax/illust/' + ID, u.path) and u.query == 'lang=ja' or
        u.hostname == 'api.fanbox.cc' and u.path == '/post.info' and re.fullmatch('postId=' + ID, u.query))):
        raise ValueError('Unsupported Pixiv metadata URL')
    limit = 4 * 1024 * 1024
    deadline = time.monotonic() + 20
    addresses = socket.getaddrinfo(u.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('Pixiv host does not resolve to public addresses')
    family, kind, proto, _, address = addresses[0]
    raw = socket.socket(family, kind, proto)
    conn = http.client.HTTPSConnection(u.hostname, timeout=20)
    timer = None
    def remaining():
        seconds = deadline - time.monotonic()
        if seconds <= 0: raise ValueError('Pixiv request timed out')
        return seconds
    try:
        raw.settimeout(remaining()); raw.connect(address); raw.settimeout(remaining())
        tls = ssl.create_default_context().wrap_socket(raw, server_hostname=u.hostname)
        conn.sock = tls
        def expire():
            try: tls.shutdown(socket.SHUT_RDWR)
            except OSError: pass
        timer = threading.Timer(remaining(), expire); timer.daemon = True; timer.start()
        origin = 'https://www.fanbox.cc' if u.hostname in ('api.fanbox.cc', 'pixiv.pximg.net') else 'https://www.pixiv.net'
        path = u.path + ('?' + u.query if u.query else '')
        conn.request('GET', path, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'image/webp,image/jpeg,image/png' if image else 'application/json', 'Accept-Encoding': 'identity', 'Referer': origin + '/', 'Origin': origin})
        tls.settimeout(remaining()); response = conn.getresponse()
        if response.status != 200:
            if response.status in (401, 403, 404): raise ValueError('Pixiv/FANBOX post unavailable without login, deleted, or private')
            raise ValueError(f'Pixiv/FANBOX source returned HTTP {response.status}')
        mime = (response.getheader('Content-Type') or '').split(';')[0].strip().lower()
        if mime not in (('image/jpeg', 'image/png', 'image/webp') if image else ('application/json',)):
            raise ValueError('Pixiv/FANBOX returned an unexpected content type')
        declared = response.getheader('Content-Length')
        if declared is not None and not 0 <= int(declared) <= limit: raise ValueError('Pixiv/FANBOX response exceeds the size limit')
        body = bytearray()
        while True:
            if CANCEL.get()(): raise ValueError('Import paused or cancelled')
            tls.settimeout(remaining()); chunk = response.read1(min(65536, limit + 1 - len(body)))
            if not chunk: break
            body.extend(chunk)
            if len(body) > limit: raise ValueError('Pixiv/FANBOX response exceeds the size limit')
        if declared is not None and len(body) != int(declared): raise ValueError('Pixiv/FANBOX response was incomplete')
        return mime, bytes(body)
    except (OSError, http.client.HTTPException) as e:
        raise ValueError('Pixiv/FANBOX source could not be reached; try again later') from e
    finally:
        if timer: timer.cancel()
        conn.close(); raw.close()


def fetch_json(value):
    host = urlsplit(value).hostname
    with _lock:
        target = max(time.monotonic(), _next.get(host, 0)); _next[host] = target + 1
    while time.monotonic() < target:
        if CANCEL.get()(): raise ValueError('Import paused or cancelled')
        time.sleep(min(.2, max(0, target - time.monotonic())))
    if CANCEL.get()(): raise ValueError('Import paused or cancelled')
    try: data = json.loads(request(value)[1])
    except (UnicodeError, json.JSONDecodeError) as e: raise ValueError('Pixiv/FANBOX returned invalid metadata') from e
    if not isinstance(data, dict): raise ValueError('Pixiv/FANBOX returned invalid metadata')
    if data.get('error'): raise ValueError('Pixiv/FANBOX post unavailable without login, deleted, or private')
    body = data.get('body')
    if not isinstance(body, dict): raise ValueError('Pixiv/FANBOX post unavailable without login, deleted, or private')
    return body


def parse_post(data, loc):
    kind, post = loc
    if kind == 'fanbox' and isinstance(data.get('post'), dict): data = data['post']
    if str(data.get('id')) != post: raise ValueError('Pixiv/FANBOX returned a different post')
    title = data.get('title')
    if not isinstance(title, str) or not title.strip() or len(title) > 4096: raise ValueError('Pixiv/FANBOX post has no usable title')
    out = {'title': title, 'source_titles': [title], 'source_label': 'Pixiv' if kind == 'pixiv' else 'FANBOX', 'cover': '', 'category': '', 'language': '', 'pages': None, 'warnings': [], **{k: [] for k in ('author', 'circle', 'series', 'character', 'tag')}}
    if kind == 'pixiv':
        author = data.get('userName')
        tags = data.get('tags', {}).get('tags', []) if isinstance(data.get('tags'), dict) else []
        tags = [item.get('tag') for item in tags if isinstance(item, dict)] if isinstance(tags, list) else None
        urls = data.get('urls') if isinstance(data.get('urls'), dict) else {}
        candidates = [urls.get(k) for k in ('regular', 'small', 'thumb', 'mini')]
        # Anonymous responses may hide full-size URLs. Use only this post's public
        # thumbnail, never adjacent works, avatars or reconstructed original URLs.
        works = data.get('userIllusts')
        current = works.get(post) if isinstance(works, dict) else None
        if isinstance(current, dict) and str(current.get('id')) == post: candidates.append(current.get('url'))
    else:
        user = data.get('user'); author = user.get('name') if isinstance(user, dict) else None
        tags = data.get('tags', [])
        candidates = [data.get('coverImageUrl'), data.get('imageForShare')]
        if data.get('isRestricted'): out['warnings'].append('FANBOX: imported public metadata and preview only; supporter content was not accessed')
    if isinstance(author, str) and author.strip() and len(author) <= 4096: out['author'] = [{'name': author.strip()}]
    else: out['warnings'].append('Pixiv/FANBOX author name unavailable; other metadata was retrieved')
    if not isinstance(tags, list) or len(tags) > 2000 or any(not isinstance(t, str) or len(t) > 4096 for t in tags):
        raise ValueError('Pixiv/FANBOX returned invalid tags')
    out['tag'] = [{'name': t, 'gender': 'neutral'} for t in dict.fromkeys(t.strip() for t in tags if t.strip())]
    out['cover'] = next((value for value in candidates if isinstance(value, str) and valid_image(value)), '')
    if not out['cover']: out['warnings'].append('Cover URL unavailable; other metadata was retrieved')
    return out


def import_url(value):
    loc = location(value)
    if not loc: raise ValueError('Use a Pixiv artwork or FANBOX post URL')
    url = 'https://www.pixiv.net/ajax/illust/' + loc[1] + '?lang=ja' if loc[0] == 'pixiv' else 'https://api.fanbox.cc/post.info?postId=' + loc[1]
    return parse_post(fetch_json(url), loc)


def fetch_image(value):
    mime, body = request(value, image=True)
    detected = 'image/jpeg' if body[:3] == b'\xff\xd8\xff' else 'image/png' if body[:8] == b'\x89PNG\r\n\x1a\n' else 'image/webp' if body[:4] == b'RIFF' and body[8:12] == b'WEBP' else None
    if not detected: raise ValueError('Pixiv/FANBOX response is not a supported image')
    return detected, body
