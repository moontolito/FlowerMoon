"""Persistent normalized visual masks for coordinate-aware PDF analysis."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from uuid import uuid4

from .models import DocumentText


MASK_VERSION = 2
MASK_PROFILE_VERSION = 2
MASK_KINDS = frozenset({"ignore", "keep"})
MASK_SHAPES = frozenset({"rectangle", "freehand", "polygon"})
MIN_MASK_SIZE = 0.005


class AreaMaskError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AreaMask:
    mask_id: str
    document_id: str
    kind: str
    page_index: int | None
    x0_ratio: float
    y0_ratio: float
    x1_ratio: float
    y1_ratio: float
    shape: str = "rectangle"
    points: tuple[tuple[float, float], ...] = ()


def _mask_from_payload(
    item: dict,
    document_id: str | None = None,
) -> AreaMask:
    values = dict(item)
    values.setdefault("shape", "rectangle")
    values["points"] = tuple(
        (float(point[0]), float(point[1]))
        for point in values.get("points", ())
    )
    if document_id is not None:
        values["document_id"] = document_id
        values["mask_id"] = uuid4().hex
    return AreaMask(**values)


class AreaMaskStore:
    def __init__(self, storage_dir: str | Path | None = None) -> None:
        default_dir = (
            Path(os.environ.get("LOCALAPPDATA", Path.home()))
            / "PDF Analyzer"
            / "masks"
        )
        self.storage_dir = Path(storage_dir) if storage_dir else default_dir

    def load(self, document_id: str, page_count: int) -> tuple[AreaMask, ...]:
        path = self._path(document_id)
        if not path.is_file():
            return ()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if (
                payload.get("version") not in (1, MASK_VERSION)
                or payload.get("document_id") != document_id
            ):
                return ()
            masks = tuple(
                _mask_from_payload(item) for item in payload.get("masks", ())
            )
            self.validate(document_id, masks, page_count)
            return masks
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return ()

    def save(
        self,
        document_id: str,
        masks: tuple[AreaMask, ...],
        page_count: int,
    ) -> None:
        self.validate(document_id, masks, page_count)
        path = self._path(document_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "version": MASK_VERSION,
                    "document_id": document_id,
                    "masks": [asdict(mask) for mask in masks],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def validate(
        document_id: str,
        masks: tuple[AreaMask, ...],
        page_count: int,
    ) -> None:
        identifiers = {mask.mask_id for mask in masks}
        if len(identifiers) != len(masks):
            raise AreaMaskError("Mask identifiers must be unique.")
        for mask in masks:
            if mask.document_id != document_id:
                raise AreaMaskError("A mask belongs to another document.")
            if mask.kind not in MASK_KINDS:
                raise AreaMaskError("Mask type must be keep or ignore.")
            if mask.shape not in MASK_SHAPES:
                raise AreaMaskError("Mask shape is not supported.")
            if mask.page_index is not None and not 0 <= mask.page_index < page_count:
                raise AreaMaskError("A mask references an invalid page.")
            values = (
                mask.x0_ratio,
                mask.y0_ratio,
                mask.x1_ratio,
                mask.y1_ratio,
            )
            if not all(isinstance(value, (int, float)) and 0 <= value <= 1 for value in values):
                raise AreaMaskError("Mask coordinates must be normalized.")
            if (
                mask.x1_ratio - mask.x0_ratio < MIN_MASK_SIZE
                or mask.y1_ratio - mask.y0_ratio < MIN_MASK_SIZE
            ):
                raise AreaMaskError("The selected mask area is too small.")
            if mask.shape == "rectangle" and mask.points:
                raise AreaMaskError("Rectangle masks cannot contain path points.")
            if mask.shape != "rectangle":
                if len(mask.points) < 3:
                    raise AreaMaskError("Path masks require at least three points.")
                if not all(
                    len(point) == 2
                    and all(
                        isinstance(value, (int, float)) and 0 <= value <= 1
                        for value in point
                    )
                    for point in mask.points
                ):
                    raise AreaMaskError("Mask path points must be normalized.")
                area = abs(
                    sum(
                        x0 * y1 - x1 * y0
                        for (x0, y0), (x1, y1) in zip(
                            mask.points,
                            mask.points[1:] + mask.points[:1],
                        )
                    )
                    / 2
                )
                if area < MIN_MASK_SIZE * MIN_MASK_SIZE:
                    raise AreaMaskError("The selected path is degenerate.")

    def _path(self, document_id: str) -> Path:
        return self.storage_dir / f"{document_id}.json"


def create_area_mask(
    document_id: str,
    kind: str,
    page_index: int | None,
    x0_ratio: float,
    y0_ratio: float,
    x1_ratio: float,
    y1_ratio: float,
) -> AreaMask:
    left, right = sorted((float(x0_ratio), float(x1_ratio)))
    top, bottom = sorted((float(y0_ratio), float(y1_ratio)))
    mask = AreaMask(
        uuid4().hex,
        document_id,
        kind,
        page_index,
        max(0.0, left),
        max(0.0, top),
        min(1.0, right),
        min(1.0, bottom),
    )
    AreaMaskStore.validate(
        document_id,
        (mask,),
        page_index + 1 if page_index is not None else 1,
    )
    return mask


def create_path_mask(
    document_id: str,
    kind: str,
    page_index: int | None,
    shape: str,
    points: tuple[tuple[float, float], ...],
) -> AreaMask:
    if shape not in {"freehand", "polygon"}:
        raise AreaMaskError("Path mask type must be freehand or polygon.")
    normalized = tuple(
        (
            max(0.0, min(float(point[0]), 1.0)),
            max(0.0, min(float(point[1]), 1.0)),
        )
        for point in points
    )
    if not normalized:
        raise AreaMaskError("The mask path is empty.")
    x_values = tuple(point[0] for point in normalized)
    y_values = tuple(point[1] for point in normalized)
    mask = AreaMask(
        uuid4().hex,
        document_id,
        kind,
        page_index,
        min(x_values),
        min(y_values),
        max(x_values),
        max(y_values),
        shape,
        normalized,
    )
    AreaMaskStore.validate(
        document_id,
        (mask,),
        page_index + 1 if page_index is not None else 1,
    )
    return mask


def copy_mask_to_page(mask: AreaMask, page_index: int | None) -> AreaMask:
    return replace(mask, mask_id=uuid4().hex, page_index=page_index)


def mask_geometry_identity(mask: AreaMask) -> tuple:
    return (
        mask.kind,
        mask.page_index,
        mask.shape,
        round(mask.x0_ratio, 6),
        round(mask.y0_ratio, 6),
        round(mask.x1_ratio, 6),
        round(mask.y1_ratio, 6),
        tuple((round(x, 6), round(y, 6)) for x, y in mask.points),
    )


def point_inside_mask(mask: AreaMask, x_ratio: float, y_ratio: float) -> bool:
    if not (
        mask.x0_ratio <= x_ratio <= mask.x1_ratio
        and mask.y0_ratio <= y_ratio <= mask.y1_ratio
    ):
        return False
    if mask.shape == "rectangle":
        return True
    inside = False
    points = mask.points
    previous_x, previous_y = points[-1]
    for current_x, current_y in points:
        crosses = (current_y > y_ratio) != (previous_y > y_ratio)
        if crosses:
            boundary_x = (
                (previous_x - current_x)
                * (y_ratio - current_y)
                / (previous_y - current_y)
                + current_x
            )
            if x_ratio < boundary_x:
                inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


def apply_masks_to_document(
    document: DocumentText,
    page_sizes: tuple[tuple[float, float], ...],
    masks: tuple[AreaMask, ...],
) -> tuple[DocumentText, int]:
    """Filter words by their source-coordinate centers without changing coordinates."""
    if not masks:
        return document, 0
    filtered_pages = []
    removed = 0
    for page in document.pages:
        page_masks = tuple(
            mask
            for mask in masks
            if mask.page_index is None or mask.page_index == page.page_index
        )
        if not page_masks:
            filtered_pages.append(page)
            continue
        width, height = (
            page_sizes[page.page_index]
            if 0 <= page.page_index < len(page_sizes)
            else (
                max((word.x1 for word in page.words), default=1.0),
                max((word.y1 for word in page.words), default=1.0),
            )
        )
        width = max(float(width), 1.0)
        height = max(float(height), 1.0)
        keep_masks = tuple(mask for mask in page_masks if mask.kind == "keep")
        ignore_masks = tuple(mask for mask in page_masks if mask.kind == "ignore")
        retained = []
        for word in page.words:
            x_ratio = ((word.x0 + word.x1) / 2) / width
            y_ratio = ((word.y0 + word.y1) / 2) / height

            allowed = not keep_masks or any(
                point_inside_mask(mask, x_ratio, y_ratio) for mask in keep_masks
            )
            if allowed and not any(
                point_inside_mask(mask, x_ratio, y_ratio)
                for mask in ignore_masks
            ):
                retained.append(word)
            else:
                removed += 1
        filtered_pages.append(
            replace(page, text=" ".join(word.text for word in retained), words=tuple(retained))
        )
    return (
        replace(
            document,
            audit=replace(
                document.audit,
                word_count=sum(len(page.words) for page in filtered_pages),
            ),
            pages=tuple(filtered_pages),
        ),
        removed,
    )


def save_mask_profile(path_value: str | Path, masks: tuple[AreaMask, ...]) -> None:
    path = Path(path_value)
    payload = {
        "mask_profile_version": MASK_PROFILE_VERSION,
        "masks": [
            {
                key: value
                for key, value in asdict(mask).items()
                if key not in {"mask_id", "document_id"}
            }
            for mask in masks
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def load_mask_profile(
    path_value: str | Path,
    document_id: str,
    page_count: int,
) -> tuple[AreaMask, ...]:
    path = Path(path_value)
    if not path.is_file() or path.stat().st_size > 1_000_000:
        raise AreaMaskError("The mask profile is missing or exceeds 1 MB.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("mask_profile_version") not in (1, MASK_PROFILE_VERSION):
            raise AreaMaskError("The mask profile version is not supported.")
        masks = tuple(
            _mask_from_payload(item, document_id)
            for item in payload.get("masks", ())
        )
        AreaMaskStore.validate(document_id, masks, page_count)
        return masks
    except AreaMaskError:
        raise
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise AreaMaskError("The mask profile is invalid or corrupted.") from exc
