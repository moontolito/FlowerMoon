import unittest,tempfile,json
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET
from domain import *
from excel_export import export_workbook,tag

class TransportTests(unittest.TestCase):
    def setUp(self):
        self.p=product(dict(name='Modul',length=9,width=3,height=3.3,weight=7,quantity=4))
        self.match=recommend(self.p,example_vehicles())[0]
        self.row=dict(product=self.p,vehicle=self.match['vehicle'],loaded=self.match['loaded'],quantity=4,distance_km=677,return_km=677,position_km=0,hours=12,origin=dict(name='Botoșani',lat=47.85,lon=26.75),destination=dict(name='Timișoara',lat=45.75,lon=21.24),server='https://valhalla1.openstreetmap.de',calculated_at=stamp())
        self.rates=dict(loaded=1.5,empty=1,fixed=100,markup=5,vat=0)
    def test_loaded_vehicle(self):
        self.assertTrue(self.match['fits'])
        self.assertEqual(self.match['vehicle']['id'],'example-2')
        self.assertEqual(self.match['loaded'],dict(length=18,width=3,height=4.2,weight=25,axle_load=9,axle_count=6))
    def test_no_fit(self):
        for changes in [dict(length=19,width=6),dict(weight=30)]:
            self.assertFalse(any(r['fits'] for r in recommend(dict(self.p,**changes),example_vehicles())))
    def test_validation(self):
        for bad in ('nan','inf','-1','0'):
            with self.assertRaises(ValueError):product(dict(self.p,weight=bad))
        with self.assertRaises(ValueError):product(dict(self.p,quantity=1.5))
        self.assertEqual(product(dict(self.p,width='3,2'))['width'],3.2)
        with self.assertRaises(ValueError):coordinates('91, 20')
    def test_request_and_response(self):
        req=route_request(coordinates('47.85,26.75'),coordinates('45.75,21.24'),self.match['loaded'])
        self.assertEqual(req['costing'],'truck');self.assertEqual(req['shape_format'],'geojson')
        self.assertFalse(req['costing_options']['truck']['ignore_restrictions'])
        self.assertEqual(req['costing_options']['truck']['weight'],25)
        parsed=parse_response(dict(code='Ok',routes=[dict(distance=677000,duration=43200,geometry=dict(type='LineString',coordinates=[[26.75,47.85],[21.24,45.75]]))]))
        self.assertEqual(parsed[0]['distance_km'],677);self.assertEqual(parsed[0]['hours'],12)
        with self.assertRaises(ValueError):parse_response(dict(code='NoRoute'))
    def test_costs(self):
        c=calculate(self.row,self.rates)
        self.assertEqual(c['billable_km'],5416);self.assertEqual(c['cost'],7170);self.assertEqual(c['total'],7528.5)
        c=calculate(dict(self.row,quantity=1,distance_km=1.005,return_km=0),dict(self.rates,loaded=1,fixed=0,markup=100))
        self.assertEqual(c['cost'],1.01);self.assertEqual(c['total'],2.02)
    def test_state_and_export(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d);state=State(path/'state.json');state.data['deliveries']=[self.row];state.save()
            self.assertEqual(State(path/'state.json').data['deliveries'][0]['loaded']['weight'],25)
            target=path/'result.xlsx';export_workbook(target,[self.row],self.rates)
            with ZipFile(target) as z:
                calc=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
                def cell(ref):return calc.find('.//'+tag('c')+f'[@r="{ref}"]')
                self.assertIsNotNone(cell('L13').find(tag('f')))
                self.assertEqual(float(cell('L13').find(tag('v')).text),7528.5)
                self.assertEqual(float(cell('C13').find(tag('v')).text),677)
            export_workbook(target,[self.row],dict(self.rates,loaded=0))
            with ZipFile(target) as z:self.assertIn('Tarif lipsă',z.read('xl/worksheets/sheet1.xml').decode())

if __name__=='__main__':unittest.main()
