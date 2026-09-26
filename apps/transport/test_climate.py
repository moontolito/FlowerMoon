import unittest,tempfile,json
from datetime import date,timedelta
from copy import deepcopy
from unittest.mock import patch
import climate
import site_conditions as sc

START=date(2024,2,28);END=date(2024,3,1)
def fixture():
    return dict(daily={'time':['2024-02-28','2024-02-29','2024-03-01'],'temperature_2m_max':[12,15,10],'temperature_2m_min':[-8,-9,-5],'temperature_2m_mean':[2,3,1]},daily_units={k:'°C' for k in climate.VARIABLES})

class ClimateTests(unittest.TestCase):
    def test_period(self):
        self.assertEqual(climate.period(date(2026,9,25)),(date(1996,1,1),date(2025,12,31)))
    def test_daily_extremes_not_annual_mean(self):
        r=climate.summarize(fixture(),START,END)
        self.assertEqual((r['maximum'],r['minimum'],r['maxDailyMean'],r['minDailyMean']),(15,-9,3,1))
        self.assertEqual(r['maximumDate'],'2024-02-29')
    def test_reject_partial_null_invalid_units_and_order(self):
        for change in ['missingday','null','nan','unit','ordering']:
            f=fixture()
            if change=='missingday':f['daily']['time'].pop()
            if change=='null':f['daily']['temperature_2m_min'][0]=None
            if change=='nan':f['daily']['temperature_2m_min'][0]=float('nan')
            if change=='unit':f['daily_units']['temperature_2m_min']='F'
            if change=='ordering':f['daily']['temperature_2m_mean'][0]=90
            with self.assertRaises(ValueError):climate.summarize(f,START,END)
    def test_historical_values_without_project_limits_and_manual_preservation(self):
        site=sc.create();sc.sync(site,'A','B','1,2','3,4')
        result=climate.summarize(fixture(),START,END);climate.apply(site,result)
        self.assertEqual(sc.get(site,'temperature.maxDesign')['value'],15)
        self.assertEqual(sc.get(site,'temperature.minDesign')['value'],-9)
        self.assertEqual(sc.get(site,'temperature.maxDailyAverage')['value'],3)
        result.update(maximum=47.2,minimum=-34.2);climate.apply(site,result)
        self.assertEqual(sc.get(site,'temperature.maxDesign')['value'],47.2)
        self.assertEqual(sc.get(site,'temperature.minDesign')['value'],-34.2)
        sc.apply_manual(site,{'temperature.maxDesign':50});climate.apply(site,result)
        self.assertEqual(sc.get(site,'temperature.maxDesign')['value'],50)
        sc.sync(site,'A','C','1,2','5,6')
        self.assertTrue(sc.get(site,'temperature.maxDesign')['reviewRequired'])
        self.assertIsNone(sc.get(site,'temperature.maxDailyAverage')['value'])
        self.assertEqual(site['climate']['status'],'pending')
    def test_legacy_project_defaults_removed_but_manual_values_retained(self):
        old=sc.create()
        old['temperature']['maxDesign'].update(value=45,status='DEFAULT')
        old['temperature']['minDesign'].update(value=-30,status='MANUAL',manualOverride=True)
        updated=sc.migrate(old)
        self.assertIsNone(updated['temperature']['maxDesign']['value'])
        self.assertEqual(updated['temperature']['minDesign']['value'],-30)
    def test_open_meteo_cache_force_and_no_credentials_in_provenance(self):
        response=unittest.mock.MagicMock();response.__enter__.return_value=response;response.read.return_value=json.dumps(fixture()).encode()
        with tempfile.TemporaryDirectory() as d,patch.dict('os.environ',{'FLOWERMOON_CLIMATE_URL':'https://example.test/archive','FLOWERMOON_CLIMATE_API_KEY':'test-secret'}),patch('climate.period',return_value=(START,END)),patch('climate.urlopen',return_value=response) as api:
            a=climate.lookup({'lat':44,'lon':28},d);b=climate.lookup({'lat':44,'lon':28},d)
            self.assertEqual(a,b);self.assertEqual(api.call_count,1)
            self.assertEqual(a['actualProvider'],'open-meteo-era5');self.assertFalse(a['providerFallback'])
            self.assertNotIn('test-secret',json.dumps(a))
            climate.lookup({'lat':44,'lon':28},d,force=True);self.assertEqual(api.call_count,2)
    def test_service_failure_has_no_alternative_provider(self):
        with tempfile.TemporaryDirectory() as d,patch('climate.urlopen',side_effect=OSError('offline secret')) as api:
            with self.assertRaisesRegex(ValueError,'Open-Meteo') as err:climate.lookup({'lat':44,'lon':28},d)
            self.assertEqual(api.call_count,1);self.assertNotIn('secret',str(err.exception))

if __name__=='__main__':unittest.main()
