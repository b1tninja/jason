"""``jason rule-records``: the association's rules as records, read: a rule on any day, its history, its comparison with the
working Doc, and where it was applied (docs/rule-records.md, phase 1).

    jason rule-records                                   # the records: number, title, status, version in force, grounds
    jason rule-records --list --status adopted --subject noise --as-of 2026-01-01
    jason rule-records --show R-12 [--as-of DAY]         # the words in force that day, then jason's readings
    jason rule-records --history R-12                    # every version, its adoption, notice, and source
    jason rule-records --compare R-12                    # the working Doc's words beside the adopted words
    jason rule-records --uses R-12                       # the uses linked to the rule, with the version in force that day
    jason rule-records --records stored|derived|auto     # where the records come from (default auto)
    jason rule-records ... --json                        # what the console loaders serve

Each view prints the words first (with the version's citation, source and day), then the readings, labeled as jason's. Reading
only: nothing is written to ``data/``, Drive, PayHOA, or the mail, and no record is edited. A change to a rule is a proposal a
person moves and the board adopts (a later phase); this command adopts, approves, and recommends nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable


def _data_dir(args: argparse.Namespace) -> Path:
    from jason.config import data_dir

    return data_dir(getattr(args, "env", None))


def _day(text: str) -> date | None:
    return date.fromisoformat(text) if text else None


def _out(args: argparse.Namespace, payload: dict[str, Any], lines: list[str]) -> int:
    print(json.dumps(payload, indent=1, ensure_ascii=False) if args.json else "\n".join(lines))
    return 0


def _wrap(text: str, indent: str = "  ") -> list[str]:
    import textwrap

    return [indent + ln for ln in textwrap.wrap(text, 110)] or [indent]


def _lines_show(view: dict[str, Any], recital: list[str]) -> list[str]:
    st, g = view["status"], view["grounds"]
    out = [*recital[:3]]
    out += _wrap(recital[3].strip()) if len(recital) > 3 else []
    out += ["", "jason's readings (labeled; the words above are the stored words):",
            f"  status: {st['statusWord']}" + (f" since {st['since']}" if st.get("since") else "") + (f" ({st['note']})" if st.get("note") else ""),
            f"  subjects: {', '.join(view['subjects']) or 'none read'} ({view['subjectSource']})",
            f"  grounds: {g['standing']}"]
    for grant in g["grants"]:
        out += [f"    {grant['id']} {grant['citation']} [{grant['tier']}; {grant['holder']}; review {grant['review']}]"]
        out += _wrap(f"\"{grant['recital']['words']}\"", "      ")
    if g["general"]:
        out.append(f"    general power only: {', '.join(g['general'])}")
    if g["note"]:
        out.append(f"    {g['note']}")
    for r in view["reach"]:
        out.append(f"  Civil Code 4355, {r['subject']}: {r['reach']} (jason's reading; {', '.join(r['cites']) or 'no listed subject'})")
    c = view.get("compare")
    if c:
        out.append(f"  working Doc: {c['word'] or c['standing']}")
    if view["openProposals"]:
        out.append(f"  open proposals: {', '.join(view['openProposals'])} (in force on no day)")
    if view["uses"].get("count") is not None:
        out.append(f"  uses linked: {view['uses']['count']}")
    out += [f"  gap: {g_}" for g_ in view["gaps"]]
    out += ["", view["caveats"][0]]
    return out


def cmd_rule_records(args: argparse.Namespace) -> int:
    from jason.community import rule_records as rr
    from jason.community.manual import ManualError
    from jason.tasks import rule_records as task

    shown = [a for a in (args.show, args.history, args.compare, args.uses) if a]
    if len(shown) > 1:
        print("choose one of --show, --history, --compare, --uses", file=sys.stderr)
        return 2
    try:
        day = _day(args.as_of)
    except ValueError:
        print(f"--as-of takes a day, YYYY-MM-DD, not {args.as_of!r}", file=sys.stderr)
        return 2
    one = shown[0] if shown else ""
    try:
        loaded = task.load(_data_dir(args), records=args.records, doc=not args.no_doc and (not shown or bool(args.compare or args.show)),
                           grants=not args.no_grants and (not shown or bool(args.show)))
    except (ManualError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    for note in loaded.notes:
        print(f"note: {note}", file=sys.stderr)
    when = day or date.today()

    if not one:
        cmp_ = task.comparisons(loaded, when)
        uses = task.use_counts(loaded)
        view = rr.book_view(loaded.book, when, loaded.events, rows=loaded.rows, authorities=loaded.authorities or (),
                            comparisons=cmp_, uses=uses, status=args.status, subject=args.subject)
        c = view["counts"]
        lines = [f"{c['records']} rule records ({view['source']}), as of {view['asOf']}",
                 f"  adopted {c['adopted']} ({c['adoptionNotOnRecord']} with the adoption not on record), proposed {c['proposed']}, "
                 f"noticed {c['noticed']}, suspended {c['suspended']}, repealed {c['repealed']}, expired {c['expired']}, "
                 f"no version in force {c['noVersionInForce']}",
                 f"  no grant found for {c['noGrantFound']}" + ("" if view["grantsRead"] else " (the grants were not read)"),
                 f"  working Doc: " + (", ".join(f"{k} {n}" for k, n in sorted(c["compare"].items())) or "not read"), ""]
        for r in view["records"]:
            ver = f"{r['inForce']['version']} {r['inForce']['adopted'] or 'adoption not on record'}" if r["inForce"] else "none"
            lines.append(f"{r['number'] or '-':<10} {r['title'][:42]:<42} {r['statusWord']:<32} {ver:<30} {r['grounds']['standing']}"
                         + (f"  [Doc: {r['compare']}]" if r["compare"] and r["compare"] != "same" else ""))
        lines += ["", rr.CAVEAT]
        return _out(args, view, lines)

    rec = loaded.record(one)
    if rec is None:
        print(f"no rule record {one!r}; jason rule-records lists them", file=sys.stderr)
        return 2
    if args.history:
        h = rr.history(rec, loaded.events, when)
        payload = {"found": True, "id": rec.id, **h}
        lines = [f"{rec.number or rec.id}  {rec.title}  ({rr.citation(rec)})", ""]
        for v in h["versions"]:
            lines.append(f"{v['id']} [{v['stage']}]" + (" (in force on the day)" if v["inForce"] else "")
                         + f", {'adopted ' + v['adopted'] if v['adopted'] else 'adoption day not on record'}"
                         + (f", board item {v['boardItem']}" if v["boardItem"] else "") + (f", decision {v['decision']}" if v["decision"] else ""))
            lines += _wrap(v["words"].strip())
            lines.append(f"  words from: {v['source']['kind']}" + (f" ({v['source'].get('file')})" if v["source"].get("file") else "")
                         + (f"; replaced {v['supersedes']}" if v["supersedes"] else ""))
            if v["notice"]:
                lines.append(f"  notice: {', '.join(v['notice'])}")
            if v.get("whoNote"):
                lines.append(f"  {v['whoNote']}")
            changes = [d for d in v["diff"] if d["op"] != "same"]
            if changes:
                lines.append(f"  change from {v['diffTo']}: " + "; ".join(f"{d['op']}: {d['text']}" for d in changes)[:600])
            lines.append("")
        lines += [f"event {e['on'] or 'undated'} {e['action']}: {e['evidence']}" for e in h["events"]]
        lines += [f"gap: {g['note']}" for g in h["gaps"]]
        lines += [rr.CAVEAT]
        return _out(args, payload, lines)

    if args.uses:
        found, notes = task.links(loaded.data_dir)
        payload = rr.uses_view(rec, found.get(rec.id, []), when)
        lines = [f"{rec.number or rec.id}  {rec.title}  ({payload['address']})", f"{payload['count']} use(s) linked"]
        lines += [f"  {u['on'] or 'undated'} {u['kind']}: {u['outcome']} (version {u['version'] or 'none in force'}"
                  f"{'' if u['isCurrent'] in (None, True) else ', not the version in force now'}) {u['ref'].get('route', '')}" for u in payload["uses"]]
        lines += [f"  {o['outcome']}: {o['n']}" for o in payload["byOutcome"]] + [payload["note"]] + [f"note: {n}" for n in notes]
        return _out(args, payload, lines)

    cmp_ = rr.compare(rec, when, loaded.docs.get(rec.id)) if loaded.doc_read else rr.compare(rec, when, None)
    if args.compare:
        payload = {"found": True, "id": rec.id, **cmp_.to_dict()}
        recital = rr.recite(rec, when, loaded.events)
        lines = ["The adopted words:", *recital[:2], *( _wrap(recital[3].strip()) if len(recital) > 3 else []), ""]
        if cmp_.doc is not None and cmp_.doc.in_doc:
            lines += [f"The working Doc's words (revision {cmp_.doc.revision or 'unknown'}):", *_wrap(cmp_.doc.words.strip()), ""]
        lines += [f"jason's reading: {cmp_.word.value if cmp_.word else cmp_.standing}" + (f" ({cmp_.note})" if cmp_.note else ""),
                  "The adopted words stay the rule; nothing here makes the Doc's words the rule or edits the Doc.", rr.NO_ADOPTION_CAVEAT]
        return _out(args, payload, lines)

    found, _ = task.links(loaded.data_dir)
    view = rr.record_view(rec, when, loaded.events, rows=loaded.rows, authorities=loaded.authorities or (), comparison=cmp_,
                          uses=len(found.get(rec.id, [])))
    return _out(args, view, _lines_show(view, rr.recite(rec, when, loaded.events)))


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("rule-records", help="The association's rules as records, read only: a rule on any day, its history, "
                                            "its comparison with the working Doc, and where it was applied")
    add_common(p)
    p.add_argument("--list", action="store_true", help="the records (the default)")
    p.add_argument("--status", default="", help="with --list: only this status (proposed, noticed, adopted, suspended, repealed, expired, "
                                                "or adoption-not-on-record)")
    p.add_argument("--subject", default="", help="with --list: only rules on this subject (a word of jason rules --subjects)")
    p.add_argument("--as-of", default="", metavar="DAY", help="read the records as of this day, YYYY-MM-DD (default today)")
    p.add_argument("--show", metavar="ID", default="", help="one rule: the words in force on the day, then jason's readings")
    p.add_argument("--history", metavar="ID", default="", help="every version of one rule, with its adoption, notice, and source")
    p.add_argument("--compare", metavar="ID", default="", help="one rule's adopted words beside the working Doc's")
    p.add_argument("--uses", metavar="ID", default="", help="the uses linked to one rule")
    p.add_argument("--records", choices=("auto", "derived", "stored"), default="auto",
                   help="auto: data/rule-records/<document>.json when it is there, else derived from the classification")
    p.add_argument("--no-doc", action="store_true", help="do not read the working Doc (no comparison)")
    p.add_argument("--no-grants", action="store_true", help="do not read the grants and the rules on file (a faster list)")
    p.add_argument("--json", action="store_true", help="JSON output, as the console loaders serve it")
    p.set_defaults(func=cmd_rule_records)
