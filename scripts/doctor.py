"""Check that this machine can build the local dictionary tools; exit 1 naming each fix.

    python3 scripts/doctor.py          (or .venv/bin/python, once the virtual environment exists)

Required: a recent Python, the pinned packages, FTS5 in Python's sqlite3, curl, and disk for
the downloads and everything built from them. Optional: jev, which two steps ask; without it
the inventories build with --without-jev and the parallel corpus takes the shared verdicts.
Also says what is already built.
"""
from __future__ import annotations

import re
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN_PYTHON = (3, 12)  # CI's Python; this repository is also developed on 3.14
# Disk used by a complete build, measured 2026-10-05: corpus/ 56 GB (21 GB of it downloads),
# inventories/data 1.4 GB, parallel_corpus/data 9.2 GB: 67 GB. The most it needs at once is more,
# while layer 3 builds: its per-dictionary shards (22 GB) sit beside the new resources.db (24 GB)
# until the merge ends, on top of the 32 GB of corpus/ already built: 78 GB.
FULL_BUILD_GB = 78
BUILT_DIRS = ("corpus", "inventories/data", "parallel_corpus/data")


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


def python_version(version: tuple[int, ...] = tuple(sys.version_info[:3])) -> Check:
    shown = ".".join(map(str, version))
    need = ".".join(map(str, MIN_PYTHON))
    return Check("python", tuple(version[:2]) >= MIN_PYTHON,
                 shown if tuple(version[:2]) >= MIN_PYTHON else f"{shown}; needs {need} or newer")


def pinned_packages(requirements: Path = ROOT / "requirements-dev.txt", version=metadata.version) -> Check:
    wrong = []
    for line in requirements.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if " @ " in line:  # a direct URL: the version is the wheel's (name-1.2.3-py3-none-any.whl)
            name, _, url = line.partition(" @ ")
            pinned = m.group(1) if (m := re.search(r"-(\d+(?:\.\d+)+)-py3", url)) else ""
        else:
            name, _, pinned = line.partition("==")
        name = name.strip()
        try:
            found = version(name)
        except metadata.PackageNotFoundError:
            wrong.append(f"{name} missing")
            continue
        if pinned and found != pinned:
            wrong.append(f"{name} {found}, pinned {pinned}")
    fix = (f"{'; '.join(wrong)}. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt, "
           "then use .venv/bin/python")
    return Check("packages", not wrong, "all pinned versions installed" if not wrong else fix)


def fts5(connect=sqlite3.connect) -> Check:
    con = connect(":memory:")
    try:
        con.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        return Check("fts5", True, f"available (SQLite {sqlite3.sqlite_version})")
    except sqlite3.OperationalError:
        return Check("fts5", False, f"Python's SQLite {sqlite3.sqlite_version} has no FTS5: use a Python built with it "
                                    "(python.org and Homebrew builds have it)")
    finally:
        con.close()


def curl(which=shutil.which) -> Check:
    found = which("curl")
    return Check("curl", found is not None, found or "not found: install curl (the downloads use it)")


def used_gb(root: Path = ROOT) -> float:
    total = 0
    for d in BUILT_DIRS:
        base = root / d
        if base.exists():
            total += sum(f.stat().st_size for f in base.rglob("*") if f.is_file())
    return total / 1e9


def disk(free_gb: float, used: float) -> Check:
    need = max(0.0, FULL_BUILD_GB - used)
    return Check("disk", free_gb >= need,
                 f"{free_gb:.0f} GB free; a full build needs about {need:.0f} GB more "
                 f"({FULL_BUILD_GB} GB at its peak, {used:.0f} GB already here)")


def jev(which=shutil.which) -> Check:
    found = which("jev")
    detail = (found if found else
              "not installed: build the inventories with --without-jev (stress contrasts tagged 'uncertain'); "
              "the parallel corpus uses the shared verdicts, and leaves out any dictionary whose pairs differ")
    return Check("jev", found is not None, detail, required=False)


def built(root: Path = ROOT) -> list[str]:
    from build_structured import STRUCTURED
    items = [("unified dictionary (layer 1)", root / "corpus" / "unified.db"),
             ("parsed dictionaries (layer 2)", STRUCTURED),
             ("resources (layer 3)", root / "corpus" / "resources.db"),
             ("inventories", root / "inventories" / "data" / "confusables.db"),
             ("parallel corpus", root / "parallel_corpus" / "data" / "parallel.db")]
    return [f"{'built  ' if path.exists() else 'not yet'}  {name}" for name, path in items]


def main() -> int:
    sys.path.insert(0, str(ROOT / "scripts"))
    checks = [python_version(), pinned_packages(), fts5(), curl(),
              disk(shutil.disk_usage(ROOT).free / 1e9, used_gb()), jev()]
    for c in checks:
        mark = "ok  " if c.ok else ("FAIL" if c.required else "note")
        print(f"{mark}  {c.name:9} {c.detail}")
    print()
    for line in built():
        print(line)
    failed = [c.name for c in checks if c.required and not c.ok]
    print(f"\n{'ready' if not failed else 'not ready: fix ' + ', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
