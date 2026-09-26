"""Hosted entry point publishes real Tk readiness to the browser portal."""
import json,os,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from planner_ui import Planner

def main():
    os.environ['FLOWERMOON_HOSTED']='1'
    app=Planner()
    status=ROOT/'data'/'hosted-status.json';status.parent.mkdir(exist_ok=True)
    app.geometry('1440x900+0+0')
    def report():
        if app.wm_state()=='iconic':app.deiconify()
        info=dict(pid=os.getpid(),updatedAt=time.time(),visible=bool(app.winfo_viewable()),widgets=len(app.winfo_children()))
        temp=status.with_suffix('.tmp');temp.write_text(json.dumps(info));temp.replace(status)
        app.after(1000,report)
    app.after(300,report)
    app.after(400,app.lift)
    app.mainloop()

if __name__=='__main__':main()
