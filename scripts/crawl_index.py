"""Crawl the freemdict nginx autoindex and write every file entry as JSONL.

Only directory listings are fetched; no dictionary files are downloaded.
Output is sorted by path (stable diffs between crawls) and written atomically:
a failed crawl exits non-zero and leaves the previous index untouched.
"""
import http.client
import json
import os
import re
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

ROOT = "https://downloads.freemdict.com/"
# What follows an entry's link on its line: "  01-Jan-2024 00:00   123" ("-" for a folder).
TAIL = re.compile(r"[ \t]+(\d{2}-\w{3}-\d{4} \d{2}:\d{2})[ \t]+(-|\d+)[ \t]*\r?")
_UMASK = os.umask(0o022)
os.umask(_UMASK)  # read the process umask (os.umask is the only way)


def fetch(url: str, attempts: int = 4) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for i in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        # HTTPException covers a body cut short (IncompleteRead), which is not an OSError.
        except (OSError, http.client.HTTPException):
            if i == attempts - 1:
                raise
            time.sleep(2 ** i)
    raise AssertionError("unreachable")


class _Listing(HTMLParser):
    """The lines of an nginx autoindex <pre>: `[href, text after the link]`
    per line, href None on a line without a link. Anything that is not text
    or one link per line raises: a listing is never partly understood."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines: list[list] = [[None, ""]]
        self.in_link = False

    def handle_starttag(self, tag, attrs):
        line = self.lines[-1]
        if tag != "a" or self.in_link:
            raise ValueError(f"unexpected <{tag}> in the listing")
        if line[0] is not None or line[1].strip():
            raise ValueError(f"more than a link on one line: {line[1]!r}")
        href = dict(attrs).get("href")
        if not href:
            raise ValueError("a link without href")
        line[0], line[1], self.in_link = href, "", True

    def handle_endtag(self, tag):
        if tag != "a" or not self.in_link:
            raise ValueError(f"unexpected </{tag}> in the listing")
        self.in_link = False

    def handle_data(self, data):
        if self.in_link:
            return  # the link text is the name cut to a width; the href is the name
        first, *rest = data.split("\n")
        self.lines[-1][1] += first
        self.lines.extend([None, part] for part in rest)


def list_dir(url: str):
    html = fetch(url)
    start, end = html.find("<pre>"), html.find("</pre>")
    if start < 0 or end < start:
        raise ValueError("no complete <pre> listing (truncated response?)")
    parser = _Listing()
    parser.feed(html[start + len("<pre>"):end])
    # An unfinished tag is held back unparsed, and close() would drop it.
    if "<" in parser.rawdata:
        raise ValueError(f"unfinished markup in the listing: {parser.rawdata[:80]!r}")
    parser.close()
    if parser.in_link:
        raise ValueError("unclosed link in the listing")
    # Every listing has at least the parent link; none at all is not a listing.
    if all(href is None for href, _ in parser.lines):
        raise ValueError("no links in the listing")
    dirs, files = [], []
    for href, tail in parser.lines:
        if href is None:
            if tail.strip():
                raise ValueError(f"text outside an entry: {tail!r}")
            continue
        if href.startswith("../") or href.startswith("?"):
            continue
        if not (m := TAIL.fullmatch(tail)):
            raise ValueError(f"entry {href!r} has no date and size: {tail!r}")
        date, size = m.groups()
        full = urllib.parse.urljoin(url, href)
        if href.endswith("/"):
            dirs.append(full)
        else:
            path = urllib.parse.unquote(full[len(ROOT):])
            files.append({"path": path, "size": int(size), "date": date})
    return dirs, files


def main(out_path: str) -> None:
    pending, seen, errors, entries = [ROOT], {ROOT}, [], []
    with ThreadPoolExecutor(8) as pool:
        while pending:
            batch, pending = pending, []
            for url, fut in [(u, pool.submit(list_dir, u)) for u in batch]:
                try:
                    dirs, files = fut.result()
                except Exception as e:  # record, never swallow
                    errors.append((url, repr(e)))
                    continue
                entries.extend(files)
                for d in dirs:
                    if d not in seen:
                        seen.add(d)
                        pending.append(d)
            print(f"dirs={len(seen)} files={len(entries)} errors={len(errors)}", file=sys.stderr)
    for url, e in errors:
        print("ERROR", url, e, file=sys.stderr)
    if errors:
        sys.exit(1)
    entries.sort(key=lambda f: f["path"])
    # A private temporary file: two crawls writing at once must not share one.
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(out_path)), prefix=".index-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as out:
            for f in entries:
                out.write(json.dumps(f, ensure_ascii=False) + "\n")
        os.chmod(tmp, 0o666 & ~_UMASK)  # mkstemp creates 0600; keep the usual file mode
        os.replace(tmp, out_path)
    except BaseException:
        os.unlink(tmp)
        raise


if __name__ == "__main__":
    main(sys.argv[1])
