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
        extra+='\nReanalysis for the grid associated with the destination, not an on-site sensor.'
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

def rows(site):
    result=[];point=site.get('destinationCoordinates') or 'Not selected'
    def add(key,label,value='',source='',reference='',detail='',url='',section=False):
        result.append(dict(key=key,label=label,value=value,source=source,status=source,reference=reference,detail=detail,url=url,section=section))
    def section(key,title):add('section_'+key,title,section=True)
    def field(key,label,reference='Destination'):
        f=get(site,key);value=f['value']
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
        reference='Previous destination · manual value' if any(f.get('reviewRequired') for f in fields) else 'Destination · weather grid'
        add(key,label,text,source,reference,detail,url)

    section('location','01  DELIVERY LOCATION')
    add('destination','Delivery address',site.get('destinationAddress') or 'Choose a destination','Selected delivery point','Destination',point)
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
    for n in (1,2,3):
        if get(site,'humidity.value'+str(n))['value'] is not None:field('humidity.value'+str(n),'Custom humidity '+str(n))
    section('structural','03  DESTINATION SEISMIC · SNOW · WIND')
    for key,label in [('seismic.ag','Seismic acceleration ag'),('seismic.tc','Seismic control period Tc'),('snow.sk','Ground snow load sk'),('wind.qb','Wind pressure qb')]:
        standard=site[key.split('.')[0]].get('standard');field(key,label+(' · '+standard if standard else ''),'Destination · zoning polygon')
    section('exposure','04  DESTINATION EXPOSURE & CORROSIVITY')
    coast=site.get('coastalDistance',{})
    add('coast','Distance to coastline',f"{coast['value']:g} km" if coast.get('value') is not None else 'Not available','Natural Earth 1:50m' if coast.get('value') is not None else 'Not available','Destination → coastline',coast.get('detail',''),'https://www.naturalearthdata.com/')
    for key,label in [('marineEnvironment','Marine environment'),('exteriorCorrosivity','Exterior corrosivity · ISO 12944-2'),('interiorCorrosivity','Interior corrosivity · ISO 12944-2'),('suggestedCorrosivity','Proposed corrosion category')]:field('environment.'+key,label)
    section('additional','05  ADDITIONAL DESTINATION PARAMETERS')
    for key,label in [('timeOfWetness','Time of wetness'),('corrosionIndex','Corrosion index'),('airQuality','SO₂ / sea-salt aerosols')]:
        data=site.get('locationContext',{}).get('pendingMethods',{}).get(key,{})
        add(key,label,'Not available','Not integrated','Destination',data.get('detail','No integrated source or validated method.'))
    section('transport','06  TRANSPORT ROUTE')
    add('departure','Departure address',site.get('departureAddress',''),'Project settings','Departure')
    field('transport.deliveryType','Delivery terms','Transport')
    field('transport.distanceKm','Road distance','Departure → destination')
    route=site.get('routeLookup',{}).get('status')=='ready'
    field('transport.maxAltitudeM','Maximum sampled route elevation' if route else 'Destination elevation · no route','Route samples' if route else 'Destination')
    field('transport.maritimeTransport','Maritime transport','Transport route')
    field('transport.suggestedProtection','Maritime transport protection','Transport route')
    return result
