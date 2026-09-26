"""Dispatch structural data only to providers eligible for the location."""
from .geography import country
from .registry import select
from importlib import import_module

VARIABLES={'seismic.ag':'g','seismic.tc':'s','snow.sk':'kN/m²','wind.qb':'kPa'}

def lookup(destination,altitude=None):
    geo=country(destination)
    providers=[p for p in select('structural',geo['code']) if p.adapter]
    if providers:
        provider=providers[0]
        module,function=provider.adapter.split(':')
        result=getattr(import_module(module),function)(destination,altitude)
        for key,item in result.items():
            item.update(jurisdiction=geo['code'],provider=provider.id,methodStatus=provider.method_status,coverage=provider.coverage,availability='available' if item['value'] is not None else 'unavailable')
            if geo['nearBoundary']:
                item['status']='VERIFY';item['applicability']='jurisdiction_to_verify'
                item['detail']=item.get('detail','')+' De verificat: aproape de frontiera generalizată; confirmați jurisdicția și încadrarea.'
        return result
    detail='Nu există adaptor normativ pentru '+(geo['name'] or 'jurisdicția necunoscută')+'. Nicio valoare din România nu este reutilizată.'
    if geo['nearBoundary']:detail='Aproape de limita poligonului geografic generalizat; jurisdicția trebuie verificată înainte de aplicarea unei hărți normative.'
    return {key:dict(value=None,source='Regional standards registry',status='VERIFY',unit=unit,operator='=',detail=detail,candidates=[],
                     jurisdiction=geo['code'],standard=None,provider=None,methodStatus='not_applicable',coverage='regional',availability='outside_coverage') for key,unit in VARIABLES.items()}
