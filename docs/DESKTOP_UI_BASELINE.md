# Debbie Desktop Visual Baseline

## Status and scope

Debbie now has a professional read-only Desktop visual baseline. This is a
presentation and usability milestone over the existing application services;
it is not the advanced editor, final commercial branding, packaging, or an
installer.

The dependency direction remains:

```text
Qt widgets
→ immutable presentation models
→ application services
→ domain, importer, mass, and nesting backends
```

The visual layer contains no engineering mass formulas, workbook parsing,
placement validation, or nesting decisions.

## Theme architecture

`src/debbie/desktop/theme.py` owns the neutral engineering palette, spacing,
typography, status tones, contrast helper, and complete application stylesheet.
`src/debbie/desktop/widgets.py` provides the reused section header, textual
status badge, compact summary card, and empty-state/message components. Long
inline QSS is not stored in the main window.

The interface uses one restrained green accent, neutral panels, explicit units,
and text paired with every status colour. Tables retain keyboard selection and
copyable content. Unavailable values use `—` and remain distinct from zero.

## Information hierarchy

- The compact application header identifies Debbie, the loaded workbook, and
  the selected Work.
- The main toolbar keeps Import Workbook, Work selection, Run Nesting, Fit View,
  Zoom In, and Zoom Out visible.
- The scrollable engineering panel groups Work, Material, Process Settings, and
  Planning Material Summary.
- Planning inventory and Nesting Result Material Summary remain separate.
- Only four high-value totals use summary cards; secondary measures remain in
  selectable detail tables.
- Parts, Stocks, Layout, Result Material, Unplaced, and Diagnostics remain
  reachable through consistent tabs.
- The layout viewer distinguishes full stock, allocated geometry, usable
  geometry, effective placement region, and placed parts without changing model
  coordinates.

## States and supported sizes

Intentional states cover no workbook, no selected Work, no nesting result, no
unplaced demand, no diagnostics, import busy, and nesting busy. COMPLETE,
PARTIAL, FAILED VALIDATION, and MATERIAL DATA REQUIRED are visible as text as
well as restrained colour.

The layout is designed and semantically tested at 1280×720 and 1920×1080, with
Qt scale factors 1, 1.5, and 2. The left engineering panel scrolls, remains
bounded at wide resolutions, and leaves additional width to tables and the
layout viewer.

## Development launcher

Double-click `Launch Debbie.bat` at the repository root. It uses `%~dp0` to
resolve the repository directory, quotes paths containing spaces, verifies
`.venv313\Scripts\python.exe`, changes only its local process directory, and
runs:

```text
.venv313\Scripts\python.exe -m debbie.desktop
```

Optional command-line arguments are forwarded, allowing the normal development
smoke check with `Launch Debbie.bat --smoke-test` while double-click behavior
remains unchanged.

If the environment is missing, the launcher prints the expected path and a
readable preparation message. It does not download files, require Administrator
privileges, modify global environment variables, or contain a developer-machine
absolute path. Python errors remain visible for development diagnosis.

To create a temporary Desktop shortcut, right-click `Launch Debbie.bat`, choose
**Send to → Desktop (create shortcut)**, and optionally rename the shortcut to
`Debbie`. A packaged executable, application shortcut, and installer belong to
the later packaging milestone.

## Deliberate limitations

The application remains read-only. This milestone adds no advanced editor,
drag-and-drop, manual placement, Temp Zone, locks, persistence, Excel/PDF
export, material library, remnants, pricing/costing, ERP/CAD/cloud behavior,
production executable, or installer. It adds no dependency and makes no change
to importer schemas, engineering formulas, deterministic identities, geometry,
or nesting behavior.
