"""Read-only, purpose-specific list previews. No source fetching or registration."""
import json
import re
from urllib.parse import urlsplit
import db
import importer

MAX_BYTES=12*1024*1024


def kemono(text):
    try: value=json.loads(text.lstrip('\ufeff'))
    except (ValueError,AttributeError): raise ValueError('Invalid Kemono favorites JSON') from None
    if isinstance(value,dict):
        rows=value.get('posts');artists=value.get('artists',[])
        if not isinstance(artists,list):raise ValueError('Invalid Kemono favorites JSON')
    else:rows=value;artists=[]
    if not isinstance(rows,list) or len(rows)>100000 or len(artists)>100000:
        raise ValueError('Use Kemono post favorites JSON, not artist favorites')
    def ident(value):
        if type(value) is int:value=str(value)
        if not isinstance(value,str) or not re.fullmatch(r'[1-9][0-9]{0,19}',value):
            raise ValueError('A supported Kemono post has invalid IDs')
        return value
    items=[];unsupported=0;seen=set()
    for row in rows:
        if not isinstance(row,dict):raise ValueError('Invalid Kemono favorites JSON')
        if row.get('service') not in ('fanbox','patreon'):unsupported+=1;continue
        user,post=ident(row.get('user')),ident(row.get('id'))
        title=row.get('title') or ''
        if not isinstance(title,str):raise ValueError('Invalid Kemono favorites JSON')
        key=(row['service'],post)
        items.append({'url':f"https://pawchive.pw/{row['service']}/user/{user}/post/{post}",
                      'label':title[:4096], 'folder':'Kemono / '+row['service'],
                      'supported':True,'duplicate':key in seen})
        seen.add(key)
    return items,{'input':len(rows),'unsupported':unsupported,'artists_ignored':len(artists)}


def preview(c,data):
    kind=data.get('kind');text=data.get('text')
    if kind not in ('bookmarks','pawchive','kemono','fanza'):raise ValueError('Choose an import source')
    if not isinstance(text,str) or len(text.encode('utf-8'))>MAX_BYTES:raise ValueError('Import file exceeds 12 MB')
    if kind=='kemono':items,summary=kemono(text)
    else:
        items=importer.bookmarks(text)
        summary={'input':len(items),'unsupported':sum(not i['supported'] for i in items) if kind=='bookmarks' else 0,'artists_ignored':0}
        if kind!='bookmarks':
            kept=[]
            for item in items:
                identity=importer.source_identity(item['url'])
                host=(urlsplit(item['url']).hostname or '').lower()
                allowed=bool(identity) and (identity[0]=='pawchive' if kind=='pawchive' else host in ('dmm.co.jp','www.dmm.co.jp') and '/doujin/' in urlsplit(item['url']).path)
                if allowed:kept.append(item)
                else:summary['unsupported']+=1
            items=kept
    for item in items:
        item['registered']=False;item['related']=[]
        if item['supported']:
            lookup=db.source_matches(c,item['url'])
            item['registered']=lookup['match']=='exact'
            item['duplicate']=item['duplicate'] or item['registered']
            item['related']=lookup['matches'] if lookup['match']=='gallery' else []
    summary.update(items=len(items),registered=sum(i['registered'] for i in items),
                   duplicates=sum(i['duplicate'] and not i['registered'] for i in items),
                   selectable=sum(i['supported'] and not i['duplicate'] for i in items))
    return {'items':items,'summary':summary}
