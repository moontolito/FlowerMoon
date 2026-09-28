"""Verify data cards, refresh selection and compact editor navigation."""
from pathlib import Path
from tempfile import TemporaryDirectory
from tkinter import ttk
from planner_ui import Planner
import site_conditions as sc

with TemporaryDirectory() as folder:
    app=Planner(Path(folder)/'state.json',offline=True)
    errors=[];app.report_callback_exception=lambda *args:errors.append(args)
    app.update();win=app.open_site();win.geometry('1120x820');app.update()
    sc.apply_manual(app.site,{'temperature.maxDesign':'35.85','temperature.minDesign':'-12.97'})
    win.refresh();app.update()
    assert win.overview.item('design','values')[1:3]==('+35.85 / -12.97','°C')
    assert win.overview.item('design','values')[3]=='Manual entry'
    win.overview.selection_set('design');win.refresh();app.update()
    assert win.overview.selection()==('design',)
    for mode in ('light','dark'):
        if app.mode!=mode:app.theme();win=app.open_site()
        for size in ('1120x820','760x600','760x820'):
            win.geometry(size);app.update()
            row_height=int(ttk.Style(win.overview).lookup(win.overview.cget('style'),'rowheight'))
            assert win.overview.winfo_height()>=3*row_height,(mode,size,win.overview.winfo_height())
            assert win.value_button.winfo_viewable()
            assert win.value_button.winfo_rooty()+win.value_button.winfo_height()<=win.winfo_rooty()+win.winfo_height()
            assert len(win.book.tabs())==1
            assert not hasattr(win,'save_button')
    app.close();assert not errors,errors
print('PASS: manual card values, selection retention, light/dark, three sizes, Overview-only layout')
