"""LZO1X decompression in pure Python (the format of LZO-compressed MDict blocks).

mdict-utils ships a pure-Python LZO decoder that produces corrupt output: on real
MDict 1.2 blocks its result fails the block's own Adler-32 checksum (for example
21世纪英汉汉英双向词典, every block tested). This is a direct transcription of the
reference decompressor (minilzo, lzo1x_d.ch), with bounds checks, so malformed input
raises LZOError instead of reading out of range.
"""
from __future__ import annotations

M2_MAX_OFFSET = 0x0800


class LZOError(ValueError):
    pass


def decompress(src: bytes | bytearray) -> bytes:
    """Decompress a raw LZO1X stream (no length header), which must end exactly at its end-of-stream marker."""
    src = bytes(src)
    n = len(src)
    out = bytearray()
    ip = 0

    def byte() -> int:
        nonlocal ip
        if ip >= n:
            raise LZOError("input overrun")
        value = src[ip]
        ip += 1
        return value

    def literals(count: int) -> None:
        nonlocal ip
        if ip + count > n:
            raise LZOError("input overrun in literal run")
        out.extend(src[ip:ip + count])
        ip += count

    def copy(distance: int, count: int) -> None:
        start = len(out) - distance
        if start < 0:
            raise LZOError("lookbehind overrun")
        if distance >= count:
            out.extend(out[start:start + count])
        else:  # overlapping copy: repeats the last `distance` bytes
            for i in range(count):
                out.append(out[start + i])

    def run_length(t: int, base: int) -> int:
        while True:
            b = byte()
            if b:
                return t + base + b
            t += 255

    t = src[0] if n else 0
    state = "loop"
    if t > 17:
        ip = 1
        t -= 17
        if t < 4:
            state = "match_next"
        else:
            literals(t)
            state = "first_literal_run"

    while True:
        if state == "loop":
            t = byte()
            if t >= 16:
                state = "match"
            else:
                if t == 0:
                    t = run_length(0, 15)
                literals(t + 3)
                state = "first_literal_run"
            continue

        if state == "first_literal_run":
            t = byte()
            if t >= 16:
                state = "match"
                continue
            distance = 1 + M2_MAX_OFFSET + (t >> 2) + (byte() << 2)
            copy(distance, 3)
            state = "match_done"
            continue

        if state == "match":
            if t >= 64:                       # M2: 3..8 bytes, distance up to 2 KiB
                distance = 1 + ((t >> 2) & 7) + (byte() << 3)
                count = (t >> 5) - 1 + 2
            elif t >= 32:                     # M3: distance up to 16 KiB
                t &= 31
                if t == 0:
                    t = run_length(0, 31)
                lo, hi = byte(), byte()
                distance = 1 + (lo >> 2) + (hi << 6)
                count = t + 2
            elif t >= 16:                     # M4: distance up to 48 KiB, or end of stream
                high = (t & 8) << 11
                t &= 7
                if t == 0:
                    t = run_length(0, 7)
                lo, hi = byte(), byte()
                distance = high + (lo >> 2) + (hi << 6)
                if distance == 0:             # end-of-stream marker
                    if ip != n:               # liblzo2: LZO_E_INPUT_NOT_CONSUMED
                        raise LZOError(f"{n - ip} bytes after the end-of-stream marker")
                    return bytes(out)
                distance += 0x4000
                count = t + 2
            else:                             # M1: 2 bytes, near
                distance = 1 + (t >> 2) + (byte() << 2)
                count = 2
            copy(distance, count)
            state = "match_done"
            continue

        if state == "match_done":
            t = src[ip - 2] & 3
            if t == 0:
                state = "loop"
                continue
            state = "match_next"
            continue

        if state == "match_next":
            literals(t)
            t = byte()
            state = "match"
            continue
