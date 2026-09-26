"""Worldwide address suggestions from Photon / OpenStreetMap (not Nominatim)."""
import os
from functools import lru_cache
from urllib.parse import urlencode
from routing import request

SOURCE='Photon / OpenStreetMap'

@lru_cache(maxsize=128)
def search(query):
    query=query.strip()
    if len(query)<3:return []
    endpoint=os.environ.get('FLOWERMOON_PHOTON_URL','https://photon.komoot.io').rstrip('/')
    data=request(endpoint+'/api/?'+urlencode(dict(q=query,limit=6,lang='en')))
    rows=[]
    for feature in data.get('features',[]):
        p=feature.get('properties',{});coords=feature.get('geometry',{}).get('coordinates',[])
        if len(coords)!=2:continue
        address=' '.join(str(p.get(k,'')) for k in ('housenumber','street')).strip()
        bits=[p.get('name'),address,p.get('city') or p.get('town') or p.get('village'),p.get('county'),p.get('state'),p.get('postcode'),p.get('country')]
        label=', '.join(dict.fromkeys(str(v) for v in bits if v))
        if label:rows.append(dict(label=label,lat=float(coords[1]),lon=float(coords[0]),source=SOURCE,region=p.get('county') or p.get('state') or '',country=p.get('country','')))
    return rows
