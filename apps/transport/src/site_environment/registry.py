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
    Provider('photon-osm','geocoding','global-osm',('address_suggestions','coordinates'),'place_search','OSM coverage varies. Public Photon is a rate-limited demo; configure a private endpoint for production.'),
    Provider('geoboundaries-gbopen','administrative_boundaries','global-available-countries',('administrative_region',),'ADM1 polygon','First-level administrative boundaries; years and local names vary by country. Not a legal boundary or a structural zoning map.'),
    Provider('open-meteo-era5','weather','global',('temperature','relative_humidity_hourly'),'reanalysis','Historical API / ERA5 grid, not a local weather station. Free API is non-commercial; commercial access uses the customer endpoint and a key.'),
    Provider('natural-earth','geography','global',('country','coast_distance'),'geographic_estimate','Countries 1:10m, coastline 1:50m; does not establish legal jurisdiction.'),
    Provider('valhalla','routing','server-dependent',('route','distance','travel_time'),'estimate','Coverage depends on the server and OSM. Does not plan ocean transport or authorize a route.'),
    Provider('utcb-ro','structural','regional',('seismic.ag','seismic.tc','snow.sk','wind.qb'),'informational_map','Romania only; map editions are documented and not assumed to be the current applicable codes.',countries=('RO',),adapter='zoning:lookup'),
    Provider('copernicus-glo90','elevation','global-land',('elevation',),'DSM','GLO-90 2021 public AWS mirror. Nominal 90 m DSM / EGM2008. Missing tiles are not treated as zero elevation.'),
    Provider('cams-eac4','air_quality','global',('so2','sea_salt'),'reanalysis','Adapter not installed; requires ADS access, a token and dataset licence acceptance.',False),
    Provider('cams-europe','air_quality','Europe',('so2',),'reanalysis','Adapter not installed; European coverage, not a global source.',False),
    Provider('efehr-eshm20','seismic_hazard','Euro-Mediterranean',('pga',),'hazard_model','Adapter not installed. ESHM20 PGA does not replace national ag/Tc requirements.',False),
    Provider('open-meteo-extra','weather_extra','global-model-dependent',('wind','precipitation','snowfall','snow_depth','snow_water_equivalent'),'reanalysis','Planned; variables and coverage depend on the model. Does not replace code snow load sk or wind pressure qb.',False),
)

def select(domain,country_code=None):
    return [p for p in PROVIDERS if p.installed and p.domain==domain and (not p.countries or country_code in p.countries)]

def weather_order():
    return ['open-meteo-era5']

def manifest():
    return [dict(asdict(p),configured=p.installed and (p.domain!='weather' or p.id in weather_order())) for p in PROVIDERS]

def pending_methods():
    return {
        'timeOfWetness':dict(value=None,status='method_not_validated',detail='The ISO criterion and edition require validation; the method needs synchronized hourly temperature and RH.'),
        'corrosionIndex':dict(value=None,status='method_not_validated',detail='No validated weights or thresholds; an ISO category is not derived from coastal distance.'),
        'airQuality':dict(value=None,status='provider_not_configured',detail='CAMS EAC4 requires ADS integration and configured access; SO₂ and sea-salt aerosols are not available in this version.'),
    }
