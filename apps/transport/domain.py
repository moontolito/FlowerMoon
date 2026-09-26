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
    except (ValueError,TypeError):raise ValueError(f'{label}: introduceți un număr.') from None
    if not math.isfinite(n) or n<minimum or (integer and n!=int(n)):raise ValueError(f'{label}: valoare invalidă (minim {minimum:g}).')
    return int(n) if integer else n

def product(data):
    p={k:num(data.get(k),label,.001) for k,label in [('length','Lungime'),('width','Lățime'),('height','Înălțime'),('weight','Masă')]}
    p['name']=str(data.get('name','')).strip()
    if not p['name']:raise ValueError('Completați numele produsului.')
    p['quantity']=num(data.get('quantity'),'Cantitate',1,True)
    return p

VEHICLE_FIELDS=[('name','Nume profil'),('deck_length','Lungime utilă platformă (m)'),('load_width','Lățime marfă acceptată (m)'),('deck_height','Platformă de la sol (m)'),('length','Lungime totală ansamblu (m)'),('width','Lățime vehicul (m)'),('height','Înălțime vehicul gol (m)'),('tare','Masă proprie, inclusiv fixări (t)'),('payload','Sarcină utilă (t)'),('gross','Masă totală tehnică maximă (t)'),('axle_count','Număr axe'),('axle_load','Masă maximă pe o axă încărcată (t)')]

def vehicle(data):
    v=deepcopy(data)
    if not str(v.get('name','')).strip():raise ValueError('Completați numele vehiculului.')
    for k,label in VEHICLE_FIELDS[1:]:v[k]=num(v.get(k),label,.001,k=='axle_count')
    if v['deck_length']>v['length']:raise ValueError('Platforma utilă nu poate fi mai lungă decât ansamblul.')
    if v['tare']>=v['gross']:raise ValueError('Masa proprie trebuie să fie sub masa totală tehnică.')
    if not str(v.get('notes','')).strip():raise ValueError('Precizați sursa sau ipotezele profilului.')
    v.setdefault('id',uuid.uuid4().hex);v.setdefault('example',True)
    return v

def example_vehicles():
    # Illustrations chosen for demonstrating selection, not verified fleet assets.
    rows=[('Platformă ușoară',6,2.55,1,9,2.55,3,5,5,10,2,6),
          ('Semiremorcă standard',13.6,2.55,1.3,16.5,2.55,4,15,24,40,5,9),
          ('Trailer jos pentru module',12.2,3.6,.9,18,2.55,4,18,24,42,6,9)]
    result=[]
    keys=[x[0] for x in VEHICLE_FIELDS]
    for i,row in enumerate(rows):
        v=dict(zip(keys,row));v.update(id=f'example-{i}',example=True,notes='EXEMPLU pentru simulare. Dimensiunile, lățimea acceptată, capacitățile și sarcina pe axă trebuie confirmate de transportator pentru încărcătura concretă.')
        result.append(v)
    return result

def evaluate(p,v):
    p=product(p);v=vehicle(v);reasons=[]
    for k,limit,label in [('length','deck_length','lungime utilă'),('width','load_width','lățime acceptată'),('weight','payload','sarcină utilă')]:
        if p[k]>v[limit]:reasons.append(f'{label}: {p[k]:g} > {v[limit]:g}')
    weight=p['weight']+v['tare']
    if weight>v['gross']:reasons.append(f'masă totală: {weight:g} > {v["gross"]:g} t')
    if v['axle_load']>weight or v['axle_load']*v['axle_count']<weight:reasons.append('sarcina maximă pe axă nu este compatibilă cu masa totală')
    loaded={'length':v['length'],'width':max(p['width'],v['width']),'height':max(v['height'],v['deck_height']+p['height']),'weight':weight,'axle_load':v['axle_load'],'axle_count':v['axle_count']}
    return {'vehicle':v,'loaded':loaded,'fits':not reasons,'reasons':reasons}

def recommend(p,vehicles):
    results=[evaluate(p,v) for v in vehicles]
    # Lower loaded height first, then smaller useful deck; no unsupported cost ranking.
    return sorted(results,key=lambda r:(not r['fits'],r['loaded']['height'],r['vehicle']['deck_length']))

def coordinates(text):
    parts=str(text).replace(';',' ').replace(',',' ').split()
    if len(parts)!=2:raise ValueError('Coordonate: latitudine, longitudine; exemplu 47.8528263, 26.759334.')
    lat,lon=num(parts[0],'Latitudine',-90),num(parts[1],'Longitudine',-180)
    if lat>90 or lon>180:raise ValueError('Coordonate în afara intervalului.')
    return {'lat':lat,'lon':lon}

def route_request(origin,destination,loaded,via=None):
    truck={k:num(loaded.get(k),k,.001,k=='axle_count') for k in ('length','width','height','weight','axle_load','axle_count')}
    truck.update(ignore_restrictions=False,ignore_access=False,ignore_closures=False,hgv_no_access_penalty=43200)
    points=[dict(origin,type='break'),*[dict(p,type='via') for p in (via or [])],dict(destination,type='break')]
    return {'locations':points,'costing':'truck','costing_options':{'truck':truck},'units':'kilometers','language':'ro-RO','format':'osrm','shape_format':'geojson','alternates':0 if via else 2}

def parse_response(data):
    if data.get('code')!='Ok':raise ValueError('Valhalla nu a găsit o rută pentru configurația trimisă. '+str(data.get('error') or data.get('message') or ''))
    rows=[]
    for i,r in enumerate(data.get('routes',[]),1):
        geometry=r.get('geometry',{})
        if geometry.get('type')!='LineString' or len(geometry.get('coordinates',[]))<2:raise ValueError('Răspuns fără geometrie validă.')
        rows.append({'name':f'Varianta {i}','distance_km':num(r.get('distance'),'Distanță',.001)/1000,'hours':num(r.get('duration'),'Timp',0)/3600,'geometry':geometry})
        rows[-1]['ferryDetected']=any(step.get('mode')=='ferry' or any('ferry' in intersection.get('classes',[]) for intersection in step.get('intersections',[])) for leg in r.get('legs',[]) for step in leg.get('steps',[]))
    if not rows:raise ValueError('Serviciul nu a returnat rute.')
    return rows

def cash(n):return float(Decimal(str(n)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
def calculate(row,rates):
    # One product per trip, deliberately explicit for the initial release.
    qty=num(row['quantity'],'Cantitate livrare',1,True);km=num(row['distance_km'],'Distanță',.001)
    empty=num(row.get('return_km',0),'Retur')+num(row.get('position_km',0),'Poziționare')
    r={k:num(rates.get(k,0),k) for k in ('loaded','empty','fixed','markup','vat')}
    cost=cash((km*r['loaded']+empty*r['empty']+r['fixed'])*qty)
    net=cash(cost*(1+r['markup']/100));vat=cash(net*r['vat']/100)
    return {'trips':qty,'billable_km':(km+empty)*qty,'cost':cash(cost),'net':net,'vat':vat,'total':cash(net+vat)}

class State:
    def __init__(self,path):
        self.path=Path(path)
        if self.path.exists():
            try:self.data=json.loads(self.path.read_text(encoding='utf-8'))
            except (OSError,json.JSONDecodeError) as e:raise ValueError('Datele salvate nu pot fi citite; fișierul nu a fost suprascris.') from e
        else:self.data={'vehicles':example_vehicles(),'product':{'name':'Modul 1','length':9,'width':3,'height':3.3,'weight':7,'quantity':1},'deliveries':[],'rates':dict(loaded=0,empty=0,fixed=0,markup=0,vat=0),'server':'https://valhalla1.openstreetmap.de','origin_name':'10 Peco Street, Botosani 710003, Romania','origin_coords':'47.8528263, 26.759334'}
        from site_conditions import migrate
        self.data['siteConditions']=migrate(self.data.get('siteConditions'))
    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True);temp=self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(self.path)
