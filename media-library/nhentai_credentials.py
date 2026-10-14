"""API keys live in RAM or an optional encrypted envelope, never SQLite."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import threading
import secrets

PATH = Path(os.environ['FOLIO_KEY_FILE']) if os.environ.get('FOLIO_KEY_FILE') else Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Folio' / 'nhentai-api-key.dpapi'
_lock = threading.RLock()
_key = ''
LINUX_HEADER = b'Folio-nhentai-key-v1\x00'

def linux_master():
    directory = os.environ.get('CREDENTIALS_DIRECTORY')
    if not directory: raise ValueError('Encrypted key storage is not configured on this server')
    with (Path(directory) / 'folio-nhentai-master').open('rb') as stream:
        key = stream.read(33)
    if len(key) != 32: raise ValueError('Invalid server key storage configuration')
    return key

def protect_linux(raw, decrypt=False):
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.exceptions import InvalidTag
    except ImportError as e:
        raise ValueError('Encrypted key storage requires the cryptography package') from e
    cipher = AESGCM(linux_master())
    if not decrypt:
        nonce = secrets.token_bytes(12)
        return LINUX_HEADER + nonce + cipher.encrypt(nonce, raw, LINUX_HEADER)
    if not raw.startswith(LINUX_HEADER) or len(raw) < len(LINUX_HEADER) + 28:
        raise ValueError('Invalid encrypted API key')
    offset = len(LINUX_HEADER)
    try: return cipher.decrypt(raw[offset:offset+12], raw[offset+12:], LINUX_HEADER)
    except InvalidTag as e: raise ValueError('Server could not unlock the saved API key') from e

def can_remember():
    if os.name == 'nt': return True
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        linux_master()
        return bool(os.environ.get('FOLIO_KEY_FILE'))
    except (ImportError, ValueError, OSError): return False

class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]

def protect(raw, decrypt=False):
    if os.name != 'nt': return protect_linux(raw, decrypt)
    buffer = ctypes.create_string_buffer(raw)
    source = Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ValueError('Windows could not protect or unlock the saved API key')
    try: return ctypes.string_at(target.data, target.size)
    finally: kernel.LocalFree(ctypes.cast(target.data, ctypes.c_void_p))

def validate(value):
    value = str(value or '').strip()
    if not value or len(value) > 512 or any(ord(ch) < 33 or ord(ch) > 126 for ch in value):
        raise ValueError('Enter a valid nhentai API key')
    return value

def get():
    global _key
    with _lock:
        if not _key and PATH.is_file():
            try:
                with PATH.open('rb') as stream: encrypted = stream.read(4097)
                if len(encrypted) > 4096: return ''
                _key = validate(protect(encrypted, decrypt=True).decode('utf-8'))
            except (ValueError, OSError, UnicodeError): return ''
        return _key

def status():
    return {'connected': bool(get()), 'remembered': PATH.is_file(), 'can_remember': can_remember()}

def set_key(value, remember=False):
    global _key
    value = validate(value)
    with _lock:
        if remember:
            if not can_remember(): raise ValueError('Encrypted key storage is not configured on this server')
            encrypted = protect(value.encode('utf-8'))
            PATH.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            temporary = PATH.with_name(PATH.name + '.' + secrets.token_hex(8) + '.tmp')
            try:
                descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(encrypted); stream.flush(); os.fsync(stream.fileno())
                temporary.replace(PATH)
            finally: temporary.unlink(missing_ok=True)
        else: PATH.unlink(missing_ok=True)
        _key = value
    return status()

def forget():
    global _key
    with _lock:
        PATH.unlink(missing_ok=True)
        _key = ''
    return status()
