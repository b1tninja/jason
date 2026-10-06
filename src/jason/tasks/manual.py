"""The owner's manual on disk: classify its sections, write the concordance, render the official rules and the
generated manual, and compare the rendering with the manual.

- ``classify`` reads the manual's outline (``data/outlines/KEY.json``, the Doc as last read by ``jason outlines
  --fetch``), the norms the deontic grammar reads in it, and the copies the embedded-copy scan found
  (``data/section-refs/copies.json``), and applies the profile's rows (``Community.owners_manual()``). A person's
  answers to the open questions (``jason intake``) are applied.
- ``save_classification`` writes ``data/manual/KEY/classification.{json,md}`` and ``concordance.{json,md}``;
  ``references`` resolves every existing citation of the manual (notice provisions, assignments, conflict rows, the
  duties store, other documents' references) through the concordance.
- ``render`` fills the base templates (``src/jason/templates/manual``) and writes ``data/drafts/rules-and-regulations.md``,
  ``data/drafts/owners-manual.md``, and ``data/drafts/owners-manual.diff``; the check is in ``data/manual/KEY/render.json``.
  The official rules hold the last adopted words: a passage the revision history finds changed with no adoption (the
  (b) of ``manual_rule_change``) shows them where an adoption on record covers them, then jason's bracketed note with
  the working words; where no adopted version is on record the note says so and no words are printed as the rule.
  ``current=True`` writes the working words (``rules-and-regulations-current.md``) with the same notes. Pending
  suggestions (c) never appear. ``working_rules`` is the working text in memory, with no notes.
- ``adoption_history`` is the profile's recorded steps, the rule-change records that name the manual, and a
  detector's dated versions from ``history_path`` (``data/manual/KEY/history.json``, a list of
  ``AdoptionEvent.to_dict()`` rows).

Reading only: nothing here writes to Drive, PayHOA, or the mail, and the Doc is never edited. ``merge_asks`` writes the
open questions to the intake store only when a person asks for it (``jason manual --classify --asks``).
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from jason.community.manual import (AdoptionAction, AdoptionEvent, Chunk, Classification, CopyHit, CopyState, ManualError,
                                    ManualSpec, Norm, Passage, SectionKind, Segment, asks as asks_of, check,
                                    classify as classify_, compare, concordance, places, render as render_, resolve_old,
                                    segments, words)
from jason.community.outlines import DocumentOutline

TEMPLATES = Path(__file__).resolve().parents[1] / "templates" / "manual"


def default_data_dir() -> Path:
    from jason.config import Settings

    return Settings.load().ownership_db.parent


def spec_of(community: Any) -> ManualSpec:
    spec = getattr(community, "owners_manual", lambda: None)()
    if spec is None:
        raise ManualError("the profile has no owner's manual (Community.owners_manual())")
    return spec


def store(data_dir: Path, key: str) -> Path:
    path = Path(data_dir) / "manual" / key
    path.mkdir(parents=True, exist_ok=True)
    return path


def history_path(data_dir: Path, key: str) -> Path:
    """Where a detector writes a section's dated versions: a JSON list of ``AdoptionEvent.to_dict()`` rows (``on``,
    ``action`` "in force" or "adopted", ``sections`` as the manual's outline numbers them, ``evidence``, ``version``,
    ``digest``, ``source`` "detector")."""
    return Path(data_dir) / "manual" / key / "history.json"


def load_outline(data_dir: Path, key: str) -> DocumentOutline:
    path = Path(data_dir) / "outlines" / f"{key}.json"
    if not path.is_file():
        raise ManualError(f"no outline of {key} on disk: run jason outlines --fetch (read-only) first")
    return DocumentOutline.from_dict(json.loads(path.read_text(encoding="utf-8")))


# --- Evidence ---------------------------------------------------------------------------------------------------------

def norms(outline: DocumentOutline) -> list[Norm]:
    from jason.community.deontic import read_outline

    return [Norm(d.start, d.kind.value, d.bearer.value, d.quote) for d in read_outline(outline)]


def copy_hits(data_dir: Path, key: str) -> list[CopyHit]:
    path = Path(data_dir) / "section-refs" / "copies.json"
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for host in raw.get("hosts", []):
        if host.get("host") != f"outline:{key}":
            continue
        for c in host.get("copies", []):
            out.append(CopyHit(int(c["start"]), int(c["end"]), c.get("target", ""), c.get("kind", ""),
                               c.get("currency", ""), float(c.get("coverage") or 0), float(c.get("fidelity") or 0)))
    return out


_SUB = re.compile(r"^\(([a-z0-9]+)\)", re.M)


def statute_words(data_dir: Path, citation: str) -> tuple[str, str]:
    """A statute's words on disk, and the session they were read from: the section, or one subdivision
    ("CIV 5730(a)"); empty when the law is not on disk."""
    from jason.tasks.export_authorities import authority_text

    m = re.match(r"^([A-Z0-9-]+)\s+(\d+(?:\.\d+)?)((?:\([a-z0-9]+\))*)$", citation.strip())
    if not m:
        return "", ""
    try:
        found = authority_text(Path(data_dir), f"{m.group(1)} {m.group(2)}")
    except Exception:
        return "", ""
    if not found.get("found"):
        return "", ""
    text = found.get("text") or ""
    body = text[text.find(f"{m.group(2)}."):] if f"{m.group(2)}." in text else text
    body = re.sub(r"^\d+(?:\.\d+)?\.\s*\([^)]*\)\s*", "", body.strip())        # "5730. (Amended by ...)"
    subs = re.findall(r"\(([a-z0-9]+)\)", m.group(3))
    if subs:
        marks = list(_SUB.finditer(body))
        at = next((k for k, x in enumerate(marks) if x.group(1) == subs[0]), None)
        if at is None:
            return "", ""
        end = next((x.start() for x in marks[at + 1:] if not re.fullmatch(r"[ivx]+|\d+", x.group(1))
                    or x.group(1) == subs[0]), len(body))
        body = body[marks[at].start():end]
    return body.strip(), str(found.get("session") or "")


def quoted(text: str) -> str:
    """The passage a subdivision prints in quotation marks (a notice the statute gives word for word); empty when none."""
    a, b = text.find("“"), text.rfind("”")
    return text[a + 1:b].strip() if 0 <= a < b else ""


def unwrap(text: str) -> str:
    """Hard-wrapped lines joined; paragraphs (a blank line) kept."""
    return re.sub(r"[ \t]*(?<!\n)\n(?!\n)[ \t]*", " ", text or "").strip()


def law_for(data_dir: Path, citation: str, copy: str) -> tuple[str, str]:
    """The statute's words a copy stands for: the quoted passage when it reads closer than the whole subdivision."""
    whole, session = statute_words(data_dir, citation)
    if not whole:
        return "", ""
    inner = quoted(whole)
    if inner and compare(copy, inner)[1] >= compare(copy, whole)[1]:
        return unwrap(inner), session
    body = re.sub(r"^\([a-z0-9]+\)\s*", "", whole)
    return unwrap(body), session


def answers(data_dir: Path, key: str) -> dict[str, str]:
    from jason.community.intake import AskKind, AskStatus, load

    out = {}
    for a in load(Path(data_dir)):
        if a.kind is AskKind.SECTION_KIND and a.subject.startswith(f"{key}#") and a.status in (AskStatus.ANSWERED,
                                                                                             AskStatus.APPLIED):
            out[a.subject.split("#", 1)[1]] = a.answer
    return out


# --- Classification ---------------------------------------------------------------------------------------------------

def classify(data_dir: Path | None = None, community: Any = None) -> tuple[Classification, DocumentOutline, ManualSpec]:
    data_dir = Path(data_dir) if data_dir is not None else default_data_dir()
    if community is None:
        from jason.community import community as active

        community = active()
    spec = spec_of(community)
    outline = load_outline(data_dir, spec.document)
    law = lambda cite, seg: law_for(data_dir, cite, outline.text[seg.start:seg.end])[0]      # noqa: E731
    result = classify_(outline, spec, norms(outline), copy_hits(data_dir, spec.document),
                       answers=answers(data_dir, spec.document), law=law)
    return result, outline, spec


def counts_by_letter(result: Classification) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in result.sections:
        name = f"({c.kind.letter}) {c.kind.value}" if c.kind is not SectionKind.UNCLEAR else "unclear"
        out[name] = out.get(name, 0) + 1
    return out


def classification_lines(result: Classification, text: str) -> list[str]:
    lines = [f"# {result.document}: what each section is", "",
             f"_Outline revision {result.revision[:16]}…; {len(result.sections)} sections. Kinds: (a) operating rule, "
             "(b) copy of a governing document or statute, (c) policy bound in, (d) guidance, (e) mixed. A row is "
             "the reading; the evidence is the grammar's norms and the copy scan. Unclear sections are questions for a "
             "person (jason intake)._", "",
             "| Kind | Sections |", "|---|---|"]
    lines += [f"| {k} | {n} |" for k, n in sorted(counts_by_letter(result).items())]
    lines += ["", "| Section | Kind | Pieces (kind → new address) | Evidence |", "|---|---|---|---|"]
    for c in result.sections:
        pieces = "; ".join(f"{s.kind.value}{'/' + s.state.value if s.state else ''} → {s.address}"
                           + (f" (copies {', '.join(s.copies)})" if s.copies else "") for s in c.segments)
        kind = c.kind.value + (f" (suggest {c.suggestion.value})" if c.suggestion else "") + \
            (f" (answered {c.answered})" if c.answered else "")
        ev = "; ".join(e.replace("|", "/") for e in c.evidence[:3])
        lines.append(f"| {c.old.replace('|', '/')[:60]} | {kind} | {pieces.replace('|', '/')} | {ev[:240]} |")
    open_ = [c for c in result.sections if c.question]
    if open_:
        lines += ["", "## Questions for a person", ""]
        seen = set()
        for c in open_:
            if c.question in seen:
                continue
            seen.add(c.question)
            same = [x.old for x in open_ if x.question == c.question]
            lines.append(f"- **{', '.join(same)}**: {c.question} (suggestion: {c.suggestion.value if c.suggestion else '-'})")
    if result.findings:
        lines += ["", "## Grammar leads (rule rows where no norm was read)", ""]
        lines += [f"- {f}" for f in result.findings]
    return lines


def concordance_lines(rows: list, refs: list[dict[str, str]]) -> list[str]:
    lines = ["# Concordance: the manual's addresses and where each piece goes", "",
             "_Old: the manual's section as its outline reads it (the second of two alike is marked). New: the book and "
             "number. Every printed number is kept; a number only the outline reader made up is replaced by the one "
             "the Doc prints, and the old one resolves here._", "",
             "| Old | Piece | New | Kind | In the official rules | Status | Words |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r.old.replace('|', '/')[:50]} | {r.piece or ''} | {r.new} | {r.kind} | "
                     f"{'yes' if r.official else ''} | {r.status} | {r.words.replace('|', '/')[:60]} |")
    if refs:
        lines += ["", "## Existing citations of the manual, resolved", "", "| Where | Cites | Now |", "|---|---|---|"]
        lines += [f"| {r['where']} | {r['ref']} | {r['new'] or 'UNRESOLVED'} |" for r in refs]
    return lines


_MANUAL_CITE = re.compile(r"owner'?s manual\s+((?:[A-Z]-)?\d+(?:\([A-Za-z0-9]+\))*)", re.I)


def references(community: Any, rows: list, spec: ManualSpec, data_dir: Path | None = None) -> list[dict[str, str]]:
    """Every existing citation of the manual, with its new address: notice provisions, assignments, conflict rows,
    the duties store's sections, and other documents' references."""
    key = spec.document
    found: list[tuple[str, str]] = []
    for n in getattr(community, "notice_provisions", lambda: ())():
        if getattr(n, "document", "") == key:
            for part in str(n.section).split(","):
                found.append((f"notice provision {n.key}", part.strip()))
    for a in getattr(community, "assignments", lambda: ())():
        for c in getattr(a, "covers", ()):
            if c.startswith(f"{key}#"):
                found.append((f"assignment {a.key}", c.split("#", 1)[1]))
    for c in getattr(community, "conflicts", lambda: ())():
        for m in _MANUAL_CITE.finditer(getattr(c, "provision", "")):
            found.append((f"conflict {c.key}", m.group(1)))
    if data_dir is not None:
        duties = Path(data_dir) / "duties" / f"{key}.json"
        if duties.is_file():
            raw = json.loads(duties.read_text(encoding="utf-8"))
            for sec in sorted({d.get("section", "") for d in raw.get("duties", [])}):
                found.append(("duties store", sec))
        refs = Path(data_dir) / "outlines" / "references.json"
        if refs.is_file():
            for r in json.loads(refs.read_text(encoding="utf-8")):
                t = r.get("target", "")
                if t.startswith(f"{key}#") and r.get("source") != key:
                    found.append((f"{r.get('source')} reference", t.split("#", 1)[1]))
    out, seen = [], set()
    for where, ref in found:
        if (where, ref) in seen:
            continue
        seen.add((where, ref))
        out.append({"where": where, "ref": ref, "new": resolve_old(rows, ref)})
    return out


def save_classification(data_dir: Path, result: Classification, outline: DocumentOutline, spec: ManualSpec,
                        community: Any) -> dict[str, Path]:
    folder = store(data_dir, spec.document)
    rows = concordance(result, outline.text)
    refs = references(community, rows, spec, data_dir)
    raw = {"document": result.document, "revision": result.revision, "counts": counts_by_letter(result),
           "sections": [{"old": c.old, "title": c.title[:120], "kind": c.kind.value,
                         "suggestion": c.suggestion.value if c.suggestion else "", "question": c.question,
                         "answered": c.answered, "evidence": c.evidence,
                         "pieces": [{"piece": s.piece, "start": s.start, "end": s.end, "kind": s.kind.value,
                                     "new": s.address, "slot": s.slot, "copies": list(s.copies),
                                     "state": s.state.value if s.state else "", "note": s.note,
                                     "reason": s.row.reason} for s in c.segments]}
                        for c in result.sections],
           "findings": result.findings}
    paths = {"classification": folder / "classification.json", "classification_md": folder / "classification.md",
             "concordance": folder / "concordance.json", "concordance_md": folder / "concordance.md"}
    paths["classification"].write_text(json.dumps(raw, indent=1), encoding="utf-8")
    paths["classification_md"].write_text("\n".join(classification_lines(result, outline.text)) + "\n", encoding="utf-8")
    paths["concordance"].write_text(json.dumps({"rows": [asdict(r) for r in rows], "references": refs}, indent=1),
                                    encoding="utf-8")
    paths["concordance_md"].write_text("\n".join(concordance_lines(rows, refs)) + "\n", encoding="utf-8")
    return paths


def merge_asks(data_dir: Path, result: Classification) -> Path:
    """The open questions into the intake store: one per question (sections a row asks about together share it); an
    answered one keeps its answer; one no run asks any more goes stale."""
    from jason.community import intake

    new, seen = [], set()
    for a in asks_of(result):
        if a.question in seen:
            continue
        seen.add(a.question)
        new.append(a)
    old = intake.load(Path(data_dir))
    return intake.save(Path(data_dir), intake.merge(old, new, scope=(f"{result.document}#",)))


# --- History ----------------------------------------------------------------------------------------------------------

def adoption_history(data_dir: Path, community: Any, spec: ManualSpec) -> list[AdoptionEvent]:
    """The profile's recorded steps, each rule-change record on the manual no step names, and a detector's rows."""
    events = list(spec.adoptions)
    named = {e.record for e in events if e.record}
    for r in getattr(community, "rule_change_records", lambda: ())():
        if getattr(r, "document", "") == spec.document and r.key not in named and getattr(r, "decided", None):
            events.append(AdoptionEvent(r.decided, AdoptionAction.ADOPTED, (), r.title, r.key, "rule-change record"))
    path = history_path(data_dir, spec.document)
    if path.is_file():
        for raw in json.loads(path.read_text(encoding="utf-8")):
            events.append(AdoptionEvent.from_dict(raw))
    return events


# --- Rendering --------------------------------------------------------------------------------------------------------

class DiskSource:
    """The words each rendered piece is read from: its book's own document when the profile names one, the statute
    on disk for a verbatim copy of the law outside the rules, else the manual."""

    def __init__(self, data_dir: Path, community: Any, spec: ManualSpec, outline: DocumentOutline):
        self.data_dir, self.community, self.spec, self.outline = Path(data_dir), community, spec, outline
        self._others: dict[str, dict[tuple, Segment]] = {}
        self._other_text: dict[str, str] = {}

    def _segments_of(self, document: str) -> dict[tuple, Segment]:
        if document not in self._others:
            other = load_outline(self.data_dir, document)
            self._other_text[document] = other.text
            self._others[document] = {(s.locator, s.piece): s for s in segments(other, self.spec)}
        return self._others[document]

    def words(self, s: Segment) -> tuple[str, str]:
        text = self.outline.text[s.start:s.end]
        if (s.kind is SectionKind.COPY and s.state is CopyState.VERBATIM and s.target.top != "rules" and s.copies
                and "#" not in s.copies[0]):
            got, session = law_for(self.data_dir, s.copies[0], text)
            if got:
                return got, f"{s.copies[0]}: the statute's words on disk ({session} session), in place of the copy"
        source = self.spec.source_of(s.target.book)
        if source and s.kind in (SectionKind.RULE, SectionKind.COPY):
            other = self._segments_of(source).get((s.locator, s.piece))
            if other is None:
                raise ManualError(f"{s.id}: not in {source} (the book's own document)")
            return self._other_text[source][other.start:other.end], f"read from {source}"
        return text, ""

    def law(self, citation: str, quoted_: bool) -> tuple[str, str]:
        whole, session = statute_words(self.data_dir, citation)
        if not whole:
            raise ManualError(f"{{LAW:{citation}}}: the law is not on disk (jason export-authorities)")
        return (unwrap(quoted(whole)) if quoted_ and quoted(whole) else unwrap(whole)), f"{citation} ({session} session)"

    def cite(self, ref: str) -> str:
        """A copy's source as it is cited: "CC&Rs Section 4.18"; a statute as written ("CIV 5730(a)")."""
        if "#" not in ref:
            return ref
        from jason.community.section_refs import SectionRefError
        from jason.tasks.section_refs import DiskResolver

        if not hasattr(self, "_resolver"):
            self._resolver = DiskResolver(self.data_dir, self.community)
        key, _, number = ref.partition("#")
        try:
            return self._resolver.citation(key, number)
        except SectionRefError:
            return ref

    def excerpt(self, ref: str) -> str:
        from jason.tasks.section_refs import fill_markdown

        return fill_markdown("{QUOTE:" + ref + "}", self.data_dir, self.community)[0]

    def history(self) -> list[AdoptionEvent]:
        return adoption_history(self.data_dir, self.community, self.spec)


def template(name: str) -> str:
    path = TEMPLATES / name
    if not path.is_file():
        raise ManualError(f"no base template {name} in {TEMPLATES}")
    return path.read_text(encoding="utf-8")


def _values(community: Any, outline: DocumentOutline, spec: ManualSpec, *, basis: bool = True, current: bool = False,
            separated: bool = False) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        values.update(community.identity().values())
    except Exception:
        pass
    values["SOURCE_TITLE"] = outline.title or spec.document
    values["SOURCE_REVISION"] = (outline.revision or "")[:16]
    if not basis:
        values["TEXT_BASIS"] = ""
    elif not separated:
        values["TEXT_BASIS"] = (" These are the working words of the source document: no revision history is on disk "
                                "(jason revisions), so which of them the board adopted is not shown.")
    elif current:
        values["TEXT_BASIS"] = (" These are the working words of the source document, not the adopted text. Where the "
                                "words changed with no adoption found in the board's records, jason's bracketed note "
                                "says so and recites the last adopted words, or says that no adopted version is on "
                                "record. Pending suggestions in the source are left out.")
    else:
        values["TEXT_BASIS"] = (" Where the source's working words changed with no adoption found in the board's "
                                "records, the last adopted words are printed and jason's bracketed note recites the "
                                "working words; where no adopted version of the passage is on record, the note says so "
                                "and no words are printed as the rule. Pending suggestions in the source are left out.")
    return values


RULES_FILE = "rules-and-regulations.md"                    # the official rules: the last adopted words, with notes
CURRENT_FILE = "rules-and-regulations-current.md"          # --current: the working words, with notes


def working_rules(data_dir: Path | None = None, community: Any = None) -> str:
    """The official rules' working text, in memory: the rules template filled from the manual's current Doc as the
    outline reads it, word for word, with no note on what was adopted. What ``jason rule-change --from-manual``
    proposes, and what the (b) and (c) separation reads."""
    data_dir = Path(data_dir) if data_dir is not None else default_data_dir()
    if community is None:
        from jason.community import community as active

        community = active()
    result, outline, spec = classify(data_dir, community)
    source = DiskSource(data_dir, community, spec, outline)
    return render_(template("rules.md"), result, spec, source, outline.text,
                   values=_values(community, outline, spec, basis=False))[0]


def _span(text: str, words: str, near: int) -> tuple[int, int] | None:
    """Where a passage's words (whitespace collapsed, as the revision history keeps them) sit in the outline's text,
    near ``near``: the first to the last run of three or more words in common, in order. None when nothing matches."""
    want = [m.group(0).casefold() for m in re.finditer(r"\w+", words or "")]
    if not want:
        return None
    lo = max(0, near - 200)
    hi = min(len(text), near + int(len(words) * 1.2) + 200)           # the words, and a little: not the next section
    hay = [(m.group(0).casefold(), lo + m.start(), lo + m.end()) for m in re.finditer(r"\w+", text[lo:hi])]
    sm = difflib.SequenceMatcher(None, [w for w, _, _ in hay], want, autojunk=False)
    least = 3 if len(want) >= 3 else len(want)
    blocks = [b for b in sm.get_matching_blocks() if b.size >= least]
    if not blocks:
        return None
    return hay[blocks[0].a][1], hay[blocks[-1].a + blocks[-1].size - 1][2]


def place_passages(part: Any, result: Classification, text: str, spec: ManualSpec) -> list[Passage]:
    """The (b) passages of a separation (``manual_rule_change.partition``), each placed on the rendered pieces of the
    official rules its working words are: the piece the concordance names for it, and every other piece of rule text
    the words run over. A removed passage follows its section's last piece; one the concordance cannot place is shown
    at the end of its book."""
    rule = [s for s in result.segments if s.slot == "rules" and s.end > s.start and s.target.top == "rules"
            and s.kind in (SectionKind.RULE, SectionKind.COPY)]
    claimed: set[str] = set()
    out: list[Passage] = []
    for u in part.unadopted:
        title = spec.title_of(u.book)
        base = Passage(u.address, u.outline, u.kind, u.from_on, u.to_on, u.before, u.after, u.basis, book_title=title)
        anchors = [s for s in rule if s.address == u.address]
        anchors = [s for s in anchors if s.old == u.outline] or anchors
        if u.book.split(".")[0] != "rules" or not anchors:
            out.append(base)
            continue
        if not u.after:
            group = [s for s in rule if s.old == anchors[0].old]
            out.append(replace(base, follows=group[-1].id))
            continue
        span = _span(text, u.after, anchors[0].start)
        mine = [anchors[0]]
        if span is not None:
            a, b = span
            mine = [s for s in rule if s is anchors[0] or (s.start < b and s.end > a
                                                          and min(s.end, b) - max(s.start, a) >= (s.end - s.start) / 2)]
        free = [s.id for s in sorted(mine, key=lambda s: s.start) if s.id not in claimed]
        if not free:
            out.append(replace(base, follows=mine[-1].id))
            continue
        claimed.update(free)
        out.append(replace(base, segments=tuple(free)))
    return out


def pending_inserts(part: Any) -> list[Any]:
    """The pending insertions (c) the working text may carry (an outline read with suggestions inline)."""
    return [s for s in (part.suggestions if part is not None else ()) if s.kind == "insert" and s.words.strip()
            and s.in_draft is not False]


def strip_inserts(text: str, inserts: list[Any]) -> tuple[str, list[str]]:
    """``text`` with each pending insertion taken out where its words are found once, by the words before it in the
    Doc. All are found in the text as given, then taken out together, so one insertion does not hide another's
    context. A suggested deletion's words stay: they stand until a person accepts it."""
    from jason.tasks.manual_rule_change import _find_words

    spans = []
    for s in inserts:
        span = _find_words(text, s.words, s.where)
        if span is not None:
            spans.append((span[0], span[1], s.words))
    out, at, removed = [], 0, []
    for a, b, words_ in sorted(spans):
        if a < at:
            continue
        if a > 0 and text[a - 1] == " " and (b >= len(text) or text[b] in " \n.,;:)]"):
            a -= 1
        out.append(text[at:a])
        at = b
        removed.append(words_)
    out.append(text[at:])
    return "".join(out), removed


class WithoutSuggestions:
    """A ``Source`` whose words leave the pending insertions out: each piece's words, as its source reads them, with
    the insertions found in them taken out. Everything else is the source's."""

    def __init__(self, source: Any, inserts: list[Any]):
        self.source, self.inserts, self.removed = source, inserts, set()

    def words(self, s: Segment) -> tuple[str, str]:
        got, label = self.source.words(s)
        text, removed = strip_inserts(got, self.inserts)
        self.removed.update(removed)
        return text, label

    def __getattr__(self, name: str) -> Any:
        return getattr(self.source, name)


def render(data_dir: Path | None = None, community: Any = None, *, out_dir: Path | None = None,
           current: bool = False) -> dict[str, Any]:
    """Render the official rules and the generated manual to ``data/drafts`` and compare the manual's rendering with
    the Doc's text. Returns the paths and the check.

    The official rules hold the last adopted words: each passage the revision history finds changed with no adoption
    (``manual_rule_change.partition``, (b)) shows its last adopted words where an adoption on record covers them, with
    jason's note reciting the working words, and only the note where no adopted version is on record. ``current``
    renders the working words instead (to ``rules-and-regulations-current.md``), with the same notes. Pending
    suggestions (c) never appear. With no revision history on disk the rules are the working words, and say so."""
    from jason.tasks import manual_rule_change as mrc

    data_dir = Path(data_dir) if data_dir is not None else default_data_dir()
    if community is None:
        from jason.community import community as active

        community = active()
    result, outline, spec = classify(data_dir, community)
    source = DiskSource(data_dir, community, spec, outline)
    plain = _values(community, outline, spec, basis=False)
    working = render_(template("rules.md"), result, spec, source, outline.text, values=plain)[0]
    try:
        part = mrc.partition(data_dir, community, text=working)
    except ManualError as exc:
        part, why = None, str(exc)
    else:
        why = ""
    passages = place_passages(part, result, outline.text, spec) if part is not None else []
    # (c) never appears: not in the rules' words, and not in the working words a note recites.
    inserts = pending_inserts(part)
    clean = WithoutSuggestions(source, inserts)
    # A placed passage's working words are its pieces' words as rendered (the Doc's words with a pending deletion still
    # standing); the revision history's copy of them reads the Doc as if every suggestion were accepted.
    by_id = {s.id: s for s in result.segments}

    def working_of(p: Passage) -> str:
        if p.segments:
            return " ".join(" ".join(clean.words(by_id[i])[0].split()) for i in p.segments if i in by_id)
        return strip_inserts(p.working, inserts)[0]

    passages = [replace(p, working=working_of(p),
                        earlier=strip_inserts(p.earlier, [s for s in inserts if s.since and s.since <= p.from_on])[0])
                for p in passages]
    values = _values(community, outline, spec, basis=True, current=current, separated=part is not None)
    rules_md, rules_chunks = render_(template("rules.md"), result, spec, clean, outline.text, values=values,
                                     passages=passages, current=current)
    from jason.tasks.manual_rule_change import _find_words

    removed = sorted(clean.removed)
    left = [s.words for s in inserts if s.words not in clean.removed and s.in_draft
            and _find_words(rules_md, s.words, s.where) is not None]
    manual_md, manual_chunks = render_(template("owners-manual.md"), result, spec, source, outline.text, values=plain,
                                       passages=passages)
    found = check(manual_chunks, outline.text)
    drafts = Path(out_dir) if out_dir is not None else Path(data_dir) / "drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    paths = {"rules": drafts / (CURRENT_FILE if current else RULES_FILE), "manual": drafts / "owners-manual.md",
             "diff": drafts / "owners-manual.diff", "check": store(data_dir, spec.document) / "render.json"}
    paths["rules"].write_text(rules_md, encoding="utf-8")
    paths["manual"].write_text(manual_md, encoding="utf-8")
    paths["diff"].write_text(diff_text(manual_chunks, outline.text, spec.document), encoding="utf-8")
    official = [p for p in passages if p.top == "rules"]
    adoption = {
        "mode": "current" if current else "adopted", "separated": part is not None, "why": why,
        "passages": len(official), "known": sum(1 for p in official if p.known),
        "unknown": sum(1 for p in official if not p.known),
        "placed": sum(1 for p in official if p.segments or p.follows),
        "policies": len([p for p in passages if p.top != "rules"]),
        "suggestionsRemoved": removed, "suggestionsLeft": left,
        "rows": [{"address": p.address, "number": p.number, "kind": p.kind, "from": p.from_on, "to": p.to_on,
                  "basis": p.basis, "segments": list(p.segments), "follows": p.follows} for p in passages]}
    paths["check"].write_text(json.dumps({
        "covered": found.covered, "missing": found.missing, "outOfOrder": found.out_of_order, "same": found.same,
        "labeled": [asdict(d) for d in found.labeled], "unlabeled": [asdict(d) for d in found.unlabeled],
        "editorial": [{"label": c.label, "markdown": c.markdown[:200]} for c in manual_chunks if c.start < 0],
        "rulesLeftOut": [c.segment for c in rules_chunks if c.label == "left out of the official rules"],
        "adoption": adoption,
    }, indent=1), encoding="utf-8")
    return {"paths": paths, "check": found, "rules_chunks": rules_chunks, "manual_chunks": manual_chunks,
            "rules_source": clean,
            "classification": result, "passages": passages, "adoption": adoption}


def diff_text(chunks: list[Chunk], text: str, key: str) -> str:
    """The manual's words beside the rendering's, line by line with layout removed (one paragraph a line, spacing
    collapsed): a line that differs is a labeled change or a defect."""
    def lines_of(s: str) -> list[str]:
        return [" ".join(words(p)) for p in re.split(r"\n+", s) if p.strip()]

    doc = lines_of(text)
    # The pieces read from the manual are slices of its text: joined back in order they keep its paragraphs, so a piece
    # that splits a paragraph (a sentence of guidance inside a rule) is not reported as a difference.
    def joined(c: Chunk) -> str:
        own = text[c.start:c.end]
        if c.words == own:
            return own
        return c.words.strip() + own[len(own.rstrip()):]          # a piece read elsewhere keeps the manual's spacing

    ours = lines_of("".join(joined(c) for c in sorted((c for c in chunks if c.start >= 0), key=lambda c: c.start)))
    out = list(difflib.unified_diff(doc, ours, f"{key} (the Doc's text)", f"{key} (rendered from its sources)",
                                    lineterm="", n=1))
    return "\n".join(out) + "\n" if out else "no difference in the words\n"


__all__ = ["CURRENT_FILE", "DiskSource", "RULES_FILE", "adoption_history", "answers", "classification_lines",
           "classify", "concordance_lines", "copy_hits", "counts_by_letter", "diff_text", "history_path", "law_for",
           "load_outline", "merge_asks", "norms", "place_passages", "quoted", "references", "render",
           "save_classification", "spec_of", "statute_words", "store", "strip_inserts", "template", "unwrap",
           "working_rules"]
