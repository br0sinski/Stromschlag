"""Minimal smoke tests for Stromschlag models."""
from stromschlag.core.generator import generate_icon_raster
from stromschlag.core.models import IconDefinition, PackSettings


def test_icon_definition_round_trip() -> None:
    icon = IconDefinition(
        name="sample",
        glyph="S",
        background="#112233",
        foreground="#ffffff",
    )
    assert icon.name == "sample"
    assert icon.glyph == "S"
    assert icon.normalized_background() == "#112233"


def test_pack_settings_defaults() -> None:
    settings = PackSettings(name="Demo Pack", author="tester")
    assert settings.base_sizes[-1] == 128
    assert settings.theme_slug() == "demo-pack"


def test_generate_icon_raster() -> None:
    settings = PackSettings(name="Demo", author="Tester", base_sizes=[32])
    icon = IconDefinition(
        name="Terminal",
        glyph="T",
        background="#445566",
        foreground="#ffffff",
    )
    rasters = generate_icon_raster(icon, settings)
    assert 32 in rasters
    assert rasters[32].size == (32, 32)
