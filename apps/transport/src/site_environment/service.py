"""Location context is independent of route success and climate availability."""
from . import geography,standards,registry

def context(destination):
    return dict(geography=geography.country(destination),providers=registry.manifest(),pendingMethods=registry.pending_methods())

def apply_context(site,context):
    site['locationContext']=context

def apply_zoning(site,values):
    from site_conditions import automatic
    for key,item in values.items():
        automatic(site,key,**item)
    for group in ('seismic','snow','wind'):
        items=[v for k,v in values.items() if k.startswith(group+'.')]
        site[group]['standard']=next((v.get('standard') for v in items if v.get('standard')),None)
        site[group]['jurisdiction']=next((v.get('jurisdiction') for v in items if v.get('jurisdiction')),None)
