# Local Site & Environment update — 2026-09-27

The supplied `propt.txt` was used as a requested seismic layout, not as evidence that a source supplies a value.

## Interface

- Removed the three large elevation/temperature cards. Their values remain in the overview table.
- Added separate Unit, Meaning / use and Status columns. Selecting a row shows the fuller explanation; double-click opens sources and methods. Dataset headings also have descriptions.
- Retained the English UI, shared Sun Valley theme, logo and existing palette (`#82478C` accent, `#FAFAFA` background, `#FFFFFF` surfaces; corresponding shared dark tokens).
- Order: departure/map/transport; climate/humidity; seismic information; snow/wind; optional destination corrosivity last.
- Excel export reuses the same rows and includes their explanatory details and source links.

## Seismic limitations

PGA, reference and interpretation are distinct from national design parameters. Romania is a requested comparison reference, not a set of invented PGA thresholds. A defensible comparison still requires the reference PGA, return period, ground conditions and an interpretation rule.

The GEM ATLAS API requires access which has not been configured in this application. PGA is therefore displayed as Not available, with the reason and source link. No ag-to-PGA conversion or sampling of map colours is performed. Source: https://www.globalquakemodel.org/products/atlas

The expanded Romanian group retains ag and Tc from the existing P100-1/2013 maps. The integrated maps do not supply TB, TD or S, so those fields say Not available. Other countries show Not available under their national group, as requested. The code edition shown is the source-map edition, not a claim that it is the currently applicable project code.

## Optional annual corrosivity

Settings → Calculate annual corrosivity is initially off, including migration of old projects. Air-quality and deposition ADS workers are gated by that setting. Disabling cancels local polling, prevents further monthly submissions, and rejects in-flight callbacks. Jobs already submitted to ADS may finish remotely.

When enabled, the calculation requests the last complete calendar year (2025 at this update). Monthly jobs resume from a dedicated annual cache with at most two active monthly requests. It requires all 12 months and all eight daily forecast samples per input. Means are weighted by sample counts (including leap days); partial years and 30-day snapshots cannot produce an annual category. Former seasonal assessments are retained in history during migration.

ISO 9223:2012 provides annual dose-response equations and first-year carbon-steel category thresholds. Annual CAMS ground-deposition data is still a model proxy, not an ISO 9225 wet-candle measurement. The result remains an indicative annual estimate requiring verification, rather than a certified classification or coating specification. Wet-deposition flags are retained; flagged values do not enter the supplementary total-chloride scenario. Reference: https://www.iso.org/standard/53499.html

## Validation boundary

Annual aggregation, missing samples, leap years, queue limits, cache/resume, cancellation and stale callbacks are tested with fixtures and mocked provider calls. Native GRIB handling remains covered by the existing parser tests. No fresh full-year ADS download is started during implementation: the option is off until the user enables it. The global GEM value remains unavailable pending licensed API/data access.

Work is installed in the local source application. GitHub and the previously exported EXE are separate releases.
