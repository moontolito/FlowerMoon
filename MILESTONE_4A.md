# Milestone 4A - Workspace Batch Analysis and Management Report

## Goal

Analyze every selected workspace PDF in one controlled operation and create a
review-ready PDF containing the complete dashboard and every Categories and
Standards finding.

## Included

- `Analyze Selected` in the multi-document Dashboard.
- Categories and Standards run for every checked PDF.
- Native text and previously cached OCR are reused; OCR is never started
  silently.
- Active noise filters, category profile and document masks are respected.
- Every deterministic finding is saved as a tagged note.
- Re-running the batch does not duplicate existing notes.
- Per-document failures do not stop the remaining documents.
- Pages that still require OCR are reported after the batch.
- New `Management report` export mode:
  - complete dashboard overview;
  - full document names and complete tag lists;
  - all Categories, Standards and personal findings;
  - dynamically expanding finding blocks;
  - continuation pages for long text;
  - editable `Delegated to` department selector;
  - editable manager comment field;
  - PDF bookmarks for documents and tag groups;
  - source PDF pages are not appended.

## Existing exports preserved

- `Overview only`
- `Full annotated package`
- editable Excel report
- single-document annotated PDF

## Deliberate limits

- Batch analysis does not run OCR automatically. A page without native or
  cached OCR text is reported for manual OCR.
- Manager edits in an exported PDF do not synchronize back into PDF Analyzer.
- Analysis remains local and deterministic; no cloud or AI service is used.

## Acceptance

- One action analyzes all checked documents.
- A rerun creates zero duplicate notes.
- Long document names, tags, comments and excerpts are not replaced by
  ellipses.
- The management report contains no source document pages.
- Delegation and manager comment fields remain editable.
