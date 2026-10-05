"""The applicability questions against the intake queue: read the answers, and file the questions.

``jason.community.applicability_asks`` makes the questions and reads the answers; this module is its store side, over
the one intake queue (``data/intake/asks.json``):

- ``answers(data_dir)`` reads the answered questions as facts (read-only);
- ``evaluate(community, data_dir)`` is ``life_safety.applicable`` with those facts, so a caller with a data folder
  gets a person's answers without knowing about the queue;
- ``association_facts(community, data_dir)`` are the association's own facts as a notice row is asked them: the
  profile's, then a person's answers about the association (read-only);
- ``standing(community, found)`` are the notice catalog's rows and elements that wait on a standing fact the
  profile does not state, as findings for ``applicability_asks.questions(result, also=...)``;
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
from jason.community.applicability import Facts, profile_facts
from jason.community.applicability_asks import SCOPE, Answered, FactQuestion, answered, standing_findings
from jason.community.intake import Ask, AskKind
from jason.community.life_safety import Finding, SystemApplicability, applicable


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


def association_facts(community: Any, data_dir: Path | None = None, *, found: Answered | None = None,
                      as_of: date | None = None) -> Facts:
    """The association's own facts: the profile's (``Community.applicability_facts()``), then a person's answers
    about the association from the queue (source ``ANSWER``). An answer that disagrees with the profile is kept
    beside it, so a row that turns on the fact stays undetermined with both named. With no queue, the profile's."""
    if found is None:
        found = answers(data_dir) if data_dir is not None else Answered({})
    return Facts.build(profile=profile_facts(community), as_of=as_of).merge(found.facts.get(None, ()))


def standing(community: Any, found: Answered, *, as_of: date | None = None,
             rows: Iterable[Any] | None = None) -> tuple[Finding, ...]:
    """The notice catalog's rows and elements that wait on a standing fact of the association's: one the profile
    does not state and no person has answered, or one two sources disagree on. ``rows`` default to the catalog's
    conditions (``notice_elements.conditionals()``)."""
    if rows is None:
        from jason.community.notice_elements import conditionals

        rows = conditionals()
    return standing_findings(rows, association_facts(community, found=found, as_of=as_of))


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


__all__ = ["stored", "answers", "evaluate", "association_facts", "standing", "file_questions"]
