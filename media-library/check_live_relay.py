"""Verify a saved cover through the local relay; keep response bytes only in RAM."""
import hashlib
import json
from urllib.request import urlopen
import db

if __name__=='__main__':
    origin='http://localhost:8765'
    with db.transaction() as c:
        rows=c.execute("SELECT id FROM works WHERE owner=? AND (cover LIKE '%tn.hitomi.la/%' OR cover LIKE '%tn.gold-usergeneratedcontent.net/%')",(db.OWNER,)).fetchall()
    if not rows:
        raise SystemExit('No saved Hitomi cover available for live verification')
    url=origin+'/api/works/'+rows[0]['id']+'/cover'
    before={str(p) for folder in ('data','backups') for p in (db.ROOT/folder).rglob('*') if p.is_file()}
    with urlopen(url,timeout=45) as response:
        body=response.read(2*1024*1024+1)
        assert response.status==200 and response.headers['Content-Type'].startswith('image/')
        assert 'no-store' in response.headers['Cache-Control']
        assert 0<len(body)<=2*1024*1024
        mime=response.headers['Content-Type']; digest=hashlib.sha256(body).digest()
    with urlopen(url,timeout=45) as response:
        second=response.read(2*1024*1024+1)
        assert hashlib.sha256(second).digest()==digest
    after={str(p) for folder in ('data','backups') for p in (db.ROOT/folder).rglob('*') if p.is_file()}
    # Allow the normal background database backup/log files, but no image/temp files.
    unexpected=[p for p in after-before if not p.endswith(('.sqlite3','-wal','-shm','.log','.pid'))]
    assert not unexpected, 'Unexpected file creation during cover requests'
    print(json.dumps({'status':200,'type':mime,'bytes':len(body),'repeat_matches':True,'browser_cache':'no-store','new_image_files':0,'new_files':len(after-before)}))
