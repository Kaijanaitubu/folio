"""Comic-store metadata and bounded RAM-only covers. No source scripts run."""
import contextvars,http.client,ipaddress,json,re,socket,ssl,threading,time
from html.parser import HTMLParser
from http.cookies import SimpleCookie
from urllib.parse import urlsplit,urljoin,parse_qs,quote

CANCEL=contextvars.ContextVar('store_cancel',default=lambda:False)
MAX_HTML=4*1024*1024
_lock=threading.Lock();_next={};_age_cookie=''
DL_HOSTS={'www.dlsite.com','dlsite.com','dlsharing.com','www.dlsharing.com'}
BOOK_HOSTS={'book.dmm.com','book.dmm.co.jp'}
IMAGE_HOSTS={'img.dlsite.jp','doujin-assets.dmm.co.jp','ebook-assets.dmm.co.jp','ebook-assets.dmm.com'}

def location(value):
    try:
        u=urlsplit(value)
        if u.scheme not in ('http','https') or u.port not in (None,80,443) or u.username or u.password:return None
        if u.hostname=='play.dlsite.com':
            m=re.fullmatch(r'/work/((?:RJ|BJ)[0-9]{6,12})/?',u.path,re.I)
            if m:return ('dlsite',m[1].upper(),'books' if m[1].upper().startswith('BJ') else 'maniax')
        if u.hostname in DL_HOSTS:
            m=re.fullmatch(r'/(home|maniax|girls|books)(?:-touch)?/work/=/product_id/((?:RJ|BJ)[0-9]{6,12})\.html/?',u.path,re.I)
            if m:return ('dlsite',m[2].upper(),m[1].lower())
        if u.hostname in ('www.dmm.co.jp','dmm.co.jp'):
            m=re.fullmatch(r'/dc/doujin/-/detail/=/cid=(d_[1-9][0-9]{0,11})/?',u.path)
            if m:return ('fanza-doujin',m[1],'')
        if u.hostname in BOOK_HOSTS:
            m=re.fullmatch(r'/product/([1-9][0-9]{0,11})/([a-z0-9_]{1,80})/?',u.path)
            if m and m[2]!='latest':return ('dmm-books',m[2],m[1])
    except (ValueError,TypeError):pass
    return None

def play_series(value):
    try:
        u=urlsplit(value)
        return u.scheme in ('http','https') and u.hostname=='play.dlsite.com' and u.port in (None,80,443) and not (u.username or u.password) and bool(re.fullmatch(r'/series/TITLE[0-9]{6,12}/?',u.path))
    except (ValueError,TypeError):return False

def canonical(value):
    loc=location(value)
    if not loc:raise ValueError('Use a DLsite, FANZA doujin or DMM Books comic product URL')
    kind,pid,section=loc
    if kind=='dlsite':return f'https://www.dlsite.com/{section}/work/=/product_id/{pid}.html'
    if kind=='fanza-doujin':return f'https://www.dmm.co.jp/dc/doujin/-/detail/=/cid={pid}/'
    return f'https://{urlsplit(value).hostname}/product/{section}/{pid}/'

def comparison(value):
    loc=location(value)
    if not loc:return None
    kind,pid,_=loc
    # A stable product key, not a fetch target. Preserve editions and volumes.
    return 'https://www.dlsite.com/work/'+pid if kind=='dlsite' else ('https://www.dmm.co.jp/dc/doujin/product/'+pid if kind=='fanza-doujin' else 'https://book.dmm.com/product-id/'+pid)

def label(value):
    loc=location(value)
    if not loc:return ''
    if loc[0]=='dlsite' and urlsplit(value).hostname=='play.dlsite.com':return 'DLsite Play'
    return 'DLsite' if loc[0]=='dlsite' else 'FANZA同人' if loc[0]=='fanza-doujin' else 'FANZAブックス' if urlsplit(value).hostname=='book.dmm.co.jp' else 'DMMブックス'

def valid_image(value):
    try:
        u=urlsplit(value)
        if u.scheme!='https' or u.hostname not in IMAGE_HOSTS or u.port not in (None,443) or u.username or u.password or u.query or u.fragment:return False
        if u.hostname=='img.dlsite.jp':return bool(re.fullmatch(r'/modpub/images2/work/(doujin|books)/((?:RJ|BJ)[0-9]{6,12})/((?:RJ|BJ)[0-9]{6,12})_img_main\.(jpg|webp|png)',u.path))
        if u.hostname=='doujin-assets.dmm.co.jp':return bool(re.fullmatch(r'/digital/comic/(d_[1-9][0-9]{0,11})/\1pr\.(jpg|webp|png)',u.path))
        return bool(re.fullmatch(r'/digital/e-book/([a-z0-9_]{1,80})/\1(?:pl|ps)\.(jpg|webp|png)',u.path))
    except (ValueError,TypeError):return False

def age_location(value,target):
    try:
        u=urlsplit(value);q=parse_qs(u.query)
        return u.scheme=='https' and u.hostname=='www.dmm.co.jp' and not (u.username or u.password) and u.port in (None,443) and u.path in ('/age_check/=/','/age_check/=/declared=yes/','/en/age_check/=/','/en/age_check/=/declared=yes/') and q.get('rurl')==[target] and set(q)<= {'rurl','force'}
    except ValueError:return False

def product_redirect(value,target):
    # A store may change its display section, never its product ID or host.
    if location(target) and location(target)[0]=='dlsite':
        u=urlsplit(value)
        loc=location(value)
        return u.hostname=='www.dlsite.com' and u.scheme=='https' and u.port in (None,443) and loc and loc[:2]==location(target)[:2] and canonical(value)==value
    return value==canonical(target)

def request(value,target=None,image=False,cookie=''):
    u=urlsplit(value)
    if image:
        if not valid_image(value):raise ValueError('Unsupported store cover URL')
    elif not product_redirect(value,target) and not age_location(value,target):raise ValueError('Unexpected store redirect')
    if u.hostname not in {'www.dlsite.com','www.dmm.co.jp',*BOOK_HOSTS,*IMAGE_HOSTS}:raise ValueError('Unsupported store host')
    limit=2*1024*1024 if image else MAX_HTML;deadline=time.monotonic()+25
    addresses=socket.getaddrinfo(u.hostname,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):raise ValueError('Store host does not resolve to public addresses')
    family,kind,proto,_,address=addresses[0];raw=socket.socket(family,kind,proto)
    conn=http.client.HTTPSConnection(u.hostname,timeout=25);timer=None
    def remaining():
        n=deadline-time.monotonic()
        if n<=0:raise ValueError('Store request timed out')
        return n
    try:
        raw.settimeout(remaining());raw.connect(address);tls=ssl.create_default_context().wrap_socket(raw,server_hostname=u.hostname);conn.sock=tls
        def expire():
            try:tls.shutdown(socket.SHUT_RDWR)
            except OSError:pass
        timer=threading.Timer(remaining(),expire);timer.daemon=True;timer.start()
        headers={'User-Agent':'Mozilla/5.0','Accept-Encoding':'identity','Accept':'image/jpeg,image/webp,image/png' if image else 'text/html'}
        if cookie and not image and u.hostname.endswith('dmm.co.jp'):headers['Cookie']='age_check_done='+cookie
        conn.request('GET',u.path+('?' +u.query if u.query else ''),headers=headers);tls.settimeout(remaining());r=conn.getresponse()
        response_headers=r.getheaders();mime=(r.getheader('Content-Type') or '').split(';')[0].lower()
        if r.status!=200:return r.status,response_headers,mime,b''
        declared=r.getheader('Content-Length')
        if declared and (int(declared)<0 or int(declared)>limit):raise ValueError('Store response exceeds size limit')
        body=bytearray()
        while True:
            if not image and CANCEL.get()():raise ValueError('Import paused or cancelled')
            tls.settimeout(remaining());chunk=r.read1(min(65536,limit+1-len(body)))
            if not chunk:break
            body.extend(chunk)
            if len(body)>limit:raise ValueError('Store response exceeds size limit')
        if declared and len(body)!=int(declared):raise ValueError('Store response was incomplete')
        return r.status,response_headers,mime,bytes(body)
    except (OSError,http.client.HTTPException) as e:
        raise ValueError('Store could not be reached') from e
    finally:
        if timer:timer.cancel()
        conn.close();raw.close()

class StoreHTTPError(ValueError):
    def __init__(self,status):
        self.status=status
        super().__init__(f'Store metadata returned HTTP {status}')

def fetch(value):
    target=canonical(value)
    if urlsplit(value).hostname!='play.dlsite.com':return _fetch(target)
    kind,pid,section=location(value)
    sections=[section]+(['home','girls'] if pid.startswith('RJ') else [])
    for section in sections:
        try:return _fetch(f'https://www.dlsite.com/{section}/work/=/product_id/{pid}.html')
        except StoreHTTPError as e:
            if e.status not in (404,410):raise
    raise ValueError('DLsite product page unavailable; enter metadata manually or use another source')

def _fetch(value):
    global _age_cookie
    target=canonical(value);provider=location(value)[0]
    with _lock:
        start=max(time.monotonic(),_next.get(provider,0));_next[provider]=start+3
    while time.monotonic()<start:
        if CANCEL.get()():raise ValueError('Import paused or cancelled')
        time.sleep(min(.2,max(0,start-time.monotonic())))
    current=target
    for _ in range(6):
        if CANCEL.get()():raise ValueError('Import paused or cancelled')
        status,headers,mime,body=request(current,target,cookie=_age_cookie)
        for name,value in headers:
            if name.lower()=='set-cookie' and urlsplit(current).hostname in ('www.dmm.co.jp','book.dmm.co.jp'):
                jar=SimpleCookie();jar.load(value)
                if 'age_check_done' in jar:_age_cookie=jar['age_check_done'].value
        if status in (301,302,303,307,308):
            dest=urljoin(current,next((v for k,v in headers if k.lower()=='location'),''))
            if provider=='dlsite' and urlsplit(dest).hostname in DL_HOSTS and location(dest) and location(dest)[:2]==location(target)[:2]:dest=canonical(dest)
            if not product_redirect(dest,target) and not age_location(dest,target):raise ValueError('Unexpected store redirect; login or challenge may be required')
            current=dest;continue
        if status!=200:raise StoreHTTPError(status)
        html=body.decode('utf-8-sig')
        if age_location(current,target):
            m=re.search(r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',html,re.S)
            try:dest=json.loads(m[1])['props']['pageProps']['yesButtonLink']
            except (TypeError,KeyError,ValueError):raise ValueError('Store age confirmation format changed')
            if not age_location(dest,target) or '/declared=yes/' not in dest:raise ValueError('Invalid store age confirmation')
            current=dest;continue
        return html
    raise ValueError('Store redirected too many times')

class Node:
    def __init__(self,tag='',attrs=None):self.tag=tag;self.attrs=attrs or {};self.children=[]
    def text(self):return ''.join(c.text() if isinstance(c,Node) else c for c in self.children).strip()
    def walk(self):
        yield self
        for c in self.children:
            if isinstance(c,Node):yield from c.walk()
    def find(self,tag=None,ident=None,cls=None):return [n for n in self.walk() if (not tag or n.tag==tag) and (not ident or n.attrs.get('id')==ident) and (not cls or cls in n.attrs.get('class','').split())]

class Page(HTMLParser):
    VOID={'img','meta','link','br','input','hr','source','wbr','area','base','embed','param'}
    def __init__(self):super().__init__(convert_charrefs=True);self.root=Node();self.stack=[self.root];self.count=0
    def handle_starttag(self,tag,attrs):
        self.count+=1
        if self.count>200000 or len(self.stack)>200:raise ValueError('Store HTML is too complex')
        n=Node(tag,dict(attrs));self.stack[-1].children.append(n)
        if tag not in self.VOID:self.stack.append(n)
    def handle_data(self,data):self.stack[-1].children.append(data)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:self.stack=self.stack[:i];break

def parse_page(html,value):
    if len(html.encode('utf-8'))>MAX_HTML:raise ValueError('Store HTML exceeds size limit')
    loc=location(value)
    if not loc:raise ValueError('Unsupported store product URL')
    kind,pid,_=loc;p=Page();p.feed(html);root=p.root
    h1=root.find('h1',ident='work_name') if kind=='dlsite' else root.find('h1')
    title=h1[0].text() if h1 else ''
    if not title:raise ValueError('Store page has no product title; login or source format change may be responsible')
    out={'title':title,'source_titles':[title],'source_label':label(value),'language':'','pages':None,'category':'doujinshi' if kind=='fanza-doujin' or kind=='dlsite' and pid.startswith('RJ') else 'manga','cover':'','warnings':[],**{k:[] for k in ('author','circle','series','character','tag')}}
    variant=re.sub(r'\s+([【\[])',r'\1',title)
    if variant!=title:out['source_titles'].append(variant)
    def add(field,name):
        name=name.strip()
        if not name:return
        if len(name)>4096 or len(out[field])>=2000:raise ValueError('Store metadata exceeds item limit')
        if not any(e['name']==name for e in out[field]):out[field].append({'name':name,**({'gender':'neutral'} if field=='tag' else {})})
    comic_type=False
    def cell(key,n):
        nonlocal comic_type
        names=[a.text() for a in n.find('a') if a.text()]
        if key in ('作者','著者','作家'):
            for name in names or [n.text()]:add('author',name)
        elif key in ('シリーズ','シリーズ名'):add('series',n.text())
        elif key=='ジャンル':
            for name in names:add('tag',name)
        elif key=='ページ数':
            m=re.fullmatch(r'\s*([1-9][0-9]{0,5})\s*(?:ページ)?\s*',n.text())
            if m:out['pages']=int(m[1])
        elif key in ('作品形式','カテゴリー'):
            if kind=='dmm-books' and key=='カテゴリー' and not any(s in n.text() for s in ('マンガ','漫画','コミック')):raise ValueError('This importer supports comic products only')
            if kind=='dlsite':
                cg='CG・イラスト' in n.text()
                if not cg and not any(s in n.text() for s in ('マンガ','漫画','コミック','同人誌')):raise ValueError('DLsite importer supports comics and CG illustrations only')
                if cg:out['category']='artist cg'
            if kind=='fanza-doujin' and 'コミック' not in n.text():raise ValueError('This importer supports comic products only')
            comic_type=any(s in n.text() for s in ('マンガ','漫画','コミック','同人誌')) or kind=='dlsite' and cg
    if kind=='dlsite':
        for ident in ('work_outline','work_maker'):
            for table in root.find(ident=ident):
                for row in table.find('tr'):
                    th,td=row.find('th'),row.find('td')
                    if th and td:cell(th[0].text(),td[0])
        if pid.startswith('RJ'):
            for maker in root.find(cls='maker_name'):
                for a in maker.find('a'):add('circle',a.text())
    else:
        rows=root.find(cls='productInformation__item') if kind=='fanza-doujin' else root.find('dl')
        if kind=='fanza-doujin':
            for area in root.find(cls='circleName'):
                for a in area.find('a'):
                    if 'article=maker' in a.attrs.get('href',''):add('circle',a.text())
        for row in rows:
            dt,dd=row.find('dt'),row.find('dd')
            if dt and dd:cell(dt[0].text().strip().rstrip('：:'),dd[0])
        if kind=='dmm-books':
            for script in root.find('script'):
                if script.attrs.get('type')!='application/ld+json':continue
                try:j=json.loads(script.text())
                except ValueError:continue
                if not isinstance(j,dict) or j.get('@type')!='Product' or j.get('name')!=title:continue
                book=j.get('subjectOf') or {};authors=book.get('author') or []
                if isinstance(authors,dict):authors=[authors]
                for author in authors:
                    names=author.get('name',[]) if isinstance(author,dict) else []
                    for name in names if isinstance(names,list) else [names]:add('author',str(name))
                genres=book.get('genre') or []
                for name in genres if isinstance(genres,list) else [genres]:add('tag',str(name))
    if not comic_type:raise ValueError('This importer supports comic products only')
    for meta in root.find('meta'):
        image=meta.attrs.get('content','')
        if meta.attrs.get('property')=='og:image' and valid_image(image):
            path=urlsplit(image).path
            if '/'+pid+'/' in path or '/'+pid+'_img_main.' in path:out['cover']=image
    if not out['cover']:out['warnings'].append('Cover URL unavailable; other metadata was retrieved')
    return out

def import_url(value):return parse_page(fetch(value),value)

def fetch_image(value):
    status,_,mime,body=request(value,image=True)
    valid=(mime=='image/jpeg' and body[:3]==b'\xff\xd8\xff') or (mime=='image/png' and body[:8]==b'\x89PNG\r\n\x1a\n') or (mime=='image/webp' and body[:4]==b'RIFF' and body[8:12]==b'WEBP')
    if status!=200 or not valid:raise ValueError('Store cover response is not a supported image')
    return mime,body
