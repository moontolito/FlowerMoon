# FlowerMoon Tools (GitHub Pages)

Static browser tools published from this `gh-pages` branch at
https://moontolito.github.io/FlowerMoon/

```text
index.html        tool selector (home page)
tools.js          list of tools shown on the home page
logo.png          FlowerMoon logo
flowercutter/     FlowerCutter 1.0.0 — sheet cutting and layout planning
painting/         Painting calculator v18 — paint quantities and cost
                  Transport is linked from tools.js; it runs on Render (main branch)
```

## Add a tool

1. Create a folder with the tool's `index.html` and any files it needs, using
   relative paths (for example `mytool/index.html`).
2. Add one entry to `tools.js` (`id`, `name`, `path`, `icon`, `category`,
   `language`, `version`, `description`). Available icons: `cutter`, `paint`,
   `generic`.
3. Commit to `gh-pages`. GitHub Pages republishes in about a minute.

Every tool runs entirely in the browser; there is no server or login. This site
is public: do not publish tools that contain confidential prices or customer data.
