"""Data models for Stromschlag icon pack definitions."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .. import __version__
from .utils import slugify


@dataclass(slots=True)
class IconDefinition:
    """Represents a single icon configuration."""

    name: str
    source_path: Path | None = None
    category: str | None = None

    def has_source_asset(self) -> bool:
        return self.source_path is not None and self.source_path.exists()


@dataclass(slots=True)
class PackSettings:
    """Meta information for the icon pack."""

    name: str
    author: str
    version: str = __version__
    description: str = "Custom icon theme generated with Stromschlag"
    inherits: str = "breeze"
    base_sizes: List[int] = field(default_factory=lambda: [16, 24, 32, 48, 64, 128])
    output_dir: Path = field(default_factory=lambda: Path("build"))
    targets: List[str] = field(default_factory=lambda: ["gnome", "kde"])

    def theme_slug(self) -> str:
        return slugify(self.name)

    def theme_comment(self) -> str:
        return self.description or f"Icon theme crafted by {self.author}"
