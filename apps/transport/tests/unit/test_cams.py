import calendar,json,os,shutil,tempfile,unittest,zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch,MagicMock
import numpy as np
from netCDF4 import Dataset,date2num
import cams,ads_credentials,site_conditions as sc
from site_overview import rows

POINT=dict(lat=44.18,lon=28.63)

def fixture(path,year=2025,months=12,units='kg kg**-1',level=60):
    with Dataset(path,'w',format='NETCDF4') as ds:
        for name,size in [('valid_time',months),('model_level',1),('latitude',3),('longitude',3)]:ds.createDimension(name,size)
        ds.createVariable('latitude','f8',('latitude',))[:]=[45,44.25,43.5]
        ds.createVariable('longitude','f8',('longitude',))[:]=[27.75,28.5,29.25]
        ds.createVariable('model_level','i4',('model_level',))[:]=[level]
        t=ds.createVariable('valid_time','f8',('valid_time',));t.units='hours since 2000-01-01';t.calendar='standard'
        t[:]=date2num([datetime(year,m,1) for m in range(1,months+1)],t.units)
        for key,values in [('so2',np.arange(1,months+1)),('aermr01',np.ones(months)),('aermr02',np.ones(months)*2),('aermr03',np.ones(months)*3)]:
            v=ds.createVariable(key,'f8',('valid_time','model_level','latitude','longitude'),fill_value=-9999);v.units=units
            v[:]=np.broadcast_to(values[:,None,None,None]*1e-9,(months,1,3,3))
    return path

class CamsTests(unittest.TestCase):
    def test_global_requests_and_dateline(self):
        for lat,lon in [(44.18,28.63),(35.6,139.7),(-33.9,151.2),(-33.9,18.4),(89.9,179.9),(-90,-180)]:
            r=cams.request_for(dict(lat=lat,lon=lon));n,w,s,e=r['area']
            self.assertTrue(-90<=s<=n<=90 and -180<=w<=e<=180)
            self.assertEqual(r['model_level'],['60']);self.assertEqual(len(r['variable']),4)
        self.assertEqual(cams.request_for(dict(lat=0,lon=180)),cams.request_for(dict(lat=0,lon=-180)))
        with self.assertRaises(ValueError):cams.request_for(dict(lat=float('nan'),lon=0))

    def test_units_month_weights_salt_bins_and_grid(self):
        with tempfile.TemporaryDirectory() as d:
            r=cams.parse_download(fixture(Path(d)/'values.nc'),POINT)
        expected=sum(m*calendar.monthrange(2025,m)[1] for m in range(1,13))/365
        self.assertAlmostEqual(r['so2']['mean'],expected)
        self.assertEqual(r['so2']['minimumMonthlyMean'],1)
        self.assertAlmostEqual(r['seaSalt']['mean'],6)
        self.assertAlmostEqual(r['seaSaltDry']['mean'],6/4.3)
        self.assertEqual((r['gridLatitude'],r['gridLongitude']),(44.25,28.5))
        self.assertEqual(len(r['so2']['monthly']),12)

    def test_rejects_incomplete_wrong_units_levels_and_masked_values(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'values.nc'
            for options in [dict(months=11),dict(units='kg m-3'),dict(level=59)]:
                fixture(p,**options)
                with self.assertRaises(ValueError):cams.parse_download(p,POINT)
            fixture(p)
            with Dataset(p,'a') as ds:ds['so2'][0,0,1,1]=-9999
            with self.assertRaises(ValueError):cams.parse_download(p,POINT)
            fixture(p)
            with self.assertRaises(ValueError):cams.parse_download(p,dict(lat=0,lon=0))

    def test_zip_input_and_leap_year(self):
        with tempfile.TemporaryDirectory() as d:
            nc=fixture(Path(d)/'values.nc',year=2024);z=Path(d)/'download.zip'
            with zipfile.ZipFile(z,'w') as archive:archive.write(nc,'nested/data.nc')
            r=cams.parse_download(z,POINT,2024)
            self.assertAlmostEqual(r['so2']['mean'],sum(m*calendar.monthrange(2024,m)[1] for m in range(1,13))/366)

    def test_persistent_job_resume_cache_and_no_secret_in_results(self):
        with tempfile.TemporaryDirectory() as d:
            p=fixture(Path(d)/'fixture.nc');cache=Path(d)/'cache'
            client=MagicMock();job=MagicMock();job.request_id='test-job';job.status='accepted'
            client.retrieve.return_value=job;client.client.get_remote.return_value=job
            with patch('cams.make_client',return_value=client):
                a=cams.lookup(POINT,cache);self.assertEqual(a['status'],'queued')
                job.status='successful';assets=job.get_results.return_value;assets.content_length=p.stat().st_size
                assets.download.side_effect=lambda target:shutil.copy2(p,target)
                b=cams.lookup(POINT,cache);self.assertEqual(b['status'],'ready')
                c=cams.lookup(dict(lat=44.2,lon=28.6),cache)
            self.assertEqual(client.retrieve.call_count,1)
            self.assertEqual(c['requestedCoordinates'],dict(lat=44.2,lon=28.6))
            self.assertEqual(c['so2'],b['so2']);self.assertGreater(c['gridDistanceKm'],0)
            self.assertNotIn('key',json.dumps(b).lower())

    def test_failures_are_redacted_and_licence_is_actionable(self):
        error=Exception('403 required licences not accepted; secret-test-token')
        safe=cams.safe_error(error);self.assertEqual(safe.code,'licence');self.assertNotIn('secret-test-token',str(safe))
        with tempfile.TemporaryDirectory() as d,patch('cams.make_client',side_effect=error):
            with self.assertRaises(cams.CamsError) as result:cams.lookup(POINT,d)
            self.assertNotIn('secret-test-token',str(result.exception))
            self.assertEqual(list(Path(d).iterdir()),[])

    def test_overview_and_destination_invalidation(self):
        site=sc.create();sc.sync(site,'A','Constanta','1,2','44.18,28.63')
        with tempfile.TemporaryDirectory() as d:r=cams.parse_download(fixture(Path(d)/'values.nc'),POINT)
        r.update(cams.base_result(cams.request_for(POINT)));r['status']='ready'
        site['airQuality']=cams.for_point(r,POINT)
        data={x['key']:x for x in rows(site)}
        self.assertIn('µg/kg',data['airQuality.so2']['value']);self.assertEqual(data['airQuality.so2']['source'],cams.SOURCE)
        self.assertIn('44.25',data['airQuality.so2']['detail']);self.assertIn('2025',data['airQuality.so2']['reference'])
        self.assertIn('/ 4.3',data['airQuality.seaSaltDry']['detail'])
        sc.sync(site,'A','Tokyo','1,2','35.6,139.7');self.assertEqual(site['airQuality']['status'],'pending')
        self.assertNotIn('so2',site['airQuality'])

    @unittest.skipUnless(os.name=='nt','Windows DPAPI')
    def test_windows_credential_is_encrypted_and_round_trips(self):
        with tempfile.TemporaryDirectory() as d,patch('ads_credentials.secret_path',return_value=Path(d)/'ads.json'),patch.dict(os.environ,{'FLOWERMOON_ADS_KEY':''}):
            ads_credentials.save_key('fixture-key-not-a-real-token')
            self.assertNotIn('fixture-key-not-a-real-token',(Path(d)/'ads.json').read_text())
            self.assertEqual(ads_credentials.configuration()[1],'fixture-key-not-a-real-token')

if __name__=='__main__':unittest.main()
