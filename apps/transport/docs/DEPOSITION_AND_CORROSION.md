# Destination deposition and indicative exterior corrosivity

Local installation only. No change to GitHub. Existing manual final classes,
indoor classes, routes and saved delivery data are preserved.

## Source and temporal coverage

The existing EAC4 monthly air-quality rows remain unchanged. The new adapter
uses the **CAMS global atmospheric composition forecast archive**, reference
year **2025**, on its 0.4-degree grid. These are archived model forecasts, not
EAC4 reanalysis or measurements on a structure. Select the nearest grid point
globally, including poles and the longitude wrap. Record the destination and
returned grid coordinates separately.

Request 00 UTC forecasts for every day, lead hours 3, 6, 9, 12, 15, 18, 21, 24.
The GRIB fields must be **instantaneous flux samples** with the documented
units and expected time/level metadata. Their arithmetic mean estimates the
annual mean flux; it does not reconstruct sub-three-hour variability. The last
sample is midnight following 31 December (the endpoint of that day's sampling).
Monthly requests are resumed by job ID, with at most two active requests per
destination. All 12 months, every date and every expected variable/sample must
be present before publishing annual statistics. Missing/negative/nonfinite
data, unexpected units, levels, time processing, grids and duplicates are errors.
Raw GRIB files, hashes, requests and monthly means are retained for audit.
Refresh retries failed requests and reuses validated historical month results.
The interface checks queued work every 20 seconds. ADS tape retrieval may take
considerably longer than the EAC4 monthly download.

## Displayed deposition quantities

Three sea-salt size bins are summed for each distinct process:

- Dry deposition, parameter IDs 215004–215006.
- Gravitational settling/sedimentation, 215007–215009.
- Wet deposition by large-scale precipitation, 215010–215012.
- Wet deposition by convective precipitation, 215013–215015.

All archived sea-salt mass diagnostics use the RH80% convention. Convert to dry
mass by division by **4.3** (IFS CY49R1 documentation). For instantaneous flux
in kg/m²/s, the displayed annual-mean rate in mg/m²/day is the sample mean times
1,000,000 times 86,400 divided by 4.3. Do not interpret these as accumulated
fields or divide by forecast lead time. Gravitational settling is a separate
diagnostic; wet large-scale and convective contributions are summed once.

The **chloride estimate** assumes fresh sea-salt composition: chloride is
**55% of dry sea-salt mass**. This is an explicit composition assumption, not a
downloaded chloride variable. It does not include atmospheric chloride depletion,
de-icing salt or industrial chlorides. Dry+settling and total (including wet)
chloride estimates are displayed separately.

## Matching meteorology and SO2

Use the same forecast samples/grid for 2m temperature, 2m dewpoint, surface
pressure and SO2 at the lowest model level 137. RH is estimated with the Magnus
formula over water: e(T)=610.94 exp(17.625 T/(T+243.04)) Pa, T in Celsius;
RH=100 e(Tdew)/e(Tair). This RH formulation is documented as an approximation.
Moist-air density = (p - 0.378 e)/(287.05 TK). SO2 kg/kg times density times 1e9
gives µg/m³. Using 2m meteorology/surface pressure for ML137 is an approximation;
it is not an exact reconstruction of hybrid-level pressure and density.
Mean temperature, RH and SO2 are computed from matched individual samples,
not by multiplying unrelated annual averages. Display this annual input set
separately from the application's longer historical climate statistics.

## ISO calculation and interpretation

Material/exposure assumption: **carbon steel in outdoor atmosphere**.
Use ISO 9223:2012 Equation 1 for first-year loss r in µm/year:

    r = 1.77 Pd^0.52 exp(0.020 RH + fT)
        + 0.102 Sd^0.62 exp(0.033 RH + 0.040 T)
    fT = 0.150(T-10) when T <= 10; otherwise -0.054(T-10)

Pd is estimated as 0.8 times annual SO2 concentration (µg/m³), following the
standard's approximate concentration/deposition relationship. Sd uses **dry +
settling chloride as an uncalibrated ground-flux proxy**. It has not been shown
equivalent to the ISO 9225 wet-candle measurement and this application does not
claim normative conformity. This difference can materially affect the result.

ISO 9223 Table 2 carbon-steel boundaries: C1 <=1.3; C2 >1.3–25; C3 >25–50;
C4 >50–80; C5 >80–200; CX >200–700 µm/year. Above 700, no class is assigned.
Table 3 calibration intervals: T -17.1–28.7°C; RH 34–93%; Pd 0.7–150.4 and Sd
0.4–760.5 mg/m²/day. Values outside these intervals are not clipped; the result
is explicitly labelled **extrapolated**. Otherwise it is labelled **preliminary**.
Neither label means the proxy has been validated or that the result is suitable
for final design. A total-chloride scenario is retained in the detail record to
show sensitivity to deposition choice; this is not a confidence interval.

The formula and threshold implementation is tested; the CAMS-to-wet-candle
equivalence is not validated. Do not attach an unsubstantiated accuracy figure.
Local sea spray, microclimate, sheltered exposure and special chemical industrial
environments can require a different assessment. Indoor and immersion classes
are not inferred from exterior data.

The result stays in **Indicative exterior category**, with verification status,
and never overwrites the final exterior or interior class. C1–CX are categories
of atmospheric corrosivity, not layer counts, paint thicknesses or durability
grades. Selecting a coating system still needs substrate preparation, intended
durability and a qualified system under the relevant ISO 12944 provisions.

## Primary sources

- https://ads.atmosphere.copernicus.eu/datasets/cams-global-atmospheric-composition-forecasts
- https://www.ecmwf.int/sites/default/files/elibrary/112024/81630-ifs-documentation-cy49r1-part-viii-atmospheric-composition.pdf
- https://gmd.copernicus.org/articles/12/4627/2019/ (separate dry deposition and settling processes)
- https://doi.org/10.1038/ncomms15883 (55% chloride fresh sea-salt composition)
- https://www.iso.org/standard/53499.html
- https://nnr.co.za/wp-content/uploads/2024/04/Appendix-5.8.E-ISO_9223_2012en.pdf
- https://www.iso.org/standard/77795.html

Credentials continue to use the existing Windows DPAPI store outside the project.
The additional GRIB dependency is eccodes==2.48.0. FLOWERMOON_CAMS_ENABLED=0
disables live automatic requests during offline regression checks.
