"""Deterministic page-layout similarity and explicit page-range parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import DocumentText


GRID_COLUMNS = 6
GRID_ROWS = 8
DEFAULT_SIMILARITY_THRESHOLD = 0.78


@dataclass(frozen=True, slots=True)
class SimilarPage:
    page_index: int
    score: float


def parse_page_selection(value: str, page_count: int) -> tuple[int, ...]:
    """Parse one-based values such as ``1, 3-5`` into unique zero-based pages."""
    if page_count < 1:
        raise ValueError("The document has no pages.")
    result: list[int] = []
    seen: set[int] = set()
    for fragment in value.split(","):
        token = fragment.strip()
        if not token:
            continue
        match = re.fullmatch(r"(\d+)(?:\s*-\s*(\d+))?", token)
        if not match:
            raise ValueError(f'Invalid page selection: "{token}".')
        first = int(match.group(1))
        last = int(match.group(2) or first)
        if first > last:
            raise ValueError("Page ranges must be written from lower to higher.")
        if first < 1 or last > page_count:
            raise ValueError(f"Pages must be between 1 and {page_count}.")
        for page_number in range(first, last + 1):
            page_index = page_number - 1
            if page_index not in seen:
                seen.add(page_index)
                result.append(page_index)
    if not result:
        raise ValueError("Enter at least one page number.")
    return tuple(result)


def _signature(
    document: DocumentText,
    page_index: int,
    page_sizes: tuple[tuple[float, float], ...],
) -> tuple[frozenset[int], float, float]:
    page = next(page for page in document.pages if page.page_index == page_index)
    width, height = page_sizes[page_index]
    width = max(float(width), 1.0)
    height = max(float(height), 1.0)
    occupied: set[int] = set()
    for word in page.words:
        x = max(0.0, min(((word.x0 + word.x1) / 2) / width, 0.999999))
        y = max(0.0, min(((word.y0 + word.y1) / 2) / height, 0.999999))
        column = int(x * GRID_COLUMNS)
        row = int(y * GRID_ROWS)
        occupied.add(row * GRID_COLUMNS + column)
    density = min(len(page.words) / 500.0, 1.0)
    aspect = width / height
    return frozenset(occupied), density, aspect


def find_similar_pages(
    document: DocumentText,
    page_sizes: tuple[tuple[float, float], ...],
    source_page_index: int,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> tuple[SimilarPage, ...]:
    if not 0 <= source_page_index < len(page_sizes):
        raise ValueError("The source page is invalid.")
    source_grid, source_density, source_aspect = _signature(
        document, source_page_index, page_sizes
    )
    results: list[SimilarPage] = []
    for page_index in range(len(page_sizes)):
        if page_index == source_page_index:
            continue
        grid, density, aspect = _signature(document, page_index, page_sizes)
        union = source_grid | grid
        grid_score = len(source_grid & grid) / len(union) if union else 1.0
        density_score = 1.0 - min(abs(source_density - density), 1.0)
        aspect_score = 1.0 - min(
            abs(source_aspect - aspect) / max(source_aspect, aspect, 0.01),
            1.0,
        )
        score = grid_score * 0.60 + density_score * 0.25 + aspect_score * 0.15
        if score >= threshold:
            results.append(SimilarPage(page_index, round(score, 4)))
    return tuple(sorted(results, key=lambda item: (-item.score, item.page_index)))

