"""Destination-centred overview with actual providers and explicit spatial scope."""
from site_conditions import get

ZONING_URLS={
 'seismic.ag':'harta-de-zonare-seismica-din-p100-1-2013',
 'seismic.tc':'harta-de-zonare-seismica-tc-din-p100-2013',
 'snow.sk':'harta-de-zonare-a-incarcarii-din-zapada-pe-sol-conform-cr-1-1-3-2012',
 'wind.qb':'harta-de-zonare-a-presiunii-dinamice-a-vantului-conform-cr-1-1-4-2012'}

def provenance(site,key):
    f=get(site,key)
    if f.get('manualOverride'):return 'Manual entry','', 'Entered by the user for this destination.'+(' Destination changed; confirm this retained value.' if f.get('reviewRequired') else '')
    raw=f.get('source','');url='';extra=f.get('detail','')
    if 'Open-Meteo' in raw:
        source='Open-Meteo Historical / ERA5';url='https://open-meteo.com/en/docs/historical-weather-api'
        data=site.get('humidityAnalysis' if key.startswith('humidity.') else 'climate',{})
        extra+='\nPeriod: '+str(data.get('periodStart',f.get('periodStart','—')))+' to '+str(data.get('periodEnd',f.get('periodEnd','—')))+' (UTC).'
        if data.get('gridLatitude') is not None:extra+=f"\nReturned grid point: {data['gridLatitude']}, {data.get('gridLongitude')} · grid elevation {data.get('gridElevationM','—')} m."
        extra+='\nAir temperature / relative humidity at 2 m above ground. Reanalysis for the grid associated with the destination, not an on-site sensor.'
    elif 'ISO 9223' in raw:
        source=raw;url='https://www.iso.org/standard/53499.html'
    elif 'Copernicus' in raw:
        source='Copernicus DEM GLO-90 (2021)';url='https://registry.opendata.aws/copernicus-dem/'
        extra+='\nNominal 90 m surface model; EGM2008 elevation datum.'
        if key=='transport.maxAltitudeM':extra+='\n'+raw
    elif key in ZONING_URLS and 'UTCB' in raw:
        source='UTCB / CCERS via Encipedia';url='https://www.encipedia.org/articole/proiectare/resurse-utile/harti-de-zonare/'+ZONING_URLS[key]+'.html'
        extra+='\n'+raw+'\nMap polygon selected using the delivery destination coordinates.'
    elif 'Valhalla' in raw:source='Valhalla / OpenStreetMap';url='https://valhalla.github.io/valhalla/';extra+='\n'+raw
    elif raw=='Project default':source='Project settings'
    elif f.get('value') in (None,'Unknown','Manual / Unknown'):source='Not available'
    else:source=raw or 'Not available'
    if f.get('availability')=='outside_coverage':source='No source for this region'
    if f.get('candidateValues'):extra+='\nMap candidates: '+', '.join(str(v.get('operator','='))+' '+str(v['value']) for v in f['candidateValues'])
    return source,url,('Source: '+source+'\n'+(url+'\n' if url else '')+extra).strip()

def raw_rows(site):
    result=[];point=site.get('destinationCoordinates') or 'Not selected'
    def add(key,label,value='',source='',reference='',detail='',url='',section=False):
        result.append(dict(key=key,label=label,value=value,source=source,status=source,reference=reference,detail=detail,url=url,section=section))
    def section(key,title):add('section_'+key,title,section=True)
    def field(key,label,reference='Destination'):
        f=get(site,key);value=f['value']
        if f.get('manualOverride'):reference='Destination · manual entry'
        if f.get('reviewRequired'):reference='Previous destination · manual value'
        if value is None and not f.get('manualOverride'):value=f.get('candidateValue')
        if value is None and f.get('candidateValues') and not f.get('manualOverride'):
            text=' / '.join((c.get('operator','')+' ' if c.get('operator') not in (None,'=') else '')+f"{c['value']:g}" for c in f['candidateValues'])+' '+f.get('unit','')
        elif isinstance(value,(int,float)):
            text=f'{value:.2f}'.rstrip('0').rstrip('.')+' '+f.get('unit','')
            if f.get('operator') not in (None,'='):text=f['operator']+' '+text
        else:text=str(value) if value is not None else 'Not available'
        source,url,detail=provenance(site,key)
        add(key,label,text.strip(),source,reference,f'{reference}\nDelivery destination: {site.get("destinationAddress","")}\nCoordinates: {point}\n'+detail,url)
    def pair(key,label,keys):
        fields=[get(site,k) for k in keys];values=[f['value'] for f in fields]
        text=' / '.join('—' if v is None else f'{v:+g}' for v in values)+' °C'
        if all(v is None for v in values):text='Not available'
        providers=[provenance(site,k) for k in keys]
        source=' / '.join(dict.fromkeys(p[0] for p in providers));url=next((p[1] for p in providers if p[1]),'')
        detail=f'Delivery destination: {site.get("destinationAddress","")}\nCoordinates: {point}\n'+'\n'.join(dict.fromkeys(p[2] for p in providers))
        reference='Destination · manual entry' if all(f.get('manualOverride') for f in fields) else 'Destination · manual / weather grid' if any(f.get('manualOverride') for f in fields) else 'Destination · weather grid'
        if any(f.get('reviewRequired') for f in fields):reference='Previous destination · manual value'
        add(key,label,text,source,reference,detail,url)

    section('location','01  DELIVERY LOCATION')
    address=site.get('destinationAddressLookup',{})
    add('destination','Delivery address',site.get('destinationAddress') or 'Choose a destination',address.get('source','Selected delivery point'),'Destination',address.get('detail',point),address.get('sourceUrl',''))
    add('coordinates','Delivery coordinates',point,'Selected delivery point','WGS84 · latitude, longitude')
    geo=site.get('locationContext',{}).get('geography',{})
    add('country','Country / territory',geo.get('name') or 'Not available','Natural Earth 1:10m','Destination',geo.get('detail',''),'https://www.naturalearthdata.com/')
    region=site.get('administrativeRegion',{})
    add('region','Delivery region / county / state',region.get('name') or 'Not available',region.get('source','Not available'),'Destination · ADM1',region.get('detail',''),region.get('sourceUrl',''))
    field('environment.siteAltitudeM','Destination elevation')
    section('climate','02  DESTINATION CLIMATE & HUMIDITY')
    pair('design','Historical temperature · max / min',('temperature.maxDesign','temperature.minDesign'))
    pair('daily','Daily mean temperature · max / min',('temperature.maxDailyAverage','temperature.minDailyAverage'))
    for key,label in [('maximum','Maximum hourly relative humidity'),('mean','Mean relative humidity'),('minimum','Minimum hourly relative humidity')]:field('humidity.'+key,label,'Destination · weather grid')
    humidity_rows=result[-3:]
    humidity_fields=[get(site,'humidity.'+k) for k in ('maximum','mean','minimum')]
    humidity_text=' / '.join('—' if f['value'] is None else f"{f['value']:.2f}".rstrip('0').rstrip('.') for f in humidity_fields)+' %'
    if all(f['value'] is None for f in humidity_fields):humidity_text='Not available'
    add('humidity.summary','Humidity · Max / Mean / Min',humidity_text,
        ' / '.join(dict.fromkeys(r['source'] for r in humidity_rows)),
        'Previous destination · manual value' if any(f.get('reviewRequired') for f in humidity_fields) else 'Destination · includes manual values' if any(f.get('manualOverride') for f in humidity_fields) else 'Destination · weather grid',
        '\n\n'.join(r['label']+': '+r['value']+'\n'+r['detail'] for r in humidity_rows),next((r['url'] for r in humidity_rows if r['url']),''))
    for n in (1,2,3):
        if get(site,'humidity.value'+str(n))['value'] is not None:field('humidity.value'+str(n),'Custom humidity '+str(n))
    section('structural','03  DESTINATION SEISMIC · SNOW · WIND')
    for key,label in [('seismic.ag','Seismic acceleration ag'),('seismic.tc','Seismic control period Tc'),('snow.sk','Ground snow load sk'),('wind.qb','Wind pressure qb')]:
        standard=site[key.split('.')[0]].get('standard');field(key,label+(' · '+standard if standard else ''),'Destination · zoning polygon')
    section('exposure','04  DESTINATION EXPOSURE & CORROSIVITY')
    coast=site.get('coastalDistance',{})
    add('coast','Distance to coastline',f"{coast['value']:g} km" if coast.get('value') is not None else 'Not available','Natural Earth 1:50m' if coast.get('value') is not None else 'Not available','Destination → coastline',coast.get('detail',''),'https://www.naturalearthdata.com/')
    for key,label in [('marineEnvironment','Marine environment'),('exteriorCorrosivity','Final exterior corrosivity · ISO 12944-2'),('interiorCorrosivity','Interior corrosivity · ISO 12944-2')]:field('environment.'+key,label)
    section('air','05  DESTINATION AIR QUALITY')
    import cams
    air=site.get('airQuality',{})
    ready=air.get('status')=='ready'
    reference=f"Destination · {air.get('periodStart',str(cams.YEAR))[:4]} · ML60"
    scope=f"Delivery destination: {site.get('destinationAddress','')}\nCoordinates (WGS84): {point}\n"
    if ready:
        scope+=f"CAMS grid point: {air.get('gridLatitude')}, {air.get('gridLongitude')} · offset {air.get('gridDistanceKm','—')} km.\n"
        scope+=f"Period: {air.get('periodStart')} to {air.get('periodEnd')}.\n{air.get('statistic','')}\n{air.get('detail','')}\n"
    else:scope+=air.get('message','CAMS data loads automatically for the delivery destination.')+'\n'
    for key,label in [('so2','SO₂ · annual mean'),('seaSalt','Sea-salt aerosol · annual mean (RH80%)'),('seaSaltDry','Sea-salt aerosol · dry equivalent')]:
        item=air.get(key,{}) if ready else {}
        value=f"{item['mean']:.4g} µg/kg" if item.get('mean') is not None else 'Loading…' if air.get('status') in ('loading','queued','running') else 'Licence required' if air.get('errorCode')=='licence' else 'Not available'
        detail=scope+'Source: '+cams.SOURCE+'\n'+cams.DOCS
        if item.get('mean') is not None:
            detail+=f"\nMinimum / maximum monthly mean: {item['minimumMonthlyMean']:.4g} / {item['maximumMonthlyMean']:.4g} µg/kg."
        if key.startswith('seaSalt'):
            detail+='\nThree CAMS sea-salt radius bins: 0.03–0.5, 0.5–5 and 5–20 µm at 80% RH. Dry-equivalent mass = RH80% mass / 4.3.\n'+cams.SALT_DOCS
        add('airQuality.'+key,label,value,cams.SOURCE,reference,detail,cams.DOCS)
    import exposure_overview
    exposure_overview.append_rows(site,add,section)
    section('additional','08  ADDITIONAL DESTINATION PARAMETERS')
    for key,label in [('timeOfWetness','Time of wetness'),('corrosionIndex','Corrosion index')]:
        data=site.get('locationContext',{}).get('pendingMethods',{}).get(key,{})
        add(key,label,'Not available','Not integrated','Destination',data.get('detail','No integrated source or validated method.'))
    section('transport','09  TRANSPORT ROUTE')
    address=site.get('departureAddressLookup',{})
    add('departure','Departure address',site.get('departureAddress',''),address.get('source','Project settings'),'Departure',address.get('detail',''),address.get('sourceUrl',''))
    add('departure.coordinates','Departure coordinates',site.get('departureCoordinates') or 'Not selected','Selected departure point','WGS84 · latitude, longitude')
    field('transport.distanceKm','Total route distance','Departure → destination · includes detected crossings')
    route=site.get('routeLookup',{}).get('status')=='ready'
    field('transport.maxAltitudeM','Maximum sampled route elevation' if route else 'Destination elevation · no route','Route samples' if route else 'Destination')
    field('transport.maritimeTransport','Maritime transport','Transport route')
    field('transport.suggestedProtection','Maritime transport protection','Transport route')
    return result


CORROSIVITY_GROUP='environment.suggestedCorrosivity'
CORROSIVITY_INPUTS=(
    'deposition.temperature','deposition.humidity',
    'deposition.so2Volume','deposition.so2DepositionProxy',
    'deposition.dry','deposition.sedimentation','deposition.chlorideDryProxy',
    'corrosion.rate',
)
SUPPLEMENTARY_DEPOSITION=('deposition.wet','deposition.total','deposition.chlorideTotalProxy')


def display_rows(site):
    """Result-first hierarchy without deleting saved or archival source records."""
    by_key={row['key']:row for row in rows(site)}
    result=[]
    def add(key,parent='',**changes):
        result.append(dict(by_key[key],parent=parent,**changes))
    def heading(key,label,parent=''):
        result.append(dict(key=key,label=label,value='',source='',status='',reference='',detail='',url='',section=True,parent=parent))
    def available(key):
        f=get(site,key)
        return f.get('value') not in (None,'','Unknown','Manual / Unknown') or f.get('candidateValue') is not None or bool(f.get('candidateValues'))

    heading('section_location','01  DEPARTURE, MAP & TRANSPORT')
    for key in ('departure','departure.coordinates','destination','coordinates','country','region',
                'environment.siteAltitudeM','transport.distanceKm'):
        add(key)
    if site.get('routeLookup',{}).get('status')=='ready' or get(site,'transport.maxAltitudeM').get('manualOverride'):
        add('transport.maxAltitudeM')
    for key in ('transport.maritimeTransport','transport.suggestedProtection'):
        if available(key):add(key)

    heading('section_climate','02  DESTINATION CLIMATE & HUMIDITY')
    for key in ('design','daily','humidity.summary'):add(key)
    for n in (1,2,3):
        key='humidity.value'+str(n)
        if key in by_key:add(key)

    heading('section_structural','03  SEISMIC INFORMATION')
    for key in ('seismic.pga','seismic.interpretation','seismic.designCode'):
        add(key)
    add('seismic.national',expandable=True)
    if site.get('locationContext',{}).get('geography',{}).get('code')=='RO':
        for key in ('seismic.ag','seismic.tb','seismic.tc','seismic.td','seismic.s'):
            add(key,'seismic.national')
    else:add('seismic.nationalUnavailable','seismic.national')
    heading('section_loads','04  SNOW & WIND DESIGN INPUTS')
    for key in ('snow.sk','wind.qb'):add(key)

    heading('section_corrosion','05  DESTINATION CORROSIVITY · OPTIONAL')
    parent=dict(by_key[CORROSIVITY_GROUP],expandable=bool(site.get('corrosivityEnabled',False)))
    if not site.get('corrosivityEnabled',False):
        parent.update(value='Disabled · enable in Settings',status='Disabled')
        result.append(parent)
        from dataset_explanations import annotate
        return [annotate(row) for row in result]
    dep=site.get('deposition',{})
    if not site['environment']['suggestedCorrosivity'].get('manualOverride') and not site.get('corrosionAssessment',{}).get('category'):
        import deposition_progress
        parent['value']=deposition_progress.value_label(dep) if dep.get('status') in ('loading','queued','running') else 'Not available · see details'
    parent['reference']='Destination · full calendar year · verify'
    result.append(parent)
    heading('section_corrosion_inputs','Calculation inputs · full calendar year',CORROSIVITY_GROUP)
    for key in CORROSIVITY_INPUTS:add(key,CORROSIVITY_GROUP)
    heading('section_exposure','Coastal exposure · context',CORROSIVITY_GROUP)
    add('coast',CORROSIVITY_GROUP)
    if available('environment.marineEnvironment'):add('environment.marineEnvironment',CORROSIVITY_GROUP)
    heading('section_air','Air quality · annual context',CORROSIVITY_GROUP)
    for key in ('airQuality.so2','airQuality.seaSalt','airQuality.seaSaltDry'):add(key,CORROSIVITY_GROUP)
    label='Wet deposition & totals · verify' if dep.get('qualityFlags') else 'Totals · sensitivity scenario only'
    heading('section_corrosion_supplementary',label,CORROSIVITY_GROUP)
    for key in SUPPLEMENTARY_DEPOSITION:add(key,CORROSIVITY_GROUP)
    for key in ('environment.exteriorCorrosivity','environment.interiorCorrosivity'):
        if available(key):add(key,CORROSIVITY_GROUP)
    from dataset_explanations import annotate
    return [annotate(row) for row in result]


def rows(site):
    from seismic_information import rows as seismic_rows
    from dataset_explanations import annotate
    return [annotate(row) for row in raw_rows(site)+seismic_rows(site)]
