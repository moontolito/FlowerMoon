"""Pure geometry helpers for fitting and cursor-anchored zoom."""

from __future__ import annotations


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def calculate_fit_scale(
    viewport_width: float,
    viewport_height: float,
    page_width: float,
    page_height: float,
    padding: float = 40,
) -> float:
    if page_width <= 0 or page_height <= 0:
        return 1.0
    available_width = max(1.0, viewport_width - padding)
    available_height = max(1.0, viewport_height - padding)
    return clamp(min(available_width / page_width, available_height / page_height), 0.20, 2.50)


def next_zoom_scale(current: float, direction: int) -> float:
    step = 0.10 if direction > 0 else -0.10
    return round(clamp(current + step, 0.25, 2.50), 2)


def anchored_scroll_value(current_scroll: int, old_screen: float, new_screen: float) -> int:
    """Return scroll required to put a resized anchor back at its old position."""
    return max(0, round(current_scroll + new_screen - old_screen))
