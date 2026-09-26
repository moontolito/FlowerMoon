# FlowerMoon application template

## Shared design rules

Read `DESIGN_RULES.md` before designing, changing, or auditing an interface in this template or an application copied from it. It contains the user's shared product design requirements. Apply them to the scope of the current request; saving documentation alone does not require building an interface or performing a design audit.

## Current platform and assets

- The current template targets Python with Tkinter/ttk. Use Sun Valley (`sv_ttk`) as the base theme.
- Official source: https://github.com/rdbende/Sun-Valley-ttk-theme
- Local theme source: `vendor/sun-valley/`.
- Supplied logo: `assets/FlowerMoonLogo.png`. Do not redesign or replace it without an explicit request.
- Interpret web-oriented terminology and CSS examples in `DESIGN_RULES.md` as design concepts. Implement their equivalents using centralized Python tokens, ttk styles, and reusable Tkinter components; do not change frameworks merely to follow the examples.
- Keep the shared design layer separate from application-specific behavior. Build components as the requested scope requires.

## Audit and verification

- Audit an existing interface before changing it, and preserve its features and behavior unless changes are requested.
- For an audit-only request, report findings and proposed fixes without editing the application.
- Check appearance and actual interactions. Screenshots alone do not establish that buttons, forms, exports, or other workflows work.
- For each finding, identify the affected screen or control, severity, evidence, reproduction steps when applicable, and a proposed correction.
- Clearly separate verified results from untested behavior. State any unavailable runtime or UI-control capability and do not claim a visual or functional check passed without evidence.
- These files provide project instructions; they do not create a running bot or scheduled audit.
