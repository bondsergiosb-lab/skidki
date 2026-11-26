"""LC Waikiki — каталог лежит в странице в переменной catalogModel.

Цена акции приходит в CampaignBadges, а LowestPriceInLastMonth — минимальная цена за месяц,
по ней проверяем, что скидка настоящая.

robots.txt запрещает разделы распродажи (/mvc/…) и листание страниц (PageIndex=), поэтому берём
первую страницу каждой женской и девичьей категории из меню главной — примерно половина товаров там со скидкой.
"""
import json
import re

from ..models import Item

NAME = "LC Waikiki"
SITE = "https://www.lcwaikiki.ua"
MAX_CATEGORIES = 40


def _categories(html: str) -> list[tuple[str, str]]:
    found = {}
    for path in re.findall(r'href="(/[a-z0-9\-]+-[tu]-\d+)"', html):
        if "nemovl" in path or "khlop" in path or "cholov" in path:
            continue
        if "zhin" in path:
            found.setdefault(path, "women")
        elif "divch" in path:
            found.setdefault(path, "girls")
    return list(found.items())[:MAX_CATEGORIES]


def _catalog(html: str) -> dict:
    m = re.search(r"var\s+catalogModel\s*=\s*(\{.*?\});\s*\n", html, re.S)
    if not m:
        raise ValueError("на странице нет catalogModel — разметка сайта изменилась")
    return json.loads(m.group(1))["CatalogList"]


def _sale_price(x: dict) -> float | None:
    for b in x.get("CampaignBadges") or []:
        if b.get("ShowDiscountedPrice") and b.get("DiscountedPrice"):
            return float(b["DiscountedPrice"])
    return float(x["DiscountedPriceValue"]) if x.get("DiscountedPriceValue") else None


def _audience(gender: str, source: str) -> str:
    g = (gender or "").lower()
    if "дівч" in g:
        return "girls"
    if "жін" in g:
        return "women"
    if "чолов" in g or "хлопч" in g:
        return "men"
    return source


def scrape(http):
    categories = _categories(http.get(SITE + "/"))
    if not categories:
        raise ValueError("в меню главной не нашли категорий — разметка сайта изменилась")
    for path, source in categories:
        html = http.get_optional(SITE + path)
        if html is None:
            continue
        cat = _catalog(html)
        for x in cat["Items"]:
            sale = _sale_price(x)
            regular = float(x.get("PriceValue") or 0)
            if not sale or not regular or sale >= regular:
                continue
            crumbs = x.get("BreadCrump") or {}
            yield Item(
                store="lcw",
                sku=str(x["OptionId"]),
                title=x.get("ProductDescription") or "",
                url=SITE + x["ModelUrl"],
                image=x.get("DefaultOptionImageUrl") or "",
                price=sale,
                old_price=regular,
                brand=x.get("Brand") or "LC Waikiki",
                path=" / ".join(filter(None, [x.get("Category"), crumbs.get("Level4")])),
                audience=_audience(x.get("Gender"), source),
                lowest_30d=x.get("LowestPriceInLastMonth") or None,
            )
