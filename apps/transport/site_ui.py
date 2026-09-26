"""Compact project conditions editor using the existing Sun Valley widgets."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from copy import deepcopy
import json
import webbrowser
from urllib.parse import quote
from site_visuals import configure_site, MetricCard
from site_overview import rows as summary_rows
from site_conditions import FIELDS,get,badge,apply_manual,recommendation,now

MARINE_WARNING='Marine environment detected. Increased atmospheric corrosivity may apply. Verify salinity, distance from shoreline and exposure conditions according to EN ISO 12944-2.'
MARITIME_WARNING='Maritime transport detected. Verify coating and temporary corrosion protection requirements for marine transport and storage.'

class SiteWindow(tk.Toplevel):
    def __init__(self,app):
        super().__init__(app);self.app=app;self.title('SITE & ENVIRONMENTAL CONDITIONS');self.geometry('1120x820');self.minsize(760,600);self.transient(app)
        self.vars={};self.original={};self.badges={};self.reviews={};self.dirty=False
        self.edit_location=(app.site['destinationAddress'],app.site['destinationCoordinates'])
        self.configure(bg=app.c['background']);configure_site(self,app.c)
        head=ttk.Frame(self,style='Panel.TFrame',padding=(20,12));head.pack(fill='x')
        tk.Label(head,image=app.logo,bg='white').pack(side='left',padx=(0,12))
        titles=ttk.Frame(head,style='Panel.TFrame');titles.pack(side='left')
        ttk.Label(titles,text='FlowerMoon  /  Site & Environment',style='PanelSection.TLabel',font=('Segoe UI',13,'bold')).pack(anchor='w')
        ttk.Label(titles,text='Condițiile amplasamentului · date automate',style='PanelMuted.TLabel').pack(anchor='w',pady=(3,0))
        ttk.Button(head,text='Înapoi la hartă  →',command=self.destroy).pack(side='right')
        context=ttk.Frame(self,style='App.TFrame',padding=(20,12,20,0));context.pack(fill='x')
        self.address=ttk.Label(context,style='AppSection.TLabel',font=('Segoe UI',12,'bold'),wraplength=1000);self.address.pack(anchor='w')
        self.summary=ttk.Label(context,style='AppMuted.TLabel',wraplength=1000);self.summary.pack(anchor='w',pady=(3,10))
        metrics=ttk.Frame(context,style='App.TFrame');metrics.pack(fill='x',pady=(0,12))
        self.metrics={}
        for i,(key,title) in enumerate([('route','RUTĂ & ALTITUDINE'),('temperature','TEMPERATURĂ · MAX / MIN'),('daily','MEDII ZILNICE · MAX / MIN')]):
            metrics.columnconfigure(i,weight=1,uniform='metric')
            card=MetricCard(metrics,app.c,title);card.grid(row=0,column=i,sticky='nsew',padx=(0,10 if i<2 else 0));self.metrics[key]=card
        book=ttk.Notebook(self,style='Site.TNotebook');self.book=book;book.pack(fill='both',expand=True,padx=20)
        overview=ttk.Frame(book,style='Panel.TFrame',padding=12);book.add(overview,text='Privire de ansamblu')
        self.progress=ttk.Label(overview,style='SiteHint.TLabel',wraplength=1000);self.progress.pack(anchor='w',pady=(0,10))
        self.overview=app.table(overview,[('field','Parametru',300),('value','Valoare',200),('status','Sursă / stare',150),('note','Observații',380)],[],15)
        self.overview.configure(style='SiteSummary.Treeview')
        self.overview.bind('<<TreeviewSelect>>',self.overview_detail)
        self.detail=ttk.Label(overview,style='SiteHint.TLabel',wraplength=820);self.detail.pack(anchor='w',pady=(8,0))
        overview.bind('<Configure>',lambda e:[w.configure(wraplength=max(240,e.width-24)) for w in (self.progress,self.detail)])
        for title,groups in [('Transport',('transport',)),('Mediu & climă',('environment','temperature','humidity')),('Seism · zăpadă · vânt',('seismic','snow','wind'))]:
            outer=ttk.Frame(book);book.add(outer,text=title)
            canvas=tk.Canvas(outer,highlightthickness=0,bg=app.c['surface']);canvas.pack(side='left',fill='both',expand=True)
            scroll=ttk.Scrollbar(outer,command=canvas.yview);scroll.pack(side='right',fill='y');canvas.configure(yscrollcommand=scroll.set)
            body=ttk.Frame(canvas,style='Panel.TFrame',padding=16);item=canvas.create_window(0,0,anchor='nw',window=body)
            def resize(e,c=canvas,i=item,b=body):
                c.itemconfigure(i,width=e.width)
                for widget in b.winfo_children():
                    if isinstance(widget,ttk.Label) and int(widget.grid_info().get('columnspan',1))==4:widget.configure(wraplength=max(240,e.width-48))
            canvas.bind('<Configure>',resize)
            body.bind('<Configure>',lambda e,c=canvas:c.configure(scrollregion=c.bbox('all')))
            body.columnconfigure(1,weight=1)
            row=0;previous_group=None
            for key,(label,unit,default,choices) in FIELDS.items():
                if key.split('.')[0] not in groups:continue
                if key.startswith('humidity.value') and get(app.site,key)['value'] is None:continue
                group=key.split('.')[0]
                if group!=previous_group:
                    heading={'transport':'Transport & acces','environment':'Expunere & corozivitate','temperature':'Temperaturi istorice','humidity':'Umiditate atmosferică','seismic':'Acțiune seismică','snow':'Încărcare din zăpadă','wind':'Presiunea vântului'}[group]
                    ttk.Label(body,text=heading,style='PanelSection.TLabel',font=('Segoe UI',11,'bold')).grid(row=row,column=0,columnspan=4,sticky='w',pady=(12,8));row+=1;previous_group=group
                ttk.Label(body,style='Panel.TLabel',text=label+(f' ({unit})' if unit else ''),wraplength=230).grid(row=row,column=0,sticky='w',padx=(0,12),pady=6)
                var=tk.StringVar();self.vars[key]=var
                control=ttk.Combobox(body,textvariable=var,values=choices,state='readonly',width=22) if choices else ttk.Entry(body,textvariable=var,width=24)
                control.grid(row=row,column=1,sticky='ew',pady=6)
                control.bind('<FocusIn>',lambda e,c=canvas,b=body:c.yview_moveto(max(0,e.widget.winfo_y()-25)/max(1,b.winfo_height())))
                status=ttk.Label(body,style='SiteHint.TLabel',wraplength=170);status.grid(row=row,column=2,sticky='w',padx=12);self.badges[key]=status
                review=tk.BooleanVar();self.reviews[key]=review
                ttk.Checkbutton(body,text='Confirm',variable=review).grid(row=row,column=3)
                row+=1
            if title=='Transport':
                text='EXW – Ridicare de la fabrica vânzătorului. Transportul este organizat de cumpărător.\nDistance reuses the selected route; a manual override applies to site data only.\nAltitude: route DEM sample maximum (VERIFY), or destination elevation fallback. See Sources / details for scope. Neither replaces a site survey.'
            elif title=='Mediu & climă':
                text='Date globale, cu sursa și acoperirea afișate. Temperaturile sunt extreme istorice din reanaliză, nu măsurători la amplasament.\nTemperatura și umiditatea: Open-Meteo Historical / ERA5. Umiditatea maximă / medie / minimă se calculează din valorile orare; perioada și acoperirea sunt documentate în observații.\nAltitudine: Copernicus GLO-90. Corozivitatea nu se deduce din coastă; TOW și indicele de corozivitate necesită validarea metodei.'
                ttk.Button(body,text='Exposure checklist / notes',command=self.checklist).grid(row=row,column=0,columnspan=4,sticky='w',pady=8);row+=1
                self.suggestion=ttk.Label(body,style='Panel.TLabel',wraplength=800);self.suggestion.grid(row=row,column=0,columnspan=4,sticky='w',pady=8);row+=1
            else:
                text='Parametrii normativi depind de țară și de standardul proiectului. Hărțile regionale disponibile sunt selectate automat numai în aria lor de acoperire.\nPentru țările fără adaptor, câmpurile rămân disponibile pentru completare manuală. Nu se reutilizează valori din România.'
                self.structural_context=ttk.Label(body,style='PanelMuted.TLabel',wraplength=780)
                self.structural_context.grid(row=row,column=0,columnspan=4,sticky='w',pady=8);row+=1
            ttk.Label(body,text=text,style='SiteHint.TLabel',wraplength=780).grid(row=row,column=0,columnspan=4,sticky='w',pady=12)
        foot=ttk.Frame(self,style='Panel.TFrame',padding=(20,10));foot.pack(fill='x')
        self.warning=ttk.Label(foot,style='SiteHint.TLabel',wraplength=1000,foreground=app.c['warning']);self.warning.pack(anchor='w')
        legend=ttk.Label(foot,style='SiteHint.TLabel',text='Selectează un rând pentru sursă și observații. Modificările manuale sunt disponibile în filele de mai sus.');legend.pack(anchor='w',pady=(4,6))
        self.error=ttk.Label(foot,foreground=app.c['danger'],wraplength=870);self.error.pack(anchor='w')
        bar=ttk.Frame(foot,style='Panel.TFrame');bar.pack(fill='x')
        ttk.Button(bar,text='Surse & detalii',command=self.sources).pack(side='left')
        ttk.Button(bar,text='Actualizează datele',command=lambda:app.refresh_site_sources(force=True)).pack(side='left',padx=6)
        ttk.Button(bar,text='Exportă JSON',command=self.export).pack(side='left')
        self.save_button=ttk.Button(bar,text='Salvează modificările',style='Brand.TButton',command=self.save)
        book.bind('<<NotebookTabChanged>>',lambda e:self.save_button.pack(side='right') if book.index(book.select()) else self.save_button.pack_forget())
        context.bind('<Configure>',lambda e:[w.configure(wraplength=max(240,e.width-32)) for w in (self.address,self.summary)])
        foot.bind('<Configure>',lambda e:[w.configure(wraplength=max(240,e.width-32)) for w in (self.warning,self.error,legend)])
        # Reserve the footer before giving the remaining height to the tabs.
        book.pack_forget();foot.pack_configure(side='bottom');book.pack(fill='both',expand=True,padx=20,pady=(0,12))
        self.compact=None
        def adapt(event):
            if event.widget is not self:return
            compact=event.height<700
            if compact==self.compact:return
            self.compact=compact
            if compact:
                metrics.pack_forget();legend.pack_forget()
            else:
                metrics.pack(fill='x',pady=(0,12));legend.pack(after=self.warning,anchor='w',pady=(4,6))
        self.bind('<Configure>',adapt,add='+')
        self.refresh()
    def refresh(self):
        site=self.app.site
        self.address.configure(text='Destinație  /  '+(site['destinationAddress'] or 'Alege destinația pe hartă'))
        for key,var in self.vars.items():
            f=get(site,key);text='' if f['value'] is None else str(f['value'])
            if key not in self.original or var.get()==self.original[key]:var.set(text);self.original[key]=text
            self.badges[key].configure(text=badge(f))
        def pair(a,b):return ' / '.join('—' if get(site,k)['value'] is None else f"{get(site,k)['value']:+g}" for k in (a,b))+' °C'
        alt=get(site,'transport.maxAltitudeM')['value'];dist=get(site,'transport.distanceKm')['value']
        altitude_label='Altitudine destinație' if 'destination elevation' in get(site,'transport.maxAltitudeM')['source'] else 'Max. eșantionat pe rută'
        self.summary.configure(text='Plecare: '+site['departureAddress'])
        self.metrics['route'].set(f'{dist:,.1f} km' if dist is not None else '— km',f'{altitude_label}: {alt:g} m' if alt is not None else 'Altitudine indisponibilă')
        def provenance(keys):
            fields=[get(site,k) for k in keys]
            if any(f.get('reviewRequired') for f in fields):return 'Modificat manual · de verificat'
            if any(f.get('manualOverride') for f in fields):return 'Valori modificate manual'
            climate=site.get('climate',{})
            if climate.get('status')=='ready':return climate['periodStart'][:4]+'–'+climate['periodEnd'][:4]+' · '+climate['source']
            return 'Se încarcă datele…' if climate.get('status')=='loading' else 'Date istorice indisponibile'
        for card,keys in [('temperature',('temperature.maxDesign','temperature.minDesign')),('daily',('temperature.maxDailyAverage','temperature.minDailyAverage'))]:
            self.metrics[card].set(pair(*keys),provenance(keys))
        suggestion=get(site,'environment.suggestedCorrosivity');self.suggestion.configure(text='Categorie de corozivitate: '+str(suggestion['value'] or 'fără estimare automată; metodă nevalidată'))
        warnings=[]
        if get(site,'environment.marineEnvironment')['value'] in ('Yes','Possible'):warnings.append(MARINE_WARNING)
        if get(site,'transport.maritimeTransport')['value']=='Yes':warnings.append(MARITIME_WARNING)
        elif site['transport'].get('ferryDetected'):warnings.append('Ferry detected on route. Confirm whether this is maritime or an inland crossing; verify temporary transport/storage protection.')
        self.warning.configure(text='\n'.join(warnings))
        geo=site.get('locationContext',{}).get('geography',{})
        standards=', '.join(str(site[g].get('standard')) for g in ('seismic','snow','wind') if site[g].get('standard'))
        self.structural_context.configure(text='Țară / teritoriu: '+str(geo.get('name') or 'neconfirmat')+' · Hărți disponibile: '+(standards or 'niciun adaptor aplicabil'))
        self.refresh_overview()
    def refresh_overview(self):
        site=self.app.site
        self.progress.configure(text=site.get('lookupState','Valorile implicite sunt completate. Alegeți punctul de livrare pentru datele zonei.'))
        climate=site.get('climate',{})
        climate_status=climate.get('status')
        climate_note='Climă: se descarcă și se verifică seria istorică…' if climate_status=='loading' else 'Climă: indisponibilă; nu se folosesc temperaturi implicite.' if climate_status=='unavailable' else ('Climă: '+climate['periodStart']+' – '+climate['periodEnd']+' · '+climate['source']) if climate_status=='ready' else ''
        if climate_note:self.progress.configure(text=self.progress.cget('text')+'\n'+climate_note)
        if site.get('routeLookup',{}).get('status')=='unavailable':self.progress.configure(text=self.progress.cget('text')+'\nRută rutieră indisponibilă · datele amplasamentului sunt independente.')
        humidity=site.get('humidityAnalysis',{})
        if humidity.get('status')=='loading':self.progress.configure(text=self.progress.cget('text')+'\nUmiditate: se descarcă seria orară…')
        elif humidity.get('status')=='ready':self.progress.configure(text=self.progress.cget('text')+'\nUmiditate: '+humidity['periodStart']+' – '+humidity['periodEnd']+' · '+humidity.get('source','Sursă nespecificată')+' · valori orare')
        elif humidity.get('status')=='unavailable':self.progress.configure(text=self.progress.cget('text')+'\nUmiditate: sursă indisponibilă; reîncercați Actualizează datele.')
        selected=self.overview.selection();scroll=self.overview.yview()
        self.overview.delete(*self.overview.get_children());self.overview_sources={}
        for tag,bg,fg in [('even',self.app.c['surface'],self.app.c['text']),('odd',self.app.c['raised'],self.app.c['text']),('section',self.app.c['selection'],self.app.c['primary'])]:
            self.overview.tag_configure(tag,background=bg,foreground=fg)
        self.overview.tag_configure('section',font=('Segoe UI',10,'bold'))
        for index,row in enumerate(summary_rows(site)):
            tag='section' if row['section'] else 'odd' if index%2 else 'even'
            self.overview.insert('','end',iid=row['key'],values=(row['label'],row['value'],row['status'],row['note']),tags=(tag,))
            self.overview_sources[row['key']]=row['note']+'\n'+row['detail']
        if selected and self.overview.exists(selected[0]):self.overview.selection_set(selected[0]);self.overview_detail()
        if scroll:self.overview.yview_moveto(scroll[0])
    def overview_detail(self,*_):
        selection=self.overview.selection()
        if selection:self.detail.configure(text=self.overview_sources.get(selection[0],'')[:260])
    def save(self):
        try:
            changes={k:v.get() for k,v in self.vars.items() if v.get()!=self.original[k] or self.reviews[k].get()}
            location=(self.app.site['destinationAddress'],self.app.site['destinationCoordinates'])
            if changes and location!=self.edit_location:
                if not messagebox.askyesno('Review required','The destination changed while editing. Apply these edits to the current destination?',parent=self):return False
            apply_manual(self.app.site,changes,[k for k,v in self.reviews.items() if v.get()]);recommendation(self.app.site)
            self.app.state.save()
            self.edit_location=location
            for k in changes:self.original[k]=self.vars[k].get();self.reviews[k].set(False)
            self.refresh();self.error.configure(text='Saved');return True
        except (ValueError,OSError) as e:self.error.configure(text=str(e));return False
    def sources(self):
        win=tk.Toplevel(self);win.title('Sources and verification');win.geometry('850x600')
        area=tk.Text(win,wrap='word',padx=16,pady=16);area.pack(fill='both',expand=True)
        for key in FIELDS:
            f=get(self.app.site,key);area.insert('end',f"{FIELDS[key][0]}: {f['value']} {f.get('unit','')}\n{badge(f)} · {f['source']}\n{f.get('detail','')}\nUpdated: {f['lastUpdated']}\n\n")
        area.insert('end','\nCONTEXT ȘI ACOPERIRE\n'+json.dumps(self.app.site.get('locationContext',{}),ensure_ascii=False,indent=2))
        area.insert('end','\nCOASTĂ\n'+json.dumps(self.app.site.get('coastalDistance',{}),ensure_ascii=False,indent=2))
        area.insert('end','\nPROVENIENȚĂ CLIMATICĂ\n'+json.dumps(self.app.site.get('climate',{}),ensure_ascii=False,indent=2))
        area.insert('end','\nUMIDITATE\n'+json.dumps(self.app.site.get('humidityAnalysis',{}),ensure_ascii=False,indent=2))
        area.insert('end','\nALTITUDINE COPERNICUS\n'+json.dumps(self.app.site.get('elevationAnalysis',{}),ensure_ascii=False,indent=2))
        area.configure(state='disabled')
    def checklist(self):
        from app import Form
        data=self.app.site['exposureChecklist'];initial={k:f['value'] for k,f in data.items()}
        def save(values):
            for k,v in values.items():
                if v!=initial[k]:data[k].update(value=v,source='manual',status='MANUAL',manualOverride=True,lastUpdated=now(),reviewRequired=False)
            self.app.state.save()
        Form(self.app,'Exposure checklist',[(k,k+(' · Review required' if f.get('reviewRequired') else '')) for k,f in data.items()],initial,save,'Record measured/project evidence and source. Unknown means manual confirmation required.')
    def export(self):
        if not self.save():return
        path=filedialog.asksaveasfilename(parent=self,defaultextension='.json',initialfile='site-conditions.json',filetypes=[('JSON','*.json')])
        if path:
            from pathlib import Path
            Path(path).write_text(json.dumps(self.app.site,ensure_ascii=False,indent=2),encoding='utf-8')
