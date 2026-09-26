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

**Existing Codespace:** pull the latest `main` using Source Control, then stop and restart the Codespace to load the updated application. If it predates the browser portal, use **Codespaces: Rebuild Container** once after pulling. A new Codespace uses the current configuration immediately. Preserve any unsaved work before restarting the app or rebuilding.

After exporting in Transport, select **Download Excel** in the browser toolbar. Projects and exports stay in `apps/transport/data/`, inside your session, and are excluded from Git.

The repository and application port remain private. Each tester needs repository access and their own Codespace. Codespaces uses the GitHub account quota; stop the session after testing.

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
