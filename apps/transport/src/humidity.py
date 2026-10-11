"""Global RH statistics from Open-Meteo hourly ERA5, with explicit coverage."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlencode
import json,math,hashlib,uuid
from climate import period
from weather_config import SOURCE,DOCS,VERSION,configuration
from site_environment.geography import validate

METHOD='rh-hourly-max-mean-min-v2'

HOURS=frozenset(f'{h:02d}:00' for h in range(24))

def summarize(raw,start,end):
    variable='relative_humidity_2m'
    if raw.get('hourly_units',{}).get(variable)!='%':raise ValueError('Humidity: unexpected unit.')
    if raw.get('utc_offset_seconds',0)!=0:raise ValueError('Humidity: UTC series expected.')
    hourly=raw.get('hourly',{});times=hourly.get('time',[]);values=hourly.get(variable,[])
    if len(times)!=len(values):raise ValueError('Humidity: inconsistent array lengths.')
    # 30 years are ~263 000 hours. Checking fixed-width ISO strings against the
    # set of valid period dates is equivalent to parsing each one, and ~20x faster.
    days=frozenset((start+timedelta(days=i)).isoformat() for i in range((end-start).days+1))
    valid=[];previous=''
    for key,value in zip(times,values):
        if not isinstance(key,str) or len(key)!=16 or key[10]!='T' or key[:10] not in days or key[11:] not in HOURS or key<=previous:
            raise ValueError('Humidity: invalid, duplicate, unsorted or out-of-period hours.')
        previous=key
        if not isinstance(value,bool) and isinstance(value,(int,float)) and math.isfinite(value) and 0<=value<=100:valid.append((key,value))
    if not valid:raise ValueError('Humidity: no valid values in the returned series.')
    samples=[v for _,v in valid];expected=((end-start).days+1)*24
    maximum=max(samples);minimum=min(samples)
    detail='Maximum, arithmetic mean and minimum of hourly RH at 2 m, ERA5 / UTC; not direct site readings. Verify suitability for the project.'
    if len(valid)!=expected:detail+=f' Incomplete series: {len(valid)} of {expected} valid hours; statistics describe available data only.'
    return dict(maximum=maximum,mean=math.fsum(samples)/len(samples),minimum=minimum,
                maximumDate=next(d for d,v in valid if v==maximum),minimumDate=next(d for d,v in valid if v==minimum),
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
    result=None
    if not force and path.exists():
        try:
            cached=json.loads(path.read_text(encoding='utf-8'));result=summarize(cached['raw'],start,end);payload=cached
        except (OSError,ValueError,TypeError,KeyError):pass
    if payload is None:
        request_params=dict(params)
        if key:request_params['apikey']=key
        try:
            req=Request(endpoint+'?'+urlencode(request_params),headers={'User-Agent':'FlowerMoonTransportSimple/1.0'})
            with urlopen(req,timeout=120) as response:raw=json.load(response)
            result=summarize(raw,start,end)
        except Exception:
            raise ValueError('Open-Meteo Historical: humidity unavailable or invalid series. Check API access; no other provider is substituted automatically.') from None
        payload=dict(raw=raw,retrievedAt=datetime.now(timezone.utc).isoformat(timespec='seconds'))
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_suffix('.'+uuid.uuid4().hex+'.tmp');temporary.write_text(json.dumps(payload),encoding='utf-8');temporary.replace(path)
    result.update(requestedCoordinates=dict(destination),requestParameters=params,endpoint=endpoint,actualProvider='open-meteo-era5',retrievedAt=payload['retrievedAt'],rawSha256=hashlib.sha256(json.dumps(payload['raw'],sort_keys=True).encode()).hexdigest())
    return result

def apply(site,result):
    from site_conditions import automatic
    site['humidityAnalysis']=dict(result,status='ready')
    for key in ('maximum','mean','minimum'):
        automatic(site,'humidity.'+key,result[key],result['source'],'CALCULATED' if result['validFraction']==1 else 'VERIFY',
                  detail=result['detail'],periodStart=result['periodStart'],periodEnd=result['periodEnd'],validFraction=result['validFraction'],methodId=result['methodId'])
