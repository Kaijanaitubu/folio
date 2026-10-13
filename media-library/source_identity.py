"""Comparison keys only; never rewrite the displayed source or fetch redirects."""
import re
from urllib.parse import urlsplit

def normalize_url(value):
    value=str(value or '').strip()
    if not value: return ''
    try:
        u=urlsplit(value); port=u.port
        host=(u.hostname or '').lower().encode('idna').decode('ascii')
    except (ValueError,UnicodeError): raise ValueError('Invalid URL')
    if u.scheme not in ('http','https') or not host or u.username is not None or u.password is not None:
        raise ValueError('Use an HTTP or HTTPS URL without credentials')
    if host.startswith('www.'): host=host[4:]
    if ':' in host: host='['+host+']'
    if port not in (None,80,443): host+=':'+str(port)
    def percent(text):
        def replace(m):
            ch=chr(int(m[1],16))
            return ch if ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~' else '%'+m[1].upper()
        return re.sub(r'%([0-9a-fA-F]{2})',replace,text)
    path=percent(u.path or '/'); query=percent(u.query); fragment=percent(u.fragment)
    if host=='momon-ga.com' and re.fullmatch(r'/(?:fanzine|magazine)/mo[1-9][0-9]{0,11}/?',path):
        path=path.rstrip('/')+'/'
        query=''
        # No numbered page anchors have been established; preserve fragments.
    if host=='nhentai.net':
        match=re.fullmatch(r'/g/([1-9][0-9]*)(?:/([1-9][0-9]*))?/?',path)
        if match:
            path='/g/'+str(int(match[1]))+'/'+(str(int(match[2]))+'/' if match[2] else '')
            # Gallery and reader pages remain separate; incidental tracking has no effect.
            query=''; fragment=''
    if host=='hitomi.la' and re.fullmatch(r'/reader/\d+\.html',path):
        if not fragment: fragment='1'
        elif re.fullmatch(r'0*[1-9]\d*',fragment): fragment=str(int(fragment))
    return 'https://'+host+path+('?' + query if query else '')+('#'+fragment if fragment else '')
