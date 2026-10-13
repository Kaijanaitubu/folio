"""Confirmed, snapshot-guarded URL reuse; save and purge are atomic."""
import hashlib,json
import db,features

def preview(c,url,exclude=''):
    matches=db.exact_sources(c,url,exclude)
    if any(not w['deleted_at'] for w in matches): raise db.DuplicateSource(matches)
    works=[db.get_work(c,w['id'],include_deleted=True) for w in matches]
    signature=hashlib.sha256(json.dumps(works,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {'url':db.url(url),'works':works,'signature':signature}

def approved(c,consents,urls,exclude=''):
    if not isinstance(consents,list) or len(consents)>100: raise ValueError('Invalid Trash confirmations')
    allowed={db.normalize_url(url) for url in urls};ids=set()
    for item in consents:
        if not isinstance(item,dict) or db.normalize_url(item.get('url','')) not in allowed: raise ValueError('Trash confirmation must refer to a saved source link')
        current=preview(c,item['url'],exclude)
        if not current['works'] or current['signature']!=item.get('signature'): raise ValueError('Trash entries changed; review the link again')
        ids.update(w['id'] for w in current['works'])
    return ids

def save(c,data,wid=None):
    if not c.in_transaction:c.execute('BEGIN IMMEDIATE')
    ids=approved(c,data.get('trash_sources',[]),[l.get('url','') for l in data.get('links',[])],wid or '')
    for source in ids:db.purge_work(c,source)
    return features.save_work(c,data,wid)
