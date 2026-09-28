"""Read-only, row-specific explanations of the methods actually used by the app."""
import math
import re
from urllib.parse import urlsplit
from site_overview import rows, display_rows
from site_conditions import get


def safe_url(value):
    try:
        p = urlsplit(value)
        return value if p.scheme in ('http', 'https') and p.hostname and not p.username and not p.password and not p.query else ''
    except (ValueError, TypeError):
        return ''


def number(value):
    return f'{value:.8g}' if isinstance(value, (int, float)) and not isinstance(value, bool) else 'Not available'


def record(site, key):
    if key=='seismic.pga':
        import gem_hazard
        return gem_hazard.current(site)
    if key in ('design', 'daily'): return site.get('climate', {})
    if key.startswith('humidity.'): return site.get('humidityAnalysis', {})
    if key.startswith('airQuality.'): return site.get('airQuality', {})
    if key.startswith(('deposition.', 'corrosion.')) or key == 'environment.suggestedCorrosivity':
        import annual_deposition
        data=site.get('deposition',{})
        return data if data.get('methodVersion')==annual_deposition.VERSION else {'status':'pending','assessmentBasis':'Full calendar year','detail':'Waiting for full-year data; legacy seasonal records are not annual inputs.'}
    if key in ('environment.siteAltitudeM', 'transport.maxAltitudeM'): return site.get('elevationAnalysis', {})
    if key == 'coast': return site.get('coastalDistance', {})
    if key == 'country': return site.get('locationContext', {}).get('geography', {})
    if key == 'region': return site.get('administrativeRegion', {})
    try: return get(site, key)
    except (KeyError, ValueError): return {}


def build(site, key):
    row = next((r for r in display_rows(site)+rows(site) if r['key'] == key), None)
    if row is None: return None
    doc = dict(title=row['label'], value=row['value'], sections=[], links=[])
    def section(title, body):
        if body: doc['sections'].append((title, str(body)))
    def link(label, url):
        url = safe_url(url)
        if url and all(u != url for _, u in doc['links']): doc['links'].append((label, url))
    section('Meaning / use', row.get('meaning',''))
    if row['section']:
        section('Dataset',row.get('detail',''));return doc
    data = record(site, key)
    if (key.startswith(('deposition.','corrosion.')) or key=='environment.suggestedCorrosivity') and not site.get('corrosivityEnabled',False):
        section('Optional annual assessment','Disabled. Enable Calculate annual corrosivity in Settings. No new corrosion data is requested while disabled; old 30-day results are not used as annual inputs.')
        return doc
    try: field = get(site, key)
    except (KeyError, ValueError): field = {}
    manual = bool(field.get('manualOverride'))
    pair_keys = {'design': ('temperature.maxDesign','temperature.minDesign'), 'daily': ('temperature.maxDailyAverage','temperature.minDailyAverage'), 'humidity.summary': ('humidity.maximum','humidity.mean','humidity.minimum')}.get(key, ())
    if pair_keys and all(get(site,k).get('manualOverride') for k in pair_keys):
        manual = True
        field = dict(reviewRequired=any(get(site,k).get('reviewRequired') for k in pair_keys))
    section('Source & location', f"Source: {row['source']}\nApplies to: {row['reference']}\nDelivery destination: {site.get('destinationAddress') or 'Not selected'}\nDestination coordinates (WGS84): {site.get('destinationCoordinates') or 'Not selected'}")
    link(row['source'], row['url'])
    if manual:
        section('Manual value', 'This displayed value was entered by a user. It was not downloaded or calculated by the application. No formula is attributed to this manual value.' + ('\nREVIEW REQUIRED: retained from the previous destination.' if field.get('reviewRequired') else ''))
        section('Entry record', '\n'.join(f'{name}: {field[name]}' for name in ('lastUpdated', 'detail') if field.get(name)))
        # A model method must never be presented as the origin of a manual override.
        doc['links'] = []
        return doc

    meta = [('status','Retrieval status'), ('periodStart','Period start (UTC)'), ('periodEnd','Period end (UTC)'),
            ('requestedCoordinates','Requested coordinates'), ('gridLatitude','Model grid latitude'), ('gridLongitude','Model grid longitude'),
            ('gridElevationM','Model grid elevation (m)'), ('gridDistanceKm','Distance to model grid (km)'),
            ('resolutionDegrees','Grid spacing (degrees)'), ('modelLevel','Model level'), ('sampling','Sampling'),
            ('sampleCount','Samples per input'), ('expectedSamples','Expected samples per input'), ('validHours','Valid hours'),
            ('expectedHours','Expected hours'), ('validFraction','Valid fraction'), ('days','Days'), ('coverage','Coverage')]
    section('Data coverage', '\n'.join(f'{label}: {data[k]}' for k,label in meta if data.get(k) is not None))

    if key in ('design', 'daily'):
        keys = ('temperature.maxDesign','temperature.minDesign') if key == 'design' else ('temperature.maxDailyAverage','temperature.minDailyAverage')
        section('Inputs used', '\n'.join(f"{k.split('.')[1]}: {number(get(site,k).get('value'))} °C — {'manual entry' if get(site,k).get('manualOverride') else get(site,k).get('source','Not available')}" + ('; review required' if get(site,k).get('reviewRequired') else '') for k in keys))
        section('Method for automatic values', 'Open-Meteo Historical API, ERA5 reanalysis, air temperature at 2 m. The requested window is the last 30 complete calendar years.\n' +
                ('Maximum = max(daily temperature_2m_max); minimum = min(daily temperature_2m_min).' if key == 'design' else 'Maximum daily mean = max(temperature_2m_mean); minimum daily mean = min(temperature_2m_mean). Daily means are supplied by the provider, not calculated as (daily maximum + daily minimum) / 2.') +
                '\nThese describe the returned weather grid, not a sensor at the delivery point. The method applies only to automatic values; manual entries are listed separately above.')
        dates = ('maximumDate','minimumDate') if key == 'design' else ('maxDailyMeanDate','minDailyMeanDate')
        section('Dates of extremes', '\n'.join(f'{k}: {data[k]}' for k in dates if data.get(k)))
    elif key.startswith('humidity.'):
        if key=='humidity.summary':
            section('Values in display order', '\n'.join(f"{label}: {number(get(site,'humidity.'+name).get('value'))} % — {'manual entry' if get(site,'humidity.'+name).get('manualOverride') else get(site,'humidity.'+name).get('source','Not available')}" for name,label in [('maximum','Maximum'),('mean','Mean'),('minimum','Minimum')]))
        section('Method', 'Input: hourly relative_humidity_2m (%) from Open-Meteo ERA5, UTC.\nMaximum = max(valid hourly RH); minimum = min(valid hourly RH).\nMean = sum(valid hourly RH) / number of valid hours.\nOnly finite values from 0 to 100% are included. If coverage is incomplete, the statistics describe available hours only. These long-term statistics are separate from the annual CAMS humidity used for corrosion.')
        section('Individual sources and retained values',row['detail'])
    elif key.startswith('airQuality.'):
        import cams
        item = data.get(key.split('.')[1], {})
        section('Method', 'CAMS EAC4 monthly reanalysis, lowest model level ML60, 0.75° grid.\nMixing ratio (µg/kg) = provider mixing ratio (kg/kg) × 10⁹.\nAnnual mean = sum(monthly mean × days in month) / total days in year. All 12 months are required.\nSea-salt mass = sum of radius bins 0.03–0.5, 0.5–5 and 5–20 µm (80% RH convention).\nDry-equivalent sea salt = sea-salt mass at RH80% / 4.3.\nThese are model mixing ratios; they are not surface chloride deposition and are not the annual forecast inputs used by the corrosion screening.')
        section('Stored annual statistics', '\n'.join(f'{k}: {number(item[k])} µg/kg' for k in ('mean','minimumMonthlyMean','maximumMonthlyMean') if item.get(k) is not None))
        section('Monthly inputs (January → December)', ', '.join(number(v) for v in item.get('monthly', [])))
        link('CAMS EAC4 dataset', cams.DOCS); link('ECMWF sea-salt mass convention', cams.SALT_DOCS)
    elif key.startswith(('deposition.', 'corrosion.')) or key == 'environment.suggestedCorrosivity':
        import deposition, annual_corrosion as corrosion
        import deposition_progress
        means = data.get('means', {}) if data.get('status') == 'ready' else {}
        if key in ('deposition.wet','deposition.total','deposition.chlorideTotalProxy'):
            section('Why this is separate from the main category', 'The main category uses Sd = 0.55 × (dry deposition + gravitational settling). Wet deposition and totals are retained for comparison; they are not additional terms in that equation. Ground deposition is already an uncalibrated proxy for the ISO chloride measurement, so adding rain removal is not assumed to improve it.\n'+('The source contains flagged wet-deposition samples, so the optional total-chloride sensitivity scenario is also disabled until those values are verified.' if data.get('qualityFlags') else 'When valid, total chloride is used only in a separate sensitivity scenario shown in the category details.'))
        if data.get('status')!='ready':
            section('Archive request progress', deposition_progress.detail(data))
            link('My Copernicus ADS requests', deposition_progress.REQUESTS)
        link('ECMWF archive access documentation', deposition_progress.DOCS)
        section('Forecast inputs & aggregation', 'CAMS global atmospheric composition forecasts via the ADS API. 0.4° grid; nearest requested grid point. Each day uses the 00 UTC forecast at leads 3, 6, 9, 12, 15, 18, 21 and 24 hours.\nFluxes are instantaneous kg/m²/s; meteorology is 2 m temperature, 2 m dewpoint and surface pressure. SO₂ is mixing ratio at model level 137.\nAnnual mean = sum(monthly mean × verified sample count) / sum(sample counts). Twelve monthly requests cover January 1 to December 31 of the last complete year, including leap days (2920 or 2928 samples per input). All 16 inputs must have complete sampling; missing values are never filled with zero. The last lead-hour sample is valid at 00 UTC on the next calendar day. Forecast model upgrades can affect consistency within the archive.')
        section('Source quality checks', deposition.QUALITY_NOTE)
        if data.get('negativeWetSamples'):
            section('Wet-deposition source flags', '\n'.join(f"Parameter {param}: {item['count']} negative samples; minimum {item['minimum']:.8g} kg/m²/s. Retained in source means, excluded from wet corrosion scenario." for param,item in data['negativeWetSamples'].items()))
        section('Conversion formulas', 'For each sea-salt flux: dry-mass deposition D (mg/m²/day) = mean(flux in kg/m²/s) × 10⁶ × 86400 / 4.3. Sum the three aerosol size bins for each process.\n10⁶ converts kg to mg; 86400 converts seconds to days; 4.3 removes the CAMS RH80% mass convention.\nWet deposition = large-scale rain removal + convective rain removal.\nTotal = dry deposition + gravitational settling + wet deposition.\nChloride dry proxy = 0.55 × (dry deposition + gravitational settling).\nChloride total proxy = 0.55 × total. The 55% fraction assumes fresh sea salt; this is not a measured chloride deposition value.')
        section('Meteorology & SO₂ formulas', 'At each sample: T (°C) = temperature (K) − 273.15; Td is dewpoint (°C).\ne(Td) = 610.94 × exp(17.625 Td / (Td + 243.04)) Pa.\nRH (%) = 100 × e(Td) / e(T), using the same saturation formula at T.\nAir density ρ (kg/m³) = [p − 0.378 e(Td)] / [287.05 × temperature(K)], with surface pressure p in Pa.\nSO₂ (µg/m³) = mixing ratio (kg/kg) × 10⁹ × ρ.\nPd (mg/m²/day) = 0.8 × annual mean SO₂ (µg/m³), the ISO 9223 deposition equivalent.\nConversions are performed per sample before averaging. Surface density applied to near-surface model SO₂ is an approximation.')
        units = {'dry':'mg/m²/day','sedimentation':'mg/m²/day','wetLargeScale':'mg/m²/day','wetConvective':'mg/m²/day','wet':'mg/m²/day','total':'mg/m²/day','chlorideDryProxy':'mg Cl⁻/m²/day','chlorideTotalProxy':'mg Cl⁻/m²/day','temperature':'°C','humidity':'%','so2Volume':'µg/m³','so2DepositionProxy':'mg/m²/day'}
        section('annual values used', '\n'.join(f'{name}: {number(means.get(name))} {unit}' for name,unit in units.items()))
        link('CAMS forecast dataset / API download', deposition.DOCS)
        link('ECMWF IFS atmospheric composition — mass convention', deposition.MASS_DOCS)
        link('Fresh sea-salt chloride composition assumption', deposition.CHLORIDE_DOCS)
        link('ISO 9223:2012 — classification and estimation', corrosion.DOCS)
        if key.startswith('corrosion.') or key == 'environment.suggestedCorrosivity':
            estimate = site.get('corrosionAssessment', {})
            if estimate.get('methodVersion')!=corrosion.VERSION:estimate={'status':'unavailable','reason':'A complete verified calendar year is required.'}
            section('Scope & verification', estimate.get('assumptions', corrosion.ASSUMPTIONS))
            section('Standard & equation', 'Implemented reference: ISO 9223:2012, Equation 1 (carbon steel), Table 2 (categories) and Table 3 (calibration ranges).\nr = 1.77 Pd^0.52 × exp(0.020 RH + fT) + 0.102 Sd^0.62 × exp(0.033 RH + 0.040 T)\nfT = 0.150(T − 10) when T ≤ 10 °C; otherwise fT = −0.054(T − 10).\nr is an estimated first-year loss in µm/year using full-calendar-year inputs, not a certified classification; exp(x) means e raised to x.\nT = annual mean CAMS temperature (°C); RH = annual mean CAMS relative humidity (%).\nPd = 0.8 × CAMS annual mean SO₂ (µg/m³), in mg/m²/day.\nSd = CAMS dry + settling chloride proxy, in mg Cl⁻/m²/day. This substitutes ground flux for the standard chloride input; it is not a validated equivalence.\nThe EAC4 air-quality values and the 30-year climate extrema are not used in this equation.')
            inputs = estimate.get('inputs', {})
            if estimate.get('status') == 'ready' and all(k in inputs for k in corrosion.LIMITS):
                t,rh,pd,sd = (inputs[k] for k in corrosion.LIMITS)
                ft = .150*(t-10) if t <= 10 else -.054*(t-10)
                first = 1.77*pd**.52*math.exp(.020*rh+ft)
                second = .102*sd**.62*math.exp(.033*rh+.040*t)
                section('Calculation for this destination', f'T = {number(t)} °C; RH = {number(rh)} %\nPd = {number(pd)} mg/m²/day; Sd = {number(sd)} mg Cl⁻/m²/day\nfT = {number(ft)}\nSO₂ term = 1.77 × {number(pd)}^0.52 × exp(0.020 × {number(rh)} + ({number(ft)})) = {number(first)} µm/year\nSalt term = 0.102 × {number(sd)}^0.62 × exp(0.033 × {number(rh)} + 0.040 × {number(t)}) = {number(second)} µm/year\nTotal r = {number(first)} + {number(second)} = {number(estimate.get("rate"))} µm/year\nStored category: {estimate.get("category") or "Above CX range"}. Display values are rounded; calculations use full precision.')
                section('Calibration check', '\n'.join(f'{k}: {number(inputs[k])}; calibration range {lo} to {hi} — {"OUTSIDE / EXTRAPOLATED" if not lo <= inputs[k] <= hi else "within range"}' for k,(lo,hi) in corrosion.LIMITS.items()))
                if estimate.get('wetScenarioRate') is not None:
                    section('Sensitivity scenario', f'Using total chloride including wet deposition instead gives {number(estimate.get("wetScenarioRate"))} µm/year, category {estimate.get("wetScenarioCategory") or "above CX range"}. This is a separate annual sensitivity scenario, not a confidence interval.')
                else:section('Sensitivity scenario', estimate.get('wetScenarioReason','Wet scenario unavailable.'))
            else:
                section('Calculation status', estimate.get('reason') or 'Waiting for complete annual data. No numerical corrosion result is available.')
            section('Category thresholds — first-year carbon steel loss', 'C1: r ≤ 1.3 µm/year\nC2: 1.3 < r ≤ 25\nC3: 25 < r ≤ 50\nC4: 50 < r ≤ 80\nC5: 80 < r ≤ 200\nCX: 200 < r ≤ 700\nAbove 700: no category assigned by this implementation.\nA corrosivity category does not specify paint layers or thickness. The final exterior category and coating system require verification.')
    elif key in ('environment.siteAltitudeM', 'transport.maxAltitudeM'):
        section('Method', 'Copernicus DEM GLO-90 (2021): nearest raster sample at WGS84 coordinates, nominal 90 m surface model, EGM2008 vertical datum. Surface height can include vegetation and buildings.\nFor a route, the app takes the maximum of up to 512 samples at approximately 500 m spacing where the budget allows. Peaks between samples may be missed. Without route geometry it displays destination elevation, not a route maximum.')
    elif key in ('seismic.ag','seismic.tc','snow.sk','wind.qb'):
        section('Map lookup & standard', 'The destination point is tested against the selected regional zoning polygons. The returned map value is read from the matching zone; the application does not calculate a structural design action from weather data.\nStandard: ' + str(site.get(key.split('.')[0], {}).get('standard') or field.get('standard') or 'No applicable standard recorded') + '\nCoverage is regional. Boundary candidates, altitude restrictions and applicability flags in the source record must be checked. A regional map is never silently reused worldwide.')
    elif key == 'coast':
        section('Method', 'Minimum spherical distance from the destination to Natural Earth 1:50m coastline segments, Earth radius R = 6,371,000 m. For a projection inside a segment, distance = R × |asin(sin(δ) × sin(θ))|, where δ is angular distance from the segment start and θ is the difference in initial bearings. Otherwise the nearest endpoint distance is used.\nThe minimum is converted to km and rounded to 0.001 km. This rounding does not imply metre-level map accuracy. Coastal distance does not measure chloride or assign an ISO category.')
    elif key == 'country':
        section('Method', 'Point-in-polygon lookup in Natural Earth 1:10m country boundaries. Generalized borders do not establish legal jurisdiction; small islands, disputed territories and boundary proximity require review.')
    elif key == 'region':
        section('Method', 'Point-in-polygon lookup in geoBoundaries gbOpen ADM1 (first-level administrative boundaries). The country selects the regional dataset; a unique polygon containing the destination supplies its name. Simplified boundaries and administrative levels vary by country.')
        section('Boundary dataset', '\n'.join(f'{k}: {data[k]}' for k in ('country','year','originalSource','license') if data.get(k)))

    # Retain provider-specific detail, including unavailable reasons and zoning candidates.
    if key.startswith('corrosion.') or key == 'environment.suggestedCorrosivity':
        section('Source record & limitations', data.get('detail') or data.get('message') or 'Complete annual CAMS data required.')
    else:
        section('Source record & limitations', row['detail'])
    audit = [(k,data[k]) for k in ('dataset','model','method','methodId','methodVersion','retrievedAt','readyAt','rawSha256','verticalDatum') if data.get(k)]
    section('Retrieval & audit trail', '\n'.join(f'{k}: {v}' for k,v in audit))
    for part in data.get('monthly', []) + data.get('tiles', []):
        if isinstance(part,dict):
            section('Source file record', '\n'.join(f'{k}: {part[k]}' for k in ('month','sampleCount','retrievedAt','rawSha256','sha256') if part.get(k) is not None))
            link('Source raster tile', part.get('url',''))
    link('Provider documentation', data.get('sourceUrl',''))
    for url in re.findall(r'https?://[^\s<>]+', row['detail']): link('Reference', url.rstrip('.,;'))
    return doc


def plain_text(doc):
    return doc['title'] + '\n' + doc['value'] + '\n\n' + '\n\n'.join(title+'\n'+body for title,body in doc['sections']) + '\n\nSources & links\n' + '\n'.join(label+'\n'+url for label,url in doc['links'])
