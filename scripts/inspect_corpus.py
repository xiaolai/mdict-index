"""Inspect every downloaded dictionary in corpus/ and report its structure.

    .venv/bin/python scripts/inspect_corpus.py [--only key,key]

One full pass over each .mdx (and each downloaded .mdd's key list):
header fields, entry and redirect counts, headword shape, resource
references, HTML tag and class usage, CJK share, and a few sample entries.
Writes corpus/_inspect/report.json (with --only, updating just those keys in it)
and corpus/_inspect/<key>/sample-*.html.
Everything stays under corpus/, which is git-ignored.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from mdict_utils.base.readmdict import MDD, MDX

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
OUT = CORPUS / "_inspect"
SAMPLES = ["take", "set", "run", "serendipity", "hello"]

RE_TAG = re.compile(rb"<([a-zA-Z][a-zA-Z0-9]*)")
RE_CLASS = re.compile(rb'class\s*=\s*["\']([^"\']+)["\']')
# CJK ideographs: the BMP blocks and the supplementary planes (Extension B onwards)
RE_CJK = re.compile("[㐀-䶿一-鿿豈-﫿\U00020000-\U0003FFFF]")
FEATURES = {
    "sound://": re.compile(rb"sound://"),
    "entry://": re.compile(rb"entry://"),
    "bword://": re.compile(rb"bword://"),
    "<img": re.compile(rb"<img\b", re.I),
    "<script": re.compile(rb"<script\b", re.I),
    "<link css": re.compile(rb"<link\b[^>]*\.css", re.I),
    "style=": re.compile(rb"\sstyle\s*=", re.I),
}


def text(value: bytes) -> str:
    return value.decode("utf-8", errors="replace")


def inspect_mdx(path: Path) -> dict:
    mdx = MDX(str(path))
    header = {k.decode("utf-8", "replace"): text(v)[:300] for k, v in mdx.header.items()}
    keys: Counter[str] = Counter()
    tags: Counter[bytes] = Counter()
    classes: Counter[bytes] = Counter()
    features: Counter[str] = Counter()
    n = redirects = empty = cjk = total_bytes = max_bytes = 0
    samples: dict[str, list[str]] = {}
    redirect_example = None
    for raw_key, value in mdx.items():
        key = raw_key.decode("utf-8", errors="replace").strip()  # the reader re-encodes every key as UTF-8
        n += 1
        keys[key] += 1
        stripped = value.strip()
        if not stripped:
            empty += 1
            continue
        if stripped.startswith(b"@@@LINK="):
            redirects += 1
            if redirect_example is None:
                redirect_example = f"{key} -> {text(stripped[8:]).strip()}"
            continue
        total_bytes += len(value)
        max_bytes = max(max_bytes, len(value))
        # Tag/class/feature counts on every entry; decoding only for the CJK check, over the whole entry.
        tags.update(t.lower() for t in RE_TAG.findall(value))
        for cls in RE_CLASS.findall(value):
            classes.update(cls.split())
        for name, pattern in FEATURES.items():
            if pattern.search(value):
                features[name] += 1
        if RE_CJK.search(text(value)):
            cjk += 1
        if key.lower() in SAMPLES and len(samples.get(key.lower(), [])) < 2:
            samples.setdefault(key.lower(), []).append(text(value))
    content = n - redirects - empty
    return {
        "file": path.name,
        "bytes": path.stat().st_size,
        "version": mdx._version,
        "encoding": mdx._encoding,
        "header": {k: header[k] for k in header if k in (
            "GeneratedByEngineVersion", "RequiredEngineVersion", "Format", "KeyCaseSensitive", "StripKey",
            "Encrypted", "Encoding", "CreationDate", "Compact", "Compat", "Left2Right", "Title")},
        "description": re.sub(r"<[^>]+>", " ", header.get("Description", ""))[:200].strip(),
        "has_stylesheet_header": bool(mdx._stylesheet),
        "entries": n,
        "content_entries": content,
        "redirects": redirects,
        "empty": empty,
        "unique_headwords": len(keys),
        "duplicated_headwords": sum(1 for c in keys.values() if c > 1),
        "multiword_headwords": sum(1 for k in keys if " " in k),
        "cjk_headwords": sum(1 for k in keys if RE_CJK.search(k)),
        "cjk_entry_share": round(cjk / content, 3) if content else 0,
        "html_bytes_total": total_bytes,
        "html_bytes_mean": round(total_bytes / content) if content else 0,
        "html_bytes_max": max_bytes,
        "features": {k: features[k] for k in FEATURES},
        "top_tags": [t.decode() for t, _ in tags.most_common(12)],
        "top_classes": [(c.decode("utf-8", "replace"), k) for c, k in classes.most_common(40)],
        "redirect_example": redirect_example,
        "_samples": samples,
    }


def inspect_mdd(path: Path) -> dict:
    mdd = MDD(str(path))
    exts: Counter[str] = Counter()
    names = []
    for raw_key in mdd.keys():
        name = raw_key.decode("utf-8", errors="replace") if isinstance(raw_key, bytes) else str(raw_key)
        exts[(Path(name.replace("\\", "/")).suffix or "(none)").lower()] += 1
        if len(names) < 8:
            names.append(name)
    return {"file": path.name, "bytes": path.stat().st_size, "resources": sum(exts.values()),
            "by_ext": dict(exts.most_common(10)), "examples": names}


def inspect_key(key: str) -> dict:
    t0 = time.time()
    folder = CORPUS / key
    out: dict = {"key": key, "mdx": [], "mdd": [], "errors": []}
    for path in sorted(folder.iterdir()):
        low = path.name.lower()
        try:
            if low.endswith(".mdx"):
                out["mdx"].append(inspect_mdx(path))
            elif low.endswith(".mdd"):
                out["mdd"].append(inspect_mdd(path))
        except Exception as e:  # recorded per file and surfaced in the summary
            out["errors"].append(f"{path.name}: {type(e).__name__}: {e}")
    sample_dir = OUT / key
    sample_dir.mkdir(parents=True, exist_ok=True)
    for m in out["mdx"]:
        for word, htmls in m.pop("_samples").items():
            for i, html in enumerate(htmls):
                (sample_dir / f"sample-{word}-{i}.html").write_text(html)
    out["seconds"] = round(time.time() - t0, 1)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    only = set(filter(None, args.only.split(",")))
    present = sorted(p.name for p in CORPUS.iterdir() if p.is_dir() and not p.name.startswith("_"))
    if unknown := sorted(only - set(present)):
        raise SystemExit(f"--only: no corpus folder for {unknown}; present: {', '.join(present)}")
    keys = [k for k in present if not only or k in only]
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    with ProcessPoolExecutor(6) as pool:
        futures = {pool.submit(inspect_key, k): k for k in keys}
        for fut in as_completed(futures):
            k = futures[fut]
            results[k] = fut.result()
            r = results[k]
            status = "ERR " if r["errors"] else "ok  "
            entries = sum(m["entries"] for m in r["mdx"])
            print(f"{status}{k:11} {entries:>9,} entries  {r['seconds']:>6}s  {'; '.join(r['errors'])}", file=sys.stderr)
    report_path = OUT / "report.json"
    # --only re-inspects some dictionaries: the others keep their entries (build_unified.py reads them all).
    report = json.loads(report_path.read_text()) if only and report_path.exists() else {}
    report.update(results)
    report_path.write_text(json.dumps(dict(sorted(report.items())), ensure_ascii=False, indent=1))
    if any(r["errors"] for r in results.values()):
        sys.exit("some dictionaries could not be read; see report.json")


if __name__ == "__main__":
    main()
