# Debbie

Debbie vNext is in its Python foundation phase. The current code defines typed
domain models and shared rectangular geometry validation; it is not yet an
operational nesting application. `Nesting_Tool_alpha_v63.html` remains the
stable legacy behavior reference.

The Python package requires Python 3.13 or 3.14 and has no runtime
dependencies. Python 3.13 is the primary development and validation version;
Python 3.14 is a secondary compatibility target. Python 3.12 and earlier are
not supported.

To prepare the primary development environment in Windows PowerShell:

```powershell
py -3.13 -m venv .venv313
.\.venv313\Scripts\python.exe -m pip install --upgrade pip
.\.venv313\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv313\Scripts\python.exe -m pytest
```

Python 3.14 compatibility can be checked separately with a `.venv314`
environment; Python 3.13 remains authoritative.

There is currently no nesting solver, placement search, graphical interface,
import/export implementation, or persistence layer.
