"""Build the site's search data from the crawl index.

    python3 scripts/build_site.py [--date YYYY-MM-DD]

Reads   data/index.jsonl                 (crawl output, one file per line)
        site/t2s.json                    (Traditional -> Simplified map)
        site/data/dicts.json, meta.json  (previous build, if any)
        data/recommended.json            (hand-curated recommendations)
Writes  site/data/dicts.json             (one record per distinct dictionary)
        site/data/meta.json              (counts, crawl date, change log)
        site/data/recommended.json       (recommendations resolved to record ids)

A record is one dictionary: an .mdx with its same-named .mdd/.css/.js files,
a standalone .mdd resource pack, or an archive whose contents are unknown.
Byte-identical copies in different folders become one record with several
locations. `first_seen` survives rebuilds, which is what makes this a tracker.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from classify import classify
from families import aliases_of, brands_of
from recommended import resolve_recommended

ROOT = Path(__file__).resolve().parent.parent
# An archive or one volume of a split archive; `base` is the name shared by all volumes.
ARCHIVE_RE = re.compile(r"(?P<base>.+?)(\.part\d+\.rar|\.rar|\.r\d\d|\.zip|\.z\d\d|\.(7z|zip)\.\d{3}|\.7z)", re.I)
# The volume a user opens to extract: .zip of a split zip, .part1.rar, .001.
ARCHIVE_ENTRY_RE = re.compile(r"(\.zip|\.part0*1\.rar|\.001|\.7z|\.rar)$", re.I)
ASSET_EXT = (".css", ".js", ".ttf", ".otf", ".woff", ".woff2")
# Folders that hold no dictionaries at all (video courses).
SKIP_PREFIXES = ("Language_Learning_Videos/",)
MAX_SHRINK = 0.2  # refuse to publish if the record count drops more than this
MAX_CHANGES = 60  # change-log entries kept in meta.json


@dataclass
class Record:
    kind: str  # "mdx" | "mdd" | "archive"
    name: str
    lang: str
    size: int
    date: str
    has_resources: bool
    locations: list[dict] = field(default_factory=list)


def make_fold(t2s: dict[str, str]):
    def fold(text: str) -> str:
        text = unicodedata.normalize("NFKC", text).lower()
        return "".join(t2s.get(ch, ch) for ch in text)
    return fold


def iso_date(listing_date: str) -> str:
    return dt.datetime.strptime(listing_date, "%d-%b-%Y %H:%M").date().isoformat()


def strip_ext(name: str) -> str:
    if m := ARCHIVE_RE.fullmatch(name):
        return m["base"]
    return re.sub(r"(\.\d+)?\.(mdx|mdd)$", "", name, flags=re.I)


def group_folder(folder: str, files: list[dict]) -> list[Record]:
    """Split one folder's files into dictionary records."""
    mdx = [f for f in files if f["name"].lower().endswith(".mdx")]
    groups: list[tuple[dict, list[dict]]] = []
    claimed: set[str] = set()
    for m in mdx:
        stem = re.escape(m["name"][:-4].lower())
        own = [m] + [
            f for f in files
            if f is not m and re.fullmatch(stem + r"((\.\d+)?\.mdd|\.css|\.js)", f["name"].lower())
        ]
        claimed.update(f["name"] for f in own)
        groups.append((m, own))

    # A folder with a single dictionary: its stylesheets/fonts belong to it
    # even when they are named differently (a common MDict layout).
    if len(groups) == 1:
        extra = [f for f in files if f["name"].lower().endswith(ASSET_EXT) and f["name"] not in claimed]
        groups[0][1].extend(extra)
        claimed.update(f["name"] for f in extra)

    records = [_record("mdx", folder, m, own) for m, own in groups]

    # .mdd files no .mdx claimed: standalone audio/image packs, grouped by stem.
    orphans: dict[str, list[dict]] = defaultdict(list)
    for f in files:
        if f["name"].lower().endswith(".mdd") and f["name"] not in claimed:
            orphans[strip_ext(f["name"].lower())].append(f)
    for group in orphans.values():
        records.append(_record("mdd", folder, group[0], group))
        claimed.update(f["name"] for f in group)

    archives: dict[str, list[dict]] = defaultdict(list)
    for f in files:
        if m := ARCHIVE_RE.fullmatch(f["name"]):
            archives[m["base"].lower()].append(f)
    for volumes in archives.values():
        entry = min(volumes, key=lambda f: (not ARCHIVE_ENTRY_RE.search(f["name"]), f["name"]))
        records.append(_record("archive", folder, entry, [entry] + [v for v in volumes if v is not entry]))
        claimed.update(f["name"] for f in volumes)

    dropped = [
        f["name"] for f in files
        if (f["name"].lower().endswith((".mdx", ".mdd")) or ARCHIVE_RE.fullmatch(f["name"]))
        and f["name"] not in claimed
    ]
    if dropped:
        raise AssertionError(f"{folder}: dictionary files not assigned to any record: {dropped}")
    return records


def _record(kind: str, folder: str, main: dict, own: list[dict]) -> Record:
    name = unicodedata.normalize("NFC", strip_ext(main["name"]))
    path = f"{folder}/{main['name']}" if folder else main["name"]
    lang = classify(re.sub(r"\.[^./]+$", ".mdx", path))
    return Record(
        kind=kind,
        name=name,
        lang=lang,
        size=sum(f["size"] for f in own),
        date=max(iso_date(f["date"]) for f in own),
        has_resources=kind != "archive" and any(f["name"].lower().endswith(".mdd") for f in own),
        locations=[{
            "folder": folder,
            "files": [[f["name"], f["size"]] for f in own],
            "main_size": main["size"],
        }],
    )


def record_id(r: Record) -> str:
    """Stable identity: the same file content (name + main-file size) anywhere on the site."""
    key = f"{r.kind}|{unicodedata.normalize('NFKC', r.name).lower()}|{r.locations[0]['main_size']}"
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def build_records(index_rows: list[dict]) -> dict[str, Record]:
    folders: dict[str, list[dict]] = defaultdict(list)
    for row in index_rows:
        path = row["path"]
        if path.startswith(SKIP_PREFIXES):
            continue
        folder, _, name = path.rpartition("/")
        folders[folder].append({"name": name, "size": row["size"], "date": row["date"]})

    merged: dict[str, Record] = {}
    for folder in sorted(folders):
        for r in group_folder(folder, sorted(folders[folder], key=lambda f: f["name"])):
            rid = record_id(r)
            if rid in merged:
                merged[rid].locations.extend(r.locations)
                merged[rid].date = min(merged[rid].date, r.date)
            else:
                merged[rid] = r
    for r in merged.values():
        _settle_copies(r)
    return merged


def _settle_copies(r: Record) -> None:
    """Copies share the main file but not always its companions (one copy may
    lack the .mdd). Lead with the most complete copy, since the Download
    button and size come from it, and flag resources if any copy has them."""
    total = lambda loc: sum(size for _, size in loc["files"])
    r.locations.sort(key=lambda loc: (-total(loc), loc["folder"]))
    r.size = total(r.locations[0])
    r.has_resources = r.kind != "archive" and any(
        name.lower().endswith(".mdd") for loc in r.locations for name, _ in loc["files"]
    )


def to_json(rid: str, r: Record, fold, first_seen: str | None) -> dict:
    folded = fold(r.name)
    out = {
        "id": rid,
        "k": r.kind,
        "n": r.name,
        "l": r.lang,
        "b": brands_of(folded),
        "a": aliases_of(folded),
        "s": r.size,
        "d": r.date,
        "loc": [{"p": loc["folder"], "f": loc["files"]} for loc in r.locations],
    }
    if r.has_resources:
        out["r"] = 1
    if first_seen:
        out["fs"] = first_seen
    return out


def load_json(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def build(index_path: Path, out_dir: Path, t2s_path: Path, today: str, recommended_path: Path | None = None) -> dict:
    rows = [json.loads(line) for line in index_path.read_text().splitlines() if line]
    if not rows:
        raise SystemExit(f"{index_path} is empty; refusing to build")
    fold = make_fold(json.loads(t2s_path.read_text()))
    records = build_records(rows)

    prev_dicts = load_json(out_dir / "dicts.json")
    prev_meta = load_json(out_dir / "meta.json") or {}
    prev = {d["id"]: d for d in prev_dicts} if prev_dicts else {}
    if prev and len(records) < len(prev) * (1 - MAX_SHRINK):
        raise SystemExit(
            f"record count fell from {len(prev)} to {len(records)} (>{MAX_SHRINK:.0%}); "
            "likely a partial crawl, refusing to publish"
        )

    tracking_since = prev_meta.get("tracking_since", today)
    dicts = []
    for rid, r in records.items():
        if rid in prev:
            first_seen = prev[rid].get("fs")
        else:
            first_seen = today if prev else None  # the first build is the baseline
        dicts.append(to_json(rid, r, fold, first_seen))
    dicts.sort(key=lambda d: (fold(d["n"]), d["id"]))

    changes = list(prev_meta.get("changes", []))
    if prev:
        added = sorted(d["n"] for d in dicts if d["id"] not in prev)
        removed = sorted(d["n"] for rid, d in prev.items() if rid not in records)
        if added or removed:
            changes.insert(0, {"date": today, "added": added, "removed": removed})
    meta = {
        "crawled": today,
        "tracking_since": tracking_since,
        "source": "https://downloads.freemdict.com/",
        "total": len(dicts),
        "by_lang": _count(d["l"] for d in dicts),
        "by_kind": _count(d["k"] for d in dicts),
        "changes": changes[:MAX_CHANGES],
    }

    recommended = None
    if recommended_path is not None:
        recommended, warnings = resolve_recommended(json.loads(recommended_path.read_text()), dicts)
        prefix = "::warning::" if os.environ.get("GITHUB_ACTIONS") else "WARNING: "
        for w in warnings:
            print(prefix + w, file=sys.stderr)

    out_dir.mkdir(parents=True, exist_ok=True)
    _write_atomic(out_dir / "dicts.json", json.dumps(dicts, ensure_ascii=False, separators=(",", ":")))
    _write_atomic(out_dir / "meta.json", json.dumps(meta, ensure_ascii=False, indent=1))
    if recommended is not None:
        _write_atomic(out_dir / "recommended.json", json.dumps(recommended, ensure_ascii=False, indent=1))
    return meta


def _count(values) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for v in values:
        out[v] += 1
    return dict(sorted(out.items()))


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    ap.add_argument("--index", type=Path, default=ROOT / "data" / "index.jsonl")
    ap.add_argument("--out", type=Path, default=ROOT / "site" / "data")
    args = ap.parse_args()
    meta = build(args.index, args.out, ROOT / "site" / "t2s.json", args.date, ROOT / "data" / "recommended.json")
    print(json.dumps({k: meta[k] for k in ("total", "by_lang", "by_kind")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
