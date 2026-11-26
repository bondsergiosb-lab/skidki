"""Gepur — украинский бренд женской одежды. Каталог распродажи лежит в странице в __NEXT_DATA__.

На странице 24 товара, поэтому кроме общей распродажи берём первую страницу каждой её категории
(ссылки вида /uk/sale-catalog?filters=categories:… есть прямо на странице).
"""
import html as htmllib
import json
import re

from ..models import Item

NAME = "Gepur"
SITE = "https://gepur.com"
SALE = SITE + "/uk/sale-catalog"
IMG = "https://img.gepur.com"
MAX_CATEGORIES = 25


def _products(page: str) -> list[dict]:
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', page, re.S)
    if not m:
        raise ValueError("на странице нет __NEXT_DATA__ — разметка сайта изменилась")
    return json.loads(m.group(1))["props"]["pageProps"]["server"]["catalog"]["products"]


def parse(page: str):
    for p in _products(page):
        uah = ((p.get("prices") or {}).get("retail") or {}).get("1") or {}  # 1 — гривна
        price, old = float(uah.get("price") or 0), float(uah.get("base_price") or 0)
        if not price or price >= old:
            continue
        images = ((p.get("images") or {}).get("simple") or {}).get("catalog_big") or [""]
        yield Item(
            store="gepur",
            sku=str(p["id"]),
            title=p.get("label") or "",
            url=f"{SITE}/uk{p['link']}",
            image=IMG + images[0] if images[0] else "",
            price=price,
            old_price=old,
            brand="Gepur",
            audience="women",
        )


def scrape(http):
    first = http.get(SALE)
    yield from parse(first)
    links = dict.fromkeys(htmllib.unescape(x) for x in re.findall(r'href="(/uk/sale-catalog\?filters=categories:[^"]+)"', first))
    for link in list(links)[:MAX_CATEGORIES]:
        page = http.get_optional(SITE + link)
        if page:
            yield from parse(page)
