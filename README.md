# Debbie

Debbie vNext now contains its first pure-Python rectangular nesting engine in
addition to typed domain models and shared geometry validation.
`Nesting_Tool_alpha_v63.html` remains the stable legacy behavior reference.

The only implemented strategy is:

- ID: `left_to_right_rectangular_v1`
- Name: `Deterministic Left-to-Right Rectangular Placement`
- Feasibility: `Free rectangular placement — non-guillotine`

The synchronous public API accepts one independent `Work` and does not mutate
it:

```python
from debbie.nesting import nest_work

result = nest_work(work)
```

The engine supports rectangular parts, 0°/90° orientation subject to each
part's approved orientation set, four-sided trim, boundary and inter-part
clearance, finite work-owned stock, structured partial results, and explicit
lexicographic objective metadata. Every committed placement passes the shared
geometry validator.

Part instances are ordered by descending nominal area, descending maximum
side, descending minimum side, restricted orientation before unrestricted,
normalized label, and stable source identities only as final tie-breakers.
Already-open sheets are tried before a new sheet. Unopened sheets are ranked by
the number of remaining pieces placed by a deterministic one-sheet simulation,
then smaller nominal full-stock area, full length, full width, normalized
label, specification identity, physical sequence, and instance identity.

Placement candidates are combinations of the effective-region origin and the
right/bottom edges of placed parts plus explicit clearance. Valid candidates
are generated lazily in smallest-X, smallest-Y, non-rotated-orientation order;
boundary-impossible coordinates are discarded before incremental collision
checks, and every selected commit still passes the complete shared validator.
No pixel grid or random search is used.

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

Developers can run deterministic performance fixtures and instrumentation with:

```powershell
.\.venv313\Scripts\python.exe scripts\benchmark_nesting.py
.\.venv313\Scripts\python.exe scripts\benchmark_nesting.py --scenario simple --size 100 --profile
```

The benchmark reports runtime, candidate/validation counts, stock simulations,
and result reconciliation. It is development evidence, not a production or
commercial performance guarantee. Dense mixed-dimension layouts can still
produce substantial candidate growth and require representative production
datasets before performance targets are accepted.

There is no graphical interface, PySide6 integration, import/export,
persistence, manual layout editing, cutting sequence, guillotine planner, or
machine toolpath. Generated layouts are not machine-ready and are not
guaranteed global optima. The current greedy edge-candidate search is intended
as an understandable deterministic first engine, not an exhaustive optimizer.
