"""Deterministic filtering of repeated PDF page furniture for analysis."""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, replace

from .models import DocumentText, PageText, TextWord
from .text_selection import selected_text


HEADER_RATIO = 0.08
FOOTER_RATIO = 0.92
REPEAT_PAGE_RATIO = 0.60


@dataclass(frozen=True, slots=True)
class SearchNoiseOptions:
    ignore_headers: bool = True
    ignore_footers: bool = True
    ignore_page_numbers: bool = True
    hide_repeated_text: bool = True


@dataclass(frozen=True, slots=True)
class SearchNoiseReport:
    original_word_count: int
    retained_word_count: int
    header_words: int
    footer_words: int
    page_number_words: int
    repeated_words: int
    repeated_block_count: int
    mask_words: int = 0

    @property
    def excluded_word_count(self) -> int:
        return self.original_word_count - self.retained_word_count


def _paragraph_ranges(words: tuple[TextWord, ...]) -> tuple[tuple[int, int], ...]:
    if not words:
        return ()
    result: list[tuple[int, int]] = []
    start = 0
    identity = (words[0].block_number, words[0].paragraph_number)
    for index, word in enumerate(words[1:], start=1):
        candidate = (word.block_number, word.paragraph_number)
        if candidate != identity:
            result.append((start, index - 1))
            start = index
            identity = candidate
    result.append((start, len(words) - 1))
    return tuple(result)


def _normalized_block(words: tuple[TextWord, ...], start: int, end: int) -> str:
    value = selected_text(words, start, end)
    value = unicodedata.normalize("NFKD", value).casefold()
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = re.sub(r"\d+", "#", value)
    return " ".join(re.findall(r"\w+|#", value, flags=re.UNICODE))


def _page_number_block(value: str) -> bool:
    compact = " ".join(value.casefold().split())
    return bool(
        re.fullmatch(
            r"(?:page|pagina|pag\.?)?\s*(?:\d+|[ivxlcdm]+)"
            r"(?:\s*(?:of|din|/|-)\s*(?:\d+|[ivxlcdm]+))?",
            compact,
        )
    )


def _repeated_blocks(
    document: DocumentText,
    page_heights: tuple[float, ...],
) -> frozenset[str]:
    if len(document.pages) < 2:
        return frozenset()
    occurrences: dict[str, set[int]] = {}
    for page in document.pages:
        height = (
            float(page_heights[page.page_index])
            if 0 <= page.page_index < len(page_heights) and page_heights[page.page_index] > 0
            else max((word.y1 for word in page.words), default=1.0)
        )
        for start, end in _paragraph_ranges(page.words):
            normalized = _normalized_block(page.words, start, end)
            token_count = len(normalized.split())
            if not normalized or token_count < 3 or token_count > 40 or len(normalized) > 240:
                continue
            center = sum(
                (page.words[index].y0 + page.words[index].y1) / 2
                for index in range(start, end + 1)
            ) / (end - start + 1)
            near_edge = center <= height * 0.10 or center >= height * 0.90
            table_furniture = bool(
                re.search(
                    r"\b(?:revision|rev|confidential|document\s+(?:no|number)|"
                    r"project\s+(?:no|number)|drawing\s+(?:no|number))\b",
                    normalized,
                )
            )
            if not near_edge and not table_furniture:
                continue
            occurrences.setdefault(normalized, set()).add(page.page_index)
    threshold = max(2, math.ceil(len(document.pages) * REPEAT_PAGE_RATIO))
    return frozenset(
        value for value, pages in occurrences.items() if len(pages) >= threshold
    )


def filter_document_for_analysis(
    document: DocumentText,
    page_heights: tuple[float, ...],
    options: SearchNoiseOptions,
) -> tuple[DocumentText, SearchNoiseReport]:
    """Return a coordinate-preserving analysis view and an exclusion report."""
    repeated = (
        _repeated_blocks(document, page_heights)
        if options.hide_repeated_text
        else frozenset()
    )
    counts = {"header": 0, "footer": 0, "page_number": 0, "repeated": 0}
    filtered_pages: list[PageText] = []

    for page in document.pages:
        height = (
            float(page_heights[page.page_index])
            if 0 <= page.page_index < len(page_heights) and page_heights[page.page_index] > 0
            else max((word.y1 for word in page.words), default=1.0)
        )
        excluded: dict[int, str] = {}
        for index, word in enumerate(page.words):
            center = (word.y0 + word.y1) / 2
            if options.ignore_headers and center <= height * HEADER_RATIO:
                excluded[index] = "header"
            elif options.ignore_footers and center >= height * FOOTER_RATIO:
                excluded[index] = "footer"

        for start, end in _paragraph_ranges(page.words):
            indices = range(start, end + 1)
            normalized = _normalized_block(page.words, start, end)
            center = sum(
                (page.words[index].y0 + page.words[index].y1) / 2 for index in indices
            ) / (end - start + 1)
            near_edge = center <= height * 0.18 or center >= height * 0.82
            raw = " ".join(word.text for word in page.words[start : end + 1])
            if options.ignore_page_numbers and near_edge and _page_number_block(raw):
                for index in indices:
                    excluded.setdefault(index, "page_number")
            if normalized in repeated:
                for index in indices:
                    excluded.setdefault(index, "repeated")

        for reason in excluded.values():
            counts[reason] += 1
        retained = tuple(
            word for index, word in enumerate(page.words) if index not in excluded
        )
        filtered_pages.append(
            replace(
                page,
                text=" ".join(word.text for word in retained),
                words=retained,
            )
        )

    original_count = sum(len(page.words) for page in document.pages)
    retained_count = sum(len(page.words) for page in filtered_pages)
    filtered = DocumentText(
        audit=replace(document.audit, word_count=retained_count),
        pages=tuple(filtered_pages),
    )
    return filtered, SearchNoiseReport(
        original_word_count=original_count,
        retained_word_count=retained_count,
        header_words=counts["header"],
        footer_words=counts["footer"],
        page_number_words=counts["page_number"],
        repeated_words=counts["repeated"],
        repeated_block_count=len(repeated),
    )
