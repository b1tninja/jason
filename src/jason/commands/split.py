"""``jason split``: cut a large combined PDF into the documents it holds (docs/pdf-splitter.md, section 7.2).

    jason split --list                                   the drafts, with status
    jason split FILE|library:ID|SESSION                  what opening would do (a dry run); --yes --by NAME opens or resumes it
    jason split SESSION --suggest --by NAME --yes        run the cheap rule pass again; prints each suggestion with its reasons
    jason split SESSION --boundaries 1,15,23,40 --by NAME --yes     set the boundaries (the whole set; page 1 is always one)
    jason split SESSION --accept all|g12,g20 | --reject g12 | --mark 30 | --unmark 30 | --undo | --redo   (each: --by NAME --yes)
    jason split SESSION --review [--part s2=SLOT[@PERIOD][#ENTRY] ...] [--drop 7,29]     counts, collisions, duplicates; writes nothing
    jason split SESSION --flags                           per-segment flags before the review (disk only)
    jason split SESSION --apply --yes --by NAME [--part ...] [--drop ...] [--filing held|library|slots] [--no-ocr] [--rotate 61=90,66=fix|sideways]    write the files (the only command that writes PDFs)
    jason split SESSION --decline --yes --by NAME
    jason split --purge [SESSION | --all-drafts] --yes --by NAME     drop drafts with their copy and page pictures (never an original)
    jason split --sweep [--yes]                           the retention sweep (split.draft_days)

**A dry run is the default**: without ``--yes`` a draft change is made on a copy and shown, and an apply writes nothing. ``--by NAME``
names the person (a claim on a terminal; never jason). The command opens no browser, calls no network, and only a person's ``--apply
--yes`` writes a PDF, through the record intake's one split writer. The history line holds the session id and counts, never a file
name or a page's text. A file path is read, and neither it nor its name is printed or kept. Exit 1 is a refusal in words, 2 a usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable


def _print_session(view: dict[str, Any]) -> None:
    c = view["counts"]
    print(f"split {view['id']}: {view['status']}, {c['pages']} pages, {c['segments']} segments"
          f"{', ' + str(c['nested']) + ' nested' if c['nested'] else ''}, {c['suggestionsOpen']} suggestions open, version {view['version']}")
    for seg in view["segments"]:
        lab = seg.get("labels") or {}
        extra = "".join(f"  {k}={v}" for k, v in lab.items())
        indent = "  " * seg["level"]
        print(f"  {indent}{seg['key']:<6} pages {seg['start']}-{seg['end']} ({seg['pages']}){extra}")
    for s in view["suggestions"]:
        if s["state"] == "open":
            print(f"  suggested {s['id']}: page {s['page']}  {s['band']} ({s['confidence']:.2f})  {s['why']}")


def _print_review(r: dict[str, Any]) -> None:
    print(f"review of {r['id']}: {r['files']} files from {r['sourcePages']} pages; {r['pagesInFiles']} pages in files, {len(r['dropped'])} left out"
          f"{'' if r['totalsOk'] else '  (THE PAGES DO NOT ADD UP)'}")
    for p in r["parts"]:
        runs = ",".join(f"{a}-{b}" if a != b else str(a) for a, b in p["pages"])
        slot = (f" -> {p['slot']}" if p["action"] in ("fill", "collision") else " (to the library intake)" if p["action"] == "library"
                else " (held, no slot yet)")
        note = f"  [{p['action']}{': ' + p['why'] if p.get('why') else ''}]" if p["action"] not in ("fill", "held", "library") else ""
        turned = f"  turn {', '.join(str(x['page']) + ' by ' + str(x['degrees']) for x in p.get('rotated') or ())}" if p.get("rotated") else ""
        side = f"  sideways, left as is: {', '.join(str(x['page']) for x in p['sideways'])}" if p.get("sideways") else ""
        print(f"  {p['segment']:<6} pages {runs} ({p['count']}){slot}{note}{turned}{side}")
    for problem in r["problems"]:
        print(f"  problem: {problem}")
    print(f"  {r['result']}")


def _print_flags(f: dict[str, Any]) -> None:
    c = f["counts"]
    print(f"flags for {f['id']}: {f['measured']['pages']} of {f['measured']['of']} pages measured; {c['blankOnly']} blank only, "
          f"{c['nearDuplicate']} near-duplicate, {c['sideways']} sideways pages, {c['overPartLimit']} over the part limit, "
          f"{c['mayHoldMore']} may hold more than one document, {c['slotFilled']} for a slot that holds a file")
    for r in f["segments"]:
        if not r["flagged"]:
            continue
        bits = []
        if r["blankOnly"]:
            bits.append("blank only")
        if r["nearDuplicateOf"]:
            bits.append(f"near-duplicate of {r['nearDuplicateOf']}")
        if r["repeatedBy"]:
            bits.append(f"repeated by {', '.join(r['repeatedBy'])}")
        if r["sideways"]:
            bits.append("sideways: " + ", ".join(f"{x['page']} (turn {x['fix']})" for x in r["sideways"]))
        if r["overPartLimit"]:
            bits.append(f"about {r['estimatedBytes']:,} bytes, over the {r['partLimit']:,} limit")
        if r["mayHoldMore"]:
            bits.append("may hold more than one: pages " + ", ".join(str(m["page"]) for m in r["mayHoldMore"]))
        if r["slotFilled"]:
            bits.append(f"{r['slot']} already holds a file")
        print(f"  {r['segment']:<6} pages {r['start']}-{r['end']}: " + "; ".join(bits))
    if f["parts"]["over"]:
        print(f"  {f['parts']['count']} segments is over the {f['parts']['limit']} files one split writes")


def _target(raw: str, root: Path) -> tuple[str, dict[str, Any] | str]:
    """A session id, a library file (``library:ID``), or a path on this machine."""
    from jason.tasks import split_session as ss

    text = raw.strip()
    if text.startswith("library:"):
        return "ref", {"kind": "library", "id": text.split(":", 1)[1]}
    if ss.ID_FORM.match(text) and ss.session_file(root, text).is_file():
        return "session", text
    return "ref", {"kind": "path", "path": text}


def cmd_split(args: argparse.Namespace) -> int:
    from jason import limits
    from jason.community.split_session import SplitConflict
    from jason.tasks import split_session as ss

    def out(data: Any) -> None:
        if getattr(args, "json", False):
            print(json.dumps(data, indent=1, ensure_ascii=False, default=str))

    yes = bool(getattr(args, "yes", False))
    by = (getattr(args, "by", "") or "").strip()
    changes = [f for f in ("suggest", "boundaries", "accept", "reject", "mark", "unmark", "undo", "redo", "decline", "facts")
               if getattr(args, f, None)]
    if yes and not by and not args.sweep:
        print("jason split: --yes needs --by NAME (a split is a named person's act)", file=sys.stderr)
        return 2
    try:
        from jason.community import community as active

        community = active()
    except Exception:  # noqa: BLE001 - the splitter reads without a chosen community; the limits then use their defaults
        community = None
    try:
        from jason.mcp.county import _data_dir

        root = Path(_data_dir(None))
    except Exception as exc:  # noqa: BLE001
        print(f"jason split: {exc}", file=sys.stderr)
        return 1
    who = by or "a person (dry run)"
    try:
        if args.list:
            rows = ss.listing(root)
            if args.json:
                out(rows)
            else:
                for r in rows:
                    print(f"{r['id']}  {r['status']:<9} {r['pages']} pages  {r['segments']} segments  {r['suggestionsOpen']} suggestions  {r['updated']}  {r['label']}")
                if not rows:
                    print("no splits yet")
            return 0
        if args.sweep:
            res = ss.sweep(dry_run=not yes, community=community, root=root)
            if args.json:
                out(res)
            else:
                gone = (res.get("would") or {}).get("sessions") if res["dryRun"] else res["removed"]
                print(f"{'would remove' if res['dryRun'] else 'removed'} {len(gone or [])} drafts older than {res.get('days') or res['would']['days']} days")
            return 0
        if args.purge:
            res = ss.purge(sid=args.target or "", all_drafts=args.all_drafts, dry_run=not yes, by=by, root=root, community=community)
            if args.json:
                out(res)
            else:
                print(res.get("note") or f"removed {len(res['removed'])} drafts; freed {res['freed']} bytes")
            return 0
        if not args.target:
            print("jason split: name a PDF, a library file (library:ID), or a split id; --list shows the splits", file=sys.stderr)
            return 2
        kind, target = _target(args.target, root)
        sid = ""
        if kind == "ref":
            res = ss.open_session(target, by=who, dry_run=not yes, community=community, root=root)  # type: ignore[arg-type]
            if res.get("dryRun"):
                if args.json:
                    out(res)
                else:
                    w = res["would"]
                    print(f"would open a file of {w['pages']} pages ({w['size']} bytes); {res['note']}")
                return 0
            sid = res["session"]["id"]
            if res.get("factsPending"):
                res.update(ss.queue_facts(root, sid, by))
            if not changes and not args.review and not args.apply:
                if args.json:
                    out(res)
                else:
                    print("resumed the draft on the same file" if res["resumed"] else "opened")
                    _print_session(res["session"])
                    if res.get("job"):
                        print(f"page facts are filling in as job {res['job']} (jason worker --once)")
                return 0
        else:
            sid = str(target)
        final: dict[str, Any] = {}
        body_for: list[tuple[str, dict[str, Any]]] = []
        if args.facts:
            res = ss.build_facts(sid, by=who, community=community, root=root)
            final["facts"] = res
            print(f"measured {res['pages']} pages" + (f"; {res['suggestions']} suggestions open" if "suggestions" in res else ""))
        if args.undo:
            body_for.append(("undo", {}))
        if args.redo:
            body_for.append(("redo", {}))
        if args.boundaries:
            body_for.append(("boundaries", {"pages": args.boundaries}))
        for p in args.mark or ():
            body_for.append(("mark", {"pages": p}))
        for p in args.unmark or ():
            body_for.append(("unmark", {"pages": p}))
        if args.accept:
            body_for.append(("accept", {"id": args.accept}))
        if args.reject:
            body_for.append(("reject", {"id": args.reject}))
        for name, body in body_for:
            res = ss.act(sid, name, body, by=who, dry_run=not yes, community=community, root=root)
            final[name] = res
        if args.suggest:
            if yes:
                res = ss.suggest(sid, by=who, community=community, root=root)
                final["suggest"] = res
            else:
                limits.check("split.suggest_enabled", True, community=community, record=False)
        if args.decline:
            final["decline"] = ss.decline(sid, by=who, dry_run=not yes, root=root, community=community)
        parts = list(args.part or ())
        drop = _numbers(args.drop)
        if args.review or (args.apply and not yes):
            rev = ss.review(sid, parts=parts, drop=drop, keep_copies=args.keep_copies, community=community, root=root,
                            filing=args.filing or '', rotate=args.rotate or None)
            final["review"] = rev
        if args.flags:
            from jason.tasks import split_flags

            final["flags"] = split_flags.flags(sid, community=community, root=root)
        if args.apply:
            res = ss.apply(sid, by=who, parts=parts, drop=drop, keep_copies=args.keep_copies, confirm=yes, community=community, root=root,
                           filing=args.filing or '', rotate=args.rotate or None, ocr=not getattr(args, "no_ocr", False))
            final["apply"] = res
        if args.json:
            from jason.tasks import split_session as _s

            final["session"] = _s.view_of(root, _s.load(root, sid))
            out(final)
            return 0
        for name in ("decline",):
            if name in final:
                print(final[name].get("note") or "declined")
        if "flags" in final:
            _print_flags(final["flags"])
        if "review" in final:
            _print_review(final["review"])
        if "apply" in final:
            a = final["apply"]
            if a.get("dryRun"):
                print(a["note"])
            else:
                print(f"wrote {len(a['filled'])} files into slots"
                      f"{', ' + str(len(a['library'])) + ' into the library,' if a['library'] else ''} and held {len(a['held'])}; "
                      f"skipped {len(a['skipped'])}{'; turned ' + str(len(a['rotated'])) + ' pages' if a['rotated'] else ''}"
                      f"{'; ' + str(len(a['failed'])) + ' failed' if a['failed'] else ''}")
                if a.get("ocrQueued") or a.get("ocrSkipped"):
                    print(f"OCR: {len(a['ocrQueued'])} job(s) queued, {len(a['ocrSkipped'])} skipped (jason worker --once)")
                for n in a.get("notQueued") or ():
                    print(f"  not queued {n.get('segment') or n.get('libraryId') or ''}: {n['why']}")
                for f in a["failed"]:
                    print(f"  failed {f['segment']}: {f['why']}")
        elif not final.get("review"):
            _print_session(ss.view_of(root, ss.load(root, sid)))
            if not yes and (changes):
                print("A dry run: nothing was saved. Add --yes (with --by NAME) to keep the change.")
        return 0
    except SplitConflict as exc:
        print(f"jason split: {exc}", file=sys.stderr)
        return 1
    except KeyError as exc:
        print(f"jason split: no split {exc.args[0] if exc.args else ''}", file=sys.stderr)
        return 1
    except (ValueError, OSError) as exc:
        print(f"jason split: {exc}", file=sys.stderr)
        return 1


def _numbers(text: str | None) -> list[int]:
    if not text:
        return []
    out: list[int] = []
    for part in re.split(r"[,\s]+", text.strip()):
        if not part:
            continue
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("split", help="Split a large combined PDF into the documents it holds: boundaries a person marks, jason's suggestions "
                                     "with reasons, and a confirmed write (a dry run until --yes)")
    add_common(p)
    p.add_argument("target", nargs="?", help="a PDF on this machine, a library file (library:ID), or a split id")
    p.add_argument("--list", action="store_true", help="list the splits")
    p.add_argument("--suggest", action="store_true", help="run the cheap rule pass again")
    p.add_argument("--facts", action="store_true", help="measure every page (the job a long file's open queues)")
    p.add_argument("--boundaries", help="set the boundaries: 1,15,23,40 (the whole set; page 1 is always one)")
    p.add_argument("--mark", action="append", metavar="PAGES", help="mark pages (12 or 12-14) as the first page of a segment")
    p.add_argument("--unmark", action="append", metavar="PAGES", help="remove a mark")
    p.add_argument("--accept", metavar="ID|all", help="accept suggestions: g12,g20, or all (High and better)")
    p.add_argument("--reject", metavar="ID", help="reject suggestions: g12,g20")
    p.add_argument("--undo", action="store_true", help="undo the last change to the draft")
    p.add_argument("--redo", action="store_true", help="redo it")
    p.add_argument("--review", action="store_true", help="the review of what an apply would do (counts, collisions, duplicates); writes nothing")
    p.add_argument("--apply", action="store_true", help="write the files (only with --yes --by NAME; the only command that writes PDFs)")
    p.add_argument("--part", action="append", metavar="SEGMENT=SLOT[@PERIOD][#ENTRY]", help="assign a segment to a record slot, as `jason records --split`")
    p.add_argument("--filing", choices=("held", "library", "slots"), help="how the parts are filed: held in jason's store, taken in by the library "
                   "intake, or each into the slot it names (without it, a part with a slot fills it and any other is held)")
    p.add_argument("--no-ocr", action="store_true", help="with --filing library: do not queue OCR for the parts filed to the library "
                   "(default: one background job a part, in your name, at most split.ocr_queue_max)")
    p.add_argument("--rotate", metavar="PAGE=DEGREES,...|sideways", help="turn pages in the new files only: 61=90,66=fix (degrees clockwise, or fix for "
                   "the measured turn), or `sideways` for every page measured sideways; the original is never changed")
    p.add_argument("--flags", action="store_true", help="the flags of each segment before the review (blank only, near-duplicate, sideways, over the "
                   "part limit, may hold more than one document); reads disk, writes nothing")
    p.add_argument("--drop", help="pages to leave out of every file: 7,29 (the totals are checked)")
    p.add_argument("--keep-copies", action="store_true", help="write a part even if jason already holds an identical file")
    p.add_argument("--decline", action="store_true", help="record that a person wants none of this split")
    p.add_argument("--purge", action="store_true", help="drop a draft (or --all-drafts) with its copy and page pictures; never an original")
    p.add_argument("--all-drafts", action="store_true", help="with --purge: every draft")
    p.add_argument("--sweep", action="store_true", help="the retention sweep: drafts older than split.draft_days")
    p.add_argument("--by", help="who is doing this (a claim on a terminal; never jason)")
    p.add_argument("--yes", action="store_true", help="make the change (without it, a dry run)")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_split)
