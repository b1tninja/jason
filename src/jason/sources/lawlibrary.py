"""The lawlibrary checkout as a source of statute text.

lawlibrary keeps the Legislature's publications on its own shelf and
answers ``query.section``, ``query.range``, and ``query.act`` from the
newest session. Its modules are flat (``query``, ``config``, ``core``), so
they are not imported into Jason. A small worker runs inside lawlibrary's
own environment instead: Jason hands it a JSON job on stdin and reads
JSON back. A span the shelf cannot serve is a miss in the result, never
an invented section.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# The checkout beside jason's, taken from jason's own folder and not the working directory (``lawlibrary_home`` in .env or
# the user config names another).
DEFAULT_HOME = Path(__file__).resolve().parents[3].parent / "lawlibrary"

# Runs with lawlibrary's checkout as the working directory. A span too large for one text answer is split
# at the numeric midpoint until each half answers, so a chapter of forty sections still comes back whole.
_WORKER = r'''
import json, sys
import query

def texts(code, start, end, depth=0, session=None):
    r = query.range(code, start, end, text=True, session=session)
    if r.get("reason") == "span_too_large" and depth < 8:
        lo, hi = float(start), float(end)
        mid = (lo + hi) / 2
        left = texts(code, start, ("%.3f" % mid).rstrip("0").rstrip("."), depth + 1, session)
        right = texts(code, ("%.3f" % (mid + 0.001)).rstrip("0").rstrip("."), end, depth + 1, session)
        seen, out = set(), []
        for s in left + right:
            if s["citation"] not in seen:
                seen.add(s["citation"]); out.append(s)
        return out
    if not r.get("found"):
        return []
    return r.get("sections") or []

job = json.load(sys.stdin)
out = {"spans": [], "acts": {}, "session": None}
for code, start, end in job.get("spans", []):
    sections = texts(code, start, end)
    if sections and out["session"] is None:
        out["session"] = sections[0].get("session")
    out["spans"].append({"code": code, "start": start, "end": end, "sections": [
        {k: s.get(k) for k in ("citation", "code", "section", "title", "text", "path", "session", "history", "effective")} for s in sections]})
for name in job.get("acts", []):
    a = query.act(name)
    out["acts"][name] = {"found": bool(a.get("found")), "code": a.get("code"), "nodes": a.get("nodes") or [], "reason": a.get("reason")}
# One edition's text and outline for a span: {"code", "start", "end", "session"} ("2011", "2013"; None for the newest).
out["editions"] = []
for e in job.get("editions", []):
    sections = texts(e["code"], e["start"], e["end"], session=e.get("session"))
    o = query.outline(e["code"], e["start"], e["end"], session=e.get("session"))
    out["editions"].append({"code": e["code"], "start": e["start"], "end": e["end"], "session": e.get("session"),
        "nodes": o.get("nodes") or [], "sections": [
        {k: s.get(k) for k in ("citation", "code", "section", "title", "text", "path", "session", "history")} for s in sections]})
if job.get("former") or job.get("changes"):
    import history, succession
    out["former"] = []
    for code, act in job.get("former", []):
        # The former sections the last edition carrying them holds (the pool lawlibrary's coverage counts).
        numbers = sorted(succession._pool(act).former, key=query.section_key)
        out["former"].append({"code": code, "act": act, "sections": [succession.successors(code, n) for n in numbers]})
    out["changes"] = [history.changes(c["code"], [tuple(s) for s in c["spans"]], since=c.get("since"), until=c.get("until"))
                      for c in job.get("changes", [])]
# Every row each session publication prints for the named sections: {"code", "sections": [numbers]}. A section a
# publication prints twice comes back twice; "note" is the Legislature's history note read into days.
if job.get("versions"):
    import history
    out["versions"] = []
    for v in job["versions"]:
        wanted = {query.section_address(n) for n in v["sections"]}
        ordered = sorted(wanted, key=query.section_key)
        carried = history.code_editions(v["code"])
        rows = []
        for session in carried:
            r = query.range(v["code"], ordered[0], ordered[-1], text=True, session=session, limit=None) if ordered else {}
            found = (r.get("sections") or []) if r.get("found") else []
            if r.get("reason") == "span_too_large":
                found = [s for n in ordered for s in (query.range(v["code"], n, n, text=True, session=session).get("sections") or [])]
            for s in found:
                if query.section_address(s.get("section")) in wanted:
                    row = {k: s.get(k) for k in ("citation", "code", "section", "title", "text", "session", "history", "effective")}
                    row["note"] = history.read_note(s.get("history") or "").record()
                    rows.append(row)
        out["versions"].append({"code": v["code"], "editions": carried, "rows": rows})
json.dump(out, sys.stdout, default=str)
'''


@dataclass(frozen=True)
class Section:
    citation: str
    code: str
    number: str
    title: str
    text: str
    path: tuple[str, ...]
    session: str
    history: str = ""

    @property
    def heading(self) -> str:
        return self.path[-1] if self.path else ""


@dataclass(frozen=True)
class SpanText:
    code: str
    start: str
    end: str
    sections: tuple[Section, ...]

    @property
    def found(self) -> bool:
        return bool(self.sections)


@dataclass(frozen=True)
class OutlineNode:
    level: str
    heading: str
    first: str
    last: str
    count: int


@dataclass
class Job:
    spans: list[tuple[str, str, str]] = field(default_factory=list)
    acts: list[str] = field(default_factory=list)
    # (code, act): each former section of a recodified act ("davis-stirling"), with its successors (lawlibrary's
    # ``succession``: the Law Revision Commission's disposition tables, then its Comments, then a similarity candidate).
    former: list[tuple[str, str]] = field(default_factory=list)
    # {"code", "spans": [[start, end]], "since", "until"}: every change between consecutive editions (``history.changes``).
    changes: list[dict[str, Any]] = field(default_factory=list)
    # {"code", "start", "end", "session"}: one edition's section text and outline nodes for a span (``edition``).
    editions: list[dict[str, Any]] = field(default_factory=list)
    # {"code", "sections": [numbers]}: every row each session publication prints for those sections (``versions``).
    versions: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class Edition:
    """A span as one legislative session printed it: its sections (text and heading path) and its outline."""

    code: str
    start: str
    end: str
    session: str
    sections: tuple[Section, ...]
    nodes: tuple[OutlineNode, ...]

    @property
    def found(self) -> bool:
        return bool(self.sections)


class LawLibraryUnavailable(RuntimeError):
    """The checkout or its environment is missing; nothing was fetched."""


class LawLibrary:
    """Statute text from the lawlibrary checkout at ``home``, run in its own environment.

    ``run`` replaces the subprocess in tests: it takes the job dict and
    returns the worker's result dict.
    """

    def __init__(self, home: Path | None = None, *, python: Path | None = None, run=None, timeout: int = 900) -> None:
        self.home = Path(home) if home else DEFAULT_HOME
        self.python = python
        self._run = run
        self.timeout = timeout

    def interpreter(self) -> Path:
        if self.python:
            return self.python
        venv = self.home / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        return venv if venv.is_file() else Path(sys.executable)

    def available(self) -> bool:
        return self._run is not None or (self.home / "query.py").is_file()

    def execute(self, job: Job) -> dict[str, Any]:
        payload = {"spans": [list(span) for span in job.spans], "acts": list(job.acts), "former": [list(f) for f in job.former],
                   "changes": list(job.changes), "editions": list(job.editions), "versions": list(job.versions)}
        if self._run is not None:
            return self._run(payload)
        if not (self.home / "query.py").is_file():
            raise LawLibraryUnavailable(f"lawlibrary checkout not found at {self.home}; set lawlibrary_home in .env")
        done = subprocess.run(
            [str(self.interpreter()), "-c", _WORKER], input=json.dumps(payload), capture_output=True, text=True,
            encoding="utf-8", cwd=str(self.home), timeout=self.timeout,
        )
        if done.returncode != 0:
            raise LawLibraryUnavailable(f"lawlibrary worker failed: {done.stderr.strip()[-800:]}")
        return json.loads(done.stdout or "{}")

    def spans(self, spans: list[tuple[str, str, str]]) -> tuple[SpanText, ...]:
        """Section text for each span, in order. A span the shelf cannot serve has no sections."""
        if not spans:
            return ()
        result = self.execute(Job(spans=list(spans)))
        return tuple(_span(row) for row in result.get("spans") or [])

    def act(self, name: str) -> tuple[OutlineNode, ...]:
        """The outline of a named act (division, part, chapter, article rows in order), or nothing."""
        result = self.execute(Job(acts=[name]))
        found = (result.get("acts") or {}).get(name) or {}
        return tuple(
            OutlineNode(str(n.get("level") or ""), str(n.get("heading") or ""), str(n.get("first") or ""), str(n.get("last") or ""), int(n.get("count") or 0))
            for n in found.get("nodes") or []
        )


    def recodification(self, code: str, act: str) -> list[dict[str, Any]]:
        """Each former section of a recodified act (``davis-stirling``), with its successor rows (lawlibrary's JSON)."""
        result = self.execute(Job(former=[(code, act)]))
        rows = result.get("former") or []
        return list(rows[0].get("sections") or []) if rows else []

    def editions(self, wanted: list[tuple[str, str, str, str | None]]) -> tuple[Edition, ...]:
        """Each (code, start, end, session) span's text and outline as that session printed it; a session the shelf
        does not hold comes back with no sections (a miss, never another edition's text)."""
        if not wanted:
            return ()
        result = self.execute(Job(editions=[{"code": c, "start": a, "end": b, "session": s} for c, a, b, s in wanted]))
        out: list[Edition] = []
        for row in result.get("editions") or []:
            span = _span(row)
            nodes = tuple(OutlineNode(str(n.get("level") or ""), str(n.get("heading") or ""), str(n.get("first") or ""),
                                      str(n.get("last") or ""), int(n.get("count") or 0)) for n in row.get("nodes") or [])
            out.append(Edition(span.code, span.start, span.end, str(row.get("session") or ""), span.sections, nodes))
        return tuple(out)

    def changes(self, code: str, spans: list[tuple[str, str]], *, since: str | None = None, until: str | None = None) -> dict[str, Any]:
        """Every change to the spans between consecutive editions, oldest first (lawlibrary's JSON)."""
        result = self.execute(Job(changes=[{"code": code, "spans": [list(s) for s in spans], "since": since, "until": until}]))
        rows = result.get("changes") or []
        return rows[0] if rows else {"found": False, "reason": "no_result"}

    def versions(self, wanted: dict[str, list[str]]) -> list[dict[str, Any]]:
        """For each code, the session publications that carry it (``editions``, oldest first) and every row each
        prints for the named sections (``rows``: ``session``, ``section``, ``title``, ``text``, the Legislature's note
        as ``history``, and the note read into days as ``note``). A section a publication prints in two versions has
        two rows; one it does not print has none (a miss, never another publication's words)."""
        if not wanted:
            return []
        result = self.execute(Job(versions=[{"code": code, "sections": list(numbers)} for code, numbers in wanted.items()]))
        return list(result.get("versions") or [])


def _span(row: dict[str, Any]) -> SpanText:
    sections = tuple(
        Section(
            str(s.get("citation") or ""), str(s.get("code") or ""), str(s.get("section") or ""), str(s.get("title") or ""),
            str(s.get("text") or ""), tuple(str(p.get("heading") or "") for p in (s.get("path") or []) if isinstance(p, dict)),
            str(s.get("session") or ""), str(s.get("history") or ""),
        )
        for s in row.get("sections") or []
    )
    return SpanText(str(row.get("code") or ""), str(row.get("start") or ""), str(row.get("end") or ""), sections)


def _key(value: str) -> tuple[float, ...]:
    try:
        return tuple(float(part) for part in value.split("."))
    except ValueError:
        return (-1.0,)


def article_groups(nodes: tuple[OutlineNode, ...]) -> tuple[OutlineNode, ...]:
    """The finest headings that tile an act: each article, and each chapter no article falls inside.

    lawlibrary lists the outline by level, chapters together and articles
    together, so a chapter is matched to its articles by section range.
    """
    articles = [n for n in nodes if n.level == "article"]
    chapters = [n for n in nodes if n.level == "chapter"]
    bare = [c for c in chapters if not any(_key(c.first) <= _key(a.first) and _key(a.last) <= _key(c.last) for a in articles)]
    groups = sorted((*articles, *bare), key=lambda n: _key(n.first))
    if not groups:
        groups = [node for node in nodes if node.level in ("part", "division")][-1:]
    return tuple(groups)
