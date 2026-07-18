# Debbie Incremental Migration Plan

## Guardrails

The migration is an evidence-led replacement, not a one-step rewrite. `Nesting_Tool_alpha_v63.html` and tag `debbie-html-stable` remain the comparison baseline. Every phase should produce a reviewable result, tests, documented assumptions, and an explicit decision about parity versus corrected behavior.

## Phase 1 — Legacy audit

- **Objective:** Establish a complete technical map of the single-file application.
- **Deliverables:** Repository inventory; function/state/dependency map; risk register; `CURRENT_BEHAVIOR.md`; `NESTING_RULES.md`.
- **Acceptance criteria:** All UI, import, state, packing, editing, metrics, and export paths are traced; unknowns are classified rather than guessed.
- **Dependencies:** Protected legacy file and a browser capable of running it.
- **Main risks:** UI labels are mistaken for behavior; late function overrides hide earlier implementations; browser-only paths are not exercised.
- **Do not implement yet:** Python packages, algorithm changes, UI prototypes, or legacy fixes.

## Phase 2 — Behavior documentation

- **Objective:** Convert audit evidence into an approved compatibility contract.
- **Deliverables:** Behavior scenarios, state transitions, input/output examples, defect-versus-feature decisions, decision log.
- **Acceptance criteria:** Product owner approves the behavior categories and resolves safety/materially significant questions.
- **Dependencies:** Phase 1.
- **Main risks:** Accidental preservation of defects; desired behavior described as current fact; missing real production cases.
- **Do not implement yet:** Geometry or nesting code beyond throwaway test harnesses approved for measurement.

## Phase 3 — Test fixtures and golden datasets

- **Objective:** Make legacy comparison reproducible.
- **Deliverables:** Sanitized workbook fixtures; expected placements/stock/unplaced/metrics; malformed-input corpus; dataset provenance and tolerances.
- **Acceptance criteria:** Fixtures cover strategies, rotation, trim, kerf, batches, stock limits, multi-work, manual edits, and exports; each expected value is marked parity, correction, or new requirement.
- **Dependencies:** Phases 1–2 and representative user data.
- **Main risks:** Golden files encode unstable ordering or known defects; sensitive production data leaks; too few edge cases.
- **Do not implement yet:** Product UI or broad engine optimization.

## Decision gate before Python implementation

**Gate status on 2026-07-18:** the first domain and geometry decision content gate is passed for `GEO-001`, `GEO-002`, `GEO-003`, `GEO-004`, `KERF-001`, `TRIM-001`, `ROT-001`, `BATCH-001`, and `WORK-001`, approved by Product Owner Cuvuliuc Nicolae. These decisions establish canonical units and coordinates, the centralized geometry epsilon, clearance and boundary semantics, kerf separation, four-sided trim, orientation sets, and independent work/batch/stock ownership.

Production Python domain-model work was authorized after that documentation update was reviewed and committed. The complete decision register is not resolved. Pending decisions in `PRODUCT_DECISIONS.md` continue to block their relevant phases, including Temp and production-release semantics, locks and repeated-layout editing, metrics and cutting calculations, import/export contracts, persistence, and later commercial capabilities. Engineering may prepare fixtures and documentation while those decisions are pending, but must not encode recommendations as requirements or implement a later phase behind unresolved manufacturing assumptions.

## Phase 4 — Python package structure

- **Objective:** Establish enforceable boundaries and development tooling.
- **Deliverables:** Package skeleton for `domain`, `geometry`, `nesting`, `application`, `io`, `persistence`, `reporting`, and `ui`; test layout; lint/type/test configuration; architecture notes.
- **Acceptance criteria:** Imports respect layer direction; headless tests run without PySide6 UI construction; CI/local commands are documented.
- **Dependencies:** Approved architecture and supported Python/OS policy.
- **Main risks:** Premature frameworks; circular dependencies; UI types leaking into core modules.
- **Do not implement yet:** Full feature behavior, polished screens, installer, licensing.

## Phase 5 — Domain models

- **Objective:** Define one authoritative representation of jobs and manufacturing inputs.
- **Deliverables:** Typed models for dimensions, parts, demand, stock/inventory, trim, kerf/spacing policy, batch/work, placements, layouts, unplaced reasons, and diagnostics.
- **Acceptance criteria:** Invariants and quantity conservation are unit-tested; model values use millimetres; serialization-facing DTOs are separated where needed.
- **Dependencies:** Phases 2–4 and unit/identity decisions.
- **Main risks:** Reusing ambiguous legacy `w/h` meanings; losing source identity; allowing invalid partial state.
- **Do not implement yet:** Packing heuristics, QWidget models, or permanent project format.

## Phase 6 — Geometry and collision engine

- **Objective:** Provide one tested source of truth for rectangular placement validity.
- **Deliverables:** Rectangles/transforms, tolerances, usable-stock calculation, rotation, boundary/spacing/edge-touch predicates, collision index abstraction, layout validator.
- **Acceptance criteria:** Property and fixture tests cover symmetry, touching, tolerance, trim, kerf, rotation, transfers, and invalid imported placements; no pixel coordinates enter the engine.
- **Dependencies:** Phase 5 and approved nesting rules.
- **Main risks:** Floating-point boundary errors; confusing kerf with clearance; performance degradation at high part counts.
- **Do not implement yet:** Strategy-specific placement policy or canvas behavior.

## Phase 7 — Nesting engine

**First-solver decision gate on 2026-07-18:** `NEST-001`, `NEST-002`, `OPT-001`, `OPT-002`, and `NEST-003` are accepted by Product Owner Cuvuliuc Nicolae. Implementation may begin only after this documentation change is reviewed and committed. Approval is limited to `Deterministic Left-to-Right Rectangular Placement` with feasibility class `Free rectangular placement — non-guillotine`, the accepted lexicographic objective, deterministic metadata, finite work-owned stock, and structured unplaced results/statuses. No other strategy is approved; later strategies require separate decisions, contracts, tests, and metadata.

- **Objective:** Implement the one approved strategy behind a stable deterministic contract.
- **Deliverables:** One deterministic non-guillotine rectangular strategy; stable strategy boundary; finite work-isolated stock allocation; structured unplaced demand; result status; engine/strategy/policy/objective metadata; future cancellation boundary; unit and golden tests.
- **Acceptance criteria:** Every placement passes the shared validator; demand and inventory reconcile; objective priority and candidate ordering match the accepted contracts; repeated approved inputs reproduce the same result; feasibility and partial status are explicit; golden expectations pass within approved tolerances.
- **Dependencies:** Phases 3, 5, and 6.
- **Main risks:** Calling a heuristic “optimal”; strategy and stock selection objectives conflict; free-rectangle worst cases grow excessively.
- **Do not implement yet:** Additional strategies; guillotine/cutting-line planning; toolpaths or cutting-length optimization; random/metaheuristic search; cost/remnant objectives; UI/background execution; editor/Temp/locks/repetition; reports; import/export; persistence; advanced CAD geometry; or unapproved manufacturing constraints.

The phase is not complete. Editor behavior, metrics/reporting, import/export, persistence, and commercial capabilities remain gated by their own pending decisions and later phases.

**Implementation checkpoint:** the first pure-Python implementation now provides the approved strategy and metadata, deterministic part/stock normalization, geometry-edge candidates accepted only through the shared validator, finite stock allocation, structured validation/partial results, exact reconciliation checks, an active synchronous cancellation callback boundary, and focused/golden automated tests. A bounded performance review replaced full-layout validation of every rejected candidate with contract-equivalent lazy candidate iteration and incremental shared-predicate checks, retained complete validation for selected commits/final layouts, and added per-run equivalent-stock simulation caching plus a reproducible development benchmark. The simple 100-piece engineering fixture now completes on the current development machine, but this is not a product guarantee. This checkpoint remains uncommitted and subject to Product Owner review. Phase 7 remains in progress pending approved representative production golden datasets, benchmark-derived acceptance targets, and review of dense mixed-dimension scaling; no additional strategy or later-phase capability is implied.

## Phase 8 — Excel import/export

**Canonical import gate on 2026-07-18:** `IMPORT-001` is accepted by Product Owner Cuvuliuc Nicolae for the strict `.xlsx` `Debbie Nesting Workbook` schema 1.0 specified in `EXCEL_SCHEMA_V1.md`. Canonical importer implementation may begin only after this documentation update is reviewed and committed. Approval does not select any legacy compatibility adapter and does not accept `LINEAR-001`, `EXPORT-001`, or `PERSIST-001`.

- **Objective:** Convert one canonical, versioned, multi-work workbook into fully validated Debbie domain objects through a deterministic, atomic, structured-diagnostic boundary.
- **Canonical importer deliverables:** `.xlsx` workbook reader adapter; `Debbie` metadata/version recognition; strict required-sheet/header parser; neutral import records with source provenance; locale-independent value parsing; key/reference/uniqueness validation; deterministic namespace-based IDs; effective-region/domain validation; atomic import result; structured diagnostics; fixture matrix and acceptance tests. A blank canonical template is a separate reviewed deliverable if included.
- **Canonical importer acceptance criteria:** all `IMPORT-001` traceability tests pass; reordered equivalent rows produce equivalent domain results; multiple works remain isolated; invalid/fractional/default-prone values fail explicitly; all reasonably discoverable errors are reported; any error returns no usable works and mutates no active state; no canonical alias guessing occurs; imported works run through existing domain/geometry/solver contracts without semantic conversion.
- **Legacy adapter gate:** `LEGACY_IMPORT_INVENTORY.md` records evidence and proposed priority only. Product Owner must select exact retained formats and provide/approve fixtures before any compatibility adapter is implemented.
- **Separate later phases:** Excel result export remains governed by pending `EXPORT-001`; project persistence remains governed by pending `PERSIST-001`; PySide6 import preview belongs to the UI phase; linear import remains governed by pending `LINEAR-001`.
- **Dependencies:** Phases 3 and 5–7; accepted `IMPORT-001`; selection of a safe `.xlsx` library during implementation review.
- **Main risks:** untrusted/oversized workbook content; formula/external-link behavior; hidden locale conversion; accidental alias heuristics; partial state mutation; deterministic identity drift; lack of representative legacy fixtures.
- **Do not implement in the canonical first phase:** `.xls`, CSV, macros, formula evaluation, broad legacy recognition, linear cutting, Excel result export, project persistence, UI, ERP/CAD/cloud integration, or automatic repair.

**Implementation progress:** the first canonical `.xlsx` schema 1.0 importer is implemented behind the offline `canonical_excel_v1` adapter. It uses strict row-1 headers and locale-independent values, immutable neutral records, structured diagnostics, UUID5 identities, bounded workbook loading, complete cross-reference/effective-region validation, and atomic `Work` construction. Programmatically generated tests cover success, malformed data, deterministic row reordering, resource release, security boundaries, and solver handoff.

Phase 8 remains in progress pending review of this implementation, representative production-scale fixtures, and any separately approved template/preview work. No legacy adapter, Excel export, persistence, or UI work is complete.

## Phase 9 — Minimal desktop UI

- **Objective:** Deliver a thin PySide6 workflow over tested application services.
- **Deliverables:** Job inputs, validation messages, strategy execution with progress/cancel, results list, unplaced list, and logs suitable for support.
- **Acceptance criteria:** UI remains responsive; widget state is not authoritative domain state; keyboard navigation and basic accessibility are reviewed; core MVP scenarios run end-to-end.
- **Dependencies:** Phases 4–8.
- **Main risks:** Recreating global state in widgets; background-thread misuse; premature styling consumes migration effort.
- **Do not implement yet:** Full graphical editor, commercial branding, licensing, or updater.

## Phase 10 — Graphical layout editor

- **Objective:** Add safe selection, movement, transfer, rotation, Temp/unplaced handling, locking, and undo/redo.
- **Deliverables:** Model/view transforms, interaction commands, shared validity feedback, transaction-based history, multi-selection, zoom/pan, and accessible alternatives to drag.
- **Acceptance criteria:** Every command is atomic, undoable, and validated by the shared geometry engine; locked behavior matches the approved contract; screen scale never changes model coordinates.
- **Dependencies:** Phases 6–9 and resolved editing semantics.
- **Main risks:** Display/model divergence; expensive collision checks during drag; ambiguous repeated-layout editing; lost history across job switches.
- **Do not implement yet:** Free-form CAD editing, machine toolpaths, or collaborative editing.

## Phase 11 — Project persistence

- **Objective:** Save, recover, and migrate complete Debbie work safely.
- **Deliverables:** Versioned project schema, atomic save, open/recent workflow, dirty-state handling, backups/recovery, migrations, and compatibility tests.
- **Acceptance criteria:** Round trips preserve identity, inputs, settings, placements, locks, unplaced parts, and approved history scope; corrupt/incompatible files fail safely.
- **Dependencies:** Stable domain and command models from Phases 5 and 10.
- **Main risks:** Schema freeze too early; unsafe overwrite; partial data loss; embedding transient UI state.
- **Do not implement yet:** Cloud sync, multi-user collaboration, or ERP ownership of projects.

## Phase 12 — PDF/report exports

- **Objective:** Produce reproducible, professional reports from authoritative snapshots.
- **Deliverables:** Report model, PDF output, Excel/report consistency tests, multi-work options, pagination/font policy, and metadata.
- **Acceptance criteria:** Counts, dimensions, repetition, stock, unplaced demand, and agreed cut metrics match the project snapshot and golden reports.
- **Dependencies:** Phases 5–11 and approved report definitions.
- **Main risks:** Canvas screenshots differ from model; pagination clips data; reports imply machine readiness without valid toolpaths.
- **Do not implement yet:** Regulatory certification, arbitrary report designer, or machine-code generation.

## Phase 13 — Comparative testing

- **Objective:** Decide and demonstrate where Python matches, intentionally corrects, or intentionally departs from legacy behavior.
- **Deliverables:** Automated comparison runner, parity matrix, discrepancy reports, product-owner sign-offs, performance comparison.
- **Acceptance criteria:** Every supported behavior has evidence; every discrepancy is explained; no unresolved high-impact manufacturing difference remains.
- **Dependencies:** Phases 2–12.
- **Main risks:** Comparing rounded screenshots instead of models; nondeterminism; approving regressions because legacy is ambiguous.
- **Do not implement yet:** New commercial features that obscure parity assessment.

## Phase 14 — Packaging and installer

- **Objective:** Produce repeatable, supportable desktop builds.
- **Deliverables:** Locked dependencies, build pipeline, signed installer plan/build, clean-machine tests, data/log locations, uninstall/upgrade behavior, SBOM/license inventory.
- **Acceptance criteria:** Offline core works; installation and upgrade preserve projects; supported OS targets pass smoke tests; builds are reproducible enough for release control.
- **Dependencies:** Stable internal release candidate and deployment policy.
- **Main risks:** Native dependency size; antivirus false positives; unsigned builds; update-related data loss.
- **Do not implement yet:** Public auto-update or licensing unless separately approved and threat-modeled.

## Phase 15 — Commercial readiness

- **Objective:** Add the operational capabilities needed to sell and support Debbie responsibly.
- **Deliverables:** Product security review, licensing/entitlement if required, signed update channels, privacy/support policies, onboarding/help, telemetry decision, accessibility and localization plans, release/support lifecycle.
- **Acceptance criteria:** Legal, security, support, quality, and product owners approve release; recovery and rollback are tested; commercial claims match validated capability.
- **Dependencies:** Internal stable release and business decisions.
- **Main risks:** Licensing harms offline reliability; telemetry/privacy obligations; support burden; unsupported manufacturing claims.
- **Do not implement yet:** CAD/ERP, advanced optimization, costing, traceability, or other roadmap features without their own discovery and acceptance plans.
