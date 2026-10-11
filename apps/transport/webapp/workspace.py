"""One browser session: the desktop Planner workflow without Tk.

The engineering, routing, source and export modules in ``src/`` are reused
unchanged. This class only replaces the Tk variables, timers and windows with
plain state guarded by a lock, so FastAPI worker threads can share it.
"""
import json
import sys
import tempfile
import threading
import uuid
from copy import deepcopy
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from domain import State, calculate, coordinates, evaluate, num, product, recommend, route_request, stamp  # noqa: E402
import climate  # noqa: E402
import gem_hazard  # noqa: E402
import humidity  # noqa: E402
import places  # noqa: E402
import regions  # noqa: E402
import routing  # noqa: E402
import site_conditions as sc  # noqa: E402
import site_sources  # noqa: E402
from site_environment import service as site_service, standards  # noqa: E402

PRESET_TITLES = {'example-0': 'Light · flatbed', 'example-1': 'Standard · semi-trailer', 'example-2': 'Oversize · low loader'}
ADJUSTABLE = ('length', 'width', 'height', 'weight', 'axle_load', 'axle_count')
MARINE_WARNING = ('Marine environment detected. Increased atmospheric corrosivity may apply. Verify salinity, '
                  'distance from shoreline and exposure conditions according to EN ISO 12944-2.')
MARITIME_WARNING = ('Maritime transport detected. Verify coating and temporary corrosion protection requirements '
                    'for marine transport and storage.')
FERRY_WARNING = ('Ferry detected on route. Confirm whether this is maritime or an inland crossing; '
                 'verify temporary transport/storage protection.')


def optional_point(text):
    return coordinates(text) if str(text or '').strip() else None


class Workspace:
    def __init__(self, path, cache, pool):
        self.lock = threading.RLock()
        self.state = State(path)
        self.cache = Path(cache)
        self.pool = pool
        self.site = self.state.data['siteConditions']
        sc.recommendation(self.site)
        self.origin_name = self.state.data['origin_name']
        self.origin_coords = self.state.data['origin_coords']
        self.dest_name = self.site['destinationAddress']
        self.dest_coords = self.site['destinationCoordinates']
        self.via = ''
        self.active = None
        self.manual = False
        self.accepted = False
        self.route_results = []
        self.route_context = None
        self.selected = None
        self.generation = 0
        self.site_token = 0
        self.site_route_key = None
        self.pending = {}
        self.sources_cache = {}
        self.status = 'Choose the destination, then calculate the route.'
        self.choose_recommended()
        if self.dest_coords:
            self.location_ready()

    # ----- vehicle -------------------------------------------------------
    def choose_recommended(self):
        matches = recommend(self.state.data['product'], self.state.data['vehicles'])
        self.active = deepcopy(next((r for r in matches if r['fits']), None))
        self.manual = False
        self.accepted = False
        self.invalidate_route()

    def set_product(self, values):
        self.state.data['product'] = product(values)
        self.state.save()
        self.choose_recommended()
        self.status = 'Product saved. A compatible vehicle was recommended.' if self.active else 'No compatible vehicle. Edit the product or choose a profile.'

    def select_preset(self, ident):
        vehicle = next((v for v in self.state.data['vehicles'] if v['id'] == ident), None)
        if vehicle is None:
            raise ValueError('Unknown vehicle profile.')
        result = evaluate(self.state.data['product'], vehicle)
        self.active = deepcopy(result) if result['fits'] else None
        self.manual = False
        self.accepted = False
        self.invalidate_route()
        self.status = ('Preset applied. Dimensions include the product.' if result['fits']
                       else 'Incompatible product: ' + '; '.join(result['reasons']))

    def adjust(self, values):
        if not self.active:
            raise ValueError('Select a compatible vehicle.')
        d = {k: num(values.get(k), k, .001, k == 'axle_count') for k in ADJUSTABLE}
        base = evaluate(self.state.data['product'], self.active['vehicle'])['loaded']
        for key in ('length', 'width', 'height', 'weight'):
            if d[key] < base[key]:
                raise ValueError(f'{key}: value cannot be below the loaded vehicle dimensions ({base[key]:g}). '
                                 'Change the product or actual vehicle specifications.')
        if d['weight'] > self.active['vehicle']['gross']:
            raise ValueError('Weight exceeds the technical vehicle capacity.')
        if d['axle_load'] > d['weight'] or d['axle_load'] * d['axle_count'] < d['weight']:
            raise ValueError('Axle load is incompatible with total weight.')
        self.active['loaded'] = d
        self.manual = True
        self.accepted = False
        self.invalidate_route()
        self.status = 'Adjustments applied. Recalculate the route.'

    def profile_summary(self):
        if not self.active:
            return 'No compatible vehicle. Edit the product or profile.'
        d = self.active['loaded']
        return (f"{d['length']:g} × {d['width']:g} × {d['height']:g} m  ·  {d['weight']:g} t\n"
                + ('Custom · ' if self.manual else '')
                + ('Example profile' if self.active['vehicle']['example'] else 'User profile'))

    # ----- locations -----------------------------------------------------
    def invalidate_route(self):
        self.site_token += 1
        self.site_route_key = None
        sc.invalidate(self.site, sc.ROUTE_KEYS)
        self.generation += 1
        self.route_results = []
        self.route_context = None
        self.selected = None

    def set_locations(self, origin_name, origin_coords, dest_name, dest_coords, via=''):
        origin_coords, dest_coords = str(origin_coords or '').strip(), str(dest_coords or '').strip()
        for text in (origin_coords, dest_coords):
            optional_point(text)
        for text in str(via or '').split(';'):
            if text.strip():
                coordinates(text)
        new = (str(origin_name or '').strip(), origin_coords, str(dest_name or '').strip(), dest_coords, str(via or '').strip())
        old = (self.origin_name, self.origin_coords, self.dest_name, self.dest_coords, self.via)
        if new == old:
            return False
        self.origin_name, self.origin_coords, self.dest_name, self.dest_coords, self.via = new
        self.invalidate_route()
        for key, name, coords in [('departureAddressLookup', self.origin_name, self.origin_coords),
                                  ('destinationAddressLookup', self.dest_name, self.dest_coords)]:
            record = self.site.get(key, {})
            if record and (record.get('coordinates') != coords or record.get('label', name) != name):
                self.site.pop(key, None)
        if old[3] != self.dest_coords:
            self.site.pop('administrativeRegion', None)
        sc.sync(self.site, self.origin_name, self.dest_name, self.origin_coords, self.dest_coords)
        self.refresh_local_hazard()
        self.site['lookupState'] = ('Updating destination data…' if self.dest_coords
                                    else 'Select an address suggestion or a delivery point on the map.')
        self.state.data.update(origin_name=self.origin_name, origin_coords=self.origin_coords)
        self.site_token += 1
        self.state.save()
        self.location_ready()
        return True

    def apply_label(self, target, record):
        """Reverse-geocoded label for a map click; never moves the selected point."""
        coords = self.origin_coords if target == 'origin' else self.dest_coords
        if record.get('coordinates') != coords:
            return False
        key = 'departureAddressLookup' if target == 'origin' else 'destinationAddressLookup'
        self.site[key] = dict(record)
        if record.get('status') == 'ready':
            label = record['label']
            if target == 'origin':
                self.origin_name = label
                self.site['departureAddress'] = label
                self.state.data['origin_name'] = label
            else:
                self.dest_name = label
                self.site['destinationAddress'] = label
            if self.route_context:
                self.route_context['origin' if target == 'origin' else 'destination']['name'] = label
            self.status = (('Departure' if target == 'origin' else 'Destination')
                           + ' address found · Photon / OpenStreetMap. Selected coordinates retained.')
        else:
            self.status = 'Address unavailable for this map point. Selected coordinates are retained; you can still calculate the route.'
        self.state.save()
        return True

    # ----- destination data ---------------------------------------------
    def refresh_local_hazard(self):
        try:
            point = coordinates(self.dest_coords)
        except ValueError:
            self.site.pop('seismicHazard', None)
            return
        self.site['seismicHazard'] = gem_hazard.lookup(point)

    def location_ready(self):
        try:
            destination = coordinates(self.dest_coords)
        except ValueError:
            return
        site_service.apply_context(self.site, site_service.context(destination))
        sc.apply_zoning(self.site, standards.lookup(destination, sc.get(self.site, 'environment.siteAltitudeM')['value']))
        sc.recommendation(self.site)
        self.state.save()
        self.refresh_sources(force=False)

    def refresh_sources(self, force=False):
        self.refresh_local_hazard()
        self.refresh_region(force)
        self.refresh_climate(force)
        self.refresh_humidity(force)
        self.refresh_destination(force)

    def _job(self, name, work, apply, still_current):
        token = object()
        self.pending[name] = token

        def run():
            try:
                result = work()
            except Exception as error:  # every provider failure is shown as unavailable
                result = {'error': str(error)}
            with self.lock:
                if self.pending.get(name) is token:
                    self.pending.pop(name)
                if not still_current():
                    return
                apply(result)
                sc.recommendation(self.site)
                self.state.save()
        self.pool.submit(run)

    def refresh_destination(self, force=False):
        try:
            destination = coordinates(self.dest_coords)
        except ValueError:
            return
        geometry = self.route_results[self.selected]['geometry'] if self.route_context and self.selected is not None else None
        token = self.site_token
        server = self.state.data['server']
        key = (server, destination['lat'], destination['lon'], json.dumps(geometry, sort_keys=True))
        if force:
            self.sources_cache.pop(key, None)

        def apply(result):
            if result and 'error' not in result:
                self.sources_cache[key] = result
                if len(self.sources_cache) > 16:
                    self.sources_cache.pop(next(iter(self.sources_cache)))
            if 'altitude' in result:
                sc.automatic(self.site, 'transport.maxAltitudeM', *result['altitude'], status=result.get('altitudeStatus', 'AUTO'))
            if 'siteAltitude' in result:
                sc.automatic(self.site, 'environment.siteAltitudeM', result['siteAltitude'],
                             result.get('siteAltitudeSource', 'Source not specified'), 'VERIFY', detail=result.get('siteAltitudeDetail', ''))
            if 'elevationAnalysis' in result:
                self.site['elevationAnalysis'] = result['elevationAnalysis']
            if 'locationContext' in result:
                site_service.apply_context(self.site, result['locationContext'])
            if 'coastalDistance' in result:
                self.site['coastalDistance'] = result['coastalDistance']
            if 'zoning' in result:
                sc.apply_zoning(self.site, result['zoning'])
            self.site['lookupState'] = ('Destination elevation unavailable: ' + result['error'] if 'error' in result
                                        else 'Destination lookup complete. Available values and their sources are shown below.')

        if key in self.sources_cache:
            apply(self.sources_cache[key])
            sc.recommendation(self.site)
            self.state.save()
            return
        self.site['lookupState'] = 'Loading destination elevation and coastal data…'
        self._job('destination', lambda: site_sources.lookup(server, destination, geometry), apply,
                  lambda: token == self.site_token)

    def _weather(self, name, record, module, force):
        try:
            destination = coordinates(self.dest_coords)
        except ValueError:
            return
        existing = self.site.get(record, {})
        if not force and existing.get('status') == 'unavailable':
            return
        if (not force and existing.get('status') == 'ready' and existing.get('methodVersion') == module.VERSION
                and existing.get('periodEnd') == climate.period()[1].isoformat()):
            return
        if name in self.pending and not force:
            return
        location = self.dest_coords
        self.site[record] = {'status': 'loading'}

        def apply(result):
            if 'error' in result:
                self.site[record] = {'status': 'unavailable', 'message': result['error']}
            else:
                module.apply(self.site, result)
        self._job(name, lambda: module.lookup(destination, self.cache / (name + '-cache'), force=force), apply,
                  lambda: location == self.dest_coords)

    def refresh_climate(self, force=False):
        self._weather('climate', 'climate', climate, force)

    def refresh_humidity(self, force=False):
        self._weather('humidity', 'humidityAnalysis', humidity, force)

    def refresh_region(self, force=False):
        try:
            destination = coordinates(self.dest_coords)
        except ValueError:
            return
        existing = self.site.get('administrativeRegion', {})
        if not force and existing.get('requestedCoordinates') == destination and existing.get('status') == 'ready':
            return
        location = self.dest_coords

        def work():
            try:
                return regions.lookup(destination, self.cache / 'boundary-cache')
            except Exception:
                return dict(status='unavailable', name='', source=regions.SOURCE,
                            detail='Administrative boundary unavailable. Other destination data remains available.')

        def apply(result):
            self.site['administrativeRegion'] = result
        self._job('region', work, apply, lambda: location == self.dest_coords)

    # ----- route ---------------------------------------------------------
    def route_payload(self, confirmed, preliminary=False):
        """Preliminary routes run automatically and never count as vehicle approval."""
        if not self.active:
            raise ValueError('No compatible vehicle. Edit the product or choose a profile.')
        if not self.origin_coords:
            raise ValueError('Choose the departure: select an address suggestion or click on the map.')
        if not self.dest_coords:
            raise ValueError('Choose the destination: select an address suggestion or click on the map.')
        if not self.origin_name or not self.dest_name:
            raise ValueError('Enter departure and destination names.')
        if not (self.accepted or confirmed or preliminary):
            raise ValueError('Confirm the vehicle assumptions before routing.')
        if confirmed:
            self.accepted = True
        origin, destination = coordinates(self.origin_coords), coordinates(self.dest_coords)
        via = [coordinates(text) for text in self.via.split(';') if text.strip()]
        payload = route_request(origin, destination, self.active['loaded'], via)
        context = {'product': deepcopy(self.state.data['product']), 'vehicle': deepcopy(self.active['vehicle']),
                   'loaded': deepcopy(self.active['loaded']), 'origin': dict(origin, name=self.origin_name),
                   'destination': dict(destination, name=self.dest_name), 'request': payload,
                   'calculated_at': stamp(), 'server': self.state.data['server'], 'vehicleConfirmed': self.accepted}
        return payload, context, self.generation, self.state.data['server']

    def finish_route(self, results, context, generation):
        if generation != self.generation:
            raise ValueError('Inputs changed during the request. Recalculate the route.')
        self.site['routeLookup'] = {'status': 'ready'}
        context['origin']['name'] = self.origin_name
        context['destination']['name'] = self.dest_name
        self.route_results = results
        self.route_context = context
        self.select_route(0)
        self.status = ('Route ready, including the detected ferry crossing.' if any(r.get('ferryDetected') for r in results)
                       else 'Valhalla route ready. Select an option and export Excel. Validate the proposed route.')

    def route_failed(self, message, generation):
        if generation == self.generation:
            self.site['routeLookup'] = {'status': 'unavailable', 'detail': message}
            self.status = message
            self.state.save()

    def select_route(self, index):
        if not self.route_context or not 0 <= index < len(self.route_results):
            raise ValueError('Calculate and select a route.')
        from route_segments import route_description
        self.selected = index
        r = self.route_results[index]
        route_key = json.dumps(r, sort_keys=True)
        changed = self.site_route_key != route_key
        if changed:
            self.site_route_key = route_key
            self.site_token += 1
            sc.invalidate(self.site, sc.ROUTE_KEYS)
        detail = route_description(r)
        sc.automatic(self.site, 'transport.distanceKm', r['distance_km'], 'Valhalla / OpenStreetMap', 'CALCULATED', detail=detail)
        sc.automatic(self.site, 'transport.maritimeTransport', r.get('maritimeTransport', 'Unknown'),
                     'Valhalla route ferry evidence' if r.get('maritimeTransport') == 'Yes' else 'No reliable maritime evidence in route response', 'VERIFY')
        self.site['transport']['ferryDetected'] = r.get('ferryDetected', False)
        if r.get('ferryDetected'):
            sc.automatic(self.site, 'transport.maritimeTransport', 'Unknown',
                         'Valhalla: ferry detected. Confirm marine versus inland crossing.', 'VERIFY')
        if changed:
            self.refresh_destination()
        sc.recommendation(self.site)
        self.state.save()

    # ----- deliveries and export ----------------------------------------
    def current_delivery(self, values):
        if not self.route_context or self.selected is None:
            raise ValueError('Calculate and select a route before exporting the current transport.')
        row = dict(deepcopy(self.route_context), **deepcopy(self.route_results[self.selected]))
        quantity = num(values.get('quantity'), 'Quantity', 1, True)
        if quantity > row['product']['quantity']:
            raise ValueError('Export quantity exceeds the product quantity.')
        row.update(id=uuid.uuid4().hex, quantity=quantity, return_km=num(values.get('return_km'), 'Empty return'),
                   position_km=num(values.get('position_km'), 'Positioning'), notes=str(values.get('notes', '')),
                   siteConditions=deepcopy(self.site))
        return row

    def save_delivery(self, values):
        row = self.current_delivery(values)
        used = sum(r['quantity'] for r in self.state.data['deliveries'] if r['product'] == row['product'])
        if used + row['quantity'] > row['product']['quantity']:
            raise ValueError('The allocated quantity exceeds the product total. Update saved deliveries or the product quantity.')
        if len(self.state.data['deliveries']) >= 100:
            raise ValueError('Maximum 100 saved deliveries in this version.')
        self.state.data['deliveries'].append(row)
        self.state.save()
        self.status = 'Delivery saved. Export Excel directly from Transport.'

    def archive_delivery(self, ident):
        rows = self.state.data['deliveries']
        row = next((r for r in rows if r['id'] == ident), None)
        if row is None:
            raise ValueError('Select a delivery.')
        self.state.data.setdefault('archive', []).append(row)
        self.state.data['deliveries'] = [r for r in rows if r['id'] != ident]
        self.state.save()

    def export(self, values):
        from excel_export import export_workbook
        rates = {k: num(values.get(k, 0), k) for k in ('loaded', 'empty', 'fixed', 'markup', 'vat')}
        if values.get('mode') == 'saved':
            rows = deepcopy(self.state.data['deliveries'])
            if not rows:
                raise ValueError('Save a route before exporting saved deliveries.')
        else:
            rows = [self.current_delivery(values)]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'export.xlsx'
            export_workbook(path, rows, rates)
            data = path.read_bytes()
        self.state.data['rates'] = rates
        self.state.save()
        self.status = 'Excel exported.'
        return data

    # ----- views ---------------------------------------------------------
    def snapshot(self):
        data = self.state.data
        product_data = data['product']
        deliveries = [dict(id=r['id'], name=r['product']['name'] + ' → ' + r['destination']['name'],
                           distance_km=r['distance_km'], quantity=r['quantity'],
                           empty_km=r['return_km'] + r['position_km'], total=calculate(r, data['rates'])['total'])
                      for r in data['deliveries']]
        return dict(
            product=product_data,
            presets=[dict(id=v['id'], title=PRESET_TITLES.get(v['id'], v['name']), name=v['name'], example=v['example'])
                     for v in data['vehicles']],
            active=deepcopy(self.active), manual=self.manual, accepted=self.accepted,
            profileSummary=self.profile_summary(),
            origin=dict(name=self.origin_name, coords=self.origin_coords),
            destination=dict(name=self.dest_name, coords=self.dest_coords), via=self.via,
            routes=[dict(name=r['name'], distance_km=r['distance_km'], hours=r['hours'], geometry=r['geometry'],
                         ferryDetected=r.get('ferryDetected', False)) for r in self.route_results],
            selectedRoute=self.selected, routeDetail=self.route_detail(),
            rates=data['rates'], deliveries=deliveries, status=self.status,
            region=self.region_summary(), server=data['server'])

    def route_detail(self):
        if self.selected is None or not self.route_results:
            return ''
        from route_segments import route_description
        return route_description(self.route_results[self.selected])

    def region_summary(self):
        region = self.site.get('administrativeRegion') or {}
        return dict(status=region.get('status'), name=region.get('name', ''),
                    version=uuid.uuid5(uuid.NAMESPACE_URL, json.dumps(region.get('requestedCoordinates'), sort_keys=True)).hex
                    if region.get('status') == 'ready' else None)

    def site_view(self):
        from dataset_explanations import table_value
        from site_overview import display_rows
        site = self.site
        progress = [site.get('lookupState', 'Choose the delivery destination to load site data.')]
        climate_state = site.get('climate', {})
        status = climate_state.get('status')
        if status == 'loading':
            progress.append('Climate: downloading and checking historical data…')
        elif status == 'unavailable':
            progress.append('Climate unavailable; no default temperatures are substituted.')
        elif status == 'ready':
            progress.append('Climate: ' + climate_state['periodStart'] + ' – ' + climate_state['periodEnd'] + ' · ' + climate_state['source'])
        if site.get('routeLookup', {}).get('status') == 'unavailable':
            progress.append('Road route unavailable · destination data loads independently.')
        hum = site.get('humidityAnalysis', {})
        if hum.get('status') == 'loading':
            progress.append('Humidity: downloading hourly data…')
        elif hum.get('status') == 'ready':
            progress.append('Humidity: ' + hum['periodStart'] + ' – ' + hum['periodEnd'] + ' · '
                            + hum.get('source', 'Source not specified') + ' · hourly values')
        elif hum.get('status') == 'unavailable':
            progress.append('Humidity: source unavailable; retry Refresh data.')
        warnings = []
        if sc.get(site, 'environment.marineEnvironment')['value'] in ('Yes', 'Possible'):
            warnings.append(MARINE_WARNING)
        if sc.get(site, 'transport.maritimeTransport')['value'] == 'Yes':
            warnings.append(MARITIME_WARNING)
        elif site['transport'].get('ferryDetected'):
            warnings.append(FERRY_WARNING)
        rows = []
        for row in display_rows(site):
            value, unit = table_value(row) if not row['section'] else ('', '')
            estimate = row['key'] == 'environment.suggestedCorrosivity' or (
                site.get('deposition', {}).get('qualityFlags') and row['key'] in ('deposition.wet', 'deposition.total', 'deposition.chlorideTotalProxy'))
            rows.append(dict(key=row['key'], label=row['label'], value=value, unit=unit, source=row['source'],
                             meaning=row.get('meaning', ''), brief=row.get('brief', ''), status=row.get('status', ''),
                             section=row['section'], parent=row.get('parent', ''), expandable=row.get('expandable', False),
                             estimate=bool(estimate)))
        return dict(address=site.get('destinationAddress') or '', coordinates=site.get('destinationCoordinates') or '',
                    progress=progress, warnings=warnings, rows=rows, pending=sorted(self.pending),
                    region=self.region_summary())

    def value_details(self, key):
        from value_details import build
        document = build(self.site, key)
        if not document:
            raise ValueError('Unknown value.')
        return dict(title=document['title'], value=document['value'],
                    sections=[dict(title=t, body=b) for t, b in document['sections']],
                    links=[dict(label=label, url=url) for label, url in document['links']])

    def region_geometry(self):
        region = self.site.get('administrativeRegion') or {}
        if region.get('status') != 'ready':
            return None
        return dict(name=region['name'], geometry=region['geometry'], source=region.get('source', ''))


def reverse_record(target, coords, point):
    base = dict(source=places.SOURCE, sourceUrl=places.DOCS, coordinates=coords, requestedCoordinates=dict(point))
    try:
        result = places.reverse(point['lat'], point['lon'])
    except Exception:
        result = dict(status='unavailable', detail='Address service unavailable. Try selecting the point again; exact coordinates are retained.')
    return dict(base, **result)


def route(server, payload):
    return routing.route(server, payload)
