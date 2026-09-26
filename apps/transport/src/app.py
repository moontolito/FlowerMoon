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
from site_ui import SiteWindow

class Form(tk.Toplevel):
    def __init__(self,app,title,fields,values,save,help_text=''):
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
            widget=ttk.Checkbutton(cell,text='Da',variable=var) if kind=='bool' else ttk.Combobox(cell,textvariable=var,values=kind,state='readonly') if isinstance(kind,list) else ttk.Entry(cell,textvariable=var)
            widget.pack(fill='x');widget.bind('<FocusIn>',lambda e:canvas.yview_moveto(max(0,e.widget.master.winfo_y()-30)/max(1,body.winfo_height())),add='+')
        foot=ttk.Frame(self,padding=16);foot.grid(row=2,column=0,sticky='ew');self.error=tk.StringVar()
        ttk.Label(foot,textvariable=self.error,foreground=app.c['danger'],wraplength=730).pack(anchor='w',pady=(0,8))
        ttk.Button(foot,text='Salvează',style='Brand.TButton',command=self.submit).pack(side='right');ttk.Button(foot,text='Anulează',command=self.destroy).pack(side='right',padx=8)
        self.bind('<Escape>',lambda e:self.destroy());self.grab_set()
    def submit(self):
        try:self.save({k:v.get() for k,v in self.vars.items()})
        except (ValueError,OSError) as e:self.error.set(str(e));return
        self.destroy()

class App(tk.Tk):
    def __init__(self,path=None,offline=False):
        super().__init__();self.title('FlowerMoon • Transport simplu');self.geometry('1320x840+20+20');self.minsize(1120,700)
        self.icons=[create_icon(self,n) for n in (16,32,48)];self.iconphoto(True,*self.icons)
        self.logo_original=tk.PhotoImage(file=str(HERE/'assets'/'FlowerMoonLogo.png'));self.logo=self.logo_original.subsample(8,8)
        self.state=State(path or HERE/'data'/'planning.json');self.offline=offline;self.mode='light';self.step=1
        self.active=None;self.matches=[];self.route_results=[];self.route_context=None;self.busy=False;self.jobs=queue.Queue();self.site_jobs=queue.Queue();self.generation=0
        self.product_vars={k:tk.StringVar(value=str(v)) for k,v in self.state.data['product'].items()}
        for v in self.product_vars.values():v.trace_add('write',self.invalidate)
        self.origin_name=tk.StringVar(value=self.state.data['origin_name']);self.origin_coords=tk.StringVar(value=self.state.data['origin_coords'])
        self.site=self.state.data['siteConditions'];self.site_window=None;self.site_timer=None;self.site_token=0;self.site_cache={};self.site_inflight=set();self.climate_inflight=set();self.humidity_inflight=set()
        self.dest_name=tk.StringVar(value=self.site['destinationAddress']);self.dest_coords=tk.StringVar(value=self.site['destinationCoordinates']);self.via=tk.StringVar()
        for v in (self.origin_name,self.origin_coords,self.dest_name,self.dest_coords,self.via):v.trace_add('write',self.invalidate_route)
        for v in (self.origin_name,self.origin_coords,self.dest_name,self.dest_coords):v.trace_add('write',self.site_location_changed)
        self.accept=tk.BooleanVar(value=False);self.status=tk.StringVar(value='Introduceți produsul, apoi apăsați „Recomandă vehicul”.');self.build()
        self.poll_id=self.after(100,self.poll);self.protocol('WM_DELETE_WINDOW',self.close)

    def site_location_changed(self,*_):
        sc.sync(self.site,self.origin_name.get(),self.dest_name.get(),self.origin_coords.get(),self.dest_coords.get())
        self.site['lookupState']='Se actualizează datele zonei alese…' if self.dest_coords.get() else 'Alegeți adresa din căutare sau punctul de livrare pe hartă.'
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
        try:
            destination=coordinates(self.dest_coords.get())
            site_service.apply_context(self.site,site_service.context(destination))
            sc.apply_zoning(self.site,standards.lookup(destination,sc.get(self.site,'environment.siteAltitudeM')['value']))
        except ValueError:pass
        if self.site_window and self.site_window.winfo_exists():self.refresh_site_window();self.site_window.lift();return self.site_window
        self.site_window=SiteWindow(self);self.refresh_humidity();self.refresh_climate();self.refresh_site_sources();return self.site_window
    def refresh_site_window(self):
        if self.site_window and self.site_window.winfo_exists():self.site_window.refresh()
    def refresh_site_sources(self,force=False):
        if force:self.refresh_climate(force=True);self.refresh_humidity(force=True)
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
            if 'siteAltitude' in result:sc.automatic(self.site,'environment.siteAltitudeM',result['siteAltitude'],result.get('siteAltitudeSource','Sursă nespecificată'),'VERIFY',detail=result.get('siteAltitudeDetail',''))
            if 'elevationAnalysis' in result:self.site['elevationAnalysis']=result['elevationAnalysis']
            if 'locationContext' in result:site_service.apply_context(self.site,result['locationContext'])
            if 'coastalDistance' in result:self.site['coastalDistance']=result['coastalDistance']
            if 'zoning' in result:sc.apply_zoning(self.site,result['zoning'])
            self.site['lookupState']='Consultarea automată s-a încheiat. Valorile indisponibile și observațiile sunt marcate în rezumat.'
            sc.recommendation(self.site);self.state.save();self.refresh_site_window()
        if key in self.site_cache:done(self.site_cache[key]);return
        if (key,token) in self.site_inflight:return
        self.site_inflight.add((key,token));self.site['lookupState']='Se verifică automat altitudinea și expunerea marină…';self.refresh_site_window()
        def worker():
            try:result=site_sources.lookup(server,destination,geometry)
            except Exception as error:result={'error':str(error)}
            self.site_jobs.put((done,result,None))
        threading.Thread(target=worker,daemon=True).start()
    def refresh_humidity(self,force=False):
        if self.offline:return
        try:destination=coordinates(self.dest_coords.get())
        except ValueError:return
        location=(self.dest_name.get(),self.dest_coords.get())
        if location in self.humidity_inflight:return
        existing=self.site.get('humidityAnalysis',{})
        if not force and existing.get('status')=='unavailable':return
        if not force and existing.get('status')=='ready' and existing.get('methodVersion')==humidity.VERSION and existing.get('periodEnd')==climate.period()[1].isoformat():return
        self.humidity_inflight.add(location);self.site['humidityAnalysis']={'status':'loading'};self.refresh_site_window()
        def done(result):
            self.humidity_inflight.discard(location)
            if location!=(self.dest_name.get(),self.dest_coords.get()):return
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
        location=(self.dest_name.get(),self.dest_coords.get())
        if location in self.climate_inflight:return
        existing=self.site.get('climate',{})
        if not force and existing.get('status')=='unavailable':return
        if not force and existing.get('status')=='ready' and existing.get('methodVersion')==climate.VERSION and existing.get('periodEnd')==climate.period()[1].isoformat():return
        self.climate_inflight.add(location);self.site['climate']={'status':'loading'};self.refresh_site_window()
        def done(result):
            self.climate_inflight.discard(location)
            if location!=(self.dest_name.get(),self.dest_coords.get()):return
            if 'error' in result:self.site['climate']={'status':'unavailable','message':result['error']}
            else:climate.apply(self.site,result)
            self.state.save();self.refresh_site_window()
        def worker():
            try:result=climate.lookup(destination,self.state.path.parent/'climate-cache',force=force)
            except Exception as error:result={'error':str(error)}
            self.site_jobs.put((done,result,None))
        threading.Thread(target=worker,daemon=True).start()
    def close(self):
        if self.site_timer:self.after_cancel(self.site_timer);self.site_timer=None
        sc.sync(self.site,self.origin_name.get(),self.dest_name.get(),self.origin_coords.get(),self.dest_coords.get())
        self.state.data.update(origin_name=self.origin_name.get(),origin_coords=self.origin_coords.get())
        try:self.state.save()
        except OSError as e:messagebox.showerror('Salvare nereușită',str(e),parent=self);return
        if self.poll_id:self.after_cancel(self.poll_id);self.poll_id=None
        self.destroy()
    def safe(self,fn):
        try:return fn()
        except (ValueError,OSError) as e:self.status.set(str(e));messagebox.showerror('Verificați datele',str(e),parent=self)
    def label(self,parent,text,kind='Panel',**kw):return ttk.Label(parent,text=text,style=kind+'.TLabel',**kw)
    def invalidate(self,*_):
        self.active=None;self.matches=[];self.accept.set(False) if hasattr(self,'accept') else None;self.invalidate_route()
        if hasattr(self,'vehicle_tree') and self.vehicle_tree.winfo_exists():self.vehicle_tree.delete(*self.vehicle_tree.get_children())
        if hasattr(self,'selection_text'):self.selection_text.set('Date modificate. Apăsați „Recomandă vehicul” pentru o evaluare nouă.')
    def invalidate_route(self,*_):
        if hasattr(self,'site'):
            self.site_token+=1;self.site_route_key=None
            sc.invalidate(self.site,sc.ROUTE_KEYS);self.refresh_site_window()
        self.generation+=1;self.route_results=[];self.route_context=None
        if hasattr(self,'route_tree') and self.route_tree.winfo_exists():self.route_tree.delete(*self.route_tree.get_children())
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
        brand=ttk.Frame(header,style='Panel.TFrame');brand.pack(side='left');self.label(brand,'FlowerMoon','PanelSection').pack(anchor='w');self.label(brand,'TRANSPORT SIMPLU','PanelMuted').pack(anchor='w')
        ttk.Button(header,text='Temă '+('luminoasă' if self.mode=='light' else 'întunecată'),command=self.theme).pack(side='right')
        ttk.Button(header,text='Site & Environment',command=self.open_site).pack(side='right',padx=6)
        ttk.Button(header,text='Vehicule',command=self.fleet).pack(side='right',padx=8);ttk.Button(header,text='Setări',command=self.settings).pack(side='right')
        nav=ttk.Frame(self,style='App.TFrame',padding=(24,14));nav.grid(row=1,column=0,sticky='ew')
        for n,name in [(1,'1. Produs și vehicul'),(2,'2. Rută și calcul')]:ttk.Button(nav,text=name,style='Brand.TButton' if n==self.step else 'TButton',command=lambda s=n:self.safe(lambda:self.navigate(s))).pack(side='left',padx=(0,12))
        ttk.Button(nav,text=f"Foaie de calcul ({len(self.state.data['deliveries'])})",command=self.sheet).pack(side='right')
        self.body=ttk.Frame(self,style='App.TFrame',padding=(24,0,24,16));self.body.grid(row=2,column=0,sticky='nsew');self.body.columnconfigure(1,weight=1);self.body.rowconfigure(0,weight=1)
        if self.step==1:self.product_page()
        else:self.route_page()
        foot=ttk.Frame(self,style='Panel.TFrame',padding=(20,10));foot.grid(row=3,column=0,sticky='ew')
        ttk.Label(foot,textvariable=self.status,style='PanelMuted.TLabel',wraplength=1220).pack(anchor='w')
    def theme(self):self.mode='dark' if self.mode=='light' else 'light';self.build()
    def navigate(self,step):
        if step==2:
            if not self.active:raise ValueError('Introduceți produsul și selectați mai întâi un vehicul compatibil.')
            if not self.accept.get():raise ValueError('Confirmați ipotezele vehiculului înainte de rutare.')
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
        self.label(left,'Ce transportăm?','PanelSection').grid(row=0,column=0,columnspan=2,sticky='w',pady=(0,6))
        self.label(left,'Dimensiunile unui singur produs.','PanelMuted').grid(row=1,column=0,columnspan=2,sticky='w',pady=(0,18))
        for i,(key,label) in enumerate([('name','Nume produs'),('quantity','Cantitate (buc.)'),('length','Lungime (m)'),('width','Lățime (m)'),('height','Înălțime (m)'),('weight','Masă / produs (t)')]):self.entry(left,label,self.product_vars[key],2+i//2,i%2,16)
        self.label(left,'Exemplu din Excel: 9 × 3 × 3,3 m,\naproximativ 7 t. Măsurați produsul real.','PanelMuted',wraplength=330).grid(row=5,column=0,columnspan=2,sticky='w',pady=(4,16))
        ttk.Button(left,text='Recomandă vehicul',style='Brand.TButton',command=lambda:self.safe(self.find_vehicle)).grid(row=6,column=0,columnspan=2,sticky='ew')
        self.label(left,'Prima versiune: un produs pe cursă.\nFără stivuire sau console calculate automat.','PanelMuted',wraplength=330).grid(row=7,column=0,columnspan=2,sticky='w',pady=(24,0))
        right=ttk.Frame(self.body,style='Panel.TFrame',padding=20);right.grid(row=0,column=1,sticky='nsew')
        self.label(right,'Vehiculul potrivit pentru produs','PanelSection').pack(anchor='w',pady=(0,6))
        self.label(right,'Comparăm capacitatea și dimensiunile. Preferăm înălțimea încărcată mai mică.','PanelMuted',wraplength=710).pack(anchor='w',pady=(0,16))
        self.vehicle_tree=self.table(right,[('name','Vehicul',210),('fit','Potrivire',160),('height','H total (m)',100),('weight','Total (t)',85)],[],5)
        self.vehicle_tree.bind('<<TreeviewSelect>>',self.select_vehicle)
        self.selection_text=tk.StringVar(value='Apăsați „Recomandă vehicul” pentru a compara profilurile salvate.')
        ttk.Label(right,textvariable=self.selection_text,style='Panel.TLabel',wraplength=700,justify='left').pack(anchor='w',fill='x',pady=18)
        ttk.Checkbutton(right,text='Accept ipotezele afișate pentru o rută preliminară.',variable=self.accept).pack(anchor='w',pady=(0,12))
        ttk.Button(right,text='Continuă la rută →',style='Brand.TButton',command=lambda:self.safe(lambda:self.navigate(2))).pack(anchor='e')
        if self.matches:self.populate_matches()

    def find_vehicle(self):
        p=product({k:v.get() for k,v in self.product_vars.items()});self.matches=recommend(p,self.state.data['vehicles']);self.accept.set(False)
        self.state.data['product']=p;self.state.save();self.populate_matches()
        self.status.set('Alegeți un vehicul și verificați ipotezele încărcării.')
    def populate_matches(self):
        selected=next((str(i) for i,r in enumerate(self.matches) if r==self.active),'0')
        self.vehicle_tree.delete(*self.vehicle_tree.get_children())
        for i,r in enumerate(self.matches):
            label='Compatibil provizoriu' if r['fits'] else 'Nu încape / depășire'
            if i==0 and r['fits']:label='Recomandat provizoriu'
            self.vehicle_tree.insert('','end',iid=str(i),values=(r['vehicle']['name']+(' · exemplu' if r['vehicle']['example'] else ''),label,f"{r['loaded']['height']:.2f}",f"{r['loaded']['weight']:.2f}"))
        if self.matches:self.vehicle_tree.selection_set(selected);self.select_vehicle()
        else:self.selection_text.set('Adăugați un profil din butonul Vehicule.');self.active=None
    def select_vehicle(self,*_):
        ids=self.vehicle_tree.selection()
        if not ids:return
        r=self.matches[int(ids[0])];selected=deepcopy(r) if r['fits'] else None
        if selected!=self.active:self.accept.set(False);self.invalidate_route()
        self.active=selected
        if not r['fits']:
            self.selection_text.set('Acest vehicul nu este potrivit:\n'+'\n'.join(r['reasons'])+'\n\nDacă niciun profil nu se potrivește, este necesar un vehicul special. Adăugați datele transportatorului în Vehicule.');return
        d=r['loaded'];v=r['vehicle']
        self.selection_text.set(f"Ansamblu încărcat: {d['length']:g} × {d['width']:g} × {d['height']:g} m\nMasă totală: {d['weight']:g} t · {d['axle_count']} axe · maximum {d['axle_load']:g} t/axă\n\n"+('PROFIL EXEMPLU — valorile nu descriu un vehicul verificat.\n' if v['example'] else '')+v['notes']+'\nConfirmați sprijinirea, fixarea și sarcinile reale pe axe cu transportatorul.')

    def fleet(self):
        win=tk.Toplevel(self);win.title('Vehicule disponibile');win.geometry('1000x470');win.transient(self)
        frame=ttk.Frame(win,padding=18);frame.pack(fill='both',expand=True)
        self.label(frame,'Profiluri editabile · lățimea acceptată se confirmă de transportator','PanelSection').pack(anchor='w',pady=(0,16))
        tree=self.table(frame,[('name','Vehicul',240),('deck','Platformă L (m)',130),('width','Marfă l (m)',110),('payload','Utilă (t)',110),('source','Tip',180)],[(v['id'],(v['name'],v['deck_length'],v['load_width'],v['payload'],'Exemplu' if v['example'] else 'Date utilizator')) for v in self.state.data['vehicles']])
        bar=ttk.Frame(frame);bar.pack(fill='x',pady=(16,0))
        def edit(new=False):
            if not new and not tree.selection():return
            initial={} if new else deepcopy(next(v for v in self.state.data['vehicles'] if v['id']==tree.selection()[0]))
            def save(values):
                v=vehicle(dict(initial,**values));existing=[x for x in self.state.data['vehicles'] if x['id']!=v['id']];self.state.data['vehicles']=existing+[v];self.state.save();self.invalidate();self.step=1;win.destroy();self.after_idle(self.build)
            Form(self,'Profil vehicul',VEHICLE_FIELDS+[('example','Profil ilustrativ, neconfirmat','bool'),('notes','Sursă / ipoteze / fixare')],initial,save,'Datele trebuie să descrie ansamblul real. Sarcina pe axă depinde de încărcătura curentă. Nu măriți limitele doar pentru a obține o potrivire.')
        ttk.Button(bar,text='Vehicul nou',command=lambda:edit(True)).pack(side='left');ttk.Button(bar,text='Editează selectat',command=edit).pack(side='left',padx=10);ttk.Button(bar,text='Închide',command=win.destroy).pack(side='right')

    def route_page(self):
        left=ttk.Frame(self.body,style='Panel.TFrame',padding=18);left.grid(row=0,column=0,sticky='ns',padx=(0,16))
        self.label(left,'Unde livrăm?','PanelSection').grid(row=0,column=0,sticky='w',pady=(0,12))
        self.entry(left,'Plecare · localitate / adresă',self.origin_name,1,width=36)
        ttk.Button(left,text='Caută plecarea',command=lambda:self.search('origin')).grid(row=2,column=0,sticky='ew',pady=(0,10))
        self.entry(left,'Coordonate plecare · lat, lon',self.origin_coords,3)
        self.entry(left,'Destinație · localitate / adresă',self.dest_name,4)
        ttk.Button(left,text='Caută destinația',command=lambda:self.search('destination')).grid(row=5,column=0,sticky='ew',pady=(0,10))
        self.entry(left,'Coordonate destinație · lat, lon',self.dest_coords,6)
        self.entry(left,'Via (opțional) · lat lon; lat lon',self.via,7)
        self.pick_mode=tk.StringVar(value='Destinație');ttk.Combobox(left,textvariable=self.pick_mode,values=['Destinație','Plecare'],state='readonly').grid(row=8,column=0,sticky='ew')
        self.label(left,'Clic pe hartă: alege punctul de mai sus.','PanelMuted').grid(row=9,column=0,sticky='w',pady=(4,10))
        self.calculate_button=ttk.Button(left,text='Calculează cu Valhalla',style='Brand.TButton',command=lambda:self.safe(self.calculate_route));self.calculate_button.grid(row=10,column=0,sticky='ew')
        self.label(left,'Valhalla public · fără cheie API\nRezultatul necesită verificarea traseului și AST.','PanelMuted',wraplength=310).grid(row=11,column=0,sticky='w',pady=(12,0))
        right=ttk.Frame(self.body,style='App.TFrame');right.grid(row=0,column=1,sticky='nsew');right.columnconfigure(0,weight=1);right.rowconfigure(1,weight=2);right.rowconfigure(2,weight=1)
        d=self.active['loaded'];self.label(right,f"{self.active['vehicle']['name']} · {d['length']:g} × {d['width']:g} × {d['height']:g} m · {d['weight']:g} t",'AppSection',wraplength=710).grid(row=0,column=0,sticky='w',pady=(0,10))
        self.map=Map(right,self.c,HERE/'data'/'tiles',on_pick=self.pick,online=not self.offline,height=285);self.map.grid(row=1,column=0,sticky='nsew')
        result=ttk.Frame(right,style='Panel.TFrame',padding=12);result.grid(row=2,column=0,sticky='nsew',pady=(12,0))
        self.route_tree=self.table(result,[('route','Rută propusă',160),('km','km sens unic',140),('time','Condus (ore)',120)],[(i,(r['name'],f"{r['distance_km']:.2f}",f"{r['hours']:.2f}")) for i,r in enumerate(self.route_results)],3)
        self.route_tree.bind('<<TreeviewSelect>>',self.show_route)
        ttk.Button(result,text='Trimite distanța în foaia de calcul',style='Brand.TButton',command=lambda:self.safe(self.transfer)).pack(anchor='e',pady=(10,0))
        if self.route_results:self.route_tree.selection_set('0');self.show_route()

    def pick(self,lat,lon):
        coords=f'{lat:.7f}, {lon:.7f}'
        if self.pick_mode.get()=='Plecare':self.origin_coords.set(coords);self.origin_name.set('Punct de plecare pe hartă')
        else:self.dest_coords.set(coords);self.dest_name.set('Punct de livrare pe hartă')
        self.map.set_content([dict(lat=lat,lon=lon,label=self.pick_mode.get())],fit=False)
    def search(self,target):
        query=self.origin_name.get() if target=='origin' else self.dest_name.get()
        def done(rows):
            if not rows:self.status.set('Niciun rezultat. Introduceți coordonatele sau alegeți punctul pe hartă.');return
            options={f"{i+1}. {p['label']}":p for i,p in enumerate(rows)}
            def choose(values):
                p=options[values['choice']];name=self.origin_name if target=='origin' else self.dest_name;coords=self.origin_coords if target=='origin' else self.dest_coords
                name.set(p['label']);coords.set(f"{p['lat']}, {p['lon']}")
                if hasattr(self,'map') and self.map.winfo_exists():self.map.set_content([dict(p,label='Punct ales')])
            Form(self,'Alege adresa',[('choice','Rezultate găsite',list(options))],{'choice':next(iter(options))},choose,'Confirmați punctul exact de acces pe hartă.')
        self.start_job(lambda:routing.geocode(query),done)
    def start_job(self,work,done):
        if self.busy:self.status.set('O cerere este deja în curs.');return
        if self.offline:self.status.set('Mod test offline: serviciile externe sunt dezactivate.');return
        self.busy=True;self.status.set('Se calculează… puteți continua după primirea rezultatului.')
        def worker():
            try:self.jobs.put((done,work(),None))
            except Exception as e:self.jobs.put((done,None,str(e)))
        threading.Thread(target=worker,daemon=True).start()
    def poll(self):
        while not self.site_jobs.empty():
            done,result,error=self.site_jobs.get();self.safe(lambda:done(result))
        while not self.jobs.empty():
            done,result,error=self.jobs.get();self.busy=False
            if error:self.status.set(error);messagebox.showerror('Serviciu online',error,parent=self)
            else:self.safe(lambda:done(result))
        self.poll_id=self.after(100,self.poll)
    def calculate_route(self,preliminary=False):
        if self.busy:self.status.set('O cerere este deja în curs.');return
        if not self.active or (not preliminary and not self.accept.get()):raise ValueError('Reconfirmați profilul vehiculului în pasul 1.')
        origin=coordinates(self.origin_coords.get());destination=coordinates(self.dest_coords.get());via=[]
        if not self.origin_name.get().strip() or not self.dest_name.get().strip():raise ValueError('Completați denumirile plecării și destinației.')
        for text in self.via.get().split(';'):
            if text.strip():via.append(coordinates(text))
        payload=route_request(origin,destination,self.active['loaded'],via)
        self.route_results=[];self.route_context=None;self.route_tree.delete(*self.route_tree.get_children());self.map.set_content([dict(origin,label='Plecare'),dict(destination,label='Livrare')])
        context={'product':deepcopy(self.state.data['product']),'vehicle':deepcopy(self.active['vehicle']),'loaded':deepcopy(self.active['loaded']),'origin':dict(origin,name=self.origin_name.get()),'destination':dict(destination,name=self.dest_name.get()),'request':payload,'calculated_at':stamp(),'server':self.state.data['server']}
        context['vehicleConfirmed']=self.accept.get()
        generation=self.generation;server=self.state.data['server']
        self.state.data.update(origin_name=self.origin_name.get(),origin_coords=self.origin_coords.get());self.state.save()
        def done(results):
            if self.generation!=generation:self.status.set('Datele s-au schimbat în timpul cererii. Recalculați ruta.');return
            if isinstance(results,dict) and 'routeUnavailable' in results:
                self.site['routeLookup']={'status':'unavailable','detail':results['routeUnavailable']}
                self.status.set('Rută rutieră indisponibilă. Datele amplasamentului se încarcă independent.')
                self.state.save();self.refresh_site_window();return
            self.site['routeLookup']={'status':'ready'}
            self.route_results=results;self.route_context=context
            if self.step==2:
                for i,r in enumerate(results):self.route_tree.insert('','end',iid=str(i),values=(r['name'],f"{r['distance_km']:.2f}",f"{r['hours']:.2f}"))
                self.route_tree.selection_set('0');self.show_route()
            self.status.set('Rută Valhalla calculată. Alegeți varianta și trimiteți distanța în foaia de calcul. Traseu de validat.')
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
        sc.automatic(self.site,'transport.distanceKm',r['distance_km'],'Valhalla · selected road route','CALCULATED')
        sc.automatic(self.site,'transport.maritimeTransport',r.get('maritimeTransport','Unknown'),'Valhalla route ferry evidence' if r.get('maritimeTransport')=='Yes' else 'No reliable maritime evidence in route response','VERIFY')
        self.site['transport']['ferryDetected']=r.get('ferryDetected',False)
        if r.get('ferryDetected'):
            sc.automatic(self.site,'transport.maritimeTransport','Unknown','Valhalla: ferry detected. Confirm marine versus inland crossing.','VERIFY')
        if changed:self.refresh_site_sources()
        sc.recommendation(self.site)
        self.refresh_site_window()
        self.map.set_content([dict(c['origin'],label='Plecare'),dict(c['destination'],label='Livrare')],r['geometry'])
    def transfer(self):
        if not self.route_context or not self.route_tree.selection():raise ValueError('Calculați și selectați o rută.')
        route=deepcopy(self.route_results[int(self.route_tree.selection()[0])]);context=deepcopy(self.route_context)
        context['siteConditions']=deepcopy(self.site)
        def save(values):
            row=dict(context,**route,id=uuid.uuid4().hex,quantity=num(values['quantity'],'Cantitate livrare',1,True),return_km=num(values['return_km'],'Retur'),position_km=num(values['position_km'],'Poziționare'),notes=values['notes'])
            used=sum(r['quantity'] for r in self.state.data['deliveries'] if r['product']==context['product'])
            if used+row['quantity']>context['product']['quantity']:raise ValueError('Cantitatea alocată acestui produs depășește totalul. Modificați alocările din foaia de calcul sau cantitatea produsului.')
            if len(self.state.data['deliveries'])>=100:raise ValueError('Prima versiune acceptă maximum 100 livrări pe foaie.')
            self.state.data['deliveries'].append(row);self.state.save();self.status.set('Distanța a fost transferată. Deschideți Foaie de calcul pentru tarife și export.');self.after_idle(self.build)
        used=sum(r['quantity'] for r in self.state.data['deliveries'] if r['product']==context['product'])
        Form(self,'Trimite în foaia de calcul',[('quantity','Produse pentru această destinație (buc.)'),('return_km','Retur gol per cursă (km)'),('position_km','Poziționare goală per cursă (km)'),('notes','Note / ipoteze')],{'quantity':max(1,context['product']['quantity']-used),'return_km':route['distance_km'],'position_km':0,'notes':'Retur egal cu dusul — ipoteză de confirmat.'},save,f"Distanță Valhalla: {route['distance_km']:.2f} km sens unic. Un produs pe cursă. Returul este editabil; nu îl presupunem traseu validat.")

    def sheet(self):
        win=tk.Toplevel(self);win.title('Foaie de calcul transport');win.geometry('1180x720');win.minsize(960,600);win.transient(self)
        panel=ttk.Frame(win,padding=20);panel.pack(fill='both',expand=True)
        self.label(panel,'Distanțe în calculul de transport','PanelSection').pack(anchor='w');self.label(panel,'Fiecare rând este o livrare. Un produs pe cursă. Tarifele se aplică tuturor rândurilor.','PanelMuted').pack(anchor='w',pady=(6,16))
        rates=ttk.Frame(panel);rates.pack(fill='x');ratevars={}
        for i,(k,label) in enumerate([('loaded','EUR/km încărcat'),('empty','EUR/km gol'),('fixed','Fixe EUR/cursă · AST etc.'),('markup','Adaos (%)'),('vat','TVA (%)')]):
            var=tk.StringVar(value=str(self.state.data['rates'][k]));ratevars[k]=var;self.entry(rates,label,var,0,i,16)
        tree=self.table(panel,[('name','Produs / destinație',350),('km','km rută',90),('qty','Buc./curse',95),('empty','km goi/cursă',115),('bill','km facturați',110),('total','Total EUR',115)],[],8)
        summary=tk.StringVar();ttk.Label(panel,textvariable=summary,font=(FONT,11,'bold')).pack(anchor='e',pady=14)
        bar=ttk.Frame(panel);bar.pack(fill='x')
        def refresh():
            tree.delete(*tree.get_children());total=0;r=self.state.data['rates']
            for row in self.state.data['deliveries']:
                c=calculate(row,r);total+=c['total'];tree.insert('','end',iid=row['id'],values=(row['product']['name']+' → '+row['destination']['name'],f"{row['distance_km']:.2f}",row['quantity'],f"{row['return_km']+row['position_km']:.2f}",f"{c['billable_km']:.2f}",f"{c['total']:.2f}" if r['loaded']>0 else 'Tarif lipsă'))
            summary.set(f'Total: {total:.2f} EUR' if r['loaded']>0 else 'Completați tariful încărcat înainte de calcularea prețului.')
        def save_rates():
            self.state.data['rates']={k:num(v.get(),k) for k,v in ratevars.items()};self.state.save();refresh()
        def edit():
            if not tree.selection():raise ValueError('Selectați o livrare.')
            row=next(r for r in self.state.data['deliveries'] if r['id']==tree.selection()[0])
            def save(values):
                q=num(values['quantity'],'Cantitate',1,True)
                used=sum(r['quantity'] for r in self.state.data['deliveries'] if r['id']!=row['id'] and r['product']==row['product'])
                if used+q>row['product']['quantity']:raise ValueError('Cantitatea livrărilor depășește totalul produsului.')
                row.update(quantity=q,return_km=num(values['return_km'],'Retur'),position_km=num(values['position_km'],'Poziționare'),notes=values['notes']);self.state.save();refresh()
            Form(self,'Ipoteze livrare',[('quantity','Produse / curse'),('return_km','Retur gol (km/cursă)'),('position_km','Poziționare (km/cursă)'),('notes','Note')],row,save,'Distanța calculată de Valhalla este păstrată. Editați separat kilometrii goi.')
        def remove():
            if not tree.selection():raise ValueError('Selectați o livrare.')
            ident=tree.selection()[0];row=next(r for r in self.state.data['deliveries'] if r['id']==ident)
            self.state.data.setdefault('archive',[]).append(row);self.state.data['deliveries']=[r for r in self.state.data['deliveries'] if r['id']!=ident];self.state.save();refresh()
        def restore():
            archived=self.state.data.get('archive',[])
            if not archived:raise ValueError('Nu există livrări arhivate.')
            if len(self.state.data['deliveries'])>=100:raise ValueError('Prima versiune acceptă maximum 100 livrări pe foaie.')
            row=archived[-1];used=sum(r['quantity'] for r in self.state.data['deliveries'] if r['product']==row['product'])
            if used+row['quantity']>row['product']['quantity']:raise ValueError('Nu se poate restaura: cantitatea este deja alocată.')
            self.state.data['deliveries'].append(archived.pop());self.state.save();refresh()
        def export():
            save_rates()
            if not self.state.data['deliveries']:raise ValueError('Trimiteți o rută în foaia de calcul înainte de export.')
            path=filedialog.asksaveasfilename(parent=win,defaultextension='.xlsx',initialfile='Calcul transport.xlsx',filetypes=[('Excel','*.xlsx')])
            if path:
                from excel_export import export_workbook
                export_workbook(path,self.state.data['deliveries'],self.state.data['rates']);self.status.set('Foaia Excel a fost creată: '+path)
                messagebox.showinfo('Export Excel','Distanțele și formulele au fost exportate. Celulele galbene sunt editabile.',parent=win)
        ttk.Button(bar,text='Aplică tarife',command=lambda:self.safe(save_rates)).pack(side='left');ttk.Button(bar,text='Editează livrarea',command=lambda:self.safe(edit)).pack(side='left',padx=6)
        ttk.Button(bar,text='Arhivează',command=lambda:self.safe(remove)).pack(side='left');ttk.Button(bar,text='Restaurează ultima',command=lambda:self.safe(restore)).pack(side='left',padx=6)
        ttk.Button(bar,text='Exportă Excel',style='Brand.TButton',command=lambda:self.safe(export)).pack(side='right')
        refresh();return win
    def settings(self):
        def save(values):
            from urllib.parse import urlparse
            p=urlparse(values['server'])
            if p.scheme not in ('https','http') or not p.netloc:raise ValueError('Adresă server invalidă.')
            self.state.data['server']=values['server'].rstrip('/');self.state.save();self.invalidate_route()
        Form(self,'Setări Valhalla',[('server','Adresă server')],self.state.data,save,'Serverul public funcționează fără cheie API și are limite de utilizare. Pentru distribuirea aplicației, anunțați operatorii; pentru utilizare intensă configurați un server propriu. Nu se transmit numele produselor, doar coordonatele și parametrii camionului.')

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--offline',action='store_true');parser.add_argument('--state');args=parser.parse_args()
    App(args.state,args.offline).mainloop()
