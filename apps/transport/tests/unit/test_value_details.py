import unittest
from copy import deepcopy
import site_conditions as sc
import annual_corrosion as corrosion
from test_annual import ready, POINT
from site_overview import rows, display_rows
from value_details import build, plain_text, safe_url


class ValueDetailsTests(unittest.TestCase):
    def setUp(self):
        self.site=sc.create();self.site['corrosivityEnabled']=True;self.site['locationContext']={'geography':{'code':'RO','name':'Romania'}}
        self.site.update(destinationAddress='QA destination',destinationCoordinates='45.1,24.1')

    def test_every_value_has_details_without_mutation(self):
        before=deepcopy(self.site)
        for row in rows(self.site):
            doc=build(self.site,row['key'])
            if row['section']:self.assertIsNotNone(doc)
            else:
                displayed=next((r for r in display_rows(self.site) if r['key']==row['key']),row)
                self.assertEqual(doc['value'],displayed['value'])
                self.assertIn('QA destination',plain_text(doc))
        self.assertEqual(before,self.site)

    def test_manual_value_never_gets_model_origin(self):
        self.site['environment']['suggestedCorrosivity'].update(value='C4',manualOverride=True,source='Manual entry')
        self.site['environment']['suggestedCorrosivity']['reviewRequired']=True
        doc=build(self.site,'environment.suggestedCorrosivity');text=plain_text(doc)
        self.assertIn('Manual value',text);self.assertIn('REVIEW REQUIRED',text)
        self.assertNotIn('r =',text);self.assertEqual(doc['links'],[])

    def test_temperature_manual_and_mixed(self):
        sc.apply_manual(self.site,{'temperature.maxDesign':'40'})
        text=plain_text(build(self.site,'design'))
        self.assertIn('manual entry',text);self.assertIn('only to automatic',text)
        sc.apply_manual(self.site,{'temperature.minDesign':'-20'})
        text=plain_text(build(self.site,'design'))
        self.assertIn('Manual value',text);self.assertNotIn('temperature_2m_max',text)

    def test_numerical_corrosion_chain_and_audit(self):
        self.site['deposition']=ready();self.site['corrosionAssessment']=corrosion.evaluate(self.site['deposition'],POINT)
        text=plain_text(build(self.site,'environment.suggestedCorrosivity'))
        self.assertIn('T = 10 °C',text);self.assertIn('SO₂ term = 1.77',text)
        self.assertIn('Stored category: '+self.site['corrosionAssessment']['category'],text)
        self.assertIn('0.55',text);self.assertIn('/ 4.3',text);self.assertIn('ISO 9223:2012',text)
        self.assertIn('not a validated equivalence',text);self.assertIn('Calibration check',text)
        self.assertIn('https://ads.atmosphere.copernicus.eu/',text)
        self.assertNotIn("'temperature':",text)

    def test_pending_does_not_invent_calculation(self):
        self.site['deposition']={'status':'queued','completedMonths':2}
        text=plain_text(build(self.site,'corrosion.rate'))
        self.assertIn('Calculation status',text);self.assertNotIn('Calculation for this destination',text)
        self.assertIn('Not available °C',text)

    def test_links_and_request_secrets(self):
        for value in ('javascript:alert(1)','file:///x','https://user:secret@example.org/','https://example.org/?apikey=secret','https://[bad'):
            self.assertFalse(safe_url(value))
        self.assertEqual(safe_url('https://example.org/docs'),'https://example.org/docs')
        self.site['climate']={'requestParameters':{'apikey':'SECRET_QA'},'rawSha256':'audit-hash','retrievedAt':'2026-09-27'}
        text=plain_text(build(self.site,'design'))
        self.assertIn('audit-hash',text);self.assertNotIn('SECRET_QA',text)

    def test_corrosion_extrapolation_is_visible(self):
        self.site['deposition']=ready();self.site['deposition']['means']['temperature']=35
        for part in self.site['deposition']['monthly']:part['means']['temperature']=35
        self.site['corrosionAssessment']=corrosion.evaluate(self.site['deposition'],POINT)
        self.assertIn('OUTSIDE / EXTRAPOLATED',plain_text(build(self.site,'corrosion.rate')))

    def test_missing_source_is_explicit(self):
        doc=build(self.site,'timeOfWetness')
        self.assertEqual(doc['links'],[]);self.assertIn('Not available',plain_text(doc))

if __name__=='__main__':unittest.main()
