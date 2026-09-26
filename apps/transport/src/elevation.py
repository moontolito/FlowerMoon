"""Copernicus GLO-90 2021 public DSM tiles; never an unidentified DEM fallback."""
from pathlib import Path
from urllib.request import Request,urlopen
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib,json,math,threading,uuid,time
try:
    from PIL import Image
except ImportError:
    Image=None
from site_environment.geography import validate

SOURCE='Copernicus DEM GLO-90 · DSM 2021'
BASE='https://copernicus-dem-90m.s3.amazonaws.com/'
DOCS='https://registry.opendata.aws/copernicus-dem/'
CACHE=Path(__file__).resolve().parents[1]/'data'/'copernicus-dem-cache'
_lock=threading.Lock()

def tile_name(point):
    validate(point)
    lat=math.floor(min(point['lat'],89.999999999))
    lon=math.floor((point['lon']+180)%360-180)
    return f'Copernicus_DSM_COG_30_{"N" if lat>=0 else "S"}{abs(lat):02d}_00_{"E" if lon>=0 else "W"}{abs(lon):03d}_00_DEM'

def pixel(image,point):
    scale=image.tag_v2.get(33550);tie=image.tag_v2.get(33922);keys=image.tag_v2.get(34735,())
    codes={keys[i]:keys[i+3] for i in range(4,len(keys),4) if keys[i+1]==0}
    if not scale or not tie or codes.get(2048)!=4326 or codes.get(1025)!=2:
        raise ValueError('Copernicus: georeferențiere neașteptată.')
    lon=(point['lon']+180)%360-180
    # GeoTIFF RasterPixelIsPoint: tie point is the first sample centre.
    x=int(math.floor((lon-tie[3])/scale[0]+tie[0]+.5))
    y=int(math.floor((tie[4]-point['lat'])/scale[1]+tie[1]+.5))
    if not -1<=x<=image.width or not -1<=y<=image.height:raise ValueError('Coordonată în afara dalei DEM.')
    x=min(image.width-1,max(0,x));y=min(image.height-1,max(0,y))
    value=float(image.getpixel((x,y)))
    nodata=image.tag_v2.get(42113)
    if (nodata is not None and value==float(str(nodata).strip('\x00'))) or not math.isfinite(value) or not -500<=value<=9000:
        raise ValueError('Copernicus: valoare lipsă sau invalidă.')
    return value

def _tile(name,cache_dir):
    path=Path(cache_dir)/(name+'.tif');url=BASE+name+'/'+name+'.tif'
    with _lock:
        if not path.exists():
            request=Request(url,headers={'User-Agent':'FlowerMoonTransportSimple/1.0'})
            for attempt in range(3):
                try:
                    with urlopen(request,timeout=30) as response:raw=response.read(20*1024*1024+1)
                    break
                except OSError:
                    if attempt==2:raise
                    time.sleep(1)
            if len(raw)>20*1024*1024:raise ValueError('Copernicus: dală prea mare.')
            path.parent.mkdir(parents=True,exist_ok=True)
            temporary=path.with_suffix('.'+uuid.uuid4().hex+'.tmp');temporary.write_bytes(raw)
            with Image.open(temporary) as image:image.load()
            temporary.replace(path)
            metadata=dict(source=SOURCE,url=url,retrievedAt=datetime.now(timezone.utc).isoformat(timespec='seconds'),sha256=hashlib.sha256(raw).hexdigest())
            path.with_suffix('.json').write_text(json.dumps(metadata),encoding='utf-8')
    return path,url

def samples(points,cache_dir=None):
    if Image is None:
        return dict(values=[None]*len(points),source=SOURCE,sourceUrl=DOCS,tiles=[],
                    errors=['Biblioteca Pillow lipsește din Python-ul folosit la pornire. Instalați dependențele din requirements.txt.'],
                    unit='m',verticalDatum='EGM2008',complete=False)
    groups={};values=[None]*len(points);sources=[];errors=[]
    for i,point in enumerate(points):groups.setdefault(tile_name(point),[]).append((i,point))
    def read(group):
        name,items=group
        try:
            path,url=_tile(name,cache_dir or CACHE)
            with Image.open(path) as image:
                sampled=[(i,pixel(image,point)) for i,point in items]
            meta=json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
            return sampled,meta,None
        except Exception:
            # 404 is not proof of ocean; keep missing tiles explicitly unavailable.
            return [],None,f'Dală indisponibilă sau invalidă: {name}'
    with ThreadPoolExecutor(max_workers=4) as pool:
        for sampled,meta,error in pool.map(read,groups.items()):
            for i,value in sampled:values[i]=value
            if meta:sources.append(meta)
            if error:errors.append(error)
    return dict(values=values,source=SOURCE,sourceUrl=DOCS,tiles=sources,errors=errors,
                unit='m',verticalDatum='EGM2008',method='Nearest DSM sample; nominal 90 m, includes vegetation/buildings. Verify survey elevation.',
                complete=bool(points) and all(v is not None for v in values))
