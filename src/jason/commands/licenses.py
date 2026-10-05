"""``jason licenses``: the license numbers the association's documents print, who holds each, and where to check it.

``--library`` reads every file the library holds and writes the register ``data/parties/licenses.json`` (private);
FILE reads one file and prints what it finds; with neither, the saved register is printed. Reads disk only: jason does
not look a license up, it gives the board's page for a person to check.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

from jason.commands._shared import data_dir as _data_dir


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    parser = sub.add_parser(
        "licenses",
        help="The license numbers the documents print (contractor, alarm, pest, real estate, insurance, and others), "
             "who holds each, and the board's page to check it",
        description="Finds every license mention (a CSLB number with its class, an alarm operator's ACO, a pest control "
                    "PR, a DRE number, an insurance agent's, a State Bar number, a public works registration) and the "
                    "business it is printed beside. --library sweeps the library into data/parties/licenses.json; FILE "
                    "reads one file. Disk only: the board's page is the authority.",
    )
    add_common(parser)
    parser.add_argument("file", nargs="*", help="files to read (a PDF, a scan, a .txt)")
    parser.add_argument("--library", action="store_true", help="read every file in the library and save the register")
    parser.add_argument("--people", action="store_true", help="also list notaries' commissions and certifications")
    parser.add_argument("--json", action="store_true", help="print JSON")
    parser.set_defaults(func=lambda args: run(args, agent_factory))


def run(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.community.licenses import by_license, find_licenses
    from jason.tasks import licenses as task

    root = _data_dir(args)
    if args.file:
        from jason.tasks.library import text_of

        found = []
        for name in args.file:
            path = Path(name)
            if not path.is_file():
                print(f"jason licenses: no such file: {name}", file=sys.stderr)
                return 2
            text, _how = text_of(path)
            found += [({"id": path.name, "path": str(path)}, m) for m in by_license(find_licenses(text))]
        rows = task.register(found)
    elif args.library:
        rows = task.run_library(root, log=lambda s: print(s, file=sys.stderr))
        print(f"wrote {task.save(root, rows)}", file=sys.stderr)
    else:
        rows = task.load_register(root)
        if not rows:
            print("no register yet: jason licenses --library", file=sys.stderr)
            return 1
    if args.json:
        print(json.dumps(rows, indent=1, ensure_ascii=False))
    else:
        print(task.markdown(rows, personal=args.people))
    return 0


__all__ = ["register", "run"]
