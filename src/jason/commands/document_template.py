"""``jason document-template``: a document rendered from one definition, a layout apart from its blocks.

``jason document-template owners-manual`` renders the owner's manual from its definition (``jason.community.document_templates``)
after ``jason manual --render``'s own pass, writes ``owners-manual.document.md``, ``.html``, and ``owners-manual.parts.json``
(the part map) to ``data/drafts``, and compares the Markdown with the manual ``jason manual --render`` wrote: it must be
identical, and the command exits 1 if it is not, or if a piece is unlabeled. ``--rules-from-document`` reads its rule words
from the Rules document's records instead (an option; off by default).

``rules-and-regulations`` is the Rules document: the rules book as rule records, each with a stable id, rendered with its
status line, adoption history, and an appendix naming the policies bound in apart. It is compared with ``jason manual
--render``'s own ``rules-and-regulations.md``: every line must be the same or a labeled difference. ``owners-manual-template``
is the manual that refers to it instead of containing the rules (``--with-rules`` renders them in).
``--export-records`` writes the derived records to ``data/rule-records`` for a person to keep as data (never over an
existing file).

``--doc plan`` prints what the Docs would be (a dry run); ``--doc create --yes`` writes them through the Google layer and
records the ids in ``data/templates/<profile>.json``. Nothing else is written to Drive, PayHOA, or the mail.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from typing import Any, Callable

DOCUMENTS = ("owners-manual", "rules-and-regulations", "owners-manual-template")
BLOCKS = (("prose", "words written once"), ("part", "the guide's own words for a slot"),
          ("rule-book", "a book of rules, read by reference"), ("excerpts", "governing documents' passages"),
          ("law", "a statute's words from disk"), ("history", "when each part was adopted"),
          ("quote", "a passage by reference"), ("form", "a form's paper rendering, one definition with the live form"),
          ("directory", "roles and published contact fields"), ("computed", "a table from the stores"),
          ("embedded", "another document by reference: nested, attached, or a visible gap"),
          ("status", "the adoption status line, a token filled from the adoption record"),
          ("rule", "one rule record, by its stable id, the version in force on the day"),
          ("rules-reference", "the Rules document by reference: its rules, or a link and an index"),
          ("policy-references", "the policies bound in apart, by their book keys"))


def _print_check(found: Any) -> None:
    from jason.tasks import document_templates as task

    for line in task.summary(found):
        print(line)
    for gap in found.gaps:
        print(f"gap: {gap}")
    for line in found.unlabeled:
        print(f"unlabeled: {line}")


def _manual(args: argparse.Namespace) -> int:
    from jason.community.manual import ManualError
    from jason.tasks import document_templates as task

    try:
        done = task.render_manual(layout=args.layout, as_of=args.as_of, rules_from_document=args.rules_from_document,
                                  records=args.records)
    except (ManualError, ValueError) as exc:
        print(f"jason document-template: {exc}", file=sys.stderr)
        return 1
    found = done["check"]
    for name, path in done["paths"].items():
        print(f"{name:9} {path}")
    section = done.get("rules")
    if section is None:
        print("the plain rendering is identical to jason manual --render's: " + ("yes" if done["identical"] else "NO"))
        ok = done["identical"] and found.clean
    else:
        pieces = done["pieces"]
        print(f"the rules are read from the Rules document: {section.same} pieces equal their record's words, "
              f"{len(section.different)} differ, {len(section.unplaced)} records the manual does not place")
        print("the plain rendering is identical to jason manual --render's: " + ("yes" if done["identical"] else "no")
              + f" ({len(pieces.labeled)} pieces differ from the working Doc, each labeled; "
                f"{len(pieces.unlabeled)} unlabeled)")
        for d in pieces.labeled:
            print(f"labeled difference: {d.segment}: {d.label}")
        for d in pieces.unlabeled:
            print(f"unlabeled: {d.segment}: {d.detail}")
        ok = found.clean and not pieces.unlabeled and not section.unplaced
    _print_check(found)
    return 0 if ok else 1


def _documents(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.community.manual import ManualError
    from jason.community.profile import profile_name
    from jason.community.rules_document import MANUAL_TEMPLATE_KEY, RULES_KEY
    from jason.tasks import document_docs as docs_task
    from jason.tasks import rules_documents as rd

    try:
        prepared = rd.prepare(as_of=args.as_of, records=args.records)
    except (ManualError, ValueError) as exc:
        print(f"jason document-template: {exc}", file=sys.stderr)
        return 1
    if args.export_records:
        path = rd.records_path(prepared.data_dir, prepared.spec.document)
        try:
            rd.save_book(prepared.book, path)
        except ManualError as exc:
            print(f"jason document-template: {exc}", file=sys.stderr)
            return 1
        print(f"{len(prepared.book.records)} rule records written to {path}: edit them there to keep the rules as data")
        return 0
    keys = (args.document,) if args.document in (RULES_KEY, MANUAL_TEMPLATE_KEY) else rd.DEFINITIONS
    if not args.doc:
        ok = True
        for key in keys:
            layout_mode = "full"
            done = rd.render(prepared, key, layout=args.layout if args.layout != "plain" else "book", mode=layout_mode)
            print(f"{key}")
            for name, path in done["paths"].items():
                print(f"  {name:9} {path}")
            _print_check(done["check"])
            ok = ok and done["check"].clean
            if key == RULES_KEY:
                official = prepared.made["paths"]["rules"].read_text(encoding="utf-8")
                plain = rd.render(prepared, key, layout="plain")
                proof = rd.prove_rules(official, plain["markdown"], prepared.values)
                print(f"  the Rules document equals jason manual --render's rules-and-regulations.md apart from labeled "
                      f"differences: {'yes' if proof.equal else 'NO'} ({proof.same} lines the same, "
                      f"{len(proof.labeled)} labeled, {len(proof.unlabeled)} unlabeled)")
                for line in proof.unlabeled:
                    print(f"  unlabeled: {line}")
                ok = ok and proof.equal
                switched = rd.prove_switch(prepared)
                print(f"  the owner's manual with its rules read from the Rules document: {switched.section.same} rules "
                      f"equal their record's words, {len(switched.section.different)} differ, "
                      f"{len(switched.section.unplaced)} records unplaced; identical to the manual read from the "
                      f"classification: {'yes' if switched.identical else 'no'} ({len(switched.labeled)} pieces differ "
                      f"from the working Doc, each labeled; {len(switched.unlabeled)} unlabeled)")
                for line in switched.labeled:
                    print(f"  labeled difference: {line}")
                for line in switched.unlabeled:
                    print(f"  unlabeled: {line}")
                ok = ok and switched.clean
        return 0 if ok else 1

    state = docs_task.load_state(prepared.data_dir, profile_name())
    jobs = docs_task.jobs_for(prepared, keys, state, with_rules=args.with_rules)
    texts: dict[str, str | None] = {}
    known = [str((state.get(docs_task.PREFIX + k) or {}).get("docId") or "") for k in keys]
    known = [k for k in known if k]
    if known:
        try:
            from jason.tasks.letters import document_text

            with agent_factory(args) as agent:
                docs = agent.drive().docs()
                for doc_id in known:
                    try:
                        texts[doc_id] = document_text(docs.get(doc_id))
                    except Exception:                               # noqa: BLE001 - gone or trashed
                        texts[doc_id] = None
        except Exception as exc:                                    # noqa: BLE001 - no Google access: a dry run still plans
            print(f"(the existing Docs were not read: {type(exc).__name__}; they are planned as not read)")
    steps = docs_task.plan_docs(prepared, jobs, state, texts)
    for step in steps:
        for line in docs_task.describe(step, state):
            print(line)
    writes = [s for s in steps if s.action.writes]
    if args.doc == "plan" or not args.yes:
        if args.doc == "create" and not args.yes:
            print("--doc create is a dry run without --yes")
        if writes:
            print(f"--doc create --yes would write {len(writes)} Doc(s) on the Letterhead; this was a dry run, "
                  "nothing was written to Drive")
        return 0
    if not writes:
        return 0
    letterhead = prepared.community.letterhead()
    with agent_factory(args) as agent:
        drive = agent.drive()
        done = docs_task.generate(drive, drive.docs(), prepared, steps, state, letterhead_id=letterhead.doc_id,
                                  footer=letterhead.footer, with_rules=args.with_rules)
    path = docs_task.save_state(prepared.data_dir, profile_name(), state)
    for d in done:
        print(f"{d['action']:8} {d['key']:24} {d['url']}  ({d['requests']} requests)")
        for problem in d["problems"]:
            print(f"  check: {problem}")
    print(f"recorded in {path}")
    return 0


def cmd_document_template(args: argparse.Namespace, agent_factory: Callable[[Any], Any] | None = None) -> int:
    from jason.community.document_templates import LAYOUTS

    if args.list or (not args.document and not args.doc and not args.export_records):
        print("documents: " + ", ".join(DOCUMENTS))
        print("layouts:   " + ", ".join(LAYOUTS))
        for kind, what in BLOCKS:
            print(f"  {kind:17} {what}")
        return 0
    if args.document == "owners-manual" and not args.doc:
        return _manual(args)
    return _documents(args, agent_factory or args.agent_factory)


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("document-template", help="Render a document from one definition: a layout apart from its "
                                                 "blocks (the owner's manual, the Rules document, the manual template)")
    add_common(p)
    p.add_argument("document", nargs="?", choices=DOCUMENTS, help="the document to render")
    p.add_argument("--layout", default="plain", help="how it looks: plain, guide, or book (--list)")
    p.add_argument("--list", action="store_true", help="the documents, layouts, and block kinds")
    p.add_argument("--as-of", type=date.fromisoformat, default=None, metavar="YYYY-MM-DD",
                   help="the day the rules are read as in force (default: today)")
    p.add_argument("--records", choices=("auto", "derived", "stored"), default="auto",
                   help="where the rule records come from: stored in data/rule-records when there, else derived from the "
                        "classification (auto); always derived; or only stored")
    p.add_argument("--rules-from-document", action="store_true",
                   help="owners-manual: read the rule words from the Rules document's records (off unless asked)")
    p.add_argument("--export-records", action="store_true",
                   help="write the derived rule records to data/rule-records (never over an existing file)")
    p.add_argument("--doc", choices=("plan", "create"), default=None,
                   help="plan: print what the Docs would be (a dry run); create: write them, with --yes")
    p.add_argument("--with-rules", action="store_true",
                   help="the manual template's Doc carries the rules' full text (default: a link and an index)")
    p.add_argument("--yes", action="store_true", help="with --doc create: write the Docs (without it, a dry run)")
    p.set_defaults(func=cmd_document_template, agent_factory=agent_factory)


__all__ = ["cmd_document_template", "register"]
