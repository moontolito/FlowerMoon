"""Export a consolidated, editable PDF overview for a multi-document workspace."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pymupdf

from .project_state import READING_STATUSES
from .workspace_analysis import WorkspaceSummary


REPORT_WIDTH = 595
REPORT_HEIGHT = 842
REPORT_MARGIN = 42
OTHER_PAGE_START = 112
REPORT_BOTTOM = 798
ROW_GAP = 8


class WorkspaceReportError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class WorkspaceReportResult:
    path: str
    document_count: int
    page_count: int
    note_count: int
    report_page_count: int


@dataclass(frozen=True, slots=True)
class _DocumentRow:
    title_lines: tuple[str, ...]
    details: str
    tag_lines: tuple[str, ...]
    height: float


@dataclass(frozen=True, slots=True)
class _SummaryLayout:
    status_lines: tuple[str, ...]
    tag_lines: tuple[str, ...]
    status_top: float
    tags_top: float
    rows_start: float


def _font_file() -> Path | None:
    fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    return next(
        (
            candidate
            for candidate in (fonts / "segoeui.ttf", fonts / "arial.ttf")
            if candidate.is_file()
        ),
        None,
    )


def _shorten(value: str, limit: int) -> str:
    clean = " ".join(value.split())
    return clean if len(clean) <= limit else clean[: limit - 3].rstrip() + "..."


def _report_font() -> pymupdf.Font:
    font_file = _font_file()
    return (
        pymupdf.Font(fontfile=str(font_file))
        if font_file
        else pymupdf.Font("helv")
    )


def _wrap_text(
    value: str,
    max_width: float,
    font: pymupdf.Font,
    size: float,
) -> tuple[str, ...]:
    clean = " ".join(value.split())
    if not clean:
        return ("",)
    lines: list[str] = []
    current = ""
    for word in clean.split(" "):
        candidate = word if not current else f"{current} {word}"
        if font.text_length(candidate, fontsize=size) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        remainder = word
        while remainder and font.text_length(remainder, fontsize=size) > max_width:
            split_at = 1
            for index in range(2, len(remainder) + 1):
                if font.text_length(remainder[:index], fontsize=size) > max_width:
                    split_at = index - 1
                    break
                split_at = index
            preferred = max(
                (
                    index + 1
                    for index, character in enumerate(remainder[:split_at])
                    if character in "_-/."
                ),
                default=0,
            )
            if preferred >= max(4, split_at // 2):
                split_at = preferred
            lines.append(remainder[:split_at])
            remainder = remainder[split_at:]
        current = remainder
    if current:
        lines.append(current)
    return tuple(lines) or ("",)


def _text_height(lines: tuple[str, ...], size: float) -> float:
    return max(1, len(lines)) * size * 1.15


def _document_row(
    item,
    font: pymupdf.Font,
) -> _DocumentRow:
    availability = "" if item.available else " [MISSING / INVALID]"
    title_lines = _wrap_text(
        f"{item.name}{availability}",
        332,
        font,
        8.7,
    )
    details = f"Pages: {item.page_count}   |   Notes: {item.note_count}"
    tags = ", ".join(item.tags) or "No tags"
    tag_lines = _wrap_text(f"Tags: {tags}", REPORT_WIDTH - 2 * REPORT_MARGIN - 20, font, 7.5)
    title_height = _text_height(title_lines, 8.7)
    metadata_bottom = 14 + title_height + 10
    tags_top = max(50, metadata_bottom + 5)
    height = tags_top + _text_height(tag_lines, 7.5) + 9
    return _DocumentRow(title_lines, details, tag_lines, height)


def _summary_layout(summary: WorkspaceSummary, font: pymupdf.Font) -> _SummaryLayout:
    statuses = "   |   ".join(
        f"{status}: {count}" for status, count in summary.status_counts
    ) or "No reading statuses"
    status_lines = _wrap_text(
        f"Reading status: {statuses}",
        REPORT_WIDTH - 2 * REPORT_MARGIN,
        font,
        8.3,
    )
    tags = ", ".join(f"{tag} ({count})" for tag, count in summary.tag_counts) or "No tags"
    tag_lines = _wrap_text(
        f"Tags: {tags}",
        REPORT_WIDTH - 2 * REPORT_MARGIN,
        font,
        8.3,
    )
    status_top = 142
    tags_top = status_top + _text_height(status_lines, 8.3) + 9
    rows_start = tags_top + _text_height(tag_lines, 8.3) + 18
    return _SummaryLayout(
        status_lines,
        tag_lines,
        status_top,
        tags_top,
        rows_start,
    )


def _paginate_rows(
    rows: tuple[_DocumentRow, ...],
    first_start: float,
) -> tuple[tuple[tuple[int, _DocumentRow, float], ...], ...]:
    pages: list[list[tuple[int, _DocumentRow, float]]] = [[]]
    y = first_start
    for index, row in enumerate(rows):
        if y + row.height > REPORT_BOTTOM:
            pages.append([])
            y = OTHER_PAGE_START
        if y + row.height > REPORT_BOTTOM:
            raise WorkspaceReportError(
                "A document contains too much tag text to fit on one report page."
            )
        pages[-1].append((index, row, y))
        y += row.height + ROW_GAP
    return tuple(tuple(page) for page in pages)


def _insert_text(page, rect, text: str, size: float, font_name: str, color=(0.12, 0.16, 0.2)):
    result = page.insert_textbox(
        rect,
        text,
        fontname=font_name,
        fontsize=size,
        color=color,
        lineheight=1.15,
    )
    if result < 0:
        raise WorkspaceReportError("The workspace report text does not fit its layout.")


def _new_page(document, index: int, page_count: int, summary: WorkspaceSummary):
    page = document.new_page(width=REPORT_WIDTH, height=REPORT_HEIGHT)
    font_name = "helv"
    font_file = _font_file()
    if font_file:
        page.insert_font(fontname="SegoeUI", fontfile=str(font_file))
        font_name = "SegoeUI"
    _insert_text(
        page,
        pymupdf.Rect(REPORT_MARGIN, 35, REPORT_WIDTH - REPORT_MARGIN, 62),
        "PDF ANALYZER - WORKSPACE OVERVIEW",
        15,
        font_name,
        (0.08, 0.35, 0.58),
    )
    _insert_text(
        page,
        pymupdf.Rect(REPORT_MARGIN, 67, REPORT_WIDTH - REPORT_MARGIN, 92),
        f"{_shorten(summary.project_name, 70)}   |   Report page {index + 1} of {page_count}",
        9,
        font_name,
        (0.35, 0.4, 0.45),
    )
    page.draw_line(
        pymupdf.Point(REPORT_MARGIN, 98),
        pymupdf.Point(REPORT_WIDTH - REPORT_MARGIN, 98),
        color=(0.75, 0.79, 0.83),
        width=0.8,
    )
    return page, font_name


def export_workspace_report(
    summary: WorkspaceSummary,
    destination_value: str | Path,
) -> WorkspaceReportResult:
    if not summary.documents:
        raise WorkspaceReportError("The workspace contains no PDF documents.")
    destination = Path(destination_value).resolve()
    if destination.suffix.casefold() != ".pdf":
        raise WorkspaceReportError("The workspace report must use the .pdf extension.")
    if any(
        destination == Path(item.path).resolve()
        for item in summary.documents
    ):
        raise WorkspaceReportError(
            "The workspace overview cannot overwrite a source PDF."
        )
    report_font = _report_font()
    summary_layout = _summary_layout(summary, report_font)
    rows = tuple(
        _document_row(item, report_font)
        for item in summary.documents
    )
    page_rows = _paginate_rows(rows, summary_layout.rows_start)
    report_pages = len(page_rows)
    temporary = destination.with_name(
        f".{destination.name}.{uuid4().hex}.pdf-analyzer.tmp"
    )
    document = pymupdf.open()
    try:
        for report_index in range(report_pages):
            page, font_name = _new_page(document, report_index, report_pages, summary)
            if report_index == 0:
                _insert_text(
                    page,
                    pymupdf.Rect(REPORT_MARGIN, 112, REPORT_WIDTH - REPORT_MARGIN, 137),
                    (
                        f"Documents: {len(summary.documents)}    "
                        f"Pages: {summary.total_pages}    Notes: {summary.total_notes}"
                    ),
                    11,
                    font_name,
                )
                _insert_text(
                    page,
                    pymupdf.Rect(
                        REPORT_MARGIN,
                        summary_layout.status_top,
                        REPORT_WIDTH - REPORT_MARGIN,
                        summary_layout.tags_top - 4,
                    ),
                    "\n".join(summary_layout.status_lines),
                    8.3,
                    font_name,
                    (0.35, 0.4, 0.45),
                )
                _insert_text(
                    page,
                    pymupdf.Rect(
                        REPORT_MARGIN,
                        summary_layout.tags_top,
                        REPORT_WIDTH - REPORT_MARGIN,
                        summary_layout.rows_start - 8,
                    ),
                    "\n".join(summary_layout.tag_lines),
                    8.3,
                    font_name,
                    (0.35, 0.4, 0.45),
                )

            for document_index, row_layout, y in page_rows[report_index]:
                item = summary.documents[document_index]
                row = pymupdf.Rect(
                    REPORT_MARGIN,
                    y,
                    REPORT_WIDTH - REPORT_MARGIN,
                    y + row_layout.height,
                )
                page.draw_rect(
                    row,
                    color=(0.79, 0.84, 0.88),
                    fill=(
                        (0.965, 0.977, 0.987)
                        if document_index % 2 == 0
                        else (0.985, 0.989, 0.994)
                    ),
                    width=0.6,
                )
                page.draw_rect(
                    pymupdf.Rect(row.x0, row.y0, row.x0 + 3, row.y1),
                    color=(0.12, 0.43, 0.64),
                    fill=(0.12, 0.43, 0.64),
                    width=0,
                )
                title_height = _text_height(row_layout.title_lines, 8.7)
                _insert_text(
                    page,
                    pymupdf.Rect(
                        row.x0 + 11,
                        row.y0 + 8,
                        row.x0 + 31,
                        row.y0 + 22,
                    ),
                    f"{document_index + 1}.",
                    8.7,
                    font_name,
                )
                _insert_text(
                    page,
                    pymupdf.Rect(
                        row.x0 + 32,
                        row.y0 + 8,
                        410,
                        row.y0 + 14 + title_height,
                    ),
                    "\n".join(row_layout.title_lines),
                    8.7,
                    font_name,
                )
                _insert_text(
                    page,
                    pymupdf.Rect(
                        row.x0 + 11,
                        row.y0 + 15 + title_height,
                        410,
                        row.y0 + 29 + title_height,
                    ),
                    row_layout.details,
                    7.2,
                    font_name,
                    (0.35, 0.4, 0.45),
                )
                tags_top = row.y1 - _text_height(row_layout.tag_lines, 7.5) - 8
                _insert_text(
                    page,
                    pymupdf.Rect(
                        row.x0 + 11,
                        tags_top,
                        row.x1 - 9,
                        row.y1 - 6,
                    ),
                    "\n".join(row_layout.tag_lines),
                    7.5,
                    font_name,
                    (0.25, 0.34, 0.42),
                )
                _insert_text(
                    page,
                    pymupdf.Rect(425, row.y0 + 8, row.x1 - 7, row.y0 + 19),
                    "READING STATUS",
                    6.2,
                    font_name,
                    (0.35, 0.4, 0.45),
                )
                widget = pymupdf.Widget()
                widget.field_name = f"reading_status_{document_index + 1}"
                widget.field_label = f"Reading status for {item.name}"
                widget.field_type = pymupdf.PDF_WIDGET_TYPE_COMBOBOX
                widget.choice_values = list(READING_STATUSES)
                widget.field_value = item.reading_status
                widget.rect = pymupdf.Rect(425, row.y0 + 20, row.x1 - 7, row.y0 + 42)
                widget.text_font = font_name
                widget.text_fontsize = 7.5
                widget.text_color = (0.12, 0.16, 0.2)
                widget.fill_color = (0.93, 0.95, 0.985)
                widget.border_color = (0.76, 0.82, 0.88)
                widget.border_width = 0.7
                widget.field_flags = pymupdf.PDF_CH_FIELD_IS_EDIT
                page.add_widget(widget)

        document.set_metadata(
            {
                "title": f"{summary.project_name} - Workspace Overview",
                "subject": "PDF Analyzer multi-document analysis report",
                "creator": "PDF Analyzer",
            }
        )
        document.set_toc([[1, "Workspace Overview", 1]])
        destination.parent.mkdir(parents=True, exist_ok=True)
        document.save(str(temporary), garbage=3, deflate=True)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    finally:
        document.close()
    return WorkspaceReportResult(
        path=str(destination),
        document_count=len(summary.documents),
        page_count=summary.total_pages,
        note_count=summary.total_notes,
        report_page_count=report_pages,
    )
