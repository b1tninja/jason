"""Embedded references: a token a document carries in place of a copied passage of a governing document.

A notice, letter, or owner guide that copies a section of the declaration goes stale when an amendment changes the
section. It can carry a reference instead, filled from the document kept as amended (``jason.community.living``) each
time it is rendered:

- ``{QUOTE:ccrs#4.2(b)}``: the section's current words, with its citation, and who set them.
- ``{QUOTE:ccrs#4.2(b) as-of=2025-01-01}``: the words in force on a date.
- ``{CITE:ccrs#4.2(b)}``: the citation alone, as the document is cited ("CC&Rs Section 4.2(b)").

The target is written the way ``jason.community.references`` names a section of a known document (``key#number``),
and settings follow it as they do a ``{REPORT:key setting=value}``. The key is a document the profile keeps
(``Community.living_documents()``, else ``Community.citable_documents()``), so a bylaw or a rule works as a declaration
section does.

A reference never renders nothing. An unknown document, an unknown section, a section removed by an amendment, or a
date the record cannot answer raises ``SectionRefError`` with the reason, and the document is not rendered. Each
rendering returns an ``Embedded`` record per token: the section, the date asked, the instrument that set the words
and its date, and a digest of the words, so a person can see later what a sent document quoted and from what.

The words come from jason's consolidated text, which is not an official restatement: a quote says so, and says the
recorded instruments control. This module is pure: ``Resolver`` supplies the sections (``jason.tasks.section_refs``
reads them from disk).
"""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import asdict, dataclass
from datetime import date
from enum import Enum
from typing import Any, Protocol

from jason.community.outlines import normalize_number

TOKEN = re.compile(r"\{(?P<verb>QUOTE|CITE):(?P<key>[a-z0-9-]+)#(?P<section>[A-Za-z0-9.()\-]+?)"
                   r"(?P<args>(?:\s+[a-z][a-z-]*=[^\s{}]+)*)\s*\}")
SETTINGS = frozenset({"as-of"})

CAVEAT = ("Provisions are quoted from jason's copy of the governing documents, each kept as amended from the "
          "instruments' own words. It is not an official restatement; the recorded and adopted documents control.")


class Verb(Enum):
    QUOTE = "QUOTE"
    CITE = "CITE"


class SectionRefError(LookupError):
    """A reference that cannot be filled: the reason is the message. A document with one is not rendered."""


@dataclass(frozen=True)
class Ref:
    verb: Verb
    key: str
    section: str
    as_of: date | None = None
    token: str = ""

    @property
    def target(self) -> str:
        return f"{self.key}#{self.section}"

    def text(self) -> str:
        """The token as written canonically."""
        return "{" + f"{self.verb.value}:{self.target}" + (f" as-of={self.as_of.isoformat()}" if self.as_of else "") + "}"


def parse(m: re.Match) -> Ref:
    """A token match as a ``Ref``. An unknown setting or a bad date raises: a token is never half read."""
    settings: dict[str, str] = {}
    for pair in (m.group("args") or "").split():
        name, _, value = pair.partition("=")
        if name not in SETTINGS:
            raise SectionRefError(f"{m.group(0)}: unknown setting {name!r} (settings: {', '.join(sorted(SETTINGS))})")
        settings[name] = value
    as_of = None
    if "as-of" in settings:
        if m.group("verb") == "CITE":
            raise SectionRefError(f"{m.group(0)}: a citation has no date; as-of is for a quote")
        try:
            as_of = date.fromisoformat(settings["as-of"])
        except ValueError as exc:
            raise SectionRefError(f"{m.group(0)}: as-of is a date, YYYY-MM-DD") from exc
    return Ref(Verb(m.group("verb")), m.group("key"), normalize_number(m.group("section")), as_of, m.group(0))


def refs_in(text: str) -> list[Ref]:
    return [parse(m) for m in TOKEN.finditer(text or "")]


@dataclass(frozen=True)
class SectionText:
    """One section as a reference fills it: its words (with its subsections'), and where they came from."""

    key: str
    number: str
    caption: str
    words: str
    citation: str                     # "CC&Rs Section 4.2(b)"
    document: str                     # the document's title
    set_by: str                       # the instrument (or base document) key that last set the words
    set_by_title: str                 # "the Second Amendment, recorded 2023-12-06 as No. 000000000001"
    dated: date | None = None         # when those words took effect, when known
    amended: bool = False             # an amendment set the words, not the base document
    as_of: date | None = None         # the date asked for, or None for the current text
    source: str = ""                  # where the base text came from ("the recorded copy", "the Doc, revision ...")
    note: str = ""                    # a caution for the person sending it ("check the words: OCR")

    @property
    def digest(self) -> str:
        return hashlib.sha256(re.sub(r"\s+", " ", self.words).strip().encode("utf-8")).hexdigest()[:16]

    def provenance(self) -> str:
        """Who set the words, in a phrase: "as amended by ...", or "as written in ..."."""
        if self.amended:
            return f"as amended by {self.set_by_title}"
        title = self.set_by_title or self.document
        return f"as written in {title if title.lower().startswith('the ') else 'the ' + title}"


class Resolver(Protocol):
    def section(self, key: str, number: str, as_of: date | None = None) -> SectionText: ...

    def citation(self, key: str, number: str) -> str: ...


@dataclass(frozen=True)
class Embedded:
    """The record of one filled reference."""

    token: str
    verb: str
    key: str
    section: str
    as_of: str
    citation: str
    set_by: str
    set_by_title: str
    dated: str
    digest: str
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _record(ref: Ref, citation: str, found: SectionText | None) -> Embedded:
    return Embedded(ref.token or ref.text(), ref.verb.value, ref.key, ref.section,
                    ref.as_of.isoformat() if ref.as_of else "", citation,
                    found.set_by if found else "", found.set_by_title if found else "",
                    found.dated.isoformat() if found and found.dated else "", found.digest if found else "",
                    found.note if found else "")


# Citations ------------------------------------------------------------------------------------------------------------

_LETTERED = re.compile(r"^[A-Za-z]+-")             # "R-3(a)": a rule numbered by its own letter


def citation_of(name: str, number: str, *, article: bool = False) -> str:
    """A section as a document is cited: "CC&Rs Section 4.2(b)", "CC&Rs Article 8" (a top-level number the
    document calls an article), "Rules R-3(a)" (a lettered rule carries its own label)."""
    number = normalize_number(number)
    if _LETTERED.match(number):
        return f"{name} {number}"
    if article and re.fullmatch(r"\d+", number):
        return f"{name} Article {number}"
    return f"{name} Section {number}"


# Rendering -----------------------------------------------------------------------------------------------------------

def _fill(text: str, resolver: Resolver, one) -> tuple[str, list[Embedded]]:
    """Each token replaced by ``one(ref, match)``. Every token is resolved before any is replaced, and every failure
    is reported at once: a document with a bad reference raises and is not rendered."""
    records: list[Embedded] = []
    errors: list[str] = []
    filled: dict[int, str] = {}
    for m in TOKEN.finditer(text or ""):
        try:
            ref = parse(m)
            citation = resolver.citation(ref.key, ref.section)
            found = resolver.section(ref.key, ref.section, ref.as_of) if ref.verb is Verb.QUOTE else None
            if ref.verb is Verb.CITE:
                resolver.section(ref.key, ref.section)          # a citation to a section that is not there fails too
        except SectionRefError as exc:
            errors.append(str(exc))
            continue
        filled[m.start()] = one(ref, citation, found, m)
        records.append(_record(ref, citation, found))
    if errors:
        raise SectionRefError("; ".join(errors))
    out = TOKEN.sub(lambda m: filled[m.start()], text or "")
    return out, records


def _alone(text: str, m: re.Match) -> bool:
    """The token is a paragraph of its own (the only thing on its line)."""
    start = text.rfind("\n", 0, m.start()) + 1
    end = text.find("\n", m.end())
    end = len(text) if end < 0 else end
    return not text[start:m.start()].strip() and not text[m.end():end].strip()


def _when(found: SectionText) -> str:
    if found.as_of:
        return f" (the text in force on {found.as_of.isoformat()})"
    return ""


def _dated(found: SectionText) -> str:
    return f", in force from {found.dated.isoformat()}" if found.amended and found.dated else ""


def expand_markdown(text: str, resolver: Resolver, *, caveat: bool = True) -> tuple[str, list[Embedded]]:
    """Markdown with each reference filled. A ``QUOTE`` on a line of its own is a block quote with its citation and
    provenance under it; one inside a sentence is the words in quotation marks with the citation after. ``CITE`` is
    the citation. With ``caveat``, a document that quotes ends with a note that the text is not an official
    restatement and the recorded instruments control."""
    def one(ref: Ref, citation: str, found: SectionText | None, m: re.Match) -> str:
        if found is None:
            return citation
        words = found.words.strip()
        if _alone(text, m):
            caption = found.caption.strip()
            if caption and words.startswith(caption):
                words = f"**{caption}**" + words[len(caption):]
            lines = [f"> {line}" if line.strip() else ">" for line in words.splitlines()]
            return "\n".join(lines + [">", f"> _{citation}, {found.provenance()}{_dated(found)}{_when(found)}._"])
        flat = re.sub(r"\s+", " ", words)
        return f"“{flat}” ({citation}{_when(found)})"

    out, records = _fill(text, resolver, one)
    if caveat and any(r.verb == "QUOTE" for r in records):
        out = out.rstrip("\n") + f"\n\n_{CAVEAT}_\n"
    return out, records


def expand_html(text: str, resolver: Resolver, *, caveat: bool = True) -> tuple[str, list[Embedded]]:
    """``expand_markdown`` for an HTML template: a quote alone on its line is a ``blockquote``; the words are escaped."""
    def one(ref: Ref, citation: str, found: SectionText | None, m: re.Match) -> str:
        if found is None:
            return html.escape(citation)
        words = found.words.strip()
        note = html.escape(f"{citation}, {found.provenance()}{_dated(found)}{_when(found)}.")
        if _alone(text, m):
            paras = "".join(f"<p>{html.escape(p.strip())}</p>" for p in words.splitlines() if p.strip())
            return f'<blockquote class="quoted-provision">{paras}<p><em>{note}</em></p></blockquote>'
        flat = html.escape(re.sub(r"\s+", " ", words))
        return f"“{flat}” ({html.escape(citation)}{html.escape(_when(found))})"

    out, records = _fill(text, resolver, one)
    if caveat and any(r.verb == "QUOTE" for r in records):
        out += f'\n<p class="quoted-provision-note"><em>{html.escape(CAVEAT)}</em></p>\n'
    return out, records


__all__ = ["CAVEAT", "Embedded", "Ref", "Resolver", "SETTINGS", "SectionRefError", "SectionText", "TOKEN", "Verb",
           "citation_of", "expand_html", "expand_markdown", "parse", "refs_in"]
