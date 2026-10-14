"""Build one portable PDF package from selected annotated workspace documents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pymupdf

from .annotations import HighlightStore
from .bookmarks import BookmarkStore
from .evidence import EvidenceStore
from .pdf_export import PdfExportResult, export_annotated_pdf
from .workspace_analysis import WorkspaceSummary
from .workspace_report import export_workspace_report


class ConsolidatedExportError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ConsolidatedExportResult:
    path: str
    document_count: int
    source_page_count: int
    report_page_count: int
    total_page_count: int
    highlight_count: int
    note_count: int


@dataclass(frozen=True, slots=True)
class ManagementAnalysisReportResult:
    path: str
    document_count: int
    source_page_count: int
    report_page_count: int
    note_count: int


def export_management_analysis_report(
    summary: WorkspaceSummary,
    destination_value: str | Path,
    evidence_storage_dir: str | Path,
    selected_tags: tuple[str, ...] | None = None,
) -> ManagementAnalysisReportResult:
    """Export overview and complete finding pages without appending source PDFs."""
    if not summary.documents:
        raise ConsolidatedExportError("Select at least one workspace document.")
    destination = Path(destination_value).resolve()
    if destination.suffix.casefold() != ".pdf":
        raise ConsolidatedExportError("The management report must use the .pdf extension.")
    sources = tuple(Path(item.path).resolve() for item in summary.documents)
    if destination in sources:
        raise ConsolidatedExportError("The management report cannot overwrite a source PDF.")
    for item, source in zip(summary.documents, sources):
        if not item.available or not source.is_file():
            raise ConsolidatedExportError(
                f'The selected document "{item.name}" is missing or invalid.'
            )

    destination.parent.mkdir(parents=True, exist_ok=True)
    token = uuid4().hex
    overview_path = destination.with_name(f".{destination.name}.{token}.overview.tmp.pdf")
    section_paths = tuple(
        destination.with_name(f".{destination.name}.{token}.findings-{index}.tmp.pdf")
        for index in range(len(summary.documents))
    )
    final_path = destination.with_name(f".{destination.name}.{token}.final.tmp.pdf")
    evidence_store = EvidenceStore(evidence_storage_dir)
    assembled = None
    section_results: list[PdfExportResult] = []
    try:
        overview_result = export_workspace_report(summary, overview_path)
        for item, section_path in zip(summary.documents, section_paths):
            result = export_annotated_pdf(
                item.path,
                section_path,
                (),
                evidence_store.load(item.document_id),
                selected_tags,
            )
            section_results.append(result)

        assembled = pymupdf.open(str(overview_path))
        toc: list[list] = [[1, "Workspace Overview", 1]]
        page_offset = assembled.page_count
        for number, (item, section_path, result) in enumerate(
            zip(summary.documents, section_paths, section_results),
            start=1,
        ):
            section = pymupdf.open(str(section_path))
            try:
                toc.append([1, f"{number}. {item.name}", page_offset + 1])
                for level, title, page_number, *rest in section.get_toc(simple=True):
                    if 0 < page_number <= result.index_page_count:
                        toc.append(
                            [
                                min(4, int(level) + 1),
                                str(title),
                                page_offset + int(page_number),
                            ]
                        )
                assembled.insert_pdf(
                    section,
                    from_page=0,
                    to_page=result.index_page_count - 1,
                    links=False,
                    annots=True,
                    widgets=True,
                )
                page_offset += result.index_page_count
            finally:
                section.close()
        assembled.set_toc(toc)
        metadata = dict(assembled.metadata or {})
        metadata["title"] = f"{summary.project_name} - Management Analysis Report"
        metadata["subject"] = "Dashboard, Categories and Standards findings"
        metadata["producer"] = "PDF Analyzer"
        assembled.set_metadata(metadata)
        assembled.save(str(final_path), garbage=3, deflate=True)
        assembled.close()
        assembled = None

        verification = pymupdf.open(str(final_path))
        try:
            expected_pages = overview_result.report_page_count + sum(
                result.index_page_count for result in section_results
            )
            if verification.page_count != expected_pages or not verification.get_toc():
                raise ConsolidatedExportError(
                    "The management analysis report could not be verified."
                )
        finally:
            verification.close()
        final_path.replace(destination)
        return ManagementAnalysisReportResult(
            path=str(destination),
            document_count=len(summary.documents),
            source_page_count=sum(item.page_count for item in summary.documents),
            report_page_count=expected_pages,
            note_count=sum(result.evidence_count for result in section_results),
        )
    except ConsolidatedExportError:
        raise
    except Exception as error:
        raise ConsolidatedExportError(
            "The management analysis report could not be exported."
        ) from error
    finally:
        if assembled is not None:
            assembled.close()
        for path in (overview_path, *section_paths, final_path):
            path.unlink(missing_ok=True)


def export_consolidated_package(
    summary: WorkspaceSummary,
    destination_value: str | Path,
    evidence_storage_dir: str | Path,
    highlight_storage_dir: str | Path,
    bookmark_storage_dir: str | Path,
    selected_tags: tuple[str, ...] | None = None,
) -> ConsolidatedExportResult:
    if not summary.documents:
        raise ConsolidatedExportError("Select at least one workspace document.")
    destination = Path(destination_value).resolve()
    if destination.suffix.casefold() != ".pdf":
        raise ConsolidatedExportError("The consolidated package must use the .pdf extension.")
    sources = tuple(Path(item.path).resolve() for item in summary.documents)
    if destination in sources:
        raise ConsolidatedExportError(
            "The consolidated package cannot overwrite a source PDF."
        )
    for item, source in zip(summary.documents, sources):
        if not item.available or not source.is_file():
            raise ConsolidatedExportError(
                f'The selected document "{item.name}" is missing or invalid.'
            )

    destination.parent.mkdir(parents=True, exist_ok=True)
    token = uuid4().hex
    overview_path = destination.with_name(f".{destination.name}.{token}.overview.tmp.pdf")
    section_paths = tuple(
        destination.with_name(f".{destination.name}.{token}.section-{index}.tmp.pdf")
        for index in range(len(summary.documents))
    )
    final_path = destination.with_name(f".{destination.name}.{token}.final.tmp.pdf")
    evidence_store = EvidenceStore(evidence_storage_dir)
    highlight_store = HighlightStore(highlight_storage_dir)
    bookmark_store = BookmarkStore(bookmark_storage_dir)
    assembled = None
    total_highlights = 0
    total_notes = 0
    report_pages = 0
    source_pages = sum(item.page_count for item in summary.documents)
    section_results: list[PdfExportResult] = []
    try:
        overview_result = export_workspace_report(summary, overview_path)
        report_pages += overview_result.report_page_count
        for item, section_path in zip(summary.documents, section_paths):
            highlights = highlight_store.load(item.document_id)
            evidence = evidence_store.load(item.document_id)
            bookmarks = bookmark_store.load(item.document_id, item.page_count)
            result = export_annotated_pdf(
                item.path,
                section_path,
                highlights,
                evidence,
                selected_tags,
                bookmarks,
            )
            section_results.append(result)
            total_highlights += result.highlight_count
            total_notes += result.evidence_count
            report_pages += result.index_page_count

        assembled = pymupdf.open(str(overview_path))
        toc: list[list] = [[1, "Workspace Overview", 1]]
        page_offset = assembled.page_count
        for number, (item, section_path, result) in enumerate(
            zip(summary.documents, section_paths, section_results),
            start=1,
        ):
            section = pymupdf.open(str(section_path))
            try:
                toc.append([1, f"{number}. {item.name}", page_offset + 1])
                for level, title, page_number, *rest in section.get_toc(simple=True):
                    if page_number > 0:
                        toc.append(
                            [
                                min(4, int(level) + 1),
                                str(title),
                                page_offset + int(page_number),
                            ]
                        )
                assembled.insert_pdf(
                    section,
                    links=True,
                    annots=True,
                    widgets=True,
                )
                page_offset += section.page_count
            finally:
                section.close()
        assembled.set_toc(toc)
        metadata = dict(assembled.metadata or {})
        metadata["title"] = f"{summary.project_name} - Consolidated Annotated Package"
        metadata["subject"] = "PDF Analyzer multi-document annotated export"
        metadata["producer"] = "PDF Analyzer"
        assembled.set_metadata(metadata)
        assembled.save(str(final_path), garbage=3, deflate=True)
        assembled.close()
        assembled = None

        verification = pymupdf.open(str(final_path))
        try:
            expected_pages = overview_result.report_page_count + sum(
                result.total_page_count for result in section_results
            )
            if verification.page_count != expected_pages:
                raise ConsolidatedExportError(
                    "The consolidated package could not be verified."
                )
            if not verification.get_toc():
                raise ConsolidatedExportError(
                    "The consolidated package has no navigation bookmarks."
                )
        finally:
            verification.close()
        final_path.replace(destination)
        return ConsolidatedExportResult(
            path=str(destination),
            document_count=len(summary.documents),
            source_page_count=source_pages,
            report_page_count=report_pages,
            total_page_count=expected_pages,
            highlight_count=total_highlights,
            note_count=total_notes,
        )
    except ConsolidatedExportError:
        raise
    except Exception as error:
        raise ConsolidatedExportError(
            "The consolidated annotated package could not be exported."
        ) from error
    finally:
        if assembled is not None:
            assembled.close()
        for path in (overview_path, *section_paths, final_path):
            path.unlink(missing_ok=True)
