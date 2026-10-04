"""Directory-listing parsing, retries and output writing of the crawler (no network)."""
import http.client
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import crawl_index

ROOT = crawl_index.ROOT


def listing(*lines: str) -> str:
    return "<html><body><pre>" + "\n".join(lines) + "\n</pre></body></html>"


PARENT = '<a href="../">../</a>'
FILE = '<a href="A.mdx">A.mdx</a>                 01-Jan-2024 00:00               123'
DIR = '<a href="sub/">sub/</a>                   01-Jan-2024 00:00                 -'


class ListDir(unittest.TestCase):
    def list_dir(self, html):
        with mock.patch.object(crawl_index, "fetch", return_value=html):
            return crawl_index.list_dir(ROOT)

    def test_files_and_dirs_are_parsed(self):
        dirs, files = self.list_dir(listing(PARENT, DIR, FILE))
        self.assertEqual(dirs, [ROOT + "sub/"])
        self.assertEqual(files, [{"path": "A.mdx", "size": 123, "date": "01-Jan-2024 00:00"}])

    def test_indented_entries_are_parsed(self):
        _, files = self.list_dir(listing(PARENT, "  " + FILE))
        self.assertEqual([f["path"] for f in files], ["A.mdx"])

    def test_an_entry_that_does_not_parse_fails_loud_wherever_it_sits(self):
        # A link the entry pattern does not understand is never silently dropped.
        for odd in ['<a href="B.mdx">B.mdx</a> yesterday 5', 'x <a href="C.mdx">C</a>', '\t<a  href="D.mdx">D</a>']:
            with self.assertRaises(ValueError, msg=odd):
                self.list_dir(listing(PARENT, FILE, odd))

    def test_links_are_read_as_html_not_by_pattern(self):
        # Any attribute order, quoting or content: ">" inside an attribute value ends nothing.
        for link in ['<a title="download > file" href="A.mdx">A.mdx</a>', "<a href='A.mdx' class=f>A.mdx</a>",
                     '<A HREF="A.mdx">A.mdx</A>']:
            _, files = self.list_dir(listing(PARENT, link + "   01-Jan-2024 00:00   123"))
            self.assertEqual(files, [{"path": "A.mdx", "size": 123, "date": "01-Jan-2024 00:00"}], link)

    def test_a_listing_without_links_fails_loud(self):
        for body in ["Forbidden", "", "   \n  "]:
            with self.assertRaises(ValueError, msg=repr(body)):
                self.list_dir(listing(body))

    def test_text_outside_an_entry_fails_loud(self):
        for odd in ["stray text", '<b>A.mdx</b>  01-Jan-2024 00:00  1', FILE + " " + FILE, '<a href="B.mdx"']:
            with self.assertRaises(ValueError, msg=odd):
                self.list_dir(listing(PARENT, odd))

    def test_a_truncated_listing_fails_loud(self):
        with self.assertRaises(ValueError):
            self.list_dir("<html><body><pre>" + FILE)


class Fetch(unittest.TestCase):
    def test_truncated_responses_are_retried(self):
        body = mock.MagicMock()
        body.__enter__.return_value.read.return_value = b"ok"
        calls = [http.client.IncompleteRead(b"par"), body]
        with mock.patch.object(crawl_index.urllib.request, "urlopen", side_effect=calls), \
             mock.patch.object(crawl_index.time, "sleep"):
            self.assertEqual(crawl_index.fetch(ROOT), "ok")


class Main(unittest.TestCase):
    def test_output_is_written_through_a_private_temporary_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "index.jsonl"
            # A file at the old fixed temporary name (another crawl's) must be left alone.
            other = Path(str(out) + ".tmp")
            other.write_text("another crawl\n")
            with mock.patch.object(crawl_index, "list_dir", return_value=([], [{"path": "A.mdx", "size": 1, "date": "d"}])):
                crawl_index.main(str(out))
            self.assertEqual([json.loads(line)["path"] for line in out.read_text().splitlines()], ["A.mdx"])
            self.assertEqual(other.read_text(), "another crawl\n")
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["index.jsonl", "index.jsonl.tmp"])
            self.assertEqual(out.stat().st_mode & 0o044, 0o044)  # not mkstemp's private 0600


if __name__ == "__main__":
    unittest.main()
