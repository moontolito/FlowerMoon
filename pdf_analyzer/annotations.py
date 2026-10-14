"""Persistent local highlight storage; never writes to the source PDF."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .models import Highlight, TextRect


ANNOTATION_VERSION = 1


class HighlightStore:
    def __init__(self, storage_dir: str | Path | None = None) -> None:
        default_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "PDF Analyzer" / "annotations"
        self.storage_dir = Path(storage_dir) if storage_dir else default_dir

    def load(self, document_id: str) -> tuple[Highlight, ...]:
        path = self._path(document_id)
        if not path.is_file():
            return ()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("version") != ANNOTATION_VERSION or payload.get("document_id") != document_id:
                return ()
            highlights = []
            for item in payload.get("highlights", []):
                rects = tuple(TextRect(**rect) for rect in item.pop("rects"))
                highlights.append(Highlight(rects=rects, **item))
            return tuple(highlights)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return ()

    def create(
        self,
        document_id: str,
        page_index: int,
        text: str,
        rects: tuple[TextRect, ...],
        color: str = "#ffd54f",
    ) -> Highlight:
        if not text.strip() or not rects:
            raise ValueError("A highlight requires text and valid coordinates.")
        return Highlight(
            highlight_id=uuid4().hex,
            document_id=document_id,
            page_index=page_index,
            text=text,
            rects=rects,
            color=color,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def save(self, document_id: str, highlights: tuple[Highlight, ...]) -> None:
        if any(highlight.document_id != document_id for highlight in highlights):
            raise ValueError("The highlight belongs to a different document.")
        path = self._path(document_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        payload = {
            "version": ANNOTATION_VERSION,
            "document_id": document_id,
            "highlights": [asdict(highlight) for highlight in highlights],
        }
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    def _path(self, document_id: str) -> Path:
        return self.storage_dir / f"{document_id}.json"
