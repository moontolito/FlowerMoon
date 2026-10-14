"""Pure selection geometry shared by the Qt canvas and automated tests."""

from __future__ import annotations

from math import hypot

from .models import TextRect, TextWord


def word_index_at(
    words: tuple[TextWord, ...], x: float, y: float, tolerance: float = 4.0
) -> int | None:
    for index, word in enumerate(words):
        if word.x0 - tolerance <= x <= word.x1 + tolerance and word.y0 - tolerance <= y <= word.y1 + tolerance:
            return index
    nearest: tuple[float, int] | None = None
    for index, word in enumerate(words):
        nearest_x = max(word.x0, min(x, word.x1))
        nearest_y = max(word.y0, min(y, word.y1))
        distance = hypot(x - nearest_x, y - nearest_y)
        if distance <= tolerance and (nearest is None or distance < nearest[0]):
            nearest = (distance, index)
    return nearest[1] if nearest else None


def normalized_range(anchor: int, active: int) -> tuple[int, int]:
    return (anchor, active) if anchor <= active else (active, anchor)


def selected_text(words: tuple[TextWord, ...], start: int, end: int) -> str:
    if not words or start < 0 or end >= len(words) or start > end:
        return ""
    parts: list[str] = []
    previous_line = None
    for word in words[start : end + 1]:
        line_key = (word.block_number, word.paragraph_number, word.line_number)
        if previous_line is not None:
            parts.append("\n" if line_key != previous_line else " ")
        parts.append(word.text)
        previous_line = line_key
    return "".join(parts)


def selection_rects(words: tuple[TextWord, ...], start: int, end: int) -> tuple[TextRect, ...]:
    if not words or start < 0 or end >= len(words) or start > end:
        return ()
    rects: list[TextRect] = []
    current_key = None
    current: TextRect | None = None
    for word in words[start : end + 1]:
        line_key = (word.block_number, word.paragraph_number, word.line_number)
        word_rect = TextRect(word.x0, word.y0, word.x1, word.y1)
        if current is None or line_key != current_key:
            if current is not None:
                rects.append(current)
            current = word_rect
            current_key = line_key
        else:
            current = TextRect(
                min(current.x0, word.x0),
                min(current.y0, word.y0),
                max(current.x1, word.x1),
                max(current.y1, word.y1),
            )
    if current is not None:
        rects.append(current)
    return tuple(rects)
