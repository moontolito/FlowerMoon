"""Native text extraction, local Tesseract OCR and deterministic caching."""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
from dataclasses import asdict
from io import StringIO
from pathlib import Path
from statistics import fmean
from threading import Event

import pymupdf

from .models import DocumentText, PageText, TextAudit, TextWord


CACHE_VERSION = 3
OCR_DPI = 350
MAX_OCR_PIXELS = 40_000_000
MIN_NATIVE_CHARACTERS = 8
SPARSE_TEXT_MAX_WORDS = 30
SPARSE_TEXT_MAX_CHARACTERS = 180
LARGE_IMAGE_COVERAGE = 0.55


class TextExtractionError(RuntimeError):
    """Controlled text/OCR error suitable for the interface."""


class TesseractBackend:
    def __init__(self, executable: str | Path | None = None, requested_languages=("eng", "ron")) -> None:
        self.executable = Path(executable).resolve() if executable else self._find_executable()
        self.available_languages = self._read_languages() if self.executable else ()
        self.languages = tuple(language for language in requested_languages if language in self.available_languages)

    @staticmethod
    def _find_executable() -> Path | None:
        command = shutil.which("tesseract")
        portable_runtime = Path(__file__).resolve().parents[1] / "runtime" / "Tesseract-OCR" / "tesseract.exe"
        candidates = [
            Path(command) if command else None,
            portable_runtime,
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Tesseract-OCR" / "tesseract.exe",
            Path(os.environ.get("PROGRAMFILES", "")) / "Tesseract-OCR" / "tesseract.exe",
            Path(os.environ.get("PROGRAMFILES", "")) / "PDF24" / "tesseract" / "tesseract.exe",
        ]
        return next((candidate.resolve() for candidate in candidates if candidate and candidate.is_file()), None)

    @property
    def available(self) -> bool:
        return self.executable is not None and bool(self.languages)

    @property
    def language_label(self) -> str:
        return "+".join(self.languages)

    @staticmethod
    def _process_flags() -> int:
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def _read_languages(self) -> tuple[str, ...]:
        try:
            result = subprocess.run(
                [str(self.executable), "--list-langs"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
                creationflags=self._process_flags(),
            )
        except (OSError, subprocess.SubprocessError):
            return ()
        lines = [line.strip() for line in result.stdout.splitlines()]
        return tuple(line for line in lines if line and not line.casefold().startswith("list of"))

    def recognize(
        self,
        png_bytes: bytes,
        page_width: float,
        page_height: float,
        dpi: int = OCR_DPI,
    ) -> tuple[str, tuple[TextWord, ...], float | None]:
        if not self.available:
            raise TextExtractionError("Motorul OCR local sau limbile OCR nu sunt disponibile.")
        command = [
            str(self.executable),
            "stdin",
            "stdout",
            "--dpi",
            str(dpi),
            "-l",
            self.language_label,
            "tsv",
        ]
        try:
            result = subprocess.run(
                command,
                input=png_bytes,
                capture_output=True,
                timeout=180,
                check=False,
                creationflags=self._process_flags(),
            )
        except subprocess.TimeoutExpired as exc:
            raise TextExtractionError("OCR exceeded the 3-minute limit for one page.") from exc
        except OSError as exc:
            raise TextExtractionError("Motorul OCR local nu a putut fi pornit.") from exc
        if result.returncode != 0:
            details = result.stderr.decode("utf-8", errors="replace").strip()
            raise TextExtractionError(f"Tesseract failed: {details or 'unknown error'}")
        return self._parse_tsv(result.stdout.decode("utf-8", errors="replace"), page_width, page_height)

    @staticmethod
    def _parse_tsv(tsv: str, page_width: float, page_height: float) -> tuple[str, tuple[TextWord, ...], float | None]:
        rows = list(csv.DictReader(StringIO(tsv), delimiter="\t"))
        page_row = next((row for row in rows if row.get("level") == "1"), None)
        pixel_width = max(float((page_row or {}).get("width") or 1), 1.0)
        pixel_height = max(float((page_row or {}).get("height") or 1), 1.0)
        scale_x = page_width / pixel_width
        scale_y = page_height / pixel_height
        words: list[TextWord] = []
        lines: dict[tuple[int, int, int], list[str]] = {}
        confidences: list[float] = []
        for row in rows:
            text = (row.get("text") or "").strip()
            if row.get("level") != "5" or not text:
                continue
            try:
                confidence = float(row.get("conf") or -1)
                left = float(row.get("left") or 0)
                top = float(row.get("top") or 0)
                width = float(row.get("width") or 0)
                height = float(row.get("height") or 0)
                block = int(row.get("block_num") or 0)
                paragraph = int(row.get("par_num") or 0)
                line = int(row.get("line_num") or 0)
                word = int(row.get("word_num") or 0)
            except ValueError:
                continue
            confidence_value = confidence if confidence >= 0 else None
            if confidence_value is not None:
                confidences.append(confidence_value)
            words.append(
                TextWord(
                    text=text,
                    x0=left * scale_x,
                    y0=top * scale_y,
                    x1=(left + width) * scale_x,
                    y1=(top + height) * scale_y,
                    block_number=block,
                    paragraph_number=paragraph,
                    line_number=line,
                    word_number=word,
                    confidence=confidence_value,
                )
            )
            lines.setdefault((block, paragraph, line), []).append(text)
        full_text = "\n".join(" ".join(parts) for parts in lines.values())
        return full_text, tuple(words), fmean(confidences) if confidences else None


class TextEngine:
    def __init__(
        self,
        cache_dir: str | Path | None = None,
        ocr: TesseractBackend | None = None,
        ocr_dpi: int = OCR_DPI,
    ) -> None:
        default_cache = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "PDF Analyzer" / "text-cache"
        self.cache_dir = Path(cache_dir) if cache_dir else default_cache
        self.ocr = ocr or TesseractBackend()
        self.ocr_dpi = max(150, min(int(ocr_dpi), 400))

    def audit_document(
        self, path: str | Path, document_id: str, cancel_event: Event | None = None
    ) -> DocumentText:
        """Extract native text and reuse cached OCR without starting new OCR."""
        pages: list[PageText] = []
        try:
            document = pymupdf.open(str(path))
        except Exception as exc:
            raise TextExtractionError("Documentul nu a putut fi deschis pentru analiza textului.") from exc
        try:
            for page_index in range(document.page_count):
                self._check_cancelled(cancel_event)
                cached = self._load_cache(document_id, page_index, "native")
                page_text = cached or self._extract_native(document[page_index], document_id)
                if cached is None:
                    self._save_cache(page_text, "native")
                if page_text.source == "empty":
                    page_text = self._load_cache(document_id, page_index, "ocr") or page_text
                pages.append(page_text)
        finally:
            document.close()
        return self._document_result(document_id, pages)

    def ocr_pages(
        self,
        path: str | Path,
        document_id: str,
        page_indices: tuple[int, ...],
        cancel_event: Event | None = None,
    ) -> DocumentText:
        if not self.ocr.available:
            raise TextExtractionError("Local OCR is unavailable. Check Tesseract and its language files.")
        requested = set(page_indices)
        pages: list[PageText] = []
        try:
            document = pymupdf.open(str(path))
        except Exception as exc:
            raise TextExtractionError("Documentul nu a putut fi deschis pentru OCR.") from exc
        try:
            for page_index in range(document.page_count):
                self._check_cancelled(cancel_event)
                native = self._load_cache(document_id, page_index, "native")
                if native is None:
                    native = self._extract_native(document[page_index], document_id)
                    self._save_cache(native, "native")
                if page_index not in requested or native.source == "native":
                    pages.append(native)
                    continue
                cached_ocr = self._load_cache(document_id, page_index, "ocr")
                page_text = cached_ocr or self._extract_ocr(document[page_index], document_id)
                if cached_ocr is None:
                    self._save_cache(page_text, "ocr")
                pages.append(page_text)
        finally:
            document.close()
        return self._document_result(document_id, pages)

    @staticmethod
    def _extract_native(page, document_id: str) -> PageText:
        raw_words = page.get_text("words", sort=True)
        words = tuple(
            TextWord(
                text=str(item[4]),
                x0=float(item[0]),
                y0=float(item[1]),
                x1=float(item[2]),
                y1=float(item[3]),
                block_number=int(item[5]),
                paragraph_number=0,
                line_number=int(item[6]),
                word_number=int(item[7]),
                confidence=None,
            )
            for item in raw_words
            if str(item[4]).strip()
        )
        text = page.get_text("text", sort=True).strip()
        character_count = sum(character.isalnum() for character in text)
        sparse_text_over_scan = (
            len(words) < SPARSE_TEXT_MAX_WORDS
            and character_count < SPARSE_TEXT_MAX_CHARACTERS
            and TextEngine._large_image_coverage(page) >= LARGE_IMAGE_COVERAGE
        )
        meaningful = character_count >= MIN_NATIVE_CHARACTERS and not sparse_text_over_scan
        return PageText(
            document_id=document_id,
            page_index=page.number,
            page_number=page.number + 1,
            source="native" if meaningful else "empty",
            text=text if meaningful else "",
            words=words if meaningful else (),
            language="embedded" if meaningful else "",
            mean_confidence=None,
        )

    @staticmethod
    def _large_image_coverage(page) -> float:
        page_area = max(float(page.rect.width * page.rect.height), 1.0)
        largest = 0.0
        try:
            image_info = page.get_image_info()
        except Exception:
            return 0.0
        for image in image_info:
            try:
                bounds = pymupdf.Rect(image["bbox"]) & page.rect
                largest = max(largest, float(bounds.width * bounds.height) / page_area)
            except (KeyError, TypeError, ValueError):
                continue
        return min(largest, 1.0)

    def _extract_ocr(self, page, document_id: str) -> PageText:
        requested_scale = self.ocr_dpi / 72.0
        page_area = max(float(page.rect.width * page.rect.height), 1.0)
        pixel_limit_scale = (MAX_OCR_PIXELS / page_area) ** 0.5
        scale = min(requested_scale, pixel_limit_scale)
        actual_dpi = max(72, round(scale * 72))
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        text, words, confidence = self.ocr.recognize(
            pixmap.tobytes("png"),
            float(page.rect.width),
            float(page.rect.height),
            actual_dpi,
        )
        return PageText(
            document_id=document_id,
            page_index=page.number,
            page_number=page.number + 1,
            source="ocr",
            text=text,
            words=words,
            language=self.ocr.language_label,
            mean_confidence=confidence,
        )

    @staticmethod
    def _document_result(document_id: str, pages: list[PageText]) -> DocumentText:
        native_pages = sum(page.source == "native" for page in pages)
        ocr_pages = sum(page.source == "ocr" for page in pages)
        empty_pages = tuple(page.page_index for page in pages if page.source == "empty")
        unreadable_pages = tuple(
            page.page_index for page in pages if page.source == "ocr" and not page.words
        )
        audit = TextAudit(
            document_id=document_id,
            page_count=len(pages),
            native_pages=native_pages,
            ocr_pages=ocr_pages,
            empty_pages=empty_pages,
            unreadable_pages=unreadable_pages,
            word_count=sum(len(page.words) for page in pages),
        )
        return DocumentText(audit=audit, pages=tuple(pages))

    def _cache_path(self, document_id: str, page_index: int, source: str) -> Path:
        language = self.ocr.language_label or "none"
        return self.cache_dir / document_id / (
            f"v{CACHE_VERSION}-p{page_index + 1:06d}-{source}-{language}-{self.ocr_dpi}dpi.json"
        )

    def _load_cache(self, document_id: str, page_index: int, source: str) -> PageText | None:
        path = self._cache_path(document_id, page_index, source)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            words = tuple(TextWord(**word) for word in payload.pop("words"))
            return PageText(words=words, **payload)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return None

    @staticmethod
    def _check_cancelled(cancel_event: Event | None) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise TextExtractionError("Text analysis was cancelled.")

    def _save_cache(self, page: PageText, cache_source: str) -> None:
        path = self._cache_path(page.document_id, page.page_index, cache_source)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(page), ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)
