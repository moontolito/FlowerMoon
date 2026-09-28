"""Indicative exterior carbon-steel screening, never a certified ISO category."""
import math

VERSION='iso9223-steel-cams-seasonal-30day-v2'
SOURCE='ISO 9223:2012 + Copernicus CAMS'
DOCS='https://www.iso.org/standard/53499.html'
LIMITS={'temperature':(-17.1,28.7),'humidity':(34,93),'so2DepositionProxy':(.7,150.4),'chlorideDryProxy':(.4,760.5)}
THRESHOLDS=[('C1',1.3),('C2',25),('C3',50),('C4',80),('C5',200),('CX',700)]
ASSUMPTIONS=('30-DAY SEASONAL SCENARIO, not an annual site classification. The ISO annual-response equation is evaluated with 30-day means; '
             'the annualized result assumes these recent conditions persist. It is not measured loss over 30 days or a prediction for the coming year. '
             'Carbon steel exposed outdoors. CAMS ground deposition used as an uncalibrated proxy for the ISO wet-candle chloride input; '
             'fresh sea salt assumed to contain 55% chloride. Local sea spray, de-icing salt, chemical emissions, sheltered surfaces and '
             'chloride depletion are not resolved. Near-surface SO2 density conversion is approximate. '
             'This is a preliminary model-based screening result, not an ISO-conforming site classification or a paint-system specification. '
             'Verify the category before design or coating selection. It does not apply to indoor or immersed exposure.')

def category(rate):
    if isinstance(rate,bool) or not isinstance(rate,(int,float)) or not math.isfinite(rate) or rate<0:raise ValueError('Invalid corrosion rate')
    return next((label for label,limit in THRESHOLDS if rate<=limit),None)

def steel_rate(t,rh,pd,sd):
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (t,rh,pd,sd)):raise ValueError('Nonfinite corrosion input')
    if not -90<=t<=70 or not 0<=rh<=100 or pd<0 or sd<0:raise ValueError('Invalid corrosion input')
    ft=.150*(t-10) if t<=10 else -.054*(t-10)
    rate=1.77*pd**.52*math.exp(.020*rh+ft)+.102*sd**.62*math.exp(.033*rh+.040*t)
    if not math.isfinite(rate):raise ValueError('Invalid corrosion rate')
    return rate

def evaluate(deposition,point=None):
    result=dict(methodVersion=VERSION,source=SOURCE,sourceUrl=DOCS,status='unavailable',category=None,
                material='Carbon steel',exposure='Outdoor atmosphere',confidence='Low — model proxies; verification required',
                assumptions=ASSUMPTIONS,unit='µm/year',thresholds=dict(THRESHOLDS))
    if deposition.get('status')!='ready':
        result['reason']='Complete 30-day CAMS deposition and matching meteorology are required.';return result
    if point is not None and deposition.get('requestedCoordinates')!=point:
        result['reason']='The source data belongs to a different destination.';return result
    try:
        from deposition import WINDOW_DAYS,VERSION as DEPOSITION_VERSION
        from datetime import date
        days=(date.fromisoformat(deposition['periodEnd'])-date.fromisoformat(deposition['periodStart'])).days+1
        if deposition.get('methodVersion')!=DEPOSITION_VERSION or deposition.get('sampleCount')!=WINDOW_DAYS*8 or days!=WINDOW_DAYS or deposition.get('windowDays')!=WINDOW_DAYS:raise ValueError('Unverified 30-day coverage or method')
        values=deposition['means']
        inputs={name:values[name] for name in LIMITS}
        t,rh,pd,sd=(inputs[k] for k in ('temperature','humidity','so2DepositionProxy','chlorideDryProxy'))
        rate=steel_rate(t,rh,pd,sd)
        wet_rate=None
        wet_reason='Not calculated: wet-deposition source values need verification.'
        if deposition.get('wetScenarioUsable') and not deposition.get('qualityFlags'):
            total=values['chlorideTotalProxy']
            if not isinstance(total,(int,float)) or not math.isfinite(total) or total<sd:raise ValueError('Invalid total deposition scenario')
            wet_rate=steel_rate(t,rh,pd,total);wet_reason='Separate seasonal sensitivity scenario; not a confidence interval.'
        outside=[key for key,(lo,hi) in LIMITS.items() if not lo<=inputs[key]<=hi]
        estimate=category(rate)
        result.update(status='ready',category=estimate,rate=rate,inputs=inputs,periodStart=deposition['periodStart'],periodEnd=deposition['periodEnd'],
                      requestedCoordinates=deposition['requestedCoordinates'],gridLatitude=deposition['gridLatitude'],gridLongitude=deposition['gridLongitude'],
                      outsideCalibration=outside,extrapolated=bool(outside),wetScenarioRate=wet_rate,wetScenarioCategory=category(wet_rate) if wet_rate is not None else None,
                      wetScenarioReason=wet_reason,windowDays=WINDOW_DAYS,seasonal=True,
                      reason='30-day seasonal scenario — verify before use.' if estimate else 'Above the tabulated CX corrosion-rate range; specialist review required.',
                      formula='r = 1.77 Pd^0.52 exp(0.020 RH + fT) + 0.102 Sd^0.62 exp(0.033 RH + 0.040 T); fT=0.150(T-10) for T<=10, otherwise -0.054(T-10). Pd=0.8 times 30-day mean SO2 in µg/m³. ISO 9223:2012 Eq.1, Table 2 and Table 3; annual inputs replaced by 30-day means for a seasonal scenario, not a normative classification.')
        return result
    except (KeyError,TypeError,ValueError,OverflowError) as error:
        result['reason']='Corrosion inputs incomplete or invalid: '+str(error);return result
