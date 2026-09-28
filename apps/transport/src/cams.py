"""Global CAMS EAC4 monthly exposure, at the destination's nearest ML60 cell.

Native kg/kg values are converted only to micrograms/kg. Sea salt includes
water at 80% RH; its dry equivalent is explicitly divided by ECMWF's 4.3 factor.
Neither mixing ratio is a deposition flux or an ISO corrosivity category.
"""
from datetime import date,datetime,timezone
from pathlib import Path
import calendar,hashlib,io,json,math,os,threading,time,uuid,zipfile
import ads_credentials
from site_environment.geography import validate

DATASET='cams-global-reanalysis-eac4-monthly'
SOURCE='Copernicus CAMS EAC4 / ADS'
DOCS='https://ads.atmosphere.copernicus.eu/datasets/'+DATASET
SALT_DOCS='https://confluence.ecmwf.int/plugins/viewsource/viewpagesrc.action?pageId=70951402'
VERSION='cams-eac4-monthly-ml60-v1'
# Latest complete year verified against the ADS catalogue, September 2026.
YEAR=2025
VARIABLES=['sulphur_dioxide','sea_salt_aerosol_0.03-0.5um_mixing_ratio','sea_salt_aerosol_0.5-5um_mixing_ratio','sea_salt_aerosol_5-20um_mixing_ratio']
ALIASES=dict(so2=('so2','sulphur_dioxide'),ss1=('aermr01',VARIABLES[1]),ss2=('aermr02',VARIABLES[2]),ss3=('aermr03',VARIABLES[3]))
MAX_BYTES=32*1024*1024
_lock=threading.Lock()

def enabled():
    return os.environ.get('FLOWERMOON_CAMS_ENABLED','1')!='0'

class CamsError(ValueError):
    def __init__(self,code,message):super().__init__(message);self.code=code

def request_for(point,year=YEAR):
    validate(point)
    lat=max(-90,min(90,math.floor(point['lat']/.75+.5)*.75))
    lon=(math.floor(point['lon']/.75+.5)*.75+180)%360-180
    return dict(variable=VARIABLES,model_level=['60'],year=[str(year)],month=[f'{m:02d}' for m in range(1,13)],
                product_type=['monthly_mean'],data_format='netcdf_zip',
                area=[min(90,lat+.75),max(-180,lon-.75),max(-90,lat-.75),min(179.25,lon+.75)])

def fingerprint(request):
    return hashlib.sha256((VERSION+json.dumps(request,sort_keys=True)).encode()).hexdigest()[:24]

def write_json(path,value):
    temp=path.with_suffix('.'+uuid.uuid4().hex+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)

def make_client():
    try:import cdsapi
    except ImportError:raise CamsError('dependencies','CAMS requires cdsapi and netCDF4 from requirements.txt.') from None
    try:url,key=ads_credentials.configuration()
    except ValueError as error:raise CamsError('credentials',str(error)) from None
    return cdsapi.Client(url=url,key=key,quiet=True,debug=False,progress=False,timeout=30,retry_max=1,sleep_max=5,wait_until_complete=False)

def safe_error(error):
    if isinstance(error,CamsError):return error
    # Inspect provider messages only to classify; never persist server messages or tokens.
    message=str(error).lower();response=getattr(error,'response',None)
    code=getattr(response,'status_code',None)
    if 'licen' in message and ('accept' in message or code==403):
        return CamsError('licence','Accept the CAMS EAC4 monthly dataset licence in your ADS account, then select Refresh data.')
    if code in (401,403):return CamsError('credentials','ADS denied access. Check the local ADS key and dataset permissions.')
    if code==429:return CamsError('rate_limit','ADS request limit reached. Try Refresh data later.')
    if code==404:return CamsError('expired','The ADS job is no longer available. Select Refresh data to request it again.')
    if code in (400,422):return CamsError('request','ADS could not process the requested CAMS year or variables. No values were substituted.')
    if isinstance(error,(ValueError,KeyError,zipfile.BadZipFile)):return CamsError('invalid_data','CAMS returned incomplete or unexpected data. No values were substituted.')
    return CamsError('connection','CAMS could not be reached or downloaded. Check the connection and select Refresh data.')

def base_result(request):
    year=int(request['year'][0])
    return dict(source=SOURCE,sourceUrl=DOCS,dataset=DATASET,methodVersion=VERSION,periodStart=f'{year}-01-01',periodEnd=f'{year}-12-31',
                modelLevel=60,resolutionDegrees=.75,unit='µg/kg',nativeUnit='kg/kg',requestParameters=request)

def for_point(result,point):
    result=dict(result,requestedCoordinates=dict(point))
    if result.get('gridLatitude') is not None:
        lat1,lat2=map(math.radians,(point['lat'],result['gridLatitude']))
        dlon=math.radians((result['gridLongitude']-point['lon']+180)%360-180)
        a=math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
        result['gridDistanceKm']=round(6371*2*math.asin(min(1,math.sqrt(a))),2)
    return result

def lookup(point,cache_dir,force=False):
    request=request_for(point);folder=Path(cache_dir);folder.mkdir(parents=True,exist_ok=True)
    ident=fingerprint(request);result_path=folder/(ident+'.json');job_path=folder/(ident+'-job.json')
    with _lock:
        if not force and result_path.is_file() and time.time()-result_path.stat().st_mtime<30*86400:
            try:
                result=json.loads(result_path.read_text(encoding='utf-8'))
                if result.get('methodVersion')==VERSION and result.get('status')=='ready':return for_point(result,point)
            except (OSError,ValueError):pass
        try:
            client=make_client();record=None
            if not force and job_path.is_file():
                record=json.loads(job_path.read_text(encoding='utf-8'))
                if record.get('requestParameters')!=request:record=None
            if record:
                job=client.client.get_remote(record['requestId'])
            else:
                job=client.retrieve(DATASET,request)
                record=dict(requestId=job.request_id,requestParameters=request,submittedAt=datetime.now(timezone.utc).isoformat())
                write_json(job_path,record)
            status=job.status
            if status in ('accepted','running'):
                return for_point(dict(base_result(request),status='queued' if status=='accepted' else 'running',
                                      message='CAMS is preparing the destination data. This view updates automatically.'),point)
            if status!='successful':raise CamsError('processing','The CAMS data request did not complete. Select Refresh data to try again.')
            results=job.get_results()
            if results.content_length>MAX_BYTES:raise CamsError('size','CAMS result exceeds the local download limit.')
            raw=folder/(ident+'-'+uuid.uuid4().hex[:8]+'.zip')
            results.download(str(raw))
            if raw.stat().st_size>MAX_BYTES:raise CamsError('size','CAMS result exceeds the local download limit.')
            result=parse_download(raw,point,int(request['year'][0]))
            result.update(base_result(request));result.update(status='ready',retrievedAt=datetime.now(timezone.utc).isoformat(),rawSha256=hashlib.sha256(raw.read_bytes()).hexdigest())
            write_json(result_path,result)
            return for_point(result,point)
        except Exception as error:raise safe_error(error) from None

def parse_download(path,point,year=YEAR):
    try:import numpy as np;from netCDF4 import Dataset,num2date
    except ImportError:raise CamsError('dependencies','CAMS requires netCDF4 from requirements.txt.') from None
    payload=Path(path).read_bytes()
    if len(payload)>MAX_BYTES:raise ValueError('CAMS file too large')
    if zipfile.is_zipfile(io.BytesIO(payload)):
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            entries=[v for v in archive.infolist() if v.filename.lower().endswith('.nc')]
            if not entries or sum(v.file_size for v in entries)>MAX_BYTES:raise ValueError('Invalid CAMS archive')
            files=[archive.read(v) for v in entries]
    else:files=[payload]
    data={};grid=None
    for content in files:
        with Dataset('cams.nc',memory=content) as ds:
            lat_name=next((n for n in ('latitude','lat') if n in ds.variables),None)
            lon_name=next((n for n in ('longitude','lon') if n in ds.variables),None)
            if lat_name is None or lon_name is None:raise ValueError('Missing spatial coordinates')
            lats=np.asarray(ds[lat_name][:]);lons=np.asarray(ds[lon_name][:])
            if lats.ndim!=1 or lons.ndim!=1 or not lats.size or not lons.size:raise ValueError('Unexpected spatial grid')
            yi=int(np.argmin(abs(lats-point['lat'])));xi=int(np.argmin(abs((lons-point['lon']+180)%360-180)))
            cell=(float(lats[yi]),float((lons[xi]+180)%360-180))
            if abs(cell[0]-point['lat'])>.376 or abs((cell[1]-point['lon']+180)%360-180)>.376:raise ValueError('Grid does not cover destination')
            if grid is not None and grid!=cell:raise ValueError('Inconsistent variable grid')
            grid=cell
            lat_dim=ds[lat_name].dimensions[0];lon_dim=ds[lon_name].dimensions[0]
            for key,aliases in ALIASES.items():
                name=next((n for n in aliases if n in ds.variables),None)
                if not name:continue
                var=ds[name];unit=str(getattr(var,'units','')).replace(' ','').replace('**','^')
                if unit not in ('kgkg^-1','kgkg-1','kg/kg'):raise ValueError('Unexpected units')
                time_dim=next((d for d in var.dimensions if d in ('time','valid_time')),None)
                if not time_dim or time_dim not in ds.variables:raise ValueError('Missing monthly time axis')
                indices=[];level_found=False
                for dim in var.dimensions:
                    if dim==time_dim:indices.append(slice(None))
                    elif dim==lat_dim:indices.append(yi)
                    elif dim==lon_dim:indices.append(xi)
                    elif dim in ('level','model_level','hybrid'):
                        values=np.asarray(ds[dim][:]).reshape(-1);found=np.where(values==60)[0]
                        if len(found)!=1:raise ValueError('Expected model level 60')
                        indices.append(int(found[0]));level_found=True
                    elif len(ds.dimensions[dim])==1:indices.append(0)
                    else:raise ValueError('Unexpected variable dimension')
                if not level_found:
                    level_found=any(n in ds.variables and np.asarray(ds[n][:]).size==1 and float(np.asarray(ds[n][:]).reshape(-1)[0])==60 for n in ('level','model_level','hybrid'))
                if not level_found and getattr(var,'GRIB_level',None)!=60:raise ValueError('Model level cannot be verified')
                values=np.ma.asarray(var[tuple(indices)]).reshape(-1)
                tv=ds[time_dim];dates=num2date(tv[:],tv.units,calendar=getattr(tv,'calendar','standard'))
                if len(values)!=len(dates):raise ValueError('Time/value length mismatch')
                months=data.setdefault(key,{})
                for when,value in zip(dates,values):
                    if when.year!=year or when.month in months or np.ma.is_masked(value) or not math.isfinite(float(value)) or float(value)<0:raise ValueError('Invalid or duplicate monthly value')
                    months[when.month]=float(value)*1e9
    if any(set(data.get(key,{}))!=set(range(1,13)) for key in ALIASES):raise ValueError('Incomplete annual series')
    def stats(values):
        return dict(mean=sum(values[m]*calendar.monthrange(year,m)[1] for m in range(1,13))/(366 if calendar.isleap(year) else 365),
                    minimumMonthlyMean=min(values.values()),maximumMonthlyMean=max(values.values()),monthly=[values[m] for m in range(1,13)])
    total={m:sum(data[k][m] for k in ('ss1','ss2','ss3')) for m in range(1,13)}
    return dict(gridLatitude=grid[0],gridLongitude=grid[1],so2=stats(data['so2']),seaSalt=stats(total),
                seaSaltDry=stats({m:v/4.3 for m,v in total.items()}),seaSaltBins={k:stats(data[k]) for k in ('ss1','ss2','ss3')},
                statistic='Calendar-day-weighted annual mean of 12 monthly means',
                detail='Lowest model layer (ML60), nearest 0.75° grid cell. Reanalysis, not a site sensor. Native kg/kg multiplied by 1e9 to give µg/kg of air. Sea salt is the sum of three size bins at 80% RH; dry equivalent divides that sum by 4.3. Monthly minima/maxima are extrema of monthly means, not hourly extremes. These are not deposition fluxes and do not establish ISO corrosivity.')
