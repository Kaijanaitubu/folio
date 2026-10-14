"""DLsite Play inventory protocol and offline conversion, with no auth/network access.

The request callback is deliberately supplied by the caller. There is no browser,
cookie reader, login client or production HTTP transport in this prototype.
"""
import html
import re

FORMAT='folio-dlsite-play-purchases-v1'
MAX_ITEMS=100000
MAX_BYTES=12*1024*1024
COUNT='/api/v3/content/count?last=0'
SALES='/api/v3/content/sales?last=0'
WORKS='/api/v3/content/works'
TYPES={'MNG':'manga','SCM':'manga','WBT':'manga','ICG':'artist cg'}

class InventoryError(ValueError):pass

def product_id(value):
    return isinstance(value,str) and bool(re.fullmatch(r'[A-Z]{2}[0-9]{6,12}',value))

def count_value(data):
    if not isinstance(data,dict) or type(data.get('user')) is not int or not 0<=data['user']<=MAX_ITEMS:
        raise InventoryError('Purchase count response has an unexpected format')
    return data['user']

def sales_ids(data):
    if not isinstance(data,list) or len(data)>MAX_ITEMS:
        raise InventoryError('Purchase list response has an unexpected format')
    ids=[];seen=set();duplicates=0
    for row in data:
        if not isinstance(row,dict) or not product_id(row.get('workno')):
            raise InventoryError('Purchase list contains an invalid product ID')
        pid=row['workno']
        if pid in seen:duplicates+=1;continue
        seen.add(pid);ids.append(pid)
    return ids,duplicates

def work_rows(data):
    if not isinstance(data,dict) or not isinstance(data.get('works'),list) or len(data['works'])>MAX_ITEMS:
        raise InventoryError('Purchase metadata response has an unexpected format')
    return data['works']

def collect(request,*,cancelled=lambda:False,progress=lambda done,total:None):
    """Protocol runner for an externally supplied, authorized JSON transport.

    request(method, relative_path, body) returns parsed JSON, or raises on any
    HTTP/authentication/challenge error. No transport is provided here. A future
    live transport must enforce host/TLS, bounded responses, timeouts and pacing.
    """
    def call(method,path,body=None):
        if cancelled():raise InventoryError('Purchase inventory collection cancelled')
        return request(method,path,body)
    count=call('GET',COUNT);count_value(count)
    sales=call('GET',SALES);ids,_=sales_ids(sales)
    rows=[];returned=set();progress(0,len(ids))
    for start in range(0,len(ids),100):
        batch=ids[start:start+100];response=call('POST',WORKS,batch)
        for row in work_rows(response):
            if not isinstance(row,dict) or row.get('workno') not in batch:
                raise InventoryError('Purchase metadata contains an unexpected product ID')
            if row['workno'] in returned:raise InventoryError('Purchase metadata repeats a product ID')
            returned.add(row['workno']);rows.append(row)
        progress(min(start+100,len(ids)),len(ids))
    if cancelled():raise InventoryError('Purchase inventory collection cancelled')
    # Project only product fields; never persist the original account/API objects.
    bundle={'format':FORMAT,'count':{'user':count['user']},
            'sales':[{'workno':row['workno']} for row in sales],
            'works':[project(row) for row in rows]}
    normalize(bundle)
    return bundle

def project(row):
    projected={'workno':row['workno']}
    kind=row.get('work_type')
    if isinstance(kind,str) and re.fullmatch(r'[A-Z0-9_]{1,32}',kind):projected['work_type']=kind
    if 'name' in row:projected['name']=title_value(row['name'])
    return projected

def title_value(value):
    if isinstance(value,dict):
        # The original Japanese title takes priority; do not guess a translation.
        value=next((value[k] for k in ('ja_JP','en_US') if isinstance(value.get(k),str) and value[k].strip()),'')
    if not isinstance(value,str):return ''
    value=value.strip()
    if len(value)>4096:raise InventoryError('Purchase title exceeds the size limit')
    return value

def normalize(bundle):
    if not isinstance(bundle,dict) or bundle.get('format')!=FORMAT:
        raise InventoryError('Use a Folio DLsite Play purchase inventory file')
    expected=count_value(bundle.get('count'))
    ids,duplicates=sales_ids(bundle.get('sales'))
    rows=bundle.get('works')
    if not isinstance(rows,list) or len(rows)>MAX_ITEMS:
        raise InventoryError('Purchase metadata response has an unexpected format')
    indexed={};allowed=set(ids)
    for row in rows:
        if not isinstance(row,dict) or not product_id(row.get('workno')) or row['workno'] not in allowed:
            raise InventoryError('Purchase metadata contains an unexpected product ID')
        if row['workno'] in indexed:raise InventoryError('Purchase metadata repeats a product ID')
        indexed[row['workno']]=project(row)
    items=[];review=[];excluded=[]
    for pid in ids:
        row=indexed.get(pid)
        if row is None:
            review.append({'id':pid,'reason':'metadata_missing'});continue
        name=title_value(row.get('name'));kind=row.get('work_type')
        if not pid.startswith(('RJ','BJ')):
            excluded.append({'id':pid,'title':name,'reason':'unsupported_product_family'});continue
        if not isinstance(kind,str) or not kind:
            review.append({'id':pid,'title':name,'reason':'work_type_missing'});continue
        if kind not in TYPES:
            # Codes that are not yet documented are review items, not presumed games.
            known={'ACN','ADV','QIZ','DNV','IMT','ET3','ETC','MUS','AMT','NRE','PBC','PZL','RPG','STG','SLN','TBL','TOL','TYP','MOV','SOU','VCM'}
            target=excluded if kind in known else review
            target.append({'id':pid,'title':name,'work_type':kind,'reason':'unsupported_work_type' if kind in known else 'unknown_work_type'});continue
        if not name:
            review.append({'id':pid,'reason':'title_missing'});continue
        items.append({'id':pid,'url':'https://play.dlsite.com/work/'+pid,'label':name,
                      'category':TYPES[kind] if TYPES[kind]=='artist cg' or pid.startswith('BJ') else 'doujinshi'})
    warnings=[]
    if expected!=len(ids):warnings.append('count_mismatch')
    if duplicates:warnings.append('duplicate_sales_ids')
    if review:warnings.append('items_need_review')
    return {'items':items,'review':review,'excluded':excluded,'warnings':warnings,
            'counts':{'expected':expected,'unique_ids':len(ids),'metadata':len(indexed),
                      'eligible':len(items),'review':len(review),'excluded':len(excluded),'duplicate_sales_ids':duplicates},
            'complete':expected==len(ids) and len(indexed)==len(ids)}

def bookmarks(result):
    """Existing Folio bookmark imports supply preview, duplicates and cross-site review."""
    if not result['items']:raise InventoryError('No eligible comics or CG illustrations to export')
    if not result['complete']:raise InventoryError('Purchase inventory is incomplete; resolve the count or missing metadata first')
    if result['review']:raise InventoryError('Purchase inventory needs review before export')
    lines=['<!DOCTYPE NETSCAPE-Bookmark-file-1>','<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
           '<TITLE>DLsite purchase links</TITLE>','<H1>DLsite purchase links</H1>','<DL><p>',
           '<DT><H3>DLsite purchases</H3>','<DL><p>']
    for item in result['items']:
        lines.append('<DT><A HREF="'+html.escape(item['url'],quote=True)+'">'+html.escape(item['label'])+'</A>')
    lines+=['</DL><p>','</DL><p>'];text='\n'.join(lines)+'\n'
    if len(text.encode('utf-8'))>MAX_BYTES:raise InventoryError('Purchase bookmark export exceeds 12 MB')
    return text
