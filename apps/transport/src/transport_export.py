"""Export the selected transport directly, with optional saved deliveries."""
import os,uuid
from copy import deepcopy
from pathlib import Path
from tkinter import filedialog,messagebox
from domain import num,stamp
from excel_export import export_workbook

def current_delivery(app,values):
    if not app.route_context or not app.route_tree.selection():raise ValueError('Calculate and select a route before exporting the current transport.')
    row=dict(deepcopy(app.route_context),**deepcopy(app.route_results[int(app.route_tree.selection()[0])]))
    quantity=num(values['quantity'],'Quantity',1,True)
    if quantity>row['product']['quantity']:raise ValueError('Export quantity exceeds the product quantity.')
    row.update(id=uuid.uuid4().hex,quantity=quantity,return_km=num(values['return_km'],'Empty return'),position_km=num(values['position_km'],'Positioning'),notes=values['notes'],siteConditions=deepcopy(app.site))
    return row

def show_export(app):
    from app import Form
    current=bool(app.route_context and app.route_tree.selection())
    saved=bool(app.state.data['deliveries'])
    if not current and not saved:
        messagebox.showinfo('Export Excel','Choose the destination and calculate a route first.',parent=app);return
    modes=(['Current transport'] if current else [])+(['Saved deliveries'] if saved else [])
    selected=app.route_results[int(app.route_tree.selection()[0])] if current else {}
    values=dict(mode=modes[0],quantity=app.state.data['product']['quantity'],return_km=selected.get('distance_km',0),position_km=0,notes='Return distance equals outbound distance; verify the return route.',**app.state.data['rates'])
    generation=app.generation
    fields=[('mode','Export',modes),('quantity','Products / trips'),('return_km','Empty return per trip (km)'),('position_km','Positioning per trip (km)'),
            ('loaded','Loaded rate (EUR/km)'),('empty','Empty rate (EUR/km)'),('fixed','Fixed cost (EUR/trip)'),('markup','Markup (%)'),('vat','VAT (%)'),('notes','Transport assumptions')]
    def save(v):
        if v['mode']=='Current transport':
            if app.generation!=generation:raise ValueError('Transport changed. Reopen Export Excel for the current route.')
            rows=[current_delivery(app,v)]
        else:rows=deepcopy(app.state.data['deliveries'])
        rates={k:num(v[k],k) for k in ('loaded','empty','fixed','markup','vat')}
        hosted=os.environ.get('FLOWERMOON_HOSTED')=='1'
        if hosted:
            folder=app.state.path.parent/'exports';folder.mkdir(parents=True,exist_ok=True)
            path=folder/('FlowerMoon-Transport-'+stamp().replace(':','-')+'-'+uuid.uuid4().hex[:8]+'.xlsx')
        else:path=filedialog.asksaveasfilename(parent=app,defaultextension='.xlsx',initialfile='FlowerMoon Transport.xlsx',filetypes=[('Excel workbook','*.xlsx')])
        if not path:return
        export_workbook(path,rows,rates);app.state.data['rates']=rates;app.state.save()
        app.status.set('Excel is ready. Use Download Excel in the browser toolbar.' if hosted else 'Excel exported: '+str(path))
    form=Form(app,'Export transport to Excel',fields,values,save,'Exports transport costs, route details and Site & Environment with the delivery address, coordinates and sources. Return distance is an editable assumption. Quantity and empty kilometres apply to Current transport; Saved deliveries retain their stored values.',save_label='Export Excel')
    return form
