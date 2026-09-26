import json,tempfile,unittest
from pathlib import Path
from datetime import date
from unittest.mock import patch,MagicMock
from PIL import Image,TiffImagePlugin
import elevation,humidity,site_conditions as sc
from weather_config import configuration
from site_environment import registry
from test_humidity import fixture,START,END

class SourceAlignmentTests(unittest.TestCase):
    def test_explicit_sources_and_commercial_endpoint(self):
        self.assertEqual(registry.weather_order(),['open-meteo-era5'])
        with patch.dict('os.environ',{'FLOWERMOON_CLIMATE_URL':'','FLOWERMOON_CLIMATE_API_KEY':'test-secret'}):
            endpoint,key=configuration();self.assertEqual(endpoint,'https://customer-archive-api.open-meteo.com/v1/archive')
        with patch.dict('os.environ',{'FLOWERMOON_CLIMATE_URL':'https://example.test/?apikey=secret'}):
            with self.assertRaises(ValueError):configuration()
        self.assertFalse(next(p for p in registry.manifest() if p['id']=='efehr-eshm20')['configured'])
    def test_migration_preserves_manual_and_archives_old_sources(self):
        site=sc.create();sc.automatic(site,'humidity.maximum',90,'NASA POWER')
        sc.automatic(site,'environment.siteAltitudeM',123,'Valhalla DEM')
        sc.automatic(site,'temperature.maxDesign',40,'NASA POWER')
        sc.apply_manual(site,{'humidity.mean':60})
        site['humidityAnalysis']={'status':'ready','source':'NASA POWER'}
        migrated=sc.migrate(site)
        self.assertIsNone(migrated['humidity']['maximum']['value'])
        self.assertIsNone(migrated['temperature']['maxDesign']['value'])
        self.assertIsNone(migrated['environment']['siteAltitudeM']['value'])
        self.assertEqual(migrated['humidity']['mean']['value'],60)
        self.assertEqual(migrated['sourceHistory'][0]['data']['humidity.maximum']['value'],90)
        self.assertEqual(sc.migrate(migrated),migrated)
    def test_hourly_duplicates_gaps_and_invalid_samples(self):
        raw=fixture();raw['hourly']['time'][1]=raw['hourly']['time'][0]
        with self.assertRaises(ValueError):humidity.summarize(raw,START,END)
        raw=fixture();raw['hourly']['time'].pop(0);raw['hourly']['relative_humidity_2m'].pop(0)
        self.assertEqual(humidity.summarize(raw,START,END)['validHours'],71)
        self.assertLess(humidity.summarize(raw,START,END)['validFraction'],1)
    def test_humidity_credentials_never_saved(self):
        response=MagicMock();response.__enter__.return_value=response;response.read.return_value=json.dumps(fixture()).encode()
        with tempfile.TemporaryDirectory() as d,patch('humidity.period',return_value=(START,END)),patch('humidity.urlopen',return_value=response),patch.dict('os.environ',{'FLOWERMOON_CLIMATE_API_KEY':'test-secret'}):
            result=humidity.lookup({'lat':40,'lon':-74},d)
            self.assertNotIn('test-secret',json.dumps(result))
            for path in Path(d).glob('*.json'):self.assertNotIn('test-secret',path.read_text())
    def test_tile_addressing_global(self):
        self.assertIn('S34_00_E151_00',elevation.tile_name({'lat':-33.8,'lon':151.2}))
        self.assertIn('N40_00_W075_00',elevation.tile_name({'lat':40.7,'lon':-74.01}))
        self.assertEqual(elevation.tile_name({'lat':0,'lon':180}),elevation.tile_name({'lat':0,'lon':-180}))
    def test_geotiff_pixel_centres_and_missing_tile(self):
        image=Image.new('F',(3,3));image.putdata(range(9))
        image.tag_v2={33550:(.1,.1,0),33922:(0,0,0,28,45,0),34735:(1,1,0,2,1025,0,1,2,2048,0,1,4326)}
        self.assertEqual(elevation.pixel(image,{'lat':44.9,'lon':28.1}),4)
        self.assertEqual(elevation.pixel(image,{'lat':45,'lon':28}),0)
        with patch('elevation._tile',side_effect=OSError('404')):
            result=elevation.samples([{'lat':0,'lon':0}])
            self.assertEqual(result['values'],[None]);self.assertFalse(result['complete'])

if __name__=='__main__':unittest.main()
