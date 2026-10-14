import importlib.util
from contextlib import closing
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import db

spec=importlib.util.spec_from_file_location('cloud_backup',Path(__file__).parent/'deploy/linux/cloud_backup.py')
backup=importlib.util.module_from_spec(spec);spec.loader.exec_module(backup)

class CloudBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=db.ROOT/'test-output')
        self.root=Path(self.temp.name)
        self.path=patch.object(db,'PATH',self.root/'library.sqlite3');self.path.start()
        self.env=patch.dict(os.environ,{'MEDIA_BACKUPS':str(self.root/'backups'),'FOLIO_BACKUP_REMOTE':'test:dedicated-backups'});self.env.start()
        db.init()
        with db.transaction() as c: db.save_work(c,{'title':'Synthetic backup','tag':[{'name':'synthetic-tag','gender':'neutral'}]})
    def tearDown(self):
        self.env.stop();self.path.stop();self.temp.cleanup()
    def test_snapshot_with_expression_indexes_and_download_verification(self):
        with patch.object(backup.subprocess,'run') as run:
            backup.main()
        calls=run.call_args_list
        self.assertEqual([c.args[0][1] for c in calls],['copyto','check'])
        self.assertIn('--download',calls[1].args[0])
        status=json.loads((self.root/'backups/last-cloud-backup.json').read_text())
        self.assertTrue(status['verified'])
        with closing(db.connect(self.root/'backups'/status['snapshot'])) as connection:
            self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(connection.execute('SELECT count(*) FROM works').fetchone()[0],1)
    def test_upload_failure_does_not_report_success(self):
        with patch.object(backup.subprocess,'run',side_effect=subprocess.CalledProcessError(1,['rclone'])):
            with self.assertRaises(subprocess.CalledProcessError): backup.main()
        self.assertFalse((self.root/'backups/last-cloud-backup.json').exists())

if __name__=='__main__': unittest.main()
