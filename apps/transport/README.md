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
7. Select **Export Excel** directly in Transport; check the Transport, Routes and Site & Environment sheets. In Codespaces, use **Download Excel** in the browser toolbar.
8. Test both themes and a smaller window. Report destination, steps, expected result and actual result, avoiding private customer information.

## Data and limits

- Temperature/RH: Open-Meteo Historical / ERA5. RH statistics are hourly; temperatures are historical reanalysis, not current sensor readings.
- Altitude: Copernicus DEM GLO-90, nominal 90 m DSM.
- Routes: OSM / the configured Valhalla server. Public endpoints can throttle or fail; no car-route substitution is used.
- Country/coast: Natural Earth GIS. Structural maps currently cover Romania only.
- Address suggestions: Photon / OpenStreetMap. Delivery region: geoBoundaries gbOpen ADM1, where available. See [destination and source details](../../docs/DESTINATION_WORKFLOW.md).
- CAMS, EFEHR, TOW and the corrosion index are not implemented/validated. No automatic ISO corrosion category is claimed.

The [source alignment document](docs/SOURCE_ALIGNMENT.md) records actual providers and their limits. For commercial Open-Meteo usage, configure the appropriate access through a Codespaces secret named `FLOWERMOON_CLIMATE_API_KEY`; never commit credentials. `FLOWERMOON_CLIMATE_URL` can override the historical endpoint. No credentials are shipped in this repository.

## Developer checks

```bash
python tests/run_checks.py
python tests/run_checks.py --ui
```

GUI checks require a desktop/X display. GitHub Actions runs them under Xvfb on Ubuntu. The Sun Valley theme is vendored with its original MIT license; FlowerMoon branding and application code have not been relicensed as open source.

Source lives in `src/`, assets in `assets/`, technical notes in `docs/`, third-party theme in `vendor/`. Start locally with `python run.py` (or `python run.py --offline` for an offline session). `hosted.py` is the managed Codespaces entry point; testers use the browser portal. Existing project data remains in `data/`.
