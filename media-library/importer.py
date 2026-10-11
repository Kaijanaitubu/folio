"""Metadata-only Hitomi adapter. Never evaluates JavaScript or fetches image bytes."""
import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
import threading
from html.parser import HTMLParser
from urllib.parse import urlsplit

HOSTS={'hitomi.la','www.hitomi.la','ltn.hitomi.la','ltn.gold-usergeneratedcontent.net'}
_routing_lock=threading.Lock()
_routing_cache=None
_routing_time=0

def parse_thumbnail_routes(text):
    """Parse the site's restricted integer switch table, never execute its JS."""
    default=re.search(r'm\s*:\s*function\s*\(g\)\s*\{\s*var\s+o\s*=\s*([01])\s*;',text)
    switch=re.search(r'switch\s*\(g\)\s*\{\s*((?:case\s+\d+\s*:\s*)+)o\s*=\s*([01])\s*;\s*break\s*;\s*\}',text)
    if not default or not switch: raise ValueError('Thumbnail routing format changed; metadata can still be saved')
    numbers={int(n) for n in re.findall(r'case\s+(\d+)',switch[1])}
    if any(n>4095 for n in numbers): raise ValueError('Invalid thumbnail routing table')
    return int(default[1]),numbers,int(switch[2])

def thumbnail_routes():
    global _routing_cache,_routing_time
    with _routing_lock:
        if _routing_cache is None or time.monotonic()-_routing_time>3600:
            _routing_cache=parse_thumbnail_routes(fetch('/gg.js'))
            _routing_time=time.monotonic()
        return _routing_cache

def thumbnail_url(image_hash,routes=None,directory='webpbigtn',extension='webp'):
    if not re.fullmatch(r'[0-9a-f]{64}',str(image_hash)): raise ValueError('Invalid thumbnail hash')
    if directory not in ('webpbigtn','webpsmalltn','webpsmallbigtn','avifbigtn','avifsmalltn','avifsmallbigtn','bigtn','smalltn') or extension not in ('webp','avif','jpg'): raise ValueError('Invalid thumbnail format')
    default,numbers,override=routes or thumbnail_routes()
    shard=int(image_hash[-1]+image_hash[-3:-1],16)
    host=('a' if (override if shard in numbers else default)==0 else 'b')+'tn.gold-usergeneratedcontent.net'
    return f'https://{host}/{directory}/{image_hash[-1]}/{image_hash[-3:-1]}/{image_hash}.{extension}'

def resolve_thumbnail_url(value,routes=None):
    parsed=urlsplit(value)
    if parsed.scheme not in ('http','https') or parsed.hostname not in ('tn.hitomi.la','atn.hitomi.la','btn.hitomi.la','tn.gold-usergeneratedcontent.net','atn.gold-usergeneratedcontent.net','btn.gold-usergeneratedcontent.net'):
        raise ValueError('Not a supported Hitomi thumbnail URL')
    m=re.fullmatch(r'/([^/]+)/[0-9a-f]/[0-9a-f]{2}/([0-9a-f]{64})\.(webp|avif|jpg)',parsed.path)
    if not m: raise ValueError('Not a supported Hitomi thumbnail URL')
    return thumbnail_url(m[2],routes,m[1],m[3])
def gallery_id(url):
    try: u=urlsplit(url)
    except ValueError: return None
    if u.scheme not in ('https','http') or u.hostname not in HOSTS or u.username or u.password: return None
    m=re.search(r'(?:/galleries/|/reader/)(\d+)(?:\.html)?(?:/|$)',u.path)
    if not m: m=re.search(r'-(\d+)\.html$',u.path)
    return m.group(1) if m else None

def fetch(path,host='ltn.gold-usergeneratedcontent.net'):
    # Pin a verified public address for the actual socket (no second DNS lookup).
    if host not in HOSTS: raise ValueError('Unsupported metadata host')
    addresses=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses): raise ValueError('Metadata host does not resolve to public addresses')
    family,socktype,proto,_,address=addresses[0]
    conn=http.client.HTTPSConnection(host,timeout=15,context=ssl.create_default_context())
    raw=socket.socket(family,socktype,proto); raw.settimeout(15)
    try:
        raw.connect(address)
        conn.sock=ssl.create_default_context().wrap_socket(raw,server_hostname=host)
        conn.request('GET',path,headers={'User-Agent':'PersonalMediaLibrary/2.0','Referer':'https://hitomi.la/','Accept':'application/javascript,application/json,text/html'})
        response=conn.getresponse()
        if response.status!=200: raise ValueError(f'Metadata source returned HTTP {response.status}')
        data=response.read(4*1024*1024+1)
        if len(data)>4*1024*1024: raise ValueError('Metadata response exceeds 4 MB')
        return data.decode('utf-8')
    finally:
        conn.close(); raw.close()

def parse_gallery(text):
    text=re.sub(r'^\s*(?:var\s+)?galleryinfo\s*=\s*','',text).strip().rstrip(';')
    data=json.loads(text)
    out={'title':data.get('japanese_title') or data.get('title') or '', 'language':data.get('language') or '', 'pages':len(data.get('files',[])) or None, 'author':[], 'circle':[], 'series':[], 'character':[], 'tag':[], 'cover':'', 'warnings':[], '_cover_hash':(data.get('files') or [{}])[0].get('hash')}
    types={'manga':'manga','doujinshi':'doujinshi','artistcg':'artist cg','gamecg':'game cg','imageset':'image set','anime':'anime'}
    out['category']=types.get(str(data.get('type','')).lower().replace(' ',''),'')
    for key,field,name in [('artists','author','artist'),('groups','circle','group'),('parodys','series','parody'),('characters','character','character')]:
        for item in data.get(key,[]) or []:
            value=item.get(name) if isinstance(item,dict) else item
            if value and str(value).casefold()!='n/a': out[field].append({'name':str(value)})
    for item in data.get('tags',[]) or []:
        name=item.get('tag') if isinstance(item,dict) else str(item)
        if not name: continue
        genders=[]
        for g in ('female','male'):
            if isinstance(item,dict) and str(item.get(g,'')).lower() in ('1','true'): genders.append(g)
        for g in genders or ['neutral']: out['tag'].append({'name':name,'gender':g})
    return out

def import_url(url):
    gid=gallery_id(url)
    if not gid: raise ValueError('Unsupported URL; save it as a source or enter metadata manually')
    result=parse_gallery(fetch('/galleries/'+gid+'.js'))
    # Mirror gallery.js/common.js: first-file hash + live gg.js routing table.
    # Only metadata/code text is read; no source JS runs and no image is fetched.
    image_hash=result.pop('_cover_hash',None)
    try:
        if image_hash: result['cover']=thumbnail_url(image_hash)
        else: result['warnings'].append('Cover URL unavailable; other metadata was retrieved')
    except Exception:
        result['warnings'].append('Cover URL unavailable; other metadata was retrieved')
    if not result['title'].strip(): result['warnings'].append('No title was retrieved')
    return result

class Bookmarks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.items=[]; self.folders=[]; self.heading=None; self.pending_folder=None; self.link=None; self.depth=0; self.folder_depths=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='h3': self.heading=''
        if tag=='dl':
            self.depth+=1
            if self.pending_folder is not None:
                self.folders.append(self.pending_folder); self.folder_depths.append(self.depth); self.pending_folder=None
        if tag=='a' and a.get('href'): self.link={'url':a['href'],'label':'','folder':' / '.join(self.folders)}
    def handle_data(self,text):
        if self.heading is not None: self.heading+=text
        if self.link is not None: self.link['label']+=text
    def handle_endtag(self,tag):
        if tag=='h3': self.pending_folder=self.heading; self.heading=None
        if tag=='dl':
            if self.folder_depths and self.folder_depths[-1]==self.depth: self.folder_depths.pop(); self.folders.pop()
            self.depth=max(0,self.depth-1)
        if tag=='a' and self.link is not None:
            self.items.append(self.link); self.link=None
            if len(self.items)>100000: raise ValueError('Bookmark file exceeds 100,000 items')

def bookmarks(text):
    if len(text.encode())>12*1024*1024: raise ValueError('Bookmark file exceeds 12 MB')
    parser=Bookmarks(); parser.feed(text)
    if not parser.items: raise ValueError('No bookmark links found in this HTML file')
    seen=set()
    for item in parser.items:
        item['supported']=bool(gallery_id(item['url'])); item['duplicate']=item['url'] in seen; seen.add(item['url'])
    return parser.items
