"""The applicability questions against the intake queue: read the answers, and file the questions.

``jason.community.applicability_asks`` makes the questions and reads the answers; this module is its store side, over
the one intake queue (``data/intake/asks.json``):

- ``answers(data_dir)`` reads the answered questions as facts (read-only);
- ``evaluate(community, data_dir)`` is ``life_safety.applicable`` with those facts, so a caller with a data folder
  gets a person's answers without knowing about the queue;
- ``file_questions(data_dir, questions)`` parks the questions in the queue under the store lock. It runs only from a
  person's command (``jason applies --file-questions``). A question already there keeps its answer and status, a new
  one is added, and an open one this run no longer raises is stale.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from jason.community import intake
from jason.community.applicability_asks import SCOPE, Answered, FactQuestion, answered
from jason.community.intake import Ask, AskKind
from jason.community.life_safety import SystemApplicability, applicable


def stored(data_dir: Path) -> list[Ask]:
    """The applicability questions the queue holds; empty when there is no queue."""
    return [a for a in intake.load(Path(data_dir)) if a.kind is AskKind.APPLICABILITY]


def answers(data_dir: Path) -> Answered:
    return answered(stored(data_dir))


def evaluate(community: Any, data_dir: Path, *, as_of: date | None = None,
             rows: Iterable[Any] | None = None) -> tuple[SystemApplicability, Answered]:
    """Each row's answer for each system, with the queue's answers as facts; and the answers as they were read."""
    found = answers(data_dir)
    return applicable(community, rows, as_of=as_of, answers=found.facts), found


def file_questions(data_dir: Path, asked: Iterable[FactQuestion]) -> dict[str, int]:
    """Park the questions in the intake queue. Returns how many are new, were there already, and went stale."""
    from jason.locks import Resource, hold

    data_dir = Path(data_dir)
    fresh = [q.ask() for q in asked]
    with hold(Resource.STORE, "intake-asks", timeout=120, purpose="jason applies --file-questions"):
        before = intake.load(data_dir)
        had = {a.id: a.status for a in before}
        after = intake.merge(before, fresh, scope=SCOPE)
        intake.save(data_dir, after)
    counts = Counter("new" if a.id not in had else "kept" for a in fresh)
    stale = sum(1 for a in after if a.status is intake.AskStatus.STALE and had.get(a.id) is intake.AskStatus.OPEN)
    return {"new": counts["new"], "kept": counts["kept"], "stale": stale}


__all__ = ["stored", "answers", "evaluate", "file_questions"]
