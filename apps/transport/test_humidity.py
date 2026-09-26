import json,tempfile,unittest
from datetime import date,datetime,timedelta
from copy import deepcopy
from unittest.mock import patch
from pathlib import Path
import humidity,site_conditions as sc,zoning
from site_overview import rows

START=date(2024,2,28);END=date(2024,3,1)
def fixture():
    return dict(hourly={'time':[(datetime(2024,2,28)+timedelta(hours=i)).strftime('%Y-%m-%dT%H:%M') for i in range(72)],'relative_humidity_2m':[40]*24+[70]*24+[90]*24},hourly_units={'relative_humidity_2m':'%'},utc_offset_seconds=0)


class HumidityTests(unittest.TestCase):
    def test_actual_statistics_and_period(self):
        r=humidity.summarize(fixture(),START,END)
        self.assertEqual((r['maximum'],r['minimum'],r['validHours']),(90,40,72))
        self.assertAlmostEqual(r['mean'],200/3)
        self.assertEqual(r['maximumDate'],'2024-03-01T00:00');self.assertEqual(r['validFraction'],1)
    def test_partial_series_retained_with_explicit_coverage(self):
        f=fixture();f['hourly']['relative_humidity_2m'][24:48]=[-999]*24
        r=humidity.summarize(f,START,END)
        self.assertEqual((r['maximum'],r['mean'],r['minimum']),(90,65,40))
        self.assertAlmostEqual(r['validFraction'],2/3);self.assertIn('incompletă',r['detail'])
        site=sc.create();humidity.apply(site,r)
        self.assertEqual(site['humidity']['mean']['status'],'VERIFY')
        self.assertIn('incompletă',next(x for x in rows(site) if x['key']=='humidity.mean')['note'])
    def test_units_empty_invalid_dates(self):
        for mode in ('unit','empty','dates','invalid'):
            f=fixture()
            if mode=='unit':f['hourly_units']['relative_humidity_2m']='g/kg'
            elif mode=='empty':f['hourly']={}
            elif mode=='dates':f['hourly']['time'][0]='2024-03-32T00:00'
            else:f['hourly']['relative_humidity_2m']=[float('nan'),101,True]*24
            with self.assertRaises(ValueError):humidity.summarize(f,START,END)
    def test_manual_override_and_location_reset(self):
        site=sc.create();sc.sync(site,'A','B','1,2','3,4')
        sc.apply_manual(site,{'humidity.mean':55})
        humidity.apply(site,humidity.summarize(fixture(),START,END))
        self.assertEqual(site['humidity']['mean']['value'],55)
        sc.sync(site,'A','C','1,2','5,6')
        self.assertEqual(site['humidity']['mean']['value'],55);self.assertTrue(site['humidity']['mean']['reviewRequired'])
        self.assertIsNone(site['humidity']['maximum']['value'])
        self.assertEqual(site['humidityAnalysis']['status'],'pending')
    def test_cache_force_and_provenance(self):
        response=unittest.mock.MagicMock();response.__enter__.return_value=response;response.read.return_value=json.dumps(fixture()).encode()
        with tempfile.TemporaryDirectory() as d,patch('humidity.period',return_value=(START,END)),patch('humidity.urlopen',return_value=response) as api:
            a=humidity.lookup(dict(lat=-33,lon=151),d);b=humidity.lookup(dict(lat=-33,lon=151),d)
            self.assertEqual(a,b);self.assertEqual(api.call_count,1);self.assertEqual(len(a['rawSha256']),64)
            humidity.lookup(dict(lat=-33,lon=151),d,force=True);self.assertEqual(api.call_count,2)
    def test_candidate_values_and_logical_groups(self):
        site=sc.create();sc.apply_zoning(site,zoning.lookup(dict(lat=44.4268,lon=26.1025),1200))
        items=rows(site);snow=next(r for r in items if r['key']=='snow.sk')
        self.assertEqual(snow['value'],'2 kN/m²');self.assertIn('1000',snow['note'])
        # Saved pre-update values hidden by the old altitude rule are also visible.
        site['snow']['sk']['value']=None
        self.assertEqual(next(r for r in rows(site) if r['key']=='snow.sk')['value'],'2 kN/m²')
        groups=[r['key'] for r in items if r['section']]
        self.assertEqual(groups,['section_location','section_transport','section_climate','section_exposure','section_structural','section_additional'])
        self.assertFalse(any(r['key'].startswith('humidity.value') for r in items))

if __name__=='__main__':unittest.main()
