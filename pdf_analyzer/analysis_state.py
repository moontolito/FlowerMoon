"""Portable JSON state for categories, search terms and the bilingual dictionary."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .bilingual_dictionary import (
    BilingualDictionary,
    BilingualDictionaryStore,
    default_dictionary,
    dictionary_from_payload,
)
from .categories import (
    PROFILE_SCHEMA_VERSION,
    CategoryDefinition,
    CategoryProfile,
    CategoryProfileStore,
    upgrade_profile,
)
from .noise_filter import SearchNoiseOptions


STATE_SCHEMA_VERSION = 3
MAX_STATE_BYTES = 2 * 1024 * 1024


class AnalysisStateError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AnalysisState:
    profile: CategoryProfile
    keyword_text: str
    bilingual_dictionary: BilingualDictionary
    noise_options: SearchNoiseOptions = SearchNoiseOptions()


def save_analysis_state(
    path_value: str | Path,
    profile: CategoryProfile,
    keyword_text: str,
    bilingual_dictionary: BilingualDictionary | None = None,
    noise_options: SearchNoiseOptions | None = None,
) -> None:
    CategoryProfileStore.validate(profile)
    active_dictionary = bilingual_dictionary or default_dictionary()
    BilingualDictionaryStore.validate(active_dictionary)
    path = Path(path_value)
    payload = {
        "state_schema_version": STATE_SCHEMA_VERSION,
        "profile": asdict(profile),
        "keyword_text": keyword_text,
        "bilingual_dictionary": asdict(active_dictionary),
        "noise_options": asdict(noise_options or SearchNoiseOptions()),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def load_analysis_state(path_value: str | Path) -> AnalysisState:
    path = Path(path_value)
    if not path.is_file() or path.stat().st_size > MAX_STATE_BYTES:
        raise AnalysisStateError("The profile file is missing or exceeds the 2 MB limit.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        state_version = payload.get("state_schema_version")
        if state_version not in (1, 2, STATE_SCHEMA_VERSION):
            raise AnalysisStateError("The profile file version is not supported.")
        raw_profile = dict(payload["profile"])
        raw_categories = raw_profile.pop("categories")
        categories = []
        for raw_category in raw_categories:
            category = dict(raw_category)
            for field in ("terms_ro", "terms_en", "context_ro", "context_en"):
                category[field] = tuple(category[field])
            categories.append(CategoryDefinition(**category))
        profile = upgrade_profile(CategoryProfile(categories=tuple(categories), **raw_profile))
        keyword_text = payload.get("keyword_text", "")
        if not isinstance(keyword_text, str) or len(keyword_text) > 100_000:
            raise AnalysisStateError("The saved search list is invalid.")
        if profile.schema_version != PROFILE_SCHEMA_VERSION:
            raise AnalysisStateError("The category profile is not compatible.")
        CategoryProfileStore.validate(profile)
        dictionary = (
            default_dictionary()
            if state_version == 1
            else dictionary_from_payload(payload["bilingual_dictionary"])
        )
        BilingualDictionaryStore.validate(dictionary)
        noise_options = (
            SearchNoiseOptions()
            if state_version < 3
            else SearchNoiseOptions(**payload["noise_options"])
        )
        if not all(
            isinstance(value, bool)
            for value in (
                noise_options.ignore_headers,
                noise_options.ignore_footers,
                noise_options.ignore_page_numbers,
                noise_options.hide_repeated_text,
            )
        ):
            raise AnalysisStateError("The saved noise-filter options are invalid.")
        return AnalysisState(profile, keyword_text, dictionary, noise_options)
    except AnalysisStateError:
        raise
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise AnalysisStateError("The profile file is invalid or corrupted.") from exc
