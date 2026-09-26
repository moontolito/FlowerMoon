"""App startup must remain possible when the optional DEM reader is missing."""
import builtins,tempfile
from pathlib import Path

original_import=builtins.__import__
def without_pillow(name,*args,**kwargs):
    if name=='PIL' or name.startswith('PIL.'):
        raise ModuleNotFoundError("No module named 'PIL'")
    return original_import(name,*args,**kwargs)

builtins.__import__=without_pillow
try:
    import elevation
    from planner_ui import Planner
    assert elevation.Image is None
    result=elevation.samples([dict(lat=44.18,lon=28.63)])
    assert result['values']==[None] and not result['complete']
    assert 'Pillow' in result['errors'][0]
    with tempfile.TemporaryDirectory() as folder:
        app=Planner(Path(folder)/'state.json',offline=True)
        app.update()
        assert app.winfo_viewable()
        window=app.open_site();app.update();assert window.winfo_viewable()
        app.close()
finally:
    builtins.__import__=original_import
print('PASS: planner and site window start without Pillow; elevation reports the missing dependency')
