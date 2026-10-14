"""Deterministic recognition of standards, certificates and technical documents."""

from __future__ import annotations

import re
import unicodedata

from .models import DocumentText, StandardMatch, TextWord
from .text_selection import selected_text, selection_rects


STANDARD_FAMILIES = frozenset(
    {"ISO", "EN", "DIN", "IEC", "ASTM", "ANSI", "BS", "NF", "JIS", "API", "NACE", "SAE"}
)
MATERIAL_CERTIFICATES = frozenset({"2.1", "2.2", "3.1", "3.2"})
DOCUMENT_CODES = frozenset(
    {"TDS", "SDS", "MSDS", "DOC", "DOP", "COC", "COA", "MTC", "CMTR"}
)
OBLIGATION_PHRASES = (
    "shall provide", "shall submit", "must provide", "must submit", "shall comply",
    "must comply", "shall conform", "is required",
    "required to", "trebuie", "va furniza", "va transmite",
)
DOCUMENT_WORDS = (
    "datasheet", "certificate", "certification", "approval", "accreditation",
    "compliance", "conformity", "traceability",
)


def _token(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip(".,;:()[]{}")
    return normalized


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).casefold()
    return "".join(character for character in normalized if not unicodedata.combining(character))


def _paragraphs(words: tuple[TextWord, ...]) -> tuple[tuple[int, int], ...]:
    if not words:
        return ()
    result = []
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


def _classification(kind: str, paragraph: str) -> tuple[str, tuple[str, ...]]:
    folded = _fold(paragraph)
    obligation = next((phrase for phrase in OBLIGATION_PHRASES if phrase in folded), None)
    if kind == "certificate":
        title = "Required Material Certificate" if obligation else "Material Certificate Reference"
    elif kind == "document":
        title = "Required Technical Document" if obligation else "Technical Document Reference"
    else:
        title = "Mandatory Standard" if obligation or "applicable" in folded else "Standard Reference"
    reasons = [f"Detected as {title.lower()}"]
    if obligation:
        reasons.append(f'Obligation context: "{obligation}"')
    return title, tuple(reasons)


def analyze_standards(document: DocumentText) -> tuple[StandardMatch, ...]:
    results: list[StandardMatch] = []
    for page in document.pages:
        words = page.words
        for paragraph_start, paragraph_end in _paragraphs(words):
            paragraph_words = words[paragraph_start : paragraph_end + 1]
            paragraph = " ".join(selected_text(words, paragraph_start, paragraph_end).split())
            folded_paragraph = _fold(paragraph)
            found: set[tuple[int, int, str]] = set()
            for relative, word in enumerate(paragraph_words):
                index = paragraph_start + relative
                token = _token(word.text)
                upper = token.upper()
                if upper in STANDARD_FAMILIES:
                    end = index
                    numeric_found = False
                    for candidate_index in range(index + 1, min(paragraph_end + 1, index + 4)):
                        candidate = _token(words[candidate_index].text)
                        if not candidate or not re.search(r"[A-Za-z0-9]", candidate):
                            break
                        if candidate.casefold() in {"and", "or"}:
                            break
                        if candidate.upper() in STANDARD_FAMILIES and not numeric_found:
                            end = candidate_index
                            continue
                        if numeric_found:
                            break
                        end = candidate_index
                        if re.search(r"\d", candidate):
                            numeric_found = True
                    reference = " ".join(_token(words[item].text) for item in range(index, end + 1))
                    found.add((index, end, "standard:" + reference))
                normalized_certificate = token.replace(",", ".")
                if normalized_certificate in MATERIAL_CERTIFICATES and (
                    "certificate" in folded_paragraph or "10204" in folded_paragraph
                ):
                    found.add((index, index, "certificate:" + normalized_certificate))
                if upper in DOCUMENT_CODES or _fold(token) in DOCUMENT_WORDS:
                    found.add((index, index, "document:" + token))

            for start, end, identity in sorted(found):
                kind, reference = identity.split(":", 1)
                classification, reasons = _classification(kind, paragraph)
                results.append(
                    StandardMatch(
                        match_id=f"{page.page_index}:{start}:{end}:{kind}",
                        classification=classification,
                        reference=reference,
                        page_index=page.page_index,
                        context=paragraph,
                        reasons=reasons,
                        rects=selection_rects(words, start, end),
                    )
                )
    return tuple(results)
