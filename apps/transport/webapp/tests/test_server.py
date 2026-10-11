"""Browser API checks with external providers replaced by deterministic fakes."""
import io
import math
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

APP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP))

from fastapi.testclient import TestClient  # noqa: E402

from webapp import server, workspace as ws  # noqa: E402

CLUJ = '46.7712000, 23.6236000'


def fake_route(_server, payload):
    a, b = payload['locations'][0], payload['locations'][-1]
    coords = [[a['lon'] + (b['lon'] - a['lon']) * t / 10, a['lat'] + (b['lat'] - a['lat']) * t / 10] for t in range(11)]
    return [dict(name='Option 1', distance_km=380.0, hours=6.1, geometry=dict(type='LineString', coordinates=coords),
                 ferryDetected=False, crossings=[], maritimeTransport='No'),
            dict(name='Option 2', distance_km=425.0, hours=6.9, geometry=dict(type='LineString', coordinates=coords[::-1][::-1]),
                 ferryDetected=False, crossings=[], maritimeTransport='No')]


def fake_sources(_server, destination, geometry=None):
    return dict(siteAltitude=330.0, siteAltitudeSource='Copernicus DEM GLO-90 · DSM 2021', altitude=(812.0, 'test samples'),
                altitudeStatus='VERIFY', elevationAnalysis=dict(values=[330.0], complete=True),
                coastalDistance=ws.site_sources.geography.coast(destination),
                locationContext=ws.site_service.context(destination),
                zoning=ws.standards.lookup(destination, 330.0))


def unavailable(*_args, **_kwargs):
    raise ValueError('offline test')


class BrowserApi(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        patches = [
            mock.patch.object(server, 'DATA', Path(self.folder.name)),
            mock.patch.object(ws, 'route', fake_route),
            mock.patch.object(ws.site_sources, 'lookup', fake_sources),
            mock.patch.object(ws.climate, 'lookup', unavailable),
            mock.patch.object(ws.humidity, 'lookup', unavailable),
            mock.patch.object(ws.regions, 'lookup', unavailable),
            mock.patch.object(ws.places, 'search', lambda q: [dict(label='Cluj-Napoca, Romania', lat=46.7712, lon=23.6236)]),
            mock.patch.object(ws.places, 'reverse', lambda lat, lon: dict(status='ready', label='Mapped address', detail='test')),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        server._sessions.clear()
        self.client = TestClient(server.app)
        self.addCleanup(self.folder.cleanup)

    def wait(self):
        for _ in range(100):
            view = self.client.get('/api/site').json()
            if not view['pending']:
                return view
            time.sleep(.05)
        self.fail('Destination jobs did not finish.')

    def choose_destination(self):
        response = self.client.post('/api/locations', json=dict(
            originName='Botosani', originCoords='47.8528263, 26.759334', destinationName='Cluj-Napoca', destinationCoords=CLUJ))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def rows(self, view):
        return {row['key']: row for row in view['rows']}

    def test_default_state_needs_no_desktop(self):
        state = self.client.get('/api/state').json()
        self.assertEqual(state['product']['name'], 'Module 1')
        self.assertTrue(state['active']['fits'])
        self.assertNotIn('tkinter', sys.modules)
        self.assertIn('fm_session', self.client.cookies)

    def test_destination_loads_local_and_provider_data(self):
        self.choose_destination()
        rows = self.rows(self.wait())
        self.assertEqual(rows['country']['value'], 'Romania')
        self.assertEqual(rows['seismic.pga']['unit'], 'g')
        self.assertTrue(math.isfinite(float(rows['seismic.pga']['value'])))
        self.assertEqual(rows['environment.siteAltitudeM']['value'], '330')
        self.assertNotEqual(rows['seismic.ag']['value'], 'Not available')
        self.assertEqual(rows['design']['value'], 'Not available')  # failed climate is never replaced by defaults
        details = self.client.get('/api/site/value', params=dict(key='seismic.pga')).json()
        self.assertEqual(details['title'], 'PGA')
        self.assertTrue(all(link['url'].startswith('https://') for link in details['links']))

    def test_route_requires_confirmation_then_exports_excel(self):
        self.choose_destination()
        refused = self.client.post('/api/route', json={})
        self.assertEqual(refused.status_code, 400)
        state = self.client.post('/api/route', json=dict(confirmed=True)).json()
        self.assertEqual([r['name'] for r in state['routes']], ['Option 1', 'Option 2'])
        self.assertEqual(state['selectedRoute'], 0)
        state = self.client.post('/api/route/select', json=dict(index=1)).json()
        self.assertEqual(state['selectedRoute'], 1)
        rows = self.rows(self.wait())
        self.assertEqual(rows['transport.distanceKm']['value'], '425')
        response = self.client.post('/api/export', json=dict(mode='current', quantity=1, return_km=425, position_km=0,
                                                             loaded=2, empty=1, fixed=0, markup=10, vat=19, notes='test'))
        self.assertEqual(response.status_code, 200, response.text)
        with zipfile.ZipFile(io.BytesIO(response.content)) as workbook:
            self.assertIn('xl/worksheets/sheet3.xml', workbook.namelist())
            self.assertIn('Cluj-Napoca', workbook.read('xl/worksheets/sheet2.xml').decode())

    def test_preliminary_route_needs_no_confirmation_and_never_fails_loudly(self):
        self.choose_destination()
        state = self.client.post('/api/route', json=dict(preliminary=True)).json()
        self.assertEqual(len(state['routes']), 2)
        self.assertFalse(state['accepted'])  # automatic routes are not vehicle approval
        again = self.client.post('/api/route', json=dict(preliminary=True))
        self.assertEqual(again.status_code, 200)
        with mock.patch.object(ws, 'route', unavailable):
            self.client.post('/api/locations', json=dict(
                originName='Botosani', originCoords='47.8528263, 26.759334', destinationName='Iasi', destinationCoords='47.16, 27.58'))
            failed = self.client.post('/api/route', json=dict(preliminary=True))
            self.assertEqual(failed.status_code, 200)
            self.assertEqual(failed.json()['routes'], [])
            self.assertEqual(self.client.post('/api/route', json=dict(confirmed=True)).status_code, 400)

    def test_saved_deliveries_export_and_archive(self):
        self.choose_destination()
        self.client.post('/api/route', json=dict(confirmed=True))
        state = self.client.post('/api/deliveries', json=dict(quantity=1, return_km=380, position_km=0, notes='')).json()
        self.assertEqual(len(state['deliveries']), 1)
        over = self.client.post('/api/deliveries', json=dict(quantity=1, return_km=0, position_km=0, notes=''))
        self.assertEqual(over.status_code, 400)  # product quantity is already allocated
        exported = self.client.post('/api/export', json=dict(mode='saved', loaded=0, empty=0, fixed=0, markup=0, vat=0))
        self.assertEqual(exported.status_code, 200)
        state = self.client.delete('/api/deliveries/' + state['deliveries'][0]['id']).json()
        self.assertEqual(state['deliveries'], [])

    def test_vehicle_adjustment_validation(self):
        state = self.client.get('/api/state').json()
        loaded = dict(state['active']['loaded'], height=0.5)
        response = self.client.post('/api/vehicle/adjust', json=loaded)
        self.assertEqual(response.status_code, 400)
        self.assertIn('cannot be below', response.json()['detail'])
        presets = [p['id'] for p in state['presets']]
        state = self.client.post('/api/vehicle/preset', json=dict(id=presets[0])).json()
        self.assertIsNone(state['active'])  # a 9 m module does not fit the light flatbed

    def test_map_click_label_keeps_coordinates(self):
        self.choose_destination()
        state = self.client.post('/api/locations/reverse', json=dict(target='destination')).json()
        self.assertEqual(state['destination'], dict(name='Mapped address', coords=CLUJ))

    def test_invalid_input_and_hazard_tiles(self):
        bad = self.client.post('/api/locations', json=dict(destinationName='x', destinationCoords='999, 1'))
        self.assertEqual(bad.status_code, 400)
        tile = self.client.get('/api/hazard/6/36/22.png')
        self.assertEqual(tile.status_code, 200)
        self.assertEqual(tile.content[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(self.client.get('/api/hazard/20/0/0.png').status_code, 404)
        self.assertEqual(len(self.client.get('/api/hazard/legend').json()), 11)
        page = self.client.get('/')
        self.assertIn('FlowerMoon Transport', page.text)


if __name__ == '__main__':
    unittest.main()
