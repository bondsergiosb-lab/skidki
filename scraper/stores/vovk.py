"""VOVK — украинский бренд женской одежды. Разделы распродажи (sale-dress, sale-coats …) — готовый HTML.

robots.txt просит 10 секунд между запросами, поэтому страниц берём немного.
"""
import html as htmllib
import re

from ..models import Item

NAME = "VOVK"
SITE = "https://vovk.com"
PAGES = 2

_CARD = re.compile(r'<div class="product-card[^"]*" data-product-id="(\d+)">(.*?)(?=<div class="product-card|</main>|$)', re.S)


def _money(s: str) -> float:
    return float(re.sub(r"[^\d]", "", s) or 0)


def parse(page: str):
    for pid, card in _CARD.findall(page):
        new, old = re.search(r'price-new">([^<]+)<', card), re.search(r'price-old">([^<]+)<', card)
        link, title = re.search(r'href="(https://vovk\.com/ua/[^"]+)"', card), re.search(r'item-title">([^<]+)<', card)
        if not (new and old and link and title):
            continue
        img = re.search(r'data-src="([^"]+)"', card)
        sizes = [htmllib.unescape(s).strip() for s in
                 re.findall(r'<div class="card-hover-size"\s*>.*?<label[^>]*>([^<]+)</label>', card, re.S)]
        yield Item(
            store="vovk",
            sku=pid,
            title=htmllib.unescape(title.group(1)).strip(),
            url=link.group(1),
            image=img.group(1) if img else "",
            price=_money(new.group(1)),
            old_price=_money(old.group(1)),
            brand="VOVK",
            audience="women",
            sizes=sizes,
        )


def scrape(http):
    home = http.get(SITE + "/ua/sales/")
    sections = dict.fromkeys(re.findall(r'href="(?:https://vovk\.com)?(/ua/(?:sale-[a-z\-]+|rozprodazh[a-z\-]*)/)"', home))
    yield from parse(home)
    for path in sections:
        for page in range(1, PAGES + 1):
            html = http.get_optional(SITE + path + (f"?page={page}" if page > 1 else ""))
            items = list(parse(html)) if html else []
            yield from items
            if not items:
                break
