"""Debounced suggestions with keyboard selection and stale-response rejection."""
import queue,threading,tkinter as tk
from tkinter import ttk
import places

class AddressEntry(ttk.Frame):
    def __init__(self,parent,variable,on_select,online=True):
        super().__init__(parent,style='Panel.TFrame')
        self.variable=variable;self.on_select=on_select;self.online=online
        self.token=0;self.timer=None;self.results=queue.Queue();self.rows=[];self.suppress=False;self.alive=True;self.worker_busy=False;self.pending_query=None
        self.entry=ttk.Entry(self,textvariable=variable);self.entry.pack(fill='x')
        self.listbox=tk.Listbox(self,height=4,exportselection=False,activestyle='dotbox',font=('Segoe UI',9))
        self.hint=ttk.Label(self,style='PanelMuted.TLabel',wraplength=260)
        self.entry.bind('<Down>',self.focus_list);self.entry.bind('<Return>',self.enter);self.entry.bind('<Escape>',self.dismiss)
        self.listbox.bind('<Return>',self.choose);self.listbox.bind('<ButtonRelease-1>',self.choose);self.listbox.bind('<Escape>',self.dismiss)
        self.trace=variable.trace_add('write',self.changed)
        self.bind('<Destroy>',self.dispose,add='+');self.poll_id=self.after(100,self.poll)

    def changed(self,*_):
        self.token+=1
        if self.timer:self.after_cancel(self.timer);self.timer=None
        self.hide()
        query=self.variable.get().strip()
        if not self.suppress and self.online and len(query)>=3:self.timer=self.after(650,lambda:self.lookup(query,self.token))

    def lookup(self,query,token):
        self.timer=None
        if self.worker_busy:self.pending_query=(query,token);return
        self.worker_busy=True
        self.hint.configure(text='Searching addresses…');self.hint.pack(anchor='w',pady=3)
        def work():
            try:self.results.put((token,query,places.search(query),None))
            except Exception as error:self.results.put((token,query,[],str(error)))
        threading.Thread(target=work,daemon=True).start()

    def poll(self):
        while not self.results.empty():
            token,query,rows,error=self.results.get()
            self.worker_busy=False
            if token!=self.token or query!=self.variable.get().strip():continue
            self.rows=rows;self.listbox.delete(0,'end')
            for row in rows:self.listbox.insert('end',row['label'])
            if rows:
                self.listbox.configure(height=min(4,len(rows)));self.listbox.pack(fill='x',before=self.hint,pady=(4,0))
                self.hint.configure(text='Photon / OpenStreetMap · ↓ then Enter to select')
            else:self.hint.configure(text='Address search unavailable. Use the map or try again.' if error else 'No matching address. Try a city and country.')
        if self.pending_query and not self.worker_busy:
            query,token=self.pending_query;self.pending_query=None
            if token==self.token and query==self.variable.get().strip():self.lookup(query,token)
        if self.alive:self.poll_id=self.after(100,self.poll)

    def dismiss(self,event=None):
        self.token+=1;self.pending_query=None
        if self.timer:self.after_cancel(self.timer);self.timer=None
        self.hide();self.entry.focus_set();return 'break'

    def hide(self):
        self.listbox.pack_forget();self.hint.pack_forget();self.rows=[]

    def focus_list(self,event=None):
        if self.rows:self.listbox.focus_set();self.listbox.selection_set(0);self.listbox.activate(0)
        return 'break'

    def enter(self,event=None):
        if self.rows:return self.focus_list()
        if self.online and len(self.variable.get().strip())>=3:
            if self.timer:self.after_cancel(self.timer);self.timer=None
            self.lookup(self.variable.get().strip(),self.token)
        return 'break'

    def choose(self,event=None):
        selected=self.listbox.curselection()
        if not selected or not self.rows:return 'break'
        row=self.rows[selected[0]];self.suppress=True
        try:self.on_select(row)
        finally:self.suppress=False
        self.hide();self.entry.focus_set();return 'break'

    def dispose(self,event):
        if event.widget is not self:return
        self.alive=False;self.token+=1;self.variable.trace_remove('write',self.trace)
        for timer in (self.timer,self.poll_id):
            if timer:
                try:self.after_cancel(timer)
                except tk.TclError:pass
