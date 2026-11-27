// Сервер подписок на ежедневное уведомление (Cloudflare Workers + хранилище KV).
//
// Страница присылает сюда подписку браузера и профиль (POST /sub) или отписывается (DELETE /sub).
// Сами уведомления раз в день рассылает scraper/push.py из GitHub Actions — он читает KV через API Cloudflare.
// Хранится только то, что нужно для отбора скидок: адрес подписки браузера, размеры и фильтры профиля.

// Адреса push-сервисов браузеров: Chrome/Android, Firefox, Safari/iPhone, Edge
const PUSH_HOSTS = /^(fcm\.googleapis\.com|updates\.push\.services\.mozilla\.com|web\.push\.apple\.com|[a-z0-9.-]+\.push\.apple\.com|[a-z0-9.-]+\.notify\.windows\.com)$/;
const MAX_BODY = 8000;

export default {
  async fetch(request, env) {
    const cors = {
      "Access-Control-Allow-Origin": env.ORIGIN,
      "Access-Control-Allow-Methods": "POST, DELETE, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Max-Age": "86400",
    };
    const reply = (status, text = "") => new Response(text, { status, headers: cors });
    if (request.method === "OPTIONS") return reply(204);
    if (new URL(request.url).pathname !== "/sub") return reply(404, "not found");
    if (request.method !== "POST" && request.method !== "DELETE") return reply(405);

    const raw = await request.text();
    if (raw.length > MAX_BODY) return reply(413, "too large");
    let body;
    try { body = JSON.parse(raw); } catch { return reply(400, "bad json"); }
    const id = String(body.id || "");
    if (!/^[0-9a-f-]{36}$/i.test(id)) return reply(400, "bad id");

    if (request.method === "DELETE") {
      await env.SUBS.delete("sub:" + id);
      return reply(200, "ok");
    }
    const sub = body.subscription || {};
    let host = "";
    try { host = new URL(sub.endpoint).hostname; } catch { /* проверка ниже */ }
    if (!String(sub.endpoint).startsWith("https://") || !PUSH_HOSTS.test(host)
        || typeof sub.keys?.p256dh !== "string" || typeof sub.keys?.auth !== "string") return reply(400, "bad subscription");
    if (typeof body.profile !== "object" || body.profile === null) return reply(400, "bad profile");

    await env.SUBS.put("sub:" + id, JSON.stringify({
      subscription: { endpoint: sub.endpoint, keys: { p256dh: sub.keys.p256dh, auth: sub.keys.auth } },
      profile: body.profile,
      updated: new Date().toISOString(),
    }));
    return reply(200, "ok");
  },
};
