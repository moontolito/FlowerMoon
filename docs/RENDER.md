# Browser version on Render (free plan)

The browser version runs Transport as a normal web application: the page, map and
tables render in the visitor's browser, and the server only answers small JSON
requests. There is no desktop, VNC or screen streaming, so it stays responsive on
Render's free instance.

```text
apps/transport/webapp/
  server.py        FastAPI routes (JSON API, Excel download, seismic map tiles)
  workspace.py     one browser session: the Planner workflow without Tk
  static/          index.html, app.css, app.js, vendored Leaflet 1.9.4
  tests/           API checks with external providers replaced by fakes
render.yaml        Render Blueprint (repository root)
```

All engineering logic is reused unchanged from `apps/transport/src/`: vehicle
selection, Valhalla routing, Photon addresses, Copernicus elevation, Open-Meteo
climate and humidity, GEM PGA, Romanian zoning, geoBoundaries regions and the
Excel template.

## Deploy

**New service (recommended):** Render Dashboard → **New → Blueprint** → select this
repository. Render reads `render.yaml` and creates `flowermoon-transport` on the
free plan.

**Existing service:** open the service → **Settings** and set

| Setting | Value |
| --- | --- |
| Runtime | Python 3 |
| Build Command | `pip install -r apps/transport/webapp/requirements.txt && python scripts/prepare_transport_assets.py` |
| Start Command | `cd apps/transport && uvicorn webapp.server:app --host 0.0.0.0 --port $PORT --workers 1 --proxy-headers --forwarded-allow-ips '*'` |
| Health Check Path | `/healthz` |
| Environment | `PYTHON_VERSION=3.13.1` |

If the existing service uses Docker (the Codespaces desktop image), create a new
Blueprint service instead: a Docker service cannot be switched to the Python runtime.

## Run locally

```bash
cd apps/transport
python -m pip install -r webapp/requirements.txt
python ../../scripts/prepare_transport_assets.py
uvicorn webapp.server:app --reload --port 8000
# open http://localhost:8000
```

Tests: `python -m unittest discover -s webapp/tests -t .` (needs `httpx`).

## Free-plan behaviour

- The instance sleeps after about 15 minutes without traffic; the first visit then
  takes up to a minute. After that, clicks respond immediately. An external
  uptime ping every 10 minutes keeps it awake (the free plan includes 750 hours
  per month, enough for one service).
- The disk is temporary. Sessions, provider caches and saved deliveries reset on
  redeploy or restart. Export Excel to keep results.
- Memory: about 50 MB at start and about 250 MB peak after a destination lookup,
  mostly the bundled Natural Earth country polygons. The free plan allows 512 MB.

## Scope of this version

Included: address suggestions, map picking with reverse address lookup, exact
coordinates and via points, automatic preliminary route once both points are set
(as in the desktop app), product editing, vehicle presets and adjustments,
truck route options, delivery region outline, seismic PGA map layer, the full
Site & Environment table with value details, saved deliveries, Excel and JSON
export, light and dark themes.

Not exposed yet: editing vehicle profiles, the Valhalla server setting and the
optional CAMS corrosivity assessment (it needs a personal ADS key and long
background jobs). The desktop app keeps all of these.
