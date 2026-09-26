"""Record real provider availability separately from deterministic regression tests."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'apps'/'transport'/'src'))
import places,regions
report=[]
for query in ('Botosani Romania','Tokyo Japan'):
    try:
        results=places.search(query)
        report.append(dict(provider='Photon / OSM',query=query,status='ready' if results else 'no_results',results=results[:2]))
    except Exception as error:report.append(dict(provider='Photon / OSM',query=query,status='unavailable',error=str(error)))
for name,point in [('Botosani',dict(lat=47.74,lon=26.66)),('New York',dict(lat=40.71,lon=-74.0))]:
    try:
        result=regions.lookup(point,ROOT/'.runtime'/'boundary-cache')
        report.append(dict(provider='geoBoundaries',testLocation=name,**{k:v for k,v in result.items() if k!='geometry'}))
    except Exception as error:report.append(dict(provider='geoBoundaries',testLocation=name,status='unavailable',error=str(error)))
target=ROOT/'.artifacts'/'source-connectivity.json';target.parent.mkdir(exist_ok=True)
target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
for item in report:print(item['provider'],item.get('query',item.get('testLocation')),item['status'],item.get('name',''))
