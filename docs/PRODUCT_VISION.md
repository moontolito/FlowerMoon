# Debbie Product Vision

## Product direction

Debbie should evolve from a useful single-file internal nesting calculator into a professional desktop application for planning rectangular sheet-metal and related cutting work. The product should help users turn trusted production data into valid, understandable, editable layouts with traceable material requirements and reports.

The current legacy tool is an alpha-stage internal application. It demonstrates valuable workflows—Excel-driven jobs, multiple stock sizes, three 2D strategies, manual layout editing, batches, temporary unplaced parts, and Excel/PDF output—but it is not yet a safe commercial architecture or a complete manufacturing specification.

## Target users

- Sheet-metal production planners and nesting operators.
- Estimators who need credible material, waste, and cutting-length figures.
- Manufacturing engineers who define kerf, trim, orientation, spacing, and stock rules.
- Workshop supervisors who need repeatable work instructions and traceability.
- Small and medium fabricators that lack an integrated CAD/CAM nesting platform.
- Internal engineering teams that exchange jobs through spreadsheets.

## Problems Debbie should solve

- Convert part demand and available stock into valid layouts quickly.
- Make unplaced parts, inventory shortages, and invalid input visible before production.
- Allow controlled manual refinement without corrupting geometry or metrics.
- Explain which material is required, why a strategy chose it, and how much waste remains.
- Preserve job state so work can be reviewed, resumed, compared, and audited.
- Produce dependable reports and integration data without manual transcription.

## Product principles

1. **Manufacturing correctness before visual polish.** Every placement and metric must have explicit rules and validation.
2. **Operator control with guardrails.** Manual edits are first-class, but invalid layouts are never silently accepted.
3. **Transparent results.** Show assumptions, strategy, unplaced demand, inventory use, warnings, and calculation definitions.
4. **Deterministic and testable.** The same input and settings should reproduce the same result unless a stochastic strategy is explicitly selected and seeded.
5. **Incremental compatibility.** Preserve confirmed legacy workflows while resolving defects through recorded decisions.
6. **Separation of model and presentation.** Millimetre geometry is authoritative; screen pixels and report scaling are views.
7. **Local-first reliability.** Core nesting and project work must not depend on an internet connection.
8. **Commercial foundations without premature features.** Design clear boundaries for licensing, updates, and integrations, but do not let them delay a correct core.

## Release definitions

### Migration MVP

The MVP is a PySide6 desktop application that can:

- Create or import one rectangular 2D job in millimetres.
- Validate stock, parts, quantities, trim, kerf, and rotation settings.
- Run at least one agreed nesting strategy through a shared geometry validator.
- Display layouts and unplaced parts.
- Report stock usage, part conservation, yield/waste, and an agreed cutting metric.
- Save and reopen a versioned project.
- Export the agreed minimum Excel/PDF output.
- Pass golden parity/correction tests for an approved core dataset.

It need not reproduce every manual editor interaction or every legacy workbook variation.

### Internal stable release

An internal stable release supports the agreed legacy production workflows, multiple works and stock sizes, robust manual editing with undo/redo, all retained strategies, validated Excel formats, reliable project recovery, and repeatable packaging. It has production-owner acceptance datasets, documented limitations, error telemetry/logging suitable for support, and performance targets based on real jobs.

### Commercial release

A commercial release additionally requires a polished installer and update path, signed builds, supported operating-system policy, user documentation, onboarding, accessibility review, security and dependency review, privacy policy where applicable, licensing/entitlement design, diagnostic/support tooling, compatibility guarantees, migration/back-up policy, release notes, and a defined support lifecycle. Results marketed as manufacturing or cost data require validated definitions and appropriate disclaimers/certification decisions.

## Differentiation opportunities

- A clean operator experience that exposes constraints instead of hiding them.
- Fast comparison of several strategies and objectives, with explainable trade-offs.
- Strong spreadsheet interoperability for businesses not ready for full ERP/CAD integration.
- Reliable manual layout editing backed by the same collision engine as automatic nesting.
- Reproducible jobs, golden comparisons, and traceable revisions.
- Configurable manufacturing rules by machine, material, customer, or facility.
- Useful waste/remnant and cost insight for smaller fabricators.

## Capabilities the architecture should allow later

These are architectural extension points, not current implementation commitments:

- CAD import/export and geometry beyond rectangles.
- ERP/MRP, inventory, purchasing, and production-order integration.
- Versioned project files, templates, job history, and collaboration metadata.
- Material cost, waste value, remnant reuse, quoting, and scenario comparison.
- Configurable reports, labels, barcodes, and machine/operator work packs.
- Licensing, account/entitlement handling, signed updates, and release channels.
- Multiple nesting strategies and objectives, including time-bounded or pluggable solvers.
- Production traceability from source part through layout, sheet, batch, machine, and completion.
- Configurable grain, rotation, edge clearance, common-line, clamp, lead-in, and machine rules.
- Background computation, cancellation, progress, benchmark profiles, and optional compute services.

These capabilities must not be implemented until their phase, requirements, and acceptance criteria are approved.

