"""Jason CLI entrypoint."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _agent(args: argparse.Namespace):
    from jason.agent import Jason

    return Jason(
        env_file=getattr(args, "env", None),
        interactive=getattr(args, "interactive", False),
    )


def cmd_login(args: argparse.Namespace) -> int:
    """Interactive Keeper login; persists device + password in ~/.keeper/."""
    from jason.config import Settings
    from jason.secrets import KeeperAuthRequired, login_to_vault

    settings = Settings.load(args.env)
    print(f"Keeper config: {settings.keeper_config}")
    if settings.env_path:
        print(f"Settings from: {settings.env_path}")
    try:
        auth, login = login_to_vault(
            username=settings.keeper_username or None,
            password=settings.keeper_password or None,
            config=settings.keeper_config,
            interactive=True,
            persist_password=not args.no_persist_password,
        )
    except KeeperAuthRequired as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    username = auth.auth_context.username
    auth.close()
    login.close()
    print(f"Logged in as {username}")
    print(f"Persistent config updated: {settings.keeper_config}")
    print("Stay Logged In enabled (persistent_login + device data key).")
    print("Non-interactive jason commands should work without prompts now.")
    return 0


def spawn_login_terminal(*, env_file: str | None = None) -> None:
    """Open a new terminal window for interactive `jason login` (Windows)."""
    jason_root = Path(__file__).resolve().parents[2]
    venv_python = jason_root / ".venv" / "Scripts" / "python.exe"
    python = str(venv_python) if venv_python.is_file() else sys.executable
    cmd = [python, "-m", "jason", "login"]
    if env_file:
        cmd.extend(["--env", env_file])
    # Keep window open so the user can read errors.
    ps = (
        f"Set-Location '{jason_root}'; "
        f"& '{python}' -m jason login"
        + (f" --env '{env_file}'" if env_file else "")
        + "; Write-Host ''; Write-Host 'Press Enter to close...'; Read-Host"
    )
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoExit",
            "-Command",
            ps,
        ],
        cwd=str(jason_root),
    )


def cmd_dump_transactions(args: argparse.Namespace) -> int:
    reviewed = args.reviewed
    if reviewed == "all":
        reviewed_arg: bool | str = "all"
    elif reviewed == "true":
        reviewed_arg = True
    else:
        reviewed_arg = False

    out = Path(args.out)
    with _agent(args) as agent:
        path = agent.dump_transactions(
            out,
            reviewed=reviewed_arg,  # type: ignore[arg-type]
            search=args.search or "",
            raw=args.raw,
            fmt=args.format,
        )
    print(f"Wrote {path}")
    return 0


def cmd_probe_transactions(args: argparse.Namespace) -> int:
    with _agent(args) as agent:
        results = agent.probe_transactions()
    for row in results:
        status = "ok" if row.get("ok") else "FAIL"
        err = f" err={row['error']}" if row.get("error") else ""
        samples = row.get("sample_ids") or []
        keys = row.get("keys")
        extra = f" keys={keys}" if keys else ""
        print(
            f"[{status}] {row['probe']}: total={row.get('total', 0)} "
            f"smud={row.get('smud_candidates', 0)} "
            f"samples={samples}{extra}{err}"
        )
    return 0


def _print_upload_report(report, *, dry_run: bool) -> None:
    for r in report.results:
        bill_info = ""
        if r.bill:
            bill_info = f" bill={r.bill.bill_id}"
        print(
            f"[{r.status}] tx={r.transaction_id} "
            f"amount={r.amount_cents} date={r.transaction_date}"
            f"{bill_info} — {r.detail}"
        )
    print(report.summary())
    if dry_run:
        print("(dry-run: no uploads performed)")


def cmd_attach_bills(args: argparse.Namespace) -> int:
    sources = None
    if getattr(args, "source", None):
        sources = [args.source]
    with _agent(args) as agent:
        report = agent.attach_bills(
            date_window_days=args.date_window_days,
            dry_run=args.dry_run,
            approve=args.approve,
            sources=sources,
        )
    _print_upload_report(report, dry_run=args.dry_run)
    return 0


def cmd_upload_smud_bills(args: argparse.Namespace) -> int:
    with _agent(args) as agent:
        report = agent.upload_smud_bills(
            date_window_days=args.date_window_days,
            dry_run=args.dry_run,
            approve=args.approve,
        )
    _print_upload_report(report, dry_run=args.dry_run)
    return 0


def cmd_upload_idoxs_bills(args: argparse.Namespace) -> int:
    with _agent(args) as agent:
        report = agent.upload_idoxs_bills(
            date_window_days=args.date_window_days,
            dry_run=args.dry_run,
            approve=args.approve,
        )
    _print_upload_report(report, dry_run=args.dry_run)
    return 0


def cmd_sync_idoxs(args: argparse.Namespace) -> int:
    import logging

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    with _agent(args) as agent:
        result = agent.sync_idoxs(
            full=args.full,
            download_pdfs=args.download_pdfs,
            account=args.account,
        )
        print(result.summary())
        if result.errors:
            for err in result.errors:
                print(f"  error: {err}", file=sys.stderr)
        print(f"\nDatabase: {agent.settings.idoxs_db}")
        print(f"Bills:    {agent.settings.idoxs_bills_dir}")
        return 1 if result.errors and result.bills_new == 0 and result.accounts_synced == 0 else 0


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--env",
        default=os.environ.get("JASON_ENV"),
        help="Path to .env (default: ./ .env or JASON_ENV)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Allow interactive Keeper password / MFA / device approval prompts",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jason",
        description="Jason HOA agent — PayHOA and utility administration",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    login = sub.add_parser(
        "login",
        help="Interactive Keeper login (run in a real terminal; persists session)",
    )
    login.add_argument(
        "--env",
        default=os.environ.get("JASON_ENV"),
        help="Path to .env",
    )
    login.add_argument(
        "--no-persist-password",
        action="store_true",
        help="Do not store master password in keeper-config.json",
    )
    login.set_defaults(func=cmd_login)

    dump = sub.add_parser(
        "dump-transactions",
        help="Dump PayHOA transactions to JSONL/JSON for analysis",
    )
    _add_common(dump)
    dump.add_argument(
        "--reviewed",
        choices=("false", "true", "all"),
        default="false",
        help="reviewed filter (default: false = unreviewed queue)",
    )
    dump.add_argument("--search", default="", help="PayHOA search query param")
    dump.add_argument(
        "--out",
        default="data/payhoa_txs.jsonl",
        help="Output path (default: data/payhoa_txs.jsonl)",
    )
    dump.add_argument(
        "--format",
        choices=("jsonl", "json"),
        default="jsonl",
        help="Output format (default: jsonl)",
    )
    dump.add_argument(
        "--raw",
        action="store_true",
        help="Write full API transaction objects",
    )
    dump.set_defaults(func=cmd_dump_transactions)

    probe = sub.add_parser(
        "probe-transactions",
        help="Live-probe PayHOA list/search filters (no uploads)",
    )
    _add_common(probe)
    probe.set_defaults(func=cmd_probe_transactions)

    upload = sub.add_parser(
        "upload-smud-bills",
        help="Match SMUD PDFs to unapproved PayHOA SMUD transactions and upload",
    )
    _add_common(upload)
    upload.add_argument(
        "--date-window-days",
        type=int,
        default=7,
        help="Max |tx date - bill date| in days (default: 7)",
    )
    upload.add_argument(
        "--dry-run",
        action="store_true",
        help="Print matches without uploading or downloading PDFs",
    )
    upload.add_argument(
        "--approve",
        action="store_true",
        help="Mark transaction approved after successful upload",
    )
    upload.set_defaults(func=cmd_upload_smud_bills)

    sync_idoxs = sub.add_parser(
        "sync-idoxs",
        help=(
            "Sync City of Sacramento bill history (ACCOUNT=ALL, metadata only, "
            "skip pages already in the DB)"
        ),
    )
    _add_common(sync_idoxs)
    sync_idoxs.add_argument(
        "--account",
        help="Single account number (default: ALL accounts)",
    )
    sync_idoxs.add_argument(
        "--full",
        action="store_true",
        help="Wider date range; do not stop early on known bills",
    )
    sync_idoxs.add_argument(
        "--download-pdfs",
        action="store_true",
        help="Also download PDFs missing from the local cache",
    )
    sync_idoxs.add_argument("-v", "--verbose", action="store_true")
    sync_idoxs.set_defaults(func=cmd_sync_idoxs)

    upload_idoxs = sub.add_parser(
        "upload-idoxs-bills",
        help=(
            "Match City of Sacramento (i-doxs) PDFs to unapproved "
            "PayHOA transactions and upload"
        ),
    )
    _add_common(upload_idoxs)
    upload_idoxs.add_argument(
        "--date-window-days",
        type=int,
        default=7,
        help="Max |tx date - bill date| in days (default: 7)",
    )
    upload_idoxs.add_argument(
        "--dry-run",
        action="store_true",
        help="Print matches without uploading or downloading PDFs",
    )
    upload_idoxs.add_argument(
        "--approve",
        action="store_true",
        help="Mark transaction approved after successful upload",
    )
    upload_idoxs.set_defaults(func=cmd_upload_idoxs_bills)

    attach = sub.add_parser(
        "attach-bills",
        help=(
            "Match unapproved PayHOA transactions to registered bill sources "
            "(SMUD, City of Sacramento) and upload PDFs"
        ),
    )
    _add_common(attach)
    attach.add_argument(
        "--date-window-days",
        type=int,
        default=7,
        help="Max |tx date - bill date| in days (default: 7)",
    )
    attach.add_argument(
        "--source",
        choices=("smud", "idoxs"),
        help="Limit to one bill source (default: all registered)",
    )
    attach.add_argument(
        "--dry-run",
        action="store_true",
        help="Print matches without uploading or downloading PDFs",
    )
    attach.add_argument(
        "--approve",
        action="store_true",
        help="Mark transaction approved after successful upload",
    )
    attach.set_defaults(func=cmd_attach_bills)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        code = args.func(args)
    except Exception as exc:  # noqa: BLE001 — CLI surface
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    raise SystemExit(code)


if __name__ == "__main__":
    main()
