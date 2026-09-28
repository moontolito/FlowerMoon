# CAMS atmospheric exposure (local installation)

The application reads **CAMS global reanalysis (EAC4) monthly averaged fields** from the Copernicus Atmosphere Data Store. The reference period is **January–December 2025**, the latest complete year verified in the catalogue when this adapter was added in September 2026. This reference year is explicit, not silently presented as current weather or as a multi-decade climate normal.

## Data and spatial reference

- Coverage: global regular 0.75° grid. The application requests a small area around the delivery destination and selects its nearest grid point. The requested coordinates, returned grid coordinates and distance between them are recorded.
- Level: **model level 60**, the lowest model layer. This is modelled near-surface air, not an instrument at a specified site height. Surface geometry and local sources are not resolved at building scale.
- Variables: `sulphur_dioxide`, `sea_salt_aerosol_0.03-0.5um_mixing_ratio`, `sea_salt_aerosol_0.5-5um_mixing_ratio`, `sea_salt_aerosol_5-20um_mixing_ratio`.
- Native unit: kg/kg. Display unit: **µg/kg of air**, using a factor of 1e9. This is a mass mixing ratio, not µg/m³.
- Sea-salt total: sum of the three bins at **80% relative humidity**. The separately labelled dry-equivalent mass divides this sum by **4.3**, following ECMWF guidance. Bin radii in the documentation refer to the RH80% convention.
- Annual mean: average of the 12 monthly means weighted by calendar days in each month. The detail record retains all monthly values and the minimum/maximum monthly mean; these are not hourly pollution extremes.
- No conversion to deposition flux, chloride deposition, ISO corrosion category or health threshold is made. Such quantities need additional validated methods and evidence.

## Application behaviour

Choosing the delivery point loads CAMS in the background. ADS jobs can be queued; the application checks again automatically every 20 seconds without freezing the interface. Job identifiers are cached so that closing/reopening the app can resume retrieval. Completed historical data is cached for 30 days. **Refresh data** retries failed requests. A licence/access/network failure is shown explicitly and never becomes a zero.

Moving the destination clears its previous air-quality values. Late replies cannot replace the new destination's data. Overview, JSON and the Transport Excel export use the same source record. No additional manual-edit tab is introduced.

## Local access

The ADS token is stored outside the project in `%LOCALAPPDATA%\FlowerMoon\Secrets\ads.json`, encrypted with Windows DPAPI for the current Windows user. It is not included in project state, caches, source code or exported files. Other platforms may provide `FLOWERMOON_ADS_KEY` as an environment variable. `FLOWERMOON_CAMS_ENABLED=0` disables automatic requests, including in offline regression tests.

The account must accept the dataset licence at:
https://ads.atmosphere.copernicus.eu/datasets/cams-global-reanalysis-eac4-monthly?tab=download#manage-licences

Dependencies: `cdsapi==0.7.7`, `netCDF4==1.7.4` (plus the existing Pillow dependency).

## Primary references

- https://ads.atmosphere.copernicus.eu/how-to-api
- https://ads.atmosphere.copernicus.eu/datasets/cams-global-reanalysis-eac4-monthly
- https://ads.atmosphere.copernicus.eu/api/retrieve/v1/processes/cams-global-reanalysis-eac4-monthly
- https://confluence.ecmwf.int/pages/viewpage.action?pageId=621030809
- https://confluence.ecmwf.int/plugins/viewsource/viewpagesrc.action?pageId=70951402

This release is local only. GitHub remains unchanged until explicitly requested.
