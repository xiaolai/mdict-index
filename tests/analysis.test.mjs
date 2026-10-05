// The text analyzer's renderer (scripts/lookup_ui/analysis.js): pure functions over a result.
import assert from "node:assert/strict";
import test from "node:test";
import { readable, renderAnalysis, segments, shownSpans, wordNotes } from "../scripts/lookup_ui/analysis.js";

const TEXT = "She gave it up. It was a <bold> choice.";
const span = (o) => ({ source: "phrase", kind: "phrasal_verb", text: "give up", variant: "give {obj} up", base: "",
  relation: "", n: 12, confidence: "likely", definition: "to stop", definition_zh: "放弃", ...o });
const RESULT = {
  sentences: [[0, 15], [16, 39]],
  tokens: [
    { text: "choice", start: 32, end: 38, lemma: "choice", cefr: "b2", labels: [], confusable: [] },
    { text: "She", start: 0, end: 3, lemma: "she" },
  ],
  spans: [
    span({ ranges: [[4, 8], [12, 14]] }),
    span({ kind: "idiom", text: "it up", variant: "it up", confidence: "possible", ranges: [[9, 14]] }),
  ],
};

test("a sentence is cut wherever a mark begins or ends, crossing marks combined", () => {
  const pieces = segments(0, 10, [{ from: 2, to: 6, cls: "a" }, { from: 4, to: 8, cls: "b" }]);
  assert.deepEqual(pieces.map((p) => [p.from, p.to, p.classes.join("+")]),
    [[0, 2, ""], [2, 4, "a"], [4, 6, "a+b"], [6, 8, "b"], [8, 10, ""]]);
});

test("possible spans only when asked for", () => {
  assert.equal(shownSpans(RESULT.spans, false).length, 1);
  assert.equal(shownSpans(RESULT.spans, true).length, 2);
  assert.ok(!renderAnalysis(TEXT, RESULT).includes("it up</b>"));
  assert.ok(renderAnalysis(TEXT, RESULT, { possible: true }).includes("a-chip--possible"));
});

test("slots read as a reader writes them", () => {
  assert.equal(readable("make up {poss} mind"), "make up one's mind");
  assert.equal(readable("give {obj} up"), "give sb/sth up");
  assert.equal(readable("take {sb/sth} for granted"), "take sb/sth for granted");
  assert.equal(readable("what's with {sb/sth} {...}"), "what's with sb/sth …");
});

test("a split phrasal verb is marked in two pieces, the object between left plain", () => {
  const html = renderAnalysis(TEXT, RESULT);
  assert.ok(html.includes('<mark class="a-phrase">gave</mark> it <mark class="a-phrase">up</mark>'));
  assert.ok(html.includes("give sb/sth up") && html.includes("放弃"));
});

test("words worth a note, and only those", () => {
  assert.deepEqual(wordNotes({ cefr: "b2", labels: ["register:formal"], flags: [{ kind: "misspelling", word: "x" }],
    confusable: [{ word: "y", notable: true }, { word: "z", notable: false }] }), ["B2", "formal", "→ x", "≠ y"]);
  assert.deepEqual(wordNotes({ cefr: "a1" }), []);
  assert.ok(renderAnalysis(TEXT, RESULT).includes('<mark class="a-word">choice</mark>'));
});

test("everything from the text and the dictionaries is escaped", () => {
  const html = renderAnalysis(TEXT, { ...RESULT, spans: [span({ definition: "<script>x</script>", ranges: [[4, 8]] })] });
  assert.ok(!html.includes("<script>") && html.includes("&lt;script&gt;"));
  assert.ok(html.includes("&lt;bold&gt;"));
});
