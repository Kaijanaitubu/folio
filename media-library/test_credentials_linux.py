import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import nhentai_credentials as credentials

TEMP_ROOT=Path(__file__).resolve().parent/'test-output'
TEMP_ROOT.mkdir(exist_ok=True)

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    AESGCM = None

@unittest.skipIf(AESGCM is None, 'Optional cryptography package is unavailable')
class LinuxCredentials(unittest.TestCase):
    def test_authenticated_envelope_and_fresh_nonce(self):
        with patch.object(credentials, 'linux_master', return_value=b'a'*32):
            first = credentials.protect_linux(b'synthetic-test-key')
            second = credentials.protect_linux(b'synthetic-test-key')
            self.assertNotEqual(first, second)
            self.assertNotIn(b'synthetic-test-key', first)
            self.assertEqual(credentials.protect_linux(first, True), b'synthetic-test-key')
            with self.assertRaises(ValueError): credentials.protect_linux(first[:-1]+bytes([first[-1]^1]), True)
            with self.assertRaises(ValueError): credentials.protect_linux(b'bad-format', True)
        with patch.object(credentials, 'linux_master', return_value=b'b'*32):
            with self.assertRaises(ValueError): credentials.protect_linux(first, True)

    def test_missing_or_invalid_master_is_rejected(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError): credentials.linux_master()
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory, patch.dict(os.environ, {'CREDENTIALS_DIRECTORY':directory}):
            path=Path(directory)/'folio-nhentai-master'
            path.write_bytes(b'a'*33)
            with self.assertRaises(ValueError): credentials.linux_master()
            path.write_bytes(b'a'*32)
            self.assertEqual(credentials.linux_master(), b'a'*32)

    @unittest.skipIf(os.name == 'nt', 'Linux runtime integration')
    def test_remember_reload_permissions_and_forget(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            master=Path(directory)/'folio-nhentai-master'; master.write_bytes(b'a'*32)
            path=Path(directory)/'private'/'key.aesgcm'
            with patch.dict(os.environ, {'CREDENTIALS_DIRECTORY':directory, 'FOLIO_KEY_FILE':str(path)}), patch.object(credentials,'PATH',path), patch.object(credentials,'_key',''):
                self.assertTrue(credentials.set_key('synthetic-test-key',True)['remembered'])
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                credentials._key=''
                self.assertEqual(credentials.get(),'synthetic-test-key')
                credentials.forget(); self.assertFalse(path.exists())

if __name__ == '__main__': unittest.main()
