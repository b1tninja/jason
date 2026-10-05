"""jason's own rule rows, cited as a plan item writes them and recited as data.

A plan item names the rule it rests on. Most are the law or the association's documents (``jason cite`` reads those);
some are jason's own: a row of the owner-information response policy (``owner_responses.RULES: delivery``), a list a
module keeps (``owner_info.FOR_A_PERSON``), a value the specification holds (``Community.owner_information:
EARLIER_ELECTIONS``). A rule row is a decision written as data (AGENTS.md: "a new decision is a new rule row"), and a
row is recited as it stands: its key, the words it carries, the action it gives, the condition it tests (a function:
its name, where it is, its own source), and where it came from. It is labeled plainly as **jason's rule row, not a rule
of the association**: the association's rules are its governing documents, and a row that rests on a board decision
names the board item that decides it. Reading only; nothing is written.

The tables are a closed list (``TABLES``): an address names a table jason registers, never an arbitrary attribute of
an arbitrary module. ``Community.<method>: ATTRIBUTE`` reads one named attribute of the specification, through a no-argument
method of ``Community`` (a profile's own data).
"""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable

LABEL = ("jason's own rule row, a decision kept as data: not a rule of the association. The association's rules are its "
         "governing documents; a row that rests on a board decision names the board item.")


@dataclass(frozen=True)
class Row:
    key: str
    words: str                                 # what the row says, in its own words
    fields: dict[str, Any] = field(default_factory=dict)
    where: str = ""                            # the file and line it is written at
    board_item: str = ""                       # the board item that decides it, when the row names one


@dataclass(frozen=True)
class Table:
    name: str                                  # "owner_responses.RULES"
    title: str
    source: str                                # the module's path under the repository
    rows: Callable[[Any], list[Row]]           # the specification (Community) -> the table's rows
    note: str = ""


def _repo() -> Path:
    return Path(__file__).resolve().parents[3]


def _rel(path: str | None) -> str:
    if not path:
        return ""
    try:
        return Path(path).resolve().relative_to(_repo()).as_posix()
    except ValueError:
        return Path(path).name


def _where(obj: Any) -> str:
    try:
        _, line = inspect.getsourcelines(obj)
        return f"{_rel(inspect.getsourcefile(obj))}:{line}"
    except (OSError, TypeError):
        return _rel(getattr(inspect.getmodule(obj), "__file__", ""))


def _condition(fn: Callable[..., Any]) -> dict[str, str]:
    """A rule's test: its name, where it is, and its own source: the words that decide whether the row applies."""
    try:
        source = inspect.getsource(fn)
    except (OSError, TypeError):
        source = ""
    doc = inspect.getdoc(fn) or ""
    return {"function": getattr(fn, "__name__", str(fn)), "where": _where(fn), "doc": doc.splitlines()[0] if doc else "",
            "source": source.strip()}


def _comment_above(module: Any, name: str) -> tuple[str, str]:
    """The comment lines right above ``NAME = ...`` in a module, and where the assignment is."""
    try:
        lines = inspect.getsource(module).splitlines()
    except (OSError, TypeError):
        return "", ""
    for k, line in enumerate(lines):
        if re.match(rf"{re.escape(name)}\s*(?::[^=]+)?=", line):
            above: list[str] = []
            j = k - 1
            while j >= 0 and lines[j].lstrip().startswith("#"):
                above.insert(0, lines[j].lstrip().lstrip("#").strip())
                j -= 1
            return " ".join(above), f"{_rel(getattr(module, '__file__', ''))}:{k + 1}"
    return "", ""


# --- The registered tables ----------------------------------------------------------------------------------------------


def _owner_responses(_community: Any) -> list[Row]:
    from jason.tasks import owner_responses as module

    out = []
    for rule in module.RULES:
        out.append(Row(rule.key, rule.why, {"outcome": rule.outcome.value, "stops": rule.stops,
                                            "condition": _condition(rule.test)}, _where(rule.test), rule.board_item))
    return out


def _owner_info_for_a_person(_community: Any) -> list[Row]:
    from jason.tasks import owner_info as module

    comment, where = _comment_above(module, "FOR_A_PERSON")
    return [Row(item, f"a person enters the {item}" + (f". {comment}" if comment else ""),
                {"action": f"a person enters the {item} in PayHOA", "outcome": "person"}, where)
            for item in module.FOR_A_PERSON]


def _response_rules(community: Any) -> list[Row]:
    from jason.community.responses import rules_for

    out = []
    for kind, rule in rules_for(community)[1].items():
        out.append(Row(kind.value, rule.note or rule.first_step or rule.authority,
                       {"clock": rule.source.value, "days": rule.days, "authority": rule.authority,
                        "firstStep": rule.first_step}, "the profile's response rules (Community.response_rules)"))
    return out


TABLES: dict[str, Table] = {t.name: t for t in (
    Table("owner_responses.RULES", "the owner-information response policy (how each answer is handled)",
          "src/jason/tasks/owner_responses.py", _owner_responses,
          "applied in order; each row's condition is the function it tests"),
    Table("owner_info.FOR_A_PERSON", "what an owner-information answer can ask that a person enters",
          "src/jason/tasks/owner_info.py", _owner_info_for_a_person),
    Table("responses.RULES", "the response rules: the clock and the owner of each kind of request",
          "src/jason/community/responses.py", _response_rules),
)}

# "Community.owner_information: EARLIER_ELECTIONS": one attribute of the specification.
_SPEC = re.compile(r"^Community\.(?P<method>[a-z][a-z0-9_]*)$")


def table_names() -> list[str]:
    """The names a citation may use for a table (for the scanner)."""
    return [*TABLES, "Community.owner_information"]


@dataclass(frozen=True)
class Recited:
    found: bool
    citation: str
    table: str = ""
    key: str = ""
    title: str = ""
    text: str = ""
    row: dict[str, Any] = field(default_factory=dict)
    rows: tuple[dict[str, Any], ...] = ()
    reason: str = ""
    detail: str = ""
    source: str = ""


def _plain(value: Any, depth: int = 0) -> Any:
    """A specification value as data a person can read: an enum by its value, a record by its fields, a collection by
    its members (to a depth)."""
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type) and depth < 3:
        return {f.name: _plain(getattr(value, f.name), depth + 1) for f in fields(value)}
    if isinstance(value, (list, tuple, set, frozenset)) and depth < 3:
        return [_plain(v, depth + 1) for v in value]
    if isinstance(value, dict) and depth < 3:
        return {str(k): _plain(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)[:300]


def _lines(row: Row) -> list[str]:
    out = [f"key: {row.key}", f"words: {row.words}"]
    for k, v in row.fields.items():
        if k == "condition" and isinstance(v, dict):
            out.append(f"condition: {v['function']} ({v['where']})" + (f", {v['doc']}" if v.get("doc") else ""))
            if v.get("source"):
                out += ["", v["source"], ""]
        else:
            out.append(f"{k}: {v}")
    if row.where:
        out.append(f"written at: {row.where}")
    return out


def _row_dict(row: Row) -> dict[str, Any]:
    out = {"key": row.key, "words": row.words, **{k: _plain(v) for k, v in row.fields.items()}, "where": row.where}
    if row.board_item:
        out["adoption"] = {"boardItem": row.board_item, "address": f"board-item:{row.board_item}",
                           "note": "the board item that decides this row"}
    return out


def parse(text: str) -> tuple[str, str] | None:
    """A rule-row address in ``text``: (table, key). "owner_responses.RULES: delivery", "the response policy's delivery row
    (owner_responses.RULES: delivery)", "owner_info.FOR_A_PERSON", "Community.owner_information: EARLIER_ELECTIONS"."""
    names = sorted([*TABLES, "Community.owner_information"], key=len, reverse=True)
    m = re.search(rf"(?<![\w.])(?P<table>{'|'.join(re.escape(n) for n in names)})(?![\w]|\.\w)(?:\s*:\s*(?P<key>[A-Za-z0-9_-]+))?",
                  text or "")
    return (m.group("table"), m.group("key") or "") if m else None


def recite(table: str, key: str = "", community: Any = None) -> Recited:
    """One row (or a whole table, when ``key`` is empty) of jason's rule rows, as data. A miss is an answer with its
    reason: ``unknown_table`` (not a registered table), ``no_such_row``."""
    citation = f"{table}: {key}" if key else table
    if table.startswith("Community."):
        return _spec(table, key, community)
    spec = TABLES.get(table)
    if spec is None:
        return Recited(False, citation, reason="unknown_table", detail="the registered tables: " + ", ".join(table_names()))
    try:
        rows = spec.rows(community)
    except Exception as exc:  # noqa: BLE001 - a table that cannot be read is a miss with its reason
        return Recited(False, citation, table, key, spec.title, reason="unreadable", detail=f"{type(exc).__name__}: {exc}")
    if key:
        row = next((r for r in rows if r.key == key), None)
        if row is None:
            return Recited(False, citation, table, key, spec.title, reason="no_such_row",
                           detail=f"{table} has the rows: " + ", ".join(r.key for r in rows), source=spec.source)
        return Recited(True, citation, table, key, spec.title, "\n".join(_lines(row)), _row_dict(row), (), "", "", spec.source)
    text = "\n\n".join("\n".join(_lines(r)) for r in rows)
    return Recited(True, citation, table, "", spec.title, text, {}, tuple(_row_dict(r) for r in rows), "", "", spec.source)


def _spec(table: str, key: str, community: Any) -> Recited:
    citation = f"{table}: {key}" if key else table
    m = _SPEC.match(table)
    if community is None or m is None:
        return Recited(False, citation, reason="unknown_table", detail="no specification to read")
    from jason.community.base import Community

    method = m.group("method")
    if method.startswith("_") or not callable(getattr(Community, method, None)):
        return Recited(False, citation, reason="unknown_table", detail=f"Community has no method {method!r}")
    try:
        held = getattr(community, method)()
    except TypeError:
        return Recited(False, citation, reason="unknown_table", detail=f"Community.{method} takes arguments")
    except Exception as exc:  # noqa: BLE001
        return Recited(False, citation, reason="unreadable", detail=f"{type(exc).__name__}: {exc}")
    if held is None:
        return Recited(False, citation, reason="no_such_row", detail=f"the profile sets nothing in Community.{method}()")
    if not key:
        names = sorted(n for n in dir(held) if n.isupper() and not n.startswith("_"))
        return Recited(True, citation, table, "", f"the profile's {method}", "\n".join(f"{n}: {_plain(getattr(held, n))}"
                       for n in names), {}, tuple({"key": n, "value": _plain(getattr(held, n))} for n in names), "", "",
                       "the profile (the specification)")
    if not key.isupper() or not hasattr(held, key):
        return Recited(False, citation, table, key, reason="no_such_row", detail=f"Community.{method}() has no attribute {key}")
    value = getattr(held, key)
    row: dict[str, Any] = {"key": key, "value": _plain(value)}
    lines = [f"{key}: {_plain(value)}"]
    # A module's attribute carries its reason in the comment above it (a board decision, with its date): recite it.
    comment, where = _comment_above(held, key) if inspect.ismodule(held) else ("", "")
    if comment:
        row["comment"] = comment
        lines.append(f"comment: {comment}")
    if where:
        row["where"] = where
        lines.append(f"written at: {where}")
    return Recited(True, citation, table, key, f"the profile's {method}", "\n".join(lines), row, (),
                   "", "", "the profile (the specification)")


def as_dict(r: Recited) -> dict[str, Any]:
    """A rule row as ``cite.resolve`` answers it: the words first, labeled as jason's row, with the caveat."""
    out: dict[str, Any] = {"kind": "row", "found": r.found, "citation": r.citation, "expression": r.citation}
    if r.found:
        out.update({"text": r.text, "inForce": f"{r.source or 'jason'}, as it is written now (jason's own record: not dated)",
                    "caveat": LABEL, "title": r.title, "table": r.table, "target": f"row:{r.table}" + (f"/{r.key}" if r.key else "")})
        if r.row:
            out["row"] = r.row
        if r.rows:
            out["rows"] = list(r.rows)
        if r.row.get("adoption"):
            out["adoption"] = r.row["adoption"]
        out["scope"] = {"standing": "scoped", "form": "jason's rule row", "basis": "row", "document": r.table}
    else:
        out.update({"reason": r.reason, "detail": r.detail, "table": r.table})
    return out
