"""Deterministic keyword parsing and coordinate-aware document search."""

from __future__ import annotations

import re
import unicodedata

from .bilingual_dictionary import BilingualDictionary
from .models import DocumentText, SearchHit, TextWord
from .search_expansion import expand_keywords
from .text_selection import selected_text, selection_rects


MAX_KEYWORDS = 100
MAX_KEYWORD_LENGTH = 80
CONTEXT_WORDS = 12


def parse_keywords(raw_text: str) -> tuple[str, ...]:
    if not raw_text.strip():
        return ()
    fragments = re.split(r"(?:\r?\n|[;,]|\s+[-•]\s+|#{1,6}\s*)", raw_text)
    keywords: list[str] = []
    seen: set[str] = set()
    for fragment in fragments:
        cleaned = re.sub(
            r"^\s*(?:(?:[-*•]+)|(?:\d+[.)])|(?:[A-Za-z][.)]))\s*",
            "",
            fragment,
        ).strip(" \t:-")
        cleaned = " ".join(cleaned.split())
        folded = cleaned.casefold()
        if not cleaned or not any(character.isalnum() for character in cleaned):
            continue
        if "keywords to search" in folded or "cuvinte cheie" in folded:
            continue
        if re.search(r"\b(?:terms?|termeni)$", folded):
            continue
        if len(cleaned) > MAX_KEYWORD_LENGTH:
            continue
        identity = _fold_text(cleaned)
        if len(identity) < 2 or identity in seen:
            continue
        seen.add(identity)
        keywords.append(cleaned)
        if len(keywords) >= MAX_KEYWORDS:
            break
    return tuple(keywords)


def _fold_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"\w+", normalized, flags=re.UNICODE))


def _word_token(word: str) -> str:
    return "".join(re.findall(r"\w+", unicodedata.normalize("NFKC", word).casefold()))


def _term_tokens(keyword: str) -> tuple[str, ...]:
    return tuple(token for token in (_word_token(part) for part in keyword.split()) if token)


def _context_range(words: tuple[TextWord, ...], start: int, end: int) -> tuple[int, int]:
    paragraph = (
        words[start].block_number,
        words[start].paragraph_number,
    )
    context_start = start
    while context_start > 0 and start - context_start < CONTEXT_WORDS:
        candidate = words[context_start - 1]
        if (candidate.block_number, candidate.paragraph_number) != paragraph:
            break
        context_start -= 1
    context_end = end
    while context_end + 1 < len(words) and context_end - end < CONTEXT_WORDS:
        candidate = words[context_end + 1]
        if (candidate.block_number, candidate.paragraph_number) != paragraph:
            break
        context_end += 1
    return context_start, context_end


def search_document(
    document: DocumentText,
    keywords: tuple[str, ...],
    expanded: bool = False,
    bilingual: bool = False,
    dictionary: BilingualDictionary | None = None,
) -> tuple[SearchHit, ...]:
    hits: list[SearchHit] = []
    seen: set[tuple[str, int, int, int]] = set()
    expansions = expand_keywords(
        keywords,
        expanded=expanded,
        bilingual=bilingual,
        dictionary=dictionary,
    )
    for expansion_index, expansion in enumerate(expansions):
        expected = _term_tokens(expansion.term)
        if not expected:
            continue
        for page in document.pages:
            tokens = tuple(_word_token(word.text) for word in page.words)
            width = len(expected)
            for start in range(0, len(tokens) - width + 1):
                if tokens[start : start + width] != expected:
                    continue
                end = start + width - 1
                paragraph = (page.words[start].block_number, page.words[start].paragraph_number)
                if any(
                    (word.block_number, word.paragraph_number) != paragraph
                    for word in page.words[start : end + 1]
                ):
                    continue
                identity = (expansion.original.casefold(), page.page_index, start, end)
                if identity in seen:
                    continue
                seen.add(identity)
                context_start, context_end = _context_range(page.words, start, end)
                context = selected_text(page.words, context_start, context_end).replace("\n", " ")
                hits.append(
                    SearchHit(
                        hit_id=f"{expansion_index}:{page.page_index}:{start}:{end}",
                        keyword=expansion.original,
                        page_index=page.page_index,
                        matched_text=selected_text(page.words, start, end),
                        context=" ".join(context.split()),
                        rects=selection_rects(page.words, start, end),
                        matched_term=expansion.term,
                        match_reason=expansion.reason,
                    )
                )
    return tuple(hits)
