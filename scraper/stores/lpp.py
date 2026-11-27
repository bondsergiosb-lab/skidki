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
            yield from _items(store, brand, audience, products)
    return scrape


SALE = re.compile(r"rozprodazh|discounted|(?<![a-z])sale(?![a-z])|black-friday|chorna-pyatnytsya")
SKIP = re.compile(r"nemovl|/sales/|help|faq|guest|order|discount-codes")
AUDIENCES = [("girls", re.compile(r"divchat|girls")), ("boys", re.compile(r"khlop|boys")),
             ("kids", re.compile(r"/dity|kids")), ("women", re.compile(r"zhink|zhinky|women")),
             ("men", re.compile(r"cholov|(?<![a-z])men"))]


def _sale_sections(html: str, default_audience: str) -> list[tuple[str, str]]:
    """Разделы распродажи из меню главной: у каждого бренда и сезона они называются по-своему."""
    paths = {p.rstrip("/") for p in re.findall(r'(/ua/uk/[a-z0-9\-/]+)', html)
             if SALE.search(p) and not SKIP.search(p)}
    # подраздел не нужен, если уже берём весь раздел (…/discounted и …/discounted/dresses)
    top = sorted(p for p in paths if not any(p.startswith(q + "/") for q in paths))
    return [(p, next((a for a, rx in AUDIENCES if rx.search(p)), default_audience)) for p in top]


def _items(store: str, brand: str, audience: str, products: list[dict]):
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


def make_auto_scraper(store: str, site: str, brand: str, default_audience: str = "women", known: tuple = ()):
    """Для брендов, у которых распродажа разбита по отделам и меняет адрес: ищем разделы на главной
    (плюс known — постоянные адреса, которые меню иногда пишет без /ua/uk/).
    Сначала смотрим первую страницу раздела — если скидок нет (например, акция «в корзине»), дальше не листаем."""
    origin = re.match(r"https://[^/]+", site).group(0)

    def scrape(http):
        page = http.get(site) + "".join(f' "{p}"' for p in known)
        sections = _sale_sections(page, default_audience)
        if not sections:
            raise ValueError("на главной нет ссылок на распродажу — разметка сайта изменилась")
        for path, audience in sections:
            try:
                first, total = _catalog(http.get(origin + path))
            except ValueError:
                continue  # страница-витрина без каталога
            if not any(float(p.get("minQtyFinalPrice") or 0) < float(p.get("minQtyRegularPrice") or 0) for p in first):
                continue
            products = first
            if total > len(first):
                products, _ = _catalog(http.get(f"{origin}{path}?page={min(PAGE, total // 50)}"))
            yield from _items(store, brand, audience, products)
    return scrape


RESERVED = make_auto_scraper("reserved", "https://www.reserved.com/ua/uk/", "Reserved")
# у Cropp и House мужского больше, чем женского: пол без подсказки раздела определит классификатор
CROPP = make_auto_scraper("cropp", "https://www.cropp.com/ua/uk/", "Cropp", default_audience="")
HOUSE = make_auto_scraper("house", "https://www.housebrand.com/ua/uk/", "House", default_audience="")
MOHITO = make_auto_scraper("mohito", "https://www.mohito.com/ua/uk/", "Mohito", known=("/ua/uk/sale",))

SINSAY = make_scraper("sinsay", "https://www.sinsay.com/ua/uk/",
                      [("l-sale-all", "women"), ("m-sale-all", "men"), ("k-sale-all", "kids")],
                      brand="Sinsay", sale_fallback="all/rozprodazh-do-50")
