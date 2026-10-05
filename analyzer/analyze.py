"""Analyse English text: its phrases, collocations, word levels and likely confusions.

    .venv/bin/python analyzer/analyze.py FILE        (or - for standard input)  [--json]
    [--possible] [--min-collocation-n N]

Prints each sentence's phrases and collocations, and the words worth a learner's attention
(above B1, labelled, confusable, misspelt). Phrases the analyzer is less sure of (a verb with a
preposition that may be literal, one content word among function words) are left out unless
--possible; --json prints everything, each span with its confidence (analysis/analyze.py).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parent.parent / "scripts")]
from analysis import load_nlp  # noqa: E402
from analysis.analyze import analyze  # noqa: E402
from analysis.lexicon import load  # noqa: E402

NOTABLE_CEFR = ("b2", "c1", "c2")


def report(text: str, result: dict, possible: bool = False) -> str:
    lines = []
    for start, end in result["sentences"]:
        lines.append(text[start:end].strip())
        for s in (s for s in result["spans"] if start <= s["ranges"][0][0] < end
                  and (possible or s["confidence"] == "likely")):
            words = " ... ".join(text[a:b] for a, b in s["ranges"])
            what = s["kind"] if s["source"] == "phrase" else f"collocation, {s['relation']}"
            entry = s["variant"] if s["source"] == "phrase" else s["text"]
            also = f" (entry: {s['text']})" if s["source"] == "phrase" and s["variant"] != s["text"] else ""
            lines.append(f"    [{what}] {words}  =  {entry}{also}  ({s['n']} dictionaries)")
        for t in (t for t in result["tokens"] if start <= t["start"] < end):
            notes = []
            if t.get("cefr") in NOTABLE_CEFR:
                notes.append(t["cefr"].upper())
            notes += [label.split(":", 1)[1] for label in t.get("labels", [])]
            notes += [f"often confused with {c['word']}" for c in t.get("confusable", []) if c["notable"]][:2]
            for f in t.get("flags", []):
                notes.append(f"misspelling of {f['word']}" if f["kind"] == "misspelling"
                             else "unknown word" + (f"; did you mean {', '.join(f['suggestions'])}?" if f["suggestions"] else ""))
            if notes:
                lines.append(f"    {t['text']}: {'; '.join(notes)}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", help="a text file, or - for standard input")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--possible", action="store_true", help="also phrases the analyzer is less sure of")
    ap.add_argument("--min-collocation-n", type=int, default=2, help="dictionaries a collocation needs (default 2)")
    args = ap.parse_args()
    text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    result = analyze(text, load_nlp(), load(min_collocation_n=args.min_collocation_n))
    print(json.dumps(result, ensure_ascii=False, indent=1) if args.json else report(text, result, args.possible))


if __name__ == "__main__":
    main()
