"""Themed, scrollable read-only provenance viewer."""
from datetime import datetime
import tkinter as tk
from tkinter import ttk
import webbrowser
from value_details import plain_text, safe_url


class ValueDetailsWindow(tk.Toplevel):
    def __init__(self, parent, document):
        super().__init__(parent)
        self.document = document
        self.c = parent.app.c
        self.title('Value details — ' + document['title'])
        self.geometry('900x740'); self.minsize(620, 420); self.transient(parent)
        self.configure(bg=self.c['background'])
        head = ttk.Frame(self, style='Panel.TFrame', padding=(20,16))
        head.pack(fill='x')
        self.heading = ttk.Label(head, text=document['title'], style='PanelSection.TLabel', font=('Segoe UI',13,'bold'), wraplength=830)
        self.heading.pack(anchor='w')
        self.result = ttk.Label(head, text=document['value'], style='SiteValue.TLabel', wraplength=830)
        self.result.pack(anchor='w', pady=(6,0))
        head.bind('<Configure>', lambda e: [w.configure(wraplength=max(200,e.width-40)) for w in (self.heading,self.result)])
        foot = ttk.Frame(self, style='Panel.TFrame', padding=(16,10)); foot.pack(side='bottom',fill='x')
        self.copy_button = ttk.Button(foot, text='Copy details', command=self.copy); self.copy_button.pack(side='left')
        ttk.Button(foot, text='Close', command=self.destroy).pack(side='right')
        snapshot = ttk.Label(foot, style='PanelMuted.TLabel', text='Snapshot '+datetime.now().strftime('%H:%M:%S')+' · reopen after a data refresh')
        snapshot.pack(side='left',padx=12)
        body = ttk.Frame(self, style='App.TFrame', padding=12); body.pack(fill='both',expand=True)
        self.area = tk.Text(body, wrap='word', padx=16,pady=12, borderwidth=0, highlightthickness=1,
                            highlightbackground=self.c['border'],highlightcolor=self.c['focus'],bg=self.c['surface'],fg=self.c['text'],
                            selectbackground=self.c['selection'],selectforeground=self.c['text'],font=('Segoe UI',10),spacing3=5,cursor='arrow')
        scroll = ttk.Scrollbar(body, command=self.area.yview); scroll.pack(side='right',fill='y')
        self.area.configure(yscrollcommand=scroll.set); self.area.pack(fill='both',expand=True)
        self.area.tag_configure('heading', font=('Segoe UI',11,'bold'),foreground=self.c['primary'],spacing1=14,spacing3=8)
        self.area.tag_configure('link',foreground=self.c['info'],underline=True)
        self.links = {}
        # Links are directly reachable near the top, before long method explanations.
        if document['sections']:
            title,text = document['sections'][0]; self.add_section(title,text)
        self.area.insert('end','Sources & links\n','heading')
        for index,(label,url) in enumerate(document['links']):
            tag = 'source_'+str(index); self.links[tag] = url
            self.area.insert('end',label+'\n'+url+'\n',('link',tag))
            self.area.tag_bind(tag,'<Button-1>',lambda e,u=url:self.open_link(u))
            self.area.tag_bind(tag,'<Enter>',lambda e:self.area.configure(cursor='hand2'))
            self.area.tag_bind(tag,'<Leave>',lambda e:self.area.configure(cursor='arrow'))
        if not document['links']: self.area.insert('end','No external source link recorded for this value.\n')
        for title,text in document['sections'][1:]: self.add_section(title,text)
        self.area.configure(state='disabled')
        self.bind('<Escape>',lambda e:self.destroy())
        self.bind('<Control-Shift-C>',lambda e:self.copy())
        self.area.focus_set()

    def add_section(self,title,text):
        self.area.insert('end',title+'\n','heading'); self.area.insert('end',text+'\n')

    def copy(self):
        self.clipboard_clear(); self.clipboard_append(plain_text(self.document))
        self.copy_button.configure(text='Copied')

    def open_link(self,url):
        if safe_url(url): webbrowser.open_new_tab(url)
