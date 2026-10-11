# FlowerMoon

Transport planning with destination environmental data, plus an HTML nesting tool.

- **Transport:** departure and delivery addresses with suggestions or map picking, vehicle selection for the product, truck routes and the delivery region.
- **Site & Environment:** for the delivery point — elevation, historical temperature and humidity, GEM seismic PGA, Romanian seismic / snow / wind zoning and coastal distance, each with its source.
- **Excel:** route costs, vehicle details and destination conditions with source references.
- **Nesting:** the existing part-arrangement tool (`apps/nesting/`).

## Ways to run Transport

| | Where | Use it for |
| --- | --- | --- |
| **Web app** (recommended) | Render, free plan — `apps/transport/webapp/` | Colleagues and demos: open a link, nothing to install. [Setup](docs/RENDER.md) |
| **Desktop app** | Windows, local — `apps/transport/run.py` | Full feature set, including vehicle profile editing and optional CAMS corrosivity. [Guide](apps/transport/README.md) |
| **Desktop in Codespaces** | GitHub Codespaces | Testing the desktop app from a browser without installing Python. [Guide](docs/CODESPACES.md) |

Both versions share the same engineering code in `apps/transport/src/`; the web app
only replaces the Tk interface with a browser page and a JSON API.

### Web app on Render

Render → **New → Blueprint** → this repository. `render.yaml` builds and starts it.
Locally:

```bash
cd apps/transport
python -m pip install -r webapp/requirements.txt
python ../../scripts/prepare_transport_assets.py
uvicorn webapp.server:app --reload --port 8000
```

### Desktop in Codespaces

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/moontolito/FlowerMoon?quickstart=1)

Create a Codespace; the FlowerMoon page opens on port **8000**. Select **Open application**.
After exporting, use **Download Excel** in the browser toolbar. Details, rebuilds and
the optional `FLOWERMOON_ADS_KEY` secret for CAMS: [docs/CODESPACES.md](docs/CODESPACES.md).

## Data

The GEM seismic raster is bundled as a 34.5 MB gzip archive;
`scripts/prepare_transport_assets.py` restores the 173 MB raster and verifies its SHA-256
(Render, Codespaces and CI run it automatically). No API key is needed except for the
optional CAMS assessment. Provider details and limits: [apps/transport/docs/](apps/transport/docs/README.md).

## Project layout

```text
apps/
  transport/
    src/          shared engineering, routing, source and export code
    webapp/       browser version: FastAPI server, static page, tests
    assets/       logo, Excel template, geography, zoning and GEM data
    tests/        desktop unit tests, UI checks and source fixtures
    docs/         technical notes (changes/ and archive/ inside)
    vendor/       Sun Valley theme with original licence
    run.py        desktop entry point · Porneste.cmd Windows launcher
    hosted.py     desktop entry point used by Codespaces
  nesting/        HTML nesting tool
web/portal/       Codespaces home page and desktop connection service
tests/browser/    Codespaces portal browser tests
scripts/          asset preparation, startup and verification utilities
docs/             Render, Codespaces and destination workflow guides
.devcontainer/    Codespaces environment
.github/          automated checks
render.yaml       Render Blueprint for the web app
```

[Destination, sources and export](docs/DESTINATION_WORKFLOW.md) · [Automated checks](https://github.com/moontolito/FlowerMoon/actions/workflows/transport-tests.yml)
