"""Map-first presentation; existing routing, fleet, pricing and export stay shared."""
from app import App,Form,HERE,LIGHT,DARK,FONT,configure,sv_ttk,tk,ttk,messagebox,deepcopy
from domain import product,recommend,evaluate,num,coordinates
from map_widget import Map

class Planner(App):
    def __init__(self,*args,**kwargs):
        self.panel='route';self.ready=False;self.manual=False
        super().__init__(*args,**kwargs)
        self.title('FlowerMoon • Transport');self.minsize(1000,700)
        for name,coords in ((self.origin_name,self.origin_coords),(self.dest_name,self.dest_coords)):
            name.trace_add('write',lambda *_,c=coords:c.set(''))
        self.ready=True;self.choose_recommended();self.status.set('Alegeți destinația, apoi calculați ruta.')

    def build(self):
        for w in self.winfo_children():w.destroy()
        self.step=2;self.c=LIGHT if self.mode=='light' else DARK
        sv_ttk.set_theme(self.mode,self);configure(self,self.c)
        self.configure(bg=self.c['background']);self.columnconfigure(0,weight=1)
        self.rowconfigure(1,weight=1);self.rowconfigure(2,weight=0)
        header=ttk.Frame(self,style='Panel.TFrame',padding=(20,10));header.grid(row=0,column=0,sticky='ew')
        tk.Label(header,image=self.logo,bg='white').pack(side='left',padx=(0,12))
        self.label(header,'FlowerMoon  /  Transport','PanelSection').pack(side='left')
        menu=tk.Menu(self,tearoff=False)
        menu.add_command(label='Vehicule și preseturi',command=self.fleet)
        menu.add_command(label='Coordonate / puncte intermediare',command=self.location_details)
        menu.add_command(label='Temă luminoasă / întunecată',command=self.theme)
        menu.add_command(label='Setări Valhalla',command=self.settings)
        ttk.Button(header,text='Mai multe ···',command=lambda:menu.tk_popup(self.winfo_rootx()+self.winfo_width()-220,self.winfo_rooty()+70)).pack(side='right')
        ttk.Button(header,text='Site & Environment',command=self.open_site).pack(side='right',padx=6)
        ttk.Button(header,text=f"Foaie de calcul · {len(self.state.data['deliveries'])}",command=self.sheet).pack(side='right',padx=8)
        workspace=ttk.Frame(self,style='App.TFrame',padding=(12,12,12,8));workspace.grid(row=1,column=0,sticky='nsew')
        workspace.columnconfigure(1,weight=1);workspace.rowconfigure(0,weight=1)
        side=ttk.Frame(workspace,style='Panel.TFrame',width=360);side.grid(row=0,column=0,sticky='ns',padx=(0,12));side.grid_propagate(False)
        side.columnconfigure(0,weight=1);side.rowconfigure(1,weight=1)
        tabs=ttk.Frame(side,style='Panel.TFrame',padding=16);tabs.grid(row=0,column=0,sticky='ew')
        for key,label in [('route','Rută'),('vehicle','Vehicul')]:
            ttk.Button(tabs,text=label,style='Brand.TButton' if self.panel==key else 'TButton',command=lambda k=key:self.set_panel(k)).pack(side='left',expand=True,fill='x',padx=3)
        canvas=tk.Canvas(side,bg=self.c['surface'],highlightthickness=0);canvas.grid(row=1,column=0,sticky='nsew')
        scroll=ttk.Scrollbar(side,command=canvas.yview);scroll.grid(row=1,column=1,sticky='ns');canvas.configure(yscrollcommand=scroll.set)
        body=ttk.Frame(canvas,style='Panel.TFrame',padding=(18,0,18,16));item=canvas.create_window(0,0,anchor='nw',window=body)
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width));body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        body.bind('<MouseWheel>',lambda e:canvas.yview_scroll(-1 if e.delta>0 else 1,'units'))
        self.sidebar=body
        if self.panel=='route':self.route_controls(body)
        else:self.vehicle_controls(body)
        action=ttk.Frame(side,style='Panel.TFrame',padding=16);action.grid(row=2,column=0,columnspan=2,sticky='ew')
        self.calculate_button=ttk.Button(action,text='Calculează ruta  →',style='Brand.TButton',command=lambda:self.safe(self.calculate_route));self.calculate_button.pack(fill='x')
        right=ttk.Frame(workspace,style='App.TFrame');right.grid(row=0,column=1,sticky='nsew');right.columnconfigure(0,weight=1);right.rowconfigure(0,weight=1)
        mapbox=ttk.Frame(right);mapbox.grid(row=0,column=0,sticky='nsew');mapbox.columnconfigure(0,weight=1);mapbox.rowconfigure(0,weight=1)
        self.map=Map(mapbox,self.c,HERE/'data'/'tiles',on_pick=self.pick,online=not self.offline);self.map.grid(row=0,column=0,sticky='nsew')
        tools=ttk.Frame(mapbox,padding=6);tools.place(relx=1,x=-14,y=14,anchor='ne')
        ttk.Button(tools,text='+',width=3,command=lambda:self.map.change_zoom(1)).pack()
        ttk.Button(tools,text='−',width=3,command=lambda:self.map.change_zoom(-1)).pack(pady=4)
        self.pick_mode=tk.StringVar(value='Destinație')
        ttk.Combobox(tools,textvariable=self.pick_mode,values=['Destinație','Plecare'],state='readonly',width=12).pack()
        self.label(tools,'Clic pe hartă','PanelMuted').pack(pady=(4,0))
        self.results_panel=ttk.Frame(right,style='Panel.TFrame',padding=14)
        self.route_tree=self.table(self.results_panel,[('route','Variante',170),('km','Distanță · km',140),('time','Condus · ore',130)],[(i,(r['name'],f"{r['distance_km']:.1f}",f"{r['hours']:.1f}")) for i,r in enumerate(self.route_results)],3)
        self.route_tree.bind('<<TreeviewSelect>>',self.show_route)
        ttk.Button(self.results_panel,text='Trimite în foaia de calcul  →',style='Brand.TButton',command=lambda:self.safe(self.transfer)).pack(anchor='e',pady=(10,0))
        if self.route_results:self.results_panel.grid(row=1,column=0,sticky='ew',pady=(10,0));self.route_tree.selection_set('0');self.show_route()
        else:self.place_markers()
        foot=ttk.Frame(self,style='Panel.TFrame',padding=(18,8));foot.grid(row=2,column=0,sticky='ew')
        self.label(foot,'Rută preliminară · verificare transportator / AST','PanelMuted').pack(side='right')
        ttk.Label(foot,textvariable=self.status,style='PanelMuted.TLabel',wraplength=550).pack(side='left')

    def set_panel(self,panel):self.panel=panel;self.build()
    def section(self,parent,text):self.label(parent,text,'PanelSection').pack(anchor='w',pady=(12,6))
    def route_controls(self,parent):
        for key,title,var in [('origin','A  Plecare',self.origin_name),('destination','B  Destinație',self.dest_name)]:
            self.label(parent,title,'PanelMuted').pack(anchor='w',pady=(8,4))
            row=ttk.Frame(parent,style='Panel.TFrame');row.pack(fill='x')
            entry=ttk.Entry(row,textvariable=var);entry.pack(side='left',fill='x',expand=True)
            entry.bind('<Return>',lambda e,k=key:self.search(k))
            ttk.Button(row,text='Caută',command=lambda k=key:self.search(k)).pack(side='right',padx=(6,0))
        ttk.Button(parent,text='Puncte exacte / via',command=self.location_details).pack(anchor='w',pady=(8,0))
        self.section(parent,'Ce transportăm?')
        p=self.state.data['product']
        row=ttk.Frame(parent,style='Panel.TFrame');row.pack(fill='x')
        self.label(row,p['name'],'PanelSection',wraplength=180).pack(side='left')
        ttk.Button(row,text='Modifică',command=self.edit_product).pack(side='right')
        self.label(parent,f"{p['length']:g} × {p['width']:g} × {p['height']:g} m   ·   {p['weight']:g} t",'PanelMuted').pack(anchor='w',pady=(4,8))
        self.section(parent,'Tip transport')
        self.preset_picker(parent)
        self.truck(parent,compact=True)
        self.label(parent,self.profile_summary(),'PanelMuted',wraplength=290).pack(anchor='w',pady=(0,8))
        ttk.Button(parent,text='Ajustează vehiculul  →',command=lambda:self.set_panel('vehicle')).pack(fill='x')

    def preset_picker(self,parent):
        self.preset_ids={self.preset_title(v):v['id'] for v in self.state.data['vehicles']}
        selected=self.preset_title(self.active['vehicle']) if self.active else ''
        self.preset_var=tk.StringVar(value=selected)
        combo=ttk.Combobox(parent,textvariable=self.preset_var,values=list(self.preset_ids),state='readonly');combo.pack(fill='x',pady=(0,8))
        combo.bind('<<ComboboxSelected>>',lambda e:self.select_preset(self.preset_ids[self.preset_var.get()]))
    def preset_title(self,v):
        return {'example-0':'Ușor · platformă','example-1':'Standard · semiremorcă','example-2':'Agabaritic · trailer jos'}.get(v['id'],v['name'])
    def profile_summary(self):
        if not self.active:return 'Niciun vehicul compatibil. Modificați produsul sau profilul.'
        d=self.active['loaded'];return f"{d['length']:g} × {d['width']:g} × {d['height']:g} m  ·  {d['weight']:g} t\n"+('Personalizat · ' if self.manual else '')+('Profil exemplu' if self.active['vehicle']['example'] else 'Profil utilizator')
    def choose_recommended(self):
        matches=recommend(self.state.data['product'],self.state.data['vehicles'])
        self.active=deepcopy(next((r for r in matches if r['fits']),None));self.manual=False;self.accept.set(False);self.invalidate_route();self.build()
    def select_preset(self,ident):
        v=next(v for v in self.state.data['vehicles'] if v['id']==ident)
        result=evaluate(self.state.data['product'],v)
        self.active=deepcopy(result) if result['fits'] else None;self.manual=False;self.accept.set(False);self.invalidate_route();self.build()
        self.status.set('Preset aplicat. Dimensiunile includ produsul.' if result['fits'] else 'Produs incompatibil: '+ '; '.join(result['reasons']))
    def vehicle_controls(self,parent):
        self.section(parent,'Vehiculul încărcat');self.preset_picker(parent);self.truck(parent)
        if not self.active:
            self.label(parent,self.profile_summary(),'PanelMuted',wraplength=290).pack();ttk.Button(parent,text='Recomandă după produs',command=self.choose_recommended).pack(pady=16);return
        self.label(parent,'Dimensiuni totale, cu produsul inclus.','PanelMuted').pack(anchor='w',pady=(0,12))
        self.slider_vars={}
        for key,label,unit,lo,hi in [('length','Lungime','m',1,30),('width','Lățime','m',1,6),('height','Înălțime','m',1,6),('weight','Masă totală','t',1,80),('axle_load','Maxim pe axă','t',1,20),('axle_count','Număr de axe','',2,12)]:
            row=ttk.Frame(parent,style='Panel.TFrame');row.pack(fill='x',pady=(0,3))
            self.label(row,label,'PanelMuted').pack(side='left');self.label(row,unit,'PanelMuted').pack(side='right')
            var=tk.StringVar(value=f"{self.active['loaded'][key]:g}");self.slider_vars[key]=var
            entry=ttk.Entry(row,textvariable=var,width=7);entry.pack(side='right',padx=6)
            scale=ttk.Scale(parent,from_=lo,to=max(hi,self.active['loaded'][key]),value=self.active['loaded'][key],command=lambda value,v=var,k=key:v.set(str(round(float(value),0 if k=='axle_count' else 2))))
            scale.pack(fill='x',pady=(0,12));entry.bind('<Return>',lambda e:self.safe(self.apply_sliders))
        ttk.Button(parent,text='Aplică ajustările',command=lambda:self.safe(self.apply_sliders)).pack(fill='x')
        ttk.Button(parent,text='Refă recomandarea după produs',command=self.choose_recommended).pack(fill='x',pady=8)
    def apply_sliders(self):
        if not self.active:raise ValueError('Selectați un vehicul compatibil.')
        d={k:num(v.get(),k,.001,k=='axle_count') for k,v in self.slider_vars.items()}
        base=evaluate(self.state.data['product'],self.active['vehicle'])['loaded']
        for key in ('length','width','height','weight'):
            if d[key]<base[key]:raise ValueError(f'{key}: valoarea nu poate fi sub ansamblul calculat ({base[key]:g}). Modificați produsul sau datele reale din Vehicule.')
        if d['weight']>self.active['vehicle']['gross']:raise ValueError('Masa depășește capacitatea tehnică a vehiculului.')
        if d['axle_load']>d['weight'] or d['axle_load']*d['axle_count']<d['weight']:raise ValueError('Sarcina pe axă nu este compatibilă cu masa totală.')
        self.active['loaded']=d;self.manual=True;self.accept.set(False);self.invalidate_route();self.build();self.status.set('Ajustări aplicate. Ruta trebuie recalculată.')
    def truck(self,parent,compact=False):
        cv=tk.Canvas(parent,height=80 if compact else 145,bg=self.c['surface'],highlightthickness=0);cv.pack(fill='x',pady=(4,8))
        c=self.c;cv.create_rectangle(42,44,226,80,fill=c['selection'],outline=c['primary'],width=2)
        cv.create_polygon(230,59,260,59,277,77,277,93,230,93,fill=c['primary'],outline=c['primary'])
        cv.create_rectangle(241,64,256,76,fill=c['surface'],outline='')
        cv.create_line(34,87,278,87,fill=c['secondary'],width=3)
        for x in (61,82,200,219,257):cv.create_oval(x-6,86,x+6,98,fill=c['text'],outline=c['surface'],width=2)
        if self.active:
            d=self.active['loaded'];cv.create_text(134,63,text=f"{d['weight']:g} t",fill=c['primary'],font=(FONT,12,'bold'))
            if not compact:
                cv.create_line(35,118,278,118,arrow='both',fill=c['secondary']);cv.create_text(157,133,text=f"L {d['length']:g} m  ·  l {d['width']:g} m",fill=c['secondary'],font=(FONT,10))
                cv.create_line(22,42,22,97,arrow='both',fill=c['primary']);cv.create_text(150,23,text=f"Înălțime totală {d['height']:g} m",fill=c['primary'],font=(FONT,10,'bold'))
        if compact:cv.move('all',0,-20)
    def edit_product(self):
        def save(values):
            self.state.data['product']=product(values);self.state.save()
            for k,v in self.state.data['product'].items():self.product_vars[k].set(str(v))
            self.after_idle(self.choose_recommended)
        Form(self,'Produsul transportat',[('name','Nume produs'),('quantity','Cantitate'),('length','Lungime (m)'),('width','Lățime (m)'),('height','Înălțime (m)'),('weight','Masă / produs (t)')],self.state.data['product'],save,'Dimensiunile unui singur produs. Recomandăm automat vehiculul după salvare.')
    def location_details(self):
        def save(v):
            if v['origin']:coordinates(v['origin'])
            if v['destination']:coordinates(v['destination'])
            for point in v['via'].split(';'):
                if point.strip():coordinates(point)
            self.origin_coords.set(v['origin']);self.dest_coords.set(v['destination']);self.via.set(v['via']);self.place_markers()
        Form(self,'Puncte exacte',[('origin','Plecare · lat, lon'),('destination','Destinație · lat, lon'),('via','Via · lat lon; lat lon')],dict(origin=self.origin_coords.get(),destination=self.dest_coords.get(),via=self.via.get()),save,'Opțional: folosiți coordonate sau alegeți punctele prin clic pe hartă.')
    def place_markers(self):
        markers=[]
        for label,value in [('A',self.origin_coords.get()),('B',self.dest_coords.get())]:
            try:markers.append(dict(coordinates(value),label=label))
            except ValueError:pass
        self.map.set_content(markers,fit=len(markers)>1)
    def pick(self,lat,lon):
        name,coords=(self.origin_name,self.origin_coords) if self.pick_mode.get()=='Plecare' else (self.dest_name,self.dest_coords)
        name.set('Punct ales pe hartă');coords.set(f'{lat:.7f}, {lon:.7f}');self.place_markers();self.status.set('Punct ales. Puteți calcula ruta.')
    def invalidate_route(self,*args):
        super().invalidate_route(*args)
        if hasattr(self,'results_panel') and self.results_panel.winfo_exists():self.results_panel.grid_remove()
    def calculate_route(self):
        if self.busy:return
        if self.panel=='vehicle' and hasattr(self,'slider_vars') and self.active:
            if any(abs(num(v.get(),k,.001)-self.active['loaded'][k])>.00001 for k,v in self.slider_vars.items()):raise ValueError('Aplicați ajustările vehiculului înainte de calcul.')
        if not self.active:raise ValueError('Niciun vehicul compatibil. Modificați produsul sau alegeți un profil.')
        if not self.origin_coords.get():self.search('origin');return
        if not self.dest_coords.get():self.search('destination');return
        if not self.accept.get():
            if not messagebox.askyesno('Confirmă vehiculul',self.profile_summary()+'\n\n'+self.active['vehicle']['notes']+'\n\nFolosiți aceste valori pentru o rută preliminară?',parent=self):return
            self.accept.set(True)
        super().calculate_route()
    def start_job(self,work,done):
        def finished(result):
            done(result)
            if self.route_results:self.results_panel.grid(row=1,column=0,sticky='ew',pady=(10,0))
            if not self.route_results:self.status.set('Punct găsit. Confirmați adresa din lista de rezultate.')
        super().start_job(work,finished)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--offline',action='store_true');parser.add_argument('--state');args=parser.parse_args()
    Planner(args.state,args.offline).mainloop()
