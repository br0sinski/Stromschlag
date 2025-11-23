"""Icon rendering helpers."""
from __future__ import annotations

from typing import Dict, Iterable, Sequence

from PIL import Image, ImageDraw, ImageFont

from .models import IconDefinition, PackSettings
from .utils import hex_to_rgba


def generate_icon_raster(
    icon: IconDefinition,
    settings: PackSettings,
    sizes: Sequence[int] | None = None,
) -> Dict[int, Image.Image]:
    """Render the icon for each requested size and return image objects."""

    target_sizes: Iterable[int] = sizes or settings.base_sizes
    return {size: _render_single_icon(icon, size) for size in target_sizes}


def _render_single_icon(icon: IconDefinition, size: int) -> Image.Image:
    padding = max(2, int(size * 0.08))
    corner_radius = max(4, int(size * 0.2))
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (padding, padding, size - padding, size - padding),
        radius=corner_radius,
        fill=hex_to_rgba(icon.normalized_background()),
    )

    glyph = _resolve_glyph(icon)
    font = _load_font(size)
    text_bbox = font.getbbox(glyph)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    position = (
        (size - text_width) / 2 - text_bbox[0],
        (size - text_height) / 2 - text_bbox[1],
    )
    draw.text(
        position,
        glyph,
        fill=hex_to_rgba(icon.normalized_foreground()),
        font=font,
    )
    return image


def _resolve_glyph(icon: IconDefinition) -> str:
    text = (icon.glyph or icon.name or "?").strip()
    if not text:
        return "?"
    return text[0]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    target_px = max(12, int(size * 0.6))
    for candidate in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(candidate, target_px)
        except OSError:
            continue
    return ImageFont.load_default()
