"""Start one desktop instance in Codespaces; wait for the X display to be ready."""
import fcntl,os,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'apps'/'transport'

def main():
    state=APP/'data';state.mkdir(parents=True,exist_ok=True)
    with (state/'desktop.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print('FlowerMoon is already running.');return 0
        os.environ.setdefault('DISPLAY',':1')
        import tkinter as tk
        for attempt in range(60):
            try:
                root=tk.Tk();root.withdraw();root.destroy();break
            except tk.TclError:
                if attempt==59:raise RuntimeError('Desktop display unavailable; check /tmp/container-init.log') from None
                time.sleep(1)
        print('Launching FlowerMoon Transport',flush=True)
        return subprocess.call([sys.executable,'-B',str(APP/'planner_ui.py')],cwd=APP)

if __name__=='__main__':raise SystemExit(main())

