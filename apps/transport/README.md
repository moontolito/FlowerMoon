# FlowerMoon Transport — testing build

Python/Tkinter transport planner with the existing FlowerMoon / Sun Valley interface. For browser testing, use [the Codespaces instructions](../../README.md).

## Windows

Install Python with Tkinter, then run in this folder:

```powershell
py -3 -m pip install -r requirements.txt
```

Open `Porneste.cmd`. Install dependencies with the same interpreter used by the launcher.

## Test checklist

1. Enter product dimensions and weight; select a suitable vehicle.
2. Choose a destination through address search or the map.
3. Check route distance and Site & Environment. Climate, humidity and elevation load independently of route availability.
4. Confirm temperature/RH periods, sources and verification notes.
5. Modify a value manually, refresh, and confirm the manual value is preserved.
6. Change destination; ensure previous automatic values are not reused.
7. Add a delivery and export the calculation workbook.
8. Test both themes and a smaller window. Report destination, steps, expected result and actual result, avoiding private customer information.

## Data and limits

- Temperature/RH: Open-Meteo Historical / ERA5. RH statistics are hourly; temperatures are historical reanalysis, not current sensor readings.
- Altitude: Copernicus DEM GLO-90, nominal 90 m DSM.
- Routes: OSM / the configured Valhalla server. Public endpoints can throttle or fail; no car-route substitution is used.
- Country/coast: Natural Earth GIS. Structural maps currently cover Romania only.
- CAMS, EFEHR, TOW and the corrosion index are not implemented/validated. No automatic ISO corrosion category is claimed.

The [source alignment document](SOURCE_ALIGNMENT.md) records actual providers and their limits. For commercial Open-Meteo usage, configure the appropriate access through a Codespaces secret named `FLOWERMOON_CLIMATE_API_KEY`; never commit credentials. `FLOWERMOON_CLIMATE_URL` can override the historical endpoint. No credentials are shipped in this repository.

## Developer checks

```bash
python -m unittest discover -p 'test_*.py'
python verify_source_ui.py
```

GUI checks require a desktop/X display. GitHub Actions runs them under Xvfb on Ubuntu. The Sun Valley theme is vendored with its original MIT license; FlowerMoon branding and application code have not been relicensed as open source.
