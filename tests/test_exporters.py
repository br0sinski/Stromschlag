"""Tests for exporter behavior."""
from pathlib import Path

from PIL import Image

from stromschlag.core.exporters import export_icon_pack
from stromschlag.core.models import IconDefinition, PackSettings


def _make_icon_file(path: Path, color: str) -> None:
    image = Image.new("RGBA", (32, 32), color)
    image.save(path)


def test_export_copies_source_assets(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    settings = PackSettings(name="My Pack", author="Tester", base_sizes=[32], output_dir=build_dir)
    source = tmp_path / "folder.png"
    _make_icon_file(source, "#ff0000")

    icon = IconDefinition(
        name="folder",
        glyph="F",
        background="#000000",
        foreground="#ffffff",
        source_path=source,
    )

    target = export_icon_pack(settings, [icon])

    kde_icon = target / "kde" / settings.name / "32x32" / "apps" / "folder.png"
    assert kde_icon.exists()
    assert kde_icon.read_bytes() == source.read_bytes()


def test_export_renders_when_missing_source(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    settings = PackSettings(name="My Pack", author="Tester", base_sizes=[32], output_dir=build_dir)

    icon = IconDefinition(
        name="terminal",
        glyph="T",
        background="#123456",
        foreground="#abcdef",
    )

    target = export_icon_pack(settings, [icon])

    kde_icon = target / "kde" / settings.name / "32x32" / "apps" / "terminal.png"
    assert kde_icon.exists()
    assert kde_icon.stat().st_size > 0


def test_export_honors_selected_targets(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    settings = PackSettings(
        name="My Pack",
        author="Tester",
        base_sizes=[32],
        output_dir=build_dir,
        targets=["kde"],
    )

    icon = IconDefinition(
        name="app",
        glyph="A",
        background="#222222",
        foreground="#ffffff",
    )

    target = export_icon_pack(settings, [icon])

    kde_icon = target / "kde" / settings.name / "32x32" / "apps" / "app.png"
    assert kde_icon.exists()
    assert not (target / "gnome").exists()
