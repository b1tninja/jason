"""``jason discover-forms``: find the requests a member makes that a standard form could take (docs/standard-forms.md).

The pass is the one that document describes under "How to find them": seed from the statutes and the governing documents
with general phrase patterns (no model), join a statute with the document sections that carry it out, read each span with
the local model (``--read`` only), and let a person confirm, hold, or drop each candidate. The records, the seeds, and the
acts are ``jason.tasks.form_discovery``; this module is the command line over them.

- No option: what is on disk (``data/forms/candidates.json``), by status and source, and what to run next.
- ``--seed [--source statutes|documents|all]``: run the seeds. No model, no GPU. New candidates are added; one already kept
  keeps its status, note, and reading (a person's word is never overwritten).
- ``--read [--model NAME] [--limit N] [--source S]``: read the new, unread candidates with the local model. A person at a
  console, after the local-AI preflight, holding the GPU lock. A reading whose quote is not in the span word for word is
  dropped with its candidate.
- ``--list [--status S] [--source S] [--known|--unknown]``, ``--show ID``, ``--report [--out FILE]``: from disk.
- ``--confirm ID --by NAME [--why TEXT]``, ``--hold ID --by NAME --why TEXT``, ``--drop ID --by NAME --why TEXT``: a
  person's act, logged. Each writes the candidate's status and the log and nothing else: no form, no procedure, and no
  known-form row is made. That is a person's next step.

A refusal prints ``jason discover-forms: <reason>`` and exits 2.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Callable

from jason.commands.integrations import at_terminal

ACTIONS = ("seed", "read", "list", "show", "report", "confirm", "hold", "drop")
SOURCES = ("statutes", "documents", "all")
# An option and the actions it goes with (None: the listing of what is on disk). A stray one is refused, not ignored.
MODIFIERS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("source", "--source", ("seed", "read", "list", "report")), ("model", "--model", ("read",)),
    ("limit", "--limit", ("read",)), ("status", "--status", ("list",)), ("known", "--known", ("list",)),
    ("unknown", "--unknown", ("list",)), ("out", "--out", ("report",)),
    ("why", "--why", ("confirm", "hold", "drop")), ("by", "--by", ("seed", "read", "confirm", "hold", "drop")))
NEXT_STEP = ("Confirming wrote only the candidate's status and the log (data/forms/candidate-acts.jsonl). It did not create a "
             "form, a procedure, or a known-form row: that is a person's next step (docs/standard-forms.md; the known-form "
             "table is docs/arrivals-design.md; a procedure is `jason sop`).")
HELD_STEP = "Held: kept for the board, which adopts a policy where the law is silent. Nothing else was written."
DROPPED_STEP = "Dropped: set aside, not deleted. A re-seed keeps it dropped. Nothing else was written."


def _refuse(reason: str) -> int:
    print(f"jason discover-forms: {reason}", file=sys.stderr)
    return 2


def _data_dir(args: argparse.Namespace) -> Any:
    from jason.commands._shared import data_dir

    return data_dir(args)


def _community() -> Any:
    from jason.community import community

    return community()


def _reader(model: str) -> Any:
    from jason.tasks.form_discovery import LocalModelReader

    return LocalModelReader(model)


def _print_json(body: Any) -> None:
    from jason.commands._shared import to_json

    print(to_json(body))


def _fd() -> Any:
    from jason.tasks import form_discovery

    return form_discovery


def _by(args: argparse.Namespace) -> str:
    by = (args.by or "").strip()
    if by:
        return by
    from jason.approvals.audit import os_actor

    return os_actor()


# -- no option ----------------------------------------------------------------------------------------------------------

def _listing(args: argparse.Namespace, data_dir: Any) -> int:
    fd = _fd()
    store = fd.load(data_dir)
    s = fd.summary(store)
    if args.json:
        _print_json(s)
        return 0
    if not store.candidates:
        print("No form candidates on disk (data/forms/candidates.json).")
        print("Next: `jason discover-forms --seed` runs the seeds over the statutes and the governing documents (no model).")
        return 0
    st, so = s["byStatus"], s["bySource"]
    print(f"Form candidates on disk: {s['candidates']} (seeded {s['seededAt'] or 'unknown'}).")
    print("  by status: " + ", ".join(f"{k} {v}" for k, v in st.items()))
    print("  by source: " + ", ".join(f"{k} {v}" for k, v in so.items()))
    print(f"  known as an existing request kind or notice row: {s['known']}; not known: {s['unknown']}")
    print(f"  read by the model: {s['read']}; not read: {s['unread']}")
    print(f"  groups (a statute with the document sections that carry it out): {s['groups']}")
    print()
    print("Next: `--list` (with --status, --source, --known, --unknown), `--show ID`, `--report`; `--read` reads the new ones "
          "with the local model; `--confirm`, `--hold`, `--drop` (each with --by NAME) are a person's acts.")
    return 0


# -- --seed -------------------------------------------------------------------------------------------------------------

def _seed(args: argparse.Namespace, data_dir: Any) -> int:
    fd = _fd()
    source = args.source or "all"
    result = fd.seed(data_dir, source=source, community=_community(), by=_by(args))
    if args.json:
        _print_json({"source": source, "found": result.found, "added": result.added, "removed": result.removed,
                     "kept": result.total, "joins": result.joins, "byPattern": result.by_pattern})
        return 0
    print(f"Seeded from {source}: {result.found} span(s) found, {result.added} new, {result.removed} removed (new and "
          f"unread, no longer found); {result.total} kept, {result.joins} joined to a statute. No model was run.")
    for name, n in sorted(result.by_pattern.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {name:24} {n}")
    print("A person's status, note, and reading on a candidate already kept were left as they were.")
    print("Next: `jason discover-forms --list`, `--report`, or `--read` (the local model, at a console).")
    return 0


# -- --read -------------------------------------------------------------------------------------------------------------

def _read(args: argparse.Namespace, data_dir: Any) -> int:
    from jason import local_ai
    from jason.community.content import ModelUnavailable
    from jason.community.ollama_extractor import DEFAULT_MODEL

    if not at_terminal():
        return _refuse("reading spans runs a local model on the GPU, so a person runs it at a terminal (stdin is not one)")
    fd = _fd()
    if not any(c.status.value == "new" and c.reading is None for c in fd.load(data_dir).candidates):
        print("Nothing to read: no new candidate without a reading (`jason discover-forms --seed` finds them).")
        return 0
    model = (args.model or "").strip() or DEFAULT_MODEL
    try:
        local_ai.preflight(model)
    except local_ai.LocalAIUnavailable as exc:
        return _refuse(f"the local model is not ready, so nothing was read: {exc}")
    try:
        reader = _reader(args.model or "")
        results = fd.read_new(data_dir, reader, limit=int(args.limit or 0), source=args.source or "all", by=_by(args),
                              progress=lambda line: print(line, flush=True) if not args.json else None)
    except (ModelUnavailable, local_ai.LocalAIUnavailable, ValueError) as exc:
        return _refuse(f"the local model could not read: {exc}")
    if args.json:
        _print_json({"model": getattr(reader, "model", model), "read": [{"id": i, "outcome": o} for i, o in results]})
        return 0
    counts: dict[str, int] = {}
    for _, outcome in results:
        counts[outcome.split(" (")[0].split(":")[0]] = counts.get(outcome.split(" (")[0].split(":")[0], 0) + 1
    print(f"Read {len(results)} candidate(s) with {getattr(reader, 'model', model)}: "
          + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "none") + ".")
    print("A reading is a lead for a person to check against the quote, never the rule. Nothing but the candidates and the "
          "log was written.")
    return 0


# -- --list, --show, --report -------------------------------------------------------------------------------------------

def _list(args: argparse.Namespace, data_dir: Any) -> int:
    fd = _fd()
    store = fd.load(data_dir)
    known = True if args.known else False if args.unknown else None
    rows = fd.select(store.candidates, status=args.status or "", source=args.source if args.source != "all" else "", known=known)
    if args.json:
        _print_json({"candidates": [c.to_dict() for c in rows]})
        return 0
    if not rows:
        print("No candidate matches." if store.candidates else "No form candidates on disk: `jason discover-forms --seed`.")
        return 0
    print(f"{len(rows)} candidate(s):")
    for c in rows:
        print("  " + fd.brief(c))
    return 0


def _show(args: argparse.Namespace, data_dir: Any) -> int:
    fd = _fd()
    store = fd.load(data_dir)
    c = store.get(args.show)
    if c is None:
        return _refuse(f"no candidate {args.show} (jason discover-forms --list)")
    history = fd.acts(data_dir, c.id)
    if args.json:
        _print_json({"candidate": c.to_dict(), "joins": [j.to_dict() for j in store.joins if c.id in (j.statute, j.document)],
                     "acts": history})
        return 0
    print("\n".join(fd.candidate_lines(c, store.joins)))
    if history:
        print("Acts:")
        for a in history:
            why = f": {a['why']}" if a.get("why") else ""
            print(f"  {a['at']}  {a['by']}  {a['act']}{why}" + (f"  ({a['detail']})" if a.get("detail") else ""))
    return 0


def _report(args: argparse.Namespace, data_dir: Any) -> int:
    from pathlib import Path

    fd = _fd()
    store = fd.load(data_dir)
    source = args.source if args.source and args.source != "all" else ""
    rows = fd.select(store.candidates, source=source)
    ids = {c.id for c in rows}
    body = fd.report(rows, [j for j in store.joins if j.statute in ids or j.document in ids])
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(body, encoding="utf-8")
        if args.json:
            _print_json({"wrote": str(out), "candidates": len(rows)})
        else:
            print(f"Wrote {out}: {len(rows)} candidate(s).")
        return 0
    if args.json:
        _print_json({"report": body, "candidates": len(rows)})
    else:
        print(body, end="")
    return 0


# -- the acts -----------------------------------------------------------------------------------------------------------

def _act(args: argparse.Namespace, data_dir: Any, act: str) -> int:
    fd = _fd()
    changed = fd.decide(data_dir, getattr(args, act), act, by=args.by or "", why=args.why or "")
    if args.json:
        _print_json({"candidate": changed.to_dict(), "wrote": ["data/forms/candidates.json", "data/forms/candidate-acts.jsonl"]})
        return 0
    print(f"{act.capitalize()}: {changed.id} ({changed.citation}) is now {changed.status.value}, by {args.by.strip()}"
          + (f": {args.why.strip()}" if args.why else "") + ".")
    print({"confirm": NEXT_STEP, "hold": HELD_STEP, "drop": DROPPED_STEP}[act])
    return 0


# -- the command --------------------------------------------------------------------------------------------------------

def _action(args: argparse.Namespace) -> str | None:
    for name in ACTIONS:
        if getattr(args, name, None):
            return name
    return None


def _stray(args: argparse.Namespace, action: str | None) -> str:
    for dest, flag, goes in MODIFIERS:
        if getattr(args, dest, None) and action not in goes:
            return flag
    return ""


def cmd_discover_forms(args: argparse.Namespace) -> int:
    action = _action(args)
    stray = _stray(args, action)
    if stray:
        return _refuse(f"{stray} does not go with " + (f"--{action}" if action else "the listing; it goes with an action "
                                                       "(see jason discover-forms --help)"))
    if args.source and args.source not in SOURCES:
        return _refuse("--source is statutes, documents, or all")
    fd = _fd()
    data_dir = _data_dir(args)
    try:
        if action == "seed":
            return _seed(args, data_dir)
        if action == "read":
            return _read(args, data_dir)
        if action == "list":
            return _list(args, data_dir)
        if action == "show":
            return _show(args, data_dir)
        if action == "report":
            return _report(args, data_dir)
        if action in ("confirm", "hold", "drop"):
            return _act(args, data_dir, action)
        return _listing(args, data_dir)
    except fd.DiscoveryError as exc:
        return _refuse(str(exc))


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    from jason.community.form_candidates import CandidateStatus

    p = sub.add_parser("discover-forms", help="Find the requests a member makes that a standard form could take: seed from the "
                                              "statutes and the governing documents, read with the local model, a person "
                                              "confirms (docs/standard-forms.md)")
    add_common(p)
    act = p.add_mutually_exclusive_group()
    act.add_argument("--seed", action="store_true",
                     help="run the seeds over the authorities shelf and the governing documents (no model, no GPU); keeps "
                          "a person's status on a candidate already kept")
    act.add_argument("--read", action="store_true",
                     help="read the new, unread candidates with the local model (a person at a console; after the local-AI "
                          "preflight, holding the GPU lock); a reading whose quote is not in the span is dropped")
    act.add_argument("--list", action="store_true", help="the candidates on disk")
    act.add_argument("--show", metavar="ID", help="one candidate: its words, reading, joins, and acts")
    act.add_argument("--report", action="store_true", help="Markdown for a person, grouped by statute and document")
    act.add_argument("--confirm", metavar="ID",
                     help="a person says it is a request a form could take (needs --by); writes only its status and the log")
    act.add_argument("--hold", metavar="ID", help="keep it for the board (needs --by and --why)")
    act.add_argument("--drop", metavar="ID", help="set it aside (needs --by and --why)")
    p.add_argument("--source", choices=SOURCES, metavar="S",
                   help="with --seed, --read, --list, or --report: statutes, documents, or all (default all)")
    p.add_argument("--model", metavar="NAME", help="with --read: the local model (default: jason's shared one)")
    p.add_argument("--limit", type=int, default=0, metavar="N", help="with --read: read at most N candidates")
    p.add_argument("--status", choices=[s.value for s in CandidateStatus], metavar="S", help="with --list: only this status")
    known = p.add_mutually_exclusive_group()
    known.add_argument("--known", action="store_true",
                       help="with --list: only candidates that match an existing request kind or notice-catalog row")
    known.add_argument("--unknown", action="store_true", help="with --list: only candidates that match none")
    p.add_argument("--out", metavar="FILE", help="with --report: write the report to this file")
    p.add_argument("--by", metavar="NAME", help="who does it, for the log (--confirm, --hold, and --drop require it)")
    p.add_argument("--why", metavar="TEXT", help="the reason, kept with the act (--hold and --drop require it)")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_discover_forms)
