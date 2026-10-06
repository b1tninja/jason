"""The handlers a form may name, until the handler registry exists (docs/arrivals-design.md, "The handler is chosen when
the form is made").

A form is made only if something can process what comes back: a reference exists only if a handler does. The registry
(``jason.handlers``, with ``@handler`` and ``Role``) is not built yet, so the library keeps its own small table of the
keys a definition may use, and the check refuses a form that names another:

- a **process handler** is tied to the law a form serves: a form with an authority takes one whose citations include one
  of its own;
- a **general handler** is for a form tied to no law, and is chosen by a person from this short fixed list. A profile
  cannot add one by data: adding a handler is development.

``built`` says whether the code that carries out the handler is written. The table is the library's contract with the
registry that replaces it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class HandlerKind(Enum):
    GENERAL = "general"
    PROCESS = "process"


@dataclass(frozen=True)
class Handler:
    key: str
    kind: HandlerKind
    summary: str
    citations: tuple[str, ...] = ()       # a process handler: the sections it serves
    procedure: str = ""                    # a process handler: the SOP it follows (a form may name another)
    built: bool = True


HANDLERS: dict[str, Handler] = {h.key: h for h in (
    # general: a form tied to no law
    Handler("collect-only", HandlerKind.GENERAL, "keep each response for a person to read", built=False),
    Handler("sheet-register", HandlerKind.GENERAL, "append each confirmed response to a register in a Google Sheet", built=False),
    Handler("board-item", HandlerKind.GENERAL, "one board item or task for each response", built=False),
    Handler("payhoa-tags", HandlerKind.GENERAL, "set PayHOA tags from the answers", built=False),
    Handler("forward-draft", HandlerKind.GENERAL, "draft a forward of each response to a person", built=False),
    # process: tied to the law the form serves
    Handler("owner-information", HandlerKind.PROCESS, "the owner information returns: read, compare, and record in PayHOA",
            ("CIV 4040", "CIV 4041"), "owner-info-cycle"),
    Handler("response-clock", HandlerKind.PROCESS, "a member's request on its clock: classified, acknowledged, and answered "
            "(jason respond; RESPONSE_RULES)", ("CIV 5205", "CIV 5210", "CIV 5215", "CIV 5900", "CIV 5910", "CIV 5915",
                                                "CIV 4525", "CIV 4530", "CIV 5220", "CIV 5225", "CIV 5658", "CIV 5665",
                                                "CIV 5930", "CIV 5935",
                                                "CIV 4045", "CIV 5260", "CIV 5103", "CIV 5105", "CIV 5110", "CIV 5115",
                                                "CIV 4920", "CIV 4925", "CIV 4930", "CIV 4935", "CIV 4760", "CIV 4765",
                                                "CIV 4766", "CIV 4745", "CIV 4745.1", "CIV 714", "CIV 714.1", "CIV 4746",
                                                "CIV 4705", "CIV 4706", "CIV 4710", "CIV 4715", "CIV 4720", "CIV 4725",
                                                "CIV 4735", "CIV 4736", "CIV 4750", "CIV 4751", "CIV 4752", "CIV 4753"),
            "respond"),
)}


def handler(key: str) -> Handler | None:
    return HANDLERS.get(key)


def _base(citation: str) -> str:
    from jason.community.law_text import normal_citation

    found = normal_citation(citation)
    return found[0] if found else citation.strip()


def problems(definition: Any, community: Any = None) -> list[str]:
    """What stops a definition from being made for want of a handler or a procedure: empty when it can be."""
    out: list[str] = []
    key = definition.handler
    row = HANDLERS.get(key) if key else None
    if not key:
        out.append("no handler chosen: a form nobody can process is not made")
    elif row is None:
        out.append(f"handler {key!r} is not registered (the registered handlers: {', '.join(sorted(HANDLERS))})")
    else:
        cited = {_base(c) for c in definition.authority}
        if row.kind is HandlerKind.PROCESS and definition.authority and not cited & {_base(c) for c in row.citations}:
            out.append(f"handler {key!r} serves {', '.join(row.citations)}, not {', '.join(definition.authority)}")
        if row.kind is HandlerKind.GENERAL and definition.authority:
            out.append(f"a form with an authority ({', '.join(definition.authority)}) takes a process handler, not the "
                       f"general handler {key!r}")
        if row.kind is HandlerKind.PROCESS and not definition.authority:
            out.append(f"the process handler {key!r} is for a form with an authority; this form names none")
    if not definition.procedure:
        out.append("no procedure named (jason sop)")
    else:
        from jason.community import procedures

        if procedures.find(definition.procedure, community) is None:
            out.append(f"procedure {definition.procedure!r} does not exist (jason sop lists them)")
    return out


__all__ = ["HANDLERS", "Handler", "HandlerKind", "handler", "problems"]
