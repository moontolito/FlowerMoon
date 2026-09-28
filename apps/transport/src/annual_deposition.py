"""Opt-in CAMS annual retrieval: resumable monthly jobs, at most two active."""
from datetime import date,datetime,timezone
from pathlib import Path
import calendar,hashlib,json,math,threading,uuid
import cams,deposition

VERSION='cams-deposition-full-calendar-year-v1'
SOURCE=deposition.SOURCE
DOCS=deposition.DOCS
MAX_ACTIVE=2
_lock=threading.Lock()

def reference_year(today=None):return (today or datetime.now(timezone.utc).date()).year-1
def period(year=None):
    year=reference_year() if year is None else year
    if isinstance(year,bool) or not isinstance(year,int) or not 2016<=year<=reference_year():
        raise ValueError('Choose a complete CAMS calendar year from 2016 onwards.')
    return date(year,1,1),date(year,12,31)

def base(point,year=None):
    start,end=period(year);days=(end-start).days+1
    deposition.validate(point)
    return dict(source=SOURCE,sourceUrl=DOCS,dataset=deposition.DATASET,methodVersion=VERSION,
        requestedCoordinates=dict(point),year=start.year,periodStart=str(start),periodEnd=str(end),
        windowDays=days,expectedSamples=days*8,completedMonths=0,assessmentBasis='Full calendar year',
        resolutionDegrees=.4,modelLevel=137,unit='mg/m²/day',
        sampling='All calendar dates; 00 UTC forecasts at lead hours 3/6/9/12/15/18/21/24. Annual means weighted by verified sample counts.')

def identity(point,year=None):
    year=period(year)[0].year
    request=deposition.request_for(point,1,year)
    return hashlib.sha256((VERSION+json.dumps(request,sort_keys=True)).encode()).hexdigest()[:24]

def aggregate(parts,year):
    start,end=period(year)
    if sorted(p['month'] for p in parts)!=list(range(1,13)):raise ValueError('All 12 months are required')
    if any(p['count']!=calendar.monthrange(year,p['month'])[1]*8 for p in parts):raise ValueError('Incomplete annual sample coverage')
    if len({(p['gridLatitude'],p['gridLongitude']) for p in parts})!=1:raise ValueError('Monthly grids differ')
    keys={'dry','sedimentation','wetLargeScale','wetConvective','temperature','humidity','so2Volume'}
    for part in parts:
        if set(part['means'])!=keys:raise ValueError('Incomplete monthly inputs')
        for key,value in part['means'].items():
            if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value):raise ValueError('Invalid monthly input')
            if key not in ('temperature','wetLargeScale','wetConvective') and value<0:raise ValueError('Invalid negative input')
        if not -93.15<part['means']['temperature']<66.85 or not 0<=part['means']['humidity']<=100:raise ValueError('Invalid meteorology')
    count=sum(p['count'] for p in parts)
    assert count==((end-start).days+1)*8
    means={k:sum(p['means'][k]*p['count'] for p in parts)/count for k in keys}
    deposition.complete_means(means)
    flags=sorted({flag for p in parts for flag in p.get('qualityFlags',[])})
    return dict(sampleCount=count,completedMonths=12,gridLatitude=parts[0]['gridLatitude'],gridLongitude=parts[0]['gridLongitude'],
        means=means,monthly=parts,qualityFlags=flags,
        wetScenarioUsable=not flags and all(p.get('wetScenarioUsable',False) for p in parts),
        detail='All 12 months verified. Annual means use the number of three-hour samples, including leap days. No missing samples are filled or extrapolated. '+deposition.QUALITY_NOTE)

def is_current(result,point,year=None):
    info=base(point,year)
    return (result.get('status')=='ready' and all(result.get(k)==info[k] for k in
            ('methodVersion','periodStart','periodEnd','requestedCoordinates','windowDays'))
            and result.get('completedMonths')==12 and result.get('sampleCount')==info['expectedSamples'])

def error_result(point,error,year=None):
    safe=cams.safe_error(error)
    message=str(safe)
    if safe.code=='licence':message='Accept the CAMS global forecasts dataset licence in ADS, then select Refresh data.'
    result=dict(base(point,year),status='unavailable',errorCode=safe.code,message=message)
    if safe.code in ('connection','rate_limit'):result.update(retryable=True,retryAfterSeconds=120)
    return result

def lookup(point,cache_dir,force=False,year=None,cancelled=lambda:False):
    info=base(point,year);year=info['year'];jobs=[];parts=[];active=0
    folder=Path(cache_dir)/identity(point,year)
    with _lock:
        if cancelled():return dict(info,status='disabled',message='Annual retrieval disabled.')
        folder.mkdir(parents=True,exist_ok=True)
        try:
            final=folder/'annual.json'
            if final.exists():
                result=cams.for_point(json.loads(final.read_text(encoding='utf-8')),point)
                if is_current(result,point,year):
                    aggregate(result['monthly'],year)
                    return result
            client=None
            for month in range(1,13):
                if cancelled():return dict(info,status='disabled',completedMonths=len(parts),jobs=jobs)
                request=deposition.request_for(point,month,year)
                parsed_path=folder/f'{month:02d}-parsed.json';job_path=folder/f'{month:02d}-job.json'
                if parsed_path.exists():
                    part=json.loads(parsed_path.read_text(encoding='utf-8'))
                    if part.get('requestParameters')==request and part.get('methodVersion')==VERSION:
                        parts.append(part)
                        jobs.append(dict(month=month,status='successful',period=request['date'],requestId=part.get('requestId')))
                        continue
                record=json.loads(job_path.read_text(encoding='utf-8')) if job_path.exists() else None
                if record and record.get('requestParameters')!=request:record=None
                if record and record.get('failed'):
                    if force:record=None
                    else:raise cams.CamsError('processing',f'CAMS month {month:02d} failed. Refresh data to retry.')
                if record is None and active>=MAX_ACTIVE:continue
                if client is None:client=cams.make_client()
                if cancelled():return dict(info,status='disabled',completedMonths=len(parts),jobs=jobs)
                if record:
                    try:job=client.client.get_remote(record['requestId'])
                    except Exception as error:
                        if force and cams.safe_error(error).code=='expired':record=None
                        else:raise
                if record is None:
                    if active>=MAX_ACTIVE:continue
                    job=client.retrieve(deposition.DATASET,request)
                    record=dict(requestId=job.request_id,requestParameters=request,submittedAt=datetime.now(timezone.utc).isoformat())
                    cams.write_json(job_path,record)
                status=job.status
                audit=dict(month=month,period=request['date'],requestId=record['requestId'],status=status,
                           submittedAt=record.get('submittedAt'),checkedAt=datetime.now(timezone.utc).isoformat())
                jobs.append(audit)
                if status in ('accepted','running'):active+=1;continue
                if status!='successful':
                    cams.write_json(job_path,dict(record,failed=True))
                    raise cams.CamsError('processing',f'CAMS month {month:02d} failed. Refresh data to retry.')
                if cancelled():return dict(info,status='disabled',completedMonths=len(parts),jobs=jobs)
                raw=folder/f'{month:02d}.grib'
                if not raw.exists():
                    remote=job.get_results()
                    if remote.content_length>deposition.MAX_BYTES:raise cams.CamsError('size','Monthly CAMS file exceeds download limit.')
                    temp=folder/(uuid.uuid4().hex+'.grib');remote.download(str(temp))
                    if temp.stat().st_size>deposition.MAX_BYTES:raise cams.CamsError('size','Monthly CAMS file exceeds download limit.')
                    temp.replace(raw)
                part=deposition.parse_grib(raw,point,month,year)
                part.update(requestParameters=request,methodVersion=VERSION,requestId=record['requestId'],rawSha256=hashlib.sha256(raw.read_bytes()).hexdigest())
                cams.write_json(parsed_path,part);parts.append(part)
            response=dict(info,jobs=jobs,completedMonths=len(parts),lastCheckedAt=datetime.now(timezone.utc).isoformat())
            if len(parts)!=12:
                response.update(status='running' if any(j['status']=='running' for j in jobs) else 'queued',
                    message=f'Annual corrosivity: {len(parts)}/12 months verified for {year}. ADS archive requests resume automatically while enabled.')
                return response
            response.update(aggregate(parts,year),status='ready',retrievedAt=datetime.now(timezone.utc).isoformat())
            response=cams.for_point(response,point);cams.write_json(final,response)
            return response
        except Exception as error:
            return dict(error_result(point,error,year),jobs=jobs,completedMonths=len(parts))
