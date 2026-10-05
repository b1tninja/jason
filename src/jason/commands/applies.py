"""``jason applies``: which recurring duties reach each of the association's life safety systems.

Each obligation carries what it applies to (``Obligation.applies``, a ``jason.community.applicability`` condition), and
the profile states its systems (``Community.life_safety_systems()``). This asks every obligation that names a system of
every system and prints three groups a system: what applies, what is undetermined with the question that settles it,
and what does not apply with the fact that decided it and where that fact comes from. Undetermined is never read as
"does not apply" (docs/applicability.md, section 2).

A person's answers in the intake queue (``data/intake/asks.json``) are read as facts with source ``answer``. An answer
that disagrees with the specification leaves the row undetermined with both named.

``--system KEY`` shows one system, ``--all`` adds the obligations asked of the association as a whole, and ``--json``
prints the same as JSON. ``--questions`` lists the questions the undetermined answers raise, one a subject and fact,
each with the rows it would decide, the kinds of record that would settle it, and its state in the queue.

The questions also cover the association's standing facts that the notice catalog turns on (whether an election rule
allows electronic secret ballots, whether the documents require a quorum for an election of directors, whether the
board keeps seating by acclamation available), where the profile does not state them
(``Community.applicability_facts()``). They are asked under ``applies:association``. A fact of one event is not asked:
``jason notices --catalog --fact`` says it.

Read-only, except ``--file-questions``: a person's command that parks those questions in the intake queue, where
``jason intake --answer ID TEXT --by NAME`` (or the MCP tool ``answer_intake_question``) answers one. Nothing is filed
on its own.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from typing import Any, Callable

from jason.commands._shared import data_dir as _data_dir


def cmd_applies(args: argparse.Namespace) -> int:
    from jason.community import community
    from jason.community.applicability_asks import question_lines, questions
    from jason.community.life_safety import applicability_lines
    from jason.tasks import applicability_asks as asks_task

    active = community()
    data_dir = _data_dir(args)
    day = date.fromisoformat(args.as_of) if args.as_of else date.today()
    result, found = asks_task.evaluate(active, data_dir, as_of=day)
    # The notice catalog's rows that wait on a standing fact of the association's join the same questions.
    asked = questions(result, asks_task.standing(active, found, as_of=day))
    if args.file_questions:
        counts = asks_task.file_questions(data_dir, asked)
        print(f"filed {len(asked)} questions in {data_dir / 'intake' / 'asks.json'}: {counts['new']} new, "
              f"{counts['kept']} already there (an answer is kept), {counts['stale']} no longer asked")
        print("answer one: jason intake --answer ID TEXT --by NAME; list them: jason intake --kind applicability")
    if args.questions or args.file_questions:
        stored = asks_task.stored(data_dir)
        if args.json:
            by_id = {a.id: a for a in stored}
            print(json.dumps({"community": active.name, "asOf": day.isoformat(),
                              "questions": [{**q.as_dict(), "filed": q.id in by_id,
                                             "status": by_id[q.id].status.value if q.id in by_id else None,
                                             "answer": by_id[q.id].answer if q.id in by_id else ""} for q in asked],
                              "answersInUse": [{"id": a.id, **v.as_dict()} for a, v in found.used],
                              "answersNotRead": [{"id": a.id, "answer": a.answer, "why": why}
                                                 for a, why in found.unread]}, indent=1))
            return 0
        print(f"{active.name}: the questions the undetermined answers raise, as of {day.isoformat()}")
        print("One question a subject and fact. An answer is recorded with who gave it and when, and is read as a fact")
        print("with source \"answer\". Where it disagrees with the specification, the row stays undetermined with both.")
        print()
        for line in question_lines(asked, stored, found):
            print(line)
        if any(q.id not in {a.id for a in stored} for q in asked):
            print()
            print("A question marked not filed is not in the intake queue yet: jason applies --file-questions parks it.")
        return 0
    if args.system:
        system = next((s for s in result.systems if s.key == args.system), None)
        if system is None:
            print("systems: " + (", ".join(s.key for s in result.systems) or "none listed"), file=sys.stderr)
            return 2
        result = result.of(system)
    if args.json:
        print(json.dumps({"community": active.name, "asOf": day.isoformat(), **result.as_dict()}, indent=1))
        return 0
    print(f"{active.name}: what applies to each life safety system, as of {day.isoformat()}")
    print("Each answer rests on the facts the specification states, shown with where each comes from. An undetermined")
    print("answer is a question for a person, not \"does not apply\". A rule's scope is recited from its row; read the")
    print("authority before relying on it.")
    print()
    for line in applicability_lines(result, association=args.all):
        print(line)
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("applies", help="Which recurring duties apply to each life safety system, which do not and why, "
                                       "and which are undetermined (read-only, except --file-questions)")
    add_common(p)
    p.add_argument("--system", metavar="KEY", help="only this system (its key in the specification)")
    p.add_argument("--all", action="store_true", help="also the obligations asked of the association as a whole")
    p.add_argument("--as-of", metavar="YYYY-MM-DD", help="the date asked for (default: today)")
    p.add_argument("--questions", action="store_true",
                   help="list the questions the undetermined answers raise, with each one's state in the intake queue; "
                        "they include the association's standing facts the notice catalog turns on")
    p.add_argument("--file-questions", action="store_true",
                   help="park those questions in the intake queue (data/intake/asks.json) for a person to answer")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_applies)
