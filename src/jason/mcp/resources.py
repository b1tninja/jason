"""MCP resources over the record addresses: each ``jason://`` address (docs/record-addresses.md) is a resource, read
by the same resolver ``jason cite`` and ``cite_document`` use (``jason.tasks.cite``).

- ``resources/list`` lists the books, each part a profile maps, and each living book's top-level articles or
  sections, capped (``LIST_CAP``, ``PER_BOOK``). A restricted book (``exec``, ``members``, ``ballots``) is listed by
  name only, with a note: a read of it is refused.
- ``resources/templates/list`` gives the address forms (``TEMPLATES``).
- ``resources/read`` returns ``text/markdown``: the recitation first (the words whole, the citation, the version in
  force, and the caveat), then the address and permanent id, the defined terms the words use with their definitions'
  addresses, and the history's address. A miss is a not-found error carrying the resolver's reason.

Annotations: ``audience`` (the user and the assistant, or the user alone for a restricted book), ``priority`` (the
governing documents first), and ``lastModified`` (the effective day of the version the words are read at, when known).

The resources are served under the ``governance`` profile and the default ``all``. A read never opens a restricted
book: ``private`` is not something a URI can ask for (``jason cite --private`` reads one locally). Subscriptions and
``list_changed`` are not emitted; the listing is computed when the server starts.

``read`` and ``listing`` are plain functions (``jason.api.read_record``, ``jason.api.record_resources``); only
``register`` imports the mcp package.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from jason.community.cite import CAVEAT

MIME = "text/markdown"
LIST_CAP = 200                     # resources listed in all
PER_BOOK = 40                      # a living book's articles or sections listed
PROFILES = ("all", "governance")   # the server profiles that serve the resources


class AddressNotFound(LookupError):
    """A ``jason://`` address that resolves to nothing, with the resolver's reason."""

    def __init__(self, address: str, reason: str, detail: str = ""):
        self.address, self.reason, self.detail = address, reason, detail
        super().__init__(f"{address}: {reason}" + (f": {detail}" if detail else ""))


@dataclass(frozen=True)
class Page:
    address: str
    title: str
    text: str                      # Markdown
    last_modified: str | None = None


@dataclass(frozen=True)
class Template:
    uri: str
    name: str
    title: str
    description: str
    address: Callable[..., str]    # the address the template's parameters spell (the URI read back)


TEMPLATES: tuple[Template, ...] = (
    Template("jason://{book}/history/{+section}", "record_history", "A section's history",
             "The section's timeline: each version, the number it went by, whether its words changed, a draft that "
             "would change it, and the numbers other readings give it. A permanent id is a program's pairing of "
             "words: evidence, not a finding.",
             lambda book, section: f"jason://{book}/history/{section}"),
    Template("jason://{book}@{version}/{+section}", "record_version", "A section at a version",
             "A section at a version: base (as first recorded or adopted), the day a version took effect "
             "(YYYY-MM-DD; a miss lists the versions), or a stage label (draft-YYYY-MM-DD: never in force).",
             lambda book, version, section: f"jason://{book}@{version}/{section}"),
    Template("jason://{book}:{date}/{+section}", "record_in_force", "A section in force on a day",
             "The words in force on a day (YYYY-MM-DD).",
             lambda book, date, section: f"jason://{book}:{date}/{section}"),
    Template("jason://res/{number}", "resolution", "A resolution",
             "A board resolution by its number, as the Doc on disk prints it.",
             lambda number: f"jason://res/{number}"),
    Template("jason://min/{day}", "minutes", "Minutes",
             "The minutes of a meeting by its day (YYYY-MM-DD), from the meeting catalog.",
             lambda day: f"jason://min/{day}"),
    Template("jason://inst/{number}", "instrument", "A recorded instrument",
             "A recorded instrument by the county's document number.",
             lambda number: f"jason://inst/{number}"),
    Template("jason://{book}/{item}{#fragment}", "series_item_part", "A part of a series item",
             "An item of a series book with a fragment (jason://min/2099-01-01#item-4): the item is read whole.",
             lambda book, item, fragment: f"jason://{book}/{item}#{fragment}"),
    Template("jason://{book}/{+section}", "record_section", "A section, or a series item",
             "The current text of a living book's section (4.15(a), B-1), a span (6.2..6.4), siblings "
             "(6.2(a),6.2(b)), or an item of a series book (res/N, min/DAY, budget/YEAR). A part of a book is its own "
             "key (rules.parking).",
             lambda book, section: f"jason://{book}/{section}"),
    Template("jason://{book}", "record_book", "A book",
             "A book: a living book's outline, a series book's record kind and where the profile keeps it, or gov, "
             "the governing documents as a set (CIV 4150). A version or a day in force may follow the key "
             "(decl@2099-01-01, decl:2099-06-01).",
             lambda book: f"jason://{book}"),
)


def _shelf(community: Any = None, data_dir: Path | None = None) -> Any:
    from jason.mcp.governance import _root
    from jason.tasks.cite import Shelf

    return Shelf(community, _root(data_dir))          # never private: a URI cannot open a restricted book


def _quote(text: str) -> list[str]:
    return [f"> {line}" if line.strip() else ">" for line in text.strip().splitlines()]


def markdown(s: Any) -> str:
    """A sheet (``jason.tasks.reader.Sheet``) as the resource's Markdown: the recitation first."""
    lines = [f"# {s.title}", ""]
    if s.words:
        lines += _quote(s.words) + [">", f"> _{s.title}" + (f", {s.in_force}" if s.in_force else "") + "._", ""]
    elif s.in_force:
        lines += [f"Version in force: {s.in_force}.", ""]
    if s.note:
        lines += [f"Note: {s.note}.", ""]
    if s.caveat:
        lines += [f"_{s.caveat}_", ""]
    meta = []
    if s.address:
        meta.append(f"- Address: `{s.address}`")
    if s.pid:
        meta.append(f"- Permanent id: `{s.pid}`")
    if s.effective:
        meta.append(f"- {'Words last changed' if s.kind == 'history' else 'In force from'}: {s.effective.isoformat()}")
    if s.history:
        meta.append(f"- History: `{s.history}`")
    if meta:
        lines += meta + [""]
    if s.terms:
        lines += ["## Defined terms", "", "The document defines words this section uses; its definition governs them "
                  "here (Civil Code 1644). Each is recited from its own section.", ""]
        for row in s.terms:
            lines += [f"**{row['term']}** ({row['citation']}, `{row['key']}`)" + (":" if row["definition"] else ""), ""]
            if row["definition"]:
                lines += _quote(row["definition"]) + [""]
    for title, rows in (("Outline", s.outline), ("Versions", s.versions)):
        if not rows:
            continue
        lines += [f"## {title}", ""]
        for r in rows[:400]:
            label = f"[{r.label}]({r.key})" if r.key else r.label
            lines.append(f"- {label}" + (f" {r.note}" if r.note else "") + ("" if r.found else " (not there)"))
        if len(rows) > 400:
            lines.append(f"- ... and {len(rows) - 400} more")
        lines.append("")
    if s.readings:
        lines += ["## Other readings' numbers", ""] + [f"- {r}" for r in s.readings] + [""]
    return "\n".join(lines).rstrip() + "\n"


def read(address: str, *, community: Any = None, data_dir: Path | None = None, shelf: Any = None) -> Page:
    """One address as a resource page; ``AddressNotFound`` with the resolver's reason on a miss (a restricted book
    is a miss with reason ``restricted``)."""
    from jason.tasks.reader import sheet

    shelf = shelf or _shelf(community, data_dir)
    text = str(address or "").strip()
    if not text.lower().startswith("jason://"):
        raise AddressNotFound(text, "unparsed", "a resource is a jason:// address")
    c = shelf(text)
    try:
        s = sheet(shelf, c)
    except Exception as exc:  # a reader that fails is a miss, not a traceback
        raise AddressNotFound(text, "unreadable", str(exc)) from exc
    if not s.found:
        raise AddressNotFound(text, s.reason or "unknown", s.detail)
    return Page(s.address or text, s.title, markdown(s), s.effective.isoformat() if s.effective else None)


def _book_row(b: Any, shelf: Any) -> dict[str, Any]:
    docs = [e.document for e in shelf.books.entries if e.book is b and e.role.value != "amendment" and not e.part]
    info = b.info
    if b.restricted:
        return {"uri": f"jason://{b.value}", "name": b.value, "title": info.title,
                "description": f"Restricted ({b.restricted}): listed by name only. A read is refused; the association "
                               "may withhold it. jason cite --private reads it locally.",
                "audience": ["user"], "priority": 0.1}
    what = {"living": "a living book, cited by section", "series": f"a series, one record per item ({info.item})",
            "group": "the governing documents as a set"}[info.shape.value]
    desc = f"{info.title} ({info.statute or 'not in the Act'}): {what}."
    if docs:
        desc += f" The profile's document: {', '.join(docs)}."
    elif info.shape.value == "living":
        desc += " The profile maps no document to it."
    if info.note:
        desc += f" {info.note[0].upper()}{info.note[1:]}."
    priority = 0.9 if b.governing else (0.3 if b.value == "manual" else 0.5)
    return {"uri": f"jason://{b.value}", "name": b.value, "title": info.title, "description": desc,
            "audience": ["user", "assistant"], "priority": priority}


def listing(*, community: Any = None, data_dir: Path | None = None, shelf: Any = None, cap: int = LIST_CAP,
            per_book: int = PER_BOOK) -> list[dict[str, Any]]:
    """The resources a client lists: every book (a restricted one by name only) and each part the profile maps,
    always; then each living book's top-level articles or sections, ``per_book`` a book, until the list holds
    ``cap``. Each row is
    ``{uri, name, title, description, audience, priority, lastModified}``."""
    from jason.community.books import Book
    from jason.community.cite import Target, Unit
    from jason.tasks.reader import effective_day

    shelf = shelf or _shelf(community, data_dir)
    rows = [_book_row(b, shelf) for b in Book]
    keys = set(shelf.names().values())
    living: list[tuple[str, Any]] = [(b.value, b) for b in Book
                                     if b.living and shelf.books.document(b.value) in keys]
    for e in shelf.books.entries:
        if e.part and e.role.value != "amendment" and all(k != e.key for k, _ in living):
            living.append((e.key, e.book))
            title = shelf.title(e.document)
            rows.append({"uri": f"jason://{e.key}", "name": e.key, "title": title,
                         "description": f"A part of {e.book.info.title}: {title}" + (f" ({e.note})" if e.note else "")
                                        + ".", "audience": ["user", "assistant"],
                         "priority": 0.7 if e.book.governing else 0.4})
    listed: set[str] = set()
    for key, book in living:
        doc = shelf.books.document(key)
        if doc in listed:              # a document in two books (the rules reprinted in the manual): its own key
            continue
        listed.add(doc)
        c = shelf(f"jason://{key}")
        try:
            when = effective_day(shelf, c)
        except Exception:
            when = None
        for row in rows:
            if row["uri"] == f"jason://{key}" and when:
                row["lastModified"] = when.isoformat()
        if not c.found:
            continue
        top = [n for n in c.state.nodes if n.get("number") and n.get("depth", 1) == 1 and not n.get("removed")]
        for n in top[:per_book]:
            if len(rows) >= cap:
                return rows
            address = shelf.address(Target(Unit.SECTION, doc, n["number"]))
            caption = (n.get("caption") or "").strip()
            rows.append({"uri": address, "name": address[len("jason://"):],
                         "title": f"{shelf.title(doc)} {n['number']}" + (f" {caption}" if caption else ""),
                         "description": f"{book.info.title}, {n['number']}" + (f": {caption}" if caption else "")
                                        + ". The current text (an article reads as its outline).",
                         "audience": ["user", "assistant"], "priority": 0.6 if book.governing else 0.4})
    return rows


def register(server: Any, *, community: Any = None, data_dir: Path | None = None) -> int:
    """Add the templates and the listed resources to an ``MCPServer``; the number of resources listed."""
    from mcp.server.mcpserver.exceptions import ResourceNotFoundError
    from mcp.server.mcpserver.resources import FunctionResource
    from mcp_types import Annotations

    def serve(address: str) -> str:
        try:
            return read(address, community=community, data_dir=data_dir).text
        except AddressNotFound as exc:
            raise ResourceNotFoundError(str(exc)) from exc

    for t in TEMPLATES:
        def handler(*args: str, _t: Template = t, **params: str) -> str:
            return serve(_t.address(**params))

        params = list(_param_names(t.uri))
        handler = _signed(handler, params, t.name)
        server.resource(t.uri, name=t.name, title=t.title, description=t.description, mime_type=MIME)(handler)
    try:
        rows = listing(community=community, data_dir=data_dir)
    except Exception:  # the listing never stops the server: the templates still read every address
        from jason.community.books import Book

        rows = [{"uri": f"jason://{b.value}", "name": b.value, "title": b.info.title, "description": b.info.note,
                 "audience": ["user"], "priority": 0.5} for b in Book]
    for row in rows:
        uri = row["uri"]
        server.add_resource(FunctionResource(
            uri=uri, name=row["name"], title=row["title"], description=row["description"], mime_type=MIME,
            annotations=Annotations(audience=row["audience"], priority=row["priority"],
                                    lastModified=row.get("lastModified")),
            fn=lambda _uri=uri: serve(_uri)))
    return len(rows)


def _param_names(uri: str) -> tuple[str, ...]:
    from mcp.shared.uri_template import UriTemplate

    return tuple(UriTemplate.parse(uri).variable_names)


def _signed(fn: Callable[..., str], params: list[str], name: str) -> Callable[..., str]:
    """A handler whose signature names exactly the template's parameters (MCPServer checks them)."""
    import inspect

    def call(**kwargs: str) -> str:
        return fn(**kwargs)

    call.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        [inspect.Parameter(p, inspect.Parameter.KEYWORD_ONLY, annotation=str) for p in params])
    call.__name__ = name
    call.__annotations__ = {**{p: str for p in params}, "return": str}
    return call


__all__ = ["AddressNotFound", "CAVEAT", "LIST_CAP", "MIME", "PER_BOOK", "PROFILES", "Page", "TEMPLATES", "Template",
           "listing", "markdown", "read", "register"]
