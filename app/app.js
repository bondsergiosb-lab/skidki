// Скидки для своих — проверенные скидки. Данные: data/meta.json + части w/m/k.json (обновляются раз в день).

const CATS = { clothes: "Одежда", shoes: "Обувь", bags: "Сумки", accessories: "Аксессуары" };
const SUBS = {
  outerwear: "Верхняя одежда", dresses: "Платья и юбки", knit: "Свитера и худи", tops: "Футболки и рубашки",
  bottoms: "Брюки и джинсы", suits: "Костюмы", underwear: "Бельё и пижамы", swim: "Купальники и плавки",
  sneakers: "Кроссовки и кеды", boots: "Ботинки и сапоги", shoes: "Туфли и босоножки", slippers: "Тапочки",
  bags: "Сумки и рюкзаки", accessories: "Шапки, шарфы и др.",
};
const AUD = {
  women: "Женское", men: "Мужское", girls: "Для девочек", boys: "Для мальчиков",
  kids: "Детское (пол не указан)", unisex: "Унисекс",
};
// В какой части данных лежат товары для кого (унисекс есть и в женской, и в мужской — берём ту, что уже нужна)
const SHARD_OF = { women: "w", unisex: "w", men: "m", girls: "k", boys: "k", kids: "k" };
const FLAGS = {
  ver: ["✓ проверено", "", "Скидка подтверждена: товар действительно продавался по старой цене."],
  low: ["мин. цена за 60 дн", "", "Самая низкая цена за всё время наблюдений (до 60 дней)."],
  drop: ["подешевело сегодня", "hot", "Цена снизилась со вчерашнего дня."],
  new: ["новое", "hot", "Товар со скидкой появился сегодня."],
  infl: ["завышенная старая цена", "warn", "Недавно товар продавался без скидки почти по нынешней цене — «старая цена» нарисована. Такие товары по умолчанию скрыты."],
  up: ["уже было дешевле", "warn", "За последние 30 дней товар уже продавался по такой же или меньшей цене."],
  perm: ["давно по этой цене", "warn", "«Скидка» не меняется больше месяца — скорее всего, это обычная цена."],
  huge: ["неправдоподобная скидка", "warn", "На маркетплейсе продавец сам пишет старую цену, а −85% и больше почти всегда означает нарисованную цену. Такие товары по умолчанию скрыты."],
};
const SUSPICIOUS = ["infl", "perm", "huge"];

const DEFAULT_PROFILE = {
  name: "", emoji: "", audience: ["women", "unisex"], sizes: "", shoeSizes: "", cats: [], subsFav: [],
  brandsFav: "", brandsHide: "", minDiscount: 30, maxPrice: 0, stores: [], onlySize: false, hideSuspicious: true,
};
// Первый запуск: для кого ищем скидки
const PRESETS = {
  women: { label: "Женское — для себя", emoji: "👩", name: "Я", audience: ["women", "unisex"] },
  men: { label: "Мужское — для себя", emoji: "👨", name: "Я", audience: ["men", "unisex"] },
  girls: { label: "Для дочери", emoji: "👧", name: "Дочь", audience: ["girls", "kids"], onlySize: true },
  boys: { label: "Для сына", emoji: "👦", name: "Сын", audience: ["boys", "kids"], onlySize: true },
};
// старые имена профилей по умолчанию → новые (у тех, кто установил раньше и не переименовывал сам)
const RENAMED = { "Мама": "Ксюшику", "Старшая": "Алюне", "Младшие": "Соне и Тоне" };

// ---------- состояние ----------
const KEY = "skidki.v1";
const saved = JSON.parse(localStorage.getItem(KEY) || "{}");
const S = {
  profiles: saved.profiles || [],
  active: saved.active ?? "",
  favs: saved.favs || {},
  notify: saved.notify || "",  // для какого профиля этот телефон получает ежедневное уведомление
  device: saved.device || crypto.randomUUID(),  // номер подписки на уведомления в браузере
  pushSig: saved.pushSig || "",  // что последним отправили на сервер уведомлений
};
for (const p of S.profiles) {
  if (RENAMED[p.name]) p.name = RENAMED[p.name];
  p.subsFav ||= [];
}
const save = () => localStorage.setItem(KEY, JSON.stringify({
  profiles: S.profiles, active: S.active, favs: S.favs, notify: S.notify, device: S.device, pushSig: S.pushSig,
}));
// Мост в Android-приложение (есть только в версии с уведомлениями)
const bridge = window.SkidkiApp;
// Сервер уведомлений для браузера и iPhone (push.json пишется при публикации сайта)
let PUSH = {};

let DATA = { items: [], stores: {} };
let byId = new Map();
const loaded = new Set();  // загруженные части данных
let wholeFile = false;     // старый формат: всё в deals.json
const ui = { cat: "", sub: "", q: "", sort: "discount", f: null, shown: 0, list: [], hot: [] };
// из уведомления приложение открывается с адресом …#hot=id1,id2,…
let pendingHot = location.hash.startsWith("#hot=") ? decodeURIComponent(location.hash.slice(5)) : "";

// ---------- утилиты ----------
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = n => new Intl.NumberFormat("uk-UA").format(Math.round(n)) + " ₴";
const list = s => String(s || "").split(",").map(x => x.trim()).filter(Boolean);
const lower = s => s.toLowerCase();
const sizeTokens = s => s.toUpperCase().replace(/,/g, ".").split(/[^0-9A-ZА-ЯІЇЄҐ.]+/).filter(Boolean);
const EPOCH = Date.UTC(2024, 0, 1);
const dayToDate = d => new Date(EPOCH + d * 864e5).toLocaleDateString("ru-RU", { day: "numeric", month: "long" });
const isIOS = /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
const standalone = navigator.standalone || matchMedia("(display-mode: standalone)").matches;
async function fetchJson(url) {
  const r = await fetch(url, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

function profile() {
  if (S.active === "all") {
    // «Все» — все профили сразу: для кого — объединение, минимальная скидка — самая мягкая
    const auds = S.profiles.some(p => !p.audience.length) ? [] : [...new Set(S.profiles.flatMap(p => p.audience))];
    return { ...DEFAULT_PROFILE, id: "all", audience: auds, minDiscount: 10 };
  }
  return S.profiles.find(p => p.id === S.active) || S.profiles[0] || { ...DEFAULT_PROFILE, id: "" };
}

// Подходит ли размер: «S» найдёт «S I UA 44», «11» найдёт «146 (10-11 р)» и «10-12», «152» найдёт «150-155»
function sizeMatch(itemSizes, wanted) {
  for (const s of itemSizes) {
    const toks = sizeTokens(s);
    // «(9-12 м)» — возраст в месяцах, не годы: диапазон не используем
    const range = /\d\s*(м|мес|m)(?![a-zа-яіїєґ])/i.test(s) ? null : s.match(/(\d+(?:[.,]\d+)?)\s*[-–]\s*(\d+(?:[.,]\d+)?)/);
    for (const w of wanted) {
      if (toks.includes(w)) return true;
      if (range && /^\d+(\.\d+)?$/.test(w)) {
        const a = +range[1].replace(",", "."), b = +range[2].replace(",", "."), x = +w;
        if (a < b && b - a <= 20 && x >= a && x <= b) return true;
      }
    }
  }
  return false;
}
function wantedSizes(it, f) {
  if (it.c === "shoes") return list(f.shoeSizes).map(x => x.toUpperCase().replace(",", "."));
  if (it.c === "clothes") return list(f.sizes).map(x => x.toUpperCase().replace(",", "."));
  return [];  // сумки и аксессуары — без размеров
}
// true — размер подходит, false — нет, null — неизвестно (магазин не отдаёт размеры или профиль без размеров)
function fits(it, f) {
  const w = wantedSizes(it, f);
  if (!w.length || !it.z || !it.z.length) return null;
  return sizeMatch(it.z, w);
}

// ---------- фильтрация и сортировка ----------
// Фильтры профиля. Те же правила — в уведомлениях: Deals.java (Android) и scraper/push.py (браузер, iPhone).
function matches(it, f) {
  if (f.audience.length && !f.audience.includes(it.a)) return false;
  if (f.stores.length && !f.stores.includes(it.s)) return false;
  if (f.cats.length && !f.cats.includes(it.c)) return false;
  if (it.r < f.minDiscount) return false;
  if (f.maxPrice && it.p > f.maxPrice) return false;
  if (f.hideSuspicious && it.f.some(x => SUSPICIOUS.includes(x))) return false;
  if (f._hide.length && f._hide.includes(lower(it.b))) return false;
  if (f.onlySize && fits(it, f) === false) return false;
  return true;
}
function passes(it, f, skipCat = false) {
  if (!matches(it, f)) return false;
  if (!skipCat && ui.cat && it.c !== ui.cat) return false;
  if (!skipCat && ui.sub && it.sc !== ui.sub) return false;
  if (ui.q) {
    const hay = it._hay || (it._hay = lower(`${it.t} ${it.b} ${DATA.stores[it.s]?.name || ""} ${SUBS[it.sc] || ""}`));
    if (!ui.q.split(/\s+/).every(w => hay.includes(w))) return false;
  }
  return true;
}
function personalScore(it, f) {
  let k = it.k;
  if (f._fav.includes(lower(it.b))) k += 25;
  if ((f.subsFav || []).includes(it.sc)) k += 15;  // «больше всего интересует»
  if (it.a === "kids") k -= 5;  // явно «для девочек/мальчиков» — выше, чем детское без пола
  if (fits(it, f) === true) k += 8;
  return k;
}
const SORTS = {
  best: (a, b) => b._ps - a._ps,
  discount: (a, b) => b.r - a.r || b._ps - a._ps,
  cheap: (a, b) => a.p - b.p,
  new: (a, b) => (b.n || 0) - (a.n || 0) || b._ps - a._ps,
};
function prepareFilter(f) {
  return { ...f, _fav: list(f.brandsFav).map(lower), _hide: list(f.brandsHide).map(lower) };
}
// Горящие скидки для уведомления: «больше всего интересует» и любимые бренды первыми, внутри — по реальной скидке
function pickHot(p, limit = 20) {
  const f = prepareFilter(structuredClone(p));
  const pri = it => (f.subsFav || []).includes(it.sc) || f._fav.includes(lower(it.b)) ? 1 : 0;
  return DATA.items.filter(it => matches(it, f))
    .sort((a, b) => pri(b) - pri(a) || b.r - a.r || b.k - a.k).slice(0, limit);
}

// ---------- данные ----------
function shardsFor(profiles) {
  if (wholeFile) return [];
  if (!profiles.length || profiles.some(p => !p.audience.length)) return ["w", "m", "k"];
  return [...new Set(profiles.flatMap(p => {
    const s = p.audience.filter(a => a !== "unisex").map(a => SHARD_OF[a]).filter(Boolean);
    return p.audience.includes("unisex") && !s.includes("w") && !s.includes("m") ? [...s, "w"] : s;
  }))];
}
async function ensureData(profiles = S.profiles) {
  const need = shardsFor(profiles).filter(s => !loaded.has(s));
  if (!need.length) return;
  const parts = await Promise.all(need.map(s => fetchJson(`data/${s}.json`)));
  parts.forEach((part, i) => {
    loaded.add(need[i]);
    for (const it of part.items) if (!byId.has(it.id)) { byId.set(it.id, it); DATA.items.push(it); }
  });
  DATA.items.sort((a, b) => b.k - a.k);
}

// ---------- отрисовка ----------
function renderProfiles() {
  const chips = [...(S.profiles.length > 1 ? [{ id: "all", name: "Все", emoji: "✨" }] : []), ...S.profiles];
  $("#profiles").innerHTML = chips.map(p =>
    `<button class="chip ${p.id === profile().id ? "on" : ""}" data-id="${esc(p.id)}">${esc(p.emoji)} ${esc(p.name)}</button>`).join("");
}
function renderCats(f) {
  const cc = {}, sc = {};
  let total = 0;
  for (const it of DATA.items) {
    if (!passes(it, f, true)) continue;
    total++;
    cc[it.c] = (cc[it.c] || 0) + 1;
    if (it.c === ui.cat) sc[it.sc] = (sc[it.sc] || 0) + 1;
  }
  $("#cats").innerHTML = [["", "Все", total], ...Object.entries(CATS).filter(([k]) => cc[k]).map(([k, v]) => [k, v, cc[k]])]
    .map(([k, v, n]) => `<button class="chip ${ui.cat === k ? "on" : ""}" data-cat="${k}">${v}<span class="n">${n}</span></button>`).join("");
  const subs = Object.entries(sc).sort((a, b) => b[1] - a[1]);
  $("#subcats").innerHTML = ui.cat && subs.length > 1
    ? [["", "Все", 0], ...subs.map(([k, n]) => [k, SUBS[k] || k, n])]
        .map(([k, v, n]) => `<button class="chip ${ui.sub === k ? "on" : ""}" data-sub="${k}">${v}${n ? `<span class="n">${n}</span>` : ""}</button>`).join("")
    : "";
}
function tagsHtml(it, max = 2) {
  return it.f.filter(x => FLAGS[x]).slice(0, max)
    .map(x => `<span class="tag ${FLAGS[x][1]}">${FLAGS[x][0]}</span>`).join("");
}
function brandAndStore(it) {  // «House · House» → «House»
  const store = DATA.stores[it.s]?.name || it.s;
  return it.b && lower(it.b) !== lower(store) ? [it.b, store] : [store];
}
function cardHtml(it, extra = "") {
  const fav = S.favs[it.id] ? "on" : "";
  return `<article class="item ${extra}" data-id="${esc(it.id)}">
    <div class="img"><img loading="lazy" referrerpolicy="no-referrer" src="${esc(it.i)}" alt="">
      ${it.r ? `<span class="badge">−${it.r}%</span>` : ""}
      <button class="fav ${fav}" data-fav="${esc(it.id)}" aria-label="В избранное"><svg viewBox="0 0 24 24"><path d="M12 21s-8-5.3-8-11a4.5 4.5 0 0 1 8-2.8A4.5 4.5 0 0 1 20 10c0 5.7-8 11-8 11z"/></svg></button>
    </div>
    <div class="body">
      <div class="price">${money(it.p)}${it.o ? `<s>${money(it.o)}</s>` : ""}</div>
      <div class="title">${esc(it.t)}</div>
      <div class="meta">${brandAndStore(it).map(esc).join(" · ")}</div>
      <div class="tags">${tagsHtml(it)}</div>
    </div></article>`;
}
function render() {
  const f = ui.f;
  renderCats(f);
  ui.list = DATA.items.filter(it => passes(it, f));
  for (const it of ui.list) it._ps = personalScore(it, f);
  ui.list.sort(SORTS[ui.sort]);
  ui.shown = 0;
  $("#grid").innerHTML = "";
  $("#count").textContent = `${ui.list.length} товаров`;
  $("#empty").hidden = ui.list.length > 0;
  const changed = filterDiff();
  $("#filter-count").hidden = !changed;
  $("#filter-count").textContent = changed;
  more();
}
function more() {
  const next = ui.list.slice(ui.shown, ui.shown + 40);
  $("#grid").insertAdjacentHTML("beforeend", next.map(it => cardHtml(it)).join(""));
  ui.shown += next.length;
}
function filterDiff() {  // сколько фильтров отличается от профиля
  const p = profile();
  return ["minDiscount", "maxPrice", "onlySize", "hideSuspicious", "stores", "audience"]
    .filter(k => JSON.stringify(ui.f[k]) !== JSON.stringify(p[k])).length;
}

// ---------- карточка товара ----------
function openDetail(id) {
  const it = byId.get(id) || S.favs[id];
  if (!it) return;
  const f = ui.f;
  const want = wantedSizes(it, f);
  const store = DATA.stores[it.s]?.name || it.s;
  const lines = [];
  if (it.d && it.d - it.r >= 3) lines.push(`Магазин пишет −${it.d}%, но по нашим наблюдениям реальная скидка −${it.r}%.`);
  for (const x of it.f || []) if (FLAGS[x]) lines.push(FLAGS[x][2]);
  if (it.m && it.m < it.p) lines.push(`Минимальная цена за 60 дней: ${money(it.m)}.`);
  if (it.n) lines.push(`Отслеживаем этот товар с ${dayToDate(it.n)}.`);
  $("#detail-body").innerHTML = `
    <img class="detail-img" referrerpolicy="no-referrer" src="${esc(it.i)}" alt="">
    <div class="detail-price">${money(it.p)}${it.o ? `<s>${money(it.o)}</s>` : ""} ${it.r ? `<span class="badge" style="position:static">−${it.r}%</span>` : ""}</div>
    <div>${esc(it.t)}</div>
    <div class="meta">${[...brandAndStore(it), SUBS[it.sc]].filter(Boolean).map(esc).join(" · ")}</div>
    ${lines.length ? `<div class="explain">${lines.map(esc).join("<br>")}</div>` : ""}
    ${it.z && it.z.length ? `<div class="label">Размеры в наличии</div>
      <div class="sizes">${it.z.map(s => `<span class="${want.length && sizeMatch([s], want) ? "mine" : ""}">${esc(s)}</span>`).join("")}</div>`
      : `<p class="muted">Магазин не показывает размеры в каталоге — уточните на сайте.</p>`}
    <a class="btn-primary" href="${esc(it.u)}" target="_blank" rel="noopener">Открыть в ${esc(store)}</a>
    <div style="height:8px"></div>
    <button type="button" class="btn-secondary" data-fav="${esc(it.id)}">${S.favs[it.id] ? "Убрать из избранного" : "♡ В избранное"}</button>`;
  $("#detail").showModal();
}

// ---------- избранное ----------
function toggleFav(id) {
  if (S.favs[id]) delete S.favs[id];
  else {
    const it = byId.get(id);
    if (!it) return;
    const { _hay, _ps, ...snap } = it;
    S.favs[id] = { ...snap, savedPrice: it.p, savedAt: DATA.today };
  }
  save();
  document.querySelectorAll(`[data-fav="${CSS.escape(id)}"]`).forEach(b => {
    b.classList.toggle("on", !!S.favs[id]);
    if (!b.classList.contains("fav")) b.textContent = S.favs[id] ? "Убрать из избранного" : "♡ В избранное";
  });
  if ($("#view-favs").classList.contains("active")) renderFavs();
}
function renderFavs() {
  const favs = Object.values(S.favs).sort((a, b) => (b.savedAt || 0) - (a.savedAt || 0));
  $("#fav-empty").hidden = favs.length > 0;
  $("#fav-grid").innerHTML = favs.map(snap => {
    const cur = byId.get(snap.id);
    const it = cur || snap;
    let note = "";
    if (!cur) note = `<span class="tag warn">нет в сегодняшних скидках</span>`;
    else if (cur.p < snap.savedPrice) note = `<span class="tag hot">подешевело: было ${money(snap.savedPrice)}</span>`;
    else if (cur.p > snap.savedPrice) note = `<span class="tag warn">подорожало: было ${money(snap.savedPrice)}</span>`;
    return cardHtml({ ...it, f: [] }, cur ? "" : "gone").replace('<div class="tags"></div>', `<div class="tags">${note}</div>`);
  }).join("");
}

// ---------- фильтры (шторка) ----------
function checks(name, options, selected, type = "checkbox") {
  return `<div class="checks">${Object.entries(options).map(([k, v]) =>
    `<label class="chip ${selected.includes(k) ? "on" : ""}"><input type="${type}" hidden name="${name}" value="${esc(k)}" ${selected.includes(k) ? "checked" : ""}>${esc(v)}</label>`).join("")}</div>`;
}
function filterFields(f, prefix) {
  const stores = Object.fromEntries(Object.entries(DATA.stores).map(([k, v]) => [k, v.name]));
  return `
    <div class="field"><label>Скидка от <b data-out="${prefix}minDiscount">${f.minDiscount}</b>%</label>
      <input type="range" name="minDiscount" min="10" max="80" step="5" value="${f.minDiscount}"></div>
    <div class="field"><label>Цена до, ₴</label>
      <input type="number" name="maxPrice" inputmode="numeric" placeholder="без ограничения" value="${f.maxPrice || ""}"></div>
    <div class="field"><span class="label">Для кого</span>${checks("audience", AUD, f.audience)}
      <div class="hint">Ничего не выбрано — показывать всё.</div></div>
    <div class="field"><span class="label">Магазины</span>${checks("stores", stores, f.stores)}
      <div class="hint">Ничего не выбрано — все магазины.</div></div>
    <label class="toggle">Только мои размеры<input type="checkbox" name="onlySize" ${f.onlySize ? "checked" : ""}></label>
    <div class="hint">Товары, у которых магазин не показывает размеры, тоже остаются.</div>
    <label class="toggle">Скрывать сомнительные скидки<input type="checkbox" name="hideSuspicious" ${f.hideSuspicious ? "checked" : ""}></label>`;
}
function readFields(form, target) {
  target.minDiscount = +form.elements.minDiscount.value;
  target.maxPrice = +form.elements.maxPrice.value || 0;
  target.onlySize = form.elements.onlySize.checked;
  target.hideSuspicious = form.elements.hideSuspicious.checked;
  for (const name of ["audience", "stores", "cats", "subsFav"]) {
    if (form.querySelector(`[name="${name}"]`)) target[name] = [...form.querySelectorAll(`[name="${name}"]:checked`)].map(x => x.value);
  }
}
function openFilters() {
  $("#filters-body").innerHTML = filterFields(ui.f, "flt-") +
    (S.active !== "all" ? `<div class="sheet-foot"><button type="button" id="save-to-profile" class="btn-secondary">Сохранить в профиль «${esc(profile().name)}»</button></div>` : "");
  $("#filters").showModal();
}

// ---------- первый запуск и новый профиль ----------
function renderWelcome() {
  const first = !S.profiles.length;
  $("#welcome").innerHTML = `
    ${first ? `<h2>Добро пожаловать!</h2>
      <p>Каждое утро приложение собирает скидки на одежду, обувь, сумки и аксессуары в ${Object.keys(DATA.stores).length || "десятках"}
        магазинов Украины, проверяет, что скидка <b>настоящая</b>, и показывает лучшее под ваши размеры и вкус.
        Настройте поиск — это займёт минуту. Всё хранится только на вашем телефоне.</p>`
      : `<h2>Новый профиль</h2><p class="muted">Например, для мужа, дочери или сына — у каждого свои размеры и фильтры.</p>`}
    <form id="welcome-form">
      <div class="field"><span class="label">Для кого ищем скидки</span>
        ${checks("preset", Object.fromEntries(Object.entries(PRESETS).map(([k, v]) => [k, `${v.emoji} ${v.label}`])), [], "radio")}</div>
      <div class="field"><label>Имя профиля</label><input type="text" name="name" placeholder="например: Я, Аня, Сын"></div>
      <div class="field"><label>Размеры одежды</label>
        <input type="text" name="sizes" placeholder="например: S, M, 44  или для детей: 146, 152">
        <div class="hint">Через запятую. Можно пропустить и заполнить потом в «Настройках».</div></div>
      <div class="field"><label>Размеры обуви</label><input type="text" name="shoeSizes" placeholder="например: 37, 38"></div>
      <div class="field"><span class="label">Больше всего интересует</span>${checks("subsFav", SUBS, [])}
        <div class="hint">Эти вещи будут первыми в подборке и в ежедневном уведомлении.</div></div>
      <div class="field"><label>Скидка от <b data-out="w-minDiscount">30</b>%</label>
        <input type="range" name="minDiscount" min="10" max="80" step="5" value="30"></div>
      <p id="welcome-error" class="bad" hidden>Выберите, для кого ищем скидки.</p>
      <button class="btn-primary" type="submit">${first ? "Показать скидки" : "Создать профиль"}</button>
      ${first ? "" : `<div style="height:8px"></div><button type="button" class="btn-secondary" data-view-go="settings">Отмена</button>`}
    </form>`;
}
async function createProfile(form) {
  const preset = PRESETS[form.elements.preset.value];
  const first = !S.profiles.length;
  const { label, ...base } = preset;
  const p = {
    ...structuredClone(DEFAULT_PROFILE), ...structuredClone(base), id: "p" + Date.now(),
    name: form.elements.name.value.trim() || base.name,
    sizes: form.elements.sizes.value.trim(), shoeSizes: form.elements.shoeSizes.value.trim(),
    subsFav: [...form.querySelectorAll('[name="subsFav"]:checked')].map(x => x.value),
    minDiscount: +form.elements.minDiscount.value,
  };
  S.profiles.push(p);
  S.active = p.id;
  if (first) S.notify = p.id;  // первый профиль сразу получает ежедневное уведомление
  save();
  document.body.classList.remove("onboarding");
  if (first) syncNotify(true);  // запрос разрешения — пока ещё идёт нажатие на кнопку
  try { await ensureData(); } catch { $("#updated").textContent = "нет связи"; }
  setProfile(p.id);
  showView("deals");
}

// ---------- настройки ----------
function renderSettings() {
  $("#settings").innerHTML = S.profiles.map(p => `
    <details class="profile-card" data-pid="${esc(p.id)}">
      <summary>${esc(p.emoji)} ${esc(p.name)}</summary>
      <form class="inner">
        <div class="field"><label>Имя и смайлик</label>
          <div style="display:flex;gap:8px"><input type="text" name="emoji" value="${esc(p.emoji)}" style="width:64px">
          <input type="text" name="name" value="${esc(p.name)}"></div></div>
        <div class="field"><label>Размеры одежды</label>
          <input type="text" name="sizes" value="${esc(p.sizes)}" placeholder="например: S, M, 44  или  146, 152, 11">
          <div class="hint">Через запятую. Для детей можно рост (146, 152) и возраст (11, 12).</div></div>
        <div class="field"><label>Размеры обуви</label>
          <input type="text" name="shoeSizes" value="${esc(p.shoeSizes)}" placeholder="например: 37, 37.5, 38"></div>
        <div class="field"><span class="label">Что интересно</span>${checks("cats", CATS, p.cats)}
          <div class="hint">Ничего не выбрано — все категории.</div></div>
        <div class="field"><span class="label">Больше всего интересует</span>${checks("subsFav", SUBS, p.subsFav || [])}
          <div class="hint">Эти вещи идут первыми в «Лучшее для меня» и в ежедневном уведомлении с горящими скидками.</div></div>
        <div class="field"><label>Любимые бренды (поднимаются выше)</label>
          <input type="text" name="brandsFav" value="${esc(p.brandsFav)}" placeholder="Nike, Adidas, Puma"></div>
        <div class="field"><label>Не показывать бренды</label>
          <input type="text" name="brandsHide" value="${esc(p.brandsHide)}" placeholder="через запятую"></div>
        ${filterFields(p, p.id + "-")}
        <div class="row-btns"><button type="button" class="btn-secondary" data-del="${esc(p.id)}">Удалить профиль</button></div>
      </form>
    </details>`).join("") +
    `<button type="button" class="btn-secondary" id="add-profile">+ Добавить профиль</button>`;

  const st = Object.values(DATA.stores);
  $("#store-status").innerHTML = st.length ? st.map(s => `<div class="store-row"><span>${esc(s.name)}</span>
    <span class="${s.ok ? "ok" : "bad"}">${s.ok ? `${s.deals} скидок` : `не ответил, данные от ${s.stale_since ? new Date(s.stale_since).toLocaleDateString("ru-RU") : "—"}`}</span></div>`).join("")
    : `<p class="muted">Данные ещё не загружены.</p>`;
  $(".legend").innerHTML = Object.values(FLAGS).map(([t, cls, d]) => `<li><span class="tag ${cls}">${t}</span> ${esc(d)}</li>`).join("");
  renderNotify();
}

// ---------- ежедневное уведомление ----------
// Android-приложение считает и показывает его само; в браузере и на iPhone присылает сервер (scraper/push.py).
const webPush = () => !bridge && "PushManager" in window && "serviceWorker" in navigator && "Notification" in window;
function notifyProfile(p) {  // то, что нужно серверу для отбора скидок
  const keys = ["name", "audience", "stores", "cats", "subsFav", "brandsFav", "brandsHide", "minDiscount", "maxPrice",
    "hideSuspicious", "onlySize", "sizes", "shoeSizes"];
  return Object.fromEntries(keys.map(k => [k, p[k]]));
}
let pushTimer;
function syncNotify(now = false) {
  const p = S.profiles.find(x => x.id === S.notify);
  if (bridge) { bridge.setNotify(p ? JSON.stringify(p) : ""); return; }
  if (!webPush() || !PUSH.endpoint) return;
  clearTimeout(pushTimer);
  if (now) enablePush();
  else pushTimer = setTimeout(() => syncPush().catch(() => {}), 1500);
}
async function enablePush() {
  try {
    if (S.notify && Notification.permission !== "granted" && (await Notification.requestPermission()) !== "granted") {
      renderNotify();
      return;
    }
    await syncPush();
  } catch (e) {
    console.warn("уведомления:", e);
  }
  renderNotify();
}
async function syncPush() {
  const p = S.profiles.find(x => x.id === S.notify);
  const reg = await navigator.serviceWorker.ready;
  let sub = await reg.pushManager.getSubscription();
  if (p && !sub && Notification.permission === "granted") {
    const key = Uint8Array.from(atob(PUSH.key.replace(/-/g, "+").replace(/_/g, "/")), c => c.charCodeAt(0));
    sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
  }
  const body = p && sub ? { id: S.device, subscription: sub.toJSON(), profile: notifyProfile(p) } : { id: S.device };
  const sig = JSON.stringify(body);
  if (sig === S.pushSig) return;  // ничего не изменилось — сервер не трогаем
  const r = await fetch(PUSH.endpoint + "/sub", {
    method: p && sub ? "POST" : "DELETE", headers: { "Content-Type": "application/json" }, body: sig,
  });
  if (r.ok) { S.pushSig = sig; save(); }
}
function renderNotify() {
  const el = $("#notify");
  const chooser = () => {
    const options = [{ id: "", name: "Не присылать", emoji: "🔕" }, ...S.profiles];
    return `<p>Каждое утро, когда скидки обновятся, придёт уведомление с 20 самыми горящими скидками для выбранного профиля —
        с учётом размеров, фильтров, «больше всего интересует» и любимых брендов. Уже присланные не повторяются, пока не подешевеют.</p>
      <div class="field"><span class="label">Присылать на этот телефон для</span>
        <div class="checks">${options.map(p => `<label class="chip ${S.notify === p.id ? "on" : ""}">
          <input type="radio" hidden name="notify" value="${esc(p.id)}" ${S.notify === p.id ? "checked" : ""}>${esc(p.emoji)} ${esc(p.name)}</label>`).join("")}</div></div>`;
  };
  if (bridge) {
    el.innerHTML = chooser() +
      `${S.notify && !bridge.permissionGranted() ? `<p class="bad">Уведомления запрещены в настройках телефона — разрешите их для приложения «Скидки для своих».</p>` : ""}
      ${S.notify ? `<button type="button" id="notify-test" class="btn-secondary">Прислать сейчас (проверка)</button>` : ""}`;
    return;
  }
  if (/SkidkiApp\//.test(navigator.userAgent)) {
    el.innerHTML = `<p>Чтобы каждое утро получать 20 самых горящих скидок, обновите приложение:
      <a href="install.html">скачайте новую версию</a> и установите поверх старой — настройки и избранное сохранятся.</p>`;
    return;
  }
  if (isIOS && !standalone) {
    el.innerHTML = `<p>На iPhone уведомления работают, когда приложение добавлено на экран «Домой»:</p>
      <ol><li>Нажмите <b>«Поделиться»</b> <span aria-hidden="true">⬆️</span> внизу Safari.</li>
      <li>Выберите <b>«На экран „Домой“»</b> → <b>«Добавить»</b>.</li>
      <li>Откройте «Скидки» с иконки на экране и включите уведомления здесь, в «Настройках».</li></ol>
      <p class="muted">Нужна iOS 16.4 или новее. Настройки, сделанные в Safari, придётся повторить в приложении с иконки.</p>`;
    return;
  }
  if (!webPush() || !PUSH.endpoint) {
    el.innerHTML = `<p>Ежедневные уведомления с горящими скидками приходят в приложении для Android
      (<a href="install.html">установить</a>) и на iPhone — с иконки на экране «Домой».</p>`;
    return;
  }
  const denied = Notification.permission === "denied";
  el.innerHTML = chooser() +
    `${S.notify && denied ? `<p class="bad">Уведомления запрещены в настройках браузера или телефона — разрешите их для этого сайта.</p>` : ""}
    ${S.notify && Notification.permission === "default" ? `<button type="button" id="notify-allow" class="btn-primary">Разрешить уведомления</button><div style="height:8px"></div>` : ""}
    ${S.notify && Notification.permission === "granted" ? `<button type="button" id="notify-test" class="btn-secondary">Прислать сейчас (проверка)</button>` : ""}`;
}
window.renderNotify = renderNotify;  // Android вызывает после ответа на запрос разрешения
async function testNotify(button) {
  button.disabled = true;
  if (bridge) {
    bridge.sendNow();
    button.textContent = "Готовлю уведомление — загляните в шторку через минуту";
    return;
  }
  // в браузере проверочное уведомление собираем прямо здесь, по тем же правилам, что и сервер
  const p = S.profiles.find(x => x.id === S.notify);
  const hot = pickHot(p);
  const reg = await navigator.serviceWorker.ready;
  await reg.showNotification(hot.length ? `${p.name ? p.name + ", с" : "С"}егодня ${hot.length} горящих скидок 🔥` : "Подходящих горящих скидок сегодня нет",
    { body: hot.slice(0, 3).map(it => `−${it.r}% · ${money(it.p)} · ${it.t}`).join("\n") || "Ослабьте фильтры профиля",
      icon: "icons/icon-192.png", badge: "icons/icon-192.png", tag: "hot",
      data: { url: new URL(`./#hot=${hot.map(it => it.id).join(",")}`, location.href).href } });
  button.textContent = "Уведомление отправлено";
}

// ---------- горящие скидки из уведомления ----------
function openHot() {
  ui.hot = pendingHot.split(",").filter(Boolean);
  pendingHot = "";
  if (location.hash) history.replaceState(null, "", location.pathname + location.search);
  showView("hot");
}
function renderHot() {
  const items = ui.hot.map(id => byId.get(id)).filter(Boolean);
  $("#hot-note").textContent = items.length ? `Из сегодняшнего уведомления — ${items.length}, от самой большой скидки.` : "";
  $("#hot-grid").innerHTML = items.map(it => cardHtml(it)).join("");
  $("#hot-empty").hidden = items.length > 0;
}
window.showHot = csv => {  // приложение уже открыто, а пользователь нажал на уведомление
  pendingHot = csv;
  if (DATA.items.length) openHot();
};
addEventListener("hashchange", () => {
  if (location.hash.startsWith("#hot=")) window.showHot(decodeURIComponent(location.hash.slice(5)));
});
navigator.serviceWorker?.addEventListener("message", e => {  // нажатие на уведомление в браузере
  if (e.data?.hot !== undefined) window.showHot(e.data.hot);
});
async function onSettingsInput(e) {
  const card = e.target.closest("[data-pid]");
  if (!card) return;
  const p = S.profiles.find(x => x.id === card.dataset.pid);
  const form = card.querySelector("form");
  for (const k of ["name", "emoji", "sizes", "shoeSizes", "brandsFav", "brandsHide"]) p[k] = form.elements[k].value.trim();
  readFields(form, p);
  if (e.target.type === "checkbox" && e.target.closest(".chip")) e.target.closest(".chip").classList.toggle("on", e.target.checked);
  const out = card.querySelector(`[data-out="${p.id}-minDiscount"]`);
  if (out) out.textContent = p.minDiscount;
  card.querySelector("summary").textContent = `${p.emoji} ${p.name}`;
  save();
  if (S.notify === p.id) syncNotify();
  renderProfiles();
  if (S.active === p.id) ui.f = prepareFilter(structuredClone(p));
  if (e.target.name === "audience") await ensureData().catch(() => {});
}

// ---------- переключение ----------
function resetSort() {  // каждая категория открывается с самых больших реальных скидок
  ui.sort = $("#sort").value = "discount";
}
function setProfile(id) {
  S.active = id;
  save();
  ui.f = prepareFilter(structuredClone(profile()));
  ui.cat = ui.sub = "";
  resetSort();
  renderProfiles();
  render();
}
function showView(name) {
  document.querySelectorAll(".view").forEach(v => v.classList.toggle("active", v.id === "view-" + name));
  document.querySelectorAll("nav.bottom button").forEach(b => b.classList.toggle("active", b.dataset.view === name));
  if (name === "favs") renderFavs();
  if (name === "settings") renderSettings();
  if (name === "hot") renderHot();
  if (name === "welcome") renderWelcome();
  if (name === "deals") render();
  scrollTo(0, 0);
}

// ---------- события ----------
document.addEventListener("click", e => {
  const t = e.target;
  const favBtn = t.closest("[data-fav]");
  if (favBtn) { e.preventDefault(); e.stopPropagation(); toggleFav(favBtn.dataset.fav); return; }
  const prof = t.closest("#profiles [data-id]");
  if (prof) { setProfile(prof.dataset.id); return; }
  const cat = t.closest("[data-cat]");
  if (cat) { ui.cat = cat.dataset.cat; ui.sub = ""; resetSort(); render(); return; }
  const sub = t.closest("[data-sub]");
  if (sub) { ui.sub = sub.dataset.sub; resetSort(); render(); return; }
  const nav = t.closest("nav.bottom button");
  if (nav) { showView(nav.dataset.view); return; }
  const go = t.closest("[data-view-go]");
  if (go) { showView(go.dataset.viewGo); return; }
  if (t.id === "notify-test") { testNotify(t); return; }
  if (t.id === "notify-allow") { enablePush(); return; }
  const card = t.closest(".item");
  if (card) { openDetail(card.dataset.id); return; }
  if (t.id === "open-filters" || t.closest("#open-filters")) { openFilters(); return; }
  if (t.id === "reset-filters") { ui.f = prepareFilter(structuredClone(profile())); $("#filters").close(); render(); return; }
  if (t.id === "save-to-profile") {
    const p = profile();
    readFields($("#filters form"), p);
    save();
    if (S.notify === p.id) syncNotify();
    $("#filters").close();
    return;
  }
  if (t.id === "add-profile") { showView("welcome"); return; }
  if (t.dataset.del) {
    if (S.profiles.length <= 1 || !confirm("Удалить профиль?")) return;
    S.profiles = S.profiles.filter(p => p.id !== t.dataset.del);
    if (S.active === t.dataset.del) S.active = S.profiles[0].id;
    if (S.notify === t.dataset.del) { S.notify = ""; syncNotify(); }
    save(); setProfile(S.active); renderSettings();
  }
});
$("#welcome").addEventListener("change", e => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  if (e.target.type === "radio") {
    $("#welcome").querySelectorAll(`[name="${e.target.name}"]`).forEach(x => x.closest(".chip").classList.toggle("on", x.checked));
    const name = $("#welcome-form").elements.name;
    name.placeholder = PRESETS[e.target.value].name;
    $("#welcome-error").hidden = true;
  } else chip.classList.toggle("on", e.target.checked);
});
$("#welcome").addEventListener("input", e => {
  if (e.target.name === "minDiscount") $('[data-out="w-minDiscount"]').textContent = e.target.value;
});
$("#welcome").addEventListener("submit", e => {
  e.preventDefault();
  const form = e.target;
  if (!form.elements.preset.value) { $("#welcome-error").hidden = false; return; }
  createProfile(form);
});
$("#filters").addEventListener("input", e => {
  const form = $("#filters form");
  readFields(form, ui.f);
  ui.f = prepareFilter(ui.f);
  if (e.target.closest(".chip")) e.target.closest(".chip").classList.toggle("on", e.target.checked);
  const out = form.querySelector('[data-out="flt-minDiscount"]');
  if (out) out.textContent = ui.f.minDiscount;
  if (e.target.name === "audience") {
    ensureData([...S.profiles, ui.f]).then(render, () => {});
    return;
  }
  render();
});
for (const d of document.querySelectorAll("dialog.sheet"))  // тап по затемнению закрывает шторку
  d.addEventListener("click", e => { if (e.target === d) d.close(); });
$("#notify").addEventListener("change", e => {
  if (e.target.name !== "notify") return;
  S.notify = e.target.value;
  save();
  syncNotify(true);
  renderNotify();
});
$("#settings").addEventListener("input", onSettingsInput);
$("#settings").addEventListener("change", onSettingsInput);
let qTimer;
$("#search").addEventListener("input", e => {
  clearTimeout(qTimer);
  qTimer = setTimeout(() => { ui.q = lower(e.target.value.trim()); render(); }, 200);
});
$("#sort").addEventListener("change", e => { ui.sort = e.target.value; render(); });
new IntersectionObserver(es => { if (es[0].isIntersecting && ui.shown < ui.list.length) more(); }, { rootMargin: "800px" })
  .observe($("#more"));

// Кнопка «Назад» в Android-приложении: закрыть шторку → вернуться на экран скидок → выйти
window.appBack = () => {
  const open = document.querySelector("dialog[open]");
  if (open) { open.close(); return true; }
  if (!S.profiles.length) return false;
  if (!$("#view-deals").classList.contains("active")) { showView("deals"); return true; }
  return false;
};

// ---------- запуск ----------
async function load() {
  PUSH = await fetchJson("push.json").catch(() => ({}));
  try {
    DATA = { ...(await fetchJson("data/meta.json")), items: [] };
  } catch {
    try {  // данные ещё в старом формате — одним файлом
      DATA = await fetchJson("data/deals.json");
      wholeFile = true;
      byId = new Map(DATA.items.map(it => [it.id, it]));
    } catch {
      $("#updated").textContent = "нет связи";
    }
  }
  if (DATA.generated) {
    const d = new Date(DATA.generated);
    $("#updated").textContent = "обновлено " + d.toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  }
  if (!S.profiles.length) {  // первый запуск — сначала настройка
    document.body.classList.add("onboarding");
    showView("welcome");
    return;
  }
  try { await ensureData(); } catch { $("#updated").textContent = "нет связи"; }
  setProfile(S.profiles.some(p => p.id === S.active) || S.active === "all" ? S.active : S.profiles[0].id);
  syncNotify();  // после обновления приложения расписание уведомлений включится само
  if (pendingHot) openHot();
}
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js");
load();
