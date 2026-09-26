"""Offline, generalized geographic screening; never legal boundary evidence."""
import json
import math
from pathlib import Path
from functools import lru_cache

ROOT=Path(__file__).resolve().parents[2]/'assets'/'geography'
SOURCE='Natural Earth 1:50m · snapshot 2026-09-26'
COUNTRY_SOURCE='Natural Earth 1:10m · snapshot 2026-09-26'
SOURCE_URL='https://www.naturalearthdata.com/'
BOUNDARY_MARGIN_M=2000  # Own screening tolerance for generalized polygons.

@lru_cache(maxsize=1)
def dataset_manifest():
    try:return {entry['file']:entry for entry in json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))}
    except (OSError,ValueError,KeyError):return {}

def validate(point):
    lat,lon=point['lat'],point['lon']
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (lat,lon)) or not -90<=lat<=90 or not -180<=lon<=180:
        raise ValueError('Invalid geographic coordinates.')
    return lat,lon

def inside(x,y,ring):
    found=False
    for (ax,ay),(bx,by) in zip(ring,ring[1:]):
        if (ay>y)!=(by>y) and x<(bx-ax)*(y-ay)/(by-ay)+ax:found=not found
    return found

def segment_distance(point,a,b):
    """Spherical cross-track / endpoint distance, metres; application GIS method."""
    lat,lon=point
    def angular(p,q):
        x,y=map(math.radians,p);u,v=map(math.radians,q)
        h=math.sin((u-x)/2)**2+math.cos(x)*math.cos(u)*math.sin((v-y)/2)**2
        return 2*math.asin(math.sqrt(min(1,max(0,h))))
    def bearing(p,q):
        x,y=map(math.radians,p);u,v=map(math.radians,q)
        return math.atan2(math.sin(v-y)*math.cos(u),math.cos(x)*math.sin(u)-math.sin(x)*math.cos(u)*math.cos(v-y))
    start=(a[1],a[0]);end=(b[1],b[0]);p=(lat,lon)
    length=angular(start,end);delta=angular(start,p)
    direction=bearing(start,p)-bearing(start,end)
    along=math.atan2(math.sin(delta)*math.cos(direction),math.cos(delta))
    if length<1e-12 or not 0<=along<=length:return min(delta,angular(end,p))*6371000
    return abs(math.asin(max(-1,min(1,math.sin(delta)*math.sin(direction)))))*6371000

@lru_cache(maxsize=1)
def countries():
    data=json.loads((ROOT/'countries_10m.geojson').read_text(encoding='utf-8'))
    result=[]
    for feature in data['features']:
        prop=feature['properties'];geo=feature['geometry']
        polygons=geo['coordinates'] if geo['type']=='MultiPolygon' else [geo['coordinates']]
        for polygon in polygons:
            xs,ys=zip(*polygon[0])
            result.append((prop,polygon,(min(xs),min(ys),max(xs),max(ys))))
    return result

@lru_cache(maxsize=256)
def _country(lat,lon):
    result=dict(code=None,name=None,status='unavailable',source=COUNTRY_SOURCE,sourceUrl=SOURCE_URL,
                method='point-in-polygon-v1',methodStatus='geographic_estimate',nearBoundary=False,
                detail='Generalized boundaries do not establish legal jurisdiction. Small islands and disputed areas require verification.',dataset=dataset_manifest().get('countries_10m.geojson',{}))
    try:
        hits=[]
        for prop,polygon,(west,south,east,north) in countries():
            if west<=lon<=east and south<=lat<=north and inside(lon,lat,polygon[0]) and not any(inside(lon,lat,r) for r in polygon[1:]):
                distance=min(segment_distance((lat,lon),a,b) for ring in polygon for a,b in zip(ring,ring[1:]))
                hits.append((prop,distance))
        if len(hits)==1:
            prop,distance=hits[0];code=prop.get('ISO_A2_EH') or prop.get('ISO_A2')
            if code=='-99':code=None
            # Coastline is a polygon edge too; proximity to the sea alone must
            # not disable a country's inland zoning adapter.
            adjacent=[]
            if distance<=BOUNDARY_MARGIN_M:
                dy=BOUNDARY_MARGIN_M/110000;dx=dy/max(.001,math.cos(math.radians(lat)))
                for other,rings,(west,south,east,north) in countries():
                    other_code=other.get('ISO_A2_EH') or other.get('ISO_A2')
                    if other_code!=code and west-dx<=lon<=east+dx and south-dy<=lat<=north+dy:
                        if min(segment_distance((lat,lon),a,b) for r in rings for a,b in zip(r,r[1:]))<=BOUNDARY_MARGIN_M:adjacent.append(other_code or 'UNCONFIRMED')
            result.update(code=code,iso3=prop.get('ISO_A3_EH') or prop.get('ISO_A3') or prop.get('ADM0_A3'),name=prop.get('ADMIN'),status='estimated',nearBoundary=bool(adjacent),boundaryDistanceM=distance,nearOtherCountries=sorted(set(adjacent)))
        elif hits:result.update(status='ambiguous',detail='Overlapping polygons; jurisdiction requires confirmation.')
        else:result['detail']='Ocean, unmapped island or area outside coverage; country is not assumed.'
    except (OSError,ValueError,KeyError):result['detail']='The local geographic dataset is unavailable.'
    return result

def country(point):
    lat,lon=validate(point)
    return dict(_country(lat,lon))

@lru_cache(maxsize=1)
def coastlines():
    data=json.loads((ROOT/'coastline.geojson').read_text(encoding='utf-8'))
    lines=[]
    for f in data['features']:
        g=f['geometry'];lines.extend(g['coordinates'] if g['type']=='MultiLineString' else [g['coordinates']])
    return lines

@lru_cache(maxsize=256)
def _coast(lat,lon):
    try:
        distance=min(segment_distance((lat,lon),a,b) for line in coastlines() for a,b in zip(line,line[1:]))
        return dict(value=round(distance/1000,3),unit='km',source=SOURCE,sourceUrl=SOURCE_URL,status='estimated',
                    method='spherical-nearest-coast-segment-v1',methodStatus='geographic_estimate',
                    detail='Spherical distance to generalized coastline segments, R=6371000 m. Does not measure salinity or determine an ISO category; accuracy is limited by the 1:50m source scale.',dataset=dataset_manifest().get('coastline.geojson',{}))
    except (OSError,ValueError,KeyError):return dict(value=None,unit='km',status='unavailable',source=SOURCE,detail='Global coastline data is unavailable.')

def coast(point):
    return dict(_coast(*validate(point)))
