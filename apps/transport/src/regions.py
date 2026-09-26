"""ADM1 delivery-region boundaries from geoBoundaries gbOpen, cached by country."""
import json,os,time,uuid
from pathlib import Path
from urllib.request import Request,urlopen
from site_environment.geography import country,inside,validate

SOURCE='geoBoundaries gbOpen · ADM1'

def read_json(url):
    if not url.startswith('https://'):raise ValueError('Boundary source must use HTTPS')
    with urlopen(Request(url,headers={'User-Agent':'FlowerMoonTransport/2.0'}),timeout=35) as response:
        data=response.read(30_000_001)
        if len(data)>30_000_000:raise ValueError('Boundary dataset exceeds the download limit')
        return json.loads(data)

def ring_contains(lon,lat,ring):
    if len(ring)<4:return False
    anchor=ring[0][0];x=anchor+(lon-anchor+180)%360-180
    points=[(anchor+(p[0]-anchor+180)%360-180,p[1]) for p in ring]
    return inside(x,lat,points)

def contains(geometry,point):
    polygons=[geometry['coordinates']] if geometry.get('type')=='Polygon' else geometry.get('coordinates',[]) if geometry.get('type')=='MultiPolygon' else []
    return any(ring_contains(point['lon'],point['lat'],p[0]) and not any(ring_contains(point['lon'],point['lat'],h) for h in p[1:]) for p in polygons if p)

def lookup(point,cache):
    validate(point);geo=country(point);code=geo.get('iso3')
    if not code or len(code)!=3 or not code.isalpha():return dict(status='unavailable',name='',source=SOURCE,detail='Country boundary is not available for this destination.')
    endpoint=os.environ.get('FLOWERMOON_BOUNDARIES_URL','https://www.geoboundaries.org/api/current/gbOpen').rstrip('/')+'/'+code+'/ADM1/'
    path=Path(cache)/(code+'-ADM1.json');payload=None
    if path.exists() and time.time()-path.stat().st_mtime<30*86400:
        try:payload=json.loads(path.read_text(encoding='utf-8'))
        except (ValueError,OSError):pass
    if payload is None:
        metadata=read_json(endpoint)
        if not isinstance(metadata,dict) or not metadata.get('simplifiedGeometryGeoJSON'):raise ValueError('No ADM1 dataset is available for this country')
        data=read_json(metadata['simplifiedGeometryGeoJSON'])
        payload=dict(metadata=metadata,data=data)
        path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.'+uuid.uuid4().hex+'.tmp')
        temp.write_text(json.dumps(payload),encoding='utf-8');temp.replace(path)
    matches=[f for f in payload['data'].get('features',[]) if contains(f.get('geometry',{}),point)]
    if len(matches)!=1:return dict(status='unavailable',name='',source=SOURCE,detail='No unique administrative polygon contains the destination.')
    feature=matches[0];meta=payload['metadata']
    return dict(status='ready',name=feature['properties'].get('shapeName') or 'Administrative region',level='ADM1',geometry=feature['geometry'],
                country=geo['name'],source=SOURCE,sourceUrl=endpoint,originalSource=meta.get('boundarySource',''),year=meta.get('boundaryYearRepresented',''),
                license=meta.get('boundaryLicense',''),requestedCoordinates=dict(point),detail='First-level administrative boundary containing the delivery point. Boundary coverage and names vary by country.')
