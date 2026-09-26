"""Capabilities and explicit coverage; planned providers are never selectable."""
from dataclasses import dataclass,asdict
import os

@dataclass(frozen=True)
class Provider:
    id:str
    domain:str
    coverage:str
    variables:tuple
    method_status:str
    limitations:str
    installed:bool=True
    countries:tuple=()
    adapter:str=''

PROVIDERS=(
    Provider('open-meteo-era5','weather','global',('temperature','relative_humidity_hourly'),'reanalysis','Historical API / ERA5. Grilă, nu stație locală. API gratuit necomercial; endpoint customer cu cheie pentru abonament comercial.'),
    Provider('natural-earth','geography','global',('country','coast_distance'),'geographic_estimate','Țări 1:10m, coastă 1:50m; nu stabilește jurisdicția legală.'),
    Provider('valhalla','routing','server-dependent',('route','distance','travel_time'),'estimate','Depinde de acoperirea serverului și OSM. Nu planifică transport oceanic și nu autorizează transportul.'),
    Provider('utcb-ro','structural','regional',('seismic.ag','seismic.tc','snow.sk','wind.qb'),'informational_map','Numai România; edițiile hărților sunt documentate, nu presupuse normative curente.',countries=('RO',),adapter='zoning:lookup'),
    Provider('copernicus-glo90','elevation','global-land',('elevation',),'DSM','GLO-90 2021, oglindă publică AWS. DSM nominal 90 m / EGM2008. Lipsa dalei nu este tratată ca altitudine zero.'),
    Provider('cams-eac4','air_quality','global',('so2','sea_salt'),'reanalysis','Adaptor neinstalat; necesită ADS, token și acceptarea licenței datasetului.',False),
    Provider('cams-europe','air_quality','Europe',('so2',),'reanalysis','Adaptor neinstalat; acoperire europeană, nu soluție globală.',False),
    Provider('efehr-eshm20','seismic_hazard','Euro-Mediterranean',('pga',),'hazard_model','Adaptor neinstalat. PGA ESHM20 nu înlocuiește ag/Tc din reglementări naționale.',False),
    Provider('open-meteo-extra','weather_extra','global-model-dependent',('wind','precipitation','snowfall','snow_depth','snow_water_equivalent'),'reanalysis','Planificat; variabilele și acoperirea depind de model. Nu înlocuiesc sk sau qb normativ.',False),
)

def select(domain,country_code=None):
    return [p for p in PROVIDERS if p.installed and p.domain==domain and (not p.countries or country_code in p.countries)]

def weather_order():
    return ['open-meteo-era5']

def manifest():
    return [dict(asdict(p),configured=p.installed and (p.domain!='weather' or p.id in weather_order())) for p in PROVIDERS]

def pending_methods():
    return {
        'timeOfWetness':dict(value=None,status='method_not_validated',detail='Criteriul și ediția ISO trebuie verificate înainte de implementare; calculul necesită temperatură și RH orare sincronizate.'),
        'corrosionIndex':dict(value=None,status='method_not_validated',detail='Nu există ponderi sau praguri validate; nu se calculează o categorie ISO din coastă.'),
        'airQuality':dict(value=None,status='provider_not_configured',detail='CAMS EAC4 necesită integrare ADS și acces configurat; SO₂ și aerosoli nu sunt disponibili în această versiune.'),
    }
