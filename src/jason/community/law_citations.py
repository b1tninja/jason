"""A document's statute citations resolved to the law in force on a day, the former-section citations through the
law history's successor table.

A document written under a former numbering cites a section that no longer exists by that number (the Davis-Stirling
Act moved from Civil Code 1350 to 1378 to 4000 to 6150 on January 1, 2014). Read as of a day, such a citation is not
a missing section: it is read through the successor table ``jason law-history --export`` keeps on disk
(``jason.community.succession``: the Law Revision Commission's disposition table and Comments), and both the former
section and its successor are recited where jason holds their words. A citation the table does not place stays an
open finding; no successor is guessed.

``resolve`` gives one citation's ``Resolved``; ``cited_in`` reads a text's citations by the one citation grammar
(``references.extract``); ``in_scope`` reads every passage a ``passage_index.Scope`` allows and groups the citations
with the documents that make them. The recodification (which former numbers moved where, by which act, operative
when) is data read from the exported table, never a number in this module, so a made-up table in a test is read the
same way as the Commission's. Reads the disk only; writes nothing; asks no network.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from jason.community.succession import FORMER_FILE, HISTORY_DIR, successors

MAX_CITED_SECTIONS = 12      # a pack brings at most this many cited sections in from a collection's documents


class Resolution(Enum):
    CURRENT = "current"              # a number in force on the day: the section, recited as of the day
    FORMER = "former"                # a number renumbered before the day: its successors named and recited
    THEN_CURRENT = "then_current"    # as of a day before the renumbering: the cited number was the section in force
    UNRESOLVED = "unresolved"        # a former number the history on disk does not place: an open finding
    NOT_HELD = "not_held"            # a number the shelf does not hold


def _key(number: str) -> tuple[float, ...]:
    try:
        return tuple(float(p) for p in re.sub(r"[^\d.]", "", number or "").split(".") if p) or (0.0,)
    except ValueError:
        return (0.0,)


@dataclass(frozen=True)
class Recodification:
    """One renumbering the exported table records: which former numbers of a code moved to which current ones, by
    which act, operative when."""

    act: str                        # "davis-stirling"
    title: str
    code: str                       # "CIV"
    former: tuple[str, str]         # ("1350", "1378")
    current: tuple[str, str]        # ("4000", "6150")
    statute: str                    # "Stats. 2012, Ch. 180"
    bill: str
    operative: str                  # ISO day
    repeals_former: bool            # the act that repealed the former numbers (the one a former citation is read by)
    source: str = ""

    def covers(self, code: str, number: str) -> bool:
        return code == self.code and _key(self.former[0]) <= _key(number) <= _key(self.former[1])

    def describe(self) -> str:
        span = f"{self.code} {self.current[0]} to {self.current[1]}"
        return f"renumbered to {span} by {self.statute}{f' ({self.bill})' if self.bill else ''}, operative {self.operative}"


def recodifications(data_dir: Path | str) -> tuple[Recodification, ...]:
    """Every renumbering the exported former-sections table records, each act once. Empty before the export."""
    path = Path(data_dir) / HISTORY_DIR / FORMER_FILE
    if not path.is_file():
        return ()
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        return ()
    out: dict[str, Recodification] = {}
    for section in data.get("sections") or []:
        code = str(section.get("code") or "CIV")
        for r in section.get("recodifications") or []:
            act = str(r.get("act") or "")
            former, current = r.get("former") or [], r.get("current") or []
            if not act or act in out or len(former) != 2 or len(current) != 2:
                continue
            out[act] = Recodification(act, str(r.get("title") or act), code, (str(former[0]), str(former[1])),
                                      (str(current[0]), str(current[1])), str(r.get("statute") or ""),
                                      str(r.get("bill") or ""), str(r.get("operative") or ""),
                                      bool(r.get("repeals_former")), str(r.get("source") or ""))
    return tuple(out.values())


def renumbered(data_dir: Path | str, code: str, number: str) -> Recodification | None:
    """The renumbering a former number is read by: the act that repealed it, else any that moved it. None when the
    table on disk records none for the number."""
    found = [r for r in recodifications(data_dir) if r.covers(code, number)]
    return next((r for r in found if r.repeals_former), found[0] if found else None)


@dataclass(frozen=True)
class Cited:
    """One statute citation a text makes, as the citation grammar read it."""

    citation: str                # "CIV 1363(g)"
    base: str                    # "CIV 1363"
    subdivisions: str            # "(g)"
    prior: bool                  # the grammar's own reading: a Davis-Stirling number from before 2014
    quote: str = ""              # the sentence it sits in
    offset: int = 0


def cited_in(text: str) -> list[Cited]:
    """Every statute citation in a text, in order, each once."""
    from jason.community.outlines import outline_from_text
    from jason.community.references import TargetKind, extract, statute_key

    out: list[Cited] = []
    seen: set[str] = set()
    for ref in extract(outline_from_text(text or "", key="passage"), {}):
        if ref.kind is not TargetKind.STATUTE or ref.target in seen:
            continue
        seen.add(ref.target)
        base, subs = statute_key(ref.target)
        out.append(Cited(ref.target, base, subs, bool(ref.prior), " ".join((ref.quote or "").split()), ref.offset))
    return out


@dataclass(frozen=True)
class Resolved:
    """One citation resolved to the law in force on a day, with the words recited where held."""

    cited: str
    base: str
    subdivisions: str
    resolution: Resolution
    day: date | None = None
    renumbered: Recodification | None = None
    successors: tuple[str, ...] = ()        # the successor citations as the table writes them ("CIV 5850(a)")
    succession: str = ""                    # continued, continued with changes, ...
    source: str = ""                        # "disposition table and commission comment"
    former: Any = None                      # the former section's own words (``ProvisionText``), where asked for
    former_day: date | None = None          # the day the former words are read as of: the last day the number was in force
    words: tuple[Any, ...] = ()             # the sections recited (``ProvisionText``): the successors', or the section's
    note: str = ""                          # the finding in one line: "cites former CIV 1363(g), now CIV 5855 (...)"

    @property
    def open(self) -> bool:
        """An open finding: the citation could not be resolved, and nothing is guessed."""
        return self.resolution is Resolution.UNRESOLVED

    @property
    def successor_bases(self) -> tuple[str, ...]:
        out: list[str] = []
        for s in self.successors:
            base = re.sub(r"\(.*$", "", s).strip()
            if base and base not in out:
                out.append(base)
        return tuple(out)

    def _recital(self, text: Any, label: str, on: date | None = None) -> list[str]:
        on = on or self.day
        day = on.isoformat() if on else ""
        if text is None:
            return []
        if not text.found:
            return [f"- {label}: not held ({text.reason})"]
        head = f"- {label}: digest {text.digest[:12]}"
        if text.source:
            head += f"; source: {text.source}"
        if day and text.decided:
            head += (f"; in force on {day}: {text.basis}" if text.decided != "not_shown"
                     else f"; NOT SHOWN to be in force on {day} (the words on the shelf now): {text.basis}")
        return [head, *(f"  > {line}" if line else "  >" for line in text.words.split("\n"))]

    def lines(self, *, recite_current: bool = False) -> list[str]:
        """The resolution as page lines: the note, then the words recited. A current citation's words are recited
        only with ``recite_current``; a former citation's successors, and the former section where held, always."""
        out = [f"- {self.note}"]
        if self.resolution is Resolution.FORMER:
            last = f" as last in force (to {self.former_day.isoformat()})" if self.former_day else ""
            out += self._recital(self.former, f"Former {self.base}, its own words{last}", self.former_day)
            for text in self.words:
                out += self._recital(text, f"Now {text.citation}")
        elif self.resolution is Resolution.THEN_CURRENT:
            for text in self.words:
                out += self._recital(text, f"{text.citation}, the words then in force")
        elif self.resolution is Resolution.CURRENT and recite_current:
            for text in self.words:
                out += self._recital(text, text.citation)
        elif self.resolution is Resolution.CURRENT:
            for text in self.words:
                out += self._recital(text, text.citation)[:1]
        return out

    def as_dict(self) -> dict[str, Any]:
        def text(t: Any) -> dict[str, Any] | None:
            if t is None:
                return None
            return {"citation": t.citation, "found": t.found, "digest": t.digest, "source": t.source,
                    "decided": t.decided, "basis": t.basis, "reason": t.reason, "words": t.words}
        return {"cited": self.cited, "base": self.base, "subdivisions": self.subdivisions,
                "resolution": self.resolution.value, "asOf": self.day.isoformat() if self.day else None,
                "renumbered": self.renumbered.describe() if self.renumbered else "", "successors": list(self.successors),
                "succession": self.succession, "source": self.source, "open": self.open, "note": self.note,
                "former": text(self.former), "formerAsOf": self.former_day.isoformat() if self.former_day else None,
                "words": [text(t) for t in self.words]}


def resolve(data_dir: Path | str, citation: str, as_of: date | None = None, *, community: Any = None,
            prior: bool = False) -> Resolved:
    """One citation resolved to the law in force on ``as_of`` (today's shelf when None), from the disk only.

    A number a renumbering on disk covers is read through the successor table for the act that repealed it: its
    successors are named with the table's source and recited as of the day, and the former section's own words are
    recited where the history holds them (``FORMER``). As of a day before the renumbering the cited number was the
    section in force (``THEN_CURRENT``), recited where held. A number the table does not place, or that the grammar
    reads as former (``prior``) when no table is on disk, is ``UNRESOLVED``: an open finding, and no successor is
    guessed. Any other number is the section itself, recited as of the day (``CURRENT``), or ``NOT_HELD``."""
    from jason.community.law_readings import provision_text
    from jason.community.references import statute_citation

    found = statute_citation(citation)
    if found is None:
        return Resolved(citation, citation, "", Resolution.UNRESOLVED, as_of,
                        note=f"{citation}: not read as a code and a section; an open finding")
    base, subs = found.base, found.subdivisions
    cited = base + subs
    act = renumbered(data_dir, found.code, found.number)
    day = as_of.isoformat() if as_of else ""
    if act is None and not prior:
        text = provision_text(base, Path(data_dir), community=community, as_of=as_of)
        if text.found:
            when = f", in force on {day}" if day and text.decided and text.decided != "not_shown" else (
                f", NOT SHOWN to be in force on {day} (the words on the shelf now)" if day and text.decided else "")
            return Resolved(cited, base, subs, Resolution.CURRENT, as_of, words=(text,),
                            note=f"cites {cited}: on the shelf (digest {text.digest[:12]}){when}")
        return Resolved(cited, base, subs, Resolution.NOT_HELD, as_of, words=(text,),
                        note=f"cites {cited}: not on the shelf ({text.reason})")
    if act is None:
        return Resolved(cited, base, subs, Resolution.UNRESOLVED, as_of,
                        note=f"cites former {cited}; the law history is not on disk (jason law-history --export), so "
                             "nothing places it: an open finding, and no successor is guessed")
    if day and act.operative and day < act.operative:
        text = provision_text(base, Path(data_dir), community=community, as_of=as_of)
        held = "" if text.found else ("; its words of that day are not held: a person adds them from an official "
                                      "source (jason law-history --add-version)")
        return Resolved(cited, base, subs, Resolution.THEN_CURRENT, as_of, act, words=(text,),
                        note=f"cites {cited}, the number in force on {day} ({act.describe()}){held}")
    rows = successors(Path(data_dir), found.number, subs, act=act.act)
    targets: list[str] = []
    for r in rows:
        for t in r.targets:
            if t and t not in targets:
                targets.append(t)
    if not targets:
        kinds = ", ".join(sorted({r.succession.replace("_", " ") for r in rows}))
        why = f"the table says {kinds}" if rows else "the law history on disk places nothing under that number"
        return Resolved(cited, base, subs, Resolution.UNRESOLVED, as_of, act,
                        succession=kinds, note=f"cites former {cited}; {why}: an open finding, and no successor is guessed")
    sources = " and ".join(sorted({r.source.replace("_", " ") for r in rows if r.targets}))
    succession = ", ".join(sorted({r.succession.replace("_", " ") for r in rows if r.targets}))
    bases: list[str] = []
    for t in targets:
        b = re.sub(r"\(.*$", "", t).strip()
        if b and b not in bases:
            bases.append(b)
    words = tuple(provision_text(b, Path(data_dir), community=community, as_of=as_of) for b in bases)
    # The former section's own words are read as they last stood: the day before the renumbering took effect, when
    # the former number was still the law. On the day asked they were not, and a reader never quotes them as such.
    former_day = last_day(act) or as_of
    former = provision_text(base, Path(data_dir), community=community, as_of=former_day)
    held = ", ".join(f"{t.citation} {'recited' if t.found else 'not on the shelf'}" for t in words)
    own = (f"its own words recited from the history as last in force (to {former_day.isoformat()})" if former.found
           else "its own words not held")
    note = (f"cites former {cited}, now {', '.join(targets)} ({sources}: {succession}; {act.describe()}); {own}; {held}")
    return Resolved(cited, base, subs, Resolution.FORMER, as_of, act, tuple(targets), succession, sources, former,
                    former_day, words, note)


def last_day(act: Recodification) -> date | None:
    """The last day a renumbered act's former numbers were the law: the day before the renumbering took effect, or
    None when the table records no operative day."""
    from datetime import timedelta

    try:
        return date.fromisoformat(act.operative) - timedelta(days=1)
    except ValueError:
        return None


@dataclass(frozen=True)
class Use:
    """One citation with the documents of a scope that make it."""

    resolved: Resolved
    cited_by: tuple[tuple[str, int], ...] = ()        # (the document as the page names it, the passage)
    quotes: tuple[str, ...] = ()                        # the sentences it sits in, a few

    @property
    def cited(self) -> str:
        return self.resolved.cited

    def as_dict(self) -> dict[str, Any]:
        return {**self.resolved.as_dict(), "citedBy": [{"document": d, "passage": p} for d, p in self.cited_by],
                "quotes": list(self.quotes)}


def in_scope(data_dir: Path | str, scope: Any, as_of: date | None = None, *, community: Any = None,
             quotes: int = 3) -> tuple[Use, ...]:
    """Every statute citation the passages a scope allows make, each resolved once, with the documents that make it.
    Raises ``FileNotFoundError`` without a passage index."""
    from jason.community import passage_index as pi

    loaded = pi.load(data_dir, scope, vectors=False)
    by: dict[str, dict[str, Any]] = {}
    for passage in loaded.passages:
        name = passage.path.name + (f" ({passage.context})" if getattr(passage, "context", "") else "")
        for c in cited_in(passage.text):
            row = by.setdefault(c.citation, {"cited": c, "by": [], "quotes": []})
            if (name, passage.index) not in row["by"]:
                row["by"].append((name, passage.index))
            if c.quote and c.quote not in row["quotes"] and len(row["quotes"]) < quotes:
                row["quotes"].append(c.quote)
    out: list[Use] = []
    for citation, row in by.items():
        c: Cited = row["cited"]
        out.append(Use(resolve(data_dir, c.citation, as_of, community=community, prior=c.prior),
                       tuple(row["by"]), tuple(row["quotes"])))
    order = {Resolution.UNRESOLVED: 0, Resolution.FORMER: 1, Resolution.THEN_CURRENT: 2, Resolution.NOT_HELD: 3,
             Resolution.CURRENT: 4}
    return tuple(sorted(out, key=lambda u: (order[u.resolved.resolution], _key(u.resolved.base.rpartition(" ")[2]),
                                            u.resolved.cited)))


def former_in(texts: Iterable[str], data_dir: Path | str) -> list[Cited]:
    """The citations in the texts that a renumbering on disk covers, or that the grammar reads as former, each once."""
    out: list[Cited] = []
    seen: set[str] = set()
    for text in texts:
        for c in cited_in(text):
            if c.citation in seen:
                continue
            code, _, number = c.base.rpartition(" ")
            if c.prior or renumbered(data_dir, code, number) is not None:
                seen.add(c.citation)
                out.append(c)
    return out


__all__ = ["MAX_CITED_SECTIONS", "Cited", "Recodification", "Resolution", "Resolved", "Use", "cited_in", "former_in",
           "in_scope", "last_day", "recodifications", "renumbered", "resolve"]
