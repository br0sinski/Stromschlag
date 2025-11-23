"""Utility helpers used across the Stromschlag core modules."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable, Tuple


_HEX_RE = re.compile(r"^#?(?P<value>[0-9a-fA-F]{6})$")


def ensure_hex(color: str) -> str:
    """Return a canonical #RRGGBB string or raise ValueError."""
    match = _HEX_RE.match(color.strip())
    if not match:
        raise ValueError(f"Invalid hex color: {color}")
    return f"#{match.group('value').lower()}"


def hex_to_rgba(color: str, alpha: int = 255) -> Tuple[int, int, int, int]:
    """Convert a #RRGGBB color to an (r, g, b, a) tuple."""
    normalized = ensure_hex(color)[1:]
    r = int(normalized[0:2], 16)
    g = int(normalized[2:4], 16)
    b = int(normalized[4:6], 16)
    return r, g, b, alpha


def slugify(value: str) -> str:
    """Turn arbitrary text into a filesystem friendly slug."""
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or "icon-pack"


def ensure_directory(path: Path) -> None:
    """Create the directory (and parents) if it does not already exist."""
    path.mkdir(parents=True, exist_ok=True)


def icon_filename(value: str) -> str:
    """Return a canonical filename for an icon (without directories)."""
    return f"{slugify(value)}.png"
