"""Transparent offline expansion of English technical search terms."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .bilingual_dictionary import BilingualDictionary, default_dictionary


@dataclass(frozen=True, slots=True)
class SearchExpansion:
    original: str
    term: str
    reason: str


CONCEPT_GROUPS = (
    ("certificate", "certificates", "certification", "certifications", "certified"),
    ("inspection", "inspections", "inspect", "inspected", "inspector", "inspectors"),
    (
        "subcontractor", "subcontractors", "subcontracting", "subcontracted",
        "subcontract", "subcontracts", "supplier", "suppliers", "vendor", "vendors",
    ),
    ("requirement", "requirements", "required", "require"),
    ("weld", "welding", "welder", "welders", "weldment"),
    ("test", "tests", "testing", "tested"),
    ("audit", "audits", "audited", "auditing"),
    ("approval", "approvals", "approve", "approved"),
    ("corrosion", "corrosive", "corrosion resistance"),
    ("delivery", "deliveries", "deliver", "delivered"),
    ("document", "documents", "documentation"),
)

ABBREVIATION_GROUPS = (
    ("welding procedure specification", "WPS"),
    ("procedure qualification record", "PQR"),
    ("welding procedure qualification record", "WPQR"),
    ("post weld heat treatment", "PWHT"),
    ("inspection and test plan", "ITP"),
    ("factory acceptance test", "FAT"),
    ("site acceptance test", "SAT"),
    ("material test certificate", "MTC"),
    ("material test report", "MTR"),
    ("non-conformance report", "NCR"),
    ("safety data sheet", "SDS"),
    ("material safety data sheet", "MSDS"),
    ("declaration of conformity", "DoC"),
    ("certificate of conformity", "CoC"),
)


def _identity(value: str) -> str:
    return " ".join(re.findall(r"\w+", value.casefold()))


def _safe_number_variants(term: str) -> tuple[str, ...]:
    if not re.fullmatch(r"[A-Za-z]{4,}", term):
        return ()
    folded = term.casefold()
    if folded.endswith("ies") and len(term) > 4:
        return (term[:-3] + "y",)
    if folded.endswith("s") and not folded.endswith(("ss", "us")):
        return (term[:-1],)
    if folded.endswith(("ch", "sh", "x", "z")):
        return (term + "es",)
    if folded.endswith("y") and len(term) > 4 and folded[-2] not in "aeiou":
        return (term[:-1] + "ies",)
    return (term + "s",)


def expand_keywords(
    keywords: tuple[str, ...],
    expanded: bool = True,
    bilingual: bool = False,
    dictionary: BilingualDictionary | None = None,
) -> tuple[SearchExpansion, ...]:
    result: list[SearchExpansion] = []
    active_dictionary = dictionary or default_dictionary()
    for original in keywords:
        seen: set[str] = set()
        generated_terms: list[str] = []

        def add(term: str, reason: str) -> None:
            identity = _identity(term)
            if identity and identity not in seen:
                seen.add(identity)
                result.append(SearchExpansion(original, term, reason))
                generated_terms.append(term)

        add(original, "Exact term")
        original_identity = _identity(original)
        if bilingual:
            for entry in active_dictionary.entries:
                if original_identity not in {_identity(term) for term in entry.all_terms}:
                    continue
                for term in entry.all_terms:
                    add(
                        term,
                        f'Bilingual dictionary · {entry.name} · from "{original}"',
                    )
        if not expanded:
            continue
        for source_term in tuple(generated_terms):
            source_identity = _identity(source_term)
            for group in CONCEPT_GROUPS:
                if source_identity in {_identity(term) for term in group}:
                    for term in group:
                        add(term, f'Technical dictionary expansion from "{source_term}"')
            for group in ABBREVIATION_GROUPS:
                if source_identity in {_identity(term) for term in group}:
                    for term in group:
                        add(term, f'Abbreviation expansion from "{source_term}"')
            for variant in _safe_number_variants(source_term):
                add(variant, f'Grammatical number variant of "{source_term}"')
    return tuple(result)
