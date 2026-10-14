# Milestone 3M - Automatic Analysis Notes

## Goal

Persist every deterministic Categories and Standards result as a tagged note so
quotation engineers start with the complete finding set and remove only what is
not relevant.

## Included

- automatic note creation after Categories analysis;
- automatic note creation after Standards analysis;
- source paragraph, exact page and PDF coordinates;
- category name as the Categories tag;
- classification and detected reference as Standards tags;
- explanatory automatic comments;
- citation order based on document position;
- one atomic save for the complete analysis result;
- deterministic duplicate prevention on repeated analysis;
- visible counts for added and already-present notes;
- existing custom-note workflow and individual removal.

## Rules

- no result is silently omitted when it has valid text and coordinates;
- invalid batches do not partially modify stored notes;
- deleting a note is persistent until the corresponding analysis is run again;
- rerunning analysis recreates a deleted result but does not duplicate existing
  results;
- noise filters and visual masks are applied before automatic notes are created;
- source PDFs are never modified.

## Excluded

- semantic or AI-generated summaries;
- automatic note creation for free-form Search;
- automatic deletion when profiles, filters or masks change;
- synchronization of exported PDF or Excel edits back into the application.
