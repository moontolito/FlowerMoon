"""Native disclosure interactions, refreshing and light/dark visual artifacts."""
import os,tempfile,time
from pathlib import Path
from planner_ui import Planner
from test_annual import ready,POINT
from site_overview import CORROSIVITY_GROUP as GROUP,CORROSIVITY_INPUTS
import annual_corrosion as corrosion

with tempfile.TemporaryDirectory() as folder:
    app=Planner(Path(folder)/'state.json',offline=True);app.update()
    app.site['corrosivityEnabled']=True;app.site_location_ready=lambda:None
    errors=[];app.report_callback_exception=lambda *args:errors.append(args)
    app.dest_name.set('QA destination');app.dest_coords.set('45.1,24.1')
    app.site.update(destinationAddress='QA destination',destinationCoordinates='45.1,24.1')
    win=app.open_site();app.update()
    app.site['deposition']=ready()
    app.site['deposition'].update(qualityFlags=['negative_wet_flux_samples'],wetScenarioUsable=False)
    app.site['corrosionAssessment']=corrosion.evaluate(app.site['deposition'],POINT)
    win.refresh();app.update();tree=win.overview
    assert 'annual estimate' in tree.item(GROUP,'values')[1]
    assert tree.get_children(GROUP)
    assert not tree.item(GROUP,'open') and tree.item(GROUP,'text')=='+'
    assert all(tree.parent(key)==GROUP for key in CORROSIVITY_INPUTS)
    assert not tree.exists('timeOfWetness') and not tree.exists('transport.suggestedProtection')
    tree.see(GROUP);app.update()
    assert not tree.bbox('deposition.temperature')
    x,y,w,h=tree.bbox(GROUP,'#0')
    print('Disclosure click target:',dict(bbox=(x,y,w,h),height=tree.winfo_height(),
        region=tree.identify_region(x+w//2,y+h//2),row=tree.identify_row(y+h//2),
        column=tree.identify_column(x+w//2)),flush=True)
    tree.event_generate('<ButtonPress-1>',x=x+w//2,y=y+h//2,time=1000)
    tree.event_generate('<ButtonRelease-1>',x=x+w//2,y=y+h//2,time=1030);app.update()
    assert tree.item(GROUP,'open') and tree.item(GROUP,'text')=='−',dict(open=tree.item(GROUP,'open'),text=tree.item(GROUP,'text'),errors=errors)
    assert not hasattr(win,'value_window')
    win.refresh();app.update()
    assert tree.item(GROUP,'open') and tree.selection()==(GROUP,)
    tree.focus_force();tree.event_generate('<space>');app.update()
    assert not tree.item(GROUP,'open') and tree.item(GROUP,'text')=='+'
    tree.event_generate('<Right>');app.update()
    assert tree.item(GROUP,'open') and tree.item(GROUP,'text')=='−'
    tree.event_generate('<Left>');app.update()
    assert not tree.item(GROUP,'open') and tree.item(GROUP,'text')=='+'
    win.toggle_group(GROUP)
    tree.selection_set('deposition.temperature');win.refresh();app.update()
    assert tree.selection()==('deposition.temperature',) and tree.item(GROUP,'open')
    dialog=win.value_details('deposition.temperature');app.update()
    assert 'QA destination' in dialog.area.get('1.0','end');dialog.destroy()
    # New destination invalidation is displayed; old category must not linger.
    saved=app.site['corrosionAssessment']
    app.site['corrosionAssessment']={'status':'unavailable','reason':'Waiting for new destination'}
    win.refresh();app.update();assert 'Not available' in tree.item(GROUP,'values')[1]
    app.site['corrosionAssessment']=saved
    win.refresh();app.update()
    for mode in ('light','dark'):
        if app.mode!=mode:app.theme();win=app.open_site()
        win.geometry('1120x820+30+30');win.attributes('-topmost',True);win.lift();app.update();tree=win.overview
        for opened in (False,True):
            tree.item(GROUP,open=opened);win.sync_group_controls();tree.see(GROUP)
            # Keep the result near the top, so expanded inputs can be reviewed.
            tree.yview(tree.index(GROUP));app.update();time.sleep(.2)
            if os.environ.get('FLOWERMOON_UI_ARTIFACTS'):
                from PIL import ImageGrab
                out=Path(os.environ['FLOWERMOON_UI_ARTIFACTS']);out.mkdir(parents=True,exist_ok=True)
                ImageGrab.grab(bbox=(win.winfo_rootx(),win.winfo_rooty(),win.winfo_rootx()+win.winfo_width(),win.winfo_rooty()+win.winfo_height())).save(out/f'corrosivity-{mode}-{"expanded" if opened else "collapsed"}.png')
        win.geometry('760x600');app.update();assert tree.winfo_height()>130
        assert win.value_button.winfo_viewable()
    app.close();assert not errors,errors
print('PASS: +, Space, Left/Right, collapsed inputs, refresh state, destination invalidation, retained provenance and light/dark compact UI')
