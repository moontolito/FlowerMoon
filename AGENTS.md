# Debbie Engineering Guide

## Project identity

Debbie is a sheet-metal nesting application being migrated from a single-file HTML/JavaScript internal tool into a maintainable Python/PySide6 desktop product. The long-term objective is a reliable, testable, high-performance application that preserves validated production behavior while supporting future commercial use.

## Protected legacy baseline

- `Nesting_Tool_alpha_v63.html` is the stable legacy implementation.
- Git tag `debbie-html-stable` is the protected pre-migration baseline.
- Do not modify, rename, move, reformat, regenerate, or delete the legacy HTML unless the product owner explicitly approves that exact change.
- Treat the legacy implementation as behavioral evidence, not as an automatically correct specification. Record contradictions and defects rather than silently reproducing or correcting them.

## Branch and Git workflow

- Migration work belongs on `python-migration` or a short-lived branch created from it.
- Keep `main` stable. Do not merge migration work to `main` without review and acceptance evidence.
- Before work, run `git status` and confirm the intended branch and the state of the working tree.
- Make small, reviewable changes with one clear purpose. Do not mix refactoring, behavior changes, UI redesign, and dependency changes in one change set.
- Do not create commits, tags, pushes, merges, rebases, or releases unless the user explicitly requests them.
- Before any requested commit, run the relevant tests and `git diff --check`, inspect the diff, and report what was and was not verified.

## Incremental migration policy

- Do not perform a full rewrite in one step.
- Migrate one bounded capability at a time behind explicit interfaces and tests.
- Establish behavior fixtures and golden datasets before replacing an algorithm or workflow.
- Keep a runnable comparison path to the protected legacy baseline until parity decisions are complete.
- Do not delete, hide, or weaken an existing feature without explicit product-owner approval, even if the feature appears incomplete.
- Do not describe inferred behavior as confirmed. Document assumptions, evidence, open questions, and deliberate deviations.

## Architecture principles

- Support Python `>=3.13,<3.15`. Use the latest stable Python 3.13.x for primary development and validation, treat Python 3.14 as a secondary compatibility target, and do not use Python 3.14-only features while 3.13 is the minimum.

- Separate packages for UI, application/use-case services, domain models, geometry, nesting strategies, imports/exports, and persistence.
- Keep domain and geometry code independent of PySide6, file dialogs, widgets, and rendering.
- Use explicit immutable value objects where practical. Avoid hidden global state, shared mutable singletons, and state derived independently in several layers.
- Keep model coordinates and dimensions in millimetres. Keep rendering coordinates (pixels, device scale, viewport transforms) separate and convert only at a rendering boundary.
- Use the approved top-left usable-stock origin with X right and Y down. Use one centralized absolute geometry epsilon of `0.001 mm`; display/export rounding must never affect geometry identity or predicates.
- Define one kerf model, four-sided trim model, collision predicate, and layout-validity service. Nominal part geometry, `minimum_part_clearance`, `boundary_clearance`, trim, and physical kerf are separate concepts and separately stored values.
- Make strategy selection explicit through a stable interface. A strategy may propose a layout; shared validation must decide whether it is valid.
- Imports must produce validated domain objects plus structured diagnostics. Exports must consume domain/application snapshots, not scrape widget state.
- Persistence must be versioned, transactional where practical, and able to reject or migrate incompatible project formats safely.
- Long-running nesting, import, and report work must not block the UI thread; cancellation and progress reporting should be designed at service boundaries.

## Engineering and manufacturing correctness

- Use millimetres as the canonical 2D model unit. If other display/import units are added, convert explicitly at system boundaries.
- Never use one field meaning for nominal part dimensions, transient clearance envelopes, usable stock dimensions, full stock dimensions, trim offsets, or pixel dimensions.
- Preserve nominal part length and width unchanged. Do not encode clearance or kerf by permanently inflating nominal geometry.
- Model trim as independent non-negative left, right, top, and bottom values; every layout retains the effective trim snapshot used to create it.
- Give every part type an explicit allowed-orientation set. The MVP supports `{0°, 90°}` or `{0°}` only and forbids mirroring.
- Preserve part identity, source drawing identity, quantity, orientation, grain/directional constraints when introduced, and batch/work identity through import, nesting, editing, persistence, and export.
- Each work owns its batch multiplier, stock pool, demand, layouts, unplaced parts, and results. Do not share stock or merge layouts across works in the MVP.
- Centralize boundary, spacing, edge-touch, orientation, and collision rules. Validate every automatically generated, manually moved, transferred, rotated, restored, imported, persisted, and exported placement with the same validator contract.
- Cutting length and cut count must have a documented manufacturing definition and one authoritative implementation. Do not present heuristic rectangle-edge totals as machine-ready cutting data without validation.
- Never claim optimality unless the objective, constraints, algorithm, termination condition, and evidence support that claim.
- Use deterministic seeds/orderings where possible so failures and golden results are reproducible.

## Testing expectations

- Add unit tests for domain invariants, units, geometry predicates, tolerances, rotation, trim, kerf, collisions, and cut calculations.
- Add strategy contract tests: no overlap, all parts inside usable stock, inventory limits respected, quantities conserved, and unplaced parts reported.
- Add importer/exporter fixtures for every supported workbook shape, malformed data, locale decimals, missing sheets/headers, and round-trip expectations.
- Add golden datasets captured from representative legacy jobs and record whether each expectation represents parity, a corrected defect, or a product-owner decision.
- Add integration tests for nesting, manual edits, undo/redo, locks, multi-layout jobs, project save/load, and reports.
- Run relevant focused tests during development and the broader suite before commits. Report skipped, unavailable, flaky, or failing checks honestly.
- Include performance benchmarks for large part counts and worst-case free-rectangle/collision scenarios before claiming performance improvements.

## Working rules for future sessions

- Read `docs/CURRENT_BEHAVIOR.md`, `docs/NESTING_RULES.md`, and `docs/MIGRATION_PLAN.md` before changing migration behavior.
- Confirm ambiguous manufacturing behavior with the product owner when it affects material usage, safety, machine instructions, costing, or compatibility.
- State assumptions in code comments, tests, decision records, or documentation close to the affected behavior.
- Report incomplete, ambiguous, inferred, broken, or untested behavior honestly. Never turn uncertainty into an undocumented default.
- Preserve traceability from requirement or legacy evidence to implementation and test.
