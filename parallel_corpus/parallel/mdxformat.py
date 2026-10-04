"""The MDict .mdx file format, read through any byte source with read(start, length).

The header and its tags, the layout that locates the record section past the key section,
the index of compressed record blocks, and the decoding of one record block verified by the
checksum it carries. Shared by the range probe (parallel/probe.py), which reads remote files
in pieces, and the local reader (parallel/mdx.py); ProbeError is what both raise when a file
cannot be read this way.
"""
from __future__ import annotations

import re
import struct
import zlib
from dataclasses import dataclass

import lzo1x  # correct LZO1X; mdict-utils' decoder corrupts blocks

HEAD_BYTES = 1 << 16          # first fetch: header + key-section header, almost always enough


class ProbeError(Exception):
    """The file cannot be sampled (unsupported version, encryption, server refusing ranges)."""


@dataclass
class Layout:
    version: float
    encoding: str
    encrypted: int
    record_offset: int  # start of the record section


def _header(src) -> tuple[dict[str, str], int]:
    head = src.read(0, HEAD_BYTES)
    (size,) = struct.unpack(">I", head[:4])
    if 4 + size + 4 > len(head):
        head = src.read(0, 4 + size + 4 + 64)
    raw = head[4:4 + size]
    if len(head) < 4 + size + 4:
        raise ProbeError(f"truncated: the header needs {4 + size + 4} bytes, the file has {len(head)}")
    (checksum,) = struct.unpack("<I", head[4 + size:4 + size + 4])
    if zlib.adler32(raw) & 0xFFFFFFFF != checksum:  # what mdict-utils asserts; corrupt sizes would follow
        raise ProbeError("header checksum mismatch")
    text = raw[:-2].decode("utf-16-le", "replace") if raw[-2:] == b"\x00\x00" else raw.decode("utf-8", "replace")
    tags = dict(re.findall(r'(\w+)="((?:.|\n)*?)"', text))
    return tags, 4 + size + 4


def layout(src) -> Layout:
    tags, key_offset = _header(src)
    version = float(tags.get("GeneratedByEngineVersion", "2.0") or "2.0")
    if version >= 3:
        raise ProbeError("MDict 3 format not supported by the probe")
    enc_attr = tags.get("Encrypted", "No")
    encrypted = 0 if enc_attr in ("No", "") else 1 if enc_attr == "Yes" else int(enc_attr)
    if encrypted & 1:
        raise ProbeError("key section is encrypted (needs a registration code)")
    encoding = tags.get("Encoding", "UTF-8") or "UTF-8"
    encoding = {"GBK": "GB18030", "GB2312": "GB18030", "UTF-16": "UTF-16LE"}.get(encoding.upper(), encoding)
    width = 8 if version >= 2.0 else 4
    fmt = ">Q" if width == 8 else ">I"
    count = 5 if version >= 2.0 else 4
    block = src.read(key_offset, count * width + (4 if version >= 2.0 else 0))
    nums = [struct.unpack(fmt, block[i * width:(i + 1) * width])[0] for i in range(count)]
    key_block_info_size, key_block_size = nums[-2], nums[-1]
    header_len = count * width + (4 if version >= 2.0 else 0)
    return Layout(version, encoding, encrypted, key_offset + header_len + key_block_info_size + key_block_size)


def record_blocks(src, lay: Layout) -> list[tuple[int, int, int]]:
    """(file offset, compressed size, decompressed size) of every record block."""
    width = 8 if lay.version >= 2.0 else 4
    fmt = ">Q" if width == 8 else ">I"
    head = src.read(lay.record_offset, 4 * width)
    n_blocks, _entries, info_size, _blocks_size = (struct.unpack(fmt, head[i * width:(i + 1) * width])[0] for i in range(4))
    info = src.read(lay.record_offset + 4 * width, info_size)
    pairs = [struct.unpack(fmt + fmt[1:], info[i * 2 * width:(i + 1) * 2 * width]) for i in range(n_blocks)]
    offset = lay.record_offset + 4 * width + info_size
    out = []
    for comp, decomp in pairs:
        out.append((offset, comp, decomp))
        offset += comp
    return out


def decode_block(block: bytes, decompressed_size: int) -> bytes:
    """Decompress one record block and verify it against the Adler-32 checksum it carries.

    The check matters: mdict-utils' LZO decoder returns corrupt bytes without complaint, and
    a probe scanning garbage would report "no examples" for a rich dictionary.
    """
    (info,) = struct.unpack("<L", block[:4])
    method, encryption = info & 0xF, (info >> 4) & 0xF
    if encryption:
        raise ProbeError("record blocks are encrypted")
    (checksum,) = struct.unpack(">I", block[4:8])
    data = block[8:]
    if method == 0:
        out = data
    elif method == 2:
        out = zlib.decompress(data)
    elif method == 1:
        try:
            out = lzo1x.decompress(data)
        except lzo1x.LZOError as e:
            raise ProbeError(f"LZO block does not decode: {e}") from e
    else:
        raise ProbeError(f"unknown compression method {method}")
    if zlib.adler32(out) & 0xFFFFFFFF != checksum:
        raise ProbeError(f"block checksum mismatch (compression method {method})")
    if len(out) != decompressed_size:
        raise ProbeError(f"block size {len(out)} differs from the index ({decompressed_size})")
    return out
