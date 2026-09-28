"""Address suggestions in a bounded popup, triggered only by user input."""
import queue
import threading
import tkinter as tk
from tkinter import ttk, font
import places


class AddressEntry(ttk.Frame):
    def __init__(self, parent, variable, on_select, online=True):
        super().__init__(parent, style='Panel.TFrame')
        self.variable, self.on_select, self.online = variable, on_select, online
        self.token = 0
        self.timer = None
        self.focus_timer = None
        self.results = queue.Queue()
        self.rows = []
        self.alive = True
        self.worker_busy = False
        self.pending_query = None
        self.root = self.winfo_toplevel()
        self.entry = ttk.Entry(self, textvariable=variable, width=1)
        self.entry.pack(fill='x')
        self.popup = tk.Toplevel(self)
        self.popup.withdraw()
        self.popup.overrideredirect(True)
        self.popup.transient(self.root)
        colors = self.root.c
        panel = tk.Frame(self.popup, bg=colors['surface'], highlightbackground=colors['border'], highlightthickness=1)
        panel.pack(fill='both', expand=True)
        self.list_font = font.Font(self, family='Segoe UI', size=11)
        style = ttk.Style(self)
        style.configure('AddressSuggestion.Treeview', rowheight=34, font=('Segoe UI',11), borderwidth=0)
        style.map('AddressSuggestion.Treeview', background=[('selected',colors['selection'])], foreground=[('selected',colors['primary'])])
        self.listbox = ttk.Treeview(panel, show='tree', columns=(), height=4, selectmode='browse', style='AddressSuggestion.Treeview')
        self.listbox.column('#0', width=580, stretch=True)
        self.listbox.tag_configure('even', background=colors['surface'])
        self.listbox.tag_configure('odd', background=colors['raised'])
        self.listbox.pack(fill='both', expand=True, padx=10, pady=(10,5))
        self.hint = ttk.Label(panel, style='PanelMuted.TLabel', text='Photon / OpenStreetMap')
        self.hint.pack(anchor='w', padx=12, pady=(0,8))
        self.entry.bind('<KeyRelease>', self.typed)
        for sequence in ('<<Paste>>', '<<Cut>>'):
            self.entry.bind(sequence, lambda e: self.after_idle(self.typed), add='+')
        self.entry.bind('<Down>', self.focus_list)
        self.entry.bind('<Return>', self.enter)
        self.entry.bind('<Escape>', self.dismiss)
        self.listbox.bind('<Return>', self.choose)
        self.listbox.bind('<ButtonRelease-1>', self.choose)
        self.listbox.bind('<Escape>', self.dismiss)
        self.entry.bind('<FocusOut>', self.schedule_focus_check)
        self.listbox.bind('<FocusOut>', self.schedule_focus_check)
        self.trace = variable.trace_add('write', self.changed)
        self.click_binding = self.root.bind('<Button-1>', self.outside_click, add='+')
        self.move_binding = self.root.bind('<Configure>', self.root_moved, add='+')
        self.bind('<Destroy>', self.dispose, add='+')
        self.poll_id = self.after(100, self.poll)

    def changed(self, *_):
        # A map click, restored project or selected result is not a typed query.
        self.token += 1
        self.pending_query = None
        if self.timer:
            self.after_cancel(self.timer)
            self.timer = None
        self.hide()

    def typed(self, event=None):
        if not self.alive or not self.online:
            return
        if event and event.keysym in ('Return','Escape','Up','Down','Left','Right','Tab','Shift_L','Shift_R','Control_L','Control_R','Alt_L','Alt_R'):
            return
        if self.timer:
            self.after_cancel(self.timer)
        query = self.variable.get().strip()
        token = self.token
        self.timer = self.after(650, lambda: self.lookup(query, token)) if len(query) >= 3 else None

    def lookup(self, query, token):
        self.timer = None
        if token != self.token or not self.alive:
            return
        if self.worker_busy:
            self.pending_query = (query, token)
            return
        self.worker_busy = True
        def work():
            try:
                self.results.put((token, query, places.search(query), None))
            except Exception as error:
                self.results.put((token, query, [], str(error)))
        threading.Thread(target=work, daemon=True).start()

    def shortened(self, text, width):
        text = ' '.join(text.split())
        if self.list_font.measure(text) <= width:
            return text
        # Preserve the place name and the country at the end of long addresses.
        tail = text[-28:]
        head = text[:-28]
        while head and self.list_font.measure(head+' … '+tail) > width:
            head = head[:-1]
        return head.rstrip()+' … '+tail

    def show_results(self, error=None):
        width = min(620, max(360, self.root.winfo_width()-40), self.winfo_screenwidth()-24)
        self.listbox.delete(*self.listbox.get_children())
        for index, row in enumerate(self.rows):
            self.listbox.insert('', 'end', iid=str(index), text=self.shortened(row['label'], width-92), tags=('odd' if index%2 else 'even',))
        if not self.rows:
            self.listbox.insert('', 'end', text='Address search unavailable. Try again.' if error else 'No results. Try a city and country.')
        self.listbox.configure(height=min(4, max(1, len(self.rows))))
        self.popup.update_idletasks()
        height = self.popup.winfo_reqheight()
        x = max(8, min(self.entry.winfo_rootx(), self.winfo_screenwidth()-width-8))
        y = self.entry.winfo_rooty()+self.entry.winfo_height()+4
        if y+height > self.winfo_screenheight()-8:
            y = max(8, self.entry.winfo_rooty()-height-4)
        self.popup.geometry(f'{width}x{height}+{x}+{y}')
        self.popup.deiconify()
        self.popup.lift()

    def poll(self):
        while not self.results.empty():
            token, query, rows, error = self.results.get()
            self.worker_busy = False
            if token != self.token or query != self.variable.get().strip():
                continue
            self.rows = rows
            self.show_results(error)
        if self.pending_query and not self.worker_busy:
            query, token = self.pending_query
            self.pending_query = None
            if token == self.token and query == self.variable.get().strip():
                self.lookup(query, token)
        if self.alive:
            self.poll_id = self.after(100, self.poll)

    def hide(self):
        self.popup.withdraw()
        self.rows = []

    def dismiss(self, event=None):
        self.changed()
        self.entry.focus_set()
        return 'break'

    def check_focus(self):
        self.focus_timer = None
        if self.alive and self.focus_get() not in (self.entry, self.listbox):
            self.changed()

    def schedule_focus_check(self, event=None):
        if self.focus_timer:
            self.after_cancel(self.focus_timer)
        self.focus_timer = self.after(80, self.check_focus)

    def outside_click(self, event):
        if event.widget not in (self.entry, self.listbox) and self.popup.winfo_ismapped():
            self.changed()

    def root_moved(self, event):
        if event.widget is self.root and self.popup.winfo_ismapped():
            self.changed()

    def focus_list(self, event=None):
        if self.rows:
            self.listbox.focus_set()
            self.listbox.selection_set('0')
            self.listbox.focus('0')
        return 'break'

    def enter(self, event=None):
        if self.rows:
            return self.focus_list()
        if self.online and len(self.variable.get().strip()) >= 3:
            if self.timer:
                self.after_cancel(self.timer)
                self.timer = None
            self.lookup(self.variable.get().strip(), self.token)
        return 'break'

    def choose(self, event=None):
        selected = self.listbox.selection()
        if not selected or not self.rows:
            return 'break'
        row = self.rows[int(selected[0])]
        self.changed()
        self.on_select(row)
        self.entry.focus_set()
        return 'break'

    def dispose(self, event):
        if event.widget is not self:
            return
        self.alive = False
        self.token += 1
        self.variable.trace_remove('write', self.trace)
        for timer in (self.timer, self.poll_id, self.focus_timer):
            if timer:
                try:self.after_cancel(timer)
                except tk.TclError:pass
        self.root.unbind('<Button-1>', self.click_binding)
        self.root.unbind('<Configure>', self.move_binding)
