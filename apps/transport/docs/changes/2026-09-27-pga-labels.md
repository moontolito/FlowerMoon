# PGA display labels — 2026-09-27

The destination PGA row keeps its numeric value in g. The existing interpretation
row now shows **PGA level**, assigned from the unrounded source value using the
user-approved names. The map legend uses the same function and band names.

| PGA (g), lower inclusive / upper exclusive | Application label |
| --- | --- |
| 0.00–0.01 | Very low |
| 0.01–0.02 | Low |
| 0.02–0.03 | Low to moderate |
| 0.03–0.05 | Moderate |
| 0.05–0.08 | Moderately elevated |
| 0.08–0.13 | Elevated |
| 0.13–0.20 | High |
| 0.20–0.35 | Very high |
| 0.35–0.55 | Extremely high |
| 0.55–0.90 | Exceptional |
| ≥0.90 | Very exceptional |

These are application display labels, not official GEM, national-code, earthquake
magnitude or building-damage categories. No label is assigned to missing/invalid
values. Precision increases near a threshold if rounding would appear to put the
numeric value in another band. Original source values and national design inputs
are unchanged.

The PGA meaning is the user's sentence:

> PGA shows how strongly the ground could shake at a location during an earthquake, with a higher value meaning stronger expected shaking.

The full sentence appears in the selection explanation, value details and Excel
source details. The compact table column summarizes it without displaying Markdown
asterisks. The `PGA hazard reference` row is removed from both the overview and export.

Validation: 17 targeted unit tests passed, including every band boundary, values
immediately below a boundary, zero, high values, invalid values, unavailable data
and stale destinations. Native UI verification passed for the labels, source
meaning, removed row, legend, light/dark and compact layouts, state and Excel.

Local source update only; restart via `Porneste.cmd`. GitHub, raster source data,
saved planning data and the earlier exported EXE are unchanged.
