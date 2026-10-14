"""Persistent editable bookmarks linked to stable PDF identities."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from uuid import uuid4


BOOKMARK_VERSION = 1


@dataclass(frozen=True, slots=True)
class PersonalBookmark:
    bookmark_id: str
    document_id: str
    title: str
    page_index: int
    x_ratio: float
    y_ratio: float
    zoom: float
    parent_id: str | None = None


class BookmarkStore:
    def __init__(self, storage_dir: str | Path | None = None) -> None:
        default_dir = (
            Path(os.environ.get("LOCALAPPDATA", Path.home()))
            / "PDF Analyzer"
            / "bookmarks"
        )
        self.storage_dir = Path(storage_dir) if storage_dir else default_dir

    def load(
        self,
        document_id: str,
        page_count: int,
    ) -> tuple[PersonalBookmark, ...]:
        path = self._path(document_id)
        if not path.is_file():
            return ()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if (
                payload.get("version") != BOOKMARK_VERSION
                or payload.get("document_id") != document_id
            ):
                return ()
            bookmarks = tuple(
                PersonalBookmark(**item) for item in payload.get("bookmarks", ())
            )
            self.validate(document_id, bookmarks, page_count)
            return bookmarks
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return ()

    def save(
        self,
        document_id: str,
        bookmarks: tuple[PersonalBookmark, ...],
        page_count: int,
    ) -> None:
        self.validate(document_id, bookmarks, page_count)
        path = self._path(document_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        payload = {
            "version": BOOKMARK_VERSION,
            "document_id": document_id,
            "bookmarks": [asdict(item) for item in bookmarks],
        }
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def validate(
        document_id: str,
        bookmarks: tuple[PersonalBookmark, ...],
        page_count: int,
    ) -> None:
        identifiers = {item.bookmark_id for item in bookmarks}
        if len(identifiers) != len(bookmarks):
            raise ValueError("Bookmark identifiers must be unique.")
        for item in bookmarks:
            if item.document_id != document_id:
                raise ValueError("The bookmark belongs to a different document.")
            if not item.title.strip() or len(item.title.strip()) > 160:
                raise ValueError("Bookmark titles must contain between 1 and 160 characters.")
            if not 0 <= item.page_index < page_count:
                raise ValueError("A bookmark references an invalid page.")
            if not 0 <= item.x_ratio <= 1 or not 0 <= item.y_ratio <= 1:
                raise ValueError("Bookmark coordinates must be normalized.")
            if not 0.25 <= item.zoom <= 2.50:
                raise ValueError("Bookmark zoom must be between 25% and 250%.")
            if item.parent_id is not None and item.parent_id not in identifiers:
                raise ValueError("A bookmark references a missing parent.")
        by_id = {item.bookmark_id: item for item in bookmarks}
        for item in bookmarks:
            visited = {item.bookmark_id}
            parent_id = item.parent_id
            while parent_id is not None:
                if parent_id in visited:
                    raise ValueError("Bookmark hierarchy contains a cycle.")
                visited.add(parent_id)
                parent_id = by_id[parent_id].parent_id

    def _path(self, document_id: str) -> Path:
        return self.storage_dir / f"{document_id}.json"


def create_bookmark(
    document_id: str,
    title: str,
    page_index: int,
    x_ratio: float,
    y_ratio: float,
    zoom: float,
    parent_id: str | None = None,
) -> PersonalBookmark:
    return PersonalBookmark(
        bookmark_id=uuid4().hex,
        document_id=document_id,
        title=" ".join(title.split()),
        page_index=page_index,
        x_ratio=max(0.0, min(float(x_ratio), 1.0)),
        y_ratio=max(0.0, min(float(y_ratio), 1.0)),
        zoom=max(0.25, min(float(zoom), 2.50)),
        parent_id=parent_id,
    )


def rename_bookmark(
    bookmarks: tuple[PersonalBookmark, ...],
    bookmark_id: str,
    title: str,
) -> tuple[PersonalBookmark, ...]:
    clean = " ".join(title.split())
    if not clean or len(clean) > 160:
        raise ValueError("Bookmark titles must contain between 1 and 160 characters.")
    return tuple(
        replace(item, title=clean) if item.bookmark_id == bookmark_id else item
        for item in bookmarks
    )


def delete_bookmark_tree(
    bookmarks: tuple[PersonalBookmark, ...],
    bookmark_id: str,
) -> tuple[PersonalBookmark, ...]:
    removed = {bookmark_id}
    changed = True
    while changed:
        descendants = {
            item.bookmark_id for item in bookmarks if item.parent_id in removed
        }
        changed = bool(descendants - removed)
        removed.update(descendants)
    return tuple(item for item in bookmarks if item.bookmark_id not in removed)


def move_bookmark(
    bookmarks: tuple[PersonalBookmark, ...],
    bookmark_id: str,
    direction: int,
) -> tuple[PersonalBookmark, ...]:
    selected = next((item for item in bookmarks if item.bookmark_id == bookmark_id), None)
    if selected is None or direction not in (-1, 1):
        return bookmarks
    siblings = [item for item in bookmarks if item.parent_id == selected.parent_id]
    position = next(
        index for index, item in enumerate(siblings) if item.bookmark_id == bookmark_id
    )
    target = position + direction
    if not 0 <= target < len(siblings):
        return bookmarks
    values = list(bookmarks)
    first = values.index(siblings[position])
    second = values.index(siblings[target])
    values[first], values[second] = values[second], values[first]
    return tuple(values)


def indent_bookmark(
    bookmarks: tuple[PersonalBookmark, ...],
    bookmark_id: str,
) -> tuple[PersonalBookmark, ...]:
    selected = next((item for item in bookmarks if item.bookmark_id == bookmark_id), None)
    if selected is None:
        return bookmarks
    siblings = [item for item in bookmarks if item.parent_id == selected.parent_id]
    position = next(
        index for index, item in enumerate(siblings) if item.bookmark_id == bookmark_id
    )
    if position == 0:
        return bookmarks
    new_parent = siblings[position - 1]
    return tuple(
        replace(item, parent_id=new_parent.bookmark_id)
        if item.bookmark_id == bookmark_id
        else item
        for item in bookmarks
    )


def outdent_bookmark(
    bookmarks: tuple[PersonalBookmark, ...],
    bookmark_id: str,
) -> tuple[PersonalBookmark, ...]:
    selected = next((item for item in bookmarks if item.bookmark_id == bookmark_id), None)
    if selected is None or selected.parent_id is None:
        return bookmarks
    parent = next(item for item in bookmarks if item.bookmark_id == selected.parent_id)
    return tuple(
        replace(item, parent_id=parent.parent_id)
        if item.bookmark_id == bookmark_id
        else item
        for item in bookmarks
    )
