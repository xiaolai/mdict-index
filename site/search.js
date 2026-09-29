// Pure search over dictionary records: no DOM, so it runs under `node --test`.
//
// Matching is substring-based rather than token-based on purpose: dictionary
// names mix Chinese (no spaces between words), abbreviations and edition
// numbers, and a tokenizer would split "牛津高阶" or "OALD10" wrongly.

const NON_WORD = /[^\p{L}\p{N}]+/gu;
const BOUNDARY = /[^\p{L}\p{N}]/u; // one character, no /g: .test() stays stateless

/** Fold text for comparison: NFKC, lowercase, Traditional -> Simplified. */
export function makeFold(t2s) {
  return (text) => {
    let out = "";
    for (const ch of text.normalize("NFKC").toLowerCase()) out += t2s[ch] ?? ch;
    return out;
  };
}

/** Drop spaces and punctuation, so "oald10" matches "OALD 10" and "o.a.l.d". */
export const compact = (text) => text.replace(NON_WORD, "");

export function buildIndex(records, fold) {
  return records.map((r) => {
    const name = fold(r.n);
    const extra = fold([...r.a, ...r.b].join(" "));
    return {
      name,
      nameC: compact(name),
      extra,
      extraC: compact(extra),
      path: fold(r.loc.map((l) => l.p).join(" ")),
    };
  });
}

// Score of one query term against one record; 0 means no match.
function termScore(e, term, termC) {
  if (e.name.startsWith(term)) return 40;
  const at = e.name.indexOf(term);
  if (at > 0 && BOUNDARY.test(e.name[at - 1])) return 30;
  if (at >= 0) return 20;
  if (termC && e.nameC.includes(termC)) return 15;
  if (e.extra.includes(term) || (termC && e.extraC.includes(termC))) return 10;
  if (e.path.includes(term)) return 3;
  return 0;
}

/**
 * Records matching every whitespace-separated term, best first.
 * Returns null for an empty query so callers can tell "no query" from "no hits".
 */
export function search(index, query, fold) {
  const terms = fold(query)
    .split(/\s+/)
    .filter(Boolean)
    .map((t) => [t, compact(t)]);
  if (terms.length === 0) return null;

  const hits = [];
  for (let i = 0; i < index.length; i++) {
    const e = index[i];
    let score = 0;
    for (const [t, c] of terms) {
      const s = termScore(e, t, c);
      if (s === 0) {
        score = 0;
        break;
      }
      score += s;
    }
    // Among equal scores, prefer shorter (more specific) names.
    if (score > 0) hits.push({ i, score: score - e.name.length / 1e4 });
  }
  hits.sort((a, b) => b.score - a.score || a.i - b.i);
  return hits;
}
