"""``jason chronology`` and ``jason fact-conflicts``: two lenses for a careful reading of a set of documents.

Both read a slice of the passage index (``jason index --build``), chosen with the index's scope flags: ``--catalog``,
``--standing``, ``--kind``, ``--folder``, and ``--confidential`` for the files held back unless asked. Naming a legal
case's catalog (``case-<key>``) opens that case's confidential files, as the document search does; ``--confidential``
never opens a case catalog that is not named.

- ``jason chronology`` lists every dated statement in the scope, in date order, each quoted with its file, passage,
  and position, and labeled as the document's own date or a date the text speaks about
  (``jason.community.chronology``). ``--from`` and ``--to`` keep a range of dates. For a legal case's catalog the
  specification's own events are shown apart, as the specification's record.
- ``jason fact-conflicts`` lists where two documents give different values for what a rule takes to be the same fact,
  with both sides quoted and neither picked (``jason.community.fact_conflicts``).

``--write`` saves the generated page under ``data/collections/<slug>/`` (``chronology.md``, ``conflicts.md``) under
the store lock; without it nothing is written. A page says it is generated, that it is a summary and not the record,
and that it is confidential when any source is. Both are rule-based: no model, no network.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable


def scope_of(args: argparse.Namespace, data: Any):
    """The index scope the flags name. Held files open by catalog: a case's only when it is named; any other catalog's
    only with ``--confidential`` (the document search's rule, ``jason.mcp.county``). A collection's generated pages
    are left out, whatever is named: a lens reads documents, never a page a lens wrote
    (``document_collections.NOT_MEMBERS``). Raises ``ValueError`` for an unknown standing."""
    from jason.community import passage_index as pi
    from jason.community.document_collections import NOT_MEMBERS
    from jason.tasks.case_files import is_case_catalog

    catalogs = tuple(args.catalog)
    standings = tuple(pi.Standing(s) for s in args.standing)
    held = tuple(c for c in (catalogs or (pi.catalogs(data) if args.confidential else ()))
                 if (c in catalogs if is_case_catalog(c) else args.confidential))
    return pi.Scope(catalogs=catalogs, standings=standings, kinds=tuple(args.kind), folders=tuple(args.folder),
                    confidential_in=held, not_folders=NOT_MEMBERS)


def title_of(args: argparse.Namespace) -> str:
    """The title given, else the scope's own words ("library insurance_policy")."""
    if args.title:
        return args.title
    return " ".join([*args.catalog, *args.kind, *args.folder]) or "all records"


def named_case(catalogs: tuple[str, ...]) -> Any | None:
    """The specification's legal case whose catalog is the one case catalog named, or None."""
    from jason.tasks.case_files import catalog_name, is_case_catalog

    named = [c for c in catalogs if is_case_catalog(c)]
    if len(named) != 1:
        return None
    try:
        from jason.community import community

        cases = community().legal_cases()
    except Exception:  # noqa: BLE001 - a profile that cannot be read has no record to show; the documents still read
        return None
    return next((case for case in cases if catalog_name(case).lower() == named[0].lower()), None)


def _prepare(args: argparse.Namespace) -> tuple[Any, Any] | int:
    from jason.community import passage_index as pi
    from jason.config import data_dir as active_data_dir

    data = active_data_dir(getattr(args, "env", None))
    try:
        return data, scope_of(args, data)
    except ValueError:
        print(f"standings: {', '.join(s.value for s in pi.Standing)}", file=sys.stderr)
        return 2


def _say(line: str) -> None:
    """Print a line; a character the console's encoding lacks is shown as its escape, never dropped (a quote stays
    checkable against the file)."""
    try:
        print(line)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        print(line.encode(encoding, errors="backslashreplace").decode(encoding))


def _finish(args: argparse.Namespace, data: Any, result: Any, page: str) -> int:
    from jason.community.chronology import slug_of, write_page

    if args.json:
        print(json.dumps(result.as_dict(), indent=1))
    else:
        for line in result.lines():
            _say(line)
    if args.write:
        path = write_page(data, slug_of(result.title), page, result.markdown())
        print(f"wrote {path}" + (" (confidential: for directors and counsel)" if result.confidential else ""),
              file=sys.stderr)
    return 0


def cmd_chronology(args: argparse.Namespace) -> int:
    from jason.commands._shared import day
    from jason.community.chronology import CHRONOLOGY_PAGE, chronology

    prepared = _prepare(args)
    if isinstance(prepared, int):
        return prepared
    data, scope = prepared
    try:
        since, until = day(args.since), day(args.until)
    except ValueError:
        print("--from and --to take a date as YYYY-MM-DD", file=sys.stderr)
        return 2
    case = named_case(scope.catalogs)
    try:
        result = chronology(data, scope, title_of(args), since=since, until=until,
                            recorded=case.events if case is not None else (),
                            recorded_confidential=bool(getattr(case, "confidential", True)))
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return _finish(args, data, result, CHRONOLOGY_PAGE)


def cmd_fact_conflicts(args: argparse.Namespace) -> int:
    from jason.community.fact_conflicts import CONFLICTS_PAGE, fact_conflicts

    prepared = _prepare(args)
    if isinstance(prepared, int):
        return prepared
    data, scope = prepared
    try:
        result = fact_conflicts(data, scope, title_of(args))
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return _finish(args, data, result, CONFLICTS_PAGE)


def _scope_flags(p: Any) -> None:
    p.add_argument("--catalog", action="append", default=[], metavar="NAME",
                   help="only this index catalog (repeat); a legal case's catalog, case-<key>, opens its own held files")
    p.add_argument("--standing", action="append", default=[], help="authority, record, reference, page, or evidence (repeat)")
    p.add_argument("--kind", action="append", default=[], metavar="K", help="only this document kind (repeat)")
    p.add_argument("--folder", action="append", default=[], metavar="F", help="only under this data folder (repeat)")
    p.add_argument("--confidential", action="store_true", help="include the files held back unless asked")
    p.add_argument("--title", default="", help="the collection's title (default: the scope's own words)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--write", action="store_true",
                   help="save the generated page under data/collections/<slug>/; without it nothing is written")


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("chronology", help="Every dated statement in a slice of the passage index, in date order, each "
                                          "quoted with its source (what the documents say, not what happened)")
    add_common(p)
    _scope_flags(p)
    p.add_argument("--from", dest="since", default="", metavar="DATE", help="keep dates from this day (YYYY-MM-DD)")
    p.add_argument("--to", dest="until", default="", metavar="DATE", help="keep dates to this day (YYYY-MM-DD)")
    p.set_defaults(func=cmd_chronology)

    p = sub.add_parser("fact-conflicts", help="Where two documents in a slice of the passage index give different values "
                                              "for the same fact: both sides quoted, neither picked")
    add_common(p)
    _scope_flags(p)
    p.set_defaults(func=cmd_fact_conflicts)
