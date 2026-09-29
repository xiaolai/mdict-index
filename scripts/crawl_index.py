"""Crawl the freemdict nginx autoindex and write every file entry as JSONL.

Only directory listings are fetched; no dictionary files are downloaded.
Output is sorted by path (stable diffs between crawls) and written atomically:
a failed crawl exits non-zero and leaves the previous index untouched.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = "https://downloads.freemdict.com/"
ENTRY = re.compile(
    r'^<a href="([^"]+)">[^<]*</a>[ \t]+(\d{2}-\w{3}-\d{4} \d{2}:\d{2})[ \t]+(-|\d+)[ \t]*\r?$',
    re.M,
)
LINK = re.compile(r'^<a href="(?!\.\./)', re.M)


def fetch(url: str, attempts: int = 4) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for i in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except OSError:
            if i == attempts - 1:
                raise
            time.sleep(2 ** i)
    raise AssertionError("unreachable")


def list_dir(url: str):
    html = fetch(url)
    listing = html.split("<pre>", 1)[1].split("</pre>", 1)[0]
    entries = ENTRY.findall(listing)
    # Every non-parent link must parse; a mismatch means entries are being dropped.
    links = len(LINK.findall(listing))
    if len(entries) != links:
        raise ValueError(f"parsed {len(entries)} of {links} entries")
    dirs, files = [], []
    for href, date, size in entries:
        if href.startswith("../") or href.startswith("?"):
            continue
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
    tmp = out_path + ".tmp"
    with open(tmp, "w") as out:
        for f in entries:
            out.write(json.dumps(f, ensure_ascii=False) + "\n")
    os.replace(tmp, out_path)


if __name__ == "__main__":
    main(sys.argv[1])
