"""Legacy seasonal results are archived and never relabelled as annual results."""
import tempfile,json
from pathlib import Path
from unittest.mock import patch
from planner_ui import Planner
from domain import State
from test_deposition import ready,POINT
import corrosion
from value_details import build,plain_text

with tempfile.TemporaryDirectory() as folder:
    path=Path(folder)/'state.json';state=State(path)
    site=state.data['siteConditions'];site.pop('corrosionPolicyVersion',None)
    site.update(destinationAddress='Legacy 30-day destination',destinationCoordinates='45.1,24.1',deposition=ready())
    site['corrosionAssessment']=corrosion.evaluate(site['deposition'],POINT);state.save()
    app=Planner(path,offline=True);app.update();app.site_location_ready=lambda:None
    assert not app.site['corrosivityEnabled']
    assert app.site['sourceHistory'][-1]['data']['corrosionAssessment']['seasonal']
    win=app.open_site();app.update()
    assert win.overview.item('environment.suggestedCorrosivity','values')[1].startswith('Disabled')
    app.site['corrosivityEnabled']=True;app.offline=False
    with patch('cams.enabled',return_value=True),patch('annual_deposition.lookup') as provider,patch('app.threading.Thread'):
        app.refresh_deposition()
        assert app.site['deposition']['windowDays'] in (365,366)
        assert app.site['corrosionAssessment']['category'] is None
    text=plain_text(build(app.site,'environment.suggestedCorrosivity'))
    assert 'Calculation for this destination' not in text
    app.offline=True;app.close()
print('PASS: legacy seasonal history retained; disabled by default; no annual relabelling')
