// The site's controller (site/app.js) against a minimal stand-in DOM: what the
// page does to the search box, the result list and the filter chips.
import assert from "node:assert/strict";
import { test } from "node:test";

class Node {
  constructor(tag) {
    Object.assign(this, { tagName: tag, children: [], parent: null, listeners: {}, attrs: {} });
    // Properties app.js sets directly (`k in node`); anything else goes through setAttribute.
    Object.assign(this, { className: "", id: "", type: "", title: "", href: "", rel: "", value: "", tabIndex: 0,
      hidden: false, disabled: false, open: false, checked: false, dataset: {}, classList: { add() {} } });
    this.text = "";
  }
  get textContent() {
    return this.text + this.children.map((c) => (typeof c === "string" ? c : c.textContent)).join("");
  }
  set textContent(v) {
    this.replaceChildren();
    this.text = String(v);
  }
  get parentElement() {
    return this.parent;
  }
  get lastChild() {
    return this.children.at(-1) ?? null;
  }
  addEventListener(type, fn) {
    (this.listeners[type] ??= []).push(fn);
  }
  dispatchEvent(event) {
    for (const fn of this.listeners[event.type] ?? []) fn(event);
  }
  click() {
    this.dispatchEvent({ type: "click", button: 0, preventDefault() {} });
  }
  setAttribute(k, v) {
    this.attrs[k] = String(v);
  }
  getAttribute(k) {
    return this.attrs[k] ?? null;
  }
  append(...nodes) {
    for (const n of nodes) {
      if (typeof n !== "string") n.parent = this;
      this.children.push(n);
    }
  }
  // Like a browser: a focused element that leaves the document loses focus.
  replaceChildren(...nodes) {
    for (const c of this.children) if (typeof c !== "string" && c.contains(document.activeElement)) document.activeElement = document.body;
    this.children = [];
    this.text = "";
    this.append(...nodes);
  }
  contains(node) {
    return node === this || this.children.some((c) => typeof c !== "string" && c.contains(node));
  }
  focus() {
    if (!this.disabled) document.activeElement = this;
  }
  scrollIntoView() {}
}

const rec = (i) => ({ id: `id${i}`, k: "mdx", n: `Grelt ${String(i).padStart(3, "0")}`, l: i % 2 ? "en-en" : "en-zh",
  b: i % 3 ? [] : ["Frob Press"], a: [], s: 10, d: "2024-01-01", loc: [{ p: "x", f: [[`Grelt${i}.mdx`, 10]] }] });
const DATA = {
  "data/dicts.json": Array.from({ length: 60 }, (_, i) => rec(i)),
  "data/meta.json": { total: 60, by_lang: {}, crawled: "2024-01-01", tracking_since: "2024-01-01", changes: [] },
  "t2s.json": {},
  "data/recommended.json": { reviewed: "2024-01-01", categories: [] },
};

// Load a fresh copy of the app; `whileLoading` runs before the JSON arrives.
let copy = 0;
async function boot({ search = "", whileLoading = () => {} } = {}) {
  const byId = new Map();
  const body = new Node("body");
  globalThis.document = {
    body,
    activeElement: body,
    createElement: (tag) => new Node(tag),
    getElementById: (id) => byId.get(id) ?? byId.set(id, Object.assign(new Node("div"), { id })).get(id),
    addEventListener() {},
  };
  const urls = [];
  globalThis.location = { search, pathname: "/" };
  globalThis.history = { replaceState: (_s, _t, url) => urls.push(url) };
  globalThis.window = { scrollTo() {} };
  globalThis.HTMLInputElement = globalThis.HTMLSelectElement = class {};
  let release;
  const gate = new Promise((resolve) => (release = resolve));
  globalThis.fetch = async (url) => {
    await gate;
    return { ok: true, json: async () => structuredClone(DATA[url]) };
  };
  await import(`../site/app.js?copy=${copy++}`);
  whileLoading(document);
  release();
  for (let i = 0; i < 20; i++) await new Promise((resolve) => setImmediate(resolve));
  return { $: document.getElementById, urls };
}

// What a browser does when the user edits the box: change the value, then fire "input".
const type = (box, text) => {
  box.value = text;
  box.dispatchEvent({ type: "input" });
};

test("text typed while the index loads is searched, not overwritten", async () => {
  const { $, urls } = await boot({ search: "?q=frob", whileLoading: (doc) => type(doc.getElementById("q"), "grelt 007") });
  assert.equal($("q").value, "grelt 007");
  assert.match($("count").textContent, /^1 /);
  assert.equal(urls.at(-1), "?q=grelt+007");
});

test("a box cleared while the index loads stays empty", async () => {
  const { $, urls } = await boot({
    search: "?q=grelt+007",
    whileLoading: (doc) => {
      type(doc.getElementById("q"), "grelt 00");
      type(doc.getElementById("q"), "");
    },
  });
  assert.equal($("q").value, "");
  assert.match($("count").textContent, /^60 /);
  assert.equal(urls.at(-1), "/");
});

test("without typing, the query comes from the URL", async () => {
  const { $ } = await boot({ search: "?q=grelt+007" });
  assert.equal($("q").value, "grelt 007");
  assert.match($("count").textContent, /^1 /);
});

test("show more appends cards and leaves the ones on screen untouched", async () => {
  const { $ } = await boot();
  const before = [...$("results").children];
  assert.equal(before.length, 50);
  assert.equal($("more").hidden, false);
  $("more").click();
  assert.equal($("results").children.length, 60);
  before.forEach((card, i) => assert.equal($("results").children[i], card)); // same nodes: an open file list stays open
  assert.equal($("more").hidden, true);
});

test("a filter chip keeps keyboard focus when it is toggled", async () => {
  const { $ } = await boot();
  for (const id of ["f-lang", "f-kind", "f-brand"]) {
    const chip = $(id).children[0];
    chip.focus();
    chip.click();
    assert.equal(document.activeElement, chip, id);
    assert.equal($(id).children[0].getAttribute("aria-pressed"), "true", id);
    chip.click();
    assert.equal(document.activeElement, chip, id);
    assert.equal($(id).children[0].getAttribute("aria-pressed"), "false", id);
  }
});

test("filter chips still filter after the search is reset", async () => {
  const { $ } = await boot();
  for (const reset of ["reset", "to-rec", "home"]) {
    $("f-lang").children[0].click(); // en-en: odd records only
    assert.match($("count").textContent, /^30 /, reset);
    $(reset).click();
    assert.match($("count").textContent, /^60 /, reset);
    assert.equal($("f-lang").children[0].getAttribute("aria-pressed"), "false", reset);

    $("f-lang").children[0].click();
    assert.match($("count").textContent, /^30 /, reset);
    assert.equal($("f-lang").children[0].getAttribute("aria-pressed"), "true", reset);
    $("f-kind").children[1].click(); // mdd: none of the records
    assert.match($("count").textContent, /No matches/, reset);
    assert.equal($("f-kind").children[1].getAttribute("aria-pressed"), "true", reset);
    $(reset).click();
  }
});

test("chip counts follow the other filters", async () => {
  const { $ } = await boot();
  const brand = $("f-brand").children[0];
  assert.match(brand.textContent, /^Frob Press20$/);
  $("f-lang").children[0].click(); // en-en: odd records only
  assert.match(brand.textContent, /^Frob Press10$/);
  assert.match($("count").textContent, /^30 /);
});

test("recommendation tabs: one selected, arrows wrap, the URL follows, picks are searchable", async () => {
  const item = (key, id, extra = {}) => ({ key, id, name: key, full: `${key} full`, latest: "1", src: "https://example.invalid/", note: "", status: "current", ...extra });
  DATA["data/recommended.json"] = {
    reviewed: "2024-01-01",
    categories: [
      { key: "one", zh: "一", en: "One", tab_zh: "一", tab_en: "One", items: [item("Quux", "id3", { starter: true })] },
      { key: "two", zh: "二", en: "Two", tab_zh: "二", tab_en: "Two", items: [item("Zorp", "id4"), item("Gone", null, { status: "missing" })] },
    ],
  };
  const { $, urls } = await boot({ search: "?tab=two" });
  const [strip, ...panels] = $("rec-cards").children;
  const selected = () => strip.children.map((t) => t.getAttribute("aria-selected"));
  assert.deepEqual(strip.children.map((t) => t.id), ["tab-starter", "tab-one", "tab-two"]);
  assert.deepEqual(selected(), ["false", "false", "true"]);
  assert.deepEqual(panels.map((p) => p.hidden), [true, true, false]);

  strip.dispatchEvent({ type: "keydown", key: "ArrowRight", preventDefault() {} }); // wraps to the first tab
  assert.deepEqual(selected(), ["true", "false", "false"]);
  assert.equal(document.activeElement, strip.children[0]);
  assert.deepEqual(strip.children.map((t) => t.tabIndex), [0, -1, -1]);
  strip.children[1].click();
  assert.deepEqual(panels.map((p) => p.hidden), [true, false, true]);
  assert.equal(urls.at(-1), "?tab=one");

  // A pick is found by its curated name and by its record's name.
  for (const q of ["zorp", "grelt 004"]) {
    $("q").value = q;
    $("q").dispatchEvent({ type: "input" });
    assert.equal($("rec-hits").hidden, false, q);
  }
  DATA["data/recommended.json"] = { reviewed: "2024-01-01", categories: [] };
});
