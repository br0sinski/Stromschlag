"""Tests for loading default icon blueprints from system themes."""
from pathlib import Path

from stromschlag.core.theme_loader import (
    BlueprintLoadResult,
    ThemeCandidate,
    load_icon_blueprint,
    load_icons_from_directory,
    list_installed_themes,
)


def test_load_icon_blueprint_from_custom_theme(tmp_path: Path) -> None:
    theme_root = tmp_path / "breeze"
    (theme_root / "apps" / "48").mkdir(parents=True)
    (theme_root / "apps" / "48" / "folder.png").write_text("data")
    (theme_root / "scalable" / "apps").mkdir(parents=True)
    (theme_root / "scalable" / "apps" / "settings.svg").write_text("<svg></svg>")
    (theme_root / "status" / "22").mkdir(parents=True)
    (theme_root / "status" / "22" / "network-wired.svg").write_text("<svg></svg>")

    result = load_icon_blueprint(extra_search_paths=[tmp_path])

    assert isinstance(result, BlueprintLoadResult)
    assert not result.needs_selection
    assert result.source_theme == "breeze"
    names = {icon.name for icon in result.icons}
    assert {"folder", "settings", "network-wired"}.issubset(names)
    categories = {icon.category for icon in result.icons if icon.name == "network-wired"}
    assert categories == {"status"}


def test_load_icon_blueprint_requires_selection(tmp_path: Path) -> None:
    result = load_icon_blueprint(preferred_themes=["nonexistent"], extra_search_paths=[tmp_path])

    assert result.needs_selection
    assert result.source_theme is None
    assert result.icons == []


def test_load_icon_blueprint_limit(tmp_path: Path) -> None:
    theme_root = tmp_path / "breeze"
    (theme_root / "apps" / "48").mkdir(parents=True)
    for index in range(10):
        (theme_root / "apps" / "48" / f"app{index}.png").write_text("data")

    result = load_icon_blueprint(extra_search_paths=[tmp_path], limit=5)

    assert len(result.icons) == 5


def test_load_icons_from_directory(tmp_path: Path) -> None:
    theme_root = tmp_path / "custom"
    (theme_root / "apps" / "48").mkdir(parents=True)
    (theme_root / "apps" / "48" / "folder.png").write_text("data")

    icons = load_icons_from_directory(theme_root)

    assert len(icons) == 1
    assert icons[0].name == "folder"


def test_list_installed_themes(tmp_path: Path) -> None:
    icons_dir = tmp_path / "icons"
    theme_dir = icons_dir / "sample"
    theme_dir.mkdir(parents=True)
    (theme_dir / "index.theme").write_text("[Icon Theme]\nName=Sample\n")

    themes = list_installed_themes(extra_search_paths=[icons_dir])

    assert themes
    assert isinstance(themes[0], ThemeCandidate)
    assert themes[0].name == "sample"
```}