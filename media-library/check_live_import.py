"""Explicit metadata-only live verification, never saves a work or image."""
import json
import re
import importer

if __name__=='__main__':
    result=importer.import_url('https://hitomi.la/galleries/1036181.html')
    print(json.dumps({'has_title':bool(result['title']),'pages':result['pages'],'has_cover_url':bool(result['cover']),'warnings':result['warnings']}))
    for host in ('ltn.gold-usergeneratedcontent.net','hitomi.la'):
        try:
            text=importer.fetch('/galleryblock/1036181.html',host)
            sources=re.findall(r'<img[^>]+(?:src|data-src)=["\x27]([^"\x27]+)',text,re.I)
            print(json.dumps({'host':host,'length':len(text),'image_sources':sources[:1]}))
        except Exception as e: print(json.dumps({'host':host,'error':str(e)}))
