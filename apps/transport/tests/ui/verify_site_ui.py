"""Overview-only site window: read-only data, provenance and export."""
import os,json,tempfile
from pathlib import Path
from unittest.mock import patch
from tkinter import ttk
from planner_ui import Planner
import site_conditions as sc

def walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from walk(child)

with tempfile.TemporaryDirectory() as folder:
    app=Planner(Path(folder)/'state.json',offline=True);app.update()
    errors=[];app.report_callback_exception=lambda *args:errors.append(args)
    sc.apply_manual(app.site,{'wind.qb':'.4'})
    win=app.open_site();app.update()
    assert len(win.book.tabs())==1 and win.book.tab(0,'text')=='Overview'
    assert not any(isinstance(w,(ttk.Entry,ttk.Combobox,ttk.Checkbutton)) for w in walk(win))
    assert not any(isinstance(w,ttk.Button) and w.cget('text')=='Save changes' for w in walk(win))
    assert win.overview.item('wind.qb','values')[1:3]==('0.4','kPa')
    assert win.overview.item('wind.qb','values')[3]=='Manual entry'
    assert sc.get(app.site,'wind.qb')['manualOverride']
    win.overview.selection_set('wind.qb');win.overview_detail();assert 'Reference wind pressure' in win.detail.cget('text')
    target=Path(folder)/'conditions.json'
    with patch('site_ui.filedialog.asksaveasfilename',return_value=str(target)):win.export()
    assert json.loads(target.read_text(encoding='utf-8'))['wind']['qb']['value']==.4
    if os.environ.get('FLOWERMOON_UI_ARTIFACTS'):
        from PIL import ImageGrab
        out=Path(os.environ['FLOWERMOON_UI_ARTIFACTS']);out.mkdir(parents=True,exist_ok=True)
        win.geometry('1120x820+30+30');win.lift();app.update()
        ImageGrab.grab(bbox=(win.winfo_rootx(),win.winfo_rooty(),win.winfo_rootx()+win.winfo_width(),win.winfo_rooty()+win.winfo_height())).save(out/'overview-only.png')
    win.destroy();app.close();assert not errors,errors
print('PASS: Overview is the only tab, no manual editor controls, existing values retained, provenance and JSON export')
