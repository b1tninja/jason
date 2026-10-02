"""A packet: several documents delivered to members as one PDF, in order, each part found fresh for the year it is built.

The annual budget report and annual policy statement are the model (Civil Code 5300, 5310, 5320): a cover, the two
reports, and enclosures that live elsewhere (the pro forma budget, the reserve study summary and its 5570 form, the
insurance summary, the FHA and VA sheets, the collection policy, the fine schedule). A ``Packet`` is the order and what
each ``Part`` is; a ``PartSource`` says where this year's copy is found, never which file it is, so the same packet
builds next year from next year's files:

- ``TEMPLATE``: a Google Doc with ``{TOKENS}`` (``ref`` is the Doc id), copied and filled for the year;
- ``LIBRARY``: the newest PayHOA library file whose path matches ``pattern`` (``{year}`` is filled in), or of ``kind``;
- ``DRIVE``: the newest Drive file whose path matches ``pattern``;
- ``GENERATED``: a page jason writes from its own records (``ref`` names the generator);
- ``ADDENDUM``: pages added for some recipients only.

A packet with ``variants`` (the buildings) is built once per variant; a part naming ``{building}`` (a building's flood
policy) differs between them, and the rest are the same in every one.

``required`` marks a part the law or the governing documents require; ``authority`` cites it for the reader, and the
manager's review (``jason review annual-disclosures``) checks the assembled text against the law on hand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SourceKind(Enum):
    TEMPLATE = "template"
    LIBRARY = "library"
    DRIVE = "drive"
    GENERATED = "generated"
    ADDENDUM = "addendum"


@dataclass(frozen=True)
class PartSource:
    kind: SourceKind
    ref: str = ""                    # a Doc id (TEMPLATE) or a generator's name (GENERATED)
    pattern: str = ""                # a regex on the library or Drive path; "{year}" becomes the packet's year
    pages: str = ""                  # "1-3" or "1,4-5": the pages of the found file to include; empty is all
    markdown: str = ""               # a TEMPLATE's text: a file in mystique/packet_templates, or "form:<key>" for a form
    # Pages chosen by what they say, for a found file whose page numbers vary (an insurer's packet around its
    # declarations): ``keep`` keeps only the pages whose text matches, ``drop`` leaves out those whose text matches.
    keep: str = ""
    drop: str = ""


@dataclass(frozen=True)
class Part:
    title: str
    source: PartSource
    authority: str = ""
    required: bool = True
    note: str = ""
    # The law wants it "on a separate piece of paper" (the FHA and VA statements, 5300(b)(10), (11)): printed on both
    # sides, it starts on a front page and its last page's back is left blank.
    own_sheet: bool = False


@dataclass(frozen=True)
class Packet:
    key: str
    title: str
    parts: tuple[Part, ...]
    task: str = ""                   # the manager's review task slug that checks it
    note: str = ""
    values: tuple[tuple[str, str], ...] = field(default_factory=tuple)   # standing token values (the designated recipient)
    # One PDF per variant when the packet differs by building: "{building}" in a part's title, pattern, or ref is the
    # variant, and the token BUILDING is set to it.
    variants: tuple[str, ...] = ()


def page_list(spec: str, count: int) -> list[int]:
    """Zero-based page numbers for "1-3,5" against a file of ``count`` pages; empty means every page."""
    if not spec.strip():
        return list(range(count))
    out: list[int] = []
    for piece in spec.split(","):
        a, _, b = piece.strip().partition("-")
        first, last = int(a), int(b or a)
        out += [p - 1 for p in range(first, last + 1) if 1 <= p <= count]
    return out


def page_spec(numbers: list[int]) -> str:
    """Zero-based page numbers as "1-3,5"."""
    runs: list[list[int]] = []
    for n in sorted(set(numbers)):
        if runs and n == runs[-1][1] + 1:
            runs[-1][1] = n
        else:
            runs.append([n, n])
    return ",".join(f"{a + 1}" if a == b else f"{a + 1}-{b + 1}" for a, b in runs)


def chosen_pages(texts: list[str], source: PartSource) -> tuple[str, str]:
    """The pages of a found file to print, from its ``pages`` and its ``keep`` and ``drop`` rules, as "1-3,5" (empty
    for all), and a note when a rule chose nothing (then every listed page is kept: a rule never empties a part)."""
    import re

    listed = page_list(source.pages, len(texts))
    picked = [n for n in listed if (not source.keep or re.search(source.keep, texts[n]))
              and not (source.drop and re.search(source.drop, texts[n]))]
    if not picked:
        return source.pages, "no page matched the part's page rules; every page kept"
    return ("" if picked == list(range(len(texts))) else page_spec(picked)), ""


__all__ = ["Packet", "Part", "PartSource", "SourceKind", "chosen_pages", "page_list", "page_spec"]
