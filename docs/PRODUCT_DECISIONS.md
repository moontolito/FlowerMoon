# Debbie Product Decision Register

## Purpose and use

This register turns unresolved audit findings into explicit Product Owner decisions. Legacy behavior is evidence, not an automatic requirement. A recommendation is an engineering proposal only; it must not be implemented as decided behavior while its Product Owner field remains pending.

Statuses used here are:

- **Accepted:** explicitly approved by the Product Owner and recorded with approver and date.
- **Pending — blocking:** must be approved before the named implementation foundation begins.
- **Pending — UI gate:** may wait until the domain and geometry contracts exist, but must be resolved before editor implementation.
- **Deferred:** intentionally outside the MVP; preserve an architectural boundary without implementing the feature.

## Critical Decisions Before Coding

The smallest set that blocks domain and geometry foundations is:

1. `GEO-001` — millimetres and the model/display coordinate boundary.
2. `GEO-002` — numeric representation, tolerance, and comparison policy.
3. `GEO-003` — part edge-touch and minimum inter-part clearance.
4. `GEO-004` — usable-boundary contact and boundary clearance.
5. `KERF-001` — the meaning of kerf and how compensation is represented.
6. `TRIM-001` — full stock, per-side trim, usable area, and waste semantics.
7. `ROT-001` — allowed orientations and per-part restrictions.
8. `BATCH-001` and `WORK-001` — quantity scope, work identity, and stock ownership.

All decisions in this critical set were approved on 2026-07-18 by Product Owner Cuvuliuc Nicolae. The first domain and geometry decision content gate is therefore passed. Production Python work remains gated until this documentation update is reviewed and committed. `CUT-001` and `METRIC-001` do not block basic rectangle validity, but must be resolved before metrics are named or exported as production information. Other pending records continue to block only their stated later phases.

## Decisions required before domain-model implementation

### GEO-001 — Authoritative units and coordinate layers

- **Decision ID:** `GEO-001`
- **Topic:** Geometry and units.
- **Problem being decided:** Choose the authoritative model unit and prevent rendering scale, zoom, or device pixels from becoming domain data.
- **Current confirmed legacy behavior:** 2D input and model values are treated as millimetres. Placement origin is the top-left of usable stock, X increases right, Y increases down, and rendering adds trim offsets before scaling to pixels.
- **Legacy inconsistencies or risks:** Millimetre and pixel calculations coexist inside canvas closures; imported 2D units are ignored; linear mode labels other units without conversion.
- **Available options:**
  1. Millimetres as canonical model coordinates, with explicit transforms to display pixels. **Implication:** simplest deterministic domain and geometry APIs; imports must convert other units at boundaries.
  2. Unit-bearing values throughout the core. **Implication:** safer multi-unit arithmetic but more types and conversion paths in the MVP.
  3. Preserve unitless legacy numbers. **Implication:** smallest apparent porting effort but repeats ambiguity and is unsafe for commercial interoperability.
- **Recommended default for Debbie vNext:** Option 1. Store all 2D model dimensions and coordinates in millimetres; keep view transforms in the UI/rendering layer. Retain top-left/X-right/Y-down for rectangular parity unless later CAD integration justifies a separate Cartesian adapter.
- **Product Owner decision:** **Approved — Option 1 with binding MVP requirements:** all authoritative 2D dimensions, positions, spacing values, and stock dimensions use millimetres; rendering coordinates, zoom, DPI, scale, and pixels remain UI/rendering concerns; the origin is the top-left of usable stock, X increases right, and Y increases down; non-millimetre imports convert at the import boundary; display scaling never mutates model geometry. **Approver:** Cuvuliuc Nicolae. **Role:** Product Owner. **Approval date:** 2026-07-18.
- **Decision status:** **Accepted — 2026-07-18.** The complete unit, axis, import-conversion, and model/view boundary is binding for the MVP.
- **Affected future modules:** `domain`, `geometry`, `ui`, `reporting`, `io`, `persistence`.
- **Required tests after the decision:** Unit conversion boundary tests; zoom/DPI invariance; model-to-view/view-to-model round trips; project/report values unchanged by display scale.

### TRIM-001 — Full stock, trim, usable area, and reporting

- **Decision ID:** `TRIM-001`
- **Topic:** Trim and stock area.
- **Problem being decided:** Define trim as data, decide whether it is per side and per stock/work, and define its effect on usable area and material metrics.
- **Current confirmed legacy behavior:** Four global per-side values are subtracted from every stock size. Trimmed space is unavailable to nesting. Yield uses usable area, excluding trim from its denominator; reports show full stock dimensions.
- **Legacy inconsistencies or risks:** “Global” trim may not fit different machines/materials/stocks; left/top offsets are retained more consistently than right/bottom; excluding trim can make waste appear lower than material actually consumed.
- **Available options:**
  1. Four per-side trim values in each work/process profile; trimmed area is unusable. Report both usable-area efficiency and full-sheet material yield. **Implication:** explicit domain model and transparent metrics with manageable MVP scope.
  2. One symmetric trim value. **Implication:** simpler UI but cannot represent the confirmed four-edge workflow.
  3. Trim per stock instance. **Implication:** maximum flexibility but increases input and inventory complexity.
- **Recommended default for Debbie vNext:** Option 1, with effective trim copied into every generated layout snapshot. Allow a work-level default that can later be overridden by stock/process profile.
- **Product Owner decision:** **Approved — Option 1 with binding MVP requirements:** trim has independent non-negative left, right, top, and bottom values at work/process-profile level; every layout snapshots its effective trim; trimmed area is unavailable; trim that removes the complete usable area is rejected; reports distinguish full and usable dimensions/areas, trim loss, unoccupied usable area, usable-area utilization, and full-stock yield. Per-stock overrides are deferred without changing the core contract. **Approver:** Cuvuliuc Nicolae. **Role:** Product Owner. **Approval date:** 2026-07-18.
- **Decision status:** **Accepted — 2026-07-18.** Four-sided work-level trim and transparent material reporting are binding for the MVP; per-stock overrides are deferred.
- **Affected future modules:** `domain`, `geometry`, `nesting`, `metrics`, `reporting`, `io`, `persistence`.
- **Required tests after the decision:** Per-side usable bounds; invalid over-trim; full versus usable area metrics; asymmetric trim rendering; export round trip.

### ROT-001 — Allowed orientations and per-part restrictions

- **Decision ID:** `ROT-001`
- **Topic:** Rotation and manufacturing constraints.
- **Problem being decided:** Define valid rectangular orientations and whether rotation is a job default or an explicit per-part constraint.
- **Current confirmed legacy behavior:** Automatic nesting always considers 0° and 90°; manual rotation toggles 90°; no active setting disables it.
- **Legacy inconsistencies or risks:** Imported rotation keys are ignored. Automatic rotation may violate grain, coating, finish, or manufacturing direction. Manual rotation may create collisions.
- **Available options:**
  1. Each part has an allowed-orientation set, defaulting to `{0°, 90°}` for legacy-compatible rectangular parts. **Implication:** clear domain invariant and future constraints without arbitrary-angle geometry.
  2. One job-wide allow-rotation flag. **Implication:** simpler MVP but cannot represent mixed restrictions.
  3. Always allow 90°. **Implication:** closest to legacy but unsafe for directional material.
- **Recommended default for Debbie vNext:** Option 1. Import or user entry must be able to restrict a part to 0°; keep 0°/90° only in the MVP.
- **Product Owner decision:** **Approved — Option 1 with binding MVP requirements:** every part type has an explicit allowed-orientation set; rectangular parts default to `{0°, 90°}` and may be restricted to `{0°}`; automatic nesting, manual edits, imports, restored projects, and exports enforce the same policy; only 0° and 90° are supported; mirroring is forbidden. Arbitrary angles are deferred, and grain/visible-face constraints may be added later only as explicit constraints. **Approver:** Cuvuliuc Nicolae. **Role:** Product Owner. **Approval date:** 2026-07-18.
- **Decision status:** **Accepted — 2026-07-18.** Per-part orientation sets are binding; arbitrary rotation, mirroring support, grain, and visible-face extensions are outside the MVP as stated.
- **Affected future modules:** `domain`, `geometry`, `nesting`, `io`, `ui`, `reporting`.
- **Required tests after the decision:** Orientation-set validation; non-rotatable fit failures; width/height swap; identity preservation; manual and automatic enforcement.

### ROT-002 — Grain, face, mirroring, and future angles

- **Decision ID:** `ROT-002`
- **Topic:** Advanced orientation constraints.
- **Problem being decided:** Decide which directional attributes must exist now and which transformations are prohibited or deferred.
- **Current confirmed legacy behavior:** No grain, coating/visible-face, mirror, or arbitrary-angle model exists. Rectangles rotate only 90° and are never mirrored explicitly.
- **Legacy inconsistencies or risks:** A plain rectangle cannot express manufacturing direction; mirroring may be visually indistinguishable while still invalid for a real part.
- **Available options:**
  1. MVP stores optional grain/face policy and forbids mirroring/arbitrary angles; only enforce fields supported by approved imports. **Implication:** preserves future data semantics without polygon complexity.
  2. Omit all directional metadata until CAD support. **Implication:** smaller MVP but project/import schemas may later require migration.
  3. Implement arbitrary rotation and mirroring now. **Implication:** major geometry/CAD scope expansion.
- **Recommended default for Debbie vNext:** Option 1 only if real MVP jobs require directional material; otherwise Option 2 with explicit extension fields. Defer arbitrary angles and mirroring.
- **Product Owner decision:** **Not independently approved.** Accepted decision `ROT-001` excludes arbitrary angles and mirroring from the MVP and defers grain/visible-face constraints. Any later directional-constraint or transformation design requires a new approval.
- **Decision status:** Deferred from the MVP by `ROT-001`; not a blocker for the approved rectangular part model.
- **Affected future modules:** `domain`, `io`, `geometry`, `nesting`, `persistence`.
- **Required tests after the decision:** Grain-compatible orientation tests; forbidden mirror tests; serialization of optional constraints; rejection of unsupported angles.

### BATCH-001 — Batch scope and layout mixing

- **Decision ID:** `BATCH-001`
- **Topic:** Batches and quantities.
- **Problem being decided:** Define where batch quantity lives and whether batch identity affects layout eligibility and traceability.
- **Current confirmed legacy behavior:** Demand is `round(part quantity × rounded batch count)`. Comments call batches global, but multi-work jobs store/display per-work values. No stock-level batch exists and expanded parts lose distinct batch identity.
- **Legacy inconsistencies or risks:** Multi-work PDF paths temporarily force a global value. Mixing batches is implicit, and reports cannot trace an instance to a batch.
- **Available options:**
  1. Batch multiplier belongs to each work; identical parts from that work may share layouts unless an explicit production-lot constraint forbids it. **Implication:** matches multi-work data model and keeps MVP simple.
  2. One batch multiplier for the whole project/workbook. **Implication:** simpler bulk change but prevents independent works.
  3. Explicit batch/lot entities with no cross-lot mixing. **Implication:** strongest traceability but materially larger MVP.
- **Recommended default for Debbie vNext:** Option 1. Preserve a work ID on every demand item and defer production-lot entities.
- **Product Owner decision:** **Approved — Option 1 with binding MVP requirements:** batch multiplier belongs to each `Work`; required demand is part quantity multiplied by that work's batch multiplier; deterministic multiplication and rounding must be documented; every demand item and generated instance preserves `work_id`; different works never share a layout; production-lot entities are not part of the MVP. **Approver:** Cuvuliuc Nicolae. **Role:** Product Owner. **Approval date:** 2026-07-18.
- **Decision status:** **Accepted — 2026-07-18.** Work-owned batching and cross-work isolation are binding; production-lot modeling is deferred. The exact deterministic rounding algorithm remains a documented implementation prerequisite.
- **Affected future modules:** `domain`, `application`, `nesting`, `io`, `reporting`, `persistence`.
- **Required tests after the decision:** Quantity multiplication and rounding; independent work batches; no cross-work identity loss; report reconciliation.

### WORK-001 — Work independence, stock ownership, and cross-work repetition

- **Decision ID:** `WORK-001`
- **Topic:** Multi-work projects.
- **Problem being decided:** Define whether works are independent jobs, whether they share stock inventory, and whether layouts may be consolidated across works.
- **Current confirmed legacy behavior:** Each imported worksheet becomes an in-memory work with its own inputs/results. Optimization loops over works independently. Repetition grouping occurs within the active work; there is no shared inventory allocator.
- **Legacy inconsistencies or risks:** Combined PDF presentation can look project-wide while stock and batches are not reconciled project-wide. Cross-work identical layouts are not formally identified.
- **Available options:**
  1. Works are independent nesting jobs with independent stock pools; project reports aggregate but do not merge layouts. **Implication:** deterministic ownership and achievable MVP.
  2. Works share one project stock pool. **Implication:** requires coordinated optimization and allocation transactions.
  3. Allow configurable sharing/consolidation. **Implication:** commercially useful but significantly expands UI and solver scope.
- **Recommended default for Debbie vNext:** Option 1. Keep stable work and layout IDs so later aggregation is possible without changing geometry identity.
- **Product Owner decision:** **Approved — Option 1 with binding MVP requirements:** each `Work` independently owns its parts, batch multiplier, process settings, stock pool, layouts, unplaced demand, and results; stocks are not shared; optimization is independent; project reporting may aggregate without merging jobs; identical geometry in different works remains distinct. Stable IDs are required for work, part type, demand item, part instance, stock specification, stock instance, layout, and layout instance. Shared inventory and cross-work optimization are deferred commercial capabilities. **Approver:** Cuvuliuc Nicolae. **Role:** Product Owner. **Approval date:** 2026-07-18.
- **Decision status:** **Accepted — 2026-07-18.** Independent work ownership, stock isolation, and stable identity requirements are binding; shared inventory and cross-work optimization are deferred.
- **Affected future modules:** `domain`, `application`, `nesting`, `metrics`, `reporting`, `persistence`.
- **Required tests after the decision:** Work isolation; inventory isolation; combined-report aggregation; same geometry in different works remains distinct.

### TEMP-001 — Temp Zone and outstanding demand

- **Decision ID:** `TEMP-001`
- **Topic:** Unplaced and manually staged parts.
- **Problem being decided:** Define whether Temp is demand status, a staging area, or both, and what deletion means.
- **Current confirmed legacy behavior:** Oversized/unplaced and manually removed instances enter Temp. They can be placed back, moved there manually, or deleted. Deletion does not change the source cut-list quantity.
- **Legacy inconsistencies or risks:** Demand, placed instances, source quantity, and Temp can stop reconciling. A partial job can still be exported without a formal completion state.
- **Available options:**
  1. Temp is an explicit `Unplaced/Staged` demand state; removal requires a “cancel demand” command with reason and quantity reconciliation. **Implication:** safe, auditable, and testable.
  2. Temp is visual scratch storage and deletion is allowed. **Implication:** easy interaction but unsafe reporting.
  3. Separate `Unplaced` from an optional scratch clipboard. **Implication:** clearest semantics but extra UI concepts.
- **Recommended default for Debbie vNext:** Option 1 for MVP. Do not provide silent deletion; use an explicit cancel/adjust-demand workflow.
- **Product Owner decision:** **Pending.**
- **Decision status:** Pending — domain model before editor behavior.
- **Affected future modules:** `domain`, `application`, `ui`, `metrics`, `reporting`, `persistence`.
- **Required tests after the decision:** Quantity conservation; move to/from Temp; cancellation audit; partial-job status; export warning/block policy.

### PERSIST-001 — Project-file format and state ownership

- **Decision ID:** `PERSIST-001`
- **Topic:** Project persistence.
- **Problem being decided:** Define the future local project boundary and what must survive save/load.
- **Current confirmed legacy behavior:** No browser storage or project file exists; all state is lost on reload. Excel is input/configuration, not a complete project snapshot.
- **Legacy inconsistencies or risks:** Treating Excel as persistence would lose identities, manual edits, locks, status, and schema evolution.
- **Available options:**
  1. Versioned Debbie project container using a documented JSON schema, optionally zipped later for assets. **Implication:** inspectable, migratable, and simple for MVP.
  2. SQLite project files. **Implication:** transactional and scalable but less transparent and heavier migration tooling.
  3. Excel as the project format. **Implication:** familiar but cannot safely own complete application state.
- **Recommended default for Debbie vNext:** Option 1 with atomic writes, schema version, units, IDs, decision-policy version, and import provenance. Keep Excel as interchange.
- **Product Owner decision:** **Pending.**
- **Decision status:** Pending before persistence implementation; core models should remain serializable meanwhile.
- **Affected future modules:** `domain`, `persistence`, `application`, `io`, `ui`.
- **Required tests after the decision:** Round trip; version migration; corrupt/unknown version rejection; atomic-save recovery; identity preservation.

## Decisions required before geometry-engine implementation

### GEO-002 — Numerical representation and tolerance

- **Decision ID:** `GEO-002`
- **Topic:** Floating-point comparison.
- **Problem being decided:** Select the numeric representation and one policy for equality, containment, contact, hashing, and exported rounding.
- **Current confirmed legacy behavior:** JavaScript numbers are used. Tolerances vary around 0.0001, 0.001, and 0.01 mm; fingerprints round to whole millimetres or hundredths.
- **Legacy inconsistencies or risks:** The same placement can be valid in one path and invalid in another; rounding can merge distinct layouts.
- **Available options:**
  1. Floating-point millimetres with a centralized absolute geometry epsilon and separate display/export rounding. **Implication:** practical and fast, but predicates must be carefully tested.
  2. Integer micrometres or another fixed quantum. **Implication:** deterministic equality but import conversion and overflow/scale policy are required.
  3. Decimal arithmetic. **Implication:** exact decimal inputs but slower and not automatically simpler for geometry algorithms.
- **Recommended default for Debbie vNext:** Option 1, with a documented epsilon chosen from real machine/input precision; never use display rounding for identity.
- **Product Owner decision:** **Approved — Option 1 with binding MVP requirements:** use floating-point millimetres and one centralized absolute geometry epsilon of `0.001 mm` for containment, contact, overlap, boundary checks, and placement validity. Display/export precision may default to `0.01 mm` but never affects predicates, layout identity, hashing, fingerprints, or persistence identity. No subsystem may invent its own geometry tolerance. **Approver:** Cuvuliuc Nicolae. **Role:** Product Owner. **Approval date:** 2026-07-18.
- **Decision status:** **Accepted — 2026-07-18.** The numeric representation and centralized epsilon are binding for all geometry transitions.
- **Affected future modules:** `geometry`, `domain`, `nesting`, `metrics`, `reporting`, `persistence`.
- **Required tests after the decision:** Just-inside/outside boundaries; near-touch symmetry; translation/rotation invariance; stable serialization; tolerance-aware but identity-safe comparisons.

### GEO-003 — Part edge-touch and minimum inter-part clearance

- **Decision ID:** `GEO-003`
- **Topic:** Collision and spacing.
- **Problem being decided:** Decide whether finished part edges may touch and define minimum separation independently from cutting compensation.
- **Current confirmed legacy behavior:** Exact occupied-rectangle contact is non-overlap. With positive kerf, part occupancy is usually raw size plus one kerf, producing approximately a full-kerf visible gap.
- **Legacy inconsistencies or risks:** Raw and inflated rectangles are mixed; edge touch can mean raw touch or kerf-envelope touch depending on the caller.
- **Available options:**
  1. Explicit `minimum_part_clearance` independent of kerf; zero allows exact edge touch unless common-line rules say otherwise. **Implication:** unambiguous geometry and machine profiles.
  2. Clearance always equals kerf. **Implication:** simple but conflates machine/process concepts.
  3. Inflate each part by half the required gap on all sides. **Implication:** symmetric math, but boundaries and pair identity need careful handling.
- **Recommended default for Debbie vNext:** Option 1. Use a pairwise clearance predicate; default value may equal kerf only through an explicit process-profile setting.
- **Product Owner decision:** **Approved — Option 1 with binding MVP requirements:** nominal part dimensions remain unchanged; `minimum_part_clearance` is explicit, non-negative, and stored separately from kerf; zero permits exact finished-edge contact and a positive value is enforced on every committed placement. A process profile may initialize clearance from kerf only explicitly; the properties remain separate. Clearance must not be persisted by inflating part dimensions. Zero clearance does not imply common-line cutting, which is deferred. **Approver:** Cuvuliuc Nicolae. **Role:** Product Owner. **Approval date:** 2026-07-18.
- **Decision status:** **Accepted — 2026-07-18.** Explicit clearance and nominal-geometry preservation are binding; common-line cutting is deferred.
- **Affected future modules:** `domain`, `geometry`, `nesting`, `ui`, `validation`.
- **Required tests after the decision:** Zero-clearance touch; exact required gap; epsilon below/above; corner contact; mixed-rule pairs if later allowed.

### GEO-004 — Usable-boundary contact and minimum boundary clearance

- **Decision ID:** `GEO-004`
- **Topic:** Stock-boundary validity.
- **Problem being decided:** Decide whether a finished part may touch the usable stock boundary and whether a separate machine clearance applies.
- **Current confirmed legacy behavior:** Raw parts may touch usable boundaries; kerf is generally not reserved at stock edges. Trim defines the boundary.
- **Legacy inconsistencies or risks:** Some packers simulate this by adding kerf to usable dimensions, while manual paths subtract kerf in bounds checks. Clamp and machine constraints do not exist.
- **Available options:**
  1. Explicit non-negative `boundary_clearance`, independent per process/profile; zero permits touch. **Implication:** one clear usable-region erosion operation.
  2. Always reserve kerf at boundaries. **Implication:** simple but may waste material and misrepresent processes.
  3. Preserve unconditional boundary touch. **Implication:** legacy-compatible but cannot model clamps or edge quality.
- **Recommended default for Debbie vNext:** Option 1, with zero as the provisional legacy-compatible default until a process rule is approved.
- **Product Owner decision:** **Approved — Option 1 with binding MVP requirements:** `boundary_clearance` is explicit, non-negative, and independent from trim, kerf, and part clearance; its MVP default is `0 mm`; zero permits finished-edge contact with usable stock, while a positive value reduces the effective placement region consistently on every side. Automatic and manual placement use the same rule. Future process profiles may configure it for edge quality, clamps, or machine limits. **Approver:** Cuvuliuc Nicolae. **Role:** Product Owner. **Approval date:** 2026-07-18.
- **Decision status:** **Accepted — 2026-07-18.** The independent boundary-clearance contract and zero default are binding for the MVP.
- **Affected future modules:** `domain`, `geometry`, `nesting`, `ui`, `reporting`.
- **Required tests after the decision:** Four-side contact/clearance; asymmetric trim plus clearance; too-small usable region; manual and automatic parity.

### KERF-001 — Kerf meaning and compensation model

- **Decision ID:** `KERF-001`
- **Topic:** Cutting-width semantics.
- **Problem being decided:** Define whether kerf is physical blade width, laser/plasma cut width, or a generic process value, and how it relates to finished geometry.
- **Current confirmed legacy behavior:** A single “Blade Kerf” value inflates each rectangle by a full kerf in both axes for most nesting paths. Reports subtract it to recover visible size.
- **Legacy inconsistencies or risks:** This storage model mixes finished dimensions and occupancy. It does not explicitly model a centerline or half-kerf compensation and calls every process a blade.
- **Available options:**
  1. Kerf is process cutting width stored separately from nominal part geometry; compensation/toolpath owns half-kerf offsets, while nesting consumes explicit clearance policy. **Implication:** clean manufacturing model and future laser/saw support.
  2. Kerf directly equals required inter-part gap. **Implication:** achievable MVP but cannot distinguish tool width from clearance.
  3. Store kerf-inflated part dimensions. **Implication:** easiest legacy port but repeats source-of-truth defects.
- **Recommended default for Debbie vNext:** Option 1 in the domain. For a rectangle-only MVP without toolpaths, expose an explicit spacing setting and label any kerf-derived metric as estimated.
- **Product Owner decision:** **Approved — Option 1 with binding MVP requirements:** kerf is the physical cutting width of the active approved process, including laser, plasma, saw, or another process; it is stored separately and never mutates nominal part geometry. Rectangle nesting uses explicit clearance for validity. Half-kerf compensation belongs to a future process/toolpath layer. No output is machine-ready without an actual toolpath module, and any MVP kerf-derived metric is labeled estimated. **Approver:** Cuvuliuc Nicolae. **Role:** Product Owner. **Approval date:** 2026-07-18.
- **Decision status:** **Accepted — 2026-07-18.** Physical kerf and nominal geometry separation are binding; compensation/toolpaths are deferred.
- **Affected future modules:** `domain`, `geometry`, `nesting`, `metrics`, `reporting`, future `toolpath`.
- **Required tests after the decision:** Nominal dimensions never mutate; process width serialization; half-width compensation tests when toolpaths exist; no double application.

### KERF-002 — Where kerf/clearance is enforced and common-line boundary

- **Decision ID:** `KERF-002`
- **Topic:** Kerf enforcement scope.
- **Problem being decided:** Decide whether the same separation applies in automatic nesting, manual editing, imports, restoration, and stock boundaries, and define the future common-line exception.
- **Current confirmed legacy behavior:** Kerf-aware collision is intended for automatic and manual movement, but several paths pass different rectangle forms. Boundary kerf is generally omitted. Common-line cutting is not modeled.
- **Legacy inconsistencies or risks:** Imported/restored/exported layouts are not uniformly revalidated; manual rotation can overlap; a future common-line feature could silently invalidate the normal collision rule.
- **Available options:**
  1. One layout validator enforces nominal bounds plus clearance for every state transition; common-line is a future explicit rule/mode. **Implication:** predictable and testable.
  2. Enforce only in the automatic solver and warn during editing. **Implication:** easier editor but allows invalid saved/exported states.
  3. Allow operation-specific rules. **Implication:** flexible but recreates legacy inconsistency.
- **Recommended default for Debbie vNext:** Option 1. Kerf itself applies only where the approved process model requires it; clearance and boundary rules remain explicit. Defer common-line cutting.
- **Product Owner decision:** **Partially resolved, not independently accepted.** `GEO-003`, `GEO-004`, and `KERF-001` require the shared rectangle validator to enforce explicit clearance and boundary rules for every committed automatic or manual placement, while physical kerf remains separate. Common-line cutting and process/toolpath kerf enforcement are deferred and require later approval.
- **Decision status:** The rectangle-validator portion is governed by accepted decisions and no longer blocks MVP geometry. Process/toolpath enforcement and common-line behavior remain deferred.
- **Affected future modules:** `geometry`, `application`, `nesting`, `ui`, `io`, `persistence`, future `toolpath`.
- **Required tests after the decision:** Same validity result for nest/move/rotate/import/load/export; boundary policy; invalid legacy layout diagnostics; future common-line feature flag isolation.

### TRIM-002 — Clamp and machine keep-out zones

- **Decision ID:** `TRIM-002`
- **Topic:** Non-rectangular unavailable stock regions.
- **Problem being decided:** Decide whether MVP geometry must represent clamps/keep-outs beyond four-edge trim.
- **Current confirmed legacy behavior:** Only a rectangular usable area derived from four trims exists.
- **Legacy inconsistencies or risks:** Encoding clamps as larger trim wastes usable area; ignoring them can produce unmanufacturable layouts.
- **Available options:**
  1. MVP supports only rectangular trim and records keep-outs as a deferred process-profile capability. **Implication:** simple rectangle engine and explicit limitation.
  2. Add rectangular internal/edge keep-out zones now. **Implication:** moderate collision and UI expansion.
  3. Add arbitrary polygon keep-outs. **Implication:** major CAD geometry scope.
- **Recommended default for Debbie vNext:** Option 1 unless current production cannot safely operate without clamps. Design the validator to accept a future usable-region abstraction.
- **Product Owner decision:** **Pending.**
- **Decision status:** Pending scope check; otherwise deferred after geometry MVP.
- **Affected future modules:** `domain`, `geometry`, `nesting`, `ui`, process profiles.
- **Required tests after the decision:** MVP rejects/flags unsupported keep-outs; future keep-out intersection and persistence tests.

## Decisions required before nesting-engine implementation

### NEST-001 — Guillotine feasibility requirement

- **Decision ID:** `NEST-001`
- **Topic:** Manufacturing feasibility by strategy.
- **Problem being decided:** Determine whether every accepted layout must have a guillotine cut sequence or whether any collision-free rectangular layout is valid.
- **Current confirmed legacy behavior:** Area Priority is guillotine-based. Left-to-Right and Free Area are explicitly not guillotine strategies, yet all are selectable as valid outputs.
- **Legacy inconsistencies or risks:** Strategy names do not communicate machine feasibility; reports show cut estimates without an executable sequence.
- **Available options:**
  1. Process profile declares required feasibility; MVP supports one approved class and labels others unsupported. **Implication:** safest extensible model.
  2. Require guillotine feasibility for all MVP layouts. **Implication:** narrower solver scope and clear saw use case.
  3. Accept any non-overlapping rectangle layout. **Implication:** higher yield potential but may not be manufacturable on target equipment.
- **Recommended default for Debbie vNext:** Option 1; ship only the feasibility class backed by real MVP machines and tests.
- **Product Owner decision:** **Pending.**
- **Decision status:** Pending before strategy implementation.
- **Affected future modules:** `domain`, `nesting`, `validation`, `reporting`, future `toolpath`.
- **Required tests after the decision:** Strategy output feasibility; rejected incompatible strategy/profile combinations; cut-sequence validation if guillotine is required.

### NEST-002 — Strategy names and behavioral contracts

- **Decision ID:** `NEST-002`
- **Topic:** “Left-to-Right” and “Ignore Cutting Lines.”
- **Problem being decided:** Give each retained strategy an exact, testable contract rather than a marketing label.
- **Current confirmed legacy behavior:** Left-to-Right ranks placements by smallest X, then Y, then larger area. The visible third strategy is “Free Area Optimization”; comments say it ignores guillotine/cutting-line sequence. No current visible label exactly says “Ignore Cutting Lines.”
- **Legacy inconsistencies or risks:** Users may interpret left-to-right as strict columns, stable input order, or a guillotine pattern. “Ignore Cutting Lines” could wrongly imply that kerf or collision is ignored.
- **Available options:**
  1. Define strategies by constraints and objective, with user-facing descriptions; rename the free strategy to “Free rectangular placement (non-guillotine).” **Implication:** transparent and testable.
  2. Preserve labels and approximate code behavior. **Implication:** superficially compatible but retains ambiguity.
  3. Expose only one MVP strategy. **Implication:** fastest reliable MVP; other strategies remain compatibility backlog.
- **Recommended default for Debbie vNext:** Option 3 for the first engine, plus Option 1 before adding further strategies. Never use “Ignore Cutting Lines” to mean ignore collision or clearance.
- **Product Owner decision:** **Pending.**
- **Decision status:** Pending before strategy parity commitments.
- **Affected future modules:** `nesting`, `domain`, `ui`, `documentation`, `reporting`.
- **Required tests after the decision:** Golden ordering/placement; contract invariants; localized/user-facing descriptions; non-guillotine label checks.

### OPT-001 — Optimization objective, tie-breaks, and stock priority

- **Decision ID:** `OPT-001`
- **Topic:** Optimization policy.
- **Problem being decided:** Establish an ordered objective for demand placement, stock count/type, waste, cost, cut effort, and deterministic tie-breaking.
- **Current confirmed legacy behavior:** Strategy selection first minimizes unplaced instances, then sheet count. Stock candidates favor most pieces placed, with local waste/yield/extent tie-breakers. Cost and remnant value are absent.
- **Legacy inconsistencies or risks:** “Most pieces” can favor many small parts over scarce large parts; sheet area, cost, and stock preferences may conflict. Results are called optimized without a declared objective.
- **Available options:**
  1. Lexicographic MVP objective: maximize placed required demand, minimize sheets consumed, minimize full stock area consumed, then deterministic stable keys. **Implication:** explainable and testable without speculative cost data.
  2. Weighted score. **Implication:** flexible but weights are difficult to explain and tune.
  3. Cost-first objective. **Implication:** commercially useful but requires trusted material cost/remnant inputs.
- **Recommended default for Debbie vNext:** Option 1. Record objective values and strategy in every result. Defer costing and remnant valuation.
- **Product Owner decision:** **Pending.**
- **Decision status:** Pending before solver scoring and stock allocation.
- **Affected future modules:** `nesting`, `domain`, `metrics`, `reporting`, `ui`.
- **Required tests after the decision:** Objective priority counterexamples; stable tie cases; scarce-stock cases; explanation metadata; no false optimality claims.

### OPT-002 — Determinism, randomization, and computation budget

- **Decision ID:** `OPT-002`
- **Topic:** Solver execution policy.
- **Problem being decided:** Decide whether repeated runs must match, whether randomized search is allowed, and what runtime/cancellation contract is acceptable.
- **Current confirmed legacy behavior:** Strategies are deterministic for a given array/order and run synchronously on the browser main thread. There is no time limit, progress, or cancellation.
- **Legacy inconsistencies or risks:** Input and sort ties can depend on incidental order. Large jobs can freeze the UI.
- **Available options:**
  1. Deterministic MVP with stable tie-breaks and configurable time/cancel boundary for future strategies. **Implication:** reproducible fixtures and support.
  2. Seeded randomized search. **Implication:** potentially better layouts; seed and time budget become result metadata.
  3. Unseeded randomized search. **Implication:** simplest experimentation but poor reproducibility.
- **Recommended default for Debbie vNext:** Option 1. Define benchmark-derived responsiveness targets after representative datasets exist; design cancellation now, not randomized search.
- **Product Owner decision:** **Pending.** Runtime target requires representative job sizes.
- **Decision status:** Pending before engine execution API; randomization deferred.
- **Affected future modules:** `nesting`, `application`, `ui`, `testing`, `reporting`.
- **Required tests after the decision:** Repeat-run identity; stable ties; cancellation; time-budget behavior; benchmark thresholds on approved datasets.

### NEST-003 — Parts that do not fit and release status

- **Decision ID:** `NEST-003`
- **Topic:** Partial nesting.
- **Problem being decided:** Decide how oversized, inventory-blocked, and strategy-unplaced parts affect results, completion, and export.
- **Current confirmed legacy behavior:** Such parts enter Temp, valid layouts still render, a warning appears, and exports remain possible.
- **Legacy inconsistencies or risks:** Failure reasons are partly inferred; operators can delete Temp demand; reports may appear complete.
- **Available options:**
  1. Return a valid partial result with structured unplaced reasons and a non-releasable status until acknowledged/resolved. **Implication:** useful planning plus safe workflow.
  2. Fail the entire run if any part is unplaced. **Implication:** simple completion semantics but hides usable partial work.
  3. Preserve warning-only behavior. **Implication:** compatible but unsafe for production release.
- **Recommended default for Debbie vNext:** Option 1. Allow draft exports clearly watermarked/statused; require explicit policy for production release.
- **Product Owner decision:** **Pending.**
- **Decision status:** Pending before nesting result/status model.
- **Affected future modules:** `domain`, `nesting`, `application`, `ui`, `reporting`, `io`.
- **Required tests after the decision:** Oversized/inventory/constraint reason codes; quantity reconciliation; release guard; draft export warnings.

## Decisions required before UI/editor implementation

### EDIT-001 — Invalid placements, pushing, and strategy properties

- **Decision ID:** `EDIT-001`
- **Topic:** Manual placement safety.
- **Problem being decided:** Decide whether the editor may temporarily contain invalid placements, whether moving one part can push others, and whether manual edits must preserve strategy-specific properties.
- **Current confirmed legacy behavior:** Drag tries to push other parts and reverts when overlap resolution fails. Rotation can create overlap. Manual edits can break guillotine structure without warning.
- **Legacy inconsistencies or risks:** Different commands enforce different validity; automatic pushing can move parts the operator did not intend; reports may use invalid/non-guillotine layouts.
- **Available options:**
  1. Every committed command must be valid; drag preview may show invalidity but cannot commit it. Pushing is an explicit editor mode/command. **Implication:** safest and predictable.
  2. Always push neighbors automatically. **Implication:** fluid interaction but surprising cascades and harder undo/explanation.
  3. Allow invalid drafts. **Implication:** flexible but requires invalid-state persistence, release blocking, and extensive UI.
- **Recommended default for Debbie vNext:** Option 1. A manual edit may break a strategy preference only if it still satisfies the selected manufacturing feasibility profile; otherwise reject or clearly change layout status.
- **Product Owner decision:** **Pending.**
- **Decision status:** Pending — UI gate.
- **Affected future modules:** `ui`, `application`, `geometry`, `domain`, `undo`, `reporting`.
- **Required tests after the decision:** Command atomicity; invalid preview/commit; explicit push; guillotine-status change; undo restores all affected parts.

### EDIT-002 — Immediate metric recalculation

- **Decision ID:** `EDIT-002`
- **Topic:** Editor-derived state.
- **Problem being decided:** Decide when geometry metrics, repetition, stock totals, and warnings update after edits.
- **Current confirmed legacy behavior:** Many moves recalculate repetition and summaries immediately, but result arrays and cut calculations can remain stale depending on the path.
- **Legacy inconsistencies or risks:** Displayed layout and exports can disagree; synchronous recalculation may make large edits lag.
- **Available options:**
  1. Commit commands update authoritative layout, validate, then recompute cheap metrics synchronously and expensive metrics asynchronously with visible stale/busy state. **Implication:** consistent architecture and responsive UI.
  2. Recompute everything synchronously. **Implication:** simple but may block interaction.
  3. Recalculate only on demand. **Implication:** fast editing but stale numbers are easy to misuse.
- **Recommended default for Debbie vNext:** Option 1; MVP metrics should be cheap enough to update immediately, while future toolpaths remain background work.
- **Product Owner decision:** **Pending.**
- **Decision status:** Pending — UI/application gate.
- **Affected future modules:** `application`, `ui`, `metrics`, `reporting`, `undo`.
- **Required tests after the decision:** No stale export after commands; busy-state behavior; repeated-layout regrouping; undo/redo metric parity.

### EDIT-003 — Keyboard increments and snapping

- **Decision ID:** `EDIT-003`
- **Topic:** Precision interaction.
- **Problem being decided:** Define keyboard movement increments and snapping targets/tolerances in model units.
- **Current confirmed legacy behavior:** Arrow movement is 1 mm, Shift is 10 mm, Ctrl/Cmd is 0.10 mm. Drag transfer includes nearest-solution searches; there is no single documented snap policy.
- **Legacy inconsistencies or risks:** Modifier conventions may conflict by OS; 0.10 mm may exceed or undercut real process precision; snap behavior differs by operation.
- **Available options:**
  1. User/process-configurable base, fine, and coarse millimetre steps; optional explicit snapping to usable edges and part clearance lines. **Implication:** precise and extensible.
  2. Preserve fixed legacy increments. **Implication:** familiar and simple but not machine-specific.
  3. Pixel-based movement/snapping. **Implication:** visually intuitive but violates model/view separation.
- **Recommended default for Debbie vNext:** Option 1 with legacy 1/0.1/10 mm defaults for MVP. Snapping must never bypass validation.
- **Product Owner decision:** **Pending.**
- **Decision status:** Pending — UI gate, not domain blocker.
- **Affected future modules:** `ui`, `application`, `geometry`, settings/process profiles.
- **Required tests after the decision:** Modifier increments; zoom-independent movement; snap tolerance; boundary/clearance validation; locale-independent settings.

### LOCK-001 — Lock permissions and recalculation behavior

- **Decision ID:** `LOCK-001`
- **Topic:** Layout locks.
- **Problem being decided:** Define what a lock prevents and which non-mutating or derived operations remain allowed.
- **Current confirmed legacy behavior:** Locks preserve cloned layouts across a later Optimize when inputs are unchanged. Keyboard movement skips locked layouts, but mouse move/rotate/transfer may still edit them. Viewing and exporting remain possible.
- **Legacy inconsistencies or risks:** “Lock” conflates edit protection with optimization preservation; input changes silently clear locks on the next run.
- **Available options:**
  1. Separate `edit_locked` from `pinned_for_recalculation`; locked layouts remain viewable/selectable/copyable/exportable, but mutation requires unlock. **Implication:** explicit semantics and permissions.
  2. One lock does both. **Implication:** simpler UI but couples unrelated workflows.
  3. Preserve legacy mixed behavior. **Implication:** confusing and unsafe.
- **Recommended default for Debbie vNext:** Option 1. Recalculation must report conflicts instead of silently clearing pins.
- **Product Owner decision:** **Pending.**
- **Decision status:** Pending — domain status before editor and recalc workflows.
- **Affected future modules:** `domain`, `application`, `ui`, `nesting`, `persistence`, `reporting`.
- **Required tests after the decision:** Permission matrix for view/select/copy/export/move/rotate/recalculate; conflict handling; persistence; undo/redo.

### LOCK-002 — Repeated layout editing, divergence, and fingerprints

- **Decision ID:** `LOCK-002`
- **Topic:** Repetition identity.
- **Problem being decided:** Decide whether repetitions share one editable template, whether an instance can diverge, and what makes layouts identical.
- **Current confirmed legacy behavior:** Physical sheet results are grouped by rounded X/Y/W/H and one representative is rendered. Fingerprints omit stock and part identity. Editing/regrouping can split groups implicitly.
- **Legacy inconsistencies or risks:** Different stock or part identities can be merged; edits do not have an explicit “all versus one” target; letters are presentation identity only.
- **Available options:**
  1. A repeated layout is an immutable layout definition plus instance count; editing asks/declares “all instances” or “split N instances.” Identity includes stock specification, process rules, part instance/type identity and exact normalized placements/orientations. **Implication:** explicit and auditable.
  2. Always edit all repetitions. **Implication:** simple but cannot handle one-off divergence.
  3. Store every physical sheet separately and group only for display. **Implication:** easy divergence but larger state and more reconciliation.
- **Recommended default for Debbie vNext:** Option 1, with “edit all” as the MVP default and explicit split support deferred if not required.
- **Product Owner decision:** **Pending.**
- **Decision status:** Pending before repeated-layout domain/editor implementation.
- **Affected future modules:** `domain`, `application`, `ui`, `nesting`, `metrics`, `persistence`, `reporting`.
- **Required tests after the decision:** No cross-stock/part false grouping; stable identity; edit-all; split behavior if supported; lock and export counts.

## Decisions required before metrics and reporting implementation

### CUT-001 — Cutting length, cut count, shared edges, and toolpath distinction

- **Decision ID:** `CUT-001`
- **Topic:** Cutting calculations.
- **Problem being decided:** Define authoritative early metrics and distinguish them from executable machine toolpaths.
- **Current confirmed legacy behavior:** Guillotine packing initially records split cuts, while live code mostly sums internal right/bottom rectangle edges. Outer perimeters, shared-cut policy, trim cuts, pierces, lead-ins, sequencing, and travel are absent or inconsistent.
- **Legacy inconsistencies or risks:** Different UI/export paths return different values. “Cut length” can be mistaken for production time or NC toolpath length.
- **Available options:**
  1. MVP exposes clearly named geometry estimates: total nominal part perimeter and/or unique boundary length, plus an explicitly defined geometric segment count. Machine toolpath length/count remains unavailable. **Implication:** transparent and achievable.
  2. Preserve legacy right/bottom estimate. **Implication:** parity but no defensible manufacturing meaning.
  3. Implement process-specific toolpaths, shared cuts, trim cuts, and pierces now. **Implication:** potentially authoritative but far beyond rectangle nesting MVP.
- **Recommended default for Debbie vNext:** Option 1. Choose one primary estimate after Product Owner review; shared edges do not reduce it unless a separate approved common-line mode is active. Exclude trim cuts and pierces unless explicitly reported as separate estimates.
- **Product Owner decision:** **Pending.** Must specify the primary metric and cut-count definition.
- **Decision status:** Pending before naming/display/exporting cutting metrics; toolpath metrics deferred.
- **Affected future modules:** `metrics`, `geometry`, `reporting`, `ui`, future `toolpath`.
- **Required tests after the decision:** Single/multiple rectangle examples; shared edge; stock-edge contact; trim exclusion/inclusion; rotation invariance; report consistency.

### METRIC-001 — Used area, waste, yield, and stock consumption

- **Decision ID:** `METRIC-001`
- **Topic:** Material metrics.
- **Problem being decided:** Define denominators and distinguish usable-layout efficiency from full-material consumption.
- **Current confirmed legacy behavior:** Raw part area is divided by usable sheet area; trim is excluded from the denominator. Waste is `100% - yield`; required stock uses grouped repetition.
- **Legacy inconsistencies or risks:** This can understate purchased-material waste. Temp deletion and incorrect grouping can make counts diverge.
- **Available options:**
  1. Report both usable-area utilization and full-stock material yield; report trim loss, unoccupied usable area, stock count, and unplaced demand separately. **Implication:** transparent and commercially extensible.
  2. Keep only usable-area yield. **Implication:** simple but incomplete for costing.
  3. Keep only full-stock yield. **Implication:** purchasing-oriented but hides nesting efficiency inside the usable region.
- **Recommended default for Debbie vNext:** Option 1, without monetary costing in MVP.
- **Product Owner decision:** **Pending.**
- **Decision status:** Pending before reporting acceptance criteria.
- **Affected future modules:** `metrics`, `domain`, `reporting`, `ui`, `nesting`.
- **Required tests after the decision:** Area conservation; trim-loss examples; repeated layouts; partial demand; mixed stock sizes; identical values across UI/PDF/Excel.

## Decisions required before import, export, and compatibility implementation

### IMPORT-001 — MVP Excel schema, compatibility, and validation policy

- **Decision ID:** `IMPORT-001`
- **Topic:** Excel import.
- **Problem being decided:** Select the supported first schema, strictness, compatibility adapters, and whether errors reject or partially apply a file.
- **Current confirmed legacy behavior:** Import heuristically detects compact per-sheet sections, legacy `Data Entry`, and separate sheets with many aliases. Invalid quantities often default to 1; parsing can partially mutate state and lacks robust exception handling.
- **Legacy inconsistencies or risks:** Wrong sheets/columns may be accepted silently; the embedded template is not independently versioned; multi-work fallback rereads files.
- **Available options:**
  1. One versioned canonical MVP schema with strict validation and atomic import; separately identified legacy adapters produce warnings and a preview. **Implication:** safe and compatible without heuristic behavior in the core.
  2. Preserve broad heuristic detection. **Implication:** convenient but difficult to test and support.
  3. Support only manual entry initially. **Implication:** smallest engineering scope but likely fails a core user workflow.
- **Recommended default for Debbie vNext:** Option 1. A validation error must not replace the active project; no silent quantity defaults for malformed supplied values.
- **Product Owner decision:** **Pending.** Must list required legacy formats and mandatory columns.
- **Decision status:** Pending before importer implementation; not a geometry blocker.
- **Affected future modules:** `io`, `domain`, `application`, `ui`, `testing`.
- **Required tests after the decision:** Schema/version matrix; missing/duplicate headers; decimal locale; invalid/blank quantities; atomic failure; legacy adapter warnings; multi-work fixtures.

### EXPORT-001 — PDF and Excel MVP contracts

- **Decision ID:** `EXPORT-001`
- **Topic:** Result exports.
- **Problem being decided:** Define required workbook/report content, multi-work scope, status warnings, and coordinate/metric precision.
- **Current confirmed legacy behavior:** Excel exports only the active 2D work with summary and placements; PDF supports current work or all works. The Excel code calculates rotation but omits its column. Export rendering and cut metrics differ by path.
- **Legacy inconsistencies or risks:** Reports can imply completion despite unplaced demand; values may differ between formats; screenshots can diverge from model state.
- **Available options:**
  1. Define one report snapshot model consumed by PDF and Excel; MVP exports inputs, process settings, stock, placements including orientation/IDs, unplaced demand, status, and approved metrics. **Implication:** consistent and testable.
  2. Reproduce legacy files visually. **Implication:** faster familiarity but carries omissions and inconsistent calculations.
  3. Defer one export format. **Implication:** smaller MVP if users approve the workflow gap.
- **Recommended default for Debbie vNext:** Option 1, with model-rendered visuals and no machine-ready claim. Decide whether multi-work Excel is one workbook with per-work sheets or separate files.
- **Product Owner decision:** **Pending.**
- **Decision status:** Pending before reporting implementation.
- **Affected future modules:** `reporting`, `io`, `application`, `domain`, `ui`.
- **Required tests after the decision:** PDF/Excel snapshot equality; multi-work counts; rotation/IDs; partial-status warning; pagination; numeric precision.

### LINEAR-001 — Hidden linear-cutting migration status

- **Decision ID:** `LINEAR-001`
- **Topic:** Legacy feature scope.
- **Problem being decided:** Decide whether the hidden but implemented 1D linear-cutting mode belongs in MVP, later migration, or explicit retirement.
- **Current confirmed legacy behavior:** Linear stock/cuts, imports, two sort orders, greedy packing, and rendering exist, but the navigation tab is hidden. PDF and Excel exports explicitly support only 2D.
- **Legacy inconsistencies or risks:** Removing it silently violates the no-feature-deletion policy; migrating it now expands domain/UI/test scope without evidence of active use.
- **Available options:**
  1. Record as supported legacy backlog after stable 2D MVP. **Implication:** preserves intent without delaying geometry foundations.
  2. Include in MVP. **Implication:** requires separate 1D domain, solver, imports, UI, and reports.
  3. Retire with explicit Product Owner approval and migration note. **Implication:** smallest product scope but deliberate feature removal.
- **Recommended default for Debbie vNext:** Option 1 until actual users and files demonstrate priority.
- **Product Owner decision:** **Pending.**
- **Decision status:** Pending scope decision; safely deferred from 2D foundations if retained in backlog.
- **Affected future modules:** future `linear`, `io`, `ui`, `reporting`, product documentation.
- **Required tests after the decision:** If retained, legacy linear fixtures, kerf/count conservation, stock limits, import/export and hidden-feature migration tests.

## Decisions that may safely be deferred

### PROD-001 — Offline-first and external dependency policy

- **Decision ID:** `PROD-001`
- **Topic:** Runtime reliability.
- **Problem being decided:** Decide whether core operation requires network access and how third-party dependencies are packaged and governed.
- **Current confirmed legacy behavior:** Fonts, PDF, and spreadsheet libraries load from public CDNs; core nesting is local, but import/export may fail offline.
- **Legacy inconsistencies or risks:** Availability, supply-chain, privacy, and version drift are uncontrolled.
- **Available options:**
  1. Offline-first desktop core with pinned, reviewed, locally packaged dependencies; network features are optional adapters. **Implication:** reliable commercial baseline and larger packaged application.
  2. Permit required cloud/CDN dependencies. **Implication:** smaller distribution but unreliable/offline-incompatible.
  3. Hybrid with mandatory online activation. **Implication:** affects licensing and recovery architecture.
- **Recommended default for Debbie vNext:** Option 1.
- **Product Owner decision:** **Pending.**
- **Decision status:** Pending before packaging; architecture should assume offline-first now.
- **Affected future modules:** packaging, dependency management, `io`, updater, licensing.
- **Required tests after the decision:** Clean offline startup and core workflow; dependency inventory; missing-network behavior; reproducible builds.

### PRIV-001 — Telemetry and user-data ownership

- **Decision ID:** `PRIV-001`
- **Topic:** Privacy and diagnostics.
- **Problem being decided:** Decide telemetry default, consent, and ownership/location of job, production, and diagnostic data.
- **Current confirmed legacy behavior:** No telemetry or remote persistence exists; data remains in the browser session or user-downloaded files.
- **Legacy inconsistencies or risks:** Adding telemetry later without an explicit boundary could expose commercially sensitive production data.
- **Available options:**
  1. Telemetry off by default; local diagnostics; any future opt-in telemetry excludes job geometry/content unless separately consented. User owns project/export data. **Implication:** privacy-preserving and offline-friendly.
  2. Opt-out usage telemetry. **Implication:** better product analytics but greater compliance/trust burden.
  3. No telemetry capability. **Implication:** simplest privacy posture but limits field diagnostics.
- **Recommended default for Debbie vNext:** Option 1; do not implement remote telemetry in MVP.
- **Product Owner decision:** **Pending.**
- **Decision status:** Deferred commercial decision; privacy boundary should be documented before diagnostics design.
- **Affected future modules:** logging, support, settings, networking, legal documentation.
- **Required tests after the decision:** No network calls by default; consent persistence; payload redaction; data export/deletion if telemetry is added.

### COMM-001 — Licensing and update boundaries

- **Decision ID:** `COMM-001`
- **Topic:** Commercial platform boundaries.
- **Problem being decided:** Define how licensing and updates may interact with offline project use without implementing them prematurely.
- **Current confirmed legacy behavior:** No licensing, installer, or update mechanism exists.
- **Legacy inconsistencies or risks:** Retrofitting license checks into domain services can compromise offline reliability and testability; unsafe updates can damage projects.
- **Available options:**
  1. Keep licensing/updating behind application-shell services; core domain/geometry has no entitlement dependency. Updates are signed, explicit, and rollback-aware when implemented. **Implication:** clean commercial boundary.
  2. Embed checks throughout features. **Implication:** harder testing and fragile offline behavior.
  3. No licensing/update support. **Implication:** simplest technically but may not meet business model.
- **Recommended default for Debbie vNext:** Option 1 as an architectural rule; defer implementation until commercial-readiness phase.
- **Product Owner decision:** **Pending.**
- **Decision status:** Deferred commercial decision.
- **Affected future modules:** application shell, packaging, licensing adapter, updater; never core geometry.
- **Required tests after the decision:** Core works with licensing adapter absent; offline grace/recovery policy; signed update verification; project backup/rollback.

### INT-001 — Plugin and integration architecture

- **Decision ID:** `INT-001`
- **Topic:** CAD, ERP, and extensibility.
- **Problem being decided:** Decide whether MVP needs a public plugin system or only internal adapter boundaries.
- **Current confirmed legacy behavior:** No plugin system exists. Excel import/export is directly coupled to global UI/state.
- **Legacy inconsistencies or risks:** A premature plugin API freezes unstable domain contracts; no boundary makes later CAD/ERP work expensive.
- **Available options:**
  1. Define internal ports/adapters for imports, exports, strategies, and persistence; do not expose a public plugin API in MVP. **Implication:** clean architecture without compatibility burden.
  2. Publish a plugin SDK now. **Implication:** enables ecosystem work but freezes APIs too early and expands security/support scope.
  3. Hard-code MVP integrations. **Implication:** quickest initially but repeats coupling.
- **Recommended default for Debbie vNext:** Option 1. Reassess a signed/versioned plugin model after domain and security contracts stabilize.
- **Product Owner decision:** **Pending.**
- **Decision status:** Deferred public-plugin decision; internal separation is an engineering requirement.
- **Affected future modules:** `io`, `nesting`, `persistence`, application services, future plugin host.
- **Required tests after the decision:** Adapter contract tests; failure isolation; schema/version negotiation and security tests if public plugins are added.

## Deferred Commercial Decisions

The following are intentionally outside the first Python MVP unless the Product Owner promotes them through the change procedure:

- Common-line cutting and machine-ready toolpath generation (`KERF-002`, `CUT-001`).
- Arbitrary-angle rotation, mirroring, and polygonal CAD geometry (`ROT-002`).
- Arbitrary clamp/keep-out polygons (`TRIM-002`).
- Randomized/metaheuristic optimization and cost/remnant objectives (`OPT-001`, `OPT-002`).
- Hidden linear-cutting migration beyond recording its disposition (`LINEAR-001`).
- Public plugins, CAD/ERP connectors, licensing, telemetry, and update services (`INT-001`, `COMM-001`, `PRIV-001`).

Deferral means the architecture must avoid blocking a future addition; it does not authorize implementation or imply a promised feature.

## Decision Change Procedure

1. Product Owner records the selected option or a precise alternative in **Product Owner decision**, with name/role and date.
2. Engineering changes **Decision status** to accepted and records assumptions, affected releases, and compatibility impact.
3. Link evidence: production examples, machine/process rules, workbook samples, calculations, or user research.
4. Update `NESTING_RULES.md` from “requires decision” to an approved rule; update `CURRENT_BEHAVIOR.md` only to clarify legacy evidence, never to rewrite history.
5. Add or update acceptance fixtures and tests listed by the decision before implementing behavior.
6. If an accepted decision changes, create a superseding record or revision note. Record project/schema migration, report compatibility, and whether existing saved layouts must be revalidated.
7. Do not silently change a policy default in code. The decision ID must appear in the relevant specification/test name or traceability metadata.

## Traceability to Tests and Documentation

- Each accepted decision must map to one or more named tests using its stable ID, for example `test_KERF_001_clearance_is_not_double_applied`.
- Golden datasets must record the decision IDs and versions under which expected results were approved.
- Domain and geometry API documentation must cite the governing IDs for units, tolerance, clearance, trim, rotation, work/batch ownership, and layout identity.
- UI help and validation messages must use the same approved terminology as this register.
- PDF, Excel, and project schemas must record enough policy/version metadata to reproduce or revalidate a result.
- `MIGRATION_PLAN.md` provides the phase gate; `CURRENT_BEHAVIOR.md` remains evidence of legacy behavior; `NESTING_RULES.md` becomes the approved manufacturing rule summary as decisions are accepted.
