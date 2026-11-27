// Оболочка приложения работает офлайн; данные о скидках — сначала из сети, без сети — последние сохранённые.
// Здесь же — ежедневное уведомление в браузере и на iPhone (его присылает scraper/push.py).
const SHELL = "skidki-shell-v6";
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
  if (url.pathname.includes("/data/") || url.pathname.endsWith("/push.json")) {
    e.respondWith(fetch(e.request).then(r => {
      const copy = r.clone();
      if (r.ok) caches.open(DATA).then(c => c.put(e.request, copy));
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

self.addEventListener("push", e => {
  let msg = {};
  try { msg = e.data ? e.data.json() : {}; } catch { msg = { title: e.data.text() }; }
  e.waitUntil(self.registration.showNotification(msg.title || "Скидки для своих", {
    body: msg.body || "", icon: "icons/icon-192.png", badge: "icons/icon-192.png", tag: "hot",
    data: { url: msg.url || "./" },
  }));
});
self.addEventListener("notificationclick", e => {
  e.notification.close();
  const url = new URL(e.notification.data?.url || "./", self.registration.scope).href;
  const hot = url.includes("#hot=") ? decodeURIComponent(url.split("#hot=")[1]) : null;
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(list => {
    const win = list.find(c => c.url.startsWith(self.registration.scope));
    if (win) {  // приложение уже открыто — показываем горящие в нём
      if (hot !== null) win.postMessage({ hot });
      return win.focus();
    }
    return self.clients.openWindow(url);
  }));
});
