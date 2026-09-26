"""Point-in-polygon lookup in the public UTCB maps linked by Encipedia.

No nearest-town substitutions or interpolation across zoning boundaries.
KML polygon holes and MultiGeometry are retained. Values remain informational.
"""
from functools import lru_cache
from pathlib import Path
import math
import re
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]/'assets'/'zoning'
NS={'k':'http://www.opengis.net/kml/2.2'}
MAPS={
 'seismic.ag':('ag','ag','g','P100-1/2013'),
 'seismic.tc':('tc','Tc','s','P100-1/2013'),
 'snow.sk':('snow','sk','kN/m²','CR 1-1-3/2012'),
 'wind.qb':('wind','qb','kPa','CR 1-1-4/2012'),
}
BOUNDARY_MARGIN_M=250  # Application screening tolerance, not a code requirement.

def ring(text):
    points=[tuple(float(v) for v in row.split(',')[:2]) for row in text.split()]
    if len(points)<3:raise ValueError('Invalid polygon')
    if points[0]!=points[-1]:points.append(points[0])
    return points

@lru_cache(maxsize=4)
def load_map(kind):
    document=ET.parse(ROOT/(kind+'.kml'));zones=[]
    for mark in document.findall('.//k:Placemark',NS):
        description=mark.findtext('k:description','',NS)
        match=re.search(r'(ag|Tc|sk|qb)\s*(=|≥|>=)\s*([\d.,]+)',description)
        if not match:continue
        value=float(match[3].replace(',','.'));operator=match[2]
        for polygon in mark.findall('.//k:Polygon',NS):
            outer=ring(polygon.findtext('k:outerBoundaryIs/k:LinearRing/k:coordinates','',NS))
            holes=[ring(el.text or '') for el in polygon.findall('k:innerBoundaryIs/k:LinearRing/k:coordinates',NS)]
            xs,ys=zip(*outer)
            zones.append(dict(value=value,operator=operator,description=description,outer=outer,holes=holes,bounds=(min(xs),min(ys),max(xs),max(ys))))
    if not zones:raise ValueError('No zoning polygons')
    return zones

def inside(x,y,points):
    result=False
    for (ax,ay),(bx,by) in zip(points,points[1:]):
        if ((ay>y)!=(by>y)) and x<(bx-ax)*(y-ay)/(by-ay)+ax:result=not result
    return result

def edge_distance(x,y,points):
    # Local equirectangular projection is sufficient for this short-distance flag.
    sx=111320*math.cos(math.radians(y));sy=111320
    best=math.inf
    for (ax,ay),(bx,by) in zip(points,points[1:]):
        ax,ay=(ax-x)*sx,(ay-y)*sy;bx,by=(bx-x)*sx,(by-y)*sy
        dx,dy=bx-ax,by-ay;length=dx*dx+dy*dy
        t=max(0,min(1,-(ax*dx+ay*dy)/length)) if length else 0
        best=min(best,math.hypot(ax+t*dx,ay+t*dy))
    return best

def lookup(destination,altitude=None):
    x,y=destination['lon'],destination['lat'];result={}
    for key,(kind,param,unit,standard) in MAPS.items():
        source=f'UTCB / CCERS via Encipedia · {standard} · KML snapshot 2026-09-25'
        item=dict(value=None,source=source,status='VERIFY',unit=unit,operator='=',detail='',candidates=[],candidateValues=[],candidateValue=None,applicability='map_unverified',standard=standard,jurisdiction='RO')
        try:
            zones=load_map(kind);hits=[];near=[]
            for zone in zones:
                left,bottom,right,top=zone['bounds']
                if not left-.004<=x<=right+.004 or not bottom-.004<=y<=top+.004:continue
                contained=inside(x,y,zone['outer']) and not any(inside(x,y,h) for h in zone['holes'])
                if contained:hits.append(zone)
                if min(edge_distance(x,y,r) for r in [zone['outer'],*zone['holes']])<=BOUNDARY_MARGIN_M:near.append(zone)
            choices={(z['value'],z['operator']) for z in hits}
            item['candidates']=sorted({z['description'] for z in hits+near})
            item['candidateValues']=[dict(value=value,operator=operator) for value,operator in sorted({(z['value'],z['operator']) for z in hits+near})]
            if len(choices)==1:
                item['value'],item['operator']=next(iter(choices))
                item['detail']='Value from the UTCB polygon containing the destination; informational map.'
                if near:item['detail']+=' Close to the zone boundary (≤250 m): verify the applicable zone.'
            elif len(choices)>1:item['detail']='Overlapping polygons with different values; verify the applicable zone.'
            else:item['detail']='The point is outside the published polygons; no value is assumed.'
            if key.startswith(('snow.','wind.')):
                if altitude is None:item['detail']+=' Applicability below 1000 m has not yet been checked.'
                elif altitude>=1000:
                    item['candidateValue']=item['value'];item['applicability']='unverified_at_altitude'
                    item['detail']+=' Destination altitude ≥1000 m. The displayed map value requires a site-specific applicability check.'
            item['nearBoundary']=bool(near)
        except (OSError,ValueError,ET.ParseError) as error:item['detail']='Zoning source unavailable: '+str(error)
        result[key]=item
    return result
