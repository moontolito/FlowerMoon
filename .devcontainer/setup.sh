#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
/opt/flowermoon-venv/bin/python -c 'import tkinter, aiohttp, cdsapi, netCDF4, eccodes; from PIL import Image; print("FlowerMoon dependencies ready")'
/opt/flowermoon-venv/bin/python scripts/prepare_transport_assets.py
printf 'Setup complete. The FlowerMoon page opens on port 8000.\n'
