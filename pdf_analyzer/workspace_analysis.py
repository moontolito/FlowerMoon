"""Read-only aggregation of a multi-PDF quotation workspace."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from .engine import PdfSession
from .evidence import EvidenceStore
from .project_state import READING_STATUSES, normalize_path


@dataclass(frozen=True, slots=True)
class WorkspaceDocumentSummary:
    path: str
    name: str
    document_id: str
    page_count: int
    reading_status: str
    note_count: int
    tags: tuple[str, ...]
    available: bool = True
    error: str = ""


@dataclass(frozen=True, slots=True)
class WorkspaceSummary:
    project_name: str
    documents: tuple[WorkspaceDocumentSummary, ...]
    total_pages: int
    total_notes: int
    status_counts: tuple[tuple[str, int], ...]
    tag_counts: tuple[tuple[str, int], ...]


def _build_summary(
    project_name: str,
    documents: tuple[WorkspaceDocumentSummary, ...],
) -> WorkspaceSummary:
    status_counts = tuple(
        (status, sum(item.reading_status == status for item in documents))
        for status in READING_STATUSES
        if any(item.reading_status == status for item in documents)
    )
    tag_totals: dict[str, tuple[str, int]] = {}
    for item in documents:
        for tag in item.tags:
            identity = tag.casefold()
            display, count = tag_totals.get(identity, (tag, 0))
            tag_totals[identity] = (display, count + 1)
    tag_counts = tuple(
        sorted(tag_totals.values(), key=lambda value: (-value[1], value[0].casefold()))
    )
    return WorkspaceSummary(
        project_name=project_name.strip() or "Untitled Project",
        documents=documents,
        total_pages=sum(item.page_count for item in documents),
        total_notes=sum(item.note_count for item in documents),
        status_counts=status_counts,
        tag_counts=tag_counts,
    )


def analyze_workspace(
    paths: tuple[str, ...],
    reading_statuses: dict[str, str],
    evidence_storage_dir: str | Path,
    project_name: str,
) -> WorkspaceSummary:
    evidence_store = EvidenceStore(evidence_storage_dir)
    results: list[WorkspaceDocumentSummary] = []
    for path_value in paths:
        path = Path(path_value).resolve()
        status = reading_statuses.get(normalize_path(path), "Not Read")
        if status not in READING_STATUSES:
            status = "Not Read"
        session = PdfSession()
        try:
            info, _ = session.open(path)
            notes = evidence_store.load(info.document_id)
            tags = tuple(
                sorted(
                    {tag for note in notes for tag in note.tags},
                    key=str.casefold,
                )
            )
            results.append(
                WorkspaceDocumentSummary(
                    path=str(path),
                    name=info.name,
                    document_id=info.document_id,
                    page_count=info.page_count,
                    reading_status=status,
                    note_count=len(notes),
                    tags=tags,
                )
            )
        except (OSError, ValueError, RuntimeError) as error:
            results.append(
                WorkspaceDocumentSummary(
                    path=str(path),
                    name=path.name,
                    document_id="",
                    page_count=0,
                    reading_status=status,
                    note_count=0,
                    tags=(),
                    available=False,
                    error=str(error),
                )
            )
        finally:
            session.close()
    return _build_summary(project_name, tuple(results))


def update_workspace_status(
    summary: WorkspaceSummary,
    path_value: str,
    reading_status: str,
) -> WorkspaceSummary:
    if reading_status not in READING_STATUSES:
        raise ValueError("Invalid reading status.")
    identity = normalize_path(path_value)
    documents = tuple(
        replace(item, reading_status=reading_status)
        if normalize_path(item.path) == identity
        else item
        for item in summary.documents
    )
    return _build_summary(summary.project_name, documents)


def select_workspace_documents(
    summary: WorkspaceSummary,
    selected_paths: tuple[str, ...],
) -> WorkspaceSummary:
    identities = {normalize_path(path) for path in selected_paths}
    documents = tuple(
        item for item in summary.documents if normalize_path(item.path) in identities
    )
    if not documents:
        raise ValueError("Select at least one workspace document.")
    return _build_summary(summary.project_name, documents)
