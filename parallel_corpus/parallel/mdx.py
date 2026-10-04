"""Read every record of a local .mdx file.

mdict-utils' reader handles the key index (including encrypted ones); for LZO-compressed
blocks it imports the optional python-lzo package, which is not installed, so this module
puts the verified pure-Python decoder (scripts/lzo1x.py) in its place. The reader checks each
block's Adler-32 against the decompressed data, so a wrong decompression fails loudly.

The reader decodes records with errors='ignore': bytes invalid in the declared encoding are
dropped. That cannot be repaired here; it only affects already-corrupt source text.

Some files have a key index mdict-utils cannot open (an encryption variant it does not
support, or a key block failing its checksum). The records do not depend on it: then they are
read straight from the record blocks, each verified by its own checksum (parallel/mdxformat.py),
and split at their NUL terminators, without headwords. A bad record block, or a header failing
its checksum, still fails.
"""
from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import lzo1x
import mdict_utils.base.readmdict as readmdict


class _LZO:
    @staticmethod
    def decompress(data: bytes) -> bytes:
        # the reader prepends python-lzo's header: 0xF0 and the 4-byte big-endian output size
        return lzo1x.decompress(data[5:])


readmdict.lzo = _LZO


def records(path: Path) -> Iterator[tuple[str, str]]:
    """(headword, record markup) for every record, in file order; headword "" if the key index is unreadable."""
    from parallel.mdxformat import _header
    _header(_File(path))  # a corrupt header fails here: only the key index may be bypassed below
    try:
        mdx = readmdict.MDX(str(path))
    except AssertionError as e:
        print(f"{path.name}: key index unreadable ({e!r}); reading record blocks without headwords",
              file=sys.stderr, flush=True)
        yield from _records_without_keys(path)
        return
    for key, value in mdx.items():
        yield key.decode("utf-8", "replace"), value.decode("utf-8", "replace")


class _File:
    """Byte ranges of a local file, for parallel/mdxformat.py's readers."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def read(self, start: int, length: int) -> bytes:
        with self.path.open("rb") as f:
            f.seek(start)
            return f.read(length)


def _records_without_keys(path: Path) -> Iterator[tuple[str, str]]:
    """Records split at their terminators across the whole record stream: a record (and a
    character in it) may continue into the next block, so only complete records are decoded."""
    from parallel.mdxformat import decode_block, layout, record_blocks
    from parallel.ranges import BytesSource
    data = path.read_bytes()
    src = BytesSource(data)  # layout() verifies the header's checksum
    lay = layout(src)
    nul = "\x00".encode(lay.encoding)  # two bytes in UTF-16
    pending = b""
    for offset, compressed, decompressed in record_blocks(src, lay):
        *complete, pending = _split(pending + decode_block(data[offset:offset + compressed], decompressed), nul)
        for raw in complete:
            yield from _record(raw, lay.encoding)
    yield from _record(pending, lay.encoding)


def _split(data: bytes, nul: bytes) -> list[bytes]:
    """data split at nul, found only at character boundaries (a multiple of its width from a record's start)."""
    parts, start, i = [], 0, 0
    while (i := data.find(nul, i)) != -1:
        if (i - start) % len(nul):
            i += 1
            continue
        parts.append(data[start:i])
        start = i = i + len(nul)
    parts.append(data[start:])
    return parts


def _record(raw: bytes, encoding: str) -> Iterator[tuple[str, str]]:
    record = raw.decode(encoding, "replace").strip()
    if record:
        yield "", record
