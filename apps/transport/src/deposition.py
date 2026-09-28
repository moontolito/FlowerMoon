"""CAMS forecast archive: traceable 3-hourly destination deposition screening.

One resumable 30-day job. Every three-hour sample is required; period means
are seasonal, not annual statistics. No deposition velocities are assumed.
"""
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
import calendar,hashlib,json,math,threading,uuid
import cams
import deposition_progress as progress
from site_environment.geography import validate

DATASET='cams-global-atmospheric-composition-forecasts'
SOURCE='Copernicus CAMS forecasts / ADS'
DOCS='https://ads.atmosphere.copernicus.eu/datasets/'+DATASET
MASS_DOCS='https://www.ecmwf.int/sites/default/files/elibrary/112024/81630-ifs-documentation-cy49r1-part-viii-atmospheric-composition.pdf'
CHLORIDE_DOCS='https://doi.org/10.1038/ncomms15883'
VERSION='cams-deposition-30day-signed-wet-v2'
YEAR=2025
MAX_BYTES=64*1024*1024
DRY_FACTOR=4.3
CHLORIDE_FRACTION=.55  # Explicit fresh sea-salt composition assumption, not an ADS chloride field.
BINS=('0.03-0.5um','0.5-5um','5-20um')
PROCESSES=(('dry_deposition',''),('sedimentation',''),('wet_deposition','_by_large_scale_precipitation'),('wet_deposition','_by_convective_precipitation'))
VARIABLES=[f'{prefix}_of_sea_salt_aerosol_{size}{suffix}' for prefix,suffix in PROCESSES for size in BINS]+['2m_temperature','2m_dewpoint_temperature','surface_pressure','sulphur_dioxide']
FLUX_IDS=tuple(range(215004,215016))
PARAM_IDS=FLUX_IDS+(167,168,134,210122)
_lock=threading.Lock()
WET_IDS=tuple(range(215010,215016))
WINDOW_DAYS=30
QUALITY_NOTE=('Negative wet-deposition samples, if present, are retained unchanged in signed period means; '
              'their cause is not assumed. Wet-derived values require source verification. '
              'The main corrosion scenario uses dry deposition plus gravitational settling only. '
              'The optional wet scenario is disabled when any wet input is negative. No values are clipped or filled with zero.')

def period(today=None):
    end=(today or datetime.now(timezone.utc).date())-timedelta(days=1)
    return end-timedelta(days=WINDOW_DAYS-1),end

def request_for(point,month=None,year=YEAR,*,today=None):
    validate(point)
    if month is not None:
        if not 1<=month<=12:raise ValueError('Invalid month')
        start,end=date(year,month,1),date(year,month,calendar.monthrange(year,month)[1])
    else:start,end=period(today)
    lat=round(max(-90,min(90,math.floor(point['lat']/.4+.5)*.4)),6)
    lon=round((math.floor(point['lon']/.4+.5)*.4+180)%360-180,6)
    return dict(variable=VARIABLES,date=f'{start}/{end}',
                time=['00:00'],leadtime_hour=[str(h) for h in range(3,25,3)],type=['forecast'],model_level=['137'],
                data_format='grib',area=[lat,lon,lat,lon])

def identity(point,today=None):
    return hashlib.sha256((VERSION+json.dumps(request_for(point,today=today),sort_keys=True)).encode()).hexdigest()[:24]

def base(point,today=None):
    start,end=period(today)
    return dict(source=SOURCE,sourceUrl=DOCS,dataset=DATASET,methodVersion=VERSION,
                requestedCoordinates=dict(point),periodStart=str(start),periodEnd=str(end),windowDays=WINDOW_DAYS,assessmentBasis='30-day seasonal scenario',
                resolutionDegrees=.4,modelLevel=137,expectedSamples=WINDOW_DAYS*8,
                sampling='00 UTC forecasts, lead hours 3/6/9/12/15/18/21/24, every day; mean of instantaneous 3-hourly samples',
                unit='mg/m²/day',seaSaltMassConvention='RH80%; dry mass = archived mass / 4.3',
                chlorideFraction=CHLORIDE_FRACTION,chlorideSource='Fresh sea-salt composition assumption (55% chloride)',
                chlorideSourceUrl=CHLORIDE_DOCS,massSourceUrl=MASS_DOCS)

def error_result(point,error,today=None):
    safe=cams.safe_error(error)
    message=str(safe)
    if safe.code=='licence':message='Accept the CAMS global forecasts dataset licence in ADS, then select Refresh data.'
    return dict(base(point,today),status='unavailable',errorCode=safe.code,message=message)

def is_current(result,point,today=None):
    start,end=period(today)
    return (result.get('status')=='ready' and result.get('methodVersion')==VERSION and
            result.get('requestedCoordinates')==point and result.get('periodStart')==str(start) and
            result.get('periodEnd')==str(end) and result.get('windowDays')==WINDOW_DAYS and
            result.get('sampleCount')==WINDOW_DAYS*8)

def lookup(point,cache_dir,force=False,today=None):
    today=today or datetime.now(timezone.utc).date()
    folder=Path(cache_dir)/identity(point,today);folder.mkdir(parents=True,exist_ok=True)
    with _lock:
        jobs=[]
        try:
            request=request_for(point,today=today);result_path=folder/'period.json';job_path=folder/'job.json'
            if result_path.exists():
                cached=json.loads(result_path.read_text(encoding='utf-8'))
                rebound=cams.for_point(cached,point)
                if is_current(rebound,point,today) and cached.get('requestParameters')==request:return rebound
            client=cams.make_client()
            record=json.loads(job_path.read_text(encoding='utf-8')) if job_path.exists() else None
            if record and record.get('requestParameters')!=request:record=None
            if record and force and record.get('failed'):record=None
            if record and record.get('failed'):raise cams.CamsError('processing','CAMS 30-day request failed. Select Refresh data to retry.')
            if record:
                try:job=client.client.get_remote(record['requestId'])
                except Exception as error:
                    if force and cams.safe_error(error).code=='expired':record=None
                    else:raise
            if record is None:
                job=client.retrieve(DATASET,request)
                record=dict(requestId=job.request_id,requestParameters=request,submittedAt=datetime.now(timezone.utc).isoformat())
                cams.write_json(job_path,record)
            status=job.status;checked=datetime.now(timezone.utc).isoformat(timespec='seconds')
            jobs.append(dict(period=request['date'],requestId=record['requestId'],submittedAt=record.get('submittedAt'),status=status,checkedAt=checked))
            cams.write_json(job_path,dict(record,lastStatus=status,lastCheckedAt=checked))
            response=dict(base(point,today),jobs=jobs,lastCheckedAt=checked,archiveNote=progress.ARCHIVE_NOTE)
            if status in ('accepted','running'):
                return dict(response,status='running' if status=='running' else 'queued',message=progress.message(response))
            if status!='successful':
                cams.write_json(job_path,dict(record,failed=True))
                raise cams.CamsError('processing','CAMS 30-day request failed. Select Refresh data to retry.')
            raw=folder/'period.grib'
            if not raw.exists():
                result=job.get_results()
                if result.content_length>MAX_BYTES:raise cams.CamsError('size','CAMS period file exceeds the download limit.')
                temporary=folder/(uuid.uuid4().hex+'.grib')
                result.download(str(temporary))
                if temporary.stat().st_size>MAX_BYTES:raise cams.CamsError('size','CAMS period file exceeds the download limit.')
                temporary.replace(raw)
            parsed=parse_grib(raw,point,today=today)
            response.update(parsed,status='ready',requestParameters=request,requestId=record['requestId'],
                            rawSha256=hashlib.sha256(raw.read_bytes()).hexdigest(),retrievedAt=datetime.now(timezone.utc).isoformat())
            response=cams.for_point(response,point)
            cams.write_json(result_path,response)
            return response
        except Exception as error:
            response=error_result(point,error,today)
            response.update(jobs=jobs,lastAttemptAt=datetime.now(timezone.utc).isoformat(timespec='seconds'))
            if response.get('errorCode') in ('connection','rate_limit'):
                response.update(retryable=True,retryAfterSeconds=120,
                                message='CAMS check interrupted; retrying automatically in 2 minutes. The existing 30-day request is retained.')
            return response


def parse_grib(path,point,month=None,year=YEAR,*,today=None):
    try:import eccodes as ec
    except ImportError:raise cams.CamsError('dependencies','CAMS deposition requires eccodes from requirements.txt.') from None
    if month is None:start,end=period(today);days=WINDOW_DAYS
    else:start=date(year,month,1);days=calendar.monthrange(year,month)[1]
    expected={(int((start+timedelta(days=d)).strftime('%Y%m%d')),h) for d in range(days) for h in range(3,25,3)}
    records={key:{} for key in PARAM_IDS};grid=None
    if Path(path).stat().st_size>MAX_BYTES:raise ValueError('File too large')
    with Path(path).open('rb') as stream:
        while True:
            g=ec.codes_grib_new_from_file(stream)
            if g is None:break
            try:
                param=ec.codes_get(g,'paramId')
                if param not in records:raise ValueError('Unexpected variable')
                if ec.codes_get(g,'numberOfDataPoints')!=1:raise ValueError('Expected the requested single grid point')
                if ec.codes_get(g,'numberOfMissing')!=0:raise ValueError('Missing sample')
                lat=float(ec.codes_get_array(g,'latitudes')[0]);lon=float((ec.codes_get_array(g,'longitudes')[0]+180)%360-180)
                if not all(math.isfinite(v) for v in (lat,lon)):raise ValueError('Invalid grid')
                if abs(lat-point['lat'])>.201 or abs((lon-point['lon']+180)%360-180)>.201:raise ValueError('Grid does not cover destination')
                if grid is not None and (lat,lon)!=grid:raise ValueError('Variable grids differ')
                grid=(lat,lon)
                hour=int(ec.codes_get(g,'endStep'));key=(int(ec.codes_get(g,'dataDate')),hour)
                if ec.codes_get(g,'dataTime')!=0 or ec.codes_get(g,'stepUnits')!=1 or ec.codes_get(g,'stepType')!='instant' or int(ec.codes_get(g,'startStep'))!=hour:raise ValueError('Unexpected time semantics')
                if key not in expected or key in records[param]:raise ValueError('Duplicate or unexpected sample')
                unit=ec.codes_get(g,'units').replace(' ','').replace('**','^')
                want='kgm^-2s^-1' if param in FLUX_IDS else 'K' if param in (167,168) else 'Pa' if param==134 else 'kgkg^-1'
                if unit!=want:raise ValueError('Unexpected units')
                if param==210122:
                    if ec.codes_get(g,'level')!=137 or ec.codes_get(g,'typeOfLevel') not in ('hybrid','hybridLayer'):raise ValueError('Expected lowest model level 137')
                elif param in FLUX_IDS and ec.codes_get(g,'typeOfLevel')!='surface':raise ValueError('Expected surface deposition')
                value=float(ec.codes_get_values(g)[0])
                if not math.isfinite(value) or (value<0 and param not in WET_IDS):raise ValueError('Invalid negative/nonfinite sample outside wet fluxes')
                records[param][key]=value
            finally:ec.codes_release(g)
    result=summarize_records(records,expected,grid,month)
    if month is None:
        result.update(sampleCount=result.pop('count'),periodStart=str(start),periodEnd=str(end),windowDays=WINDOW_DAYS,
                      detail='30-day forecast sample means, not annual climate statistics. All 240 three-hour samples per input checked. '+QUALITY_NOTE)
        result.pop('month',None)
        complete_means(result['means'])
    return result

def summarize_records(records,expected,grid,month):
    if grid is None or any(set(records[p])!=expected for p in PARAM_IDS):raise ValueError('Incomplete monthly series')
    if any(not math.isfinite(v) or (v<0 and p not in WET_IDS) for p,values in records.items() for v in values.values()):raise ValueError('Invalid sample values')
    sums={k:0.0 for k in ('dry','sedimentation','wetLargeScale','wetConvective','temperature','humidity','so2Volume')}
    for key in sorted(expected):
        for label,ids in [('dry',range(215004,215007)),('sedimentation',range(215007,215010)),('wetLargeScale',range(215010,215013)),('wetConvective',range(215013,215016))]:
            sums[label]+=sum(records[p][key] for p in ids)*1e6*86400/DRY_FACTOR
        kelvin=records[167][key];dew=records[168][key];pressure=records[134][key]
        if not 180<kelvin<340 or not 150<dew<=kelvin+.05 or not 30000<pressure<110000:raise ValueError('Invalid meteorology')
        t=kelvin-273.15;td=min(dew,kelvin)-273.15
        # Magnus over water, appropriate to a defined atmospheric RH approximation.
        vapor=610.94*math.exp(17.625*td/(td+243.04))
        saturation=610.94*math.exp(17.625*t/(t+243.04))
        rh=100*vapor/saturation
        density=(pressure-.378*vapor)/(287.05*kelvin)
        sums['temperature']+=t;sums['humidity']+=rh
        sums['so2Volume']+=records[210122][key]*1e9*density
    count=len(expected)
    negative={str(p):dict(count=sum(v<0 for v in values.values()),minimum=min(values.values()),unit='kg/m²/s') for p,values in records.items() if any(v<0 for v in values.values())}
    return dict(month=month,count=count,gridLatitude=grid[0],gridLongitude=grid[1],means={k:v/count for k,v in sums.items()},
                qualityFlags=['negative_wet_flux_samples'] if negative else [],negativeWetSamples=negative,wetScenarioUsable=not bool(negative))

def complete_means(means):
    dry=means['dry']+means['sedimentation'];wet=means['wetLargeScale']+means['wetConvective']
    means.update(dryAndSettling=dry,wet=wet,total=dry+wet,chlorideDryProxy=dry*CHLORIDE_FRACTION,
                 chlorideTotalProxy=(dry+wet)*CHLORIDE_FRACTION,so2DepositionProxy=.8*means['so2Volume'])

def aggregate(parts):
    if sorted(p['month'] for p in parts)!=list(range(1,13)):raise ValueError('Incomplete annual coverage')
    if any(p['count']!=calendar.monthrange(YEAR,p['month'])[1]*8 for p in parts):raise ValueError('Incomplete annual samples')
    if len({(p['gridLatitude'],p['gridLongitude']) for p in parts})!=1:raise ValueError('Monthly grids differ')
    keys={'dry','sedimentation','wetLargeScale','wetConvective','temperature','humidity','so2Volume'}
    for part in parts:
        if set(part['means'])!=keys:raise ValueError('Incomplete monthly statistics')
        for key,value in part['means'].items():
            if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or (key!='temperature' and value<0):raise ValueError('Invalid monthly statistics')
        if not -93.15<part['means']['temperature']<66.85 or not 0<=part['means']['humidity']<=100.000001:raise ValueError('Invalid monthly meteorology')
    count=sum(p['count'] for p in parts)
    means={k:sum(p['means'][k]*p['count'] for p in parts)/count for k in parts[0]['means']}
    dry=means['dry']+means['sedimentation'];wet=means['wetLargeScale']+means['wetConvective']
    means.update(dryAndSettling=dry,wet=wet,total=dry+wet,chlorideDryProxy=dry*CHLORIDE_FRACTION,
                 chlorideTotalProxy=(dry+wet)*CHLORIDE_FRACTION,so2DepositionProxy=.8*means['so2Volume'])
    return dict(sampleCount=count,gridLatitude=parts[0]['gridLatitude'],gridLongitude=parts[0]['gridLongitude'],means=means,
                monthly=parts,detail='Archived forecasts, not EAC4 reanalysis. All months and 3-hourly samples checked. Sea-salt deposition shown as dry mass (RH80% / 4.3). Dry deposition and gravitational settling are separate CAMS diagnostics. Chloride = 55% of dry sea-salt mass, assuming fresh sea salt; no chloride depletion or non-marine chloride sources. Ground flux is not a wet-candle measurement. SO2 volume uses surface pressure and 2m moist-air density as a near-surface approximation for ML137. RH uses 2m temperature/dewpoint. No missing sample is filled with zero.')
