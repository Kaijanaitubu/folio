"""Upload a consistent DB snapshot; never sync live SQLite or credential files."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import db

def main():
    remote=os.environ.get('FOLIO_BACKUP_REMOTE','').rstrip('/')
    if not remote or ':' not in remote: raise ValueError('Configure FOLIO_BACKUP_REMOTE')
    snapshot=db.backup()
    connection=db.connect(snapshot)
    try:
        if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Snapshot integrity check failed')
        if connection.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('Snapshot contains invalid references')
    finally: connection.close()
    destination=remote+'/'+snapshot.name
    # Copy only one snapshot, without deleting or syncing any destination files.
    subprocess.run(['rclone','copyto',str(snapshot),destination,'--retries','3','--contimeout','20s','--timeout','2m'],check=True,timeout=600)
    # Check the remote bytes, not merely that a filename was created.
    subprocess.run(['rclone','check',str(snapshot.parent),remote,'--include',snapshot.name,'--one-way','--download'],check=True,timeout=240)
    status={'snapshot':snapshot.name,'size':snapshot.stat().st_size,'verified':True,'uploaded_at':db.now()}
    path=snapshot.parent/'last-cloud-backup.json'
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(status),encoding='utf-8'); temporary.replace(path)
    print(json.dumps(status))

if __name__=='__main__': main()
