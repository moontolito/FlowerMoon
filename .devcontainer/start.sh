#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$repo_root/.runtime"
if ! curl --silent --fail http://127.0.0.1:8000/api/status > /dev/null; then
  nohup setsid /opt/flowermoon-venv/bin/python -u "$repo_root/scripts/launch_portal.py" \
    >> "$repo_root/.runtime/portal.log" 2>&1 < /dev/null &
fi
for attempt in {1..30}; do
  if curl --silent --fail http://127.0.0.1:8000/api/status > /dev/null; then
    printf 'FlowerMoon is ready. Open port 8000 in your browser.\n'
    if [[ -n "${CODESPACE_NAME:-}" ]]; then
      printf 'https://%s-8000.%s\n' "$CODESPACE_NAME" "${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
    fi
    exit 0
  fi
  sleep 1
done
printf 'FlowerMoon did not start. Details: .runtime/portal.log\n' >&2
exit 1
