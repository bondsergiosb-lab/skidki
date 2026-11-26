"""HTTP-клиент: вежливые паузы между запросами, повторы при сбоях, соблюдение robots.txt."""
import logging
import random
import re
import time
from urllib.parse import urlsplit

try:  # на домашнем ПК HTTPS может перехватывать антивирус — берём сертификаты из системы
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

import httpx

log = logging.getLogger(__name__)

UA = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36")


class Blocked(Exception):
    """Страница закрыта robots.txt или защитой от ботов."""


class Robots:
    """robots.txt по правилам Google: шаблоны с * и $, побеждает самое длинное правило, при равенстве — Allow.
    (urllib.robotparser звёздочки не понимает и пропускает то, что сайт просит не трогать.)"""

    def __init__(self, text: str):
        self.rules: list[tuple[int, bool, re.Pattern]] = []
        self.crawl_delay = 0.0  # сколько секунд сайт просит ждать между запросами
        agents, in_rules = set(), False
        for line in text.splitlines():
            key, _, value = line.split("#", 1)[0].partition(":")
            key, value = key.strip().lower(), value.strip()
            if key == "user-agent":
                if in_rules:  # началась новая группа
                    agents, in_rules = set(), False
                agents.add(value.lower())
            elif key == "crawl-delay":
                in_rules = True
                if "*" in agents:
                    try:
                        self.crawl_delay = min(float(value), 30.0)
                    except ValueError:
                        pass
            elif key in ("allow", "disallow"):
                in_rules = True
                if "*" in agents and value:
                    pattern = re.escape(value).replace(r"\*", ".*")
                    if pattern.endswith(r"\$"):
                        pattern = pattern[:-2] + "$"
                    self.rules.append((len(value), key == "allow", re.compile(pattern)))

    def allowed(self, url: str) -> bool:
        u = urlsplit(url)
        path = (u.path or "/") + (f"?{u.query}" if u.query else "")
        best = max(((n, allow) for n, allow, rx in self.rules if rx.match(path)), default=(0, True))
        return best[1]


class Http:
    def __init__(self, delay=(1.5, 3.0), retries=3):
        self.delay = delay
        self.retries = retries
        self.client = httpx.Client(
            headers={"User-Agent": UA, "Accept-Language": "uk-UA,uk;q=0.9,ru;q=0.8",
                     "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"},
            follow_redirects=True, timeout=60)
        self._robots: dict[str, Robots] = {}
        self._last: dict[str, float] = {}

    def allowed(self, url: str) -> bool:
        host = urlsplit(url).netloc
        if host not in self._robots:
            try:
                r = self.client.get(f"https://{host}/robots.txt", timeout=20)
                self._robots[host] = Robots(r.text if r.status_code == 200 else "")
            except httpx.HTTPError:
                self._robots[host] = Robots("")
        return self._robots[host].allowed(url)

    def get(self, url: str) -> str:
        if not self.allowed(url):
            raise Blocked(f"robots.txt запрещает {url}")
        host = urlsplit(url).netloc
        pause = max(random.uniform(*self.delay), self._robots[host].crawl_delay)
        for attempt in range(1, self.retries + 1):
            wait = self._last.get(host, 0) + pause - time.time()
            if wait > 0:
                time.sleep(wait)
            try:
                r = self.client.get(url)
                self._last[host] = time.time()
                if r.status_code in (403, 429) or "Just a moment..." in r.text[:5000]:
                    raise Blocked(f"{r.status_code} защита от ботов: {url}")
                r.raise_for_status()
                return r.text
            except httpx.HTTPError as e:
                self._last[host] = time.time()
                log.warning("попытка %s/%s %s: %s", attempt, self.retries, url, str(e).splitlines()[0])
                not_found = isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (404, 410)
                if attempt == self.retries or not_found:
                    raise
                time.sleep(5 * attempt)

    def get_optional(self, url: str) -> str | None:
        """Как get, но раздел, которого больше нет (404/410), не роняет весь магазин — вернёт None."""
        try:
            return self.get(url)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (404, 410):
                log.warning("раздела больше нет: %s", url)
                return None
            raise
