"""Public read-only HTTP surface. Deliberately imports no private API handler."""
import argparse,html,json,re,sqlite3
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
import db,cover_sources,cover_relay

def get_page(token):
    c=sqlite3.connect(db.PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=10)
    try:
        row=c.execute("SELECT payload,created FROM shared_pages WHERE token=? AND revoked IS NULL AND visibility='unlisted' AND update_mode='snapshot'",(token,)).fetchone()
        return (json.loads(row[0]),row[1]) if row else None
    finally:c.close()

def render(page,created,token):
    e=lambda x:html.escape(str(x or ''),quote=True)
    ja=page.get('ui_language')=='ja';t=lambda en,jp:jp if ja else en
    blocks=[]
    for key,en,jp in [('author','Authors','作者'),('circle','Circles','サークル'),('series','Series','シリーズ'),('character','Characters','キャラクター'),('tag','Tags','タグ')]:
        if page[key]:blocks.append('<section><h2>'+t(en,jp)+'</h2><div class="tags">'+''.join('<span>'+e(x['name'])+(' · '+e(x['gender']) if x.get('gender') not in (None,'neutral','none','') else '')+'</span>' for x in page[key])+'</div></section>')
    if page['ratings']:blocks.append('<section><h2>'+t('Ratings','評価')+'</h2>'+''.join('<p>'+e(x['name'])+' '+str(x['value'])+' / '+str(x['maximum'])+'</p>' for x in page['ratings'])+'</section>')
    if page['marks']:blocks.append('<section><h2>'+t('Marks','マーク')+'</h2><div class="tags">'+''.join('<span>'+e(x['symbol'])+' '+e(x['label'])+'</span>' for x in page['marks'])+'</div></section>')
    if page['review']:blocks.append('<section><h2>'+t('Review','レビュー')+'</h2><p class="review">'+e(page['review'])+'</p></section>')
    if page['links']:blocks.append('<section><h2>'+t('Source links','ソースリンク')+'</h2>'+''.join('<p><a href="'+e(x['url'])+'" rel="noopener noreferrer nofollow" target="_blank">'+e(x['label'] or x['url'])+(' · '+t('Primary','主リンク') if x['is_primary'] else '')+'</a></p>' for x in page['links'])+'</section>')
    cover='<img class="cover" src="/s/'+token+'/cover" alt="" loading="lazy">' if page['cover'] else ''
    return ('<!doctype html><html lang="'+('ja' if ja else 'en')+'"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive"><title>'+e(page['title'])+' - Folio</title><style>body{margin:0;background:#101010;color:#eee;font:16px/1.6 system-ui,sans-serif}main{max-width:900px;margin:auto;padding:24px}a{color:#f7a144;overflow-wrap:anywhere}h1{font-size:2rem;overflow-wrap:anywhere}h2{font-size:1rem;color:#aaa}section{border-top:1px solid #333;padding:12px 0}.cover{width:100%;height:auto;display:block;border-radius:12px}.tags{display:flex;flex-wrap:wrap;gap:8px}.tags span{padding:4px 10px;background:#252525;border-radius:12px}.review{white-space:pre-wrap;overflow-wrap:anywhere}small{color:#aaa}</style></head><body><main><a href="/" aria-label="Folio">Folio</a><p><small>'+t('Shared snapshot','共有時点の記録')+' · '+e(created[:10])+'</small></p><h1>'+e(page['title'])+'</h1>'+cover+'<p>'+e(page['language'])+(' · '+str(page['pages'])+' pages' if page['pages'] is not None else '')+'</p>'+''.join(blocks)+'</main></body></html>').encode()

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def respond(self,raw,status=200,mime='text/html; charset=utf-8'):
        self.send_response(status)
        for k,v in [('Content-Type',mime),('Content-Length',str(len(raw))),('Cache-Control','no-store, max-age=0'),('X-Robots-Tag','noindex, nofollow, noarchive'),('Referrer-Policy','no-referrer'),('X-Content-Type-Options','nosniff'),('Content-Security-Policy',"default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")]:self.send_header(k,v)
        self.end_headers()
        if self.command!='HEAD':self.wfile.write(raw)
    def run(self):
        if self.command not in ('GET','HEAD'):return self.respond(b'Not found',404)
        path=urlsplit(self.path).path
        if path=='/robots.txt':return self.respond(b'User-agent: *\nDisallow: /\n',mime='text/plain')
        match=re.fullmatch(r'/s/([A-Za-z0-9_-]{32})(/cover)?',path)
        if not match:return self.respond(b'Not found',404)
        try:
            result=get_page(match[1])
            if not result:return self.respond(b'Not found',404)
            page,created=result
            if not match[2]:return self.respond(render(page,created,match[1]))
            if not page['cover']:return self.respond(b'Not found',404)
            if not cover_relay.SLOTS.acquire(blocking=False):return self.respond(b'Busy',503)
            try:
                mime,raw=cover_sources.load(page['cover'])
                # A revocation during a slow image fetch must take effect too.
                if not get_page(match[1]):return self.respond(b'Not found',404)
                return self.respond(raw,mime=mime)
            finally:cover_relay.SLOTS.release()
        except (ValueError,OSError,sqlite3.Error,cover_relay.RelayError):self.respond(b'Unavailable',503)
    do_GET=run;do_HEAD=run;do_POST=run;do_PUT=run;do_DELETE=run

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8768);args=parser.parse_args()
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
