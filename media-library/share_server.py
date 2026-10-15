"""Public read-only HTTP surface. Deliberately imports no private API handler."""
import argparse,html,json,re,sqlite3
from pathlib import Path
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
    e=lambda x:html.escape(str(x if x is not None else ''),quote=True)
    ja=page.get('ui_language')=='ja';t=lambda en,jp:jp if ja else en
    external='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M14 3h7v7M21 3 10 14M10 3H4v17h17v-6"/></svg>'
    primary=next((l for l in page['links'] if l.get('is_primary')),None)
    def tag(x,kind):
        gender=x.get('gender') if kind=='tag' else ''
        gender=gender if gender in ('female','male') else ''
        suffix=' ♀' if gender=='female' else ' ♂' if gender=='male' else ''
        return '<span class="tag '+gender+'">'+e(x['name'])+suffix+'</span>'
    blocks=[]
    for key,en,jp in [('author','Authors','作者'),('circle','Circles','サークル・グループ'),('tag','Tags','タグ'),('series','Series','シリーズ'),('character','Characters','キャラクター')]:
        if page[key] or key in ('author','circle'):
            content='<div class="tags">'+''.join(tag(x,key) for x in page[key])+'</div>' if page[key] else '<small class="muted">'+t('Not specified','未設定')+'</small>'
            blocks.append('<section><h2>'+t(en,jp)+'</h2>'+content+'</section>')
    if page['review']:blocks.append('<section><h2>'+t('Review','レビュー')+'</h2><p class="review">'+e(page['review'])+'</p></section>')
    if page['links']:blocks.append('<section><h2>'+t('Source links','ソースリンク')+'</h2><div class="source-list">'+''.join('<a class="source-link" href="'+e(x['url'])+'" rel="noopener noreferrer nofollow" target="_blank">'+external+'<span>'+e(x['label'] or x['url'])+'</span>'+('<span class="tag">'+t('Primary','主リンク')+'</span>' if x['is_primary'] else '')+'</a>' for x in page['links'])+'</div></section>')
    cover='<img src="/s/'+token+'/cover" alt="'+e(page['title'])+'" loading="lazy">' if page['cover'] else '<div class="placeholder">'+t('No cover','表紙なし')+'</div>'
    if primary:cover='<a href="'+e(primary['url'])+'" target="_blank" rel="noopener noreferrer nofollow">'+cover+'</a>'
    symbol_map={'Star':('★','☆'),'Heart':('♥','♡'),'Circle':('●','○'),'Diamond':('◆','◇'),'Square':('■','□'),'Triangle':('▲','△'),'Flower':('✿','❀'),'Sun':('☀','☀'),'Moon':('☾','☾'),'Sparkle':('✦','✧')}
    ratings=[]
    for index,r in enumerate(page['ratings'],1):
        on,off=symbol_map.get(r.get('symbol'),('★','☆'));value=r['value'];maximum=r['maximum']
        ratings.append('<div class="ratingline"><span>'+e(r.get('number',index))+'. '+e(r['name'])+'</span><span class="symbols" aria-label="'+str(value)+' / '+str(maximum)+'">'+on*value+'<span class="off">'+off*(maximum-value)+'</span></span><small class="muted">'+str(value)+' / '+str(maximum)+'</small></div>')
    mark_html='<details class="marks"><summary>'+t('Marks','マーク')+' '+e(' '.join(x['symbol'] for x in page['marks']))+'</summary><div class="tags">'+''.join('<span class="tag">'+e(x['symbol'])+' '+e(x['label'])+'</span>' for x in page['marks'])+'</div></details>' if page['marks'] else ''
    info='<div class="row"><span class="tag">'+e(db.language_name(page['language']) or t('Not specified','未設定'))+'</span>'+('<span class="tag">'+t('Pages','ページ数')+': '+str(page['pages'])+'</span>' if page['pages'] is not None else '')+('<a class="btn primary" href="'+e(primary['url'])+'" rel="noopener noreferrer nofollow" target="_blank">'+external+t('Open source','ソースを開く')+'</a>' if primary else '')+'</div>'
    categories={'Manga':'漫画','Doujinshi':'同人誌','Artist CG':'アーティストCG','Image Set':'画像集','Game CG':'ゲームCG'}
    category=page['category'] or t('Library','ライブラリ')
    if ja:category=categories.get(category,category)
    return ('<!doctype html><html lang="'+('ja' if ja else 'en')+'"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive"><title>'+e(page['title'])+' - Folio</title><link rel="stylesheet" href="/s/'+token+'/style.css"></head><body><main><header class="shared-head"><div class="brand"><span class="brandmark">f</span>Folio</div><small class="muted">'+t('Shared snapshot','共有時点の記録')+' · '+e(created[:10])+'</small></header><article class="detail"><div class="detail-cover">'+cover+'</div><div><div class="eyebrow">'+e(category)+'</div><h1>'+e(page['title'])+'</h1>'+mark_html+'<div class="ratings">'+''.join(ratings)+'</div>'+info+'<div class="meta">'+''.join(blocks)+'</div></div></article></main></body></html>').encode()

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def respond(self,raw,status=200,mime='text/html; charset=utf-8'):
        self.send_response(status)
        for k,v in [('Content-Type',mime),('Content-Length',str(len(raw))),('Cache-Control','no-store, max-age=0'),('X-Robots-Tag','noindex, nofollow, noarchive'),('Referrer-Policy','no-referrer'),('X-Content-Type-Options','nosniff'),('Content-Security-Policy',"default-src 'none'; img-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")]:self.send_header(k,v)
        self.end_headers()
        if self.command!='HEAD':self.wfile.write(raw)
    def run(self):
        if self.command not in ('GET','HEAD'):return self.respond(b'Not found',404)
        path=urlsplit(self.path).path
        if path=='/robots.txt':return self.respond(b'User-agent: *\nDisallow: /\n',mime='text/plain')
        match=re.fullmatch(r'/s/([A-Za-z0-9_-]{32})(/cover|/style.css)?',path)
        if not match:return self.respond(b'Not found',404)
        try:
            result=get_page(match[1])
            if not result:return self.respond(b'Not found',404)
            page,created=result
            if not match[2]:return self.respond(render(page,created,match[1]))
            if match[2]=='/style.css':return self.respond((Path(__file__).parent/'static'/'shared-detail.css').read_bytes(),mime='text/css; charset=utf-8')
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
