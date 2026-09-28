"""Full-year model-based estimate; CAMS chloride remains a non-standard proxy."""
import annual_deposition as annual
from corrosion import steel_rate,category,LIMITS,THRESHOLDS,SOURCE,DOCS

VERSION='iso9223-steel-cams-full-year-v1'
ASSUMPTIONS=('Full-calendar-year model-based estimate for outdoor carbon steel. '
    'ISO 9223 annual-response equation uses verified annual means of T, RH, SO2 and the chloride proxy. '
    'CAMS ground flux is not the ISO 9225 wet-candle measurement: no validated equivalence is claimed. '
    'Fresh sea salt is assumed to contain 55% chloride; RH80% mass is divided by 4.3. '
    'Local sea spray, sheltered surfaces, de-icing salt and chloride depletion are not resolved. '
    'Verify before coating selection. This is not a certified ISO site classification or a paint-system specification.')
FORMULA=('ISO 9223:2012 Eq.1: r = 1.77 Pd^0.52 exp(0.020 RH + fT) + 0.102 Sd^0.62 exp(0.033 RH + 0.040 T); '
         'fT=0.150(T-10) for T<=10, otherwise -0.054(T-10). T and RH are annual means; '
         'Pd=0.8 times annual mean SO2 in µg/m³; Sd is the annual dry + settling chloride proxy. '
         'r is estimated first-year loss in µm/year. Table 2 maps this rate to C1–CX; Table 3 defines calibration ranges.')

def evaluate(data,point=None):
    result=dict(status='unavailable',category=None,methodVersion=VERSION,source=SOURCE,sourceUrl=DOCS,
                assumptions=ASSUMPTIONS,formula=FORMULA,unit='µm/year',seasonal=False,thresholds=dict(THRESHOLDS))
    try:
        year=data.get('year')
        if year is None or not annual.is_current(data,point if point is not None else data.get('requestedCoordinates'),year):
            raise ValueError('A complete verified calendar year for this destination is required; 30-day results are not used.')
        validated=annual.aggregate(data['monthly'],year)
        # Recompute from monthly records, not a stale stored category/annual total.
        values=validated['means'];inputs={key:values[key] for key in LIMITS}
        t,rh,pd,sd=(inputs[k] for k in LIMITS)
        rate=steel_rate(t,rh,pd,sd);label=category(rate)
        wet_rate=steel_rate(t,rh,pd,values['chlorideTotalProxy']) if validated['wetScenarioUsable'] else None
        outside=[k for k,(lo,hi) in LIMITS.items() if not lo<=inputs[k]<=hi]
        result.update(status='ready',category=label,rate=rate,inputs=inputs,year=year,periodStart=data['periodStart'],periodEnd=data['periodEnd'],
            requestedCoordinates=data['requestedCoordinates'],gridLatitude=data['gridLatitude'],gridLongitude=data['gridLongitude'],
            windowDays=data['windowDays'],outsideCalibration=outside,extrapolated=bool(outside),
            wetScenarioRate=wet_rate,wetScenarioCategory=category(wet_rate) if wet_rate is not None else None,
            wetScenarioReason='Annual sensitivity scenario only; ground flux is not wet-candle chloride.' if wet_rate is not None else 'Wet scenario unavailable: source verification required.',
            reason='Annual estimate using model proxies — verify.' if label else 'Above CX tabulated range; specialist review required.')
    except (ValueError,KeyError,TypeError,OverflowError) as error:result['reason']=str(error)
    return result
