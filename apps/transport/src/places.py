"""Worldwide address suggestions from Photon / OpenStreetMap (not Nominatim)."""
import os
from functools import lru_cache
from urllib.parse import urlencode
from routing import request

SOURCE='Photon / OpenStreetMap'
DOCS='https://github.com/komoot/photon/blob/master/docs/api-v1.md'

@lru_cache(maxsize=128)
def search(query):
    query=query.strip()
    if len(query)<3:return []
    endpoint=os.environ.get('FLOWERMOON_PHOTON_URL','https://photon.komoot.io').rstrip('/')
    data=request(endpoint+'/api/?'+urlencode(dict(q=query,limit=6,lang='en')))
    return feature_rows(data)

def feature_rows(data,prefer_address=False):
    rows=[]
    for feature in data.get('features',[]):
        p=feature.get('properties',{});coords=feature.get('geometry',{}).get('coordinates',[])
        if len(coords)!=2:continue
        address=' '.join(str(p.get(k,'')) for k in ('housenumber','street')).strip()
        bits=[None if prefer_address and address else p.get('name'),address,p.get('city') or p.get('town') or p.get('village'),p.get('county'),p.get('state'),p.get('postcode'),p.get('country')]
        label=', '.join(dict.fromkeys(str(v) for v in bits if v))
        if label:rows.append(dict(label=label,lat=float(coords[1]),lon=float(coords[0]),source=SOURCE,region=p.get('county') or p.get('state') or '',country=p.get('country','')))
    return rows

@lru_cache(maxsize=128)
def reverse(lat,lon):
    """Find a nearby mapped address; never move the user's selected point."""
    from site_environment.geography import validate
    from datetime import datetime,timezone
    validate(dict(lat=lat,lon=lon))
    endpoint=os.environ.get('FLOWERMOON_PHOTON_URL','https://photon.komoot.io').rstrip('/')
    result=feature_rows(request(endpoint+'/reverse?'+urlencode(dict(lat=lat,lon=lon,limit=1,lang='en',radius=1))),prefer_address=True)
    base=dict(source=SOURCE,sourceUrl=DOCS,requestedCoordinates=dict(lat=lat,lon=lon),retrievedAt=datetime.now(timezone.utc).isoformat())
    if not result:
        return dict(base,status='unavailable',detail='No mapped address was returned within 1 km. The selected coordinates are retained.')
    row=result[0]
    return dict(base,status='ready',label=row['label'],matchedCoordinates=dict(lat=row['lat'],lon=row['lon']),
                detail='Nearby mapped address from Photon / OpenStreetMap (search radius 1 km). The address can refer to a nearby feature; it is not a surveyed access point. Exact clicked coordinates are retained.\n'+DOCS)
