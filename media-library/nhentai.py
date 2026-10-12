"""Official API v2 adapter; fixed public TLS host, bounded JSON, paced reads only."""
import http.client
import contextvars
import ipaddress
import json
import re
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit, urlencode
import nhentai_credentials as credentials

HOST = 'nhentai.net'
IMAGE_HOSTS = {'t.nhentai.net', 't1.nhentai.net', 't2.nhentai.net', 't3.nhentai.net'}
MAX_JSON = 8 * 1024 * 1024
_lock = threading.Lock()
_next = {'favorites': 0, 'details': 0}
CANCEL = contextvars.ContextVar('nhentai_cancel', default=lambda:False)

class ApiError(ValueError):
    def __init__(self, status, retry_after=0):
        self.status, self.retry_after = status, retry_after
        message = {401:'nhentai API key was rejected; reconnect in Imports',403:'nhentai access was refused; check your API key or try later',404:'nhentai gallery was not found',429:'nhentai rate limit reached; waiting before retry'}.get(status, f'nhentai source returned HTTP {status}')
        super().__init__(message)

class Cancelled(ValueError): pass

def location(value):
    try:
        u = urlsplit(value)
        if u.scheme not in ('http','https') or u.hostname not in ('nhentai.net','www.nhentai.net') or u.port not in (None,80,443) or u.username or u.password: return None
        m = re.fullmatch(r'/g/([1-9][0-9]{0,11})(?:/([1-9][0-9]{0,7}))?/?',u.path)
        return (str(int(m[1])), int(m[2]) if m[2] else None) if m else None
    except (ValueError, TypeError): return None

def image_url(path):
    path = str(path or '').lstrip('/')
    if not re.fullmatch(r'galleries/[0-9]{1,15}/(?:cover|thumb|[1-9][0-9]{0,7}t)\.(?:jpg|png|webp|avif)', path):
        raise ValueError('nhentai image path is unsupported')
    return 'https://t.nhentai.net/' + path

def valid_image(value):
    try:
        u = urlsplit(value)
        return u.scheme == 'https' and u.hostname in IMAGE_HOSTS and u.port in (None,443) and not (u.username or u.password or u.query or u.fragment) and image_url(u.path).endswith(u.path)
    except (ValueError, TypeError): return False

def request(path, key=None, cancelled=None):
    cancelled = cancelled or CANCEL.get()
    if not re.fullmatch(r'/api/v2/(?:galleries/[1-9][0-9]{0,11}|favorites(?:\?[^\r\n]*)?)',path): raise ValueError('Unsupported nhentai API path')
    key = credentials.get() if key is None else key
    group = 'favorites' if path.startswith('/api/v2/favorites') else 'details'
    if group == 'favorites' and not key: raise ApiError(401)
    interval = 4.2 if group == 'favorites' else 1.5 if key else 3.2
    # Reservations are shared by interactive requests and jobs in this process.
    with _lock:
        now = time.monotonic(); target = max(now, _next[group]); _next[group] = target + interval
    while time.monotonic() < target:
        if cancelled(): raise Cancelled('Import paused or cancelled')
        time.sleep(min(.2, max(0,target-time.monotonic())))
    if cancelled(): raise Cancelled('Import paused or cancelled')
    addresses = socket.getaddrinfo(HOST,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses): raise ValueError('nhentai host does not resolve to public addresses')
    family,kind,proto,_,address = addresses[0]
    raw = socket.socket(family,kind,proto); raw.settimeout(20)
    connection = http.client.HTTPSConnection(HOST,timeout=20)
    timer = None
    try:
        raw.connect(address)
        tls = ssl.create_default_context().wrap_socket(raw,server_hostname=HOST)
        connection.sock = tls
        def expire():
            try: tls.shutdown(socket.SHUT_RDWR)
            except OSError: pass
        timer = threading.Timer(25, expire); timer.daemon = True; timer.start()
        headers = {'User-Agent':'Folio/2.0 (https://github.com/Kaijanaitubu/folio)', 'Accept':'application/json'}
        if key: headers['Authorization'] = 'Key ' + credentials.validate(key)
        connection.request('GET',path,headers=headers)
        response = connection.getresponse()
        if response.status != 200:
            retry = response.getheader('Retry-After') or ''
            delay = min(3600,max(5,int(retry))) if retry.isdigit() else 65
            if response.status == 429:
                with _lock: _next[group] = max(_next[group],time.monotonic()+delay)
            raise ApiError(response.status,delay)
        if 'application/json' not in (response.getheader('Content-Type') or ''): raise ValueError('nhentai did not return JSON metadata')
        data = response.read(MAX_JSON+1)
        if len(data) > MAX_JSON: raise ValueError('nhentai metadata exceeds 8 MB')
        result = json.loads(data)
        if not isinstance(result,dict): raise ValueError('nhentai returned invalid metadata')
        return result
    except (OSError,http.client.HTTPException) as e:
        raise ValueError('nhentai request timed out or could not connect') from e
    finally:
        if timer: timer.cancel()
        connection.close(); raw.close()

def favorites(page=1, query='', key=None, cancelled=lambda:False):
    if type(page) != int or not 1 <= page <= 100000: raise ValueError('Invalid Favorites page')
    result = request('/api/v2/favorites?' + urlencode({'page':page, 'q':str(query)[:1000]}), key, cancelled)
    items, pages = result.get('result'), result.get('num_pages')
    if not isinstance(items,list) or len(items)>1000 or type(pages)!=int or not 0 <= pages <= 100000: raise ValueError('nhentai returned invalid Favorites pagination')
    if any(not isinstance(i,dict) or type(i.get('id'))!=int or not 0<i['id']<10**12 for i in items): raise ValueError('nhentai returned invalid Favorites IDs')
    return {'items':[{'url':f'https://nhentai.net/g/{i["id"]}/','title':i.get('japanese_title') or i.get('english_title') or '', 'id':i['id']} for i in items], 'num_pages':pages, 'total':result.get('total') if type(result.get('total'))==int else None}

def parse_gallery(data, page=None):
    titles = data.get('title') or {}
    if not isinstance(titles,dict): raise ValueError('nhentai returned invalid titles')
    originals = list(dict.fromkeys(str(titles.get(k) or '').strip() for k in ('japanese','english','pretty') if str(titles.get(k) or '').strip()))
    out = {'title':originals[0] if originals else '', 'source_titles':originals, 'author':[], 'circle':[], 'series':[], 'character':[], 'tag':[], 'category':'', 'language':'', 'pages':data.get('num_pages'), 'cover':'', 'warnings':[]}
    if type(out['pages'])!=int or not 0<=out['pages']<=100000: raise ValueError('nhentai returned invalid page count')
    mapping = {'artist':'author','group':'circle','parody':'series','character':'character','tag':'tag'}
    categories = {'manga':'manga','doujinshi':'doujinshi','artistcg':'artist cg','gamecg':'game cg','imageset':'image set','anime':'anime'}
    for tag in data.get('tags') or []:
        if not isinstance(tag,dict): continue
        name,kind = str(tag.get('name') or '').strip(), tag.get('type')
        if not name: continue
        if kind in mapping: out[mapping[kind]].append({'name':name,'gender':'neutral'})
        elif kind=='category':
            category = categories.get(name.casefold().replace(' ',''))
            if category: out['category']=category
            else: out['warnings'].append('Unrecognized source category: '+name)
        elif kind=='language' and name.casefold() not in ('translated','rewrite'): out['language']=name
    path = (data.get('cover') or {}).get('path','')
    if page is not None:
        selected = next((p for p in data.get('pages',[]) if p.get('number')==page),None)
        if selected: path=selected.get('thumbnail') or path
        else: out['warnings'].append('Linked page is unavailable; using the cover')
    try: out['cover'] = image_url(path)
    except ValueError: out['warnings'].append('Cover URL unavailable; other metadata was retrieved')
    if not out['title']: out['warnings'].append('No title was retrieved')
    return out

def import_url(value, cancelled=None):
    parsed = location(value)
    if not parsed: raise ValueError('Use a nhentai gallery or page URL')
    data = request('/api/v2/galleries/'+parsed[0],cancelled=cancelled)
    if data.get('id') != int(parsed[0]): raise ValueError('nhentai returned a different gallery')
    return parse_gallery(data, parsed[1])
