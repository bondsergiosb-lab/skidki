"""Проверки логики скидок и классификатора.  Запуск:  python -m tests.test_logic"""
import tempfile
from pathlib import Path

from scraper.classify import audience, baby_only, categorize
from scraper.history import History
from scraper.models import Item
from scraper.net import Robots
from scraper.push import message, pick, size_match
from scraper.scoring import evaluate


def item(price, old, lowest_30d=None):
    return Item(store="t", sku="1", title="x", url="", image="", price=price, old_price=old, lowest_30d=lowest_30d)


def history(points: list[tuple[int, float, float]], last_seen: int) -> tuple[History, int]:
    h = History(Path(tempfile.mkdtemp()) / "h.json.gz")
    for d, p, o in points:
        h.record("t:1", d, p, o)
    h.items["t:1"]["ls"] = last_seen
    return h, last_seen + 1


def test_inflated_old_price():
    # 30 дней продавали за 1000 без скидки, сегодня «2000 → 1000, −50%»
    h, today = history([(100, 1000, 0)], 129)
    v = evaluate(item(1000, 2000), h.past("t:1", today), h.last_price("t:1", today), False)
    assert "infl" in v.flags and v.real < 0.05, v


def test_verified_real_drop():
    # 30 дней за 1000 без скидки, сегодня 600 со старой ценой 1000
    h, today = history([(100, 1000, 0)], 129)
    v = evaluate(item(600, 1000), h.past("t:1", today), h.last_price("t:1", today), False)
    assert {"ver", "low", "drop"} <= set(v.flags) and abs(v.real - 0.4) < 0.01, v


def test_was_cheaper_recently():
    # неделю назад было 500, сейчас 700 при «старой» 1000
    h, today = history([(100, 1000, 0), (110, 500, 1000), (120, 700, 1000)], 129)
    v = evaluate(item(700, 1000), h.past("t:1", today), h.last_price("t:1", today), False)
    assert "up" in v.flags and "low" not in v.flags, v


def test_store_lowest_30d():
    # магазин сам пишет: минимальная цена за 30 дней = старой → подтверждено
    v = evaluate(item(500, 1000, lowest_30d=1000), [], None, True)
    assert "ver" in v.flags and "new" in v.flags and abs(v.real - 0.5) < 0.01
    # минимальная за 30 дней 700 → реальная скидка считается от 700
    v = evaluate(item(500, 1000, lowest_30d=700), [], None, False)
    assert abs(v.real - (1 - 500 / 700)) < 0.01 and v.declared == 0.5


def test_permanent_sale():
    h, today = history([(100, 700, 1000)], 140)
    v = evaluate(item(700, 1000), h.past("t:1", today), h.last_price("t:1", today), False)
    assert "perm" in v.flags, v


def test_huge_marketplace_discount():
    fake = Item(store="rozetka", sku="1", title="x", url="", image="", price=4169, old_price=62000)
    assert "huge" in evaluate(fake, [], None, False).flags
    brand = Item(store="house", sku="1", title="x", url="", image="", price=199, old_price=1399)
    assert "huge" not in evaluate(brand, [], None, False).flags   # у бренда старую цену пишет сам магазин


def test_history_roundtrip():
    h, today = history([(100, 1000, 0), (105, 900, 1000)], 109)
    assert h.past("t:1", today) == [(1000, 0)] * 5 + [(900, 1000)] * 5
    h.save()
    assert History(h.path).past("t:1", today) == h.past("t:1", today)


def test_classifier():
    assert categorize("Кросівки на масивній підошві", "") == ("shoes", "sneakers")
    assert categorize("W NSW CLUB FLC PANT", "Спортивні штани") == ("clothes", "bottoms")
    assert categorize("Плаття з оборкою", "") == ("clothes", "dresses")
    assert categorize("Светр жіночий трикотажний з коміром-поло", "Светри - Жінкам") == ("clothes", "knit")
    assert categorize("Тарілки, 2 шт.", "") is None
    assert audience("kids", "Плаття з оборкою", "") == "girls"
    assert audience("kids", "Футболка Star Wars", "") == "boys"
    assert audience("kids", "Шорти", "") == "kids"
    assert audience("", "Чоловіча куртка", "") == "men"
    assert audience("", "Куртка для хлопчика", "") == "boys"
    assert audience("", "Боді для немовлят", "") is None
    assert audience("women", "Худі", "") == "women"
    assert audience("", "Дитячі кеди Smash 3.0 Dino Sneakers Kids", "") == "boys"
    assert audience("", "Дитячі кросівки Carina Kids", "") == "kids"
    assert audience("", "Кросівки Speedcat OG Unisex", "") == "unisex"
    assert baby_only(["74 (6-9 м)", "80 (9-12 м)"])
    assert not baby_only(["80 (9-12 м)", "146 (10-11 р)"])
    assert not baby_only(["S I UA 44"]) and not baby_only([])


def test_robots():
    r = Robots("User-agent: *\nAllow: /\nCrawl-delay: 10\nDisallow: /mvc/\nDisallow: /*PageIndex=*\nDisallow: /*?\n"
               "Allow: /*offset=*\nDisallow: /x$\n\nUser-agent: Yandex\nDisallow: /\n")
    assert not r.allowed("https://a.ua/mvc/women-sales")             # длинное правило побеждает «Allow: /»
    assert not r.allowed("https://a.ua/women?PageIndex=2")
    assert r.allowed("https://a.ua/market/odyag/?offset=50")          # Allow длиннее, чем «Disallow: /*?»
    assert not r.allowed("https://a.ua/x") and r.allowed("https://a.ua/xy")
    assert r.allowed("https://a.ua/zhinky-odyah-t-10")
    assert r.crawl_delay == 10
    assert Robots("").allowed("https://a.ua/anything")


def test_push_pick():
    def deal(i, a="women", r=50, sc="dresses", c="clothes", b="X", z=(), f=(), p=1000):
        return {"id": f"s:{i}", "s": "s", "t": "t", "b": b, "a": a, "r": r, "k": r, "c": c, "sc": sc,
                "z": list(z), "f": list(f), "p": p}
    items = [deal(1, r=70), deal(2, a="men", r=90), deal(3, r=40, sc="boots", c="shoes"),
             deal(4, r=60, z=["XS"]), deal(5, r=80, f=["infl"]), deal(6, r=20), deal(7, r=45, b="Nike")]
    p = {"name": "Аня", "audience": ["women", "unisex"], "minDiscount": 30, "hideSuspicious": True,
         "onlySize": True, "sizes": "M", "subsFav": ["boots"], "brandsFav": "nike"}
    # мужское, сомнительная, слабая скидка и чужой размер — мимо; сапоги и Nike — первыми
    assert [x["id"] for x in pick(items, p, {})] == ["s:7", "s:3", "s:1"]
    # уже присылали — не повторяем, пока не подешевеет
    assert [x["id"] for x in pick(items, p, {"s:7": 1000, "s:1": 1200})] == ["s:3", "s:1"]
    assert size_match(["146 (10-11 р)"], ["11"]) and not size_match(["74 (6-9 м)"], ["7"])
    msg = message(p, pick(items, p, {}), {}, "https://x/")
    assert msg["title"] == "Аня, сегодня 3 горящие скидки 🔥" and msg["url"] == "https://x/#hot=s:7,s:3,s:1"


if __name__ == "__main__":
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print("ok ", name)
    print(f"все {len(tests)} проверок прошли")
