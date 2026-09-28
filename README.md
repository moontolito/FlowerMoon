# FlowerMoon

Transport planning, destination environmental data and nesting tools in one private workspace.

- **Transport:** find departure and delivery addresses with suggestions, select a vehicle, check routes and highlight the delivery region. Site & Environment identifies the destination coordinates and the actual sources for elevation, temperature, humidity and available structural zoning.
- **Excel:** export directly from Transport. The workbook includes route costs, vehicle details and destination conditions with source references.
- **Nesting:** open the existing part-arrangement tool from the same home page.

## Open in your browser

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/moontolito/FlowerMoon?quickstart=1)

1. Create a Codespace using the button above. You need access to this private repository.
2. Wait for initial setup. The FlowerMoon page opens automatically. If your browser blocks this, select **Open in Browser** for **8000 — FlowerMoon** in **Ports**.
3. Select **Open application**. Startup and connection are automatic.

No Python commands or extra desktop password are needed. Bookmark the generated FlowerMoon address; add `/app` to open Transport directly. The link works while its Codespace is running.

**Existing Codespace:** pull the latest `main` using Source Control, then stop and restart the Codespace to load the updated application. For this update, use **Codespaces: Rebuild Container** after pulling to install the new CAMS dependencies and restore the bundled seismic dataset. A new Codespace uses the current configuration immediately. Preserve any unsaved work before restarting the app or rebuilding.

After exporting in Transport, select **Download Excel** in the browser toolbar. Projects and exports stay in `apps/transport/data/`, inside your session, and are excluded from Git.

The repository and application port remain private. Each tester needs repository access and their own Codespace. Codespaces uses the GitHub account quota; stop the session after testing.

## Current Transport version

This repository includes the installed Transport app as of 28 September 2026: destination selection on the map, crossing-aware route display, the Site & Environment overview, source details, GEM seismic values, and optional annual CAMS/corrosivity assessment.

Codespaces runs the existing Tkinter app through the browser desktop portal on port **8000**. The dataset is bundled as a 34.5 MB gzip archive; setup restores the exact 173 MB raster and checks its SHA-256 against the versioned manifest. No dataset download or API key is needed for the seismic map.

### Optional CAMS access

For CAMS data, add a personal Codespaces secret named **FLOWERMOON_ADS_KEY** and grant it access to this repository, then restart the Codespace. Use your Copernicus ADS personal access token and accept the required dataset terms in your ADS account. The Windows encrypted credential stays on the local computer. Corrosivity assessment is disabled by default; enable it in Application settings when needed. Without ADS access, these results remain unavailable and the rest of Transport can still run.

GitHub secret settings: https://github.com/settings/codespaces

## Project layout

```text
apps/
  transport/
    src/         application and shared interface code
    assets/      logo, Excel template, geography and zoning data
    tests/       unit tests, UI checks and source fixtures
    docs/        source and engineering notes
    vendor/      Sun Valley theme with original licence
    run.py       local desktop entry point
    hosted.py    managed browser entry point
  nesting/       existing HTML nesting tool
web/portal/      home page, connection service and downloads
tests/browser/  real browser connection and recovery tests
scripts/        startup and verification utilities
docs/           workflow and Codespaces documentation
.devcontainer/  testing environment configuration
.github/        automated checks
```

[Transport guide](apps/transport/README.md) · [Destination, sources and export](docs/DESTINATION_WORKFLOW.md) · [Codespaces guide](docs/CODESPACES.md) · [Automated checks](https://github.com/moontolito/FlowerMoon/actions/workflows/transport-tests.yml)
