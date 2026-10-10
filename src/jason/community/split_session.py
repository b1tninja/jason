"""The PDF splitter's records (docs/pdf-splitter.md, section 2): a session over one file, the boundaries a person chose, the suggestions
jason made, and the commands that change them. Pure: it reads no file, model, or profile, and imports nothing of an association.

A **boundary** is the first page of a segment; page 1 is always one. A boundary has a ``level`` (0 for a document, 1 or more for a
document inside one: the nested stack). A **suggestion** is jason's guess, with its signals and a reason in words; it is never merged
into the boundaries except by a person's ``accept``. Every change to boundaries or labels is one **command** on an undo stack (a bulk
act is one step), and the draft carries a ``version`` so a second writer is told of a conflict rather than overwriting.

The segments are derived, never stored: ``SplitSession.segments()``.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

STATUSES = ("draft", "confirmed", "applied", "stale", "declined")
SOURCE_KINDS = ("library", "drive", "upload", "path")
BOUNDARY_SOURCES = ("person", "accepted")
SUGGESTION_STATES = ("open", "accepted", "rejected", "edited")
TIERS = ("likely", "suggested")
NESTED_CHOICES = ("inside", "file")          # "take out" is a later phase (docs/pdf-splitter.md, open decision 8)
LABEL_FIELDS = ("title", "kind", "slot", "period", "entry", "nested")
MAX_LEVEL = 3
HISTORY_CAP = 200
HIGH = 0.85
MEDIUM = 0.6


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def band(confidence: float) -> str:
    """The word for a confidence: High (0.85 and above), Medium (0.6 to 0.85), Low (below)."""
    return "High" if confidence >= HIGH else "Medium" if confidence >= MEDIUM else "Low"


class SplitConflict(ValueError):
    """A save made from an older version of the draft than the server holds. ``current`` is the server's draft, for a person to compare."""

    def __init__(self, message: str, current: dict[str, Any] | None = None):
        super().__init__(message)
        self.current = current or {}


# --- per-page facts --------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class PageFact:
    """What is known of one page without drawing it (from the preflight's and the segmentation's readers). ``pending`` is a page
    whose facts are not read yet: only its number and size are known."""

    n: int
    width: float = 0.0                 # points
    height: float = 0.0
    rotation: int = 0
    blank: str = "content"             # content | blank | marked
    has_text: bool = False
    words: int = 0
    chars: int = 0
    dpi: int = 0
    colour: str = ""                   # bilevel | grey | colour
    codec: str = ""
    header: str = ""
    footer: str = ""
    label: tuple[int, int] | None = None     # a printed page number as (n, of): "2 of 7" is (2, 7); (2, 0) when no total is printed
    title: str = ""
    date: str = ""
    lang: str = ""
    lqip: str = ""                     # a 16 by 16 greyscale picture, 256 bytes as hex, for a placeholder
    pending: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items()}
        d["label"] = list(self.label) if self.label else None
        return d

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PageFact":
        fields = {k: raw[k] for k in cls.__dataclass_fields__ if k in raw}
        label = fields.get("label")
        fields["label"] = (int(label[0]), int(label[1])) if label else None
        return cls(**fields)


# --- boundaries and suggestions --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Boundary:
    page: int
    level: int = 0
    by: str = ""
    at: str = ""
    source: str = "person"             # person | accepted
    suggestion: str = ""               # the id of the suggestion a person accepted

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Boundary":
        return cls(**{k: raw[k] for k in cls.__dataclass_fields__ if k in raw})


@dataclass(frozen=True)
class Signal:
    signal: str
    weight: float
    said: str

    def to_dict(self) -> dict[str, Any]:
        return {"signal": self.signal, "weight": round(self.weight, 2), "said": self.said}


@dataclass
class Suggestion:
    id: str
    page: int
    level: int = 0
    confidence: float = 0.0
    tier: str = "suggested"
    signals: list[Signal] = field(default_factory=list)
    why: str = ""
    reader: str = "rules"
    state: str = "open"

    @property
    def band(self) -> str:
        return band(self.confidence)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "page": self.page, "level": self.level, "confidence": round(self.confidence, 3), "band": self.band,
                "tier": self.tier, "signals": [s.to_dict() for s in self.signals], "why": self.why, "reader": self.reader,
                "state": self.state}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Suggestion":
        return cls(str(raw["id"]), int(raw["page"]), int(raw.get("level", 0)), float(raw.get("confidence", 0.0)),
                   str(raw.get("tier", "suggested")),
                   [Signal(str(s["signal"]), float(s["weight"]), str(s.get("said", ""))) for s in raw.get("signals") or ()],
                   str(raw.get("why", "")), str(raw.get("reader", "rules")), str(raw.get("state", "open")))


@dataclass(frozen=True)
class Segment:
    key: str                  # s1, s2 ... for a document; s2.1 for a document inside s2
    start: int
    end: int
    level: int = 0
    parent: str = ""
    source: str = "first"     # first | person | accepted

    @property
    def pages(self) -> int:
        return self.end - self.start + 1

    @property
    def path(self) -> str:
        return f"{self.parent}/{self.key}" if self.parent else self.key

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "path": self.path, "start": self.start, "end": self.end, "pages": self.pages, "level": self.level,
                "parent": self.parent, "source": self.source}


# --- the source ------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Source:
    """The file. ``ref`` is a library id or a held-upload id, never a file name; ``stamp`` is a cheap change check (size and
    modified time of a library file when the session opened)."""

    sha256: str
    size: int
    pages: int
    kind: str = "path"
    ref: str = ""
    confidential: bool = False
    stamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Source":
        return cls(**{k: raw[k] for k in cls.__dataclass_fields__ if k in raw})


def new_id() -> str:
    return secrets.token_hex(4)


# --- the session -----------------------------------------------------------------------------------------------------------

@dataclass
class SplitSession:
    id: str
    source: Source
    status: str = "draft"
    created: str = ""
    updated: str = ""
    by: str = ""
    version: int = 1
    boundaries: list[Boundary] = field(default_factory=list)
    suggestions: list[Suggestion] = field(default_factory=list)
    labels: dict[str, dict[str, str]] = field(default_factory=dict)       # by a segment's first page: title, kind, slot, period, entry, nested
    undo: list[dict[str, Any]] = field(default_factory=list)
    redo: list[dict[str, Any]] = field(default_factory=list)
    confirmed: dict[str, str] = field(default_factory=dict)               # {by, at} of the person who confirmed the apply
    applied: dict[str, Any] = field(default_factory=dict)
    suggested_at: str = ""
    notes: list[str] = field(default_factory=list)

    # --- reading ---

    @property
    def pages(self) -> int:
        return self.source.pages

    def boundary_at(self, page: int) -> Boundary | None:
        return next((b for b in self.boundaries if b.page == page), None)

    def ordered(self) -> list[Boundary]:
        """The boundaries in page order with page 1 always first (a stored draft that lacks it is read as having it)."""
        rows = sorted((b for b in self.boundaries if b.page != 1), key=lambda b: b.page)
        first = self.boundary_at(1) or Boundary(1, 0, self.by, self.created, "person")
        return [Boundary(1, 0, first.by, first.at, first.source, first.suggestion), *rows]

    def segments(self) -> list[Segment]:
        """The ranges the boundaries make. A segment ends the page before the next boundary at its own level or a shallower one; a
        nested segment lies inside its parent, and a parent's range still holds its children's pages."""
        rows = self.ordered()
        out: list[Segment] = []
        counter = 0
        children: dict[str, int] = {}
        stack: list[Segment] = []
        for i, b in enumerate(rows):
            end = self.pages
            for later in rows[i + 1:]:
                if later.level <= b.level:
                    end = later.page - 1
                    break
            while stack and stack[-1].level >= b.level:
                stack.pop()
            if b.level == 0:
                counter += 1
                key, parent = f"s{counter}", ""
            else:
                parent_seg = stack[-1] if stack else None
                parent = parent_seg.key if parent_seg else ""
                children[parent] = children.get(parent, 0) + 1
                key = f"{parent}.{children[parent]}" if parent else f"s0.{children[parent]}"
            seg = Segment(key, b.page, max(b.page, end), b.level, parent, "first" if b.page == 1 else b.source)
            out.append(seg)
            stack.append(seg)
        return out

    def top_segments(self) -> list[Segment]:
        return [s for s in self.segments() if s.level == 0]

    def counts(self) -> dict[str, int]:
        sug = [s for s in self.suggestions if s.state == "open"]
        return {"pages": self.pages, "segments": len(self.top_segments()), "nested": len(self.segments()) - len(self.top_segments()),
                "boundaries": len(self.ordered()), "suggestionsOpen": len(sug), "undo": len(self.undo), "redo": len(self.redo)}

    def label_of(self, page: int) -> dict[str, str]:
        return dict(self.labels.get(str(page), {}))

    # --- the commands ---

    def _check_page(self, page: int) -> int:
        if not isinstance(page, int) or isinstance(page, bool) or page < 1 or page > self.pages:
            raise ValueError(f"page {page} is not in a file of {self.pages} pages")
        return page

    def _check_level(self, level: int) -> int:
        if not isinstance(level, int) or isinstance(level, bool) or level < 0 or level > MAX_LEVEL:
            raise ValueError(f"a level is 0 (a document) to {MAX_LEVEL} (a document inside one inside one)")
        return level

    def _snapshot(self) -> dict[str, Any]:
        return {"b": [b.to_dict() for b in self.boundaries], "l": {k: dict(v) for k, v in self.labels.items()},
                "s": {s.id: s.state for s in self.suggestions}}

    def _restore(self, snap: dict[str, Any]) -> None:
        self.boundaries = [Boundary.from_dict(b) for b in snap["b"]]
        self.labels = {k: dict(v) for k, v in snap["l"].items()}
        for s in self.suggestions:
            if s.id in snap["s"]:
                s.state = snap["s"][s.id]

    def _normalize(self) -> None:
        """Page 1 is a boundary at level 0, one boundary a page, and a level never more than one deeper than the one before."""
        by_page = {b.page: b for b in self.boundaries if 1 <= b.page <= self.pages}
        rows = [Boundary(1, 0, by_page[1].by, by_page[1].at, by_page[1].source, by_page[1].suggestion)] if 1 in by_page else []
        rows += [by_page[p] for p in sorted(by_page) if p != 1]
        if not rows or rows[0].page != 1:
            rows.insert(0, Boundary(1, 0, self.by, self.created or now(), "person"))
        prev = 0
        fixed: list[Boundary] = []
        for b in rows:
            lvl = min(b.level, prev + 1) if fixed else 0
            fixed.append(b if lvl == b.level else Boundary(b.page, lvl, b.by, b.at, b.source, b.suggestion))
            prev = lvl
        self.boundaries = fixed
        self.labels = {k: v for k, v in self.labels.items() if int(k) in {b.page for b in fixed}}

    def _do(self, change: Callable[[], Any], *, by: str = "") -> None:
        """One command: snapshot, change, normalize, push the undo step, clear redo, bump the version."""
        if self.status not in ("draft",):
            raise ValueError(f"this split is {self.status}; only a draft can be changed")
        snap = self._snapshot()
        change()
        self._normalize()
        if self._snapshot() == snap:
            return
        self.undo.append(snap)
        del self.undo[:-HISTORY_CAP]
        self.redo = []
        self.version += 1
        self.updated = now()
        if by:
            self.by = by

    def mark(self, page: int, *, level: int = 0, by: str, at: str = "") -> None:
        """Make ``page`` the first page of a segment (a document at ``level``). Marking a marked page at a new level changes its level."""
        self._check_page(page)
        self._check_level(level)
        if page == 1 and level != 0:
            raise ValueError("The first page always starts a document, at level 0")

        def go() -> None:
            self.boundaries = [b for b in self.boundaries if b.page != page]
            self.boundaries.append(Boundary(page, level, by, at or now(), "person"))
        self._do(go, by=by)

    def unmark(self, page: int, *, by: str = "") -> None:
        self._check_page(page)
        if page == 1:
            raise ValueError("The first page always starts a segment")
        self._do(lambda: setattr(self, "boundaries", [b for b in self.boundaries if b.page != page]), by=by)

    def move(self, source: int, to: int, *, by: str) -> None:
        self._check_page(source)
        self._check_page(to)
        if source == 1:
            raise ValueError("The first page always starts a segment and cannot be moved")
        held = self.boundary_at(source)
        if held is None:
            raise ValueError(f"page {source} does not start a segment")
        if source != to and self.boundary_at(to) is not None:
            raise ValueError(f"page {to} already starts a segment")
        if to == 1:
            raise ValueError("Page 1 already starts the first segment")

        def go() -> None:
            self.boundaries = [b for b in self.boundaries if b.page != source]
            self.boundaries.append(Boundary(to, held.level, by, now(), "person"))
            if str(source) in self.labels:
                self.labels[str(to)] = self.labels.pop(str(source))
        self._do(go, by=by)

    def set_level(self, page: int, level: int, *, by: str) -> None:
        held = self.boundary_at(self._check_page(page))
        if held is None:
            raise ValueError(f"page {page} does not start a segment")
        self.mark(page, level=level, by=by)

    def set_boundaries(self, rows: list[tuple[int, int]] | list[dict[str, Any]], *, by: str) -> None:
        """Replace the person's boundaries with ``rows`` ((page, level) pairs, or dicts): the autosave. One undo step. Accepted
        boundaries that stay keep their record."""
        want: dict[int, int] = {}
        for r in rows:
            page, level = (int(r["page"]), int(r.get("level", 0))) if isinstance(r, dict) else (int(r[0]), int(r[1]) if len(r) > 1 else 0)
            want[self._check_page(page)] = self._check_level(level)
        want.setdefault(1, 0)
        want[1] = 0
        held = {b.page: b for b in self.boundaries}

        def go() -> None:
            out = []
            for p, lvl in want.items():
                old = held.get(p)
                out.append(old if old is not None and old.level == lvl else Boundary(p, lvl, by, now(), "person"))
            self.boundaries = out
        self._do(go, by=by)

    def clear(self, pages: list[int] | None = None, *, by: str) -> int:
        """Remove the person's boundaries on ``pages`` (all but page 1 when None). Returns how many were removed."""
        targets = {p for p in (pages if pages is not None else [b.page for b in self.boundaries]) if p != 1}
        for p in targets:
            self._check_page(p)
        n = len([b for b in self.boundaries if b.page in targets])
        self._do(lambda: setattr(self, "boundaries", [b for b in self.boundaries if b.page not in targets]), by=by)
        return n

    def mark_range(self, first: int, last: int, *, every: int = 1, level: int = 0, by: str) -> int:
        """Mark every ``every``-th page from ``first`` to ``last`` as a start ("these are all two-page letters"). Pages already
        marked are kept. Returns how many were added."""
        self._check_page(first)
        self._check_page(last)
        if every < 1 or first > last:
            raise ValueError("a range runs from a first page to a later one, marking every 1st page or more")
        self._check_level(level)
        added = [p for p in range(first, last + 1, every) if self.boundary_at(p) is None and p != 1]

        def go() -> None:
            self.boundaries += [Boundary(p, level, by, now(), "person") for p in added]
        self._do(go, by=by)
        return len(added)

    def label(self, page: int, name: str, value: str, *, by: str = "") -> None:
        """A guess or a choice for the segment that starts at ``page``: its title, kind, slot, period, entry, or ``nested`` (inside | file)."""
        self._check_page(page)
        if name not in LABEL_FIELDS:
            raise ValueError(f"a label is one of {', '.join(LABEL_FIELDS)}")
        if self.boundary_at(page) is None and page != 1:
            raise ValueError(f"page {page} does not start a segment")
        text = " ".join(str(value or "").split())[:200]
        if name == "nested" and text and text not in NESTED_CHOICES:
            raise ValueError("a nested segment stays inside its parent or is also made a file (inside | file); taking it out comes later")

        def go() -> None:
            row = dict(self.labels.get(str(page), {}))
            if text:
                row[name] = text
            else:
                row.pop(name, None)
            if row:
                self.labels[str(page)] = row
            else:
                self.labels.pop(str(page), None)
        self._do(go, by=by)

    def accept(self, suggestion_id: str, *, by: str) -> Boundary:
        s = self._suggestion(suggestion_id)
        if s.state == "accepted":
            return self.boundary_at(s.page) or Boundary(s.page)

        def go() -> None:
            self.boundaries = [b for b in self.boundaries if b.page != s.page]
            self.boundaries.append(Boundary(s.page, s.level, by, now(), "accepted", s.id))
            s.state = "accepted"
        self._do(go, by=by)
        return self.boundary_at(s.page) or Boundary(s.page)

    def reject(self, suggestion_id: str, *, by: str = "") -> None:
        s = self._suggestion(suggestion_id)

        def go() -> None:
            s.state = "rejected"
        self._do(go, by=by)

    def accept_all(self, *, minimum: float = HIGH, by: str) -> int:
        """Accept every open suggestion at ``minimum`` confidence or better, as one undo step. A model-only suggestion is never taken."""
        chosen = [s for s in self.suggestions if s.state == "open" and s.confidence >= minimum and s.reader != "model"]

        def go() -> None:
            for s in chosen:
                self.boundaries = [b for b in self.boundaries if b.page != s.page]
                self.boundaries.append(Boundary(s.page, s.level, by, now(), "accepted", s.id))
                s.state = "accepted"
        self._do(go, by=by)
        return len(chosen)

    def _suggestion(self, suggestion_id: str) -> Suggestion:
        found = next((s for s in self.suggestions if s.id == suggestion_id), None)
        if found is None:
            raise KeyError(suggestion_id)
        return found

    def do_undo(self, *, by: str = "") -> bool:
        if self.status != "draft":
            raise ValueError(f"this split is {self.status}; only a draft can be changed")
        if not self.undo:
            return False
        self.redo.append(self._snapshot())
        self._restore(self.undo.pop())
        self._normalize()
        self.version += 1
        self.updated = now()
        return True

    def do_redo(self, *, by: str = "") -> bool:
        if self.status != "draft":
            raise ValueError(f"this split is {self.status}; only a draft can be changed")
        if not self.redo:
            return False
        self.undo.append(self._snapshot())
        self._restore(self.redo.pop())
        self._normalize()
        self.version += 1
        self.updated = now()
        return True

    def replace_suggestions(self, fresh: list[Suggestion]) -> None:
        """jason's new guesses replace the old ones; a person's boundaries are never touched. A page a person rejected stays
        rejected, and a page already a boundary is marked accepted-by-hand rather than offered again."""
        before = {s.page: s for s in self.suggestions}
        marked = {b.page for b in self.boundaries}
        out = []
        for s in fresh:
            old = before.get(s.page)
            if old is not None and old.state in ("rejected", "edited"):
                s.state = old.state
            elif s.page in marked:
                s.state = "accepted"
            out.append(s)
        self.suggestions = out
        self.suggested_at = now()
        self.updated = now()

    # --- storage ---

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "id": self.id, "source": self.source.to_dict(), "status": self.status, "created": self.created,
                "updated": self.updated, "by": self.by, "boundaries": [b.to_dict() for b in self.boundaries],
                "suggestions": [s.to_dict() for s in self.suggestions], "labels": self.labels, "undo": self.undo, "redo": self.redo,
                "confirmed": self.confirmed, "applied": self.applied, "suggestedAt": self.suggested_at, "notes": self.notes}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SplitSession":
        return cls(str(raw["id"]), Source.from_dict(raw["source"]), str(raw.get("status", "draft")), str(raw.get("created", "")),
                   str(raw.get("updated", "")), str(raw.get("by", "")), int(raw.get("version", 1)),
                   [Boundary.from_dict(b) for b in raw.get("boundaries") or ()],
                   [Suggestion.from_dict(s) for s in raw.get("suggestions") or ()],
                   {str(k): dict(v) for k, v in (raw.get("labels") or {}).items()}, list(raw.get("undo") or ()),
                   list(raw.get("redo") or ()), dict(raw.get("confirmed") or {}), dict(raw.get("applied") or {}),
                   str(raw.get("suggestedAt", "")), list(raw.get("notes") or ()))

    def view(self, *, mask: bool = False) -> dict[str, Any]:
        """The session as a screen or a command reads it: no file name, ever (``ref`` is an id). ``mask`` hides the library ref of a
        confidential file."""
        src = self.source.to_dict()
        if mask:
            src["ref"] = ""
        return {"id": self.id, "status": self.status, "version": self.version, "created": self.created, "updated": self.updated,
                "by": self.by, "source": src, "counts": self.counts(), "boundaries": [b.to_dict() for b in self.ordered()],
                "segments": [{**s.to_dict(), "labels": self.label_of(s.start)} for s in self.segments()],
                "suggestions": [s.to_dict() for s in self.suggestions], "confirmed": self.confirmed, "applied": self.applied,
                "suggestedAt": self.suggested_at, "notes": list(self.notes)}
