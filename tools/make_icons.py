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


def masked(img: Image.Image, round_: bool) -> Image.Image:
    """Иконка Android: скруглённый квадрат или круг на прозрачном фоне."""
    size = img.size[0]
    mask = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(mask)
    if round_:
        d.ellipse([0, 0, size - 1, size - 1], fill=255)
    else:
        d.rounded_rectangle([0, 0, size - 1, size - 1], radius=size * 0.22, fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, mask=mask)
    return out


OUT.mkdir(parents=True, exist_ok=True)
for size in (192, 512):
    tag(size * 4, 0.16).resize((size, size), Image.LANCZOS).save(OUT / f"icon-{size}.png")
tag(512 * 4, 0.26).resize((512, 512), Image.LANCZOS).save(OUT / "icon-maskable-512.png")

RES = Path(__file__).resolve().parents[1] / "android" / "app" / "src" / "main" / "res"
for density, size in {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}.items():
    folder = RES / f"mipmap-{density}"
    folder.mkdir(parents=True, exist_ok=True)
    big = tag(size * 4, 0.2)
    masked(big, False).resize((size, size), Image.LANCZOS).save(folder / "ic_launcher.png")
    masked(big, True).resize((size, size), Image.LANCZOS).save(folder / "ic_launcher_round.png")
print("ok", OUT, RES)
