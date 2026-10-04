import { esc, renderEntry, resultSummary } from "./render.js";

const $ = (selector) => document.querySelector(selector);
const out = $("#out");
const input = $("#q");
// CJK ideographs, including the supplementary planes (Extension B onwards).
const CJK = /[\u3400-\u9fff\uf900-\ufaff\u{20000}-\u{3ffff}]/u;
let generation = 0; // the latest search; a response for any earlier one is dropped

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return res.json();
}

function show(html) {
  out.innerHTML = html;
}

function card(hit) {
  const via = hit.via.length ? `<span class="dict-card__via">← ${hit.via.map(esc).join(" → ")}</span>` : "";
  return (
    `<section class="dict-card"><header class="dict-card__head"><h2 class="dict-card__name">${esc(hit.dict_name)}</h2>${via}</header>` +
    hit.summaries.map(renderEntry).join("") +
    `<details class="dict-card__original"><summary>原文 Original design</summary>` +
    `<div class="dict-card__frames" data-ids="${hit.entry_ids.map(Number).join(",")}"></div></details></section>`
  );
}

// lookup, zh and define return the results' HTML; run() decides whether it is still wanted.
async function lookup(q) {
  const r = await getJSON(`/api/lookup?q=${encodeURIComponent(q)}`);
  if (!r.hits.length) {
    const links = r.suggestions.map((s) => `<a href="?q=${encodeURIComponent(s)}">${esc(s)}</a>`).join(", ");
    return `<p class="results__note">没有找到 No entry for <b>${esc(q)}</b>.${links ? ` 你是不是要找 Did you mean: ${links}` : ""}</p>`;
  }
  return `<p class="results__note">${esc(resultSummary(r.hits))}</p>` + r.hits.map(card).join("");
}

async function zh(q) {
  const r = await getJSON(`/api/zh?q=${encodeURIComponent(q)}`);
  return (r.results.length
    ? `<p class="results__note">中→英 Chinese → English</p>` + r.results.map((x) =>
        `<section class="dict-card hit"><a class="hit__word" href="?q=${encodeURIComponent(x.headword)}">${esc(x.headword)}</a>` +
        `<span class="hit__meta">${x.dicts.length} 部词典 dictionaries</span>` +
        x.glosses.map((g) => `<span class="u-def-zh">${esc(g)}</span>`).join("") + `</section>`).join("")
    : `<p class="results__note">没有找到 No English word for <b>${esc(q)}</b>.</p>`);
}

async function define(q) {
  const r = await getJSON(`/api/define?q=${encodeURIComponent(q)}`);
  return (r.results.length
    ? `<p class="results__note">按释义 By definition</p>` + r.results.map((x) =>
        `<section class="dict-card hit"><a class="hit__word" href="?q=${encodeURIComponent(x.headword)}">${esc(x.headword)}</a>` +
        `<span class="hit__meta">${esc(x.dict)}</span><span class="u-def">${esc(x.definition)}</span></section>`).join("")
    : `<p class="results__note">没有释义匹配 No definitions match <b>${esc(q)}</b>.</p>`);
}

async function run(params) {
  const current = ++generation;
  const q = (params.get("q") || params.get("define") || "").trim();
  input.value = q;
  if (!q) return show("");
  show(`<p class="results__note">…</p>`);
  let html;
  try {
    if (params.has("define")) html = await define(q);
    else if (CJK.test(q)) html = await zh(q);
    else html = await lookup(q);
  } catch (err) {
    html = `<p class="error">出错了 Something went wrong: ${esc(err.message)}</p>`;
  }
  if (current === generation) show(html); // a newer search started meanwhile: its results win
}

function go(key, q) {
  const params = new URLSearchParams({ [key]: q });
  history.pushState(null, "", `?${params}`);
  run(params);
}

$("#form").addEventListener("submit", (e) => {
  e.preventDefault();
  if (input.value.trim()) go("q", input.value.trim());
});
$("#define").addEventListener("click", () => input.value.trim() && go("define", input.value.trim()));
window.addEventListener("popstate", () => run(new URLSearchParams(location.search)));

out.addEventListener("click", async (e) => {
  const play = e.target.closest("button[data-audio]");
  if (play) {
    try {
      await new Audio(play.dataset.audio).play();
    } catch (err) {
      play.after(Object.assign(document.createElement("span"), { className: "error", textContent: `播放失败 Playback failed: ${err.message}` }));
    }
    return;
  }
  const more = e.target.closest("button.u-more");
  if (more) {
    more.disabled = true;
    try {
      const full = await getJSON(`/api/entry/${Number(more.dataset.entry)}`);
      more.closest(".u-entry").outerHTML = renderEntry(full);
    } catch (err) {
      more.replaceWith(Object.assign(document.createElement("p"), { className: "error", textContent: err.message }));
    }
  }
});

// Original designs load only when opened: 25 full dictionary pages at once would be heavy.
out.addEventListener("toggle", (e) => {
  const box = e.target.querySelector?.(".dict-card__frames");
  if (!e.target.open || !box || box.childElementCount) return;
  for (const id of box.dataset.ids.split(",").map(Number)) {
    const frame = document.createElement("iframe");
    Object.assign(frame, { className: "dict-card__frame", loading: "lazy", src: `/entry/${id}` });
    frame.setAttribute("sandbox", "allow-scripts allow-top-navigation-by-user-activation");
    box.append(frame);
  }
}, true);

run(new URLSearchParams(location.search));
