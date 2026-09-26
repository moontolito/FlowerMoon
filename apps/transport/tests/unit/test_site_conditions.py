import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import site_conditions as sc
import site_sources
from domain import State,parse_response

class SiteTests(unittest.TestCase):
    def test_ferry_evidence_is_retained(self):
        route={'distance':1000,'duration':60,'geometry':{'type':'LineString','coordinates':[[1,2],[3,4]]},'legs':[{'steps':[{'mode':'ferry'}]}]}
        self.assertTrue(parse_response({'code':'Ok','routes':[route]})[0]['ferryDetected'])
        route['legs']=[]
        self.assertFalse(parse_response({'code':'Ok','routes':[route]})[0]['ferryDetected'])
    def test_defaults_and_legacy_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'planning.json';state=State(p);state.data.pop('siteConditions');state.save()
            state=State(p);site=state.data['siteConditions']
            self.assertIsNone(sc.get(site,'temperature.minDesign')['value'])
            sc.apply_manual(site,{'seismic.ag':'0.25','humidity.value2':'26'})
            state.save();loaded=State(p).data['siteConditions']
            self.assertEqual(sc.get(loaded,'seismic.ag')['value'],.25)
            self.assertTrue(sc.get(loaded,'seismic.ag')['manualOverride'])
            self.assertEqual(sc.get(loaded,'humidity.value2')['status'],'MANUAL')
    def test_location_preserves_manual_and_clears_automatic(self):
        site=sc.create();sc.sync(site,'A','B','1,2','3,4')
        sc.apply_manual(site,{'wind.qb':'.4','temperature.maxDesign':'48'})
        sc.automatic(site,'transport.distanceKm',250,'route','CALCULATED')
        sc.automatic(site,'environment.marineEnvironment','Possible','coast','VERIFY')
        sc.sync(site,'A','C','1,2','5,6')
        self.assertEqual(sc.get(site,'wind.qb')['value'],.4)
        self.assertTrue(sc.get(site,'wind.qb')['reviewRequired'])
        self.assertTrue(sc.get(site,'temperature.maxDesign')['reviewRequired'])
        self.assertIsNone(sc.get(site,'transport.distanceKm')['value'])
        self.assertEqual(sc.get(site,'environment.marineEnvironment')['value'],'Unknown')
        sc.automatic(site,'wind.qb',.7,'provider');self.assertEqual(sc.get(site,'wind.qb')['value'],.4)
        sc.apply_manual(site,{'wind.qb':'.4'},['wind.qb']);self.assertFalse(sc.get(site,'wind.qb')['reviewRequired'])
    def test_atomic_validation(self):
        site=sc.create();before=json.dumps(site)
        for bad in [{'wind.qb':'nan'},{'seismic.ag':'-1'},{'humidity.value1':'101'},{'temperature.minDesign':'60','temperature.maxDesign':'40'},{'transport.distanceKm':'inf'},{'environment.exteriorCorrosivity':'C6'}]:
            with self.assertRaises(ValueError):sc.apply_manual(site,bad)
            self.assertEqual(json.dumps(site),before)
    def test_no_corrosion_assignment_from_maritime_or_coast(self):
        site=sc.create();sc.apply_manual(site,{'transport.maritimeTransport':'Yes','environment.marineEnvironment':'Yes'})
        sc.recommendation(site)
        self.assertEqual(sc.get(site,'environment.exteriorCorrosivity')['value'],'Manual / Unknown')
        self.assertIsNone(sc.get(site,'environment.suggestedCorrosivity')['value'])
        self.assertEqual(sc.get(site,'environment.suggestedCorrosivity')['status'],'VERIFY')
        self.assertIsNone(sc.get(site,'transport.suggestedProtection')['value'])
    def test_sources_failure_null_and_coast_absence(self):
        with patch('elevation.samples',return_value={'values':[None],'complete':False}):
            result=site_sources.lookup('https://example.test',{'lat':1,'lon':2})
            self.assertIsNone(result['altitude'][0]);self.assertTrue(all(v['value'] is None for v in result['zoning'].values()))
            self.assertNotIn('marine',result);self.assertEqual(result['coastalDistance']['status'],'estimated')
    def test_route_samples_and_destination_fallback(self):
        shape={'coordinates':[[2,1],[2.001,1.001]]}
        with patch('elevation.samples',return_value={'values':[20,642,1100],'complete':True}):
            result=site_sources.lookup('https://example.test',{'lat':2,'lon':3},shape)
            self.assertEqual(result['altitude'][0],1100);self.assertEqual(result['altitudeStatus'],'VERIFY')
            self.assertEqual(result['siteAltitude'],20);self.assertNotIn('marine',result)
        with patch('elevation.samples',return_value={'values':[20,642,None],'complete':False}):
            result=site_sources.lookup('https://example.test',{'lat':2,'lon':3},shape)
            self.assertIsNone(result['altitude'][0]);self.assertEqual(result['siteAltitude'],20)
        with patch('elevation.samples',return_value={'values':[20],'complete':True}):
            result=site_sources.lookup('https://example.test',{'lat':2,'lon':3})
            self.assertEqual(result['altitude'][0],20)

if __name__=='__main__':unittest.main()
