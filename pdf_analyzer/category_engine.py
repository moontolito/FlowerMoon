"""Deterministic paragraph and proximity analysis for editable categories."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .categories import CategoryDefinition, CategoryProfile
from .models import CategoryMatch, DocumentText, TextRect, TextWord
from .text_selection import selected_text, selection_rects


CONTEXT_WINDOW = 40
DISPLAY_CONTEXT_WORDS = 18


@dataclass(frozen=True, slots=True)
class _TermHit:
    term: str
    start: int
    end: int


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).casefold()
    value = "".join(character for character in value if not unicodedata.combining(character))
    return "".join(re.findall(r"\w+", value, flags=re.UNICODE))


def _term_tokens(term: str) -> tuple[str, ...]:
    return tuple(token for token in (_fold(part) for part in term.split()) if token)


def _find_terms(tokens: tuple[str, ...], terms: tuple[str, ...]) -> tuple[_TermHit, ...]:
    hits: list[_TermHit] = []
    for term in terms:
        expected = _term_tokens(term)
        if not expected:
            continue
        width = len(expected)
        for start in range(len(tokens) - width + 1):
            if tokens[start : start + width] == expected:
                hits.append(_TermHit(term, start, start + width - 1))
    return tuple(hits)


def _paragraphs(words: tuple[TextWord, ...]) -> tuple[tuple[int, int], ...]:
    if not words:
        return ()
    ranges: list[tuple[int, int]] = []
    start = 0
    identity = (words[0].block_number, words[0].paragraph_number)
    for index, word in enumerate(words[1:], start=1):
        candidate = (word.block_number, word.paragraph_number)
        if candidate != identity:
            ranges.append((start, index - 1))
            start = index
            identity = candidate
    ranges.append((start, len(words) - 1))
    return tuple(ranges)


def _unique_rects(words: tuple[TextWord, ...], hits: tuple[_TermHit, ...]) -> tuple[TextRect, ...]:
    result: list[TextRect] = []
    identities: set[tuple[float, float, float, float]] = set()
    for hit in hits:
        for rect in selection_rects(words, hit.start, hit.end):
            identity = (rect.x0, rect.y0, rect.x1, rect.y1)
            if identity not in identities:
                identities.add(identity)
                result.append(rect)
    return tuple(result)


def _analyze_paragraph(
    category: CategoryDefinition,
    page_index: int,
    words: tuple[TextWord, ...],
    paragraph_start: int,
    paragraph_end: int,
    subject_hits: tuple[_TermHit, ...],
    context_hits: tuple[_TermHit, ...],
) -> CategoryMatch:
    distinct_subjects = tuple(dict.fromkeys(hit.term for hit in subject_hits))
    score = min(6, len(subject_hits) * 2)
    reasons = [f"Termen: {term}" for term in distinct_subjects]
    if any(len(_term_tokens(hit.term)) > 1 for hit in subject_hits):
        score += 3
        reasons.append("Exact phrase")
    if len(distinct_subjects) >= 2:
        score += 4
        reasons.append(f"{len(distinct_subjects)} terms in the same paragraph")

    same_paragraph = tuple(
        hit for hit in context_hits if paragraph_start <= hit.start <= paragraph_end
    )
    nearest: _TermHit | None = None
    nearest_distance: int | None = None
    for context_hit in context_hits:
        distance = min(
            abs(context_hit.start - subject.end)
            if context_hit.start > subject.end
            else abs(subject.start - context_hit.end)
            for subject in subject_hits
        )
        if nearest_distance is None or distance < nearest_distance:
            nearest = context_hit
            nearest_distance = distance
    if same_paragraph:
        distinct_context = tuple(dict.fromkeys(hit.term for hit in same_paragraph))
        score += 6
        reasons.append(f"Obligation context in the same paragraph: {', '.join(distinct_context[:3])}")
    elif nearest is not None and nearest_distance is not None and nearest_distance <= CONTEXT_WINDOW:
        score += 4
        reasons.append(f'Context "{nearest.term}" within {nearest_distance} words')
    elif nearest is not None:
        score += 1
        reasons.append("Relevant context on the same page")

    strength = "high" if score >= 10 else "medium" if score >= 6 else "low"
    context_start = max(paragraph_start, min(hit.start for hit in subject_hits) - DISPLAY_CONTEXT_WORDS)
    context_end = min(paragraph_end, max(hit.end for hit in subject_hits) + DISPLAY_CONTEXT_WORDS)
    context = " ".join(selected_text(words, context_start, context_end).split())
    visible_context_hits = tuple(hit for hit in same_paragraph if hit.start <= context_end)
    rects = _unique_rects(words, subject_hits + visible_context_hits)
    return CategoryMatch(
        match_id=f"{category.category_id}:{page_index}:{paragraph_start}",
        category_id=category.category_id,
        category_name=category.display_name,
        group=category.group,
        color=category.color,
        page_index=page_index,
        score=score,
        strength=strength,
        context=context,
        matched_terms=distinct_subjects,
        reasons=tuple(reasons),
        rects=rects,
    )


def analyze_categories(
    document: DocumentText, profile: CategoryProfile
) -> tuple[CategoryMatch, ...]:
    """Return one explainable result per category and matching paragraph."""
    results: list[CategoryMatch] = []
    for page in document.pages:
        words = page.words
        tokens = tuple(_fold(word.text) for word in words)
        for category in profile.categories:
            if not category.enabled:
                continue
            page_subjects = _find_terms(tokens, category.subject_terms)
            if not page_subjects:
                continue
            page_contexts = _find_terms(tokens, category.context_terms)
            for paragraph_start, paragraph_end in _paragraphs(words):
                paragraph_subjects = tuple(
                    hit
                    for hit in page_subjects
                    if paragraph_start <= hit.start and hit.end <= paragraph_end
                )
                if paragraph_subjects:
                    results.append(
                        _analyze_paragraph(
                            category,
                            page.page_index,
                            words,
                            paragraph_start,
                            paragraph_end,
                            paragraph_subjects,
                            page_contexts,
                        )
                    )
    return tuple(sorted(results, key=lambda match: (-match.score, match.page_index, match.match_id)))
