# Debbie Material, Allocation, and Weight Model

## Purpose and status

This document defines the approved product direction and the proposed detailed contract for material identity, thickness, partial-sheet allocation, and mass reporting in Debbie vNext. It is a documentation gate only: none of these additions is implemented in the domain, importer, solver, desktop UI, export, or persistence layers.

The Product Owner accepted the high-level direction for `MATERIAL-001`, `THICKNESS-001`, `ALLOCATION-001`, and `WEIGHT-001` on 2026-07-19. Rules explicitly labelled **Proposed** remain review items and must not be treated as implemented or binding input behavior. Remnant inventory, material-library ownership, costing, purchasing, ERP integration, and optimization by mass or commercial allocation remain deferred.

| Decision | Accepted product direction | Proposed or deferred detail |
|---|---|---|
| `MATERIAL-001` | Explicit homogeneous Work material/grade and density snapshot with provenance. | Controlled vocabulary, custom-grade permissions, coating model, and library administration are proposed/deferred. |
| `THICKNESS-001` | Positive Work-level millimetre thickness inherited without row-level overrides. | No unresolved first-contract ownership rule. |
| `ALLOCATION-001` | Explicit full/allocated rectangle, derived physical fraction, separate commercial fraction, and first-contract fraction bounds. | Origin, trim boundary, and remnant lifecycle are proposed/deferred details. |
| `WEIGHT-001` | Dimensionally correct separate part-estimate, physical, commercial, difference, and per-product calculations, with authoritative measure names and a PARTIAL presentation boundary. | Detailed UI styling is deferred. |

No decision is rejected in this gate. The accepted directions do not exist in the current Python models or canonical schema 1.0.

## Approved homogeneous Work boundary

One `Work` represents one homogeneous production and reporting context:

- one material category;
- one material grade;
- one nominal thickness;
- one effective-density snapshot and provenance policy;
- one process profile; and
- only parts and stock compatible with that material, grade, thickness, and process.

Parts and stocks inherit material category, grade, thickness, and effective density from their owning `Work`. They do not override those values in the first contract. Different material categories, grades, thicknesses, or incompatible process requirements require distinct works. Existing `WORK-001` isolation remains authoritative: works do not share stock, layouts, or nesting runs.

Project summaries may show several works together, but they retain per-work identity and detail. Kilogram values may be summed only when the summary explicitly says that it is a simple physical-mass total. Debbie must not average densities, infer shared stock, or merge nesting across works.

Material and thickness are never inferred from `Work Name`, stock labels, or part labels. Duplicate Work display names are permitted; stable `Work Key`/`WorkId` identity and the explicit engineering fields distinguish the Works.

## Material identity and density (`MATERIAL-001`)

### Approved direction

- Material is explicit Work-level data, not text inferred from part or stock names.
- A material identity contains a stable category identifier and display name plus a stable grade identifier and display name.
- Effective density is a positive finite value stored in canonical unit `g/cm³` as a snapshot on the Work.
- `g/cm³` and `kg/dm³` have the same numeric value; Excel uses the ASCII-safe `g/cm3` spelling while engineering prose uses superscript notation.
- Density provenance is retained so reports can distinguish a library default from an explicit override.
- A future material library may propose defaults, but changing the library never silently changes an existing Work snapshot.

### Proposed detailed policy

- Controlled category identifiers should initially cover `steel`, `stainless_steel`, `aluminium`, `copper`, `zinc`, and `other`, with stable machine identifiers independent of localized display labels.
- Grade should be required and non-empty. A controlled list may assist selection, while an explicit custom-grade path preserves uncommon production grades without inventing a false match.
- Category/grade compatibility should initially produce a structured warning when the combination is unknown, not rejection, unless an approved library later identifies the combination as impossible.
- `density_source` should be one of `library_default` or `explicit_override`; future migrations may add another explicit provenance value without reinterpreting existing records.
- Zinc-plated steel should remain a category/coating modelling question. Until a coating model is approved, it must not be silently normalized to zinc or carbon steel.

The category vocabulary, custom-grade policy, material-library ownership, and zinc-plated-steel treatment remain pending Product Owner review.

## Thickness (`THICKNESS-001`)

Nominal thickness is an explicit positive finite Work-level value in millimetres. Every part and stock in that Work inherits the same thickness. Per-part and per-stock thickness overrides are forbidden in the first contract because they would break homogeneous-work compatibility, mass reconciliation, and stock eligibility. A job containing more than one thickness must use more than one Work.

Thickness is independent from 2D part length/width, trim, kerf, clearance, rendering scale, and display rounding. Import and UI validation must reject zero, negative, non-finite, or missing thickness once schema 1.1 is implemented.

## Partial-sheet allocation (`ALLOCATION-001`)

### Approved direction

Partial stock is represented by explicit geometry, not by a fraction alone. Each future stock record retains:

- full-sheet length and width for provenance and commercial reference;
- allocated-rectangle length and width for physical availability;
- a derived physical fraction;
- an explicit commercial fraction; and
- a positive integer quantity.

The physical and commercial views are separate. Debbie must not infer one from the other or describe commercial purchasing/accounting allocation as geometry.

### Proposed first detailed contract

- The allocated rectangle is anchored at the full-sheet origin; schema 1.1 has no X/Y allocation offset.
- Allocated length follows the full-sheet length/X direction and allocated width follows the full-sheet width/Y direction. The first contract has no separate cut-direction or allocation-rotation field; `1250 × 1250` and `2500 × 625` remain geometrically distinct half-sheet allocations.
- Allocated dimensions must be positive and must fit inside the corresponding full dimensions.
- The geometric physical fraction is derived, never entered independently:

  `physical_fraction = (allocated_length_mm × allocated_width_mm) / (full_length_mm × full_width_mm)`

- The physical fraction must satisfy `0 < physical_fraction <= 1`.
- The commercial fraction must satisfy `physical_fraction <= commercial_fraction <= 1`. The accepted first contract allows commercial allocation greater than physical allocation and rejects a smaller value rather than guessing its business meaning.
- Full and partial allocations are distinct stock records. Identical allocations may be grouped using `Quantity`; geometrically different allocations remain separate records.
- The future solver should see the allocated rectangle as the stock geometry and apply the Work's trim and boundary-clearance rules to that rectangle. Full dimensions are provenance and reporting data, not additional nestable space.
- The unallocated remainder is not automatically inventory. Debbie may preserve source provenance sufficient for a future remnant workflow, but remnant creation, shape tracking, reuse, and lifecycle are deferred.

The origin/offset policy, trim application boundary, and remnant lifecycle remain detailed review items until Product Owner acceptance. A fraction without allocated geometry is insufficient for nesting in every case.

## Weight terminology and formulas (`WEIGHT-001`)

### Dimensional contract

For a rectangular volume measured in millimetres with density in grams per cubic centimetre:

`mass_kg = length_mm × width_mm × thickness_mm × density_g_per_cm3 / 1,000,000`

Dimension proof:

`mm × mm × mm = mm3`; `1 cm3 = 1,000 mm3`; density therefore gives grams after division by `1,000`; and grams become kilograms after another division by `1,000`. The combined divisor is `1,000,000`.

Geometry calculations use unrounded source values. Display rounding happens only after the authoritative result is calculated and never feeds back into geometry, identity, reconciliation, or persistence.

### Authoritative measures

- **Rectangular Part Mass Estimate:** `part_length × part_width × Work thickness × Work density / 1,000,000`, multiplied by expanded required quantity. This is a bounding-rectangle estimate, not exact CAD/net-part mass.
- **Gross Physical Allocation Mass:** sum of `allocated_length × allocated_width × Work thickness × Work density / 1,000,000 × stock quantity`.
- **Gross Commercial Allocation Mass:** sum of `full_length × full_width × Work thickness × Work density / 1,000,000 × commercial_fraction × stock quantity`.
- **Equivalent Physical Sheets:** sum of `physical_fraction × stock quantity`.
- **Equivalent Commercial Sheets:** sum of `commercial_fraction × stock quantity`.
- **Per-product values:** divide the applicable authoritative Work total by the positive Work batch multiplier. Do not multiply an already expanded total again by stock count or batch count.
- **Physical Unused Allocation Mass:** Gross Physical Allocation Mass minus the appropriate post-nesting rectangular part-mass estimate for parts placed on consumed stock instances.
- **Commercial Allocation Difference:** Gross Commercial Allocation Mass minus Gross Physical Allocation Mass.
- **Commercial Material Allowance:** Gross Commercial Allocation Mass minus the appropriate placed rectangular part-mass estimate.

The corresponding per-product formulas are:

- `Gross Physical Allocation Mass per Product = Gross Physical Allocation Mass / Batch Multiplier`;
- `Gross Commercial Allocation Mass per Product = Gross Commercial Allocation Mass / Batch Multiplier`; and
- `Rectangular Part Mass per Product = Rectangular Part Mass Estimate for the expanded batch / Batch Multiplier`.

Expanded Part Quantity is `Base Quantity × Batch Multiplier` and must reconcile as a positive integer under the existing batch policy. Equivalent-sheet sums already include physical stock quantity; that quantity must not be multiplied a second time.

These are distinct business quantities. Debbie must not label all differences as `scrap`: physical unused allocation may contain reusable space; a commercial allocation difference may represent purchasing/accounting policy; and neither value establishes a remnant, scrap sale, toolpath loss, or exact net-part mass.

Physical Unused Allocation Mass may include four-sided trim, boundary and part clearances, kerf/process allowances, spaces between rectangles, entirely unused regions, and error introduced by rectangular part approximation. It is therefore not an authoritative machine scrap or saleable-remnant measurement.

### Pre-nesting and post-nesting scope

Pre-nesting planning may show required rectangular part-mass estimates and available inventory allocation totals, clearly labelled as planning values. Post-nesting results use only stock instances actually consumed by the result, not all available inventory.

For a `PARTIAL` result, Debbie reports batch-level consumed allocation mass, placed rectangular mass, and unplaced rectangular mass estimate separately, with structured reason codes visible. It withholds the normal completed-product gross-mass presentation rather than implying the batch is fulfilled. It must not charge unconsumed inventory as physically used. A `FAILED_VALIDATION` result or a cancelled operation does not produce an accepted post-nesting production mass summary.

For a `COMPLETE` result, result-specific physical and commercial totals use only the consumed stock instances, placed rectangular mass reconciles to all expanded demand, unplaced estimated mass is zero, and per-product allocation values may be presented as complete-result values. `COMPLETE` still does not make rectangular mass an exact CAD/net-part mass, make unused allocation synonymous with scrap, make the non-guillotine result machine-ready, or establish a toolpath.

### Invalid and unavailable calculation conditions

- Missing, zero, negative, or non-finite density or thickness makes every dependent mass calculation invalid; Debbie must return structured diagnostics rather than zero or a guessed default.
- A missing, zero, negative, non-integral, or non-finite batch multiplier makes expanded-demand and per-product calculations invalid.
- A physical fraction outside `(0, 1]`, allocated dimensions outside full dimensions, or a commercial fraction outside the accepted range makes that stock allocation invalid.
- With no allocated stock, available physical/commercial stock totals may be reported as zero only when the Work is otherwise valid and the label clearly means available inventory; no consumed-result mass exists.
- Before nesting, only planning/inventory calculations are available. Consumed stock, placed/unplaced mass, result-specific unused mass, and result-specific per-product allocation require an accepted nesting result.
- A `PARTIAL` result retains valid consumed-stock and placed/unplaced calculations but must not expose an unqualified completed-product claim.
- Display rounding, missing UI state, and material-name inference never repair an invalid engineering input.

## Worked example: four full sheets and one half sheet

Assume a Work with batch multiplier `10`, full sheet `2500 × 1250 mm`, thickness `3 mm`, and density `7.9 g/cm3`. A result consumes four full sheets and one allocated rectangle of `1250 × 1250 mm` from a fifth full sheet.

Full-sheet mass:

`2500 × 1250 × 3 × 7.9 / 1,000,000 = 74.0625 kg`

Half-sheet physical mass:

`1250 × 1250 × 3 × 7.9 / 1,000,000 = 37.03125 kg`

Equivalent Physical Sheets:

`4 × 1 + 1 × 0.5 = 4.5 sheets`

Gross Physical Allocation Mass:

`4 × 74.0625 + 1 × 37.03125 = 333.28125 kg`

Gross Physical Allocation Mass per product:

`333.28125 / 10 = 33.328125 kg/product`

Display values rounded to two decimals are `333.28 kg` and `33.33 kg/product`. There is no additional multiplication by five: the four full instances and one half instance were already included in the sum.

If the half-sheet geometry is commercially charged as one full sheet, its commercial fraction is `1`, so:

- Equivalent Commercial Sheets = `5`;
- Gross Commercial Allocation Mass = `5 × 74.0625 = 370.3125 kg`;
- Commercial Allocation Difference = `370.3125 - 333.28125 = 37.03125 kg`; and
- Gross Commercial Allocation Mass per product = `37.03125 kg/product`.

The `0.5` physical fraction describes nestable geometry. The `1.0` commercial fraction describes the chosen commercial allocation. They are intentionally not interchangeable.

## Future UI implications (documentation only)

A later UI should provide controlled material-category and grade selectors with an explicit custom-grade workflow, show density plus provenance, and require Work thickness. Stock editing should show full and allocated dimensions together, derive the physical fraction live, and keep commercial fraction separately labelled.

Planning and result views should separate physical from commercial measures, explain every formula through labels/tooltips, show whether values are pre- or post-nesting, and keep `PARTIAL` status plus placed/unplaced demand visible. It must not present a rectangular part estimate as exact part mass or use `scrap` as a catch-all label. These are UI requirements only; this gate adds no widgets or behavior.

## Product Owner review questions and recommendations

| # | Question | Recommended direction | Status |
|---|---|---|---|
| 1 | Is Material Grade mandatory for custom/`Other` materials? | Yes. Require a non-empty stable grade identity and provide an explicit custom namespace/value rather than dropping grade identity. | Proposed |
| 2 | Is density override always allowed or permission-controlled later? | Allow an explicit positive finite override in the first contract with visible provenance; a later role/permission system may govern who can apply it without changing stored meaning. | Proposed |
| 3 | May Commercial Allocation Fraction exceed Physical Allocation Fraction? | Yes, up to `1`, because commercial charging may include physically unallocated source material. | Accepted first-contract rule |
| 4 | May Commercial Allocation Fraction be smaller than Physical Allocation Fraction? | No in the first contract; require `physical_fraction <= commercial_fraction <= 1` and reject rather than infer a credit/reuse policy. | Accepted first-contract rule |
| 5 | Are partial allocated regions always origin-anchored in v1? | Yes. Anchor at the source origin and add offsets only through a later versioned schema backed by production evidence. | Proposed |
| 6 | Does trim apply to the full sheet or allocated rectangle? | Apply Work trim to the allocated nestable rectangle; retain full dimensions only for provenance/commercial reporting. | Proposed; manufacturing review required |
| 7 | Is leftover material provenance only or a future remnant candidate? | Preserve source/remainder provenance as a future candidate, but do not automatically create or promise usable remnant inventory. | Proposed/deferred |
| 8 | What official terminology replaces ambiguous `scrap`? | Use `Physical Unused Allocation Mass`, `Commercial Allocation Difference`, and `Commercial Material Allowance`; reserve `scrap` for a future disposition decision. | Accepted terminology |
| 9 | Is rectangular part mass called net weight or estimated rectangular mass? | Use `Rectangular Part Mass Estimate`; do not claim exact net/finished mass without CAD geometry. | Accepted terminology |
| 10 | Must schema 1.1 state allocated dimensions even for full sheets? | Yes. Require explicit values equal to full dimensions; do not use blank-driven defaults in a canonical schema. | Proposed |
| 11 | How are `PARTIAL` result masses presented per product? | Show batch-level consumed and placed/unplaced masses with a prominent incomplete-demand status; withhold the normal completed-product gross-mass presentation. | Accepted presentation boundary; detailed UI deferred |
| 12 | Is Zinc-Plated Steel a category or coating over Steel? | Treat this as an unresolved coating model; do not silently collapse it into zinc or uncoated steel. | Pending |

Implementation of schema 1.1, UI, exports, persistence, remnant handling, and any behavior governed by the remaining proposed details stays blocked until separate review and authorization.

## Implementation checkpoint

The first pure-Python domain and calculation foundation now implements the
accepted portions of `MATERIAL-001`, `THICKNESS-001`, `ALLOCATION-001`, and
`WEIGHT-001` without implementing schema 1.1 import or Desktop integration.

- `MaterialIdentity`, stable category/grade keys, `Density`, `DensitySource`,
  and `Thickness` are immutable Work-level values.
- `Work` preserves a deliberate compatibility boundary: material and thickness
  are either both present or both absent. Existing schema 1.0 construction
  remains unclassified and receives no invented values; mass calculation then
  returns structured `MATERIAL_DATA_REQUIRED` unavailability.
- `StockAllocation` retains full and allocated rectangles, derives physical
  fraction without rounding, and enforces the accepted commercial bounds.
  Legacy stock construction retains a structural full-allocation view only for
  compatibility; a material-classified Work requires explicit allocation.
- Allocation containment and commercial bounds are strict input invariants:
  overshoot is rejected even below geometry epsilon rather than silently
  clamped. The centralized geometry epsilon remains limited to placement
  predicates; it does not rewrite full/allocated provenance.
- For an explicitly allocated stock, `StockSpecification.dimensions` remains
  the rectangle visible to current nesting and must equal the allocated
  dimensions. Full dimensions remain allocation provenance. This preserves the
  current strategy while avoiding exposure of unallocated material.
- Partial allocation with non-zero Work trim or boundary clearance is rejected
  at solver preparation with `FAILED_VALIDATION`. This is a safety isolation
  boundary, not an acceptance of where trim applies; partial allocation with
  zero trim and zero boundary clearance can use its explicit rectangle.
- `calculate_work_mass_plan` uses all available Work stock instances;
  `calculate_nesting_result_mass` uses only stock instances consumed by the
  supplied result. Both sort by stable identity and use `math.fsum`.
- COMPLETE exposes per-product values; PARTIAL exposes batch-level consumed and
  placed/unplaced values but withholds completed-product values;
  FAILED_VALIDATION produces no fabricated consumption totals.

The origin-anchor proposal and the rule applying Work trim/boundary clearance
to the allocated rectangle remain unresolved product/manufacturing decisions.
This implementation adds no allocation offset or remnant shape and does not
change trim, geometry-validator, or solver-strategy behavior. Schema 1.1 import,
Desktop presentation, a material library, remnants, costing, export, and
persistence remain unimplemented.
