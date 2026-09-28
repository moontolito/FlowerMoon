# 30-day atmospheric exposure and corrosion scenario

The local app requests one rolling window of 30 complete forecast dates, ending yesterday in UTC. Each date uses the 00 UTC forecast and leads 3, 6, 9, 12, 15, 18, 21 and 24 hours: 240 samples for each of 16 variables. The last lead is valid at midnight following the last forecast date. Period bounds and grid are displayed in the overview and value details.

The cache key includes the period, requested grid and method version. Results for the same grid/window are reused, including on Refresh; the request is resumed after a restart. The next daily window uses a new cache key. Annual jobs and files remain preserved, but this mode does not poll or submit annual requests. Existing completed downloads can be imported only when their request parameters and raw hash match and the parser verifies all samples.

The existing ISO 9223 carbon-steel equation is evaluated using matching 30-day temperature, humidity, SO2 and dry-plus-settling chloride proxies. The output in µm/year is an **annualized seasonal scenario** assuming recent conditions persist. It is not measured 30-day loss, a verified annual prediction, an ISO-conforming classification, or a paint-system specification. C1–CX is explicitly labelled seasonal; extrapolation warnings and existing final/manual classes remain intact. The separate 2025 EAC4 air-quality statistics and long-term ERA5 climate fields are unchanged and are not inputs to this scenario.

## Negative wet-deposition values

The live GRIB probe contains negative wet-deposition samples. Their cause has not been established. They are retained unchanged in the raw file and signed period means, with counts and minima disclosed by parameter. No numeric tolerance, clipping, zero filling or assumption about packing noise is introduced. Wet-derived table values are marked **source flagged**, and the optional corrosion scenario using total wet-plus-dry chloride is disabled. The main scenario uses nonnegative dry deposition plus gravitational settling, independent of wet fluxes. Nonfinite values, negative dry/settling/SO2 values, invalid meteorology, missing/duplicate samples, wrong units, dates, grid or levels still fail validation.

## References

- CAMS forecasts: https://ads.atmosphere.copernicus.eu/datasets/cams-global-atmospheric-composition-forecasts
- Dataset and access documentation: https://confluence.ecmwf.int/spaces/CKB/pages/212454117/CAMS+Global+atmospheric+composition+forecast+data+documentation
- ISO 9223:2012: https://www.iso.org/standard/53499.html

The approximately three-minute completed probe is one observed retrieval, not a service-level guarantee. No GitHub changes are part of this local update.
