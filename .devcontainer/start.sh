#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$repo_root/apps/transport/data"
nohup python -u "$repo_root/scripts/run_transport.py" \
  >> "$repo_root/apps/transport/data/codespaces.log" 2>&1 < /dev/null &
printf 'FlowerMoon starting. Open the FlowerMoon desktop on port 6080.\n'

