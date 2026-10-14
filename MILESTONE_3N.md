# Milestone 3N - Complete Editable PDF Overview

## Goal

Show complete document names and complete tag information in the workspace PDF
overview while preserving editable reading-status fields and a clear
professional layout.

## Included

- full document names without ellipsis;
- complete global tag list;
- complete per-document tag lists;
- measured word wrapping with safe splitting for long technical filenames;
- dynamic row heights;
- automatic pagination;
- separate document index column;
- page and note counts;
- visibly editable Reading Status fields;
- alternating row backgrounds and a restrained blue accent;
- identical overview behavior inside consolidated annotated packages.

## Validation Rules

- every document receives exactly one editable Reading Status field;
- names and tags are never discarded to fit a fixed row;
- rows never overlap or cross the printable page boundary;
- excessively large single-document content fails safely instead of producing a
  clipped report;
- source PDFs are never overwritten or modified.

## Excluded

- changes to the individual annotated-PDF report pages;
- synchronization of edited PDF fields back into the project;
- new report formats;
- changes to search, OCR or analysis scoring.
