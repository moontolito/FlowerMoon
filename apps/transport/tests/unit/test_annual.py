import calendar,json,tempfile,unittest
from pathlib import Path
from copy import deepcopy
from unittest.mock import MagicMock,patch
from datetime import date
import annual_deposition as a,annual_corrosion as c,site_conditions as sc
from site_overview import display_rows

POINT=dict(lat=45.1,lon=24.1)
def parts(year=2025):
    return [dict(month=m,count=calendar.monthrange(year,m)[1]*8,gridLatitude=45.2,gridLongitude=24.,
        means=dict(dry=2.,sedimentation=1.,wetLargeScale=.5,wetConvective=.2,temperature=10.,humidity=65.,so2Volume=5.),
        qualityFlags=[],wetScenarioUsable=True) for m in range(1,13)]
def ready(point=POINT,year=2025):
    result=dict(a.base(point,year),status='ready');result.update(a.aggregate(parts(year),year));return result

class AnnualTests(unittest.TestCase):
    def test_year_coverage_and_day_weighting(self):
        for year,days in [(2024,366),(2025,365)]:
            data=parts(year);data[1]['means']['temperature']=20
            value=a.aggregate(data,year)
            self.assertEqual(value['sampleCount'],days*8)
            self.assertAlmostEqual(value['means']['temperature'],10+10*calendar.monthrange(year,2)[1]/days)
        self.assertEqual(a.reference_year(date(2026,1,1)),2025)
        with self.assertRaises(ValueError):a.aggregate(parts()[:-1],2025)
        data=parts();data[0]['count']-=1
        with self.assertRaises(ValueError):a.aggregate(data,2025)

    def test_complete_year_only_and_wrong_destination(self):
        from test_deposition import ready as seasonal
        self.assertIsNone(c.evaluate(seasonal(),POINT)['category'])
        r=ready();estimate=c.evaluate(r,POINT)
        self.assertEqual(estimate['status'],'ready');self.assertFalse(estimate['seasonal'])
        self.assertAlmostEqual(estimate['rate'],c.steel_rate(10,65,4,1.65))
        self.assertIsNone(c.evaluate(r,dict(lat=0,lon=0))['category'])
        r['sampleCount']-=1;self.assertIsNone(c.evaluate(r,POINT)['category'])

    def test_flags_preserved_and_not_used_for_wet_scenario(self):
        monthly=parts();monthly[0]['means']['wetLargeScale']=-.5
        monthly[0].update(qualityFlags=['negative_wet_flux_samples'],wetScenarioUsable=False)
        data=dict(a.base(POINT,2025),status='ready');data.update(a.aggregate(monthly,2025))
        self.assertTrue(data['qualityFlags']);self.assertIsNone(c.evaluate(data,POINT)['wetScenarioRate'])
        self.assertIsNotNone(c.evaluate(data,POINT)['category'])

    def test_queue_limit_resume_and_cancel(self):
        with tempfile.TemporaryDirectory() as folder:
            client=MagicMock();client.retrieve.side_effect=[MagicMock(request_id='first',status='accepted'),MagicMock(request_id='second',status='running')]
            client.client.get_remote.return_value=MagicMock(status='accepted')
            with patch('cams.make_client',return_value=client):
                result=a.lookup(POINT,folder,year=2025)
                self.assertEqual(client.retrieve.call_count,2);self.assertEqual(result['completedMonths'],0)
                again=a.lookup(POINT,folder,year=2025)
                self.assertEqual(client.retrieve.call_count,2);self.assertEqual(client.client.get_remote.call_count,2)
                blocked=a.lookup(POINT,folder,year=2025,cancelled=lambda:True)
                self.assertEqual(blocked['status'],'disabled');self.assertEqual(client.retrieve.call_count,2)

    def test_downloads_aggregate_and_cached_result_needs_no_client(self):
        with tempfile.TemporaryDirectory() as folder:
            client=MagicMock();job=MagicMock(request_id='test-job',status='successful');client.retrieve.return_value=job
            remote=job.get_results.return_value;remote.content_length=4
            remote.download.side_effect=lambda filename:Path(filename).write_bytes(b'GRIB')
            def parse(path,point,month,year):return parts(year)[month-1]
            with patch('cams.make_client',return_value=client),patch('deposition.parse_grib',side_effect=parse):
                result=a.lookup(POINT,folder,year=2025)
            self.assertEqual(result['status'],'ready');self.assertEqual(result['completedMonths'],12)
            self.assertEqual(client.retrieve.call_count,12)
            with patch('cams.make_client',side_effect=AssertionError('Must use cache')):
                self.assertTrue(a.is_current(a.lookup(POINT,folder,year=2025),POINT,2025))

    def test_disable_default_and_no_old_category_relabelled(self):
        site=sc.create();site.update(deposition=ready(),destinationCoordinates='45.1,24.1')
        sc.recommendation(site)
        self.assertEqual(site['corrosionAssessment']['status'],'disabled')
        rows=display_rows(site);group=next(r for r in rows if r['key']=='environment.suggestedCorrosivity')
        self.assertFalse(group['expandable']);self.assertEqual(group['status'],'Disabled')
        self.assertFalse(any(r['key'].startswith('deposition.') for r in rows))
        site['corrosivityEnabled']=True;sc.recommendation(site)
        self.assertIsNotNone(site['corrosionAssessment']['category'])

    def test_seismic_country_layer_and_meanings(self):
        for code,name in [('RO','Romania'),('JP','Japan')]:
            site=sc.create();site['locationContext']={'geography':{'code':code,'name':name}}
            rows=display_rows(site);by={r['key']:r for r in rows}
            self.assertEqual(by['seismic.pga']['value'],'Not available')
            self.assertEqual(by['seismic.national']['label'],'National Design Parameters — '+name)
            self.assertEqual('seismic.ag' in by,code=='RO')
            self.assertEqual('seismic.nationalUnavailable' in by,code!='RO')
            self.assertEqual([r['key'] for r in rows if r['section'] and not r.get('parent')][-1],'section_corrosion')
            self.assertTrue(all(r.get('meaning') for r in rows if not r['section']))

if __name__=='__main__':unittest.main()
