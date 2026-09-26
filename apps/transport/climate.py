"""Thirty complete historical years, never presented as code design values."""
from datetime import date,timedelta
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from pathlib import Path
import hashlib,json,math,os
from weather_config import configuration, SOURCE, DOCS, VERSION
from site_environment.geography import validate

MODEL='era5'
VARIABLES=('temperature_2m_max','temperature_2m_min','temperature_2m_mean')
def period(today=None):
    year=(today or date.today()).year
    return date(year-30,1,1),date(year-1,12,31)

def summarize(data,start,end):
    daily=data.get('daily',{});days=daily.get('time',[])
    expected=[(start+timedelta(days=i)).isoformat() for i in range((end-start).days+1)]
    if days!=expected:raise ValueError('Seria climatică nu acoperă integral perioada solicitată.')
    for key in VARIABLES:
        values=daily.get(key,[])
        if data.get('daily_units',{}).get(key)!='°C':raise ValueError('Unitate climatică neașteptată.')
        if len(values)!=len(days) or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not -100<=v<=70 for v in values):
            raise ValueError('Seria climatică are valori lipsă sau invalide; extremele nu pot fi confirmate.')
    highs,lows,means=(daily[k] for k in VARIABLES)
    if any(not lo<=avg<=hi for hi,lo,avg in zip(highs,lows,means)):raise ValueError('Temperaturi climatice inconsistente.')
    high=max(highs);low=min(lows);daily_high=max(means);daily_low=min(means)
    return dict(maximum=high,minimum=low,maxDailyMean=daily_high,minDailyMean=daily_low,
                maximumDate=days[highs.index(high)],minimumDate=days[lows.index(low)],
                maxDailyMeanDate=days[means.index(daily_high)],minDailyMeanDate=days[means.index(daily_low)],
                periodStart=start.isoformat(),periodEnd=end.isoformat(),days=len(days),model=MODEL,
                gridLatitude=data.get('latitude'),gridLongitude=data.get('longitude'),gridElevationM=data.get('elevation'),
                method='Extreme ale temperaturilor zilnice și ale mediilor zilnice din reanaliză, nu valori normative de proiectare.',
                source=SOURCE,
                sourceUrl=DOCS,
                spatialNote='Reanaliză globală pe grilă; nu măsurătoare meteo la amplasament.',timeStandard=data.get('_timeStandard',data.get('timezone','')),
                methodId='historical-daily-extrema-v1',methodStatus='descriptive_statistics',unit='°C',coverage='global',validFraction=1.0,
                methodSource='FlowerMoon: max/min ale seriilor zilnice complete; fără conversie la valori normative.',
                datasetMetadata=data.get('_datasetMetadata',{}))

def lookup(destination,cache_dir,force=False,today=None):
    validate(destination)
    start,end=period(today);endpoint,key=configuration()
    params=dict(latitude=destination['lat'],longitude=destination['lon'],start_date=start.isoformat(),end_date=end.isoformat(),
                daily=','.join(VARIABLES),models=MODEL,timezone='UTC',cell_selection='nearest',temperature_unit='celsius')
    digest=hashlib.sha256(json.dumps([VERSION,params,endpoint],sort_keys=True).encode()).hexdigest()
    path=Path(cache_dir)/(digest+'.json')
    if not force and path.exists():
        try:
            payload=json.loads(path.read_text(encoding='utf-8'))
            result=summarize(payload['data'],start,end);result.update(payload['provenance']);result['retrievedAt']=payload['retrievedAt'];return result
        except (OSError,ValueError,KeyError,TypeError):pass
    request_params=dict(params)
    if key:request_params['apikey']=key
    try:
        req=Request(endpoint+'?'+urlencode(request_params),headers={'User-Agent':'FlowerMoonTransportSimple/1.0'})
        with urlopen(req,timeout=120) as response:data=json.load(response)
        result=summarize(data,start,end)
    except Exception:
        raise ValueError('Open-Meteo Historical: date indisponibile sau incomplete. Verificati conexiunea si accesul API; nu se foloseste alta sursa automat.') from None
    from datetime import datetime,timezone
    retrieved=datetime.now(timezone.utc).isoformat(timespec='seconds');result['retrievedAt']=retrieved
    provenance=dict(requestedCoordinates=dict(destination),rawSha256=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest(),
                    requestParameters=params,endpoint=endpoint,actualProvider='open-meteo-era5',methodVersion=VERSION,providerFallback=False)
    result.update(provenance)
    path.parent.mkdir(parents=True,exist_ok=True)
    import uuid
    temporary=path.with_suffix('.'+uuid.uuid4().hex+'.tmp');temporary.write_text(json.dumps(dict(data=data,retrievedAt=retrieved,provenance=provenance)),encoding='utf-8');temporary.replace(path)
    return result

def apply(site,result):
    from site_conditions import automatic
    site['climate']=dict(result,status='ready')
    source=f"{result['source']} · {result['periodStart']} – {result['periodEnd']}"
    # Legacy storage names remain compatible; values are historical extrema only.
    pairs={'maxDesign':result['maximum'],'minDesign':result['minimum'],
           'maxDailyAverage':result['maxDailyMean'],'minDailyAverage':result['minDailyMean']}
    for key,value in pairs.items():
        design=key.endswith('Design')
        automatic(site,'temperature.'+key,value,source,'CALCULATED',
                  detail='Maximul/minimul istoric din reanaliză, fără limite implicite de proiect sau rotunjire conservatoare. Nu este măsurătoare directă la amplasament.' if design else 'Maximul/minimul mediilor zilnice din perioada istorică; nu media anuală și nu prognoză.',
                  periodStart=result['periodStart'],periodEnd=result['periodEnd'],model=result['model'])
