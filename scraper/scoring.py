"""Проверка, настоящая ли скидка, и оценка «насколько интересно».

Флаги (показываются в приложении значками):
  ver   — скидка подтверждена: товар реально продавался по старой цене (видели сами или магазин публикует
          минимальную цену за 30 дней, равную старой)
  low   — самая низкая цена за последние 60 дней наблюдений
  drop  — подешевело со вчерашнего дня
  new   — товар со скидкой появился сегодня
  infl  — старая цена завышена: недавно товар продавался без скидки примерно по текущей цене
  up    — за последние 30 дней было дешевле, чем сейчас
  perm  — «скидка» висит больше месяца без изменений
  huge  — на маркетплейсе (старую цену пишет сам продавец) заявлено −85% и больше, и это ничем не подтверждено
"""
from dataclasses import dataclass, field
from statistics import median

from .models import Item

MARKETPLACES = {"kasta", "rozetka", "prom"}
HUGE = 0.85


@dataclass
class Verdict:
    declared: float          # скидка, которую пишет магазин (0..1)
    real: float              # скидка относительно реальной обычной цены (0..1)
    ref: float               # цена, от которой считаем реальную скидку
    min60: float | None      # минимальная цена за 60 дней наблюдений
    known_days: int          # сколько дней истории есть
    flags: list[str] = field(default_factory=list)
    score: float = 0.0


def evaluate(item: Item, past: list[tuple[float, float]], prev_price: float | None,
             is_new: bool) -> Verdict:
    p = item.price
    old = item.old_price if item.old_price and item.old_price > p else None
    declared = 1 - p / old if old else 0.0
    ref = old or p
    flags = []

    if old and item.lowest_30d:
        if item.lowest_30d >= old * 0.97:
            flags.append("ver")
        elif item.lowest_30d > p:
            ref = item.lowest_30d    # магазин сам признаёт, что за 30 дней было дешевле старой цены
        else:
            flags.append("up")       # за 30 дней уже продавали по такой же или меньшей цене

    min60 = None
    if past:
        prices = [pr for pr, _ in past]
        min60 = min(prices)
        regular = [pr for pr, o in past if not o or o <= pr]   # дни, когда товар был без скидки
        if len(past) >= 7 and old:
            if regular and max(regular) >= old * 0.95:
                if "ver" not in flags:
                    flags.append("ver")
            elif regular and median(regular) < old * 0.9:
                ref = min(ref, median(regular))
                if 1 - p / ref < declared - 0.1:
                    flags.append("infl")
        if p < min60 * 0.99 or (p <= min60 and max(prices) > p * 1.01):
            flags.append("low")
        recent = prices[-30:]
        if min(recent) < p * 0.97 and "up" not in flags:
            flags.append("up")
        if len(past) >= 30 and max(prices) <= p * 1.01 and min(prices) >= p * 0.99 and "ver" not in flags:
            flags.append("perm")

    if item.store in MARKETPLACES and declared >= HUGE and "ver" not in flags:
        flags.append("huge")
    if prev_price and p < prev_price * 0.98:
        flags.append("drop")
    if is_new and old:
        flags.append("new")

    real = max(0.0, 1 - p / ref) if ref > p else 0.0
    score = (real * 100 + 12 * ("low" in flags) + 8 * ("drop" in flags) + 6 * ("ver" in flags)
             + 4 * ("new" in flags) - 25 * ("infl" in flags) - 10 * ("up" in flags) - 8 * ("perm" in flags)
             - 25 * ("huge" in flags))
    return Verdict(declared, real, ref, min60, len(past), flags, round(score, 1))
