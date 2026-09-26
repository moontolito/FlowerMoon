@echo off
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (py -3 -B planner_ui.py) else (python -B planner_ui.py)
if errorlevel 1 pause
