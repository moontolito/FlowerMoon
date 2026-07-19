# Debbie Nesting Workbook Schema 1.1 — Draft

## Status and compatibility boundary

This is a **proposed, unimplemented schema** for Product Owner and engineering review. It does not replace the accepted `Debbie Nesting Workbook` schema `1.0` in `EXCEL_SCHEMA_V1.md`, does not authorize importer changes, and is not accepted canonical input today.

Schema `1.1` preserves the four canonical worksheet names and the strict, atomic, key-based import principles of schema 1.0 while adding Work material/thickness/density data and explicit stock-allocation geometry. A future 1.1 importer must recognize the metadata version before parsing version-specific headers. It must not silently upgrade 1.0, interpret 1.1 as 1.0, guess header aliases, or fall back to a legacy adapter.

## Workbook identity and units

The workbook contains exactly one metadata declaration using the existing `Debbie` sheet:

| Key | Required value |
|---|---|
| `Format Name` | `Debbie Nesting Workbook` |
| `Schema Version` | `1.1` |
| `Units` | `mm` |
| `Density Units` | `g/cm3` |

Required worksheets remain:

1. `Debbie`
2. `Works`
3. `Parts`
4. `Stocks`

Worksheet names and row-1 headers are case-sensitive canonical strings. Column order may vary; header meaning may not. No alias, fuzzy matching, hidden default, row-position identity, formula evaluation, or locale-dependent numeric conversion is permitted.

## `Debbie` worksheet

Required headers:

| Column | Type | Requirement |
|---|---|---|
| `Key` | Text | Non-empty and unique. |
| `Value` | Text | Non-empty for required metadata keys. |

Required keys are `Format Name`, `Schema Version`, `Units`, and `Density Units`, with the exact values above. `Density Units` is required because density participates in engineering calculations and must never be inferred. As in schema 1.0, optional `Application Version` and `Description` metadata are provenance only. Other unknown metadata keys require an explicit future extension policy rather than changing calculation meaning.

## `Works` worksheet

Proposed canonical headers (all required except `Material Description`):

| Column | Type | Requirement |
|---|---|---|
| `Work Key` | Text | Non-empty, unique canonical key. |
| `Work Name` | Text | Non-empty display label; not identity. |
| `Material Category Key` | Text | Stable controlled identifier; exact launch vocabulary remains pending. |
| `Material Category Name` | Text | Non-empty display label; does not replace the key. |
| `Material Grade Key` | Text | Stable non-empty grade identifier, including an explicit custom namespace if approved. |
| `Material Grade Name` | Text | Non-empty display label. |
| `Thickness (mm)` | Decimal | Positive, finite Work-level nominal thickness. |
| `Density (g/cm3)` | Decimal | Positive, finite effective-density snapshot. |
| `Density Source` | Text enum | Proposed values: `library_default`, `explicit_override`. |
| `Material Description` | Text | Optional human-readable detail; never identity or a source of inferred fields. |
| `Batch Multiplier` | Integer | Positive integer. |
| `Kerf (mm)` | Decimal | Finite and non-negative. |
| `Part Clearance (mm)` | Decimal | Finite and non-negative. |
| `Boundary Clearance (mm)` | Decimal | Finite and non-negative. |
| `Trim Left (mm)` | Decimal | Finite and non-negative. |
| `Trim Right (mm)` | Decimal | Finite and non-negative. |
| `Trim Top (mm)` | Decimal | Finite and non-negative. |
| `Trim Bottom (mm)` | Decimal | Finite and non-negative. |

Each Work defines one homogeneous material category, grade, thickness, effective density, and process context. A future library match may validate or initialize those fields, but imported values are explicit snapshots and are never silently rewritten.

## `Parts` worksheet

Canonical headers remain unchanged from schema 1.0 (required unless marked optional):

| Column | Type | Requirement |
|---|---|---|
| `Work Key` | Text | Must reference exactly one `Works.Work Key`. |
| `Part Key` | Text | Non-empty and unique within its Work. |
| `Part Name` | Text | Non-empty display label. |
| `Length (mm)` | Decimal | Positive, finite nominal rectangle length. |
| `Width (mm)` | Decimal | Positive, finite nominal rectangle width. |
| `Quantity` | Integer | Positive integer before Work batch expansion. |
| `Allow Rotation` | Text enum | Exactly `Yes` or `No`. |
| `Drawing Number` | Text | Optional provenance field; may be blank and never replaces `Part Key`. |

Parts inherit material category, grade, thickness, and density from the referenced Work. Schema 1.1 has no part-level override columns for those properties. The rectangular part mass is explicitly an estimate based on nominal bounding dimensions, not exact CAD/net-part mass.

## `Stocks` worksheet

Proposed required headers:

| Column | Type | Requirement |
|---|---|---|
| `Work Key` | Text | Must reference exactly one `Works.Work Key`. |
| `Stock Key` | Text | Non-empty and unique within its Work. |
| `Stock Name` | Text | Non-empty display label. |
| `Full Length (mm)` | Decimal | Positive, finite source-sheet length. |
| `Full Width (mm)` | Decimal | Positive, finite source-sheet width. |
| `Allocated Length (mm)` | Decimal | Positive, finite nestable rectangle length, not greater than full length. |
| `Allocated Width (mm)` | Decimal | Positive, finite nestable rectangle width, not greater than full width. |
| `Commercial Allocation Fraction` | Decimal | Positive, finite commercial allocation satisfying physical fraction through `1`. |
| `Quantity` | Integer | Positive integer count of identical allocation records. |

Stocks inherit material category, grade, thickness, density, and process settings from the referenced Work. Schema 1.1 deliberately does not accept a `Physical Fraction` input column: physical fraction is derived from geometry.

Proposed derivation:

`physical_fraction = (Allocated Length × Allocated Width) / (Full Length × Full Width)`

For a full allocation, allocated and full dimensions are equal and the physical fraction is `1`. For a partial allocation, the proposed first contract anchors the allocated rectangle at the source-sheet origin and provides no X/Y offset. Full and partial stock remain explicit records; identical records may use `Quantity`, while different allocated rectangles require different `Stock Key` values.

## Proposed cross-record validation

A future 1.1 importer should accumulate structured diagnostics and return no usable works when any error exists. In addition to schema 1.0 invariants, it should validate:

- exact 1.1 metadata and density units;
- stable non-empty material category and grade identities;
- positive finite thickness and density;
- supported density provenance values;
- part and stock references to exactly one Work;
- no material, grade, thickness, or density override at part/stock level;
- positive allocated and full dimensions;
- allocated dimensions contained within full dimensions;
- derived physical fraction satisfying `0 < physical_fraction <= 1`;
- accepted first-contract commercial constraint `physical_fraction <= commercial_allocation_fraction <= 1`;
- Work trim plus boundary clearance leaving a valid region inside the allocated rectangle;
- positive integer stock quantity and demand quantity;
- deterministic identities independent of row or worksheet order; and
- no cross-Work stock, demand, layout, or result ownership.

Unknown columns, missing required columns, duplicate headers, formulas, non-finite numbers, unsupported enum text, and ambiguous keys remain errors. `Material Description` is the only optional column proposed in this draft; an empty value carries no implicit semantics.

## Physical and commercial interpretation

`Full Length` and `Full Width` preserve source-sheet and commercial provenance. `Allocated Length` and `Allocated Width` define the only rectangle available to future nesting. A physical fraction alone cannot establish shape or placement feasibility and is therefore not canonical input.

`Commercial Allocation Fraction` records the portion of a full sheet assigned commercially to that allocation. For example, an allocated half sheet may have physical fraction `0.5` and commercial fraction `1.0` when purchasing/accounting charges a complete source sheet. This difference must not enlarge nestable geometry.

The future solver should apply Work trim and boundary-clearance rules to the allocated rectangle, subject to Product Owner approval of that detailed rule. The unallocated remainder does not become inventory automatically. Remnant geometry, location, ownership, reuse, and lifecycle require a separate decision and a future versioned contract.

## Version dispatch and migration

- Metadata `Schema Version = 1.0` is parsed only by the accepted schema 1.0 adapter and its exact headers.
- Metadata `Schema Version = 1.1` will be parsed only by a future, separately approved schema 1.1 adapter and its exact headers.
- A 1.0 workbook lacking material/allocation fields is not upgraded by inserting defaults.
- A 1.1 workbook is not downgraded by ignoring its additional fields.
- Unsupported or missing versions fail with structured diagnostics and no partial Work state.
- Legacy layouts remain named compatibility adapters and never become version fallback behavior.

Any explicit 1.0-to-1.1 migration/template workflow must ask for or deterministically supply reviewed material, grade, thickness, density, density provenance, full geometry, allocated geometry, and commercial allocation. That workflow is not approved or implemented by this draft.

## Example stock rows

| Work Key | Stock Key | Stock Name | Full Length (mm) | Full Width (mm) | Allocated Length (mm) | Allocated Width (mm) | Commercial Allocation Fraction | Quantity |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `W-STEEL-3` | `S-FULL` | Full sheet | 2500 | 1250 | 2500 | 1250 | 1 | 4 |
| `W-STEEL-3` | `S-HALF` | Allocated half | 2500 | 1250 | 1250 | 1250 | 1 | 1 |

The second row has derived physical fraction `0.5` but explicit commercial fraction `1`. With thickness `3 mm` and density `7.9 g/cm3`, the physical and commercial calculations are shown in `MATERIAL_AND_WEIGHT_MODEL.md`.

## Explicitly outside this draft

This draft does not define or implement material-library storage, coatings, price/cost, suppliers, heat/batch certificates, exact CAD part mass, non-rectangular allocations, allocation offsets, remnant creation, shared inventory, cross-Work nesting, schema migration tooling, legacy adapters, linear stock, export, persistence, UI behavior, or solver objectives based on mass or cost.
