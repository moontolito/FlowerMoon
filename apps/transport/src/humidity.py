"""Global RH statistics from Open-Meteo hourly ERA5, with explicit coverage."""
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlencode
import json,math,hashlib,uuid
from climate import period
from weather_config import SOURCE,DOCS,VERSION,configuration
from site_environment.geography import validate

METHOD='rh-hourly-max-mean-min-v2'

def summarize(raw,start,end):
    variable='relative_humidity_2m'
    if raw.get('hourly_units',{}).get(variable)!='%':raise ValueError('Umiditate: unitate neașteptată.')
    if raw.get('utc_offset_seconds',0)!=0:raise ValueError('Umiditate: se așteaptă seria UTC.')
    hourly=raw.get('hourly',{});times=hourly.get('time',[]);values=hourly.get(variable,[])
    if len(times)!=len(values):raise ValueError('Umiditate: dimensiuni inconsistente.')
    valid=[];seen=set();previous=None
    for key,value in zip(times,values):
        try:stamp=datetime.strptime(key,'%Y-%m-%dT%H:%M')
        except (ValueError,TypeError):raise ValueError('Umiditate: dată invalidă.') from None
        if stamp.minute or not start<=stamp.date()<=end or stamp in seen or (previous and stamp<=previous):
            raise ValueError('Umiditate: ore duplicate, nesortate sau în afara perioadei.')
        seen.add(stamp);previous=stamp
        if not isinstance(value,bool) and isinstance(value,(int,float)) and math.isfinite(value) and 0<=value<=100:valid.append((stamp,value))
    if not valid:raise ValueError('Umiditate: nu există valori valide în seria primită.')
    samples=[v for _,v in valid];expected=((end-start).days+1)*24
    maximum=max(samples);minimum=min(samples)
    detail='Maximul, media aritmetică și minimul valorilor orare RH la 2 m, ERA5 / UTC; nu citiri directe la amplasament. De verificat pentru proiect.'
    if len(valid)!=expected:detail+=f' Serie incompletă: {len(valid)} din {expected} ore valide; indicatori doar pentru datele disponibile.'
    return dict(maximum=maximum,mean=math.fsum(samples)/len(samples),minimum=minimum,
                maximumDate=min(d for d,v in valid if v==maximum).isoformat(timespec='minutes'),minimumDate=min(d for d,v in valid if v==minimum).isoformat(timespec='minutes'),
                validHours=len(valid),expectedHours=expected,validFraction=len(valid)/expected,periodStart=start.isoformat(),periodEnd=end.isoformat(),
                source=SOURCE,sourceUrl=DOCS,unit='%',model='era5',coverage='global',
                methodId=METHOD,methodVersion=VERSION,methodStatus='descriptive_statistics',timeStandard='UTC',
                gridLatitude=raw.get('latitude'),gridLongitude=raw.get('longitude'),gridElevationM=raw.get('elevation'),detail=detail)

def lookup(destination,cache_dir,force=False,today=None):
    validate(destination);start,end=period(today);endpoint,key=configuration()
    params=dict(longitude=destination['lon'],latitude=destination['lat'],start_date=start.isoformat(),end_date=end.isoformat(),
                hourly='relative_humidity_2m',models='era5',timezone='UTC',cell_selection='nearest')
    digest=hashlib.sha256(json.dumps([endpoint,params,METHOD],sort_keys=True).encode()).hexdigest()
    path=Path(cache_dir)/(digest+'.json');payload=None
    if not force and path.exists():
        try:
            cached=json.loads(path.read_text(encoding='utf-8'));summarize(cached['raw'],start,end);payload=cached
        except (OSError,ValueError,TypeError,KeyError):pass
    if payload is None:
        request_params=dict(params)
        if key:request_params['apikey']=key
        try:
            req=Request(endpoint+'?'+urlencode(request_params),headers={'User-Agent':'FlowerMoonTransportSimple/1.0'})
            with urlopen(req,timeout=120) as response:raw=json.load(response)
            summarize(raw,start,end)
        except Exception:
            raise ValueError('Open-Meteo Historical: umiditate indisponibilă sau serie invalidă. Verificați accesul API; nu se folosește altă sursă automat.') from None
        payload=dict(raw=raw,retrievedAt=datetime.now(timezone.utc).isoformat(timespec='seconds'))
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_suffix('.'+uuid.uuid4().hex+'.tmp');temporary.write_text(json.dumps(payload),encoding='utf-8');temporary.replace(path)
    result=summarize(payload['raw'],start,end)
    result.update(requestedCoordinates=dict(destination),requestParameters=params,endpoint=endpoint,actualProvider='open-meteo-era5',retrievedAt=payload['retrievedAt'],rawSha256=hashlib.sha256(json.dumps(payload['raw'],sort_keys=True).encode()).hexdigest())
    return result

def apply(site,result):
    from site_conditions import automatic
    site['humidityAnalysis']=dict(result,status='ready')
    for key in ('maximum','mean','minimum'):
        automatic(site,'humidity.'+key,result[key],result['source'],'CALCULATED' if result['validFraction']==1 else 'VERIFY',
                  detail=result['detail'],periodStart=result['periodStart'],periodEnd=result['periodEnd'],validFraction=result['validFraction'],methodId=result['methodId'])
