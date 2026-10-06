"""The seven checks of the form library (docs/form-library-design.md, "What the library checks").

``check(resolved, data_dir)`` runs them over a community's resolved forms and returns a ``Report``: one ``Finding`` for
each problem, naming the form and the item. A finding is ``FAIL`` (the form is wrong), ``NOT_OFFERED`` (the form waits for
a slot or a binding), or ``DEFERRED`` (a gap the definition names, to be closed by a later step). Only ``FAIL`` fails the
report.

1. **Required content.** Each item of ``required_content`` is carried by a question, or by the template's signature,
   preamble, description, or attestation; an item with no carrier and no named deferral fails.
2. **Recitals resolve.** Each recital is read from the statutes on disk (``jason.community.law_text``; a document section
   through ``jason.tasks.section_refs.DiskResolver``): the section is on the shelf, the cited subdivision is in it, and the
   words have not changed on the shelf since the form's as-of day. A missing statute is "not on the shelf", never an
   exception.
3. **Slots are filled.** A form with a slot not given, or a family form with an incomplete binding, is not offered, and
   the finding names the missing piece.
4. **Adjustments are lawful.** The resolver refused what removes or rewords a question, drops a recital, lengthens a
   statutory clock, sets one, or adds what a binding forbids; each refusal is a finding.
5. **A handler exists.** The form's handler and procedure are registered (``handlers``); a form with neither is not made.
6. **Marker codes are unique** across the resolved forms, are codes ``form_refs`` can print, and do not name a form other
   than the one that sent copies under that code (``data/forms/references.json``, read only).
7. **Nothing a binding bars is asked.**

This module reads the data folder only: the statutes, ``forms/references.json``, and the documents' outlines.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from jason.community.form_library.resolve import Resolved, ResolvedForm
from jason.community.form_library.tiers import CARRIERS, Check, Finding, Severity, Status


@dataclass(frozen=True)
class Recital:
    """One recital read from the shelf: the words (or the problem), and whose words they are."""

    citation: str
    found: bool
    words: str = ""
    source: str = ""
    problem: str = ""
    caveats: tuple[str, ...] = ()
    document: bool = False                  # a governing-document section ("ccrs#4.15"), not a statute

    def lines(self, *, caveats: bool = True) -> list[str]:
        if not self.found:
            return [f"{self.citation}: {self.problem}"]
        out = [f"{self.citation}" + (f" ({self.source})" if self.source else "")]
        out += [f"  {line}" for line in self.words.strip().splitlines() if line.strip()]
        if caveats:
            out += [f"  caveat: {c}" for c in self.caveats]
        return out

    def as_dict(self) -> dict[str, Any]:
        return {"citation": self.citation, "found": self.found, "words": self.words, "source": self.source,
                "problem": self.problem, "caveats": list(self.caveats), "document": self.document}


@dataclass(frozen=True)
class Report:
    """The checks' findings, and each form's status once they are counted."""

    findings: tuple[Finding, ...]
    statuses: tuple[tuple[str, Status], ...] = ()

    @property
    def failing(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity is Severity.FAIL)

    @property
    def ok(self) -> bool:
        return not self.failing

    def status(self, key: str) -> Status | None:
        return dict(self.statuses).get(key)

    def for_form(self, key: str) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.form == key)

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "failing": len(self.failing), "findings": [f.as_dict() for f in self.findings],
                "statuses": {k: s.value for k, s in self.statuses}}


def _subdivisions(words: str) -> list[str]:
    return re.findall(r"(?m)^\(([a-z]{1,2})\)", words or "")


def read_recital(citation: str, data_dir: Path, *, community: Any = None, day: date | None = None, full: bool = False) -> Recital:
    """A recital's words from the disk. A statute (``CIV 5205(f)``) is read from the shelf: not on it, or no such
    subdivision in the section, is a problem and no words. ``full`` adds the words in force on ``day`` (today), with the
    shelf's caveats. A document section (``ccrs#4.15``) is read through the one resolver the ``{QUOTE:}`` tokens use."""
    if "#" in citation:
        return _read_document(citation, Path(data_dir), community, day)
    from jason.community import law_text
    from jason.community.cite import label_text

    found = law_text.normal_citation(citation)
    if found is None:
        return Recital(citation, False, problem="not a statute citation (a code and a section, such as CIV 5205(f))")
    base, subdivisions = found
    held = law_text.versions(base, Path(data_dir))
    if not held:
        return Recital(citation, False, problem=f"{base} is not on the shelf (jason export-authorities brings its words down)")
    words = held[0].words
    if subdivisions:
        labels = re.findall(r"\(([^)]+)\)", subdivisions)
        words = next((w for w in (label_text(v.words, labels) for v in held) if w), "")
        if not words:
            have = ", ".join(f"({s})" for s in _subdivisions(held[0].words)) or "none that open a paragraph"
            return Recital(citation, False, problem=f"no paragraph of {base} on the shelf opens with {subdivisions} "
                                                    f"(the section's subdivisions: {have}); the subdivision moved or was repealed")
    caveats = [law_text.NOT_RESTATEMENT]
    source = held[0].source
    if full:
        on = law_text.version_on(citation, Path(data_dir), day or date.today())
        if on.found:
            words, source = on.subdivision_words or on.words, on.text.source if on.text else source
            caveats = list(on.caveats)
        else:
            caveats = [f"the disk does not show which words were in force on {(day or date.today()).isoformat()}: {on.reason}; "
                       "these are the words on the shelf now", law_text.NOT_RESTATEMENT]
    return Recital(citation, True, words, source, "", tuple(caveats))


def _read_document(citation: str, data_dir: Path, community: Any, day: date | None) -> Recital:
    from jason.community.section_refs import SectionRefError

    key, _, number = citation.partition("#")
    if community is None:
        return Recital(citation, False, problem="a document section is read through the community's documents: none was given", document=True)
    try:
        from jason.tasks.section_refs import DiskResolver

        text = DiskResolver(data_dir, community).section(key, number, day if day and day != date.today() else None)
    except SectionRefError as exc:
        return Recital(citation, False, problem=str(exc), document=True)
    except Exception as exc:  # noqa: BLE001 - a document that cannot be read is a finding, never a crash
        return Recital(citation, False, problem=f"cannot be read: {exc}", document=True)
    return Recital(citation, True, text.words, getattr(text, "citation", ""), "", (), True)


def _stale(citation: str, data_dir: Path, as_of: date | None) -> list[dict[str, Any]]:
    """The changes the shelf logged to a section's words after the day the form recites them."""
    if as_of is None or "#" in citation:
        return []
    from jason.community import law_text

    found = law_text.normal_citation(citation)
    if found is None:
        return []
    return [r for r in law_text.changes(Path(data_dir), found[0]) if str(r.get("when") or "")[:10] > as_of.isoformat()]


# -- the checks --------------------------------------------------------------------------------------------------------

def _fail(form: str, check: Check, item: str, message: str, severity: Severity = Severity.FAIL) -> Finding:
    return Finding(form, check, severity, item, message)


def check_required(f: ResolvedForm) -> list[Finding]:
    out: list[Finding] = []
    t = f.template
    fields = {q.field for q in t.questions}
    for r in f.required_content:
        item = r.item + (f" ({r.authority})" if r.authority else "")
        bad = []
        for carrier in r.carried_by:
            if carrier in CARRIERS:
                held = {"signature": bool(t.signature), "preamble": bool(t.preamble), "description": bool(t.description.strip()),
                        "attestation": bool(t.attestation.strip())}[carrier]
                if not held:
                    bad.append(f"the form has no {carrier}")
            elif carrier not in fields:
                bad.append(f"no question {carrier!r}")
        if bad:
            out.append(_fail(f.key, Check.REQUIRED, item, "not carried: " + "; ".join(bad)))
        elif not r.carried_by:
            if r.deferred:
                out.append(_fail(f.key, Check.REQUIRED, item, f"not carried yet; {r.deferred}", Severity.DEFERRED))
            else:
                out.append(_fail(f.key, Check.REQUIRED, item, "required, and no question or text carries it"))
    return out


def check_recitals(f: ResolvedForm, data_dir: Path, community: Any = None) -> list[Finding]:
    out: list[Finding] = []
    d = f.definition
    for citation in d.recitals:
        recital = read_recital(citation, data_dir, community=community)
        if not recital.found:
            out.append(_fail(f.key, Check.RECITALS, citation, recital.problem))
            continue
        for row in _stale(citation, data_dir, d.as_of):
            out.append(_fail(f.key, Check.RECITALS, citation,
                             f"stale: the shelf logged a change to its words on {str(row.get('when'))[:10]}, after the form's as-of "
                             f"{d.as_of.isoformat()}; read the amendment, update the definition, and bump its version "
                             f"(now {d.version})"))
    return out


def check_slots(f: ResolvedForm) -> list[Finding]:
    return [_fail(f.key, Check.SLOTS, gap, "not given: the form is not offered until it is", Severity.NOT_OFFERED) for gap in f.missing]


def check_adjustments(f: ResolvedForm) -> list[Finding]:
    return list(f.refused)


def check_handler(f: ResolvedForm) -> list[Finding]:
    return [_fail(f.key, Check.HANDLER, "handler" if "handler" in p else "procedure", p) for p in f.handler_problems]


def _sent_codes(data_dir: Path) -> dict[str, set[str]]:
    """The form each marker code was sent for, from the catalog of copies (``data/forms/references.json``), read only."""
    path = Path(data_dir) / "forms" / "references.json"
    try:
        rows = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError):
        return {}
    out: dict[str, set[str]] = {}
    for marker, entry in (rows.items() if isinstance(rows, dict) else ()):
        if isinstance(entry, dict) and entry.get("form"):
            out.setdefault(str(marker)[:2].upper(), set()).add(str(entry["form"]))
    return out


def check_codes(resolved: Resolved, data_dir: Path) -> list[Finding]:
    from jason.community import form_refs

    out: list[Finding] = []
    seen: dict[str, str] = {}
    sent = _sent_codes(data_dir)
    for f in resolved.forms:
        code = f.template.code
        if not code:
            continue
        try:
            form_refs.campaign(code, 2000, form_refs.Channel.EMAIL)
        except ValueError as exc:
            out.append(_fail(f.key, Check.CODES, code, str(exc)))
            continue
        if code.upper() in seen and seen[code.upper()] != f.key:
            out.append(_fail(f.key, Check.CODES, code, f"the code is also {seen[code.upper()]}'s: a marker could not tell them apart"))
        seen.setdefault(code.upper(), f.key)
        others = sent.get(code.upper(), set()) - {f.template.key.value, f.key}
        if others:
            out.append(_fail(f.key, Check.CODES, code, f"copies were already sent under this code for {', '.join(sorted(others))}"))
    return out


def check_forbidden(f: ResolvedForm) -> list[Finding]:
    asked = {q.field: q for q in f.template.questions}
    return [_fail(f.key, Check.FORBIDDEN, field, f"the question {asked[field].title!r} is on the form, and "
                  f"{f.binding.section if f.binding and f.binding.section else 'the binding'} bars it")
            for field in f.forbidden if field in asked]


def check(resolved: Resolved, data_dir: Path | str | None = None, *, community: Any = None) -> Report:
    """Run the seven checks. ``data_dir`` is the folder the statutes sit under (default: the active profile's data folder);
    ``community`` reads a recital that is a document's section."""
    if data_dir is None:
        from jason.config import default_data_dir

        data_dir = default_data_dir()
    root = Path(data_dir)
    findings: list[Finding] = list(resolved.problems)
    for f in resolved.forms:
        findings += check_required(f)
        findings += check_recitals(f, root, community)
        findings += check_slots(f)
        findings += check_adjustments(f)
        findings += check_handler(f)
        findings += check_forbidden(f)
    findings += check_codes(resolved, root)
    failing = {f.form for f in findings if f.severity is Severity.FAIL}
    statuses = tuple((f.key, Status.FAILING if f.key in failing and f.status is not Status.NOT_OFFERED else f.status)
                     for f in resolved.forms)
    return Report(tuple(findings), statuses)


__all__ = ["Recital", "Report", "check", "check_adjustments", "check_codes", "check_forbidden", "check_handler",
           "check_recitals", "check_required", "check_slots", "read_recital"]
