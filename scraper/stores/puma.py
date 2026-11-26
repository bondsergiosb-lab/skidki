"""PUMA Україна — раздел «Знижки», карточки Magento в готовом HTML.

Пол в названии («… Wmns», «Жіночі …», «Unisex»), мужское отсеет классификатор.
"""
import html as htmllib
import re

from ..models import Item

NAME = "PUMA"
SITE = "https://ua.puma.com"
SALE = SITE + "/uk/skidki.html"
PAGES = 8

_CARD = re.compile(r'<div class="product-item\s*"(.*?)(?=<div class="product-item\s*"|$)', re.S)


def parse(page: str):
    for card in _CARD.findall(page):
        sku, name = re.search(r'data-product-sku="([^"]+)"', card), re.search(r'data-product-name="([^"]+)"', card)
        link = re.search(r'<a href="([^"]+)" class="product-item__img-w"', card)
        # цены самой карточки; у цветов-вариантов они экранированы (&quot;) и сюда не попадут
        new = re.search(r'data-price-amount="([\d.]+)" data-price-type="finalPrice"', card)
        old = re.search(r'data-price-amount="([\d.]+)" data-price-type="oldPrice"', card)
        if not (sku and name and link and new and old):
            continue
        img = re.search(r'<img class="product-item__img[^>]*>', card)
        src = re.search(r'data-src="([^"]+)"', img.group(0)) or re.search(r'src="(http[^"]+)"', img.group(0)) if img else None
        yield Item(
            store="puma",
            sku=sku.group(1),
            title=htmllib.unescape(name.group(1)),
            url=link.group(1),
            image=src.group(1) if src else "",
            price=float(new.group(1)),
            old_price=float(old.group(1)),
            brand="PUMA",
            audience="",
        )


def scrape(http):
    seen = set()
    for page in range(1, PAGES + 1):
        html = http.get_optional(SALE + (f"?p={page}" if page > 1 else ""))
        items = [it for it in parse(html)] if html else []
        fresh = [it for it in items if it.sku not in seen]
        if not fresh:  # за последней страницей Magento отдаёт снова последнюю
            break
        seen.update(it.sku for it in fresh)
        yield from fresh
