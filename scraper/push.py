"""Ежедневное уведомление в браузере и на iPhone (Web Push).

Подписки хранит маленький сервер на Cloudflare (worker/index.js) в хранилище KV: ключ sub:<id> — подписка
браузера и профиль. Отсюда (GitHub Actions) раз в день каждому подписчику отбираем 20 горящих скидок по тем же
правилам, что app.js (matches/pickHot) и Deals.java, и отправляем уведомление.

    python -m scraper.push config app/push.json         # адрес сервера и открытый ключ — для страницы
    python -m scraper.push setup worker/wrangler.toml   # хранилище подписок и адрес на workers.dev
    python -m scraper.push send                         # разослать (каждому не чаще раза в день)

Переменные окружения: CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, VAPID_PRIVATE_KEY
(закрытый ключ уведомлений: 32 байта в base64url). Без них команды ничего не делают.
"""
import base64
import datetime as dt
import json
import os
import re
import sys
from urllib.parse import quote, urlsplit
from zoneinfo import ZoneInfo

import httpx

WORKER = "skidki-push"
NAMESPACE = "skidki-subs"
KYIV = ZoneInfo("Europe/Kyiv")
COUNT = 20
MAX_SENT = 800
SEND_HOURS = range(8, 21)   # по Киеву: не будим ночью
WAIT_UNTIL = 16             # до 16:00 ждём свежих данных, потом шлём по вчерашним
SUSPICIOUS = {"infl", "perm", "huge"}
PUSH_HOSTS = re.compile(r"^(fcm\.googleapis\.com|updates\.push\.services\.mozilla\.com|web\.push\.apple\.com|"
                        r"[a-z0-9.-]+\.push\.apple\.com|[a-z0-9.-]+\.notify\.windows\.com)$")


# ---------- отбор скидок: те же правила, что в app.js ----------
def csv(s) -> list[str]:
    return [x.strip() for x in str(s or "").split(",") if x.strip()]


def size_tokens(s: str) -> list[str]:
    return [t for t in re.split(r"[^0-9A-ZА-ЯІЇЄҐ.]+", s.upper().replace(",", ".")) if t]


def size_match(item_sizes: list[str], wanted: list[str]) -> bool:
    for s in item_sizes:
        toks = size_tokens(s)
        rng = None if re.search(r"\d\s*(м|мес|m)(?![a-zа-яіїєґ])", s, re.I) else \
            re.search(r"(\d+(?:[.,]\d+)?)\s*[-–]\s*(\d+(?:[.,]\d+)?)", s)
        for w in wanted:
            if w in toks:
                return True
            if rng and re.fullmatch(r"\d+(\.\d+)?", w):
                a, b, x = float(rng.group(1).replace(",", ".")), float(rng.group(2).replace(",", ".")), float(w)
                if a < b and b - a <= 20 and a <= x <= b:
                    return True
    return False


def fits(it: dict, p: dict) -> bool | None:
    field = {"shoes": "shoeSizes", "clothes": "sizes"}.get(it["c"])
    wanted = [x.upper().replace(",", ".") for x in csv(p.get(field))] if field else []
    if not wanted or not it.get("z"):
        return None
    return size_match(it["z"], wanted)


def matches(it: dict, p: dict) -> bool:
    if p.get("audience") and it["a"] not in p["audience"]:
        return False
    if p.get("stores") and it["s"] not in p["stores"]:
        return False
    if p.get("cats") and it["c"] not in p["cats"]:
        return False
    if it["r"] < (p.get("minDiscount") or 0):
        return False
    if p.get("maxPrice") and it["p"] > p["maxPrice"]:
        return False
    if p.get("hideSuspicious", True) and SUSPICIOUS & set(it["f"]):
        return False
    if (it.get("b") or "").lower() in {b.lower() for b in csv(p.get("brandsHide"))}:
        return False
    if p.get("onlySize") and fits(it, p) is False:
        return False
    return True


def pick(items: list[dict], p: dict, sent: dict[str, float], limit: int = COUNT) -> list[dict]:
    """Фильтры профиля; «больше всего интересует» и любимые бренды первыми, внутри — по реальной скидке.
    Уже присланные не повторяются, пока не подешевеют."""
    fav = {b.lower() for b in csv(p.get("brandsFav"))}
    subs = set(p.get("subsFav") or [])
    out = [it for it in items if matches(it, p) and not (it["id"] in sent and it["p"] >= sent[it["id"]])]
    out.sort(key=lambda it: (-(it["sc"] in subs or (it.get("b") or "").lower() in fav), -it["r"], -it["k"]))
    return out[:limit]


def plural(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "горящая скидка"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "горящие скидки"
    return "горящих скидок"


def message(p: dict, hot: list[dict], stores: dict, site: str) -> dict:
    name = (p.get("name") or "").strip()
    lines = [f"−{it['r']}% · {round(it['p']):,} ₴ · {it['t']}".replace(",", " ") +
             (f" — {stores[it['s']]['name']}" if it["s"] in stores else "") for it in hot[:3]]
    return {
        "title": f"{name + ', с' if name else 'С'}егодня {len(hot)} {plural(len(hot))} 🔥",
        "body": "\n".join(lines),
        "url": site + "#hot=" + ",".join(it["id"] for it in hot),
    }


# ---------- Cloudflare ----------
class Cloudflare:
    def __init__(self, token: str, account: str):
        self.account = account
        self.api = httpx.Client(base_url=f"https://api.cloudflare.com/client/v4/accounts/{account}", timeout=60,
                                headers={"Authorization": f"Bearer {token}"})

    def call(self, method: str, path: str, **kw):
        r = self.api.request(method, path, **kw)
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code >= 400 or data.get("success") is False:
            raise RuntimeError(f"Cloudflare {method} {path}: {r.status_code} {data.get('errors') or r.text[:200]}")
        return data

    def namespace(self, create: bool = False) -> str | None:
        for ns in self.call("GET", "/storage/kv/namespaces", params={"per_page": 100})["result"]:
            if ns["title"] == NAMESPACE:
                return ns["id"]
        return self.call("POST", "/storage/kv/namespaces", json={"title": NAMESPACE})["result"]["id"] if create else None

    def subdomain(self, create: bool = False) -> str | None:
        r = self.api.get("/workers/subdomain")
        sub = (r.json().get("result") or {}).get("subdomain") if r.status_code == 200 else None
        if not sub and create:  # у нового аккаунта адреса *.workers.dev ещё нет
            sub = f"skidki-{base64.b32encode(os.urandom(5)).decode().lower()}"
            self.call("PUT", "/workers/subdomain", json={"subdomain": sub})
        return sub

    def keys(self, ns: str, prefix: str) -> list[str]:
        out, cursor = [], None
        while True:
            params = {"prefix": prefix, "limit": 1000, **({"cursor": cursor} if cursor else {})}
            data = self.call("GET", f"/storage/kv/namespaces/{ns}/keys", params=params)
            out += [k["name"] for k in data["result"]]
            cursor = (data.get("result_info") or {}).get("cursor")
            if not cursor:
                return out

    def get(self, ns: str, key: str):
        r = self.api.get(f"/storage/kv/namespaces/{ns}/values/{quote(key, safe='')}")
        return json.loads(r.text) if r.status_code == 200 else None

    def put_many(self, ns: str, pairs: dict[str, object]):
        for i in range(0, len(pairs), 5000):
            chunk = list(pairs.items())[i:i + 5000]
            self.call("PUT", f"/storage/kv/namespaces/{ns}/bulk",
                      json=[{"key": k, "value": json.dumps(v, ensure_ascii=False)} for k, v in chunk])

    def delete(self, ns: str, key: str):
        self.call("DELETE", f"/storage/kv/namespaces/{ns}/values/{quote(key, safe='')}")


def cloudflare() -> Cloudflare | None:
    token, account = os.environ.get("CLOUDFLARE_API_TOKEN"), os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    return Cloudflare(token, account) if token and account else None


def public_key(private_b64: str) -> str:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    raw = base64.urlsafe_b64decode(private_b64 + "=" * (-len(private_b64) % 4))
    key = ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())
    point = key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(point).decode().rstrip("=")


def site_url() -> str:
    owner, _, repo = os.environ.get("GITHUB_REPOSITORY", "bondsergiosb-lab/skidki").partition("/")
    return os.environ.get("PAGES_URL") or f"https://{owner.lower()}.github.io/{repo}/"


# ---------- команды ----------
def config(out: str):
    """push.json для страницы: куда отправлять подписку и открытый ключ. Пустой — уведомления в браузере выключены."""
    cf, private = cloudflare(), os.environ.get("VAPID_PRIVATE_KEY")
    cfg = {}
    if cf and private:
        sub = cf.subdomain()
        if sub:
            cfg = {"endpoint": f"https://{WORKER}.{sub}.workers.dev", "key": public_key(private)}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    print("push.json:", "настроен" if cfg else "уведомления в браузере пока не подключены")


def setup(toml: str):
    """Перед публикацией сервера: хранилище подписок, адрес *.workers.dev и wrangler.toml с номером хранилища."""
    cf = cloudflare()
    if not cf:
        print("Cloudflare не подключён (нет CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID)")
        return
    ns, sub = cf.namespace(create=True), cf.subdomain(create=True)
    origin = "https://" + urlsplit(site_url()).netloc
    with open(toml, "w", encoding="utf-8") as f:
        f.write(f'name = "{WORKER}"\nmain = "index.js"\ncompatibility_date = "2024-11-01"\nworkers_dev = true\n\n'
                f'[vars]\nORIGIN = "{origin}"\n\n[[kv_namespaces]]\nbinding = "SUBS"\nid = "{ns}"\n')
    print(f"сервер будет по адресу https://{WORKER}.{sub}.workers.dev")


def send():
    cf, private = cloudflare(), os.environ.get("VAPID_PRIVATE_KEY")
    if not (cf and private):
        print("уведомления в браузере не подключены — пропускаю")
        return
    from pywebpush import WebPushException, webpush

    now = dt.datetime.now(KYIV)
    today = now.date().isoformat()
    if now.hour not in SEND_HOURS:
        print("не время для уведомлений:", now.strftime("%H:%M"))
        return
    ns = cf.namespace()
    if not ns or cf.get(ns, "meta:done") == today:
        print("сегодня уже разослано" if ns else "подписчиков ещё нет")
        return
    site = site_url()
    data = httpx.get(site + "data/deals.json", timeout=120, follow_redirects=True).json()
    fresh = dt.datetime.fromisoformat(data["generated"]).astimezone(KYIV).date().isoformat() == today
    if not fresh and now.hour < WAIT_UNTIL:
        print("скидки за сегодня ещё не собраны — попробую позже")
        return

    sent_count, states, failed = 0, {}, False
    for key in cf.keys(ns, "sub:"):
        sid = key[4:]
        rec, state = cf.get(ns, key), cf.get(ns, "state:" + sid) or {}
        if not rec or state.get("last") == today:
            continue
        endpoint = rec["subscription"]["endpoint"]
        if not PUSH_HOSTS.match(urlsplit(endpoint).hostname or ""):
            continue
        sent = {i: p for i, p in state.get("sent", [])}
        hot = pick(data["items"], rec["profile"], sent)
        state["last"] = today
        if hot:
            try:
                webpush(subscription_info=rec["subscription"],
                        data=json.dumps(message(rec["profile"], hot, data["stores"], site), ensure_ascii=False),
                        vapid_private_key=private, vapid_claims={"sub": site}, ttl=12 * 3600)
                sent_count += 1
            except WebPushException as e:
                status = e.response.status_code if e.response is not None else 0
                if status in (404, 410):  # подписка больше не действует (удалили приложение, запретили уведомления)
                    for k in (key, "state:" + sid):
                        try:
                            cf.delete(ns, k)
                        except RuntimeError:
                            pass
                    continue
                print("не отправилось:", status, str(e)[:200])
                failed = True  # попробуем ещё раз при следующем запуске
                continue
            for it in hot:
                sent.pop(it["id"], None)
                sent[it["id"]] = it["p"]
            state["sent"] = [[i, p] for i, p in list(sent.items())[-MAX_SENT:]]
        states["state:" + sid] = state
    cf.put_many(ns, {**states, **({} if failed else {"meta:done": today})})
    print(f"отправлено уведомлений: {sent_count}, подписок обработано: {len(states)}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "config":
        config(sys.argv[2])
    elif cmd == "setup":
        setup(sys.argv[2])
    elif cmd == "send":
        send()
    else:
        sys.exit(__doc__)
