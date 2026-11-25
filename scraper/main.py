"""Ежедневный сбор скидок.

    python -m scraper.main                 # все магазины
    python -m scraper.main --only sinsay   # один магазин (для отладки)
"""
import argparse
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

log = logging.getLogger("scraper")


def run(only: list[str] | None, deals_path: Path, history_path: Path):
    http = Http()
    hist = History(history_path)
    today = day_num()
    previous = json.loads(deals_path.read_text("utf-8")) if deals_path.exists() else {"items": [], "stores": {}}

    items, stores_meta = [], {}
    for sid, (name, site, scrape) in STORES.items():
        if only and sid not in only:
            continue
        started = time.time()
        meta = {"name": name, "url": site, "ok": True, "error": "", "found": 0, "deals": 0}
        store_items, seen = [], set()
        # при первом сборе магазина «новыми» были бы все товары — значок «новое» ставим только со второго дня
        has_history = any(k.startswith(sid + ":") for k in hist.items)
        try:
            for it in scrape(http):
                if it.id in seen:
                    continue
                seen.add(it.id)
                meta["found"] += 1
                cat = categorize(it.title, it.path)
                aud = audience(it.audience, it.title, f"{it.path} {it.hints}")
                if not cat or not aud or (aud in ("kids", "girls") and baby_only(it.sizes)):
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
        except Exception as e:  # один сломанный магазин не должен ронять остальные
            log.exception("%s: ошибка", sid)
            meta.update(ok=False, error=f"{type(e).__name__}: {e}"[:300])
        if not meta["ok"] and not store_items:
            # магазин сегодня не ответил — оставляем вчерашние товары, помечаем как устаревшие
            store_items = [x for x in previous["items"] if x["s"] == sid]
            meta["stale_since"] = previous.get("stores", {}).get(sid, {}).get("updated")
        else:
            meta["updated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")
        meta["deals"] = len(store_items)
        meta["seconds"] = round(time.time() - started)
        stores_meta[sid] = meta
        items += store_items
        log.info("%-10s найдено %5d, скидок %5d, %s", sid, meta["found"], meta["deals"],
                 "OK" if meta["ok"] else meta["error"])

    if only:  # частичный запуск — остальные магазины берём из прошлого файла
        items += [x for x in previous["items"] if x["s"] not in only]
        stores_meta = {**{k: v for k, v in previous.get("stores", {}).items() if k not in only}, **stores_meta}

    items.sort(key=lambda x: -x["k"])
    hist.prune(today)
    hist.save()
    deals_path.parent.mkdir(parents=True, exist_ok=True)
    deals_path.write_text(json.dumps({
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
        "today": today, "stores": stores_meta, "items": items,
    }, ensure_ascii=False, separators=(",", ":")), "utf-8")
    log.info("итого %d скидок → %s", len(items), deals_path)
    return stores_meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="id магазинов: " + ", ".join(STORES))
    ap.add_argument("--deals", type=Path, default=DEALS)
    ap.add_argument("--history", type=Path, default=HISTORY)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    meta = run(a.only, a.deals, a.history)
    if meta and not any(m["ok"] for m in meta.values()):
        raise SystemExit("ни один магазин не ответил")


if __name__ == "__main__":
    main()
