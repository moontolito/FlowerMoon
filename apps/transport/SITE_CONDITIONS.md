> Actualizare surse 2026-09-26: [SOURCE_ALIGNMENT.md](SOURCE_ALIGNMENT.md). Descrierile NASA / Valhalla DEM de mai jos sunt istorice; sursele active sunt Open-Meteo Historical si Copernicus GLO-90.

> Global update 2026-09-26: see [GLOBAL_ARCHITECTURE.md](GLOBAL_ARCHITECTURE.md). This specification supersedes older Romania-only assumptions, automatic C3/C5 suggestions and ERA5-Land adapter descriptions.

# Site & Environmental Conditions — implementation report

## Automatic climate integration

Temperatures now use 30 complete historical years for the selected destination.
NASA POWER/MERRA-2 is enabled without account configuration; an optional
Open-Meteo ERA5-Land adapter is available. Historical extremes and daily-mean
extremes are displayed directly, without project limits or default temperatures.
See `CLIMATE_INTEGRATION.md` for methods, live results, cache and validation.
On API failure, temperatures remain unavailable; no project defaults are substituted.

## Integration and design

The existing Tkinter/Sun Valley app is extended in place. Routing, fleet, pricing,
map, delivery allocation and Excel export remain shared. The map and route action
retain primary emphasis. Choosing a resolved destination automatically opens
**Date automate**, a results summary. The header action also opens this summary.
Transport, Environment and Structural Design Conditions remain optional editing
tabs. No field-by-field selection or Save is needed for automatic results.
The supplied logo and existing tokens remain unchanged: light background #FAFAFA,
surface #FFFFFF, text #1C1C1C, primary #82478C; dark background #1C1C1C,
surface #252527, text #FAFAFA, primary #D5A2DF. Warning text uses the shared
warning token. Sources/details and checklist dialogs keep explanations on demand.
The existing main screen has no space for a full engineering form; a separate
window preserves its map-first hierarchy and single destination entry.

## Files

- Modified `domain.py`: backward-compatible site migration, default departure,
  ferry evidence retained from the route response.
- Modified `app.py`: shared address/distance binding, debounced refresh,
  asynchronous environmental lookups, stale response guard, delivery snapshots.
- Modified `planner_ui.py`: secondary action in the existing header.
- Added `site_conditions.py`: UI-independent structured model, metadata,
  defaults/configuration, atomic validation, review flags and recommendation logic.
- Added `site_sources.py`: Valhalla DEM, local coastline and Overpass adapters.
- Added `site_ui.py`: automatic summary, optional editor, details, JSON export.
- Added `zoning.py`, four KML snapshots and a regional coastline extract under
  `zoning_sources/`, with provenance in `zoning_sources/SOURCES.md`.
- Added `test_zoning.py`, `verify_automatic_site.py`, and the optional live
  temporary-state check `verify_live_automatic_site.py`.
- Added `test_site_conditions.py`, `verify_site_ui.py`; updated
  `verify_planner.py` to mock the additional network adapter.
- Added this report and README usage notes.

## Data, automatic values and manual selections

`data/planning.json` gains `siteConditions` with a schema version. Existing data
is merged without rewriting old deliveries. Each new delivery gets a deep copy
of the current site conditions. JSON export supports future quotation/HVAC/
structural/coating integrations. Existing Excel output is unchanged.

Every relevant value stores value, unit, source, status, manualOverride,
lastUpdated and reviewRequired. Addresses and coordinates reference the existing
planner inputs. Existing departure values take precedence over the new default.
Humidity uses three numbered numeric fields: no undocumented interpretation.
The local `1. Project & Quotation Data.xlsm` was inspected read-only: it confirms
the displayed default notation but provides no meaning for its three positions.
Its older marine/C5 notes are superseded by this task's explicit requirement
for engineering confirmation without automatic C5 assignment.

- Distance: selected Valhalla road route, `CALCULATED`; no straight-line fallback.
- Altitude: maximum of up to 512 DEM samples distributed along the entire route,
  `VERIFY`. Sampling targets 500 m spacing, increasing for long routes to respect
  the point budget. The exact spacing is recorded. Peaks between samples are not
  guaranteed. Destination elevation is fetched separately and used as fallback
  and for snow/wind altitude applicability. No fabricated missing elevations.
- Marine environment: mapped coastline within a configurable 10 km screening radius
  gives `Possible / VERIFY`. The radius is a screening choice, not an ISO rule.
  Natural Earth 1:10 million regional geometry supplies an offline screening
  fallback; it is generalized cartography, not a site survey. Outside its coverage,
  Overpass remains available. No nearby mapped coast or API failure implies `No`.
- Ferry evidence: Valhalla OSRM step mode/classes. A ferry may cross an inland
  river, so maritime involvement remains `Unknown / VERIFY` until confirmed.
- Exterior/interior C3 and humidity values are project defaults; temperatures
  are sourced from historical climate data and have no default values.
  A coastal hint never assigns C5 or changes the selected permanent category.
- Seismic ag/Tc, snow sk and wind qb now populate automatically from the public
  UTCB/CCERS KML polygons linked in the Encipedia articles. Polygon holes and
  multipolygons are retained. Overlaps, uncovered points and proximity to boundaries
  are flagged. Snow/wind values are withheld at site altitude ≥1000 m. The `≥`
  operator in wind zones is retained as a lower bound. Maps remain informational,
  `VERIFY`, and requested references are not a claim of current code applicability.
- Suggested exterior corrosion is C3 (project default), or C5 as an explicitly
  provisional conservative suggestion when coastal exposure is possible. No
  salinity measurement is inferred. Confirmed maritime transport suggests C5
  separately for transport protection; it does not change the permanent category.

Manual values are never overwritten by lookup results. Changing destination or
coordinates clears derived data and marks manual site values **Review required**.
Route changes invalidate route-dependent values. Use **Confirm** plus **Save**
to reaffirm an unchanged value. If the destination changed while editing, saving
draft edits requires explicit confirmation for the new destination. A manual
site-distance override does not silently change transport pricing kilometres.

Resolved coordinates trigger local zoning, coastline screening, automatic saving,
the result window, and preliminary HGV routing after a short debounce. The current
compatible vehicle is used without an extra selection prompt; this does not mark
it as confirmed or approve transport permits. Route context records confirmation
state. Late responses are rejected and duplicate in-flight lookups suppressed.
Free-text address edits clear old coordinates;
use the existing **Caută** chooser to resolve and confirm the exact address.
The existing Romania geocoding restriction is retained; coordinates work abroad.

## Sources

- Existing routing and geocoding: Valhalla, Nominatim/OpenStreetMap.
- Elevation API: https://valhalla.github.io/valhalla/api/elevation/
- Coastline screening: https://overpass-api.de/api/interpreter
  and https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL
- Regional fallback: https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-coastline/
- Exact zoning map IDs, source URLs and dataset attribution: `zoning_sources/SOURCES.md`.
- Ferry evidence format: https://github.com/valhalla/valhalla/blob/master/src/tyr/route_serializer_osrm.cc
- Zoning resource index: https://www.encipedia.org/articole/proiectare/resurse-utile/2
  The originally requested directory URL returned 404 during verification;
  the UI includes the resource index and separate ag/Tc/snow/wind search actions.

Location APIs receive coordinates/route geometry, never product names or prices.
Failures leave missing data requiring manual confirmation. **Refresh location**
retries lookups. No weather observations are substituted for design temperatures.

## Verification and limits

Passed 20 unit tests (`test_transport`, `test_site_conditions`, `test_zoning`)
and four real Tk widget checks (`verify_ui.py`, `verify_planner.py`,
`verify_site_ui.py`, `verify_automatic_site.py`). These
cover old calculations/export, fleet/presets, route transfer/invalidation,
defaults/migration, numeric validation, manual preservation, location review,
sampled altitude/fallback, coast failure/absence, warnings, snapshots, save/load,
dark mode and minimum window size. Routing regression responses are simulated.
Light/dark windows were visually inspected; responsive wrapping was adjusted.

A full live automatic run for the public point 44.17, 28.65 on 2026-09-25 returned
630.896938 km from the stored Botoșani departure, a sampled route maximum of 270 m
(512 samples approximately 1233 m apart), destination elevation 5 m, and possible
coastal exposure. Zoning returned ag=0.20 g, Tc=0.7 s, sk=1.5 kN/m², qb=0.5 kPa.
The live summary was visually inspected. These verify the pipeline, not site
design suitability; route and data availability may change.

Next improvements: maintained/versioned geographic zoning datasets, explicit
engineering approval history, climate design datasets, and optional dedicated
project-sheet/quotation export of the structured site data.
