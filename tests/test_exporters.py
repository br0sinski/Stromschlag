"""Tests for exporter behavior."""
from pathlib import Path

import yaml

from stromschlag.core.exporters import export_icon_pack, install_icon_pack
from stromschlag.core.models import IconDefinition, PackSettings


def _make_icon_file(path: Path, color: str) -> None:
    path.write_bytes(color.encode("ascii"))


def test_export_copies_source_assets(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    settings = PackSettings(name="My Pack", author="Tester", base_sizes=[32], output_dir=build_dir)
    source = tmp_path / "folder.png"
    _make_icon_file(source, "#ff0000")

    icon = IconDefinition(
        name="folder",
        source_path=source,
    )

    result = export_icon_pack(settings, [icon])

    kde_icon = result.pack_root / "kde" / settings.name / "32x32" / "apps" / "folder.png"
    assert kde_icon.exists()
    assert kde_icon.read_bytes() == source.read_bytes()


def test_export_skips_icons_without_source(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    settings = PackSettings(name="My Pack", author="Tester", base_sizes=[32], output_dir=build_dir)

    icon = IconDefinition(
        name="terminal",
    )

    result = export_icon_pack(settings, [icon])

    kde_icon = result.pack_root / "kde" / settings.name / "32x32" / "apps" / "terminal.png"
    assert not kde_icon.exists()


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
        source_path=tmp_path / "app.png",
    )
    _make_icon_file(icon.source_path, "#00ff00")

    result = export_icon_pack(settings, [icon])

    kde_icon = result.pack_root / "kde" / settings.name / "32x32" / "apps" / "app.png"
    assert kde_icon.exists()
    assert not (result.pack_root / "gnome").exists()


def test_export_writes_project_descriptors(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    settings = PackSettings(name="Pack", author="Tester", base_sizes=[32], output_dir=build_dir)
    source = tmp_path / "app.png"
    _make_icon_file(source, "#00ff00")

    icon = IconDefinition(name="app", source_path=source, category="apps")

    result = export_icon_pack(settings, [icon])

    descriptor = result.pack_root / "stromschlag.yaml"
    assert descriptor.exists()
    data = yaml.safe_load(descriptor.read_text())
    assert data["name"] == "Pack"
    assert "output_dir" not in data
    assert "icons" not in data

    kde_descriptor = result.pack_root / "kde" / settings.name / "stromschlag.yaml"
    assert kde_descriptor.exists()
    kde_data = yaml.safe_load(kde_descriptor.read_text())
    assert kde_data["name"] == "Pack"
    assert "output_dir" not in kde_data
    assert "icons" not in kde_data


def test_install_icon_pack_copies_targets(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    settings = PackSettings(name="Pack", author="Tester", base_sizes=[32], output_dir=build_dir)
    source = tmp_path / "icon.png"
    _make_icon_file(source, "#123456")

    icon = IconDefinition(name="icon", source_path=source)

    result = export_icon_pack(settings, [icon])
    install_dir = tmp_path / "icons"

    installed, failures = install_icon_pack(result, [install_dir])

    assert not failures
    assert installed
    for path in installed:
        assert path.exists()
        icon_file = path / "32x32" / "apps" / "icon.png"
        assert icon_file.exists()
