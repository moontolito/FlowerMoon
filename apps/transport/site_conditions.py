"""Reusable project/site model. No geographic engineering zoning assumptions."""
from copy import deepcopy
from datetime import datetime, timezone
import math

CORROSIVITY = ['C1', 'C2', 'C3', 'C4', 'C5', 'CX', 'Manual / Unknown']
INCOTERMS = ['EXW', 'FCA', 'CPT', 'CIP', 'DAP', 'DPU', 'DDP']
# key: label, unit, default, choices (None means numeric)
FIELDS = {
 'transport.deliveryType': ('Delivery Type', '', 'EXW', INCOTERMS),
 'transport.distanceKm': ('Distance', 'km', None, None),
 'transport.maxAltitudeM': ('Max altitude', 'm', None, None),
 'transport.maritimeTransport': ('Maritime transport involved', '', 'Unknown', ['Yes','No','Unknown']),
 'environment.exteriorCorrosivity': ('Final exterior corrosivity', '', 'Manual / Unknown', CORROSIVITY),
 'environment.interiorCorrosivity': ('Interior corrosivity', '', 'Manual / Unknown', CORROSIVITY),
 'environment.marineEnvironment': ('Marine environment', '', 'Unknown', ['Yes','No','Possible','Unknown']),
 'temperature.maxDesign': ('Maximum historical temperature', '°C', None, None),
 'temperature.minDesign': ('Minimum historical temperature', '°C', None, None),
 'temperature.maxDailyAverage': ('Maximum daily average', '°C', None, None),
 'temperature.minDailyAverage': ('Minimum daily average', '°C', None, None),
 'humidity.maximum': ('Umiditate relativă maximă (orară)', '%', None, None),
 'humidity.mean': ('Umiditate relativă medie', '%', None, None),
 'humidity.minimum': ('Umiditate relativă minimă (orară)', '%', None, None),
 'humidity.value1': ('Humidity · custom 1 (manual)', '%', None, None),
 'humidity.value2': ('Humidity · custom 2 (manual)', '%', None, None),
 'humidity.value3': ('Humidity · custom 3 (manual)', '%', None, None),
 'seismic.ag': ('Seismic ag', 'g', None, None),
 'seismic.tc': ('Seismic Tc', 's', None, None),
 'snow.sk': ('Snow load sk', 'kN/m²', None, None),
 'wind.qb': ('Wind pressure qb', 'kPa', None, None),
}
ROUTE_KEYS = ['transport.distanceKm','transport.maxAltitudeM','transport.maritimeTransport']
def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def field(value=None, source='unavailable', status='VERIFY', **extra):
    return dict(value=value,source=source,status=status,manualOverride=False,lastUpdated=now(),reviewRequired=False,**extra)
def get(site,key):
    group,name=key.split('.');return site[group][name]
def create():
    site={'schemaVersion':2,'departureAddress':'','destinationAddress':'','destinationCoordinates':'','departureCoordinates':''}
    for key,(_,unit,default,_) in FIELDS.items():
        group,name=key.split('.')
        site.setdefault(group,{})[name]=field(default,'Project default' if default not in (None,'Manual / Unknown') else 'unavailable','DEFAULT' if default not in (None,'Unknown','Manual / Unknown') else 'VERIFY',unit=unit)
    site['environment']['suggestedCorrosivity']=field()
    site['environment']['standard']='EN ISO 12944-2:2017'
    site['environment']['siteAltitudeM']=field(unit='m')
    site['transport']['suggestedProtection']=field()
    for group in ('seismic','snow','wind'):site[group]['standard']=None
    site['exposureChecklist']={k:field('Unknown') for k in ['Distance from shoreline','Salinity','Sea spray','Chlorides','Humidity','Industrial pollution','Sheltered / unsheltered','Condensation','Atmospheric contamination']}
    return site
def migrate(raw=None):
    result=create()
    def merge(a,b):
        for k,v in b.items():
            if isinstance(v,dict) and isinstance(a.get(k),dict):merge(a[k],v)
            else:a[k]=deepcopy(v)
    if raw:merge(result,raw)
    if result['environment']['standard']=='EN ISO 12944-2':result['environment']['standard']='EN ISO 12944-2:2017'
    # Keep the legacy keys for saved-project compatibility, but no project limits.
    for key in ('maxDesign','minDesign','maxDailyAverage','minDailyAverage'):
        f=result['temperature'][key]
        if not f['manualOverride'] and (f['status']=='DEFAULT' or 'Anvelopă preliminară' in f.get('detail','')):
            result['temperature'][key]=field(unit='°C')
    if raw and raw.get('schemaVersion',1)<2:
        result.setdefault('legacyDefaults',{})
        for key in ('environment.exteriorCorrosivity','environment.interiorCorrosivity','humidity.value1','humidity.value2','humidity.value3','environment.suggestedCorrosivity','transport.suggestedProtection'):
            f=get(result,key)
            if not f.get('manualOverride'):
                result['legacyDefaults'][key]=deepcopy(f)
                group,name=key.split('.')
                result[group][name]=field('Manual / Unknown' if key.endswith(('exteriorCorrosivity','interiorCorrosivity')) else None,unit=f.get('unit',''))
        for group in ('seismic','snow','wind'):
            result[group]['standard']=None
            for key in FIELDS:
                if key.startswith(group+'.'):
                    f=get(result,key)
                    if not f.get('manualOverride'):
                        result['legacyDefaults'][key]=deepcopy(f)
                        result[group][key.split('.')[1]]=field(unit=f.get('unit',''))
                    else:f['reviewRequired']=True
    result['schemaVersion']=2
    # Preserve previous source results as history, never silently relabel them.
    if result.get('sourcePolicyVersion')!='suggested-sources-v1':
        keys=[k for k in FIELDS if k.startswith(('temperature.','humidity.'))]+['environment.siteAltitudeM','transport.maxAltitudeM']
        history={}
        for key in keys:
            f=get(result,key)
            if not f.get('manualOverride') and f.get('value') is not None and ('NASA' in f.get('source','') or 'Valhalla' in f.get('source','') or '/height' in f.get('source','')):
                history[key]=deepcopy(f)
                group,name=key.split('.');result[group][name]=field(unit=f.get('unit',''),detail='Sursa anterioară este arhivată; se așteaptă sursa solicitată.')
        for name in ('climate','humidityAnalysis'):
            analysis=result.get(name,{})
            if analysis and analysis.get('methodVersion')!='open-meteo-era5-v3':
                history[name]=deepcopy(analysis);result[name]={'status':'pending'}
        if history:result.setdefault('sourceHistory',[]).append(dict(archivedAt=now(),data=history))
        result['sourcePolicyVersion']='suggested-sources-v1'
    return result
def automatic(site,key,value,source,status='AUTO',**extra):
    f=get(site,key)
    if f['manualOverride']:return
    f.update(value=value,source=source,status=status,lastUpdated=now(),reviewRequired=False,**extra)

def apply_zoning(site,values):
    from site_environment.service import apply_zoning as apply
    apply(site,values)

def invalidate(site,keys):
    if 'transport.maritimeTransport' in keys:site['transport']['ferryDetected']=False
    for key in keys:
        f=get(site,key)
        if f['manualOverride']:f['reviewRequired']=True
        elif key in ROUTE_KEYS or f['status'] in ('AUTO','CALCULATED','VERIFY'):
            value='Unknown' if key.endswith(('maritimeTransport','marineEnvironment')) else 'Manual / Unknown' if key.endswith(('exteriorCorrosivity','interiorCorrosivity')) else None
            unit=f.get('unit','');f.clear();f.update(field(value,'Location / route changed','VERIFY',unit=unit))
def sync(site,departure,destination,origin_coords,dest_coords):
    site_changed=(destination,dest_coords)!=(site['destinationAddress'],site['destinationCoordinates'])
    route_changed=site_changed or (departure,origin_coords)!=(site['departureAddress'],site['departureCoordinates'])
    if site_changed:
        invalidate(site,list(FIELDS)+['environment.suggestedCorrosivity','environment.siteAltitudeM','transport.suggestedProtection'])
        site['climate']={'status':'pending'}
        site['humidityAnalysis']={'status':'pending'}
        site.pop('locationContext',None);site.pop('coastalDistance',None);site.pop('weather',None);site.pop('elevationAnalysis',None)
        for group in ('seismic','snow','wind'):site[group]['standard']=None;site[group]['jurisdiction']=None
        for key,(_,_,default,_) in FIELDS.items():
            if key.startswith('temperature.') and not get(site,key)['manualOverride']:
                automatic(site,key,None,'Date climatice în așteptare','VERIFY',detail='')
        for f in site['exposureChecklist'].values():
            if f['manualOverride']:f['reviewRequired']=True
    elif route_changed:invalidate(site,ROUTE_KEYS)
    if route_changed:site.pop('routeLookup',None)
    site.update(departureAddress=departure,destinationAddress=destination,departureCoordinates=origin_coords,destinationCoordinates=dest_coords)
    return route_changed
def apply_manual(site,values,confirmed=()):
    candidate=deepcopy(site)
    for key,raw in values.items():
        label,unit,default,choices=FIELDS[key]
        if choices:
            if raw not in choices:raise ValueError(label+': invalid selection')
            value=raw
        else:
            try:value=None if str(raw).strip()=='' else float(str(raw).replace(',','.'))
            except ValueError:raise ValueError(label+': enter a number') from None
            if value is not None:
                if not math.isfinite(value):raise ValueError(label+': finite number required')
                if key.startswith('humidity.') and not 0<=value<=100:raise ValueError('Humidity: 0–100%')
                if key.startswith(('seismic.','snow.','wind.')) or key=='transport.distanceKm':
                    if value<0:raise ValueError(label+': cannot be negative')
                if key.startswith('temperature.') and value<-273.15:raise ValueError('Temperature below absolute zero')
        f=get(candidate,key)
        if value!=f['value'] or key in confirmed:
            f.update(value=value,source='manual',status='MANUAL',manualOverride=True,lastUpdated=now(),reviewRequired=False)
            f.update(operator='=',detail='',candidates=[],candidateValue=None,candidateValues=[],applicability='manual')
            f.update(availability='manual',methodStatus='manual',standard=None,provider=None)
    for high,low in [('maxDesign','minDesign'),('maxDailyAverage','minDailyAverage')]:
        hi=get(candidate,'temperature.'+high)['value'];lo=get(candidate,'temperature.'+low)['value']
        if hi is not None and lo is not None and hi<lo:raise ValueError('Temperature: maximum must be ≥ minimum')
    site.clear();site.update(candidate)
def badge(f):return f['status']+(' · Review required' if f.get('reviewRequired') else '')
def recommendation(site):
    # No validated mapping from coast, shipping or climate to an ISO category.
    automatic(site,'environment.suggestedCorrosivity',None,
              'Metodă de clasificare nevalidată. Distanța de coastă nu determină C3/C5.',
              'VERIFY',availability='method_not_validated',methodStatus='not_validated')
    automatic(site,'transport.suggestedProtection',None,
              'Protecția de transport necesită o specificație; transportul maritim nu atribuie automat C5.',
              'VERIFY',availability='method_not_validated',methodStatus='not_validated')
