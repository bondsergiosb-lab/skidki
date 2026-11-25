"""HTTP-клиент: вежливые паузы между запросами, повторы при сбоях, соблюдение robots.txt."""
import logging
import random
import time
import urllib.robotparser
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


class Http:
    def __init__(self, delay=(1.5, 3.0), retries=3):
        self.delay = delay
        self.retries = retries
        self.client = httpx.Client(
            headers={"User-Agent": UA, "Accept-Language": "uk-UA,uk;q=0.9,ru;q=0.8",
                     "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"},
            follow_redirects=True, timeout=60)
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._last: dict[str, float] = {}

    def allowed(self, url: str) -> bool:
        host = urlsplit(url).netloc
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.client.get(f"https://{host}/robots.txt", timeout=20)
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except httpx.HTTPError:
                rp.parse([])
            self._robots[host] = rp
        return self._robots[host].can_fetch("*", url)

    def get(self, url: str) -> str:
        if not self.allowed(url):
            raise Blocked(f"robots.txt запрещает {url}")
        host = urlsplit(url).netloc
        for attempt in range(1, self.retries + 1):
            wait = self._last.get(host, 0) + random.uniform(*self.delay) - time.time()
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
