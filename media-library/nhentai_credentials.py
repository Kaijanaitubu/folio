"""API keys live in RAM or an optional Windows-user DPAPI envelope, never SQLite."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import threading

PATH = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Folio' / 'nhentai-api-key.dpapi'
_lock = threading.RLock()
_key = ''

class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]

def protect(raw, decrypt=False):
    if os.name != 'nt': raise ValueError('Remembering an API key requires Windows')
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
            try: _key = validate(protect(PATH.read_bytes(), decrypt=True).decode('utf-8'))
            except (ValueError, OSError, UnicodeError): return ''
        return _key

def status():
    return {'connected': bool(get()), 'remembered': PATH.is_file(), 'can_remember': os.name == 'nt'}

def set_key(value, remember=False):
    global _key
    value = validate(value)
    with _lock:
        if remember:
            encrypted = protect(value.encode('utf-8'))
            PATH.parent.mkdir(parents=True, exist_ok=True)
            temporary = PATH.with_suffix('.tmp')
            temporary.write_bytes(encrypted)
            temporary.replace(PATH)
        else: PATH.unlink(missing_ok=True)
        _key = value
    return status()

def forget():
    global _key
    with _lock:
        PATH.unlink(missing_ok=True)
        _key = ''
    return status()
