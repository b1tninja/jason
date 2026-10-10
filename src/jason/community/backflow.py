"""The association's backflow prevention program, and its life-safety watchlist, as records the profile states.

Nothing here names an association. A profile fills ``Community.backflow_program()`` (None until it does) and
``Community.life_safety_watch()`` (empty until it does); a view reads them with the notices and the test reports on disk
(``jason.tasks.backflow``). The records hold what a letter or a test report prints, as printed, with the record each came
from: jason enters no figure it did not read, and no source is picked over another.

- ``BackflowAssembly``: one device on a water service, with the id each source gives it (a county's assembly id, a city's
  backflow id), its serial, and the account and meter it matches on the supplier's bills;
- ``ProgramNotice``: a notice that starts a clock, with each date the clock could run from. jason does not choose one;
- ``TesterRef``: the tester as the test reports print them, to look up on the program's published lists;
- ``BackflowProgram``: the program's name, its assemblies, its notices, its tester, and where its lists are;
- ``WatchEntry``: one life-safety item the board should be able to see: its standing in words, what is on file, what
  would change it, and what was searched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Service(Enum):
    IRRIGATION = "irrigation"
    DOMESTIC = "domestic"
    FIRE = "fire"


class AssemblyType(Enum):
    RP = "RP"                   # reduced pressure principle
    DC = "DC"                   # double check
    PVB = "PVB"                 # pressure vacuum breaker
    AG = "AG"                   # air gap


class Standing(Enum):
    """A watchlist item's standing, in the words the console shows. ``UNKNOWN`` is never "not done"."""

    OVERDUE = "overdue"
    UNKNOWN = "unknown"
    PARTLY_ANSWERED = "partly answered"
    CURRENT = "current"
    NOT_APPLICABLE = "not applicable"


@dataclass(frozen=True)
class BackflowAssembly:
    """One backflow prevention assembly. ``ids`` is ``((source, id), ...)``; ``last_passed`` and ``last_failed`` are
    ISO dates a record prints, or "". ``source`` names the record the row was read from."""

    service: Service
    kind: AssemblyType
    size_in: float
    serial: str
    location: str
    ids: tuple[tuple[str, str], ...] = ()
    account: str = ""
    meter: str = ""
    test_due: str = ""
    last_passed: str = ""
    last_failed: str = ""
    tag: str = ""
    history: tuple[tuple[str, str, str], ...] = ()       # (ISO date, "passed" | "failed" | "repaired" | "not read", document name)


@dataclass(frozen=True)
class ProgramNotice:
    """A notice with a clock. ``basis`` is the notice's own words for it; ``days`` the days it gives; ``runs_from`` each
    date the clock could run from, as ``(label, ISO date)`` with the label "dated", "postmarked", "scanned", or "failed
    test"; ``settled_on`` the ISO date the thing it asks for was done ("" while open); ``document`` its name."""

    program: str
    basis: str
    days: int
    runs_from: tuple[tuple[str, str], ...]
    settled_on: str = ""
    document: str = ""
    caveat: str = "Which date counts is the program's to say."


@dataclass(frozen=True)
class TesterRef:
    """The tester as the reports print them. ``name`` is the person; ``business`` the company on the report;
    ``certificate`` the certificate number as printed (not verified)."""

    name: str
    business: str = ""
    certificate: str = ""


@dataclass(frozen=True)
class TesterList:
    """A published list of certified testers: where it is, so a person can fetch it. ``name`` is the program's."""

    name: str
    url: str


@dataclass(frozen=True)
class BackflowProgram:
    program: str
    supplier: str
    assemblies: tuple[BackflowAssembly, ...] = ()
    notices: tuple[ProgramNotice, ...] = ()
    tester: TesterRef | None = None
    lists: tuple[TesterList, ...] = ()
    # What another source says about the number of devices: ``(source, service, count, document)``. A count that differs
    # from the assemblies' is shown beside them, never settled.
    counts: tuple[tuple[str, str, int, str], ...] = ()


@dataclass(frozen=True)
class WatchEntry:
    """One watchlist item. ``obligation`` names an obligation row whose calendar standing the item takes (a standing the
    calendar computes is not repeated here); otherwise ``standing`` is entered. ``evidence`` are document names under the
    library or Drive, ``changes`` what would change the standing, ``searched`` how the records were looked through."""

    item: str
    standing: Standing = Standing.UNKNOWN
    obligation: str = ""
    evidence: tuple[str, ...] = ()
    changes: str = ""
    searched: str = ""


__all__ = ["AssemblyType", "BackflowAssembly", "BackflowProgram", "ProgramNotice", "Service", "Standing", "TesterList",
           "TesterRef", "WatchEntry"]
