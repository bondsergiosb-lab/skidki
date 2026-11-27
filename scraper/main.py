"""Ежедневный сбор скидок.

    python -m scraper.main                 # все магазины
    python -m scraper.main --only sinsay   # один магазин (для отладки)

Магазины опрашиваются параллельно (у каждого свой сайт и свои паузы), проверка скидок — по очереди.
Результат: deals.json со всеми скидками и части по отделам (w — женское, m — мужское, k — детское),
чтобы телефон скачивал только нужное профилю.
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import json
import logging
import time
from pathlib import Path

from .classify import audience, baby_only, categorize
from .history import History, day_num
from .net import Http
from .scoring import evaluate
from .stores import STORES

ROOT = Path(__file__).resolve().parents[1]
DEALS = ROOT / "app" / "data" / "deals.json"
HISTORY = ROOT / "data" / "history.json.gz"
MIN_DISCOUNT = 0.10   # меньше 10% — не скидка, в приложение не попадает
WORKERS = 8
# части данных: отдел → для кого товары (унисекс нужен и женщинам, и мужчинам)
SHARDS = {"w": ("women", "unisex"), "m": ("men", "unisex"), "k": ("girls", "boys", "kids")}

log = logging.getLogger("scraper")


def collect(sid: str, scrape, http: Http):
    """Собирает товары одного магазина; при сбое отдаёт то, что успели, и текст ошибки."""
    started, items, error = time.time(), [], ""
    try:
        for it in scrape(http):
            items.append(it)
    except Exception as e:  # один сломанный магазин не должен ронять остальные
        log.exception("%s: ошибка", sid)
        error = f"{type(e).__name__}: {e}"[:300]
    return items, error, round(time.time() - started)


def write_json(path: Path, data: dict):
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), "utf-8")


def run(only: list[str] | None, deals_path: Path, history_path: Path):
    http = Http()
    hist = History(history_path)
    today = day_num()
    previous = json.loads(deals_path.read_text("utf-8")) if deals_path.exists() else {"items": [], "stores": {}}
    chosen = {sid: v for sid, v in STORES.items() if not only or sid in only}

    with cf.ThreadPoolExecutor(WORKERS) as ex:
        futures = {sid: ex.submit(collect, sid, scrape, http) for sid, (_, _, scrape) in chosen.items()}

    items, stores_meta = [], {}
    for sid, (name, site, _) in chosen.items():
        scraped, error, seconds = futures[sid].result()
        meta = {"name": name, "url": site, "ok": not error, "error": error, "found": 0, "deals": 0}
        store_items, seen = [], set()
        # при первом сборе магазина «новыми» были бы все товары — значок «новое» ставим только со второго дня
        has_history = any(k.startswith(sid + ":") for k in hist.items)
        for it in scraped:
            if it.id in seen:
                continue
            seen.add(it.id)
            meta["found"] += 1
            cat = categorize(it.title, it.path)
            aud = audience(it.audience, it.title, f"{it.path} {it.hints}")
            if not cat or not aud or (aud in ("kids", "girls", "boys") and baby_only(it.sizes)):
                continue
            past = hist.past(it.id, today)
            v = evaluate(it, past, hist.last_price(it.id, today), is_new=has_history and hist.first_seen(it.id) in (None, today))
            hist.record(it.id, today, it.price, it.old_price)
            if max(v.real, v.declared) < MIN_DISCOUNT:
                continue
            store_items.append({
                "id": it.id, "s": sid, "t": it.title, "b": it.brand, "u": it.url, "i": it.image,
                "p": it.price, "o": it.old_price, "r": round(v.real * 100), "d": round(v.declared * 100),
                "a": aud, "c": cat[0], "sc": cat[1], "z": it.sizes, "f": v.flags,
                "m": v.min60, "k": v.score, "n": hist.first_seen(it.id),
            })
        if error and not store_items:
            # магазин сегодня не ответил — оставляем вчерашние товары, помечаем как устаревшие
            store_items = [x for x in previous["items"] if x["s"] == sid]
            meta["stale_since"] = previous.get("stores", {}).get(sid, {}).get("updated")
        else:
            meta["updated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")
        meta["deals"] = len(store_items)
        meta["seconds"] = seconds
        stores_meta[sid] = meta
        items += store_items
        log.info("%-10s найдено %5d, скидок %5d, %4d с, %s", sid, meta["found"], meta["deals"], seconds,
                 "OK" if meta["ok"] else meta["error"])

    if only:  # частичный запуск — остальные магазины берём из прошлого файла
        items += [x for x in previous["items"] if x["s"] not in only]
        stores_meta = {**{k: v for k, v in previous.get("stores", {}).items() if k not in only}, **stores_meta}

    items.sort(key=lambda x: -x["k"])
    hist.prune(today)
    hist.save()
    generated = dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")
    deals_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(deals_path, {"generated": generated, "today": today, "stores": stores_meta, "items": items})
    counts = {}
    for shard, auds in SHARDS.items():
        part = [x for x in items if x["a"] in auds]
        counts[shard] = len(part)
        write_json(deals_path.with_name(f"{shard}.json"), {"generated": generated, "items": part})
    write_json(deals_path.with_name("meta.json"), {"generated": generated, "today": today, "stores": stores_meta,
                                                   "shards": counts})
    log.info("итого %d скидок → %s (%s)", len(items), deals_path, counts)
    return stores_meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="id магазинов: " + ", ".join(STORES))
    ap.add_argument("--deals", type=Path, default=DEALS)
    ap.add_argument("--history", type=Path, default=HISTORY)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(threadName)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    meta = run(a.only, a.deals, a.history)
    if meta and not any(m["ok"] for m in meta.values()):
        raise SystemExit("ни один магазин не ответил")


if __name__ == "__main__":
    main()
