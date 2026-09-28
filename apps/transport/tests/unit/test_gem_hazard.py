import json,unittest,tempfile,struct,math
from pathlib import Path
from unittest.mock import patch
import gem_hazard as g
import site_conditions as sc
from site_overview import display_rows
from value_details import build,plain_text

BUCHAREST=dict(lat=44.4268,lon=26.1025)

class GemHazardTests(unittest.TestCase):
    def test_display_band_boundaries_use_unrounded_value(self):
        self.assertEqual(g.pga_level(0),'Very low')
        for i,(boundary,_) in enumerate(g.PALETTE[:-1]):
            with self.subTest(boundary=boundary):
                below=math.nextafter(boundary,0)
                self.assertEqual(g.pga_level(below),g.PGA_LEVELS[i])
                self.assertEqual(g.pga_level(boundary),g.PGA_LEVELS[i+1])
                self.assertEqual(g.pga_level(float(g.format_pga(below))),g.PGA_LEVELS[i])
        self.assertEqual(g.pga_level(2),'Very exceptional')
        for invalid in (None,-1,float('nan'),float('inf'),True,'0.3'):
            self.assertIsNone(g.pga_level(invalid))

    def test_real_bucharest_cell_and_provenance(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('No network permitted')):
            r=g.lookup(BUCHAREST)
        self.assertEqual(r['status'],'ready')
        self.assertAlmostEqual(r['value'],0.3229623135362622,12)
        self.assertEqual((r['row'],r['column']),(911,4122))
        self.assertEqual(r['unit'],'g');self.assertEqual(r['returnPeriodYears'],475)
        self.assertEqual(len(r['sha256']),64)
        self.assertIn('Vs30',r['referenceGround'])

    def test_global_continents(self):
        for lat,lon in [(51.5074,-.1278),(35.6762,139.6503),(40.7128,-74.006),(-33.9249,18.4241),(-33.8688,151.2093),(-23.55,-46.63)]:
            with self.subTest(point=(lat,lon)):
                r=g.lookup(dict(lat=lat,lon=lon));self.assertEqual(r['status'],'ready');self.assertGreaterEqual(r['value'],0)

    def test_nodata_outside_and_invalid(self):
        for point,status in [(dict(lat=0,lon=-140),'no_data'),(dict(lat=-90,lon=0),'outside_coverage'),(dict(lat=91,lon=0),'unavailable'),(dict(lat=float('nan'),lon=0),'unavailable')]:
            r=g.lookup(point);self.assertEqual(r['status'],status);self.assertIsNone(r['value'])

    def test_missing_file_is_not_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            r=g.lookup(BUCHAREST,folder)
        self.assertEqual(r['status'],'unavailable');self.assertIsNone(r['value'])

    def test_checksum_is_checked(self):
        path=g.DATA/g.FILENAME;s=path.stat()
        with self.assertRaisesRegex(ValueError,'checksum'):
            g._metadata(str(path),s.st_mtime_ns,s.st_size,json.dumps(dict(sha256='wrong')))

    def test_containing_cell_and_true_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'samples';p.write_bytes(struct.pack('<4d',0,.2,.3,1.7976931348623157e308))
            m=dict(west=0,north=2,sx=1,sy=1,width=2,height=2,offset=0,nodata=1.7976931348623157e308,sha256='test')
            with patch.object(g,'metadata',return_value=(p,m)):
                a=g.lookup(dict(lat=1.9,lon=.1));b=g.lookup(dict(lat=1.01,lon=.99))
                self.assertEqual(a['value'],0);self.assertEqual(b['value'],0)
                self.assertEqual(a['status'],'ready')
                self.assertEqual(g.lookup(dict(lat=1.5,lon=1))['value'],.2)
                self.assertEqual(g.lookup(dict(lat=.5,lon=1.5))['status'],'no_data')
                self.assertEqual(g.lookup(dict(lat=0,lon=.1))['status'],'outside_coverage')

    def test_dateline_equivalence(self):
        a=g.lookup(dict(lat=0,lon=180));b=g.lookup(dict(lat=0,lon=-180))
        self.assertEqual(a['value'],b['value']);self.assertEqual(a['column'],b['column'])

    def test_destination_change_and_national_values(self):
        site=sc.create();site['destinationCoordinates']='44.4268,26.1025';site['seismicHazard']=g.lookup(BUCHAREST)
        before=json.dumps(site['seismic'],sort_keys=True)
        rows={r['key']:r for r in display_rows(site)}
        self.assertEqual(rows['seismic.pga']['value'],'0.323 g')
        self.assertEqual(rows['seismic.interpretation']['value'],'Very high')
        self.assertNotIn('seismic.hazardReference',rows)
        self.assertEqual(rows['seismic.pga']['meaning'],g.PGA_MEANING)
        text=plain_text(build(site,'seismic.pga'))
        self.assertIn('SHA-256',text);self.assertIn('475',text);self.assertIn('CC BY-NC-SA',text)
        self.assertEqual(json.dumps(site['seismic'],sort_keys=True),before)
        site['destinationCoordinates']='51.5,-0.1'
        self.assertEqual(next(r for r in display_rows(site) if r['key']=='seismic.pga')['value'],'Not available')
        self.assertEqual(next(r for r in display_rows(site) if r['key']=='seismic.interpretation')['value'],'Not available')
        sc.sync(site,'A','B','0,0','35,139');self.assertNotIn('seismicHazard',site)

    def test_overlay_uses_same_cell_and_nodata_transparency(self):
        from map_widget import project
        from PIL import Image
        x,y=project(BUCHAREST['lat'],BUCHAREST['lon'],10)
        im=g.overlay(10,x-.5,y-.5,1,1)
        self.assertEqual(im.getpixel((0,0)),(255,250,20,110))
        x,y=project(0,-140,10)
        self.assertEqual(g.overlay(10,x-.5,y-.5,1,1).getpixel((0,0))[3],0)

if __name__=='__main__':unittest.main()
