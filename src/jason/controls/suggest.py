"""The suggestion reader: the governing documents' duties and limits, matched to the control types that govern them.

``suggest(community, documents, duties_read=...)`` reads each section the documents hold as stored text and decides, with
the general phrases each ``ControlType`` declares as its ``evidence`` (``jason.controls.catalog``), whether the section sets
a duty or a limit a control could add to. A match is a ``Suggestion``; it is never an adoption. A suggestion carries:

- the provision's citation and its words, whole and verbatim, as stored (``basis``), never retyped;
- the floor the provision sets, read only where the type declares an extractor and one count is certain (a count word next
  to "signed by", every read agreeing, no alternative after it); otherwise ``None``, and a person reads the floor;
- jason's proposal for the parameters, labeled as a proposal and never below the floor, with the parameters it leaves to
  the board (an amount or a period is never invented);
- jason's reading, labeled as jason's, with the phrases that matched.

A weak match (the phrases are in the section but not in one sentence, or the section reads two ways) is a *question*
(``Suggestion.question``): shown as a question for the board or counsel, not as a suggestion, and never recorded as a
control. A section whose words changed since a control was recorded from it is flagged (``Suggestion.changed``), and the
control stays as the board left it.

The reader runs only after the profile says the duties were read (``duties_read``); without that it returns nothing and
says why (``Suggestions.reason``). ``record`` appends the suggestions to the act log as ``suggested`` acts by jason. It
writes no other state: the questions and the changed provisions are kept in ``controls/readings.json`` for the screen.
Importing this module loads no profile and reads no file.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Protocol

from jason.controls import catalog
from jason.controls.types import (Basis, Control, ControlAct, ControlRefused, ControlState, ControlType, Evidence,
                                  ParamKind, Scope, normalize, parameters_to_dict, stricter)

QUESTION_MAX_CHARS = 2400          # a longer section (an article) is read by its parts; it is not itself a question
MIN_CHARS = 30
LABEL = "jason's reading, not the provision"
NOT_READ = ("the documents' duties have not been read and confirmed by a person, so jason suggests no control: a "
            "provision it misread would be suggested as if it were read")
FLOOR_BY_A_PERSON = "floor: read by a person"
READINGS = "readings.json"

_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


def digest_of(words: str) -> str:
    """The digest of a provision's words, as ``SectionText.digest`` makes it (whitespace folded), so a stored digest and a
    section's agree."""
    return hashlib.sha256(re.sub(r"\s+", " ", words or "").strip().encode("utf-8")).hexdigest()[:16]


# --- the documents ------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Provision:
    """One section of a governing document, as stored: its words whole (with its subsections')."""

    document: str
    number: str
    citation: str
    words: str
    depth: int = 1

    @property
    def digest(self) -> str:
        return digest_of(self.words)


class Documents(Protocol):
    """Anything that gives the sections to read. ``ShelfDocuments`` is the real one; a test gives a list."""

    def provisions(self) -> Iterable[Provision]: ...


class ShelfDocuments:
    """The profile's governing documents as the cite shelf reads them: a document kept as amended in its current words, any
    other from its outline on disk. An amendment is not read on its own (its words are in the document it amends). A
    section that cannot be read is named in ``unread``, never skipped silently."""

    def __init__(self, community: Any = None, data_dir: Path | None = None, keys: Iterable[str] = ()):
        self.community = community
        self.data_dir = data_dir
        self.keys = tuple(keys)
        self.unread: list[str] = []

    def provisions(self) -> Iterator[Provision]:
        from jason.community.section_refs import SectionRefError, citation_of
        from jason.tasks.section_refs import DiskResolver, is_article

        resolver = DiskResolver(self.data_dir, self.community)
        keys = list(self.keys) or self._keys(resolver)
        for key in keys:
            try:
                doc, _ = resolver.document(key)
                name = resolver.name(key)
            except SectionRefError as exc:
                self.unread.append(f"{key}: {exc}")
                continue
            for p in doc.provisions:
                if not p.number or p.removed:
                    continue
                words = doc.text_of(p.number)
                if words.strip():
                    yield Provision(key, p.number, citation_of(name, p.number, article=is_article(p)), words, p.depth)

    def _keys(self, resolver: Any) -> list[str]:
        keys = [k for k in resolver.keys() if not getattr(resolver.citable(k), "amends", "")]
        folder = Path(resolver.data_dir) / "outlines"
        if folder.is_dir():
            on_disk = sorted(p.stem for p in folder.glob("*.json") if p.stem != "references")
            keys += [k for k in on_disk if k not in keys and not getattr(resolver.citable(k), "amends", "")]
        return keys


# --- the result ---------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Suggestion:
    """One match, or one question. ``key`` is the control's key (empty for a question: it is not a control)."""

    key: str
    type_key: str
    document: str
    number: str
    basis: Basis                                  # the citation, the words whole, the floor the provision sets
    floor_note: str                               # "floor: read by a person", or what was read and from which words
    parameters: Mapping[str, Any]                 # jason's proposal, normalized; labeled as one wherever it is shown
    left_to_board: tuple[str, ...]                # the parameters only the board sets
    reading: str                                  # jason's reading, labeled
    matched: tuple[tuple[str, str], ...]          # (what jason looked for, the words that matched)
    digest: str
    question: bool = False
    why_question: str = ""
    changed: bool = False
    was_words: str = ""
    prior_state: str = ""

    @property
    def type(self) -> ControlType:
        return catalog.get(self.type_key)

    @property
    def floor(self) -> Mapping[str, Any] | None:
        """What the provision sets as data, or None where jason did not read one (a person does)."""
        return dict(self.basis.floor) if self.basis.floor else None

    def control(self) -> Control:
        """The control this suggests, in the state *suggested*; nothing here adopts it."""
        return Control(self.key, self.type, dict(self.parameters), Scope(), self.basis, self.reading,
                       ControlState.SUGGESTED)

    def as_dict(self) -> dict[str, Any]:
        ctype = self.type
        return {"key": self.key, "type": ctype.key, "title": ctype.title, "family": ctype.family.value,
                "document": self.document, "number": self.number, "citation": self.basis.citation,
                "words": self.basis.words, "floor": _plain(ctype, self.floor) if self.floor else None,
                "floorNote": self.floor_note, "parameters": parameters_to_dict(ctype, self.parameters),
                "boardSets": list(self.left_to_board), "reading": self.reading, "readingLabel": LABEL,
                "matched": [{"cue": c, "words": w} for c, w in self.matched], "digest": self.digest,
                "question": self.question, "whyQuestion": self.why_question, "changed": self.changed,
                "wasWords": self.was_words, "priorState": self.prior_state}


def _plain(ctype: ControlType, floor: Mapping[str, Any]) -> dict[str, Any]:
    return parameters_to_dict(ctype, floor)


class Suggestions(list):
    """The suggestions (and questions) in document order. An empty answer says why in ``reason``."""

    def __init__(self, items: Iterable[Suggestion] = (), *, reason: str = "", known: int = 0,
                 unread: Iterable[str] = ()):
        super().__init__(items)
        self.reason = reason
        self.known = known                  # sections that match a control already recorded from the same words
        self.unread = list(unread)          # sections or documents that could not be read

    @property
    def questions(self) -> list[Suggestion]:
        return [s for s in self if s.question]

    @property
    def suggested(self) -> list[Suggestion]:
        return [s for s in self if not s.question]


# --- matching -----------------------------------------------------------------------------------------------------------

def _sentences(text: str) -> list[str]:
    out: list[str] = []
    for line in re.split(r"\n+", text or ""):
        out += [s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if s.strip()]
    return out


def _search(pattern: str, text: str) -> re.Match[str] | None:
    return re.search(pattern, text, re.I)


@dataclass(frozen=True)
class _Hit:
    ctype: ControlType
    provision: Provision
    strong: bool
    matched: tuple[tuple[str, str], ...]
    sentences: tuple[str, ...]            # the sentences that matched (strong); the whole section otherwise
    evidence: Evidence


def _trim(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= 80 else text[:77] + "..."


def _found(evidence: Evidence, text: str) -> tuple[tuple[str, str], ...] | None:
    """The phrases that matched, one for each cue, when every cue is in ``text`` and no turning-away cue is."""
    got = []
    for cue in evidence.cues:
        m = _search(cue.pattern, text)
        if m is None:
            return None
        got.append((cue.name, _trim(m.group(0))))
    if any(_search(u.pattern, text) for u in evidence.unless):
        return None
    return tuple(got)


def _match(provision: Provision, ctype: ControlType) -> _Hit | None:
    if len(provision.words.strip()) < MIN_CHARS:
        return None
    sentences = _sentences(provision.words)
    weak: _Hit | None = None
    for ev in ctype.evidence:
        strong = [(s, _found(ev, s)) for s in sentences]
        strong = [(s, m) for s, m in strong if m is not None]
        if strong:
            return _Hit(ctype, provision, True, strong[0][1], tuple(s for s, _ in strong), ev)
        if weak is None and len(provision.words) <= QUESTION_MAX_CHARS:
            across = _found(ev, provision.words)
            if across is not None:
                weak = _Hit(ctype, provision, False, across, (provision.words,), ev)
    return weak


def _inside(inner: str, outer: str) -> bool:
    return inner != outer and (inner.startswith(outer + "(") or inner.startswith(outer + "."))


def _narrowest(hits: list[_Hit]) -> list[_Hit]:
    """Of nested sections that match one type, the narrowest strong one: a section is dropped when a section inside it matches
    strongly (or both are weak), and a weak match inside a strong one is dropped."""
    keep = []
    for h in hits:
        same = [g for g in hits if g is not h and g.provision.document == h.provision.document]
        inner = [g for g in same if _inside(g.provision.number, h.provision.number)]
        outer = [g for g in same if _inside(h.provision.number, g.provision.number)]
        if any(g.strong or not h.strong for g in inner):
            continue
        if any(g.strong and not h.strong for g in outer):
            continue
        keep.append(h)
    return keep


# --- the floor ------------------------------------------------------------------------------------------------------------

def _count(raw: str) -> int | None:
    raw = raw.lower()
    return _NUMBERS.get(raw) if raw in _NUMBERS else (int(raw) if raw.isdigit() and int(raw) > 0 else None)


def _read_floor(hit: _Hit) -> tuple[dict[str, Any], str, str]:
    """The floor the provision sets, only where it is certain: (data, a sentence saying what was read or why not, and, when
    the section reads two ways about a count, that doubt)."""
    ev, ctype = hit.evidence, hit.ctype
    if not hit.strong or not ev.floor:
        return {}, FLOOR_BY_A_PERSON, ""
    floor: dict[str, Any] = {}
    notes: list[str] = []
    doubt = ""
    for fr in ev.floor:
        spec = ctype.spec(fr.param)
        if spec.kind is not ParamKind.COUNT:
            continue
        values: list[tuple[int, str]] = []
        alternative = False
        for sentence in hit.sentences:
            for pattern in fr.patterns:
                for m in re.finditer(pattern, sentence, re.I):
                    n = _count(m.group("n"))
                    if n is None:
                        continue
                    values.append((n, _trim(m.group(0))))
                    alternative = alternative or bool(re.search(r"\bor\b", sentence[m.start():], re.I))
        if not values:
            notes.append("no count it could read with certainty")
            continue
        counts = sorted({n for n, _ in values})
        if len(counts) > 1:
            doubt = "the section names different counts (" + ", ".join(str(n) for n in counts) + ")"
            notes.append(doubt)
            continue
        if alternative:
            notes.append(f'the count "{values[0][1]}" is followed by an alternative (or)')
            continue
        try:
            floor[fr.param] = normalize(spec, counts[0])
        except ControlRefused as exc:
            notes.append(str(exc))
            continue
        notes.append(f'{fr.param} = {counts[0]}, read from "{values[0][1]}"')
    if floor:
        return floor, "floor: " + "; ".join(n for n in notes if n), doubt
    return {}, FLOOR_BY_A_PERSON + (f" ({'; '.join(notes)})" if notes else ""), doubt


# --- the proposal ---------------------------------------------------------------------------------------------------------

def _proposal(ctype: ControlType, floor: Mapping[str, Any]) -> dict[str, Any]:
    """jason's proposal: the type's own, raised to the provision's floor wherever it names one, and the floor itself where
    the type proposes nothing for that parameter (keep at least what the provision sets)."""
    out: dict[str, Any] = {}
    for key, raw in ctype.proposal.items():
        spec = ctype.spec(key)
        value = normalize(spec, raw)
        if key in floor:
            value = stricter(spec, value, normalize(spec, floor[key]))
        out[key] = value
    for key, raw in floor.items():
        out.setdefault(key, normalize(ctype.spec(key), raw))
    return out


def _say(ctype: ControlType, params: Mapping[str, Any]) -> str:
    bits = []
    for p in ctype.parameters:
        if p.key not in params:
            continue
        v = params[p.key]
        v = ", ".join(r.value for r in v) if isinstance(v, tuple) else ("yes" if v is True else v)
        bits.append(f"{p.title.lower()}: {v}")
    return "; ".join(bits)


def _reading(hit: _Hit, floor_note: str, params: Mapping[str, Any], left: tuple[str, ...], question: str) -> str:
    ctype = hit.ctype
    said = "; ".join(f'{name}: "{text}"' for name, text in hit.matched)
    if question:
        return (f"{LABEL}: this section may speak to {ctype.title.lower()} (it uses {said}), but jason cannot read it "
                f"cleanly: {question}. A question for the board or counsel; no suggestion.")
    mine = _say(ctype, params)
    sets = ", ".join(ctype.spec(k).title.split(" (")[0].lower() for k in left)
    return (f"{LABEL}: this section reads as setting a duty or a limit that the {ctype.title.lower()} control governs "
            f"(it uses {said}). {floor_note[0].upper() + floor_note[1:]}. "
            + (f"jason proposes (a proposal for the board to adopt, change, or decline; not a rule): {mine}. " if mine
               else "jason proposes no value for this one. ")
            + (f"The board sets: {sets}." if sets else ""))


# --- suggest --------------------------------------------------------------------------------------------------------------

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def suggest(community: Any, documents: Documents | Iterable[Provision] | None = None, *, duties_read: bool = False,
            prior: Iterable[Control] | None = None, data_dir: Path | None = None) -> Suggestions:
    """The controls the documents suggest, and the questions they leave, in catalog and document order.

    ``documents`` gives the sections (``Documents``, or a plain list of ``Provision``; default: the profile's governing
    documents on the cite shelf). ``duties_read`` is whether a person confirmed the documents' duties were read: without it
    the answer is empty and ``reason`` says why. ``prior`` are the controls already recorded (default: the store's): a
    section whose words match a control already recorded from it is not suggested again, and one whose words changed is
    returned with ``changed`` set, under that control's key. Reads only; nothing is written."""
    if not duties_read:
        return Suggestions(reason=NOT_READ)
    if prior is None:
        from jason.controls import store

        prior = store.load(data_dir=data_dir, community=community)
    prior = list(prior)
    if documents is None:
        documents = ShelfDocuments(community, data_dir)
    items = documents.provisions() if hasattr(documents, "provisions") else documents
    provisions = list(items)
    hits: list[_Hit] = []
    for ctype in catalog.CATALOG:
        if not ctype.evidence:
            continue
        found = [h for p in provisions if (h := _match(p, ctype)) is not None]
        hits += _narrowest(found)
    order = {t.key: n for n, t in enumerate(catalog.CATALOG)}
    where = {(p.document, p.number): n for n, p in enumerate(provisions)}
    hits.sort(key=lambda h: (order[h.ctype.key], where[(h.provision.document, h.provision.number)]))
    by_cite = {(c.type.key, c.basis.citation): c for c in prior}
    taken = {c.key for c in prior}
    out: list[Suggestion] = []
    known = 0
    for hit in hits:
        p, ctype = hit.provision, hit.ctype
        floor, note, doubt = _read_floor(hit)
        question = not hit.strong or bool(doubt)
        if not hit.strong:
            doubt = ("its phrases are in the section but not in one sentence, so jason cannot tell they speak of the "
                     "same thing")
        params: dict[str, Any] = {}
        if not question:
            params = _proposal(ctype, floor)
            try:
                _checked(ctype, p, params, floor)
            except ControlRefused as exc:
                question, doubt, params, floor = True, str(exc), {}, {}
        left = () if question else tuple(k for k in ctype.board_sets if k not in params)
        reading = _reading(hit, note, params, left, doubt if question else "")
        seen = by_cite.get((ctype.key, p.citation))
        key, changed, was, state = "", False, "", ""
        if not question:
            if seen is not None:
                if not seen.basis.words or digest_of(seen.basis.words) == p.digest:
                    known += 1
                    continue
                key, changed, was, state = seen.key, True, seen.basis.words, seen.state.value
            else:
                key = ctype.key if ctype.key not in taken else f"{ctype.key}-{_slug(p.citation)}"
                taken.add(key)
        out.append(Suggestion(key, ctype.key, p.document, p.number, Basis(p.citation, p.words, dict(floor)),
                              note if not question else "floor: read by a person", params, left, reading, hit.matched,
                              p.digest, question, doubt if question else "", changed, was, state))
    return Suggestions(out, known=known, unread=getattr(documents, "unread", ()))


def _checked(ctype: ControlType, p: Provision, params: Mapping[str, Any], floor: Mapping[str, Any]) -> None:
    """The proposal as a control must pass the same checks an adopted one does (never below a floor); else ``ControlRefused``."""
    from jason.controls.effective import ensure_valid

    ensure_valid(Control(ctype.key, ctype, dict(params), Scope(), Basis(p.citation, p.words, dict(floor))))


# --- recording ----------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Recorded:
    recorded: tuple[str, ...]
    skipped: tuple[tuple[str, str], ...]          # (key, why it was not recorded)
    questions: int
    changed: int


def record(found: Suggestions, *, by: str, data_dir: Path | None = None, community: Any = None, profile: str = "",
           now: datetime | None = None) -> Recorded:
    """Append each new suggestion to the act log as a ``suggested`` act by jason, on the request of ``by``. A question and a
    changed provision are not controls: they are kept for the screen (``controls/readings.json``). Adopts nothing."""
    from jason.controls import store

    by = (by or "").strip()
    if not by:
        raise ValueError("recording suggestions names the person who asked for it (by)")
    now = now or datetime.now(timezone.utc)
    done: list[str] = []
    skipped: list[tuple[str, str]] = []
    for s in found:
        if s.question or s.changed or not s.key:
            continue
        try:
            store.record(ControlAct.SUGGEST, s.key, by="jason", why=f"read from {s.basis.citation} at the request of {by}",
                         control=s.control(), data_dir=data_dir, profile=profile, community=community, now=now)
            done.append(s.key)
        except ControlRefused as exc:
            skipped.append((s.key, str(exc)))
    save_readings(found, by=by, data_dir=data_dir, now=now)
    return Recorded(tuple(done), tuple(skipped), len(found.questions), sum(1 for s in found if s.changed))


def readings_path(data_dir: Path | None = None) -> Path:
    from jason.controls import store

    return store.controls_dir(data_dir) / READINGS


def save_readings(found: Suggestions, *, by: str, data_dir: Path | None = None, now: datetime | None = None) -> Path:
    """The last reading's questions and changed provisions, replacing the one before (a snapshot, not a log)."""
    from jason.locks import Resource, hold

    now = now or datetime.now(timezone.utc)
    body = {"read": now.isoformat(timespec="seconds"), "by": by,
            "questions": [s.as_dict() for s in found if s.question],
            "changed": [s.as_dict() for s in found if s.changed]}
    file = readings_path(data_dir)
    file.parent.mkdir(parents=True, exist_ok=True)
    with hold(Resource.STORE, "controls-readings", timeout=60, purpose="controls: readings"):
        tmp = file.with_suffix(".tmp")
        tmp.write_text(json.dumps(body, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, file)
    return file


def load_readings(data_dir: Path | None = None) -> dict[str, Any]:
    """The last reading's snapshot (empty questions and changes when none was recorded)."""
    file = readings_path(data_dir)
    if not file.is_file():
        return {"read": "", "by": "", "questions": [], "changed": []}
    return json.loads(file.read_text(encoding="utf-8"))


__all__ = ["Documents", "FLOOR_BY_A_PERSON", "LABEL", "NOT_READ", "Provision", "Recorded", "ShelfDocuments", "Suggestion",
           "Suggestions", "digest_of", "load_readings", "readings_path", "record", "save_readings", "suggest"]
