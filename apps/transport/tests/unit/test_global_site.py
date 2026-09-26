import json
import math
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse,parse_qs
import routing,site_conditions as sc
from site_environment import geography,registry,standards,service
from map_widget import longitude_center,near_x,project

CHECKPOINTS=[('RO',44.4268,26.1025),('FR',48.8566,2.3522),('US',40.7128,-74.006),('BR',-23.5505,-46.6333),('JP',35.6762,139.6503),('ZA',-26.2041,28.0473),('AU',-33.8688,151.2093),('NZ',-41.2865,174.7762)]

class GlobalSiteTests(unittest.TestCase):
    def test_country_checkpoints_on_six_continents(self):
        for code,lat,lon in CHECKPOINTS:
            with self.subTest(code=code):self.assertEqual(geography.country(dict(lat=lat,lon=lon))['code'],code)

    def test_regional_values_never_leak_abroad(self):
        for code,lat,lon in CHECKPOINTS[1:]:
            with self.subTest(code=code),patch('zoning.lookup',side_effect=AssertionError('Romanian provider invoked abroad')):
                data=standards.lookup(dict(lat=lat,lon=lon),50)
                self.assertTrue(all(v['value'] is None and v['standard'] is None and v['availability']=='outside_coverage' for v in data.values()))
        ro=standards.lookup(dict(lat=44.4268,lon=26.1025),50)
        self.assertEqual(ro['seismic.ag']['value'],.3)
        self.assertEqual(ro['seismic.ag']['standard'],'P100-1/2013')

    def test_ambiguous_border_keeps_sourced_value_with_observation(self):
        with patch('site_environment.standards.country',return_value=dict(code='RO',name='Romania',nearBoundary=True)):
            item=standards.lookup(dict(lat=44.4268,lon=26.1025))['seismic.ag']
            self.assertEqual(item['value'],.3)
            self.assertEqual(item['applicability'],'jurisdiction_to_verify')
            self.assertIn('De verificat',item['detail'])

    def test_new_regional_provider_dispatch_does_not_use_romania(self):
        provider=registry.Provider('test-jp','structural','regional',('wind.qb',),'test', 'Fixture only',countries=('JP',),adapter='fixture_provider:lookup')
        module=SimpleNamespace(lookup=lambda p,h:{'wind.qb':dict(value=1,standard='TEST ONLY')})
        with patch('site_environment.standards.select',return_value=[provider]),patch('site_environment.standards.import_module',return_value=module) as imported:
            item=standards.lookup(dict(lat=35.68,lon=139.69))['wind.qb']
            self.assertEqual(item['provider'],'test-jp');self.assertEqual(item['jurisdiction'],'JP')
            self.assertEqual(item['standard'],'TEST ONLY');imported.assert_called_once_with('fixture_provider')

    def test_ocean_and_missing_dataset_are_unknown(self):
        self.assertIsNone(geography.country(dict(lat=0,lon=-140))['code'])
        with patch('site_environment.geography.countries',side_effect=OSError):
            self.assertIsNone(geography._country(1.12345,-150.12345)['code'])
        with self.assertRaises(ValueError):geography.country(dict(lat=float('nan'),lon=20))

    def test_coastal_polygon_gaps_are_not_assigned_a_country(self):
        point=dict(lat=44.17,lon=28.65)
        self.assertIsNone(geography.country(point)['code'])
        self.assertTrue(all(v['value'] is None for v in standards.lookup(point).values()))
        inland=dict(lat=44.18,lon=28.63)
        self.assertEqual(standards.lookup(inland,80)['seismic.ag']['value'],.2)

    def test_coast_all_hemispheres_no_iso_category(self):
        for lat,lon in [(35.68,139.69),(-33.87,151.21),(40.71,-74.00),(-33.92,18.42),(0,179.9),(89,30)]:
            coast=geography.coast(dict(lat=lat,lon=lon))
            self.assertTrue(math.isfinite(coast['value']) and coast['value']>=0)
            self.assertNotIn('corrosivity',coast)

    def test_antimeridian_geometry(self):
        distance=geography.segment_distance((1,180),(179,0),(-179,0))
        self.assertAlmostEqual(distance/1000,111.195,places=2)
        centre=longitude_center([179,-179]);self.assertAlmostEqual(abs(centre),180)
        cx=project(0,centre,6)[0]
        xs=[near_x(project(0,lon,6)[0],cx,6) for lon in (179,-179)]
        self.assertLess(abs(xs[0]-xs[1]),100)

    def test_global_geocoding_and_configurable_endpoint(self):
        with patch.dict('os.environ',{'FLOWERMOON_GEOCODER_URL':'https://example.test'}),patch('routing.request',return_value=[dict(display_name='Tokyo',lat='35.68',lon='139.69')]) as req:
            result=routing.geocode('Tokyo')
            self.assertEqual(result[0]['lon'],139.69)
            url=req.call_args[0][0];self.assertEqual(urlparse(url).netloc,'example.test')
            self.assertNotIn('countrycodes',parse_qs(urlparse(url).query))

    def test_migration_preserves_manual_and_archives_legacy(self):
        old=sc.create();old['schemaVersion']=1
        old['environment']['exteriorCorrosivity'].update(value='C3',status='DEFAULT')
        old['environment']['interiorCorrosivity'].update(value='C4',status='MANUAL',manualOverride=True)
        old['humidity']['value1'].update(value=100,status='DEFAULT')
        old['wind']['qb'].update(value=.5,status='VERIFY',source='RO map')
        old['seismic']['ag'].update(value=.3,status='MANUAL',manualOverride=True)
        new=sc.migrate(old)
        self.assertEqual(new['schemaVersion'],2)
        self.assertEqual(new['environment']['interiorCorrosivity']['value'],'C4')
        self.assertEqual(new['environment']['exteriorCorrosivity']['value'],'Manual / Unknown')
        self.assertEqual(new['legacyDefaults']['humidity.value1']['value'],100)
        self.assertIsNone(new['wind']['qb']['value']);self.assertIsNone(new['wind']['standard'])
        self.assertTrue(new['seismic']['ag']['reviewRequired'])
        self.assertEqual(sc.migrate(new),new)

    def test_global_switch_retains_override_with_review(self):
        site=sc.create();sc.sync(site,'A','B','1,2','44.4268,26.1025')
        sc.apply_zoning(site,standards.lookup(dict(lat=44.4268,lon=26.1025),20))
        sc.apply_manual(site,{'wind.qb':.9})
        sc.sync(site,'A','Tokyo','1,2','35.68,139.69')
        service.apply_context(site,service.context(dict(lat=35.68,lon=139.69)))
        sc.apply_zoning(site,standards.lookup(dict(lat=35.68,lon=139.69),20))
        self.assertEqual(site['wind']['qb']['value'],.9);self.assertTrue(site['wind']['qb']['reviewRequired'])
        self.assertIsNone(site['wind']['standard']);self.assertIsNone(site['seismic']['ag']['value'])

    def test_no_unsupported_methods_are_selected(self):
        self.assertEqual(registry.select('air_quality'),[])
        self.assertEqual(registry.select('structural','JP'),[])
        self.assertTrue(all(v['value'] is None for v in registry.pending_methods().values()))
        site=sc.create();sc.apply_manual(site,{'environment.marineEnvironment':'Yes','transport.maritimeTransport':'Yes'})
        sc.recommendation(site)
        self.assertIsNone(site['environment']['suggestedCorrosivity']['value'])
        self.assertIsNone(site['transport']['suggestedProtection']['value'])

if __name__=='__main__':unittest.main()
