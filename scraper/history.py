"""История цен: для каждого товара храним только точки изменения цены, чтобы файл оставался маленьким."""
import datetime as dt
import gzip
import json
from pathlib import Path

EPOCH = dt.date(2024, 1, 1)


def day_num(d: dt.date | None = None) -> int:
    return ((d or dt.date.today()) - EPOCH).days


class History:
    """items[id] = {"fs": первый день, "ls": последний день, "pts": [[день, цена, старая_цена_или_0], ...]}"""

    def __init__(self, path: Path):
        self.path = path
        self.items: dict[str, dict] = {}
        if path.exists():
            with gzip.open(path, "rt", encoding="utf-8") as f:
                self.items = json.load(f)["items"]

    def past(self, item_id: str, today: int, window: int = 60) -> list[tuple[float, float]]:
        """(цена, старая цена) за каждый день наблюдений в окне [today-window, today-1]."""
        rec = self.items.get(item_id)
        if not rec:
            return []
        out = []
        pts = rec["pts"]
        for i, (d, price, old) in enumerate(pts):
            end = pts[i + 1][0] - 1 if i + 1 < len(pts) else rec["ls"]
            for x in range(max(d, today - window), min(end, today - 1) + 1):
                out.append((price, old))
        return out

    def last_price(self, item_id: str, today: int) -> float | None:
        rec = self.items.get(item_id)
        if not rec:
            return None
        pts = [p for p in rec["pts"] if p[0] < today]
        return pts[-1][1] if pts else None

    def first_seen(self, item_id: str) -> int | None:
        rec = self.items.get(item_id)
        return rec["fs"] if rec else None

    def record(self, item_id: str, today: int, price: float, old: float | None):
        old = old or 0
        rec = self.items.setdefault(item_id, {"fs": today, "ls": today, "pts": []})
        pts = rec["pts"]
        if pts and pts[-1][0] == today:      # повторный запуск в тот же день — перезаписываем
            pts[-1] = [today, price, old]
        elif not pts or pts[-1][1] != price or pts[-1][2] != old:
            pts.append([today, price, old])
        rec["ls"] = today

    def prune(self, today: int, keep_days: int = 180):
        self.items = {k: v for k, v in self.items.items() if v["ls"] >= today - keep_days}
        for v in self.items.values():       # точки старше окна не нужны, кроме последней перед ним
            old = [p for p in v["pts"] if p[0] < today - keep_days]
            if len(old) > 1:
                v["pts"] = old[-1:] + [p for p in v["pts"] if p[0] >= today - keep_days]

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(self.path, "wt", encoding="utf-8") as f:
            json.dump({"v": 1, "items": self.items}, f, separators=(",", ":"))
