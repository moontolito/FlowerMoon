#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
/opt/flowermoon-venv/bin/python -c 'import tkinter, aiohttp; from PIL import Image; print("FlowerMoon dependencies ready")'
printf 'Configurare terminata. Pagina FlowerMoon se deschide pe portul 8000.\n'
