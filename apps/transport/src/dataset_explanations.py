"""Concise purpose and usage alongside the data, reused in details/exports."""
MEANINGS={
 'section_location':'Map and routing data identify the trip and destination; they do not approve transport permits.',
 'section_climate':'Historical weather describes thermal and moisture exposure; climate extremes are not corrosion equation inputs.',
 'section_structural':'Global hazard context and separate country-specific seismic design parameters.',
 'section_loads':'Destination ground snow load and reference wind pressure support structural design checks.',
 'section_corrosion':'Optional annual carbon-steel estimate. Enable in Settings to retrieve a complete year.',
 'departure':'Starting address used for the transport route.',
 'departure.coordinates':'WGS84 route start, selected or geocoded on the map.',
 'destination':'Delivery address identifies the site for environmental lookups.',
 'coordinates':'WGS84 delivery point used to select grids and zoning polygons.',
 'country':'Generalized country polygon selects the national data adapter.',
 'region':'Administrative region containing the delivery point; used for location context.',
 'environment.siteAltitudeM':'Terrain/surface elevation at destination; used for site context and zoning applicability checks.',
 'transport.distanceKm':'Total selected truck-route distance, including detected ferry crossings; used in per-km costing. Crossing fares must be added separately. Long routes may use automatic intermediate points; see details.',
 'transport.maxAltitudeM':'Highest sampled route elevation; used for route context, not destination weather.',
 'transport.maritimeTransport':'Ferry/maritime route context for checking transit protection needs.',
 'transport.suggestedProtection':'Transport protection is a separate specification, not the site corrosion category.',
 'design':'Historical maximum/minimum air temperatures for equipment exposure checks; not project design limits.',
 'daily':'Highest/lowest daily mean temperatures for sustained thermal exposure checks.',
 'humidity.summary':'Hourly maximum, arithmetic mean and minimum RH describe destination moisture exposure.',
 'seismic.ag':'National design/reference ground acceleration from the Romanian zoning polygon; used in seismic design.',
 'seismic.tc':'Characteristic spectrum control period from the Romanian zoning polygon.',
 'snow.sk':'Characteristic ground snow load. Roof snow loads require further code coefficients.',
 'wind.qb':'Reference wind pressure. Building pressures require exposure, height and shape coefficients.',
 'environment.suggestedCorrosivity':'Indicative C1–CX category from annual model inputs; supports coating review, not a final coating specification.',
 'deposition.temperature':'Annual mean temperature T used in the ISO 9223 carbon-steel equation.',
 'deposition.humidity':'Annual mean relative humidity RH used in the corrosion equation.',
 'deposition.so2Volume':'Annual near-surface SO₂ concentration estimated from mixing ratio and air density.',
 'deposition.so2DepositionProxy':'Pd = 0.8 × annual SO₂ concentration; pollution input to the corrosion equation.',
 'deposition.dry':'Sea-salt dry deposition; combined with settling to estimate chloride exposure.',
 'deposition.sedimentation':'Sea-salt gravitational settling; added to dry deposition for the chloride proxy.',
 'deposition.chlorideDryProxy':'Sd proxy = 55% of dry + settling sea-salt mass; main salinity input, not a wet-candle measurement.',
 'corrosion.rate':'Estimated first-year carbon-steel loss; compared with the ISO category thresholds.',
 'coast':'Distance to generalized shoreline; exposure context only, not a corrosion-equation input.',
 'environment.marineEnvironment':'Marine exposure context for review; does not automatically assign C5.',
 'airQuality.so2':'EAC4 annual SO₂ mixing ratio: supporting context, not the equation’s near-surface SO₂ input.',
 'airQuality.seaSalt':'EAC4 annual sea-salt mixing ratio at RH80%; contextual aerosol abundance, not deposition.',
 'airQuality.seaSaltDry':'EAC4 dry-equivalent mixing ratio (RH80% / 4.3); supporting context only.',
 'deposition.wet':'Rain-related sea-salt deposition; only supports the separate sensitivity scenario when unflagged.',
 'deposition.total':'Dry + settling + wet sea salt; supplementary annual exposure, not the main category input.',
 'deposition.chlorideTotalProxy':'Total-deposition chloride proxy; sensitivity scenario only, excluded when source flagged.',
 'environment.exteriorCorrosivity':'Previously recorded exterior category; verify its origin and project applicability.',
 'environment.interiorCorrosivity':'Previously recorded interior category; the outdoor equation does not determine it.',
}
BRIEF={
 'section_location':'Locate the site and plan the transport.',
 'section_climate':'Check temperature and moisture exposure.',
 'section_structural':'Separate hazard from national design.',
 'section_loads':'Inputs for structural load checks.',
 'section_corrosion':'Optional full-year coating review input.',
 'departure':'Starting address for route planning.',
 'departure.coordinates':'Coordinates of the route start.',
 'destination':'Site address for environmental lookups.',
 'coordinates':'Delivery point for all site lookups.',
 'country':'Select the national data adapter.',
 'region':'Identify the delivery region.',
 'environment.siteAltitudeM':'Destination elevation and zoning checks.',
 'transport.distanceKm':'Route distance for transport costing.',
 'transport.maxAltitudeM':'Highest sampled point on the route.',
 'design':'Check extreme thermal exposure.',
 'daily':'Check sustained thermal exposure.',
 'humidity.summary':'Check destination moisture exposure.',
 'seismic.pga':'Higher PGA means stronger expected shaking.',
 'seismic.interpretation':'Relative PGA level; application label.',
 'seismic.designCode':'Check the applicable code edition.',
 'seismic.national':'Expand country-specific design inputs.',
 'seismic.ag':'National seismic acceleration input.',
 'seismic.tc':'National spectrum control period.',
 'seismic.tb':'Lower characteristic spectrum period.',
 'seismic.td':'Upper characteristic spectrum period.',
 'seismic.s':'Soil/spectral amplification, if applicable.',
 'seismic.nationalUnavailable':'No adapter for this destination country.',
 'snow.sk':'Ground load input for roof snow checks.',
 'wind.qb':'Reference pressure for wind load checks.',
 'environment.suggestedCorrosivity':'Indicative category for coating review.',
 'deposition.temperature':'Annual temperature in corrosion equation.',
 'deposition.humidity':'Annual RH in corrosion equation.',
 'deposition.so2Volume':'Annual near-surface SO₂ estimate.',
 'deposition.so2DepositionProxy':'SO₂ input Pd for corrosion equation.',
 'deposition.dry':'Dry sea salt for the chloride proxy.',
 'deposition.sedimentation':'Settling sea salt for the chloride proxy.',
 'deposition.chlorideDryProxy':'Salinity input Sd; model proxy only.',
 'corrosion.rate':'Map estimated steel loss to C1–CX.',
 'coast':'Coastal context; not a formula input.',
 'airQuality.so2':'Context only; not the equation input.',
 'airQuality.seaSalt':'Aerosol context; not deposition.',
 'airQuality.seaSaltDry':'Dry aerosol context; not deposition.',
 'deposition.wet':'Supplementary sensitivity scenario.',
 'deposition.total':'Total sea-salt exposure context.',
 'deposition.chlorideTotalProxy':'Sensitivity scenario; not main category.',
}

def annotate(row):
    row=dict(row)
    meaning=row.get('meaning') or MEANINGS.get(row['key']) or ('Related supporting data; open details for source and method.' if not row['section'] else '')
    row['meaning']=meaning
    row['brief']=BRIEF.get(row['key'],meaning)
    if meaning and not row.get('detail','').startswith('Meaning / use:'):
        row['detail']='Meaning / use: '+meaning+'\n\n'+row.get('detail','')
    if row['section']:row['status']='';return row
    if row.get('expandable') and not row.get('value'):row['status']='';return row
    if row.get('status')==row.get('source') or not row.get('status'):
        value=row.get('value','')
        row['status']='Disabled' if value.startswith('Disabled') else 'Not available' if value in ('','Not available','—') or value.startswith('Not available') else 'Pending' if any(s in value for s in ('ADS ','Loading','Waiting','Checking')) else 'Verify'
    row.setdefault('unit','')
    return row

def table_value(row):
    value=row['value'];unit=row.get('unit','')
    for suffix in ('mg Cl⁻/m²/day','mg/m²/day','µm/year','µg/m³','µg/kg','kN/m²','kPa','°C','km','m','%','g','s'):
        if value.endswith(' '+suffix):return value[:-len(suffix)-1],suffix
    return value,unit
