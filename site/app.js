import { buildIndex, makeFold, search } from "./search.js";
import { tabController } from "./tabs.js";
import { $, card, el, KINDS, LANGS, recList, recPanel, recPanels, renderHeader } from "./view.js";

const PAGE = 50;
const SORTS = ["rel", "name", "size", "date", "new"];
const SUGGESTIONS = ["OALD", "牛津高阶", "LDOCE", "柯林斯 双解", "Merriam-Webster", "etymology", "发音", "英汉大词典"];

const state = { q: "", lang: new Set(), kind: new Set(), brand: "", res: false, sort: "rel", shown: PAGE, tab: "starter" };
let dicts, index, fold, brands, byId;
let shownResults = []; // record indexes of the current result list, in display order
// Recommendations: curated items, a search index over them, and the ids they point to.
let recItems = [];
let recIndex = [];
let recIds = new Set();
let revealActiveTab = () => {}; // set by renderRecommended
let selectTab = () => {}; // set by renderRecommended


// The box is usable while the index loads. Whether the user has edited it by then, not
// whether it holds text, decides between their text (possibly cleared) and the URL's query.
let qEdited = false;
$("q").addEventListener("input", () => (qEdited = true), { once: true });

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
  renderChips($("f-lang"), LANGS, count("lang", (r) => [r.l]), "lang");
  renderChips($("f-kind"), KINDS, count("kind", (r) => [r.k]), "kind");
  renderBrands(count("brand", (r) => r.b));

  const results = sortResults(pool.filter((i) => passes(dicts[i])), Boolean(hits));
  renderResults(results);
  renderRecHits(state.q ? matchRecommended() : []);
  $("suggest").hidden = Boolean(state.q);
  // Recommendations are the landing view: shown until the user searches or filters.
  const pristine = !state.q && !state.lang.size && !state.kind.size && !state.brand && !state.res;
  $("rec").hidden = !pristine;
  $("all-title").hidden = !pristine;
  $("to-rec").hidden = pristine;
  $("reset").hidden = pristine && state.sort === "rel";
  const hiddenActive = state.kind.size + (state.brand ? 1 : 0) + (state.res ? 1 : 0);
  $("more-count").hidden = hiddenActive === 0;
  $("more-count").textContent = String(hiddenActive);
  if (pristine) revealActiveTab(); // hidden elements have no layout, so re-center once shown
  writeUrl();
}

// ---- rendering ----------------------------------------------------------------

// One row of filter chips. The buttons are created once and updated in place:
// replacing them on every update would drop keyboard focus from the chip just pressed.
// `options` is [key, text] pairs; `toggle(key)` changes the state.
function renderFacet(container, options, counts, isOn, toggle) {
  if (container.children.length !== options.length) {
    container.replaceChildren(
      ...options.map(([key, text]) =>
        el(
          "button",
          {
            type: "button",
            class: "chip",
            onclick: () => {
              toggle(key);
              state.shown = PAGE;
              update();
            },
          },
          text,
          el("span", { class: "chip__n" }),
        ),
      ),
    );
  }
  options.forEach(([key], i) => {
    const chip = container.children[i];
    const n = counts.get(key) ?? 0;
    const on = isOn(key);
    chip.setAttribute("aria-pressed", String(on));
    // The focused chip stays enabled even at zero: a disabled button cannot hold focus.
    chip.disabled = n === 0 && !on && chip !== document.activeElement;
    chip.lastChild.textContent = n.toLocaleString();
  });
}

// `facet` names the state Set ("lang" or "kind"). It is looked up on every use, never
// captured: the handlers outlive a reset, which gives the state a new Set.
function renderChips(container, table, counts, facet) {
  renderFacet(
    container,
    table.map(([key, zh, en]) => [key, `${zh} ${en}`]),
    counts,
    (key) => state[facet].has(key),
    (key) => (state[facet].has(key) ? state[facet].delete(key) : state[facet].add(key)),
  );
}

function renderBrands(counts) {
  renderFacet(
    $("f-brand"),
    [...brands.keys()].map((b) => [b, b]),
    counts,
    (b) => state.brand === b,
    (b) => (state.brand = state.brand === b ? "" : b),
  );
}

function renderResults(results) {
  const n = results.length;
  shownResults = results;
  $("count").textContent = n
    ? `${n.toLocaleString()} 个结果 results`
    : "没有匹配的词典。换个名称、缩写或中文名试试。No matches — try another name, abbreviation, or the Chinese title.";
  $("results").replaceChildren(...results.slice(0, state.shown).map((i) => card(dicts[i], recIds)));
  renderMore();
}

function renderMore() {
  const n = shownResults.length;
  $("more").hidden = n <= state.shown;
  $("more").textContent = `显示更多 Show more (${(n - state.shown).toLocaleString()})`;
}

// Append the next page. The cards already on screen are left alone, so a file
// list the user opened stays open.
function showMore() {
  const from = state.shown;
  state.shown += PAGE;
  $("results").append(...shownResults.slice(from, state.shown).map((i) => card(dicts[i], recIds)));
  renderMore();
}

// Put text in the search box the way typing does: set it, then fire "input".
function setQuery(s) {
  const q = $("q");
  q.value = s;
  q.dispatchEvent(new Event("input"));
}

// Put an exact dictionary name in the search box and bring its results into view.
function showInIndex(name) {
  setQuery(name);
  $("count").scrollIntoView({ behavior: "smooth", block: "start" });
}

// Recommended items matching the current query, honouring the active filters.
function matchRecommended() {
  const hits = search(recIndex, state.q, fold) ?? [];
  const filtered = state.lang.size || state.kind.size || state.brand || state.res;
  return hits
    .map((h) => recItems[h.i])
    .filter((it) => {
      const r = byId.get(it.id);
      return r ? passes(r) : !filtered;
    });
}

function renderRecHits(items) {
  const box = $("rec-hits");
  box.hidden = items.length === 0;
  box.replaceChildren(
    ...(items.length ? [recPanel("panel--hits", "★ 推荐版本", `Recommended picks · ${items.length}`, recList(items, byId, showInIndex))] : []),
  );
}

// Index the curated picks for search, and remember which records they point to.
function indexRecommended(rec) {
  recItems = rec.categories.flatMap((c) => c.items);
  recIds = new Set(recItems.map((it) => it.id).filter(Boolean));
  // Search each pick by its curated names plus its record's name and aliases,
  // so "牛津高阶", "OALD" and "Oxford Advanced" all reach the same pick.
  recIndex = buildIndex(
    recItems.map((it) => {
      const r = byId.get(it.id);
      return { n: [it.name, it.zh, it.full].filter(Boolean).join(" "), a: r ? [r.n, ...r.a] : [], b: r ? r.b : [], loc: [] };
    }),
    fold,
  );
}

function renderRecommended(rec) {
  $("rec-meta").textContent =
    `最新版次核对于 ${rec.reviewed}；本站版本按版次、音频图片是否完整、更新时间挑选，未逐一打开验证。` +
    ` Editions checked ${rec.reviewed}; picks judged from file metadata.`;

  indexRecommended(rec);
  const panels = recPanels(rec, recItems, byId, showInIndex);
  if (!panels.some((p) => p.key === state.tab)) state.tab = "starter";

  const tabs = tabController(
    panels,
    () => state.tab,
    (key) => {
      state.tab = key;
      writeUrl();
    },
  );
  selectTab = tabs.select;
  revealActiveTab = tabs.reveal;
  $("rec-cards").replaceChildren(tabs.strip, ...tabs.bodies);
  tabs.select(state.tab);
}

// ---- boot ---------------------------------------------------------------------

async function loadJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return res.json();
}

function bindInputs() {
  const q = $("q");
  if (qEdited) state.q = q.value;
  else q.value = state.q;
  q.addEventListener("input", () => {
    state.q = q.value;
    state.shown = PAGE;
    update();
  });
  q.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && q.value) setQuery("");
  });
  document.addEventListener("keydown", (e) => {
    const typing = e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement;
    if (e.key === "/" && !typing) {
      e.preventDefault();
      q.focus();
    }
  });

  $("more-filters").open = state.kind.size > 0 || Boolean(state.brand) || state.res;

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

  $("more").addEventListener("click", showMore);

  const clearSearch = () => {
    Object.assign(state, { q: "", lang: new Set(), kind: new Set(), brand: "", res: false, sort: "rel", shown: PAGE });
    q.value = "";
    res.checked = false;
    sort.value = "rel";
  };
  $("reset").addEventListener("click", () => {
    clearSearch();
    update();
    q.focus();
  });
  // Back to the recommendation tabs, on whichever tab was last open.
  $("to-rec").addEventListener("click", () => {
    clearSearch();
    update();
    $("rec").scrollIntoView({ behavior: "smooth", block: "start" });
  });
  // The title is a real link to "./" (works in a new tab); a plain click resets in place.
  $("home").addEventListener("click", (e) => {
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    clearSearch();
    selectTab("starter");
    update();
    window.scrollTo({ top: 0, behavior: "smooth" });
    q.focus();
  });

  $("suggest").append(
    ...SUGGESTIONS.map((s) =>
      el("button", {
        type: "button",
        class: "chip",
        textContent: s,
        onclick: () => {
          setQuery(s);
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
  byId = new Map(dicts.map((d) => [d.id, d]));
  renderRecommended(rec);
  bindInputs();
  update();
}

main().catch((err) => {
  console.error(err);
  const stats = $("stats");
  stats.textContent = `索引加载失败 Failed to load the index: ${err.message}`;
  stats.classList.add("error");
});
