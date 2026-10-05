"""``jason contract-terms``: read a contract's terms: duties, deadlines, money, notice, dispute resolution, and what the
counterparty must produce.

SOURCE is a file (a PDF, a scan, a .txt, a .docx), a Drive file link or ``drive:ID`` (read-only; a Google Doc is
exported as text), or ``--library`` for every contract and proposal the library holds. The phrase grammar always reads;
``--model ollama`` adds a local model's review (preflight and the GPU lock first), ``--model bedrock`` Claude on Amazon
Bedrock (the ``bedrock`` extra and AWS credentials; it sends the contract's words to AWS, and refuses a confidential file
unless ``--allow-remote-confidential``). Each reading is saved under ``data/contracts/terms`` (private) and printed for a
person: findings, deliverables, then the terms by topic, each in the contract's own words. Never writes to Drive.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Callable

from jason.commands._shared import data_dir as _data_dir


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    parser = sub.add_parser(
        "contract-terms",
        help="Read a contract's terms: duties, deadlines, money, notice windows, dispute resolution, and what the "
             "counterparty must produce (grammar, and a model with --model ollama|bedrock)",
        description="Reads a contract with the phrase grammar (each section's duties, prohibitions, permissions, rights, "
                    "and conditions, with the parties the contract defines) and the topic rules, then draws the "
                    "deliverables and the findings beside the statutes in docs/contracts.md. --model ollama asks a "
                    "local model to review the reading; --model bedrock asks Claude on Amazon Bedrock and sends the "
                    "words to AWS. A model's term is kept only when its quote is in the text. Saves "
                    "data/contracts/terms/KEY.json (private). Never writes to Drive.",
    )
    add_common(parser)
    parser.add_argument("source", nargs="*", help="files, Drive file links, or drive:ID")
    parser.add_argument("--library", action="store_true", help="read every contract and proposal in the library")
    parser.add_argument("--model", choices=("ollama", "bedrock"), default=None,
                        help="have a model review the grammar's reading (ollama: this machine; bedrock: AWS)")
    parser.add_argument("--model-name", default="", help="the Ollama model, or the Bedrock model id")
    parser.add_argument("--model-trust", choices=("fill", "full"), default="fill",
                        help="fill (default): the model adds missed terms and fills unstated parties; full: its kind, "
                             "party, topic, and deliverable verdicts replace the grammar's")
    parser.add_argument("--region", default="", help="the Bedrock region (else JASON_BEDROCK_REGION or AWS_REGION)")
    parser.add_argument("--aws-profile", default="", help="the AWS profile for Bedrock (else JASON_BEDROCK_PROFILE)")
    parser.add_argument("--confidential", action="store_true", help="treat the named files as confidential")
    parser.add_argument("--allow-remote-confidential", action="store_true",
                        help="let a remote backend read a confidential file, for this run only")
    parser.add_argument("--list", action="store_true", help="list the saved readings (read-only)")
    parser.add_argument("--json", action="store_true", help="print the readings as JSON")
    parser.add_argument("--out", default="", help="write the markdown to this file as well")
    parser.set_defaults(func=lambda args: run(args, agent_factory))


_DRIVE_FILE = re.compile(r"(?:/file/d/|/document/d/|[?&]id=)([A-Za-z0-9_-]{20,})")


def drive_file_id(source: str) -> str:
    if source.startswith("drive:"):
        return source[len("drive:"):].strip()
    if "google.com" in source:
        m = _DRIVE_FILE.search(source)
        return m.group(1) if m else ""
    return ""


def _drive_text(drive: Any, file_id: str, stage: Path) -> tuple[str, str, bool]:
    """A Drive file's words, its name, and whether it was read as text; a PDF or scan is staged and read like a file."""
    from jason.tasks.library import text_of

    meta = drive.file_metadata(file_id, "id,name,mimeType")
    name, mime = str(meta.get("name") or file_id), str(meta.get("mimeType") or "")
    if mime == "application/vnd.google-apps.document":
        return drive.export_bytes(file_id, "text/plain").decode("utf-8", "replace"), name, True
    suffix = Path(name).suffix.lower() or ".pdf"
    stage.mkdir(parents=True, exist_ok=True)
    path = stage / f"{file_id}{suffix}"
    if not path.is_file():
        path.write_bytes(drive.download_bytes(file_id))
    text, _how = text_of(path)
    return text, name, bool(text.strip())


def run(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.community.term_model import ModelUnavailable, backend_named
    from jason.tasks import contract_terms as task

    root = _data_dir(args)
    log = lambda s: print(s, file=sys.stderr)  # noqa: E731
    # A contract's own bullets and boxes ("▪", "☒") are quoted; a console that cannot show one shows "?" instead of
    # stopping the run.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    if args.list:
        rows = task.load(root)
        if args.json:
            print(json.dumps(rows, indent=1, ensure_ascii=False))
        for r in rows:
            c = r["counts"]
            print(f"{r['key']}: {r['name']} ({r.get('counterparty') or 'no counterparty read'}) {c['terms']} terms, "
                  f"{c['deliverables']} deliverables, findings {', '.join(c['findings']) or 'none'} [{r['method']}]")
        return 0
    if not args.source and not args.library:
        print("jason contract-terms: name a file, a Drive file link, or --library (or --list)", file=sys.stderr)
        return 2
    backend = None
    if args.model:
        try:
            backend = backend_named(args.model, model=args.model_name, region=args.region, profile=args.aws_profile)
        except ValueError as exc:
            print(f"jason contract-terms: {exc}", file=sys.stderr)
            return 2
    readings = []
    try:
        with ExitStack() as stack:
            if args.library:
                readings += task.run_library(root, backend=backend, allow_remote=args.allow_remote_confidential, log=log)
            drive = None
            for source in args.source:
                file_id = drive_file_id(source)
                if file_id:
                    if drive is None:
                        agent = stack.enter_context(agent_factory(args))
                        try:
                            drive = agent.drive(interactive=getattr(args, "interactive", False))
                        except Exception as exc:  # noqa: BLE001 - no token: fail fast
                            print(f"jason contract-terms: Drive is not reachable: {exc}", file=sys.stderr)
                            return 2
                    text, name, ok = _drive_text(drive, file_id, root / "contracts" / "staging")
                    key = f"drive-{file_id}"
                else:
                    from jason.tasks.library import text_of

                    path = Path(source)
                    if not path.is_file():
                        print(f"jason contract-terms: no such file: {source}", file=sys.stderr)
                        return 2
                    text, _how = text_of(path)
                    name, ok, key = path.name, bool(text.strip()), f"file-{path.stem}"
                if not ok:
                    log(f"{name}: no text could be read")
                    continue
                try:
                    reading = task.read(text, key=key, name=name, backend=backend, confidential=args.confidential,
                                        allow_remote=args.allow_remote_confidential, trust=args.model_trust,
                                        log=log)
                except task.RemoteRefused as exc:
                    print(f"jason contract-terms: {exc}", file=sys.stderr)
                    return 2
                log(f"saved {task.save(root, reading)}")
                readings.append(reading)
    except ModelUnavailable as exc:
        print(f"jason contract-terms: the model is unavailable: {exc}", file=sys.stderr)
        return 2
    finally:
        close = getattr(backend, "close", None)
        if callable(close):
            close()
    if args.json:
        print(json.dumps([r.as_dict() for r in readings], indent=1, ensure_ascii=False))
        return 0
    text = "\n\n".join(task.markdown(r) for r in readings)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        log(f"wrote {args.out}")
    print(text)
    return 0


__all__ = ["register", "run", "drive_file_id"]
