"""Ordered site summary: values and verification notes are separate columns."""
from site_conditions import get

def rows(site):
    result=[]
    def add(key,label,value='',status='',note='',detail='',section=False):
        result.append(dict(key=key,label=label,value=value,status=status,note=note,detail=detail,section=section))
    def section(key,title):add('section_'+key,title,section=True)
    def field(key,label):
        f=get(site,key);v=f['value'];candidate=False
        if v is None and not f.get('manualOverride') and f.get('candidateValue') is not None:v=f['candidateValue'];candidate=True
        unit=f.get('unit','')
        if isinstance(v,(int,float)):
            text=f'{v:.2f}'.rstrip('0').rstrip('.')+' '+unit
            if f.get('operator') not in (None,'='):text=f['operator']+' '+text
        elif v is None and f.get('candidateValues') and not f.get('manualOverride'):
            text=' / '.join((c.get('operator','')+' ' if c.get('operator') not in (None,'=') else '')+f"{c['value']:g}" for c in f['candidateValues'])+' '+unit;candidate=True
        else:text={'Unknown':'Necunoscut','Possible':'Posibil','Yes':'Da','No':'Nu','Manual / Unknown':'Nespecificat'}.get(v,v) if v is not None else 'Indisponibil'
        status={'DEFAULT':'Implicit proiect','CALCULATED':'Calculat','AUTO':'Automat','VERIFY':'Automat','MANUAL':'Manual'}.get(f['status'],f['status'])
        note='De verificat' if f['status']=='VERIFY' and v not in (None,'Unknown','Manual / Unknown') else ''
        if key.startswith('temperature.') or key.startswith('humidity.'):
            note='De verificat · date istorice pe grilă' if v is not None and not f.get('manualOverride') else note
        if key.startswith('humidity.') and f.get('validFraction',1)<1:note=f"De verificat · serie incompletă ({f['validFraction']:.1%})"
        if candidate:note='Valori din hartă · de verificat încadrarea'
        if f.get('applicability')=='unverified_at_altitude':note='De verificat · amplasament ≥1000 m'
        elif f.get('applicability')=='jurisdiction_to_verify':note='De verificat · apropiere de frontieră'
        elif f.get('nearBoundary'):note='De verificat · limita zonei'
        if f.get('availability')=='outside_coverage':status='Fără adaptor regional';note='Nu există sursă integrată pentru această zonă'
        if f.get('availability')=='method_not_validated':status='Metodă nevalidată';note='Nu există metodă validată pentru calcul'
        if f.get('reviewRequired'):status='Manual';note='De verificat · locația s-a schimbat'
        if v is None and not candidate and f['status']!='MANUAL' and not note:status='Fără date';note='Sursa nu a furnizat o valoare'
        if v in ('Unknown','Manual / Unknown') and not f.get('manualOverride'):status='Nespecificat';note='Necesită confirmare'
        detail=f.get('source','')+'\n'+f.get('detail','')
        if f.get('periodStart'):detail+='\nPerioadă: '+f['periodStart']+' – '+f['periodEnd']
        add(key,label,text.strip(),status,note,detail)
    def pair(key,label,keys):
        fields=[get(site,k) for k in keys];values=[f['value'] for f in fields]
        text=' / '.join('—' if v is None else f'{v:+g}' for v in values)+' °C'
        if all(v is None for v in values):text='Indisponibil'
        status='Manual / mixt' if any(f.get('manualOverride') for f in fields) else 'Calculat' if all(v is not None for v in values) else 'În așteptare'
        note='De verificat · locația s-a schimbat' if any(f.get('reviewRequired') for f in fields) else 'De verificat · extreme istorice din reanaliză'
        if all(v is None for v in values):note='Sursa nu a furnizat încă valori'
        add(key,label,text,status,note,'\n'.join(f.get('source','')+'\n'+f.get('detail','') for f in fields))

    section('location','01  LOCAȚIE')
    add('destination','Adresa de livrare',site['destinationAddress'] or 'Alege destinația','Din hartă')
    geo=site.get('locationContext',{}).get('geography',{})
    add('country','Țară / teritoriu',geo.get('name') or 'Neconfirmat','Estimare GIS','De verificat · granițe generalizate',geo.get('detail',''))
    field('environment.siteAltitudeM','Altitudinea amplasamentului')

    section('transport','02  TRANSPORT')
    add('departure','Adresa de plecare',site['departureAddress'],'Din proiect')
    field('transport.deliveryType','Condiție de livrare')
    field('transport.distanceKm','Distanță rutieră')
    is_destination='destination elevation' in get(site,'transport.maxAltitudeM').get('source','')
    field('transport.maxAltitudeM','Altitudine destinație (ruta indisponibilă)' if is_destination else 'Altitudine maximă eșantionată pe rută')
    field('transport.maritimeTransport','Transport maritim')
    field('transport.suggestedProtection','Protecție pentru transportul maritim')

    section('climate','03  CLIMĂ & UMIDITATE')
    pair('design','Temperatură istorică · max / min',('temperature.maxDesign','temperature.minDesign'))
    pair('daily','Medii zilnice de temperatură · max / min',('temperature.maxDailyAverage','temperature.minDailyAverage'))
    field('humidity.maximum','Umiditate · maximă orară')
    field('humidity.mean','Umiditate relativă · medie')
    field('humidity.minimum','Umiditate · minimă orară')
    for n in (1,2,3):
        key='humidity.value'+str(n)
        if get(site,key)['value'] is not None:field(key,'Umiditate personalizată · valoare istorică '+str(n))

    section('exposure','04  EXPUNERE & COROZIVITATE')
    coast=site.get('coastalDistance',{})
    add('coast','Distanță până la coastă',f"{coast['value']:g} km" if coast.get('value') is not None else 'Indisponibil','Estimare GIS','De verificat · nu indică salinitatea',coast.get('detail',''))
    field('environment.marineEnvironment','Mediu maritim la amplasament')
    field('environment.exteriorCorrosivity','Corozivitate exterior · ISO 12944-2')
    field('environment.interiorCorrosivity','Corozivitate interior · ISO 12944-2')
    field('environment.suggestedCorrosivity','Categorie propusă de corozivitate')

    section('structural','05  SEISM · ZĂPADĂ · VÂNT')
    for key,label in [('seismic.ag','Accelerație seismică ag'),('seismic.tc','Perioadă de control Tc'),('snow.sk','Încărcare din zăpadă sk'),('wind.qb','Presiunea vântului qb')]:
        standard=site[key.split('.')[0]].get('standard');field(key,label+(' · '+standard if standard else ''))

    section('additional','06  INDICATORI SUPLIMENTARI')
    for key,title in [('timeOfWetness','Time of Wetness'),('corrosionIndex','Indice de corozivitate'),('airQuality','SO₂ / aerosoli marini')]:
        item=site.get('locationContext',{}).get('pendingMethods',{}).get(key,{})
        add(key,title,'Indisponibil','Necesită integrare' if key=='airQuality' else 'Metodă nevalidată',item.get('detail','Fără date / metodă integrată'),item.get('detail',''))
    return result
