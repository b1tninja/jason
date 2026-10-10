"""``jason ingest SOURCE``: take a folder, a zip, a Drive folder, or files into the library as one step of onboarding.

Inventories every file (hash, type, size, dates, where it came from), drops duplicates, reads the text (a text layer,
then OCR), classifies with the library's chain (the model only with ``--model``), finds versions of the documents jason
knows, reads the statutes each file cites and says which the authorities shelf does not hold (looked up in lawlibrary
unless ``--no-law``), and proposes each file's book, Civil Code 5200 record, and library folder. A dry run by default: ``--apply``
copies the ready files into ``data/library/files`` and records them in ``library.db``; ``--park`` parks the questions
(a file's kind, a file's folder) in the intake queue. The report is ``data/onboarding/ingest-<day>.md`` (private).
Never writes to Drive or PayHOA; a Drive folder is read only, and fails fast without a token.
"""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import ExitStack
from typing import Any, Callable

from jason.commands._shared import data_dir as _data_dir


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    parser = sub.add_parser(
        "ingest",
        help="Take a folder, zip, Drive folder, or files into the library: inventory, dedup, read, classify, find "
             "versions, and propose each file's book, record, and folder (a dry run unless --apply)",
        description="Runs the library's chain over a box of documents as one onboarding step. SOURCE is a local "
                    "folder, a .zip, a Drive folder (its link, or drive:ID; read-only), or files. Every file is hashed "
                    "and dated; duplicates and files the library already holds are noted. Text comes from the text "
                    "layer, then OCR; kinds from the profile's rules, the phrase rules, then a local model only with "
                    "--model. A file that holds a known document's text is a version of it: a new version of a living "
                    "or citable document is reported, never applied. A file with no kind is a CLASSIFY question, a "
                    "kind with no library folder a MAP question (--park parks them). Writes the private report "
                    "data/onboarding/ingest-DAY.md; --apply copies the ready files into data/library/files and records "
                    "them in library.db. Never writes to Drive or PayHOA.",
    )
    add_common(parser)
    parser.add_argument("source", nargs="*", help="a folder, a .zip, a Drive folder link or drive:ID, or files")
    parser.add_argument("--apply", action="store_true",
                        help="copy the ready files into the library store and record them in library.db")
    parser.add_argument("--park", action="store_true", help="park the questions in the intake queue (jason intake)")
    parser.add_argument("--model", nargs="?", const="", default=None,
                        help="ask a local Ollama model about files no rule placed (preflight and the GPU lock first; "
                             "the default model when no name is given)")
    parser.add_argument("--terms-model", choices=("ollama", "bedrock"), default=None,
                        help="have a model review each contract's terms (the grammar reads them without one; bedrock "
                             "sends the words to AWS and skips a confidential file)")
    parser.add_argument("--terms-model-name", default="", help="the Ollama model or Bedrock model id for --terms-model")
    parser.add_argument("--allow-remote-confidential", action="store_true",
                        help="let a remote --terms-model read a confidential file, for this run only")
    parser.add_argument("--no-ocr", action="store_true", help="read text layers only; an image-only file is left unread")
    parser.add_argument("--no-law", action="store_true",
                        help="do not look the statutes the files cite up in lawlibrary; one off the authorities shelf is then unchecked")
    parser.add_argument("--gate", action="store_true",
                        help="print what the last ingest says for the onboarding session's ingest stage (read-only)")
    parser.add_argument("--json", action="store_true", help="print the run as JSON")
    parser.set_defaults(func=lambda args: run(args, agent_factory))


def run(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.community import community
    from jason.tasks import ingest as task

    root = _data_dir(args)
    if args.gate:
        g = task.gate(root)
        print(json.dumps(g, indent=1) if args.json else "\n".join(task.gate_lines(root)))
        return 0
    if not args.source:
        print("jason ingest: name a SOURCE (a folder, a .zip, a Drive folder, or files), or --gate", file=sys.stderr)
        return 2
    law = None
    if not args.no_law:
        from jason.sources.lawlibrary import LawLibrary

        law = LawLibrary() if LawLibrary().available() else None
    model = None
    if args.model is not None:
        from jason.community.content import ModelClassifier

        model = ModelClassifier(model=args.model)
    terms_backend = None
    if args.terms_model:
        from jason.community.term_model import backend_named

        terms_backend = backend_named(args.terms_model, model=args.terms_model_name)
    with ExitStack() as stack:
        drive = None
        if any(task.drive_folder_id(s) for s in args.source):
            agent = stack.enter_context(agent_factory(args))
            try:
                drive = agent.drive(interactive=getattr(args, "interactive", False))
            except Exception as exc:  # noqa: BLE001 - no token: fail fast, read nothing
                print(f"jason ingest: Drive is not reachable: {exc}", file=sys.stderr)
                return 2
        try:
            result = task.run(community(), root, list(args.source), drive=drive, model=model, ocr=not args.no_ocr,
                              apply_files=args.apply, park=args.park, law=law, terms_backend=terms_backend,
                              allow_remote=args.allow_remote_confidential, log=lambda s: print(s, file=sys.stderr))
        except ValueError as exc:
            print(f"jason ingest: {exc}", file=sys.stderr)
            return 2
        except Exception as exc:  # noqa: BLE001 - the terms model went away mid-run: say so, file nothing half-read
            from jason.community.term_model import ModelUnavailable

            if not isinstance(exc, ModelUnavailable):
                raise
            print(f"jason ingest: the terms model is unavailable: {exc}", file=sys.stderr)
            return 2
        finally:
            close = getattr(terms_backend, "close", None)
            if callable(close):
                close()
            if model is not None:
                try:
                    from jason.local_ai import unload

                    unload(model.model)
                except Exception:  # noqa: BLE001 - Ollama gone already: nothing to unload
                    pass
    if args.json:
        print(json.dumps(result.as_dict(), indent=1, ensure_ascii=False))
    else:
        print("\n".join(task.lines(result)))
    return 0


__all__ = ["register", "run"]
