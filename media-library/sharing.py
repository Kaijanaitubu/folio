"""Owner-managed, versioned publication snapshots; no live library projection."""
import json,os,secrets
import db,marks

def init(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS shared_pages(token TEXT PRIMARY KEY,owner TEXT NOT NULL,work_id TEXT NOT NULL,created TEXT NOT NULL,revoked TEXT,schema_version INTEGER NOT NULL DEFAULT 1,visibility TEXT NOT NULL DEFAULT 'unlisted',update_mode TEXT NOT NULL DEFAULT 'snapshot',payload TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS shared_pages_work ON shared_pages(owner,work_id);
    CREATE TRIGGER IF NOT EXISTS revoke_deleted_shares AFTER DELETE ON works BEGIN UPDATE shared_pages SET revoked=COALESCE(revoked,datetime('now')) WHERE work_id=OLD.id; END;
    CREATE TRIGGER IF NOT EXISTS revoke_trashed_shares AFTER UPDATE OF deleted_at ON works WHEN NEW.deleted_at IS NOT NULL BEGIN UPDATE shared_pages SET revoked=COALESCE(revoked,datetime('now')) WHERE work_id=NEW.id; END;
    """)

def base():return os.environ.get('FOLIO_SHARE_BASE','').rstrip('/')
def snapshot(c,wid,options):
    if not isinstance(options,dict) or set(options)-{'ratings','review','marks','language'}:raise ValueError('Invalid share options')
    if any(type(options[k]) is not bool for k in options if k!='language'):raise ValueError('Invalid share options')
    w=db.get_work(c,wid)
    out={k:w[k] for k in ('title','cover','category','language','pages')}
    out['ui_language']='ja' if options.get('language')=='ja' else 'en'
    for k in ('author','circle','series','character','tag'):
        out[k]=[{'name':e.get('display_name') or e['name'],'gender':e.get('gender','neutral')} for e in w[k]]
    out['links']=[{k:l[k] for k in ('url','label','is_primary')} for l in w['links']]
    out['ratings']=[{'name':d['name'],'number':d['number'],'symbol':d['symbol'],'maximum':d['maximum'],'value':w['ratings'][d['id']]} for d in db.dimensions(c) if d['id'] in w['ratings']] if options.get('ratings',True) else []
    out['review']=w['review'] if options.get('review',True) else ''
    out['marks']=[{'label':d['label'] or 'Mark '+str(d['number']),'symbol':d['on']} for d in marks.definitions(c) if d['number'] in w['marks']] if options.get('marks',True) else []
    return out

def list_pages(c,wid):
    db.get_work(c,wid)
    return {'base':base(),'items':[dict(r,url=base()+'/s/'+r['token'] if base() else '') for r in c.execute('SELECT token,created,revoked FROM shared_pages WHERE owner=? AND work_id=? AND revoked IS NULL ORDER BY created DESC',(db.OWNER,wid))]}

def create(c,wid,data):
    if not base():raise ValueError('Public sharing URL is not configured yet')
    if not c.in_transaction:c.execute('BEGIN IMMEDIATE')
    preview=snapshot(c,wid,data.get('options',{}))
    if data.get('expected_updated')!=db.get_work(c,wid)['updated']:raise ValueError('Entry changed; reopen sharing before publishing')
    if c.execute('SELECT count(*) FROM shared_pages WHERE owner=? AND work_id=? AND revoked IS NULL',(db.OWNER,wid)).fetchone()[0]>=20:raise ValueError('Revoke an existing share before creating another')
    token=secrets.token_urlsafe(24)
    c.execute('INSERT INTO shared_pages(token,owner,work_id,created,payload) VALUES(?,?,?,?,?)',(token,db.OWNER,wid,db.now(),json.dumps(preview,ensure_ascii=False)))
    return {'url':base()+'/s/'+token,'token':token}

def revoke(c,wid,token):
    db.get_work(c,wid)
    if not c.execute('UPDATE shared_pages SET revoked=COALESCE(revoked,?) WHERE owner=? AND work_id=? AND token=?',(db.now(),db.OWNER,wid,token)).rowcount:raise ValueError('Shared page not found')
    return {'ok':True}
