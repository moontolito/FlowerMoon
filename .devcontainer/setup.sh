#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
python -c 'import tkinter; from PIL import Image; print("Tkinter and Pillow ready")'
mkdir -p "$HOME/Desktop"
cat > "$HOME/Desktop/FlowerMoon.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=FlowerMoon Transport
Exec=bash "$repo_root/.devcontainer/start.sh"
Icon=$repo_root/apps/transport/FlowerMoonLogo.png
Terminal=false
EOF
chmod +x "$HOME/Desktop/FlowerMoon.desktop"
printf '\nFlowerMoon is ready. Open port 6080 in your browser and click Connect.\n'
printf 'Desktop password: vscode. Keep the forwarded port PRIVATE.\n'

