# FlowerCutter 1.0.0

FlowerMoonCraft browser app for rectangular sheet cutting and layout planning, based on the existing nesting alpha v63 engine. Original credits: Danila Teodora and Cuvuliuc Nicolae, helped by ChatGPT.

## Start

Open `index.html` in Chrome or Edge. Keep `flowermoon.css`, `flowermoon-ui.js`, and `vendor/` alongside it. No installation or build step is needed to use the app. All runtime assets are local; the same folder can be served by GitHub Pages under a repository subpath.

1. Add stock sizes and available quantities in millimeters.
2. Add parts, dimensions and quantities. Set blade kerf, edge trims, strategy and batches.
3. Press **Optimise layout**. Oversized or unplaced parts remain in Temp.
4. Use the right-click menu or drag parts to adjust layouts. Undo/Redo and Lock are available.
5. **Export Config** saves the current inputs and all imported works. **Import Config** restores inputs. With no inputs, Export Config provides a blank template.
6. **Export Excel** exports the current work summary and placements. **Export PDF** can export one work or all imported works.

Input quantities and batches are whole numbers. Zero quantity is allowed for unused rows. Dimensions must be positive; kerf and active trim must be nonnegative. Changed inputs must be recalculated before result export. Reports identify parts remaining in Temp as incomplete.

## Storage and compatibility

Data is held in the browser tab. There is no backend, login, analytics or automatic server upload. Export inputs before closing/reloading the tab. Config files preserve inputs/settings, not manual layout coordinates, locks or Undo history. PDF/Excel reports preserve the calculated output for review.

The original compact `nesting_config.xlsx` template remains supported. Config exports now use the name `flowercutter_config.xlsx`. Runtime file names `flowermoon.css` and `flowermoon-ui.js` remain stable. The hidden legacy linear-cutting panel is not part of this release's supported/tested UI.

This standalone tool retains its existing spreadsheet contracts. It does not claim implementation of the FlowerMoon quotation system's future Master Output schema. The nesting strategies are heuristics; a result is not a proof of global optimality. Cutting length is the existing part-edge segment estimate, not a validated machine toolpath.

## Changes in this release

- FlowerCutter branding in the interface and generated reports; original author credits preserved.
- Bundled PDF and styled Excel libraries remove runtime CDN requests.
- Export Config now saves current inputs, including multiple works.
- Rejects invalid dimensions, negative kerf/trim and fractional quantities/batches.
- Prevents stale result export, including after switching works.
- Keeps work settings separate and preserves imported zero quantities.
- Accounts for locked sheets in remaining stock and distinguishes layout groups by stock and part identity.
- Fixes cross-sheet transfer bounds and shows newly split repeated layouts.
- Treats part labels as text, improves narrow-screen controls and PDF pagination.
- Marks incomplete PDF/Excel reports when parts remain in Temp.

## Dependencies

- jsPDF 2.5.1: `vendor/jspdf.umd.min.js` (MIT).
- xlsx-js-style 1.2.0: `vendor/xlsx.bundle.js` (Apache-2.0, including its notices).
- Source URLs and SHA-256 hashes: `vendor/manifest.json`. License files are included.

Versions were preserved from the existing app. The separate plain XLSX script was redundant because xlsx-js-style supplies the XLSX API.

## Verification ? 2026-10-03

`verification/verify_flowercutter.py` runs 36 browser checks using synthetic data in an isolated headless Chrome profile. It covers all three strategies and 24 seeded geometric scenarios; independent bounds, kerf separation, overlaps and quantity reconciliation; stock shortage, oversized parts and exact sheet fit; lock/stock accounting; Temp, Undo/Redo, context transfer and cross-layout mouse drag; config round-trip and original-template compatibility; multi-work settings and batches; actual downloaded Excel/PDF content; invalid-input and stale-export handling; repeated layouts; label escaping; and layouts at 1366, 1920, 768 and 390 pixels wide.

All 36 checks passed with zero uncaught JavaScript errors and no external network requests. The complete suite also passed against the clean publication package served over HTTP under `/FlowerCutter-GitHub-Pages/`, matching a GitHub Pages repository subpath. Screenshots were inspected at desktop and mobile widths. Sample PDFs were rendered for visual inspection. Evidence: `verification/flowercutter/results.json`, screenshots and synthetic exported files. Test tooling and evidence are excluded from the publication package.

Limits: no new-user usability session; no real cutting-machine validation; no exhaustive audit of every legacy spreadsheet variant or browser. GitHub Pages live verification is pending the repository destination and deployment.

## Files and backup

- `index.html`: application UI, packing logic and import/export.
- `flowermoon.css`: styling and responsive layouts.
- `flowermoon-ui.js`: keyboard/accessibility helpers.
- `vendor/`: local runtime dependencies and licenses.
- `PUBLISH_GITHUB_PAGES.md`: publication steps in Romanian.
- `backups/before-flowercutter-20261003/`: pre-change source preserved locally.
- `verification/build_pages.py`: builds the clean `FlowerCutter-GitHub-Pages` folder and ZIP in the parent folder.

## GitHub Pages

Deployment repository: `moontolito/FlowerMoon`, branch `gh-pages`, source `/(root)`.
This branch contains only FlowerCutter static files. The other applications remain on their existing branches.

Expected URL after Pages activation: https://moontolito.github.io/FlowerMoon/

Pages activation and live verification are pending. The available account has push permission but does not have repository administration permission. The repository owner must enable Pages in Settings if API activation is denied. A private repository requires a GitHub plan that supports private-repository Pages.

See [activation steps](PUBLISH_GITHUB_PAGES.md).
