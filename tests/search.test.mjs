import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { buildIndex, compact, makeFold, search } from "../site/search.js";

const t2s = JSON.parse(readFileSync(new URL("../site/t2s.json", import.meta.url)));
const fold = makeFold(t2s);
const rec = (n, a = [], b = [], p = "x") => ({ n, a, b, loc: [{ p, f: [] }] });
const records = [
  rec("[英-汉] 牛津高階學習詞典第7版", ["OALD", "牛津高阶"], ["Oxford"]),
  rec("OALD 10", ["OALD"], ["Oxford"]),
  rec("Longman DOCE5", ["LDOCE", "朗文当代"], ["Longman"]),
  rec("Unicode table", [], [], "100G/英语/专业"),
];
const index = buildIndex(records, fold);
const names = (q) => search(index, q, fold).map((h) => records[h.i].n);

test("empty query returns null, not an empty list", () => {
  assert.equal(search(index, "   ", fold), null);
});

test("traditional and simplified Chinese match each other", () => {
  assert.deepEqual(names("牛津高阶"), ["[英-汉] 牛津高階學習詞典第7版"]);
  assert.deepEqual(names("詞典"), ["[英-汉] 牛津高階學習詞典第7版"]);
});

test("spacing and punctuation are ignored via the compact form", () => {
  assert.deepEqual(names("oald10"), ["OALD 10"]);
  assert.equal(compact(fold("O.A.L.D 10")), "oald10");
});

test("all terms must match", () => {
  assert.deepEqual(names("oald 10"), ["OALD 10"]);
  assert.deepEqual(names("oald longman"), []);
});

test("name matches outrank alias-only matches", () => {
  assert.deepEqual(names("oald"), ["OALD 10", "[英-汉] 牛津高階學習詞典第7版"]);
});

test("aliases and folder paths are searchable", () => {
  assert.deepEqual(names("朗文当代"), ["Longman DOCE5"]);
  assert.deepEqual(names("专业"), ["Unicode table"]);
});

test("case and full-width characters are folded", () => {
  assert.deepEqual(names("ＬＤＯＣＥ"), ["Longman DOCE5"]);
});

test("the compact form never joins two aliases into one match", () => {
  const recs = [rec("Frob", ["phrasal verbs", "短语动词"], ["Grelt Press"])];
  const idx = buildIndex(recs, fold);
  assert.deepEqual(search(idx, "rbs短语动", fold), []); // tail of one alias + head of the next
  assert.deepEqual(search(idx, "词grelt", fold), []); // alias + brand
  assert.equal(search(idx, "phrasalverbs", fold).length, 1); // within one alias, spacing still ignored
  assert.equal(search(idx, "greltpress", fold).length, 1);
});
