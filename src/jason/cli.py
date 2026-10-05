"""Jason CLI entrypoint."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _bill_sources() -> tuple[str, ...]:
    """The bill sources `--source` accepts: the two utilities, then each vendor portal in the specification."""
    from jason.community import community as active

    return ("smud", "idoxs", *(p.key for p in active().vendor_portals()))


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

    out = Path(args.out) if args.out else None
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


def cmd_sync_bills(args: argparse.Namespace) -> int:
    import logging

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    sources = [args.source] if getattr(args, "source", None) else None
    with _agent(args) as agent:
        report = agent.sync_bills(
            date_window_days=args.date_window_days,
            dry_run=args.dry_run,
            approve=args.approve,
            skip_sync=args.skip_sync,
            sources=sources,
        )

    print("=== Pending PayHOA utility transactions ===")
    if not report.pending:
        print("(none)")
    else:
        for tx in report.pending:
            attached = " attached" if tx.has_attachments else ""
            desc = tx.description.replace("\n", " ")[:70]
            print(
                f"  [{tx.source}] tx={tx.transaction_id} "
                f"amount={tx.amount_cents} date={tx.transaction_date}"
                f"{attached} — {desc}"
            )

    print()
    needed = ", ".join(report.sources_needed) or "(none)"
    print(f"Sources needed: {needed}")

    for name, summary in report.sync_summaries.items():
        print()
        print(f"=== Synced {name} ===")
        print(summary)

    if report.skipped_reason:
        print()
        print(f"Note: {report.skipped_reason}")

    print()
    print("=== Attach to PayHOA ===")
    if report.upload is not None:
        _print_upload_report(report.upload, dry_run=args.dry_run)
    else:
        print("(no upload step)")
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


def cmd_sync_catalog(args: argparse.Namespace) -> int:
    kinds = None
    if args.only:
        kinds = [part.strip() for part in args.only.split(",") if part.strip()]
    with _agent(args) as agent:
        report = agent.sync_catalog(
            kinds=kinds,
            people_status=args.people_status,
            violation_status=args.violation_status,
        )
        print(report.summary())
        print(f"Catalog: {agent.settings.payhoa_catalog}")
        for err in report.errors:
            print(f"  error: {err}", file=sys.stderr)
    return 1 if report.errors else 0


def cmd_request_sheet(args: argparse.Namespace) -> int:
    statuses = ("pending",)
    if args.status:
        statuses = tuple(part.strip() for part in args.status.split(",") if part.strip())
    with _agent(args) as agent:
        if args.spreadsheet:
            count = agent.embed_request_photos(args.spreadsheet)
            print(f"photos={count} url=https://docs.google.com/spreadsheets/d/{args.spreadsheet}")
            return 0
        report = agent.export_request_sheet(statuses=statuses, title=args.title)
    print(report.summary())
    return 0


def cmd_export_requests(args: argparse.Namespace) -> int:
    statuses = None
    if args.status:
        statuses = tuple(part.strip() for part in args.status.split(",") if part.strip())
    with _agent(args) as agent:
        report = agent.export_requests(
            args.out,
            statuses=statuses,
            form_name=args.form,
            refresh=not args.no_refresh,
        )
    print(report.summary())
    print(f"Email: {report.path.with_suffix('.html')}")
    return 0


def cmd_export_documents(args: argparse.Namespace) -> int:
    with _agent(args) as agent:
        report = agent.export_documents(args.out)
    print(report.summary())
    return 0


def cmd_document_sync(args: argparse.Namespace) -> int:
    with _agent(args) as agent:
        report = agent.document_sync(interactive=args.interactive)
        dest = (
            Path(args.out)
            if args.out
            else agent.settings.payhoa_catalog.parent / "sync-plan"
        )
    from jason.tasks.sync_drive_documents import write_sync_plan

    folder = write_sync_plan(report, dest)
    print(report.summary())
    print(folder)
    return 0


def cmd_publish_document(args: argparse.Namespace) -> int:
    with _agent(args) as agent:
        created = agent.publish_google_doc(
            args.doc,
            args.parent,
            args.out,
            file_name=args.name,
            interactive=args.interactive,
        )
    print(f"{created.get('id')} {created.get('path') or created.get('fileName')}")
    return 0


def cmd_reports(args: argparse.Namespace) -> int:
    with _agent(args) as agent:
        rows = agent.list_reports()
        client = agent.payhoa()
        overview = client.issued_charges_overview(agent.org_id)
        resale = client.resale_docs_summary(agent.org_id)
        exports = client.list_pdf_exports(agent.org_id)
    print(f"Report catalog: {len(rows)}")
    group = None
    for row in rows:
        if row["group"] != group:
            group = row["group"]
            print(f"\n{group}")
        criteria = ", ".join(row["criteria"]) or "(none)"
        print(f"  {row['report_key']}: {row['name']} [{criteria}]")
    buckets = (overview.get("overview") or overview)
    print("\nIssued charges overview (cents)")
    if isinstance(buckets, dict):
        for key, value in buckets.items():
            print(f"  {key}={value}")
    banner = resale.get("data") or resale
    print("Resale docs")
    if isinstance(banner, dict):
        for key, value in banner.items():
            print(f"  {key}={value}")
    print(f"PDF exports: {len(exports)}")
    return 0


def cmd_who_owes(args: argparse.Namespace) -> int:
    with _agent(args) as agent:
        report = agent.who_owes()
    print(report.summary())
    for row in report.rows[:30]:
        print(
            f"  unit={row.unit_id} {row.unit_label} "
            f"unpaid_cents={row.unpaid_amount_cents} "
            f"charges={len(row.charge_ids)}"
        )
    if len(report.rows) > 30:
        print(f"  ... {len(report.rows) - 30} more")
    return 0


def cmd_permits(args: argparse.Namespace) -> int:
    """Search Sacramento Citizen Access. Does not submit or pay for a permit."""
    from pathlib import Path

    from jason.community.accela import CapId, RecordQuery, SacramentoCitizenAccess

    module = _permit_module(args.module)
    client = SacramentoCitizenAccess()
    _sign_in_citizen_access(client)
    if args.cap:
        detail = client.detail(CapId.parse(args.cap, module=module.value))
        print(f"{detail.cap.id1}:{detail.cap.id2}:{detail.cap.id3}")
        print(f"Paid ${detail.paid_cents / 100:.2f}  Unpaid ${detail.unpaid_cents / 100:.2f}")
        for fee in (*detail.fees_paid, *detail.fees_unpaid):
            kind = "paid" if fee.paid else "unpaid"
            print(f"  {fee.when or ''}  {fee.invoice}  ${fee.amount_cents / 100:.2f}  {kind}")
        for task in detail.tasks:
            print(task.name)
            for mark in task.marks:
                print(f"  {mark.when or ''}  {mark.status}  {mark.by}")
        for related in detail.related:
            indent = "  " * related.depth
            print(f"{indent}{related.number}  {related.record_type}  {related.project}")
        if detail.conditions:
            print("Conditions")
            for condition in detail.conditions:
                when = condition.applied.isoformat() if condition.applied else ""
                print(f"  {condition.group}  {condition.kind}  {condition.status}  {condition.severity}  {when}")
                print(f"  {condition.name}")
                if condition.comment:
                    print(f"  {condition.comment}")
        for report in detail.reports:
            print(f"Report  {report.name}  {report.report_type}  {report.report_id}")
        for document in client.documents(CapId.parse(args.cap, module=module.value)):
            uploaded = document.uploaded.isoformat() if document.uploaded else ""
            print(f"Document  {document.name}  {document.kind}  {document.size}  {uploaded}  {document.number}")
        if args.save_report:
            pdf = client.download_report(CapId.parse(args.cap, module=module.value))
            Path(args.save_report).write_bytes(pdf)
            print(f"Wrote {args.save_report}")
        return 0
    if args.lookup == "parcel":
        if not args.parcel:
            print("A parcel lookup needs --parcel", file=sys.stderr)
            return 1
        info = client.lookup_parcel(args.parcel)
        if info is None:
            hits = client.find_parcels(args.parcel)
            if not hits:
                print("No parcel")
                return 0
            for hit in hits:
                extra = f"\tseq {hit.seq}" if hit.seq else ""
                print(f"{hit.number}\tlot {hit.lot}\tblock {hit.block}{extra}")
            return 0
        print(info.number)
        print(f"Lot {info.lot}  Block {info.block}  {info.subdivision}")
        print(f"Area {info.area}  Zoning {info.zoning}")
        for address in info.addresses:
            print(address)
        return 0
    if args.lookup == "address":
        if not args.street:
            print("An address lookup needs --street", file=sys.stderr)
            return 1
        hits = client.lookup_address(
            args.street,
            suffix=args.suffix,
            number_from=args.street_from,
            number_to=args.street_to,
            direction=args.direction,
        )
        for hit in hits:
            print(f"{hit.parcel_number}\t{hit.address}")
        print(f"{len(hits)} addresses")
        return 0

    result = client.search(
        module,
        RecordQuery(
            permit_number=args.permit,
            project_name=args.project,
            start=_cli_date(args.start),
            end=_cli_date(args.end),
            street_from=args.street_from,
            street_to=args.street_to,
            direction=args.direction,
            street_name=args.street,
            street_suffix=args.suffix,
            parcel=args.parcel,
            license_type=args.license_type,
            license_number=args.license_number,
            first_name=args.first_name,
            last_name=args.last_name,
            business_name=args.business,
        ),
    )
    if args.out:
        Path(args.out).write_text(result.csv_text, encoding="utf-8")
        print(f"Wrote {args.out}")
    for permit in result.permits:
        opened = permit.opened.isoformat() if permit.opened else ""
        cap = ""
        if permit.cap is not None:
            cap = f"{permit.cap.id1}:{permit.cap.id2}:{permit.cap.id3}"
        print(f"{opened}\t{permit.number}\t{permit.record_type}\t{permit.status}\t{permit.address}\t{cap}")
    shown = ""
    if result.showing is not None:
        start, end, total = result.showing
        shown = f" (grid {start}-{end} of {total})"
    print(f"{len(result.permits)} records{shown}")
    return 0


def _sign_in_citizen_access(client) -> None:
    """Use the Keeper Citizen Access record when one is configured."""
    from jason.community.accela import AccelaError
    from jason.config import Settings
    from jason.secrets import get_accela_credentials

    settings = Settings.load()
    if not settings.accela_record_uid:
        return
    creds = get_accela_credentials(settings=settings, interactive=False)
    if not client.sign_in(creds.login, creds.password):
        raise AccelaError("Citizen Access rejected the Keeper login")
    print("Signed in to Citizen Access")


def _permit_module(name: str):
    from jason.community.accela import AccelaError, Module

    aliases = {
        "building": Module.BUILDING,
        "planning": Module.PLANNING,
        "public-works": Module.PUBLIC_WORKS,
        "publicworks": Module.PUBLIC_WORKS,
        "operating-permit": Module.OPERATING_PERMIT,
        "operatingpermit": Module.OPERATING_PERMIT,
    }
    try:
        return aliases[name.lower()]
    except KeyError as exc:
        raise AccelaError(f"Unknown module {name}") from exc


def _cli_date(value: str):
    from datetime import datetime

    from jason.community.accela import AccelaError

    if not value:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise AccelaError(f"A date is MM/DD/YYYY, not {value!r}")


def cmd_county_report(args: argparse.Namespace) -> int:
    """County tabs from the local catalogs, or a new spreadsheet when publishing."""
    from jason.tasks.county_report import summarize_tabs

    with _agent(args) as agent:
        if args.local:
            print(summarize_tabs(agent.county_tables(live=False)))
            return 0
        result = agent.county_report(interactive=args.interactive)
    print(result.summary())
    if not args.no_browser:
        from jason.tasks.ownership_sheet import open_sheet
        open_sheet(result.url)
    return 0


def cmd_property_history(args: argparse.Namespace) -> int:
    """Per-parcel Markdown histories from the local stores; a spreadsheet with --sheet."""
    with _agent(args) as agent:
        result = agent.property_history(
            out=args.out or None,
            sheet=args.sheet,
            spreadsheet_id=args.spreadsheet,
            interactive=args.interactive,
            charts=not args.no_charts,
        )
    print(result.summary())
    if result.url and not args.no_browser:
        from jason.tasks.ownership_sheet import open_sheet
        open_sheet(result.url)
    return 0


def cmd_unit_charts(args: argparse.Namespace) -> int:
    """Create a spreadsheet that charts the two unit numberings, their overlap, and the sales."""
    with _agent(args) as agent:
        result = agent.unit_charts(interactive=args.interactive)
    print(result.summary())
    if not args.no_browser:
        from jason.tasks.ownership_sheet import open_sheet
        open_sheet(result.url)
    return 0


def cmd_sales_charts(args: argparse.Namespace) -> int:
    """Create a spreadsheet that charts the conveyance history."""
    with _agent(args) as agent:
        result = agent.sales_charts(interactive=args.interactive)
    print(result.summary())
    if not args.no_browser:
        from jason.tasks.ownership_sheet import open_sheet
        open_sheet(result.url)
    return 0


def cmd_equity_charts(args: argparse.Namespace) -> int:
    """Create a spreadsheet of unit values, appreciation, building rollups, and a per-unit lookup."""
    with _agent(args) as agent:
        result = agent.equity_charts(interactive=args.interactive, spreadsheet_id=args.spreadsheet or "")
    print(result.summary())
    if not args.no_browser:
        from jason.tasks.ownership_sheet import open_sheet
        open_sheet(result.url)
    return 0


def cmd_ownership_sheet(args: argparse.Namespace) -> int:
    """Create a new ownership spreadsheet. Does not edit the Membership workbook."""
    with _agent(args) as agent:
        result = agent.ownership_sheet(interactive=args.interactive)
    print(result.summary())
    if not args.no_browser:
        from jason.tasks.ownership_sheet import open_sheet
        open_sheet(result.url)
    return 0


def cmd_who_owes_sheet(args: argparse.Namespace) -> int:
    """Write who-owes into the configured sheet for human review (no agency submit)."""
    with _agent(args) as agent:
        sheet_id = agent.settings.google_sheets_spreadsheet_id
        if not sheet_id:
            print(
                "google_sheets_spreadsheet_id is empty; set it in .env",
                file=sys.stderr,
            )
            return 1
        result = agent.who_owes_sheet(interactive=args.interactive)
    print(result.summary())
    return 0


def cmd_violations(args: argparse.Namespace) -> int:
    with _agent(args) as agent:
        report = agent.pull_violations()
    print(report.summary())
    return 0


def cmd_notes(args: argparse.Namespace) -> int:
    if args.unit_id is None and args.membership_id is None:
        print("Pass --unit and/or --member", file=sys.stderr)
        return 1
    with _agent(args) as agent:
        notes = agent.context_notes(
            unit_id=args.unit_id, membership_id=args.membership_id
        )
    print(notes.summary())
    return 0


def cmd_communications(args: argparse.Namespace) -> int:
    with _agent(args) as agent:
        report = agent.owner_communications(args.recipient_id)
    print(report.summary())
    for row in report.summaries[:20]:
        print(" ", " ".join(f"{key}={row[key]}" for key in row))
    return 0


def cmd_vendor_matches(args: argparse.Namespace) -> int:
    with _agent(args) as agent:
        report = agent.vendor_matches()
    print(report.summary())
    shown = 0
    for match in report.matches:
        if not match.unique:
            continue
        print(
            f"  tx={match.transaction_id} vendor={','.join(match.matched_vendor_names)}"
        )
        shown += 1
        if shown >= 20:
            break
    return 0


def cmd_request_comment(args: argparse.Namespace) -> int:
    with _agent(args) as agent:
        agent.comment_on_request(
            args.request_id,
            args.message,
            notify_owner=not args.no_notify,
            notify_admins=args.notify_admins,
        )
    print(f"comment request={args.request_id} notify_owner={not args.no_notify}")
    return 0


def cmd_request_note(args: argparse.Namespace) -> int:
    with _agent(args) as agent:
        saved = agent.note_on_request(
            args.request_id, args.note, private=not args.public
        )
    print(f"note request={args.request_id} id={saved.get('id')} private={saved.get('private')}")
    return 0


def cmd_request_attach(args: argparse.Namespace) -> int:
    with _agent(args) as agent:
        saved = agent.attach_to_request(
            args.request_id, args.path, notify=args.notify
        )
    print(f"file request={args.request_id} id={saved.get('id')} name={saved.get('fileName')}")
    return 0


def cmd_sync_request_files(args: argparse.Namespace) -> int:
    ids = [int(part) for part in args.request_ids.split(",") if part.strip()] if args.request_ids else None
    with _agent(args) as agent:
        report = agent.sync_request_files(request_ids=ids)
        dest = agent.settings.payhoa_catalog.parent / "payhoa-files"
    print(report.summary())
    print(f"Files: {dest}")
    for item in report.saved[:20]:
        state = "skipped" if item.skipped else "saved"
        print(f"  {state} request={item.request_id} file={item.file_id} {item.path.name}")
    if report.errors:
        for error in report.errors[:10]:
            print(f"  error {error}")
    return 1 if report.errors and report.files == 0 and report.skipped == 0 else 0


def cmd_review_requests(args: argparse.Namespace) -> int:
    with _agent(args) as agent:
        items = agent.review_requests(
            apply_tag=args.apply_tag, tag_color=args.tag_color
        )
    print(f"open_requests={len(items)}")
    for item in items[:30]:
        print(
            f"  [{item.form_name}] id={item.request_id} unit={item.unit} "
            f"quote={item.quote!r} docs={item.document_note} "
            f"tagged={item.tag_applied}"
        )
    if len(items) > 30:
        print(f"  ... {len(items) - 30} more")
    return 0


def cmd_sync_secured(args: argparse.Namespace) -> int:
    with _agent(args) as agent:
        result = agent.sync_secured(args.roll, parcel=args.parcel or None)
        print(result.summary())
        for apn in result.missed:
            print(f"  missed {apn}")
        for err in result.errors:
            print(f"  error: {err}", file=sys.stderr)
        print(f"\nDatabase: {agent.settings.secured_db}")
        return 1 if result.errors and result.parcels_synced == 0 else 0


def cmd_sync_tax(args: argparse.Namespace) -> int:
    with _agent(args) as agent:
        result = agent.sync_tax(parcel=args.parcel or None)
        print(result.summary())
        for apn in result.missed:
            print(f"  missed {apn}")
        for err in result.errors:
            print(f"  error: {err}", file=sys.stderr)
        print(f"\nDatabase: {agent.settings.tax_db}")
        print(f"Bills:    {agent.settings.tax_bills_dir}")
        return 1 if result.errors and result.accounts_synced == 0 else 0


def cmd_brief(args: argparse.Namespace) -> int:
    """One unit on one page from the stores; --escrow adds what escrow asks about."""
    import json

    from jason.community.briefs import brief_markdown
    from jason.mcp.county import escrow_brief, unit_brief

    brief = unit_brief(args.apn)
    if not brief.get("found"):
        print(f"no parcel {args.apn} in the stores", file=sys.stderr)
        return 1
    if args.escrow:
        brief["tellEscrow"] = escrow_brief(args.apn).get("tellEscrow", [])
    if args.json:
        print(json.dumps(brief, indent=2, default=str))
    else:
        print(brief_markdown(brief))
    return 0


def cmd_read_scans(args: argparse.Namespace) -> int:
    """Read each image-only governing PDF with the local vision model and keep the readings under data/readings."""
    from jason.community.ollama_extractor import OllamaExtractor, OllamaUnavailable
    from jason.tasks.read_scans import read_image_only

    with _agent(args) as agent:
        root = agent.settings.ownership_db.parent
    reader = OllamaExtractor(model=args.model) if args.model else OllamaExtractor()
    try:
        reader.check()
    except OllamaUnavailable as exc:
        print(str(exc), file=sys.stderr)
        return 1
    report = read_image_only(root, reader, refresh=args.refresh)
    print(report.summary())
    for name in report.read:
        print(f"  read {name}")
    for err in report.errors:
        print(f"  error: {err}", file=sys.stderr)
    return 0


def cmd_ocr_documents(args: argparse.Namespace) -> int:
    """Write a text layer beside each image-only PDF in the governing folders, with whatever OCR engine is installed."""
    from jason.community.ocr import engines, ocr_folder

    with _agent(args) as agent:
        root = agent.settings.ownership_db.parent / "artifacts" / "site-docs"
    names = [engine.name for engine in engines()]
    print(f"engines: {', '.join(names) or 'none'}")
    for folder in ("governing_documents", "governing_documents_Annexations"):
        report = ocr_folder(root / folder)
        print(f"{folder}: {report.summary()}")
        for path in report.written:
            print(f"  wrote {path}")
        for err in report.errors:
            print(f"  {err}", file=sys.stderr)
    return 0


def cmd_read_documents(args: argparse.Namespace) -> int:
    """Score a document reader against the pinned facts, or search the extracts by passage."""
    import json

    from jason.mcp.county import extraction_scorecard, passage_search

    if args.search:
        result = passage_search(args.search, k=args.k)
        for hit in result["hits"]:
            print(f"{hit['score']:>7}  {hit['file']}  passage {hit['passage']}")
            print("        " + hit["text"][:400])
        return 0
    result = extraction_scorecard(args.extractor, model=args.model)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0
    if not result.get("available", True):
        print(result.get("note", "unavailable"), file=sys.stderr)
        return 1
    print(f"{result['extractor']}: {result['cases']} cases")
    for name, score in result["fields"].items():
        print(f"  {name:<24} hits={score['hits']:>2} misses={score['misses']:>2} wrong={score['wrong']:>2}")
    for failure in result["failures"]:
        print(f"  {failure['case']}: {failure['field']} expected {failure['expected']} got {failure['actual']}")
    return 0


def cmd_mailroom(args: argparse.Namespace) -> int:
    """PayHOA's Mailroom: read mailings; preview a letter; mail it or cancel one only with --yes."""
    import json
    from dataclasses import asdict
    from pathlib import Path as _Path

    from jason.tasks.mailroom import prepare, printed, send, status

    if (args.send or args.cancel) and not args.yes:
        print("--send and --cancel act on real mail (a letter is printed, mailed, and charged to the association); add --yes. "
              "Without --send, --pdf only previews.")
        if not args.pdf:
            return 2
    with _agent(args) as agent:
        data_dir = agent.settings.ownership_db.parent
        client, org_id = agent.payhoa(), agent.org_id
        if args.prices:
            from payhoa.pricing import PRICING

            from jason.tasks.mailroom import price_check

            print(f"PayHOA's pricing guide (read {PRICING.read}): ${PRICING.standard / 100:.2f} standard or "
                  f"${PRICING.first_class / 100:.2f} first class for the first page, ${PRICING.page / 100:.2f} each page "
                  f"after, +${PRICING.heavy / 100:.2f} from {PRICING.heavy_from} pages; the address page is billed, so a "
                  f"PDF of {PRICING.pages_before_heavy()} pages is the most before the extra postage")
            result = price_check(client, org_id, data_dir)
            for g in result["groups"]:
                print(f"  {g['month']} {g['kind']:9} {g['pages']:>3} pages "
                      f"{'first class' if g['firstClass'] else 'standard':11} {'color' if g['color'] else 'b&w':5} "
                      f"{g['letters']:>3} letters: {g['charged']}c each, guide {g['guide']}c ({g['matches']})")
            print(f"saved {data_dir / 'mailroom' / 'price-check.json'}")
            return 0
        if args.months:
            year = int(args.months)
            for month, n in client.paper_mail_by_month(org_id, start_date=f"{year}-01-01", end_date=f"{year}-12-31"):
                print(f"  {month}: {n}")
            return 0
        if args.letters:
            rows = client.mail_letters(org_id, args.letters)
            if args.json:
                print(json.dumps(rows, indent=2, default=str))
                return 0
            for x in rows[-25:]:                      # the newest; addresses stay out of the listing
                print(f"  letter {x.get('id')} ({str(x.get('createdAt') or '')[:16]}): {x.get('status')}, "
                      f"{x.get('lastEvent')}, ${int(x.get('totalCost') or 0) / 100:.2f}, communication "
                      f"{x.get('commActivityId')}" + (", cancelled" if x.get("cancelledAt") else ""))
            print(f"{len(rows)} {args.letters} letters; --events COMMUNICATION for one letter's postal events")
            return 0
        if args.events:
            from jason.tasks.mailroom import letter_history

            for e in letter_history(client, org_id, args.events):
                print(f"  {e.get('createdAt')}: {e.get('event')}" + (f" ({e['additional']})" if e.get("additional") else ""))
            return 0
        if args.cancel:
            if args.yes:
                client.cancel_mail(org_id, args.cancel)
                print(f"cancelled letter {args.cancel}")
            return 0
        if args.batch:
            letters = client.mail_batch(org_id, args.batch)
            if args.json:
                print(json.dumps(letters, indent=2, default=str))
                return 0
            for x in letters:
                print(f"  letter {x.get('id')}: {x.get('status')}, last event {x.get('lastEvent')}, ${int(x.get('totalCost') or 0) / 100:.2f}"
                      f"{', tracking ' + x['trackingNumber'] if x.get('trackingNumber') else ''}"
                      f"{', cancelled ' + x['cancelledAt'] if x.get('cancelledAt') else ''}; to {x.get('sentToAddress', '').splitlines()[0] if x.get('sentToAddress') else '?'}")
            return 0
        if args.pdf:
            wanted = [w for w in args.units.split(",") if w.strip()]
            if not wanted:
                print("--pdf needs --units (street addresses, PayHOA unit ids, or 'all')", file=sys.stderr)
                return 2
            prepared = prepare(client, org_id, data_dir, _Path(args.pdf), wanted, send_to=args.send_to, with_invoices=args.with_invoices)
            included = [r for r in prepared.recipients if r.get("isIncluded", True)]
            print(f"{_Path(prepared.pdf).name}: {prepared.pages} pages to {len(included)} recipients at their "
                  f"{'mailing' if prepared.send_to == 'mailing' else 'unit'} address; preview saved to {prepared.preview}")
            run = printed(prepared.pages, double_sided=args.double_sided)
            print(f"  prints as {run.pages} pages on {run.sheets} sheets ({'double' if args.double_sided else 'single'}-sided), "
                  f"PayHOA's address page first (billed; not in its preview); ${run.cents / 100:.2f} a letter by the "
                  f"pricing guide, ${run.cents * len(included) / 100:.2f} for {len(included)}"
                  + ("; the last sheet's back is blank (free: billing is by page)" if run.blank_back else ""))
            if run.heavy:
                print(f"  {run.pages} billed pages: $2.25 more postage a letter; a page fewer would save it")
            for name in prepared.missing:
                print(f"  no PayHOA unit matched '{name}'")
            for r in prepared.recipients:
                flags = ("" if r.get("isIncluded", True) else " (left out)") + (" (duplicate)" if r.get("isDuplicate") else "")
                print(f"  {r.get('unitTitles')}: {r.get('address', '').replace(chr(10), ', ')}{flags}")
            if args.notice:
                from jason.tasks.notice_text import NoticeKeyError, check_key

                try:
                    check_key(args.notice)
                except NoticeKeyError as exc:
                    print(exc, file=sys.stderr)
                    return 2
            if not (args.send and args.yes):
                print("not mailed: read the preview, then rerun with --send --yes to print and mail it (postage is charged)"
                      + (f"; the letter is then kept in {data_dir / 'notices' / args.notice}" if args.notice else ""))
                return 0
            record = send(client, org_id, data_dir, prepared, double_sided=args.double_sided, with_invoices=args.with_invoices)
            cost = sum(b["costCents"] for b in record["batches"])
            print(f"mailed: batch {', '.join(str(b['id']) for b in record['batches']) or '(not listed yet)'}"
                  f"{f', ${cost / 100:.2f}' if cost else ''}; logged in {data_dir / 'mailroom' / 'sent.jsonl'}")
            if args.notice:
                from jason.tasks.mailroom import keep_notice

                entry = keep_notice(data_dir, args.notice, prepared, record, by=args.by or "")
                print(f"kept the letter as mailed in {data_dir / 'notices' / args.notice} "
                      f"(sha256 {entry['files'][0]['sha256'][:16]}); jason cite jason://notice/{args.notice}")
            return 0
        result = status(client, org_id, data_dir)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0
    v, c = result["verify"], result["counts"]
    print(f"Mailroom: return address {'on file' if v.get('hasAddress') else 'MISSING'}, payment {'on file' if v.get('hasPayment') else 'MISSING'}; "
          f"this year {c.get('letters')} letters, {c.get('paper')} paper mailings")
    for b in sorted(result["pdfBatches"] + result["invoiceBatches"], key=lambda b: str(b["created"]), reverse=True)[:15]:
        opts = ", ".join(o for o, on in (("certified", b["certified"]), ("color", b["color"]), ("2-sided", b["twoSided"])) if on)
        print(f"  {b['created']} {b['kind']:<7} batch {b['id']}: ${b['costCents'] / 100:,.2f}; sent {b['sent']}, failed {b['failed']}, "
              f"cancelled {b['cancelled']}{'; ' + str(b['pages']) + ' pages' if b['pages'] else ''}{'; ' + opts if opts else ''}")
    return 0


def cmd_law_history(args: argparse.Namespace) -> int:
    """Export, or read from disk, where the former Davis-Stirling sections went and how the Act changed."""
    import json
    import re as _re

    from jason.community.succession import changes, now_at, successors

    with _agent(args) as agent:
        root = agent.settings.ownership_db.parent
        if args.versions or args.add_version:
            from jason.commands.law_versions import run as law_versions

            return law_versions(args, root, agent.lawlibrary)
        if args.export:
            from jason.sources.lawlibrary import LawLibraryUnavailable
            from jason.tasks.law_history import export

            try:
                print(f"exported: {export(agent.lawlibrary(), root)}")
            except LawLibraryUnavailable as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return 1
    if args.sweep:
        from collections import Counter
        from pathlib import Path as _Path

        from jason.tasks.law_sweep import sweep, write

        entries = sweep(_Path(__file__).resolve().parents[2], root, since=args.since)
        if args.json:
            from dataclasses import asdict

            print(json.dumps([asdict(e) for e in entries], indent=2, default=str))
            return 0
        page = write(entries, root / "reports", since=args.since)
        kinds = Counter(e.kind for e in entries)
        print(f"{len(entries)} changed sections cited {sum(len(e.cites) for e in entries)} times "
              f"({', '.join(f'{n} {k}' for k, n in kinds.items())}); wrote {page}")
        for e in entries:
            print(f"  {'former ' if e.kind == 'former' else ''}CIV {e.section} ({e.kind}, {len(e.cites)} citations): {e.summary[:150]}")
        return 0
    section = _re.sub(r"^(?:Civil\s+Code|CIV)\b\.?\s*(?:Section|§)?\s*", "", args.section.strip(), flags=_re.I)
    if not section:
        rows = changes(root, since=args.since)
        if args.json:
            print(json.dumps(rows, indent=2, default=str))
        elif not args.export:
            print(f"{len(rows)} changes stored; see data/authorities/history/davis-stirling-changes.md")
        return 0
    if _re.match(r"13[5-7]\d", section):
        rows = successors(root, section)
        if args.json:
            print(json.dumps([r.__dict__ for r in rows], indent=2))
            return 0
        print(now_at(root, section) or f"no stored row for former CIV {section}; run jason law-history --export")
        for r in rows:
            print(f"  {r.former} -> {', '.join(r.targets) or 'nothing'}: {r.succession.replace('_', ' ')} ({r.source.replace('_', ' ')})")
        return 0
    rows = changes(root, section, since=args.since)
    if args.json:
        print(json.dumps(rows, indent=2, default=str))
        return 0
    if not rows:
        print(f"no stored change for CIV {section}; run jason law-history --export")
    for c in rows:
        print(f"  {c.get('after')} edition: {c.get('change')}, {c.get('statute') or 'no note'}"
              f"{' (' + c['bill'] + ')' if c.get('bill') else ''}, operative {c.get('operative') or '?'}"
              f"{'; ' + c['summary'] if c.get('summary') else ''}")
    return 0


def cmd_export_authorities(args: argparse.Namespace) -> int:
    """Export statute text from lawlibrary, or list the exported pages and the pointers."""
    from jason.community.authorities import pointers
    from jason.sources.lawlibrary import LawLibraryUnavailable
    from jason.tasks.export_authorities import authority_pages, fetch_publications, read_manifest

    with _agent(args) as agent:
        root = agent.settings.ownership_db.parent
        if args.list:
            pages = authority_pages(root)
            manifest = read_manifest(root)
            print(f"{len(pages)} exported pages, session {manifest.get('session') or '?'}, exported {manifest.get('exported') or 'never'}")
            for page in pages:
                print(f"  {page.citation}: {page.title} ({len(page.sections)} sections)")
            print("pointers (not exported; read at the source):")
            for item in pointers():
                print(f"  {item.citation}: {item.shelf.value}; {item.official}")
            _print_promotions(root)
            return 0
        if args.digests:
            # The pages already on disk: each section's digest goes into the manifest; lawlibrary is not asked.
            from jason.tasks.authority_digests import backfill

            for line in backfill(root).lines():
                print(line)
            return 0
        # The publications come first: the Commissioner's regulations PDF is where the Title 10 sections are read.
        if args.fetch_publications:
            for name in fetch_publications(root):
                print(f"  fetched: {name}")
        try:
            report = agent.export_authorities()
        except LawLibraryUnavailable as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(report.summary())
        for miss in report.misses:
            print(f"  miss: {miss}")
        for row in report.changed:
            print(f"  changed: {row['citation']}; the replaced words are kept in {row['history']}")
        if report.changed:
            print("  jason readings --stale lists the readings these changes made stale")
        _print_promotions(root)
    return 0


def _print_promotions(root) -> None:
    """The sections readers fetched on demand that no curated span holds: a person promotes each with a Basis and a reason."""
    from jason.tasks.statute_fetch import promotions

    leads = promotions(root)
    if not leads:
        return
    print("fetched on demand, not on the curated list (add a row to jason.community.authorities with a Basis and why):")
    for lead in leads:
        asked = f"; asked by {', '.join(lead['asked_by'])}" if lead["asked_by"] else ""
        print(f"  {lead['citation']}: {lead['title']} ({lead['session']} session, fetched {lead['fetched']}{asked})")


def cmd_utilities(args: argparse.Namespace) -> int:
    """Parse the downloaded SMUD and City bills into data/utilities.db, then print accounts, anomalies, and the forecast."""
    import json
    from datetime import date

    from jason.community import community as active
    from jason.community.utility import Service
    from jason.config import Settings
    from jason.tasks.utilities import bill_roots, load_bills, store_path, sync, usage_history, utilities_brief, brief_lines

    settings = Settings.load(args.env)
    data_dir = settings.payhoa_catalog.parent
    path = store_path(data_dir)
    if not args.no_sync:
        result = sync(bill_roots(settings), path, full=args.full)
        print(f"parsed {result.parsed} bills ({result.unchanged} unchanged, {result.removed} removed)")
        for line in result.unreadable:
            print(f"  unreadable: {line}")
        for source in result.unreconciled:
            print(f"  charges do not add to the total: {source}")
    if args.payments:
        from jason.tasks.utility_payments import audit_lines, fetch, run_audit

        if args.fetch:
            with _agent(args) as agent:
                counts = fetch(agent.payhoa(), agent.org_id, data_dir, bill_roots(settings), log=print)
            print(f"fetched {counts}")
        result = run_audit(data_dir, active(), bill_roots(settings))
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print("\n".join(audit_lines(result, only_problems=not args.all, limit=args.limit)))
        return 0 if result.get("found") else 1
    if args.account:
        service = Service(args.service) if args.service else None
        rows = usage_history(load_bills(path), args.account, service)
        if args.json:
            print(json.dumps(rows, indent=2))
            return 0
        for row in rows:
            print(f"  {row['service']:<17} {row['start']} - {row['end']} {row['days']:>3}d  {row['usage']:>10,.0f} {row['unit']:<6} "
                  f"{row['perDay']:>9,.1f}/day  ${row['costCents'] / 100:>9,.2f}")
        return 0 if rows else 1
    brief = utilities_brief(
        data_dir, active(), year=args.year or None, water_increase=args.water_increase,
        since=date.fromisoformat(args.since) if args.since else None,
    )
    if args.json:
        print(json.dumps(brief, indent=2, default=str))
    else:
        print("\n".join(brief_lines(brief)))
    return 0 if brief.get("found") else 1


def cmd_reserves(args: argparse.Namespace) -> int:
    """Read every reserve study on disk; print next year's funding plan beside the budget and the reserve accounts."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.reserves import brief_lines, reserve_brief

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    if args.transfers:
        from datetime import date

        from jason.tasks.reserve_transfers import fetch_budgets, review, review_lines

        if args.fetch:
            with _agent(args) as agent:
                print(f"budgets {fetch_budgets(agent.payhoa(), agent.org_id, data_dir, list(range(2024, date.today().year + 1)))}")
        result = review(data_dir, active())
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            for line in review_lines(result):
                print(line)
        return 0 if result.get("found") else 1
    brief = reserve_brief(data_dir, active(), year=args.year or None)
    if args.json:
        print(json.dumps(brief, indent=2, default=str))
    else:
        for line in brief_lines(brief):
            print(line)
    return 0 if brief.get("found") else 1


def cmd_invoices(args: argparse.Namespace) -> int:
    """Check every PayHOA expense payment against its attached documents (amount, vendor, date, reuse, category)."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.invoice_review import fetch, review, review_lines
    from jason.tasks.utilities import bill_roots

    settings = Settings.load(args.env)
    data_dir = settings.payhoa_catalog.parent
    if args.fetch:
        with _agent(args) as agent:
            counts = fetch(agent.payhoa(), agent.org_id, data_dir, bill_roots(settings), log=print)
        print(f"fetched {counts}")
    result = review(data_dir, active(), bill_roots(settings))
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for line in review_lines(result, limit=args.limit, payee=args.payee):
            print(line)
    return 0 if result.get("found") else 1


def cmd_policies(args: argparse.Namespace) -> int:
    """Each insurance policy term by term from its declarations, beside the policy sheet and the specification."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.policies import fetch, find, lines, load, read_sheet, run

    settings = Settings.load(args.env)
    data_dir = settings.payhoa_catalog.parent
    sheet = None
    if args.fetch:
        from jason.tasks.drive_catalog import load_files

        with _agent(args) as agent:
            drive = agent.drive(interactive=False)
            sheet = read_sheet(drive.sheets(), active().insurance_workbook_id())
            found = find(drive, active(), sheet, {f["id"]: f for f in load_files(data_dir)})
            print(f"fetched {fetch(drive, data_dir, found, log=print)}")
    report = load(data_dir) if args.stored else run(data_dir, active(), sheet=sheet)
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        for line in lines(report, policy=args.policy or ""):
            print(line)
    return 0 if report.get("found") else 1


def cmd_incidents(args: argparse.Namespace) -> int:
    """The maintenance history and insurance claims from the repair paperwork, by unit and building (--fetch pulls Drive's)."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.incidents import fetch, lines, load, run, select
    from jason.tasks.utilities import bill_roots

    settings = Settings.load(args.env)
    data_dir = settings.payhoa_catalog.parent
    if args.fetch:
        with _agent(args) as agent:
            print(f"fetched {fetch(agent.drive(interactive=False), data_dir, active(), log=print)}")
    report = load(data_dir) if args.stored else run(data_dir, active(), bill_roots(settings), ocr=not args.no_ocr,
                                                     private=args.private, log=print)
    if args.link or args.links:
        from jason.tasks.incident_links import link, link_lines, load_links

        if args.link:
            with _agent(args) as agent:
                drive = agent.drive(interactive=False)
                result = link(data_dir, active(), drive=drive, gmail=drive.gmail(), log=print)
            print(f"linked; fetched {result.get('fetched', 0)} new files, pruned {result.get('pruned', 0)} Drive and "
                  f"{result.get('prunedMail', 0)} email files no longer linked")
            if result.get("fetched") or result.get("pruned") or result.get("prunedMail"):
                report = run(data_dir, active(), bill_roots(settings), ocr=not args.no_ocr, private=args.private, log=print)
        for line in link_lines(load_links(data_dir), event=args.address or "", limit=args.limit):
            print(line)
        return 0
    rows = select(report, building=args.building, address=args.address or "", work=args.work or "", claims=args.claims,
                  cause=args.cause or "", since=args.since or "", routine=args.all or bool(args.work),
                  standing=args.standing or "")
    if args.json:
        print(json.dumps({**report, "events": rows}, indent=2, default=str))
    else:
        for line in lines(report, rows, limit=args.limit):
            print(line)
    return 0 if report.get("found") else 1


def cmd_pests(args: argparse.Namespace) -> int:
    """The pest control program from the vendor portal: products (with labels and safety data sheets when fetched), rodents, visits."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.pests import brief_lines, pest_brief

    settings = Settings.load(args.env)
    data_dir = settings.payhoa_catalog.parent
    portal = next((p for p in active().vendor_portals() if p.key == args.key), None)
    if portal is None:
        print(f"no vendor portal {args.key!r} in mystique/vendors.py")
        return 1
    if getattr(args, "fetch", False):
        from jason.tasks.pesticides import fetch_products

        print(fetch_products(data_dir, portal, log=print).summary())
    brief = pest_brief(data_dir, portal)
    print(json.dumps(brief, indent=2, default=str) if args.json else "\n".join(brief_lines(brief)))
    return 0 if brief.get("found") else 1


def cmd_vendors(args: argparse.Namespace) -> int:
    """Sync (--sync) and verify (--verify) the vendor portals, then print what each says."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.vendor_portals import brief_lines, portal_brief
    from jason.tasks.vendor_verify import verify, verify_lines

    settings = Settings.load(args.env)
    data_dir = settings.payhoa_catalog.parent
    portals = [p for p in active().vendor_portals() if not args.key or p.key == args.key]
    if not portals:
        print(f"no vendor portal {args.key!r} in mystique/vendors.py")
        return 1
    if args.sync:
        with _agent(args) as agent:
            for portal in portals:
                if not settings.record_uid(portal.key):
                    print(f"{portal.key}: {portal.key}_record_uid is not set in .env; skipped")
                    continue
                print(agent.sync_vendor_portal(portal.key, full=args.full, log=print).summary())
    out: list = []
    for portal in portals:
        brief = portal_brief(data_dir, portal, visits=args.visits)
        result = verify(data_dir, portal) if args.verify else None
        if args.json:
            out.append({"brief": brief, "verification": result})
            continue
        print("\n".join(brief_lines(brief)))
        if result is not None:
            print("")
            print("\n".join(verify_lines(result, limit=args.limit)))
    if args.json:
        print(json.dumps(out, indent=2, default=str))
    return 0


def cmd_mail(args: argparse.Namespace) -> int:
    """Sync the PostScanMail mailbox (unless --offline), then print what arrived: what to act on, what to review, and dates."""
    import json

    from jason.config import Settings
    from jason.tasks.mail import brief_lines, mail_brief, mail_text, resort

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    if args.item:
        print(json.dumps(mail_text(data_dir, args.item), indent=2, default=str))
        return 0
    if args.checks:
        from jason.community import community as active
        from jason.tasks.mail_links import links_lines, mail_links

        from jason.tasks.utilities import bill_roots

        links = mail_links(data_dir, active(), roots=bill_roots(Settings.load(args.env)))
        if args.json:
            print(json.dumps(links, indent=2, default=str))
        else:
            for line in links_lines(links):
                print(line)
        return 0
    if args.reread_ocr:
        from jason.community import community as active
        from jason.local_ai import preflight
        from jason.tasks.mail import reread_ocr

        preflight()
        print(f"read again: {reread_ocr(data_dir, active(), limit=args.limit, log=print)}")
    elif args.resort:
        from jason.community import community as active

        print(f"sorted {resort(data_dir, active())} items again")
    elif not args.offline:
        with _agent(args) as agent:
            counts = agent.sync_mail(full=args.full, log=print)
        print(f"synced {counts}")
    brief = mail_brief(data_dir, days=args.days)
    if args.json:
        print(json.dumps(brief, indent=2, default=str))
    else:
        for line in brief_lines(brief):
            print(line)
    return 0 if brief.get("found") else 1


def cmd_zoom(args: argparse.Namespace) -> int:
    """Sync the Zoom account (unless --offline), then list its meetings with their next steps and the schedule's gaps."""
    import json
    from datetime import date

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.zoom import brief_lines, meeting_text, meetings_brief

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    if args.store_app:
        if not (args.account_id and args.client_id):
            print("--store-app needs --account-id and --client-id")
            return 2
        with _agent(args) as agent:
            uid = agent.store_zoom_app(args.account_id, args.client_id)
        print(f"created Keeper record {uid}; set zoom_record_uid = \"{uid}\" in .env and put the client secret in its password field")
        return 0
    if args.meeting:
        print(json.dumps(meeting_text(data_dir, args.meeting, include_confidential=args.confidential), indent=2, default=str))
        return 0
    if args.recording or args.caption:
        if not args.meeting_id:
            print("--recording and --caption need --meeting-id (the live meeting's id)")
            return 2
        what = (f"{args.recording} the cloud recording of meeting {args.meeting_id}" if args.recording
                else f"post 'jason: {args.caption}' into the captions of meeting {args.meeting_id}, which every participant sees")
        if not args.yes:
            print(f"this would {what}, as the host; add --yes to do it")
            return 2
        with _agent(args) as agent:
            act = (agent.control_recording(args.meeting_id, args.recording, by=args.by) if args.recording
                   else agent.caption(args.meeting_id, args.caption, lang=args.lang, by=args.by))
        print(json.dumps(act, indent=2) if args.json else f"done: {act['kind']} {act['detail']} at {act['at']}")
        return 0
    if args.create_board_meeting:
        from jason.tasks.zoom import plan_board_meeting, save_board_meeting

        try:
            plan = plan_board_meeting(active(), on=date.fromisoformat(args.date) if args.date else None, at=args.time)
        except ValueError as exc:
            print(f"error: {exc}")
            return 2
        if not args.yes:
            print(f"--create-board-meeting schedules '{plan.meeting_body()['topic']}' at {plan.start.isoformat(timespec='minutes')} "
                  "on the association's account; add --yes to do it")
            return 2
        with _agent(args) as agent:
            agent.schedule_board_meeting(plan)
        record = save_board_meeting(data_dir, plan)
        print(json.dumps(record, indent=2, default=str) if args.json else
              f"scheduled {record['topic']} at {record['start']}: join {record['zoom'].get('joinUrl')}; dial-in {', '.join(record['zoom'].get('dialIn') or [])}")
        return 0
    if not args.offline:
        with _agent(args) as agent:
            since = date.fromisoformat(args.since) if args.since else None
            print(f"synced {agent.sync_zoom(full=args.full, since=since, media=args.media, log=print)}")
    brief = meetings_brief(data_dir, active(), days=args.days or None, kind=args.kind)
    if args.json:
        print(json.dumps(brief, indent=2, default=str))
    else:
        for line in brief_lines(brief, limit=args.limit):
            print(line)
    return 0 if brief.get("found") else 1


def cmd_hearing(args: argparse.Namespace) -> int:
    """Plan a disciplinary hearing under Civil Code 5855 and draft its notice; with --create --yes, schedule it on Zoom."""
    import json
    from datetime import date

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.zoom import hearing_lines, hearings, plan_hearing, save_hearing

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    if args.list or not args.address:
        result = hearings(data_dir)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(result.get("note") or "")
            for row in result["hearings"]:
                print(f"- {row['start']}  {row['address']}: {row['standing']}{'' if row['scheduled'] else ' (no Zoom meeting yet)'}")
        return 0
    community = active()
    try:
        plan = plan_hearing(community, address=args.address, violation=args.violation,
                            on=date.fromisoformat(args.date) if args.date else None, at=args.time,
                            notice_on=date.fromisoformat(args.notice_on) if args.notice_on else None,
                            suspension=args.suspension)
    except ValueError as exc:
        print(f"error: {exc}")
        return 2
    if args.create:
        if plan.problems:
            print("not scheduling: " + "; ".join(plan.problems))
            return 2
        if not args.yes:
            print("--create schedules a Zoom meeting on the association's account; add --yes to do it")
            return 2
        with _agent(args) as agent:
            agent.schedule_hearing(plan)
    else:
        # A meeting scheduled in an earlier run is carried into the notice.
        saved = next((r for r in hearings(data_dir).get("hearings", [])
                      if r["address"] == plan.address and r["start"] == plan.start.isoformat(timespec="minutes")), None)
        plan.zoom = (saved or {}).get("zoom") or {}
    letter = None
    if args.doc:
        if not args.yes:
            print("--doc writes a Google Doc into Drive's Disciplinary folder; add --yes to do it")
            return 2
        from jason.community.templates import TemplateKind
        from jason.community.template_values import profile_values
        from jason.tasks.letters import fill_letter, hearing_values, matter_folder
        from jason.community.spec import spec_module

        UNIT_CITY_STATE_ZIP = community.identity().unit_city_state_zip

        from jason.community.profile import profile_name
        from jason.tasks.template_gen import template_for

        template = template_for(community, TemplateKind.HEARING_NOTICE, data_dir, profile_name())
        values = hearing_values(plan, city_state_zip=UNIT_CITY_STATE_ZIP, owner=args.owner, delivery=args.delivery,
                                sections=args.sections, contact=args.contact)
        day = plan.start
        with _agent(args) as agent:
            drive = agent.drive()
            folder = matter_folder(drive, template.folder_id, f"{plan.address} - {args.matter or 'Hearing'} {day.month}-{day.day}-{day:%y}")
            letter = fill_letter(drive, drive.docs(), template, values, name=f"Notice of Hearing - {plan.address}", folder_id=folder,
                                 defaults=profile_values(community))
    record = save_hearing(data_dir, plan, community.name, letter=letter)
    if args.json:
        print(json.dumps(record, indent=2, default=str))
    else:
        print("\n".join(hearing_lines(plan, record)))
        if letter:
            print(f"- notice Doc: {letter['url']}")
            if letter["unfilled"]:
                print(f"  still to fill in the Doc: {', '.join(letter['unfilled'])}")
    return 1 if plan.problems else 0


def cmd_meetings(args: argparse.Namespace) -> int:
    """Catalog every meeting record on disk (Zoom, Drive, PayHOA library, jason's drafts) by meeting, with its checks."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.meeting_catalog import build, meeting, report_lines, write

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    if args.sync:
        from jason.tasks.meeting_catalog import sync_communications

        with _agent(args) as agent:
            print(f"zoom: {agent.sync_zoom(log=print)}")
            print(f"payhoa: {sync_communications(agent.payhoa(), agent.org_id, data_dir, active(), log=print)}")
    if args.links:
        from jason.tasks.agenda_links import build as build_links, fetch as fetch_links, summary_lines

        if not args.offline_links:
            with _agent(args) as agent:
                print(f"agenda docs: {fetch_links(agent.docs(), data_dir, active(), log=print)}")
        print("\n".join(summary_lines(build_links(data_dir, active()), limit=args.limit)))
    if args.items:
        from jason.tasks.agenda_items import build as build_items, summary_lines as item_lines
        from jason.tasks.agenda_kinds import fetch as fetch_agenda_files, resolve, summary_lines as kind_lines

        print("\n".join(item_lines(build_items(data_dir, active()), limit=args.limit)))
        print("")
        if args.fetch_items:
            resolve(data_dir, active())                  # which files are undecided with no text on disk
            with _agent(args) as agent:
                print(f"agenda files: {fetch_agenda_files(agent.drive(), data_dir, log=print)}")
        print("\n".join(kind_lines(resolve(data_dir, active()), limit=args.limit)))
    if args.file:
        from jason.tasks.agenda_links import lookup

        print(json.dumps(lookup(data_dir, args.file), indent=2))
        return 0
    if args.date:
        print(json.dumps(meeting(data_dir, args.date), indent=2))
        return 0
    catalog = build(data_dir, active())
    out, report = write(data_dir, catalog)
    if args.json:
        print(json.dumps(catalog, indent=2))
    else:
        print("\n".join(report_lines(catalog, limit=args.limit)))
        print(f"\nwrote {out} and {report}")
    return 0


def cmd_jobs(args: argparse.Namespace) -> int:
    """The job queue: add a jason command, list the jobs, show one's log, or cancel one."""
    import json

    from jason import jobs
    from jason.config import Settings

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    try:
        if args.action == "add":
            override = jobs.JobClass(args.resource) if args.resource else None
            job = jobs.add(data_dir, list(args.command), confirmed_by=args.confirm, max_attempts=args.max_attempts,
                           job_class_override=override)
            print(f"queued job {job.id} [{job.job_class.value}]: {job.command}" + (f" (confirmed by {job.confirmed_by})" if job.confirmed_by else ""))
            print("  run the queue with: jason worker --once")
            return 0
        if args.action == "show":
            job = jobs.get(data_dir, int(args.command[0]))
            print("\n".join(jobs.lines([job])))
            path = jobs.log_path(data_dir, job.id)
            if path.is_file():
                print("\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-args.tail:]))
            return 0
        if args.action == "cancel":
            job = jobs.cancel(data_dir, int(args.command[0]))
            print(f"job {job.id} cancelled")
            return 0
    except (jobs.JobRefused, KeyError, ValueError, IndexError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    items = jobs.jobs(data_dir, every=args.all)
    if args.json:
        print(json.dumps([{**j.__dict__, "job_class": j.job_class.value, "status": j.status.value} for j in items], indent=2))
    else:
        print("\n".join(jobs.lines(items)) or "no jobs" + ("" if args.all else " queued, running, or failed (--all for every job)"))
    return 0


def cmd_worker(args: argparse.Namespace) -> int:
    """Run the job queue: one job at a time per resource (GPU, Google, PayHOA, local)."""
    from jason import jobs
    from jason.config import Settings

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    try:
        counts = jobs.work(data_dir, once=args.once, poll=args.poll, env_file=args.env,
                           release_models=not getattr(args, "keep_models", False))
    except jobs.JobRefused as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print("worker done: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    return 0


def cmd_outlines(args: argparse.Namespace) -> int:
    """Outline the governing documents and resolutions, and map the references among them and to the law."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks import outlines as task

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    if args.model:
        return _outlines_model(args, data_dir)
    if args.fetch:
        with _agent(args) as agent:
            drive = agent.drive()
            docs = task.build(drive.docs(), drive, active(), data_dir)
        result = task.run(data_dir, docs)
    elif not (args.doc or args.section or args.cites):
        result = task.run(data_dir)
    else:
        result = None
    outlines, rows = task.load(data_dir), task.load_rows(data_dir)
    if args.doc:
        outline = next((o for o in outlines if o.key == args.doc), None)
        if outline is None:
            print(f"no outline {args.doc}; outlined: {', '.join(o.key for o in outlines)}", file=sys.stderr)
            return 1
        print("\n".join(task.outline_lines(outline, max_depth=args.depth)))
        return 0
    if args.section:
        print("\n".join(task.section_lines(outlines, rows, args.section)))
        return 0
    if args.cites:
        hits = task.cited_by(rows, args.cites)
        if args.json:
            print(json.dumps(hits, indent=2))
        else:
            for r in hits:
                print(f"{r['source']} {r['source_section']}: {r['relation']} {r['target']}\n    \"{r['quote'][:220]}\"")
            print(f"{len(hits)} references")
        return 0
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{result['documents']} documents, {result['sections']} sections, {result['references']} references")
        print("  by kind: " + ", ".join(f"{k} {v}" for k, v in result["byKind"].items()))
        print("  by status: " + ", ".join(f"{k} {v}" for k, v in result["byStatus"].items()))
        print("  read by: " + ", ".join(f"{k} {v}" for k, v in result.get("byMethod", {}).items()))
        for f in result["findings"]:
            print(f"  ! {f}")
        print(f"wrote {data_dir / 'reports' / 'references.md'}, the viewer {result.get('viewer', data_dir / 'reports' / 'references.html')}, "
              f"and a page per document in {data_dir / 'outlines'}")
    return 0


def _outlines_model(args: argparse.Namespace, data_dir) -> int:
    """jason outlines --model: the local model reads chosen sections for the references the grammar missed."""
    import json

    from jason.community.content import ModelUnavailable
    from jason.tasks import reference_review

    try:
        result = reference_review.run(data_dir, picks=args.model_doc or (), limit=args.model_limit, again=args.model_again)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ModelUnavailable as exc:
        print(f"the local model is not available; nothing more was read: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    if not result["chosen"]:
        print("nothing to read: every chosen section was read before with the same words (--model-again reads them again)")
        return 0
    print(f"read {len(result['read'])} sections with {result['model']}:")
    for e in result["read"]:
        print(f"  {e['source']} {e['section'] or '(no section)'} {e['title'][:50]}: {e['chars']} chars"
              + (" (trimmed)" if e["trimmed"] else "") + f"; {e['proposed']} proposed, {e['added']} new, {e['known']} the grammar has, "
              f"{e['dropped']} dropped" + (f", {e['malformed']} malformed" if e["malformed"] else ""))
    print(f"added {len(result['added'])}:")
    for r in result["added"]:
        print(f"  {r['source']} {r['source_section']}: {r['relation']} {r['kind']} {r['target']} [{r['status']}]\n      \"{r['said'][:160]}\"")
    print(f"the grammar already had {len(result['known'])}: " + ", ".join(r["target"] for r in result["known"]))
    print(f"dropped {len(result['dropped'])}:")
    for r in result["dropped"]:
        print(f"  {r['source']} {r['source_section']}: {r['reason']}: {r.get('kind', '')} {r.get('target', '')}"
              + (f" \"{r['quote'][:120]}\"" if r.get("quote") else ""))
    print(f"wrote {result['path']} ({result['stored']} model references from {result['passagesRead']} sections read so far)")
    return 0


def cmd_local_ai(args: argparse.Namespace) -> int:
    """The local AI stack: Ollama and its GPU, loaded models, Windows commit and page files, jason's locks."""
    import json

    from jason.local_ai import LocalAIUnavailable, restart_ollama, status, status_lines, unload

    if args.restart_ollama or args.unload:
        if not args.yes:
            print("--restart-ollama and --unload change what Ollama is running; add --yes to do it")
            return 2
        try:
            if args.unload:
                print(f"unloaded: {', '.join(unload(args.unload)) or 'nothing was loaded'}")
            if args.restart_ollama:
                done = restart_ollama()
                print(f"Ollama {done['version']} restarted; devices: "
                      + (", ".join(f"{d['library']} {d['description']}" for d in done["devices"]) or "none reported"))
        except LocalAIUnavailable as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    result = status()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("\n".join(status_lines(result)))
    return 1 if result["findings"] and args.check else 0


def cmd_vault(args: argparse.Namespace) -> int:
    """Google Vault: list the Workspace's matters and their holds (read-only)."""
    import json

    with _agent(args) as agent:
        with agent.google_vault() as vault:
            matters = []
            for m in vault.matters():
                holds = [{"holdId": h.get("holdId"), "name": h.get("name"), "corpus": h.get("corpus"),
                          "accounts": [a.get("email") for a in h.get("accounts") or []],
                          "orgUnit": (h.get("orgUnit") or {}).get("orgUnitId"), "updated": h.get("updateTime")}
                         for h in vault.holds(m["matterId"])] if m.get("state") == "OPEN" else []
                matters.append({"matterId": m.get("matterId"), "name": m.get("name"), "state": m.get("state"),
                                "description": m.get("description"), "holds": holds})
    if args.json:
        print(json.dumps(matters, indent=2))
    else:
        print(f"Vault is reachable: {len(matters)} matter(s)")
        for m in matters:
            print(f"- {m['name']} ({m['state']}) {m['matterId']}")
            for h in m["holds"]:
                print(f"    hold {h['name']}: {h['corpus']} for {', '.join(h['accounts']) or h['orgUnit'] or '?'}")
    return 0


def _generate_templates(args: argparse.Namespace, community: object) -> int:
    """``jason templates --generate``: plan the profile's template Docs against the bases; ``--yes`` writes them."""
    import json

    from jason.community.profile import profile_name
    from jason.config import Settings
    from jason.tasks import template_gen
    from jason.tasks.letters import document_text

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    profile = profile_name()
    state = template_gen.load_state(data_dir, profile)
    with _agent(args) as agent:
        drive = agent.drive()
        docs = drive.docs()
        ids = {str(e.get("docId")) for e in state.values() if e.get("docId")}
        ids |= {t.drive_id for t in community.document_templates() if t.drive_id}
        texts: dict[str, str | None] = {}
        for doc_id in sorted(ids):
            try:
                texts[doc_id] = document_text(docs.get(doc_id))
            except Exception:
                texts[doc_id] = None
        steps = template_gen.plan(community, state, texts)
        if args.json and not args.yes:
            print(json.dumps([{"kind": s.kind.slug, "action": s.action.value, "id": s.doc_id, "reason": s.reason} for s in steps],
                             indent=2))
        else:
            for step in steps:
                print(step.line())
        writes = [s for s in steps if s.action.writes]
        if not writes:
            return 0
        if not args.yes:
            print(f"--generate --yes writes {len(writes)} template Docs from the bases ({profile})")
            return 0
        home = community.drive_home()
        folder = home.templates or drive.child_folder(home.my_drive, "Templates") or drive.create_folder("Templates", home.my_drive)
        done = template_gen.generate(drive, docs, community, steps, state, folder_id=folder)
    path = template_gen.save_state(data_dir, profile, state)
    print(json.dumps(done, indent=2) if args.json else "\n".join(f"{d['action']:10} {d['kind']:16} {d['id']}" for d in done))
    print(f"recorded in {path}")
    return 0


def cmd_templates(args: argparse.Namespace) -> int:
    """The letter templates in the specification; with --build --yes, build the missing ones from the Letterhead."""
    import json

    from jason.community import community as active
    from jason.community.spec import spec_module

    from jason.community.profile import load_profile

    home, head = load_profile().drive_home(), load_profile().letterhead()

    community = active()
    rows = [{"kind": t.kind.slug, "title": t.title, "id": t.drive_id, "tokens": list(t.tokens), "optional": list(t.optional),
             "authority": t.authority} for t in community.document_templates()]
    if args.generate:
        return _generate_templates(args, community)
    if args.lint:
        from jason.community.template_values import lint

        found = [lint(t.kind.slug, t.tokens, community) for t in community.document_templates()]
        if args.json:
            print(json.dumps([f.as_dict() for f in found], indent=2))
            return 0
        for f in found:
            print(f"{f.template}:")
            print(f"  from the profile: {', '.join(f.profile) or '-'}")
            if f.general:
                print(f"  general wording (the profile cites no section): {', '.join(f.general)}")
            print(f"  left for the letter: {', '.join(f.run) or '-'}")
        return 0
    if args.rewrite:
        from jason.community.templates import TemplateKind
        from jason.tasks.letters import rewrite_template

        template = community.document_template(TemplateKind.from_slug(args.rewrite))
        if not args.yes:
            print(f"--rewrite replaces the body of {template.title} in Drive with the current text; add --yes to do it")
            return 2
        with _agent(args) as agent:
            print(json.dumps(rewrite_template(agent.docs(), template)))
        return 0
    if args.build:
        missing = [t for t in community.document_templates() if not t.drive_id]
        if not missing:
            print("every template has a Drive id")
            return 0
        if not args.yes:
            print(f"--build creates {len(missing)} Docs in My Drive/Templates; add --yes to do it")
            return 2
        from jason.tasks.letters import build_template

        with _agent(args) as agent:
            drive = agent.drive()
            folder = home.templates or drive.child_folder(home.my_drive, "Templates") or drive.create_folder("Templates", home.my_drive)
            print(f"Templates folder: {folder}")
            for t in missing:
                print(json.dumps(build_template(drive, drive.docs(), t, letterhead_id=head.doc_id, folder_id=folder,
                                                footer=head.footer)))
        print("record these ids in the profile's document templates")
        return 0
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        for r in rows:
            print(f"- {r['kind']}: {r['title']} ({r['id'] or 'not built'}) {r['authority']}")
            print("    tokens: " + ", ".join("{" + t + "}" for t in r["tokens"]))
    return 0


def _markdown_letter(args: argparse.Namespace) -> int:
    """A Markdown file (a guide, a notice) set on the letterhead as a Doc: a copy of the Letterhead the first time,
    rewritten in place after that (its id kept in the file's folder, docs.json). Pictures are put in from short-lived
    PayHOA upload links; Docs keeps its own copies."""
    from pathlib import Path

    from jason.community import community as active
    from jason.community.spec import spec_module
    from jason.google.docs_markdown import Kind, parse
    from jason.tasks import draft_docs

    source = Path(args.markdown).resolve()
    if not source.is_file():
        print(f"no file {source}")
        return 2
    markdown = source.read_text(encoding="utf-8")
    paras = parse(markdown)
    heading = next((p.text for p in paras if p.kind is Kind.HEADING), "")
    name = args.name or heading or source.stem
    missing = [p.picture for p in paras if p.picture and not (source.parent / p.picture).is_file()]
    if missing:
        print(f"pictures not found beside {source.name}: {', '.join(missing)}")
        return 2
    state = draft_docs.load_state(source.parent)
    entry = state.get(source.name) or {}
    from jason.community.profile import load_profile

    home, head = load_profile().drive_home(), load_profile().letterhead()
    folder = args.folder or home.templates
    if not args.yes:
        print(f"would {'rewrite' if entry.get('docId') else 'make'} {name!r} on the letterhead from {source.name}"
              f" ({sum(1 for p in paras if p.picture)} pictures); add --yes to do it")
        return 0
    with _agent(args) as agent:
        client = agent.payhoa()
        made = draft_docs.push_markdown(
            agent.drive(), source, name=name, folder=folder, letterhead_id=head.doc_id, footer=head.footer,
            state=state, style=args.style, pdf=Path(args.pdf) if args.pdf else None,
            articles=active().help_articles(),
            picture_link=lambda path: client.upload_file(path, filename=path.name, content_type="image/png",
                                                         context="communication")["viewUrl"])
    draft_docs.save_state(source.parent, state)
    print(f"{'made' if made['created'] else 'rewrote'} {name}: {made['url']}" + (f"; PDF {made['pdf']}" if made.get("pdf") else ""))
    return 0


def cmd_letter(args: argparse.Namespace) -> int:
    """Fill a copy of a letter template with --set KEY=value pairs, into --folder (or the template's folder)."""
    import json

    from jason.community import community as active
    from jason.community.templates import TemplateKind
    from jason.community.template_values import profile_values
    from jason.tasks.letters import fill_letter, parse_assignments

    if args.markdown:
        return _markdown_letter(args)
    if not args.template:
        print("give --template (letterhead, hearing-notice, decision-notice) or --markdown FILE")
        return 2
    community = active()
    try:
        from jason.community.profile import profile_name
        from jason.config import Settings
        from jason.tasks.template_gen import template_for

        template = template_for(community, TemplateKind.from_slug(args.template),
                                Settings.load(getattr(args, 'env', None)).payhoa_catalog.parent, profile_name())
        values = parse_assignments(args.set or [])
    except ValueError as exc:
        print(f"error: {exc}")
        return 2
    folder = args.folder or template.folder_id
    if not folder or not args.name:
        print("give --name for the new Doc, and --folder when the template has no folder of its own")
        return 2
    if not args.yes:
        print(f"would copy {template.title} to {args.name!r} in folder {folder} and fill {sorted(values)}; add --yes to do it")
        return 2
    with _agent(args) as agent:
        drive = agent.drive()
        letter = fill_letter(drive, drive.docs(), template, values, name=args.name, folder_id=folder,
                             defaults=profile_values(active()))
    print(json.dumps(letter, indent=2))
    return 0


def cmd_insurance(args: argparse.Namespace) -> int:
    """Each policy's term against the carriers' letters and the premiums PayHOA paid; renewals, notices, and claims."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.insurance import review, review_lines

    result = review(Settings.load(args.env).payhoa_catalog.parent, active())
    if args.policy:
        result = {**result, "policies": [p for p in result["policies"] if policy_matches(p, args.policy)]}
        if not result["policies"]:
            print(f"no policy matches {args.policy!r}", file=sys.stderr)
            return 1
    if args.claims:
        result = {**result, "policies": [], "unplacedFloodPayments": []}
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for line in review_lines(result):
            print(line)
    return 0 if result.get("found") else 1


def policy_matches(policy: dict, wanted: str) -> bool:
    """A policy row by kind ("master", "umbrella", "d&o"), by building ("flood-2", "flood 2"), or by number (current or
    prior, any part of it)."""
    import re

    text = wanted.strip().lower().replace("_", " ").replace("-", " ")
    kind = str(policy.get("kind") or "").lower().replace("_", " ")
    aliases = {"d&o": "directors and officers", "do": "directors and officers", "crime": "fidelity", "wc": "workers comp"}
    text = aliases.get(text, text)
    numbers = [str(n).lower() for n in (policy.get("number"), *(policy.get("priorNumbers") or [])) if n]
    flood = re.fullmatch(r"flood\s*(?:building\s*)?(\d+)", text)
    if flood:
        return kind == "flood" and str(policy.get("building")) == flood.group(1)
    return text == kind or (text in kind and len(text) >= 4) or any(text.replace(" ", "") in n.replace("-", "") for n in numbers)


def cmd_deadlines(args: argparse.Namespace) -> int:
    """The association's recurring deadlines: next due, last done, and past deadlines done late or with no evidence."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.deadlines import calendar, calendar_lines

    result = calendar(Settings.load(args.env).payhoa_catalog.parent, active())
    rows = result["obligations"]
    if args.overdue:
        rows = [r for r in rows if r["standing"] == "overdue"]
    if args.within is not None:
        rows = [r for r in rows if r["daysLeft"] is not None and r["daysLeft"] <= args.within]
    if args.name:
        rows = [r for r in rows if args.name.lower() in r["name"].lower()]
    result = {**result, "obligations": rows}
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for line in calendar_lines(result):
            print(line)
    return 0 if result.get("found") else 1


def cmd_gmail(args: argparse.Namespace) -> int:
    """Read the association's Gmail (headers only): PostScanMail's notices against the synced mail, and correspondence."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.gmail import CORRESPONDENCE, _load, check_lines, notice_check, sync

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    if args.file_vendor:
        return _file_vendor_email(args, data_dir)
    if args.filters_xml:
        from jason.community import community
        from jason.tasks.vendor_files import filters_xml

        xml, skipped = filters_xml(community(), data_dir)
        out = Path(args.filters_xml)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(xml, encoding="utf-8")
        print(f"wrote {out} ({xml.count('<entry>')} filters); import it in Gmail: Settings, Filters and Blocked Addresses, "
              "Import filters")
        if skipped:
            print(f"no known address, so no filter: {', '.join(skipped)}")
        return 0
    if args.sync:
        with _agent(args) as agent:
            counts = sync(agent.gmail(), data_dir, active(), days=args.days, log=print)
        print(f"synced {counts}")
    if args.files:
        from jason.tasks.gmail import fetch_documents

        with _agent(args) as agent:
            print(f"attachments {fetch_documents(agent.gmail(), data_dir, active(), log=print)}")
    check = notice_check(data_dir)
    corr = _load(data_dir, CORRESPONDENCE)
    if args.json:
        print(json.dumps({"notices": check, "correspondence": {k: v for k, v in corr.items() if k != "messages"}}, indent=2, default=str))
    else:
        for line in check_lines(check, corr):
            print(line)
    return 0 if check.get("found") else 1


def _file_vendor_email(args: argparse.Namespace, data_dir: Path) -> int:
    """File vendors' email attachments in Drive (jason.tasks.vendor_files): the plan, then the uploads with --yes."""
    import json

    from jason.community import community
    from jason.tasks.vendor_files import drive_index, file_plan, hold, plan_lines, plan_vendor, vendors

    profile = community()
    if profile.email_filing() is None:
        print("the specification sets no email filing (Community.email_filing)")
        return 1
    rows = vendors(profile, args.file_vendor)
    if not rows:
        print(f"no vendor {args.file_vendor!r} in the sender directory")
        return 1
    if args.via_gmail:
        return _file_vendor_via_gmail(args, data_dir, profile, rows)
    known, _ = drive_index(data_dir)
    seen: set[str] = set()
    out = []
    with _agent(args) as agent:
        drive = agent.drive(interactive=args.interactive)
        gmail = drive.gmail()
        for sender in rows:
            plan, blobs = plan_vendor(gmail, drive, profile, sender, known=known, seen=seen, data_dir=data_dir)
            hold(plan, blobs, tuple(args.hold or ()))
            if args.json:
                out.append({"vendor": plan.vendor, "query": plan.query, "messages": plan.messages,
                            "attachments": [a.__dict__ for a in plan.attachments]})
            else:
                for line in plan_lines(plan, why=getattr(args, "why", False)):
                    print(line)
            if args.yes and blobs:
                print(f"{plan.vendor}: filed {file_plan(drive, profile, plan, blobs, data_dir, log=print)}")
    if args.json:
        print(json.dumps(out, indent=1, default=str))
    if not args.yes:
        print("(plan only: --yes uploads the ones marked file)")
    return 0


def _file_vendor_via_gmail(args: argparse.Namespace, data_dir: Path, profile, rows) -> int:
    """Gmail's own Save to Drive: list what a person saves (data/gmail/save-to-drive.md), and with --yes move the copies
    they saved into their folders. Reads Gmail's metadata only; downloads and uploads nothing."""
    from jason.tasks.vendor_files import adopt_plan, plan_lines, plan_saves, save_list

    plans = []
    with _agent(args) as agent:
        drive = agent.drive(interactive=args.interactive)
        gmail = drive.gmail()
        for sender in rows:
            plan = plan_saves(gmail, drive, profile, sender, data_dir=data_dir)
            plans.append(plan)
            for line in plan_lines(plan, why=getattr(args, "why", False)):
                print(line)
            if args.yes and any(a.action == "adopt" for a in plan.attachments):
                print(f"{plan.vendor}: moved {adopt_plan(drive, profile, plan, data_dir, log=print)}")
    path = data_dir / "gmail" / "save-to-drive.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(save_list(plans), encoding="utf-8")
    waiting = sum(1 for p in plans for a in p.attachments if a.action == "save")
    print(f"{waiting} to save with Gmail's Add to Drive: {path}")
    if not args.yes:
        print("(plan only: --yes moves the saved copies marked adopt into their folders)")
    return 0


def cmd_contacts(args: argparse.Namespace) -> int:
    """Vendor contacts: PayHOA's vendor directory against who writes from each vendor in Gmail, with what to update."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.contacts import directory, directory_lines, fetch

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    if args.fetch:
        with _agent(args) as agent:
            print(f"saved {fetch(agent.payhoa(), agent.org_id, data_dir)}")
    result = directory(data_dir, active())
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for line in directory_lines(result):
            print(line)
    return 0 if result.get("found") else 1


def cmd_copies(args: argparse.Namespace) -> int:
    """Every copy of every invoice and bill (portal, email, PayHOA, paper) grouped into documents, the best copy, and the payment."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.copies import catalog, catalog_lines
    from jason.tasks.utilities import bill_roots

    settings = Settings.load(args.env)
    result = catalog(settings.payhoa_catalog.parent, active(), bill_roots(settings), log=None if args.json else print)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for line in catalog_lines(result, limit=args.limit, issuer=args.issuer, sections=set(args.section or ()),
                                  since=args.since or "", only_unexplained=args.unexplained):
            print(line)
    return 0 if result.get("found") else 1


def cmd_drive(args: argparse.Namespace) -> int:
    """Where each association record is in Drive, by the path rules and by content; duplicates and versions."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.drive_catalog import holdings, holdings_lines, sync

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    if args.sync:
        with _agent(args) as agent:
            print(f"synced {sync(agent.drive(), data_dir, log=print)}")
    result = holdings(data_dir, active(), log=print)
    if args.gmail:
        from jason.tasks.drive_gmail import link, link_lines

        with _agent(args) as agent:
            links = link(agent.gmail(), data_dir, everything=args.all_files, log=print)
        for line in link_lines(links):
            print(line)
        return 0
    if args.json:
        print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2, default=str))
    else:
        for line in holdings_lines(result, record=args.record):
            print(line)
    return 0 if result.get("found") else 1


def cmd_threads(args: argparse.Namespace) -> int:
    """Email threads as work: whose move it is, with the payments, letters, documents, Drive copies, and unit activity near each."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.threads import thread_lines, threads

    result = threads(Settings.load(args.env).payhoa_catalog.parent, active())
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for line in thread_lines(result, status=args.status, days=args.days, limit=args.limit, party=args.party):
            print(line)
    return 0 if result.get("found") else 1


def cmd_party(args: argparse.Namespace) -> int:
    """One unit or counterparty across every store: owners, PayHOA, requests, threads, letters, payments, documents, contacts."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.party import party_brief, party_lines

    brief = party_brief(args.query, Settings.load(args.env).payhoa_catalog.parent, active())
    if args.json:
        print(json.dumps(brief, indent=2, default=str))
    else:
        for line in party_lines(brief):
            print(line)
    return 0 if brief.get("found") else 1


def cmd_topics(args: argparse.Namespace) -> int:
    """What the association hears about, by topic: threads, units, recent and open, and the FAQ candidates."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.party import thread_topics

    result = thread_topics(Settings.load(args.env).payhoa_catalog.parent, active())
    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0
    print(f"Topics as of {result['asOf']} ({result['threadsWithoutTopic']} open threads carry none)")
    for e in result["topics"]:
        faq = "  FAQ candidate" if e["faqCandidate"] else ""
        print(f"  {e['topic']}: {e['inYear']} threads this year from {len(e['unitsInYear'])} units, {e['last90Days']} in 90 days, "
              f"{e['awaitingUs']} awaiting us{faq}")
        for x in e["examples"][:args.examples]:
            print(f"      {x['last']} [{x['status']}] {x['who'][:30]}: {x['subject'][:60]}")
    for c in result["caveats"]:
        print(f"* {c}")
    return 0


def cmd_new_owners(args: argparse.Namespace) -> int:
    """Units conveyed in the window: the buyer's threads and topics, PayHOA link, balance, and requests."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.party import new_owners

    result = new_owners(Settings.load(args.env).payhoa_catalog.parent, active(), days=args.days)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0
    print(f"New owners in the last {result['days']} days")
    for o in result["owners"]:
        linked = "in PayHOA" if o["memberInPayhoa"] else "NOT linked in PayHOA"
        topics = ", ".join(f"{k} {n}" for k, n in list(o["topics"].items())[:4])
        print(f"  {o['unit']}: deed {o['deedRecorded']} ({o['daysOwned']} days); {linked}; {o['threads']} threads, {o['awaitingUs']} awaiting us"
              + (f"; {topics}" if topics else ""))
        for r in o["requests"]:
            print(f"      request {r['created']} {r['form']} ({r['status']})")
    for c in result["caveats"]:
        print(f"* {c}")
    return 0


def cmd_open_items(args: argparse.Namespace) -> int:
    """What is waiting on the association across email, PayHOA, deadlines, insurance, and the mail."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.party import open_items, open_lines

    result = open_items(Settings.load(args.env).payhoa_catalog.parent, active(), days=args.days)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for line in open_lines(result):
            print(line)
    return 0


def cmd_request_links(args: argparse.Namespace) -> int:
    """PayHOA requests beside the email about them; drafts for emailed requests PayHOA lacks; enter one only when named."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.request_links import create, link_lines, request_links

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    result = request_links(data_dir, active())
    if args.create:
        draft = next((d for d in result["drafts"] if d["threadId"] == args.create), None)
        if draft is None:
            print(f"no draft for thread {args.create}")
            return 1
        print(json.dumps({**draft, "message": args.message or draft["message"]}, indent=2))
        if not args.yes:
            print("Not entered: read the thread, then run again with --yes (and --message with the owner's request in full).")
            return 1
        with _agent(args) as agent:
            ids = create(agent.payhoa(), agent.org_id, active(), draft, message=args.message, notify_owner=args.notify_owner)
        print(f"entered as PayHOA request {ids}")
        return 0
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for line in link_lines(result, limit=args.limit):
            print(line)
    return 0 if result.get("found") else 1


def cmd_inbox(args: argparse.Namespace) -> int:
    """What each email asks (complaint, maintenance, information, billing, question) and where the answer is likely written."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.intents import email_intents, intent_lines

    result = email_intents(Settings.load(args.env).payhoa_catalog.parent, active(), days=args.days)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for line in intent_lines(result, intent=args.intent, limit=args.limit):
            print(line)
    return 0 if result.get("found") else 1


def cmd_case(args: argparse.Namespace) -> int:
    """One matter across the stores by its words: threads, violations, requests, letters, Drive files, library documents."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.intents import case_file

    result = case_file(args.terms, Settings.load(args.env).payhoa_catalog.parent, active())
    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("found") else 1
    print("Case file: " + ", ".join(f"{k} {n}" for k, n in result["counts"].items()))
    for e in result["events"]:
        print(f"  {e['date'] or '-':10} {e['what']:16} {str(e['who'] or '')[:32]:32} {str(e['title'])[:70]} ({e['status']})")
    for c in result["caveats"]:
        print(f"* {c}")
    return 0 if result.get("found") else 1


def cmd_replies(args: argparse.Namespace) -> int:
    """Which email the association answers, learned from its replies, and the open threads that likely need one."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.replies import reply_lines, reply_needed

    result = reply_needed(Settings.load(args.env).payhoa_catalog.parent, active(), open_days=args.days)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for line in reply_lines(result, limit=args.limit):
            print(line)
    return 0 if result.get("found") else 1


def cmd_permit_status(args: argparse.Namespace) -> int:
    """The association's building permits from the City's Accela portal: status, fees due and paid, workflow, conditions."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.permits import permit_lines, permits, sync

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    if args.sync:
        with _agent(args) as agent:
            client = agent.citizen_access()
            community = active()
            print(f"synced {sync(client, data_dir, community.permit_portal(), community.closed_permit_statuses(), everything=args.all, log=print)}")
    result = permits(data_dir, number=args.number)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for line in permit_lines(result):
            print(line)
    return 0 if result.get("found") else 1


def cmd_sources(args: argparse.Namespace) -> int:
    """The association's counterparties from disk: who writes, who is paid, what kind of source each is, and what is unnamed."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.sources import report_lines, sources_report

    report = sources_report(Settings.load(args.env).payhoa_catalog.parent, active())
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        for line in report_lines(report):
            print(line)
    return 0


def cmd_books(args: argparse.Namespace) -> int:
    """The books from PayHOA's general ledger: sync month by month, then report or query locally."""
    import json
    from datetime import date

    from jason.config import Settings
    from jason.tasks.books import books_report, fetch_profit_loss, report_lines, sync

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    if args.sync or args.full:
        with _agent(args) as agent:
            counts = sync(agent.payhoa(), agent.org_id, data_dir, full=args.full, log=print)
            this_year = date.today().year
            for year in range(2024 if args.full else this_year, this_year + 1):
                print(f"profit and loss {year}: {fetch_profit_loss(agent.payhoa(), agent.org_id, data_dir, year)}")
        print(f"synced {counts}")
    cents = lambda value: None if value is None else round(value * 100)
    result = books_report(
        data_dir, args.report, start=date.fromisoformat(args.start) if args.start else None,
        end=date.fromisoformat(args.end) if args.end else None, kind=args.kind, text=args.text, payee=args.payee,
        category=args.category, account=args.account, minimum=cents(args.min), maximum=cents(args.max), owners=args.owners, limit=args.limit,
    )
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for line in report_lines(result):
            print(line)
    return 0 if result.get("found") else 1


def cmd_cases(args: argparse.Namespace) -> int:
    """The association's legal matters: forum, role, status, events, money, and each statutory duty's standing."""
    import json

    from jason.community import community as active
    from jason.community.document_models import to_plain
    from jason.community.legal_cases import settled_lines

    cases = active().legal_cases()
    if args.fetch_files or args.extract_text:
        from jason.tasks.case_files import catalog_name, extract_text, fetch, vision_reader

        chosen = [c for c in cases if c.drive_folder and (not args.case or args.case.lower() in (c.key, (c.case_number or "").lower()))]
        if not chosen:
            print("no case with a Drive folder matches", file=sys.stderr)
            return 1
        vision = None
        if args.extract_text and args.vision:           # a person asked: the preflight first, and fail fast
            from jason.local_ai import LocalAIUnavailable

            try:
                vision = vision_reader()
            except LocalAIUnavailable as exc:
                print(f"--vision: {exc}", file=sys.stderr)
                return 1

        def text_and_catalog(data_dir, c) -> None:
            for line in extract_text(data_dir, c, vision=vision, log=print).lines():
                print(f"  {line}")
            print(f"  catalog {catalog_name(c)} (confidential): jason index --build, then "
                  f"jason index --search QUESTION --catalog {catalog_name(c)} --confidential")

        if not args.fetch_files:
            from jason.config import data_dir as active_data_dir

            for c in chosen:
                print(f"{c.case_number or c.key}: {catalog_name(c)}")
                text_and_catalog(active_data_dir(getattr(args, "env", None)), c)
            return 0
        with _agent(args) as agent:
            data_dir = agent.settings.ownership_db.parent
            for c in chosen:
                print(f"{c.case_number or c.key}: My Drive/{c.drive_folder}")
                counts = fetch(agent.drive(), data_dir, c, include_held=args.include_held, log=print)
                print(f"  {counts}")
                text_and_catalog(data_dir, c)
        return 0
    if args.json:
        print(json.dumps([to_plain(c) for c in cases], indent=2))
        return 0
    for c in cases:
        number = f" {c.case_number}" if c.case_number else ""
        print(f"{c.title} [{c.status.value}; {c.role.value}; {c.forum.value}{number}]")
        if c.opposing:
            print(f"    against: {'; '.join(c.opposing)}")
        if c.counsel:
            print(f"    counsel: {'; '.join(c.counsel)}")
        for e in c.events[-3:]:
            print(f"    {e.day} {e.step}")
        if c.net_cents is not None:
            print(f"    gross ${(c.gross_cents or 0) / 100:,.2f}, net ${c.net_cents / 100:,.2f} to {c.proceeds_account}")
        for d in c.open_duties:
            state = "not met" if d.met is False else "not shown"
            print(f"    ! {d.statute}: {d.requirement} ({state}: {d.evidence})")
        for line in settled_lines(c):
            print(f"    - {line}")
    return 0


def cmd_google_features(args: argparse.Namespace) -> int:
    """Whether the Docs API features jason waits on (suggested edits, anchored comments) have left Developer Preview."""
    import json

    from jason.google.discovery import feature_status, fetch

    result = feature_status(fetch())
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Docs API discovery revision {result['revision']}")
        for name, f in result["features"].items():
            print(f"  {name}: {f['status']}  ({f['what']})")
    return 0


def _board_notice(args: argparse.Namespace, data_dir) -> int:
    """``jason board --notice``: the notice of a board meeting from the base template, for a person to review and send.
    Writes data/board/notices/notice-<date>.md (the source), .html (the email body on the letterhead), and .refs.json; reads
    disk only and sends nothing (jason.tasks.meeting_notice)."""
    from datetime import date

    from jason.community import community as active
    from jason.tasks import agenda_plan, meeting_notice
    from jason.tasks.board_items import load

    community = active()
    schedule = community.meeting_schedule()
    day = date.fromisoformat(args.date) if args.date else schedule.next_meeting(date.today(), monthly=True)
    plan = agenda_plan.load(data_dir, day.isoformat())
    try:
        meeting = meeting_notice.from_plan(day, plan, schedule, fmt=args.format or None, location=args.location,
                                           tech_contact=args.tech_contact, ballots_counted=args.ballots_counted,
                                           notice_date=date.fromisoformat(args.notice_date) if args.notice_date else None)
        notice = meeting_notice.render(community, meeting, load(data_dir), data_dir, plan_items=plan["items"])
    except meeting_notice.NoticeRefused as exc:
        print(f"no notice drawn: {exc}", file=sys.stderr)
        return 2
    paths = meeting_notice.write(data_dir, notice, community.email_letterhead())
    print(f"wrote {paths['markdown']} ({meeting.format.value}), its email body {paths['html'].name}, and "
          f"{paths['refs'].name}; nothing sent")
    for line in notice.review:
        print(f"  check: {line}")
    short = f"{day.month}/{day.day}/{day.year % 100:02d}"
    print("next, each a person's step:")
    print(f"  the Doc on the letterhead and its PDF: jason letter --markdown {paths['markdown']} "
          f"--name \"Notice of Board Meeting {short}\" --pdf {paths['markdown'].with_suffix('.pdf')} --yes")
    print(f"  the email, sent in PayHOA: jason broadcast {paths['markdown']} --letterhead --notice {notice.key}; it reaches "
          "the members whose delivery choice is email (CIV 4041), and general delivery is the posting (4045(a))")
    return 1 if notice.misses else 0


def _board_members_copy(args: argparse.Namespace, data_dir, meeting) -> int:
    """``jason board --packet --audience members``: the members' copy of the packet, data/board/packet-<date>-members.md,
    with what it leaves out listed by item. With ``--by NAME`` it goes to the approvals store and approval is requested
    from the officer the specification names; without, only the draft is written. jason never posts or sends it."""
    from jason.community import community as active
    from jason.tasks.board_packet import members_copy, request_members_copy

    if args.doc:
        print("--doc writes the directors' confidential packet; the members' copy goes to its approver first "
              "(--by NAME), and a person posts it once approved", file=sys.stderr)
        return 2
    community = active()
    copy = members_copy(data_dir, community, meeting)
    out = data_dir / "board" / f"packet-{meeting.isoformat()}-members.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(copy.lines), encoding="utf-8")
    print(f"wrote {out} (the members' copy; a draft, nothing posted)")
    print("\n".join(copy.withheld_lines()) or "- nothing left out")
    who = f"{copy.approver} ({', '.join(copy.approver_names) or 'no one on the roster holds it'})" if copy.approver else ""
    if not args.by:
        print(f"approval not requested: add --by NAME to ask {copy.approver or 'its approver'}" +
              ("" if copy.approver else " (the specification names none: Community.document_approvers)"))
        return 0
    try:
        letter = request_members_copy(data_dir, community, copy, out, by=args.by)
    except ValueError as exc:
        print(f"approval not requested: {exc}", file=sys.stderr)
        return 1
    print(f"approvals {letter['key']}: {letter['stage']}, from {who}; a person posts it once approved (jason approvals inbox)")
    return 0


def cmd_board(args: argparse.Namespace) -> int:
    """The board's action items: list or change them, draft the next agenda and minutes, sync the board's Sheet."""
    import json
    from datetime import date

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.board_items import TAB, create_sheet, list_lines, load, set_fields, sync_sheet, sync_tasks, to_rows
    from jason.tasks.meeting_agenda import draft, minutes_template, read_doc

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    if args.set:
        changes = {k: v for k, v in (("status", args.status), ("owner", args.owner), ("meeting", args.meeting), ("notes", args.notes)) if v}
        item = set_fields(data_dir, args.set, **changes)
        print(f"{item.id}: {item.status.value}; owner {item.owner or '-'}; meeting {item.meeting or '-'}")
        return 0
    if args.create_sheet:
        with _agent(args) as agent:
            print(f"created {create_sheet(agent.sheets())}; save the id and pass --sheet to sync")
        return 0
    if args.sheet:
        sheet_id = active().board_items_sheet() if args.sheet == "spec" else args.sheet
        if not sheet_id:
            print("no board Sheet in the specification; pass its id or run --create-sheet", file=sys.stderr)
            return 1
        with _agent(args) as agent:
            print(f"synced {sync_sheet(agent.sheets(), sheet_id, data_dir)}")
            if args.tasks:
                with agent.google_tasks() as tasks:
                    print(f"tasks {sync_tasks(tasks, data_dir, sheet_id=sheet_id)}")
                # A task checked off closes its item; write the Sheet again so it shows that.
                agent.sheets().values_update(sheet_id, f"{TAB}!A1", to_rows(load(data_dir)))
    elif args.tasks:
        with _agent(args) as agent, agent.google_tasks() as tasks:
            print(f"tasks {sync_tasks(tasks, data_dir, sheet_id=active().board_items_sheet())}")
    if args.packet:
        from jason.tasks.board_packet import packet

        if args.refresh_reports:            # each report the items name, run now; otherwise the packet shows their last runs
            from jason.commands.report import named_reports
            from jason.tasks.live_reports import refresh

            on = date.fromisoformat(args.date) if args.date else active().meeting_schedule().next_meeting(date.today(), monthly=True)
            for key, params in named_reports(data_dir):
                snap = refresh(key, data_dir, active(), params, context={"on": on})
                print(f"report {key}: " + (f"could not run ({snap.error})" if snap.error else f"ran {snap.ran_at}"))

        schedule = active().meeting_schedule()
        meeting = date.fromisoformat(args.date) if args.date else schedule.next_meeting(date.today(), monthly=True)
        if args.audience == "members":
            return _board_members_copy(args, data_dir, meeting)
        out = data_dir / "board" / f"packet-{meeting.isoformat()}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = packet(data_dir, active(), meeting)
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"wrote {out}")
        if args.doc:
            if not args.yes:
                print("--doc writes the packet to a private Google Doc in My Drive/Meetings/<year>; add --yes to do it")
                return 2
            from jason.tasks.letters import markdown_doc
            from jason.community.spec import spec_module

            from jason.community.profile import load_profile

            home, head = load_profile().drive_home(), load_profile().letterhead()

            docs_file = data_dir / "board" / "docs.json"
            known = json.loads(docs_file.read_text(encoding="utf-8")) if docs_file.is_file() else {}
            key = f"packet-{meeting.isoformat()}"
            short = f"{meeting.month}/{meeting.day}/{meeting.year % 100:02d}"
            with _agent(args) as agent:
                drive = agent.drive()
                year = drive.child_folder(home.meetings, str(meeting.year)) or drive.create_folder(str(meeting.year), home.meetings)
                made = markdown_doc(drive, drive.docs(), lines, name=f"Board Packet for {short} (confidential)", folder_id=year,
                                    letterhead_id=head.doc_id, footer=head.footer, doc_id=known.get(key, ""),
                                    continuation=f"Board packet for {meeting:%B} {meeting.day}, {meeting.year} · Confidential: "
                                                 "for the directors and counsel")
            known[key] = made["id"]
            docs_file.write_text(json.dumps(known, indent=2), encoding="utf-8")
            print(f"{'created' if made['created'] else 'updated'} {made['url']}")
        return 0
    if args.members:
        from jason.tasks.board_members import sync as sync_members

        with _agent(args) as agent:
            result = sync_members(agent.payhoa(), agent.org_id, data_dir)
        for bucket, label in (("current", "Board Member"), ("former", "Board Member, archived")):
            for m in result[bucket]:
                print(f"{label}: {m['name'] or m['email']}" + (" (PayHOA admin)" if m["admin"] else "") +
                      (f", last login {m['lastLogin']}" if m["lastLogin"] else ""))
        return 0
    if args.minutes:
        from jason.tasks.minutes_draft import check_lines, recheck
        from jason.tasks.minutes_draft import draft as draft_minutes

        if args.recheck:
            found = recheck(data_dir, active(), date.fromisoformat(args.minutes))
            print(f"checked {found['file']} (DRAFT; nothing posted)")
            print("\n".join(check_lines(found)[2:]).rstrip())
            return 0
        result = draft_minutes(data_dir, active(), date.fromisoformat(args.minutes))
        print(f"wrote {result['file']} (DRAFT; nothing posted)")
        print("\n".join(check_lines(result["checks"])[2:]).rstrip())
        print(f"  {result['unknowns']} blanks for the Secretary; the draft's own check still lacks: {', '.join(result['gaps']) or 'nothing'}")
        if result["unsupported"]:
            print(f"  sections whose quotes are not in the transcript (check them): {', '.join(result['unsupported'])}")
        return 0
    if args.notice:
        return _board_notice(args, data_dir)
    if args.agenda:
        schedule = active().meeting_schedule()
        meeting = date.fromisoformat(args.date) if args.date else schedule.next_meeting(date.today(), monthly=True)
        # The meeting's format: a person's --format, else the agenda plan saved for the date (data/meetings/plan-<date>.json);
        # with neither, the draft assumes a meeting held entirely by teleconference and says so.
        from jason.tasks import agenda_plan
        from jason.tasks.agenda_plan import MeetingFormat, meeting_format

        plan = agenda_plan.load(data_dir, meeting.isoformat())
        basics = plan["basics"]
        # Each executive matter's Civil Code 4935 subject, as a person set it in the plan: the open agenda names it by that.
        subjects = {k: v.get("subject") for k, v in plan["items"].items() if isinstance(v, dict) and v.get("subject")}
        fmt, fmt_source = (meeting_format(args.format), "--format") if args.format else (
            meeting_format(basics.get("format")), f"the agenda plan for {meeting.isoformat()}")
        if args.doc and fmt not in (None, MeetingFormat.TELECONFERENCE):
            print(f"--doc fills the agenda template, which carries 4926's lines for a meeting held entirely by teleconference; this "
                  f"meeting is {fmt.value}. Use the Markdown draft for its notice.", file=sys.stderr)
            return 2
        with _agent(args) as agent:
            previous = read_doc(agent.docs(), args.agenda)
        before = date.fromisoformat(args.previous) if args.previous else None
        # The individual-delivery reminder recites 4045(b) and 4041(a)(1) from the statutes on disk, as the notice does.
        from jason.tasks.meeting_notice import delivery_recitals, delivery_request
        from jason.tasks.meeting_agenda import delivery_section

        request = delivery_request(active().identity())
        lines = draft(previous, load(data_dir), meeting, schedule, tech_contact=args.tech_contact or basics.get("help", ""),
                      previous_meeting=before, meeting_format=fmt, format_source=fmt_source if fmt else "",
                      location=basics.get("location", ""), subjects=subjects, data_dir=data_dir,
                      delivery_request=request)
        if fmt in (None, MeetingFormat.TELECONFERENCE):
            for r in delivery_recitals(data_dir):
                if not r.found:
                    print(f"{r.label} is not on disk ({r.reason}): the agenda shows the miss; run jason "
                          "export-authorities, then draft again.", file=sys.stderr)
        out = data_dir / "board" / f"agenda-{meeting.isoformat()}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines), encoding="utf-8")
        board = active().board()
        directors = [d.strip() for d in args.directors.split(",") if d.strip()] or [f"Director {n}" for n in range(1, board.seats + 1)]
        minutes = minutes_template(meeting, directors, lines, quorum=board.quorum(len(directors)), quorum_source=board.quorum_source,
                                   roll_call=fmt in (None, MeetingFormat.TELECONFERENCE))
        (data_dir / "board" / f"minutes-template-{meeting.isoformat()}.md").write_text("\n".join(minutes), encoding="utf-8")
        print(f"wrote {out} and its minutes template")
        if args.doc:
            if not args.yes:
                print("--doc fills the agenda template into a new Google Doc; add --yes to do it")
                return 2
            from jason.community.templates import TemplateKind
            from jason.community.template_values import profile_values
            from jason.tasks.letters import fill_with_markdown
            from jason.tasks.meeting_agenda import agenda_items, agenda_values
            from jason.community.spec import spec_module

            from jason.community.profile import load_profile

            home, head = load_profile().drive_home(), load_profile().letterhead()

            from jason.community.profile import profile_name
            from jason.tasks.template_gen import template_for

            template = template_for(active(), TemplateKind.AGENDA, data_dir, profile_name())
            body = agenda_items(previous, load(data_dir), meeting, schedule, previous_meeting=before, subjects=subjects)
            body += delivery_section(data_dir, request)      # the template's note points here (4926(a)(1)(C))
            values = agenda_values(previous, meeting, schedule, tech_contact=args.tech_contact)
            short = f"{meeting.month}/{meeting.day}/{meeting.year % 100:02d}"
            docs_file = data_dir / "board" / "docs.json"
            known = json.loads(docs_file.read_text(encoding="utf-8")) if docs_file.is_file() else {}
            key = f"agenda{'-preview' if args.preview else ''}-{meeting.isoformat()}"
            with _agent(args) as agent:
                drive = agent.drive()
                if args.preview:
                    folder, name = home.templates, f"Preview - Agenda for {short}"
                else:
                    folder = drive.child_folder(home.meetings, str(meeting.year)) or drive.create_folder(str(meeting.year), home.meetings)
                    name = f"DRAFT Agenda for {short}"
                made = fill_with_markdown(drive, drive.docs(), template, values, body, name=name, folder_id=folder,
                                          defaults=profile_values(active()),
                                          doc_id=known.get(key, ""))
            known[key] = made["id"]
            docs_file.write_text(json.dumps(known, indent=2), encoding="utf-8")
            print(json.dumps(made))
        return 0
    items = load(data_dir)
    if args.json:
        from jason.tasks.board_items import _encode

        print(json.dumps([_encode(i) for i in items], indent=2))
    else:
        for line in list_lines(items, every=args.all):
            print(line)
    return 0


def cmd_cost_centers(args: argparse.Namespace) -> int:
    """Whether the association keeps the two assessment cost centers its annexations require (disk only)."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.cost_centers import review, review_lines

    result = review(Settings.load(args.env).payhoa_catalog.parent, active())
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for line in review_lines(result):
            print(line)
    return 0 if result.get("found") else 1


def cmd_securities(args: argparse.Namespace) -> int:
    """The subdivider's DRE securities by phase: agreements, bonds, and releases (disk only)."""
    import json

    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.developer_security import register, register_lines

    result = register(Settings.load(args.env).payhoa_catalog.parent, active())
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for line in register_lines(result):
            print(line)
    return 0 if result.get("found") else 1


def cmd_models(args: argparse.Namespace) -> int:
    """Read the library (or one file) with the document models: typed records and findings per document kind."""
    import json

    from jason.community import community as active
    from jason.community.symbols import DocumentKind
    from jason.config import Settings
    from jason.tasks.document_models import basis_lines, basis_report, coverage_lines, load, read_file, run, summary

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    if args.basis:
        result = basis_report(load(data_dir), kind=args.kind)
        print(json.dumps(result, indent=2, default=str) if args.json else "\n".join(basis_lines(result)))
        return 0 if result["found"] else 1
    if args.as_of:
        from datetime import date

        from jason.community.reviews import LENSES
        from jason.tasks.document_reviews import review_lines, review_stored

        try:
            as_of = date.fromisoformat(args.as_of)
        except ValueError:
            print("--as-of needs a date as YYYY-MM-DD")
            return 2
        if args.lens not in LENSES:
            print(f"--lens is one of: {', '.join(LENSES)}")
            return 2
        result = review_stored(data_dir, active(), as_of, lens=LENSES[args.lens], kind=args.kind, include_confidential=args.confidential)
        print(json.dumps(result, indent=2, default=str) if args.json else "\n".join(review_lines(result)))
        return 0 if result["found"] else 1
    if args.ask:
        from jason.tasks.model_questions import run as ask_run, summary_lines as ask_lines

        if not args.kind:
            print("--ask needs --kind (a kind with a question set, e.g. minutes)")
            return 2
        result = ask_run(data_dir, active(), DocumentKind(args.kind), limit=args.limit if args.limit != 50 else 0, log=print)
        print("\n".join(ask_lines(result)))
        return 0
    if args.file:
        if not args.kind:
            print("--file needs --kind")
            return 2
        result = read_file(Path(args.file), DocumentKind(args.kind), active(), data_dir=data_dir)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("model") else 1
    if args.show:
        result = summary(data_dir, kind=args.kind, include_confidential=args.confidential, limit=args.limit)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("found") else 1
    if args.filed:
        from jason.tasks.document_models import filed_lines, run_filed

        vision = None
        if args.vision:                                  # only when a person asks: the preflight first, then the GPU lock
            from jason.local_ai import LocalAIUnavailable
            from jason.tasks.case_files import vision_reader

            try:
                vision = vision_reader()
            except LocalAIUnavailable as exc:
                print(exc, file=sys.stderr)
                return 1
        kinds = (DocumentKind(args.kind),) if args.kind else (DocumentKind.INSPECTION_REPORT,)
        result = run_filed(data_dir, active(), kinds=kinds, vision=vision, refresh=args.refresh_text, log=None if args.json else print)
        print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2, default=str) if args.json
              else "\n".join(filed_lines(result)))
        return 0
    kinds = (DocumentKind(args.kind),) if args.kind else ()
    result = run(data_dir, active(), kinds=kinds)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for line in coverage_lines(result):
            print(line)
    return 0


def cmd_reconcile(args: argparse.Namespace) -> int:
    """PayHOA's bank reconciliations: months covered, statements against the ledger, and items that never cleared."""
    import json

    from jason.config import Settings
    from jason.tasks.reconciliations import fetch, review, review_lines

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    if args.fetch:
        with _agent(args) as agent:
            print(f"fetched {fetch(agent.payhoa(), agent.org_id, data_dir)}")
    result = review(data_dir)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for line in review_lines(result):
            print(line)
    return 0 if result.get("found") else 1


def cmd_ledger(args: argparse.Namespace) -> int:
    """PayHOA's saved treasurer's report runs and month-end balance sheets, checked against the library's copies."""
    import json

    from jason.config import Settings
    from jason.tasks.ledger_reports import fetch, library_reports, validate, validation_lines

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    if args.fetch:
        hashes = {doc["sha256"] for doc in library_reports(data_dir) if doc["sha256"]}
        with _agent(args) as agent:
            counts = fetch(agent.payhoa(), agent.org_id, data_dir, download=args.download, library_hashes=hashes, log=print)
        print(f"fetched {counts}")
    result = validate(data_dir)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for line in validation_lines(result):
            print(line)
    return 0 if result.get("found") else 1


def cmd_budget(args: argparse.Namespace) -> int:
    """Sync the year's budget and balances from PayHOA (unless --offline), then print budget against actual."""
    import json

    from jason.mcp.county import budget_status
    from jason.tasks.finance import dollars

    if not args.offline:
        with _agent(args) as agent:
            path = agent.sync_finance(year=args.year or None)
        print(f"synced {path}")
    brief = budget_status(year=args.year or 0)
    if args.json or not brief.get("found"):
        print(json.dumps(brief, indent=2, default=str))
        return 0 if brief.get("found") else 1
    ytd, full = brief["yearToDate"], brief["fullYear"]
    print(f"\n{brief['year']} budget against actual, through month {brief['throughMonth']} (synced {brief['syncedAt']})")
    print(f"  {'':<10} {'budget YTD':>14} {'actual YTD':>14} {'variance':>14}   {'full-year budget':>16}")
    for key in ("revenue", "expense", "net"):
        row = ytd.get(key) or {}
        print(f"  {key:<10} {dollars(row.get('budgeted')):>14} {dollars(row.get('actual')):>14} {dollars(row.get('variance')):>14}   {dollars((full.get(key) or {}).get('budgeted')):>16}")
    print("\nExpense categories furthest from budget, year to date:")
    for row in brief["expenseGaps"]:
        print(f"  {row['category'][:34]:<34} budget {dollars(row['budgeted']):>12}  actual {dollars(row['actual']):>12}  gap {dollars(row['gap']):>12}")
    print("\nAccounts:")
    for account in brief["accounts"]:
        print(f"  {account['label']:<12} ...{account['suffix']}  {dollars(account['balance_cents']):>14}  ({account['payhoa_name'] or 'not in PayHOA'})")
    if brief.get("reserveTotalCents") is not None:
        print(f"  reserves in all {dollars(brief['reserveTotalCents']):>18}")
    print("\n" + brief["note"])
    return 0


def cmd_accounts(args: argparse.Namespace) -> int:
    """Print the bank balances from the last finance snapshot."""
    import json

    from jason.mcp.county import bank_accounts
    from jason.tasks.finance import dollars

    result = bank_accounts()
    if args.json or not result.get("found"):
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("found") else 1
    print(f"Balances as PayHOA reported them (synced {result['syncedAt']}):")
    for account in result["accounts"]:
        refreshed = f", refreshed {account['refreshed']}" if account["refreshed"] else ""
        print(f"  {account['label']:<12} ...{account['suffix']}  {dollars(account['balance_cents']):>14}{refreshed}")
    for other in result["otherPayhoaAccounts"]:
        print(f"  other in PayHOA: {other['name']} {dollars(other['balanceCents'])}")
    print(result["note"])
    return 0


def cmd_library(args: argparse.Namespace) -> int:
    """Classify the PayHOA library by name, text, and a local model; store it and write the page."""
    from datetime import date

    from jason.community.library import coverage, library_markdown

    if args.vision:
        from jason.community.ocr import OllamaVisionOcr
        from jason.tasks.library import distinct, load, vision_read

        engine = OllamaVisionOcr(max_pages=args.pages or None)
        if not engine.available():
            print(f"the vision model {engine.model} is not on the local Ollama", file=sys.stderr)
            return 1
        kinds = {k.strip() for k in args.vision.split(",") if k.strip()}
        with _agent(args) as agent:
            root = agent.settings.ownership_db.parent
        rows = [r for r in distinct(load(root)) if r["kind"] in kinds]
        if args.limit:
            rows = rows[:args.limit]
        done = 0
        for row in rows:
            try:
                text = vision_read(root, row["id"], pages=args.pages or None, engine=engine, refresh=args.refresh_text)
            except Exception as exc:  # one bad file does not stop the run
                print(f"  error: {row['name']}: {exc}", file=sys.stderr)
                continue
            done += bool(text)
            print(f"  {'read' if text else 'skipped'} {row['name']} ({len(text)} chars)")
        print(f"vision read {done} of {len(rows)} files")
        return 0
    if args.score:
        import json

        from jason.community.content import ModelClassifier
        from jason.community.library import classify_library, payhoa_documents
        from jason.tasks.library import score

        with _agent(args) as agent:
            root = agent.settings.ownership_db.parent
            rows = classify_library(agent.community, payhoa_documents(root / "payhoa.db"))
        model = ModelClassifier(model=args.model) if args.model is not None else None
        card = score(root, rows, model=model, per_kind=args.per_kind or None)
        print(json.dumps(card.as_dict(), indent=2))
        return 0
    with _agent(args) as agent:
        rows, report = agent.ingest_library(fetch=args.fetch, model=args.model, refresh_text=args.refresh_text)
        out = agent.settings.ownership_db.parent / "reports" / "library.md"
    print(report.summary())
    for err in report.errors[:10]:
        print(f"  error: {err}", file=sys.stderr)
    cov = coverage(rows)
    print("by method: " + ", ".join(f"{k.lower()} {v}" for k, v in cov.by_method.items()))
    for path in cov.unclassified:
        print(f"  unclassified: {path}")
    out.parent.mkdir(parents=True, exist_ok=True)
    from jason.tasks.library import distinct, load

    with _agent(args) as agent:
        unique = len(distinct(load(agent.settings.ownership_db.parent)))
    out.write_text(library_markdown(rows, title="Mystique document library: what each file is", today=date.today(), distinct_files=unique), encoding="utf-8")
    print(f"wrote {out}")
    return 0


def cmd_digest(args: argparse.Namespace) -> int:
    """Print what the board should know now: what recorded, owners in default, releases owed, the association's liens."""
    import json

    from jason.mcp.county import board_digest

    d = board_digest(since=args.since, days=args.days)
    if args.json or "error" in d:
        print(json.dumps(d, indent=2, default=str))
        return 0 if "error" not in d else 1
    print(f"Since {d['since']}: {d['recorded']['count']} filings touch a unit, an owner here, or the association.")
    for row in d["recorded"]["rows"]:
        print(f"  {row['recorded']} {row.get('address', '')}: {row['what']}. {row['action']}")
    liens = d["liens"]
    print(f"\nLiens: {liens['standsCount']} stand on current owners; {liens['namesakeRisks']} name an owner by a bare name.")
    for label, key in (("In default", "inDefault"), ("Release the association owes", "releaseDue"), ("Prior owner's lien, no sale since", "standsOnPrior")):
        for row in liens[key]:
            print(f"  {label}: {row['address']} {row['process']} {row['number']} (opened {row['recorded']}, latest {row['latestStep']}), {', '.join(row['claimant'][:1])}")
    print("\nThe association's own open liens:")
    for row in d["association"]["open"] or [{"address": "none", "opened": "", "status": ""}]:
        print(f"  {row['address']} {row['opened']} {row['status']}".rstrip())
    if d["association"]["otherAssociations"]:
        print("Other associations' liens on owners here (not ours, not on these units):")
        for row in d["association"]["otherAssociations"]:
            print(f"  {row['address']}: {', '.join(row['claimant'])}, {row['status']}")
    print("\nSolar: " + ", ".join(f"{k.lower().replace('_', ' ')} {v}" for k, v in d["solar"].items()))
    fin = d.get("finance")
    if fin:
        from jason.tasks.finance import dollars

        ytd = fin.get("yearToDate") or {}
        net = ytd.get("net") or {}
        print(f"\nBudget {fin['year']} through month {fin['throughMonth']}: net {dollars(net.get('actual'))} against {dollars(net.get('budgeted'))} budgeted; "
              + "; ".join(f"{g['category']} {dollars(g['gap'])} from budget" for g in fin.get("expenseGaps") or []))
        print("Balances: " + ", ".join(f"{a['label']} {dollars(a['balance_cents'])}" for a in fin.get("accounts") or [])
              + (f"; reserves {dollars(fin['reserveTotalCents'])}" if fin.get("reserveTotalCents") is not None else "")
              + f" (synced {fin['syncedAt']})")
    coll = d.get("collections")
    if coll:
        print(f"\nCollections (the PayHOA ledger beside the association's liens): ${coll['pastDueCents'] / 100:,.2f} past due in all.")
        for label, key in (("Release owed", "releaseDue"), ("Lien secures a debt", "lienSecuresDebt"), ("Past due, no lien", "owedNoLien")):
            for row in coll[key]:
                print(f"  {label}: {row['address']} ${row['pastDueCents'] / 100:,.2f} past due" + (f", lien {row['lien']} of {row['lienRecorded']}" if row["lien"] else ""))
    return 0


def cmd_title_watch(args: argparse.Namespace) -> int:
    """Print each lien's standing against the unit's title, the ones a person acts on first."""
    import json

    from jason.mcp.county import title_watch

    result = title_watch(apn=args.apn, standing=args.standing, attention=args.attention)
    if args.json or not result.get("found"):
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("found") else 1
    for name, count in result["counts"].items():
        print(f"  {count:>4}  {name.lower().replace('_', ' ')}")
    for row in result["rows"]:
        flags = []
        if row["namesakeRisk"]:
            flags.append("namesake?")
        if row["sharedWith"]:
            flags.append("shared with " + ", ".join(row["sharedWith"]))
        if row["presumedPaidAt"]:
            flags.append(f"sale {row['presumedPaidAt']}")
        print(f"{row['standing']:<15} {row['apn']} {row['address']:<22} {row['process']:<16} {row['number']} {row['recorded']} {', '.join(row['claimant'][:1])[:34]:<34} {' | '.join(flags)}")
    return 0


def cmd_index_coverage(args: argparse.Namespace) -> int:
    """Read the whole index cache against the known processes and print what each explains and what is left."""
    import json

    from jason.mcp.county import index_coverage

    result = index_coverage(examples=args.examples)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0
    if args.write:
        from datetime import date

        from jason.community.coverage import coverage_markdown

        with _agent(args) as agent:
            out = agent.settings.ownership_db.parent / "reports" / "coverage.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(coverage_markdown(result, title="Mystique recorder index: what the processes explain", today=date.today()), encoding="utf-8")
        print(f"wrote {out}")
    print(f"{result['documents']} cached documents")
    for bucket, count in result["counts"].items():
        print(f"  {count:>5}  {bucket}")
    for bucket, rows in result["examples"].items():
        print(f"\n{bucket}:")
        for row in rows:
            print(f"  {row['number']} {row['recorded']} {row['filing']}: {'; '.join(row['from'])} -> {'; '.join(row['to'])} | {row['why']}")
    return 0


def cmd_duties(args: argparse.Namespace) -> int:
    """Write records.md and duties.md, or print one duty's brief, or (--documents) list a document's norms."""
    import json

    if getattr(args, "documents", None) is not None:
        from jason.commands.document_duties import cmd_document_duties

        return cmd_document_duties(args)
    if args.brief:
        from jason.mcp.county import duty_brief

        result = duty_brief(args.brief)
        if not result.get("found"):
            print(f"no duty named {args.brief}; one of: {', '.join(result.get('duties', []))}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(result, indent=2, default=str))
            return 0
        print(f"{result['anchor']}: {result['keepsStraight']}")
        print(f"  sections {result['sections']}; {result['cadence']}: {result['when']}")
        print(f"  artifact: {result['artifact']}")
        print(f"  records: {', '.join(result['records'])}")
        print(f"  jason: {result['produce']}")
        if result.get("limit"):
            print(f"  limit: {result['limit']}")
        for query, hits in result["passages"].items():
            print(f"  ? {query}")
            for hit in hits:
                print(f"      {hit['file']} #{hit['passage']}: {' '.join(hit['text'].split())[:200]}")
        return 0
    with _agent(args) as agent:
        report = agent.association_pages()
    print(report.summary())
    for path in report.written:
        print(f"  {path}")
    for gap in report.gaps:
        print(f"  gap: {gap}")
    return 0


def cmd_records_request(args: argparse.Namespace) -> int:
    """The copy-order list for the county clerk/recorder, as Markdown and CSV under the reports folder."""
    with _agent(args) as agent:
        result = agent.records_request(fetch_pages=args.pages, include_liens=not args.governing_only)
    print(result.summary())
    for path in result.written:
        print(f"  {path}")
    for err in result.errors:
        print(f"  error: {err}", file=sys.stderr)
    return 0


def cmd_recent_filings(args: argparse.Namespace) -> int:
    """What recorded since a date, with what to do about each."""
    import json

    from jason.mcp.county import recent_filings

    result = recent_filings(args.since)
    if result.get("error"):
        print(result["error"], file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0
    print(f"{result['count']} filings since {result['since']}")
    for row in result["filings"]:
        who = row.get("address", "")
        print(f"  {row['recorded']} {row['number']} {who}: {row['what']} -> {row['action']}")
    return 0


def cmd_sync_liens(args: argparse.Namespace) -> int:
    with _agent(args) as agent:
        result = agent.sync_liens(all_liens=args.all)
        print(result.summary())
        for err in result.errors:
            print(f"  error: {err}", file=sys.stderr)
        return 1 if result.errors and result.searched == 0 and result.narrowed == 0 else 0


def cmd_sync_solar(args: argparse.Namespace) -> int:
    with _agent(args) as agent:
        result = agent.sync_solar()
        print(result.summary())
        for err in result.errors:
            print(f"  error: {err}", file=sys.stderr)
        return 1 if result.errors and result.searched == 0 else 0


def cmd_sync_characteristics(args: argparse.Namespace) -> int:
    with _agent(args) as agent:
        result = agent.sync_characteristics(parcel=args.parcel or None)
        print(result.summary())
        for apn in result.missed:
            print(f"  missed {apn}")
        for err in result.errors:
            print(f"  error: {err}", file=sys.stderr)
        print(f"\nDatabase: {agent.settings.characteristics_db}")
        return 1 if result.errors and result.synced == 0 else 0


def cmd_sync_smud(args: argparse.Namespace) -> int:
    """SMUD bill history into the smud cache (download only; nothing goes to PayHOA)."""
    with _agent(args) as agent:
        result = agent.sync_smud(full=args.full, account=args.account)
    print(result.summary())
    for err in result.errors:
        print(f"  error: {err}", file=sys.stderr)
    return 1 if result.errors and result.bills_new == 0 and result.accounts_synced == 0 else 0


BILL_PORTALS = ("smud", "idoxs")


def cmd_fetch_bills(args: argparse.Namespace) -> int:
    """Download new utility bills from the portals (SMUD, the City's i-doxs), parse them into the utility store, and list
    what is new. Download only: attaching bills to PayHOA payments is ``jason sync-bills``."""
    from jason.tasks.utilities import bill_roots, store_path, sync

    sources = [args.source] if args.source else list(BILL_PORTALS)
    failed = False
    with _agent(args) as agent:
        for source in sources:
            try:
                if source == "smud":
                    result = agent.sync_smud(full=args.full, account=args.account)
                else:
                    result = agent.sync_idoxs(full=args.full, download_pdfs=True, account=args.account)
            except Exception as exc:  # one portal down does not stop the other
                print(f"{source}: {exc}", file=sys.stderr)
                failed = True
                continue
            print(f"{source}: {result.bills_new} new bills, {result.bills_downloaded} downloaded, {result.accounts_synced} accounts"
                  + (f", {len(result.errors)} errors" if result.errors else ""))
            for err in result.errors:
                print(f"  error: {err}", file=sys.stderr)
        settings = agent.settings
    if args.no_parse:
        return 1 if failed else 0
    store = store_path(settings.payhoa_catalog.parent)
    before = _store_sources(store)
    parsed = sync(bill_roots(settings), store)
    print(f"utility store: parsed {parsed.parsed} bills ({parsed.unchanged} unchanged, {parsed.removed} removed)")
    for line in parsed.unreadable:
        print(f"  unreadable: {line}")
    for provider, account, day, total in _new_bills(store, before):
        print(f"  new: {provider} {account} {day} ${total / 100:,.2f}")
    return 1 if failed else 0


def _store_sources(store: Path) -> set[str]:
    import sqlite3

    if not store.is_file():
        return set()
    with sqlite3.connect(store) as db:
        return {row[0] for row in db.execute("select source from bills")}


def _new_bills(store: Path, before: set[str]) -> list[tuple[str, str, str, int]]:
    """The bills the parse added, from a portal's own folder (a PayHOA attachment copy is not a new bill)."""
    import sqlite3

    with sqlite3.connect(store) as db:
        rows = db.execute("select source, provider, account, bill_date, total_cents from bills order by provider, account").fetchall()
    return [(provider, account, day, total) for source, provider, account, day, total in rows
            if source not in before and "payhoa" not in source.lower()]


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
        default=None,
        help="Output path (default: payhoa_txs.jsonl in the profile's data folder)",
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

    sync_bills = sub.add_parser(
        "sync-bills",
        help=(
            "PayHOA-first: list pending utility txs, sync only needed "
            "portals (SMUD / i-doxs), then attach PDFs"
        ),
    )
    _add_common(sync_bills)
    sync_bills.add_argument(
        "--date-window-days",
        type=int,
        default=7,
        help="Max |tx date - bill date| in days (default: 7)",
    )
    sync_bills.add_argument(
        "--source",
        choices=_bill_sources(),
        help="Limit to one bill source (default: all registered)",
    )
    sync_bills.add_argument(
        "--skip-sync",
        action="store_true",
        help="Attach using local caches only (skip portal sync)",
    )
    sync_bills.add_argument(
        "--dry-run",
        action="store_true",
        help="List pending matches without portal sync or uploads",
    )
    sync_bills.add_argument(
        "--approve",
        action="store_true",
        help="Mark transaction approved after successful upload",
    )
    sync_bills.add_argument("-v", "--verbose", action="store_true")
    sync_bills.set_defaults(func=cmd_sync_bills)

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

    sync_catalog = sub.add_parser(
        "sync-catalog",
        help=(
            "Sync PayHOA units, people, violations, requests, and documents "
            "into the local catalog"
        ),
    )
    _add_common(sync_catalog)
    sync_catalog.add_argument(
        "--only",
        help="Comma-separated kinds: units,people,violations,requests,documents",
    )
    sync_catalog.add_argument(
        "--people-status",
        default="active",
        help="people-list status query (default: active)",
    )
    sync_catalog.add_argument(
        "--violation-status",
        default="",
        help='violations-table status query (default: every status, so closed violations stay in the record; "All Outstanding" for open ones)',
    )
    sync_catalog.set_defaults(func=cmd_sync_catalog)

    export_requests = sub.add_parser(
        "export-requests",
        help="Download request attachments and write them into one markdown file",
    )
    _add_common(export_requests)
    export_requests.add_argument(
        "--out",
        help="Output markdown path (default: data/payhoa-requests.md)",
    )
    export_requests.add_argument(
        "--status",
        help="Comma-separated statuses to keep, for example pending",
    )
    export_requests.add_argument(
        "--form",
        help="Keep one form name, for example Maintenance Request",
    )
    export_requests.add_argument(
        "--no-refresh",
        action="store_true",
        help="Use attachments already on disk",
    )
    export_requests.set_defaults(func=cmd_export_requests)

    request_sheet = sub.add_parser(
        "request-sheet",
        help="Create a Google Sheet of open requests, one tab per kind",
    )
    _add_common(request_sheet)
    request_sheet.add_argument(
        "--status",
        help="Comma-separated statuses to keep (default: pending)",
    )
    request_sheet.add_argument(
        "--title",
        default="Mystique open requests",
        help="Title of the new spreadsheet",
    )
    request_sheet.add_argument(
        "--spreadsheet",
        help="Put photos into this existing spreadsheet instead of creating one",
    )
    request_sheet.set_defaults(func=cmd_request_sheet)

    export_docs = sub.add_parser(
        "export-documents",
        help="Refresh the PayHOA document library and write it to JSON for sync-rule analysis",
    )
    _add_common(export_docs)
    export_docs.add_argument(
        "--out",
        help="Output JSON path (default: data/payhoa-documents.json)",
    )
    export_docs.set_defaults(func=cmd_export_documents)

    document_sync = sub.add_parser(
        "document-sync",
        help="Dry-run Drive sync rules against the catalog. Does not upload",
    )
    _add_common(document_sync)
    document_sync.add_argument(
        "--out",
        help="Directory for plan.json and report.md (default: data/sync-plan)",
    )
    document_sync.set_defaults(func=cmd_document_sync)

    publish = sub.add_parser(
        "publish-document",
        help="Export a Google Doc to PDF and upload it into a PayHOA folder",
    )
    _add_common(publish)
    publish.add_argument("--doc", required=True, help="Google Doc id")
    publish.add_argument(
        "--parent",
        required=True,
        type=int,
        help="PayHOA folder id, from export-documents",
    )
    publish.add_argument("--out", required=True, help="Where to write the PDF")
    publish.add_argument("--name", help="File name stored in PayHOA")
    publish.set_defaults(func=cmd_publish_document)

    reports = sub.add_parser(
        "reports",
        help="List PayHOA report definitions and pull aging, resale, and PDF export summaries",
    )
    _add_common(reports)
    reports.set_defaults(func=cmd_reports)

    who = sub.add_parser(
        "who-owes",
        help="Unpaid issued charges tied to units, plus recurring assessment titles",
    )
    _add_common(who)
    who.set_defaults(func=cmd_who_owes)

    who_sheet = sub.add_parser(
        "who-owes-sheet",
        help=(
            "Write who-owes (unit, owner, balance, aging) into the configured "
            "Google Sheet for human review; does not submit to a collection agency"
        ),
    )
    _add_common(who_sheet)
    who_sheet.set_defaults(func=cmd_who_owes_sheet)
    permits = sub.add_parser(
        "permits",
        help="Search Sacramento Citizen Access permits, parcels, and addresses",
    )
    permits.add_argument(
        "--module",
        default="building",
        choices=["building", "planning", "public-works", "operating-permit"],
    )
    permits.add_argument("--permit", default="", help="Record number, such as COM-2616861")
    permits.add_argument("--project", default="")
    permits.add_argument("--street", default="")
    permits.add_argument("--suffix", default="", help="Street suffix, such as DR")
    permits.add_argument("--street-from", default="")
    permits.add_argument("--street-to", default="")
    permits.add_argument("--direction", default="")
    permits.add_argument("--parcel", default="", help="Parcel number, with or without dashes")
    permits.add_argument("--start", default="", help="Opened on or after, MM/DD/YYYY")
    permits.add_argument("--end", default="", help="Opened on or before, MM/DD/YYYY")
    permits.add_argument("--license-type", default="")
    permits.add_argument("--license-number", default="")
    permits.add_argument("--first-name", default="")
    permits.add_argument("--last-name", default="")
    permits.add_argument("--business", default="")
    permits.add_argument(
        "--lookup",
        choices=["parcel", "address"],
        help="Property lookup instead of a permit search",
    )
    permits.add_argument(
        "--cap",
        default="",
        help="Record detail for id1:id2:id3, such as 26BCM:00000:03422",
    )
    permits.add_argument("--out", default="", help="Write the portal CSV export")
    permits.add_argument(
        "--save-report",
        default="",
        help="With --cap, write the Print/View Record PDF to this path",
    )
    permits.set_defaults(func=cmd_permits)

    ownership = sub.add_parser(
        "ownership-sheet",
        help="Create a new spreadsheet of ownership from county records",
    )
    _add_common(ownership)
    ownership.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the new spreadsheet",
    )
    ownership.set_defaults(func=cmd_ownership_sheet)

    property_history = sub.add_parser(
        "property-history",
        help="Write one Markdown history per parcel from the local stores; --sheet also publishes a spreadsheet",
    )
    _add_common(property_history)
    property_history.add_argument("--out", default="", help="Folder for the Markdown (default data/reports/property-history)")
    property_history.add_argument("--sheet", action="store_true", help="Also create the property history spreadsheet")
    property_history.add_argument("--spreadsheet", default="", help="Refresh this existing spreadsheet in place instead of creating one")
    property_history.add_argument("--no-browser", action="store_true", help="Do not open the new spreadsheet")
    property_history.add_argument("--no-charts", action="store_true", help="Skip the SVG charts (matplotlib); the Mermaid charts still render")
    property_history.set_defaults(func=cmd_property_history)

    unit_charts = sub.add_parser(
        "unit-charts",
        help="Create a spreadsheet that charts the unit numberings, the overlap, and the sales",
    )
    _add_common(unit_charts)
    unit_charts.add_argument("--no-browser", action="store_true", help="Do not open the new spreadsheet")
    unit_charts.set_defaults(func=cmd_unit_charts)

    sales_charts = sub.add_parser(
        "sales-charts",
        help="Create a spreadsheet that charts the conveyance history: counts and prices by year, process, and building",
    )
    _add_common(sales_charts)
    sales_charts.add_argument("--no-browser", action="store_true", help="Do not open the new spreadsheet")
    sales_charts.set_defaults(func=cmd_sales_charts)

    equity_charts = sub.add_parser(
        "equity-charts",
        help="Create a spreadsheet of unit values and appreciation against recent comps, with a per-unit lookup",
    )
    _add_common(equity_charts)
    equity_charts.add_argument("--spreadsheet", help="Refresh this spreadsheet id in place instead of creating one")
    equity_charts.add_argument("--no-browser", action="store_true", help="Do not open the new spreadsheet")
    equity_charts.set_defaults(func=cmd_equity_charts)

    sync_characteristics = sub.add_parser(
        "sync-characteristics",
        help="Copy the assessor's residential characteristics (living area, bedrooms, baths, year built) for each unit into the local store",
    )
    _add_common(sync_characteristics)
    sync_characteristics.add_argument("--parcel", help="One parcel number (default: every unit parcel)")
    sync_characteristics.set_defaults(func=cmd_sync_characteristics)

    sync_solar = sub.add_parser(
        "sync-solar",
        help="Pull every UCC filing the solar lease funds recorded into the index cache, so each unit's lease standing can be read",
    )
    _add_common(sync_solar)
    sync_solar.set_defaults(func=cmd_sync_solar)

    sync_liens = sub.add_parser(
        "sync-liens",
        help="Pull mechanic's lien filings, releases, and notices of action for the developers, the association, and every owner into the index cache",
    )
    _add_common(sync_liens)
    sync_liens.add_argument("--all", action="store_true", help="Also fetch every other lien-family filing (association, utility, judgment, tax, default) for the wide names; a few thousand index calls")
    sync_liens.set_defaults(func=cmd_sync_liens)

    brief = sub.add_parser("brief", help="One unit on one page from the stores: title, chain, liens, solar, taxes, members, value")
    _add_common(brief)
    brief.add_argument("apn", help="Parcel number, dashed or not")
    brief.add_argument("--escrow", action="store_true", help="Add the lines the association can tell escrow")
    brief.add_argument("--json", action="store_true", help="Print the brief as JSON instead of Markdown")
    brief.set_defaults(func=cmd_brief)

    read_docs = sub.add_parser("read-documents", help="Score a document reader (regex or claude) against the pinned facts, or search the extracts by passage")
    _add_common(read_docs)
    read_docs.add_argument("--extractor", default="regex", choices=("regex", "ollama", "claude"), help="Which reader to score")
    read_docs.add_argument("--model", default="", help="Model name for ollama or claude (default qwen3.6:27b, claude-fable-5-1)")
    read_docs.add_argument("--search", default="", help="Search the extracts for this question instead of scoring")
    read_docs.add_argument("-k", type=int, default=6, help="Passages to show")
    read_docs.add_argument("--json", action="store_true", help="Print JSON")
    read_docs.set_defaults(func=cmd_read_documents)

    scans = sub.add_parser("read-scans", help="Read each image-only governing PDF with the local vision model through Ollama and keep the readings under data/readings")
    _add_common(scans)
    scans.add_argument("--model", default="", help="A local vision model (default qwen3.6:27b)")
    scans.add_argument("--refresh", action="store_true", help="Read again the files that already have a reading")
    scans.set_defaults(func=cmd_read_scans)

    ocr = sub.add_parser("ocr-documents", help="Write a text layer beside each image-only governing PDF with the installed OCR engine (Docling with RapidOCR, or PyMuPDF with Tesseract)")
    _add_common(ocr)
    ocr.set_defaults(func=cmd_ocr_documents)

    auth = sub.add_parser("export-authorities", help="Export the words of the law Jason relies on from lawlibrary into data/authorities, or --list what is there")
    _add_common(auth)
    auth.add_argument("--list", action="store_true", help="List the exported pages and the pointers without calling lawlibrary")
    auth.add_argument("--fetch-publications", action="store_true", help="Also download the DRE publications into data/authorities/publications")
    auth.add_argument("--digests", action="store_true", help="Record each section's digest in the manifest from the pages already on disk, without calling lawlibrary")
    auth.set_defaults(func=cmd_export_authorities)

    law_hist = sub.add_parser("law-history", help="The Davis-Stirling Act's history: where each former Civil Code 1350-1378 section "
                                                  "went (the Law Revision Commission's tables), and every change since 2011")
    _add_common(law_hist)
    law_hist.add_argument("--export", action="store_true", help="Ask lawlibrary again and write data/authorities/history")
    law_hist.add_argument("--section", default="", help="A former section (1363 or 1363(g)): its successors; a current one (5855): its changes")
    law_hist.add_argument("--since", default="", help="With a current section or none, only changes in editions from this year")
    law_hist.add_argument("--sweep", action="store_true", help="List every place jason cites a section changed since --since "
                                                               "(renumbered with the same effect is not a change); writes data/reports/law-sweep.md")
    law_hist.add_argument("--json", action="store_true", help="Print JSON")
    from jason.commands.law_versions import add_arguments as _law_versions_arguments

    _law_versions_arguments(law_hist)
    law_hist.set_defaults(func=cmd_law_history)

    cover = sub.add_parser("index-coverage", help="Read every cached index document against the known processes and list what is left to model")
    _add_common(cover)
    cover.add_argument("--examples", type=int, default=4, help="Examples to show per leftover pattern")
    cover.add_argument("--json", action="store_true", help="Print JSON")
    cover.add_argument("--write", action="store_true", help="Also write data/reports/coverage.md")
    cover.set_defaults(func=cmd_index_coverage)

    budget = sub.add_parser("budget", help="Sync the budget against actual and the bank balances from PayHOA, then print them")
    _add_common(budget)
    budget.add_argument("--year", type=int, default=0, help="Budget year (default this year)")
    budget.add_argument("--offline", action="store_true", help="Print the last snapshot without calling PayHOA")
    budget.add_argument("--json", action="store_true", help="Print JSON")
    budget.set_defaults(func=cmd_budget)

    invoices = sub.add_parser("invoices", help="Check every expense payment's attached invoice: amount, vendor, date, reuse, category")
    _add_common(invoices)
    invoices.add_argument("--fetch", action="store_true", help="Read all transactions, categories, and vendors, and download missing attachments first")
    invoices.add_argument("--payee", default="", help="Only this payee's findings")
    invoices.add_argument("--limit", type=int, default=60, help="Payments to list, newest first")
    invoices.add_argument("--json", action="store_true", help="Print JSON")
    invoices.set_defaults(func=cmd_invoices)

    mailroom = sub.add_parser("mailroom", help="PayHOA's Mailroom (USPS letters through Lob): mailings and their cost; preview a PDF "
                                               "letter to units; mail it only with --send --yes")
    _add_common(mailroom)
    mailroom.add_argument("--batch", type=int, default=0, help="One mailing's letters: status, Lob events, tracking")
    mailroom.add_argument("--pdf", default="", help="A PDF letter to preview (and, with --send --yes, to mail)")
    mailroom.add_argument("--units", default="", help="With --pdf: street addresses or PayHOA unit ids, comma-separated, or 'all'")
    mailroom.add_argument("--send-to", choices=("mailing", "unit"), default="mailing",
                          help="Each owner's mailing address (default) or the unit's own address")
    mailroom.add_argument("--with-invoices", action="store_true", help="Mail each owner's invoice with the letter")
    mailroom.add_argument("--double-sided", action="store_true", help="Print on both sides")
    mailroom.add_argument("--send", action="store_true", help="Mail the letter after the preview (needs --yes; charges postage)")
    mailroom.add_argument("--cancel", type=int, default=0, help="Cancel a letter still processing, by its letter id (needs --yes)")
    mailroom.add_argument("--prices", action="store_true",
                          help="Check every letter PayHOA charged against its pricing guide (payhoa.pricing); "
                               "saves data/mailroom/price-check.json")
    mailroom.add_argument("--letters", choices=("pdf", "invoice", "violation", "bill-pay", "voting"),
                          help="Every letter of one kind across its mailings: status, last event, cost, communication id")
    mailroom.add_argument("--events", type=int, default=0, metavar="COMMUNICATION",
                          help="One letter's postal events, by its communication id (from --letters or --batch)")
    mailroom.add_argument("--months", metavar="YEAR", help="Pieces mailed each month of a year")
    mailroom.add_argument("--notice", metavar="KEY",
                          help="With --pdf --send: the notice's ledger key (it starts with the requirement's key); the "
                               "letter as mailed and its recipients' ids are kept in data/notices/KEY/")
    mailroom.add_argument("--by", metavar="NAME", help="With --notice: who mailed it")
    mailroom.add_argument("--yes", action="store_true", help="Confirm --send or --cancel")
    mailroom.add_argument("--json", action="store_true", help="Print JSON")
    mailroom.set_defaults(func=cmd_mailroom)

    mail = sub.add_parser("mail", help="Read the PostScanMail mailbox: new mail, what to act on (legal, cancellations, government), and dates")
    _add_common(mail)
    mail.add_argument("--offline", action="store_true", help="Print from disk without calling PostScanMail")
    mail.add_argument("--full", action="store_true", help="Page through every item, not only the new ones")
    mail.add_argument("--resort", action="store_true", help="Sort the stored items again with the current rules (no calls)")
    mail.add_argument("--reread-ocr", action="store_true",
                      help="Read the scans Tesseract read again with the current OCR (the local vision model first), then sort (no calls)")
    mail.add_argument("--limit", type=int, default=0, help="With --reread-ocr, at most this many items")
    mail.add_argument("--days", type=int, default=30, help="Mail received in the last N days (default 30)")
    mail.add_argument("--item", default="", help="Print one item's record and scanned text")
    mail.add_argument("--checks", action="store_true",
                      help="Check the stored mail against jason's records: old addresses, escrow clocks, tax bills, bank balances, checks")
    mail.add_argument("--json", action="store_true", help="Print JSON")
    mail.set_defaults(func=cmd_mail)

    zoom = sub.add_parser("zoom", help="Sync the Zoom account's meetings, transcripts, and AI summaries; list them with next steps and schedule gaps")
    _add_common(zoom)
    zoom.add_argument("--offline", action="store_true", help="Print from disk without calling Zoom")
    zoom.add_argument("--full", action="store_true", help="Read the whole history from the first Zoom day, not only recent weeks")
    zoom.add_argument("--since", default="", help="Read from this date (YYYY-MM-DD)")
    zoom.add_argument("--media", action="store_true", help="Also download audio and video recordings (large)")
    zoom.add_argument("--days", type=int, default=0, help="List meetings from the last N days (default all)")
    zoom.add_argument("--kind", default="", help="Only this kind: board, annual, executive, hearing, committee, other")
    zoom.add_argument("--limit", type=int, default=40, help="Meetings to list, newest first")
    zoom.add_argument("--meeting", default="", help="Print one meeting (UUID, folder, date, or meeting id): summary and transcript")
    zoom.add_argument("--confidential", action="store_true", help="With --meeting, include an executive session's or hearing's text")
    zoom.add_argument("--store-app", action="store_true",
                      help="Create the Keeper record for the Zoom app (with --account-id, --client-id); the secret is filled in Keeper")
    zoom.add_argument("--account-id", default="", help="With --store-app: the app's account id")
    zoom.add_argument("--client-id", default="", help="With --store-app: the app's client id")
    zoom.add_argument("--create-board-meeting", action="store_true",
                      help="Schedule the board meeting on Zoom under the profile's board meeting policy (needs --yes); the join link and dial-in go to the notice")
    zoom.add_argument("--date", default="", help="With --create-board-meeting: the meeting date YYYY-MM-DD (default the schedule's next)")
    zoom.add_argument("--time", default="", help="With --create-board-meeting: the start, e.g. '7:00 pm' (default the schedule's hour)")
    zoom.add_argument("--meeting-id", default="", help="With --recording or --caption: the live meeting's id")
    zoom.add_argument("--recording", default="", choices=["", "start", "pause", "resume", "stop"],
                      help="Control the live meeting's cloud recording as the host (pause for an executive session); needs --meeting-id and --yes")
    zoom.add_argument("--caption", default="", help="Post one line, prefixed 'jason:', into the live meeting's captions for everyone; needs --meeting-id and --yes")
    zoom.add_argument("--lang", default="en-US", help="With --caption: the caption language (default en-US)")
    zoom.add_argument("--by", default="", help="With --recording or --caption: who asked for it, for the log")
    zoom.add_argument("--yes", action="store_true", help="Confirm --create-board-meeting, --recording, or --caption")
    zoom.add_argument("--json", action="store_true", help="Print JSON")
    zoom.set_defaults(func=cmd_zoom)

    hearing = sub.add_parser("hearing", help="Plan a disciplinary hearing (CIV 5855): dates, notice draft; --create --yes schedules it on Zoom")
    _add_common(hearing)
    hearing.add_argument("--address", default="", help="The unit's street address (e.g. '123 Main St')")
    hearing.add_argument("--violation", default="", help="The nature of the alleged violation, in the board's words")
    hearing.add_argument("--date", default="", help="Hearing date YYYY-MM-DD (default: the first meeting day the notice can reach)")
    hearing.add_argument("--time", default="", help="Hearing time, e.g. '6:30 pm' (default: the schedule's hour)")
    hearing.add_argument("--notice-on", default="", help="The day the notice is (or was) delivered, YYYY-MM-DD")
    hearing.add_argument("--create", action="store_true", help="Schedule the Zoom meeting (needs --yes)")
    hearing.add_argument("--yes", action="store_true", help="Confirm --create")
    hearing.add_argument("--list", action="store_true", help="List the saved hearings and their deadlines")
    hearing.add_argument("--suspension", action="store_true",
                         help="The board may suspend membership rights: 15 days' notice (Corporations Code 7341)")
    hearing.add_argument("--doc", action="store_true", help="Write the notice of hearing as a Google Doc from the template (needs --yes)")
    hearing.add_argument("--owner", default="", help="With --doc: the owner of record's name, as the notice should address them")
    hearing.add_argument("--matter", default="", help="With --doc: the matter's name for its Drive folder (e.g. 'Trash Cans')")
    hearing.add_argument("--delivery", default="", help="With --doc: how the notice is delivered (e.g. 'first-class mail')")
    hearing.add_argument("--sections", default="", help="With --doc: the governing-document sections the board relies on, quoted")
    hearing.add_argument("--contact", default="", help="With --doc: who to contact with questions")
    hearing.add_argument("--json", action="store_true", help="Print JSON")
    hearing.set_defaults(func=cmd_hearing)

    meetings = sub.add_parser("meetings", help="Catalog every meeting's agenda, minutes, transcripts, summaries, and recordings across Zoom, Drive, and PayHOA")
    _add_common(meetings)
    meetings.add_argument("--sync", action="store_true", help="Sync Zoom and PayHOA's meeting notices first (Drive, the library, and Gmail come from `jason drive --sync`, `jason library --fetch`, `jason gmail --sync`)")
    meetings.add_argument("--links", action="store_true", help="Read the agenda Docs (read-only) and PDFs for the files, folders, and photos each item links")
    meetings.add_argument("--items", action="store_true",
                          help="Relate each agenda item to its documents (linked, named, received) and suggest kinds for the ones the name rules miss")
    meetings.add_argument("--fetch-items", action="store_true",
                          help="With --items, read (never change) the undecided agenda files from Drive so their text can decide them")
    meetings.add_argument("--offline-links", action="store_true", help="With --links, use the agenda Docs already kept on disk")
    meetings.add_argument("--file", default="", help="The agenda labels of a linked file (Drive id, name, path, or URL)")
    meetings.add_argument("--date", default="", help="One meeting's records (YYYY-MM-DD)")
    meetings.add_argument("--limit", type=int, default=24, help="Meetings to print, newest first (the report file has all)")
    meetings.add_argument("--json", action="store_true", help="Print JSON")
    meetings.set_defaults(func=cmd_meetings)

    jobs_parser = sub.add_parser("jobs", help="The job queue: add a jason command (jason jobs add -- gmail --sync), list, show, cancel")
    _add_common(jobs_parser)
    jobs_parser.add_argument("--confirm", default="", help="With add: the person who approved a command that writes (--yes)")
    jobs_parser.add_argument("--resource", default="", choices=["", "gpu", "google", "payhoa", "county", "local"],
                             help="With add: the resource the command uses, when the guess is wrong")
    jobs_parser.add_argument("--max-attempts", type=int, default=3, help="With add: tries for a read or sync (a write runs once)")
    jobs_parser.add_argument("--all", action="store_true", help="List every job, not only queued, running, and failed")
    jobs_parser.add_argument("--tail", type=int, default=40, help="With show: lines of the job's log")
    jobs_parser.add_argument("--json", action="store_true", help="Print JSON")
    jobs_parser.add_argument("action", nargs="?", default="list", choices=["list", "add", "show", "cancel"])
    jobs_parser.add_argument("command", nargs=argparse.REMAINDER, help="With add: the jason command after --; with show or cancel: the job id")
    jobs_parser.set_defaults(func=cmd_jobs)
    worker = sub.add_parser("worker", help="Run the job queue: one job at a time per resource (GPU, Google, PayHOA, local)")
    _add_common(worker)
    worker.add_argument("--once", action="store_true", help="Stop when nothing is due")
    worker.add_argument("--poll", type=float, default=20.0, help="Seconds between looks at the queue")
    worker.add_argument("--keep-models", action="store_true",
                        help="Leave models loaded after GPU jobs (by default the worker unloads a model no queued job "
                             "needs, except jason's shared model)")
    worker.set_defaults(func=cmd_worker)
    outlines = sub.add_parser("outlines", help="Outline the governing documents and resolutions; map their references to each other and the law")
    _add_common(outlines)
    outlines.add_argument("--fetch", action="store_true", help="Read the Google Docs and the library's text again (read-only)")
    outlines.add_argument("--doc", default="", help="Print one document's outline (a key, such as bylaws)")
    outlines.add_argument("--depth", type=int, default=3, help="Outline depth for --doc")
    outlines.add_argument("--section", default="", help="One section with what it cites and what cites it (bylaws#7.2)")
    outlines.add_argument("--cites", default="", help="Everything that cites a target (\"CIV 4926\", bylaws#8.5, resolution:20230130-1)")
    outlines.add_argument("--json", action="store_true", help="Print JSON")
    outlines.add_argument("--model", action="store_true",
                          help="Read sections with the local model for the prose references the grammar misses; writes outlines/model/references.json")
    outlines.add_argument("--model-doc", action="append", default=[],
                          help="With --model: a document (owners-manual) or section (bylaws#7.2) to read; repeatable; default every outline")
    outlines.add_argument("--model-limit", type=int, default=20, help="With --model: at most this many sections (0 for no limit)")
    outlines.add_argument("--model-again", action="store_true", help="With --model: read sections read before with the same words again")
    outlines.set_defaults(func=cmd_outlines)
    local_ai = sub.add_parser("local-ai", help="Ollama, its GPU, the loaded models, Windows commit and page files, and jason's locks")
    local_ai.add_argument("--json", action="store_true", help="Print JSON")
    local_ai.add_argument("--check", action="store_true", help="Exit 1 when there is a finding (for a script or scheduled task)")
    local_ai.add_argument("--restart-ollama", action="store_true", help="Restart the Ollama app so it finds the GPU again (needs --yes)")
    local_ai.add_argument("--unload", default="", help="Unload this model from Ollama, or 'all' (needs --yes)")
    local_ai.add_argument("--yes", action="store_true", help="Confirm --restart-ollama or --unload")
    local_ai.set_defaults(func=cmd_local_ai)
    vault = sub.add_parser("vault", help="Google Vault: list matters and legal holds (read-only; first run needs --interactive to consent)")
    _add_common(vault)
    vault.add_argument("--json", action="store_true", help="Print JSON")
    vault.set_defaults(func=cmd_vault)

    templates = sub.add_parser("templates",help="The letter templates in Drive and their {TOKENS}; --build --yes builds missing ones")
    _add_common(templates)
    templates.add_argument("--build", action="store_true", help="Build the templates that have no Drive id from the Letterhead")
    templates.add_argument("--rewrite", default="", help="Replace one built template's body with the current text (a kind, e.g. hearing-notice)")
    templates.add_argument("--yes", action="store_true", help="Confirm --build or --rewrite")
    templates.add_argument("--generate", action="store_true",
                           help="Plan the profile's template Docs against jason's bases (create, adopt, update, edited, "
                                "conflict); with --yes, write them and record the ids in data/templates/<profile>.json")
    templates.add_argument("--lint", action="store_true",
                           help="Each template's tokens by where they come from: the profile, general wording, or the letter")
    templates.add_argument("--json", action="store_true", help="Print JSON")
    templates.set_defaults(func=cmd_templates)

    letter = sub.add_parser("letter", help="Fill a copy of a letter template: --template, --name, --set KEY=value (needs --yes)")
    _add_common(letter)
    letter.add_argument("--template", help="letterhead, hearing-notice, or decision-notice")
    letter.add_argument("--markdown", metavar="FILE",
                        help="set a Markdown file (a guide, a notice; pictures as ![alt](file){width=600}) on the "
                             "letterhead as a Doc, rewritten in place on later runs (--yes)")
    letter.add_argument("--pdf", metavar="OUT", help="with --markdown: also save the Doc as a PDF here (to attach or post)")
    letter.add_argument("--style", choices=("report", "letter"), default="report",
                        help="with --markdown: the house style (report: spaced paragraphs; letter: a letter's spacing)")
    letter.add_argument("--name", default="", help="The new Doc's name")
    letter.add_argument("--folder", default="", help="Drive folder id (default: the template's folder)")
    letter.add_argument("--set", action="append", metavar="KEY=value", help="A token's value; repeat. \\n for a new line")
    letter.add_argument("--yes", action="store_true", help="Confirm writing the Doc")
    letter.set_defaults(func=cmd_letter)

    cal = sub.add_parser("deadlines",help="Recurring deadlines (taxes, filings, inspections, insurance, reserve study) with the evidence each was done")
    _add_common(cal)
    cal.add_argument("--json", action="store_true", help="Print JSON")
    cal.add_argument("--within", type=int, help="Only what is due within this many days (overdue included)")
    cal.add_argument("--overdue", action="store_true", help="Only what is overdue")
    cal.add_argument("--name", help="Only deadlines whose name contains this (insurance, tax, reserve)")
    cal.set_defaults(func=cmd_deadlines)

    insurance = sub.add_parser("insurance", help="Each policy's term, renewal notices, premiums paid by term, and claims, from the mail and PayHOA on disk")
    _add_common(insurance)
    insurance.add_argument("--json", action="store_true", help="Print JSON")
    insurance.add_argument("--policy", help="One policy: master, umbrella, fidelity (crime), d&o, workers-comp, flood-2, or a policy number")
    insurance.add_argument("--claims", action="store_true", help="Only the claims in the mail")
    insurance.set_defaults(func=cmd_insurance)

    gm = sub.add_parser("gmail", help="Read the association's Gmail, headers only: PostScanMail notices against the synced mail, and correspondence")
    _add_common(gm)
    gm.add_argument("--sync", action="store_true", help="Read Gmail first (read-only; needs the Google token with the Gmail scope)")
    gm.add_argument("--days", type=int, default=730, help="How far back to read (default 730 days)")
    gm.add_argument("--files", action="store_true", help="Save the PDF attachments of business email that look like documents")
    gm.add_argument("--file-vendor", metavar="NAME", default="",
                    help="File the attachments a vendor sent from its known domains or emails in Drive (a sender directory name, "
                         "or all) by the profile's filing rules (kind, then source); skips what Drive holds. Prints the plan; --yes uploads")
    gm.add_argument("--yes", action="store_true", help="With --file-vendor: upload the attachments the plan marks file")
    gm.add_argument("--hold", action="append", metavar="GLOB",
                    help="With --file-vendor: hold back attachments whose names match (repeatable), for a person to verify")
    gm.add_argument("--why", action="store_true",
                    help="With --file-vendor: under each document, the filing rule's condition and the facts that decided it")
    gm.add_argument("--via-gmail", action="store_true",
                    help="With --file-vendor: use Gmail's own Add to Drive, which links the file to its email. Lists "
                         "what to save (data/gmail/save-to-drive.md) from Gmail's metadata only; --yes moves the copies "
                         "saved to My Drive into their folders. Nothing is downloaded or uploaded")
    gm.add_argument("--filters-xml", metavar="PATH", nargs="?", const="data/gmail/vendor-filters.xml", default="",
                    help="Write Gmail filters (the file Gmail imports) that label each vendor's mail Vendors/<vendor> by "
                         "its known domains and emails (default data/gmail/vendor-filters.xml)")
    gm.add_argument("--json", action="store_true", help="Print JSON")
    gm.set_defaults(func=cmd_gmail)

    ct = sub.add_parser("contacts", help="Vendor contacts: PayHOA's directory against who writes from each vendor in Gmail, and what to update")
    _add_common(ct)
    ct.add_argument("--fetch", action="store_true", help="Read PayHOA's vendor-info report first (read-only)")
    ct.add_argument("--json", action="store_true", help="Print JSON")
    ct.set_defaults(func=cmd_contacts)

    cp = sub.add_parser("copies", help="Group every copy of every invoice and bill across portal, email, PayHOA, and paper; best copy and payment")
    cp.add_argument("--section", action="append", choices=("proposals", "several", "documents"),
                    help="Only this part of the report (repeatable): proposals with no invoice, documents on several payments, "
                         "or the document list (default: all)")
    cp.add_argument("--since", help="Only documents issued on or after this date (YYYY-MM-DD)")
    cp.add_argument("--unexplained", action="store_true", help="With the several-payments part: only what no audit explains")
    _add_common(cp)
    cp.add_argument("--issuer", default="", help="Only this issuer's documents (all of them, not only those in several channels)")
    cp.add_argument("--limit", type=int, default=30, help="Documents to list")
    cp.add_argument("--json", action="store_true", help="Print JSON")
    cp.set_defaults(func=cmd_copies)

    dr = sub.add_parser("drive", help="Where each association record is in Drive: path rules, copies by content, duplicates, versions")
    _add_common(dr)
    dr.add_argument("--sync", action="store_true", help="List every Drive file first (read-only)")
    dr.add_argument("--record", default="", help="Only this record (a Civil Code 5200 record's name), with every file outside the rules")
    dr.add_argument("--gmail", action="store_true", help="Find the email each Drive file was saved from: same name in Gmail, same content")
    dr.add_argument("--all-files", action="store_true", help="With --gmail: every Drive file with content, not only those outside the rules or duplicated")
    dr.add_argument("--json", action="store_true", help="Print JSON (without the per-file rows)")
    dr.set_defaults(func=cmd_drive)

    th = sub.add_parser("threads", help="Email threads: awaiting us, awaiting them, with related payments, letters, documents, and unit activity")
    _add_common(th)
    th.add_argument("--status", default="", choices=["", "awaiting us", "awaiting them", "notice", "internal"], help="Only this status")
    th.add_argument("--party", default="", help='Only one party\'s threads: a unit ("123 MAIN"), a sender, or a domain')
    th.add_argument("--days", type=int, default=120, help="Threads with a message in the last N days (default 120)")
    th.add_argument("--limit", type=int, default=40, help="Threads to list")
    th.add_argument("--json", action="store_true", help="Print JSON")
    th.set_defaults(func=cmd_threads)

    pt = sub.add_parser("party", help="One unit (by address) or counterparty (by name or domain) across every store")
    _add_common(pt)
    pt.add_argument("query", help='A unit address ("123 MAIN"), a sender name, its PayHOA vendor, or its email domain')
    pt.add_argument("--json", action="store_true", help="Print JSON")
    pt.set_defaults(func=cmd_party)

    tp = sub.add_parser("topics", help="What owners, vendors, and agencies write about, by topic; the FAQ candidates")
    _add_common(tp)
    tp.add_argument("--examples", type=int, default=2, help="Recent threads to show per topic")
    tp.add_argument("--json", action="store_true", help="Print JSON")
    tp.set_defaults(func=cmd_topics)

    no = sub.add_parser("new-owners", help="Units conveyed recently: the buyer's questions, PayHOA link, balance, and requests")
    _add_common(no)
    no.add_argument("--days", type=int, default=365, help="Deeds recorded in the last N days (default 365)")
    no.add_argument("--json", action="store_true", help="Print JSON")
    no.set_defaults(func=cmd_new_owners)

    oi = sub.add_parser("open-items", help="What is waiting on the association: email, requests, deadlines, insurance, mail")
    _add_common(oi)
    oi.add_argument("--days", type=int, default=30, help="Email and letters from the last N days (default 30)")
    oi.add_argument("--json", action="store_true", help="Print JSON")
    oi.set_defaults(func=cmd_open_items)

    rl = sub.add_parser("request-links", help="PayHOA requests beside their email; drafts for emailed requests PayHOA does not have")
    _add_common(rl)
    rl.add_argument("--limit", type=int, default=25, help="Requests and drafts to list")
    rl.add_argument("--create", default="", metavar="THREAD_ID", help="Show the draft for this thread; with --yes, enter it in PayHOA")
    rl.add_argument("--message", default="", help="With --create: the request's message (the owner's request in full)")
    rl.add_argument("--notify-owner", action="store_true", help="With --create: have PayHOA notify the owner")
    rl.add_argument("--yes", action="store_true", help="With --create: enter the request (it is never approved, denied, or assigned)")
    rl.add_argument("--json", action="store_true", help="Print JSON")
    rl.set_defaults(func=cmd_request_links)

    ib = sub.add_parser("inbox", help="What each email asks (complaint, maintenance, information, billing, question) and where the answer is")
    _add_common(ib)
    ib.add_argument("--intent", default="", help='Only one intent: "complaint", "question", "maintenance request", "request for information or records"')
    ib.add_argument("--days", type=int, default=365, help="Threads active in the last N days (default 365)")
    ib.add_argument("--limit", type=int, default=30, help="Threads to list")
    ib.add_argument("--json", action="store_true", help="Print JSON")
    ib.set_defaults(func=cmd_inbox)

    cs = sub.add_parser("case", help="One matter across the stores by its words (a name, an address, a case or claim number)")
    _add_common(cs)
    cs.add_argument("terms", nargs="+", help='Words that name the matter, e.g. "water intrusion" smith 24CV000123')
    cs.add_argument("--json", action="store_true", help="Print JSON")
    cs.set_defaults(func=cmd_case)

    rp = sub.add_parser("replies", help="Reply rates learned from the association's own replies; open threads that likely need one")
    _add_common(rp)
    rp.add_argument("--days", type=int, default=120, help="Open threads with a message in the last N days (default 120)")
    rp.add_argument("--limit", type=int, default=40, help="Open threads to list")
    rp.add_argument("--json", action="store_true", help="Print JSON")
    rp.set_defaults(func=cmd_replies)

    pm = sub.add_parser("permit-status", help="The association's permits in Citizen Access: status, fees, workflow, conditions (read-only)")
    _add_common(pm)
    pm.add_argument("--sync", action="store_true", help="Sign in (Keeper record accela_record_uid) and read the collection first")
    pm.add_argument("--all", action="store_true", help="With --sync: read closed records in full too")
    pm.add_argument("--number", default="", help="Only this permit number, e.g. COM-2616861")
    pm.add_argument("--json", action="store_true", help="Print JSON")
    pm.set_defaults(func=cmd_permit_status)

    sources = sub.add_parser("sources", help="The association's counterparties: senders and payees by kind of source, other associations, unnamed letterheads")
    _add_common(sources)
    sources.add_argument("--json", action="store_true", help="Print JSON")
    sources.set_defaults(func=cmd_sources)

    books = sub.add_parser("books", help="The books from PayHOA's general ledger: profit and loss, months, vendors, cash flow, balances, queries")
    _add_common(books)
    books.add_argument("report", nargs="?", default="pl", choices=("pl", "months", "vendors", "cashflow", "balances", "receivables", "check", "query"))
    books.add_argument("--sync", action="store_true", help="Read new months and the last four again from PayHOA first")
    books.add_argument("--full", action="store_true", help="Read every month again from PayHOA first")
    books.add_argument("--start", default="", help="YYYY-MM-DD (default January 1 of the ledger's last year)")
    books.add_argument("--end", default="", help="YYYY-MM-DD (default the ledger's last day)")
    books.add_argument("--kind", default="expense", help="months: expense or income")
    books.add_argument("--text", default="", help="query: words in the description or memo")
    books.add_argument("--payee", default="", help="query: payee name")
    books.add_argument("--category", default="", help="query: category")
    books.add_argument("--account", default="", help="query: account (bank account or category)")
    books.add_argument("--min", type=float, default=None, help="query: smallest amount in dollars")
    books.add_argument("--max", type=float, default=None, help="query: largest amount in dollars")
    books.add_argument("--owners", action="store_true", help="balances, query: include the units' own accounts (confidential)")
    books.add_argument("--limit", type=int, default=200, help="rows to show")
    books.add_argument("--json", action="store_true", help="Print JSON")
    books.set_defaults(func=cmd_books)

    cases = sub.add_parser("cases", help="The association's legal matters and each statutory duty's standing (confidential)")
    cases.add_argument("--json", action="store_true", help="Print JSON")
    cases.add_argument("--fetch-files", action="store_true",
                       help="Download each case's Drive folder (read-only) into data/cases/<key> and write a text extract beside each PDF (text layer, then local OCR); jason index --build makes the text searchable as the case's own confidential catalog")
    cases.add_argument("--extract-text", action="store_true",
                       help="Write a text extract (<name>.pdf.txt) beside each fetched case file that has none or whose file changed: the text layer, else local OCR for scanned pages; prints the counts and lists what no reader could read. Held-back files are never read")
    cases.add_argument("--vision", action="store_true",
                       help="With --extract-text: read the scanned pages with the local vision model (preflight and the GPU lock first)")
    cases.add_argument("--case", default="", help="With --fetch-files or --extract-text: only this case (its key or case number)")
    cases.add_argument("--include-held", action="store_true",
                       help="With --fetch-files: also put on disk the medical and veterinary records the case holds back, for a person to read; they are never extracted or indexed")
    cases.set_defaults(func=cmd_cases)

    features = sub.add_parser("google-features", help="Check whether the Docs API's suggested edits and anchored comments are generally available")
    features.add_argument("--json", action="store_true", help="Print JSON")
    features.set_defaults(func=cmd_google_features)

    board = sub.add_parser("board", help="The board's action items; draft the next agenda and minutes from the last agenda Doc; sync the board's Sheet")
    _add_common(board)
    board.add_argument("--all", action="store_true", help="Include closed items")
    board.add_argument("--set", default="", help="An item id whose board fields to change (with --status, --owner, --meeting, --notes)")
    board.add_argument("--status", default="", help="open, proposed, on agenda, in progress, deferred, closed")
    board.add_argument("--owner", default="")
    board.add_argument("--meeting", default="", help="The meeting an item is noticed for")
    board.add_argument("--notes", default="")
    board.add_argument("--refresh-reports", action="store_true", help="with --packet: run each report the items name before building (otherwise each shows its last run: jason report --list)")
    board.add_argument("--packet", action="store_true", help="Write the board packet for the next meeting: each open-session item researched")
    board.add_argument("--audience", choices=("directors", "members"), default="directors",
                       help="With --packet: the directors' confidential packet (default), or the members' copy "
                            "(packet-<date>-members.md: no draft motions, option briefs, privileged or executive material, or "
                            "records above P1; what it leaves out is listed by item)")
    board.add_argument("--by", default="", metavar="NAME",
                       help="With --packet --audience members: the person asking; puts the copy in approvals and requests "
                            "approval from the officer the specification names. Without it, only the draft is written")
    board.add_argument("--agenda", default="", help="Draft the next agenda from this agenda Google Doc id (read-only)")
    board.add_argument("--members", action="store_true",
                       help="Read the members PayHOA tags 'Board Member' (current and archived) into data/payhoa/board-members.json")
    board.add_argument("--minutes", default="", metavar="DATE",
                       help="Draft the minutes of the board meeting on DATE from its Zoom record with the local model (open meeting only)")
    board.add_argument("--recheck", action="store_true",
                       help="With --minutes: count the quorum and find confidential subjects in the draft already written; "
                            "no model")
    board.add_argument("--date", default="", help="The meeting date (default: the next third Tuesday)")
    board.add_argument("--previous", default="", help="The previous meeting's date, for the minutes to approve")
    board.add_argument("--directors", default="", help="Comma-separated directors for the minutes template")
    board.add_argument("--tech-contact", default="", help="Name, telephone, and email of the teleconference help (CIV 4926(a)(1)(B))")
    from jason.tasks.agenda_plan import FORMATS as MEETING_FORMATS

    board.add_argument("--format", default="", choices=MEETING_FORMATS,
                       help="With --agenda: how the meeting is held (default: the agenda plan's for the date; with none, "
                            "entirely by teleconference, said as assumed). Only 'teleconference' gets 4926's notice lines. "
                            "With --notice: required unless the agenda plan sets it")
    board.add_argument("--notice", action="store_true",
                       help="Draw the notice of the meeting (--date) from the base template: data/board/notices/notice-<date>.md, "
                            "its email body (.html), and the statutes recited (.refs.json); disk only, nothing sent")
    board.add_argument("--location", default="",
                       help="With --notice: the place (in person) or the physical location members may attend (hybrid, "
                            "CIV 4090(b)); default: the agenda plan's")
    board.add_argument("--ballots-counted", action="store_true",
                       help="With --notice: ballots are counted and tabulated at this meeting (CIV 5120), so it cannot be "
                            "held entirely by teleconference (4926(b))")
    board.add_argument("--notice-date", default="", metavar="YYYY-MM-DD",
                       help="With --notice: the day the notice is posted (default: the last day the notice period allows)")
    board.add_argument("--sheet", nargs="?", const="spec", default="",
                       help="Sync with the board's Google Sheet (the specification's, or this id); reads the board's edits first")
    board.add_argument("--create-sheet", action="store_true", help="Create the board's Sheet (a new private file) and print its id")
    board.add_argument("--tasks", action="store_true",
                       help="Keep the items as a Google Tasks list; a task checked off closes its item (first run needs --interactive)")
    board.add_argument("--doc", action="store_true",
                       help="With --agenda, fill the agenda template into a Doc; with --packet, write the packet to a Doc (needs --yes)")
    board.add_argument("--preview", action="store_true", help="With --agenda --doc, put the Doc in My Drive/Templates as a preview")
    board.add_argument("--yes", action="store_true", help="Confirm writing to Drive")
    board.add_argument("--json", action="store_true", help="Print JSON")
    board.set_defaults(func=cmd_board)

    centers = sub.add_parser("cost-centers", help="The annexations' two assessment cost centers against the charges, budget, and reserve studies")
    _add_common(centers)
    centers.add_argument("--json", action="store_true", help="Print JSON")
    centers.set_defaults(func=cmd_cost_centers)

    securities = sub.add_parser("securities", help="The developer's DRE securities by phase: agreements, bonds, releases, gaps (disk only)")
    _add_common(securities)
    securities.add_argument("--json", action="store_true", help="Print JSON")
    securities.set_defaults(func=cmd_securities)

    models = sub.add_parser("models", help="Read the library with the document models: typed records and findings per kind (disk only)")
    _add_common(models)
    models.add_argument("--kind", default="", help="One document kind (e.g. minutes, elevated_element_inspection)")
    models.add_argument("--file", default="", help="Read one file on disk (PDF or text) as --kind instead of the library")
    models.add_argument("--show", action="store_true", help="Print the stored readings (with --kind, one kind) instead of reading again")
    models.add_argument("--basis", action="store_true",
                        help="From the stored readings: per reader and finding code, what the check read (text, profile, store, today, "
                             "law), so which findings are ingestion and which are reviews; reads nothing again")
    models.add_argument("--as-of", default="", metavar="DATE",
                        help="From the stored readings' fields: make the as-of lens's findings again for DATE (YYYY-MM-DD: terms ended, "
                             "deadlines passed, what is due next), save them under data/reviews/documents, and print what changed since "
                             "the rows were stored; reads no document and leaves the stored readings as they are")
    models.add_argument("--lens", default="as-of", metavar="KEY",
                        help="With --as-of: the lens to make again. as-of (the default) reads the stored fields and the date; records "
                             "sets them against the association's other records as they are on disk now (the library, the ledger, "
                             "the logs) and is made again only for a reading whose other records changed")
    models.add_argument("--ask", action="store_true",
                        help="Ask the local model --kind's question set about each file and set its grounded answers beside the rule reader's")
    models.add_argument("--filed", action="store_true",
                        help="Read the documents filed to Drive from email (jason gmail --file-vendor) instead of the library: each "
                             "filing's local copy, its words from the text layer or local OCR, stored as a reading under "
                             "drive-<file id>; --kind names the kind (default inspection_report)")
    models.add_argument("--vision", action="store_true",
                        help="With --filed: read a scan with the local vision model (preflight and the GPU lock first)")
    models.add_argument("--refresh-text", action="store_true", help="With --filed: read each file's words again, not the cached text")
    models.add_argument("--confidential", action="store_true", help="--show, --as-of: include confidential files' fields")
    models.add_argument("--limit", type=int, default=50, help="--show: readings to print")
    models.add_argument("--json", action="store_true", help="Print JSON")
    models.set_defaults(func=cmd_models)

    reconcile = sub.add_parser("reconcile", help="PayHOA's bank reconciliations: coverage, statements against the ledger, items never cleared (read-only)")
    _add_common(reconcile)
    reconcile.add_argument("--fetch", action="store_true", help="Read every reconciliation and its report from PayHOA first")
    reconcile.add_argument("--json", action="store_true", help="Print JSON")
    reconcile.set_defaults(func=cmd_reconcile)

    ledger = sub.add_parser("ledger", help="Check the library's treasurer's reports against PayHOA's saved runs and month-end balance sheets")
    _add_common(ledger)
    ledger.add_argument("--fetch", action="store_true", help="Read the saved runs, month-end balance sheets, and chart of accounts from PayHOA first")
    ledger.add_argument("--download", action="store_true", help="With --fetch: save each run's PDF the library does not hold")
    ledger.add_argument("--json", action="store_true", help="Print JSON")
    ledger.set_defaults(func=cmd_ledger)

    reserves = sub.add_parser("reserves", help="Read the reserve studies; print next year's funding plan beside the budget and the reserve accounts")
    _add_common(reserves)
    reserves.add_argument("--year", type=int, default=0, help="Plan year (default next year)")
    reserves.add_argument("--fetch", action="store_true", help="With --transfers: read each year's budget from PayHOA first (read-only)")
    reserves.add_argument("--transfers", action="store_true", help="Money in and out of the reserve accounts: borrowings and their Civil Code 5515 record, reimbursements, catch-ups")
    reserves.add_argument("--json", action="store_true", help="Print JSON")
    reserves.set_defaults(func=cmd_reserves)

    utilities = sub.add_parser("utilities", help="Parse the SMUD and City bills; print accounts and meters, abnormal usage, and next year's cost")
    _add_common(utilities)
    utilities.add_argument("--no-sync", action="store_true", help="Read the store without parsing new PDFs")
    utilities.add_argument("--full", action="store_true", help="Re-parse every PDF, not only new or changed ones")
    utilities.add_argument("--year", type=int, default=0, help="Forecast year (default next year)")
    utilities.add_argument("--water-increase", type=float, default=0.0,
                           help="Scenario: raise City water charges by this fraction from July 1, 2027 (0.1 = 10%%); not an adopted rate")
    utilities.add_argument("--since", default="", help="List anomalies from this date (YYYY-MM-DD; default about 13 months back)")
    utilities.add_argument("--account", default="", help="Print one account's usage bill by bill instead of the brief")
    utilities.add_argument("--service", default="", help="With --account: electric, water_domestic, or water_irrigation")
    utilities.add_argument("--payments", action="store_true",
                           help="Audit the PayHOA utility payments: attached PDF, bills paid, split by budget line, paid twice")
    utilities.add_argument("--fetch", action="store_true", help="With --payments: read the transactions and download their attachments first")
    utilities.add_argument("--all", action="store_true", help="With --payments: list clean payments too")
    utilities.add_argument("--limit", type=int, default=60, help="With --payments: payments to list, newest first")
    utilities.add_argument("--json", action="store_true", help="Print JSON")
    utilities.set_defaults(func=cmd_utilities)

    pests = sub.add_parser("pests", help="The pest control program from the vendor portal: products by EPA number, "
                                         "labels and safety data sheets, rodent monitoring, visits, inspections")
    _add_common(pests)
    pests.add_argument("--key", default="proactive", help="The vendor portal (mystique/vendors.py)")
    pests.add_argument("--fetch", action="store_true", help="Download each product's registration, label, and safety data sheet")
    pests.add_argument("--json", action="store_true", help="Print JSON")
    pests.set_defaults(func=cmd_pests)

    policies = sub.add_parser("policies", help="Each insurance policy term by term from its declarations (Drive, the library, email), "
                                               "beside the policy sheet and the specification")
    _add_common(policies)
    policies.add_argument("--fetch", action="store_true", help="Read the policy sheet and fetch each policy's papers from Drive first")
    policies.add_argument("--stored", action="store_true", help="Print the last run instead of reading again")
    policies.add_argument("--policy", help="One policy: master, umbrella, fidelity, directors-and-officers, flood-3, ...")
    policies.add_argument("--json", action="store_true", help="Print JSON")
    policies.set_defaults(func=cmd_policies)

    incidents = sub.add_parser("incidents", help="The maintenance history and insurance claims read from the repair paperwork "
                                                 "(PayHOA, email, library, Drive), by unit and building")
    _add_common(incidents)
    incidents.add_argument("--fetch", action="store_true", help="First download the Drive folders mystique/incidents.py names")
    incidents.add_argument("--stored", action="store_true", help="Print the last run instead of reading again")
    incidents.add_argument("--building", type=int, help="Only events on this building (1-8)")
    incidents.add_argument("--address", help="Only events at a unit whose address has these words (\"123 Main\")")
    incidents.add_argument("--work", choices=("repair", "maintenance", "improvement", "inspection"),
                           help="Only events with this kind of work (the maintenance history)")
    incidents.add_argument("--claims", action="store_true", help="Only events an insurance claim is tied to")
    incidents.add_argument("--standing", choices=("claimed", "claim candidate", "under deductible", "sudden, cost unknown"),
                           help="Only events in this standing against the master policy's deductible")
    incidents.add_argument("--cause", help="Only events whose cause has these words (\"roof leak\", \"vehicle\")")
    incidents.add_argument("--since", help="Only events that ran on or after this day (YYYY-MM-DD)")
    incidents.add_argument("--all", action="store_true", help="Include routine upkeep and inspections with no claim or sudden cause")
    incidents.add_argument("--private", action="store_true", help="Show the claims' and losses' snippets")
    incidents.add_argument("--link", action="store_true", help="Search Drive, Gmail (headers), the ledger, the library, and the mail "
                                                              "for each event's related documents; fetch new ones and read again")
    incidents.add_argument("--links", action="store_true", help="Print the stored related documents")
    incidents.add_argument("--no-ocr", action="store_true", help="Read text layers only (skip OCR of scans)")
    incidents.add_argument("--limit", type=int, default=80)
    incidents.add_argument("--json", action="store_true", help="Print JSON")
    incidents.set_defaults(func=cmd_incidents)

    vendors = sub.add_parser("vendors", help="Vendor customer portals (ProActive): sync visits, products, files, and "
                                             "invoices with the Keeper record, and verify them against PayHOA")
    _add_common(vendors)
    vendors.add_argument("--key", default="", help="One portal from mystique/vendors.py (default every portal)")
    vendors.add_argument("--sync", action="store_true", help="Sign in and download what is new (non-interactive with the Keeper record)")
    vendors.add_argument("--full", action="store_true", help="With --sync: download every invoice and file again")
    vendors.add_argument("--verify", action="store_true", help="Match PayHOA payments to the portal's payments and attached invoices")
    vendors.add_argument("--visits", type=int, default=5, help="Latest visits to print per property")
    vendors.add_argument("--limit", type=int, default=40, help="With --verify: findings to print")
    vendors.add_argument("--json", action="store_true", help="Print JSON")
    vendors.set_defaults(func=cmd_vendors)

    accounts = sub.add_parser("accounts", help="Print the bank balances from the last `jason budget` snapshot")
    _add_common(accounts)
    accounts.add_argument("--json", action="store_true", help="Print JSON")
    accounts.set_defaults(func=cmd_accounts)

    library = sub.add_parser("library", help="Classify the PayHOA document library (names, text, a local model), store it in data/library, and write library.md")
    _add_common(library)
    library.add_argument("--fetch", action="store_true", help="Download from PayHOA every file not already on disk (not templates or images)")
    library.add_argument("--model", nargs="?", const="", default=None, help="Ask a local Ollama model about files no rule placed (default model when no name is given)")
    library.add_argument("--refresh-text", action="store_true", help="Read every file's text again instead of the cache")
    library.add_argument("--score", action="store_true", help="Score the phrase rules (or --model) against the name rules instead of ingesting")
    library.add_argument("--per-kind", type=int, default=0, help="With --score, sample at most this many files of each kind")
    library.add_argument("--vision", default="", help="Read these kinds' files (comma-separated) again with the local vision model, as a second text layer")
    library.add_argument("--pages", type=int, default=0, help="With --vision, read only the first N pages (default: every page)")
    library.add_argument("--limit", type=int, default=0, help="With --vision, at most this many files")
    library.set_defaults(func=cmd_library)

    digest = sub.add_parser("digest", help="What the board should know now: what recorded, owners in default, releases owed, the association's liens")
    _add_common(digest)
    digest.add_argument("--since", default="", help="YYYY-MM-DD (default: --days ago)")
    digest.add_argument("--days", type=int, default=30, help="Look back this many days when --since is not given")
    digest.add_argument("--json", action="store_true", help="Print JSON")
    digest.set_defaults(func=cmd_digest)

    watch = sub.add_parser("title-watch", help="Where each lien on a unit's owners stands against the title today")
    _add_common(watch)
    watch.add_argument("--apn", default="", help="One unit")
    watch.add_argument("--standing", default="", help="One standing, such as STANDS, IN_DEFAULT, RELEASE_DUE, LAPSED")
    watch.add_argument("--attention", action="store_true", help="Only the standings a person acts on")
    watch.add_argument("--json", action="store_true", help="Print JSON")
    watch.set_defaults(func=cmd_title_watch)

    duties = sub.add_parser("duties", help="Write records.md (the Civil Code 5200 inventory) and duties.md (the duty briefs with the documents' passages); --brief prints one duty; --documents KEY lists the norms a governing document states")
    _add_common(duties)
    duties.add_argument("--brief", default="", help="Print the brief for one duty anchor, such as \"Assessments\"")
    duties.add_argument("--json", action="store_true", help="Print JSON")
    from jason.commands.document_duties import add_arguments as _document_duty_arguments

    _document_duty_arguments(duties)
    duties.set_defaults(func=cmd_duties)

    records = sub.add_parser("records-request", help="List the recorded instruments the association's records lack, with the form fields and the county's copy cost")
    _add_common(records)
    records.add_argument("--pages", action="store_true", help="Read page counts from the county index now (one search and one detail per instrument)")
    records.add_argument("--governing-only", action="store_true", help="Governing instruments only; leave out the association's liens and notices")
    records.set_defaults(func=cmd_records_request)

    recent = sub.add_parser("recent-filings", help="What recorded on or after a date that touches a unit, an owner, or the association, with what to do")
    _add_common(recent)
    recent.add_argument("--since", required=True, help="YYYY-MM-DD")
    recent.add_argument("--json", action="store_true", help="Print JSON")
    recent.set_defaults(func=cmd_recent_filings)

    county = sub.add_parser(
        "county-report",
        help="Create one spreadsheet: ownership, deed history, association taxes, sale prices, taxes due",
    )
    _add_common(county)
    county.add_argument(
        "--local",
        action="store_true",
        help="Read the ownership and tax databases and print tab counts. Do not publish",
    )
    county.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the new spreadsheet",
    )
    county.set_defaults(func=cmd_county_report)

    violations = sub.add_parser(
        "violations",
        help="Pull outstanding violations and a second broader status",
    )
    _add_common(violations)
    violations.set_defaults(func=cmd_violations)

    notes = sub.add_parser(
        "notes",
        help="Unit and member notes (not request notes)",
    )
    _add_common(notes)
    notes.add_argument("--unit", dest="unit_id", type=int)
    notes.add_argument("--member", dest="membership_id", type=int)
    notes.set_defaults(func=cmd_notes)

    comms = sub.add_parser(
        "communications",
        help="Email, SMS, and mail history for one recipient id",
    )
    _add_common(comms)
    comms.add_argument("--recipient", dest="recipient_id", type=int, required=True)
    comms.set_defaults(func=cmd_communications)

    vendors = sub.add_parser(
        "vendor-matches",
        help="Match unreviewed bank transactions to vendors, excluding SMUD and City of Sacramento",
    )
    _add_common(vendors)
    vendors.set_defaults(func=cmd_vendor_matches)

    review = sub.add_parser(
        "review-requests",
        help="Match open maintenance and architectural requests to document names",
    )
    _add_common(review)
    review.add_argument(
        "--apply-tag",
        help="Tag each reviewed request with this label (no tag unless set)",
    )
    review.add_argument("--tag-color", default="#7A64C8")
    review.set_defaults(func=cmd_review_requests)

    request_comment = sub.add_parser(
        "request-comment",
        help="Post a comment and notify the reporter and unit owners",
    )
    _add_common(request_comment)
    request_comment.add_argument("request_id", type=int)
    request_comment.add_argument("message")
    request_comment.add_argument(
        "--no-notify",
        action="store_true",
        help="Post the comment without notifying the reporter or owners",
    )
    request_comment.add_argument(
        "--notify-admins",
        action="store_true",
        help="Also tell admins about the comment",
    )
    request_comment.set_defaults(func=cmd_request_comment)

    request_note = sub.add_parser(
        "request-note",
        help="Post an internal note. Private unless --public",
    )
    _add_common(request_note)
    request_note.add_argument("request_id", type=int)
    request_note.add_argument("note")
    request_note.add_argument(
        "--public",
        action="store_true",
        help="The note is not private",
    )
    request_note.set_defaults(func=cmd_request_note)

    request_attach = sub.add_parser(
        "request-attach",
        help="Attach a local file to a request. Does not notify the owner unless asked",
    )
    _add_common(request_attach)
    request_attach.add_argument("request_id", type=int)
    request_attach.add_argument("path")
    request_attach.add_argument(
        "--notify",
        action="store_true",
        help="Tell the owner about the file",
    )
    request_attach.set_defaults(func=cmd_request_attach)

    request_files = sub.add_parser(
        "sync-request-files",
        help="Download request attachments, comments, and internal notes",
    )
    _add_common(request_files)
    request_files.add_argument(
        "--requests",
        dest="request_ids",
        help="Comma-separated submission ids (default: every request in the catalog)",
    )
    request_files.set_defaults(func=cmd_sync_request_files)

    sync_secured = sub.add_parser(
        "sync-secured",
        help="Copy secured-roll rows for community parcels into their own catalog",
    )
    _add_common(sync_secured)
    sync_secured.add_argument("roll", help="Path to the secured-roll workbook")
    sync_secured.add_argument(
        "--parcel",
        help="One parcel number (default: every community parcel)",
    )
    sync_secured.set_defaults(func=cmd_sync_secured)

    sync_tax = sub.add_parser(
        "sync-tax",
        help="Sync Sacramento County property tax for community parcels into the local catalog",
    )
    _add_common(sync_tax)
    sync_tax.add_argument(
        "--parcel",
        help="One parcel number (default: every community parcel)",
    )
    sync_tax.set_defaults(func=cmd_sync_tax)

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

    sync_smud = sub.add_parser("sync-smud", help="Sync SMUD bill history, payments, and usage into the smud cache (download only)")
    _add_common(sync_smud)
    sync_smud.add_argument("--account", help="Single account number (default: every linked account)")
    sync_smud.add_argument("--full", action="store_true", help="Read the whole history again, not only what is new")
    sync_smud.set_defaults(func=cmd_sync_smud)

    fetch_bills = sub.add_parser("fetch-bills", help="Download new SMUD and City (i-doxs) bills and parse them into the utility "
                                                     "store; nothing goes to PayHOA")
    _add_common(fetch_bills)
    fetch_bills.add_argument("--source", choices=BILL_PORTALS, help="One portal (default: both)")
    fetch_bills.add_argument("--account", help="Single account number (default: every account)")
    fetch_bills.add_argument("--full", action="store_true", help="Read each portal's whole history again")
    fetch_bills.add_argument("--no-parse", action="store_true", help="Download only; leave the utility store as it is")
    fetch_bills.set_defaults(func=cmd_fetch_bills)

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
        choices=_bill_sources(),
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

    # Commands that live in their own modules (jason.commands.*): each has register(sub, add_common, agent_factory).
    from jason.commands import register_all

    register_all(sub, _add_common, _agent)

    return parser


def _apply_temp_dir(args: argparse.Namespace) -> None:
    """Put JASON_TEMP_DIR into effect before the command runs (jason.config.apply_temp_dir). A command that reports on the
    setting (``jason storage``) sets ``reports_temp_dir`` and meets a folder that cannot be used itself."""
    from jason.config import TempDirError, apply_temp_dir

    try:
        apply_temp_dir(getattr(args, "env", None))
    except TempDirError:
        if not getattr(args, "reports_temp_dir", False):
            raise


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        _apply_temp_dir(args)
        code = args.func(args)
    except Exception as exc:  # noqa: BLE001 — CLI surface
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    raise SystemExit(code)


if __name__ == "__main__":
    main()
