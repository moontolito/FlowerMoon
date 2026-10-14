"""Export tagged notes and highlights as a self-contained, navigable PDF."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pymupdf

from .bookmarks import PersonalBookmark
from .models import Evidence, Highlight, TextRect


REPORT_WIDTH = 595
REPORT_HEIGHT = 842
REPORT_MARGIN = 48
NOTE_BLOCK_HEIGHT = 94
REPORT_CONTENT_CAPACITY = 625
REPORT_BODY_LINE_HEIGHT = 9.2
REPORT_BODY_CHUNK_LINES = 32
DELEGATION_CHOICES = (
    "Unassigned",
    "Quality",
    "Welding",
    "Painting / Corrosion",
    "Engineering",
    "Production",
    "Procurement",
    "Commercial",
    "Legal",
    "HSE",
    "Project Management",
)


class PdfExportError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PdfExportResult:
    path: str
    highlight_count: int
    evidence_count: int
    index_page_count: int
    total_page_count: int


@dataclass(frozen=True, slots=True)
class _ReportRow:
    kind: str
    tag: str
    note: Evidence | None = None
    lines: tuple[str, ...] = ()
    height: float = 34
    continuation: int = 0
    manager_field: bool = False


def _rgb(color: str) -> tuple[float, float, float]:
    value = color.lstrip("#")
    if len(value) != 6:
        return (1.0, 0.75, 0.15)
    try:
        return tuple(int(value[index : index + 2], 16) / 255 for index in (0, 2, 4))
    except ValueError:
        return (1.0, 0.75, 0.15)


def _valid_rects(page, rects: tuple[TextRect, ...]) -> list[pymupdf.Rect]:
    result = []
    for value in rects:
        rect = pymupdf.Rect(value.x0, value.y0, value.x1, value.y1) & page.rect
        if not rect.is_empty and rect.width > 0.5 and rect.height > 0.5:
            result.append(rect)
    return result


def _target_point(note: Evidence) -> pymupdf.Point:
    if not note.rects:
        return pymupdf.Point(0, 0)
    first = note.rects[0]
    return pymupdf.Point(max(0, first.x0), max(0, first.y0 - 28))


def _font_file() -> Path | None:
    fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    return next(
        (candidate for candidate in (fonts / "segoeui.ttf", fonts / "arial.ttf") if candidate.is_file()),
        None,
    )


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
    for word in clean.split():
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
            lines.append(remainder[:split_at])
            remainder = remainder[split_at:]
        current = remainder
    if current:
        lines.append(current)
    return tuple(lines) or ("",)


def _text_box_fits(page, rect, text: str, size: float, font_name: str, color) -> bool:
    """Insert through a shape so failed layout attempts never reach the page."""
    shape = page.new_shape()
    result = shape.insert_textbox(
        rect,
        text,
        fontname=font_name,
        fontsize=size,
        color=color,
        lineheight=1.2,
    )
    if result < 0:
        return False
    shape.commit()
    return True


def _ellipsized(value: str, length: int) -> str:
    if len(value) <= length:
        return value
    shortened = value[: max(1, length - 3)].rstrip()
    if " " in shortened:
        shortened = shortened.rsplit(" ", 1)[0].rstrip() or shortened
    return shortened + "..."


def _insert_text(page, rect, text: str, size: float, font_name: str, color=(0.12, 0.17, 0.22)) -> None:
    """Fit report text safely, preserving as much readable content as possible."""
    minimum_size = max(5.5, size * 0.72)
    candidate_size = size
    while candidate_size >= minimum_size - 0.01:
        if _text_box_fits(page, rect, text, candidate_size, font_name, color):
            return
        candidate_size -= 0.5

    low = 1
    high = len(text)
    best = ""
    while low <= high:
        middle = (low + high) // 2
        candidate = _ellipsized(text, middle)
        shape = page.new_shape()
        result = shape.insert_textbox(
            rect,
            candidate,
            fontname=font_name,
            fontsize=minimum_size,
            color=color,
            lineheight=1.2,
        )
        if result >= 0:
            best = candidate
            low = middle + 1
        else:
            high = middle - 1
    if best and _text_box_fits(page, rect, best, minimum_size, font_name, color):
        return
    raise PdfExportError("A report text area is too small to contain readable text.")


def _note_tags(note: Evidence) -> tuple[str, ...]:
    return note.tags or ("",)


def _filtered_notes(
    evidence: tuple[Evidence, ...], selected_tags: tuple[str, ...] | None
) -> tuple[Evidence, ...]:
    ordered = tuple(
        sorted(evidence, key=lambda item: (item.page_index, item.citation_number))
    )
    if selected_tags is None:
        return ordered
    identities = {tag.casefold() for tag in selected_tags}
    return tuple(
        note
        for note in ordered
        if identities.intersection(tag.casefold() for tag in _note_tags(note))
    )


def _report_groups(
    notes: tuple[Evidence, ...], selected_tags: tuple[str, ...] | None
) -> tuple[tuple[str, tuple[Evidence, ...]], ...]:
    if selected_tags is None:
        selected_tags = tuple(
            sorted({tag for note in notes for tag in _note_tags(note)}, key=lambda value: (not value, value.casefold()))
        )
    groups = []
    for selected in selected_tags:
        identity = selected.casefold()
        matching = tuple(
            note for note in notes if identity in {tag.casefold() for tag in _note_tags(note)}
        )
        if matching:
            groups.append((selected, matching))
    return tuple(groups)


def _note_report_rows(
    tag: str,
    note: Evidence,
    font: pymupdf.Font,
) -> tuple[_ReportRow, ...]:
    comment = " ".join(note.comment.split()) or "No personal comment"
    excerpt = " ".join(note.text.split()) or "No selected text"
    lines = (
        _wrap_text(f"Analyst comment: {comment}", 475, font, 7.8)
        + ("",)
        + _wrap_text(f"Source text: {excerpt}", 475, font, 7.5)
    )
    chunks = tuple(
        lines[index : index + REPORT_BODY_CHUNK_LINES]
        for index in range(0, len(lines), REPORT_BODY_CHUNK_LINES)
    ) or (("",),)
    return tuple(
        _ReportRow(
            "note",
            tag,
            note,
            chunk,
            39 + len(chunk) * REPORT_BODY_LINE_HEIGHT + (82 if index == 0 else 10),
            index,
            index == 0,
        )
        for index, chunk in enumerate(chunks)
    )


def _tag_report_row(tag: str, font: pymupdf.Font) -> _ReportRow:
    display = tag or "Untagged"
    lines = _wrap_text(display, 495, font, 11)
    return _ReportRow(
        "tag",
        tag,
        lines=lines,
        height=max(34, 11 * 1.2 * len(lines) + 12),
    )


def _layout_report(groups: tuple[tuple[str, tuple[Evidence, ...]], ...]) -> tuple[tuple[_ReportRow, ...], ...]:
    pages: list[list[_ReportRow]] = [[]]
    used = 0
    font = _report_font()
    for tag, notes in groups:
        tag_row = _tag_report_row(tag, font)
        note_rows = tuple(
            row
            for note in notes
            for row in _note_report_rows(tag, note, font)
        )
        first_note_height = note_rows[0].height if note_rows else 0
        if (
            used
            and used + tag_row.height + first_note_height
            > REPORT_CONTENT_CAPACITY
        ):
            pages.append([])
            used = 0
        pages[-1].append(tag_row)
        used += tag_row.height
        for note_row in note_rows:
            if used + note_row.height > REPORT_CONTENT_CAPACITY:
                pages.append([tag_row])
                used = tag_row.height
            pages[-1].append(note_row)
            used += note_row.height
    return tuple(tuple(page) for page in pages)


def _insert_report(
    document,
    source_name: str,
    groups: tuple[tuple[str, tuple[Evidence, ...]], ...],
    existing_toc: list[list],
) -> int:
    layouts = _layout_report(groups)
    report_pages = len(layouts)
    font_file = _font_file()
    report_font = _report_font()
    source_lines = _wrap_text(
        f"Document: {source_name}",
        REPORT_WIDTH - 2 * REPORT_MARGIN,
        report_font,
        7.5,
    )
    report_toc: list[list] = [[1, "PDF Analyzer - Tag Report", 1]]
    added_tag_bookmarks: set[str] = set()

    for report_index in range(report_pages):
        document.new_page(
            pno=report_index,
            width=REPORT_WIDTH,
            height=REPORT_HEIGHT,
        )

    for report_index, rows in enumerate(layouts):
        page = document[report_index]
        font_name = "helv"
        if font_file:
            page.insert_font(fontname="SegoeUI", fontfile=str(font_file))
            font_name = "SegoeUI"
        _insert_text(
            page,
            pymupdf.Rect(REPORT_MARGIN, 40, REPORT_WIDTH - REPORT_MARGIN, 72),
            "PDF ANALYZER - TAG REPORT",
            16,
            font_name,
        )
        _insert_text(
            page,
            pymupdf.Rect(REPORT_MARGIN, 75, REPORT_WIDTH - REPORT_MARGIN, 133),
            (
                f"{chr(10).join(source_lines)}\n"
                f"Report {report_index + 1} of {report_pages}"
            ),
            7.5,
            font_name,
        )
        page.draw_line(
            pymupdf.Point(REPORT_MARGIN, 139),
            pymupdf.Point(REPORT_WIDTH - REPORT_MARGIN, 139),
            color=(0.75, 0.79, 0.83),
            width=0.8,
        )
        y = 151
        if not rows:
            _insert_text(
                page,
                pymupdf.Rect(REPORT_MARGIN, y, REPORT_WIDTH - REPORT_MARGIN, y + 50),
                "There are no notes for the selected tags. Highlights remain in the document.",
                11,
                font_name,
            )
        for row in rows:
            if row.kind == "tag":
                display_tag = row.tag or "Untagged"
                _insert_text(
                    page,
                    pymupdf.Rect(
                        REPORT_MARGIN,
                        y + 3,
                        REPORT_WIDTH - REPORT_MARGIN,
                        y + row.height - 3,
                    ),
                    "\n".join(row.lines) or display_tag,
                    11,
                    font_name,
                    color=(0.08, 0.35, 0.58),
                )
                identity = row.tag.casefold()
                if identity not in added_tag_bookmarks:
                    report_toc.append([2, display_tag, report_index + 1])
                    added_tag_bookmarks.add(identity)
                y += row.height
                continue
            note = row.note
            if note is None:
                continue
            block = pymupdf.Rect(
                REPORT_MARGIN,
                y,
                REPORT_WIDTH - REPORT_MARGIN,
                y + row.height - 8,
            )
            page.draw_rect(block, color=(0.83, 0.86, 0.89), fill=(0.97, 0.98, 0.99), width=0.7)
            _insert_text(
                page,
                pymupdf.Rect(block.x0 + 10, block.y0 + 7, block.x1 - 10, block.y0 + 24),
                (
                    f"[{note.citation_number}] Page {note.page_index + 1}"
                    + (f" - continued {row.continuation + 1}" if row.continuation else "")
                ),
                9.5,
                font_name,
                color=(0.08, 0.35, 0.58),
            )
            body_bottom = block.y1 - (80 if row.manager_field else 7)
            _insert_text(
                page,
                pymupdf.Rect(block.x0 + 10, block.y0 + 27, block.x1 - 10, body_bottom),
                "\n".join(row.lines),
                7.7,
                font_name,
                color=(0.38, 0.43, 0.48),
            )
            if row.manager_field:
                _insert_text(
                    page,
                    pymupdf.Rect(
                        block.x0 + 10,
                        block.y1 - 76,
                        block.x1 - 10,
                        block.y1 - 64,
                    ),
                    "DELEGATED TO",
                    6.4,
                    font_name,
                    color=(0.35, 0.4, 0.45),
                )
                delegation = pymupdf.Widget()
                delegation.field_name = (
                    f"delegated_to_{note.evidence_id}_{report_index}_{int(y)}"
                )
                delegation.field_label = (
                    f"Delegated department for citation {note.citation_number}"
                )
                delegation.field_type = pymupdf.PDF_WIDGET_TYPE_COMBOBOX
                delegation.choice_values = list(DELEGATION_CHOICES)
                delegation.field_value = "Unassigned"
                delegation.rect = pymupdf.Rect(
                    block.x0 + 10,
                    block.y1 - 62,
                    block.x1 - 10,
                    block.y1 - 45,
                )
                delegation.text_font = font_name
                delegation.text_fontsize = 7
                delegation.text_color = (0.12, 0.17, 0.22)
                delegation.fill_color = (0.93, 0.95, 0.985)
                delegation.border_color = (0.76, 0.82, 0.88)
                delegation.border_width = 0.7
                delegation.field_flags = pymupdf.PDF_CH_FIELD_IS_EDIT
                page.add_widget(delegation)
                _insert_text(
                    page,
                    pymupdf.Rect(
                        block.x0 + 10,
                        block.y1 - 42,
                        block.x1 - 10,
                        block.y1 - 30,
                    ),
                    "MANAGER COMMENT",
                    6.4,
                    font_name,
                    color=(0.35, 0.4, 0.45),
                )
                widget = pymupdf.Widget()
                widget.field_name = (
                    f"manager_comment_{note.evidence_id}_{report_index}_{int(y)}"
                )
                widget.field_label = (
                    f"Manager comment for citation {note.citation_number}"
                )
                widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
                widget.field_flags = pymupdf.PDF_TX_FIELD_IS_MULTILINE
                widget.field_value = ""
                widget.rect = pymupdf.Rect(
                    block.x0 + 10,
                    block.y1 - 28,
                    block.x1 - 10,
                    block.y1 - 7,
                )
                widget.text_font = font_name
                widget.text_fontsize = 7
                widget.text_color = (0.12, 0.17, 0.22)
                widget.fill_color = (1, 1, 0.94)
                widget.border_color = (0.76, 0.82, 0.88)
                widget.border_width = 0.7
                page.add_widget(widget)
            target_page = report_pages + note.page_index
            page.insert_link(
                {
                    "kind": pymupdf.LINK_GOTO,
                    "from": block,
                    "page": target_page,
                    "to": _target_point(note),
                }
            )
            if row.continuation == 0:
                report_toc.append(
                    [3, f"[{note.citation_number}] Page {note.page_index + 1}", target_page + 1]
                )
            y += row.height

    adjusted_existing = [
        [level, title, page_number + report_pages if page_number > 0 else page_number]
        for level, title, page_number, *rest in existing_toc
    ]
    document.set_toc(report_toc + adjusted_existing)
    return report_pages


def _append_personal_bookmarks(
    document,
    bookmarks: tuple[PersonalBookmark, ...],
    report_pages: int,
    original_page_count: int,
) -> None:
    if not bookmarks:
        return
    by_parent: dict[str | None, list[PersonalBookmark]] = {}
    for bookmark in bookmarks:
        if not 0 <= bookmark.page_index < original_page_count:
            raise PdfExportError("A personal bookmark references an invalid page.")
        by_parent.setdefault(bookmark.parent_id, []).append(bookmark)
    first_page = report_pages + bookmarks[0].page_index
    toc = document.get_toc(simple=False)
    toc.append([1, "My Bookmarks", first_page + 1])

    def append_children(parent_id: str | None, depth: int) -> None:
        for bookmark in by_parent.get(parent_id, ()):
            target_page = report_pages + bookmark.page_index
            page = document[target_page]
            point = pymupdf.Point(
                bookmark.x_ratio * page.rect.width,
                bookmark.y_ratio * page.rect.height,
            )
            destination = {
                "kind": pymupdf.LINK_GOTO,
                "page": target_page,
                "to": point,
                "zoom": bookmark.zoom,
            }
            toc.append(
                [
                    min(4, depth + 2),
                    bookmark.title,
                    target_page + 1,
                    destination,
                ]
            )
            append_children(bookmark.bookmark_id, depth + 1)

    append_children(None, 0)
    document.set_toc(toc)


def export_annotated_pdf(
    source_value: str | Path,
    destination_value: str | Path,
    highlights: tuple[Highlight, ...],
    evidence: tuple[Evidence, ...],
    selected_tags: tuple[str, ...] | None = None,
    personal_bookmarks: tuple[PersonalBookmark, ...] = (),
) -> PdfExportResult:
    source = Path(source_value).resolve()
    destination = Path(destination_value).resolve()
    if not source.is_file() or source.suffix.casefold() != ".pdf":
        raise PdfExportError("The source document is not a valid PDF.")
    if destination.suffix.casefold() != ".pdf":
        raise PdfExportError("The export must use the .pdf extension.")
    if source == destination:
        raise PdfExportError("The export cannot overwrite the original document.")

    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    document = None
    try:
        document = pymupdf.open(str(source))
        if document.needs_pass or document.page_count < 1:
            raise PdfExportError("The document is protected or contains no pages.")
        original_page_count = document.page_count
        existing_toc = document.get_toc(simple=True)
        filtered_notes = _filtered_notes(evidence, selected_tags)
        groups = _report_groups(filtered_notes, selected_tags)
        report_pages = _insert_report(document, source.name, groups, existing_toc)
        exported_highlights = 0
        exported_notes = 0

        for number, highlight in enumerate(highlights, start=1):
            if not 0 <= highlight.page_index < original_page_count:
                raise PdfExportError("A highlight references an invalid page.")
            page = document[report_pages + highlight.page_index]
            rectangles = _valid_rects(page, highlight.rects)
            if not rectangles:
                continue
            annotation = page.add_highlight_annot(rectangles)
            annotation.set_colors(stroke=_rgb(highlight.color))
            annotation.set_opacity(0.38)
            annotation.set_info(
                title="PDF Analyzer",
                subject=f"Highlight H{number}",
                content=highlight.text,
            )
            annotation.update()
            exported_highlights += 1

        for note in filtered_notes:
            if not 0 <= note.page_index < original_page_count:
                raise PdfExportError("A note references an invalid page.")
            page = document[report_pages + note.page_index]
            rectangles = _valid_rects(page, note.rects)
            if not rectangles:
                continue
            annotation = page.add_highlight_annot(rectangles)
            annotation.set_colors(stroke=(0.35, 0.70, 0.95))
            annotation.set_opacity(0.30)
            tag_text = ", ".join(note.tags) or "Untagged"
            content_parts = []
            if note.comment:
                content_parts.append(note.comment)
            content_parts.append(f"Tags: {tag_text}")
            content_parts.append(f"Selected text: {note.text}")
            annotation.set_info(
                title="PDF Analyzer",
                subject=f"Note [{note.citation_number}]",
                content="\n\n".join(content_parts),
            )
            annotation.update()
            exported_notes += 1

        _append_personal_bookmarks(
            document,
            personal_bookmarks,
            report_pages,
            original_page_count,
        )

        metadata = dict(document.metadata or {})
        metadata["producer"] = "PDF Analyzer"
        metadata["keywords"] = "PDF Analyzer, tags, notes, highlights"
        document.set_metadata(metadata)
        destination.parent.mkdir(parents=True, exist_ok=True)
        document.save(str(temporary), garbage=3, deflate=True)
        document.close()
        document = None

        verification = pymupdf.open(str(temporary))
        try:
            expected_pages = original_page_count + report_pages
            if verification.page_count != expected_pages:
                raise PdfExportError("The exported PDF could not be verified.")
        finally:
            verification.close()
        temporary.replace(destination)
        return PdfExportResult(
            str(destination),
            exported_highlights,
            exported_notes,
            report_pages,
            expected_pages,
        )
    except PdfExportError:
        raise
    except Exception as exc:
        raise PdfExportError("The annotated PDF could not be exported.") from exc
    finally:
        if document is not None:
            document.close()
        if temporary.is_file():
            temporary.unlink()
