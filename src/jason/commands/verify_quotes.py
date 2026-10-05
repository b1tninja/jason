"""``jason verify-quotes``: check an answer's quotations and citations against jason's stored words.

An answer written from search hits (``jason index --search``, ``document_search``) is checked before it is given
(``jason.community.quote_check``):

- ``jason verify-quotes FILE`` reads the answer from a file; ``-`` or no file reads it from standard input.
- Each quotation is FOUND (exact, or normalized: the same after folding whitespace, quote marks, a hyphen between
  letters at a line's end, Markdown's emphasis marks, and capitalization), ALTERED (the stored words are printed
  beside the quoted ones, each difference marked ``[[so]]``), MISATTRIBUTED (stored, but not in the provision the
  answer names), or NOT FOUND.
- Each statute section and document section the answer cites is listed with whether jason holds it and its digest.
- ``--sources`` gives the hits the answer was written from (a file of them, or the text itself): file paths with
  passage numbers, citations, or the hits as JSON. A quotation found outside them is flagged.
- ``--confidential`` names confidential files and shows their words; without it one is reported as held back.
- ``--as-of DAY`` checks a statute's quotation against the version in force that day, where the disk shows it; a
  quotation of another version is OTHER VERSION, named with its digest and range. Without it a statute's words are
  the words on the shelf now.
- ``--json`` prints the same as JSON.

It exits 0 when every quotation checked is FOUND, 1 when one is not, and 2 when there is no index. It checks words,
not meaning, and reads only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable


def _read(name: str | None) -> str:
    if name in (None, "", "-"):
        return sys.stdin.buffer.read().decode("utf-8-sig", errors="replace")
    return Path(name).read_text(encoding="utf-8-sig", errors="replace")


def cmd_verify_quotes(args: argparse.Namespace) -> int:
    from jason.commands._shared import data_dir
    from jason.community import quote_check

    try:
        answer = _read(args.file)
    except OSError as exc:
        print(f"cannot read the answer: {exc}", file=sys.stderr)
        return 2
    sources = args.sources or ""
    if sources and Path(sources).is_file():
        sources = Path(sources).read_text(encoding="utf-8-sig", errors="replace")
    as_of = None
    if getattr(args, "as_of", None):
        from datetime import date

        try:
            as_of = date.fromisoformat(args.as_of)
        except ValueError:
            print(f"--as-of takes a day as YYYY-MM-DD, not {args.as_of!r}", file=sys.stderr)
            return 2
    try:
        report = quote_check.check(answer, data_dir(args), sources=sources, include_confidential=args.confidential,
                                   as_of=as_of)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report.as_dict(), indent=1))
    else:
        print("\n".join(report.lines()))
    return 0 if report.clean else 1


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("verify-quotes", help="Check an answer's quotations and citations against jason's stored words: "
                                             "found, altered, misattributed, or not found, and where")
    add_common(p)
    p.add_argument("file", nargs="?", help="the answer's text file; - or nothing reads standard input")
    p.add_argument("--sources", metavar="FILE_OR_TEXT",
                   help="the hits the answer was written from: paths with passage numbers (governing/rules.md#3), "
                        "citations (CIV 5855), or the hits as JSON; a file of them, or the text")
    p.add_argument("--confidential", action="store_true",
                   help="name confidential files and show their words (for directors and counsel)")
    p.add_argument("--as-of", dest="as_of", metavar="DAY",
                   help="check a statute's quotation against the version in force on this day (YYYY-MM-DD), where the "
                        "disk shows it; a quotation of another version is OTHER VERSION, named")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_verify_quotes)
