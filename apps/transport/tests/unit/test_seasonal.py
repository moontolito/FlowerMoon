import unittest,json,tempfile,shutil
from pathlib import Path
from datetime import date,timedelta
from unittest.mock import patch,MagicMock
import deposition as d,corrosion as c
from test_deposition import ready,POINT,records

class SeasonalTests(unittest.TestCase):
    def test_window_across_year_and_leap_month(self):
        for today,start,end in [(date(2026,1,5),'2025-12-06','2026-01-04'),(date(2024,3,1),'2024-01-31','2024-02-29'),(date(2026,9,27),'2026-08-28','2026-09-26')]:
            self.assertEqual(d.request_for(POINT,today=today)['date'],start+'/'+end)
        self.assertNotEqual(d.identity(POINT,date(2026,9,27)),d.identity(POINT,date(2026,9,28)))
        self.assertEqual(d.base(POINT)['expectedSamples'],240)

    def test_negative_wet_values_are_preserved_and_not_used_in_scenario(self):
        values,keys=records();first=next(iter(keys));original=values[215010][first]
        values[215010][first]=-1e-14
        part=d.summarize_records(values,keys,(45.2,24),1)
        expected=(3e-10-(original+1e-14)/len(keys))*1e6*86400/4.3
        self.assertAlmostEqual(part['means']['wetLargeScale'],expected)
        self.assertEqual(part['negativeWetSamples']['215010']['minimum'],-1e-14)
        self.assertFalse(part['wetScenarioUsable'])
        result=ready();result['qualityFlags']=part['qualityFlags'];result['wetScenarioUsable']=False
        estimate=c.evaluate(result,POINT)
        self.assertEqual(estimate['status'],'ready');self.assertIsNone(estimate['wetScenarioRate'])
        self.assertIn('need verification',estimate['wetScenarioReason'])

    def test_annual_and_partial_results_cannot_be_relabelled_seasonal(self):
        result=ready()
        self.assertTrue(c.evaluate(result,POINT)['seasonal'])
        result['periodStart']='2025-01-01';result['periodEnd']='2025-12-31'
        self.assertEqual(c.evaluate(result,POINT)['status'],'unavailable')
        result=ready();result['sampleCount']=239
        self.assertEqual(c.evaluate(result,POINT)['status'],'unavailable')

    def test_cached_period_reused_for_same_grid_without_network(self):
        with tempfile.TemporaryDirectory() as folder:
            result=ready();result['requestParameters']=d.request_for(POINT)
            cache=Path(folder)/d.identity(POINT);cache.mkdir()
            (cache/'period.json').write_text(json.dumps(result))
            neighbor=dict(lat=45.12,lon=24.08)
            with patch('cams.make_client',side_effect=AssertionError('No API call allowed')):
                restored=d.lookup(neighbor,folder,force=True)
            self.assertEqual(restored['status'],'ready');self.assertEqual(restored['requestedCoordinates'],neighbor)
            self.assertIn('gridDistanceKm',restored)

    def test_next_day_uses_new_request_not_yesterday_result(self):
        result=ready();start,end=d.period()
        self.assertTrue(d.is_current(result,POINT))
        self.assertFalse(d.is_current(result,POINT,today=end+timedelta(days=2)))

    def test_legacy_annual_jobs_not_resumed_or_deleted(self):
        with tempfile.TemporaryDirectory() as folder:
            old=Path(folder)/'annual-old';old.mkdir();record=old/'01-job.json';record.write_text('{"requestId":"old-year"}')
            client=MagicMock();client.retrieve.return_value=MagicMock(request_id='new-30-day',status='accepted')
            with patch('cams.make_client',return_value=client):result=d.lookup(POINT,folder)
            client.retrieve.assert_called_once();client.client.get_remote.assert_not_called()
            self.assertEqual(record.read_text(),'{"requestId":"old-year"}')
            self.assertEqual(result['windowDays'],30)

if __name__=='__main__':unittest.main()
