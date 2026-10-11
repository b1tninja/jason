"""A made-up association for the suggestion reader's CLI and web tests: an "Example Bylaws" outline on disk and a stub
community. Nothing here is an association's."""

from __future__ import annotations

import json
from pathlib import Path

from controls_support import FULL
from jason.community.outlines import DocumentOutline, Section

PAYMENT = "9.1 Checks. All checks, drafts, or orders for payment shall be signed by two directors."
RESERVE = "9.2 Reserve. Money may be withdrawn from the reserve only upon the signatures of two directors."
CONTRACT = "9.3 Contracts. No officer may bind the Association to a contract unless authorized by resolution of the Board."
QUESTION = ("9.4 Drafts. Drafts on the Association are kept by the treasurer. Signatures. A document so issued shall be "
            "signed by the person the Board names.")
UNRELATED = "9.5 Meetings. The members shall meet once a year at a place the Board names in its notice."
SECTIONS = (("9.1", "Checks", PAYMENT), ("9.2", "Reserve", RESERVE), ("9.3", "Contracts", CONTRACT),
            ("9.4", "Drafts", QUESTION), ("9.5", "Meetings", UNRELATED))


class Home:
    """The stub community: the controls the profile keeps (none), a roster, and whether the duties were confirmed."""

    name = "Example HOA"

    def __init__(self, roster=FULL, duties: bool = False):
        self._roster, self._duties = tuple(roster), duties

    def controls(self):
        return ()

    def officers(self):
        return self._roster

    def duties_read(self):
        return self._duties

    def living_documents(self):
        return ()

    def citable_documents(self):
        return ()

    def book_entries(self):
        return ()


def write_outline(root: Path, sections=SECTIONS, key: str = "example-bylaws", title: str = "Example Bylaws") -> Path:
    """``outlines/<key>.json`` under ``root``: one top-level section for each (number, heading, text)."""
    text, made = "", []
    for number, heading, words in sections:
        start = len(text)
        text += words + "\n"
        made.append(Section(number, heading, 1, start, len(text), label=number))
    outline = DocumentOutline(key, title, text=text, sections=made, kind="bylaws", aliases=[title])
    folder = Path(root) / "outlines"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{key}.json"
    path.write_text(json.dumps(outline.to_dict()), encoding="utf-8")
    return path
