import unittest
from unittest.mock import patch
import zoning
import site_conditions as sc
import site_sources

class ZoningTests(unittest.TestCase):
    def test_local_coast_is_screening_not_salinity(self):
        from site_environment.geography import coast
        result=coast({'lat':44.17,'lon':28.65})
        self.assertIsNotNone(result['value']);self.assertIn('Natural Earth',result['source'])
        self.assertNotIn('corrosivity',result)
        self.assertIsNotNone(coast({'lat':40,'lon':-75})['value'])
    def test_route_sampling_covers_endpoints_and_bends(self):
        shape,spacing=site_sources.route_samples({'coordinates':[[25,44],[25,45],[26,45]]},budget=64)
        self.assertEqual(len(shape),64);self.assertGreater(spacing,500)
        self.assertEqual(shape[0],{'lat':44,'lon':25});self.assertEqual(shape[-1],{'lat':45,'lon':26})
        self.assertTrue(all(abs(p['lon']-25)<1e-8 or abs(p['lat']-45)<1e-8 for p in shape))
    def test_published_polygons_for_cities(self):
        # Fixed checkpoints, checked against labels of the source KML polygons.
        for lat,lon,expected in [(44.4268,26.1025,(.3,1.6,2,.5)),(47.7486,26.6694,(.2,.7,2.5,.7)),(44.17,28.65,(.2,.7,1.5,.5)),(46.77,23.59,(.1,.7,1.5,.5))]:
            result=zoning.lookup({'lat':lat,'lon':lon},100)
            self.assertEqual(tuple(result[k]['value'] for k in zoning.MAPS),expected)
    def test_outside_romania_has_no_invented_values(self):
        self.assertTrue(all(v['value'] is None for v in zoning.lookup({'lat':48.8566,'lon':2.3522},35).values()))
    def test_site_altitude_not_route_max_controls_snow_and_wind(self):
        for height in (1000,1500):
            data=zoning.lookup({'lat':44.4268,'lon':26.1025},height)
            self.assertEqual(data['snow.sk']['value'],2);self.assertEqual(data['wind.qb']['value'],.5)
            self.assertEqual(data['snow.sk']['applicability'],'unverified_at_altitude')
            self.assertIn('applicability check',data['wind.qb']['detail'])
            self.assertEqual(data['seismic.ag']['value'],.3)
        self.assertEqual(zoning.lookup({'lat':44.4268,'lon':26.1025},999)['snow.sk']['value'],2)
    def test_holes_overlap_lower_bound_and_boundary(self):
        outer=zoning.ring('0,0 10,0 10,10 0,10 0,0')
        hole=zoning.ring('4,4 6,4 6,6 4,6 4,4')
        base=dict(value=.7,operator='≥',description='qb ≥0.7',outer=outer,holes=[hole],bounds=(0,0,10,10))
        with patch('zoning.load_map',return_value=[base]):
            self.assertIsNone(zoning.lookup({'lat':5,'lon':5},10)['wind.qb']['value'])
            entry=zoning.lookup({'lat':1,'lon':1},10)['wind.qb']
            self.assertEqual((entry['value'],entry['operator']),(.7,'≥'))
            self.assertTrue(zoning.lookup({'lat':.001,'lon':1},10)['wind.qb']['nearBoundary'])
        with patch('zoning.load_map',return_value=[base,dict(base,value=.6)]):
            self.assertIsNone(zoning.lookup({'lat':1,'lon':1},10)['wind.qb']['value'])
    def test_automatic_zoning_preserves_engineer_override(self):
        site=sc.create();sc.apply_manual(site,{'seismic.ag':.4})
        sc.apply_zoning(site,zoning.lookup({'lat':44.4268,'lon':26.1025},100))
        self.assertEqual(sc.get(site,'seismic.ag')['value'],.4)
        self.assertEqual(sc.get(site,'seismic.tc')['value'],1.6)

if __name__=='__main__':unittest.main()
