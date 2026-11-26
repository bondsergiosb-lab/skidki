"""Kasta — маркетплейс, страницы каталога приходят готовым HTML (карточки <article>).

В карточке: цена, зачёркнутая старая цена, размеры в наличии. Отдельного поля бренда нет —
бренд стоит первым в названии («Liardi пуховик жіночий …»).
robots.txt разрешает листать только параметром offset и не глубже двух уровней категорий.
"""
import html as htmllib
import re

from ..models import Item

NAME = "Kasta"
SITE = "https://kasta.ua"
CATEGORIES = [
    ("zhenskaya-odezhda", "women"),
    ("zhenskaya-obuv", "women"),
    ("zhenskie-aksessuary", "women"),
    ("sumki-i-ryukzaki", ""),
    ("odezhda-dlya-devochek", "girls"),
    ("obuv-dlya-devochek", "girls"),
]
PAGES = 6       # по 50 товаров
PER_PAGE = 50

_ARTICLE = re.compile(r"<article\b.*?</article>", re.S)
_KEY = re.compile(r'name="product-key" value="([^"]+)"')
_LINK = re.compile(r'<a title="([^"]*)" href="(/uk/product/[^"]+)"')
_IMG = re.compile(r'data-src="(https://cdn\.kasta\.ua/image/[^"]+)"')
_PRICE = re.compile(r'<span class="t-bold[^"]*">([^<]+)</span>')
_OLD = re.compile(r'<span class="[^"]*t-striked[^"]*">([^<]+)</span>')
_SIZES = re.compile(r'class="[^"]*product-size-list[^"]*">(.*?)</div>', re.S)


def _money(s: str) -> float:
    return float(re.sub(r"[^\d]", "", s) or 0)


_LATIN = re.compile(r"^[A-Z][A-Za-z'&.\-]*$")


def _brand(title: str) -> str:
    # Обычно бренд стоит перед артикулом в конце: «… Рожевий/чорний XK9252 Geox (401260616)» → «Geox»
    m = re.search(r"^(.*?)\s*\(\d+\)\s*$", title)
    if m:
        tail = []
        for w in reversed(m.group(1).split()):
            if not _LATIN.match(w) or len(tail) == 2:
                break
            tail.insert(0, w)
        if tail:
            brand = " ".join(tail)
            return "" if brand.lower() == "no brand" else brand
    # иначе — латинские слова в начале: «Tommy Hilfiger сукня …» → «Tommy Hilfiger»
    head = []
    for w in title.split():
        if not _LATIN.match(w) or len(head) == 3:
            break
        head.append(w)
    return " ".join(head)


def parse(page: str, audience: str):
    for card in _ARTICLE.findall(page):
        key, link, price, old = _KEY.search(card), _LINK.search(card), _PRICE.search(card), _OLD.search(card)
        if not (key and link and price and old):
            continue
        title = htmllib.unescape(link.group(1)).strip(" —")
        sizes = _SIZES.search(card)
        img = _IMG.search(card)
        yield Item(
            store="kasta",
            sku=key.group(1),
            title=title,
            url=SITE + link.group(2),
            image=img.group(1) if img else "",
            price=_money(price.group(1)),
            old_price=_money(old.group(1)),
            brand=_brand(title),
            audience=audience,
            sizes=[htmllib.unescape(s) for s in re.findall(r"<span>([^<]+)</span>", sizes.group(1))] if sizes else [],
        )


def scrape(http):
    for slug, audience in CATEGORIES:
        for page in range(PAGES):
            url = f"{SITE}/uk/market/{slug}/" + (f"?offset={page * PER_PAGE}" if page else "")
            html = http.get_optional(url)
            items = list(parse(html, audience)) if html else []
            yield from items
            if not items:
                break
