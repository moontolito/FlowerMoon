"""Separate global hazard context from national structural design parameters."""
GEM_URL='https://zenodo.org/records/8409647'
NATIONAL_GROUP='seismic.national'

def rows(site):
    geo=site.get('locationContext',{}).get('geography',{})
    country=geo.get('name') or 'Unknown country';code=geo.get('code')
    result=[]
    def add(key,label,value,source,meaning,status='Not available',url=GEM_URL,**extra):
        result.append(dict(key=key,label=label,value=value,source=source,status=status,reference='Destination',
            meaning=meaning,detail=meaning,url=url,section=False,**extra))
    import gem_hazard
    hazard=gem_hazard.current(site)
    ready=hazard.get('status')=='ready' and hazard.get('value') is not None
    add('seismic.pga','PGA',gem_hazard.format_pga(hazard['value'])+' g' if ready else 'Not available','GEM · Hazard Map 2023.1',
        gem_hazard.PGA_MEANING,
        status='Model · verify' if ready else 'Not available')
    result[-1].update(detail=gem_hazard.details(hazard),reference='Destination · 475 years · rock')
    level=gem_hazard.pga_level(hazard.get('value')) if ready else None
    add('seismic.interpretation','PGA level',level or 'Not available','Application display bands',
        'Plain-language label for the destination PGA band. Describes relative acceleration, not earthquake magnitude, building damage or safety.',
        status='Display label' if level else 'Not available',url='')
    result[-1]['detail']=gem_hazard.level_details(hazard.get('value') if ready else None)
    standard=site.get('seismic',{}).get('standard')
    add('seismic.designCode','Seismic design code',standard if code=='RO' and standard else 'Not available',
        'UTCB / CCERS via Encipedia' if code=='RO' and standard else 'National source not integrated',
        'Code edition associated with the integrated national map. Confirm the edition applicable to the project; GEM hazard does not determine the legally applicable design code.',
        status='Verify' if code=='RO' and standard else 'Not available',url='https://www.encipedia.org/articole/proiectare/resurse-utile/harti-de-zonare/harta-de-zonare-seismica-din-p100-1-2013.html' if code=='RO' else '')
    add(NATIONAL_GROUP,'National Design Parameters — '+country,'','National code',
        'Expand for parameters from the destination country. ag and Tc come from the integrated Romanian zoning maps; the other parameters are not derived from PGA.',status='',url='',expandable=True)
    if code=='RO':
        for name,unit,meaning in [('tb','s','Lower characteristic period of the design spectrum.'),('td','s','Upper characteristic period of the design spectrum.'),('s','','Soil/spectral amplification parameter, where defined by the applicable code.')]:
            add('seismic.'+name,name.upper(),'Not available','Not provided by integrated maps',
                meaning+' The existing Encipedia maps supply ag and Tc only; no formula or default is substituted.',url='',unit=unit)
    else:
        add('seismic.nationalUnavailable','National parameters','Not available','National adapter not integrated',
            'No national design-parameter adapter is integrated for '+country+'. Romanian values are not applied to this destination.',url='')
    return result
