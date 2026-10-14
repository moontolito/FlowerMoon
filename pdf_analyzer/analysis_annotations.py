"""Convert deterministic analysis results into persistent tagged note drafts."""

from __future__ import annotations

from .evidence import EvidenceDraft
from .models import CategoryMatch, StandardMatch, TextRect


def _position(rects: tuple[TextRect, ...]) -> tuple[float, float]:
    if not rects:
        return float("inf"), float("inf")
    return min((rect.y0, rect.x0) for rect in rects)


def category_evidence_drafts(
    matches: tuple[CategoryMatch, ...],
) -> tuple[EvidenceDraft, ...]:
    ordered = sorted(
        matches,
        key=lambda match: (
            match.page_index,
            *_position(match.rects),
            match.category_name.casefold(),
            match.match_id,
        ),
    )
    return tuple(
        EvidenceDraft(
            page_index=match.page_index,
            text=match.context,
            rects=match.rects,
            comment=(
                f"Automatically detected by Categories: {match.category_name}. "
                f"Relevance: {match.strength} ({match.score}). "
                f"Reasons: {'; '.join(match.reasons)}"
            ),
            tags=(match.category_name,),
        )
        for match in ordered
    )


def standard_evidence_drafts(
    matches: tuple[StandardMatch, ...],
) -> tuple[EvidenceDraft, ...]:
    ordered = sorted(
        matches,
        key=lambda match: (
            match.page_index,
            *_position(match.rects),
            match.classification.casefold(),
            match.reference.casefold(),
            match.match_id,
        ),
    )
    return tuple(
        EvidenceDraft(
            page_index=match.page_index,
            text=match.context,
            rects=match.rects,
            comment=(
                f"Automatically detected by Standards: {match.classification}. "
                f"Reference: {match.reference}. "
                f"Reasons: {'; '.join(match.reasons)}"
            ),
            tags=(match.classification, match.reference),
        )
        for match in ordered
    )
