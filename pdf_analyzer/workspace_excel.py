"""Editable Excel reading and analysis report for a selected workspace."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .evidence import EvidenceStore
from .project_state import READING_STATUSES
from .workspace_analysis import WorkspaceSummary


class WorkspaceExcelError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class WorkspaceExcelResult:
    path: str
    document_count: int
    page_count: int
    note_count: int
    tag_count: int


def _pdf_url(path_value: str, page_number: int | None = None) -> str:
    value = Path(path_value).resolve().as_uri()
    return f"{value}#page={page_number}" if page_number else value


def _safe_write_url(worksheet, row: int, column: int, url: str, label: str, cell_format) -> None:
    try:
        worksheet.write_url(row, column, url, cell_format, label)
    except ValueError:
        worksheet.write(row, column, label, cell_format)


def export_workspace_excel(
    summary: WorkspaceSummary,
    destination_value: str | Path,
    evidence_storage_dir: str | Path,
    selected_tags: tuple[str, ...] | None = None,
) -> WorkspaceExcelResult:
    if not summary.documents:
        raise WorkspaceExcelError("The workspace contains no selected documents.")
    destination = Path(destination_value).resolve()
    if destination.suffix.casefold() != ".xlsx":
        raise WorkspaceExcelError("The Excel report must use the .xlsx extension.")
    try:
        import xlsxwriter
    except ImportError as exc:
        raise WorkspaceExcelError(
            "XlsxWriter is not installed. Run the application installer BAT again."
        ) from exc

    selected = (
        {tag.casefold() for tag in selected_tags}
        if selected_tags is not None
        else None
    )
    evidence_store = EvidenceStore(evidence_storage_dir)
    notes_by_document = {}
    note_rows = []
    tag_documents: dict[str, set[str]] = defaultdict(set)
    tag_display: dict[str, str] = {}
    note_number = 0
    for document in summary.documents:
        notes = (
            evidence_store.load(document.document_id)
            if document.available and document.document_id
            else ()
        )
        filtered_notes = []
        for note in notes:
            note_tags = note.tags or ("Untagged",)
            visible_tags = tuple(
                tag
                for tag in note_tags
                if selected is None or tag.casefold() in selected
            )
            if not visible_tags:
                continue
            filtered_notes.append(note)
            for tag in visible_tags:
                identity = tag.casefold()
                tag_display.setdefault(identity, tag)
                tag_documents[identity].add(document.name)
                note_number += 1
                note_rows.append(
                    (
                        note_number,
                        document,
                        note,
                        tag,
                    )
                )
        notes_by_document[document.document_id] = tuple(filtered_notes)

    temporary = destination.with_name(
        f".{destination.stem}.{uuid4().hex}.tmp.xlsx"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    workbook = None
    try:
        workbook = xlsxwriter.Workbook(
            str(temporary),
            {
                # PDF text, document names, comments and tags are data, not
                # Excel expressions. Application formulas are always written
                # explicitly with write_formula().
                "strings_to_formulas": False,
                "strings_to_urls": False,
            },
        )
        workbook.set_properties(
            {
                "title": f"{summary.project_name} - Reading and Analysis Report",
                "subject": "Editable PDF Analyzer workspace report",
                "author": "PDF Analyzer",
                "company": "",
                "comments": "Generated locally. Source PDFs are not embedded or modified.",
            }
        )

        navy = "#17324D"
        blue = "#246B9E"
        pale_blue = "#EAF3F8"
        pale_gray = "#F4F6F8"
        border = "#D5DDE5"
        green = "#DFF1E3"
        amber = "#FFF1CC"
        red = "#FCE1DF"

        title_format = workbook.add_format(
            {"font_name": "Aptos Display", "font_size": 18, "bold": True, "font_color": navy}
        )
        subtitle_format = workbook.add_format(
            {"font_name": "Aptos", "font_size": 9, "font_color": "#5D6975"}
        )
        section_format = workbook.add_format(
            {
                "font_name": "Aptos",
                "font_size": 11,
                "bold": True,
                "font_color": "#FFFFFF",
                "bg_color": blue,
                "align": "left",
                "valign": "vcenter",
            }
        )
        card_label = workbook.add_format(
            {
                "font_name": "Aptos",
                "font_size": 9,
                "bold": True,
                "font_color": "#5D6975",
                "bg_color": pale_blue,
                "align": "center",
                "top": 1,
                "left": 1,
                "right": 1,
                "border_color": border,
            }
        )
        card_value = workbook.add_format(
            {
                "font_name": "Aptos Display",
                "font_size": 16,
                "bold": True,
                "font_color": navy,
                "bg_color": pale_blue,
                "align": "center",
                "bottom": 1,
                "left": 1,
                "right": 1,
                "border_color": border,
                "num_format": "#,##0",
            }
        )
        link_format = workbook.add_format(
            {"font_name": "Aptos", "font_color": blue, "underline": True}
        )
        wrapped_format = workbook.add_format(
            {"font_name": "Aptos", "valign": "top", "text_wrap": True}
        )
        editable_format = workbook.add_format(
            {
                "font_name": "Aptos",
                "bg_color": "#FFFBEA",
                "border": 1,
                "border_color": "#E6DDAF",
                "valign": "top",
                "text_wrap": True,
            }
        )
        date_format = workbook.add_format(
            {"font_name": "Aptos", "num_format": "yyyy-mm-dd hh:mm"}
        )
        integer_format = workbook.add_format({"font_name": "Aptos", "num_format": "#,##0"})

        summary_sheet = workbook.add_worksheet("Summary")
        documents_sheet = workbook.add_worksheet("Documents")
        notes_sheet = workbook.add_worksheet("Notes")
        tags_sheet = workbook.add_worksheet("Tags")
        lists_sheet = workbook.add_worksheet("Lists")
        for sheet in (summary_sheet, documents_sheet, notes_sheet, tags_sheet, lists_sheet):
            sheet.hide_gridlines(2)
            sheet.set_default_row(18)

        lists_sheet.write_column("A2", READING_STATUSES)
        lists_sheet.write("A1", "Reading Status")
        lists_sheet.hide()

        document_first_row = 5
        document_last_row = document_first_row + len(summary.documents) - 1
        notes_first_row = 5
        notes_last_row = notes_first_row + len(note_rows) - 1

        summary_sheet.set_tab_color(blue)
        summary_sheet.set_column("A:A", 2)
        summary_sheet.set_column("B:I", 15)
        summary_sheet.merge_range("B2:I2", "READING AND ANALYSIS REPORT", title_format)
        summary_sheet.merge_range("B3:I3", summary.project_name, subtitle_format)
        summary_sheet.write("B4", "Generated locally")
        summary_sheet.write_datetime("C4", datetime.now(), date_format)
        summary_sheet.write("B6", "DOCUMENTS", card_label)
        summary_sheet.write("D6", "PAGES", card_label)
        summary_sheet.write("F6", "NOTES", card_label)
        summary_sheet.write("H6", "REVIEWED / APPROVED", card_label)
        doc_range = f"'Documents'!$A${document_first_row}:$A${document_last_row}"
        pages_range = f"'Documents'!$C${document_first_row}:$C${document_last_row}"
        notes_range = f"'Documents'!$E${document_first_row}:$E${document_last_row}"
        status_range = f"'Documents'!$D${document_first_row}:$D${document_last_row}"
        summary_sheet.write_formula("B7", f"=COUNTA({doc_range})", card_value, len(summary.documents))
        summary_sheet.write_formula("D7", f"=SUM({pages_range})", card_value, summary.total_pages)
        summary_sheet.write_formula(
            "F7",
            f"=SUM({notes_range})",
            card_value,
            len({note.evidence_id for _, _, note, _ in note_rows}),
        )
        reviewed_count = sum(
            item.reading_status in {"Reviewed", "Approved"} for item in summary.documents
        )
        summary_sheet.write_formula(
            "H7",
            f'=COUNTIF({status_range},"Reviewed")+COUNTIF({status_range},"Approved")',
            card_value,
            reviewed_count,
        )
        summary_sheet.merge_range("B9:I9", "READING STATUS BREAKDOWN", section_format)
        status_start = 10
        for index, status in enumerate(READING_STATUSES):
            row = status_start + index
            summary_sheet.write(row - 1, 1, status)
            count = sum(item.reading_status == status for item in summary.documents)
            summary_sheet.write_formula(
                row - 1,
                3,
                f'=COUNTIF({status_range},B{row})',
                integer_format,
                count,
            )
        summary_sheet.merge_range(
            "B17:I17",
            "Yellow cells are editable. Changes made in Excel do not synchronize back to PDF Analyzer.",
            subtitle_format,
        )
        summary_sheet.freeze_panes(4, 1)
        summary_sheet.set_landscape()
        summary_sheet.fit_to_pages(1, 1)

        documents_sheet.set_tab_color("#4D86A8")
        documents_sheet.freeze_panes(4, 1)
        documents_sheet.set_landscape()
        documents_sheet.fit_to_pages(1, 0)
        documents_sheet.repeat_rows(3)
        documents_sheet.set_margins(0.35, 0.35, 0.5, 0.5)
        documents_sheet.set_column("A:A", 7)
        documents_sheet.set_column("B:B", 34)
        documents_sheet.set_column("C:C", 12)
        documents_sheet.set_column("D:D", 22)
        documents_sheet.set_column("E:F", 12)
        documents_sheet.set_column("G:G", 40)
        documents_sheet.set_column("H:H", 18)
        documents_sheet.set_column("I:I", 60)
        documents_sheet.merge_range("A1:I1", "DOCUMENTS", title_format)
        documents_sheet.merge_range(
            "A2:I2",
            "Click a PDF title to open the source file. Reading Status remains editable.",
            subtitle_format,
        )
        document_headers = [
            "No.",
            "PDF Title",
            "Page Count",
            "Reading Status",
            "Note Count",
            "Unique Tags",
            "Tag Summary",
            "Availability",
            "Source Path",
        ]
        for index, document in enumerate(summary.documents, start=1):
            row = 3 + index
            notes = notes_by_document.get(document.document_id, ())
            tags = sorted(
                {tag for note in notes for tag in (note.tags or ("Untagged",))},
                key=str.casefold,
            )
            documents_sheet.write_number(row, 0, index)
            if document.available:
                _safe_write_url(
                    documents_sheet,
                    row,
                    1,
                    _pdf_url(document.path),
                    document.name,
                    link_format,
                )
            else:
                documents_sheet.write(row, 1, document.name)
            documents_sheet.write_number(row, 2, document.page_count, integer_format)
            documents_sheet.write(row, 3, document.reading_status, editable_format)
            documents_sheet.write_number(row, 4, len(notes), integer_format)
            documents_sheet.write_number(row, 5, len(tags), integer_format)
            documents_sheet.write(row, 6, ", ".join(tags), wrapped_format)
            documents_sheet.write(row, 7, "Available" if document.available else "Missing / Invalid")
            documents_sheet.write(row, 8, document.path, wrapped_format)
            documents_sheet.set_row(row, 30)
        documents_sheet.add_table(
            3,
            0,
            3 + len(summary.documents),
            len(document_headers) - 1,
            {
                "name": "DocumentsTable",
                "style": "Table Style Medium 2",
                "columns": [{"header": value} for value in document_headers],
            },
        )
        documents_sheet.data_validation(
            4,
            3,
            3 + len(summary.documents),
            3,
            {"validate": "list", "source": "=Lists!$A$2:$A$7"},
        )
        documents_sheet.conditional_format(
            4,
            3,
            3 + len(summary.documents),
            3,
            {"type": "text", "criteria": "containing", "value": "Approved", "format": workbook.add_format({"bg_color": green})},
        )
        documents_sheet.conditional_format(
            4,
            3,
            3 + len(summary.documents),
            3,
            {"type": "text", "criteria": "containing", "value": "Needs Attention", "format": workbook.add_format({"bg_color": red})},
        )

        notes_sheet.set_tab_color("#70A1BD")
        notes_sheet.freeze_panes(4, 4)
        notes_sheet.set_landscape()
        notes_sheet.fit_to_pages(1, 0)
        notes_sheet.repeat_rows(3)
        notes_sheet.set_margins(0.35, 0.35, 0.5, 0.5)
        notes_sheet.set_column("A:A", 7)
        notes_sheet.set_column("B:B", 30)
        notes_sheet.set_column("C:C", 9)
        notes_sheet.set_column("D:D", 20)
        notes_sheet.set_column("E:E", 55)
        notes_sheet.set_column("F:F", 45)
        notes_sheet.set_column("G:G", 11)
        notes_sheet.set_column("H:H", 18)
        notes_sheet.set_column("I:I", 24)
        notes_sheet.merge_range("A1:I1", "NOTES AND HIGHLIGHTS", title_format)
        notes_sheet.merge_range(
            "A2:I2",
            "Filter by document or tag. Comment cells are intentionally editable.",
            subtitle_format,
        )
        note_headers = [
            "No.",
            "Document",
            "Page",
            "Tag",
            "Highlighted Text",
            "Comment (Editable)",
            "Citation",
            "PDF Link",
            "Created At",
        ]
        for row_offset, (number, document, note, tag) in enumerate(note_rows):
            row = 4 + row_offset
            notes_sheet.write_number(row, 0, number)
            _safe_write_url(
                notes_sheet,
                row,
                1,
                _pdf_url(document.path, note.page_index + 1),
                document.name,
                link_format,
            )
            notes_sheet.write_number(row, 2, note.page_index + 1, integer_format)
            notes_sheet.write(row, 3, tag)
            notes_sheet.write(row, 4, note.text, wrapped_format)
            notes_sheet.write(row, 5, note.comment, editable_format)
            notes_sheet.write(row, 6, f"[{note.citation_number}]")
            _safe_write_url(
                notes_sheet,
                row,
                7,
                _pdf_url(document.path, note.page_index + 1),
                f"Open page {note.page_index + 1}",
                link_format,
            )
            try:
                created = datetime.fromisoformat(note.created_at.replace("Z", "+00:00"))
                if created.tzinfo is not None:
                    created = created.replace(tzinfo=None)
                notes_sheet.write_datetime(row, 8, created, date_format)
            except ValueError:
                notes_sheet.write(row, 8, note.created_at)
            notes_sheet.set_row(row, 42)
        if note_rows:
            notes_sheet.add_table(
                3,
                0,
                3 + len(note_rows),
                len(note_headers) - 1,
                {
                    "name": "NotesTable",
                    "style": "Table Style Medium 2",
                    "columns": [{"header": value} for value in note_headers],
                },
            )
        else:
            notes_sheet.write_row(3, 0, note_headers, section_format)
            notes_sheet.merge_range("A5:I5", "No notes match the selected documents and tag filter.", subtitle_format)

        tag_identities = sorted(tag_display, key=lambda value: tag_display[value].casefold())
        tags_sheet.set_tab_color("#95B7CA")
        tags_sheet.freeze_panes(4, 0)
        tags_sheet.set_landscape()
        tags_sheet.fit_to_pages(1, 0)
        tags_sheet.repeat_rows(3)
        tags_sheet.set_margins(0.35, 0.35, 0.5, 0.5)
        tags_sheet.set_column("A:A", 28)
        tags_sheet.set_column("B:C", 18)
        tags_sheet.set_column("D:D", 70)
        tags_sheet.merge_range("A1:D1", "TAG SUMMARY", title_format)
        tags_sheet.merge_range(
            "A2:D2",
            "Mention Count is formula-driven from the editable Notes worksheet.",
            subtitle_format,
        )
        tag_headers = ["Tag", "Mention Count", "Document Count", "Documents"]
        for row_offset, identity in enumerate(tag_identities):
            row = 4 + row_offset
            display = tag_display[identity]
            mention_count = sum(tag.casefold() == identity for _, _, _, tag in note_rows)
            tags_sheet.write(row, 0, display)
            if note_rows:
                notes_tag_range = f"'Notes'!$D${notes_first_row}:$D${notes_last_row}"
                tags_sheet.write_formula(
                    row,
                    1,
                    f'=COUNTIF({notes_tag_range},A{row + 1})',
                    integer_format,
                    mention_count,
                )
            else:
                tags_sheet.write_number(row, 1, 0, integer_format)
            documents = sorted(tag_documents[identity], key=str.casefold)
            tags_sheet.write_number(row, 2, len(documents), integer_format)
            tags_sheet.write(row, 3, ", ".join(documents), wrapped_format)
            tags_sheet.set_row(row, 30)
        if tag_identities:
            tags_sheet.add_table(
                3,
                0,
                3 + len(tag_identities),
                len(tag_headers) - 1,
                {
                    "name": "TagsTable",
                    "style": "Table Style Medium 2",
                    "columns": [{"header": value} for value in tag_headers],
                },
            )
        else:
            tags_sheet.write_row(3, 0, tag_headers, section_format)
            tags_sheet.merge_range("A5:D5", "No tags match the current filter.", subtitle_format)

        workbook.close()
        workbook = None
        temporary.replace(destination)
    except Exception as exc:
        if workbook is not None:
            try:
                workbook.close()
            except Exception:
                pass
        temporary.unlink(missing_ok=True)
        if isinstance(exc, WorkspaceExcelError):
            raise
        raise WorkspaceExcelError(f"The Excel report could not be created: {exc}") from exc

    return WorkspaceExcelResult(
        path=str(destination),
        document_count=len(summary.documents),
        page_count=summary.total_pages,
        note_count=len({note.evidence_id for _, _, note, _ in note_rows}),
        tag_count=len(tag_identities),
    )
