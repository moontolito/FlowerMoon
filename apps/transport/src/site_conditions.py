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
 'humidity.maximum': ('Maximum relative humidity (hourly)', '%', None, None),
 'humidity.mean': ('Mean relative humidity', '%', None, None),
 'humidity.minimum': ('Minimum relative humidity (hourly)', '%', None, None),
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
    site={'corrosivityEnabled':False,'schemaVersion':2,'departureAddress':'','destinationAddress':'','destinationCoordinates':'','departureCoordinates':''}
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
        if not f['manualOverride'] and (f['status']=='DEFAULT' or any(text in f.get('detail','') for text in ('Preliminary envelope','Anvelop\u0103 preliminar\u0103'))):
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
    if result.get('corrosionPolicyVersion')!='optional-annual-v1':
        if result.get('corrosionAssessment'):
            result.setdefault('sourceHistory',[]).append(dict(archivedAt=now(),data={'corrosionAssessment':deepcopy(result['corrosionAssessment']),'suggestedCorrosivity':deepcopy(result['environment']['suggestedCorrosivity'])}))
        result['corrosionPolicyVersion']='optional-annual-v1'
        result['corrosivityEnabled']=False
    result['schemaVersion']=2
    # Preserve previous source results as history, never silently relabel them.
    if result.get('sourcePolicyVersion')!='suggested-sources-v1':
        keys=[k for k in FIELDS if k.startswith(('temperature.','humidity.'))]+['environment.siteAltitudeM','transport.maxAltitudeM']
        history={}
        for key in keys:
            f=get(result,key)
            if not f.get('manualOverride') and f.get('value') is not None and ('NASA' in f.get('source','') or 'Valhalla' in f.get('source','') or '/height' in f.get('source','')):
                history[key]=deepcopy(f)
                group,name=key.split('.');result[group][name]=field(unit=f.get('unit',''),detail='Previous source archived; waiting for the requested provider.')
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
        site['airQuality']={'status':'pending'}
        site['deposition']={'status':'pending'}
        site.pop('corrosionAssessment',None)
        site.pop('seismicHazard',None)
        site.pop('administrativeRegion',None)
        site.pop('locationContext',None);site.pop('coastalDistance',None);site.pop('weather',None);site.pop('elevationAnalysis',None)
        for group in ('seismic','snow','wind'):site[group]['standard']=None;site[group]['jurisdiction']=None
        for key,(_,_,default,_) in FIELDS.items():
            if key.startswith('temperature.') and not get(site,key)['manualOverride']:
                automatic(site,key,None,'Waiting for climate data','VERIFY',detail='')
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
    import annual_corrosion as corrosion
    from domain import coordinates
    try:point=coordinates(site.get('destinationCoordinates',''))
    except ValueError:point={}
    estimate=corrosion.evaluate(site.get('deposition',{}),point) if site.get('corrosivityEnabled',False) else dict(status='disabled',category=None,reason='Enable annual corrosivity in Settings to download data and calculate.')
    site['corrosionAssessment']=estimate
    value=estimate.get('category')
    automatic(site,'environment.suggestedCorrosivity',None,
              corrosion.SOURCE,'VERIFY',availability='unavailable',methodStatus='screening_proxy',detail=estimate.get('reason',''))
    if value:
        automatic(site,'environment.suggestedCorrosivity',value,corrosion.SOURCE,'VERIFY',availability='available',methodStatus='screening_proxy',
                  detail=estimate['assumptions']+' '+('Outside calibration ranges: '+', '.join(estimate['outsideCalibration'])+'. ' if estimate.get('outsideCalibration') else '')+estimate['formula'])
    automatic(site,'transport.suggestedProtection',None,
              'Transport protection requires a specification; maritime transport does not automatically assign C5.',
              'VERIFY',availability='method_not_validated',methodStatus='not_validated')
