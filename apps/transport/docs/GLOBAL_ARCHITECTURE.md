> Actualizare surse 2026-09-26: [SOURCE_ALIGNMENT.md](SOURCE_ALIGNMENT.md). Descrierile NASA / Valhalla DEM de mai jos sunt istorice; sursele active sunt Open-Meteo Historical si Copernicus GLO-90.

> Update 2026-09-26: [HUMIDITY_AND_OBSERVATIONS.md](HUMIDITY_AND_OBSERVATIONS.md) adds automatic daily RH statistics and retains sourced map values with verification notes.

# Global Site & Environment — implementation 2026-09-26

Romania is a test region and an optional regional standards adapter. It is not a geographic limit. This document supersedes older Romania-only and automatic C3/C5 descriptions in the application documentation.

## 1. Data sources and actual implementation

| Domain | Installed source | Coverage / output | Limits |
|---|---|---|---|
| Address search | Nominatim-compatible `/search`, configurable with `FLOWERMOON_GEOCODER_URL` | No country filter; coordinates and display address | Instance/OSM coverage. Public service maximum 1 request/sec, no autocomplete, attribution required. Existing request limiter uses 1.1 sec. |
| Routing | Configurable Valhalla server | Truck route geometry, km, driving time | Coverage of the actual server; not an ocean freight planner, road survey or transport permit. Automatic failure is non-modal and cannot block site data. |
| Temperature | NASA POWER daily point API by default | Last 30 complete calendar years, daily maximum/minimum/mean | Global gridded reanalysis, not a station or live thermometer. NASA LST daily basis retained explicitly in metadata. |
| Optional temperature | Open-Meteo Historical API, explicitly configured endpoint/key | ERA5, nearest cell, UTC, same requested years | Usage entitlement must cover deployment. ERA5 selected instead of land-only preference; no implicit model blending. On failure, whole-series NASA fallback is recorded. |
| Country/territory | Natural Earth countries 1:10m, local snapshot | Point-in-polygon, polygon holes/multipolygons | Generalized cartography, not legal boundary evidence. Unknown is retained for ocean, missing islands or polygon gaps. |
| Coastal distance | Natural Earth coastline 1:50m, local snapshot | Approximate shortest spherical point-to-segment distance, km | Small-scale cartography; no salinity, no automatic marine category and no distance-to-ISO mapping. |
| Elevation | Actual Valhalla `/height` endpoint | Destination elevation or sampled route maximum, m | DEM identity not verified; never relabelled Copernicus. Samples can miss peaks. |
| Structural maps | `utcb-ro` regional adapter wrapping existing `zoning.py` | RO only: ag, Tc, sk, qb | Informational snapshots labelled P100-1/2013, CR 1-1-3/2012, CR 1-1-4/2012. No assertion that these are current project codes. Existing altitude/zone-boundary checks remain in RO adapter. |

**Not implemented as active providers:** direct Copernicus GLO-90 raster retrieval, CAMS ADS retrieval, EFEHR/GEM hazard retrieval, automatic hourly RH/wind/rain/snow. Their absence is not replaced by assumed values. Registry entries for GLO-90/CAMS are explicitly `installed=false`; they cannot be selected. CAMS additionally needs a user account, token and dataset licence acceptance. Existing custom humidity fields remain manual and do not pretend to be automatic meteorological statistics.

Sources checked:
- [Nominatim API](https://nominatim.org/release-docs/latest/api/Search/) and [public-service policy](https://operations.osmfoundation.org/policies/nominatim/).
- [Valhalla](https://github.com/valhalla/valhalla).
- [NASA POWER daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) and [data sources](https://power.larc.nasa.gov/docs/methodology/data/sources/).
- [Open-Meteo Historical API](https://open-meteo.com/en/docs/historical-weather-api) and [usage terms](https://open-meteo.com/en/terms).
- [Natural Earth](https://www.naturalearthdata.com/about/); exact downloaded URLs, hashes and acquisition times in `site_environment/datasets/manifest.json`.
- [Copernicus DEM](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM).
- [CAMS EAC4](https://ads.atmosphere.copernicus.eu/datasets/cams-global-reanalysis-eac4?tab=overview) and [ADS access](https://ads.atmosphere.copernicus.eu/how-to-api).

## 2. Calculated parameters and method provenance

| Parameter | Method | Method source / status | Units / limitations |
|---|---|---|---|
| Historical temperature extremes | `max(daily maxima)`, `min(daily minima)` over the entire validated period | `historical-daily-extrema-v1`; descriptive statistics implemented by FlowerMoon, not a normative design method | °C; reject missing days, null/nonfinite values, invalid units and inconsistent min/mean/max. All daily records required. |
| Daily-average extremes | `max(daily means)`, `min(daily means)` | Same descriptive algorithm; data provider supplies the daily aggregates | °C; not annual mean, forecast or design limits. |
| Coastal distance | For each mapped segment use spherical cross-track distance when along-track projection is inside the segment; otherwise nearest endpoint; take minimum | `spherical-nearest-coast-segment-v1`, own GIS approximation, R=6,371,000 m | km; antimeridian-safe, limited by coastline generalization. No ISO status. |
| Country | Ray-crossing point-in-polygon with holes | `point-in-polygon-v1`, geographic estimate | Country/territory code or unknown; not authoritative jurisdiction. |
| Boundary screening | Flag jurisdiction for verification when another country's generalized polygon is within 2 km near the containing polygon edge; retain sourced values | Own conservative application tolerance, **not a normative threshold** | A coastal edge alone does not constitute a neighbouring-country ambiguity. |
| Route elevation | Maximum of up to 512 samples along route; fallback destination value labelled separately | Existing application sampling, estimate | m; not a guaranteed maximum or road surface survey. |

Temperature plausibility bounds -100..70 °C are parser quality checks, not engineering design bounds. Manual values remain independent. The climate snapshot records requested coordinates, actual provider, period, units, model, temporal basis, dataset metadata, download timestamp, normalized-response SHA256, request parameters without secrets, fallback status and method version. Cache keys separate the global-v2 method/model from the previous implementation. Cached data is revalidated. Different daily time bases (NASA LST versus optional Open-Meteo UTC) remain explicit; results must not be treated as identical products.

## 3. Corrosion estimation

Automatic C3/C5 recommendations from coast proximity or shipping have been removed. Default exterior/interior C3 and legacy humidity values 100/26/90 are no longer populated as site results. User-entered values are preserved.

Time of Wetness and Corrosion Environment Index have no numeric output. They are labelled `method_not_validated`. No weights, category thresholds or ISO formula have been invented. The proposed RH>80% and T>0°C criterion requires verification against the applicable edition/clause before implementation; daily statistics cannot reconstruct eligible hours.

SO2 mass mixing ratio, sea-salt mass mixing ratio, atmospheric concentration and surface deposition are different quantities. No undocumented conversion is implemented. Outdoor climate does not determine indoor corrosivity.

References for future method validation: [ISO 9223:2012](https://www.iso.org/standard/53499.html), [ISO 12944-2:2017](https://www.iso.org/standard/64834.html). Public catalogue summaries do not substitute for verified clauses.

## 4. API and extraction

- NASA request: `/api/temporal/daily/point`, `parameters=T2M_MAX,T2M_MIN,T2M`, `community=RE`, WGS84 longitude/latitude, dates `YYYYMMDD`, `format=JSON`. Full complete daily series, units C, no secret required. Default LST is recorded from response.
- Open-Meteo configured endpoint: `daily=temperature_2m_max,temperature_2m_min,temperature_2m_mean`, `models=era5`, `timezone=UTC`, `cell_selection=nearest`, dates `YYYY-MM-DD`. API key only in outbound request; excluded from snapshot/export.
- Nominatim: free-text `q`, `format=jsonv2`, `addressdetails=1`, `limit=5`; no `countrycodes=ro`. Endpoint configuration allows replacement without changing the UI.
- Valhalla: existing server setting and truck restrictions retained. Its DEM remains server-dependent. No hardcoded worldwide deployment claim.
- Global country/coast files are local and read-only at runtime. No geocoding API calls are required for country screening. Dataset coverage and service availability are independent.

## 5. Python architecture

`site_environment/geography.py`: country, coast and coordinate validation.

`site_environment/registry.py`: immutable provider descriptions, installed/configured status, coverage, variable capabilities and selection. Global weather order is chosen here. Planned providers are excluded from selection.

`site_environment/standards.py`: coordinate/country applicability, regional dispatch and explicit unavailable results.

`site_environment/service.py`: context/provenance and application of structural results.

Existing tested modules remain adapters: `routing.py`, `climate.py`, `site_sources.py`, and RO-specific `zoning.py`. Their migration into additional folders is unnecessary to isolate the regional rules. UI and storage continue through `site_ui.py` and `site_conditions.py`.

To add a regional provider: register its supported jurisdiction/variables, implement its adapter, retain exact standard/edition and source metadata, then add inside/outside/boundary tests. Do not map global PGA directly to ag or Tc. A normative provider cannot be selected only because it is geographically nearby.

## 6. Validation, migration and limits

- Schema v2 migration preserves manual values, marks manual structural values for review and archives replaced nonmanual legacy defaults/map values in `legacyDefaults`. Old delivery snapshots are left as historical records. Back up current project data before deployment.
- Location changes clear automatic values and their obsolete provenance; manual overrides stay and require review. Late results for old coordinates remain rejected.
- Offline geographic checkpoints cover Europe, North/South America, Asia, Africa and Oceania; include oceans, boundaries, missing datasets, antimeridian and polar geometry. A coast-edge coordinate in Constanta outside the generalized country polygon intentionally receives no Romanian normative values; the inland checkpoint retains the original map values.
- Live validation: Paris, New York, São Paulo, Tokyo, Johannesburg, Sydney; actual geocodes plus 10,958 daily temperature records per location (1996–2025). See `global-live-report.json`. This verifies selected points, not every location worldwide.
- UI validation includes a Japanese destination with a failed road route, automatic climate/site completion without an error dialog, source labels, persistence, manual overrides, compact layout and both themes.
- Web Mercator cannot display latitudes beyond approximately ±85°. Polar coordinates remain valid for data lookup; the map explicitly states its display limitation. Longitudes wrap at ±180° and short antimeridian spans are used for fitting/routes.
- Only Romania currently has a structural map adapter. Elsewhere structural fields stay unavailable/manual; there is no worldwide normative wind/snow/seismic solution asserted by this release.
- The Botosani departure address and EXW remain project inputs, not geographic restrictions.
