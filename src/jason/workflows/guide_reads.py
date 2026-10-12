"""The guide reads: what a step's ``LookAt`` counts for the person about to act (docs/workflows/person-steps.md, section 4.1).

A guide read is read-only, like a ``check``: ``read(readers, view, step, args) -> Looked``. It returns a count, at most five row titles
(an id or a title, never an owner's name, contact detail, or answer), the references a page may link, and the day it was read. A read
that cannot read says so in ``unavailable`` and returns no count: the panel never says "nothing to look at" for a read that failed
(``run_read`` turns an exception into that). Each read is a row of ``READS``; ``validate`` refuses a ``LookAt`` that names
one that does not exist.

This is an edge module like ``readers``: it reads jason's own stores on disk (the response inbox) and writes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

from jason.workflows.types import RunView, StepDef

MAX_ROWS = 5


@dataclass(frozen=True)
class Looked:
    """One read's answer. ``count`` is ``None`` when it could not read (then ``unavailable`` says why)."""

    count: int | None = None
    rows: tuple[str, ...] = ()
    refs: tuple[str, ...] = ()
    as_of: str = ""
    unavailable: str = ""
    screen: str = ""                     # the console screen the rows live on, for an "Open in NAME" link
    screen_name: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


GuideRead = Callable[[Any, RunView, StepDef, "tuple[str, ...]"], Looked]


def names() -> frozenset[str]:
    return frozenset(READS)


def run_read(name: str, readers: Any, view: RunView, sd: StepDef, args: tuple[str, ...] = (), *, today: date | None = None) -> Looked:
    """Ask a read, and never raise: an unknown read, a store that cannot be read, or an exception is a ``Looked`` that says so."""
    day = (today or date.today()).isoformat()
    fn = READS.get(name)
    if fn is None:
        return Looked(as_of=day, unavailable=f"the read {name!r} is not registered")
    try:
        got = fn(readers, view, sd, tuple(args))
    except Exception as exc:  # noqa: BLE001 - a read that fails says so; it never shows "nothing to look at"
        return Looked(as_of=day, unavailable=f"{type(exc).__name__}: {exc}")
    return Looked(got.count, tuple(got.rows[:MAX_ROWS]), tuple(got.refs), got.as_of or day, got.unavailable, got.screen, got.screen_name,
                  dict(got.extra))


# --- the response inbox: arrivals to read and to confirm ------------------------------------------------------------------------

def _arrivals(readers: Any, view: RunView, states: tuple[str, ...]) -> Looked:
    """The inbox's arrivals, for the requests whose return-by date is the run's, in the given states. Rows are arrival ids
    (``channel:native id``): a handle, never the sender or the unit."""
    from jason.community.response_inbox import State
    from jason.tasks import response_inbox as inbox

    wanted = {State(s) for s in states}
    requests = readers.requests_of(view)
    if not requests:
        return Looked(unavailable=f"no response request in the profile has the return-by date {view.dates.get('return_by', '?')}")
    keys = {r.key for r in requests}
    found = sorted(a.id for a in inbox.load_inbox(readers.data_dir).arrivals.values()
                   if a.request in keys and not a.superseded_by and a.state in wanted)
    return Looked(len(found), tuple(found), refs=tuple(found), screen="responses", screen_name="Responses")


def responses_new(readers: Any, view: RunView, sd: StepDef, args: tuple[str, ...] = ()) -> Looked:
    """Arrivals nobody has read yet (new, or seen and left)."""
    return _arrivals(readers, view, ("new", "seen"))


def responses_unconfirmed(readers: Any, view: RunView, sd: StepDef, args: tuple[str, ...] = ()) -> Looked:
    """Arrivals whose attachments were read and whose reading no person has confirmed."""
    return _arrivals(readers, view, ("read",))


READS: dict[str, GuideRead] = {"responses-new": responses_new, "responses-unconfirmed": responses_unconfirmed}
"""The registered guide reads, by the name a ``LookAt`` gives. A new read is a function above and a row here; two never share a name."""


__all__ = ["GuideRead", "Looked", "MAX_ROWS", "READS", "names", "run_read"]
