"""LC Waikiki — каталог лежит в странице в переменной catalogModel.

Цена акции приходит в CampaignBadges, а LowestPriceInLastMonth — минимальная цена за месяц,
по ней проверяем, что скидка настоящая.
"""
import json
import re

from ..models import Item

NAME = "LC Waikiki"
SITE = "https://www.lcwaikiki.ua"
# Отдельной распродажи для девочек у LCW нет (меню детских разделов грузится скриптом) — пока только женское
SOURCES = [
    ("/mvc/women-sales", "women"),
]
MAX_PAGES = 15


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
    for path, source in SOURCES:
        for page in range(1, MAX_PAGES + 1):
            cat = _catalog(http.get(f"{SITE}{path}?PageIndex={page}"))
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
            if page >= cat.get("PageCount", 1):
                break
