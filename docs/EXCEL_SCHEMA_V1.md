# Debbie Nesting Workbook Schema 1.0

## Purpose and status

This document is the normative canonical Excel import contract approved by **Product Owner: Cuvuliuc Nicolae** on **2026-07-18** under `IMPORT-001`. It specifies data that a future importer may convert into Debbie vNext `Work` objects. It does not describe an implemented importer or Excel export format.

The canonical flow is:

```text
Excel workbook
→ canonical schema recognition
→ complete validation
→ structured import preview/result
→ atomic conversion to Debbie domain models
→ nesting solver
```

Legacy workbooks are evidence and may later be handled by separately named compatibility adapters. They do not define this schema.

## Format identity and version

| Property | Required value |
|---|---|
| Format name | `Debbie Nesting Workbook` |
| Schema version | `1.0` |
| Unit system | `mm` |
| File type for the first implementation | `.xlsx` |

The workbook must contain one worksheet named exactly `Debbie` after trimming surrounding whitespace. Canonical recognition must not guess from data headers or worksheet position.

The `Debbie` worksheet is a key/value table:

| Cell/column | Contract |
|---|---|
| `A1` | `Key` |
| `B1` | `Value` |
| Required key | `Format Name` = `Debbie Nesting Workbook` |
| Required key | `Schema Version` = `1.0` |
| Required key | `Units` = `mm` |
| Optional key | `Application Version` = generating or last-editing application version |
| Optional key | `Description` = workbook description |

Metadata keys are unique. Missing, duplicated, or conflicting required metadata means the workbook is not a valid canonical workbook. Application version and description are provenance only and do not alter geometry.

## Workbook structure

Schema 1.0 requires exactly one of each worksheet below:

```text
Debbie
Works
Parts
Stocks
```

- Worksheet identity does not depend on position.
- Names are compared case-sensitively after trimming surrounding whitespace.
- A duplicate after trimming is an error.
- Unknown worksheets may be ignored with an `INFO` diagnostic when they do not conflict with required names.
- In `Works`, `Parts`, and `Stocks`, row 1 is the canonical header row and data begins at row 2.
- Completely blank data rows may be ignored. A partially populated row must be validated and must not disappear silently.
- Merged cells are forbidden in canonical data tables.

## Header matching

Canonical header labels are contract identifiers, not semantic hints.

An importer may normalize a header only by:

1. trimming leading and trailing whitespace;
2. collapsing consecutive internal whitespace to one ASCII space;
3. comparing case-insensitively.

Broad aliases, fuzzy matches, section searches, and worksheet-position inference are forbidden in canonical mode. Duplicate normalized headers and missing required headers fail the import. Unexpected additional columns are permitted and must be preserved in neutral records or reported as ignored; they must never override canonical columns.

## `Works` worksheet

### Required headers

| Header | Type and rule | Example |
|---|---|---|
| `Work Key` | Required unique non-empty text | `JOB-1001` |
| `Work Name` | Required non-empty display text | `North enclosure` |
| `Batch Multiplier` | Required positive integer | `2` |
| `Kerf (mm)` | Required finite non-negative number | `0.20` |
| `Part Clearance (mm)` | Required finite non-negative number | `0.50` |
| `Boundary Clearance (mm)` | Required finite non-negative number | `0` |
| `Trim Left (mm)` | Required finite non-negative number | `5` |
| `Trim Right (mm)` | Required finite non-negative number | `5` |
| `Trim Top (mm)` | Required finite non-negative number | `10` |
| `Trim Bottom (mm)` | Required finite non-negative number | `8` |

### Field rules

- `Work Key` is trimmed, case-sensitive, unique in the workbook, user-visible, and never generated from a row number. It is preserved as provenance and participates in deterministic `WorkId` generation.
- `Work Name` is a label only. Equal names do not merge works.
- `Batch Multiplier` is not rounded or defaulted. Blank, fractional, zero, and negative values are errors.
- Kerf is physical cutting width and remains separate from nominal part geometry and both clearance values.
- Part clearance does not default from kerf. Zero permits finished-edge contact.
- Boundary clearance remains separate from trim and kerf. Zero permits contact with the usable boundary.
- Trim is four independent required values; it is never assumed symmetric.
- Every work is independent. Schema 1.0 has no shared project stock.

The combination of a work's trim/boundary clearance and every referenced stock must leave a positive effective placement region.

Invalid examples include batch `1.5`, missing kerf, negative clearance, `NaN`, and trim that consumes a stock dimension.

## `Parts` worksheet

### Required and optional headers

| Header | Requirement | Type and rule | Example |
|---|---|---|---|
| `Work Key` | Required | Existing work reference | `JOB-1001` |
| `Part Key` | Required | Non-empty; unique within work | `BRACKET-A` |
| `Part Name` | Required | Non-empty display text | `Mounting bracket` |
| `Length (mm)` | Required | Finite positive nominal dimension | `250.5` |
| `Width (mm)` | Required | Finite positive nominal dimension | `120` |
| `Quantity` | Required | Positive integer | `8` |
| `Allow Rotation` | Required | `Yes` or `No` | `Yes` |
| `Drawing Number` | Optional | Text; may be blank | `DWG-42` |

### Field rules

- Unknown `Work Key` values fail the complete import.
- `Part Key` may repeat only in another work. It is not a row number and participates in deterministic part-type and demand identity.
- `Part Name` is not identity.
- Length and width are unrounded nominal finished-part dimensions. Kerf, clearance, trim, and compensation are never baked into them.
- Quantity is not rounded or defaulted. Physical demand is exactly `Quantity × Work Batch Multiplier`.
- `Allow Rotation` comparison may trim whitespace and ignore case:
  - `Yes` maps to `{0°, 90°}`;
  - `No` maps to `{0°}`.
- All other rotation values are errors. Arbitrary angles, mirroring, grain direction, and visible-face constraints are unsupported in 1.0.
- `Drawing Number` never replaces `Part Key`. The current domain model has no drawing-number field, so a future importer must retain it in neutral import/provenance records until domain exposure is separately approved.

Invalid examples include empty part keys, duplicate part keys within one work, zero dimensions, quantity `3.2`, and rotation values such as `Y`, `1`, or `Rotate`.

## `Stocks` worksheet

### Required headers

| Header | Type and rule | Example |
|---|---|---|
| `Work Key` | Existing work reference | `JOB-1001` |
| `Stock Key` | Non-empty; unique within work | `SHEET-2500X1250` |
| `Stock Name` | Required non-empty display text | `Standard sheet` |
| `Length (mm)` | Finite positive full-stock dimension | `2500` |
| `Width (mm)` | Finite positive full-stock dimension | `1250` |
| `Quantity` | Positive integer physical count | `6` |

### Field rules

- A stock belongs to exactly one existing work.
- `Stock Key` may repeat only in another work. It identifies a stock specification and is independent of row position.
- `Stock Name` is not identity.
- Dimensions are full nominal stock dimensions. Trim, boundary clearance, and kerf are never baked into them.
- Quantity is finite and creates that exact number of deterministic work-owned `StockInstance` records.
- Blank, zero, negative, or fractional quantities are errors. Unlimited stock is unsupported.

## Cell-value parsing

- Empty required values and Excel error cells are errors.
- Native numeric cells are preferred.
- Numeric text, if supported, uses ASCII digits, optional sign, and `.` as the only decimal separator. Thousands separators, comma decimals, currency, unit suffixes, and locale guessing are forbidden in 1.0.
- Integer fields must be mathematically integral and within implementation bounds; the importer never rounds them.
- All geometry/process numbers must be finite.
- Boolean values use the textual `Yes`/`No` contract only.
- Formulas may be accepted only when the chosen library reliably exposes a finite cached result without evaluating the formula. Missing or unreliable cached results produce `UNSUPPORTED_FORMULA_VALUE`.
- The importer must not evaluate formulas, execute macros, or follow external links.
- Dates are not required.

## Uniqueness, references, and work isolation

- `Work Key` is unique across the workbook.
- `Part Key` and `Stock Key` are unique within their referenced work.
- Every part and stock references a known work.
- Work name, part name, stock name, drawing number, worksheet position, and row number are never identity.
- Parts, stocks, demand, layouts, and results remain isolated by `WorkId`.
- Project-level shared stock is unsupported.

## Deterministic identifiers and ordering

The future importer must use a documented namespace-based deterministic ID algorithm. Schema 1.0 approves the following logical identity inputs:

```text
work:
  fixed Debbie canonical-import namespace + format name + schema major + trimmed Work Key

part type:
  WorkId + trimmed Part Key

demand item:
  WorkId + trimmed Part Key + canonical demand role/version

stock specification:
  WorkId + trimmed Stock Key

stock instance:
  StockSpecificationId + deterministic physical sequence 1..Quantity
```

Random UUIDs, row positions alone, worksheet positions, filesystem order, memory addresses, and file paths are forbidden identity inputs. Original worksheet/row coordinates are provenance only.

Equivalent canonical workbooks with reordered `Works`, `Parts`, or `Stocks` rows must produce equivalent domain objects, demand, stock instances, and solver results. Import records are normalized by stable canonical keys before deterministic physical sequences are generated.

## Atomic import and result boundary

Canonical import is atomic:

1. Read the workbook as untrusted data.
2. Recognize format and schema version from `Debbie` metadata.
3. Validate required worksheets and headers.
4. Parse rows into neutral import records.
5. Validate all cell values, keys, references, and uniqueness.
6. Validate trim/effective-region combinations and all domain invariants.
7. Construct all domain objects only after complete record validation.
8. Return all imported works only when the entire workbook succeeds.

An error returns no usable imported works and never mutates active application/domain state. Invalid rows are not skipped. The importer should accumulate all reasonably discoverable user-data errors, while unexpected internal failures remain distinguishable.

A future result is either:

- success: all imported works plus warnings/information; or
- failure: structured diagnostics and no usable works.

## Diagnostics

Every diagnostic should carry, where available:

- severity: `ERROR`, `WARNING`, or `INFO`;
- stable code;
- worksheet, row, and column/header;
- original value representation;
- human-readable explanation;
- related work, part, or stock key.

Any `ERROR` fails canonical import atomically. Warnings never silently change parsed values.

Initial stable categories are:

```text
WORKBOOK_FORMAT_MISMATCH
UNSUPPORTED_SCHEMA_VERSION
MISSING_REQUIRED_SHEET
DUPLICATE_REQUIRED_SHEET
MISSING_REQUIRED_HEADER
DUPLICATE_HEADER
EMPTY_REQUIRED_VALUE
INVALID_TEXT_VALUE
INVALID_NUMERIC_VALUE
NON_FINITE_NUMBER
NON_POSITIVE_DIMENSION
NEGATIVE_PROCESS_VALUE
INVALID_INTEGER_VALUE
INVALID_BOOLEAN_VALUE
DUPLICATE_WORK_KEY
DUPLICATE_PART_KEY
DUPLICATE_STOCK_KEY
UNKNOWN_WORK_REFERENCE
INVALID_TRIM_FOR_STOCK
INVALID_EFFECTIVE_STOCK_REGION
UNSUPPORTED_FORMULA_VALUE
MERGED_CELL_IN_DATA_TABLE
DOMAIN_VALIDATION_FAILURE
INTERNAL_IMPORT_ERROR
```

## Versioning and extensions

- Version `1.0` is strict.
- Unsupported major versions are rejected.
- A future schema is never silently interpreted as 1.0.
- Compatible minor-version handling requires a separately documented policy.
- Schema version and adapter identity are retained as provenance.
- Version recognition and migration belong in import adapters, not domain or nesting code.
- Additional worksheets/columns must not gain semantics until a schema revision approves them.

## Canonical template policy

A separately reviewed future deliverable may generate a blank 1.0 template with the four required sheets, metadata, headers, frozen rows, filters, basic formatting, and Excel data validation. It requires no macros or hidden logic. Spreadsheet validation is assistance only; Python validation remains authoritative.

## Security and reliability assumptions

Workbook content is untrusted. The importer must operate offline, avoid macro/formula execution and external links, make no network requests, bound unreasonable workbook/expanded ZIP sizes, and report unsupported workbook features. Library-level protections should be used against excessive archive expansion where available.

## Unsupported in schema 1.0

- `.xls`, CSV, and macro execution;
- Excel export or project persistence;
- UI preview implementation;
- legacy heuristic recognition in canonical mode;
- linear stock/cuts;
- arbitrary rotation, mirroring, grain, or visible-face constraints;
- material grade, thickness, supplier, stock cost, remnants, or unlimited stock;
- shared stock across works or per-stock trim overrides;
- clamps/keep-outs, toolpaths, cutting sequences, and machine instructions;
- CAD, ERP, cloud import, and automatic correction of malformed values.

## Canonical versus legacy

Canonical mode requires the `Debbie` metadata identity and this strict schema. Legacy adapters may later recognize selected historical layouts, must declare which adapter was used, emit compatibility warnings, map into the same neutral records, and use the same atomic domain construction. Legacy aliases never weaken canonical validation. See `LEGACY_IMPORT_INVENTORY.md`.

## Future acceptance traceability

Importer implementation must add at least:

- `test_IMPORT_001_recognizes_canonical_metadata`;
- `test_IMPORT_001_rejects_missing_required_sheet`;
- `test_IMPORT_001_rejects_duplicate_header`;
- `test_IMPORT_001_rejects_fractional_batch`;
- `test_IMPORT_001_rejects_fractional_quantity`;
- `test_IMPORT_001_keeps_kerf_and_clearance_separate`;
- `test_IMPORT_001_maps_rotation_yes_to_zero_and_ninety`;
- `test_IMPORT_001_maps_rotation_no_to_zero_only`;
- `test_IMPORT_001_reordered_rows_produce_equivalent_domain`;
- `test_IMPORT_001_import_is_atomic`;
- `test_IMPORT_001_reports_all_discoverable_validation_errors`;
- `test_IMPORT_001_deterministic_ids_repeat_across_imports`;
- `test_IMPORT_001_multiple_works_remain_isolated`;
- `test_IMPORT_001_unknown_work_reference_fails`;
- `test_IMPORT_001_invalid_trim_stock_combination_fails`;
- `test_IMPORT_001_unsupported_schema_version_fails`.

No importer tests exist yet because importer implementation has not begun.
