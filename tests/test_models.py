"""Minimal smoke tests for Stromschlag models."""
from pathlib import Path

from stromschlag.core.models import IconDefinition, PackSettings


def test_icon_definition_tracks_sources(tmp_path: Path) -> None:
    source = tmp_path / "sample.png"
    source.write_text("data")
    icon = IconDefinition(name="sample", source_path=source)
    assert icon.name == "sample"
    assert icon.has_source_asset()


def test_pack_settings_defaults() -> None:
    settings = PackSettings(name="Demo Pack", author="tester")
    assert settings.base_sizes[-1] == 128
    assert settings.theme_slug() == "demo-pack"
