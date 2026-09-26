"""Portable entry point, independent of the current directory."""
import runpy,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
if __name__=='__main__':runpy.run_path(str(ROOT/'src'/'planner_ui.py'),run_name='__main__')
