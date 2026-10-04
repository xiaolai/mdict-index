"""Parser registry: one module per dictionary, discovered by file name.

Each module defines:
    KEY: str             the dictionary key in data/recommended.json ("oald")
    COVERS: str          what an entry must yield to count as parsed (model.COVERAGE_KINDS)
    MIN_COVERAGE: float  share of content records (stubs excluded) that must be covered; the build
                         fails below it. Policy: min(0.99, measured coverage rounded down to 2
                         decimals), so corpus drift is absorbed while a real regression still fails;
                         a lower value is justified with counts in the parser's docstring.
    def parse(headword: str, html: str) -> model.Entry   must never raise
Optionally:
    PRINTED_MARKUP: frozenset[str]  headwords whose printed text legitimately contains an
                                    HTML tag (text *about* HTML); only the leftover-tag
                                    check is skipped for them. Keep it tiny and commented.
Modules are discovered, not listed, so parsers can be added independently.
"""
from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType

from structured.model import COVERAGE_KINDS


def _checked(module_name: str) -> ModuleType:
    module = importlib.import_module(f"{__name__}.{module_name}")
    for attr in ("KEY", "COVERS", "MIN_COVERAGE", "parse"):
        if not hasattr(module, attr):
            raise AttributeError(f"parser {module_name} lacks {attr}")
    if module.COVERS not in COVERAGE_KINDS:
        raise ValueError(f"parser {module_name}: COVERS {module.COVERS!r}")
    return module


def load(key: str) -> ModuleType:
    """One parser by dictionary key, without importing the others (a broken
    parser elsewhere must not stop work on this one)."""
    module = _checked(key.replace("-", "_"))
    if module.KEY != key:
        raise ValueError(f"module for {key!r} declares KEY {module.KEY!r}")
    return module


def registry() -> dict[str, ModuleType]:
    """Every parser. Any broken parser fails this: the build must not skip one silently."""
    out: dict[str, ModuleType] = {}
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        module = _checked(info.name)
        if module.KEY in out:
            raise ValueError(f"two parsers for {module.KEY}")
        out[module.KEY] = module
    return out
