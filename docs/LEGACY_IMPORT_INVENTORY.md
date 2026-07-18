# Legacy Spreadsheet Import Inventory

## Purpose and status

This document inventories spreadsheet layouts identifiable in `Nesting_Tool_alpha_v63.html` at checkpoint `dad4b2e`. It is compatibility evidence for future Product Owner selection, not approval to implement any adapter. The canonical Debbie vNext contract is `EXCEL_SCHEMA_V1.md`.

Evidence labels:

- **Confirmed:** directly visible in executable legacy code or the embedded workbook.
- **Inferred:** likely intent or practical effect that requires real fixture confirmation.

No external production workbook fixtures are present in the repository. The only inspectable workbook fixture is the base64-embedded downloaded configuration template.

## Shared legacy parsing behavior

**Confirmed:** the browser accepts `.xlsx` and `.xls` and depends on SheetJS loaded from a public CDN. Sheet names and headers are normalized to lower-case alphanumeric text. Recognition tries exact aliases, then broad substring matches. Header rows may be searched heuristically. Numeric parsing replaces comma with dot and uses `parseFloat`/`parseInt`; invalid or non-positive quantities commonly default to `1`. Rows with invalid/non-positive dimensions are commonly skipped.

**Confirmed:** parsing is not atomic. Some paths clear locks, change settings, reset arrays, or add rows before the complete workbook is known valid. There is no structured diagnostic result, no `FileReader.onerror`, and no outer parse exception boundary.

**Confirmed:** imported 2D units are ignored and the legacy UI forces millimetres. Rotation settings are ignored because automatic 2D rotation is always enabled. These behaviors are evidence only and conflict with the strict canonical schema where applicable.

## Format inventory and proposed priorities

| Provisional legacy format | Proposed priority | Real fixture available | Main risk |
|---|---|---|---|
| Compact per-sheet `STOCKS`/`PARTS` sections | High | Embedded template only | Broad section/header aliases and silent defaults |
| Multi-work compact sheets | High | No external sample | Any matching worksheet becomes a work; false recognition |
| Fixed-position `Data Entry` | Medium | No | Positional parsing and partial mutation |
| Separate 2D stock/part sheets plus settings | Medium | No | Broad sheet/header aliases select unintended data |
| Embedded `nesting_config.xlsx` template | High as a migration fixture | Yes, embedded base64 | Unversioned and not canonical |
| Fixed-position linear `Data Entry` | Low; `LINEAR-001` gate | No | Hidden feature, ambiguous overlap with 2D |
| Separate linear stock/cut sheets | Low; `LINEAR-001` gate | No | Broad aliases and no approved vNext linear model |

Priorities are engineering proposals only. Product Owner selection of actual adapters remains pending.

## Legacy format A — compact section-based work sheet

### Recognition

- **Confirmed:** a worksheet is converted to an array of rows and searched for section labels `STOCKS`, `Stocks`, or `Stock`, and `PARTS`, `Parts`, `PANELS`, `Panels`, or `Cut List`.
- **Confirmed:** within six rows after a section marker, header groups must contain an accepted length, width, and quantity alias.
- **Confirmed:** section parsing stops at another recognized stock/part section marker.
- **False-positive risk:** high. Normalization removes punctuation/case and section/header aliases are broad.

### Sheets and multi-work behavior

- **Confirmed:** the late import wrapper scans every worksheet with `parse2DJobFromSheet`.
- **Confirmed:** every sheet containing usable stock and part sections becomes an independent in-memory job. The worksheet name becomes the job display name through `safeJobName`.
- **Confirmed:** if no sheet qualifies, the file is read again through the older single-import path.
- **Inferred:** this is the most recent intended multi-work input format, but no production sample proves which aliases users rely on.

### Columns and data flow

- Stock aliases include `Stock Length`, `Length`, `Panel Length`, `L`; `Stock Width`, `Width`, `Panel Width`, `W`; and `Stock Qty`, `Quantity`, `Qty`, `QTY`.
- Part aliases include length/width variants above, quantity variants, and label aliases such as `Label`, `Part Name`, `Drawing Nr`, and `Drawing Number`.
- Settings may appear in row pairs and include units, kerf, four trims, trim enabled, batches, rotation keys, and sort strategy.
- Valid rows are pushed into job-local stock/part arrays. The later Optimize loop processes works independently.

### Defaults and ambiguity

- Invalid/non-positive quantities default to `1`.
- Invalid dimensions are skipped.
- Batch is parsed as a number; later legacy demand logic rounds/clamps it.
- Rotation keys are recognized but not enforced; rotation remains always allowed.
- Units are forced to millimetres.
- No stable textual work/part/stock identity exists beyond labels, sheet name, generated counters, and array position.

### Proposed disposition

High-priority compatibility research because it is the current embedded-template shape and only visible multi-work path. Implementation still requires sanitized real workbooks, an exact recognition signature, and Product Owner approval.

## Legacy format B — named single-sheet compact layout

### Recognition

- **Confirmed:** the older path selects sheet aliases `Nesting`, `Data Entry`, `nesting_config`, or misspelled `nexting_config`, with broad `nesting`, `nexting`, or `data` substring fallback.
- It then applies the same compact `STOCKS`/`PARTS` section extraction as format A.

### Data flow and risks

- Settings embedded beside sections may immediately update live UI fields.
- Existing locks are cleared.
- Stock and part arrays are reset independently only when corresponding sections have rows.
- Invalid rows are skipped; quantities default to `1`.
- **False-positive risk:** high because `Data Entry` can also identify the unrelated fixed-position format and the sheet search uses broad substrings.

### Proposed disposition

Treat as part of the compact adapter investigation rather than a separate canonical format. High priority only after exact historical signatures and fixture evidence distinguish it safely.

## Legacy format C — fixed-position `Data Entry`

### Recognition

- **Confirmed:** a sheet named/matching `Data Entry` is selected after compact parsing fails.
- **Confirmed:** labels are found in column B and values are read from fixed columns, primarily D–H.

### Layout

- Settings labels in column B include `Kerf / Blade thickness` and four trim labels; values are read from column D.
- A `stocks` marker in column B begins stock rows: length D, width E, quantity F.
- A later `panels` marker begins part rows: length D, width E, quantity G or F, label H.
- Blank/invalid cells terminate sections in some paths.

### Defaults, support, and risks

- Quantities use `parseInt(...) || 1`.
- Settings and arrays mutate live state during parsing.
- There is no workbook-level validation or structured error collection.
- **Inferred:** column placement probably follows an older cutting-calculator workbook, but exact headers/merged cells/styles are unknown.
- **False-positive risk:** medium to high because recognition relies mainly on a generic `Data Entry` sheet and a few positional labels.
- No repository fixture exists.

### Proposed disposition

Medium priority pending real user files and confirmation that this format remains operationally required.

## Legacy format D — separate 2D sheets and optional settings

### Recognition

- Optional settings sheets: `Settings`, `Config`, `Configuration`, or names containing `setting`/`config`.
- Stock sheets: `2D_Stocks`, `2D Stocks`, `Stocks 2D`, then names containing `2dstocks` or broadly `stock`.
- Part sheets: `2D_Parts`, `2D Parts`, `2D_Panels`, `Panels`, `Parts`, then names containing `2dparts`, `2dpanels`, `panel`, or `part`.
- Header discovery searches for rows containing alias groups and falls back to row 1 when no header is found.

### Columns and data flow

- Stock length accepts `Length`, `Stock Length`, `Panel Length`, `L`, `Width`, or `W`; stock width accepts `Width`, `Stock Width`, `Panel Width`, `Height`, or `H`.
- Part dimensions accept similarly broad aliases; quantity and labels accept multiple synonyms.
- Settings accept numerous kerf, trim, batch, units, and strategy aliases.
- Arrays/settings are applied independently, so one recognized sheet can mutate state without the other succeeding.

### Defaults and risks

- Quantity defaults to `1`; invalid dimensions are skipped.
- Header and sheet alias overlap can map width into length or select unrelated sheets.
- No multi-work identity exists in this path.
- **False-positive risk:** high due to broad `stock`, `part`, and `panel` substring matching.
- No repository fixture exists.

### Proposed disposition

Medium priority if real customers use separate-sheet workbooks. Require exact adapter-specific signatures; do not port the broad fallback rules.

## Legacy format E — embedded downloaded `nesting_config.xlsx`

### Confirmed workbook content

The base64-embedded workbook was inspected in memory without modifying it:

- one worksheet named `Nesting`;
- title `Single-sheet 2D import template`;
- sections `SETTINGS`, `STOCKS`, `PARTS`, and `RULES`;
- stock headers `Stock Length`, `Stock Width`, `Stock Qty`;
- part headers `Label`, `Part Length`, `Part Width`, `Part Qty`;
- settings/rules mention units, blade kerf, trim enabled, and four trims;
- instructions say millimetres only and that labels do not affect nesting.

The same embedded file is downloaded by both 2D and hidden linear template buttons, although its visible content is 2D.

### Risks and proposed disposition

- It has no explicit format name/version metadata and is not canonical vNext.
- It is a useful high-priority migration fixture because it is the only exact workbook in the repository.
- Product Owner must decide whether a future legacy adapter supports it directly or a conversion tool/template transition replaces it.

## Legacy format F — fixed-position linear `Data Entry`

### Confirmed behavior

- Hidden linear import reuses `Data Entry`.
- Stock bars read length D and quantity F after `stocks` in column B.
- Cuts read length D, quantity G/F, and label H after `panels`.
- Linear units, kerf, and sort strategy may come from a settings sheet.

### Risks and proposed disposition

- The navigation tab is hidden, Excel/PDF outputs do not support linear results, and `LINEAR-001` is pending.
- Recognition overlaps the 2D fixed-position format.
- Proposed priority: low; do not implement or retire without Product Owner approval and real usage evidence.

## Legacy format G — separate linear stock/cut sheets

### Confirmed behavior

- Stock aliases include `Linear_Stocks`, `Linear Stocks`, `Stock Bars`, and `Bars`, with broad substring fallbacks.
- Cut aliases include `Linear_Cuts`, `Linear Cuts`, and `Cuts`.
- Required values are length and quantity; labels are optional for cuts.
- Invalid quantities default to `1`; invalid lengths are skipped.

### Risks and proposed disposition

- Broad `stock`, `bars`, and `cut` matches can select unrelated sheets.
- No approved vNext linear domain/import contract exists.
- Proposed priority: low and gated by `LINEAR-001`.

## Decisions and evidence required before adapters

Before any legacy adapter implementation, Product Owner must select exact retained formats and priority using:

- sanitized real workbook fixtures and provenance;
- required worksheet/header variants;
- unit and decimal-locale expectations;
- multi-work and batch behavior;
- whether invalid legacy defaults are compatibility behavior or diagnosed defects;
- collision/ambiguity rules when several formats match;
- disposition of the embedded template;
- `LINEAR-001` disposition.

Every selected adapter must declare its identity, emit compatibility diagnostics, map to canonical neutral records, and use the same atomic domain construction as canonical import. Ambiguous files must be rejected rather than guessed.
