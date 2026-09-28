import calendar,json,math,tempfile,unittest
from datetime import date,timedelta
from pathlib import Path
from unittest.mock import patch,MagicMock
import deposition as d,corrosion as c

POINT=dict(lat=45.1,lon=24.1)

def records(month=1):
    keys={(int((date(2025,month,1)+timedelta(days=i)).strftime('%Y%m%d')),h) for i in range(calendar.monthrange(2025,month)[1]) for h in range(3,25,3)}
    values={p:{k:1e-10 for k in keys} for p in d.FLUX_IDS}
    for p,v in [(167,283.15),(168,278.15),(134,100000),(210122,5e-9)]:values[p]={k:v for k in keys}
    return values,keys

def ready(point=POINT):
    start,end=d.period()
    keys={(int((start+timedelta(days=i)).strftime('%Y%m%d')),h) for i in range(30) for h in range(3,25,3)}
    values={p:{k:1e-10 for k in keys} for p in d.FLUX_IDS}
    for p,v in [(167,283.15),(168,278.15),(134,100000),(210122,5e-9)]:values[p]={k:v for k in keys}
    part=d.summarize_records(values,keys,(45.2,24.0),None);d.complete_means(part['means'])
    part['sampleCount']=part.pop('count');part.pop('month')
    result=dict(d.base(point),status='ready',**part)
    return result

def grib_fixture(path,month=2,omit=False,bad_unit=False):
    import eccodes as ec
    samples,keys=records(month)
    template=ec.codes_grib_new_from_samples('regular_ll_sfc_grib2')
    try:
        for name,val in [('centre','ecmf'),('Ni',1),('Nj',1),('latitudeOfFirstGridPointInDegrees',45.2),('longitudeOfFirstGridPointInDegrees',24),('latitudeOfLastGridPointInDegrees',45.2),('longitudeOfLastGridPointInDegrees',24)]:ec.codes_set(template,name,val)
        with Path(path).open('wb') as stream:
            for param in d.PARAM_IDS:
                if omit and param==215004:continue
                for day,hour in sorted(keys):
                    g=ec.codes_clone(template)
                    try:
                        ec.codes_set(g,'paramId',param)
                        if param==210122:ec.codes_set(g,'typeOfLevel','hybrid');ec.codes_set(g,'level',137)
                        for name,val in [('dataDate',day),('dataTime',0),('stepUnits',1),('forecastTime',hour)]:ec.codes_set(g,name,val)
                        ec.codes_set_values(g,[samples[param][(day,hour)]]);ec.codes_write(g,stream)
                    finally:ec.codes_release(g)
    finally:ec.codes_release(template)
    return path

class DepositionTests(unittest.TestCase):
    def test_global_grid_and_request_coverage(self):
        for lat,lon in [(45.1,24.1),(-33.9,151.2),(35.6,139.7),(-90,180),(90,-180),(0,179.99)]:
            r=d.request_for(dict(lat=lat,lon=lon),2)
            self.assertEqual(r['date'],'2025-02-01/2025-02-28');self.assertEqual(len(r['variable']),16)
            self.assertEqual(r['leadtime_hour'],['3','6','9','12','15','18','21','24'])
            n,w,s,e=r['area'];self.assertEqual(n,s);self.assertEqual(w,e)
            self.assertTrue(-90<=n<=90 and -180<=w<180)
        self.assertEqual(d.identity(dict(lat=0,lon=180)),d.identity(dict(lat=0,lon=-180)))
        with self.assertRaises(ValueError):d.request_for(dict(lat=float('nan'),lon=0),1)

    def test_unit_conversion_and_separate_components(self):
        r=ready();m=r['means']
        self.assertAlmostEqual(m['dry'],3e-10*86400*1e6/4.3)
        self.assertAlmostEqual(m['total'],m['dry']*4)
        self.assertAlmostEqual(m['wet'],m['dry']*2)
        self.assertAlmostEqual(m['chlorideDryProxy'],m['dry']*2*.55)
        self.assertAlmostEqual(m['chlorideTotalProxy'],m['total']*.55)
        self.assertAlmostEqual(m['temperature'],10)
        self.assertTrue(70<m['humidity']<72)
        self.assertTrue(6<m['so2Volume']<6.2)
        self.assertEqual(r['sampleCount'],240)

    def test_incomplete_series_and_annual_period_rejected(self):
        r,k=records();r[215004].pop(next(iter(k)))
        with self.assertRaises(ValueError):d.summarize_records(r,k,(45.2,24),1)
        parts=[d.summarize_records(*records(m),(45.2,24),m) for m in range(1,13)]
        with self.assertRaises(ValueError):d.aggregate(parts[:-1])
        parts[-1]['count']=1
        with self.assertRaises(ValueError):d.aggregate(parts)

    def test_nonfinite_and_negative_source_values_rejected(self):
        for value in [-1,float('nan'),float('inf')]:
            r,k=records();r[215004][next(iter(k))]=value
            with self.assertRaises(ValueError):d.summarize_records(r,k,(45.2,24),1)

    def test_grib_real_reader_and_missing_variable(self):
        with tempfile.TemporaryDirectory() as temp:
            p=grib_fixture(Path(temp)/'valid.grib')
            r=d.parse_grib(p,POINT,2)
            self.assertEqual(r['count'],224);self.assertAlmostEqual(r['means']['temperature'],10,places=4)
            with self.assertRaises(ValueError):d.parse_grib(p,dict(lat=0,lon=0),2)
            with self.assertRaises(ValueError):d.parse_grib(p,POINT,1)
            missing=grib_fixture(Path(temp)/'missing.grib',omit=True)
            with self.assertRaises(ValueError):d.parse_grib(missing,POINT,2)

    def test_resumable_jobs_are_bounded(self):
        job=MagicMock(status='accepted',request_id='safe-job');client=MagicMock()
        client.retrieve.return_value=job;client.client.get_remote.return_value=job
        with tempfile.TemporaryDirectory() as temp,patch('cams.make_client',return_value=client):
            r=d.lookup(POINT,temp);self.assertEqual(r['windowDays'],30)
            self.assertEqual(client.retrieve.call_count,1)
            d.lookup(POINT,temp);self.assertEqual(client.retrieve.call_count,1)
            self.assertEqual(client.client.get_remote.call_count,1)

    def test_failure_never_becomes_zero(self):
        with tempfile.TemporaryDirectory() as temp,patch('cams.make_client',side_effect=RuntimeError('private server detail')):
            r=d.lookup(POINT,temp)
            self.assertEqual(r['status'],'unavailable');self.assertNotIn('means',r);self.assertNotIn('private',r['message'])

class CorrosionTests(unittest.TestCase):
    def test_iso_boundaries_and_above_cx(self):
        for label,edge in c.THRESHOLDS:self.assertEqual(c.category(edge),label)
        for value,label in [(0,'C1'),(1.30001,'C2'),(25.001,'C3'),(50.001,'C4'),(80.001,'C5'),(200.001,'CX'),(700.001,None)]:self.assertEqual(c.category(value),label)
        for value in [float('nan'),float('inf'),-1,True]:
            with self.assertRaises(ValueError):c.category(value)

    def test_equation_temperature_branch_and_monotonic_pollution(self):
        # At T=10, RH=0 and Pd=Sd=1 the equation reduces to two terms.
        self.assertAlmostEqual(c.steel_rate(10,0,1,1),1.77+.102*math.exp(.4))
        self.assertGreater(c.steel_rate(10,80,10,20),c.steel_rate(10,80,5,10))
        self.assertAlmostEqual(c.steel_rate(10.000001,70,5,10),c.steel_rate(9.999999,70,5,10),places=4)
        with self.assertRaises(ValueError):c.steel_rate(10,101,1,1)

    def test_screening_provenance_and_explicit_extrapolation(self):
        r=ready();a=c.evaluate(r,POINT)
        self.assertEqual(a['status'],'ready');self.assertIsNotNone(a['category'])
        self.assertIn('not an ISO-conforming',a['assumptions'])
        self.assertGreaterEqual(a['wetScenarioRate'],a['rate'])
        r['means']['chlorideDryProxy']=0
        a=c.evaluate(r,POINT);self.assertTrue(a['extrapolated']);self.assertIn('chlorideDryProxy',a['outsideCalibration'])
        self.assertIsNone(c.evaluate(r,dict(lat=0,lon=0))['category'])
        r['sampleCount']=2900;self.assertIsNone(c.evaluate(r,POINT)['category'])

    def test_reset_and_final_class_preservation(self):
        import site_conditions as sc
        site=sc.create();sc.sync(site,'A','B','0,0','45.1,24.1')
        site['deposition']=ready();sc.recommendation(site)
        self.assertIsNone(sc.get(site,'environment.suggestedCorrosivity')['value'])
        self.assertEqual(sc.get(site,'environment.exteriorCorrosivity')['value'],'Manual / Unknown')
        sc.sync(site,'A','C','0,0','35,139');sc.recommendation(site)
        self.assertEqual(site['deposition']['status'],'pending');self.assertIsNone(sc.get(site,'environment.suggestedCorrosivity')['value'])

if __name__=='__main__':unittest.main()
