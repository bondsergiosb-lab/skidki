"""Общий парсер для магазинов, у которых карточки товаров приходят готовым HTML.

Магазин описывается настройками Shop: где начинается карточка и регулярные выражения для полей
(первая группа — значение). Карточка — кусок страницы от одного начала карточки до следующего.
"""
import html as htmllib
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

from ..models import Item


def money(s: str) -> float:
    """«1 799 ₴», «1644.00», «2.499», «1 253,50 грн» → число."""
    s = re.sub(r"[^\d.,]", "", htmllib.unescape(s or ""))
    m = re.match(r"^(.*?)[.,](\d{1,2})$", s)
    whole, frac = (m.group(1), m.group(2)) if m else (s, "0")
    whole = re.sub(r"[.,]", "", whole)
    return float(f"{whole or 0}.{frac}")


def text(s: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


@dataclass
class Shop:
    store: str
    name: str
    site: str
    sections: list[tuple[str, str]]          # (адрес раздела распродажи, для кого: women/men/girls/boys/kids/"")
    card: str                                # начало карточки
    title: str
    url: str
    price: str                               # текущая цена
    old: str                                 # старая (зачёркнутая) цена
    image: str = r'<img[^>]+?(?:data-src|data-original|src)="([^"]+\.(?:jpe?g|png|webp)[^"]*)"'
    brand: str = ""                          # регулярка или пусто
    fixed_brand: str = ""                    # бренд магазина, если все товары одного бренда
    sku: str = ""                            # по умолчанию — последний кусок адреса товара
    path: str = ""                           # категория товара (для классификатора)
    sizes: str = ""                          # findall по карточке (или по блоку sizes_in)
    sizes_in: str = ""                       # блок карточки, где перечислены размеры
    gender: list[tuple[str, str]] = field(default_factory=list)  # (регулярка по карточке, для кого)
    page: str = "page={n}"                   # параметр страницы; {n} — номер
    pages: int = 5
    skip_card: str = ""                      # карточки, которые не нужны (нет в наличии и т. п.)

    def page_url(self, url: str, n: int) -> str:
        if n == 1:
            return url
        p = self.page.format(n=n)
        if p.startswith("/"):
            return url.rstrip("/") + p
        return url + ("&" if "?" in url else "?") + p

    def parse(self, page: str, audience: str):
        starts = [m.start() for m in re.finditer(self.card, page)]
        for a, b in zip(starts, starts[1:] + [len(page)]):
            card = page[a:b]
            if self.skip_card and re.search(self.skip_card, card):
                continue
            get = lambda rx: (m.group(1) if rx and (m := re.search(rx, card, re.S)) else "")
            title, url, price, old = text(get(self.title)), get(self.url), money(get(self.price)), money(get(self.old))
            if not (title and url and price and old) or price >= old:
                continue
            url = urljoin(self.site, htmllib.unescape(url))
            aud = audience
            for rx, value in self.gender:
                if re.search(rx, card, re.I):
                    aud = value
                    break
            img = get(self.image)
            sizes_text = get(self.sizes_in) if self.sizes_in else card
            yield Item(
                store=self.store,
                sku=get(self.sku) or urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1],
                title=title,
                url=url,
                image=urljoin(self.site, htmllib.unescape(img)) if img else "",
                price=price,
                old_price=old,
                brand=text(get(self.brand)) or self.fixed_brand,
                path=text(get(self.path)),
                audience=aud,
                sizes=[text(s) for s in re.findall(self.sizes, sizes_text, re.S)] if self.sizes else [],
            )

    def scrape(self, http):
        for section, audience in self.sections:
            seen = set()
            base = urljoin(self.site, section)
            for n in range(1, self.pages + 1):
                html = http.get_optional(self.page_url(base, n))
                items = [it for it in self.parse(html, audience) if it.sku not in seen] if html else []
                if not items:  # страницы кончились (или за последней снова отдаётся последняя)
                    break
                seen.update(it.sku for it in items)
                yield from items
