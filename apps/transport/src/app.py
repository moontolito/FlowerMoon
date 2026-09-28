"""Two-step FlowerMoon desktop app. Routing and estimates remain preliminary."""
import sys,json,queue,threading,webbrowser
from copy import deepcopy
from pathlib import Path
import tkinter as tk
from tkinter import ttk,messagebox,filedialog
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE/'src'/'ui_shared'));sys.path.insert(0,str(HERE/'vendor'/'sun-valley'))
import sv_ttk
from design_system import LIGHT,DARK,FONT,configure
from window_icon import create_icon
from domain import *
import routing
from map_widget import Map
import site_conditions as sc
import site_sources
import zoning
from site_environment import standards,service as site_service
import climate
import humidity
import cams
import annual_deposition as deposition
from site_ui import SiteWindow

class Form(tk.Toplevel):
    def __init__(self,app,title,fields,values,save,help_text='',save_label='Save'):
        super().__init__(app);self.app=app;self.vars={};self.save=save;self.title(title);self.geometry('790x650');self.minsize(650,440);self.transient(app)
        self.columnconfigure(0,weight=1);self.rowconfigure(1,weight=1)
        top=ttk.Frame(self,padding=16);top.grid(row=0,column=0,sticky='ew');ttk.Label(top,text=title,font=(FONT,13,'bold')).pack(anchor='w')
        if help_text:ttk.Label(top,text=help_text,wraplength=730).pack(anchor='w',pady=(8,0))
        area=ttk.Frame(self);area.grid(row=1,column=0,sticky='nsew');area.columnconfigure(0,weight=1);area.rowconfigure(0,weight=1)
        canvas=tk.Canvas(area,bg=app.c['surface'],highlightthickness=0);canvas.grid(row=0,column=0,sticky='nsew')
        scrollbar=ttk.Scrollbar(area,command=canvas.yview);scrollbar.grid(row=0,column=1,sticky='ns');canvas.configure(yscrollcommand=scrollbar.set)
        body=ttk.Frame(canvas,padding=16);item=canvas.create_window(0,0,anchor='nw',window=body)
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width));body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        for i,(key,label,*rest) in enumerate(fields):
            cell=ttk.Frame(body);cell.grid(row=i//2,column=i%2,sticky='ew',padx=(0,16),pady=(0,14));body.columnconfigure(i%2,weight=1)
            ttk.Label(cell,text=label,wraplength=330).pack(anchor='w',pady=(0,4))
            kind=rest[0] if rest else None
            var=tk.BooleanVar(value=bool(values.get(key))) if kind=='bool' else tk.StringVar(value=str(values.get(key,'')))
            self.vars[key]=var
            widget=ttk.Checkbutton(cell,text='Yes',variable=var) if kind=='bool' else ttk.Combobox(cell,textvariable=var,values=kind,state='readonly') if isinstance(kind,list) else ttk.Entry(cell,textvariable=var)
            widget.pack(fill='x');widget.bind('<FocusIn>',lambda e:canvas.yview_moveto(max(0,e.widget.master.winfo_y()-30)/max(1,body.winfo_height())),add='+')
        foot=ttk.Frame(self,padding=16);foot.grid(row=2,column=0,sticky='ew');self.error=tk.StringVar()
        ttk.Label(foot,textvariable=self.error,foreground=app.c['danger'],wraplength=730).pack(anchor='w',pady=(0,8))
        ttk.Button(foot,text=save_label,style='Brand.TButton',command=self.submit).pack(side='right');ttk.Button(foot,text='Cancel',command=self.destroy).pack(side='right',padx=8)
        self.bind('<Escape>',lambda e:self.destroy());self.grab_set()
    def submit(self):
        try:self.save({k:v.get() for k,v in self.vars.items()})
        except (ValueError,OSError) as e:self.error.set(str(e));return
        self.destroy()

class App(tk.Tk):
    def __init__(self,path=None,offline=False):
        super().__init__();self.title('FlowerMoon • Transport');self.geometry('1320x840+20+20');self.minsize(1120,700)
        self.icons=[create_icon(self,n) for n in (16,32,48)];self.iconphoto(True,*self.icons)
        self.logo_original=tk.PhotoImage(file=str(HERE/'assets'/'FlowerMoonLogo.png'));self.logo=self.logo_original.subsample(8,8)
        self.state=State(path or HERE/'data'/'planning.json');self.offline=offline;self.mode='light';self.step=1
        self.active=None;self.matches=[];self.route_results=[];self.route_context=None;self.busy=False;self.jobs=queue.Queue();self.site_jobs=queue.Queue();self.generation=0
        self.product_vars={k:tk.StringVar(value=str(v)) for k,v in self.state.data['product'].items()}
        for v in self.product_vars.values():v.trace_add('write',self.invalidate)
        self.origin_name=tk.StringVar(value=self.state.data['origin_name']);self.origin_coords=tk.StringVar(value=self.state.data['origin_coords'])
        self.site=self.state.data['siteConditions'];self.site_window=None;self.site_timer=None;self.site_token=0;self.site_cache={};self.site_inflight=set();self.climate_inflight=set();self.humidity_inflight=set();self.cams_inflight=set();self.cams_timer=None
        self.deposition_inflight=set();self.deposition_timer=None
        self.corrosion_epoch=0;self.corrosion_cancel=threading.Event()
        sc.recommendation(self.site)
        self.dest_name=tk.StringVar(value=self.site['destinationAddress']);self.dest_coords=tk.StringVar(value=self.site['destinationCoordinates']);self.via=tk.StringVar()
        for v in (self.origin_name,self.origin_coords,self.dest_name,self.dest_coords,self.via):v.trace_add('write',self.invalidate_route)
        for v in (self.origin_name,self.origin_coords,self.dest_name,self.dest_coords):v.trace_add('write',self.site_location_changed)
        self.accept=tk.BooleanVar(value=False);self.status=tk.StringVar(value='Enter the product, then select Recommend vehicle.');self.build()
        self.poll_id=self.after(100,self.poll);self.protocol('WM_DELETE_WINDOW',self.close)

    def site_location_changed(self,*_):
        if (self.site['destinationAddress'],self.site['destinationCoordinates'])!=(self.dest_name.get(),self.dest_coords.get()):
            self.corrosion_cancel.set();self.corrosion_cancel=threading.Event();self.corrosion_epoch+=1
        if (self.site['destinationAddress'],self.site['destinationCoordinates'])!=(self.dest_name.get(),self.dest_coords.get()) and self.deposition_timer:
            self.after_cancel(self.deposition_timer);self.deposition_timer=None
        if (self.site['destinationAddress'],self.site['destinationCoordinates'])!=(self.dest_name.get(),self.dest_coords.get()) and self.cams_timer:
            self.after_cancel(self.cams_timer);self.cams_timer=None
        sc.sync(self.site,self.origin_name.get(),self.dest_name.get(),self.origin_coords.get(),self.dest_coords.get())
        self.refresh_local_hazard()
        self.site['lookupState']='Updating destination data…' if self.dest_coords.get() else 'Select an address suggestion or a delivery point on the map.'
        self.state.data.update(origin_name=self.origin_name.get(),origin_coords=self.origin_coords.get())
        self.site_token+=1
        self.refresh_site_window()
        if self.site_timer:self.after_cancel(self.site_timer)
        self.site_timer=self.after(1200,self.site_location_ready)
    def site_location_ready(self):
        self.site_timer=None
        self.state.save()
        try:destination=coordinates(self.dest_coords.get())
        except ValueError:return
        site_service.apply_context(self.site,site_service.context(destination))
        if hasattr(self,'refresh_region'):self.refresh_region(destination)
        sc.apply_zoning(self.site,standards.lookup(destination,sc.get(self.site,'environment.siteAltitudeM')['value']))
        sc.recommendation(self.site);self.state.save();self.refresh_site_window()
        self.refresh_climate()
        self.refresh_humidity()
        if not self.offline:self.open_site()
        self.refresh_site_sources()
        # Automatic preliminary routing never represents vehicle/permit approval.
        if not self.offline and self.active and self.origin_coords.get() and not self.busy and not self.route_context:
            self.safe(lambda:App.calculate_route(self,preliminary=True))
        elif not self.offline and self.busy and self.active and not self.route_context:
            self.site_timer=self.after(1200,self.site_location_ready)
    def open_site(self):
        sc.sync(self.site,self.origin_name.get(),self.dest_name.get(),self.origin_coords.get(),self.dest_coords.get())
        self.refresh_local_hazard()
        try:
            destination=coordinates(self.dest_coords.get())
            site_service.apply_context(self.site,site_service.context(destination))
            sc.apply_zoning(self.site,standards.lookup(destination,sc.get(self.site,'environment.siteAltitudeM')['value']))
        except ValueError:pass
        if self.site_window and self.site_window.winfo_exists():self.refresh_site_window();self.site_window.lift();return self.site_window
        self.site_window=SiteWindow(self);self.refresh_humidity();self.refresh_climate();self.refresh_site_sources();return self.site_window
    def refresh_site_window(self):
        if self.site_window and self.site_window.winfo_exists():self.site_window.refresh()
    def refresh_local_hazard(self):
        import gem_hazard
        try:point=coordinates(self.dest_coords.get())
        except ValueError:
            self.site.pop('seismicHazard',None);return
        self.site['seismicHazard']=gem_hazard.lookup(point)
    def refresh_site_sources(self,force=False):
        self.refresh_local_hazard();self.refresh_site_window()
        if force:self.refresh_climate(force=True);self.refresh_humidity(force=True)
        self.refresh_air_quality(force=force)
        self.refresh_deposition(force=force)
        if self.offline:return
        try:destination=coordinates(self.dest_coords.get())
        except ValueError:return
        geometry=None
        if self.route_context and self.route_tree.selection():geometry=self.route_results[int(self.route_tree.selection()[0])]['geometry']
        token=self.site_token;server=self.state.data['server'];key=(server,destination['lat'],destination['lon'],json.dumps(geometry,sort_keys=True))
        if force:self.site_cache.pop(key,None)
        def done(result):
            self.site_inflight.discard((key,token))
            if token!=self.site_token:return
            if result:self.site_cache[key]=result
            if 'altitude' in result:sc.automatic(self.site,'transport.maxAltitudeM',*result['altitude'],status=result.get('altitudeStatus','AUTO'))
            if 'marine' in result:sc.automatic(self.site,'environment.marineEnvironment',*result['marine'],status='VERIFY')
            if 'siteAltitude' in result:sc.automatic(self.site,'environment.siteAltitudeM',result['siteAltitude'],result.get('siteAltitudeSource','Source not specified'),'VERIFY',detail=result.get('siteAltitudeDetail',''))
            if 'elevationAnalysis' in result:self.site['elevationAnalysis']=result['elevationAnalysis']
            if 'locationContext' in result:site_service.apply_context(self.site,result['locationContext'])
            if 'coastalDistance' in result:self.site['coastalDistance']=result['coastalDistance']
            if 'zoning' in result:sc.apply_zoning(self.site,result['zoning'])
            self.site['lookupState']='Destination lookup complete. Available values and their sources are shown below.'
            sc.recommendation(self.site);self.state.save();self.refresh_site_window()
        if key in self.site_cache:done(self.site_cache[key]);return
        if (key,token) in self.site_inflight:return
        self.site_inflight.add((key,token));self.site['lookupState']='Loading destination elevation and coastal data…';self.refresh_site_window()
        def worker():
            try:result=site_sources.lookup(server,destination,geometry)
            except Exception as error:result={'error':str(error)}
            self.site_jobs.put((done,result,None))
        threading.Thread(target=worker,daemon=True).start()
    def refresh_humidity(self,force=False):
        if self.offline:return
        try:destination=coordinates(self.dest_coords.get())
        except ValueError:return
        location=self.dest_coords.get()
        if location in self.humidity_inflight:return
        existing=self.site.get('humidityAnalysis',{})
        if not force and existing.get('status')=='unavailable':return
        if not force and existing.get('status')=='ready' and existing.get('methodVersion')==humidity.VERSION and existing.get('periodEnd')==climate.period()[1].isoformat():return
        self.humidity_inflight.add(location);self.site['humidityAnalysis']={'status':'loading'};self.refresh_site_window()
        def done(result):
            self.humidity_inflight.discard(location)
            if location!=self.dest_coords.get():return
            if 'error' in result:self.site['humidityAnalysis']={'status':'unavailable','message':result['error']}
            else:humidity.apply(self.site,result)
            self.state.save();self.refresh_site_window()
        def worker():
            try:result=humidity.lookup(destination,self.state.path.parent/'humidity-cache',force=force)
            except Exception as error:result={'error':str(error)}
            self.site_jobs.put((done,result,None))
        threading.Thread(target=worker,daemon=True).start()
    def refresh_climate(self,force=False):
        if self.offline:return
        try:destination=coordinates(self.dest_coords.get())
        except ValueError:return
        location=self.dest_coords.get()
        if location in self.climate_inflight:return
        existing=self.site.get('climate',{})
        if not force and existing.get('status')=='unavailable':return
        if not force and existing.get('status')=='ready' and existing.get('methodVersion')==climate.VERSION and existing.get('periodEnd')==climate.period()[1].isoformat():return
        self.climate_inflight.add(location);self.site['climate']={'status':'loading'};self.refresh_site_window()
        def done(result):
            self.climate_inflight.discard(location)
            if location!=self.dest_coords.get():return
            if 'error' in result:self.site['climate']={'status':'unavailable','message':result['error']}
            else:climate.apply(self.site,result)
            self.state.save();self.refresh_site_window()
        def worker():
            try:result=climate.lookup(destination,self.state.path.parent/'climate-cache',force=force)
            except Exception as error:result={'error':str(error)}
            self.site_jobs.put((done,result,None))
        threading.Thread(target=worker,daemon=True).start()
    def refresh_air_quality(self,force=False):
        if self.offline or not cams.enabled() or not self.site.get('corrosivityEnabled',False):return
        try:destination=coordinates(self.dest_coords.get())
        except ValueError:return
        location=self.dest_coords.get();epoch=self.corrosion_epoch;cancel=self.corrosion_cancel
        job_key=(location,epoch)
        if job_key in self.cams_inflight:return
        existing=self.site.get('airQuality',{})
        if not force and existing.get('status')=='unavailable':return
        if not force and existing.get('status')=='ready' and existing.get('methodVersion')==cams.VERSION and existing.get('periodEnd')==f'{cams.YEAR}-12-31' and existing.get('requestedCoordinates')==destination:return
        if self.cams_timer:self.after_cancel(self.cams_timer);self.cams_timer=None
        force=force and existing.get('status') not in ('queued','running')
        self.cams_inflight.add(job_key)
        self.site['airQuality']=dict(cams.base_result(cams.request_for(destination)),status='loading',requestedCoordinates=destination,message='Loading CAMS atmospheric exposure…')
        self.refresh_site_window()
        def done(result):
            self.cams_inflight.discard(job_key)
            if location!=self.dest_coords.get() or epoch!=self.corrosion_epoch or not self.site.get('corrosivityEnabled',False):return
            self.site['airQuality']=result;self.state.save();self.refresh_site_window()
            if result.get('status') in ('queued','running'):
                self.cams_timer=self.after(20000,self.refresh_air_quality)
        def worker():
            if cancel.is_set():
                self.site_jobs.put((done,dict(status='disabled'),None));return
            try:result=cams.lookup(destination,self.state.path.parent/'cams-cache',force=force)
            except Exception as error:
                safe=cams.safe_error(error)
                result=dict(cams.base_result(cams.request_for(destination)),status='unavailable',errorCode=safe.code,message=str(safe),requestedCoordinates=destination)
            self.site_jobs.put((done,result,None))
        threading.Thread(target=worker,daemon=True).start()

    def refresh_deposition(self,force=False):
        if self.offline or not cams.enabled() or not self.site.get('corrosivityEnabled',False):return
        try:destination=coordinates(self.dest_coords.get())
        except ValueError:return
        location=self.dest_coords.get();epoch=self.corrosion_epoch;cancel=self.corrosion_cancel
        job_key=(location,epoch)
        if job_key in self.deposition_inflight:return
        existing=self.site.get('deposition',{})
        current=deposition.base(destination)
        same_window=all(existing.get(k)==current.get(k) for k in ('methodVersion','periodStart','periodEnd','requestedCoordinates'))
        if not force and same_window and existing.get('status')=='unavailable' and not existing.get('retryable'):return
        if not force and deposition.is_current(existing,destination):
            sc.recommendation(self.site);return
        if self.deposition_timer:self.after_cancel(self.deposition_timer);self.deposition_timer=None
        self.deposition_inflight.add(job_key)
        if existing.get('jobs') and same_window:
            # Preserve the last server state during a poll instead of flashing
            # back to an uninformative loading message every twenty seconds.
            self.site['deposition']=dict(existing,polling=True)
        else:
            self.site['deposition']=dict(current,status='loading',message='Checking the full-year CAMS requests…')
        sc.recommendation(self.site);self.refresh_site_window()
        def done(result):
            self.deposition_inflight.discard(job_key)
            if location!=self.dest_coords.get() or epoch!=self.corrosion_epoch or not self.site.get('corrosivityEnabled',False):return
            self.site['deposition']=result;sc.recommendation(self.site);self.state.save();self.refresh_site_window()
            if result.get('status') in ('queued','running'):
                self.deposition_timer=self.after(20000,self.refresh_deposition)
            elif result.get('retryable'):
                self.deposition_timer=self.after(120000,self.refresh_deposition)
        def worker():
            if cancel.is_set():
                self.site_jobs.put((done,dict(status='disabled'),None));return
            try:result=deposition.lookup(destination,self.state.path.parent/'annual-deposition-cache',force=force,cancelled=cancel.is_set)
            except Exception as error:result=deposition.error_result(destination,error)
            self.site_jobs.put((done,result,None))
        threading.Thread(target=worker,daemon=True).start()

    def close(self):
        self.corrosion_cancel.set()
        if self.deposition_timer:self.after_cancel(self.deposition_timer);self.deposition_timer=None
        if self.cams_timer:self.after_cancel(self.cams_timer);self.cams_timer=None
        if self.site_timer:self.after_cancel(self.site_timer);self.site_timer=None
        sc.sync(self.site,self.origin_name.get(),self.dest_name.get(),self.origin_coords.get(),self.dest_coords.get())
        self.state.data.update(origin_name=self.origin_name.get(),origin_coords=self.origin_coords.get())
        try:self.state.save()
        except OSError as e:messagebox.showerror('Save failed',str(e),parent=self);return
        if self.poll_id:self.after_cancel(self.poll_id);self.poll_id=None
        self.destroy()
    def safe(self,fn):
        try:return fn()
        except (ValueError,OSError) as e:self.status.set(str(e));messagebox.showerror('Check inputs',str(e),parent=self)
    def label(self,parent,text,kind='Panel',**kw):return ttk.Label(parent,text=text,style=kind+'.TLabel',**kw)
    def invalidate(self,*_):
        self.active=None;self.matches=[];self.accept.set(False) if hasattr(self,'accept') else None;self.invalidate_route()
        if hasattr(self,'vehicle_tree') and self.vehicle_tree.winfo_exists():self.vehicle_tree.delete(*self.vehicle_tree.get_children())
        if hasattr(self,'selection_text'):self.selection_text.set('Data changed. Select Recommend vehicle to evaluate again.')
    def invalidate_route(self,*_):
        if hasattr(self,'site'):
            self.site_token+=1;self.site_route_key=None
            sc.invalidate(self.site,sc.ROUTE_KEYS);self.refresh_site_window()
        self.generation+=1;self.route_results=[];self.route_context=None
        if hasattr(self,'route_tree') and self.route_tree.winfo_exists():self.route_tree.delete(*self.route_tree.get_children())
        if hasattr(self,'route_details') and self.route_details.winfo_exists():self.route_details.configure(text='')
        if hasattr(self,'map') and self.map.winfo_exists():self.map.set_content([],fit=False)
    def entry(self,parent,label,var,row,col=0,width=20):
        box=ttk.Frame(parent,style='Panel.TFrame');box.grid(row=row,column=col,sticky='ew',padx=(0,12),pady=(0,12));parent.columnconfigure(col,weight=1)
        self.label(box,label,'PanelMuted').pack(anchor='w',pady=(0,4));ttk.Entry(box,textvariable=var,width=width).pack(fill='x');return box
    def build(self):
        for w in self.winfo_children():w.destroy()
        self.c=LIGHT if self.mode=='light' else DARK;sv_ttk.set_theme(self.mode,self);configure(self,self.c)
        self.configure(bg=self.c['background']);self.columnconfigure(0,weight=1);self.rowconfigure(2,weight=1)
        header=ttk.Frame(self,style='Panel.TFrame',padding=(20,10));header.grid(row=0,column=0,sticky='ew')
        tk.Label(header,image=self.logo,bg='white',borderwidth=0).pack(side='left',padx=(0,12))
        brand=ttk.Frame(header,style='Panel.TFrame');brand.pack(side='left');self.label(brand,'FlowerMoon','PanelSection').pack(anchor='w');self.label(brand,'TRANSPORT','PanelMuted').pack(anchor='w')
        ttk.Button(header,text='Theme '+('light' if self.mode=='light' else 'dark'),command=self.theme).pack(side='right')
        ttk.Button(header,text='Site & Environment',command=self.open_site).pack(side='right',padx=6)
        ttk.Button(header,text='Vehicles',command=self.fleet).pack(side='right',padx=8);ttk.Button(header,text='Settings',command=self.settings).pack(side='right')
        nav=ttk.Frame(self,style='App.TFrame',padding=(24,14));nav.grid(row=1,column=0,sticky='ew')
        for n,name in [(1,'1. Product and vehicle'),(2,'2. Route and export')]:ttk.Button(nav,text=name,style='Brand.TButton' if n==self.step else 'TButton',command=lambda s=n:self.safe(lambda:self.navigate(s))).pack(side='left',padx=(0,12))
        ttk.Button(nav,text=f"Saved deliveries ({len(self.state.data['deliveries'])})",command=self.sheet).pack(side='right')
        self.body=ttk.Frame(self,style='App.TFrame',padding=(24,0,24,16));self.body.grid(row=2,column=0,sticky='nsew');self.body.columnconfigure(1,weight=1);self.body.rowconfigure(0,weight=1)
        if self.step==1:self.product_page()
        else:self.route_page()
        foot=ttk.Frame(self,style='Panel.TFrame',padding=(20,10));foot.grid(row=3,column=0,sticky='ew')
        ttk.Label(foot,textvariable=self.status,style='PanelMuted.TLabel',wraplength=1220).pack(anchor='w')
    def theme(self):self.mode='dark' if self.mode=='light' else 'light';self.build()
    def navigate(self,step):
        if step==2:
            if not self.active:raise ValueError('Enter the product and select a compatible vehicle first.')
            if not self.accept.get():raise ValueError('Confirm vehicle assumptions before routing.')
        self.step=step;self.build()
    def table(self,parent,columns,rows,height=6):
        frame=ttk.Frame(parent);frame.pack(fill='both',expand=True);frame.columnconfigure(0,weight=1);frame.rowconfigure(0,weight=1)
        tree=ttk.Treeview(frame,columns=[c[0] for c in columns],show='headings',height=height,selectmode='browse')
        for key,text,width in columns:tree.heading(key,text=text);tree.column(key,width=width,minwidth=60)
        tree.grid(row=0,column=0,sticky='nsew');sy=ttk.Scrollbar(frame,command=tree.yview);sy.grid(row=0,column=1,sticky='ns');sx=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview);sx.grid(row=1,column=0,sticky='ew');tree.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
        for ident,values in rows:tree.insert('','end',iid=str(ident),values=values)
        return tree

    def product_page(self):
        left=ttk.Frame(self.body,style='Panel.TFrame',padding=20);left.grid(row=0,column=0,sticky='ns',padx=(0,16))
        self.label(left,'What are we transporting?','PanelSection').grid(row=0,column=0,columnspan=2,sticky='w',pady=(0,6))
        self.label(left,'Dimensions of one product.','PanelMuted').grid(row=1,column=0,columnspan=2,sticky='w',pady=(0,18))
        for i,(key,label) in enumerate([('name','Product name'),('quantity','Quantity (units)'),('length','Length (m)'),('width','Width (m)'),('height','Height (m)'),('weight','Weight / product (t)')]):self.entry(left,label,self.product_vars[key],2+i//2,i%2,16)
        self.label(left,'Example: 9 × 3 × 3.3 m,\napproximately 7 t. Measure the actual product.','PanelMuted',wraplength=330).grid(row=5,column=0,columnspan=2,sticky='w',pady=(4,16))
        ttk.Button(left,text='Recommend vehicle',style='Brand.TButton',command=lambda:self.safe(self.find_vehicle)).grid(row=6,column=0,columnspan=2,sticky='ew')
        self.label(left,'One product per trip.\nStacking and overhang are not calculated automatically.','PanelMuted',wraplength=330).grid(row=7,column=0,columnspan=2,sticky='w',pady=(24,0))
        right=ttk.Frame(self.body,style='Panel.TFrame',padding=20);right.grid(row=0,column=1,sticky='nsew')
        self.label(right,'Suitable vehicle for the product','PanelSection').pack(anchor='w',pady=(0,6))
        self.label(right,'Compare capacity and dimensions, preferring a lower loaded height.','PanelMuted',wraplength=710).pack(anchor='w',pady=(0,16))
        self.vehicle_tree=self.table(right,[('name','Vehicle',210),('fit','Fit',160),('height','H total (m)',100),('weight','Total (t)',85)],[],5)
        self.vehicle_tree.bind('<<TreeviewSelect>>',self.select_vehicle)
        self.selection_text=tk.StringVar(value='Select Recommend vehicle to compare saved profiles.')
        ttk.Label(right,textvariable=self.selection_text,style='Panel.TLabel',wraplength=700,justify='left').pack(anchor='w',fill='x',pady=18)
        ttk.Checkbutton(right,text='I accept the displayed assumptions for a preliminary route.',variable=self.accept).pack(anchor='w',pady=(0,12))
        ttk.Button(right,text='Continue to route →',style='Brand.TButton',command=lambda:self.safe(lambda:self.navigate(2))).pack(anchor='e')
        if self.matches:self.populate_matches()

    def find_vehicle(self):
        p=product({k:v.get() for k,v in self.product_vars.items()});self.matches=recommend(p,self.state.data['vehicles']);self.accept.set(False)
        self.state.data['product']=p;self.state.save();self.populate_matches()
        self.status.set('Choose a vehicle and verify the loading assumptions.')
    def populate_matches(self):
        selected=next((str(i) for i,r in enumerate(self.matches) if r==self.active),'0')
        self.vehicle_tree.delete(*self.vehicle_tree.get_children())
        for i,r in enumerate(self.matches):
            label='Provisionally compatible' if r['fits'] else 'Does not fit / exceeds capacity'
            if i==0 and r['fits']:label='Preliminary recommendation'
            self.vehicle_tree.insert('','end',iid=str(i),values=(r['vehicle']['name']+(' · example' if r['vehicle']['example'] else ''),label,f"{r['loaded']['height']:.2f}",f"{r['loaded']['weight']:.2f}"))
        if self.matches:self.vehicle_tree.selection_set(selected);self.select_vehicle()
        else:self.selection_text.set('Add a profile using Vehicles.');self.active=None
    def select_vehicle(self,*_):
        ids=self.vehicle_tree.selection()
        if not ids:return
        r=self.matches[int(ids[0])];selected=deepcopy(r) if r['fits'] else None
        if selected!=self.active:self.accept.set(False);self.invalidate_route()
        self.active=selected
        if not r['fits']:
            self.selection_text.set('This vehicle does not fit:\n'+'\n'.join(r['reasons'])+'\n\nIf no profile fits, a special vehicle is required. Add carrier specifications under Vehicles.');return
        d=r['loaded'];v=r['vehicle']
        self.selection_text.set(f"Loaded vehicle: {d['length']:g} × {d['width']:g} × {d['height']:g} m\nTotal weight: {d['weight']:g} t · {d['axle_count']} axles · maximum {d['axle_load']:g} t/axle\n\n"+('EXAMPLE PROFILE — values do not describe a verified vehicle.\n' if v['example'] else '')+v['notes']+'\nConfirm support, securing and actual axle loads with the carrier.')

    def fleet(self):
        win=tk.Toplevel(self);win.title('Available vehicles');win.geometry('1000x470');win.transient(self)
        frame=ttk.Frame(win,padding=18);frame.pack(fill='both',expand=True)
        self.label(frame,'Editable profiles · permitted width must be confirmed by the carrier','PanelSection').pack(anchor='w',pady=(0,16))
        tree=self.table(frame,[('name','Vehicle',240),('deck','Deck L (m)',130),('width','Load W (m)',110),('payload','Payload (t)',110),('source','Type',180)],[(v['id'],(v['name'],v['deck_length'],v['load_width'],v['payload'],'Example' if v['example'] else 'User input')) for v in self.state.data['vehicles']])
        bar=ttk.Frame(frame);bar.pack(fill='x',pady=(16,0))
        def edit(new=False):
            if not new and not tree.selection():return
            initial={} if new else deepcopy(next(v for v in self.state.data['vehicles'] if v['id']==tree.selection()[0]))
            def save(values):
                v=vehicle(dict(initial,**values));existing=[x for x in self.state.data['vehicles'] if x['id']!=v['id']];self.state.data['vehicles']=existing+[v];self.state.save();self.invalidate();self.step=1;win.destroy();self.after_idle(self.build)
            Form(self,'Vehicle profile',VEHICLE_FIELDS+[('example','Illustrative, unconfirmed profile','bool'),('notes','Source / assumptions / securing')],initial,save,'Describe the actual loaded vehicle. Axle loads depend on the current load. Do not increase limits merely to obtain a match.')
        ttk.Button(bar,text='New vehicle',command=lambda:edit(True)).pack(side='left');ttk.Button(bar,text='Edit selected',command=edit).pack(side='left',padx=10);ttk.Button(bar,text='Close',command=win.destroy).pack(side='right')

    def route_page(self):
        left=ttk.Frame(self.body,style='Panel.TFrame',padding=18);left.grid(row=0,column=0,sticky='ns',padx=(0,16))
        self.label(left,'Where are we delivering?','PanelSection').grid(row=0,column=0,sticky='w',pady=(0,12))
        self.entry(left,'Departure · city / address',self.origin_name,1,width=36)
        ttk.Button(left,text='Search departure',command=lambda:self.search('origin')).grid(row=2,column=0,sticky='ew',pady=(0,10))
        self.entry(left,'Departure coordinates · lat, lon',self.origin_coords,3)
        self.entry(left,'Destination · city / address',self.dest_name,4)
        ttk.Button(left,text='Search destination',command=lambda:self.search('destination')).grid(row=5,column=0,sticky='ew',pady=(0,10))
        self.entry(left,'Destination coordinates · lat, lon',self.dest_coords,6)
        self.entry(left,'Via (optional) · lat lon; lat lon',self.via,7)
        self.pick_mode=tk.StringVar(value='Destination');ttk.Combobox(left,textvariable=self.pick_mode,values=['Destination','Departure'],state='readonly').grid(row=8,column=0,sticky='ew')
        self.label(left,'Click on the map to choose the selected point.','PanelMuted').grid(row=9,column=0,sticky='w',pady=(4,10))
        self.calculate_button=ttk.Button(left,text='Calculate with Valhalla',style='Brand.TButton',command=lambda:self.safe(self.calculate_route));self.calculate_button.grid(row=10,column=0,sticky='ew')
        self.label(left,'Public Valhalla · no API key\nRoute and permit requirements need verification.','PanelMuted',wraplength=310).grid(row=11,column=0,sticky='w',pady=(12,0))
        right=ttk.Frame(self.body,style='App.TFrame');right.grid(row=0,column=1,sticky='nsew');right.columnconfigure(0,weight=1);right.rowconfigure(1,weight=2);right.rowconfigure(2,weight=1)
        d=self.active['loaded'];self.label(right,f"{self.active['vehicle']['name']} · {d['length']:g} × {d['width']:g} × {d['height']:g} m · {d['weight']:g} t",'AppSection',wraplength=710).grid(row=0,column=0,sticky='w',pady=(0,10))
        self.map=Map(right,self.c,HERE/'data'/'tiles',on_pick=self.pick,online=not self.offline,height=285);self.map.grid(row=1,column=0,sticky='nsew')
        result=ttk.Frame(right,style='Panel.TFrame',padding=12);result.grid(row=2,column=0,sticky='nsew',pady=(12,0))
        self.route_tree=self.table(result,[('route','Proposed route',160),('km','km one way',140),('time','Driving (hours)',120)],[(i,(r['name'],f"{r['distance_km']:.2f}",f"{r['hours']:.2f}")) for i,r in enumerate(self.route_results)],3)
        self.route_tree.bind('<<TreeviewSelect>>',self.show_route)
        ttk.Button(result,text='Save delivery',style='Brand.TButton',command=lambda:self.safe(self.transfer)).pack(anchor='e',pady=(10,0))
        if self.route_results:self.route_tree.selection_set('0');self.show_route()

    def pick(self,lat,lon):
        coords=f'{lat:.7f}, {lon:.7f}'
        if self.pick_mode.get()=='Departure':self.origin_coords.set(coords);self.origin_name.set('Departure point on map')
        else:self.dest_coords.set(coords);self.dest_name.set('Delivery point on map')
        self.map.set_content([dict(lat=lat,lon=lon,label=self.pick_mode.get())],fit=False)
    def search(self,target):
        query=self.origin_name.get() if target=='origin' else self.dest_name.get()
        def done(rows):
            if not rows:self.status.set('No results. Enter coordinates or choose a point on the map.');return
            options={f"{i+1}. {p['label']}":p for i,p in enumerate(rows)}
            def choose(values):
                p=options[values['choice']];name=self.origin_name if target=='origin' else self.dest_name;coords=self.origin_coords if target=='origin' else self.dest_coords
                name.set(p['label']);coords.set(f"{p['lat']}, {p['lon']}")
                if hasattr(self,'map') and self.map.winfo_exists():self.map.set_content([dict(p,label='Selected point')])
            Form(self,'Select address',[('choice','Matching addresses',list(options))],{'choice':next(iter(options))},choose,'Confirm the exact access point on the map.')
        from places import search
        self.start_job(lambda:search(query),done)
    def start_job(self,work,done):
        if self.busy:self.status.set('A request is already running.');return
        if self.offline:self.status.set('Offline test mode: external services are disabled.');return
        self.busy=True;self.status.set('Request running…')
        def worker():
            try:self.jobs.put((done,work(),None))
            except Exception as e:self.jobs.put((done,None,str(e)))
        threading.Thread(target=worker,daemon=True).start()
    def poll(self):
        while not self.site_jobs.empty():
            done,result,error=self.site_jobs.get();self.safe(lambda:done(result))
        while not self.jobs.empty():
            done,result,error=self.jobs.get();self.busy=False
            if error:self.status.set(error);messagebox.showerror('Online service',error,parent=self)
            else:self.safe(lambda:done(result))
        self.poll_id=self.after(100,self.poll)
    def calculate_route(self,preliminary=False):
        if self.busy:self.status.set('A request is already running.');return
        if not self.active or (not preliminary and not self.accept.get()):raise ValueError('Confirm the vehicle profile again.')
        origin=coordinates(self.origin_coords.get());destination=coordinates(self.dest_coords.get());via=[]
        if not self.origin_name.get().strip() or not self.dest_name.get().strip():raise ValueError('Enter departure and destination names.')
        for text in self.via.get().split(';'):
            if text.strip():via.append(coordinates(text))
        payload=route_request(origin,destination,self.active['loaded'],via)
        self.route_results=[];self.route_context=None;self.route_tree.delete(*self.route_tree.get_children());self.map.set_content([dict(origin,label='Departure'),dict(destination,label='Delivery')])
        if hasattr(self,'route_details'):self.route_details.configure(text='')
        context={'product':deepcopy(self.state.data['product']),'vehicle':deepcopy(self.active['vehicle']),'loaded':deepcopy(self.active['loaded']),'origin':dict(origin,name=self.origin_name.get()),'destination':dict(destination,name=self.dest_name.get()),'request':payload,'calculated_at':stamp(),'server':self.state.data['server']}
        context['vehicleConfirmed']=self.accept.get()
        generation=self.generation;server=self.state.data['server']
        self.state.data.update(origin_name=self.origin_name.get(),origin_coords=self.origin_coords.get());self.state.save()
        def done(results):
            if self.generation!=generation:self.status.set('Inputs changed during the request. Recalculate the route.');return
            if isinstance(results,dict) and 'routeUnavailable' in results:
                self.site['routeLookup']={'status':'unavailable','detail':results['routeUnavailable']}
                self.status.set(results['routeUnavailable'])
                self.state.save();self.refresh_site_window();return
            self.site['routeLookup']={'status':'ready'}
            context['origin']['name']=self.origin_name.get();context['destination']['name']=self.dest_name.get()
            self.route_results=results;self.route_context=context
            if self.step==2:
                for i,r in enumerate(results):self.route_tree.insert('','end',iid=str(i),values=(r['name'],f"{r['distance_km']:.2f}",f"{r['hours']:.2f}"))
                self.route_tree.selection_set('0');self.show_route()
            self.status.set('Route ready, including the detected ferry crossing.' if any(r.get('ferryDetected') for r in results) else 'Valhalla route ready. Select an option and export Excel. Validate the proposed route.')
        def work():
            try:return routing.route(server,payload)
            except Exception as error:
                if not preliminary:raise
                return {'routeUnavailable':str(error)}
        self.start_job(work,done)
    def show_route(self,*_):
        if not self.route_tree.selection() or not self.route_context:return
        r=self.route_results[int(self.route_tree.selection()[0])];c=self.route_context
        route_key=json.dumps(r,sort_keys=True)
        changed=getattr(self,'site_route_key',None)!=route_key
        if changed:
            self.site_route_key=route_key;self.site_token+=1
            sc.invalidate(self.site,sc.ROUTE_KEYS)
        from route_segments import route_description
        detail=route_description(r)
        sc.automatic(self.site,'transport.distanceKm',r['distance_km'],'Valhalla / OpenStreetMap','CALCULATED',detail=detail)
        if hasattr(self,'route_details'):self.route_details.configure(text=detail)
        sc.automatic(self.site,'transport.maritimeTransport',r.get('maritimeTransport','Unknown'),'Valhalla route ferry evidence' if r.get('maritimeTransport')=='Yes' else 'No reliable maritime evidence in route response','VERIFY')
        self.site['transport']['ferryDetected']=r.get('ferryDetected',False)
        if r.get('ferryDetected'):
            sc.automatic(self.site,'transport.maritimeTransport','Unknown','Valhalla: ferry detected. Confirm marine versus inland crossing.','VERIFY')
        if changed:self.refresh_site_sources()
        sc.recommendation(self.site)
        self.refresh_site_window()
        self.map.set_content([dict(c['origin'],label='Departure'),dict(c['destination'],label='Delivery')],r['geometry'])
    def transfer(self):
        if not self.route_context or not self.route_tree.selection():raise ValueError('Calculate and select a route.')
        route=deepcopy(self.route_results[int(self.route_tree.selection()[0])]);context=deepcopy(self.route_context)
        context['siteConditions']=deepcopy(self.site)
        def save(values):
            row=dict(context,**route,id=uuid.uuid4().hex,quantity=num(values['quantity'],'Delivery quantity',1,True),return_km=num(values['return_km'],'Return'),position_km=num(values['position_km'],'Positioning'),notes=values['notes'])
            used=sum(r['quantity'] for r in self.state.data['deliveries'] if r['product']==context['product'])
            if used+row['quantity']>context['product']['quantity']:raise ValueError('The allocated quantity exceeds the product total. Update saved deliveries or the product quantity.')
            if len(self.state.data['deliveries'])>=100:raise ValueError('Maximum 100 saved deliveries in this version.')
            self.state.data['deliveries'].append(row);self.state.save();self.status.set('Delivery saved. Export Excel directly from Transport.');self.after_idle(self.build)
        used=sum(r['quantity'] for r in self.state.data['deliveries'] if r['product']==context['product'])
        Form(self,'Save delivery',[('quantity','Products for this destination (units)'),('return_km','Empty return per trip (km)'),('position_km','Empty positioning per trip (km)'),('notes','Notes / assumptions')],{'quantity':max(1,context['product']['quantity']-used),'return_km':route['distance_km'],'position_km':0,'notes':'Return equals outbound distance — assumption to confirm.'},save,f"Valhalla distance: {route['distance_km']:.2f} km one way. One product per trip. Return distance is editable and is not a validated return route.")

    def sheet(self):
        win=tk.Toplevel(self);win.title('Saved deliveries');win.geometry('1180x720');win.minsize(960,600);win.transient(self)
        panel=ttk.Frame(win,padding=20);panel.pack(fill='both',expand=True)
        self.label(panel,'Saved transport deliveries','PanelSection').pack(anchor='w');self.label(panel,'Each row is one delivery. One product per trip. Rates apply to all rows.','PanelMuted').pack(anchor='w',pady=(6,16))
        rates=ttk.Frame(panel);rates.pack(fill='x');ratevars={}
        for i,(k,label) in enumerate([('loaded','Loaded EUR/km'),('empty','Empty EUR/km'),('fixed','Fixed EUR/trip · permits etc.'),('markup','Markup (%)'),('vat','VAT (%)')]):
            var=tk.StringVar(value=str(self.state.data['rates'][k]));ratevars[k]=var;self.entry(rates,label,var,0,i,16)
        tree=self.table(panel,[('name','Product / destination',350),('km','route km',90),('qty','Units/trips',95),('empty','empty km/trip',115),('bill','billable km',110),('total','Total EUR',115)],[],8)
        summary=tk.StringVar();ttk.Label(panel,textvariable=summary,font=(FONT,11,'bold')).pack(anchor='e',pady=14)
        bar=ttk.Frame(panel);bar.pack(fill='x')
        def refresh():
            tree.delete(*tree.get_children());total=0;r=self.state.data['rates']
            for row in self.state.data['deliveries']:
                c=calculate(row,r);total+=c['total'];tree.insert('','end',iid=row['id'],values=(row['product']['name']+' → '+row['destination']['name'],f"{row['distance_km']:.2f}",row['quantity'],f"{row['return_km']+row['position_km']:.2f}",f"{c['billable_km']:.2f}",f"{c['total']:.2f}" if r['loaded']>0 else 'Rate missing'))
            summary.set(f'Total: {total:.2f} EUR' if r['loaded']>0 else 'Enter the loaded rate to calculate the price.')
        def save_rates():
            self.state.data['rates']={k:num(v.get(),k) for k,v in ratevars.items()};self.state.save();refresh()
        def edit():
            if not tree.selection():raise ValueError('Select a delivery.')
            row=next(r for r in self.state.data['deliveries'] if r['id']==tree.selection()[0])
            def save(values):
                q=num(values['quantity'],'Quantity',1,True)
                used=sum(r['quantity'] for r in self.state.data['deliveries'] if r['id']!=row['id'] and r['product']==row['product'])
                if used+q>row['product']['quantity']:raise ValueError('Delivery quantities exceed the product total.')
                row.update(quantity=q,return_km=num(values['return_km'],'Return'),position_km=num(values['position_km'],'Positioning'),notes=values['notes']);self.state.save();refresh()
            Form(self,'Delivery assumptions',[('quantity','Products / trips'),('return_km','Empty return (km/trip)'),('position_km','Positioning (km/trip)'),('notes','Notes')],row,save,'Valhalla route distance is retained. Edit empty kilometres separately.')
        def remove():
            if not tree.selection():raise ValueError('Select a delivery.')
            ident=tree.selection()[0];row=next(r for r in self.state.data['deliveries'] if r['id']==ident)
            self.state.data.setdefault('archive',[]).append(row);self.state.data['deliveries']=[r for r in self.state.data['deliveries'] if r['id']!=ident];self.state.save();refresh()
        def restore():
            archived=self.state.data.get('archive',[])
            if not archived:raise ValueError('No archived deliveries.')
            if len(self.state.data['deliveries'])>=100:raise ValueError('Maximum 100 saved deliveries in this version.')
            row=archived[-1];used=sum(r['quantity'] for r in self.state.data['deliveries'] if r['product']==row['product'])
            if used+row['quantity']>row['product']['quantity']:raise ValueError('Cannot restore: quantity is already allocated.')
            self.state.data['deliveries'].append(archived.pop());self.state.save();refresh()
        def export():
            save_rates()
            if not self.state.data['deliveries']:raise ValueError('Save a route before exporting saved deliveries.')
            path=filedialog.asksaveasfilename(parent=win,defaultextension='.xlsx',initialfile='Transport estimate.xlsx',filetypes=[('Excel','*.xlsx')])
            if path:
                from excel_export import export_workbook
                export_workbook(path,self.state.data['deliveries'],self.state.data['rates']);self.status.set('Excel workbook created: '+path)
                messagebox.showinfo('Export Excel','Distances and formulas exported. Yellow cells are editable.',parent=win)
        ttk.Button(bar,text='Apply rates',command=lambda:self.safe(save_rates)).pack(side='left');ttk.Button(bar,text='Edit delivery',command=lambda:self.safe(edit)).pack(side='left',padx=6)
        ttk.Button(bar,text='Archive',command=lambda:self.safe(remove)).pack(side='left');ttk.Button(bar,text='Restore last',command=lambda:self.safe(restore)).pack(side='left',padx=6)
        ttk.Button(bar,text='Export Excel',style='Brand.TButton',command=lambda:self.safe(export)).pack(side='right')
        refresh();return win
    def set_corrosivity_enabled(self,enabled):
        enabled=bool(enabled)
        if enabled==self.site.get('corrosivityEnabled',False):return
        self.corrosion_epoch+=1;self.corrosion_cancel.set();self.corrosion_cancel=threading.Event()
        for name in ('cams_timer','deposition_timer'):
            timer=getattr(self,name)
            if timer:self.after_cancel(timer);setattr(self,name,None)
        self.site['corrosivityEnabled']=enabled
        sc.recommendation(self.site);self.state.save();self.refresh_site_window()
        if enabled:self.refresh_air_quality();self.refresh_deposition()

    def settings(self):
        def save(values):
            from urllib.parse import urlparse
            address=values['server'].strip();parsed=urlparse(address)
            if parsed.scheme not in ('https','http') or not parsed.netloc or parsed.username or parsed.password:raise ValueError('Invalid server address.')
            if parsed.scheme=='http' and parsed.hostname not in ('localhost','127.0.0.1'):raise ValueError('Use HTTPS for external servers.')
            changed=address.rstrip('/')!=self.state.data['server']
            self.state.data['server']=address.rstrip('/')
            self.set_corrosivity_enabled(values['corrosivityEnabled'])
            self.state.save()
            if changed:self.invalidate_route()
        values=dict(self.state.data,corrosivityEnabled=self.site.get('corrosivityEnabled',False))
        year=deposition.reference_year()
        return Form(self,'Application settings',[('server','Valhalla server address'),('corrosivityEnabled',f'Calculate annual corrosivity ({year})','bool')],values,save,
            f'Annual corrosivity is optional and off by default. Enabling it retrieves all 12 months of {year} from Copernicus ADS. A category appears only after the full year is verified. Downloads are cached and resumed; ADS processing may be slow. Disabling stops new submissions and polling; requests already sent may finish on ADS. The result remains an estimate using model proxies. Other destination data loads independently.')

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--offline',action='store_true');parser.add_argument('--state');args=parser.parse_args()
    App(args.state,args.offline).mainloop()
