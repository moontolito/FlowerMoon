# Local GEM seismic hazard — 2026-09-27

The user supplied `GEM-GSHM_PGA-475y-rock_v2023.zip`. The application now reads
the official numeric raster locally when the delivery destination changes or
Site & Environment is opened/refreshed. There are no GEM API calls or credentials.
The update keeps the existing English Overview, routing, national parameters
and optional annual corrosion calculation.

## Source and method

- Dataset: GEM Global Seismic Hazard Map 2023.1.
- Source: https://zenodo.org/records/8409647
- Original file: `v2023_1_pga_475_rock_3min.tif` (172,818,403 bytes).
- SHA-256: `c6928e0edea4d2a03e6a0d6b4aa9699159834f015c20ffb2d8ee8492ff67a5af`.
- Single-band, uncompressed Float64, 7200 x 3000 cells, EPSG:4326, PixelIsArea.
- Cell spacing: 0.05 degrees longitude, 0.049996666666667 degrees latitude.
- Extent: -180 to 180 longitude, approximately -60 to 89.99 latitude; NoData
  cells inside this extent remain unavailable.
- PGA in g, 10% exceedance probability in 50 years (approximately 475 years),
  reference rock Vs30 760–800 m/s. GEM interpolated model points spaced about
  6 km using inverse-distance weighting, as described in the supplied README.
- The app reads the containing cell using the TIFF geotransform. It does not
  scan colours, extrapolate missing cells or add further numerical interpolation.
- The checksum and layout are validated on first access and cached by file
  identity/stat/manifest. Unsupported, corrupt or missing datasets fail without
  inventing a value. Numeric lookup uses the Python standard library only.

The original README and CC BY-NC-SA 4.0 licence are retained beside the raster.
The details display the source, licence, version, cell coordinates, row/column,
resolution, exact retained numeric value and checksum. Commercial use requires
an appropriate agreement with GEM; the supplied archive is not evidence of such
an agreement. This local integration does not upload or redistribute the dataset.

## Presentation

- Existing Seismic Information / PGA row is populated automatically. Value and
  unit are separate in the Overview; three decimal places are display rounding.
- PGA is modelled hazard for the destination, not measured ground acceleration
  and not national design `ag`. No TB, TC, TD, S or national classification is
  inferred. The previous Romania comparison placeholder stays uncalculated.
- Double-click / Value details shows provenance and limitations.
- `Seismic PGA` on the map toggles an optional translucent layer. Existing OSM
  tiles, route, markers and administrative borders are preserved. The overlay
  renders only the viewport, sampled at up to 512 x 512 pixels, reprojecting
  Web Mercator coordinates to the WGS84 data grid. It uses the GEM README palette;
  values above the last class use the highest colour. NoData is transparent.
- The layer is off at app startup; its choice survives theme/panel rebuilds.
- Destination changes discard old hazard records, and the presentation checks
  stored coordinates before displaying a saved value.
- Saved site snapshots, JSON and Excel preserve the source information.

## Validation

- 128 unit tests passed, including nine new raster tests: known Bucuresti sample,
  six-continent locations, missing data/file, invalid points, integrity failure,
  cell boundaries, genuine zero values, antimeridian, stale snapshots and overlay
  agreement with the numeric cell value.
- Bucuresti sample (44.4268, 26.1025): 0.3229623135362622 g; London sample
  (51.5074, -0.1278): 0.008103378339223416 g. These are grid-model values.
- First integrity check and lookup ~95 ms in this local test; later scalar reads
  ~0.1–0.2 ms. These timings are machine-dependent, not performance guarantees.
- Native Tkinter test passed: automatic destination update, source dialog,
  original Romanian national rows, light/dark layer, 1000x700 layout, NoData,
  clearing a destination, saved state and Excel provenance; no network required.
- Existing annual-corrosion lifecycle and planner interaction scenarios passed.

Only the installed local source application is updated. GitHub and the previously
exported EXE are unchanged. Restart via `Porneste.cmd` to load this version.
