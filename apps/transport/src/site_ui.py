"""Read-only destination overview using the existing Sun Valley widgets."""
import tkinter as tk
from tkinter import ttk, filedialog
import json
from site_visuals import configure_site
from site_overview import display_rows, provenance
from site_conditions import get

MARINE_WARNING='Marine environment detected. Increased atmospheric corrosivity may apply. Verify salinity, distance from shoreline and exposure conditions according to EN ISO 12944-2.'
MARITIME_WARNING='Maritime transport detected. Verify coating and temporary corrosion protection requirements for marine transport and storage.'

class SiteWindow(tk.Toplevel):
    def __init__(self,app):
        super().__init__(app);self.app=app;self.title('SITE & ENVIRONMENTAL CONDITIONS');self.geometry('1120x820');self.minsize(760,600);self.transient(app)
        self.configure(bg=app.c['background']);configure_site(self,app.c)
        head=ttk.Frame(self,style='Panel.TFrame',padding=(20,12));head.pack(fill='x')
        tk.Label(head,image=app.logo,bg='white').pack(side='left',padx=(0,12))
        titles=ttk.Frame(head,style='Panel.TFrame');titles.pack(side='left')
        ttk.Label(titles,text='FlowerMoon  /  Site & Environment',style='PanelSection.TLabel',font=('Segoe UI',13,'bold')).pack(anchor='w')
        ttk.Label(titles,text='Environmental data for the delivery destination',style='PanelMuted.TLabel').pack(anchor='w',pady=(3,0))
        ttk.Button(head,text='Back to map  →',command=self.destroy).pack(side='right')
        context=ttk.Frame(self,style='App.TFrame',padding=(20,12,20,0));context.pack(fill='x')
        self.address=ttk.Label(context,style='AppSection.TLabel',font=('Segoe UI',12,'bold'),wraplength=1000);self.address.pack(anchor='w')
        self.summary=ttk.Label(context,style='AppMuted.TLabel',wraplength=1000);self.summary.pack(anchor='w',pady=(3,10))
        book=ttk.Notebook(self,style='Site.TNotebook');self.book=book;book.pack(fill='both',expand=True,padx=20)
        overview=ttk.Frame(book,style='Panel.TFrame',padding=12);book.add(overview,text='Overview')
        self.progress=ttk.Label(overview,style='SiteHint.TLabel',wraplength=1000);self.progress.pack(anchor='w',pady=(0,10))
        self.overview=app.table(overview,[('field','Parameter',265),('value','Value',190),('unit','Unit',85),('source','Source',210),('meaning','Meaning / use',340),('status','Status',105)],[],15)
        self.overview.configure(style='SiteSummary.Treeview',show='tree headings')
        self.overview.column('#0',width=40,minwidth=40,stretch=False,anchor='center')
        self.overview.heading('#0',text='')
        self.overview.bind('<Button-1>',self.toggle_at_pointer)
        self.overview.bind('<space>',self.toggle_selected)
        self.overview.bind('<<TreeviewOpen>>',self.sync_group_controls)
        self.overview.bind('<<TreeviewClose>>',self.sync_group_controls)
        self.overview.bind('<<TreeviewSelect>>',self.overview_detail)
        self.overview.bind('<Double-1>',self.open_value_at_pointer)
        self.overview.bind('<Return>',lambda e:self.value_details())
        self.detail=ttk.Label(overview,style='SiteHint.TLabel',wraplength=820)
        # Reserve source details before allocating remaining space to the table.
        self.detail.pack(before=self.overview.master,side='bottom',fill='x',pady=(8,0))
        overview.bind('<Configure>',lambda e:[w.configure(wraplength=max(240,e.width-24)) for w in (self.progress,self.detail)])
        foot=ttk.Frame(self,style='Panel.TFrame',padding=(20,10));foot.pack(fill='x')
        self.warning=ttk.Label(foot,style='SiteHint.TLabel',wraplength=1000,foreground=app.c['warning']);self.warning.pack(anchor='w')
        legend=ttk.Label(foot,style='SiteHint.TLabel',text='+ expands national parameters or corrosivity inputs. Select a row for its meaning; double-click for sources and formulas.');legend.pack(anchor='w',pady=(4,6))
        self.error=ttk.Label(foot,foreground=app.c['danger'],wraplength=870);self.error.pack(anchor='w')
        bar=ttk.Frame(foot,style='Panel.TFrame');bar.pack(fill='x')
        self.value_button=ttk.Button(bar,text='Value details',command=self.value_details,state='disabled');self.value_button.pack(side='left',padx=(0,6))
        ttk.Button(bar,text='Sources & location details',command=self.sources).pack(side='left')
        ttk.Button(bar,text='Settings',command=app.settings).pack(side='left',padx=6)
        ttk.Button(bar,text='Refresh data',command=lambda:app.refresh_site_sources(force=True)).pack(side='left',padx=6)
        ttk.Button(bar,text='Export JSON',command=self.export).pack(side='left')
        context.bind('<Configure>',lambda e:[w.configure(wraplength=max(240,e.width-32)) for w in (self.address,self.summary)])
        foot.bind('<Configure>',lambda e:[w.configure(wraplength=max(240,e.width-32)) for w in (self.warning,self.error,legend)])
        # Reserve the footer before giving the remaining height to the tabs.
        book.pack_forget();foot.pack_configure(side='bottom');book.pack(fill='both',expand=True,padx=20,pady=(0,12))
        self.refresh()
    def refresh(self):
        site=self.app.site
        self.address.configure(text='Destination  /  '+(site['destinationAddress'] or 'Choose the destination on the map'))
        self.summary.configure(text='Destination coordinates (WGS84): '+(site['destinationCoordinates'] or 'Not selected')+' · All environmental and structural data below refers to this delivery point.')
        warnings=[]
        if get(site,'environment.marineEnvironment')['value'] in ('Yes','Possible'):warnings.append(MARINE_WARNING)
        if get(site,'transport.maritimeTransport')['value']=='Yes':warnings.append(MARITIME_WARNING)
        elif site['transport'].get('ferryDetected'):warnings.append('Ferry detected on route. Confirm whether this is maritime or an inland crossing; verify temporary transport/storage protection.')
        self.warning.configure(text='\n'.join(warnings))
        self.refresh_overview()
    def refresh_overview(self):
        site=self.app.site
        self.progress.configure(text=site.get('lookupState','Choose the delivery destination to load site data.'))
        climate=site.get('climate',{})
        climate_status=climate.get('status')
        climate_note='Climate: downloading and checking historical data…' if climate_status=='loading' else 'Climate unavailable; no default temperatures are substituted.' if climate_status=='unavailable' else ('Climate: '+climate['periodStart']+' – '+climate['periodEnd']+' · '+climate['source']) if climate_status=='ready' else ''
        if climate_note:self.progress.configure(text=self.progress.cget('text')+'\n'+climate_note)
        if site.get('routeLookup',{}).get('status')=='unavailable':self.progress.configure(text=self.progress.cget('text')+'\nRoad route unavailable · destination data loads independently.')
        humidity=site.get('humidityAnalysis',{})
        if humidity.get('status')=='loading':self.progress.configure(text=self.progress.cget('text')+'\nHumidity: downloading hourly data…')
        elif humidity.get('status')=='ready':self.progress.configure(text=self.progress.cget('text')+'\nHumidity: '+humidity['periodStart']+' – '+humidity['periodEnd']+' · '+humidity.get('source','Source not specified')+' · hourly values')
        elif humidity.get('status')=='unavailable':self.progress.configure(text=self.progress.cget('text')+'\nHumidity: source unavailable; retry Refresh data.')
        air=site.get('airQuality',{}) if site.get('corrosivityEnabled',False) else {}
        if air.get('status') in ('loading','queued','running'):
            self.progress.configure(text=self.progress.cget('text')+'\nCAMS: preparing atmospheric exposure data…')
        elif air.get('status')=='unavailable':
            self.progress.configure(text=self.progress.cget('text')+'\nCAMS: '+air.get('message','Data unavailable.'))
        dep=site.get('deposition',{}) if site.get('corrosivityEnabled',False) else {}
        if dep.get('status') in ('loading','queued','running','unavailable'):
            self.progress.configure(text=self.progress.cget('text')+'\n'+dep.get('message','CAMS deposition data pending.'))
        selected=self.overview.selection();scroll=self.overview.yview()
        expanded={key for key in getattr(self,'overview_groups',()) if self.overview.exists(key) and self.overview.item(key,'open')}
        self.overview.delete(*self.overview.get_children());self.overview_sources={};self.overview_urls={};self.overview_meanings={}
        self.overview_groups=set()
        for tag,bg,fg in [('even',self.app.c['surface'],self.app.c['text']),('odd',self.app.c['raised'],self.app.c['text']),('section',self.app.c['selection'],self.app.c['primary'])]:
            self.overview.tag_configure(tag,background=bg,foreground=fg)
        self.overview.tag_configure('section',font=('Segoe UI',10,'bold'))
        self.overview.tag_configure('estimate',background=self.app.c['warning_bg'],foreground=self.app.c['warning'])
        self.overview.tag_configure('category',font=('Segoe UI',10,'bold'))
        from dataset_explanations import table_value
        for index,row in enumerate(display_rows(site)):
            tag='section' if row['section'] else 'odd' if index%2 else 'even'
            if row['key']=='environment.suggestedCorrosivity':tag='estimate'
            if site.get('deposition',{}).get('qualityFlags') and row['key'] in ('deposition.wet','deposition.total','deposition.chlorideTotalProxy'):tag='estimate'
            group=row.get('expandable',False);parent=row.get('parent','')
            if group:self.overview_groups.add(row['key'])
            self.overview.insert(parent,'end',iid=row['key'],text=('−' if row['key'] in expanded else '+') if group else '',
                open=row['key'] in expanded,values=(('    ' if parent else '')+row['label'],*table_value(row),row['source'],row.get('brief',''),row.get('status','')),tags=(tag,'category') if group else (tag,))
            self.overview_sources[row['key']]=row['detail'];self.overview_urls[row['key']]=row['url']
            self.overview_meanings[row['key']]=row.get('meaning','')
        if selected and self.overview.exists(selected[0]):self.overview.selection_set(selected[0]);self.overview_detail()
        if scroll:self.overview.yview_moveto(scroll[0])
        if not self.overview.selection():self.detail.configure(text='');self.value_button.configure(state='disabled')
    def sync_group_controls(self,*_):
        # Native keyboard Left/Right changes open state after the virtual event.
        def sync():
            if not self.winfo_exists():return
            for key in self.overview_groups:
                self.overview.item(key,text='−' if self.overview.item(key,'open') else '+')
        self.after_idle(sync)
    def toggle_group(self,key):
        if key not in self.overview_groups:return
        opened=not self.overview.item(key,'open')
        self.overview.item(key,open=opened,text='−' if opened else '+')
        self.overview.selection_set(key);self.overview.focus(key);self.overview.focus_set()
    def toggle_at_pointer(self,event):
        if self.overview.identify_region(event.x,event.y)=='tree' and self.overview.identify_column(event.x)=='#0':
            key=self.overview.identify_row(event.y)
            if key in self.overview_groups:
                self.toggle_group(key);return 'break'
    def toggle_selected(self,event=None):
        selected=self.overview.selection()
        if selected and selected[0] in self.overview_groups:
            self.toggle_group(selected[0]);return 'break'
    def overview_detail(self,*_):
        selection=self.overview.selection()
        self.value_button.configure(state='normal' if selection else 'disabled')
        if selection:
            self.detail.configure(text=self.overview_meanings.get(selection[0],'')+' Double-click for sources and method.')
    def open_value_at_pointer(self,event):
        if self.overview.identify_region(event.x,event.y) not in ('cell','tree'):return
        if self.overview.identify_column(event.x)=='#0':return 'break'
        key=self.overview.identify_row(event.y)
        if key:
            self.overview.selection_set(key);self.value_details(key)
        return 'break'
    def value_details(self,key=None):
        from value_details import build
        from value_details_ui import ValueDetailsWindow
        selection=self.overview.selection()
        key=key or (selection[0] if selection else None)
        if not key:return
        document=build(self.app.site,key)
        if document:
            self.value_window=ValueDetailsWindow(self,document)
            return self.value_window
    def sources(self):
        from value_details_ui import ValueDetailsWindow
        from value_details import safe_url
        document=dict(title='Sources & location details',value='Delivery destination: '+(self.app.site.get('destinationAddress') or 'Not selected'),sections=[],links=[])
        for row in display_rows(self.app.site):
            if row['section']:continue
            document['sections'].append((row['label']+': '+row['value'],'Source: '+row['source']+'\nReference: '+row['reference']+'\n'+row['detail']))
            if safe_url(row['url']) and all(u!=row['url'] for _,u in document['links']):document['links'].append((row['source'],row['url']))
        return ValueDetailsWindow(self,document)
    def export(self):
        path=filedialog.asksaveasfilename(parent=self,defaultextension='.json',initialfile='site-conditions.json',filetypes=[('JSON','*.json')])
        if path:
            from pathlib import Path
            Path(path).write_text(json.dumps(self.app.site,ensure_ascii=False,indent=2),encoding='utf-8')
