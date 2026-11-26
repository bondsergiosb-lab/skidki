// Оболочка приложения работает офлайн; данные о скидках — сначала из сети, без сети — последние сохранённые.
const SHELL = "skidki-shell-v4";
const DATA = "skidki-data";
const FILES = ["./", "index.html", "styles.css", "app.js", "manifest.webmanifest", "icons/icon-192.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== SHELL && k !== DATA).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (url.origin !== location.origin) return;  // картинки магазинов не трогаем
  if (url.pathname.endsWith("/data/deals.json")) {
    e.respondWith(fetch(e.request).then(r => {
      const copy = r.clone();
      caches.open(DATA).then(c => c.put(e.request, copy));
      return r;
    }).catch(() => caches.match(e.request, { ignoreSearch: true })));
    return;
  }
  // оболочка: отдаём из кэша, параллельно обновляем
  e.respondWith(caches.match(e.request).then(hit => {
    const net = fetch(e.request).then(r => {
      if (r.ok) {
        const copy = r.clone();  // клонируем сразу: страница может успеть прочитать тело ответа
        caches.open(SHELL).then(c => c.put(e.request, copy));
      }
      return r;
    }).catch(() => hit);
    return hit || net;
  }));
});
