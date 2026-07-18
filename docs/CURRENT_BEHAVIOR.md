# Current Legacy Behavior

## Scope and evidence

This document describes `Nesting_Tool_alpha_v63.html` as audited on `python-migration`. The repository contains no other project files, sample workbooks, tests, or documentation. Behavior is classified as **Confirmed**, **Partially implemented**, **Ambiguous**, **Broken/inconsistent**, or **Inferred, not easily testable**. Line references are approximate anchors in the protected file.

The application is one 7,824-line HTML file: about 2,160 lines of layered CSS, static HTML, and a large global script. It loads Google Fonts, jsPDF 2.5.1, SheetJS 0.18.5, and `xlsx-js-style` from public CDNs (`Nesting_Tool_alpha_v63.html:7`, `:2557-2559`). A workbook template and logo are embedded as base64 data.

## Startup and data entry

- **Confirmed:** The visible mode is 2D nesting; the Linear Cuts tab and sidebar exist but the tab is inline-hidden (`:2394`). `currentMode` starts as `2d` (`:6184`).
- **Confirmed:** 2D units are fixed to hidden value `mm`. Imported 2D unit settings are ignored (`apply2DSettingsMap`, `:6620`).
- **Confirmed:** Kerf, all four trims, and batch display as `0.00`, `0.00`, and `1.00`. Trim is enabled and its fields are shown by `DOMContentLoaded` (`:3254-3269`). Strategy defaults to `leftWidth` / “Left-to-Right Fill” (`:2289-2293`). Visual zoom starts at 100%; labels and colours start enabled.
- **Confirmed:** The 2D stock and parts arrays start empty; `renderStockSheets()` and `renderPieces()` create no default rows (`:3299-3350`, `:3879-3915`). The empty state instructs the user to import or add data.
- **Confirmed:** Stock rows contain length, width, and quantity. Part rows contain label/drawing, length, width, and quantity. Numeric edits use `parseFloat(...) || 0`; quantities are accepted as decimals in the UI but later rounded for demand.
- **Confirmed:** Adding a stock defaults to 2440 × 1220, quantity 10; adding a part defaults to 400 × 300, quantity 1.
- **Partially implemented:** Linear cutting has working data structures, first-fit-style optimization, import, and rendering, with defaults of one 3000 × 5 stock and cuts 800 × 3, 500 × 5, 300 × 8 (`:6205-6427`). The only tab that exposes it is hidden, so it is not normally discoverable.

## Import configuration

- **Confirmed:** 2D and linear import accept `.xlsx` and `.xls` through `FileReader` and SheetJS (`readXlsx`, `:6548`).
- **Confirmed:** 2D supports several heuristic formats: compact per-sheet `STOCKS`/`PARTS` sections, a legacy `Data Entry` layout, and separate stock/part sheets. Header and sheet matching normalize case and punctuation and accept many aliases (`pickSheet`, `sheetRowsToObjects`, `tableFromSection`, `importExcel2D`).
- **Confirmed:** Compact multi-work import treats every worksheet containing valid stock and part sections as a separate job (`parse2DJobFromSheet`, wrapper at `:7641`). A selector appears only when more than one work is parsed.
- **Confirmed:** Kerf, trim values, trim enablement, batches, and strategy can be imported. Rotation settings may be recognized as keys but are ignored because 2D rotation is always enabled.
- **Confirmed:** Import clears locks. Valid imported rows require positive dimensions; missing/invalid quantities default to 1 through `toInt`.
- **Partially implemented:** Import does not automatically optimize. Multi-work import alerts the user to press Optimize. The fallback path reads the same file a second time when the multi-work parser finds no jobs.
- **Broken/inconsistent:** `readXlsx` and import callbacks have no `reader.onerror` or outer parse exception handling. A malformed file or CDN/library failure may throw without a structured diagnostic. Heuristic aliases can select unintended sheets/columns, and imports can partially mutate UI/settings before all data is known valid.
- **Confirmed:** “Export Config” downloads one embedded file named `nesting_config.xlsx`; the repository contains no standalone template to inspect or version independently (`downloadNestingConfigTemplate`, `:6892`).

## Batches, strategies, and rotation

- **Confirmed:** `batchCount()` rounds the entered value and clamps it to at least 1. Optimize expands each source part to `round(qty × batches)` individual rectangles (`optimize`, `:4158-4167`).
- **Confirmed:** Rotation is always considered; there is no 2D rotation toggle in the current UI. Automatic strategies test normal and 90-degree orientation. Square parts are not duplicated as rotated candidates in left-fill.
- **Confirmed:** The selected strategy alone runs:
  - `area`: guillotine free-rectangle packing, testing four split rules and both rotation preferences (`Guillotine`, `runPass`, `runMultiStockPass`).
  - `leftWidth`: collision-based candidate placement ranked by smallest X, then Y, then larger area (`runLeftColumnPass`). It is explicitly not a guillotine strategy.
  - `freeNest`: MaxRects-like free-area splitting/pruning with best local waste score (`FreeAreaPacker`, `runFreeAreaPass`).
- **Confirmed:** Each strategy chooses among available stock sizes primarily by most pieces placed. Tie-breakers use waste/yield or leftmost extent. Stock inventory quantity is consumed one sheet at a time.
- **Broken/inconsistent:** `passScore` compares only number of unplaced pieces and number of sheets; it does not include yield or cut length once those counts differ/tie beyond strategy-local choices. UI terms such as “Optimise” do not mean global optimality.

## Trim, kerf, stock, and placement

- **Confirmed:** One global four-edge trim setting is attached to every stock size. Usable size is full width minus left/right trim and full height minus top/bottom trim.
- **Confirmed:** Automatic placement represents occupied part width/height as raw dimension plus one kerf. Boundary checks generally subtract kerf so the visible/raw part may touch the usable stock boundary; collision uses the inflated dimensions so parts retain a kerf gap (`actualPanelW/H`, `canPlacePanelAt`).
- **Confirmed:** Parts that cannot fit any stock in either orientation are placed in Temp and reported; they no longer abort all other nesting (`optimize`, `:4179-4210`). Parts left after inventory/strategy exhaustion also go to Temp.
- **Broken/inconsistent:** Several helpers alternate between raw cut rectangles and kerf-inflated rectangles. For example, `computeLiveCuts` reads `p.w/p.h` directly, while callers sometimes pass `cutRectForPanel(...)` and sometimes pass packed objects. Results can therefore vary by call path.
- **Broken/inconsistent:** `transferPiece` uses `lastRenderParams.usableW/usableH`, which are copied from `results[0]`, rather than the destination sheet’s dimensions. It also uses its own 1 mm grid scan and collision predicate, so context-menu transfer can disagree with drag transfer on mixed stock sizes.

## Layout generation and multi-layout handling

- **Confirmed:** Results are built as physical sheet entries and then grouped into unique layouts. Only one representative canvas is rendered per group; repetition shows how many identical entries exist (`renderResults`, `:5456-5530`).
- **Confirmed:** Group fingerprints sort rounded X, Y, width, and height. Manual recalculation uses a similar fingerprint.
- **Broken/inconsistent:** Fingerprints omit full/usable stock dimensions, part/source identity, labels, colours, rotation flags, and kerf/trim identity. Geometrically identical arrangements on different stock or of different part identities can be grouped incorrectly.
- **Broken/inconsistent:** Layout letters are limited to A–Z and then fall back to numbers, producing a mixed identifier scheme.
- **Confirmed:** Multi-work state is held in `nestingJobs`; switching saves current widget inputs and live results into the in-memory job, then loads another job (`saveActiveJobState`, `switchWorkSheet`). Optimize loops synchronously through all imported works and returns to the original work.
- **Broken/inconsistent:** The multi-work optimization loop has no `try/finally`; an exception can leave `__multiOptimizing` or the active job inconsistent. Work calculation blocks the browser UI. The code comment says batches are global, while parsed jobs and UI display per-job batch values; PDF paths also temporarily force a captured global batch. Semantics require confirmation.

## Temp Zone

- **Confirmed:** Temp is created only after results render and holds oversized, unplaced, or manually removed parts (`createTempZone`, `renderTempBox`). Cards show orientation-preserving dimensions and can be dragged back to a layout.
- **Confirmed:** Selected parts can be sent to Temp by context menu or drag. Temp-to-layout placement tries the drop point then a 1 mm exhaustive first-fit scan.
- **Confirmed:** A Temp item can be permanently removed with its × button; this is undoable within edit history.
- **Ambiguous:** Removing a Temp item removes unsatisfied demand from the current working result without changing the source part quantity. Exports based on source parts and layouts can consequently describe different demand sets.
- **Broken/inconsistent:** If there are no generated result sheets, oversized parts are displayed via a special clear-and-rebuild path. Temp normally lives inside the results scroll, producing different lifecycle behavior for all-oversized versus partially placed jobs.

## Selection and manual editing

- **Confirmed:** Clicking a part selects it; Shift-click adds selection. Dragging empty canvas creates a selection rectangle; Shift on mouse-up makes box selection additive (`finishSelectionBox`, canvas handlers at `:5811`, `:5969`).
- **Confirmed:** A selected group on one sheet can drag together. Moving over other layouts or Temp shows a ghost. Cross-layout drag attempts the exact group position, then nearby shifts; existing destination parts may be pushed to make room (`placeSelectionGroupInLayout`, `findNearestTransferSolution`).
- **Confirmed:** Same-layout drag treats moved parts as fixed and iteratively pushes other parts. If the solver cannot remove kerf overlaps, the edit is reverted with a popup.
- **Confirmed:** Arrow keys move selected parts on every unlocked non-empty sheet: 1 mm normally, 10 mm with Shift, 0.10 mm with Ctrl/Cmd. The entire move is accepted only per sheet when every selected part passes `canPlacePanelAt`.
- **Confirmed:** Double-click or the hover rotate control rotates one clicked part. The global rotate action rotates the first selected part in the first selected layout. Despite multi-selection, rotation intentionally does not rotate the group (`rotateSelectedPanelsInLayout`, `:3187`).
- **Broken/inconsistent:** Rotation swaps occupied and raw dimensions and clamps to the sheet but does not run the collision/push resolver immediately. A rotation can overlap another part; no invalidity notification is produced.
- **Broken/inconsistent:** Mouse editing and rotation do not check `isLayoutLocked`; only keyboard nudging explicitly skips locked layouts. Lock therefore does not consistently protect a layout from editing.
- **Broken/inconsistent:** There are multiple transfer implementations: context-menu single transfer, selection/control transfer, HTML drop fallback, robust cross-layout solver, and Temp first-fit. They use different bounds, search order, and collision calculations.

## Lock, optimize, and recalculate

- **Confirmed:** Lock clones the representative layout once per repetition into `lockedLayouts`. A later Optimize subtracts matching pieces by `sourceKey` and prepends locked results (`lockLayoutAndRecalculate`, `subtractLockedPieces`). Unlock removes clones matching a fingerprint or source index.
- **Confirmed:** Any detected left-panel input change causes the next Optimize to clear all locks before recalculation (`__leftInputsDirty`, `optimize`). “Clear locks” clears clone and flag state.
- **Partially implemented:** Function names say “AndRecalculate,” but toggling lock/unlock does not call Optimize. Locking is a preservation mechanism for a future Optimize, not an immediate recalculation.
- **Broken/inconsistent:** Lock matching and layout grouping use different fingerprints and mutable indices. Repeated layouts are cloned, but editing a representative and regrouping can change relationships without an explicit lock migration model.

## Collision and validity

- **Confirmed:** Core comparisons use axis-aligned rectangles and strict inequalities, so exact edge touch is non-overlap. With positive kerf, occupied rectangles include the kerf allowance, effectively requiring that separation between visible part edges.
- **Confirmed:** Boundary tolerance is approximately 0.001 mm in `canPlacePanelAt`; automatic left-fill uses 0.0001; the push resolver uses a 0.01 mm displacement epsilon. Fingerprints round to integers or hundredths depending on subsystem.
- **Broken/inconsistent:** There is no single authoritative layout validator run after every operation or before every export. Tolerances and rectangle representations differ by subsystem.
- **Performance risk:** First-fit placement and transfer scan every integer coordinate in nested loops. Drag push resolution is pairwise and iterative; nearest transfer generates many candidates. Free-area rectangles can grow substantially. All work runs on the main thread.

## Cutting length and metrics

- **Confirmed:** Initial guillotine packing tracks split cuts. `computeLiveCuts` instead adds only internal right and bottom part-edge segments and deduplicates endpoints rounded to whole units (`:2921`). It excludes edges near the usable sheet boundary.
- **Broken/inconsistent:** Initial results, manual edits, undo snapshots, required-stock summary, single PDF, all-work PDF, and job snapshots invoke cut calculation with different rectangle forms. Some include kerf-inflated dimensions; others use visible/raw dimensions. This is not a stable manufacturing cutting-length definition.
- **Broken/inconsistent:** Shared/common cut semantics, cut sequencing, pierces, lead-ins, trim cuts, outer perimeter, machine travel, and guillotine feasibility are not modeled. “Cut length” should be treated as an estimate until defined.
- **Confirmed:** Yield is part raw area divided by usable sheet area; trim waste is excluded from the denominator. Required stock quantity is based on grouped repetitions. Waste shown is `100 - yield`.
- **Broken/inconsistent:** Grouping errors and stale `results` cut arrays can affect summaries. Some updates recompute results; others update visible state first. Source part quantities, Temp deletions, and actual placed quantities may diverge.

## Excel and PDF export

- **Confirmed:** Excel export is 2D-only and requires generated layouts. It creates `Summary`, `Layout Colors`, and hidden `!META` sheets, styled through SheetJS, and names the file with active job and timestamp (`exportExcel`, `:7039`). It exports required stocks, source parts, and live representative placement coordinates.
- **Partially implemented:** For multi-work, Excel exports only the active job, not all works. The “rotated” value is calculated in `getLayoutRowsForExcelExport` but no Rotated column is included in `layoutAoa`.
- **Confirmed:** PDF export is 2D-only. A single report includes a summary, scaled visual layouts, part tables, repetition, and the current cut estimate. Multi-work prompts for one combined PDF or one PDF per work (`exportPDF` override, `:7769`).
- **Broken/inconsistent:** Single PDF redraws model geometry, while combined multi-work PDF embeds current canvases. Colours differ from screen/source palette in the single report. Cut calculations again use inconsistent rectangle forms. There is no export exception handling or file-write confirmation.

## Errors, notifications, persistence, and undo/redo

- **Confirmed:** Most 2D errors use a modal-like overlay that automatically hides after 6.5 seconds and can be dismissed with Escape/OK. Multi-work import uses `alert`; PDF mode uses `prompt`; linear errors use an inline element.
- **Broken/inconsistent:** Notification mechanisms and severity are inconsistent. Some `catch` blocks are empty, and copy fallback failures can be silent.
- **Confirmed:** There is no `localStorage`, `sessionStorage`, IndexedDB, server persistence, or project file. Reloading the page loses inputs, results, jobs, locks, Temp, and history.
- **Confirmed:** Undo/redo is in memory, limited to 50 snapshots, and covers manual `sheetStates`, Temp, and locks. Shortcuts are Ctrl/Cmd+Z and Ctrl/Cmd+Y or Shift+Ctrl/Cmd+Z (`:2612-2711`). It does not cover source input edits, imports, optimize runs, settings, or durable job history.
- **Broken/inconsistent:** Several functions push an undo snapshot before validating that an operation can succeed, so failed/no-op edits can consume history entries. Snapshots omit full result metadata and depend on current result/sheet structures when restored.

## Known technical fragility

- Large single global scope with mutable `pieces`, `stockSheets`, `results`, `sheetStates`, `currentLayoutGroups`, `lockedLayouts`, `tempPieces`, `nestingJobs`, widget values, and canvas closures as overlapping sources of truth.
- Late reassignment wraps `importExcel2D`, `optimize`, and `exportPDF`, making control flow order-dependent.
- UI, domain data, geometry, animation, packing, import, and reporting are tightly coupled through DOM lookups and globals.
- Millimetres and pixels are mixed inside `renderResults` closures; trim offsets are repeatedly added/subtracted during pointer conversion.
- CSS contains the original dark theme followed by extensive alpha-version overrides and repeated selectors; hidden UI remains implemented and can drift.
- CDN dependencies make offline startup/import/export/font behavior unreliable and versions are not vendored or integrity-pinned.
- There are no automated tests, fixtures, schema versions, performance benchmarks, structured logs, or project recovery.

