"""Helpers for seeding new projects from installed icon themes."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from .models import IconDefinition

_SYSTEM_ICON_DIRS = [
    Path.home() / ".local/share/icons",
    Path.home() / ".icons",
    Path("/usr/share/icons"),
    Path("/usr/local/share/icons"),
]

_PREFERRED_THEMES = ["breeze", "adwaita", "hicolor"]
_ALLOWED_SUFFIXES = {".png", ".svg", ".svgz"}
_ICON_SUBDIRS = (
    "apps",
    "actions",
    "status",
    "panel",
    "ui",
    "system",
    "devices",
    "places",
    "categories",
    "mimetypes",
)


@dataclass(slots=True)
class BlueprintLoadResult:
    """Result of attempting to seed icons from a system theme."""

    icons: List[IconDefinition]
    source_theme: str | None
    needs_selection: bool


@dataclass(slots=True)
class ThemeCandidate:
    """Represents an installed icon theme that can seed a project."""

    name: str
    path: Path


def load_icon_blueprint(
    preferred_themes: Sequence[str] | None = None,
    limit: int | None = None,
    extra_search_paths: Iterable[Path] | None = None,
) -> BlueprintLoadResult:
    """Return icon definitions derived from installed themes."""

    themes = preferred_themes or _PREFERRED_THEMES
    root = _discover_theme_root(themes, extra_search_paths)
    if root:
        entries = _collect_icon_entries(root, limit)
        if entries:
            return BlueprintLoadResult(
                icons=_build_icon_definitions(entries),
                source_theme=root.name,
                needs_selection=False,
            )
    return BlueprintLoadResult(icons=[], source_theme=None, needs_selection=True)


def load_icons_from_directory(theme_root: Path, limit: int | None = None) -> List[IconDefinition]:
    entries = _collect_icon_entries(theme_root, limit)
    return _build_icon_definitions(entries)


def list_installed_themes(
    extra_search_paths: Iterable[Path] | None = None,
) -> List[ThemeCandidate]:
    """Return available icon theme directories discovered on the system."""

    search_roots: List[Path] = []
    if extra_search_paths:
        search_roots.extend(extra_search_paths)
    search_roots.extend(_SYSTEM_ICON_DIRS)

    candidates: List[ThemeCandidate] = []
    seen: set[str] = set()
    for base in search_roots:
        if not base.exists() or not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if not child.is_dir():
                continue
            index_theme = child / "index.theme"
            if not index_theme.exists():
                continue
            key = child.resolve()
            if str(key) in seen:
                continue
            seen.add(str(key))
            candidates.append(ThemeCandidate(name=child.name, path=child))
    return candidates


def _discover_theme_root(
    themes: Sequence[str], extra_search_paths: Iterable[Path] | None
) -> Path | None:
    search_roots: List[Path] = []
    if extra_search_paths:
        search_roots.extend(extra_search_paths)
    search_roots.extend(_SYSTEM_ICON_DIRS)

    for theme in themes:
        for base in search_roots:
            candidate = base / theme
            if candidate.exists() and candidate.is_dir():
                return candidate
    return None


def _collect_icon_entries(theme_root: Path, limit: int | None) -> List[Tuple[str, Path, str]]:
    entries: List[Tuple[str, Path, str]] = []
    seen = set()
    for category in _ICON_SUBDIRS:
        for suffix in _ALLOWED_SUFFIXES:
            pattern = f"**/{category}/**/*{suffix}"
            for path in theme_root.glob(pattern):
                if not path.is_file():
                    continue
                stem = path.stem
                if stem in seen:
                    continue
                seen.add(stem)
                entries.append((stem, path, category))
                if limit is not None and len(entries) >= limit:
                    return entries
    return entries


def _build_icon_definitions(entries: Sequence[Tuple[str, Path, str]]) -> List[IconDefinition]:
    return [
        IconDefinition(
            name=name,
            source_path=path,
            category=category,
        )
        for name, path, category in entries
    ]
