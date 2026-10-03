"""The board's Civil Code 4360 course for publishing the official rules: a draft notice whose "text of the proposed
rule change" is the official rules document extracted from the owner's manual, with its concordance.

``jason manual --render`` writes the official rules (``data/drafts/rules-and-regulations.md``) from the manual's current
Doc, word for word. The Doc is not all adopted text, so the notice does not present it whole as the rules in force. The
revision history (``jason revisions KEY``, ``data/revisions/KEY.json``) separates three things:

- **(a) the text as adopted, or unchanged since the earliest version on disk**: the rules' words with no change
  between versions, or whose change an adoption on record names (the detector's finding is empty, or a later adoption
  in the manual's history names the section);
- **(b) changes made with no adoption found**: each recited with its words before and after, and labeled; the notice
  proposes the words now in the manual, so the board adopts them through 4360 or restores the earlier words. "No
  adoption found" is a finding for a person, not proof that none happened;
- **(c) pending suggestions** in the working Doc: words proposed in the Doc and never accepted. They are not the text
  in force and not part of the proposed text. The Docs API reads them inline, so the official rules draft may carry
  them; this module finds them there and strikes them from the enclosed text.

The draft (``data/drafts/rule-change-official-rules-<notice date>.md``) carries the member notice in 4360(a)'s order,
the agenda item, the adoption notice, the required-elements check, the proposed text as a stage version
(``rules@proposed-DATE``), the official rules as Enclosure A, and the concordance as Enclosure B. Nothing is sent.
"""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ElementTree
import zipfile
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

from jason.community.rule_changes import RuleChange, SectionChange

DRAFTS = "drafts"
RULES_DRAFT = "rules-and-regulations.md"
WORD_CHANGES = ("reworded", "added", "removed", "split", "merged")      # moved and renumbered keep their words
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_WORD = re.compile(r"[A-Za-z0-9$%]+(?:['’][A-Za-z]+)?")


@dataclass(frozen=True)
class Unadopted:
    """(b) A change to the manual's words between two versions, with no adoption found. ``address`` is the piece's new
    address ("rules#B-14"); ``official`` says the piece is in the official rules document."""

    lineage: str
    address: str
    outline: str                     # the manual's number as its outline reads it
    official: bool
    kind: str
    flags: tuple[str, ...]
    before: str
    after: str
    from_on: str
    to_on: str
    first_saved: str
    finding: str
    steps: int = 1                   # how many changes between milestones this lineage made with no adoption found
    in_draft: bool | None = None     # whether the official rules draft carries the words now in the manual
    suggested: bool = False          # the new words include a pending insertion: the Doc never accepted them
    ops: tuple[tuple[str, str], ...] = ()   # the words that changed, each (before, after), in order

    def changed_words(self) -> list[str]:
        """Each change of words, as a phrase: “before” became “after”; words added; words struck."""
        out = []
        for b, a in self.ops:
            if b and a:
                out.append(f"\"{b}\" became \"{a}\"")
            elif a:
                out.append(f"added \"{a}\"")
            elif b:
                out.append(f"struck \"{b}\"")
        return out

    @property
    def book(self) -> str:
        return self.address.split("#", 1)[0]

    @property
    def number(self) -> str:
        return self.address.split("#", 1)[1] if "#" in self.address else ""


@dataclass(frozen=True)
class Suggestion:
    """(c) A pending suggestion in the working Doc: proposed, never accepted."""

    kind: str                        # "insert" or "delete"
    words: str
    since: str
    in_draft: bool | None            # whether the official rules draft carries the words (None: too short to say)
    where: str = ""                  # the words around it, as the Doc reads them
    struck: bool = False             # struck from Enclosure A


@dataclass
class Partition:
    document: str
    title: str
    rules_title: str
    current: str                     # the detector's current version id
    revision: str                    # the outline's revision the draft was read from
    draft: Path
    digest: str
    unadopted: list[Unadopted] = field(default_factory=list)
    cured: list[tuple[Unadopted, str]] = field(default_factory=list)   # changed with no adoption found, adopted later
    suggestions: list[Suggestion] = field(default_factory=list)
    unplaced: list[dict[str, Any]] = field(default_factory=list)
    guidance: int = 0                # changes only to guidance (left in the manual)
    concordance: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def official(self) -> list[Unadopted]:
        return [u for u in self.unadopted if u.official]

    @property
    def other_rules(self) -> list[Unadopted]:
        return [u for u in self.unadopted if not u.official]


# --- Words -------------------------------------------------------------------------------------------------------------

def _norm(text: str) -> str:
    text = (text or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return " ".join(text.replace("*", "").split()).casefold()


def _stream(text: str) -> str:
    return re.sub(r"[^a-z0-9$]", "", _norm(text))


def _tokens(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(0).replace("’", "'").casefold(), m.start(), m.end()) for m in _WORD.finditer(text or "")]


def _find_words(text: str, words: str, before: str = "") -> tuple[int, int] | None:
    """The span of ``words`` in ``text``, by word tokens, after the context ``before`` when it is found there; the span
    is returned only when it is one place."""
    hay = _tokens(text)
    need = [t for t, _, _ in _tokens(words)]
    ctx = [t for t, _, _ in _tokens(before)]
    if not need:
        return None
    seq = [t for t, _, _ in hay]
    for take in (8, 5, 3, 0):
        pre = ctx[-take:] if take else []
        if take and len(pre) < min(take, len(ctx)):
            continue
        if not take and len(need) < 4:
            return None
        want = pre + need
        hits = [k for k in range(len(seq) - len(want) + 1) if seq[k:k + len(want)] == want]
        if len(hits) == 1:
            k = hits[0] + len(pre)
            start, end = hay[k][1], hay[k + len(need) - 1][2]
            tail = re.search(r"[^\w\s]+$", words.strip())          # "(2)", "collection.": the closing marks too
            if tail and text[end:end + len(tail.group(0))] == tail.group(0):
                end += len(tail.group(0))
            return start, end
    return None


# --- The pieces --------------------------------------------------------------------------------------------------------

def _concordance(data_dir: Path, key: str) -> list[Any]:
    from jason.community.manual import Concordance

    path = Path(data_dir) / "manual" / key / "concordance.json"
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Concordance(**r) for r in raw.get("rows") or []]


def _current_units(data_dir: Path, result: dict[str, Any]) -> list[Any]:
    from jason.community.revision_detection import outline_text, units
    from jason.tasks.revision_detection import cached_read

    cur = next((v for v in result.get("versions") or [] if v["id"] == result.get("current")), None)
    for f in (cur or {}).get("files") or []:
        path = Path(data_dir) / f["path"]
        if path.is_file():
            got = cached_read(Path(data_dir), path, f["sha256"])
            if got.get("text"):
                return units(outline_text(got["text"], key=result["key"]))
    return []


def _docx_of_current(data_dir: Path, result: dict[str, Any]) -> Path | None:
    cur = next((v for v in result.get("versions") or [] if v["id"] == result.get("current")), None)
    for s in (cur or {}).get("sightings") or []:
        if s.get("source") == "drive-revision" and s.get("path", "").endswith(".docx"):
            path = Path(data_dir) / s["path"]
            if path.is_file():
                return path
    return None


def suggestion_contexts(docx: Path) -> list[tuple[str, str, str]]:
    """Each pending suggestion in a Word export of the Doc with the words before it, as the Doc reads inline (the
    Docs API and the outline carry suggested words with the rest): ``(kind, words, before)``."""
    with zipfile.ZipFile(docx) as z:
        body = ElementTree.fromstring(z.read("word/document.xml"))
    out: list[tuple[str, str, str]] = []
    for p in body.iter(f"{_W}p"):
        said: list[str] = []
        for el in p:
            tag = el.tag
            if tag == f"{_W}r":
                said.append("".join(t.text or "" for t in el.iter(f"{_W}t")))
            elif tag in (f"{_W}ins", f"{_W}del"):
                kind = "insert" if tag == f"{_W}ins" else "delete"
                words = "".join(t.text or "" for t in el.iter(f"{_W}t" if kind == "insert" else f"{_W}delText"))
                if words.strip():
                    out.append((kind, " ".join(words.split()), " ".join("".join(said).split())))
                said.append(words)
    return out


def _parent(number: str) -> str:
    m = re.match(r"^(.*)\([^()]+\)$", number)
    return m.group(1) if m else ""


def _adopted_later(u: Unadopted, events: list[Any], rows: list[Any]) -> str:
    """An adoption on record, on or after the change was first saved, naming the section or one that holds it."""
    from jason.community.manual import AdoptionAction, resolve_old

    saved = u.first_saved or u.to_on
    for e in events:
        if e.action is not AdoptionAction.ADOPTED or e.on is None or e.on.isoformat() < saved:
            continue
        for s in e.sections:
            if "#" not in s and s == u.book.split(".")[0]:
                return f"{e.on} ({e.record or e.evidence[:60]})"
            new = s if "#" in s else (resolve_old(rows, s) or "")
            for name in (new, s):
                if not name:
                    continue
                num = name.split("#", 1)[1] if "#" in name else name
                book = name.split("#", 1)[0] if "#" in name else ""
                if book and book != u.book:
                    continue
                if u.number == num or u.number.startswith(num + "(") or u.outline == num \
                        or u.outline.startswith(num + "("):
                    return f"{e.on} ({e.record or e.evidence[:60]})"
    return ""


def partition(data_dir: Path, community: Any) -> Partition:
    """The official rules draft separated into (a), (b), and (c), from the revision history on disk."""
    from jason.community.manual import ManualError
    from jason.tasks import manual as manual_task
    from jason.tasks import revision_detection as rd

    data_dir = Path(data_dir)
    spec = manual_task.spec_of(community)
    key = spec.document
    draft = data_dir / DRAFTS / RULES_DRAFT
    if not draft.is_file():
        raise ManualError(f"no official rules draft at {draft}: run jason manual --render first")
    result = rd.load(data_dir, key)
    if result is None:
        raise ManualError(f"no revision history for {key}: run jason revisions {key} first")
    text = draft.read_text(encoding="utf-8")
    rows = _concordance(data_dir, key)
    outline = manual_task.load_outline(data_dir, key)
    part = Partition(key, outline.title or key, spec.rules_title, result.get("current", ""),
                     (outline.revision or "")[:16], draft, hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
                     concordance=[r.__dict__ for r in rows if r.official])
    names = rd.outline_names(data_dir, key, _current_units(data_dir, result))
    events = manual_task.adoption_history(data_dir, community, spec)
    contexts: list[tuple[str, str, str]] = []
    docx = _docx_of_current(data_dir, result)
    if docx is not None:
        try:
            contexts = suggestion_contexts(docx)
        except (OSError, KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
            part.notes.append(f"the current Doc's Word export could not be read for the suggestions' places: {exc}")
    return separate(part, result, rows, names, events, text, contexts)


def separate(part: Partition, result: dict[str, Any], rows: list[Any], names: dict[str, str], events: list[Any],
             text: str, contexts: list[tuple[str, str, str]] = ()) -> Partition:
    """The separation itself, from what ``partition`` read: the revision history (``result``), the concordance rows,
    the outline's names for the current sections, the adoptions on record, the official rules draft's text, and the
    places of the Doc's suggestions. Pure."""
    now = {lin["id"]: lin for lin in result.get("lineages") or []}
    by_old: dict[str, list[Any]] = {}
    for r in rows:
        by_old.setdefault(r.old, []).append(r)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for c in result.get("changes") or []:
        if not c.get("finding") or c["kind"] not in WORD_CHANGES:
            continue
        grouped.setdefault(c["lineage"], []).append(c)
    stream = _stream(text)
    for lineage, all_changes in grouped.items():
        all_changes.sort(key=lambda c: c["toOn"])
        lin = now.get(lineage) or {}
        place = _place(lin, all_changes[-1], names, rows, by_old)
        if place is None:
            last = all_changes[-1]
            part.unplaced.append({"lineage": lineage, "kind": last["kind"], "number": lin.get("current")
                                  or last["numberBefore"], "toOn": last["toOn"],
                                  "words": (last["after"] or last["before"])[:120]})
            continue
        old, piece = place
        if piece.new.startswith("manual#") or piece.kind == "guidance":
            part.guidance += 1
            continue
        # A change a later adoption on record names is cured (a); the changes after the last such adoption are (b).
        changes: list[dict[str, Any]] = []
        for c in all_changes:
            probe = _unadopted(lineage, piece, old, [c], lin, stream)
            cured = _adopted_later(probe, events, rows)
            if cured:
                part.cured.append((probe, cured))
                changes = []            # an adoption covers the words as they then stood: start again after it
            else:
                changes.append(c)
        if changes:
            part.unadopted.append(_unadopted(lineage, piece, old, changes, lin, stream))
    part.unadopted.sort(key=lambda u: (not u.official, u.address, u.to_on))
    _suggestions(part, result, text, list(contexts))
    return part


def _place(lin: dict[str, Any], last: dict[str, Any], names: dict[str, str], rows: list[Any],
           by_old: dict[str, list[Any]]) -> tuple[str, Any] | None:
    """Where a lineage's piece went: the concordance row for the section the outline names it, or, for a section that
    is gone, the row for the number it last had, else the section that held it."""
    from jason.community.manual import resolve_old

    current = lin.get("current", "")
    old = names.get(current, "") if current else ""
    if old:
        pieces = by_old.get(old, [])
        if pieces:
            return old, next((p for p in pieces if p.official), pieces[0])
        return None
    number = (lin.get("numbers") or [last["numberBefore"]])[-1] or last["numberBefore"]
    for name in (number, _parent(number)):
        new = resolve_old(rows, name) if name else ""
        if new:
            row = next((r for r in rows if r.new == new), None)
            if row is not None:
                return name, row
    return None


def _unadopted(lineage: str, piece: Any, old: str, changes: list[dict[str, Any]], lin: dict[str, Any],
               stream: str) -> Unadopted:
    first, last = changes[0], changes[-1]
    gone = not lin.get("current") and last["kind"] == "removed"
    after = "" if gone else last["after"]
    ops = tuple((o.get("before", ""), o.get("after", "")) for c in changes for o in c.get("ops") or []
                if not o.get("noise"))
    return Unadopted(lineage, piece.new, old, piece.official, "removed" if gone else last["kind"],
                     tuple(dict.fromkeys(f for c in changes for f in c["flags"])), first["before"], after,
                     first["fromOn"], last["toOn"], (first.get("firstSaved") or "")[:10], last["finding"], len(changes),
                     (_stream(after) in stream) if after else None, ops=ops)


def _suggestions(part: Partition, result: dict[str, Any], text: str, contexts: list[tuple[str, str, str]]) -> None:
    for s in result.get("suggestions") or []:
        before = next((b for k, w, b in contexts if k == s["kind"] and w == s["words"]), "")
        span = _find_words(text, s["words"], before)
        contained = _norm(s["words"]) in _norm(text)
        found: bool | None = True if span else (False if not contained else
                                                (True if len(_tokens(s["words"])) >= 4 else None))
        part.suggestions.append(Suggestion(s["kind"], s["words"], s.get("since") or "", found,
                                           " ".join(before.split()[-8:])))
    # A changed passage whose new words are a pending insertion is not adopted text at all: the Doc never accepted it.
    inserts = [_norm(s.words) for s in part.suggestions if s.kind == "insert" and len(_tokens(s.words)) >= 4]
    part.unadopted = [replace(u, suggested=any(w in _norm(u.after) and w not in _norm(u.before) for w in inserts))
                      for u in part.unadopted]


# --- Enclosure A: the official rules, with pending insertions struck -------------------------------------------------

def enclosure(part: Partition) -> tuple[str, list[Suggestion]]:
    """The official rules draft with each pending insertion it carries struck through and labeled. A deletion the Doc
    suggests is left in: its words are the text until a person accepts the suggestion."""
    text = part.draft.read_text(encoding="utf-8")
    spans: list[tuple[int, int, Suggestion]] = []
    for s in part.suggestions:
        if s.kind != "insert" or not s.in_draft:
            continue
        span = _find_words(text, s.words, s.where)
        if span:
            spans.append((span[0], span[1], s))
    out, at, done = [], 0, []
    for start, end, s in sorted(spans, key=lambda x: x[0]):
        if start < at:
            continue
        out.append(text[at:start])
        out.append(f"~~{text[start:end]}~~ [a pending suggestion in the working Doc, never accepted: not part of the "
                   "text]")
        at = end
        done.append(s)
    out.append(text[at:])
    struck = {id(s) for s in done}
    part.suggestions = [Suggestion(s.kind, s.words, s.since, s.in_draft, s.where, id(s) in struck)
                        for s in part.suggestions]
    return "".join(out), done


# --- The rule change --------------------------------------------------------------------------------------------------

LONG = 400        # a passage longer than this is named by its changed words in the notice; its text is in Enclosure A


def _caption(u: Unadopted) -> str:
    """The passage's caption ("Common Area Damage"), else its first words."""
    words = re.sub(r"^\s*(?:[A-Z]{1,2}-\d+|[A-Z]|\(?[a-z0-9]{1,3}\))[.)]?\s+", "", (u.after or u.before).strip())
    m = re.match(r"^((?:[A-Z][A-Z,'&/-]*\s+){0,6}[A-Z][A-Z,'&/-]+)(?=\s+(?:[A-Z]{1,2}-\d|[A-Z][a-z])|\s*$)", words)
    if m and len(m.group(1)) > 3:
        return m.group(1).strip().title()
    first = words.split()
    return " ".join(first[:8]) + (" ..." if len(first) > 8 else "")


def rule_change(part: Partition, *, book_titles: dict[str, str] | None = None) -> RuleChange:
    """The publication as a ``RuleChange``: its sections are the (b) changes, each proposing the words now in the
    manual; the whole text is the official rules document (Enclosure A). The purpose and effect are a draft for the
    board to adopt as its own description."""
    titles = book_titles or {}
    sections = []
    for u in part.unadopted:
        label = u.number or u.address
        sections.append(SectionChange(label, _caption(u), proposed=u.after, repeal=not u.after,
                                      note=f"{titles.get(u.book.split('.')[0], u.book)}; {u.kind} between {u.from_on} "
                                           f"and {u.to_on}, first saved {u.first_saved or u.to_on}: {u.finding}"))
    rules = part.rules_title
    purpose = (f"[Draft for the Board.] To publish the operating rules the Board has adopted as their own document, the "
               f"{rules}, apart from the guidance, contacts, and copies of other documents in the {part.title}, so "
               f"that members can see which words bind them; and to adopt, or restore, the words in the "
               f"{part.title} that were changed with no adoption found in the Board's records.")
    effect = (f"[Draft for the Board.] The {rules} keep the words and the numbers they have in the {part.title}; a "
              f"concordance shows where each section went, so a citation of the manual still finds its rule. The "
              f"guidance stays in the {part.title} and binds no one. The policies bound in the manual are published "
              f"as their own documents and are not changed by this notice except as Part 3 says. "
              f"{len(part.official)} passages of the rules and {len(part.other_rules)} of the policies bound in the "
              f"manual read differently from the earlier words shown with them; if the Board adopts this change, the "
              f"words now in the manual are the rules from the effective date.")
    return RuleChange(key="official-rules", title=f"Publishing the {rules} as their own document",
                      document=part.document, document_title=rules, purpose=purpose, effect=effect,
                      sections=tuple(sections),
                      decisions=("whether to adopt each changed passage in Part 2 and Part 3 as now written, or to "
                                 "restore the earlier words",
                                 "[effective date]",
                                 "whether the policies bound in the manual are noticed here or in their own notice"),
                      caveats=("DRAFT for the board.", "Nothing is sent: a person addresses and delivers the notice.",
                               "\"No adoption found\" is a finding for a person, not proof that none happened.",
                               "Counsel reads it before it goes out."),
                      authorities=("CIV 4340", "CIV 4355", "CIV 4360", "CIV 4365"))


def _plain(text: str) -> str:
    from jason.tasks.rule_change import _plain as plain_

    return plain_(text)


def text_part(part: Partition, *, book_titles: dict[str, str] | None = None) -> list[str]:
    """The text of the proposed rule change, as the member notice prints it: the whole document enclosed, then each
    changed passage with its earlier words and the words proposed."""
    titles = book_titles or {}
    lines = ["", _plain(f"Part 1. The {part.rules_title}, enclosed in full (Enclosure A), proposed as the operating "
                        f"rules. Their words are the rules as printed in the {part.title} (revision {part.revision}), "
                        f"with the guidance, the copies of other documents, and the separately published policies "
                        f"left out; each rule keeps its number. Enclosure B, the concordance, shows where each "
                        f"section of the {part.title} went.")]
    for heading, rows in ((f"Part 2. Passages of the {part.rules_title} that changed with no adoption found in the "
                           f"Board's records. The Board proposes the words now in the {part.title}; it may instead "
                           f"restore the earlier words.", part.official),
                          ("Part 3. Passages of the policies bound in the manual that changed with no adoption found. "
                           "The same choice applies.", part.other_rules)):
        if not rows:
            continue
        lines += ["", _plain(heading)]
        for u in rows:
            where = titles.get(u.book.split(".")[0], u.book)
            lines += ["", f"{where}, {u.number or u.address} ({_caption(u)}):"]
            if u.suggested:
                lines += [_plain("Some of the words now in the manual are a suggestion in the working copy that was "
                                 "never accepted; they are struck in Enclosure A. Adopting them is the Board's choice.")]
            if u.official and len(u.before) + len(u.after) > 2 * LONG and u.ops:
                # A long passage (an article with its sections): the words that changed, and the whole in Enclosure A.
                lines += [_plain(f"Since the version of {u.from_on}: " + "; ".join(u.changed_words()) + ". The "
                                 "passage as proposed is in Enclosure A.")]
                continue
            lines += [f"Earlier words (the version of {u.from_on}):", _plain(u.before) or "[none: the passage is new]"]
            if u.after:
                lines += [f"Words now in the {part.title} (proposed):", _plain(u.after)]
            else:
                lines += ["Proposed: the passage stays removed, as it is now."]
    return lines


def adopted_part(part: Partition) -> list[str]:
    return ["", _plain(f"The {part.rules_title}, as adopted, are enclosed in full. [Replace any passage in Part 2 or "
                       f"Part 3 the Board did not adopt as noticed with the words it adopted, from the minutes.]")]


# --- The page ---------------------------------------------------------------------------------------------------------

def proposed(part: Partition, notice_date: date, book: str = "rules"):
    from jason.community.revisions import RecordVersion, Stage

    return RecordVersion(book, "", Stage.PROPOSED, notice_date, None,
                         f"data/{DRAFTS}/{RULES_DRAFT} (sha256 {part.digest}, from {part.document} revision "
                         f"{part.revision})",
                         "the notice of the proposed rule change (Civil Code 4360(a))",
                         "the official rules as proposed: not in force; cited as itself, never merged into the text "
                         "in force")


def _q(text: str, limit: int = 500) -> str:
    w = " ".join((text or "").split())
    w = (w[:limit] + " ...") if len(w) > limit else w
    return "> " + (w or "[none]")


def render(part: Partition, when: Any, association: str, schedule: Any = None, *, law: dict[str, str] | None = None,
           book_titles: dict[str, str] | None = None, book: str = "rules") -> str:
    from jason.tasks import rule_change as rc

    change = rule_change(part, book_titles=book_titles)
    version = proposed(part, when.notice_date, book)
    body, struck = enclosure(part)
    notice = rc.member_notice(change, when, {}, association, schedule, law=law,
                              text_part=text_part(part, book_titles=book_titles))
    adopted = rc.adoption_notice(change, when, association, law=law, text_part=adopted_part(part))
    titles = book_titles or {}
    lines = [f"# Rule change: {change.title}", "",
             "**" + " ".join(change.caveats) + "**", "",
             f"The text of the proposed rule change is the official {part.rules_title} extracted from the "
             f"{part.title} (`data/{DRAFTS}/{RULES_DRAFT}`, sha256 {part.digest}), as the stage version "
             f"`{version.book}{version.label()}` (`{rc.version_address(version)}`): {version.note}.", "",
             "## What the text is", "",
             f"Read from the revision history (`jason revisions {part.document}`, current version {part.current}).", "",
             f"- **(a) As adopted, or unchanged since the earliest version on disk:** every passage not listed below. "
             f"{len(part.cured)} passages changed with no adoption found at the time but a later adoption on record "
             f"names their section; they count here.",
             f"- **(b) Changed with no adoption found:** {len(part.official)} in the {part.rules_title}, "
             f"{len(part.other_rules)} in the policies bound in the manual. Each is in the notice with its earlier words "
             f"and the words proposed.",
             f"- **(c) Pending suggestions in the working Doc:** {len(part.suggestions)}, never accepted: not part of the "
             f"proposed text.", ""]
    carried_b = [u for u in part.official if u.in_draft]
    carried_c = [s for s in part.suggestions if s.in_draft]
    lines += ["### What the official rules draft carries that it should not, or not unlabeled", "",
              f"- (b) words: {len(carried_b)} of the {len(part.official)} changed passages of the rules are in the draft "
              f"as plain rule text, with nothing to say no adoption was found. This notice is how they are adopted or "
              f"restored.",
              f"- (c) words: {len([s for s in carried_c if s.kind == 'insert'])} suggested insertions are in the draft "
              f"as if accepted (the outline the draft is rendered from reads the Doc with its suggestions inline, so "
              f"an insertion proposed and the words it would delete both appear); {len(struck)} are struck from "
              f"Enclosure A below, and any other is listed for a person. The "
              f"{len([s for s in carried_c if s.kind == 'delete'])} suggested deletions in the draft are right to be "
              f"there: the words stand until a person accepts the suggestion. The fix belongs in the outline reader "
              f"(read the Doc without its suggestions), not here.", ""]
    for p_ in part.notes:
        lines.append(f"- Note: {p_}")
    lines += ["", "## (b) The passages changed with no adoption found", ""]
    for u in part.unadopted:
        where = titles.get(u.book.split(".")[0], u.book)
        lines += [f"### {u.address} ({where}){' : official rules' if u.official else ''}", "",
                  f"- {u.kind}" + (f" [{', '.join(u.flags)}]" if u.flags else "") + f"; {u.steps} change(s) between "
                  f"{u.from_on} and {u.to_on}, first saved {u.first_saved or u.to_on}; the manual's {u.outline}.",
                  f"- Finding: {u.finding}.",
                  f"- In the official rules draft: {'yes' if u.in_draft else ('no' if u.in_draft is False else 'removed')}.",
                  *(["- The new words include a pending suggestion (c): the Doc never accepted them, so they are "
                     "struck from Enclosure A; adopting them is the Board's choice like any other."]
                    if u.suggested else []),
                  *([f"- What changed: {'; '.join(u.changed_words())[:600]}."] if u.ops else []),
                  "", "Earlier words:", "", _q(u.before), "", "Words now in the manual (proposed):", "",
                  _q(u.after) if u.after else "> [removed]", ""]
    if part.cured:
        lines += ["## Changed, then adopted later (counted as (a))", "",
                  "| Address | Changed | Adopted later |", "|---|---|---|"]
        lines += [f"| {u.address} | {u.from_on} to {u.to_on} | {when_} |" for u, when_ in part.cured]
        lines.append("")
    lines += ["## (c) Pending suggestions (not part of the proposed text)", "",
              "| Kind | Words | Since | In the draft | Struck from Enclosure A |", "|---|---|---|---|---|"]
    for s in part.suggestions:
        seen = {True: "yes", False: "no", None: "too short to say by words: check by hand"}[s.in_draft]
        lines.append(f"| {s.kind} | {s.words[:90].replace('|', '/')} | {s.since} | {seen} | "
                     f"{'yes' if s.struck else ('n/a: a deletion stays until accepted' if s.kind == 'delete' else 'no')} |")
    if part.unplaced:
        lines += ["", f"{len(part.unplaced)} changes with no adoption found could not be placed in the concordance "
                      "(a section the outline does not name); a person places them:", ""]
        lines += [f"- {x['number']} ({x['kind']}, {x['toOn']}): {x['words']}" for x in part.unplaced]
    lines += ["", f"{part.guidance} changed passages are guidance only (left in the manual) and need no notice.", ""]
    lines += ["## Timeline (Civil Code 4360)", "",
              "| Step | Date |", "|---|---|",
              f"| Member notice goes out | {when.notice_date} |",
              f"| Members' written comments due | {when.comment_deadline} |",
              f"| Agenda and meeting notice out (4920(a)) | {when.agenda_notice_by} |",
              f"| **Board decides** (4360(b)) | **{when.decision}** |",
              f"| Notice of the adopted change, at the latest (4360(c)) | {when.adoption_notice_by} |", ""]
    lines += ["## (a) Member notice of the proposed rule change (4360(a))", "",
              f"Subject: {notice.subject}", "", "```text", notice.text, "```", ""]
    lines += rc.element_lines("rule-change-proposed", notice.text) + [""]
    lines += ["## (b) Agenda item for the decision meeting", "", rc.agenda_item(change, when), "",
              "## (c) Notice of the adopted rule change (4360(c)), template", "",
              f"Subject: {adopted.subject}", "", "```text", adopted.text, "```", ""]
    lines += rc.element_lines("rule-change-adopted", adopted.text) + [""]
    if law:
        lines += ["## The law, recited from data/authorities", ""]
        for citation, words in law.items():
            lines += [f"**{citation}:** \"{words}\"", ""]
    lines += ["## Enclosure A: the text of the proposed rule change", "",
              "_Rendered by `jason manual --render`; pending insertions struck. A bracketed note is editorial, not part "
              "of the rules._", "", body.strip(), "",
              "## Enclosure B: the concordance (the manual's number to the rules' number)", "",
              "| The manual | The rules | Status |", "|---|---|---|"]
    for r in part.concordance:
        lines.append(f"| {str(r['old']).replace('|', '/')} | {r['new']} | {r['status']} |")
    return "\n".join(lines).rstrip() + "\n"


def write(data_dir: Path, notice_date: date, markdown: str) -> Path:
    path = Path(data_dir) / DRAFTS / f"rule-change-official-rules-{notice_date.isoformat()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return path


__all__ = ["Partition", "Suggestion", "Unadopted", "adopted_part", "enclosure", "partition", "proposed", "render",
           "rule_change", "separate", "suggestion_contexts", "text_part", "write"]
