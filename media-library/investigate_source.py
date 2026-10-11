"""Inspect public source HTML/JS only; never fetch image bodies."""
import json
import re
import socket
import http.client
import ssl
import ipaddress
from urllib.parse import urlsplit
import importer

if __name__=='__main__':
    # Compare generic and routed thumbnail HTTP headers, without reading bodies.
    result=importer.import_url('https://hitomi.la/galleries/1036181.html')
    fixed=result['cover']
    generic=re.sub(r'//[ab]tn\.', '//tn.',fixed)
    avif=fixed.replace('/webpbigtn/','/avifbigtn/').replace('.webp','.avif')
    for value,method,referer in [(generic,'HEAD',None),(fixed,'HEAD',None),(fixed,'GET',None),(fixed,'GET','http://localhost:8765/'),(fixed,'GET','https://hitomi.la/'),(generic,'GET','https://hitomi.la/'),(avif,'GET','https://hitomi.la/')]:
        u=urlsplit(value)
        family,kind,proto,_,address=socket.getaddrinfo(u.hostname,443,type=socket.SOCK_STREAM)[0]
        if not ipaddress.ip_address(address[0]).is_global:raise ValueError('Nonpublic address')
        raw_socket=socket.socket(family,kind,proto);raw_socket.settimeout(15);raw_socket.connect(address)
        connection=http.client.HTTPSConnection(u.hostname,timeout=15)
        connection.sock=ssl.create_default_context().wrap_socket(raw_socket,server_hostname=u.hostname)
        try:
            headers={'User-Agent':'Mozilla/5.0','Accept':'image/avif,image/webp,image/*,*/*;q=0.8'}
            if referer:headers['Referer']=referer
            connection.request(method,u.path,headers=headers)
            response=connection.getresponse()
            print(method,referer or 'no Referer',value,response.status,response.getheader('Content-Type'))
        finally:connection.close();raw_socket.close()
    raw=importer.fetch('/galleries/1036181.js')
    data=json.loads(re.sub(r'^\s*(?:var\s+)?galleryinfo\s*=\s*','',raw).strip().rstrip(';'))
    print('Title fields:',{k:len(str(v)) for k,v in data.items() if 'title' in k})
    print('Gallery URL:',data.get('galleryurl'))
    home=importer.fetch('/','hitomi.la')
    print('Scripts:',re.findall(r'<script[^>]+src=["\x27]([^"\x27]+)',home,re.I))
    for path,host in [('/gg.js','ltn.gold-usergeneratedcontent.net'),('/gallery.js','ltn.gold-usergeneratedcontent.net'),('/common.js','ltn.gold-usergeneratedcontent.net')]:
        try:
            text=importer.fetch(path,host)
            print('\nSOURCE',host+path)
            if path=='/gg.js':
                print(text[:500]); print('END:',text[-650:])
            elif path=='/common.js':
                a=text.find('function subdomain_from_url'); b=text.find('function',text.find('function url_from_url_from_hash')+20)
                print(text[a:b])
            else:
                for match in re.finditer(r'.{0,140}(?:japanese_title|webpbigtn|thumbnail|tn\.hitomi|url_from_url|replace|galleryinfo\.title|<h[12]).{0,260}',text): print(match.group(0))
        except Exception as e: print(path,str(e))
    for host in ('tn.hitomi.la','tn.gold-usergeneratedcontent.net'):
        try: print('DNS',host,socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)[0][4][0])
        except Exception as e: print('DNS',host,str(e))
