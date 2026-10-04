"""Byte sources for the .mdx readers: read(start, length), `fetched` and `size`.

HttpRange reads byte ranges of a remote file and refuses anything but the range it asked for
(a 200 would be the whole file; a 206 must say, in Content-Range and Content-Length, that it
is the requested range, and its body must be exactly that long). BytesSource is the same
interface over bytes in memory, for tests and local files.
"""
from __future__ import annotations

import http.client
import re
import time
import urllib.error
import urllib.request

from parallel.mdxformat import ProbeError

USER_AGENT = "Mozilla/5.0 (dictionary index probe)"

_CONTENT_RANGE = re.compile(r"bytes (\d+)-(\d+)/(\d+|\*)")


def _answered_range(header: str, start: int, length: int, byte_range: str) -> tuple[int, int | None]:
    """(bytes promised, file length or None) of a 206 answering a request for `length` bytes
    from `start`; ProbeError unless the answer is that range. Content-Range "bytes S-E/T" must
    be self-consistent (S <= E < T) and be the range asked for: S is its first byte, E is no
    further than its last, and E falls short of it only at the end of the file (E = T-1), which
    an unknown length ("*") cannot show."""
    m = _CONTENT_RANGE.fullmatch(header.strip())
    if not m:
        raise ProbeError(f"server answered {byte_range} with Content-Range {header!r}")
    first, last = int(m[1]), int(m[2])
    total = None if m[3] == "*" else int(m[3])
    consistent = first <= last and (total is None or last < total)
    asked = first == start and last <= start + length - 1
    whole = last == start + length - 1 or total is not None and last == total - 1
    if not (consistent and asked and whole):
        raise ProbeError(f"server answered {byte_range} with Content-Range {header!r}")
    return last - first + 1, total


class HttpRange:
    """Reads byte ranges of a remote file. Refuses to silently download a whole file."""

    def __init__(self, url: str, timeout: int = 60):
        self.url, self.timeout, self.fetched = url, timeout, 0
        self.size: int | None = None  # the file's length, from Content-Range, once known

    def read(self, start: int, length: int) -> bytes:
        try:
            return self._read(start, f"bytes={start}-{start + length - 1}", length)
        except urllib.error.HTTPError as e:
            e.close()  # an HTTPError holds the open response
            if e.code != 416:
                raise
            # 416: the range runs past the end of a file smaller than the request (a tiny
            # dictionary). An open-ended range returns whatever remains.
            return self._read(start, f"bytes={start}-", length)

    def _read(self, start: int, byte_range: str, length: int) -> bytes:
        req = urllib.request.Request(self.url, headers={"Range": byte_range, "User-Agent": USER_AGENT})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    if resp.status != 206:  # a 200 would be the whole file
                        raise ProbeError(f"server ignored the range request (HTTP {resp.status})")
                    header = resp.headers.get("Content-Range", "")
                    promised, total = _answered_range(header, start, length, byte_range)
                    declared = resp.headers.get("Content-Length")
                    if declared is not None and declared.strip() != str(promised):
                        raise ProbeError(f"Content-Length {declared!r}, Content-Range {header!r} promises {promised}")
                    if total is not None:
                        self.size = total
                    try:
                        data = resp.read(promised + 1)  # one more: a body longer than its range is an error too
                    except http.client.IncompleteRead as e:  # shorter than its Content-Length
                        data = e.partial
                    if len(data) != promised:
                        raise ProbeError(f"{'more than ' if len(data) > promised else ''}{min(len(data), promised)} "
                                         f"bytes in the body, Content-Range {header!r} promised {promised}")
                    self.fetched += len(data)
                    return data
            except urllib.error.HTTPError:
                raise  # an HTTP status is an answer, not a transient failure
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
        raise AssertionError("unreachable")


class BytesSource:
    """The same interface over bytes in memory (tests, local files)."""

    def __init__(self, data: bytes):
        self.data, self.fetched = data, 0
        self.size = len(data)

    def read(self, start: int, length: int) -> bytes:
        chunk = self.data[start:start + length]
        self.fetched += len(chunk)
        return chunk
