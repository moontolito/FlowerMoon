"""Shared FlowerMoon tokens and native ttk styles."""
from tkinter import ttk

LIGHT = dict(background='#FAFAFA', surface='#FFFFFF', raised='#F3F3F5', hover='#F0EAF2',
             border='#E2E2E7', strong='#B9BBC3', text='#1C1C1C', secondary='#5F6269',
             muted='#686B73', primary='#82478C', primary_hover='#713B7B', active='#63336C',
             selection='#EEE3F1', success='#28734B', success_bg='#EAF4ED',
             warning='#855A10', warning_bg='#FFF3D9', danger='#AF303C', danger_bg='#FCECEE',
             info='#005FB8', info_bg='#EAF2FC', focus='#82478C', disabled='#A0A0A0')
DARK = dict(background='#1C1C1C', surface='#252527', raised='#303033', hover='#3B3040',
            border='#3D3D42', strong='#74747F', text='#FAFAFA', secondary='#C2BEC8',
            muted='#B3AFBA', primary='#D5A2DF', primary_hover='#E2B7EB', active='#C68ED1',
            selection='#443149', success='#91D4AA', success_bg='#233B2D',
            warning='#F0C67F', warning_bg='#403522', danger='#FFA4AD', danger_bg='#452D32',
            info='#80C6F2', info_bg='#263A47', focus='#D5A2DF', disabled='#77777D')
SPACING = (4, 8, 12, 16, 24, 32, 48)
FONT = 'Segoe UI'

def configure(root, colors):
    s = ttk.Style(root)
    root.option_add('*Font', (FONT, 10))
    s.configure('.', font=(FONT, 10))
    for name, bg in [('App', colors['background']), ('Panel', colors['surface'])]:
        s.configure(name+'.TFrame', background=bg)
        s.configure(name+'.TLabel', background=bg, foreground=colors['text'])
        s.configure(name+'Muted.TLabel', background=bg, foreground=colors['secondary'])
        s.configure(name+'Title.TLabel', background=bg, foreground=colors['text'], font=(FONT, 17, 'bold'))
        s.configure(name+'Section.TLabel', background=bg, foreground=colors['text'], font=(FONT, 11, 'bold'))
    s.configure('Treeview', rowheight=32, background=colors['surface'], fieldbackground=colors['surface'], borderwidth=0)
    s.map('Treeview', background=[('selected', colors['selection'])], foreground=[('selected', colors['text'])])
    s.configure('Treeview.Heading', font=(FONT, 10, 'bold'))
    s.configure('TButton', padding=(12, 7))
    s.layout('Brand.TButton', [('Brand.focus', {'children': [('Brand.padding', {'children': [('Brand.label', {'sticky': 'nswe'})], 'sticky': 'nswe'})], 'sticky':'nswe'})])
    s.configure('Brand.TButton', background=colors['primary'], foreground=colors['background'], padding=(18, 9), borderwidth=0, font=(FONT, 10, 'bold'), focuscolor=colors['text'])
    s.map('Brand.TButton', background=[('disabled', colors['disabled']), ('pressed', colors['active']), ('active', colors['primary_hover'])])
    s.configure('Nav.TButton', padding=(16, 10), anchor='w')
    s.configure('Muted.TLabel', foreground=colors['secondary'])
