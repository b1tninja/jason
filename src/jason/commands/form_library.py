"""``jason form-library``: the forms built in for the association's law, as it has them (docs/form-library-design.md).

Read-only. It resolves the active community's forms (``Community.forms()``'s source: the library's forms for its
jurisdictions, with its slots, adjustments, and bindings applied, then its own), reads the statutes under the data folder,
and writes nothing.

- No option: the forms by status (ready, adjusted, not offered, failing) with the tier, jurisdiction, version, and as-of
  day, and what is adjusted, missing, or failing.
- ``--tier state|family|custom``: only that tier.
- ``--check``: the seven checks; a finding names the form and the item. Exit 1 if any form fails (a form not offered for
  want of a slot, and a gap a definition names as deferred, are reported and do not fail). ``--json`` for a program.
- ``--show KEY``: one form (by its library key or its template's): its recitals as the shelf holds the words with the as-of
  caveat, its required content with the question that carries each item, its clocks, its slots, and its adjustments.

A refusal prints ``jason form-library: <reason>`` and exits 2.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Callable

TIERS = ("state", "family", "custom")
ORDER = ("ready", "adjusted", "not offered", "failing")


def _refuse(reason: str) -> int:
    print(f"jason form-library: {reason}", file=sys.stderr)
    return 2


def _data_dir(args: argparse.Namespace) -> Any:
    from jason.commands._shared import data_dir

    return data_dir(args)


def _community() -> Any:
    from jason.community import community

    return community()


def _print_json(body: Any) -> None:
    from jason.commands._shared import to_json

    print(to_json(body))


def _where(f: Any) -> str:
    return f"{f.tier.value}" + (f", {f.definition.jurisdiction}" if f.definition.jurisdiction else "")


def _stamp(f: Any) -> str:
    d = f.definition
    return f"v{d.version}" + (f", as of {d.as_of.isoformat()}" if d.as_of else "")


def _form_dict(f: Any, report: Any) -> dict[str, Any]:
    status = report.status(f.key)
    return {**f.definition.as_dict(), "status": status.value if status else f.status.value, "missing": list(f.missing),
            "applied": list(f.applied), "refused": [r.message for r in f.refused], "clocks": [c.as_dict() for c in f.clocks],
            "findings": [x.as_dict() for x in report.for_form(f.key)]}


form_json = _form_dict            # the console's form-library loader reads the same row


def _listing(args: argparse.Namespace, resolved: Any, report: Any) -> int:
    from jason.community.form_library import Tier

    wanted = Tier(args.tier) if args.tier else None
    forms = [f for f in resolved.forms if wanted is None or f.tier is wanted]
    if args.json:
        _print_json({"chain": list(resolved.chain), "forms": [_form_dict(f, report) for f in forms],
                     "problems": [p.as_dict() for p in resolved.problems]})
        return 0
    status = {f.key: report.status(f.key) or f.status for f in forms}
    print(f"Forms in the library for {_community().name} (jurisdictions: {', '.join(resolved.chain) or 'none'}): "
          + ", ".join(f"{sum(1 for s in status.values() if s.value == name)} {name}" for name in ORDER) + ".")
    for name in ORDER:
        rows = [f for f in forms if status[f.key].value == name]
        if not rows:
            continue
        print(f"\n{name} ({len(rows)})")
        for f in rows:
            print(f"  {f.key:24} {_where(f):14} {_stamp(f):26} {f.template.title}")
            for line in f.applied:
                print(f"      adjusted: {line}")
            for gap in f.missing:
                print(f"      not offered, missing: {gap}")
            for problem in f.handler_problems:
                print(f"      cannot be made: {problem}")
            if name == "failing":
                for finding in report.for_form(f.key):
                    if finding.severity.value == "fail":
                        print(f"      {finding.line()}")
            deferred = [x for x in report.for_form(f.key) if x.severity.value == "deferred"]
            if deferred:
                print(f"      {len(deferred)} required item(s) not carried yet (jason form-library --show {f.key})")
    for problem in resolved.problems:
        print(f"\n{problem.line()}")
    if not forms:
        print("\nNo forms" + (f" in the {args.tier} tier." if args.tier else "."))
    print("\n`jason form-library --check` runs the seven checks; `--show KEY` reads one form.")
    return 0


def _check(args: argparse.Namespace, resolved: Any, report: Any) -> int:
    from jason.community.form_library import Tier

    wanted = Tier(args.tier) if args.tier else None
    keys = {f.key for f in resolved.forms if wanted is None or f.tier is wanted}
    findings = [x for x in report.findings if not x.form or x.form in keys]
    failing = [x for x in findings if x.severity.value == "fail"]
    if args.json:
        _print_json({"ok": not failing, "failing": len(failing), "findings": [x.as_dict() for x in findings],
                     "statuses": {k: s.value for k, s in report.statuses if k in keys}})
        return 1 if failing else 0
    for check_name in sorted({x.check for x in findings}, key=lambda c: c.value):
        print(f"{check_name.value}. {check_name.title}")
        for x in (y for y in findings if y.check is check_name):
            print(f"  {x.severity.value:11} {x.line()}")
    counts = {s: sum(1 for x in findings if x.severity.value == s) for s in ("fail", "not offered", "deferred")}
    print(f"{len(keys)} form(s) checked: {counts['fail']} failing, {counts['not offered']} not offered, "
          f"{counts['deferred']} deferred (a gap a definition names).")
    return 1 if failing else 0


def _show(args: argparse.Namespace, resolved: Any, report: Any, data_dir: Any) -> int:
    from jason.community.form_library import Check
    from jason.community.form_library.check import read_recital

    f = resolved.get(args.show)
    if f is None:
        return _refuse(f"no form {args.show!r}; the forms are: {', '.join(x.key for x in resolved.forms) or 'none'}")
    if args.json:
        body = _form_dict(f, report)
        body["recitalWords"] = [read_recital(c, data_dir, community=_community(), full=True).as_dict() for c in f.definition.recitals]
        body["required"] = [{"item": r.item, "authority": r.authority, "carriedBy": list(r.carried_by), "deferred": r.deferred}
                            for r in f.required_content]
        _print_json(body)
        return 0
    d, t = f.definition, f.template
    status = report.status(f.key) or f.status
    print(f"{f.key}: {t.title}")
    print(f"  {_where(f)}; {_stamp(f)}; status {status.value}; the form's own key {t.key.value}"
          + (f"; marker code {t.code}" if t.code else "; no marker code"))
    print(f"  authority: {', '.join(d.authority) or 'none'}; handler {d.handler or 'none'}; procedure {d.procedure or 'none'}; "
          f"channels {', '.join(c.value for c in f.channels) or 'none'}")
    if f.missing:
        print("  not offered, missing: " + "; ".join(f.missing))
    print("\nQuestions")
    for n, q in enumerate(t.questions, 1):
        print(f"  {n:2}. {q.field:34} {q.kind.value:9} {'required' if q.required else 'optional'}  {q.title}")
    print(f"\nRequired content ({len(f.required_content)})")
    by_item = {x.item: x for x in report.for_form(f.key) if x.check is Check.REQUIRED}
    for r in f.required_content:
        where = ", ".join(r.carried_by) if r.carried_by else "-"
        note = ""
        gap = by_item.get(r.item + (f" ({r.authority})" if r.authority else ""))
        if gap is not None:
            note = f"   [{gap.severity.value}: {gap.message}]"
        print(f"  - {r.item}" + (f" ({r.authority})" if r.authority else "") + f" -> {where}{note}")
    print(f"\nRecitals ({len(d.recitals)}), as the shelf holds them" + (f" (the form recites the law as of {d.as_of.isoformat()})" if d.as_of else ""))
    caveats: dict[str, None] = {}
    for citation in d.recitals:
        recital = read_recital(citation, data_dir, community=_community(), full=True)
        for line in recital.lines(caveats=False):
            print(f"  {line}")
        caveats.update(dict.fromkeys("the words of a subdivision are split from its section as jason splits it; the section itself is "
                                     "the source" if "split from the section" in c else c for c in recital.caveats))
    for caveat in caveats:
        print(f"  caveat: {caveat}")
    print(f"\nClocks ({len(f.clocks)})")
    for c in f.clocks:
        print(f"  - {c.words()}" + (f"; {c.note}" if c.note else "") + (f"; if it passes: {c.if_passes}" if c.if_passes else ""))
    if d.slots:
        print(f"\nSlots ({len(d.slots)})")
        given = dict(f.slot_values)
        for name in d.slots:
            print(f"  - {name}: " + (given[name] if name in given else "NOT GIVEN"))
    if f.applied or f.refused:
        print("\nAdjustments")
        for line in f.applied:
            print(f"  applied: {line}")
        for r in f.refused:
            print(f"  REFUSED: {r.item}: {r.message}")
    return 0


def cmd_form_library(args: argparse.Namespace) -> int:
    if args.tier and args.tier not in TIERS:
        return _refuse("--tier is state, family, or custom")
    if args.show and (args.check or args.tier):
        return _refuse("--show reads one form; it does not go with --check or --tier")
    from jason.community.form_library.check import check
    from jason.community.form_library.resolve import resolve

    community = _community()
    data_dir = _data_dir(args)
    resolved = resolve(community)
    report = check(resolved, data_dir, community=community)
    if args.show:
        return _show(args, resolved, report, data_dir)
    if args.check:
        return _check(args, resolved, report)
    return _listing(args, resolved, report)


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("form-library", help="The forms built in for the association's law, as it has them: by tier and status, "
                                            "the seven checks, and one form's recitals and clocks (read-only; "
                                            "docs/form-library-design.md)")
    add_common(p)
    p.add_argument("--check", action="store_true",
                   help="run the seven checks (required content, recitals, slots, adjustments, handler, marker codes, what a "
                        "binding forbids); exit 1 if any form fails")
    p.add_argument("--show", metavar="KEY", help="one form by its library key or its template's: recitals as the words, required "
                                                 "content, clocks, slots, adjustments")
    p.add_argument("--tier", choices=TIERS, metavar="T", help="only this tier: state, family, or custom")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_form_library)
