"""User-triggered public-service requests. No API key, no silent car fallback."""
import os
import json
import time
import threading
from urllib.request import Request,urlopen
from urllib.parse import urlencode,urlparse
from urllib.error import HTTPError,URLError
from domain import parse_response

AGENT='FlowerMoonTransportSimple/1.0 (personal desktop planner)'
_lock=threading.Lock();_last=0
def request(url,payload=None):
    global _last
    with _lock:
        time.sleep(max(0,1.1-(time.monotonic()-_last)))
        _last=time.monotonic()
        headers={'User-Agent':AGENT,'X-Client-Id':'flowermoon-transport-personal','Accept':'application/json'}
        if payload is not None:headers['Content-Type']='application/json'
        req=Request(url,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
        try:
            with urlopen(req,timeout=45) as response:return json.load(response)
        except HTTPError as e:
            if e.code==429:raise ValueError('Serviciul public a limitat cererile. Încercați mai târziu sau configurați un server propriu.') from None
            raise ValueError(f'Serviciul a răspuns HTTP {e.code}. Nicio rută nu a fost salvată.') from None
        except (URLError,TimeoutError,OSError):raise ValueError('Conexiune indisponibilă. Verificați internetul și permisiunile de rețea.') from None

def route(server,payload):
    parsed=urlparse(server)
    if parsed.scheme not in ('http','https') or not parsed.netloc or parsed.username or parsed.password:raise ValueError('Adresa serverului Valhalla nu este validă.')
    if parsed.scheme=='http' and parsed.hostname not in ('localhost','127.0.0.1'):raise ValueError('Folosiți HTTPS pentru servere externe.')
    return parse_response(request(server.rstrip('/')+'/route',payload))

def geocode(query):
    if len(query.strip())<3:raise ValueError('Introduceți localitatea sau adresa (minimum trei caractere).')
    endpoint=os.environ.get('FLOWERMOON_GEOCODER_URL','https://nominatim.openstreetmap.org').rstrip('/')
    rows=request(endpoint+'/search?'+urlencode({'q':query,'format':'jsonv2','addressdetails':1,'limit':5}))
    return [{'label':r['display_name'],'lat':float(r['lat']),'lon':float(r['lon'])} for r in rows]
