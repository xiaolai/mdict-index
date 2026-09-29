import { buildIndex, makeFold, search } from "./search.js";

// All text from the index is inserted with textContent, and every link is
// built from these two hosts: names come from a third-party site.
const HOST = "https://downloads.freemdict.com/";
const DIRECT = "https://downloads-direct.freemdict.com/"; // freemdict routes .rar here (its CDN blocks .rar)
const PAGE = 50;
const NEW_DAYS = 60; // about the last two monthly crawls

const LANGS = [
  ["en-en", "英英", "English"],
  ["en-zh", "英汉", "English–Chinese"],
  ["en-other", "英语–其他", "English–other"],
  ["other", "其他语种", "Other"],
  ["unknown", "未分类", "Unclassified"],
];
const KINDS = [
  ["mdx", "词典", "Dictionary"],
  ["mdd", "资源包", "Audio/image pack"],
  ["archive", "压缩包", "Archive"],
];
const SORTS = ["rel", "name", "size", "date", "new"];
const STATUS = {
  current: ["最新", "Current"],
  behind: ["落后一版", "One edition behind"],
  snapshot: ["在线版快照", "Online snapshot"],
  final: ["终版", "Final, discontinued"],
  unclear: ["版本不明", "Edition unclear"],
  missing: ["本站暂无", "Not on freemdict"],
};
const SUGGESTIONS = ["OALD", "牛津高阶", "LDOCE", "柯林斯 双解", "Merriam-Webster", "etymology", "发音", "英汉大词典"];

const state = { q: "", lang: new Set(), kind: new Set(), brand: "", res: false, sort: "rel", shown: PAGE, tab: "starter" };
let dicts, index, fold, brands;
let revealActiveTab = () => {}; // set by renderRecommended

const $ = (id) => document.getElementById(id);

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (k in node) node[k] = v;
    else node.setAttribute(k, v);
  }
  node.append(...children.filter((c) => c != null && c !== false));
  return node;
}

const label = (table, key) => {
  const row = table.find((t) => t[0] === key);
  return row ? `${row[1]} ${row[2]}` : key;
};

function fmtSize(bytes) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (bytes >= 1024 && i < units.length - 1) (bytes /= 1024), i++;
  return `${bytes.toFixed(bytes < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
}

const segments = (folder) => folder.split("/").filter(Boolean).map(encodeURIComponent);
const folderUrl = (folder) => HOST + segments(folder).map((s) => s + "/").join("");
const fileUrl = (folder, name) =>
  (name.toLowerCase().endsWith(".rar") ? DIRECT : HOST) +
  [...segments(folder), encodeURIComponent(name)].join("/");

// ---- URL state: every view is shareable -------------------------------------

function readUrl() {
  const p = new URLSearchParams(location.search);
  const set = (key, table) => new Set((p.get(key) ?? "").split(",").filter((v) => table.some((t) => t[0] === v)));
  state.q = p.get("q") ?? "";
  state.lang = set("lang", LANGS);
  state.kind = set("kind", KINDS);
  state.brand = brands.has(p.get("brand")) ? p.get("brand") : "";
  state.res = p.get("res") === "1";
  state.sort = SORTS.includes(p.get("sort")) ? p.get("sort") : "rel";
  state.tab = p.get("tab") ?? "starter"; // validated against the loaded tabs in renderRecommended
}

function writeUrl() {
  const p = new URLSearchParams();
  if (state.q) p.set("q", state.q);
  if (state.lang.size) p.set("lang", [...state.lang].join(","));
  if (state.kind.size) p.set("kind", [...state.kind].join(","));
  if (state.brand) p.set("brand", state.brand);
  if (state.res) p.set("res", "1");
  if (state.sort !== "rel") p.set("sort", state.sort);
  if (state.tab !== "starter") p.set("tab", state.tab);
  const qs = p.toString();
  history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
}

// ---- filtering ----------------------------------------------------------------

// `skip` leaves one facet out, so each facet's counts reflect the other filters.
function passes(r, skip) {
  return (
    (skip === "lang" || state.lang.size === 0 || state.lang.has(r.l)) &&
    (skip === "kind" || state.kind.size === 0 || state.kind.has(r.k)) &&
    (skip === "brand" || !state.brand || r.b.includes(state.brand)) &&
    (!state.res || r.r === 1)
  );
}

function sortResults(ids, hasQuery) {
  const by = {
    size: (a, b) => dicts[b].s - dicts[a].s,
    date: (a, b) => dicts[b].d.localeCompare(dicts[a].d),
    new: (a, b) => (dicts[b].fs ?? "").localeCompare(dicts[a].fs ?? "") || dicts[b].d.localeCompare(dicts[a].d),
    name: (a, b) => a - b, // dicts.json is pre-sorted by folded name
  }[state.sort === "rel" && !hasQuery ? "name" : state.sort];
  return by ? [...ids].sort(by) : ids; // "rel" with a query keeps search order
}

function update() {
  const hits = search(index, state.q, fold);
  const pool = hits ? hits.map((h) => h.i) : dicts.map((_, i) => i);
  const count = (facet, key) => {
    const out = new Map();
    for (const i of pool) {
      const r = dicts[i];
      if (!passes(r, facet)) continue;
      for (const k of key(r)) out.set(k, (out.get(k) ?? 0) + 1);
    }
    return out;
  };
  renderChips($("f-lang"), LANGS, count("lang", (r) => [r.l]), state.lang);
  renderChips($("f-kind"), KINDS, count("kind", (r) => [r.k]), state.kind);
  renderBrands(count("brand", (r) => r.b));

  const results = sortResults(pool.filter((i) => passes(dicts[i])), Boolean(hits));
  renderResults(results);
  $("suggest").hidden = Boolean(state.q);
  // Recommendations are the landing view: shown until the user searches or filters.
  const pristine = !state.q && !state.lang.size && !state.kind.size && !state.brand && !state.res;
  $("rec").hidden = !pristine;
  $("all-title").hidden = !pristine;
  if (pristine) revealActiveTab(); // hidden elements have no layout, so re-center once shown
  writeUrl();
}

// ---- rendering ----------------------------------------------------------------

function renderChips(container, table, counts, selected) {
  container.replaceChildren(
    ...table.map(([key, zh, en]) => {
      const n = counts.get(key) ?? 0;
      const on = selected.has(key);
      return el(
        "button",
        {
          type: "button",
          class: "chip",
          "aria-pressed": String(on),
          disabled: n === 0 && !on,
          onclick: () => {
            on ? selected.delete(key) : selected.add(key);
            state.shown = PAGE;
            update();
          },
        },
        `${zh} ${en}`,
        el("span", { class: "n", textContent: n.toLocaleString() }),
      );
    }),
  );
}

function renderBrands(counts) {
  $("f-brand").replaceChildren(
    ...[...brands.keys()].map((b) => {
      const n = counts.get(b) ?? 0;
      const on = state.brand === b;
      return el(
        "button",
        {
          type: "button",
          class: "chip",
          "aria-pressed": String(on),
          disabled: n === 0 && !on,
          onclick: () => {
            state.brand = on ? "" : b;
            state.shown = PAGE;
            update();
          },
        },
        b,
        el("span", { class: "n", textContent: n.toLocaleString() }),
      );
    }),
  );
}

// The last folders are what tell same-named records apart ("[英-汉]/oald4" vs "[英-英]/oald4").
function shortFolder(folder) {
  const parts = folder.split("/").filter(Boolean);
  return "📁 " + (parts.length > 3 ? "…/" + parts.slice(-3).join("/") : parts.join("/") || "/");
}

function daysSince(iso) {
  return (Date.now() - Date.parse(iso)) / 86_400_000;
}

function card(r) {
  const [first] = r.loc;
  const [mainName] = first.f[0];
  const ext = mainName.slice(mainName.lastIndexOf(".")).toLowerCase();
  const fileCount = r.loc.reduce((n, l) => n + l.f.length, 0);
  return el(
    "li",
    { class: "card" },
    el("h2", { textContent: r.n }),
    el("p", { class: "where", title: first.p, textContent: shortFolder(first.p) + (r.loc.length > 1 ? ` · +${r.loc.length - 1} 处副本 copies` : "") }),
    el(
      "div",
      { class: "badges" },
      el("span", { class: "badge lang", textContent: label(LANGS, r.l) }),
      r.k !== "mdx" && el("span", { class: "badge", textContent: label(KINDS, r.k) }),
      ...r.b.map((b) => el("span", { class: "badge", textContent: b })),
      r.r === 1 && el("span", { class: "badge", textContent: "含 .mdd 音频/图片" }),
      r.fs && daysSince(r.fs) <= NEW_DAYS && el("span", { class: "badge new", textContent: `新收录 New · ${r.fs}` }),
    ),
    el(
      "div",
      { class: "meta" },
      el("a", { class: "dl", href: fileUrl(first.p, mainName), rel: "noopener", textContent: `下载 Download ${ext}` }),
      el("span", { textContent: fmtSize(r.s) }),
      el("span", { textContent: `更新 ${r.d}` }),
    ),
    el(
      "details",
      {},
      el("summary", { textContent: `全部文件 All files (${fileCount})` }),
      ...r.loc.map((loc) =>
        el(
          "div",
          { class: "loc" },
          el("a", { class: "folder", href: folderUrl(loc.p), rel: "noopener", textContent: `📁 ${loc.p || "/"}` }),
          el(
            "ul",
            { class: "files" },
            ...loc.f.map(([name, size]) =>
              el(
                "li",
                {},
                el("a", { href: fileUrl(loc.p, name), rel: "noopener", textContent: name }),
                el("span", { class: "sz", textContent: fmtSize(size) }),
              ),
            ),
          ),
        ),
      ),
    ),
  );
}

function renderResults(results) {
  const n = results.length;
  $("count").textContent = n
    ? `${n.toLocaleString()} 个结果 results`
    : "没有匹配的词典。换个名称、缩写或中文名试试。No matches — try another name, abbreviation, or the Chinese title.";
  $("results").replaceChildren(...results.slice(0, state.shown).map((i) => card(dicts[i])));
  $("more").hidden = n <= state.shown;
  $("more").textContent = `显示更多 Show more (${(n - state.shown).toLocaleString()})`;
}

// Put an exact dictionary name in the search box and bring its results into view.
function showInIndex(name) {
  const q = $("q");
  q.value = name;
  q.dispatchEvent(new Event("input"));
  $("count").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderRecommended(rec, byId) {
  $("rec-meta").textContent =
    `最新版次核对于 ${rec.reviewed}；本站版本按版次、音频图片是否完整、更新时间挑选，未逐一打开验证。` +
    ` Editions checked ${rec.reviewed}; picks judged from file metadata.`;

  const status = (s) => el("span", { class: `status st-${s}`, textContent: `${STATUS[s][0]} · ${STATUS[s][1]}` });
  const name = (it) =>
    el(
      "div",
      { class: "rec-name" },
      el("strong", { textContent: it.name }),
      it.zh && el("span", { class: "zh", textContent: it.zh }),
      el("span", { class: "full", textContent: it.full }),
    );
  const best = (it) => {
    const r = byId.get(it.id);
    if (!r) return el("div", { class: "rec-note", textContent: it.note });
    const [first] = r.loc;
    return el(
      "div",
      {},
      el("button", {
        type: "button",
        class: "link rec-find",
        title: "在索引中查看 Show in the index",
        textContent: r.n,
        onclick: () => showInIndex(r.n),
      }),
      el(
        "div",
        { class: "rec-sub" },
        el("a", { class: "dl", href: fileUrl(first.p, first.f[0][0]), rel: "noopener", textContent: "下载 Download" }),
        ` · ${fmtSize(r.s)}`,
        r.r === 1 ? " · 含音频/图片" : "",
      ),
      el("div", { class: "rec-note", textContent: it.note }),
    );
  };
  const latest = (it) => el("a", { href: it.src, rel: "noopener", title: "来源 Source", textContent: it.latest });
  const td = (label, child) => el("td", { "data-label": label }, child);
  const table = (heads, rows) =>
    el(
      "table",
      { class: "rec-table" },
      el("thead", {}, el("tr", {}, ...heads.map((h) => el("th", { scope: "col", textContent: h })))),
      el("tbody", {}, ...rows),
    );
  const card = (cls, zh, en, ...body) =>
    el("article", { class: `rec-card ${cls}` }, el("h3", {}, zh, el("span", { class: "sub", textContent: en })), ...body);

  const items = rec.categories.flatMap((c) => c.items);
  const starters = items.filter((it) => it.starter && byId.has(it.id));
  const starterSize = starters.reduce((n, it) => n + byId.get(it.id).s, 0);

  const panels = [
    {
      key: "starter",
      tab: ["入门套装", "Starter set"],
      count: starters.length,
      body: () =>
        card(
          "starter",
          "入门套装",
          `Starter set · ${starters.length} 部 · 共 ${fmtSize(starterSize)}`,
          el("p", {
            class: "rec-note",
            textContent: "一套覆盖学习释义、母语释义、生僻词、发音、搭配、词源和中文释义。体积主要是音频。",
          }),
          table(
            ["词典 Dictionary", "本站版本 Best on freemdict", "状态 Status"],
            starters.map((it) => el("tr", {}, td("词典", name(it)), td("本站版本", best(it)), td("状态", status(it.status)))),
          ),
        ),
    },
    ...rec.categories.map((cat) => ({
      key: cat.key,
      tab: [cat.tab_zh, cat.tab_en],
      count: cat.items.length,
      body: () =>
        card(
          "",
          cat.zh,
          cat.en,
          table(
            ["词典 Dictionary", "最新版次 Latest edition", "本站最佳版本 Best on freemdict", "状态 Status"],
            cat.items.map((it) =>
              el(
                "tr",
                {},
                td("词典", name(it)),
                td("最新版次", latest(it)),
                td("本站最佳版本", best(it)),
                td("状态", status(it.status)),
              ),
            ),
          ),
        ),
    })),
  ];
  if (!panels.some((p) => p.key === state.tab)) state.tab = "starter";

  // WAI-ARIA tabs: one tab stop, arrow keys move between tabs, panels follow selection.
  const tabs = panels.map((p) =>
    el(
      "button",
      {
        type: "button",
        role: "tab",
        id: `tab-${p.key}`,
        class: "rec-tab",
        "aria-controls": `panel-${p.key}`,
        onclick: () => select(p.key),
      },
      p.tab[0],
      el("span", { class: "en", textContent: p.tab[1] }),
      el("span", { class: "n", textContent: String(p.count) }),
    ),
  );
  const bodies = panels.map((p) => {
    const body = p.body();
    body.id = `panel-${p.key}`;
    body.tabIndex = 0;
    body.setAttribute("role", "tabpanel");
    body.setAttribute("aria-labelledby", `tab-${p.key}`);
    return body;
  });
  function select(key, focus = false) {
    state.tab = key;
    panels.forEach((p, i) => {
      const on = p.key === key;
      tabs[i].setAttribute("aria-selected", String(on));
      tabs[i].tabIndex = on ? 0 : -1;
      bodies[i].hidden = !on;
      if (on && focus) tabs[i].focus();
    });
    revealActiveTab();
    writeUrl();
  }
  // On narrow screens the strip scrolls sideways; keep the active tab in view.
  // Sets scrollLeft only: scrollIntoView would also scroll the page.
  revealActiveTab = () => {
    const t = tabs[panels.findIndex((p) => p.key === state.tab)];
    const strip = t.parentElement;
    strip.scrollLeft = t.offsetLeft - (strip.clientWidth - t.offsetWidth) / 2;
  };
  const onKey = (e) => {
    const i = panels.findIndex((p) => p.key === state.tab);
    const next = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: panels.length - 1 }[e.key];
    if (next === undefined) return;
    e.preventDefault();
    select(panels[(next + panels.length) % panels.length].key, true);
  };

  $("rec-cards").replaceChildren(
    el("div", { class: "rec-tabs", role: "tablist", "aria-label": "推荐分类 Recommendation categories", onkeydown: onKey }, ...tabs),
    ...bodies,
  );
  select(state.tab);
}

function renderHeader(meta) {
  const by = meta.by_lang;
  $("stats").textContent =
    `${meta.total.toLocaleString()} 条目 entries · 英英 ${by["en-en"] ?? 0} · 英汉 ${by["en-zh"] ?? 0} · ` +
    `抓取于 crawled ${meta.crawled} · 自 ${meta.tracking_since} 起跟踪 tracking`;

  const body = $("changes-body");
  if (meta.changes.length === 0) {
    body.textContent = `暂无变更。自 ${meta.tracking_since} 起每月比对一次。No changes yet; checked monthly.`;
    return;
  }
  body.replaceChildren(
    ...meta.changes.map((c) =>
      el(
        "div",
        { class: "change" },
        el("strong", { textContent: `${c.date}  +${c.added.length} / −${c.removed.length}` }),
        ...[
          ["新增 Added", c.added],
          ["移除 Removed", c.removed],
        ]
          .filter(([, names]) => names.length)
          .map(([title, names]) =>
            el("div", {}, title, el("ul", {}, ...names.slice(0, 100).map((nm) => el("li", { textContent: nm })))),
          ),
      ),
    ),
  );
}

// ---- boot ---------------------------------------------------------------------

async function loadJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return res.json();
}

function bindInputs() {
  const q = $("q");
  q.value = state.q;
  q.addEventListener("input", () => {
    state.q = q.value;
    state.shown = PAGE;
    update();
  });
  q.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && q.value) {
      q.value = "";
      q.dispatchEvent(new Event("input"));
    }
  });
  document.addEventListener("keydown", (e) => {
    const typing = e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement;
    if (e.key === "/" && !typing) {
      e.preventDefault();
      q.focus();
    }
  });

  const res = $("f-res");
  res.checked = state.res;
  res.addEventListener("change", () => {
    state.res = res.checked;
    state.shown = PAGE;
    update();
  });

  const sort = $("sort");
  sort.value = state.sort;
  sort.addEventListener("change", () => {
    state.sort = sort.value;
    update();
  });

  $("more").addEventListener("click", () => {
    state.shown += PAGE;
    update();
  });

  $("reset").addEventListener("click", () => {
    Object.assign(state, { q: "", lang: new Set(), kind: new Set(), brand: "", res: false, sort: "rel", shown: PAGE });
    q.value = "";
    res.checked = false;
    sort.value = "rel";
    update();
    q.focus();
  });

  $("suggest").append(
    ...SUGGESTIONS.map((s) =>
      el("button", {
        type: "button",
        class: "chip",
        textContent: s,
        onclick: () => {
          q.value = s;
          q.dispatchEvent(new Event("input"));
          q.focus();
        },
      }),
    ),
  );
}

async function main() {
  const [data, meta, t2s, rec] = await Promise.all(
    ["data/dicts.json", "data/meta.json", "t2s.json", "data/recommended.json"].map(loadJson),
  );
  dicts = data;
  fold = makeFold(t2s);
  index = buildIndex(dicts, fold);
  // Brand chips, most common first.
  const brandCount = new Map();
  for (const r of dicts) for (const b of r.b) brandCount.set(b, (brandCount.get(b) ?? 0) + 1);
  brands = new Map([...brandCount].sort((a, b) => b[1] - a[1]));

  readUrl();
  renderHeader(meta);
  renderRecommended(rec, new Map(dicts.map((d) => [d.id, d])));
  bindInputs();
  update();
}

main().catch((err) => {
  console.error(err);
  const stats = $("stats");
  stats.textContent = `索引加载失败 Failed to load the index: ${err.message}`;
  stats.classList.add("error");
});
