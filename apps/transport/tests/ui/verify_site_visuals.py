"""Verify data cards, refresh selection and compact editor navigation."""
from pathlib import Path
from tempfile import TemporaryDirectory
from planner_ui import Planner
import site_conditions as sc

with TemporaryDirectory() as folder:
    app=Planner(Path(folder)/'state.json',offline=True)
    errors=[];app.report_callback_exception=lambda *args:errors.append(args)
    app.update();win=app.open_site();win.geometry('1120x820');app.update()
    sc.apply_manual(app.site,{'temperature.maxDesign':'35.85','temperature.minDesign':'-12.97'})
    win.refresh();app.update()
    assert win.metrics['temperature'].value.cget('text')=='+35.85 / -12.97 °C'
    assert 'Manual' in win.metrics['temperature'].note.cget('text')
    win.overview.selection_set('design');win.refresh();app.update()
    assert win.overview.selection()==('design',)
    for mode in ('light','dark'):
        if app.mode!=mode:app.theme();win=app.open_site()
        for size in ('1120x820','760x600','760x820'):
            win.geometry(size);app.update()
            assert win.overview.winfo_height()>130,(mode,size,win.overview.winfo_height())
            for tab in (1,2,3):
                win.book.select(tab);app.update()
                assert win.save_button.winfo_ismapped()
                assert win.save_button.winfo_rootx()+win.save_button.winfo_width()<=win.winfo_rootx()+win.winfo_width()
            win.book.select(0);app.update()
            assert not win.save_button.winfo_ismapped()
    app.close();assert not errors,errors
print('PASS: manual card values, selection retention, light/dark, three sizes, all editor tabs and Save')
