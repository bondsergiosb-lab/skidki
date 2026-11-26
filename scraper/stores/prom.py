"""Prom.ua — маркетплейс; товары каталога лежат в странице в window.ApolloCacheState.

Скидки на Prom ставят сами продавцы, поэтому здесь особенно полезна проверка по истории цен:
«вечные» и завышенные скидки через несколько дней получат пометки и скроются.
"""
import json
import re

from ..models import Item

NAME = "Prom.ua"
SITE = "https://prom.ua"
CATEGORIES = [
    ("Zhenskaya-verhnyaya-odezhda", "women"),
    ("Zhenskii-platya", "women"),
    ("Zhenskie-kofty-i-kardigany", "women"),
    ("Zhenskie-bryuki", "women"),
    ("Zhenskie-dzhinsy", "women"),
    ("Zhenskie-bluzki", "women"),
    ("Zhenskie-kostyumy", "women"),
    ("Pizhamy-zhenskie", "women"),
    ("Odezhda-dlya-devochek", "girls"),
]
PAGES = 3


def _products(page: str) -> list[dict]:
    i = page.find("window.ApolloCacheState =")
    if i < 0:
        raise ValueError("на странице нет ApolloCacheState — разметка сайта изменилась")
    state, _ = json.JSONDecoder().raw_decode(page[i + len("window.ApolloCacheState ="):].lstrip())
    found = []

    def walk(x):
        if isinstance(x, dict):
            if x.get("__typename") == "Product" and "discountedPrice" in x:
                found.append(x)
            else:
                for v in x.values():
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(state)
    return found


def parse(page: str, audience: str):
    for p in _products(page):
        if not p.get("hasDiscount") or not p.get("discountedPrice") or not p.get("price"):
            continue
        brand = (p.get("manufacturerInfo") or {}).get("name") or (p.get("company") or {}).get("name") or ""
        yield Item(
            store="prom",
            sku=str(p["id"]),
            title=p.get("name") or "",
            url=f"{SITE}/ua/p{p['id']}-{p.get('urlText') or ''}.html",
            image=p.get("image400x400") or p.get("image") or "",
            price=float(p["discountedPrice"]),
            old_price=float(p["price"]),
            brand=brand,
            audience=audience,
        )


def scrape(http):
    for slug, audience in CATEGORIES:
        for page in range(1, PAGES + 1):
            html = http.get_optional(f"{SITE}/ua/{slug}" + (f"?p={page}" if page > 1 else ""))
            if html is None:
                break
            yield from parse(html, audience)
