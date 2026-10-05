// The text analyzer's result as HTML (analyzer/README.md): each sentence with its phrases,
// collocations and notable words marked, and under it what each of them is.
// Pure functions returning HTML strings (no DOM), so they run under `node --test`.
// Every value is escaped: definitions come from third-party dictionaries.

import { esc } from "./render.js";

const NOTABLE_CEFR = new Set(["b2", "c1", "c2"]);
const SLOT = /\{([^{}]+)\}/g;
const SLOT_WORDS = { obj: "sb/sth", poss: "one's", "...": "…" };

/** A pattern as a reader writes it: "give {obj} up" -> "give sb/sth up", "take {sb/sth} for granted" ->
 *  "take sb/sth for granted". */
export const readable = (variant) => String(variant ?? "").replace(SLOT, (_, s) => SLOT_WORDS[s] ?? s);

/** The spans a reader sees: every likely one, and the possible ones when asked for. */
export const shownSpans = (spans, possible) => spans.filter((s) => possible || s.confidence === "likely");

/** What makes a word worth a note: a high level, a label, a spelling flag, a known confusion. */
export function wordNotes(token) {
  const notes = [];
  if (NOTABLE_CEFR.has(token.cefr)) notes.push(token.cefr.toUpperCase());
  for (const label of token.labels ?? []) notes.push(label.split(":")[1]);
  for (const flag of token.flags ?? []) {
    if (flag.kind === "misspelling") notes.push(`→ ${flag.word}`);
    else notes.push(flag.suggestions?.length ? `? ${flag.suggestions.join(", ")}` : "?");
  }
  for (const c of (token.confusable ?? []).filter((c) => c.notable)) notes.push(`≠ ${c.word}`);
  return notes;
}

/**
 * The stretch [start, end) cut wherever a mark begins or ends; each piece with the marks covering it.
 * marks: [{from, to, cls}]. Pieces without marks come back with an empty class list.
 */
export function segments(start, end, marks) {
  const cuts = new Set([start, end]);
  for (const m of marks) {
    if (m.from > start && m.from < end) cuts.add(m.from);
    if (m.to > start && m.to < end) cuts.add(m.to);
  }
  const points = [...cuts].sort((a, b) => a - b);
  return points.slice(0, -1).map((from, i) => {
    const to = points[i + 1];
    const classes = [...new Set(marks.filter((m) => m.from <= from && m.to >= to).map((m) => m.cls))];
    return { from, to, classes };
  });
}

function spanClass(span) {
  const base = span.source === "phrase" ? "a-phrase" : "a-colloc";
  return span.confidence === "likely" ? base : `${base} a-possible`;
}

function chipClass(span) {
  const kind = span.source === "phrase" ? "a-chip--phrase" : "a-chip--colloc";
  return `a-chip ${kind}${span.confidence === "likely" ? "" : " a-chip--possible"}`;
}

function chip(text, span) {
  const words = span.ranges.map(([a, b]) => text.slice(a, b)).join(" … ");
  const name = span.source === "phrase" ? readable(span.variant) : span.text.replace("~", span.base);
  const entry = span.source === "phrase" && span.variant !== span.text ? ` <span class="a-chip__meta">(${esc(readable(span.text))})</span>` : "";
  const kind = span.source === "phrase" ? span.kind.replace("_", " ") : `collocation · ${span.relation.replace("_", "–")}`;
  const sure = span.confidence === "likely" ? "" : ` · <span class="a-chip__possible">possible</span>`;
  const def = [span.definition, span.definition_zh].filter(Boolean).map((d, i) =>
    `<span class="${i ? "u-def-zh" : "u-def"}">${esc(d)}</span>`).join("");
  const look = name.split(" ").find((w) => w.length > 2 && !w.includes("/")) ?? name;
  return (
    `<li class="${chipClass(span)}"><span class="a-chip__words">${esc(words)}</span> = ` +
    `<b>${esc(name)}</b>${entry} <span class="a-chip__meta">${esc(kind)} · ${Number(span.n)} 部词典 dictionaries${sure}</span>` +
    `${def} <a class="a-chip__look" href="/?q=${encodeURIComponent(look)}">查 Look up</a></li>`
  );
}

function wordChip(token) {
  const notes = wordNotes(token);
  return `<li class="a-chip a-chip--word"><a href="/?q=${encodeURIComponent(token.lemma)}">${esc(token.text)}</a> ` +
    `<span class="a-chip__meta">${notes.map(esc).join(" · ")}</span></li>`;
}

/** The whole result: one block per sentence. */
export function renderAnalysis(text, result, { possible = false } = {}) {
  const spans = shownSpans(result.spans, possible);
  if (!result.sentences.length) return `<p class="results__note">没有文字 No text to analyse.</p>`;
  const blocks = result.sentences.map(([start, end]) => {
    const here = spans.filter((s) => s.ranges[0][0] >= start && s.ranges[0][0] < end);
    const words = result.tokens.filter((t) => t.start >= start && t.start < end && wordNotes(t).length);
    const marks = [
      ...here.flatMap((s) => s.ranges.map(([from, to]) => ({ from, to, cls: spanClass(s).split(" ")[0] }))),
      ...here.filter((s) => s.confidence !== "likely").flatMap((s) => s.ranges.map(([from, to]) => ({ from, to, cls: "a-possible" }))),
      ...words.map((t) => ({ from: t.start, to: t.end, cls: "a-word" })),
    ];
    const sentence = segments(start, end, marks).map(({ from, to, classes }) =>
      classes.length ? `<mark class="${classes.join(" ")}">${esc(text.slice(from, to))}</mark>` : esc(text.slice(from, to))).join("");
    const list = here.map((s) => chip(text, s)).concat(words.map(wordChip));
    return `<section class="dict-card a-sentence"><p class="a-text">${sentence}</p>` +
      (list.length ? `<ul class="a-chips">${list.join("")}</ul>` : "") + `</section>`;
  });
  const counts = `${spans.filter((s) => s.source === "phrase").length} 个短语 phrases · ` +
    `${spans.filter((s) => s.source === "collocation").length} 个搭配 collocations`;
  return `<p class="results__note">${counts}</p>` + blocks.join("");
}
