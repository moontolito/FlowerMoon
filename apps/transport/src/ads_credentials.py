"""ADS credentials: Windows user-bound encryption, never project data."""
import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path

ENDPOINT = 'https://ads.atmosphere.copernicus.eu/api'

def secret_path():
    return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData'/'Local')))/'FlowerMoon'/'Secrets'/'ads.json'

def crypt(data, decrypt=False):
    if os.name != 'nt':
        raise ValueError('Use FLOWERMOON_ADS_KEY on this operating system.')
    class Blob(ctypes.Structure):
        _fields_=[('length',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
    buf=ctypes.create_string_buffer(data)
    source=Blob(len(data),ctypes.cast(buf,ctypes.POINTER(ctypes.c_ubyte)));output=Blob()
    lib=ctypes.WinDLL('crypt32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    fn=lib.CryptUnprotectData if decrypt else lib.CryptProtectData
    fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p if decrypt else wintypes.LPCWSTR,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    fn.restype=wintypes.BOOL
    if not fn(ctypes.byref(source),None if decrypt else 'FlowerMoon ADS',None,None,None,1,ctypes.byref(output)):
        raise ValueError('ADS credential could not be read with this Windows account.')
    try:return ctypes.string_at(output.data,output.length)
    finally:kernel.LocalFree(output.data)

def save_key(key):
    if not key.strip():raise ValueError('ADS key is empty.')
    target=secret_path();target.parent.mkdir(parents=True,exist_ok=True)
    payload=dict(protection='Windows DPAPI current user',keyEncrypted=base64.b64encode(crypt(key.strip().encode())).decode())
    target.write_text(json.dumps(payload,indent=2),encoding='utf-8')

def configuration():
    key=os.environ.get('FLOWERMOON_ADS_KEY','').strip()
    if not key and os.name=='nt' and secret_path().is_file():
        try:key=crypt(base64.b64decode(json.loads(secret_path().read_text())['keyEncrypted']),True).decode()
        except Exception:raise ValueError('ADS credentials are unavailable for this Windows account.') from None
    if not key:raise ValueError('ADS access is not configured on this computer.')
    return ENDPOINT,key

def configured():
    return bool(os.environ.get('FLOWERMOON_ADS_KEY','').strip()) or (os.name=='nt' and secret_path().is_file())
