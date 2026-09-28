"""Honest archive progress: remote activity is separate from verified months."""
from datetime import datetime,timezone

DOCS='https://confluence.ecmwf.int/spaces/CKB/pages/212454117/CAMS+Global+atmospheric+composition+forecast+data+documentation'
REQUESTS='https://ads.atmosphere.copernicus.eu/requests'
ARCHIVE_NOTE=('Sea-salt deposition is an ECMWF slow-access archive product (tape storage). '
              'Server processing can be slow even for one grid point; ADS does not provide a reliable completion time. '
              'One request covers the latest 30 complete forecast dates; its 240 samples per variable must be complete. '
              'Results are cached by grid and exact period. Existing requests resume without duplication.')

def elapsed(submitted,now=None):
    try:
        start=datetime.fromisoformat(submitted.replace('Z','+00:00'))
        if start.tzinfo is None:start=start.replace(tzinfo=timezone.utc)
        return max(0,int(((now or datetime.now(timezone.utc))-start).total_seconds()))
    except (ValueError,TypeError,AttributeError):return None

def duration(seconds):
    if seconds is None:return 'unknown'
    minutes=int(seconds)//60
    return f'{minutes//60} h {minutes%60} min' if minutes>=60 else f'{minutes} min'

def message(data):
    jobs=data.get('jobs',[])
    running=sum(j.get('status')=='running' for j in jobs)
    queued=sum(j.get('status')=='accepted' for j in jobs)
    basis="annual period" if data.get("assessmentBasis")=="Full calendar year" else "30-day window"
    text=f"CAMS {basis}: {data.get('periodStart','—')} to {data.get('periodEnd','—')}; {running} processing at ADS, {queued} queued."
    ages=[elapsed(j.get('submittedAt')) for j in jobs if j.get('status') in ('accepted','running')]
    ages=[age for age in ages if age is not None]
    if ages:text+=' Oldest active request: '+duration(max(ages))+'.'
    if data.get('lastCheckedAt'):text+=' Last checked: '+data['lastCheckedAt'].replace('T',' ').replace('+00:00',' UTC')+'.'
    return text

def value_label(data):
    progress=(str(data.get('completedMonths',0))+'/12 months') if data.get('assessmentBasis')=='Full calendar year' else '30-day window'
    if data.get('retryable'):return 'Connection retry pending'
    if data.get('status')=='running':return 'ADS processing · '+progress
    if data.get('status')=='queued':return 'ADS queued · '+progress
    if data.get('status')=='loading':return 'Checking ADS · '+progress
    return 'Licence required' if data.get('errorCode')=='licence' else 'Not available'

def detail(data):
    note=ARCHIVE_NOTE if data.get('assessmentBasis')!='Full calendar year' else ('Monthly full-year archive retrieval; at most two active monthly jobs. All 12 months and every three-hour sample are required. Completed months are cached and resumed; no partial-year extrapolation. ADS processing time is not predictable.')
    lines=[message(data),note]
    for j in data.get('jobs',[]):
        status={'accepted':'Queued at ADS','running':'Processing at ADS','successful':'Ready at ADS','failed':'Failed at ADS'}.get(j.get('status'),j.get('status','Unknown'))
        lines.append(f"Period {j.get('period','30 days')}: {status}\nRequest ID: {j.get('requestId','Not recorded')}\nSubmitted (UTC): {j.get('submittedAt','Not recorded')}\nLast checked (UTC): {j.get('checkedAt','Not recorded')}")
    return '\n\n'.join(lines)
