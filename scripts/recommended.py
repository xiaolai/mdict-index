"""Resolve the hand-curated recommendations (data/recommended.json) to record ids.

Each curated pick names a dictionary file; resolve_recommended validates the
curation file and points every pick at the id of the matching record in the
site's dicts.json, so the site can link a pick to its download. build_site.py
calls it after building the records.
"""
from __future__ import annotations

import unicodedata
from collections import defaultdict

STATUSES = {"current", "behind", "snapshot", "final", "unclear", "missing"}


def resolve_recommended(curated: dict, dicts: list[dict]) -> tuple[dict, list[str]]:
    """Point each curated pick at a record id.

    A malformed curation file is an authoring error and raises. A pick that
    matches no record (the file left freemdict) resolves to null with a
    warning: one vanished file must not block the monthly update.
    """
    by_name: dict[str, list[dict]] = defaultdict(list)
    for d in dicts:
        if d["k"] == "mdx":
            by_name[unicodedata.normalize("NFC", d["n"])].append(d)

    warnings: list[str] = []
    seen: set[str] = set()
    categories = []
    for cat in curated["categories"]:
        missing = {"key", "zh", "en", "tab_zh", "tab_en"} - cat.keys()
        if missing:
            raise ValueError(f"recommended category {cat.get('key')!r}: missing {sorted(missing)}")
        items = []
        for item in cat["items"]:
            key = item["key"]
            if key in seen:
                raise ValueError(f"recommended: duplicate key {key!r}")
            seen.add(key)
            if item["status"] not in STATUSES:
                raise ValueError(f"recommended {key!r}: unknown status {item['status']!r}")
            if not str(item.get("src", "https://")).startswith("https://"):
                raise ValueError(f"recommended {key!r}: src must be an https:// URL")
            pick = item.get("pick")
            if pick is None and item["status"] != "missing":
                raise ValueError(f"recommended {key!r}: no pick, so status must be 'missing'")
            rid = None
            if pick:
                folder = pick.get("folder")
                matches = [
                    d for d in by_name.get(unicodedata.normalize("NFC", pick["name"]), [])
                    if folder is None or any(folder in loc["p"] for loc in d["loc"])
                ]
                if not matches:
                    warnings.append(f"recommended {key!r}: no record named {pick['name']!r} is on freemdict any more")
                else:
                    if len(matches) > 1:
                        warnings.append(f"recommended {key!r}: {len(matches)} records match; using the most complete")
                    rid = max(matches, key=lambda d: d["s"])["id"]
            items.append({**{k: v for k, v in item.items() if k != "pick"}, "id": rid})
        categories.append({**{k: v for k, v in cat.items() if k != "items"}, "items": items})
    return {"reviewed": curated["reviewed"], "categories": categories}, warnings
