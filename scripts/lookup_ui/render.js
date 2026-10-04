// The unified entry view: one layout for every dictionary, rendered from layer-2 data.
// Pure functions returning HTML strings (no DOM), so they run under `node --test`.
// Every value from the database is escaped: entries come from third-party files.

export const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const REGION = { uk: "英 UK", us: "美 US", "": "" };

// Section titles for senses that are not ordinary meanings.
export const KINDS = {
  phrase: "习语与短语 Phrases & idioms",
  phrasal_verb: "短语动词 Phrasal verbs",
  derivative: "派生词 Derivatives",
  collocation: "搭配 Collocations",
  note: "用法说明 Usage notes",
};

// What a stub record is, when a dictionary's record carries no content of its own.
export const STUBS = {
  xref: "参见其他词条 See another entry",
  popup: "附属内容 Part of another entry",
  inflection: "词形变化 An inflected form",
  variant: "异体拼写 A variant spelling",
  derivative: "派生形式 A derived form",
  index: "索引页 An index page",
  image: "插图 An illustration",
  empty: "无释义 No definition",
};

/**
 * Consecutive senses grouped under one heading: a part of speech for ordinary senses,
 * a section title for phrases, phrasal verbs, derivatives, collocations and notes.
 */
export function groupSenses(senses) {
  const groups = [];
  for (const s of senses) {
    const title = s.kind === "sense" ? s.pos || "" : KINDS[s.kind] ?? s.kind;
    const last = groups.at(-1);
    if (last && last.kind === s.kind && last.title === title) last.senses.push(s);
    else groups.push({ kind: s.kind, title, senses: [s] });
  }
  return groups;
}

const labels = (list) =>
  list.length ? `<span class="u-labels">${list.map((l) => `<span class="u-label">${esc(l)}</span>`).join("")}</span>` : "";

export function renderPron(p) {
  const region = REGION[p.region] ?? p.region;
  const play = p.audio
    ? `<button type="button" class="u-play" data-audio="${esc(p.audio)}" aria-label="播放 Play ${esc(p.ipa)}">▶</button>`
    : "";
  return (
    `<span class="u-pron">${region ? `<span class="u-region">${esc(region)}</span>` : ""}` +
    `${p.ipa ? `<span class="u-ipa">/${esc(p.ipa)}/</span>` : ""}` +
    `${p.note ? `<span class="u-note">${esc(p.note)}</span>` : ""}${play}</span>`
  );
}

export function renderExample(x) {
  const cite = [x.date, x.source].filter(Boolean).map(esc).join(" · ");
  return (
    `<li class="u-example u-example--${esc(x.kind)}">${labels(x.labels ?? [])}` +
    `${x.text ? `<span class="u-ex">${esc(x.text)}</span>` : ""}` +
    `${x.text_zh ? `<span class="u-ex-zh">${esc(x.text_zh)}</span>` : ""}` +
    `${cite ? `<cite class="u-cite">${cite}</cite>` : ""}</li>`
  );
}

export function renderSense(s) {
  const examples = s.examples ?? [];
  return (
    `<li class="u-sense">${s.number ? `<span class="u-num">${esc(s.number)}</span>` : ""}<div class="u-body">` +
    `${s.phrase && s.kind !== "sense" ? `<span class="u-phrase">${esc(s.phrase)}</span>` : ""}` +
    labels(s.labels ?? []) +
    `${s.definition ? `<p class="u-def">${esc(s.definition)}</p>` : ""}` +
    `${s.definition_zh ? `<p class="u-def-zh">${esc(s.definition_zh)}</p>` : ""}` +
    `${examples.length ? `<ul class="u-examples">${examples.map(renderExample).join("")}</ul>` : ""}` +
    `</div></li>`
  );
}

/** One dictionary entry in the unified layout, with a "show all" button when senses or examples were left out. */
export function renderEntry(e) {
  if (!e) return `<p class="u-missing">此词典没有结构化数据 No structured data for this entry.</p>`;
  const shownExamples = e.senses.reduce((n, s) => n + (s.examples ?? []).length, 0);
  const moreSenses = Math.max(0, (e.totals?.senses ?? 0) - e.senses.length);
  const moreExamples = Math.max(0, (e.totals?.examples ?? 0) - shownExamples);
  const more = [moreSenses && `${moreSenses} more senses`, moreExamples && `${moreExamples} more examples`]
    .filter(Boolean).join(", ");
  const head =
    `<header class="u-head"><span class="u-hw">${esc(e.headword)}` +
    `${e.homograph ? `<sup class="u-hom">${esc(e.homograph)}</sup>` : ""}</span>` +
    `${e.pos.length ? `<span class="u-pos">${e.pos.map(esc).join(" · ")}</span>` : ""}</header>`;
  const prons = e.prons.length ? `<div class="u-prons">${e.prons.map(renderPron).join("")}</div>` : "";
  const forms = e.forms.length ? `<p class="u-forms">${e.forms.map(esc).join(" · ")}</p>` : "";
  const stub = e.stub && !e.senses.length ? `<p class="u-stub">${esc(STUBS[e.stub] ?? e.stub)}</p>` : "";
  const groups = groupSenses(e.senses)
    .map(
      (g) =>
        `<section class="u-group u-group--${esc(g.kind)}">` +
        `${g.title ? `<h4 class="u-group__title">${esc(g.title)}</h4>` : ""}` +
        `<ol class="u-senses">${g.senses.map(renderSense).join("")}</ol></section>`,
    )
    .join("");
  const etym = e.etymology
    ? `<p class="u-etym"><span class="u-etym__label">词源 Origin</span>${esc(e.etymology)}</p>`
    : "";
  const moreButton = more
    ? `<button type="button" class="link-btn u-more" data-entry="${esc(e.entry_id)}">显示全部 Show all (${more})</button>`
    : "";
  return `<article class="u-entry" data-entry="${esc(e.entry_id)}">${head}${prons}${forms}${stub}${groups}${etym}${moreButton}</article>`;
}

/** The line above the results: dictionaries are counted once even when they have several cards ("set", "Set"). */
export function resultSummary(hits) {
  const dictionaries = new Set(hits.map((h) => h.dict)).size;
  return hits.length === dictionaries
    ? `${dictionaries} 部词典 dictionaries`
    : `${dictionaries} 部词典，${hits.length} 个词条 ${dictionaries} dictionaries, ${hits.length} headwords`;
}
