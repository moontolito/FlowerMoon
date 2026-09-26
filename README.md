# FlowerMoon

Private workspace for FlowerMoon applications.

- **Transport:** [source and testing guide](apps/transport/README.md), including Site & Environment, historical climate, humidity and elevation.
- **Nesting:** the existing `Nesting_Tool_alpha_v63.html` tool remains at the repository root.

## Test Transport in your browser

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/moontolito/FlowerMoon?quickstart=1)

1. Open the button and create a Codespace. You need access to this private repository.
2. Wait for the container setup. FlowerMoon starts automatically.
3. In **Ports**, open **6080 — FlowerMoon desktop** in your browser.
4. Click **Connect**. Desktop password: `vscode`.

The existing desktop interface runs inside the browser through noVNC. Keep port 6080 **private**. Each tester should create their own Codespace; a private port URL is not a public testing link. Do not expose the desktop publicly: it also provides access to the container and its repository credentials.

Codespaces usage is subject to the account's quota and billing settings. Stop the Codespace when finished. This setup does not enable paid plans or alter spending limits.

Saved projects, caches, exports and logs stay inside that Codespace and are excluded from Git. To download an exported workbook, save it under `apps/transport/data/exports`, then use **Download** from the VS Code Explorer. Microsoft Excel is not installed in the container; export remains available.

If the app was closed, run `bash .devcontainer/start.sh` in the terminal. Logs: `apps/transport/data/codespaces.log`.

See [GitHub's Codespaces creation guide](https://docs.github.com/en/codespaces/developing-in-a-codespace/creating-a-codespace-for-a-repository) and [desktop-lite documentation](https://github.com/devcontainers/features/tree/main/src/desktop-lite).

