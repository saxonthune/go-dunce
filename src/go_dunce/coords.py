from __future__ import annotations

from .contracts import Point

# Go coordinates skip the letter I so it cannot be confused with J or 1.
COLUMNS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"


def to_gtp(point: Point | None, size: int) -> str:
    if point is None:
        return "pass"
    return f"{COLUMNS[point.x]}{size - point.y}"


def from_gtp(text: str, size: int) -> Point | None:
    if text.lower() == "pass":
        return None
    return Point(x=COLUMNS.index(text[0].upper()), y=size - int(text[1:]))


def line(points: list[Point | None], size: int) -> str:
    return ", ".join(to_gtp(p, size) for p in points)
