"""Megasport — данные каталога встроены в страницу (window.__PRELOADED_PROVIDER_CONTEXT__)."""
import json
import re

from ..models import Item

NAME = "Megasport"
SITE = "https://megasport.ua"
SOURCES = [
    ("/ua/catalog/sections-all/female/outlet/", "women"),
    ("/ua/catalog/sections-all/genders-all/outlet/child_gender-girls/", "girls"),
]
MAX_PAGES = 40


def _snapshot(html: str) -> dict[str, dict]:
    m = re.search(r'window\.__PRELOADED_PROVIDER_CONTEXT__ = JSON\.parse\((".*?")\);', html, re.S)
    if not m:
        raise ValueError("на странице нет данных каталога — разметка сайта изменилась")
    data = json.loads(json.loads(m.group(1)))
    return {json.loads(s["key"])["method"]: s["value"] for s in data["techStore"]["ssrDataSnapshot"]}


def _audience(p: dict, source: str) -> str:
    if source == "girls":
        return {"girls": "girls", "boys": "boys"}.get(p.get("childGender"), "kids")
    return {"female": "women", "male": "men", "child": "kids"}.get(p.get("sex"), "unisex")


def scrape(http):
    for path, source in SOURCES:
        for page in range(1, MAX_PAGES + 1):
            url = SITE + path + (f"page-{page}/" if page > 1 else "")
            snap = _snapshot(http.get(url))
            cat = snap["getCatalogData"]
            brands = snap.get("getBrands", {}).get("brandsRecord", {})
            types = snap.get("getProductTypes", {}).get("productsTypes", {})
            products = cat["productsMapper"]
            ids = cat["pages"].get(str(page))
            if not ids:  # за последней страницей сайт перенаправляет на первую
                break
            for pid in ids:
                p = products.get(str(pid))
                if not p or not p.get("price") or not p.get("salePrice"):
                    continue
                sizes = p.get("sizesEuro") or p.get("sizes") or []
                yield Item(
                    store="megasport",
                    sku=str(p["id"]),
                    title=p["name"],
                    url=f"{SITE}/ua/product/{p['unique']}/",
                    image=(p.get("images") or [""])[0],
                    price=float(p["salePrice"]),
                    old_price=float(p["price"]),
                    brand=brands.get(str(p.get("brandId")), {}).get("name", ""),
                    path=types.get(str(p.get("typeId")), {}).get("name", ""),
                    audience=_audience(p, source),
                    sizes=[str(s["size"]) for s in sizes if s.get("count", 1) > 0],
                )
            if page * cat["productsCountLimits"] >= cat["productsCount"]:
                break
