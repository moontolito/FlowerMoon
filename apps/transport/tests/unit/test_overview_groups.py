import unittest
from copy import deepcopy
import site_conditions as sc
import annual_corrosion as corrosion
from test_annual import ready, POINT
from site_overview import rows, display_rows, CORROSIVITY_GROUP, CORROSIVITY_INPUTS, SUPPLEMENTARY_DEPOSITION


class OverviewGroupsTests(unittest.TestCase):
    def setUp(self):
        self.site=sc.create();self.site['corrosivityEnabled']=True;self.site['locationContext']={'geography':{'code':'RO','name':'Romania'}}
        self.site.update(destinationAddress='QA destination',destinationCoordinates='45.1,24.1')

    def test_group_contains_the_complete_chain_once(self):
        self.site['deposition']=ready()
        self.site['corrosionAssessment']=corrosion.evaluate(self.site['deposition'],POINT)
        before=deepcopy(self.site);items=display_rows(self.site)
        by_key={row['key']:row for row in items}
        self.assertEqual(len(items),len(by_key))
        self.assertTrue(by_key[CORROSIVITY_GROUP]['expandable'])
        self.assertIn('annual estimate',by_key[CORROSIVITY_GROUP]['value'])
        for key in (*CORROSIVITY_INPUTS,*SUPPLEMENTARY_DEPOSITION):
            self.assertEqual(by_key[key]['parent'],CORROSIVITY_GROUP)
        self.assertIn('sensitivity scenario',by_key['section_corrosion_supplementary']['label'])
        self.assertNotIn('section_deposition',by_key)
        self.assertNotIn('corrosion.basis',by_key)
        self.assertEqual(before,self.site)

    def test_hide_empty_manual_fields_not_automated_failures(self):
        items={r['key']:r for r in display_rows(self.site)}
        for key in ('environment.exteriorCorrosivity','environment.interiorCorrosivity','transport.suggestedProtection',
                    'timeOfWetness','corrosionIndex','transport.maxAltitudeM','environment.marineEnvironment'):
            self.assertNotIn(key,items)
        for key in ('snow.sk','wind.qb','design','humidity.summary',CORROSIVITY_GROUP):
            self.assertIn(key,items)
        # Archival details remain accessible and no saved data is discarded.
        self.assertIn('timeOfWetness',{r['key'] for r in rows(self.site)})

    def test_retained_values_and_route_elevation_stay_visible(self):
        sc.apply_manual(self.site,{'environment.exteriorCorrosivity':'C4','environment.interiorCorrosivity':'C2','transport.maxAltitudeM':'800'})
        items={r['key']:r for r in display_rows(self.site)}
        self.assertEqual(items['environment.exteriorCorrosivity']['value'],'C4')
        self.assertEqual(items['environment.interiorCorrosivity']['value'],'C2')
        self.assertIn('transport.maxAltitudeM',items)
        self.site['routeLookup']={'status':'ready'}
        self.assertIn('transport.maxAltitudeM',{r['key'] for r in display_rows(self.site)})

    def test_requested_order_and_context_under_category(self):
        items=display_rows(self.site);keys=[r['key'] for r in items]
        self.assertEqual(keys[:3],['section_location','departure','departure.coordinates'])
        self.assertNotIn('transport.deliveryType',keys)
        self.assertEqual([r['key'] for r in items if r['section'] and not r.get('parent')],['section_location','section_climate','section_structural','section_loads','section_corrosion'])
        by_key={r['key']:r for r in items}
        for key in ('coast','airQuality.so2','airQuality.seaSalt','airQuality.seaSaltDry','section_air'):
            self.assertEqual(by_key[key]['parent'],CORROSIVITY_GROUP)
        structural_start=keys.index('section_structural')
        self.assertEqual(keys[structural_start+1:structural_start+5],['seismic.pga','seismic.interpretation','seismic.designCode','seismic.national'])
        self.assertNotIn('seismic.hazardReference',keys)
        self.assertTrue(keys.index('section_climate')<structural_start<keys.index('section_corrosion'))

    def test_combined_humidity_and_manual_provenance(self):
        from value_details import build,plain_text
        for key,value in [('maximum',95),('mean',60),('minimum',20)]:
            sc.automatic(self.site,'humidity.'+key,value,'Open-Meteo Historical / ERA5')
        items={r['key']:r for r in display_rows(self.site)}
        self.assertEqual(items['humidity.summary']['value'],'95 / 60 / 20 %')
        self.assertNotIn('humidity.maximum',items)
        self.assertNotIn('humidity.mean',items)
        sc.apply_manual(self.site,{'humidity.mean':'55'})
        text=plain_text(build(self.site,'humidity.summary'))
        self.assertIn('Mean: 55 % — manual entry',text)
        self.assertIn('Maximum: 95 %',text)

    def test_loading_and_failure_do_not_show_a_fabricated_category(self):
        self.site['deposition']={'status':'queued','message':'Request queued'}
        parent=next(r for r in display_rows(self.site) if r['key']==CORROSIVITY_GROUP)
        self.assertTrue(parent['value']);self.assertNotIn('C2',parent['value'])
        self.site['deposition']['status']='unavailable'
        parent=next(r for r in display_rows(self.site) if r['key']==CORROSIVITY_GROUP)
        self.assertIn('Not available',parent['value'])

    def test_distinct_periods_and_source_flags_are_preserved(self):
        self.site['deposition']=ready()
        self.site['deposition']['qualityFlags']=['negative_wet_flux_samples']
        items={r['key']:r for r in display_rows(self.site)}
        for key in ('airQuality.so2','deposition.so2Volume','humidity.summary','deposition.humidity'):
            self.assertIn(key,items)
        self.assertIn('source flagged',items['deposition.wet']['value'])


if __name__=='__main__':unittest.main()
