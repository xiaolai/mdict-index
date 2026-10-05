"""Measure the analyzer's precision on running text: a sample of what it marks, screened and read.

    PYTHONPATH=scripts:analyzer .venv/bin/python analyzer/analysis/precision.py [--n 200] [--queue]

Texts are analyzer/data/texts/*.txt: public-domain or freely licensed prose, kept locally
(Project Gutenberg's header and licence are cut off). Each paragraph is analysed; then n phrase
spans and n collocation spans are drawn at random (a fixed seed) from everything marked.

Screen: each sampled span goes to jev's analyzer-span docket (analyzer/jev/dockets, passed
through JEV_HOME); a span is flagged when its "correct" score is below SCREEN. Review: flagged
spans are read and labelled in analyzer/data/precision/review.json ({key: "good" | "bad"});
--queue lists the flagged spans not yet labelled. The lower bound counts unread flags as errors.

The screen misses errors too: an idiom used literally ("the old man at my side" is not "the old
man" = father) reads as fluent English. So spans it passed are also read, a random share of them
(--audit-queue N lists N), labelled in the same file; the estimate then adds their error rate,
per confidence tier, to the flags' errors. jev's answers are cached in answers.json.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(ROOT / "analyzer"), str(ROOT / "scripts")]
from analysis import DATA, load_nlp  # noqa: E402
from analysis.analyze import MAX_CHARS, analyze_doc  # noqa: E402
from analysis.lexicon import load  # noqa: E402

TEXTS = DATA / "texts"
OUT = DATA / "precision"
JEV_HOME = ROOT / "analyzer" / "jev"
SCREEN = 0.5
_GUTENBERG = re.compile(r"\*\*\* START OF .*?\*\*\*(.*?)\*\*\* END OF ", re.S)


def paragraphs(text: str) -> list[str]:
    """Paragraphs with their hard line breaks joined; Gutenberg's front and back matter cut off."""
    if m := _GUTENBERG.search(text):
        text = m.group(1)
    out = []
    for block in re.split(r"\n\s*\n", text):
        para = " ".join(block.split())
        if len(para.split()) >= 8 and not para.startswith("#"):
            out.append(para[:MAX_CHARS])
    return out


def phrase_text(span: dict) -> str:
    """How the docket is told the phrase: a collocation with its base filled in ("make a decision")."""
    if span["source"] == "collocation":
        return span["text"].replace("~", span["base"])
    return span["variant"].replace("{obj}", "sb/sth").replace("{poss}", "one's").replace("{oneself}", "oneself") \
        .replace("{somewhere}", "somewhere").replace("{...}", "...")


def state(record: dict) -> str:
    lines = [f"SENTENCE: {record['sentence']}", f"WORDS: {record['words']}", f"PHRASE: {record['phrase']}"]
    if record["meaning"]:
        lines.append(f"MEANING: {record['meaning'][:200]}")
    return "\n".join(lines)


def ask(record: dict) -> float:
    out = subprocess.run(["jev", "docket", "analyzer-span", "--json", "--retries", "5", "--state", state(record)],
                         capture_output=True, text=True, timeout=120, env={**os.environ, "JEV_HOME": str(JEV_HOME)})
    if out.returncode != 0:
        raise RuntimeError(f"jev exited {out.returncode}: {out.stderr.strip()[:300]}")
    return float(json.loads(out.stdout)["answers"]["correct"]["noul"])


def collect(nlp, lex) -> list[dict]:
    """Every span the analyzer marks in the texts, with its sentence and the words it marked."""
    found = []
    for path in sorted(TEXTS.glob("*.txt")):
        paras = paragraphs(path.read_text(encoding="utf-8", errors="replace"))
        for p, (para, doc) in enumerate(zip(paras, nlp.pipe(paras, batch_size=64))):
            result = analyze_doc(doc, lex)
            for s in result["spans"]:
                start, end = next((a, b) for a, b in result["sentences"] if a <= s["ranges"][0][0] < b)
                found.append({"key": f"{path.stem}:{p}:{s['ranges'][0][0]}:{s['id']}", "source": s["source"],
                              "kind": s["kind"], "n": s["n"], "confidence": s["confidence"], "sentence": para[start:end],
                              "words": " ... ".join(para[a:b] for a, b in s["ranges"]),
                              "phrase": phrase_text(s), "meaning": s["definition"] if s["source"] == "phrase" else ""})
    return found


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200, help="spans sampled per source (phrase, collocation)")
    ap.add_argument("--seed", default="precision")
    ap.add_argument("--queue", action="store_true", help="print the flagged spans awaiting review")
    ap.add_argument("--audit-queue", type=int, default=0, help="print N spans the screen passed, to read")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    nlp, lex = load_nlp(), load()
    spans = collect(nlp, lex)
    by_source = defaultdict(list)
    for s in spans:
        by_source[s["source"]].append(s)
    # one generator per source: a change to one source's spans must not reshuffle the other's sample
    sample = [s for src in sorted(by_source)
              for s in random.Random(f"{args.seed}:{src}").sample(by_source[src], min(args.n, len(by_source[src])))]
    answers_path, review_path = OUT / "answers.json", OUT / "review.json"
    answers = json.loads(answers_path.read_text()) if answers_path.exists() else {}
    todo = [s for s in sample if s["key"] not in answers]
    try:
        with ThreadPoolExecutor(8) as pool:
            for s, score in zip(todo, pool.map(ask, todo)):
                answers[s["key"]] = score
    finally:
        answers_path.write_text(json.dumps(answers, indent=1) + "\n")
    review = json.loads(review_path.read_text()) if review_path.exists() else {}
    (OUT / "sample.jsonl").write_text("".join(json.dumps({**s, "score": answers[s["key"]]}, ensure_ascii=False) + "\n"
                                              for s in sample))
    flagged = [s for s in sample if answers[s["key"]] < SCREEN]
    if args.audit_queue:
        passed = [s for s in sample if answers[s["key"]] >= SCREEN and s["key"] not in review]
        for s in random.Random("audit").sample(passed, min(args.audit_queue, len(passed))):
            print(json.dumps({k: s[k] for k in ("key", "words", "phrase", "sentence")}, ensure_ascii=False))
        return
    if args.queue:
        for s in flagged:
            if s["key"] not in review:
                print(json.dumps({k: s[k] for k in ("key", "words", "phrase", "sentence", "meaning")}, ensure_ascii=False))
        return
    counts = Counter(s["source"] for s in spans)
    print(f"texts: {len(list(TEXTS.glob('*.txt')))} files; spans marked: {dict(counts)}")
    for src in sorted(by_source):
        part = [s for s in sample if s["source"] == src]
        flags = [s for s in part if answers[s["key"]] < SCREEN]
        bad = sum(review.get(s["key"]) == "bad" for s in flags)
        unread = sum(s["key"] not in review for s in flags)
        print(f"{src:12} sample {len(part)}: flagged {len(flags)}, reviewed bad {bad}, unread {unread}; "
              f"screened precision {1 - (bad + unread) / len(part):.1%} (flags read, unread ones errors; "
              f"spans the screen passed counted correct)")
        for tier in sorted({s["confidence"] for s in part}):
            group = [s for s in part if s["confidence"] == tier]
            flagged_bad = sum(review.get(s["key"]) != "good" for s in group if answers[s["key"]] < SCREEN)
            passed = [s for s in group if answers[s["key"]] >= SCREEN]
            audited = [s for s in passed if s["key"] in review]
            if not audited:
                print(f"    {tier:9} {len(group)}: no passed span read yet; estimate needs --audit-queue")
                continue
            miss = sum(review[s["key"]] == "bad" for s in audited) / len(audited)
            estimate = 1 - (flagged_bad + miss * len(passed)) / len(group)
            print(f"    {tier:9} {len(group)}: estimated precision {estimate:.0%} (flags read; {miss:.0%} of "
                  f"{len(audited)} passed spans read were wrong)")
        for field in ("kind", "confidence"):
            groups = Counter(s[field] for s in part)
            bad_in = Counter(s[field] for s in flags if review.get(s["key"]) == "bad" or s["key"] not in review)
            print(f"    by {field}:", {k: f"{1 - bad_in[k] / n:.0%} of {n}" for k, n in groups.most_common()})


if __name__ == "__main__":
    main()
