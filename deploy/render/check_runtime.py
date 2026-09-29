"""Exercise unchanged provider functions from the hosting container; never save app state."""
import gc
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/transport/src'))
CACHE = ROOT / '.runtime/provider-check'
CACHE.mkdir(parents=True, exist_ok=True)
report = []


def check(name, call, summarize):
    started = time.monotonic()
    try:
        value = call()
        summary = summarize(value)
        status = 'ready'
        if summary.get('providerStatus') not in (None, 'ready') or summary.get('complete') is False:
            status = 'unavailable'
        report.append(dict(check=name, status=status, seconds=round(time.monotonic()-started, 2), **summary))
        return value
    except Exception as error:
        # Do not include request URLs or environment variables in reports.
        report.append(dict(check=name, status='unavailable', seconds=round(time.monotonic()-started, 2), error=type(error).__name__))
        return None
    finally:
        print(json.dumps(report[-1]), flush=True)
        gc.collect()


import domain, routing, places, regions, climate, humidity, elevation, gem_hazard
from urllib.request import Request, urlopen

origin = dict(lat=47.7407, lon=26.6658)
destination = dict(lat=44.4268, lon=26.1025)
state = domain.State(CACHE / 'not-saved.json')
loaded = next(r['loaded'] for r in domain.recommend(state.data['product'], state.data['vehicles']) if r['fits'])
check('Address search', lambda: places.search('Bucharest Romania'), lambda v: dict(results=len(v)))
check('Administrative region', lambda: regions.lookup(destination, CACHE/'boundaries'),
      lambda v: dict(providerStatus=v.get('status'), name=v.get('name')))
def tile():
    with urlopen(Request('https://tile.openstreetmap.org/5/18/11.png', headers={'User-Agent':routing.AGENT}), timeout=30) as response:
        data = response.read(2_000_000)
    if not data.startswith(b'\x89PNG'):
        raise ValueError('Map tile not PNG')
    return len(data)
check('Map tile', tile, lambda v: dict(bytes=v))
routes = check('Truck route', lambda: routing.route(state.data['server'], domain.route_request(origin, destination, loaded)),
               lambda v: dict(routes=len(v), distanceKm=v[0]['distance_km']))
check('GEM PGA', lambda: gem_hazard.lookup(destination), lambda v: dict(providerStatus=v.get('status'), value=v.get('value'), detail=v.get('message')))
check('Copernicus elevation', lambda: elevation.samples([destination], CACHE/'elevation'),
      lambda v: dict(complete=v['complete'], values=v['values']))
check('30-year temperature', lambda: climate.lookup(destination, CACHE/'climate'),
      lambda v: dict(periodStart=v['periodStart'], periodEnd=v['periodEnd'], days=v['days']))
check('30-year hourly humidity', lambda: humidity.lookup(destination, CACHE/'humidity'),
      lambda v: dict(periodStart=v['periodStart'], periodEnd=v['periodEnd'], validFraction=v['validFraction']))
report.append(dict(check='Optional credentials', adsConfigured=bool(os.environ.get('FLOWERMOON_ADS_KEY')),
                   weatherKeyConfigured=bool(os.environ.get('FLOWERMOON_CLIMATE_API_KEY')), status='not_exercised'))
target = ROOT / '.runtime/render-providers.json'
target.write_text(json.dumps(report, indent=2), encoding='utf-8')
print('Provider report saved.', flush=True)
if any(item.get('status') == 'unavailable' for item in report):
    raise SystemExit('One or more provider checks were unavailable; inspect the report before deployment.')
