"""``jason cross-checks``: what each agenda item linked beside what the minutes of that meeting recorded (read-only)."""

from __future__ import annotations

import argparse
import json
from typing import Any, Callable


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    parser = sub.add_parser(
        "cross-checks",
        help="Agenda items against the minutes: amounts, prior minutes, insurance renewals, stale items (read-only)",
        description="Reads the agenda items (jason agenda-items), the minutes readings (jason models), the meeting catalog, "
                    "and the Drive and library listings already on disk, and sets what each agenda linked beside what the "
                    "minutes recorded. Writes data/meetings/cross-checks.json. Each result is a lead for a person.",
    )
    add_common(parser)
    parser.add_argument("--ask-model", action="store_true",
                        help="ask the local model one grounded question per unmatched document with an amount (a few calls)")
    parser.add_argument("--max-questions", type=int, default=3, metavar="N", help="at most N model questions (default 3)")
    parser.add_argument("--model", default="", help="the local model (default: the extractor's)")
    parser.add_argument("--limit", type=int, default=8, help="lines per section in the summary")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from jason.config import Settings
    from jason.tasks.cross_checks import build, summary_lines

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    ask = None
    if args.ask_model:
        from jason.community.ollama_extractor import DEFAULT_MODEL
        from jason.local_ai import preflight
        from jason.tasks.model_questions import _asker

        model = args.model or DEFAULT_MODEL
        preflight(model)
        ask = _asker(model)
    result = build(data_dir, ask=ask, max_questions=args.max_questions, log=print if args.ask_model else None)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print("\n".join(summary_lines(result, limit=args.limit)))
        print(f"wrote {data_dir / 'meetings' / 'cross-checks.json'}")
    return 0


__all__ = ["register", "run"]
