"""Рисует иконки приложения (нужен Pillow: pip install pillow). Запускается один раз, PNG лежат в app/icons."""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "app" / "icons"
PINK, WHITE = (232, 69, 122), (255, 255, 255)


def tag(size: int, pad: float) -> Image.Image:
    """Ценник со знаком процента на розовом фоне."""
    img = Image.new("RGB", (size, size), PINK)
    d = ImageDraw.Draw(img)
    s = size * (1 - 2 * pad)
    o = size * pad
    w = max(2, int(s * 0.075))
    # знак %: два кружка и косая черта
    r = s * 0.13
    for cx, cy in ((0.30, 0.30), (0.70, 0.70)):
        x, y = o + s * cx, o + s * cy
        d.ellipse([x - r, y - r, x + r, y + r], outline=WHITE, width=w)
    d.line([o + s * 0.74, o + s * 0.22, o + s * 0.26, o + s * 0.78], fill=WHITE, width=int(w * 1.2))
    return img


OUT.mkdir(parents=True, exist_ok=True)
for size in (192, 512):
    tag(size * 4, 0.16).resize((size, size), Image.LANCZOS).save(OUT / f"icon-{size}.png")
tag(512 * 4, 0.26).resize((512, 512), Image.LANCZOS).save(OUT / "icon-maskable-512.png")
print("ok", OUT)
