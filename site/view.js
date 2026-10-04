// Rendering for the site: the element builder, labels and URL builders, result cards,
// recommendation rows and panels, and the header. Holds no state: app.js re-imports itself
// with fresh state per test while this module loads once, so whatever a function needs
// (the recommended ids, the record lookup, the "show in index" action) comes in as an argument.

// All text from the index is inserted with textContent, and every link is
// built from these two hosts: names come from a third-party site.
const HOST = "https://downloads.freemdict.com/";
const DIRECT = "https://downloads-direct.freemdict.com/"; // freemdict routes .rar here (its CDN blocks .rar)
const NEW_DAYS = 60; // about the last two monthly crawls

export const LANGS = [
  ["en-en", "英英", "English"],
  ["en-zh", "英汉", "English–Chinese"],
  ["en-other", "英语–其他", "English–other"],
  ["other", "其他语种", "Other"],
  ["unknown", "未分类", "Unclassified"],
];
export const KINDS = [
  ["mdx", "词典", "Dictionary"],
  ["mdd", "资源包", "Audio/image pack"],
  ["archive", "压缩包", "Archive"],
];
const STATUS = {
  current: ["最新", "Current"],
  behind: ["落后一版", "Behind"],
  snapshot: ["在线快照", "Snapshot"],
  final: ["终版", "Final"],
  unclear: ["版本不明", "Unclear"],
  missing: ["本站暂无", "Missing"],
};

export const $ = (id) => document.getElementById(id);

export function el(tag, props = {}, ...children) {
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

// The last folders are what tell same-named records apart ("[英-汉]/oald4" vs "[英-英]/oald4").
function shortFolder(folder) {
  const parts = folder.split("/").filter(Boolean);
  return parts.length > 3 ? "…/" + parts.slice(-3).join("/") : parts.join("/") || "/";
}

function daysSince(iso) {
  return (Date.now() - Date.parse(iso)) / 86_400_000;
}

// `recIds` is the set of record ids the recommendations point to.
export function card(r, recIds) {
  const [first] = r.loc;
  const [mainName] = first.f[0];
  const ext = mainName.slice(mainName.lastIndexOf(".")).toLowerCase();
  const fileCount = r.loc.reduce((n, l) => n + l.f.length, 0);
  const copies = r.loc.length > 1 ? ` · ${r.loc.length} 处副本 copies` : "";
  return el(
    "li",
    { class: "entry" },
    el("h3", { class: "entry__title", textContent: r.n }),
    el("p", { class: "entry__path", title: first.p, textContent: shortFolder(first.p) }),
    el(
      "div",
      { class: "tags" },
      recIds.has(r.id) && el("span", { class: "tag tag--rec", textContent: "★ 推荐" }),
      el("span", { class: "tag tag--lang", textContent: label(LANGS, r.l) }),
      r.k !== "mdx" && el("span", { class: "tag", textContent: label(KINDS, r.k) }),
      ...r.b.map((b) => el("span", { class: "tag", textContent: b })),
      r.r === 1 && el("span", { class: "tag", textContent: "含音频/图片" }),
      r.fs && daysSince(r.fs) <= NEW_DAYS && el("span", { class: "tag tag--new", textContent: `新收录 ${r.fs}` }),
    ),
    el(
      "div",
      { class: "entry__foot" },
      el("a", {
        class: "btn btn--primary btn--sm",
        href: fileUrl(first.p, mainName),
        rel: "noopener",
        textContent: `下载 ${ext}`,
      }),
      el("span", { class: "entry__meta", textContent: `${fmtSize(r.s)} · ${r.d}${copies}` }),
    ),
    el(
      "details",
      { class: "files" },
      el("summary", { class: "files__summary", textContent: `全部文件 All files (${fileCount})` }),
      ...r.loc.map((loc) =>
        el(
          "div",
          { class: "files__loc" },
          el("a", { class: "files__folder", href: folderUrl(loc.p), rel: "noopener", textContent: loc.p || "/" }),
          el(
            "ul",
            { class: "files__list" },
            ...loc.f.map(([name, size]) =>
              el(
                "li",
                { class: "files__item" },
                el("a", { href: fileUrl(loc.p, name), rel: "noopener", textContent: name }),
                el("span", { class: "files__size", textContent: fmtSize(size) }),
              ),
            ),
          ),
        ),
      ),
    ),
  );
}

// ---- recommendation rows (shared by the tabs and the in-search panel) -------------
// `byId` maps record ids to records; `onFind(name)` shows a record in the index.

const recStatus = (s) =>
  el("span", { class: `status status--${s}`, textContent: `${STATUS[s][0]} ${STATUS[s][1]}` });

function recRow(it, byId, onFind) {
  const r = byId.get(it.id);
  const first = r?.loc[0];
  return el(
    "li",
    { class: "rec-row" },
    el(
      "div",
      { class: "rec-row__dict" },
      el(
        "div",
        {},
        el("span", { class: "rec-row__name", textContent: it.name }),
        it.zh && el("span", { class: "rec-row__zh", textContent: it.zh }),
      ),
      el("span", { class: "rec-row__full", textContent: it.full }),
      el(
        "span",
        { class: "rec-row__latest" },
        "最新版次 ",
        el("a", { href: it.src, rel: "noopener", title: "来源 Source", textContent: it.latest }),
      ),
    ),
    el(
      "div",
      { class: "rec-row__best" },
      r &&
        el("button", {
          type: "button",
          class: "rec-row__find",
          title: "在索引中查看 Show in the index",
          textContent: r.n,
          onclick: () => onFind(r.n),
        }),
      r &&
        el(
          "div",
          { class: "rec-row__sub" },
          el("a", {
            class: "btn btn--primary btn--sm",
            href: fileUrl(first.p, first.f[0][0]),
            rel: "noopener",
            textContent: "下载 Download",
          }),
          el("span", { textContent: fmtSize(r.s) + (r.r === 1 ? " · 含音频/图片" : "") }),
        ),
      el("span", { class: "rec-row__note", textContent: it.note }),
    ),
    el("div", { class: "rec-row__status" }, recStatus(it.status)),
  );
}

export const recList = (items, byId, onFind) =>
  el("ul", { class: "rec-list" }, ...items.map((it) => recRow(it, byId, onFind)));

export function recPanel(modifier, title, sub, ...body) {
  return el(
    "article",
    { class: `panel ${modifier}` },
    el("header", { class: "panel__head" }, el("h3", { class: "panel__title" }, title, el("span", { class: "panel__sub", textContent: sub }))),
    ...body,
  );
}

// One panel per tab: the starter set, then each curated category.
// `recItems` is every curated pick, across categories.
export function recPanels(rec, recItems, byId, onFind) {
  const starters = recItems.filter((it) => it.starter && byId.has(it.id));
  const starterSize = starters.reduce((n, it) => n + byId.get(it.id).s, 0);
  return [
    {
      key: "starter",
      tab: ["入门套装", "Starter set"],
      count: starters.length,
      body: () =>
        recPanel(
          "panel--starter",
          "入门套装",
          `Starter set · ${starters.length} 部 · 共 ${fmtSize(starterSize)}`,
          el("p", {
            class: "panel__note",
            textContent: "一套覆盖学习释义、母语释义、生僻词、发音、搭配、词源和中文释义。体积主要是音频。",
          }),
          recList(starters, byId, onFind),
        ),
    },
    ...rec.categories.map((cat) => ({
      key: cat.key,
      tab: [cat.tab_zh, cat.tab_en],
      count: cat.items.length,
      body: () => recPanel("", cat.zh, cat.en, recList(cat.items, byId, onFind)),
    })),
  ];
}

export function renderHeader(meta) {
  const by = meta.by_lang;
  const stat = (num, text) =>
    el("li", { class: "stats__item" }, el("span", { class: "stats__num", textContent: num }), text);
  $("stats").replaceChildren(
    stat(meta.total.toLocaleString(), "条目 entries"),
    stat((by["en-en"] ?? 0).toLocaleString(), "英英"),
    stat((by["en-zh"] ?? 0).toLocaleString(), "英汉"),
    stat(meta.crawled, "抓取 crawled"),
  );

  const body = $("changes-body");
  if (meta.changes.length === 0) {
    body.textContent = `暂无变更。自 ${meta.tracking_since} 起每月比对一次。No changes yet; checked monthly since ${meta.tracking_since}.`;
    return;
  }
  body.replaceChildren(
    ...meta.changes.map((c) =>
      el(
        "div",
        { class: "change" },
        el("div", { class: "change__title", textContent: `${c.date}  +${c.added.length} / −${c.removed.length}` }),
        ...[
          ["新增 Added", c.added],
          ["移除 Removed", c.removed],
        ]
          .filter(([, names]) => names.length)
          .map(([title, names]) =>
            el(
              "div",
              {},
              title,
              el("ul", { class: "change__list" }, ...names.slice(0, 100).map((nm) => el("li", { textContent: nm }))),
            ),
          ),
      ),
    ),
  );
}
