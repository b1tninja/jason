"""The loss packet: five questions asked in order about a loss in a unit, each with the provisions that speak to it.

The profile supplies the ladder (``Community.loss_ladder()``): step, question, and the provisions as ``cite_document``
expressions. This module assembles a packet from inputs a loader has gathered. It never retypes a provision: each step carries
the expressions, and the words the loader recited sit only in ``recited``. It says what the record shows and who confirmed it.
It never says a loss is or is not insured or who is at fault: the carrier decides coverage, and the board and counsel decide
responsibility. A step with a missing provision, or the deductible step with no adopted guideline, carries a ``held`` note.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

STEP_COUNT = 5


@dataclass(frozen=True)
class LadderStep:
    """A profile's row: one question and the provisions that bear on it."""

    step: int
    question: str
    provisions: tuple[str, ...] = ()  # cite_document expressions
    open: tuple[str, ...] = ()  # open-question keys that touch this step


@dataclass(frozen=True)
class OpenQuestion:
    key: str
    title: str
    with_whom: str = ""
    status: str = "open"
    asked: str = ""
    answered: str = ""
    source: str = ""


@dataclass(frozen=True)
class StepRecord:
    """What the record shows for one step, and who confirmed it (a person, never jason)."""

    shows: tuple[str, ...] = ()
    confirmed_by: str = ""
    confirmed_at: str = ""


@dataclass(frozen=True)
class PacketStep:
    step: int
    question: str
    provisions: tuple[str, ...]
    recited: tuple[str, ...]  # the words the loader recited, in the order of ``provisions`` found
    shows: tuple[str, ...]
    confirmed_by: str
    confirmed_at: str
    state: str  # "confirmed" or "unconfirmed"
    held: str = ""
    open: tuple[str, ...] = ()


@dataclass(frozen=True)
class LossPacket:
    unit: str
    incident: str
    steps: tuple[PacketStep, ...]
    history: tuple[str, ...] = ()
    open_questions: tuple[OpenQuestion, ...] = ()
    confirmed: bool = False
    note: str = ""


def assemble(
    unit: str,
    incident: str,
    record: Mapping[int, StepRecord] | None,
    ladder: Sequence[LadderStep],
    policy: Any,
    history: Sequence[str] = (),
    guideline: Any = None,
    *,
    recited: Mapping[str, str] | None = None,
    questions: Sequence[OpenQuestion] = (),
) -> LossPacket:
    """Build a packet over what the loader gathered.

    ``recited`` maps a provision expression to the words the loader recited for it; an expression with no entry is a miss.
    ``policy`` is the unit's policy record (None when none is on file). ``guideline`` is the board's adopted deductible
    guideline (None until adopted). ``questions`` are the association's open questions; a step lists those its row names.
    """
    record = record or {}
    recited = recited or {}
    steps: list[PacketStep] = []
    for row in sorted(ladder, key=lambda r: r.step):
        found = tuple(recited[p] for p in row.provisions if p in recited)
        missing = [p for p in row.provisions if p not in recited]
        held: list[str] = []
        if not row.provisions:
            held.append("No provision is on file for this step.")
        elif missing:
            held.append("Provision not found on file: " + ", ".join(missing) + ".")
        if row.step == 3 and policy is None:
            held.append("No policy is on file for this unit.")
        if row.step == STEP_COUNT and guideline is None:
            held.append("The board has not adopted a deductible guideline.")
        rec = record.get(row.step, StepRecord())
        confirmed = bool(rec.confirmed_by and rec.confirmed_at)
        steps.append(
            PacketStep(
                step=row.step,
                question=row.question,
                provisions=row.provisions,
                recited=found,
                shows=rec.shows,
                confirmed_by=rec.confirmed_by,
                confirmed_at=rec.confirmed_at,
                state="confirmed" if confirmed else "unconfirmed",
                held=" ".join(held),
                open=row.open,
            )
        )
    all_confirmed = bool(steps) and all(s.state == "confirmed" for s in steps)
    keys = {k for s in steps for k in s.open}
    note = "" if all_confirmed else "Unconfirmed: a person has not confirmed every step."
    return LossPacket(
        unit=unit,
        incident=incident,
        steps=tuple(steps),
        history=tuple(history),
        open_questions=tuple(q for q in questions if q.key in keys),
        confirmed=all_confirmed,
        note=note,
    )
