"""Бренды группы LPP (Sinsay, Reserved, Cropp, House, Mohito) — одна платформа, один парсер.

Уценённые товары живут в отдельном разделе распродажи (например /all/rozprodazh-do-50), у которого
есть подразделы по отделам: l-sale-all — женщины, k-sale-all — дети, m- — мужчины, h- — дом.
Название раздела распродажи сезонное, поэтому находим его на главной странице.

Товары лежат в странице раздела (window.getCatalogData → products). Пагинация накопительная:
?page=N отдаёт первые ~50·(N+1) товаров, поэтому делаем один запрос с нужным N на раздел.
"""
import json
import re

from ..models import Item

PAGE = 20  # ≈1000 товаров на раздел, страница ~40 МБ


def _catalog(html: str) -> tuple[list[dict], int]:
    i = html.find("categoryBaseUrl:")
    if i < 0:
        raise ValueError("на странице нет getCatalogData — разметка сайта изменилась")
    block = html[i:html.index("</script>", i)]
    products = json.loads(re.search(r"\n\s+products:\s*(\[.*\]),\n", block).group(1))
    total = int(re.search(r"\n\s+productsQuantity:\s*(\d+)", block).group(1))
    return products, total


def _sale_root(http, site: str, fallback: str) -> str:
    m = re.search(r"/(all/rozprodazh[a-z0-9\-]*)", http.get(site))
    return m.group(1) if m else fallback


def make_scraper(store: str, site: str, sections: list[tuple[str, str]], brand: str,
                 sale_fallback: str = "all/rozprodazh"):
    def scrape(http):
        root = _sale_root(http, site, sale_fallback)
        for section, audience in sections:
            products, _ = _catalog(http.get(f"{site}{root}/{section}?page={PAGE}"))
            for p in products:
                # price/final_price — строки с пробелами («1 799»), берём числовые поля
                price, old = float(p.get("minQtyFinalPrice") or 0), float(p.get("minQtyRegularPrice") or 0)
                if not price or not old or price >= old:
                    continue
                yield Item(
                    store=store,
                    sku=p["sku"],
                    title=p.get("name") or "",
                    url=p["url"],
                    image=(p.get("img") or [""])[0],
                    price=price,
                    old_price=old,
                    brand=brand,
                    audience=audience,
                    hints=p.get("extendedName") or "",
                    sizes=[s["sizeName"].strip() for s in p.get("sizes") or [] if s.get("stock")],
                    lowest_30d=float(p["historyPrice"]) if p.get("historyPrice") else None,
                )
    return scrape


SINSAY = make_scraper("sinsay", "https://www.sinsay.com/ua/uk/",
                      [("l-sale-all", "women"), ("k-sale-all", "kids")],
                      brand="Sinsay", sale_fallback="all/rozprodazh-do-50")
