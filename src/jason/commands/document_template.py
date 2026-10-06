"""``jason document-template``: a document rendered from one definition, a layout apart from its blocks.

``jason document-template owners-manual`` renders the owner's manual from its definition (``jason.community.document_templates``)
after ``jason manual --render``'s own pass, writes ``owners-manual.document.md``, ``.html``, and ``owners-manual.parts.json``
(the part map) to ``data/drafts``, and compares the Markdown with the manual ``jason manual --render`` wrote: it must be
identical, and the command exits 1 if it is not, or if a piece is unlabeled. ``--layout`` picks how it looks; ``--list``
names the layouts and the block kinds. Reading only: nothing is written to Drive, PayHOA, or the mail.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Callable

DOCUMENTS = ("owners-manual",)
BLOCKS = (("prose", "words written once"), ("part", "the guide's own words for a slot"),
          ("rule-book", "a book of rules, read by reference"), ("excerpts", "governing documents' passages"),
          ("law", "a statute's words from disk"), ("history", "when each part was adopted"),
          ("quote", "a passage by reference"), ("form", "a form's paper rendering, one definition with the live form"),
          ("directory", "roles and published contact fields"), ("computed", "a table from the stores"),
          ("embedded", "another document by reference: nested, attached, or a visible gap"))


def cmd_document_template(args: argparse.Namespace) -> int:
    from jason.community.document_templates import LAYOUTS
    from jason.community.manual import ManualError
    from jason.tasks import document_templates as task

    if args.list or not args.document:
        print("documents: " + ", ".join(DOCUMENTS))
        print("layouts:   " + ", ".join(LAYOUTS))
        for kind, what in BLOCKS:
            print(f"  {kind:10} {what}")
        return 0
    try:
        done = task.render_manual(layout=args.layout)
    except (ManualError, ValueError) as exc:
        print(f"jason document-template: {exc}", file=sys.stderr)
        return 1
    found = done["check"]
    for name, path in done["paths"].items():
        print(f"{name:9} {path}")
    print("the plain rendering is identical to jason manual --render's: " + ("yes" if done["identical"] else "NO"))
    for line in task.summary(found):
        print(line)
    for gap in found.gaps:
        print(f"gap: {gap}")
    for line in found.unlabeled:
        print(f"unlabeled: {line}")
    return 0 if done["identical"] and found.clean else 1


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("document-template", help="Render a document from one definition: a layout apart from its "
                                                 "blocks (the owner's manual first)")
    add_common(p)
    p.add_argument("document", nargs="?", choices=DOCUMENTS, help="the document to render")
    p.add_argument("--layout", default="plain", help="how it looks: plain or guide (--list)")
    p.add_argument("--list", action="store_true", help="the documents, layouts, and block kinds")
    p.set_defaults(func=cmd_document_template)


__all__ = ["cmd_document_template", "register"]
