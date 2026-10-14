# Milestone 3O - Safe Excel Text Export

## Goal

Prevent Excel from interpreting imported PDF text, document names, comments or
tags as formulas.

## Included

- All content originating outside the application is exported as literal text.
- Text beginning with `=` remains visible and editable in Excel.
- Automatic URL conversion is disabled for imported text.
- Application-owned formulas and PDF hyperlinks remain active because they are
  written explicitly.
- A regression test covers formula-like text in the Notes sheet.

## Not changed

- Workbook layout and worksheet order.
- Summary and tag formulas.
- PDF hyperlinks.
- Reading-status data validation.

## Acceptance

- Excel opens the generated workbook without a repair warning.
- The Notes sheet contains no formulas derived from PDF or user content.
- Summary and Tags formulas continue to calculate normally.
