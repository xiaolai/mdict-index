"""Look a word up in every dictionary of the unified database at once.

    python3 scripts/unified_lookup.py WORD [--db corpus/unified.db]

For each dictionary: its entries whose lookup form matches the word; if it
has none, its redirects are followed (up to MAX_HOPS) to the entries they
point at. With no exact match anywhere, headwords containing the word are
suggested via the trigram index.

For rendered entries with audio, images and working cross-links, use the
lookup server (scripts/serve_unified.py).
"""
from __future__ import annotations

import argparse
import html
import re
import sqlite3
import string
import sys
import zlib
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_unified import CORPUS, norm  # noqa: E402  (same lookup form as the build)

MAX_HOPS = 5
SUGGESTIONS = 20
CANDIDATES = 400        # trigram matches considered before re-ranking
MIN_SIMILARITY = 0.75   # SequenceMatcher ratio a suggestion must reach


@dataclass(frozen=True)
class Hit:
    entry_id: int
    dict_id: int
    dict_key: str
    dict_name: str
    headword: str
    via: tuple[str, ...]  # redirect chain that led here, empty for a direct hit
    html: str


def _entries(conn: sqlite3.Connection, dict_id: int, key: str) -> list[tuple[int, str, bytes]]:
    return conn.execute(
        "SELECT id, headword, body FROM entry WHERE norm = ? AND dict_id = ? ORDER BY id", (key, dict_id)
    ).fetchall()


def _follow(conn: sqlite3.Connection, dict_id: int, key: str) -> list[tuple[tuple[int, str, bytes], tuple[str, ...]]]:
    """Entries reached from `key` through redirects, each with its chain.

    A redirect may have several targets (an abbreviation naming several
    people), so every target is followed, breadth first, up to MAX_HOPS; a
    target with entries ends its branch. Each entry is returned once, by its
    shortest chain.
    """
    found: list[tuple[tuple[int, str, bytes], tuple[str, ...]]] = []
    frontier: list[tuple[str, tuple[str, ...]]] = [(key, ())]
    seen = {key}
    for _ in range(MAX_HOPS):
        following: list[tuple[str, tuple[str, ...]]] = []
        for current, chain in frontier:
            for target, target_norm in conn.execute(
                "SELECT target, target_norm FROM redirect WHERE norm = ? AND dict_id = ? ORDER BY rowid", (current, dict_id)
            ).fetchall():
                if target_norm in seen:
                    continue
                seen.add(target_norm)
                entries = _entries(conn, dict_id, target_norm)
                if entries:
                    found.extend((e, chain + (target,)) for e in entries)
                else:
                    following.append((target_norm, chain + (target,)))
        if not following:
            break
        frontier = following
    return found


def lookup(conn: sqlite3.Connection, word: str) -> list[Hit]:
    key = norm(word)
    hits: list[Hit] = []
    for dict_id, dkey, name in conn.execute("SELECT id, key, name FROM dictionary ORDER BY id"):
        direct = _entries(conn, dict_id, key)
        found = [(e, ()) for e in direct] if direct else _follow(conn, dict_id, key)
        for (entry_id, headword, body), chain in found:
            hits.append(Hit(entry_id, dict_id, dkey, name, headword, chain, zlib.decompress(body).decode("utf-8", "replace")))
    return hits


def suggest(conn: sqlite3.Connection, word: str) -> list[str]:
    """Headwords close to `word`, including misspellings ("serendipty").

    Candidates share at least one trigram with the query (FTS5 ranks those
    sharing more first); they are then re-ranked by edit similarity. A plain
    substring query would miss every misspelling.
    """
    key = norm(word)
    if not key:
        return []
    if len(key) < 3:
        return _suggest_short(conn, key)
    grams = sorted({key[i:i + 3] for i in range(len(key) - 2)})
    query = " OR ".join('"' + g.replace('"', '""') + '"' for g in grams)
    candidates = [r[0] for r in conn.execute(
        "SELECT norm FROM headword_fts WHERE headword_fts MATCH ? ORDER BY rank LIMIT ?", (query, CANDIDATES)
    )]
    scored = sorted(((SequenceMatcher(None, key, c).ratio(), c) for c in candidates), key=lambda sc: (-sc[0], sc[1]))
    return [c for score, c in scored if score >= MIN_SIMILARITY][:SUGGESTIONS]


def _suggest_short(conn: sqlite3.Connection, key: str) -> list[str]:
    """Suggestions for a one- or two-character query, too short for trigrams.

    Relevant means: starts with the query ("ab" -> "abc"), or is one edit
    away from it ("bx" -> "box", "ax" -> "a"). Both come from the headword
    index, so nothing unrelated fills the list just by sorting nearby.
    """
    prefixed = [r[0] for r in conn.execute(
        "SELECT norm FROM headword WHERE norm >= ? AND norm < ? ORDER BY length(norm), norm LIMIT ?",
        (key, key + chr(0x10FFFF), CANDIDATES),
    )]
    edits = sorted(_one_edit(key))
    nearby = [r[0] for r in conn.execute(
        f"SELECT norm FROM headword WHERE norm IN ({','.join('?' * len(edits))})", edits
    )]
    candidates = set(prefixed) | set(nearby)
    return sorted(candidates, key=lambda c: (-SequenceMatcher(None, key, c).ratio(), c))[:SUGGESTIONS]


def _one_edit(key: str) -> set[str]:
    """Strings one deletion, transposition, substitution or insertion (of a-z) from `key`."""
    splits = [(key[:i], key[i:]) for i in range(len(key) + 1)]
    out = {a + b[1:] for a, b in splits if b}
    out |= {a + b[1] + b[0] + b[2:] for a, b in splits if len(b) > 1}
    out |= {a + c + b[1:] for a, b in splits if b for c in string.ascii_lowercase}
    out |= {a + c + b for a, b in splits for c in string.ascii_lowercase}
    out.discard("")
    out.discard(key)
    return out


def plain(fragment: str, limit: int = 160) -> str:
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", fragment, flags=re.S | re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "…"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("word")
    ap.add_argument("--db", type=Path, default=CORPUS / "unified.db")
    args = ap.parse_args()
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    hits = lookup(conn, args.word)
    if not hits:
        print(f"no entry for {args.word!r}; did you mean: {', '.join(suggest(conn, args.word)) or '—'}")
        return
    for h in hits:
        via = f"  (via {' → '.join(h.via)})" if h.via else ""
        print(f"[{h.dict_key}] {h.headword}{via}\n    {plain(h.html)}")


if __name__ == "__main__":
    main()
