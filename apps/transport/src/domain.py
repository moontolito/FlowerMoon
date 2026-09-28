"""Small, explicit product-to-vehicle model. Units: metres, metric tonnes, km."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import json
import math
import uuid

def stamp():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def num(value,label,minimum=0,integer=False):
    try:n=float(str(value).strip().replace(',','.'))
    except (ValueError,TypeError):raise ValueError(f'{label}: enter a number.') from None
    if not math.isfinite(n) or n<minimum or (integer and n!=int(n)):raise ValueError(f'{label}: invalid value (minimum {minimum:g}).')
    return int(n) if integer else n

def product(data):
    p={k:num(data.get(k),label,.001) for k,label in [('length','Length'),('width','Width'),('height','Height'),('weight','Weight')]}
    p['name']=str(data.get('name','')).strip()
    if not p['name']:raise ValueError('Enter a product name.')
    p['quantity']=num(data.get('quantity'),'Quantity',1,True)
    return p

VEHICLE_FIELDS=[('name','Profile name'),('deck_length','Usable deck length (m)'),('load_width','Permitted load width (m)'),('deck_height','Deck height above ground (m)'),('length','Total vehicle length (m)'),('width','Vehicle width (m)'),('height','Empty vehicle height (m)'),('tare','Tare weight, including securing (t)'),('payload','Payload (t)'),('gross','Maximum technical gross weight (t)'),('axle_count','Axle count'),('axle_load','Maximum loaded axle weight (t)')]

def vehicle(data):
    v=deepcopy(data)
    if not str(v.get('name','')).strip():raise ValueError('Enter a vehicle name.')
    for k,label in VEHICLE_FIELDS[1:]:v[k]=num(v.get(k),label,.001,k=='axle_count')
    if v['deck_length']>v['length']:raise ValueError('Usable deck length cannot exceed total vehicle length.')
    if v['tare']>=v['gross']:raise ValueError('Tare weight must be below maximum gross weight.')
    if not str(v.get('notes','')).strip():raise ValueError('Specify the profile source or assumptions.')
    v.setdefault('id',uuid.uuid4().hex);v.setdefault('example',True)
    return v

def example_vehicles():
    # Illustrations chosen for demonstrating selection, not verified fleet assets.
    rows=[('Light flatbed',6,2.55,1,9,2.55,3,5,5,10,2,6),
          ('Standard semi-trailer',13.6,2.55,1.3,16.5,2.55,4,15,24,40,5,9),
          ('Low loader for modules',12.2,3.6,.9,18,2.55,4,18,24,42,6,9)]
    result=[]
    keys=[x[0] for x in VEHICLE_FIELDS]
    for i,row in enumerate(rows):
        v=dict(zip(keys,row));v.update(id=f'example-{i}',example=True,notes='EXAMPLE for simulation. Dimensions, permitted width, capacity and axle loads must be confirmed by the carrier for the actual load.')
        result.append(v)
    return result

def evaluate(p,v):
    p=product(p);v=vehicle(v);reasons=[]
    for k,limit,label in [('length','deck_length','usable length'),('width','load_width','permitted width'),('weight','payload','payload')]:
        if p[k]>v[limit]:reasons.append(f'{label}: {p[k]:g} > {v[limit]:g}')
    weight=p['weight']+v['tare']
    if weight>v['gross']:reasons.append(f'total weight: {weight:g} > {v["gross"]:g} t')
    if v['axle_load']>weight or v['axle_load']*v['axle_count']<weight:reasons.append('maximum axle load is incompatible with total weight')
    loaded={'length':v['length'],'width':max(p['width'],v['width']),'height':max(v['height'],v['deck_height']+p['height']),'weight':weight,'axle_load':v['axle_load'],'axle_count':v['axle_count']}
    return {'vehicle':v,'loaded':loaded,'fits':not reasons,'reasons':reasons}

def recommend(p,vehicles):
    results=[evaluate(p,v) for v in vehicles]
    # Lower loaded height first, then smaller useful deck; no unsupported cost ranking.
    return sorted(results,key=lambda r:(not r['fits'],r['loaded']['height'],r['vehicle']['deck_length']))

def coordinates(text):
    parts=str(text).replace(';',' ').replace(',',' ').split()
    if len(parts)!=2:raise ValueError('Coordinates: latitude, longitude; example 47.8528263, 26.759334.')
    lat,lon=num(parts[0],'Latitude',-90),num(parts[1],'Longitude',-180)
    if lat>90 or lon>180:raise ValueError('Coordinates outside the valid range.')
    return {'lat':lat,'lon':lon}

def route_request(origin,destination,loaded,via=None):
    truck={k:num(loaded.get(k),k,.001,k=='axle_count') for k in ('length','width','height','weight','axle_load','axle_count')}
    truck.update(ignore_restrictions=False,ignore_access=False,ignore_closures=False,hgv_no_access_penalty=43200,use_ferry=0.5)
    points=[dict(origin,type='break'),*[dict(p,type='via') for p in (via or [])],dict(destination,type='break')]
    return {'locations':points,'costing':'truck','costing_options':{'truck':truck},'units':'kilometers','language':'en-GB','format':'osrm','shape_format':'geojson','alternates':0 if via else 2}

def parse_response(data):
    if data.get('code')!='Ok':raise ValueError('Valhalla found no route for the submitted configuration. '+str(data.get('error') or data.get('message') or ''))
    rows=[]
    for i,r in enumerate(data.get('routes',[]),1):
        geometry=r.get('geometry',{})
        if geometry.get('type')!='LineString' or len(geometry.get('coordinates',[]))<2:raise ValueError('Response contains no valid geometry.')
        rows.append({'name':f'Option {i}','distance_km':num(r.get('distance'),'Distance',.001)/1000,'hours':num(r.get('duration'),'Time',0)/3600,'geometry':geometry})
        rows[-1]['ferryDetected']=any(step.get('mode')=='ferry' or any('ferry' in intersection.get('classes',[]) for intersection in step.get('intersections',[])) for leg in r.get('legs',[]) for step in leg.get('steps',[]))
        steps=[s for leg in r.get('legs',[]) for s in leg.get('steps',[])]
        crossings=[s for s in steps if s.get('mode')=='ferry']
        rows[-1]['crossings']=[dict(name=s.get('name') or 'Unnamed ferry / vehicle crossing',distance_km=num(s['distance'],'Crossing distance',0)/1000 if s.get('distance') is not None else None,hours=num(s['duration'],'Crossing time',0)/3600 if s.get('duration') is not None else None) for s in crossings]
        # Split only when the step distances cover the whole response. A missing
        # step list must not be presented as proof that a route is all road.
        if steps and all(s.get('mode') in ('driving','ferry') and s.get('distance') is not None for s in steps) and abs(sum(float(s['distance']) for s in steps)/1000-rows[-1]['distance_km'])<0.1:
            crossing_km=sum(c['distance_km'] for c in rows[-1]['crossings'])
            rows[-1].update(crossing_distance_km=crossing_km,road_distance_km=max(0,rows[-1]['distance_km']-crossing_km))
    if not rows:raise ValueError('The service returned no routes.')
    return rows

def cash(n):return float(Decimal(str(n)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
def calculate(row,rates):
    # One product per trip, deliberately explicit for the initial release.
    qty=num(row['quantity'],'Delivery quantity',1,True);km=num(row['distance_km'],'Distance',.001)
    empty=num(row.get('return_km',0),'Return')+num(row.get('position_km',0),'Positioning')
    r={k:num(rates.get(k,0),k) for k in ('loaded','empty','fixed','markup','vat')}
    cost=cash((km*r['loaded']+empty*r['empty']+r['fixed'])*qty)
    net=cash(cost*(1+r['markup']/100));vat=cash(net*r['vat']/100)
    return {'trips':qty,'billable_km':(km+empty)*qty,'cost':cash(cost),'net':net,'vat':vat,'total':cash(net+vat)}

class State:
    def __init__(self,path):
        self.path=Path(path)
        if self.path.exists():
            try:self.data=json.loads(self.path.read_text(encoding='utf-8'))
            except (OSError,json.JSONDecodeError) as e:raise ValueError('Saved data could not be read; the file was not overwritten.') from e
        else:self.data={'vehicles':example_vehicles(),'product':{'name':'Module 1','length':9,'width':3,'height':3.3,'weight':7,'quantity':1},'deliveries':[],'rates':dict(loaded=0,empty=0,fixed=0,markup=0,vat=0),'server':'https://valhalla1.openstreetmap.de','origin_name':'10 Peco Street, Botosani 710003, Romania','origin_coords':'47.8528263, 26.759334'}
        from site_conditions import migrate
        self.data['siteConditions']=migrate(self.data.get('siteConditions'))
    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True);temp=self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(self.path)
