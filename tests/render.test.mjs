import assert from "node:assert/strict";
import { test } from "node:test";
import { esc, groupSenses, KINDS, renderEntry, renderPron, resultSummary, STUBS } from "../scripts/lookup_ui/render.js";

const sense = (over = {}) => ({ kind: "sense", pos: "verb", number: "1", phrase: "", labels: [], definition: "to grelt",
  definition_zh: "", examples: [], ...over });
const entry = (over = {}) => ({ entry_id: 7, headword: "grelt", homograph: "", pos: ["verb"], forms: [], etymology: "",
  stub: "", prons: [], senses: [sense()], totals: { senses: 1, examples: 0 }, ...over });

test("every database value is escaped, in text and in attributes", () => {
  const evil = '<img src=x onerror="alert(1)">';
  const html = renderEntry(entry({
    headword: evil, pos: [evil], forms: [evil], etymology: evil,
    prons: [{ region: "uk", ipa: evil, note: evil, audio: `x" onclick="alert(1)` }],
    senses: [sense({ labels: [evil], definition: evil, definition_zh: evil,
      examples: [{ kind: "example", text: evil, text_zh: evil, source: evil, date: evil, labels: [evil] }] })],
  }));
  assert.ok(!html.includes("<img"), "no element injected");
  assert.ok(!/onclick="alert/.test(html), "no attribute injected");
  assert.equal(esc(`a&b<c>"d'`), "a&amp;b&lt;c&gt;&quot;d&#39;");
});

test("senses group by part of speech, then by section kind, in order", () => {
  const groups = groupSenses([
    sense({ pos: "verb" }), sense({ pos: "verb", number: "2" }), sense({ pos: "noun" }),
    sense({ kind: "phrase", phrase: "grelt up" }), sense({ kind: "phrase", phrase: "grelt down" }),
    sense({ kind: "phrasal_verb", phrase: "grelt off" }),
  ]);
  assert.deepEqual(groups.map((g) => [g.title, g.senses.length]),
    [["verb", 2], ["noun", 1], [KINDS.phrase, 2], [KINDS.phrasal_verb, 1]]);
});

test("an entry shows headword, homograph, prons, forms, senses, examples and etymology", () => {
  const html = renderEntry(entry({
    homograph: "2", forms: ["grelted", "grelting"], etymology: "from Old Norse",
    prons: [{ region: "us", ipa: "ɡrɛlt", note: "strong form", audio: "/res/a/g.mp3" }],
    senses: [sense({ labels: ["informal"], definition_zh: "折叠",
      examples: [{ kind: "quotation", text: "He grelted.", text_zh: "", source: "Author, Title", date: "1592", labels: [] }] })],
  }));
  for (const part of ["grelt", '<sup class="u-hom">2</sup>', "美 US", "/ɡrɛlt/", "strong form", 'data-audio="/res/a/g.mp3"',
    "grelted · grelting", "informal", "to grelt", "折叠", "He grelted.", "1592 · Author, Title", "from Old Norse"]) {
    assert.ok(html.includes(part), part);
  }
});

test("a play button appears only when there is audio", () => {
  assert.ok(!renderPron({ region: "", ipa: "x", note: "", audio: "" }).includes("u-play"));
  assert.ok(renderPron({ region: "uk", ipa: "x", note: "", audio: "/res/a/x.mp3" }).includes("u-play"));
});

test("'show all' appears only when senses were left out, with the count", () => {
  assert.ok(!renderEntry(entry()).includes("u-more"));
  const html = renderEntry(entry({ totals: { senses: 9, examples: 0 } }));
  assert.ok(html.includes('data-entry="7"') && html.includes("8 more"));
});

test("'show all' also appears when only examples were left out", () => {
  const ex = { kind: "example", text: "He grelted.", text_zh: "", source: "", date: "", labels: [] };
  const html = renderEntry(entry({ senses: [sense({ examples: [ex, ex] })], totals: { senses: 1, examples: 5 } }));
  assert.ok(html.includes("u-more") && html.includes("3 more examples"), html);
  const both = renderEntry(entry({ senses: [sense({ examples: [ex] })], totals: { senses: 3, examples: 4 } }));
  assert.ok(both.includes("2 more senses") && both.includes("3 more examples"), both);
  assert.ok(!renderEntry(entry({ senses: [sense({ examples: [ex] })], totals: { senses: 1, examples: 1 } })).includes("u-more"));
});

test("stub records say what they are instead of rendering an empty entry", () => {
  const html = renderEntry(entry({ stub: "xref", senses: [], totals: { senses: 0, examples: 0 } }));
  assert.ok(html.includes(STUBS.xref));
  assert.ok(renderEntry(null).includes("u-missing"));
});

test("the results line counts dictionaries, not cards", () => {
  assert.equal(resultSummary([{ dict: "a" }, { dict: "b" }]), "2 部词典 dictionaries");
  assert.equal(resultSummary([{ dict: "a" }, { dict: "a" }, { dict: "b" }]), "2 部词典，3 个词条 2 dictionaries, 3 headwords");
});
