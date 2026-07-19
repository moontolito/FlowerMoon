# Debbie Nesting Workbook Schema 1.1

## Status and compatibility

This is the implemented canonical contract for material-classified Debbie
Works. The public `import_canonical_workbook` entry point reads the declared
schema version before choosing exactly one parser:

- `1.0` uses `canonical_excel_v1` and creates unclassified Works;
- `1.1` uses `canonical_excel_v1_1` and creates classified Works;
- missing, duplicate, malformed, or unsupported versions fail atomically.

There is no fallback, aliasing, upgrade, downgrade, locale guessing, or
material defaulting between versions. Workbook paths, row/worksheet order,
timestamps, Python hash seeds, and display labels do not determine identity.

## Workbook identity

Required worksheets are `Debbie`, `Works`, `Parts`, and `Stocks`. Metadata is a
two-column table with normalized case-insensitive `Key` and `Value` headers.
Required rows are:

| Key | Value |
|---|---|
| `Format Name` | `Debbie Nesting Workbook` |
| `Schema Version` | `1.1` |
| `Units` | `mm` |
| `Density Units` | `g/cm3` |

Surrounding whitespace is trimmed. Required keys are unique. Unknown metadata
is retained as provenance and reported at INFO severity.

## Works

Required headers are:

```text
Work Key
Work Name
Material Category Key
Material Category Name
Material Grade Key
Material Grade Name
Thickness (mm)
Density (g/cm3)
Density Source
Batch Multiplier
Kerf (mm)
Part Clearance (mm)
Boundary Clearance (mm)
Trim Left (mm)
Trim Right (mm)
Trim Top (mm)
Trim Bottom (mm)
```

`Material Description` is optional. Category and grade keys/names are trimmed,
non-empty, and bounded by the domain contract. Keys are case-sensitive;
display names and description do not affect identity. Thickness and density
are explicit, finite, strictly positive, and unrounded. Density is in `g/cm3`.
`Density Source` trims and compares case-insensitively, then stores exactly
`library_default` or `explicit_override`. No material-library lookup occurs.

Every Work has one material, grade, density snapshot, thickness, and process
profile. Part- or stock-level material/thickness overrides do not exist.

## Parts

Required headers are `Work Key`, `Part Key`, `Part Name`, `Length (mm)`, `Width
(mm)`, `Quantity`, and `Allow Rotation`. `Drawing Number` is optional
provenance. Geometry is positive finite nominal millimetres. Quantity is a
bounded positive integer. Rotation accepts only case-insensitive, trimmed
`Yes` or `No`. Parts inherit Work classification.

## Stocks

Required headers are:

```text
Work Key
Stock Key
Stock Name
Full Length (mm)
Full Width (mm)
Allocated Length (mm)
Allocated Width (mm)
Commercial Allocation Fraction
Quantity
```

All dimensions are explicit positive finite millimetres. Allocated dimensions
must not exceed full dimensions and are never clamped. Full sheets repeat their
full dimensions in the allocated columns; blanks never mean full allocation.
The physical fraction is derived without rounding:

```text
(Allocated Length / Full Length) × (Allocated Width / Full Width)
```

It is not an input column. Commercial allocation is explicit, positive,
finite, unrounded, and satisfies `physical fraction <= commercial fraction <=
1`. Quantity is a bounded positive integer and expands into deterministic
physical stock instances.

Partial allocations combined with any non-zero Work trim or boundary clearance
fail with `PARTIAL_ALLOCATION_PROCESS_POLICY_UNRESOLVED`. Values are never
silently zeroed. This isolates the unresolved manufacturing boundary rather
than deciding where trim applies. Partial allocations with zero values and full
allocations using the existing process behavior are supported.

## Parsing, identity, and atomicity

Headers trim surrounding whitespace, collapse repeated whitespace, and compare
case-insensitively. Duplicate normalized headers and missing required headers
fail. Unknown non-conflicting columns are INFO diagnostics; aliases and fuzzy
matching are forbidden.

Numbers accept native Excel numeric cells and strict ASCII dot-decimal text.
Booleans, comma decimals, separators, units, currency, blanks, NaN, and
infinity fail. Formulas are never evaluated; only a valid available cached
value can proceed through normal validation.
The importer cannot prove that a workbook's cached formula values are fresh;
workbook producers are responsible for recalculating and saving before import.

Work IDs use the canonical format identity, exact schema version `1.1`, and
trimmed case-sensitive Work Key. Child IDs derive from Work ID and stable part
or stock keys. Schema 1.0 and 1.1 Works intentionally do not share Work IDs.

Import is atomic. All reasonably discoverable errors are accumulated; any
ERROR returns no Works, neutral records, summary, material summary, or Drawing
Number summary. A successful result exposes version-specific neutral records,
classified Works, material provenance, drawings, and allocation summaries.

## Safety boundary and exclusions

Schema 1.1 uses the same bounded `.xlsx` ZIP/XML preflight, formula policy,
macro/encryption rejection, worksheet/table limits, expansion limits, offline
reader, and workbook-handle cleanup as schema 1.0.

This schema implements import only. It adds no material library, remnant
inventory, allocation offset/polygon, export/template generator, persistence,
pricing, costing, Desktop material/mass UI, legacy adapter, CAD, ERP, or cloud
behavior. Rectangular part mass remains an estimate, not CAD/net mass.
