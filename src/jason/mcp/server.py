"""Stdio MCP tools over the local catalog and the deed chain.

No Keeper, PayHOA, or Google calls. Deed tools read the ownership store and
the extracts on disk. Recorder tools search the county's public index. A
search hit is not a pin. Tax search reads the public account index and does
not download bills. Secured tools read the stored roll and the bulk workbook.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jason.catalog import PayhoaCatalog
from jason.config import Settings
from jason.mcp.governance import TOOLS as GOVERNANCE_TOOLS
from jason.mcp.index import recorder_around, recorder_descend, recorder_detail, recorder_priors, recorder_search
from jason.mcp.rolls import (
    secured_parcel,
    secured_roll,
    secured_search,
    secured_status,
    tax_account,
    tax_reassessments,
    tax_search,
    tax_status,
    unit_characteristics,
)
from jason.mcp.county import (
    association_records,
    audit_chains,
    anythingllm_query,
    manager_context,
    anythingllm_status,
    assessment_liens,
    document_readings,
    extraction_scorecard,
    passage_search,
    read_document,
    read_scan,
    records_inventory,
    records_request,
    duty_brief,
    escrow_brief,
    explain_filing,
    authorities,
    index_coverage,
    index_survey,
    lifecycle_of,
    recent_filings,
    association_collections,
    bank_accounts,
    budget_status,
    books_report,
    invoice_review,
    ledger_query,
    ledger_validation,
    bank_reconciliations,
    reserve_transfers,
    document_models,
    document_references,
    jobs_status,
    developer_securities,
    cost_centers,
    board_items,
    legal_cases,
    mail_brief,
    mail_checks,
    counterparties,
    insurance_review,
    association_calendar,
    vendor_contacts,
    document_copies,
    record_locations,
    email_threads,
    party_brief,
    request_links,
    email_intents,
    case_file,
    reply_needed,
    permits,
    thread_topics,
    new_owners,
    open_items,
    mail_item,
    zoom_meetings,
    zoom_meeting,
    hearings,
    meeting_records,
    reserve_study,
    utility_accounts,
    utility_brief,
    utility_payments,
    utility_usage,
    vendor_portal,
    pest_program,
    incident_history,
    insurance_policies,
    library_search,
    library_status,
    library_text,
    board_digest,
    title_watch,
    unit_brief,
    mechanics_liens,
    parcel_liens,
    solar_status,
    unit_number,
    compare_parties,
    county_status,
    expand_deed_anchors,
    list_developers,
    list_public_reports,
    ownership_record,
    pinned_chain,
    read_deed,
    search_ownership,
)


def _settings() -> Settings:
    return Settings.load()


def _catalog() -> PayhoaCatalog:
    return PayhoaCatalog(_settings().payhoa_catalog)


def catalog_status() -> dict[str, Any]:
    settings = _settings()
    with _catalog() as catalog:
        return {"orgId": settings.payhoa_org_id, "counts": catalog.counts(settings.payhoa_org_id)}


def search_requests(
    status: str | None = None,
    form_name: str | None = None,
    unit_id: int | None = None,
    text: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    settings = _settings()
    with _catalog() as catalog:
        return catalog.search_requests(
            settings.payhoa_org_id,
            status=status,
            form_name=form_name,
            unit_id=unit_id,
            text=text,
            limit=limit,
        )


def search_documents(
    path_prefix: str | None = None,
    name_contains: str | None = None,
    files_only: bool = True,
    limit: int = 100,
) -> list[dict[str, Any]]:
    settings = _settings()
    with _catalog() as catalog:
        return catalog.search_documents(
            settings.payhoa_org_id,
            path_prefix=path_prefix,
            name_contains=name_contains,
            files_only=files_only,
            limit=limit,
        )


def get_request_local_export(request_id: int) -> dict[str, Any]:
    """Comments, notes, and attachment names already saved by sync-request-files."""
    root = _settings().payhoa_catalog.parent / "payhoa-files" / "requests" / str(request_id)
    if not root.is_dir():
        return {"requestId": request_id, "found": False, "files": []}
    files = sorted(path.name for path in root.iterdir() if path.is_file())

    def _json(name: str) -> Any:
        path = root / name
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    return {
        "requestId": request_id,
        "found": True,
        "files": files,
        "comments": _json("comments.json"),
        "notes": _json("notes.json"),
    }


def read_exported_file(request_id: int, name: str, *, max_bytes: int = 262144) -> dict[str, Any]:
    """Read one file from a request export. Rejects paths outside that folder."""
    root = (_settings().payhoa_catalog.parent / "payhoa-files" / "requests" / str(request_id)).resolve()
    path = (root / Path(name).name).resolve()
    if path.parent != root or not path.is_file():
        raise FileNotFoundError(name)
    data = path.read_bytes()[:max_bytes]
    if path.suffix.lower() == ".json" or data.startswith(b"{") or data.startswith(b"["):
        return {"name": path.name, "text": data.decode("utf-8", errors="replace")}
    return {"name": path.name, "bytes": len(data)}


def _working_directory() -> None:
    """Run from the project: ``JASON_CWD`` when a client sets it, else the folder that holds ``.env``.

    An MCP client such as AnythingLLM launches the server from its own
    folder, and the stores are addressed as ``data/...`` from the project.
    """
    import os

    from jason.config import resolve_env_path

    target = os.environ.get("JASON_CWD") or str(resolve_env_path().parent)
    if target and Path(target).is_dir():
        os.chdir(target)


ALL_TOOLS = (
    catalog_status,
    search_requests,
    search_documents,
    get_request_local_export,
    read_exported_file,
    county_status,
    list_developers,
    list_public_reports,
    ownership_record,
    search_ownership,
    pinned_chain,
    compare_parties,
    read_deed,
    expand_deed_anchors,
    audit_chains,
    association_records,
    parcel_liens,
    unit_number,
    solar_status,
    mechanics_liens,
    index_survey,
    index_coverage,
    authorities,
    board_digest,
    association_collections,
    budget_status,
    bank_accounts,
    utility_brief,
    utility_usage,
    utility_accounts,
    utility_payments,
    vendor_portal,
    pest_program,
    incident_history,
    insurance_policies,
    reserve_study,
    invoice_review,
    ledger_validation,
    bank_reconciliations,
    reserve_transfers,
    document_models,
    document_references,
    jobs_status,
    developer_securities,
    cost_centers,
    board_items,
    legal_cases,
    books_report,
    ledger_query,
    mail_brief,
    mail_checks,
    counterparties,
    insurance_review,
    association_calendar,
    vendor_contacts,
    document_copies,
    record_locations,
    email_threads,
    party_brief,
    request_links,
    email_intents,
    case_file,
    reply_needed,
    permits,
    thread_topics,
    new_owners,
    open_items,
    mail_item,
    zoom_meetings,
    zoom_meeting,
    hearings,
    meeting_records,
    library_search,
    library_status,
    library_text,
    unit_brief,
    title_watch,
    escrow_brief,
    recent_filings,
    lifecycle_of,
    assessment_liens,
    explain_filing,
    read_document,
    document_readings,
    records_request,
    records_inventory,
    duty_brief,
    passage_search,
    extraction_scorecard,
    read_scan,
    anythingllm_query,
    manager_context,
    anythingllm_status,
    recorder_search,
    recorder_detail,
    recorder_around,
    recorder_descend,
    recorder_priors,
    tax_status,
    tax_account,
    tax_reassessments,
    tax_search,
    secured_status,
    secured_parcel,
    secured_search,
    secured_roll,
    unit_characteristics,
)

ALL_TOOLS = ALL_TOOLS + GOVERNANCE_TOOLS

# A profile is a named subset, in the order a client lists them. A small local model (AnythingLLM's agent) picks
# better from the board set: the digest, the briefs, and the law, not the research tools behind them.
PROFILES: dict[str, tuple[str, ...]] = {
    "board": (
        "board_digest", "title_watch", "association_collections", "budget_status", "bank_accounts", "utility_brief", "utility_payments", "vendor_portal", "pest_program", "incident_history", "insurance_policies", "reserve_study", "reserve_transfers", "invoice_review", "bank_reconciliations", "mail_brief", "zoom_meetings", "meeting_records", "hearings", "insurance_review", "association_calendar", "open_items", "party_brief", "unit_brief", "escrow_brief", "recent_filings", "lifecycle_of", "assessment_liens",
        "explain_filing", "solar_status", "unit_characteristics", "duty_brief", "records_inventory", "authorities",
        "records_request", "passage_search", "library_search", "manager_context",
    ),
    # The governance systems: the living documents, conflicts, intake questions, the schedule, members' requests, the
    # notice catalog and delivery, and the documents' duties. Three tools write a person's record to data/.
    "governance": tuple(tool.__name__ for tool in GOVERNANCE_TOOLS),
    # Onboarding by conversation (docs/onboarding.md): the session, its questions, and the two writes, with the
    # onboard and onboard_review prompts. A small set, so a local model picks the right tool.
    "onboarding": ("onboarding_status", "next_questions", "intake_questions", "answer_intake_question",
                   "onboarding_confirm"),
}


def tools_for(profile: str = "") -> tuple:
    """The tools a profile serves: every tool for "" or "all", else the named subset in its own order."""
    wanted = (profile or "all").strip().lower()
    if wanted == "all":
        return ALL_TOOLS
    if wanted not in PROFILES:
        raise SystemExit(f"unknown profile {profile!r}; choose all or " + ", ".join(sorted(PROFILES)))
    by_name = {tool.__name__: tool for tool in ALL_TOOLS}
    return tuple(by_name[name] for name in PROFILES[wanted])


def _profile() -> str:
    """``--profile NAME`` on the command line, else ``JASON_MCP_PROFILE``, else every tool."""
    import os
    import sys

    args = sys.argv[1:]
    if "--profile" in args:
        index = args.index("--profile")
        if index + 1 < len(args):
            return args[index + 1]
    return os.environ.get("JASON_MCP_PROFILE", "")


def build(profile: str = "", *, community: Any = None, data_dir: Path | None = None) -> Any:
    """The server for a profile: its tools; under ``all`` and ``governance`` the record addresses as resources
    (``jason.mcp.resources``); and under ``all``, ``governance``, and ``onboarding`` the onboarding prompts
    (``jason.mcp.prompts``)."""
    try:
        from mcp.server.mcpserver import MCPServer
    except ImportError as exc:
        raise SystemExit(
            'The mcp package is not installed. pip install -e ".[mcp]"'
        ) from exc
    from jason.mcp import prompts, resources

    server = MCPServer("jason")
    for tool in tools_for(profile):
        server.add_tool(tool)
    wanted = (profile or "all").strip().lower()
    if wanted in resources.PROFILES:
        resources.register(server, community=community, data_dir=data_dir)
    if wanted in prompts.PROFILES:
        prompts.register(server)
    return server


def main() -> None:
    _working_directory()
    build(_profile()).run(transport="stdio")
