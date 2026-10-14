"""Persistent evidence citations linked to exact PDF coordinates."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .models import Evidence, TextRect


EVIDENCE_VERSION = 2


class EvidenceStore:
    def __init__(self, storage_dir: str | Path | None = None) -> None:
        default_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "PDF Analyzer" / "evidence"
        self.storage_dir = Path(storage_dir) if storage_dir else default_dir

    def load(self, document_id: str) -> tuple[Evidence, ...]:
        path = self._path(document_id)
        if not path.is_file():
            return ()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("version") not in (1, EVIDENCE_VERSION) or payload.get("document_id") != document_id:
                return ()
            results: list[Evidence] = []
            for raw_item in payload.get("evidence", []):
                item = dict(raw_item)
                rects = tuple(TextRect(**rect) for rect in item.pop("rects"))
                item["comment"] = str(item.get("comment", ""))
                item["tags"] = tuple(item.get("tags", ()))
                results.append(Evidence(rects=rects, **item))
            return tuple(sorted(results, key=lambda item: item.citation_number))
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return ()

    def create(
        self,
        document_id: str,
        existing: tuple[Evidence, ...],
        page_index: int,
        text: str,
        rects: tuple[TextRect, ...],
        comment: str = "",
        tags: tuple[str, ...] = (),
    ) -> Evidence:
        if not text.strip() or not rects or page_index < 0:
            raise ValueError("A note requires text, a page and valid coordinates.")
        next_number = max(
            self._stored_next_number(document_id),
            max((item.citation_number for item in existing), default=0) + 1,
        )
        clean_tags = self.normalize_tags(tags)
        return Evidence(
            evidence_id=uuid4().hex,
            document_id=document_id,
            citation_number=next_number,
            page_index=page_index,
            text=text.strip(),
            rects=rects,
            created_at=datetime.now(timezone.utc).isoformat(),
            comment=comment.strip(),
            tags=clean_tags,
        )

    @staticmethod
    def normalize_tags(tags: tuple[str, ...]) -> tuple[str, ...]:
        result = []
        seen: set[str] = set()
        for raw_tag in tags:
            tag = " ".join(str(raw_tag).split()).strip(" ,;")
            identity = tag.casefold()
            if tag and identity not in seen:
                if len(tag) > 64:
                    raise ValueError("Un tag poate avea maximum 64 de caractere.")
                seen.add(identity)
                result.append(tag)
        if len(result) > 20:
            raise ValueError("A note can contain at most 20 tags.")
        return tuple(result)

    def save(self, document_id: str, evidence: tuple[Evidence, ...]) -> None:
        if any(item.document_id != document_id for item in evidence):
            raise ValueError("The note belongs to a different document.")
        citation_numbers = [item.citation_number for item in evidence]
        if len(citation_numbers) != len(set(citation_numbers)):
            raise ValueError("Note citation numbers must be unique.")
        for item in evidence:
            if self.normalize_tags(item.tags) != item.tags or not isinstance(item.comment, str):
                raise ValueError("Comentariul sau tagurile notei sunt invalide.")
        path = self._path(document_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        next_number = max(
            self._stored_next_number(document_id),
            max((item.citation_number for item in evidence), default=0) + 1,
        )
        payload = {
            "version": EVIDENCE_VERSION,
            "document_id": document_id,
            "next_citation_number": next_number,
            "evidence": [asdict(item) for item in evidence],
        }
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    def add_many(
        self,
        document_id: str,
        existing: tuple[Evidence, ...],
        drafts: tuple["EvidenceDraft", ...],
    ) -> "EvidenceBatchResult":
        """Validate, deduplicate and persist analysis notes in one atomic save."""
        updated = list(existing)
        identities = {
            self._note_identity(
                item.page_index,
                item.text,
                item.rects,
                item.tags,
            )
            for item in existing
        }
        added: list[Evidence] = []
        skipped = 0
        for draft in drafts:
            clean_tags = self.normalize_tags(draft.tags)
            identity = self._note_identity(
                draft.page_index,
                draft.text,
                draft.rects,
                clean_tags,
            )
            if identity in identities:
                skipped += 1
                continue
            note = self.create(
                document_id,
                tuple(updated),
                draft.page_index,
                draft.text,
                draft.rects,
                draft.comment,
                clean_tags,
            )
            updated.append(note)
            added.append(note)
            identities.add(identity)
        if added:
            self.save(document_id, tuple(updated))
        return EvidenceBatchResult(tuple(updated), tuple(added), skipped)

    def _path(self, document_id: str) -> Path:
        return self.storage_dir / f"{document_id}.json"

    def _stored_next_number(self, document_id: str) -> int:
        path = self._path(document_id)
        if not path.is_file():
            return 1
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return max(1, int(payload.get("next_citation_number", 1)))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return 1

    @staticmethod
    def _note_identity(
        page_index: int,
        text: str,
        rects: tuple[TextRect, ...],
        tags: tuple[str, ...],
    ) -> tuple[object, ...]:
        normalized_text = " ".join(text.split()).casefold()
        normalized_rects = tuple(
            (
                round(rect.x0, 3),
                round(rect.y0, 3),
                round(rect.x1, 3),
                round(rect.y1, 3),
            )
            for rect in rects
        )
        normalized_tags = tuple(sorted(tag.casefold() for tag in tags))
        return page_index, normalized_text, normalized_rects, normalized_tags


@dataclass(frozen=True, slots=True)
class EvidenceDraft:
    page_index: int
    text: str
    rects: tuple[TextRect, ...]
    comment: str
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceBatchResult:
    evidence: tuple[Evidence, ...]
    added: tuple[Evidence, ...]
    skipped_count: int
