"""Export helpers for creating themed icon directories."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shutil import copy2
from typing import Dict, Iterable, List
from .models import IconDefinition, PackSettings
from .project_io import save_project
from .utils import ensure_directory, icon_filename


@dataclass(slots=True)
class _ThemeTarget:
    theme_root: Path
    size_dirs: Dict[int, Path]
    scalable_dir: Path


def export_icon_pack(settings: PackSettings, icons: Iterable[IconDefinition]) -> Path:
    """Export icons for the configured desktop targets (GTK/GNOME, KDE/Qt).

    Returns the path to the root export directory.
    """

    icon_list = list(icons)
    if not icon_list:
        raise ValueError("No icons provided for export")

    pack_root = settings.output_dir / settings.theme_slug()
    targets = _prepare_theme_targets(pack_root, settings)

    for icon in icon_list:
        if not icon.has_source_asset():
            continue

        filename = icon_filename(icon.name)
        _copy_source_asset(icon.source_path, filename, targets)

    _write_project_descriptors(pack_root, targets, settings, icon_list)
    return pack_root


def _prepare_theme_targets(root: Path, settings: PackSettings) -> List[_ThemeTarget]:
    themes: List[_ThemeTarget] = []
    comment = settings.theme_comment()
    desired = [target for target in settings.targets if target in {"gnome", "kde"}]
    if not desired:
        desired = ["gnome", "kde"]

    for desktop in desired:
        theme_root = root / desktop / settings.name
        ensure_directory(theme_root)
        size_dirs = {}
        directories = []
        for size in settings.base_sizes:
            dir_path = theme_root / f"{size}x{size}" / "apps"
            ensure_directory(dir_path)
            size_dirs[size] = dir_path
            directories.append(f"{size}x{size}/apps")

        scalable = theme_root / "scalable" / "apps"
        ensure_directory(scalable)
        directories.append("scalable/apps")

        _write_index_theme(theme_root, settings, directories, comment)
        themes.append(_ThemeTarget(theme_root, size_dirs, scalable))
    return themes


def _copy_source_asset(source: Path | None, filename: str, targets: List[_ThemeTarget]) -> None:
    if source is None:
        return
    suffix = source.suffix.lower()
    for target in targets:
        if suffix in {".svg", ".svgz"}:
            copy2(source, target.scalable_dir / filename)
        else:
            for directory in target.size_dirs.values():
                copy2(source, directory / filename)
            copy2(source, target.scalable_dir / filename)


def _write_project_descriptors(
    pack_root: Path,
    targets: List[_ThemeTarget],
    settings: PackSettings,
    icons: Iterable[IconDefinition],
) -> None:
    icon_snapshot = [
        IconDefinition(name=icon.name, source_path=icon.source_path, category=icon.category)
        for icon in icons
    ]
    save_project(pack_root / "stromschlag.yaml", settings, icon_snapshot, include_categories=False)

    for target in targets:
        themed_icons = [
            IconDefinition(
                name=icon.name,
                source_path=(target.scalable_dir / icon_filename(icon.name))
                if icon.has_source_asset()
                else None,
                category=icon.category,
            )
            for icon in icons
        ]
        save_project(
            target.theme_root / "stromschlag.yaml",
            settings,
            themed_icons,
            include_categories=False,
        )

def _write_index_theme(
    theme_root: Path, settings: PackSettings, directories: List[str], comment: str
) -> None:
    theme_file = theme_root / "index.theme"
    dirs = ",".join(directories)
    content = (
        "[Icon Theme]\n"
        f"Name={settings.name}\n"
        f"Comment={comment}\n"
        f"Inherits={settings.inherits}\n"
        f"Directories={dirs}\n\n"
    )
    for directory in directories:
        size_part = directory.split("/", 1)[0]
        if "x" in size_part:
            size_value = size_part.split("x")[0]
            extra = (
                f"[{directory}]\n"
                f"Size={size_value}\n"
                "Type=Fixed\n\n"
            )
        else:
            extra = (
                f"[{directory}]\n"
                "Size=128\n"
                "Type=Scalable\n\n"
            )
        content += extra

    theme_file.write_text(content)
