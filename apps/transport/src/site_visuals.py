"""Site presentation components using the shared FlowerMoon palette."""
import tkinter as tk
from tkinter import ttk
from design_system import FONT


def configure_site(root, c):
    style = ttk.Style(root)
    style.configure('Site.TNotebook', background=c['background'], borderwidth=0)
    style.configure('Site.TNotebook.Tab', padding=(16, 10), font=(FONT, 10, 'bold'))
    style.map('Site.TNotebook.Tab', foreground=[('selected', c['primary'])])
    style.configure('SiteSummary.Treeview', rowheight=32, font=(FONT, 10))
    # A literal + / minus control replaces the theme's disclosure arrow.
    style.layout('SiteSummary.Treeview.Item', [('Treeitem.padding', {'sticky':'nswe','children':[
        ('Treeitem.text', {'sticky':'nswe'})]})])
    style.map('SiteSummary.Treeview', background=[('selected', c['selection'])], foreground=[('selected', c['text'])])
    style.configure('SiteSummary.Treeview.Heading', font=(FONT, 10, 'bold'), padding=(8, 8))
    style.configure('SiteValue.TLabel', background=c['surface'], foreground=c['primary'], font=(FONT, 17, 'bold'))
    style.configure('SiteHint.TLabel', background=c['surface'], foreground=c['secondary'], font=(FONT, 9))


class MetricCard(tk.Frame):
    def __init__(self, parent, colors, title):
        super().__init__(parent, bg=colors['surface'], highlightbackground=colors['border'], highlightthickness=1)
        tk.Frame(self, bg=colors['primary'], width=3).pack(side='left', fill='y')
        body = ttk.Frame(self, style='Panel.TFrame', padding=(14, 10))
        body.pack(fill='both', expand=True)
        ttk.Label(body, text=title, style='PanelMuted.TLabel', font=(FONT, 9, 'bold')).pack(anchor='w')
        self.value = ttk.Label(body, text='—', style='SiteValue.TLabel', font=(FONT, 18, 'bold'))
        self.value.pack(anchor='w', pady=(4, 2))
        self.note = ttk.Label(body, text='', style='SiteHint.TLabel', font=(FONT, 9))
        self.note.pack(anchor='w')
        def resize(event):
            self.note.configure(wraplength=max(120, event.width-28))
            self.value.configure(font=(FONT, 14 if event.width<280 else 18, 'bold'))
        body.bind('<Configure>', resize)

    def set(self, value, note):
        self.value.configure(text=value)
        self.note.configure(text=note)
