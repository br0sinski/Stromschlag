"""Tests for project I/O helpers."""
from pathlib import Path

from stromschlag.core.models import IconDefinition, PackSettings
from stromschlag.core.project_io import load_project, save_project


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "project.yaml"
    settings = PackSettings(
        name="Test Pack",
        author="Tester",
        description="Demo",
        base_sizes=[32],
        targets=["kde"],
    )
    source_file = tmp_path / "folder.png"
    source_file.write_text("data")
    icons = [
        IconDefinition(
            name="Folder",
            glyph="F",
            background="#123456",
            foreground="#ffffff",
            source_path=source_file,
            category="apps",
        ),
        IconDefinition(
            name="Gear",
            glyph="G",
            background="#654321",
            foreground="#eeeeee",
            category="actions",
        ),
    ]

    save_project(path, settings, icons)
    loaded_settings, loaded_icons = load_project(path)

    assert loaded_settings.name == settings.name
    assert loaded_settings.author == settings.author
    assert loaded_settings.base_sizes == [32]
    assert loaded_settings.targets == ["kde"]
    assert len(loaded_icons) == 2
    assert loaded_icons[0].name == "Folder"
    assert loaded_icons[1].glyph == "G"
    assert loaded_icons[0].source_path == source_file
    assert loaded_icons[0].category == "apps"
    assert loaded_icons[1].category == "actions"
