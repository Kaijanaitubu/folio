"""Metadata-only momon-ga HTML adapter. No scripts run and no images persist."""
import contextvars
import http.client
import ipaddress
import re
import socket
import ssl
import threading
import time
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin

HOST = 'momon-ga.com'
IMAGE_HOSTS = {'z2.momon-ga.me', 'z3.momon-ga.me'}
MAX_HTML = 4 * 1024 * 1024
CANCEL = contextvars.ContextVar('momonga_cancel', default=lambda: False)
_lock = threading.Lock()
_next = 0

def location(value):
    try:
        u = urlsplit(value)
        if u.scheme not in ('http', 'https') or u.hostname not in (HOST, 'www.'+HOST) or u.port not in (None, 80, 443) or u.username or u.password:
            return None
        m = re.fullmatch(r'/(fanzine|magazine)/mo([1-9][0-9]{0,11})/?', u.path)
        return (m[1], m[2]) if m else None
    except (ValueError, TypeError):
        return None

def canonical(value):
    parsed = location(value)
    if not parsed: raise ValueError('Use a momon-ga work page URL')
    return f'https://{HOST}/{parsed[0]}/mo{parsed[1]}/'

def valid_image(value):
    try:
        u = urlsplit(value)
        return (u.scheme == 'https' and u.hostname in IMAGE_HOSTS and u.port in (None,443)
                and not (u.username or u.password or u.query or u.fragment)
                and bool(re.fullmatch(r'/galleries/[1-9][0-9]{0,11}/[1-9][0-9]{0,5}\.(?:webp|jpg|jpeg|png)', u.path)))
    except (ValueError, TypeError): return False

def response(url, limit, image=False):
    """Pinned public TLS, fixed hosts/paths, no redirects, bounded total deadline."""
    u = urlsplit(url)
    if image:
        if not valid_image(url): raise ValueError('Unsupported momon-ga image URL')
    elif url != canonical(url): raise ValueError('Unsupported momon-ga metadata URL')
    deadline = time.monotonic()+20
    addresses = socket.getaddrinfo(u.hostname,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('momon-ga host does not resolve to public addresses')
    family, kind, proto, _, address = addresses[0]
    raw = socket.socket(family,kind,proto)
    conn = http.client.HTTPSConnection(u.hostname,timeout=20)
    timer = None
    def remaining():
        seconds=deadline-time.monotonic()
        if seconds<=0: raise ValueError('momon-ga request timed out')
        return seconds
    try:
        raw.settimeout(remaining()); raw.connect(address)
        raw.settimeout(remaining())
        tls=ssl.create_default_context().wrap_socket(raw,server_hostname=u.hostname)
        conn.sock=tls; tls.settimeout(remaining())
        def expire():
            try: tls.shutdown(socket.SHUT_RDWR)
            except OSError: pass
        timer=threading.Timer(remaining(),expire); timer.daemon=True; timer.start()
        conn.request('GET',u.path,headers={'User-Agent':'Mozilla/5.0', 'Accept':'image/webp,image/jpeg,image/png' if image else 'text/html', 'Accept-Encoding':'identity', 'Referer':'https://momon-ga.com/'})
        r=conn.getresponse()
        if r.status!=200: raise ValueError(f'momon-ga source returned HTTP {r.status}; try again later')
        mime=(r.getheader('Content-Type') or '').split(';')[0].strip().lower()
        if mime not in (('image/webp','image/jpeg','image/png') if image else ('text/html','application/xhtml+xml')):
            raise ValueError('momon-ga returned an unexpected content type')
        declared=r.getheader('Content-Length')
        if declared is not None and not 0<=int(declared)<=limit: raise ValueError('momon-ga response exceeds the size limit')
        body=bytearray()
        while True:
            if CANCEL.get()(): raise ValueError('Import paused or cancelled')
            tls.settimeout(remaining())
            chunk=r.read1(min(65536,limit+1-len(body)))
            if not chunk: break
            body.extend(chunk)
            if len(body)>limit: raise ValueError('momon-ga response exceeds the size limit')
        if declared is not None and len(body)!=int(declared): raise ValueError('momon-ga response was incomplete')
        return mime,bytes(body)
    except (OSError,http.client.HTTPException) as e:
        raise ValueError('momon-ga source could not be reached; try again later') from e
    finally:
        if timer: timer.cancel()
        conn.close(); raw.close()

def fetch(url):
    global _next
    with _lock:
        target=max(time.monotonic(),_next); _next=target+2
    while time.monotonic()<target:
        if CANCEL.get()(): raise ValueError('Import paused or cancelled')
        time.sleep(min(.2,max(0,target-time.monotonic())))
    if CANCEL.get()(): raise ValueError('Import paused or cancelled')
    return response(canonical(url),MAX_HTML)[1].decode('utf-8-sig')

class Page(HTMLParser):
    VOID={'img','meta','link','br','input','hr','source','wbr','area','base','embed','param'}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]; self.text=None; self.title=''; self.pages=''; self.links=[]; self.cover=''; self.fallback_title=''
    def handle_starttag(self,tag,attrs):
        a=dict(attrs); ids={entry[1] for entry in self.stack}
        if tag=='div' and a.get('class','').split().count('history') and 'post-data' in ids:
            self.fallback_title=a.get('data-title','')
        if tag=='h1' and 'post-data' in ids: self.text=['title',tag,'',len(self.stack)]
        if a.get('id')=='post-number' and 'post-data' in ids: self.text=['pages',tag,'',len(self.stack)]
        if tag=='a' and 'post-tag' in ids and a.get('rel')=='tag': self.text=[a.get('href',''),tag,'',len(self.stack)]
        if tag=='img' and 'post-hentai' in ids and not self.cover: self.cover=a.get('src','')
        if tag not in self.VOID: self.stack.append((tag,a.get('id')))
    def handle_data(self,text):
        if self.text: self.text[2]+=text
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:
                if self.text and self.text[1]==tag and self.text[3]==i:
                    key,_,value,_=self.text; value=value.strip()
                    if key=='title': self.title=value
                    elif key=='pages': self.pages=value
                    else: self.links.append((key,value))
                    self.text=None
                self.stack=self.stack[:i]; break

def parse_page(html,url):
    if len(html.encode('utf-8'))>MAX_HTML: raise ValueError('momon-ga HTML exceeds the size limit')
    loc=location(url)
    if not loc: raise ValueError('Use a momon-ga work page URL')
    p=Page(); p.feed(html)
    title=p.title or p.fallback_title
    if not title: raise ValueError('momon-ga page has no work title; source format may have changed')
    out={'title':title,'source_titles':[title],'language':'','pages':None,'category':'doujinshi' if loc[0]=='fanzine' else 'manga','cover':'','warnings':[],**{k:[] for k in ('author','circle','series','character','tag')}}
    count=re.fullmatch(r'([1-9][0-9]{0,5})\s*ページ',p.pages)
    if count: out['pages']=int(count[1])
    fields={'cartoonist':'author','group':'circle','parody':'series','character':'character','tag':'tag'}
    seen=set()
    for href,name in p.links:
        u=urlsplit(urljoin(canonical(url),href)); parts=u.path.strip('/').split('/')
        field=fields.get(parts[0]) if len(parts)>=2 and u.hostname==HOST and u.scheme=='https' else None
        if not field or not name or (field,name) in seen: continue
        if len(name)>4096 or len(seen)>=2000: raise ValueError('momon-ga metadata exceeds the item limit')
        seen.add((field,name)); out[field].append({'name':name,**({'gender':'neutral'} if field=='tag' else {})})
    image=urljoin(canonical(url),p.cover)
    if valid_image(image) and re.fullmatch(r'/galleries/'+loc[1]+r'/1\.(?:webp|jpg|jpeg|png)',urlsplit(image).path): out['cover']=image
    else: out['warnings'].append('Cover URL unavailable; other metadata was retrieved')
    return out

def import_url(url): return parse_page(fetch(url),url)

def fetch_image(url):
    mime,body=response(url,2*1024*1024,image=True)
    valid=(mime=='image/webp' and body[:4]==b'RIFF' and body[8:12]==b'WEBP') or (mime=='image/jpeg' and body[:3]==b'\xff\xd8\xff') or (mime=='image/png' and body[:8]==b'\x89PNG\r\n\x1a\n')
    if not valid: raise ValueError('momon-ga response is not a supported image')
    return mime,body
