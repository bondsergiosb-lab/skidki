"""Проверки логики скидок и классификатора.  Запуск:  python -m tests.test_logic"""
import tempfile
from pathlib import Path

from scraper.classify import audience, baby_only, categorize
from scraper.history import History
from scraper.models import Item
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
    assert audience("kids", "Футболка Star Wars", "") is None
    assert audience("kids", "Шорти", "") == "kids"
    assert audience("", "Чоловіча куртка", "") is None
    assert audience("women", "Худі", "") == "women"
    assert baby_only(["74 (6-9 м)", "80 (9-12 м)"])
    assert not baby_only(["80 (9-12 м)", "146 (10-11 р)"])
    assert not baby_only(["S I UA 44"]) and not baby_only([])


if __name__ == "__main__":
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print("ok ", name)
    print(f"все {len(tests)} проверок прошли")
