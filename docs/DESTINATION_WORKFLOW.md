# Destination, sources and export

The Transport interface and browser portal use English. Supplied addresses, place names and user-entered project content retain their original spelling.

## Site & Environment

The overview contains **Parameter**, **Value**, **Source**, and **Location / reference**. The former observations column is removed. Source displays the actual provider, a manual entry, or a clear absence of data; it does not substitute a processing status such as calculated or automatic for the provider name.

The header and location rows identify the delivery address and WGS84 coordinates. Destination elevation, historical climate, humidity and structural zoning refer to that point. Route distance and maximum route-sample elevation are grouped separately. Manual values retained after moving the destination are identified as belonging to the previous destination until confirmed.

Select **Sources & location details** for provider URLs, grid coordinates, historical period and applicability information. ERA5 is gridded reanalysis rather than an on-site sensor; Copernicus is a surface model rather than a site survey; zoning values come from the polygon containing the destination. Regional structural coverage remains limited to installed datasets.

## Addresses and boundaries

- Suggestions: [Photon / OpenStreetMap](https://github.com/komoot/photon/blob/master/docs/api-v1.md), with English results, a 650 ms typing delay, a six-result limit, request throttling, a session cache and stale-result rejection. The public demo is suitable for light testing and provides no availability guarantee. Set `FLOWERMOON_PHOTON_URL` to use another Photon deployment. Autocomplete does not call public Nominatim, whose policy does not permit this use.
- Boundaries: [geoBoundaries gbOpen](https://www.geoboundaries.org/api.html), first-level administrative polygons (ADM1). This means counties in Romania, states in the USA and the corresponding level in other countries. Coverage, names and dataset dates vary; this is not a universal county-level dataset. The selected polygon is highlighted with a dashed FlowerMoon border. The original provider, year, API URL and licence are retained with the result. Boundaries are cached for 30 days; `FLOWERMOON_BOUNDARIES_URL` can replace the metadata API.
- Missing or ambiguous polygons produce an unavailable result. No nearest-region or rectangular substitute is drawn. These boundaries are separate from engineering zoning maps and do not determine snow, seismic or wind parameters.

## Excel

Select **Export Excel** directly in Transport. The export dialog accepts trip quantity, empty kilometres and rates. **Current transport** exports the selected route without first adding it to a worksheet. **Saved deliveries** exports previously stored deliveries; their quantities and empty distances are retained. Saved delivery management remains available under **More**.

The workbook contains **Transport**, **Routes**, and **Site & Environment**. The site sheet records each delivery address, coordinates, parameter, value, source, spatial reference and source URL. Existing calculation formulas and their cached results are retained with English labels.

In Codespaces, exports are saved under `apps/transport/data/exports/`. **Download Excel** appears in the browser toolbar for the latest file. Downloads are restricted to Excel files inside that directory; private project files are not served. Local desktop users choose a save location normally.

## Verification

Regression checks cover existing calculations and editing, manual-value retention, automatic destination lookups, autocomplete keyboard selection and stale responses, polygon holes and date-line geometry, boundary clearing, direct export totals, English workbook formulas and site provenance, and the private download endpoint. GitHub Actions also records actual public-source availability separately from deterministic tests and captures the English destination interface.
