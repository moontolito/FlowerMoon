# Legacy Nesting and Manufacturing Rules

## Purpose

This document combines approved Debbie vNext requirements with evidence extracted from `Nesting_Tool_alpha_v63.html`. Only the **Approved Debbie vNext rules** section is normative. The legacy sections preserve implementation history and contradictions; pending and deferred sections are not approved behavior.

## Approved Debbie vNext rules

The following requirements were approved on 2026-07-18 by **Product Owner: Cuvuliuc Nicolae**. They supersede conflicting legacy behavior for Debbie vNext. See `PRODUCT_DECISIONS.md` for evidence, alternatives, implications, and required tests.

### Units and coordinate layers (`GEO-001`)

- All authoritative 2D dimensions, positions, spacing, and stock dimensions are stored in millimetres.
- Model origin is the top-left of the usable stock area; X increases right and Y increases down.
- Rendering coordinates, pixels, DPI, zoom, and scale exist only in the UI/rendering layer.
- Non-millimetre imports convert to millimetres at the import boundary.
- Display transforms never modify model geometry.

### Numerical policy (`GEO-002`)

- Domain and geometry layers use floating-point millimetres.
- One centralized absolute geometry epsilon of `0.001 mm` governs containment, contact, overlap, boundary checks, and placement validity.
- Display/export precision may default to `0.01 mm`, but rounding never affects geometry predicates, layout identity, hashing, fingerprints, or persistence identity.
- No subsystem may invent an independent geometry tolerance.

### Nominal geometry and inter-part clearance (`GEO-003`)

- Nominal part length and width never include kerf or clearance and are never permanently inflated.
- `minimum_part_clearance` is an explicit non-negative property independent from kerf.
- At zero clearance, exact finished-edge contact is valid. At positive clearance, every committed placement maintains at least that distance.
- A process profile may explicitly initialize clearance from kerf, but the two values remain separately stored and semantically distinct.
- Zero clearance does not enable or imply common-line cutting.

### Usable boundary and boundary clearance (`GEO-004`)

- `boundary_clearance` is explicit, non-negative, and independent from trim, kerf, and `minimum_part_clearance`.
- Its MVP default is `0 mm`; at zero, a finished part may touch the usable stock boundary.
- A positive value consistently reduces the effective placement region on all four sides.
- Automatic nesting and every manual/import/restore geometry transition use the same boundary rule.

### Kerf (`KERF-001`)

- Kerf is the physical cutting width of the active approved process, such as laser, plasma, or saw.
- Kerf is stored separately from nominal part geometry and from both clearance properties.
- Rectangle-nesting validity is governed by explicit clearance, not by kerf-inflated authoritative dimensions.
- Half-kerf compensation belongs to a future process/toolpath layer.
- No MVP output is described as machine-ready toolpath data. Any kerf-derived MVP metric is labeled as estimated.

### Trim and material reporting (`TRIM-001`)

- Trim has four independent non-negative values: left, right, top, and bottom.
- In the MVP, trim belongs to a work/process profile. Every generated layout stores a snapshot of the effective trim used.
- Trimmed area is unavailable for placement. A trim combination that removes the complete usable area is invalid.
- Reports separately show full and usable stock dimensions/areas, trim loss, unoccupied usable area, usable-area utilization, and full-stock material yield.
- Per-stock trim overrides are deferred and must not change the core usable-area contract when later added.

### Part orientation (`ROT-001`)

- Each part type has an explicit set of allowed orientations.
- Rectangular parts default to `{0°, 90°}` and may be restricted to `{0°}`.
- The same orientation policy is enforced by automatic nesting, manual rotation, imports, restored projects, validation, persistence, and exports.
- The MVP supports only 0° and 90°. Mirroring is forbidden.

### Work-owned batches (`BATCH-001`)

- Batch multiplier belongs to each `Work`.
- Required demand is calculated deterministically from part quantity multiplied by the work batch multiplier; the rounding policy must be documented and tested before implementation.
- Every demand item and generated part instance preserves its `work_id`.
- Parts from different works are never combined into one layout.
- Production-lot entities are outside the MVP.

### Independent works and stable identity (`WORK-001`)

- Each `Work` independently owns its parts, batch multiplier, process settings, stock pool, layouts, unplaced demand, and results.
- Stocks are not shared between works and optimization runs independently per work.
- Project reports may aggregate work results but never merge the underlying jobs. Identical geometry in different works remains distinct.
- Stable IDs are required for work, part type, demand item, part instance, stock specification, stock instance, layout, and layout instance.

### Shared validation contract

- One future geometry validator must enforce the approved unit, epsilon, clearance, boundary, trim, and orientation rules for automatic placement, manual editing, rotation, transfer, import, restoration, persistence, and export validation.
- A geometry transition is not committed merely because it renders successfully; it must satisfy the same model-level validator used by nesting.

### Canonical Excel import protection (`IMPORT-001`)

- The canonical import contract is `Debbie Nesting Workbook` schema `1.0`, defined normatively in `EXCEL_SCHEMA_V1.md`; legacy heuristic layouts are not canonical.
- Imported authoritative dimensions and process values are millimetres. Part and stock dimensions remain nominal; kerf, part clearance, boundary clearance, and four-sided trim remain separate values.
- `Allow Rotation = Yes` maps only to `{0°, 90°}` and `No` maps only to `{0°}`. Import does not infer arbitrary angles, mirroring, grain, or face constraints.
- Every imported work has a positive-integer batch multiplier, independent deterministic identity, demand, process profile, and finite work-owned stock. Parts and stocks from different works are never mixed.
- Canonical keys and namespace-based deterministic IDs are independent of worksheet and row order. Labels are not identity.
- Import is atomic: all canonical records, references, effective stock regions, and domain invariants are validated before any usable `Work` objects are returned or active state is changed.
- Invalid rows are never silently skipped/defaulted. Import failures and warnings use structured diagnostics rather than free text alone.
- Canonical and legacy adapters remain separate; a future legacy adapter cannot weaken canonical or domain validation.

## Approved first nesting-engine rules

The following first-engine rules were approved on 2026-07-18 by **Product Owner: Cuvuliuc Nicolae**. They authorize only the bounded solver phase described here; they do not approve editor, reporting, import/export, persistence, or machine-cutting behavior.

### Feasibility class (`NEST-001`)

- Every first-engine result declares `Free rectangular placement — non-guillotine`.
- Generated placements are collision-free rectangles accepted by the shared geometry validator.
- The feasibility class does not guarantee a guillotine sequence, machine toolpath, or manufacturability for every cutting machine.
- User-facing descriptions and future reports must not imply guillotine or machine-ready output.
- Process-specific feasibility and guillotine-only nesting remain separate future capabilities.

### Strategy contract (`NEST-002`)

- The only approved first strategy is `Deterministic Left-to-Right Rectangular Placement`.
- It considers only candidates valid for usable stock, boundary clearance, part clearance, allowed orientation, work ownership, and finite available stock.
- Candidate preference is lexicographic: smallest X; smallest Y; non-rotated before rotated when otherwise equivalent; stable part and stock identifiers as final tie-breakers.
- Stable identifiers are final explicit tie-breakers only; input normalization must not regenerate IDs or derive business ordering from UUID randomness.
- Left-to-right is a candidate preference, not a row, shelf, column, guillotine, cutting-line, or machine-sequence guarantee. Valid placements may occur above or below existing parts.
- The strategy never bypasses collision, clearance, trim, boundary, orientation, ownership, or inventory rules.
- `Ignore Cutting Lines` is not an approved strategy name.
- No second strategy is approved. Every later strategy requires its own decision record, contract, tests, and result metadata.

### Objective and stock consumption (`OPT-001`)

Results are compared lexicographically in this order:

1. Maximize placed required demand.
2. Minimize physical stock sheets consumed.
3. Minimize total nominal full-stock area consumed.
4. Minimize unused usable area only as a later tie-breaker.
5. Apply deterministic stable tie-breakers.

- A later objective never overrides an earlier objective.
- Stock availability is finite, physical sheets are consumed, and stock pools remain isolated by work.
- Full-stock area uses nominal full dimensions, not usable dimensions alone.
- Material cost, remnant value, cutting length, and weighted objectives are excluded.
- Results record the objective policy and its values.
- Allowed descriptions include `generated result`, `selected result`, and `best result found by the active deterministic strategy`. The first solver must not claim `optimal nesting`, a `globally optimized layout`, or a global mathematical optimum.

### Deterministic execution and metadata (`OPT-002`)

- The same approved input, decision-policy version, and engine version produces the same result.
- Input collections use explicit stable ordering and never rely on dictionary hash order, set order, UUID random order, object addresses, or filesystem enumeration.
- Randomized and stochastic search, seeds, genetic algorithms, simulated annealing, and metaheuristics are excluded.
- The core may run synchronously. Its API preserves a future cancellation boundary, while UI-thread and background-worker policy remains deferred.
- Hard runtime targets require benchmarks using representative approved datasets.
- Every result records engine version, strategy identifier, decision-policy version, and deterministic objective metadata.

### Unplaced demand and result status (`NEST-003`)

- A run may return valid layouts with structured unplaced demand; unplaced items do not invalidate correct layouts.
- Every unplaced item retains `work_id`, demand identity, part-type identity, remaining quantity, and a structured reason code.
- Approved initial reason codes are:
  - `PART_EXCEEDS_ALL_USABLE_STOCK`;
  - `INSUFFICIENT_STOCK_QUANTITY`;
  - `NO_VALID_PLACEMENT_FOUND`;
  - `ORIENTATION_CONSTRAINT`;
  - `INVALID_INPUT_REJECTED_BEFORE_RUN`.
- Free-text-only reasons are invalid.
- Approved initial statuses are:
  - `COMPLETE`: all valid required demand was placed;
  - `PARTIAL`: at least one valid required item remains unplaced;
  - `FAILED_VALIDATION`: input was invalid and the run did not begin.
- A solver exception is not a valid partial result.
- Requested demand equals placed instances plus structured unplaced quantity exactly.
- Production release, Temp Zone, and deletion/cancellation semantics remain pending. This decision does not equate Temp with unplaced demand.

### First-solver implementation boundary

The first solver phase may implement deterministic rectangular placement, this one strategy, shared geometry validation, work-isolated runs, finite stock availability, structured unplaced demand, result status, deterministic result metadata, lexicographic objective evaluation, and unit/golden tests.

It must not implement guillotine planning, cutting lines, toolpaths, common-line cutting, cutting-length optimization, machine simulation, arbitrary angles, mirroring, polygon parts, remnants, cost optimization, cross-work stock sharing, random search, multiple strategies, manual editing, Temp Zone, locks, repeated-layout grouping, PDF/Excel, PySide6, background workers, or persistence.

### Solver decision traceability

Future implementation tests and fixtures must include at least:

- `test_NEST_001_result_declares_non_guillotine_feasibility`;
- `test_NEST_002_candidate_order_prefers_smallest_x_then_y`;
- `test_OPT_001_placed_demand_precedes_sheet_count`;
- `test_OPT_002_same_input_produces_same_result`;
- `test_NEST_003_partial_result_reconciles_unplaced_quantity`.

These names document future acceptance coverage; no solver tests or solver implementation exist in this decision-only change.

## Confirmed legacy behavior

### Coordinates and units

- The 2D model operates in millimetres. Imported 2D unit settings are ignored and the hidden units field is forced to `mm` (`apply2DSettingsMap`).
- Placement coordinates use an origin at the top-left of the **usable** stock rectangle. X increases rightward and Y increases downward.
- Full-stock rendering converts usable coordinates by adding left and top trim offsets. Canvas scaling then converts millimetres to logical pixels; device-pixel ratio and visual zoom affect only the backing/display scale.
- Linear mode can label values as mm, cm, or inches but performs no unit conversion; entered values are treated as one consistent unit.

### Stock and trim

- A stock record has full length, full width, quantity, and a generated label.
- One global trim setting applies to every stock size: `usableW = fullW - left - right`, `usableH = fullH - top - bottom`.
- Stock with non-positive usable dimensions is skipped.
- Stock inventory quantity is a hard upper limit during an automatic pass.
- Among usable stock candidates, strategies prioritize the candidate placing the most pieces, then apply strategy-specific waste/extent tie-breakers.

### Parts, batches, and orientation

- Source parts are axis-aligned rectangles with length, width, label, and quantity.
- Required instances equal `round(source quantity × rounded batch count)`, with batches clamped to at least one.
- Automatic nesting always permits a 90-degree rotation. There is no active 2D rotation-disable rule.
- Rotation swaps width and height and toggles a `rotated` flag. No arbitrary angles are supported.
- A part is initially classified as oversized only when neither normal nor rotated raw dimensions fit any usable stock.

### Kerf and spacing representation

- Automatic packers normally represent occupancy as `(raw width + kerf) × (raw height + kerf)`.
- Sheet-boundary checks generally use raw/visible dimensions (`occupied dimension - kerf`), allowing a part to touch the usable stock boundary without reserving kerf against it.
- Part-to-part collision uses occupied dimensions. With positive kerf this reserves approximately one full kerf between visible rectangular edges along the separating axis.
- With zero kerf, exact edge contact is allowed because collision comparisons use strict overlap.

### Placement validity

- A valid automatic/manual placement is intended to keep the raw part inside the usable stock and prevent overlap of kerf-inflated occupied rectangles.
- Same-layout drag uses the moved part/group as fixed and may push other parts. If overlaps cannot be resolved, the drag is reverted.
- Cross-layout robust drag may shift the dropped group and push existing destination parts. If no solution is found, the source placement is restored.
- Keyboard movement is rejected for a sheet unless all selected parts can move by the requested increment without boundary/collision failure.

### Strategies

- **Area Priority:** Sorts by descending raw area and uses a guillotine free-rectangle packer. It tests four split rules and two rotation preferences, then minimizes unplaced count and sheet count.
- **Left-to-Right Fill:** Sorts primarily by descending height then width and repeatedly chooses the candidate with smallest X, then Y, then larger area. It is collision-based, not guillotine-feasible by definition.
- **Free Area Optimization:** Sorts by descending area and places into MaxRects-like free rectangles using local waste/short-side/long-side score. It is not a cut-sequence strategy.

### Multiple sheets, batches, and unplaced parts

- Packing consumes physical stock entries until demand is placed or available stock cannot accept more parts.
- Geometrically identical physical results are grouped and shown once with a repetition count.
- Oversized pieces and pieces remaining after packing are sent to Temp and reported, while valid layouts still render.
- A job is considered calculable with partial placement; the UI warns but does not reject the entire result.

### Manual locks

- Locking clones the representative layout for its repetition count. A later Optimize subtracts those source-key occurrences from demand and carries the cloned layouts forward.
- Editing stock/parts/settings in the left panel marks inputs dirty; the next Optimize clears all locks.

## Legacy behavior inferred from code

- Length maps to horizontal X/width and width maps to vertical Y/height in the default orientation. This is consistent throughout rectangular placement but is not formally described for grain or rolling direction.
- The kerf model intends an inter-part blade gap, not a perimeter allowance. Comments explicitly state this, but implementation paths are not uniform.
- “Required stocks” intends physical full-size sheet counts; layout metrics use usable area, so trim is treated as unavailable material rather than nested waste.
- Temp represents outstanding/unassigned demand, but the ability to delete Temp items suggests it is also used as an operator scratch area.
- Locks intend to preserve operator-approved layouts during recalculation, not necessarily prevent all editing, although the label and keyboard behavior imply both meanings.

## Legacy behavior currently inconsistent

### Coordinate and geometry consistency

- Stored `w/h` usually mean raw dimension plus kerf, while `rawW/rawH`, `pw/ph`, and rendered dimensions may mean raw size. Different functions choose different fields as authoritative.
- Collision tolerances vary: roughly 0.0001, 0.001, and 0.01 mm. Layout/group fingerprints round to either whole millimetres or 0.01 mm.
- Cross-layout context-menu transfer uses the first rendered sheet’s usable dimensions instead of the actual target sheet. Other transfer paths use target dimensions.
- Manual rotation clamps to boundaries but does not validate collisions, so it can create an overlapping layout.
- Lock state blocks keyboard nudging but does not consistently block mouse drag, transfer, Temp movement, or rotation.

### Edge touch and kerf

- Exact occupied-rectangle touch is valid, but callers do not consistently pass occupied rectangles. Some computations subtract kerf first, effectively permitting closer placement or changing cut endpoints.
- The guillotine strategy sometimes packs into `usable + kerf` dimensions to allow far-edge occupancy, while left-fill packs into raw usable dimensions with custom boundary subtraction. Equivalent inputs therefore travel through different geometry models.

### Layout identity and completion

- Repetition fingerprints ignore stock dimensions and part identity. Two layouts can be classified as identical solely because rounded positions and sizes match.
- Deleting a Temp item reduces visible outstanding demand without changing the source cut list. There is no authoritative reconciliation status for “job complete.”
- A partially placed job with Temp items still produces stock and report exports; whether that is a completed manufacturing job is not indicated.

### Cutting length

- Guillotine initial results track split cuts, but most live metrics reconstruct only internal right/bottom part edges.
- Callers sometimes calculate with raw rectangles and sometimes kerf-inflated rectangles. Deduplication rounds endpoints to whole units.
- Outer perimeter, trim cuts, common-line sharing, pierces, lead-ins/outs, sequencing, and machine travel are omitted. The displayed value is not a defined toolpath length.

### Batches and multi-work

- Code comments describe batches as global across works, while imported jobs store and display a per-work batch. PDF multi-work paths preserve/force a global batch value in some flows.
- Excel exports only the active work; PDF can export all works. There is no common multi-work export contract.

## Pending Debbie vNext decisions

- What “cutting length” and “cut count” must include and whether they are estimates, saw cuts, or machine toolpaths.
- What production release permits when a result is partial, how Temp relates to structured unplaced demand, and what Temp deletion means.
- Whether a locked layout is immutable, only preserved during Optimize, or both.
- Whether editing one representative of a repeated layout edits all repetitions, splits off one physical sheet, or asks the operator.
- Exact deterministic rounding rule for non-integral part quantity multiplied by work batch multiplier.
- Which Excel schemas, export contracts, project format, and hidden linear-cutting capability belong to the first Python release.
- Whether current production requires clamp/keep-out zones beyond four-sided trim.

## Questions for Product Owner

1. Define cutting length and cut count for Debbie: which boundaries, shared cuts, trim cuts, pierces, and toolpath motions are included?
2. When structured unplaced demand remains, may the job be exported or released for production, and what status or approval is required?
3. How should future Temp behavior relate to structured unplaced demand, and what should deleting a Temp item mean?
4. Does locking prevent all edits, preserve a layout across recalculation, or both?
5. When an operator edits a layout shown with repetition greater than one, should the edit apply to all copies or split a single sheet from the group?
6. How must non-integral `part quantity × work batch multiplier` be rounded?
7. Which legacy Excel formats and which hidden Linear Cuts capability must be supported in the first stable Python release?
8. Do current MVP machines require clamp or keep-out zones beyond trim and `boundary_clearance`?

## Deferred capabilities

- Common-line cutting and all half-kerf/toolpath compensation.
- Machine-ready toolpaths, lead-ins/outs, sequencing, travel, and process-specific cut planning.
- Arbitrary-angle rotation and mirroring support; mirroring remains forbidden in the MVP.
- Grain direction and coating/visible-face constraints until introduced as explicit part constraints.
- Per-stock trim overrides and non-rectangular clamp/keep-out regions.
- Production-lot entities.
- Shared project inventory, stock sharing between works, cross-work optimization, and cross-work layout merging.
