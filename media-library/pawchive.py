"""Public post metadata and bounded RAM covers; no account or original-site access."""
import contextvars
import csv
import http.client
import ipaddress
import json
import re
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit, urljoin

HOST='pawchive.pw'
SERVICES=('fanbox','patreon')
IMAGE_HOSTS={'file.pawchive.pw','img.pawchive.pw'}
CANCEL=contextvars.ContextVar('pawchive_cancel',default=lambda:False)
_lock=threading.Lock()
_next=0
ID=r'[1-9][0-9]{0,19}'
FILE=r'/([0-9a-f]{2})/([0-9a-f]{2})/([0-9a-f]{64})\.(jpeg|jpg|png|webp)'

def location(value):
    try:
        u=urlsplit(value)
        if u.scheme not in ('http','https') or u.hostname not in (HOST,'www.'+HOST) or u.port not in (None,80,443) or u.username is not None or u.password is not None:return None
        m=re.fullmatch(r'/(fanbox|patreon)/(?:user/('+ID+r')/)?post/('+ID+r')/?',u.path)
        return (m[1],m[2],m[3]) if m else None
    except (ValueError,TypeError):return None

def canonical(value):
    loc=location(value)
    if not loc:raise ValueError('Use a Pawchive FANBOX or Patreon post URL')
    service,creator,post=loc
    return f'https://{HOST}/{service}/'+(f'user/{creator}/' if creator else '')+f'post/{post}'

def comparison(value):
    loc=location(value)
    # The site's short route resolves a post ID within its service, regardless
    # of the author path. Never equate FANBOX and Patreon IDs.
    return f'https://{HOST}/{loc[0]}/post/{loc[2]}' if loc else None

def original_comparison(value):
    try:
        u=urlsplit(value)
        if u.scheme not in ('http','https') or u.port not in (None,80,443) or u.username is not None or u.password is not None:return None
        if u.hostname in ('patreon.com','www.patreon.com'):
            m=re.fullmatch(r'/(?:[a-zA-Z0-9_-]+/)?posts/(?:[a-zA-Z0-9_-]+-)?('+ID+r')/?',u.path)
            if m:return 'https://www.patreon.com/posts/'+m[1]
        if u.hostname in ('fanbox.cc','www.fanbox.cc'):
            m=re.fullmatch(r'/@[a-zA-Z0-9_-]{1,64}/posts/('+ID+r')/?',u.path)
        elif re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.fanbox\.cc',u.hostname or ''):
            m=re.fullmatch(r'/posts/('+ID+r')/?',u.path)
        else:m=None
        if m:return 'https://www.fanbox.cc/posts/'+m[1]
    except (ValueError,TypeError):pass
    return None

def original_label(value):
    key=original_comparison(value)
    return 'Patreon' if key and 'patreon.com/' in key else 'FANBOX' if key else ''

def original_candidates(service,creator,post,profile):
    if service=='patreon':return [{'url':f'https://www.patreon.com/posts/{post}','label':'Patreon','verified':False}]
    public=profile.get('public_id') if isinstance(profile,dict) and str(profile.get('id'))==creator and profile.get('service')==service else None
    if not isinstance(public,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',public):return []
    # Prefer the observed subdomain form; underscore handles use the path form.
    if re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?',public):url=f'https://{public.lower()}.fanbox.cc/posts/{post}'
    else:url=f'https://www.fanbox.cc/@{public}/posts/{post}'
    return [{'url':url,'label':'FANBOX','verified':False}]

def image_path(value):
    if not isinstance(value,str):return False
    m=re.fullmatch(FILE,value)
    return bool(m and m[3].startswith(m[1]+m[2]))

def valid_image(value):
    try:
        u=urlsplit(value)
        if u.scheme!='https' or u.hostname not in IMAGE_HOSTS or u.port not in (None,443) or u.username is not None or u.password is not None or u.query or u.fragment:return False
        prefix='/data' if u.hostname=='file.pawchive.pw' else '/thumbnail/data'
        return u.path.startswith(prefix+'/') and image_path(u.path[len(prefix):])
    except (ValueError,TypeError):return False

def request(value,image=False):
    """Fixed paths/hosts, public-address-pinned TLS, no automatic redirects."""
    u=urlsplit(value)
    if image:
        if not valid_image(value):raise ValueError('Unsupported Pawchive image URL')
    else:
        api=re.fullmatch(r'/api/v1/(fanbox|patreon)/user/'+ID+r'/(?:post/'+ID+r'|profile)',u.path)
        short=re.fullmatch(r'/(fanbox|patreon)/post/'+ID,u.path)
        if u.scheme!='https' or u.hostname!=HOST or u.port not in (None,443) or u.username is not None or u.password is not None or u.query or u.fragment or not (api or short):raise ValueError('Unsupported Pawchive metadata URL')
    limit=2*1024*1024 if image else 4*1024*1024
    deadline=time.monotonic()+20
    addresses=socket.getaddrinfo(u.hostname,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):raise ValueError('Pawchive host does not resolve to public addresses')
    family,kind,proto,_,address=addresses[0]
    raw=socket.socket(family,kind,proto);conn=http.client.HTTPSConnection(u.hostname,timeout=20);timer=None
    def remaining():
        seconds=deadline-time.monotonic()
        if seconds<=0:raise ValueError('Pawchive request timed out')
        return seconds
    try:
        raw.settimeout(remaining());raw.connect(address);raw.settimeout(remaining())
        tls=ssl.create_default_context().wrap_socket(raw,server_hostname=u.hostname);conn.sock=tls
        def expire():
            try:tls.shutdown(socket.SHUT_RDWR)
            except OSError:pass
        timer=threading.Timer(remaining(),expire);timer.daemon=True;timer.start()
        conn.request('GET',u.path,headers={'User-Agent':'Folio/2.0','Accept':'image/webp,image/jpeg,image/png' if image else 'application/json,text/html','Accept-Encoding':'identity'})
        tls.settimeout(remaining());r=conn.getresponse()
        headers=dict((k.lower(),v) for k,v in r.getheaders())
        mime=headers.get('content-type','').split(';')[0].strip().lower()
        if r.status!=200:return r.status,headers,mime,b''
        if image and not mime.startswith('image/'):raise ValueError('Pawchive returned an unexpected image content type')
        declared=headers.get('content-length')
        if declared is not None and not 0<=int(declared)<=limit:raise ValueError('Pawchive response exceeds the size limit')
        body=bytearray()
        while True:
            if not image and CANCEL.get()():raise ValueError('Import paused or cancelled')
            tls.settimeout(remaining());chunk=r.read1(min(65536,limit+1-len(body)))
            if not chunk:break
            body.extend(chunk)
            if len(body)>limit:raise ValueError('Pawchive response exceeds the size limit')
        if declared is not None and len(body)!=int(declared):raise ValueError('Pawchive response was incomplete')
        return r.status,headers,mime,bytes(body)
    except (OSError,http.client.HTTPException) as e:raise ValueError('Pawchive source could not be reached; try again later') from e
    finally:
        if timer:timer.cancel()
        conn.close();raw.close()

def fetch(value):
    global _next
    with _lock:
        target=max(time.monotonic(),_next);_next=target+1
    while time.monotonic()<target:
        if CANCEL.get()():raise ValueError('Import paused or cancelled')
        time.sleep(min(.2,max(0,target-time.monotonic())))
    if CANCEL.get()():raise ValueError('Import paused or cancelled')
    return request(value)

def fetch_json(value):
    status,_,mime,body=fetch(value)
    if status!=200:raise ValueError(f'Pawchive source returned HTTP {status}; try again later')
    if mime!='application/json':raise ValueError('Pawchive returned an unexpected metadata content type')
    try:data=json.loads(body)
    except (ValueError,UnicodeError) as e:raise ValueError('Pawchive returned invalid metadata') from e
    if not isinstance(data,dict):raise ValueError('Pawchive returned invalid metadata')
    return data

def resolve(value):
    url=canonical(value);loc=location(url)
    if loc[1]:return url
    status,headers,_,_=fetch(url)
    target=urljoin(url,headers.get('location',''));dest=location(target)
    u=urlsplit(target)
    if status not in (301,302,303,307,308) or not dest or not dest[1] or dest[::2]!=loc[::2] or u.scheme!='https' or u.hostname!=HOST or u.query or u.fragment:
        raise ValueError('Pawchive short link could not be resolved; use the full post URL')
    return canonical(target)

def parse_tags(value):
    if value is None or value=='':return []
    if isinstance(value,str):
        text=value.strip()
        if text.startswith('['):value=json.loads(text)
        elif text.startswith('{') and text.endswith('}'):
            inner=text[1:-1]
            if not inner:return []
            # PostgreSQL-style one-dimensional arrays. Validate quoting before
            # CSV decoding, which understands commas and backslash escapes.
            if not re.fullmatch(r'(?:\s*(?:"(?:[^"\\]|\\.)*"|[^",{}\\]*(?:\\.[^",{}\\]*)*)\s*)(?:,\s*(?:"(?:[^"\\]|\\.)*"|[^",{}\\]*(?:\\.[^",{}\\]*)*)\s*)*',inner):raise ValueError('Invalid tag array')
            value=next(csv.reader([inner],escapechar='\\',skipinitialspace=True,strict=True))
        else:raise ValueError('Invalid tag array')
    if not isinstance(value,list) or len(value)>2000 or any(not isinstance(tag,str) or len(tag)>4096 for tag in value):raise ValueError('Invalid tag array')
    return list(dict.fromkeys(tag.strip() for tag in value if tag.strip()))

class VideoPostSkipped(ValueError):
    pass

def media_kind(data):
    """Classify attachment metadata only; never download video or archives."""
    images=videos=unknown=False
    for item in [data.get('file'),*(data.get('attachments') or [])]:
        if not isinstance(item,dict):continue
        path=item.get('path') or item.get('name') or ''
        ext=path.rsplit('.',1)[-1].lower() if '.' in path else ''
        if ext in ('jpg','jpeg','png','webp','gif','avif','bmp'):images=True
        elif ext in ('mp4','webm','mov','mkv','avi','m4v','mpeg','mpg','ogv'):videos=True
        elif path:unknown=True
    return 'mixed' if videos and images else 'video' if videos and not unknown else 'uncertain' if videos or unknown else 'image' if images else 'unknown'

def parse_post(data,profile,url):
    loc=location(url)
    if not loc or not loc[1]:raise ValueError('Use a full Pawchive post URL')
    service,creator,post=loc
    if (str(data.get('service')),str(data.get('user')),str(data.get('id')))!=(service,creator,post):raise ValueError('Pawchive returned a different post')
    title=data.get('title')
    if not isinstance(title,str) or not title.strip() or len(title)>4096:raise ValueError('Pawchive post has no usable title')
    out={'title':title,'source_titles':[title],'source_label':'Pawchive','cover':'','category':'','language':'','pages':None,'warnings':[],**{k:[] for k in ('author','circle','series','character','tag')}}
    out['original_links']=original_candidates(service,creator,post,profile)
    if not out['original_links']:out['warnings'].append('Original FANBOX link unavailable; add it manually if needed')
    name=profile.get('name') if isinstance(profile,dict) and str(profile.get('id'))==creator and profile.get('service')==service else None
    if isinstance(name,str) and name.strip() and len(name)<=4096:out['author']=[{'name':name.strip()}]
    else:out['warnings'].append('Pawchive author name unavailable; other metadata was retrieved')
    try:out['tag']=[{'name':name,'gender':'neutral'} for name in parse_tags(data.get('tags'))]
    except (ValueError,csv.Error):out['warnings'].append('Pawchive tags could not be read; other metadata was retrieved')
    attachments=data.get('attachments')
    if attachments is not None and (not isinstance(attachments,list) or len(attachments)>10000):raise ValueError('Pawchive attachment metadata exceeds the item limit')
    out['media_kind']=media_kind(data)
    if out['media_kind']=='video':raise VideoPostSkipped('Video-only Pawchive post skipped')
    if out['media_kind'] in ('unknown','uncertain'):out['warnings'].append('Pawchive media type could not be determined')
    for item in [data.get('file'),*(attachments or [])]:
        path=item.get('path') if isinstance(item,dict) else None
        if image_path(path):
            out['cover']='https://file.pawchive.pw/data'+path;break
    if not out['cover']:out['warnings'].append('Cover URL unavailable; other metadata was retrieved')
    return out

def import_url(value):
    url=resolve(value);service,creator,post=location(url)
    prefix=f'https://{HOST}/api/v1/{service}/user/{creator}'
    data=fetch_json(prefix+'/post/'+post)
    try:profile=fetch_json(prefix+'/profile')
    except ValueError:
        if CANCEL.get()():raise
        profile={}
    return parse_post(data,profile,url)

def fetch_image(value):
    def load(url):
        status,_,_,body=request(url,image=True)
        if status!=200:raise ValueError(f'Pawchive source returned HTTP {status}; try again later')
        # Thumbnail responses may declare JPEG while actually carrying WebP.
        if body[:3]==b'\xff\xd8\xff':return 'image/jpeg',body
        if body[:8]==b'\x89PNG\r\n\x1a\n':return 'image/png',body
        if body[:4]==b'RIFF' and body[8:12]==b'WEBP':return 'image/webp',body
        raise ValueError('Pawchive response is not a supported image')
    if not valid_image(value):raise ValueError('Unsupported Pawchive image URL')
    try:return load(value)
    except ValueError:
        if urlsplit(value).hostname!='file.pawchive.pw':raise
        return load('https://img.pawchive.pw/thumbnail'+urlsplit(value).path)
