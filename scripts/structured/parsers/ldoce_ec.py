"""Longman Dictionary of Contemporary English, 6th edition, English-Chinese (朗文当代高级英语辞典 英英·英汉双解).

Same markup as LDOCE6 (see ldoce.py, whose parser this module reuses) plus Chinese:
  def > en + tran                     -> definition / definition_zh
  example > exaen + example           -> text / text_zh (an example without exaen is English only)
  signpost > signen + sign            (signposts are not extracted)
Popups are inlined, not separate records: span.popup-button followed by div.at-link.
  div.at-link with span.popetym       -> etymology
  div.at-link with div.verbtable      -> forms
  div.at-link with span.popexa        -> the example bank: one unnumbered, definition-less Sense
                                         appended after the senses of the homograph that owns it
  thesaurus, collocations, phrases (corpus examples), entry menu, word family, word sets
                                      -> stay in layer 1
One record holds every homograph of a word, as in LDOCE6.

Stubs: as in LDOCE6, a record whose only content is span.crossref is "xref"; there are no
popup records (the popups are inlined). Example.labels and Pron.note as in LDOCE6.
"""
from __future__ import annotations

from structured.model import Entry
from structured.parsers import ldoce

KEY = "ldoce-ec"
COVERS = "definitions"
MIN_COVERAGE = 0.99


def parse(headword: str, html: str) -> Entry:
    return ldoce.parse(headword, html)
