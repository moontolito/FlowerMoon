import tempfile,unittest
from unittest.mock import patch
import places,regions,site_conditions as sc
from site_overview import rows

class PlaceRegionTests(unittest.TestCase):
    def test_autocomplete_provider_language_cache_and_coordinates(self):
        places.search.cache_clear()
        data={'features':[{'geometry':{'type':'Point','coordinates':[139.7,35.6]},'properties':{'name':'Tokyo','city':'Tokyo','country':'Japan','state':'Tokyo'}}]}
        with patch('places.request',return_value=data) as fetch:
            a=places.search('Tokyo');self.assertEqual(a,places.search('Tokyo'))
            self.assertEqual(fetch.call_count,1);url=fetch.call_args.args[0]
            self.assertIn('photon',url);self.assertIn('lang=en',url);self.assertNotIn('nominatim',url)
            self.assertEqual(a[0]['lat'],35.6);self.assertEqual(a[0]['lon'],139.7)
            self.assertEqual(a[0]['label'],'Tokyo, Japan')
        self.assertEqual(places.search('ab'),[])

    def test_region_holes_and_dateline(self):
        shape=dict(type='Polygon',coordinates=[[[0,0],[10,0],[10,10],[0,10],[0,0]],[[2,2],[4,2],[4,4],[2,4],[2,2]]])
        self.assertTrue(regions.contains(shape,dict(lat=1,lon=1)))
        self.assertFalse(regions.contains(shape,dict(lat=3,lon=3)))
        shape=dict(type='MultiPolygon',coordinates=[[[[179,-5],[-179,-5],[-179,5],[179,5],[179,-5]]]])
        self.assertTrue(regions.contains(shape,dict(lat=0,lon=-179.5)))
        self.assertFalse(regions.contains(shape,dict(lat=0,lon=0)))

    def test_global_boundary_selection_cache_and_missing_coverage(self):
        meta=dict(simplifiedGeometryGeoJSON='https://example.org/regions.json',boundarySource='Survey office',boundaryYearRepresented='2024',boundaryLicense='CC BY 4.0')
        geometry=dict(type='Polygon',coordinates=[[[0,0],[10,0],[10,10],[0,10],[0,0]]])
        data=dict(features=[dict(properties=dict(shapeName='Test region'),geometry=geometry)])
        with tempfile.TemporaryDirectory() as cache,patch('regions.country',return_value=dict(iso3='ZAF',name='South Africa')),patch('regions.read_json',side_effect=[meta,data]) as api:
            a=regions.lookup(dict(lat=1,lon=1),cache);b=regions.lookup(dict(lat=1,lon=1),cache)
            self.assertEqual(a,b);self.assertEqual(api.call_count,2);self.assertIn('/ZAF/ADM1/',api.call_args_list[0].args[0])
            self.assertEqual(a['name'],'Test region');self.assertEqual(a['geometry'],geometry)
            self.assertEqual(regions.lookup(dict(lat=50,lon=50),cache)['status'],'unavailable')

    def test_overview_explicit_sources_and_destination_scope(self):
        site=sc.create();sc.sync(site,'Departure','Tokyo','1,2','35.6,139.7')
        sc.automatic(site,'environment.siteAltitudeM',32,'Copernicus DEM GLO-90','VERIFY')
        sc.automatic(site,'humidity.mean',64,'Open-Meteo Historical / ERA5','CALCULATED')
        site['humidityAnalysis']=dict(gridLatitude=35.5,gridLongitude=139.75,periodStart='1996-01-01',periodEnd='2025-12-31')
        data={r['key']:r for r in rows(site)}
        self.assertEqual(data['environment.siteAltitudeM']['source'],'Copernicus DEM GLO-90 (2021)')
        self.assertEqual(data['humidity.mean']['source'],'Open-Meteo Historical / ERA5')
        self.assertIn('35.5, 139.75',data['humidity.mean']['detail']);self.assertIn('Tokyo',data['humidity.mean']['detail'])
        self.assertFalse(any('note' in r for r in data.values()))
        sc.apply_manual(site,{'humidity.mean':50});sc.sync(site,'Departure','Sydney','1,2','-33.8,151.2')
        row=next(r for r in rows(site) if r['key']=='humidity.mean')
        self.assertEqual(row['source'],'Manual entry');self.assertIn('Previous destination',row['reference'])

if __name__=='__main__':unittest.main()
