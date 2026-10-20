"""Gera o PNG base do ícone do Release Radar (arte de radar, sem dependências do app).

Uso: uv run --with pillow python scripts/make_icon.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024
BACKGROUND = (13, 22, 32, 255)
RING = (34, 53, 74, 255)
RING_BRIGHT = (74, 222, 128, 90)
ACCENT = (74, 222, 128, 255)


def main() -> None:
    image = Image.new("RGBA", (SIZE, SIZE), BACKGROUND)
    draw = ImageDraw.Draw(image, "RGBA")
    center = SIZE / 2

    for radius in (140, 260, 380):
        draw.ellipse(
            [center - radius, center - radius, center + radius, center + radius],
            outline=RING,
            width=14,
        )

    # Setor do radar (varredura) com degradê de opacidade por fatias.
    for index in range(36):
        start = -90 + index * 2.5
        end = start + 2.5
        alpha = int(120 * (index / 36))
        draw.pieslice(
            [center - 380, center - 380, center + 380, center + 380],
            start=start,
            end=end,
            fill=(74, 222, 128, alpha),
        )

    for radius in (140, 260, 380):
        draw.ellipse(
            [center - radius, center - radius, center + radius, center + radius],
            outline=RING,
            width=12,
        )

    # Ponto central e "blips" de novidades.
    draw.ellipse([center - 40, center - 40, center + 40, center + 40], fill=ACCENT)
    for angle, radius in ((35, 200), (150, 300), (250, 240)):
        rad = math.radians(angle)
        x = center + radius * math.cos(rad)
        y = center + radius * math.sin(rad)
        draw.ellipse([x - 22, y - 22, x + 22, y + 22], fill=ACCENT)

    out = Path(__file__).resolve().parent.parent / "app-icon.png"
    image.save(out)
    print(f"Ícone base gravado em {out}")


if __name__ == "__main__":
    main()
