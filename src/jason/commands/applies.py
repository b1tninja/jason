"""``jason applies``: which recurring duties reach each of the association's life safety systems.

Each obligation carries what it applies to (``Obligation.applies``, a ``jason.community.applicability`` condition), and
the profile states its systems (``Community.life_safety_systems()``). This asks every obligation that names a system of
every system and prints three groups a system: what applies, what is undetermined with the question that settles it,
and what does not apply with the fact that decided it and where that fact comes from. Undetermined is never read as
"does not apply" (docs/applicability.md, section 2).

Read-only: it reads the specification and nothing else. ``--system KEY`` shows one system, ``--all`` adds the
obligations asked of the association as a whole, and ``--json`` prints the same as JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from typing import Any, Callable


def cmd_applies(args: argparse.Namespace) -> int:
    from jason.community import community
    from jason.community.life_safety import applicability_lines, applicable

    active = community()
    day = date.fromisoformat(args.as_of) if args.as_of else date.today()
    result = applicable(active, as_of=day)
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
                                       "and which are undetermined (read-only)")
    add_common(p)
    p.add_argument("--system", metavar="KEY", help="only this system (its key in the specification)")
    p.add_argument("--all", action="store_true", help="also the obligations asked of the association as a whole")
    p.add_argument("--as-of", metavar="YYYY-MM-DD", help="the date asked for (default: today)")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_applies)
