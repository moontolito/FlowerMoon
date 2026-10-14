"""Thread-safe, read-only PDF validation and rendering."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from threading import RLock
from uuid import uuid4

from .models import DocumentInfo, PageLayout, RenderedPage


MAX_PDF_SIZE_BYTES = 500 * 1024 * 1024
MAX_RENDER_WIDTH = 4200
MAX_RENDER_PIXELS = 28_000_000


class PdfImportError(ValueError):
    """Controlled import/render error suitable for display to the user."""


class PdfSession:
    def __init__(self) -> None:
        self._lock = RLock()
        self._document = None
        self._source: Path | None = None
        self._info: DocumentInfo | None = None

    @staticmethod
    def _library():
        try:
            import pymupdf
        except ImportError as exc:
            raise RuntimeError("PyMuPDF is not installed.") from exc
        return pymupdf

    @staticmethod
    def _hash_file(source: Path) -> str:
        digest = hashlib.sha256()
        with source.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @property
    def info(self) -> DocumentInfo | None:
        with self._lock:
            return self._info

    def close(self) -> None:
        with self._lock:
            if self._document is not None:
                self._document.close()
            self._document = None
            self._source = None
            self._info = None

    def open(self, path_value: str | Path) -> tuple[DocumentInfo, list[PageLayout]]:
        """Validate completely before atomically replacing the current document."""
        source = Path(path_value).resolve()
        if not source.is_file():
            raise PdfImportError("The selected file does not exist or cannot be accessed.")
        if source.suffix.casefold() != ".pdf":
            raise PdfImportError("Invalid format. Select a PDF document.")
        size = source.stat().st_size
        if size == 0:
            raise PdfImportError("The selected document is empty.")
        if size > MAX_PDF_SIZE_BYTES:
            raise PdfImportError("The document exceeds the 500 MB limit.")

        pymupdf = self._library()
        try:
            candidate = pymupdf.open(str(source))
        except Exception as exc:
            raise PdfImportError("The file is not a valid PDF or is corrupted.") from exc

        try:
            if candidate.needs_pass:
                raise PdfImportError("The document is password protected.")
            if candidate.page_count < 1:
                raise PdfImportError("The document contains no displayable pages.")
            metadata = candidate.metadata or {}
            document_id = self._hash_file(source)
            info = DocumentInfo(
                document_id=document_id,
                name=source.name,
                path=str(source),
                size_bytes=size,
                page_count=candidate.page_count,
                title=(metadata.get("title") or "").strip(),
                author=(metadata.get("author") or "").strip(),
                is_encrypted=False,
            )
            layouts = [
                PageLayout(
                    document_id=document_id,
                    page_index=index,
                    page_number=index + 1,
                    width_points=page.rect.width,
                    height_points=page.rect.height,
                )
                for index, page in enumerate(candidate)
            ]
        except Exception:
            candidate.close()
            raise

        with self._lock:
            previous = self._document
            self._document = candidate
            self._source = source
            self._info = info
            if previous is not None:
                previous.close()
        return info, layouts

    @classmethod
    def merge_documents(
        cls, source_values: tuple[str, ...], destination_value: str | Path
    ) -> str:
        """Validate and merge PDFs into a new file without changing the active session."""
        if len(source_values) < 2:
            raise PdfImportError("Select at least two documents to combine.")
        sources = tuple(Path(value).resolve() for value in source_values)
        destination = Path(destination_value).resolve()
        if destination.suffix.casefold() != ".pdf":
            raise PdfImportError("The combined document must use the .pdf extension.")
        if destination in sources:
            raise PdfImportError("The combined document cannot overwrite a source file.")
        if len(set(sources)) != len(sources):
            raise PdfImportError("The combine list contains duplicate documents.")

        pymupdf = cls._library()
        merged = pymupdf.open()
        opened = []
        temporary = destination.with_name(
            f".{destination.name}.{uuid4().hex}.pdf-analyzer.tmp"
        )
        try:
            for source in sources:
                if not source.is_file() or source.suffix.casefold() != ".pdf":
                    raise PdfImportError(f"Invalid file for combining: {source.name}")
                if source.stat().st_size == 0 or source.stat().st_size > MAX_PDF_SIZE_BYTES:
                    raise PdfImportError(f"Invalid file size: {source.name}")
                try:
                    document = pymupdf.open(str(source))
                except Exception as exc:
                    raise PdfImportError(f"Corrupted or inaccessible PDF: {source.name}") from exc
                opened.append(document)
                if document.needs_pass or document.page_count < 1:
                    raise PdfImportError(f"Protected or empty PDF: {source.name}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            for document in opened:
                merged.insert_pdf(document)
            merged.save(str(temporary), garbage=3, deflate=True)
            if temporary.stat().st_size > MAX_PDF_SIZE_BYTES:
                raise PdfImportError("The combined PDF exceeds the 500 MB limit.")
            temporary.replace(destination)
        except Exception:
            if temporary.is_file():
                temporary.unlink()
            raise
        finally:
            merged.close()
            for document in opened:
                document.close()
        return str(destination)

    def outline(self) -> tuple[tuple[int, str, int], ...]:
        with self._lock:
            if self._document is None:
                return ()
            return tuple(
                (int(level), str(title), max(0, int(page_number) - 1))
                for level, title, page_number, *rest in self._document.get_toc(simple=True)
                if int(page_number) > 0
            )

    @classmethod
    def copy_document(cls, source_value: str | Path, destination_value: str | Path) -> str:
        source = Path(source_value).resolve()
        destination = Path(destination_value).resolve()
        if not source.is_file() or source.suffix.casefold() != ".pdf":
            raise PdfImportError("The source document is not a valid PDF.")
        if destination.suffix.casefold() != ".pdf":
            raise PdfImportError("The saved copy must use the .pdf extension.")
        if source == destination:
            raise PdfImportError("The saved copy cannot overwrite the open document.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
        try:
            with source.open("rb") as source_stream, temporary.open("wb") as target_stream:
                for chunk in iter(lambda: source_stream.read(1024 * 1024), b""):
                    target_stream.write(chunk)
            temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return str(destination)

    def render(self, page_index: int, target_width: int = 1100, rotation: int = 0) -> RenderedPage:
        with self._lock:
            if self._document is None or self._info is None:
                raise PdfImportError("No document is open.")
            if not isinstance(page_index, int) or not 0 <= page_index < self._info.page_count:
                raise PdfImportError(f"The page must be between 1 and {self._info.page_count}.")
            rotation = int(rotation) % 360
            if rotation not in (0, 90, 180, 270):
                raise PdfImportError("Rotation must be 0, 90, 180 or 270 degrees.")
            target_width = max(120, min(int(target_width), MAX_RENDER_WIDTH))
            page = self._document[page_index]
            source_width = max(page.rect.width, 1)
            source_height = max(page.rect.height, 1)
            width_points = source_height if rotation in (90, 270) else source_width
            height_points = source_width if rotation in (90, 270) else source_height
            width_scale = target_width / width_points
            pixel_limit_scale = math.sqrt(MAX_RENDER_PIXELS / (width_points * height_points))
            scale = min(8.0, max(0.25, width_scale), pixel_limit_scale)
            pymupdf = self._library()
            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(scale, scale).prerotate(rotation), alpha=False
            )
            return RenderedPage(
                document_id=self._info.document_id,
                page_index=page_index,
                page_number=page_index + 1,
                page_count=self._info.page_count,
                width_points=width_points,
                height_points=height_points,
                image_width=pixmap.width,
                image_height=pixmap.height,
                png_bytes=pixmap.tobytes("png"),
            )
