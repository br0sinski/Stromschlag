"""Helpers for reading and writing Stromschlag project files."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Tuple

import yaml

from .models import IconDefinition, PackSettings

_PROJECT_HEADER = "# Icon pack generated with Stromschlag - https://github.com/br0sinski/Stromschlag\n"


def load_project(path: Path) -> Tuple[PackSettings, List[IconDefinition]]:
    """Load a Stromschlag project from disk and return settings plus icons."""
    data = yaml.safe_load(path.read_text()) or {}

    settings = PackSettings(
        name=data.get("name", "Untitled Icon Pack"),
        author=data.get("author", "Unknown"),
        description=data.get("description", ""),
        inherits=data.get("inherits", "breeze"),
        base_sizes=[int(size) for size in data.get("base_sizes", [16, 24, 32, 48, 64, 128])],
        output_dir=Path(data.get("output_dir", "build")),
        targets=[str(target) for target in data.get("targets", ["gnome", "kde"])],
    )

    icons: List[IconDefinition] = []
    for index, payload in enumerate(data.get("icons", []), start=1):
        name = payload.get("name", f"Icon {index}")
        source_path_str = payload.get("source_path")
        icons.append(
            IconDefinition(
                name=name,
                source_path=Path(source_path_str).expanduser() if source_path_str else None,
                category=payload.get("category"),
            )
        )
    return settings, icons


def save_project(
    path: Path,
    settings: PackSettings,
    icons: Iterable[IconDefinition],
    *,
    include_categories: bool = True,
) -> None:
    """Persist the project as a YAML document."""
    payload = {
        "name": settings.name,
        "author": settings.author,
        "description": settings.description,
        "inherits": settings.inherits,
        "base_sizes": settings.base_sizes,
        "output_dir": str(settings.output_dir),
        "targets": settings.targets,
        "icons": [
            {
                "name": icon.name,
                **(
                    {"category": icon.category}
                    if include_categories and icon.category
                    else {}
                ),
                **(
                    {"source_path": str(icon.source_path)}
                    if icon.source_path is not None
                    else {}
                ),
            }
            for icon in icons
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml_text = yaml.safe_dump(payload, sort_keys=False)
    path.write_text(f"{_PROJECT_HEADER}{yaml_text}")
