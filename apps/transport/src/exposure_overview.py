"""Compact, exportable provenance rows for deposition and corrosion screening."""
import deposition
import annual_deposition as annual
import annual_corrosion as corrosion
import deposition_progress

def append_rows(site,add,section):
    dep=site.get('deposition',{}) if site.get('corrosivityEnabled',False) else {}
    if dep.get('methodVersion')!=annual.VERSION:dep={}
    ready=dep.get('status')=='ready';means=dep.get('means',{}) if ready else {}
    start,end=annual.period()
    reference=f"Destination · {dep.get('periodStart',str(start))} – {dep.get('periodEnd',str(end))}"
    scope='Sea-salt deposition values are dry mass (CAMS RH80% mass / 4.3). Chloride values assume 55% chloride in fresh sea salt.\n'
    scope+=f"Delivery destination: {site.get('destinationAddress','')}\nCoordinates (WGS84): {site.get('destinationCoordinates','')}\n"
    if ready:
        scope+=f"CAMS grid: {dep.get('gridLatitude')}, {dep.get('gridLongitude')} · offset {dep.get('gridDistanceKm','—')} km.\n"
        scope+=f"Period: {dep['periodStart']} to {dep['periodEnd']}; {dep['sampleCount']} samples per input.\n{dep.get('sampling','')}\n{dep.get('detail','')}\n"
    else:
        scope+=dep.get('message','Annual deposition retrieval starts only when enabled in Settings.')+'\n'
        if dep.get('jobs'):scope+=deposition_progress.detail(dep)+'\n'
    scope+='Source: '+deposition.SOURCE+'\n'+deposition.DOCS+'\nDry-mass convention: '+deposition.MASS_DOCS+'\nChloride composition assumption: '+deposition.CHLORIDE_DOCS
    waiting=deposition_progress.value_label(dep)
    def field(key,label,unit,source=deposition.SOURCE):
        value=f'{means[key]:.4g} {unit}' if key in means else waiting
        if key in ('wet','total','chlorideTotalProxy') and dep.get('qualityFlags'):value+=' · source flagged'
        add('deposition.'+key,label,value,source,reference,scope,deposition.DOCS)
    section('deposition','06  DESTINATION DEPOSITION · FULL CALENDAR YEAR')
    field('dry','Sea salt · dry deposition','mg/m²/day')
    field('sedimentation','Sea salt · gravitational settling','mg/m²/day')
    field('wet','Sea salt · wet deposition','mg/m²/day')
    field('total','Sea salt · total deposition','mg/m²/day')
    field('chlorideDryProxy','Chloride · dry + settling estimate','mg Cl⁻/m²/day','CAMS + fresh sea-salt assumption')
    field('chlorideTotalProxy','Chloride · total deposition estimate','mg Cl⁻/m²/day','CAMS + fresh sea-salt assumption')
    section('corrosion','07  EXTERIOR CORROSIVITY · ANNUAL ESTIMATE')
    estimate=site.get('corrosionAssessment',{}) if site.get('corrosivityEnabled',False) else {}
    if estimate.get('methodVersion')!=corrosion.VERSION:estimate={}
    field('temperature','Annual temperature · corrosion input','°C')
    field('humidity','Annual RH · corrosion input','%')
    field('so2Volume','Annual SO₂ · near-surface estimate','µg/m³')
    field('so2DepositionProxy','SO₂ · ISO deposition equivalent','mg/m²/day','CAMS + ISO 9223:2012')
    detail=corrosion.ASSUMPTIONS+'\n'
    if estimate.get('outsideCalibration'):detail+='EXTRAPOLATED: inputs outside the formula calibration ranges.\n'
    detail+=scope+'\n'+estimate.get('assumptions',corrosion.ASSUMPTIONS)+'\n'+estimate.get('reason','Waiting for complete annual inputs.')
    if estimate.get('status')=='ready':
        detail+='\n'+estimate['formula']+'\nInputs: '+str(estimate['inputs'])
        if estimate.get('outsideCalibration'):detail+='\nEXTRAPOLATION: outside ISO formula calibration ranges: '+', '.join(estimate['outsideCalibration'])+'.'
        if estimate.get('wetScenarioRate') is not None:
            detail+=f"\nSensitivity scenario using dry + wet chloride: {estimate['wetScenarioRate']:.4g} µm/year, {estimate.get('wetScenarioCategory') or 'above CX range'}. This is an annual sensitivity scenario, not a confidence interval or an ISO wet-candle equivalent."
        else:detail+='\n'+estimate.get('wetScenarioReason','Wet scenario unavailable.')
    detail+='\nCarbon-steel first-year limits (µm/year): C1 ≤1.3; C2 >1.3–25; C3 >25–50; C4 >50–80; C5 >80–200; CX >200–700.\n'+corrosion.DOCS
    rate=f"{estimate['rate']:.4g} µm/year" if estimate.get('status')=='ready' else 'Waiting for annual data' if dep.get('status') in ('loading','queued','running') else 'Not available'
    add('corrosion.rate','Steel · estimated first-year loss',rate,corrosion.SOURCE,reference,detail,corrosion.DOCS)
    suggested=site['environment']['suggestedCorrosivity']
    if suggested.get('manualOverride'):
        text=str(suggested.get('value') or 'Not available')+' · manual';source='Manual entry'
        if suggested.get('reviewRequired'):text+=' · review required'
    else:
        text=(estimate['category']+' · annual estimate'+(' · extrapolated' if estimate.get('extrapolated') else ' · preliminary')) if estimate.get('category') else estimate.get('reason','Waiting for annual data')
        if len(text)>65:text='Not available · see details'
        source=corrosion.SOURCE
    add('environment.suggestedCorrosivity','Indicative exterior category',text,source,'Carbon steel · verify',detail,corrosion.DOCS)
    add('corrosion.basis','Assessment basis','Full calendar year · verify',corrosion.SOURCE,'Exterior only',detail,corrosion.DOCS)
