# Debbie

Debbie vNext now contains its first pure-Python rectangular nesting engine in
addition to typed domain models and shared geometry validation.
`Nesting_Tool_alpha_v63.html` remains the stable legacy behavior reference.

The Python foundation also provides immutable Work-level material identity,
effective-density provenance, thickness, rectangular stock allocation, and
deterministic engineering mass calculations. Material-aware Works use explicit
full and allocated stock geometry; physical allocation is derived while
commercial allocation remains separate. Planning and nesting-result APIs are:

```python
from debbie.mass import calculate_nesting_result_mass, calculate_work_mass_plan

plan = calculate_work_mass_plan(work)
result_mass = calculate_nesting_result_mass(work, nesting_result)
```

Schema 1.0 imports deliberately remain unclassified: they receive no invented
material, density, thickness, or allocation values, and mass calculation
returns a structured `MATERIAL_DATA_REQUIRED` status. Canonical schema 1.1 is
implemented through an explicit `canonical_excel_v1_1` path; it requires Work
material, density, thickness, and full/allocated stock geometry and constructs
classified Works. The read-only Desktop now presents classified material,
thickness, density provenance, stock allocation, planning mass, and consumed
result mass. A material library, remnant inventory, export/template generation,
and the trim-on-allocation rule are not implemented.
Until that rule is accepted, nesting rejects partial allocations combined with
non-zero trim or boundary clearance instead of silently choosing a boundary.

Canonical `.xlsx` import is implemented for the strict `Debbie Nesting
Workbook` schemas 1.0 and 1.1 specified in `docs/EXCEL_SCHEMA_V1.md` and
`docs/EXCEL_SCHEMA_V1_1.md`. It operates
offline, validates the complete workbook atomically, and returns structured
diagnostics with no partially usable works when any error exists:

```python
from debbie.importers.excel import import_canonical_workbook

result = import_canonical_workbook("job.xlsx")
if result.success:
    works = result.works
else:
    errors = result.errors
```

If an import attempt fails in the Desktop, `IMPORT-001` keeps the last valid
project, selected Work, planning summary, and accepted nesting result active;
only the import-attempt diagnostics and status are updated. A later successful
import replaces that project atomically.

The adapters accept `.xlsx` only and identify themselves as
`canonical_excel_v1` or `canonical_excel_v1_1` after metadata-first dispatch.
Legacy workbook evidence is catalogued separately in
`docs/LEGACY_IMPORT_INVENTORY.md`; no legacy compatibility adapter is
implemented. Workbook content is treated as untrusted and passes bounded
archive/XML checks before strict schema validation. Formulas are never
evaluated; a required formula cell is accepted only when the workbook contains
a usable cached value, and an empty cache is rejected. There is no import UI.

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

The first Debbie Desktop MVP is a read-only PySide6 workflow over the existing
importer and nesting engine. It imports a canonical workbook, lets an engineer
select a work and review its process settings, parts, and stocks, runs nesting
outside the UI thread, and displays layouts, structured diagnostics, and
unplaced demand. Launch it with either:

```powershell
.\.venv313\Scripts\python.exe -m debbie.desktop
.\.venv313\Scripts\debbie-desktop.exe
```

The application opens without a workbook and requires neither Excel, a browser,
nor internet access. The basic workflow is **Import Excel → select work → Run
Nesting → select and inspect a layout**. Input may use canonical `.xlsx`
`Debbie Nesting Workbook` schema 1.0 or 1.1. Schema 1.0 remains explicitly
unclassified and shows material/mass as unavailable rather than zero. Schema
1.1 shows Work material and allocation-aware planning and result summaries;
planning inventory and consumed nesting totals remain separate, and PARTIAL
results withhold completed-product values. Legacy workbook formats are
unsupported.

The Python package requires Python 3.13 or 3.14. Canonical workbook import uses
`openpyxl>=3.1.5,<4`, and the desktop uses `PySide6>=6.10,<6.12`. Python 3.13 is
the primary development and validation version; Python 3.14 is a secondary
compatibility target. Python 3.12 and earlier are not supported.

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

The desktop is a read-only engineering viewer, not the visually finalized
Debbie interface. Its material/mass integration is functional presentation,
not the dedicated UI/UX refinement milestone.
There is no editing, drag-and-drop placement, Temp Zone, locking, export,
persistence, legacy import, cutting sequence, guillotine planner, machine
toolpath, `.exe` bundle, or installer. Generated layouts are non-guillotine,
not machine-ready, and not guaranteed global optima. Large solver jobs can
still take significant time even though desktop execution occurs on a worker.
The current deterministic edge-candidate search is an understandable first
engine, not an exhaustive optimizer or a commercially ready release.
