// Скидки — приложение для просмотра проверенных скидок. Данные: data/deals.json (обновляется раз в день).

const CATS = { clothes: "Одежда", shoes: "Обувь", bags: "Сумки", accessories: "Аксессуары" };
const SUBS = {
  outerwear: "Верхняя одежда", dresses: "Платья и юбки", knit: "Свитера и худи", tops: "Футболки и блузки",
  bottoms: "Брюки и джинсы", suits: "Костюмы", underwear: "Бельё и пижамы", swim: "Купальники",
  sneakers: "Кроссовки и кеды", boots: "Ботинки и сапоги", shoes: "Туфли и босоножки", slippers: "Тапочки",
  bags: "Сумки и рюкзаки", accessories: "Шапки, шарфы и др.",
};
const AUD = { women: "Женское", girls: "Для девочек", kids: "Детское (пол не указан)", unisex: "Унисекс" };
const FLAGS = {
  ver: ["✓ проверено", "", "Скидка подтверждена: товар действительно продавался по старой цене."],
  low: ["мин. цена за 60 дн", "", "Самая низкая цена за всё время наблюдений (до 60 дней)."],
  drop: ["подешевело сегодня", "hot", "Цена снизилась со вчерашнего дня."],
  new: ["новое", "hot", "Товар со скидкой появился сегодня."],
  infl: ["завышенная старая цена", "warn", "Недавно товар продавался без скидки почти по нынешней цене — «старая цена» нарисована. Такие товары по умолчанию скрыты."],
  up: ["уже было дешевле", "warn", "За последние 30 дней товар уже продавался по такой же или меньшей цене."],
  perm: ["давно по этой цене", "warn", "«Скидка» не меняется больше месяца — скорее всего, это обычная цена."],
};

const DEFAULT_PROFILE = {
  name: "", emoji: "", audience: ["women", "unisex"], sizes: "", shoeSizes: "", cats: [],
  brandsFav: "", brandsHide: "", minDiscount: 30, maxPrice: 0, stores: [], onlySize: false, hideSuspicious: true,
};
const DEFAULT_PROFILES = [
  { ...DEFAULT_PROFILE, id: "mom", name: "Мама", emoji: "👩" },
  { ...DEFAULT_PROFILE, id: "big", name: "Старшая", emoji: "👱‍♀️" },
  { ...DEFAULT_PROFILE, id: "small", name: "Младшие", emoji: "👧", audience: ["girls", "kids"],
    sizes: "146, 152, 158, 11, 12", shoeSizes: "35, 36, 37", onlySize: true },
];

// ---------- состояние ----------
const KEY = "skidki.v1";
const saved = JSON.parse(localStorage.getItem(KEY) || "{}");
const S = {
  profiles: saved.profiles || structuredClone(DEFAULT_PROFILES),
  active: saved.active ?? "all",
  favs: saved.favs || {},
};
const save = () => localStorage.setItem(KEY, JSON.stringify({ profiles: S.profiles, active: S.active, favs: S.favs }));

let DATA = { items: [], stores: {} };
let byId = new Map();
const ui = { cat: "", sub: "", q: "", sort: "best", f: null, shown: 0, list: [] };

// ---------- утилиты ----------
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = n => new Intl.NumberFormat("uk-UA").format(Math.round(n)) + " ₴";
const list = s => String(s || "").split(",").map(x => x.trim()).filter(Boolean);
const lower = s => s.toLowerCase();
const sizeTokens = s => s.toUpperCase().replace(/,/g, ".").split(/[^0-9A-ZА-ЯІЇЄҐ.]+/).filter(Boolean);
const EPOCH = Date.UTC(2024, 0, 1);
const dayToDate = d => new Date(EPOCH + d * 864e5).toLocaleDateString("ru-RU", { day: "numeric", month: "long" });

function profile() {
  if (S.active === "all") return { ...DEFAULT_PROFILE, id: "all", audience: [], minDiscount: 10 };
  return S.profiles.find(p => p.id === S.active) || S.profiles[0];
}

// Подходит ли размер: «S» найдёт «S I UA 44», «11» найдёт «146 (10-11 р)» и «10-12», «152» найдёт «150-155»
function sizeMatch(itemSizes, wanted) {
  for (const s of itemSizes) {
    const toks = sizeTokens(s);
    // «(9-12 м)» — возраст в месяцах, не годы: диапазон не используем
    const range = /\d\s*м\b|\d\s*мес|\d\s*m\b/i.test(s) ? null : s.match(/(\d+(?:[.,]\d+)?)\s*[-–]\s*(\d+(?:[.,]\d+)?)/);
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
function passes(it, f, skipCat = false) {
  if (f.audience.length && !f.audience.includes(it.a)) return false;
  if (f.stores.length && !f.stores.includes(it.s)) return false;
  if (f.cats.length && !f.cats.includes(it.c)) return false;
  if (!skipCat && ui.cat && it.c !== ui.cat) return false;
  if (!skipCat && ui.sub && it.sc !== ui.sub) return false;
  if (it.r < f.minDiscount) return false;
  if (f.maxPrice && it.p > f.maxPrice) return false;
  if (f.hideSuspicious && (it.f.includes("infl") || it.f.includes("perm"))) return false;
  if (f._hide.length && f._hide.includes(lower(it.b))) return false;
  if (f.onlySize && fits(it, f) === false) return false;
  if (ui.q) {
    const hay = it._hay || (it._hay = lower(`${it.t} ${it.b} ${DATA.stores[it.s]?.name || ""} ${SUBS[it.sc] || ""}`));
    if (!ui.q.split(/\s+/).every(w => hay.includes(w))) return false;
  }
  return true;
}
function personalScore(it, f) {
  let k = it.k;
  if (f._fav.includes(lower(it.b))) k += 25;
  if (it.a === "kids") k -= 5;  // явно «для девочек» — выше, чем детское без пола
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

// ---------- отрисовка ----------
function renderProfiles() {
  const chips = [{ id: "all", name: "Все", emoji: "✨" }, ...S.profiles];
  $("#profiles").innerHTML = chips.map(p =>
    `<button class="chip ${p.id === S.active ? "on" : ""}" data-id="${esc(p.id)}">${esc(p.emoji)} ${esc(p.name)}</button>`).join("");
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
      <div class="meta">${esc(it.b)} · ${esc(DATA.stores[it.s]?.name || it.s)}</div>
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
    <div class="meta">${esc(it.b)} · ${esc(store)} · ${esc(SUBS[it.sc] || "")}</div>
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
function checks(name, options, selected) {
  return `<div class="checks">${Object.entries(options).map(([k, v]) =>
    `<label class="chip ${selected.includes(k) ? "on" : ""}"><input type="checkbox" hidden name="${name}" value="${esc(k)}" ${selected.includes(k) ? "checked" : ""}>${esc(v)}</label>`).join("")}</div>`;
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
  for (const name of ["audience", "stores", "cats"]) {
    if (form.querySelector(`[name="${name}"]`)) target[name] = [...form.querySelectorAll(`[name="${name}"]:checked`)].map(x => x.value);
  }
}
function openFilters() {
  $("#filters-body").innerHTML = filterFields(ui.f, "flt-") +
    (S.active !== "all" ? `<div class="sheet-foot"><button type="button" id="save-to-profile" class="btn-secondary">Сохранить в профиль «${esc(profile().name)}»</button></div>` : "");
  $("#filters").showModal();
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
}
function onSettingsInput(e) {
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
  renderProfiles();
  if (S.active === p.id) ui.f = prepareFilter(structuredClone(p));
}

// ---------- переключение ----------
function setProfile(id) {
  S.active = id;
  save();
  ui.f = prepareFilter(structuredClone(profile()));
  ui.cat = ui.sub = "";
  renderProfiles();
  render();
}
function showView(name) {
  document.querySelectorAll(".view").forEach(v => v.classList.toggle("active", v.id === "view-" + name));
  document.querySelectorAll("nav.bottom button").forEach(b => b.classList.toggle("active", b.dataset.view === name));
  if (name === "favs") renderFavs();
  if (name === "settings") renderSettings();
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
  if (cat) { ui.cat = cat.dataset.cat; ui.sub = ""; render(); return; }
  const sub = t.closest("[data-sub]");
  if (sub) { ui.sub = sub.dataset.sub; render(); return; }
  const nav = t.closest("nav.bottom button");
  if (nav) { showView(nav.dataset.view); return; }
  const card = t.closest(".item");
  if (card) { openDetail(card.dataset.id); return; }
  if (t.id === "open-filters" || t.closest("#open-filters")) { openFilters(); return; }
  if (t.id === "reset-filters") { ui.f = prepareFilter(structuredClone(profile())); $("#filters").close(); render(); return; }
  if (t.id === "save-to-profile") {
    const p = profile();
    readFields($("#filters form"), p);
    save();
    $("#filters").close();
    return;
  }
  if (t.id === "add-profile") {
    const id = "p" + Date.now();
    S.profiles.push({ ...structuredClone(DEFAULT_PROFILE), id, name: "Новый профиль", emoji: "🙂" });
    save(); renderProfiles(); renderSettings();
    document.querySelector(`[data-pid="${id}"]`).open = true;
    return;
  }
  if (t.dataset.del) {
    if (S.profiles.length <= 1 || !confirm("Удалить профиль?")) return;
    S.profiles = S.profiles.filter(p => p.id !== t.dataset.del);
    if (S.active === t.dataset.del) S.active = "all";
    save(); setProfile(S.active); renderSettings();
  }
});
$("#filters").addEventListener("input", e => {
  const form = $("#filters form");
  readFields(form, ui.f);
  ui.f = prepareFilter(ui.f);
  if (e.target.closest(".chip")) e.target.closest(".chip").classList.toggle("on", e.target.checked);
  const out = form.querySelector('[data-out="flt-minDiscount"]');
  if (out) out.textContent = ui.f.minDiscount;
  render();
});
for (const d of document.querySelectorAll("dialog.sheet"))  // тап по затемнению закрывает шторку
  d.addEventListener("click", e => { if (e.target === d) d.close(); });
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

// ---------- запуск ----------
async function load() {
  try {
    const r = await fetch("data/deals.json", { cache: "no-cache" });
    DATA = await r.json();
  } catch {
    $("#updated").textContent = "нет связи";
  }
  byId = new Map(DATA.items.map(it => [it.id, it]));
  if (DATA.generated) {
    const d = new Date(DATA.generated);
    $("#updated").textContent = "обновлено " + d.toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  }
  setProfile(S.active);
}
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js");
load();
