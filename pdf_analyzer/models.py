"""Stable immutable models shared by the PDF engine and Qt interface."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DocumentInfo:
    document_id: str
    name: str
    path: str
    size_bytes: int
    page_count: int
    title: str
    author: str
    is_encrypted: bool


@dataclass(frozen=True, slots=True)
class PageLayout:
    document_id: str
    page_index: int
    page_number: int
    width_points: float
    height_points: float


@dataclass(frozen=True, slots=True)
class RenderedPage:
    document_id: str
    page_index: int
    page_number: int
    page_count: int
    width_points: float
    height_points: float
    image_width: int
    image_height: int
    png_bytes: bytes


@dataclass(frozen=True, slots=True)
class TextWord:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    block_number: int
    paragraph_number: int
    line_number: int
    word_number: int
    confidence: float | None


@dataclass(frozen=True, slots=True)
class PageText:
    document_id: str
    page_index: int
    page_number: int
    source: str
    text: str
    words: tuple[TextWord, ...]
    language: str
    mean_confidence: float | None


@dataclass(frozen=True, slots=True)
class TextAudit:
    document_id: str
    page_count: int
    native_pages: int
    ocr_pages: int
    empty_pages: tuple[int, ...]
    unreadable_pages: tuple[int, ...]
    word_count: int


@dataclass(frozen=True, slots=True)
class DocumentText:
    audit: TextAudit
    pages: tuple[PageText, ...]


@dataclass(frozen=True, slots=True)
class TextRect:
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True, slots=True)
class Highlight:
    highlight_id: str
    document_id: str
    page_index: int
    text: str
    rects: tuple[TextRect, ...]
    color: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_id: str
    document_id: str
    citation_number: int
    page_index: int
    text: str
    rects: tuple[TextRect, ...]
    created_at: str
    comment: str = ""
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SearchHit:
    hit_id: str
    keyword: str
    page_index: int
    matched_text: str
    context: str
    rects: tuple[TextRect, ...]
    matched_term: str = ""
    match_reason: str = "Exact term"


@dataclass(frozen=True, slots=True)
class CategoryMatch:
    match_id: str
    category_id: str
    category_name: str
    group: str
    color: str
    page_index: int
    score: int
    strength: str
    context: str
    matched_terms: tuple[str, ...]
    reasons: tuple[str, ...]
    rects: tuple[TextRect, ...]


@dataclass(frozen=True, slots=True)
class StandardMatch:
    match_id: str
    classification: str
    reference: str
    page_index: int
    context: str
    reasons: tuple[str, ...]
    rects: tuple[TextRect, ...]
