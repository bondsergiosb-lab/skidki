"""Rozetka — маркетплейс; плитки товаров приходят готовым HTML (rz-catalog-tile).

В плитке: название, бренд (<strong>), цена и зачёркнутая старая цена. Страницы листаются
сегментом пути page=N/ — параметры после «?» robots.txt запрещает.
"""
import html as htmllib
import re

from ..models import Item

NAME = "Rozetka"
SITE = "https://rozetka.com.ua"
CATEGORIES = [
    ("/ua/1162060/c1162060/", "women"),           # одяг для жінок
    ("/ua/women_shoes/c721659/", "women"),
    ("/ua/sumki/c4630220/52257=117387/", ""),     # сумки (жіночі — отфильтрует классификатор)
    ("/ua/girls_clothing/c1285573/", "girls"),
    ("/ua/kids_girls_shoes/c721664/", "girls"),
]
PAGES = 5  # по 60 товаров

_TILE = re.compile(r"<rz-catalog-tile\b.*?</rz-catalog-tile>", re.S)
_TITLE_TAG = re.compile(r"<a\b[^>]*\brztiletitle\b[^>]*>(.*?)</a>", re.S)
_IMG_TAG = re.compile(r'<img\b[^>]*class="tile-image"[^>]*>')
_PRICE = re.compile(r'class="price\b[^"]*"[^>]*>([^<]+)<')
_OLD = re.compile(r'class="old-price\b[^"]*"[^>]*>([^<]+)<')


def _attr(tag: str, name: str) -> str:
    m = re.search(rf'\b{name}="([^"]*)"', tag)
    return htmllib.unescape(m.group(1)) if m else ""


def _money(s: str) -> float:
    return float(re.sub(r"[^\d]", "", htmllib.unescape(s)) or 0)


def parse(page: str, audience: str):
    for tile in _TILE.findall(page):
        a, price, old = _TITLE_TAG.search(tile), _PRICE.search(tile), _OLD.search(tile)
        if not (a and price and old):
            continue
        tag = a.group(0)[:a.group(0).index(">") + 1]
        url = _attr(tag, "href").split("#")[0]
        sku = re.search(r"/p(\d+)/", url)
        if not sku:
            continue
        brand = re.search(r"<strong[^>]*>([^<]+)</strong>", a.group(1))
        img = _IMG_TAG.search(tile)
        yield Item(
            store="rozetka",
            sku=sku.group(1),
            title=_attr(tag, "title"),
            url=url,
            image=_attr(img.group(0), "src") if img else "",
            price=_money(price.group(1)),
            old_price=_money(old.group(1)),
            brand=htmllib.unescape(brand.group(1)).strip() if brand else "",
            audience=audience,
        )


def scrape(http):
    for path, audience in CATEGORIES:
        for page in range(1, PAGES + 1):
            html = http.get_optional(SITE + path + (f"page={page}/" if page > 1 else ""))
            items = list(parse(html, audience)) if html else []
            yield from items
            if not items:
                break
