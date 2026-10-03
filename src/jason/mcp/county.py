"""Local deed-chain tools. No recorder, PayHOA, Google, or Keeper calls.

The pool is the ownership store, the pinned community chain, and deed
extracts already on disk. ``expand_deed_anchors`` grows that pool out from
the pinned deeds and the developer grants. A parcel whose current document
joins an anchor is solved and drops out. The deeds that never join are the
candidates left to search.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jason.community.base import Developer
from jason.community.consideration import deed_price, granting_clause
from jason.community.history_report import followups
from jason.community.ownership import OwnershipRecord, OwnershipStore
from jason.community.recorder import (
    developer_for,
    Conveyance,
    OwnerName,
    document_numbers,
    expand_anchors,
    name_candidates,
)
from jason.community.tax import parcel_number
from jason.config import Settings


def county_status(data_dir: Path | None = None) -> dict[str, Any]:
    """How much local chain material is on disk.

    Counts the ownership rows, the pinned community deeds, the unit parcels
    that still have no current deed, and the deed extracts available to read.
    """
    root = _data_dir(data_dir)
    units = _units()
    with _store(root) as store:
        have = {_digits(record.apn) for record in store.records()}
        pinned = store.pinned_history()
    missing = [parcel_number(apn) for apn in units if _digits(apn) not in have]
    extracts = _deed_files(root)
    return {
        "ownershipRows": len(have),
        "pinnedDeeds": 0 if pinned is None else len(pinned.steps),
        "units": len(units),
        "unitsMissingDeed": missing,
        "deedExtracts": len(extracts),
    }


def list_public_reports() -> list[dict[str, Any]]:
    """Each Bureau file, its phase, and the pinned copies and annexations.

    ``assessmentCents`` is the monthly assessment. It is null when the
    Buildings tab left the amount blank. A related file is not the report.
    """
    from jason.community import mystique
    from jason.community.reports import catalog_reports

    community = mystique()
    catalog = catalog_reports(community.public_reports(), community.pins())
    return [_report(item) for item in catalog]


def _report(item) -> dict[str, Any]:
    report = item.report
    return {
        "fileNumber": report.file_number,
        "building": int(report.building),
        "phase": report.phase,
        "units": report.units,
        "developer": report.developer,
        "firstConveyance": report.first_conveyance.isoformat(),
        "opened": report.opened.isoformat() if report.opened else "",
        "issued": report.issued.isoformat() if report.issued else "",
        "annexation": report.annexation.isoformat() if report.annexation else "",
        "assessmentCents": report.assessment_cents,
        "copies": [_pin(row) for row in item.copies],
        "annexations": [_pin(row) for row in item.annexations],
        "related": [
            {"title": row.title, "driveId": row.drive_id, "role": row.role}
            for row in report.related
        ],
    }


def _pin(row) -> dict[str, str]:
    return {"title": row.title, "driveId": row.drive_id}


def list_developers() -> list[dict[str, Any]]:
    """The subdividers pinned on the community, and each index spelling."""
    from jason.community import mystique

    community = mystique()
    return [
        {"name": developer.name, "names": list(developer.names)}
        for developer in community.developers()
    ]


def ownership_record(apn: str, data_dir: Path | None = None) -> dict[str, Any]:
    """The assessor's current deed for one parcel, from the ownership store."""
    root = _data_dir(data_dir)
    with _store(root) as store:
        record = _find_record(store, apn)
    if record is None:
        return {"apn": parcel_number(apn), "found": False}
    return {"found": True, **_record(record)}


def search_ownership(name: str, data_dir: Path | None = None, limit: int = 40) -> list[dict[str, Any]]:
    """Current deeds whose grantor or grantee compares equal to ``name``.

    Equality is ``OwnerName``: the same spelling rules the chain uses, including
    a candidate abbreviation that accounts for every remaining word.
    """
    query = name.strip()
    if not query:
        return []
    root = _data_dir(data_dir)
    found: list[dict[str, Any]] = []
    with _store(root) as store:
        for record in store.records():
            parties = (*record.grantors, *record.grantees)
            if any(OwnerName(query) == party for party in parties):
                found.append(_record(record))
            if len(found) >= limit:
                break
    return found


def pinned_chain(data_dir: Path | None = None) -> dict[str, Any]:
    """The pinned community deeds, newest first, with gaps and cited unknowns."""
    root = _data_dir(data_dir)
    developers = _developers()
    with _store(root) as store:
        history = store.pinned_history(developers=developers)
    if history is None:
        return {"deeds": [], "followups": []}
    deeds = []
    for step in history.steps:
        item = step.conveyance
        deeds.append(
            {
                "number": item.number,
                "recorded": item.recorded.isoformat() if item.recorded else "",
                "grantors": list(item.grantors),
                "grantees": list(item.grantees),
                "priors": list(step.priors),
                "cited": list(step.cited),
                "developer": history.from_developer(item),
            }
        )
    rows = [
        {"kind": kind, "number": number, "detail": detail}
        for kind, number, detail in followups(history)
    ]
    return {"deeds": deeds, "followups": rows}


def compare_parties(left: str, right: str) -> dict[str, Any]:
    """Whether two party strings are one owner, and the abbreviation candidates.

    A candidate is a shorter token and the longer word it may stand for.
    The names compare equal only when a shared word anchors them and every
    other word is one of those pairs, or an earlier handoff rule already joins them.
    """
    pairs = name_candidates(left, right)
    return {
        "equal": OwnerName(left) == right,
        "candidates": [
            {"short": item.short, "long": item.long} for item in pairs
        ],
    }


def read_deed(number: str, data_dir: Path | None = None) -> dict[str, Any]:
    """Consideration and granting clause from a deed extract already on disk.

    The price is integer cents computed from the documentary transfer tax.
    A missing extract returns ``found`` false. The recorder is not called.
    """
    root = _data_dir(data_dir)
    path = _deed_file(root, number)
    if path is None:
        return {"number": number, "found": False}
    text = path.read_text(encoding="utf-8", errors="replace")
    price = deed_price(text)
    grantor, grantee = granting_clause(text)
    body: dict[str, Any] = {
        "number": number,
        "found": True,
        "file": path.name,
        "grantor": grantor,
        "grantee": grantee,
    }
    if price is None:
        body["priceCents"] = None
        body["exempt"] = False
        return body
    body["priceCents"] = price.price_cents
    body["exempt"] = price.exempt
    body["countyTaxCents"] = price.county_tax_cents
    body["cityTaxCents"] = price.city_tax_cents
    return body


def expand_deed_anchors(data_dir: Path | None = None) -> dict[str, Any]:
    """Place deeds out from the pinned chain until a current deed is solved.

    Each pass adds a deed that cites a placed deed, or whose parties hand off
    and whose APN does not name a different parcel. A deed that would join two
    parcels stays contested. Solved parcels drop out. ``remaining`` is the
    candidate pool for the next search. The stored unit chains are in the
    pool with their priors, so a resale already walked back to a developer is
    solved. A resale stays open until the deeds between it and an anchor are
    in the store.
    """
    root = _data_dir(data_dir)
    developers = _developers()
    with _store(root) as store:
        pinned = store.pinned_history(developers=developers)
        records = store.records()
        units = store.unit_histories(developers=developers)
    items: list[Conveyance] = []
    anchors: list[str] = []
    if pinned is not None:
        for step in pinned.steps:
            item = step.conveyance
            items.append(
                Conveyance(
                    item.number,
                    item.recorded,
                    item.grantors,
                    item.grantees,
                    step.priors,
                    item.apn,
                )
            )
            anchors.append(item.number)
    seen = {item.number for item in items}
    for history in units:
        for step in history.steps:
            item = step.conveyance
            if item.number in seen:
                continue
            seen.add(item.number)
            items.append(
                Conveyance(
                    item.number,
                    item.recorded,
                    item.grantors,
                    item.grantees,
                    step.priors,
                    item.apn,
                )
            )
    currents: list[tuple[str, str]] = []
    newest = {history.apn: history.steps[0].conveyance.number for history in units if history.steps}
    for record in records:
        if not record.conveys:
            # A death record moves no title. The chain's newest deed is the current conveyance.
            if record.apn in newest:
                currents.append((record.apn, newest[record.apn]))
            continue
        currents.append((record.apn, record.document_number))
        if record.document_number in seen:
            continue
        seen.add(record.document_number)
        items.append(
            Conveyance(
                record.document_number,
                record.document_date,
                record.grantors,
                record.grantees,
                (),
                record.apn,
            )
        )
    expansion = expand_anchors(
        tuple(items),
        anchors=tuple(anchors),
        currents=tuple(currents),
        developers=developers,
    )
    by_number = {item.number: item for item in items}
    return {
        "solved": [
            {"apn": parcel_number(apn), "current": number, "path": list(path)}
            for apn, number, path in expansion.solved
        ],
        "open": [
            {"apn": parcel_number(apn), "current": number}
            for apn, number in expansion.open_deeds
        ],
        "remaining": [_brief(by_number[number]) for number in expansion.remaining if number in by_number],
        "contested": [
            {"number": number, "links": list(links)}
            for number, links in expansion.contested
        ],
    }


def audit_chains(apn: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """Check every stored unit chain, or one parcel, against the other records.

    Each chain has to be in recording order, start at a pinned developer's
    grant inside the phase window of the parcel's building, land each
    reassessing deed on a bill year that left the 2% track, explain every
    sale-sized rise with a deed, and declare a price near the base the next
    bill enrolled. ``restorationYears`` are bill years most parcels rose in
    with no deed behind it; a rise there is a market restoration. A finding
    names the record to read next. It is not a verdict.
    """
    from jason.community import mystique
    from jason.community.audit import audit_chain, reassessing_steps
    from jason.community.base import assign_building
    from jason.community.calendar import community_restoration_years
    from jason.community.tax_store import TaxStore

    root = _data_dir(data_dir)
    community = mystique()
    developers = community.developers()
    reports = {report.building: report for report in community.public_reports()}
    ranges = community.buildings()
    with _store(root) as store:
        histories = store.unit_histories(developers=developers)
        current = {_digits(record.apn): record.document_date for record in store.records()}
    with TaxStore(root / "tax.db") as taxes:
        accounts = {_digits(history.apn): taxes.get(parcel_number(history.apn)) for history in histories}
    bills = {
        apn: tuple(account.bills) if account is not None else ()
        for apn, account in accounts.items()
    }
    restoration = community_restoration_years(
        tuple((bills[_digits(history.apn)], reassessing_steps(history)) for history in histories)
    )
    wanted = _digits(apn)
    prices = _prices(root, tuple(step.conveyance.number for history in histories for step in history.steps))
    parcels: list[dict[str, Any]] = []
    for history in histories:
        digits = _digits(history.apn)
        if wanted and digits != wanted:
            continue
        account = accounts.get(digits)
        building = assign_building(_situs(account.address), ranges) if account is not None else None
        report = reports.get(building.number) if building is not None else None
        audit = audit_chain(
            history,
            developers=developers,
            report=report,
            blocks=community.plan_blocks(),
            held=community.held_units(),
            bills=bills[digits],
            prices=prices,
            restoration_years=restoration,
            current_instrument=current.get(digits),
        )
        parcels.append(
            {
                "apn": parcel_number(history.apn),
                "phase": report.phase if report is not None else None,
                "steps": audit.steps,
                "reassessing": {str(year): number for year, number in sorted(audit.reassessing.items())},
                "findings": [
                    {"check": item.check, "detail": item.detail, "number": item.number, "year": item.year}
                    for item in audit.findings
                ],
            }
        )
    return {
        "checked": len(parcels),
        "clean": sum(1 for item in parcels if not item["findings"]),
        "restorationYears": sorted(restoration),
        "parcels": parcels,
    }


def association_records(data_dir: Path | None = None) -> dict[str, Any]:
    """The association's record in the index cache: governing instruments, liens, notices.

    Governing instruments are tied to the 2792.23 deliveries and to phases.
    ``placed`` are assessment liens the association recorded on owners and
    how each ended; ``against`` are liens and notices recorded against the
    association, such as utility liens and a tax-default notice. Nothing is
    searched; run the community name searches first to fill the cache.
    """
    from jason.community import mystique
    from jason.tasks.property_history import load_association_record

    record = load_association_record(mystique(), _data_dir(data_dir))
    return {
        "governing": [
            {"number": r.number, "recorded": r.recorded.isoformat() if r.recorded else "", "filing": r.filing, "role": r.role,
             "phase": r.phase, "delivery": r.delivery.value, "recordedBy": r.developer, "parties": list(r.parties), "cites": list(r.cites),
             "status": r.status, "supersededBy": r.superseded_by}
            for r in record.governing
        ],
        "deliveries": [
            {"delivery": s.delivery.value, "found": [r.number for r in s.records], "missing": list(s.missing)} for s in record.deliveries
        ],
        "placed": [_lifecycle(e) for e in record.placed],
        "against": [_lifecycle(e) for e in record.against],
        "notices": [{"number": i.number, "recorded": i.recorded.isoformat() if i.recorded else "", "filing": f"{i.filing_code} {i.filing_name}".strip()} for i in record.notices],
        "unplaced": [{"number": r.number, "recorded": r.recorded.isoformat() if r.recorded else "", "filing": r.filing, "recordedBy": r.developer} for r in record.unplaced],
    }


def parcel_liens(apn: str, data_dir: Path | None = None) -> dict[str, Any]:
    """Every lien, default, loan, or release lifecycle naming an owner of this parcel.

    A lien indexes a person, not a parcel. ``where`` says whether the
    lifecycle opened while that owner held this unit, is the association's
    own assessment lien, or belongs to another time or property.
    """
    from jason.tasks.property_history import load_parcel_histories
    from jason.community import mystique

    wanted = _digits(apn)
    for item in load_parcel_histories(mystique(), _data_dir(data_dir)):
        if _digits(item.apn) == wanted:
            return {
                "apn": parcel_number(item.apn),
                "address": item.address,
                "liens": [
                    {"owner": lien.owner, "where": lien.where, **_lifecycle(lien.encumbrance)} for lien in item.liens
                ],
            }
    return {"apn": parcel_number(apn), "found": False, "liens": []}


def read_document(path: str) -> dict[str, Any]:
    """What one recorded document's text says: the recorder's stamp (its own number, date, pages, fees),
    the title and phase, the declarant, the units and common areas an annexation covers, the instruments
    it cites with the relation stated (rescinds, amends, annexes under, relies on, plan, map), and the
    sections an amendment changes. A reading is evidence, not a pin; OCR can garble any of it."""
    from jason.community.readings import read_document as build, reading_dict

    target = Path(path)
    if not target.is_file():
        return {"path": path, "found": False}
    return {"found": True, **reading_dict(build(target))}


def document_readings(data_dir: Path | None = None) -> dict[str, Any]:
    """Every governing and annexation extract on disk read at once, with the supersessions the texts state and
    whether the specification pins each, and the instrument numbers the recorded copies carry."""
    from jason.community import mystique
    from jason.community.readings import numbers_on_disk, proposed_supersessions, read_folder, reading_dict

    root = _data_dir(data_dir)
    readings = read_folder(
        root / "artifacts" / "site-docs" / "governing_documents",
        root / "artifacts" / "site-docs" / "governing_documents_Annexations",
        root / "governing",
    )
    proposals = proposed_supersessions(readings, mystique().supersessions())
    return {
        "count": len(readings),
        "recordedCopies": {number: str(path) for number, path in numbers_on_disk(readings).items()},
        "supersessions": [{"number": p.number, "supersededBy": p.superseded_by, "phase": p.phase, "source": p.source, "pinned": p.pinned} for p in proposals],
        "readings": [reading_dict(r) for r in readings if r.readable],
        "unreadable": [str(r.path) for r in readings if not r.readable],
    }


def passage_search(query: str, k: int = 8, data_dir: Path | None = None, mode: str = "keyword") -> dict[str, Any]:
    """Find the passages in the governing documents, annexations, policies, and deed extracts that best match
    a question, ranked by BM25. A hit is a passage to read, with its file and place; it pins nothing. ``mode``
    "hybrid" fuses BM25 with the local embedder (qwen3-embedding:8b on Ollama, under the GPU lock) and puts passages
    carrying the question's exact numbers first; "exact" is BM25 with that boost and no model."""
    from jason.community import retrieval

    root = _data_dir(data_dir)
    folders = (
        root / "artifacts" / "site-docs" / "governing_documents", root / "artifacts" / "site-docs" / "governing_documents_Annexations",
        root / "artifacts" / "site-docs" / "governing_documents_Policies", root / "artifacts" / "site-docs" / "governing_documents_Resolutions",
        root / "governing",
    )
    try:
        hits = retrieval.search(query, *folders, k=max(1, min(int(k), 30)), data_dir=root, mode=mode or "keyword")
    except retrieval.EmbeddingUnavailable as exc:
        return {"query": query, "mode": mode, "available": False, "note": str(exc)}
    return {
        "query": query, **({"mode": mode} if mode and mode != "keyword" else {}), "count": len(hits),
        "hits": [{"file": hit.passage.title, "path": str(hit.passage.path), "passage": hit.passage.index,
                  "startWord": hit.passage.start_word, "score": hit.score, "text": hit.passage.text,
                  "section": getattr(hit.passage, "heading", "") or "",
                  "alsoIn": [str(p.path) for p in (getattr(hit, "also", None) or ())]} for hit in hits],
    }


def manager_context(task: str = "", subject: str = "", ask: str = "", draft: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """A professional community manager's context pack for a task: the base prompt (the order of authority under Civil
    Code 4205, working out what governs, the text over memory, the method, the privacy rules), the task's prompt (purpose,
    the topics it turns on, the kinds of documents to read, a manager's considerations; no section numbers or figures), and
    the sources retrieval found, numbered in order of authority (the law on hand by topic, then the declaration, articles, bylaws, rules and
    policies, then the association's records). ``task`` is a slug (insurance-change, flood-renewal, meeting-notice,
    annual-disclosures, treasurer-report, balance-forward, fire-system-testing, rule-reminder, hearing-notice,
    decision-notice, question); ``subject`` picks it from a template's subject instead. ``draft`` is text to review,
    ``ask`` a question. Work from the sources, cite them by id, and quote them; the pack decides nothing. Without a
    task, lists the tasks."""
    from jason.community import mystique
    from jason.community.prompts import TaskKind
    from jason.tasks.manager_review import build

    community = mystique()
    if not task and not subject:
        return {"tasks": [{"task": t.kind.slug, "what": t.kind.value, "audience": t.audience.value, "topics": list(t.topics),
                           "read": [k.value for k in t.documents], "consider": list(t.considerations)} for t in community.task_prompts()]}
    chosen = community.task_for_subject(subject) if subject else community.task_prompt(TaskKind.from_slug(task))
    if chosen is None:
        return {"found": False, "subject": subject, "note": "no task's subjects match; name the task"}
    pack = build(community, chosen, _data_dir(data_dir), ask=ask, draft=draft)
    return {"task": chosen.kind.slug, "sources": len(pack.sources), "gaps": pack.gaps, "pack": pack.markdown()}


def extraction_scorecard(extractor: str = "regex", model: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """Score a document reader against the pinned facts: the in-force annexation of each phase, its units and
    common area, the supersessions, and the numbers of the files whose names carry them. ``extractor`` is
    "regex" (the parsers over the extracts), "ollama" (a local vision model over the page images; ``model``
    names it, default qwen3.6:27b), or "claude" (needs the models extra and a key, else this says so and
    sends nothing)."""
    from jason.community import mystique
    from jason.community.extraction import RegexExtractor, cases, evaluate
    from jason.tasks.property_history import load_association_record

    community = mystique()
    root = _data_dir(data_dir)
    items = cases(community, load_association_record(community, root), root)
    if extractor == "claude":
        from jason.community.model_extractor import ClaudeExtractor, ExtractionUnavailable

        try:
            reader = ClaudeExtractor(model=model) if model else ClaudeExtractor()
            reader._connect()
        except ExtractionUnavailable as exc:
            return {"extractor": "claude", "available": False, "note": str(exc), "cases": len(items)}
    elif extractor == "ollama":
        from jason.community.ollama_extractor import OllamaExtractor, OllamaUnavailable

        try:
            reader = OllamaExtractor(model=model) if model else OllamaExtractor()
            reader.check()
        except OllamaUnavailable as exc:
            return {"extractor": "ollama", "available": False, "note": str(exc), "cases": len(items)}
    else:
        reader = RegexExtractor()
    card = evaluate(reader, items)
    return {"available": True, "caseFiles": [c.path.name for c in items], **card.as_dict()}


def anythingllm_query(question: str, catalog: str = "", workspace: str = "", mode: str = "query") -> dict[str, Any]:
    """Ask the local AnythingLLM catalogs. ``catalog`` is authorities (the law and DRE publications),
    association-records (the governing documents and public reports), or jason-pages (Jason's own pages,
    summaries only), mail, or a legal case's own catalog, case-<key> (e.g. case-sacramento-26cv016125: the case
    file from Drive; confidential, for directors and counsel, and never in the shared workspace); empty asks the shared
    Mystique workspace that holds the others. Each source says its
    catalog, so an answer resting on a summary is read as one. ``query`` answers only from the documents;
    ``chat`` keeps a thread. Needs ANYTHINGLLM_API_KEY, else this says so and sends nothing. An answer is
    evidence to read, and it pins nothing."""
    from jason.community import mystique
    from jason.community.anythingllm import AnythingLLM, AnythingLLMUnavailable
    from jason.tasks.anythingllm_sync import ask
    from jason.tasks.case_files import case_catalogs

    try:
        return ask(AnythingLLM(), question, workspace=workspace, catalog=catalog, mode=mode,
                   extra=case_catalogs(mystique().legal_cases()))
    except AnythingLLMUnavailable as exc:
        return {"available": False, "note": str(exc)}


def anythingllm_status() -> dict[str, Any]:
    """AnythingLLM as jason manages it: whether the app answers, its chat and embedding settings beside jason's
    (``drift``), each workspace's embedded documents and retrieval, the catalogs with no workspace, the workspaces no
    catalog owns, and the stored documents no workspace embeds, with ``findings`` saying what is wrong and the command
    that fixes it. Read-only: starting the app, applying settings, and re-embedding are `jason anythingllm` commands a
    person runs with --yes. Needs ANYTHINGLLM_API_KEY for everything past the ping."""
    from jason import anythingllm_admin as admin
    from jason.community import mystique
    from jason.community.anythingllm import AnythingLLM, AnythingLLMUnavailable
    from jason.tasks.anythingllm_sync import CATALOGS
    from jason.tasks.case_files import case_catalogs

    if not admin.online():
        return {"online": False, "findings": ["AnythingLLM is not answering: jason anythingllm --start --yes"]}
    try:
        client = AnythingLLM()
        current = admin.settings(client)
        inv = admin.inventory(client, (*CATALOGS, *case_catalogs(mystique().legal_cases())))
    except AnythingLLMUnavailable as exc:
        return {"online": True, "available": False, "note": str(exc)}
    return {"online": True, "settings": current, "drift": admin.drift(current), "inventory": inv,
            "findings": admin.findings(current, inv)}


def read_scan(path: str, model: str = "") -> dict[str, Any]:
    """Read one PDF's page images with a local vision model through Ollama (default qwen3.6:27b) into the
    concept records: stamp, title, phase, declarant, annexed property, citations with relation, sections.
    For the copies whose text layer is empty. Slow (a minute or two a document); a reading is evidence."""
    from jason.community.ollama_extractor import OllamaExtractor, OllamaUnavailable
    from jason.community.readings import reading_dict

    target = Path(path)
    if not target.is_file():
        return {"path": path, "found": False}
    reader = OllamaExtractor(model=model) if model else OllamaExtractor()
    try:
        reader.check()
    except OllamaUnavailable as exc:
        return {"path": path, "available": False, "note": str(exc)}
    return {"found": True, "available": True, "model": reader.model, **reading_dict(reader.extract(target))}


def authorities(citation: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """The words of the law Jason relies on, from the pages lawlibrary exported into data/authorities.

    With a citation such as "CIV 5200" the section's text, its heading, the session it comes from, and why Jason
    holds it. Without one, the exported pages and the pointers (Title 10 regulations, federal law, DRE publications)
    that must be read at their source. These pages are the authority; records.md and duties.md only summarize them."""
    from jason.community.authorities import pointers
    from jason.tasks.export_authorities import authority_pages, authority_text, read_manifest

    root = _data_dir(data_dir)
    if citation.strip():
        import re as _re

        from jason.community.succession import changes, now_at, successors

        number = _re.sub(r"^(?:Civil\s+Code|CIV)\b\.?\s*(?:Section|§)?\s*", "", citation.strip(), flags=_re.I)
        if _re.match(r"13[5-7]\d", number):
            # A former Davis-Stirling section: where the 2014 recodification put it, read from the Law Revision
            # Commission's tables (jason law-history --export); the text in force is at the successor.
            rows = successors(root, number)
            return {"citation": f"CIV {number}", "former": True, "nowAt": now_at(root, number),
                    "successors": [r.__dict__ for r in rows],
                    "caveats": ["Former Civil Code 1350-1378 was repealed by Stats. 2012, Ch. 180 (AB 805), operative January 1, "
                                "2014; each row names its source (the disposition table, a Commission Comment, or a similarity "
                                "candidate). Read the successor's text for the law in force."]}
        found = authority_text(root, citation)
        section = _re.sub(r"\(.*$", "", number).strip()
        history = changes(root, section)
        if history:
            found = {**found, "history": [{k: c.get(k) for k in ("after", "change", "statute", "bill", "effective", "operative", "summary")}
                                          for c in history]}
        return found
    manifest = read_manifest(root)
    # After an export the manifest says what is still only a pointer; before one, the registry does.
    listed = manifest.get("pointers") if manifest else [
        {"citation": a.citation, "shelf": a.shelf.value, "source": a.official, "why": a.why} for a in pointers()
    ]
    return {
        "session": manifest.get("session"), "exported": manifest.get("exported"),
        "pages": [{"citation": p.citation, "title": p.title, "sections": len(p.sections), "why": p.why} for p in authority_pages(root)],
        "pointers": list(listed or []),
    }


def index_coverage(examples: int = 4, data_dir: Path | None = None) -> dict[str, Any]:
    """Every cached index document read against the known processes: how many each process explains (chain
    steps, instruments beside them, the land chain, lien lifecycles, owner events, governing records, the
    association's filings, solar notices), and what is left sorted by pattern (a re-recording of a chain step,
    a companion transfer at a closing, an owner's other property, the developer's other projects, the
    developer's insolvency, nothing yet), with examples. "No process yet" is the list to model next."""
    from jason.community import mystique
    from jason.community.coverage import coverage
    from jason.community.index_cache import IndexCache
    from jason.community.ownership import OwnershipStore
    from jason.tasks.property_history import load_association_record, load_parcel_histories

    community = mystique()
    root = _data_dir(data_dir)
    histories = load_parcel_histories(community, root)
    record = load_association_record(community, root)
    with OwnershipStore(root / "ownership.db") as store:
        pinned = store.pinned_history(developers=community.developers())
    land = tuple(step.conveyance.number for step in (pinned.steps if pinned else ()))
    with IndexCache(root / "index-cache.db") as cache:
        numbers = [row["number"] for row in cache._conn.execute("SELECT number FROM documents")]
        docs = tuple(d for d in (cache.get(n) for n in numbers) if d is not None)
    result = coverage(
        histories, record, docs, developers=community.developers(), association=community.index_association(),
        project=community.index_project(), land_chain=land, examples=max(1, min(int(examples), 12)),
    )
    return result.as_dict()


def records_inventory(data_dir: Path | None = None) -> dict[str, Any]:
    """The association's records under Civil Code 5200: each kind with its citation, meaning, retention, where the
    specification keeps it (PayHOA folder, Drive sync rule, known file), how many files the catalog holds there, and
    the gap when nothing is pinned or nothing is on hand. The governing copies are listed with their recorded
    status. Reads disk only."""
    from jason.community import mystique
    from jason.tasks.association_pages import build_inventory, inventory_dicts
    from jason.tasks.property_history import load_association_record

    community = mystique()
    root = _data_dir(data_dir)
    holdings = build_inventory(community, root, governing=load_association_record(community, root).governing)
    return {"count": len(holdings), "gaps": [f"{h.kind.value}: {h.gap}" for h in holdings if h.gap], "records": inventory_dicts(holdings)}


def duty_brief(anchor: str, data_dir: Path | None = None) -> dict[str, Any]:
    """A brief for one of the manager's duty anchors (governing documents, developer file, notice, meetings,
    elections, records, annual disclosures, money, assessments, insurance, maintenance, exclusive use,
    architecture, protected uses, transfers, discipline, manager's own duties): the statute, the artifact, the
    records, the cadence, what Jason produces, the limit, and the passages the governing documents and the law
    notes give for its questions. A map for a person; it decides nothing."""
    from jason.tasks.association_pages import brief_for

    root = _data_dir(data_dir)
    return brief_for(anchor, root, root.parent / "docs" / "laws")


def records_request(fetch_pages: bool = False, include_liens: bool = True, data_dir: Path | None = None) -> dict[str, Any]:
    """The recorded instruments the association's record names and no recorded copy on disk carries, as a
    copy-order list for the county clerk/recorder: number, book and page, title, why it matters, page count,
    plain or certified, and the cost at the county's fees. ``fetch_pages`` reads page counts from the index now."""
    from jason.community import mystique
    from jason.community.records_request import MAIL_TO, ORDER_FORM, request_dicts
    from jason.tasks.property_history import load_association_record
    from jason.tasks.records_request import build_records_request

    community = mystique()
    root = _data_dir(data_dir)
    recorder = None
    if fetch_pages:
        from jason.community.recorder import Sacramento

        recorder = Sacramento.county_recorder
    report = build_records_request(community, root, load_association_record(community, root), fetch_pages=fetch_pages, recorder=recorder, include_liens=include_liens)
    return {
        "count": len(report.rows), "costCents": report.cost_cents, "pagesFetched": report.fetched_pages, "errors": report.errors,
        "orderForm": ORDER_FORM, "mailTo": MAIL_TO, "rows": request_dicts(report.rows),
        "note": "Fees and the form are as the county's page read on 2026-09-28; an estimated page count is marked.",
    }


def title_watch(apn: str = "", standing: str = "", attention: bool = False, data_dir: Path | None = None) -> dict[str, Any]:
    """Every recorded lien joined to a unit's owners, with where it stands against the title today: released,
    in default, a default gone quiet, standing against the current owner, the current owner's loan or solar lease,
    a prior owner's lien with no sale since, a release the association owes (Civil Code 5685), presumed paid at a
    sale, lapsed or expired, running with the land, or elsewhere. ``apn`` limits to one unit, ``standing`` to one
    standing by name (such as STANDS or RELEASE_DUE), ``attention`` to the ones a person acts on. Each row says
    when it names the owner by a bare name (a namesake risk) and which other units the same filing names.
    This is what the index shows, not a title report; a presumption is not a release."""
    from jason.community import mystique
    from jason.community.title import ATTENTION, LienStanding, standing_counts
    from jason.community.title import title_watch as watch
    from jason.tasks.property_history import load_parcel_histories

    histories = load_parcel_histories(mystique(), _data_dir(data_dir))
    wanted = _digits(apn)
    if wanted:
        histories = tuple(h for h in histories if _digits(h.apn) == wanted)
        if not histories:
            return {"apn": parcel_number(apn), "found": False}
    include: tuple[LienStanding, ...] = ()
    if standing.strip():
        key = standing.strip().upper().replace(" ", "_")
        if key not in LienStanding.__members__:
            return {"found": False, "standing": standing, "standings": [s.name for s in LienStanding]}
        include = (LienStanding[key],)
    elif attention:
        include = ATTENTION
    rows = watch(histories, include=include)
    if not wanted and not include:
        rows = tuple(row for row in rows if row.standing is not LienStanding.ELSEWHERE)
    return {
        "found": True, "counts": standing_counts(rows), "rows": [row.as_dict() for row in rows],
        "note": "what the index shows, not a title report; a presumption is not a release, and a release under another spelling can be missing",
    }


def unit_brief(apn: str, data_dir: Path | None = None) -> dict[str, Any]:
    """One unit on one page: title and chain, open liens while owning here, solar standing, taxes, members,
    owner events, audit findings, the home, and the value figures. Reads disk only.

    The brief carries its caveats: a lien indexes a person, an expired lien
    is still of record, a cure is not a release, no solar filing is not
    proof of purchase, and no value figure is an appraisal.
    """
    from jason.community import mystique
    from jason.community.briefs import unit_brief as build
    from jason.community.characteristics import CharacteristicsStore, classify_plan
    from jason.tasks.equity_charts import unit_values
    from jason.tasks.market_report import valuations
    from jason.tasks.property_history import load_parcel_histories

    community = mystique()
    root = _data_dir(data_dir)
    wanted = _digits(apn)
    histories = load_parcel_histories(community, root)
    item = next((h for h in histories if _digits(h.apn) == wanted), None)
    if item is None:
        return {"apn": parcel_number(apn), "found": False}
    unit = None
    if (root / "characteristics.db").is_file():
        with CharacteristicsStore(root / "characteristics.db") as store:
            unit = store.get(wanted)
    plan = classify_plan(unit, community.floor_plans(), item.developer) if unit is not None else None
    characteristics = {}
    if (root / "characteristics.db").is_file():
        with CharacteristicsStore(root / "characteristics.db") as store:
            characteristics = store.all()
    value = valuations(unit_values(histories, characteristics=characteristics, plans=community.floor_plans())).get(item.address)
    return {"found": True, **build(item, unit=unit, plan=plan, value=value)}


def escrow_brief(apn: str, data_dir: Path | None = None) -> dict[str, Any]:
    """What the association can tell escrow before a sale of this unit: its own assessment liens, defaults and
    sale notices of record, mechanic's liens with their standing, other open liens, the solar lease standing,
    taxes, deaths on title, the membership check, and the association's own open liens. Reads disk only.

    The brief says what the records show and what they cannot prove. It
    does not state a demand amount; PayHOA holds the ledger.
    """
    from jason.community import mystique
    from jason.community.briefs import escrow_brief as build
    from jason.tasks.property_history import load_association_record, load_parcel_histories

    community = mystique()
    root = _data_dir(data_dir)
    wanted = _digits(apn)
    item = next((h for h in load_parcel_histories(community, root) if _digits(h.apn) == wanted), None)
    if item is None:
        return {"apn": parcel_number(apn), "found": False}
    return {"found": True, **build(item, load_association_record(community, root))}


def budget_status(year: int = 0, data_dir: Path | None = None) -> dict[str, Any]:
    """The association's budget against actual, as PayHOA reported it at the last `jason budget` sync: year to date
    and full year (revenue, expense, net: budgeted, actual, variance), each month's budget and actual for income and
    expense, the categories furthest from budget, collection progress, and the bank balances named from the
    specification (operating ...5286, reserve ...6177, reserve CD ...7476) with the reserve total. Amounts are integer
    cents. Reads disk only; the balances are Plaid's and can lag the bank."""
    from jason.community import mystique
    from jason.tasks.finance import finance_summary, latest_year, load

    root = _data_dir(data_dir)
    wanted = int(year) if year else latest_year(root)
    snap = load(root, wanted) if wanted else None
    if snap is None:
        return {"found": False, "note": "no finance snapshot; run jason budget"}
    return {"found": True, **finance_summary(snap, mystique().bank_accounts())}


def invoice_review(payee: str = "", problems_only: bool = True, since: str = "", limit: int = 80,
                   data_dir: Path | None = None) -> dict[str, Any]:
    """The review of every PayHOA expense payment against its attached documents, as `jason invoices` last ran it:
    a payment with nothing attached, an attachment that does not print the payment's amount, one that names another
    vendor, the same file or invoice number on another payment (a misattachment, or a double payment when the
    amounts agree), an invoice dated after the payment, a category the payee almost never uses, and scans the reader
    cannot check. A payment the bank returned is noted, not counted; a reserve reimbursement that carries the
    operating invoice is not a duplicate. Also the per-vendor reader scorecard. Integer cents. Reads disk only;
    jason changes nothing in PayHOA."""
    from jason.tasks.invoice_review import load_review

    result = load_review(_data_dir(data_dir))
    if result is None:
        return {"found": False, "note": "no review; run jason invoices --fetch"}
    rows = [r for r in result["payments"] if (not problems_only or not r["ok"]) and (not since or r["date"] >= since)
            and (not payee or payee.casefold() in (r["payee"] or r["description"]).casefold())]
    rows.sort(key=lambda r: r["date"], reverse=True)
    return {"found": True, "transactionsSyncedAt": result.get("transactionsSyncedAt"), "summary": result["summary"],
            "scorecard": result["scorecard"][:30], "payments": rows[: max(1, int(limit))],
            "more": max(0, len(rows) - int(limit)), "caveats": result.get("caveats", [])}


def mail_brief(days: int = 30, kind: str = "", urgency: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """The association's paper mail as PostScanMail received and scanned it (`jason mail` syncs it): what arrived in the
    last ``days``, sorted by sender and the letters' words into legal notices, insurance cancellations and renewals,
    government and tax notices, escrow requests, bank statements, utility bills, checks, invoices, and advertising; what
    a person should act on now; and the dates the letters tie to an action ("respond by", "due", "effective"). ``kind``
    and ``urgency`` ("act", "review", "file") narrow it. Reads disk only; jason never asks PostScanMail to scan, forward,
    shred, or discard. The sort is not a reading of what a letter means; repeat the caveats."""
    from jason.tasks.mail import mail_brief as brief

    return brief(_data_dir(data_dir), days=int(days), kind=kind, urgency=urgency)


def zoom_meetings(days: int = 0, kind: str = "", since: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """The association's Zoom meetings as `jason zoom` synced them (`data/zoom`): each occurrence's date, topic, kind
    (board, annual, executive session, hearing, committee, other; by the topic's words, or a board meeting by the
    schedule's day), length, how many joined, which files are held (transcript, chat, AI Companion summary,
    participants), and the summary's next steps; plus the schedule's meeting days with no Zoom meeting. ``days``,
    ``since`` (YYYY-MM-DD), and ``kind`` narrow it. Reads disk only. The AI summary is not the minutes (no roll call,
    motion, or vote); an executive session's or hearing's next steps are held back. Repeat the caveats."""
    from jason.community import mystique
    from jason.tasks.zoom import meetings_brief

    return meetings_brief(_data_dir(data_dir), mystique(), days=int(days) or None, kind=kind, since=since)


def zoom_meeting(meeting: str, include_confidential: bool = False, max_chars: int = 60000, data_dir: Path | None = None) -> dict[str, Any]:
    """One Zoom meeting by UUID, folder, date (YYYY-MM-DD), or meeting id: its record, the AI Companion summary (the
    host's edits when there are any), words by speaker, who joined, the chat, and the transcript as speaker turns with
    times. Several on one date are listed to choose from. An executive session's or hearing's text is held back unless
    ``include_confidential`` (Civil Code 4935). Speech recognition misreads names and numbers; quote with that caveat."""
    from jason.tasks.zoom import meeting_text

    return meeting_text(_data_dir(data_dir), meeting, include_confidential=bool(include_confidential), max_chars=int(max_chars))


def meeting_records(date: str = "", file: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """Every meeting's records as `jason meetings` last cataloged them: per meeting date, which agendas, notices, minutes
    (final or draft), transcripts, AI summaries, chats, attendance, and audio or video recordings exist, and where (Zoom
    cloud, jason's copy, Drive, the PayHOA library, jason's drafts); each meeting's checks (no minutes 30 days on, CIV
    4950; a recording still held after the minutes, against the Decorum Rules; a transcript that runs into an executive
    session or hearing, CIV 4935); the schedule's days with no record; and the files whose names carry no date. ``date``
    (YYYY-MM-DD) gives one meeting with each record's location and the files, folders, and photo albums its agenda links
    under each item. ``file`` (a Drive id, name, path, or URL) gives every agenda item that linked that file, with the
    topics its labels name and the document kind its name suggests; a label is where the board used a file, a lead for
    filing it, not a classification. Reads disk only and deletes nothing; a retained recording may be under a
    litigation hold. Repeat the caveats."""
    from jason.tasks.meeting_catalog import load, meeting

    root = _data_dir(data_dir)
    if file:
        from jason.tasks.agenda_links import lookup

        found = lookup(root, file)
        return {"found": bool(found), "targets": found[:25], "count": len(found)}
    if date:
        return meeting(root, date)
    catalog = load(root)
    if not catalog:
        return {"found": False, "note": "no meeting catalog; run `jason meetings`"}
    brief = [{k: m[k] for k in ("date", "titles", "has", "checks")} for m in catalog["meetings"]]
    return {"found": True, "builtAt": catalog.get("builtAt"), "count": catalog.get("count"), "meetings": brief,
            "scheduleGaps": catalog.get("scheduleGaps"), "unplaced": catalog.get("unplaced"), "caveats": catalog.get("caveats")}


def hearings(data_dir: Path | None = None) -> dict[str, Any]:
    """The disciplinary hearings saved with `jason hearing`: each one's address, date, the board's statement of the
    alleged violation, the Civil Code 5855 dates (notice 10 days before, the decision in writing within 14 days after),
    the Zoom meeting when one was scheduled, and where it stands. Confidential: for directors. Reads disk only; jason
    schedules a meeting only when a person runs `jason hearing --create --yes`, and never sends the notice."""
    from jason.tasks.zoom import hearings as saved

    return saved(_data_dir(data_dir))


def mail_checks(data_dir: Path | None = None) -> dict[str, Any]:
    """The association's mail checked against jason's other records: senders still writing to the prior manager's or the
    property's address (and letters addressed in care of someone); each escrow or title request with the 10-day window
    Civil Code 4530(a)(1) sets, counted from arrival; each county tax bill and delinquency notice matched to the stored
    bill by number or amount, with whether it is paid now; each bank statement's date, account ending, and ending
    balance; each check against the PayHOA deposit of its amount; and each preliminary notice or lien claim against
    the payments to its claimant. Integer cents. Reads disk only; jason answers
    no request, pays no bill, and changes no address. Repeat the caveats."""
    from jason.community import mystique
    from jason.tasks.mail_links import mail_links

    try:
        from jason.config import Settings
        from jason.tasks.utilities import bill_roots

        roots = bill_roots(Settings.load(None))
    except Exception:  # without settings, the utility accounts' addresses are left out
        roots = None
    return mail_links(_data_dir(data_dir), mystique(), roots=roots)


def request_links(unit: str = "", drafts_only: bool = False, limit: int = 40, data_dir: Path | None = None) -> dict[str, Any]:
    """PayHOA's requests beside the email about them: each request with PayHOA's own notices (submission, comment, status
    change, joined by time) and the owner's threads about the same unit (joined by dates, topics, and subject words, with
    the reasons), and the drafts for emailed requests PayHOA does not have (form, unit, title, a message pointing at the
    thread). Filter by ``unit``. Read-only: a draft is entered only by a person with `jason request-links --create THREAD
    --yes`, and no request is ever approved, denied, or assigned. Repeat the caveats."""
    from jason.community import mystique
    from jason.tasks.request_links import request_links as build

    result = build(_data_dir(data_dir), mystique())
    u = unit.upper()
    rows = [] if drafts_only else [r for r in result["rows"] if (not u or u in r["unit"]) and (r["notices"] or r["ownerThreads"])]
    drafts = [d for d in result["drafts"] if not u or u in d["unit"]]
    return {**{k: v for k, v in result.items() if k not in ("rows", "drafts")}, "rows": rows[:limit], "drafts": drafts[:limit]}


def permits(number: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """The association's building permits from the City of Sacramento's Accela portal, as `jason permit-status --sync` read them:
    the collection's totals (records, fees paid and due, inspections by result), and each open record's status, fees due
    and paid, the review workflow's last step and what it waits on, conditions not resolved, inspections, and related
    records; closed records from their list row (``--all`` reads them in full). ``feesComplete`` false means the fee lines
    read do not add up to the totals the portal printed; ``dueOnRecordsNotRead`` is fees due on records not read in full. A
    fee line's date is its invoice date, not the day paid. Filter by ``number`` (e.g. COM-2616861). Integer cents. Reads disk only;
    jason pays no fee and schedules nothing. Repeat the caveats."""
    from jason.tasks.permits import permits as build

    return build(_data_dir(data_dir), number=number)


def email_intents(intent: str = "", topic: str = "", days: int = 365, limit: int = 40, data_dir: Path | None = None) -> dict[str, Any]:
    """What each email thread asks of the association, read from its subject: a complaint, a maintenance request, a request
    for information or records, a billing matter, a question, or the association's own enforcement notice; with its topics,
    and, for a complaint, question, or information request, where the answer is likely written: the governing documents'
    passages (BM25), the library's documents of the kinds that speak to the topic, and the PayHOA violations that are its
    precedents with the restriction each cited and its hearing language. Filter by ``intent`` or ``topic``. A passage is
    text to read, not a ruling; a precedent is a pattern, not a decision. Repeat the caveats."""
    from jason.community import mystique
    from jason.tasks.intents import email_intents as build

    result = build(_data_dir(data_dir), mystique(), days=days)
    rows = [r for r in result["rows"] if (not intent or intent in r["intents"]) and (not topic or topic in r["topics"])]
    return {**{k: v for k, v in result.items() if k not in ("rows", "violations")}, "matching": len(rows), "rows": rows[:limit],
            "violations": result["violations"]}


def case_file(terms: list[str], data_dir: Path | None = None) -> dict[str, Any]:
    """One matter across the stores by the words that name it (a person, an address, a case or claim number, e.g.
    ["water intrusion", "smith", "24CV000123"]): the email threads, PayHOA violations (with the restriction cited and the
    hearing date) and requests, the paper letters, the Drive files, and the library's documents, in date order. A match is
    by words in subjects, titles, names, and paths. Reads disk only. Repeat the caveats."""
    from jason.community import mystique
    from jason.tasks.intents import case_file as build

    return build(list(terms), _data_dir(data_dir), mystique())


def reply_needed(party_class: str = "", days: int = 120, limit: int = 40, data_dir: Path | None = None) -> dict[str, Any]:
    """Which email the association answers, learned from its own replies: the reply rate and usual reply time by kind of
    party (owner, buyer, former owner, board member, vendor, insurer, government agency, business, personal), by party and
    what the subject asks, and by sender; and the open threads (the last message came in) that likely need a response,
    most likely and longest past the usual time first, each with the history it was judged by. Filter by ``party_class``.
    A reply from another mailbox, by phone, or through PayHOA is not seen. Repeat the caveats."""
    from jason.community import mystique
    from jason.tasks.replies import reply_needed as build

    result = build(_data_dir(data_dir), mystique(), open_days=days)
    rows = [o for o in result["open"] if not party_class or o["partyClass"] == party_class]
    return {**{k: v for k, v in result.items() if k != "open"}, "matching": len(rows), "open": rows[:limit]}


def party_brief(query: str, data_dir: Path | None = None) -> dict[str, Any]:
    """One unit or one counterparty across every store. A unit (by address, e.g. "123 MAIN"): its owners by deed, PayHOA
    balance and members, requests, violations, email threads with topics and status, letters naming it, and the unit brief
    (title, liens, solar, taxes). A counterparty (by sender name, PayHOA vendor, or email domain): payments by year, its
    invoices and whether each is paid, threads awaiting us and them, letters, the people who write from its domains and the
    contact changes proposed for PayHOA, and the Drive files saved from its email. Reads disk only. Repeat the caveats."""
    from jason.community import mystique
    from jason.tasks.party import party_brief as build

    return build(query, _data_dir(data_dir), mystique())


def thread_topics(data_dir: Path | None = None) -> dict[str, Any]:
    """What the association hears about, by topic (parking, bins, solar, insurance, assessments, maintenance, landscaping,
    pests, architecture, neighbors, escrow, governance, security, utilities): threads this year, units raising it, threads in
    90 days, threads awaiting us, recent examples, and the FAQ candidates (three or more units in a year). Topics are read
    from subject words. Repeat the caveats."""
    from jason.community import mystique
    from jason.tasks.party import thread_topics as build

    return build(_data_dir(data_dir), mystique())


def new_owners(days: int = 365, data_dir: Path | None = None) -> dict[str, Any]:
    """Units whose latest deed recorded in the last ``days``: the recording date, whether a PayHOA member holds the unit, its
    balance, the buyer's email threads (from 60 days before the deed) with topics and status, and the unit's requests and
    violations since. Reads disk only. Repeat the caveats."""
    from jason.community import mystique
    from jason.tasks.party import new_owners as build

    return build(_data_dir(data_dir), mystique(), days=days)


def open_items(days: int = 30, data_dir: Path | None = None) -> dict[str, Any]:
    """What is waiting on the association: email threads awaiting us (last ``days``), PayHOA requests pending, deadlines due
    soon or overdue, insurance findings, mail delivered and not scanned, letters to act on, and lien notices not paid.
    Jason answers, pays, and files nothing. Repeat the caveats."""
    from jason.community import mystique
    from jason.tasks.party import open_items as build

    return build(_data_dir(data_dir), mystique(), days=days)


def email_threads(status: str = "", party: str = "", sender: str = "", days: int = 120, limit: int = 40,
                  data_dir: Path | None = None) -> dict[str, Any]:
    """The association's email as threads of work (headers only, from `jason gmail --sync`): each thread's status (awaiting
    us: the last message came in and nothing went out after; awaiting them; notice; internal), its age, parties (a vendor or
    agency by domain; an owner, former owner after a conveyance, buyer, or board member as the records knew them that day;
    never an owner's address), and what happened near it: payments to its sender, its sender's paper letters, the invoices
    among its attachments and their payments, the files saved from it to Drive, and the owner's unit requests and
    violations. Filter by ``status``, ``party`` (e.g. "owner of 3048"), or ``sender``. A related item is a lead, not proof.
    Jason sends no email. Repeat the caveats."""
    from datetime import date as _date, timedelta as _td

    from jason.community import mystique
    from jason.tasks.threads import threads

    result = threads(_data_dir(data_dir), mystique())
    since = (_date.today() - _td(days=days)).isoformat()
    rows = [r for r in result["rows"] if r["last"] >= since
            and (not status or r["status"] == status)
            and (not party or any(party.lower() in p.lower() for p in r["parties"]))
            and (not sender or sender.lower() in r["sender"].lower())]
    return {**{k: v for k, v in result.items() if k != "rows"}, "matching": len(rows), "rows": rows[:limit]}


def record_locations(record: str = "", kind: str = "", name: str = "", outside_rules_only: bool = False, limit: int = 60,
                     data_dir: Path | None = None) -> dict[str, Any]:
    """Where the association's records are in Drive (from the last `jason drive` run): each Drive file with its path, the
    library path its Drive root gives it (the path rule), its kind and Civil Code 5200 records by the same rules as the
    PayHOA library, and every other place the same content is held (the PayHOA library, a payment's attachment, an
    email, a scanned letter). Also the summary: each record's files in Drive and how many are under a path rule, the same
    content in several Drive folders, the same name with different content, library files not in Drive, and the Drive
    folders no path rule covers. Filter by ``record``, ``kind``, or ``name``. Reads disk only; jason moves nothing."""
    import json as _json

    path = _data_dir(data_dir) / "drive" / "holdings.json"
    if not path.is_file():
        return {"found": False, "hint": "run jason drive --sync"}
    result = _json.loads(path.read_text(encoding="utf-8"))
    rows = [r for r in result["rows"]
            if (not record or any(record.lower() in x.lower() for x in r["records"]))
            and (not kind or kind.lower() == r["kind"].lower())
            and (not name or name.lower() in r["name"].lower())
            and (not outside_rules_only or not r["pathRule"])]
    summary = {k: v for k, v in result.items() if k != "rows"}
    summary["duplicatesInDrive"] = summary["duplicatesInDrive"][:40]
    summary["versionsInDrive"] = summary["versionsInDrive"][:40]
    return {**summary, "matching": len(rows), "rows": rows[:limit]}


def document_copies(issuer: str = "", number: str = "", across_channels_only: bool = False, limit: int = 50,
                    data_dir: Path | None = None) -> dict[str, Any]:
    """The invoices and bills as documents, each with every copy the association holds (the issuer's portal, email,
    PayHOA attachments, paper scans), the rule that joined each copy, the best copy to read by the channel priority, and
    the PayHOA payment (the one a copy hangs on, or a candidate by amount and date). Reads the last `jason copies` run
    (data/reports/copies.json); filter by ``issuer`` or ``number``. Every copy stays where it is. Integer cents.
    Repeat the caveats."""
    import json as _json

    path = _data_dir(data_dir) / "reports" / "copies.json"
    if not path.is_file():
        return {"found": False, "hint": "run jason copies"}
    result = _json.loads(path.read_text(encoding="utf-8"))
    rows = [r for r in result["rows"]
            if (not issuer or issuer.lower() in r["issuer"].lower())
            and (not number or number.lstrip("0") in (r["number"] or "").lstrip("0"))
            and (not across_channels_only or len(r["channels"]) > 1)]
    return {**{k: v for k, v in result.items() if k != "rows"}, "matching": len(rows), "rows": rows[:limit]}


def vendor_contacts(data_dir: Path | None = None) -> dict[str, Any]:
    """Each PayHOA vendor's contact on file (name, email, phone, website) beside the people who actually write from its
    email domains in the association's Gmail (headers only: name, address, first and last date, counts each way), with
    proposals for a person: an email or contact name PayHOA lacks, an address on file no message carries, a domain the
    sender row in mystique/senders.py does not list. Also the business domains no vendor claims, matched to a vendor by
    name where the words agree, and the PayHOA notices in Gmail against the synced mail (items the API sync lacks, items
    delivered and never scanned). Reads disk only; jason changes nothing in PayHOA and sends no email."""
    from jason.community import mystique
    from jason.tasks.contacts import directory
    from jason.tasks.gmail import notice_check

    root = _data_dir(data_dir)
    return {**directory(root, mystique()), "postscanmailNotices": notice_check(root)}


def association_calendar(data_dir: Path | None = None) -> dict[str, Any]:
    """The association's recurring deadlines, overdue and due soon first: property tax installments, income tax payments
    and returns, the Secretary of State filing, backflow and fire sprinkler tests, the balcony inspection, the budget
    report and reviewed statement, each insurance term, and the reserve study's site visit. Each carries its authority,
    the next deadline, the last time a PayHOA payment shows it done, and past deadlines done late or with no evidence.
    A payment is evidence, not proof; a deadline no store shows is listed as such. Integer cents. Reads disk only.
    Repeat the caveats."""
    from jason.community import mystique
    from jason.tasks.deadlines import calendar

    return calendar(_data_dir(data_dir), mystique())


def insurance_review(data_dir: Path | None = None) -> dict[str, Any]:
    """Each insurance policy on the sheet (master, umbrella, fidelity, D&O, workers' comp, flood by building): its number
    and earlier numbers, carrier, program, and agent; the end of the term in force and a standing (in term, renewal
    notice received, next term paid, or ended with no premium for the next term); premiums by term from PayHOA (a flood
    payment placed on the building whose renewal bill prints its amount); the letters that print its number, with
    conditional renewals, non-renewals, and cancellations; and the claims the mail acknowledges. Integer cents. Reads
    disk only; jason buys, renews, cancels, and claims nothing. Repeat the caveats."""
    from jason.community import mystique
    from jason.tasks.insurance import review

    return review(_data_dir(data_dir), mystique())


def counterparties(data_dir: Path | None = None) -> dict[str, Any]:
    """The association's counterparties by kind of source (government agency with its level, utility, insurer, bank,
    vendor, title company, law firm, manager, accountant, owner, another association): each named sender's letters by
    kind and its PayHOA payments (money out only; wires and deposits in are not payments), the PayHOA vendors the
    specification does not name, the letterheads no rule names yet, and the other associations the mail names (their
    own mail that came to the box, or an agency's record under their name). Integer cents. Reads disk only. Repeat
    the caveats."""
    from jason.community import mystique
    from jason.tasks.sources import sources_report

    return sources_report(_data_dir(data_dir), mystique())


def mail_item(mail_id: str, data_dir: Path | None = None) -> dict[str, Any]:
    """One mail item: sender, arrival, status, PostScanMail's AI summary, the sort, and the scanned text (text layer or
    OCR). Quote a letter only from this text. Reads disk only."""
    from jason.tasks.mail import mail_text

    return mail_text(_data_dir(data_dir), str(mail_id))


def books_report(report: str = "pl", start: str = "", end: str = "", kind: str = "expense", limit: int = 100,
                 data_dir: Path | None = None) -> dict[str, Any]:
    """The association's books computed from PayHOA's general ledger as `jason books --sync` stored it (every entry,
    month by month). ``report`` is pl (income and expense by category and the net), months (each category by month;
    ``kind`` expense or income), vendors (spending by payee with payments, categories, first and last date), cashflow
    (each bank account's start, money in and out by category, end), balances (bank accounts on ``end``), receivables
    (what the units owe and prepaid, totals and counts, no names), or check (the ledger's year-to-date categories against
    PayHOA's own budget-against-actual). Dates are YYYY-MM-DD; the default period is the ledger's last year to date.
    Integer cents. Reads disk only."""
    from datetime import date as _date

    from jason.tasks.books import books_report as run

    if report == "query":
        return {"found": False, "note": "use ledger_query for entries"}
    return run(_data_dir(data_dir), report, start=_date.fromisoformat(start) if start else None,
               end=_date.fromisoformat(end) if end else None, kind=kind, limit=int(limit))


def ledger_query(text: str = "", payee: str = "", category: str = "", account: str = "", min_dollars: float = 0.0,
                 max_dollars: float = 0.0, start: str = "", end: str = "", limit: int = 100, data_dir: Path | None = None) -> dict[str, Any]:
    """Entries in PayHOA's general ledger (as `jason books --sync` stored it) matching every filter given: words in the
    description or memo, payee, category, account, an amount range in dollars (0 for none), and dates (YYYY-MM-DD). The
    units' own receivable and prepayment accounts are left out. Each row: date, type, account, payee, description,
    category, memo, debit, credit, running balance, in integer cents. Reads disk only."""
    from datetime import date as _date

    from jason.tasks.books import books_report as run

    return run(_data_dir(data_dir), "query", start=_date.fromisoformat(start) if start else _date(2000, 1, 1),
               end=_date.fromisoformat(end) if end else None, text=text, payee=payee, category=category, account=account,
               minimum=round(min_dollars * 100) if min_dollars else None, maximum=round(max_dollars * 100) if max_dollars else None,
               limit=int(limit))


def ledger_validation(data_dir: Path | None = None) -> dict[str, Any]:
    """The treasurer's reports in the library checked against their source, PayHOA's "Treasurer's Report" packet, as
    `jason ledger` last ran it: which library copies are a PayHOA run as generated (by SHA-256), runs the library lacks,
    runs whose dates are not the month they are named for, copies filed under the wrong month, accounts a report printed
    that PayHOA's balance sheet for that date no longer carries (with the chart of accounts' starting balance and date),
    balances the ledger now reports differently for the same date, and the latest month-end balance sheet. Integer cents.
    Reads disk only; the printed report is the record of what the board was told."""
    from jason.tasks.ledger_reports import validate

    return validate(_data_dir(data_dir))


def bank_reconciliations(data_dir: Path | None = None) -> dict[str, Any]:
    """PayHOA's bank reconciliations as `jason reconcile --fetch` stored them, per bank account: the months reconciled
    and any month skipped, the latest statement's ending balance and PayHOA's register balance, the register items that
    never cleared (oldest first, with their age in days), each statement's ending balance against the general ledger's
    balance for that account and day (and whether the items in transit explain the difference), and transfers open on
    both sides. Each open item has a ``reason``: the same bank line already cleared under its trace or transaction number
    (held twice in the register), a cleared twin, a voided bill payment, a transfer, or in transit; a reason is a lead,
    not a finding. Integer cents. Reads disk only; clearing, voiding, or re-reconciling is the treasurer's work in PayHOA."""
    from jason.tasks.reconciliations import review

    return review(_data_dir(data_dir))


def legal_cases() -> dict[str, Any]:
    """The association's legal matters from the specification: the construction defect claim, pending lawsuits, liens, and
    others, each with its forum, number, role, status, businesses involved (private persons by role only), counsel,
    insurer claims, events, money, and each statutory duty with whether the record shows it met. CONFIDENTIAL: litigation
    is an executive session matter (CIV 4935(a)); share only with directors and counsel."""
    from jason.community import mystique
    from jason.community.document_models import to_plain

    cases = mystique().legal_cases()
    return {"found": bool(cases), "cases": [to_plain(c) for c in cases],
            "openDuties": [{"case": c.key, "statute": d.statute, "requirement": d.requirement, "met": d.met} for c in cases for d in c.open_duties],
            "caveats": ["Confidential: for directors and counsel.", "A duty 'not shown' may be met in records jason does not hold."]}


def board_items(include_closed: bool = False, data_dir: Path | None = None) -> dict[str, Any]:
    """The board's running list of action items (`jason board`): each matter jason's reviews found that needs a board
    decision, with what the board is asked to do, the authority, the evidence, the priority, and the board's own status,
    owner, meeting, and notes. Reads disk only. An item is a matter to decide, never the decision."""
    from jason.tasks.board_items import _encode, load

    items = [i for i in load(_data_dir(data_dir)) if include_closed or i.status.value != "closed"]
    return {"found": bool(items), "items": [_encode(i) for i in items]}


def cost_centers(data_dir: Path | None = None) -> dict[str, Any]:
    """The two assessment cost centers each Watt declaration of annexation (section 1.3) requires: the Phases 1 and 2
    Property (A.C.A. 3 and 8, WL Homes' buildings) and the Annexed Property (Watt's buildings), each sharing its component
    equally on top of the General Assessment Component. Sets the rule beside the DRE reports' cost center budgets, the
    monthly assessments PayHOA charged each cost center's units, the budget's lines, and the reserve studies' funding
    plans. Integer cents. Reads disk only. A flat assessment could still be built from both components; the budget
    worksheets would show it. Restoring the cost centers is the board's, with counsel; repeat the caveats."""
    from jason.community import mystique
    from jason.tasks.cost_centers import review

    return review(_data_dir(data_dir), mystique())


def developer_securities(data_dir: Path | None = None) -> dict[str, Any]:
    """The subdivider's securities to the association under the Real Estate Commissioner's regulations, phase by phase:
    assessment security agreements and bonds (10 CCR 2792.9), subsidy agreements and their securities (2792.10),
    completion securities (2792.4, B&P 11018.5), and the releases (the escrow holder's letters, the association's
    letters and resolutions) that name each bond. A bond with no release on file is listed as open on the record, and
    copies that read differently are flagged. Reads disk only (data/developer-security). A bond may have been released
    without a copy reaching Drive, and OCR can misread amounts; repeat both caveats."""
    from jason.community import mystique
    from jason.tasks.developer_security import register

    return register(_data_dir(data_dir), mystique())


def document_models(kind: str = "", include_confidential: bool = False, limit: int = 50, data_dir: Path | None = None) -> dict[str, Any]:
    """The library read by the document models (`jason models`): per document kind, how many files a model read and how
    many readings are complete, and for ``kind`` (a DocumentKind value such as minutes, insurance_policy,
    elevated_element_inspection) each file's typed record and findings, newest first. A finding cites the statute when
    the law shapes the document (CIV 4950 minutes, CIV 5551 balcony report). A confidential file's fields are held back
    unless ``include_confidential``. Reads disk only. A reading is what a model found in the text; OCR can be wrong, and a
    finding is a lead, not a determination; repeat that."""
    from jason.tasks.document_models import summary

    return summary(_data_dir(data_dir), kind=kind, include_confidential=bool(include_confidential), limit=int(limit))


_REFERENCE_CAVEATS = [
    "References are read by a citation grammar from the documents' own text (`jason outlines`); a citation the grammar "
    "does not read is not listed.",
    "A finding is a lead for a person, not a conclusion.",
    "An outline read from a scanned PDF (the annexations) can miss subsections because of OCR; a section 'missing' or "
    "'parent only' there may be the outline's miss, not the document's.",
]
_SECTION_CHARS = 2500


def _reference_row(r: dict[str, Any], *, quote: bool = True) -> dict[str, Any]:
    row = {"source": r["source"], "sourceSection": r["source_section"], "kind": r["kind"], "target": r["target"],
           "relation": r["relation"], "status": r["status"]}
    if r.get("nearest"):
        row["nearest"] = r["nearest"]
    if r.get("claimants"):
        row["claimants"] = r["claimants"]
    if quote:
        row["quote"] = " ".join(r["quote"].split())[:200]
    return row


def document_references(document: str = "", section: str = "", cites: str = "", depth: int = 2, limit: int = 100,
                        data_dir: Path | None = None) -> dict[str, Any]:
    """The association's documents as `jason outlines` outlined them (the governing documents, the rules and policies,
    the resolutions, the annexations) and the references among them and to the law. With no argument: each document
    with its sections and references out and in, and the findings (a section cited that the outline lacks, a
    resolution number two Docs print, statutes cited by their pre-2014 numbers). ``document`` (a key such as bylaws, or
    a name documents cite it by such as Declaration): its outline to ``depth`` and its reference counts. ``section``
    ("bylaws#7.2"): the section's text, what it cites, and what cites it. ``cites`` ("CIV 4926", "bylaws#8.5",
    "resolution:20230130-1"): every reference to that target or inside it. Reads disk only. References are read by a
    grammar, a finding is a lead, and a scanned annexation's outline can miss subsections; repeat the caveats."""
    import re
    from collections import Counter

    root = _data_dir(data_dir)
    if not (root / "outlines").is_dir():
        return {"found": False, "note": "no outlines; run jason outlines --fetch", "caveats": _REFERENCE_CAVEATS}
    from jason.community.outlines import normalize_number
    from jason.community.references import ancestors, section_target
    from jason.tasks.outlines import aliases_of, cited_by, findings, load, load_rows

    outlines, rows = load(root), load_rows(root)
    by_key = {o.key: o for o in outlines}
    limit = max(1, int(limit))

    def incoming(key: str) -> list[dict[str, Any]]:
        return [r for r in rows if r["kind"] in ("section", "document") and r["target"].split("#")[0] == key and r["source"] != key]

    if section:
        if "#" not in section:
            return {"found": False, "note": "section is key#number, such as bylaws#7.2", "caveats": _REFERENCE_CAVEATS}
        key, number = section_target(section.strip())
        key = key if key in by_key else aliases_of(outlines).get(key.lower(), key)
        number = normalize_number(number)
        target = f"{key}#{number}"
        outline = by_key.get(key)
        citing = [_reference_row(r) for r in cited_by(rows, target)]
        if outline is None:
            return {"found": False, "section": target, "note": f"no outline for {key}", "citedBy": citing[:limit],
                    "caveats": _REFERENCE_CAVEATS}
        found = outline.section(number)
        if found is None:
            nearest = next((a for a in ancestors(number) if outline.section(a)), "")
            return {"found": False, "section": target, "document": outline.title, "note": f"the outline has no section {number}",
                    "nearest": nearest, "citedBy": citing[:limit], "caveats": _REFERENCE_CAVEATS}
        text = " ".join(outline.text_of(found).split())
        own = [_reference_row(r, quote=False) for r in rows if r["source"] == key and r["source_section"] == found.name]
        citing = [c for c in citing if not (c["source"] == key and c["sourceSection"] == found.name)]
        return {"found": True, "section": target, "document": outline.title, "number": found.number, "title": found.title,
                "text": text[:_SECTION_CHARS], "truncated": len(text) > _SECTION_CHARS,
                "subsections": [s.number for s in outline.sections if s.parent == found.number and s.number],
                "cites": own[:limit], "citedBy": citing[:limit], "citedByTotal": len(citing), "caveats": _REFERENCE_CAVEATS}

    if cites:
        target = cites.strip()
        if re.match(r"^[a-z]+\s+\d", target):
            target = target.upper()            # "civ 4926" is cited as "CIV 4926"
        if "#" in target:
            key, number = section_target(target)
            target = f"{key}#{normalize_number(number)}" if number else key
        hits = cited_by(rows, target)
        return {"found": bool(hits), "target": target, "total": len(hits), "bySource": dict(Counter(r["source"] for r in hits)),
                "references": [_reference_row(r) for r in hits[:limit]], "caveats": _REFERENCE_CAVEATS}

    if document:
        key = document.strip()
        key = key if key in by_key else aliases_of(outlines).get(key.lower(), key)
        outline = by_key.get(key)
        if outline is None:
            return {"found": False, "note": f"no outline {document}", "documents": sorted(by_key), "caveats": _REFERENCE_CAVEATS}
        out_rows = [r for r in rows if r["source"] == key]
        in_rows = incoming(key)
        return {"found": True, "key": key, "title": outline.title, "kind": outline.kind, "aliases": outline.aliases,
                "amends": outline.amends, "numbers": outline.numbers, "library": outline.library,
                "sectionCount": len(outline.sections),
                "outline": [{"number": s.number, "title": s.title[:120], "depth": s.depth}
                            for s in outline.sections if s.depth <= max(1, int(depth))],
                "referencesOut": len(out_rows), "referencesOutByKind": dict(Counter(r["kind"] for r in out_rows)),
                "referencesOutByStatus": dict(Counter(r["status"] for r in out_rows)),
                "referencesIn": len(in_rows), "citedByDocuments": sorted({r["source"] for r in in_rows}),
                "caveats": _REFERENCE_CAVEATS}

    documents = []
    for o in outlines:
        out_rows = [r for r in rows if r["source"] == o.key]
        documents.append({"key": o.key, "title": o.title, "kind": o.kind, "sections": len(o.sections),
                          "referencesOut": len(out_rows), "referencesIn": len(incoming(o.key)),
                          "citedByDocuments": len({r["source"] for r in incoming(o.key)})})
    return {"found": bool(outlines), "documents": documents, "references": len(rows),
            "byKind": dict(Counter(r["kind"] for r in rows)), "byStatus": dict(Counter(r["status"] for r in rows)),
            "findings": findings(rows, outlines), "caveats": _REFERENCE_CAVEATS}


def reserve_transfers(data_dir: Path | None = None) -> dict[str, Any]:
    """Money in and out of the reserve accounts from the general ledger `jason books --sync` stored: each borrowing to
    operating with its Civil Code 5515 record (the agenda's notice of intent to borrow, the minutes of that meeting, the
    resolution, and the contributions that restored it and whether within a year), other withdrawals (reimbursements of
    operating expenses, forwarded deposits), catch-up contributions, and moves to certificates of deposit. Integer cents.
    Reads disk only. A repayment is matched by amount and a missing document may be in the board's files; repeat the
    caveats. Whether the statute was met is the board's to say."""
    from jason.community import mystique
    from jason.tasks.reserve_transfers import review

    return review(_data_dir(data_dir), mystique())


def reserve_study(year: int = 0, data_dir: Path | None = None) -> dict[str, Any]:
    """The association's reserve studies read from the PDFs on disk (library studies and data/reserve-studies): the
    latest study's plan for ``year`` (default next year) - contribution per year, month, and unit, planned component
    expenditures, ending balance and percent funded - beside the budget's 'Transfer to Reserves' line and the reserve
    account balances; each study's disclosure figures (Civil Code 5570) over the years; checks (a wrong unit count, a
    plan the next study did not start from, a budget off the plan); and when the next site visit and review are due
    (Civil Code 5550). Integer cents. Reads disk only. The figures are the preparer's estimates; the board adopts the
    funding plan."""
    from jason.community import mystique
    from jason.tasks.reserves import reserve_brief

    return reserve_brief(_data_dir(data_dir), mystique(), year=int(year) or None)


def utility_brief(year: int = 0, water_increase: float = 0.0, since: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """The association's utility bills as `jason utilities` parsed them (SMUD electric; City of Sacramento water,
    irrigation, fire service, storm drainage, street sweeping): each account's purpose, meters, sizes, service address,
    and parcel as the bills state them; abnormal usage per day against the same period in earlier years (a possible
    leak or short, a reason to look, not a finding); files whose content is an older bill than their name says; and a
    year's cost (default next year) with SMUD priced at its adopted CITS-0 tariff and the City at current rates, set
    beside the PayHOA budget line for each service. ``water_increase`` (0.1 = 10%) is a scenario from July 1, 2027,
    not an adopted City rate. Integer cents. Reads disk only; repeat the caveats."""
    from datetime import date as _date

    from jason.community import mystique
    from jason.tasks.utilities import utilities_brief

    return utilities_brief(
        _data_dir(data_dir), mystique(), year=int(year) or None, water_increase=float(water_increase or 0.0),
        since=_date.fromisoformat(since) if since else None,
    )


def utility_usage(account: str, service: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """One utility account's metered usage bill by bill: period, days, usage (kWh or cubic feet), usage per day, and
    the service's cost in integer cents. ``service`` narrows to electric, water_domestic, or water_irrigation."""
    from jason.community.utility import Service
    from jason.tasks.utilities import load_bills, store_path, usage_history

    path = store_path(_data_dir(data_dir))
    if not path.is_file():
        return {"found": False, "note": "no utility store; run jason utilities"}
    rows = usage_history(load_bills(path), str(account).strip(), Service(service) if service else None)
    return {"found": bool(rows), "account": account, "bills": rows}


def utility_accounts(data_dir: Path | None = None) -> dict[str, Any]:
    """Every SMUD and City account: its purpose from the specification (building, ACA lot, pump room), and the meters,
    sizes, service address, parcel, and first and last bill the bills themselves state, with notes on replaced meters,
    accounts the specification does not name, and accounts with no recent bill."""
    from jason.community import mystique
    from jason.tasks.utilities import load_bills, service_map, store_path

    path = store_path(_data_dir(data_dir))
    if not path.is_file():
        return {"found": False, "note": "no utility store; run jason utilities"}
    return {"found": True, "accounts": service_map(load_bills(path), mystique())}


def utility_payments(problems_only: bool = True, since: str = "", limit: int = 80, data_dir: Path | None = None) -> dict[str, Any]:
    """The audit of the association's SMUD and City payments in PayHOA as `jason utilities --payments` last ran it:
    each payment's bills (matched by the amount each bill asked), whether the attached PDF is that bill, the split by
    budget line the bills support against the categories the payment carries, and payments made twice (confirmed by
    the next bill's credit). Findings are for the treasurer; jason changes nothing in PayHOA. Integer cents; newest
    first. Reads disk only."""
    from jason.tasks.utility_payments import load_audit

    result = load_audit(_data_dir(data_dir))
    if result is None:
        return {"found": False, "note": "no audit; run jason utilities --payments --fetch"}
    rows = [r for r in result["payments"] if (not problems_only or not r["ok"]) and (not since or r["date"] >= since)]
    rows.sort(key=lambda r: r["date"], reverse=True)
    return {"found": True, "transactionsSyncedAt": result.get("transactionsSyncedAt"), "summary": result["summary"],
            "payments": rows[: max(1, int(limit))], "more": max(0, len(rows) - int(limit)), "caveats": result.get("caveats", [])}


def pest_program(key: str = "proactive", data_dir: Path | None = None) -> dict[str, Any]:
    """The association's pest control program as the vendor's portal records it (`jason vendors --sync`): each product
    applied, by EPA registration number, with its active ingredient, amounts, methods, areas, target pests, and years,
    and, once `jason pests --fetch` has run, its registration, signal word, label, safety data sheet, and the California
    rules that apply (pyrethroid surface-water limits, neonicotinoid and rodenticide restrictions); the rodent bait
    stations' activity by month from the technicians' notes; visits by building; and the vendor's inspection reports
    with their quotes. The declaration decides who pays (CC&Rs Article 7, Section 7); the duty is "Pest control" in
    duty_brief. Reads disk only; the vendor's record is the vendor's."""
    from jason.community import mystique
    from jason.tasks.pests import pest_brief

    portal = next((p for p in mystique().vendor_portals() if p.key == key), None)
    if portal is None:
        return {"found": False, "note": f"no vendor portal {key!r}"}
    return pest_brief(_data_dir(data_dir), portal)


def insurance_policies(policy: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """The association's insurance policies as `jason policies` read them from their own declarations (master package,
    umbrella, crime, D&O, and the eight NFIP flood policies): for each, the carrier, program, agent, number in force and
    earlier numbers, each term read from its declarations (dates, premium, deductible, limits), the policy sheet's number,
    renewal date, and premiums by year, the documents (declarations, certificates, renewal notices, invoices, disclosures),
    and findings: the sheet out of step with the policies, a renewed term whose declarations are not on file, a mailing
    address that is not the association's, the Civil Code 5800/5805/5806 limits, protective safeguards, and exclusions.
    `policy` narrows to one ("master", "fidelity", "flood-3"). Amounts are integer cents. The declarations and forms govern;
    this is a reading. Reads disk only; ask the insurance catalog in AnythingLLM for the policies' own words."""
    from jason.tasks.policies import load

    report = load(_data_dir(data_dir))
    if not report.get("found"):
        return {"found": False, "note": "run `jason policies --fetch` first"}
    rows = [p for p in report["policies"] if not policy or policy.lower() in p["key"]]
    return {"found": True, "builtAt": report["builtAt"], "documents": report["documents"], "policies": rows}


def incident_history(building: int | None = None, address: str = "", work: str = "", claims_only: bool = False, standing: str = "",
                     cause: str = "",
                     since: str = "", limit: int = 40, include_routine: bool = False, data_dir: Path | None = None) -> dict[str, Any]:
    """The association's maintenance history and insurance claims as `jason incidents` read them from its repair
    paperwork (proposals, estimates, contracts, change orders, invoices, inspection reports, claim letters, and notices
    in PayHOA, email, the library, and Drive), grouped into events and placed on units (street addresses) and buildings.
    Each event has its work (repair, maintenance, improvement, inspection), its causes (roof leak, plumbing leak,
    vehicle collision, ...), and whether an insurance claim is tied to it (claimed, with claim numbers) or it names a
    sudden cause with no claim on file; its standing against the master policy's deductible (claimed, claim candidate when the
    paperwork's cost reaches the deductible, under deductible, sudden with cost unknown). Filter by building (1-8), address words ("123 Main"), work, claims_only,
    cause words, or since (YYYY-MM-DD). Routine upkeep and inspections with no claim and no sudden cause are left out
    unless include_routine or a work is named. Amounts are integer cents. An event is a rule's reading of the paperwork;
    whether a peril was covered is the insurer's answer; a claim file's snippet is held back. Reads disk only."""
    from jason.tasks.incidents import load, select

    report = load(_data_dir(data_dir))
    if not report.get("found"):
        return {"found": False, "note": "run `jason incidents` (and `jason incidents --fetch` for the Drive paperwork) first"}
    rows = select(report, building=building, address=address, work=work, claims=claims_only, cause=cause, since=since,
                  routine=include_routine or bool(work), standing=standing)
    return {"found": True, "builtAt": report.get("builtAt"), "documents": report.get("documents"), "counts": report.get("counts"),
            "byBuilding": report.get("byBuilding"), "byUnit": dict(list((report.get("byUnit") or {}).items())[:20]),
            "deductibleCents": report.get("deductibleCents"), "matched": len(rows), "events": rows[-max(1, int(limit)):], "more": max(0, len(rows) - int(limit)),
            "caveats": report.get("caveats", [])}


def vendor_portal(key: str = "proactive", visits: int = 5, findings: bool = True, data_dir: Path | None = None) -> dict[str, Any]:
    """A vendor's customer portal as `jason vendors --sync` saved it (ProActive Pest Control, key "proactive"): each
    property on the account with its plan, balance, latest visits (technician, time in and out, notes, products applied),
    the products applied this year with their EPA numbers, and the counts of invoices, photos, and documents on disk;
    and, when `jason vendors --verify` has run, each PayHOA payment to the vendor against the portal's payment and the
    invoice attached (no portal payment, another property's ticket, wrong category, missing or wrong attachment, the
    same invoice on two payments). Integer cents. Reads disk only; findings are for the treasurer."""
    import json as _json

    from jason.community import mystique
    from jason.tasks.vendor_portals import portal_brief, portal_root

    portal = next((p for p in mystique().vendor_portals() if p.key == key), None)
    if portal is None:
        return {"found": False, "note": f"no vendor portal {key!r}; known: " + ", ".join(p.key for p in mystique().vendor_portals())}
    root = _data_dir(data_dir)
    brief = portal_brief(root, portal, visits=int(visits))
    if findings and brief.get("found"):
        path = portal_root(root, key) / "verification.json"
        if path.is_file():
            body = _json.loads(path.read_text(encoding="utf-8"))
            brief["findings"] = [{k: r[k] for k in ("date", "amountCents", "ticket", "property", "transactionId", "findings")}
                                 for r in body["payments"] if r["findings"]]
            brief["portalPaymentsNotInPayhoa"] = body.get("portalPaymentsNotInPayhoa", [])
            brief["caveats"] = body.get("caveats", [])
    return brief


def bank_accounts(data_dir: Path | None = None) -> dict[str, Any]:
    """The association's bank accounts and their balances at the last `jason budget` sync, named from the
    specification, plus every other account PayHOA lists (a former manager's accounts carry no balance). Integer cents."""
    from jason.community import mystique
    from jason.tasks.finance import balances, latest_year, load

    root = _data_dir(data_dir)
    year = latest_year(root)
    snap = load(root, year) if year else None
    if snap is None:
        return {"found": False, "note": "no finance snapshot; run jason budget"}
    named = balances(snap, mystique().bank_accounts())
    matched = {b.payhoa_name for b in named}
    others = [{"name": row.get("friendlyName"), "balanceCents": row.get("plaidBalance")} for row in snap.get("bankAccounts") or []
              if row.get("friendlyName") not in matched]
    return {"found": True, "syncedAt": snap.get("syncedAt"), "accounts": [b.__dict__ for b in named], "otherPayhoaAccounts": others,
            "deposit": snap.get("depositAccounts"), "note": "balances are Plaid's as PayHOA last refreshed them; confirm on the bank's statement"}


def library_search(kind: str = "", record: str = "", period: str = "", words: str = "", include_confidential: bool = False,
                   limit: int = 25, data_dir: Path | None = None) -> dict[str, Any]:
    """Find documents in the association's classified library (run `jason library` to refresh it). ``kind`` is a
    document kind (minutes, agenda, treasurer_report, bank_statement, budget, reserve_study, policy, contract,
    insurance_policy, ...), ``record`` a Civil Code 5200 record (minutes, interim_financial, financial_disclosure,
    enhanced, executed_contract, election_materials, governing_documents, vendor_approval, reserve_account, ...),
    ``period`` a prefix such as 2025 or 2025-03, ``words`` a phrase to find in the file's text. Newest first.
    Confidential files (bank statements, owner histories, delinquency files, executive sessions, the member list,
    the Confidential folder) are left out unless ``include_confidential``. Each row says how it was classified."""
    from jason.tasks.library import distinct, load, text_for

    root = _data_dir(data_dir)
    rows = distinct(load(root))
    if not rows:
        return {"found": False, "note": "no library store; run jason library"}
    wanted_kind = kind.strip().lower().replace(" ", "_")
    wanted_record = record.strip().lower().replace(" ", "_")
    phrase = words.strip().casefold()
    hits = []
    held_back = 0
    for row in rows:
        if wanted_kind and row["kind"] != wanted_kind:
            continue
        if wanted_record and wanted_record not in row["records"]:
            continue
        if period.strip() and not str(row.get("period") or "").startswith(period.strip()):
            continue
        if phrase and phrase not in text_for(root, row["id"]).casefold():
            continue
        if row["confidential"] and not include_confidential:
            held_back += 1
            continue
        hits.append(row)
    hits.sort(key=lambda r: (str(r.get("period") or ""), r["path"]), reverse=True)
    return {"found": bool(hits), "count": len(hits), "heldBackConfidential": held_back,
            "rows": [{k: r[k] for k in ("id", "path", "kind", "records", "period", "method", "evidence", "confidential")} for r in hits[: max(1, int(limit))]]}


def library_status(data_dir: Path | None = None) -> dict[str, Any]:
    """How the association's library is classified: files by method (name rule, phrase rule, local model, none), by
    kind, and by Civil Code 5200 record, with the newest file of each record and what no stage placed."""
    from jason.tasks.library import distinct, load

    everything = load(_data_dir(data_dir))
    rows = distinct(everything)
    if not rows:
        return {"found": False, "note": "no library store; run jason library"}
    methods: dict[str, int] = {}
    kinds: dict[str, int] = {}
    records: dict[str, dict[str, Any]] = {}
    for row in rows:
        methods[row["method"]] = methods.get(row["method"], 0) + 1
        kinds[row["kind"] or "(none)"] = kinds.get(row["kind"] or "(none)", 0) + 1
        for value in row["records"]:
            entry = records.setdefault(value, {"files": 0, "newest": "", "newestPeriod": ""})
            entry["files"] += 1
            if str(row.get("period") or "") > entry["newestPeriod"]:
                entry["newestPeriod"], entry["newest"] = str(row["period"]), row["path"]
    return {"found": True, "files": len(everything), "distinctFiles": len(rows), "byMethod": methods, "byKind": dict(sorted(kinds.items(), key=lambda kv: -kv[1])),
            "byRecord": records, "unclassified": [row["path"] for row in rows if not row["kind"]]}


def library_text(doc_id: str, include_confidential: bool = False, max_chars: int = 20000, data_dir: Path | None = None) -> dict[str, Any]:
    """The cached text of one library file, by its id from library_search. A confidential file's text is held back
    unless ``include_confidential``. Text read by OCR can be wrong; quote it as the file's words, not as fact."""
    from jason.tasks.library import load, text_for

    root = _data_dir(data_dir)
    row = next((r for r in load(root) if r["id"] == str(doc_id)), None)
    if row is None:
        return {"found": False, "id": doc_id}
    if row["confidential"] and not include_confidential:
        return {"found": True, "id": doc_id, "path": row["path"], "confidential": True, "text": "", "note": "confidential; ask with include_confidential"}
    text = text_for(root, row["id"])
    return {"found": True, "id": doc_id, "path": row["path"], "kind": row["kind"], "period": row["period"], "chars": len(text),
            "text": text[: max(1000, int(max_chars))], "truncated": len(text) > max_chars}


def association_collections(data_dir: Path | None = None) -> dict[str, Any]:
    """The association's own collections: the PayHOA ledger (as last synced to data/payhoa.db) read beside the
    liens the association recorded. Each account with a lien, a past-due balance, or a credit gets one standing:
    RELEASE_DUE (paid, lien still of record; Civil Code 5685 gives 21 days), LIEN_SECURES_DEBT, OWED_NO_LIEN, or
    CREDIT, with the statute's next step and the section 5720 foreclosure-floor question. Amounts are integer cents.
    The ledger's past-due figure can include late charges and fees the floor excludes. Jason does not send an account
    to a collection agency, record a lien, or start a foreclosure; those are the board's decisions."""
    from jason.community import mystique
    from jason.community.collections import collections, load_ledger
    from jason.tasks.property_history import load_parcel_histories

    root = _data_dir(data_dir)
    ledger = load_ledger(root / "payhoa.db")
    if not ledger:
        return {"found": False, "note": "no PayHOA catalog at data/payhoa.db; run jason sync-catalog"}
    rows = collections(load_parcel_histories(mystique(), root), ledger)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.standing.name] = counts.get(row.standing.name, 0) + 1
    synced = max((b.synced for b in ledger.values()), default="")
    return {
        "found": True, "ledgerSynced": synced, "counts": counts, "rows": [row.as_dict() for row in rows],
        "pastDueCents": sum(row.past_due_cents for row in rows if row.past_due_cents > 0),
        "note": "the ledger as of its last sync; Jason does not submit an account to a collection agency, record a lien, or start a foreclosure",
    }


def board_digest(since: str = "", days: int = 30, data_dir: Path | None = None) -> dict[str, Any]:
    """Start here for "what does the board need to know": what recorded since ``since`` (YYYY-MM-DD, default the
    last ``days`` days), owners in default, releases the association owes, prior owners' liens with no sale since,
    how many liens stand on current owners, the association's own open liens (and other associations' liens that
    are not ours), and the solar standings. Each list is capped, with the tool that gives the rest in ``more``.
    Reads the stores; run the syncs first for the newest filings. It decides nothing."""
    from datetime import date as _date
    from datetime import timedelta

    from jason.community import mystique
    from jason.community.briefs import board_digest as build
    from jason.tasks.property_history import load_association_record, load_parcel_histories

    try:
        day = _date.fromisoformat(since.strip()) if since.strip() else _date.today() - timedelta(days=max(1, int(days)))
    except ValueError:
        return {"error": "since is YYYY-MM-DD"}
    community = mystique()
    root = _data_dir(data_dir)
    from jason.community.collections import load_ledger
    from jason.tasks.finance import finance_summary, latest_year, load as load_finance

    year = latest_year(root)
    snap = load_finance(root, year) if year else None
    finance = finance_summary(snap, community.bank_accounts()) if snap else None
    return build(load_parcel_histories(community, root), load_association_record(community, root), day,
                 ledger=load_ledger(root / "payhoa.db"), finance=finance)


def recent_filings(since: str, data_dir: Path | None = None) -> dict[str, Any]:
    """Everything recorded on or after ``since`` (YYYY-MM-DD) that touches a unit, an owner while owning here, or
    the association: transfers, lien steps, owner events, the association's own liens, governing instruments.
    Each row says what to do about it. Reads the stores; run the syncs first for the newest filings.
    """
    from datetime import date as _date

    from jason.community import mystique
    from jason.community.briefs import recent_filings as build
    from jason.tasks.property_history import load_association_record, load_parcel_histories

    try:
        day = _date.fromisoformat(since.strip())
    except ValueError:
        return {"error": "since is YYYY-MM-DD", "filings": []}
    community = mystique()
    root = _data_dir(data_dir)
    rows = build(load_parcel_histories(community, root), load_association_record(community, root), day)
    return {"since": day.isoformat(), "count": len(rows), "filings": rows}


def lifecycle_of(number: str, data_dir: Path | None = None) -> dict[str, Any]:
    """Where a recorded document number sits in the stores: on a chain, in an owner's lien lifecycle, as an owner
    event, in the association's record, or nowhere yet. A lifecycle comes back whole, with its status and the law."""
    from jason.community import mystique
    from jason.community.briefs import lifecycle_lookup
    from jason.tasks.property_history import load_association_record, load_parcel_histories

    community = mystique()
    root = _data_dir(data_dir)
    return lifecycle_lookup(load_parcel_histories(community, root), load_association_record(community, root), number)


def assessment_liens(data_dir: Path | None = None) -> dict[str, Any]:
    """The association's own assessment liens, unit by unit, with where each stands under Civil Code sections
    5650 to 5720. The sheet is the handoff; nothing is submitted to a collection agency."""
    from jason.community import mystique
    from jason.community.briefs import assessment_liens as build
    from jason.tasks.property_history import load_association_record, load_parcel_histories

    community = mystique()
    root = _data_dir(data_dir)
    return build(load_parcel_histories(community, root), load_association_record(community, root))


def explain_filing(filing: str) -> dict[str, Any]:
    """What a county filing code or name is: its family, which side gives and receives, the lifecycle it opens,
    advances, cures, or closes, and the statute that lifecycle runs under. No disk, no network."""
    from jason.community.briefs import explain_filing as build

    return build(filing)


def index_survey(data_dir: Path | None = None, limit: int = 40) -> dict[str, Any]:
    """Every cached index document counted by family, process, and filing, and the filings no model reads.

    ``unmodeled`` lists filings whose class is ``other``, most common first,
    with how many name a community party. Reads disk only.
    """
    from jason.community import mystique
    from jason.community.filings import Family, instrument_class
    from jason.community.index_cache import IndexCache

    community = mystique()
    developers = community.developers()
    project = community.index_project().upper()
    families: dict[str, int] = {}
    processes: dict[str, int] = {}
    filings: dict[str, int] = {}
    unmodeled: dict[str, dict[str, Any]] = {}
    with IndexCache(_data_dir(data_dir) / "index-cache.db") as cache:
        numbers = [row["number"] for row in cache._conn.execute("SELECT number FROM documents").fetchall()]
        for number in numbers:
            item = cache.get(number)
            if item is None:
                continue
            klass = instrument_class(item.filing_code, item.filing_name, item.kind)
            families[klass.family.value] = families.get(klass.family.value, 0) + 1
            if klass.process is not None:
                processes[klass.process.value] = processes.get(klass.process.value, 0) + 1
            label = f"{klass.code} {klass.name}".strip() or "(no filing)"
            filings[label] = filings.get(label, 0) + 1
            if klass.family is Family.OTHER:
                entry = unmodeled.setdefault(label, {"filing": label, "count": 0, "namingCommunity": 0, "examples": []})
                entry["count"] += 1
                parties = (*item.grantors, *item.grantees)
                if any(developer_for(name, developers) or project in name.upper() for name in parties):
                    entry["namingCommunity"] += 1
                if len(entry["examples"]) < 3:
                    entry["examples"].append({"number": item.number, "recorded": item.recorded.isoformat() if item.recorded else "", "parties": list(parties)[:4]})
    return {
        "documents": len(numbers),
        "families": dict(sorted(families.items(), key=lambda kv: -kv[1])),
        "processes": dict(sorted(processes.items(), key=lambda kv: -kv[1])),
        "filings": dict(sorted(filings.items(), key=lambda kv: -kv[1])[:limit]),
        "unmodeled": sorted(unmodeled.values(), key=lambda e: -e["count"])[:limit],
    }


def mechanics_liens(data_dir: Path | None = None) -> dict[str, Any]:
    """Every mechanic's lien lifecycle in the cache: against a developer during construction, against the
    association, or against an owner, with whether it was released, bonded, sued on, or expired.

    A claim of lien unsued within ninety days of recording is expired under
    Civil Code section 8460: unenforceable, but of record until released.
    Reads disk only; ``jason sync-liens`` fetches the filings first.
    """
    from jason.community import mystique
    from jason.community.filings import Process
    from jason.tasks.property_history import load_association_record, load_parcel_histories

    community = mystique()
    root = _data_dir(data_dir)
    record = load_association_record(community, root)
    found: list[dict[str, Any]] = []
    for e in record.construction:
        found.append({"against": "developer", **_lifecycle(e), "unenforceableAfter": e.unenforceable_after.isoformat() if e.unenforceable_after else ""})
    for e in record.against:
        if e.process is Process.MECHANICS_LIEN:
            found.append({"against": "association", **_lifecycle(e), "unenforceableAfter": e.unenforceable_after.isoformat() if e.unenforceable_after else ""})
    for item in load_parcel_histories(community, root):
        for lien in item.liens:
            e = lien.encumbrance
            if e.process is Process.MECHANICS_LIEN:
                found.append({
                    "against": "owner", "apn": parcel_number(item.apn), "address": item.address, "owner": lien.owner, "where": lien.where,
                    **_lifecycle(e), "unenforceableAfter": e.unenforceable_after.isoformat() if e.unenforceable_after else "",
                })
    return {"count": len(found), "liens": found}


def solar_status(apn: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """Each unit's solar standing from the lease funds' UCC filings: leased on the current owner,
    on a prior owner only, terminated, no filing, or outside the program.

    One parcel when ``apn`` is given, else every unit. Reads the stores on
    disk; ``jason sync-solar`` refreshes the filings first. No filing is not
    proof of purchase.
    """
    from jason.community import mystique
    from jason.community.property_report import shared_filing_notes
    from jason.tasks.property_history import load_parcel_histories

    community = mystique()
    program = community.solar_program()
    if program is None:
        return {"found": False, "units": [], "note": "the specification names no solar program"}
    root = Path(data_dir) if data_dir is not None else Settings.load().payhoa_catalog.parent
    digits = "".join(ch for ch in apn if ch.isdigit())
    units = []
    histories = load_parcel_histories(community, root)
    shared = shared_filing_notes(histories)
    for item in histories:
        if item.association or item.solar is None or (digits and item.apn != digits):
            continue
        record = item.solar
        current = record.current_filing
        units.append({
            "apn": parcel_number(item.apn), "address": item.address, "building": item.building,
            "currentOwner": list(item.owners), "standing": record.standing.name, "meaning": record.standing.value,
            "lessor": record.lessor, "currentFiling": current.number if current else "",
            "filings": [
                {"number": f.number, "recorded": f.recorded.isoformat() if f.recorded else "", "lessor": f.lessor,
                 "against": f.owner, "status": f.status, "terminated": f.closed.isoformat() if f.closed else "",
                 "duringTenure": f.during_tenure, "steps": list(f.steps)}
                for f in record.filings
            ],
            "note": (record.note + " " + shared.get(item.apn, "")).strip(),
        })
    return {
        "found": bool(units), "count": len(units), "program": program.name, "developer": program.developer,
        "buildings": [int(b) for b in program.buildings], "servicer": program.servicer, "units": units,
    }


def unit_number(unit: int) -> dict[str, Any]:
    """Every parcel a unit number can mean on this community.

    The 2007 plan numbered buildings 3 and 8 as 21 to 32 and 81 to 92; Watt
    numbered its six buildings 1 to 57 from scratch, so 21 to 32 name two
    parcels each. ``ambiguous`` is true then. A unit number places a deed
    only on a 2007 deed that prints the block's parent parcel.
    """
    from jason.community import mystique
    from jason.community.reports import unit_parcels

    community = mystique()
    found = unit_parcels(int(unit), community.unit_blocks())
    return {
        "unit": int(unit),
        "ambiguous": len(found) > 1,
        "parcels": [
            {"apn": parcel_number(apn), "building": int(block.building), "numbering": block.plan,
             "placesByUnit": bool(block.parent_parcels)}
            for block, apn in found
        ],
    }


def _lifecycle(e) -> dict[str, Any]:
    return {
        "process": e.process.value,
        "status": e.status,
        "opened": e.opened.recorded.isoformat() if e.opened.recorded else "",
        "closed": e.closed.isoformat() if e.closed else "",
        "debtor": list(e.debtor),
        "claimant": list(e.claimant),
        "steps": [{"number": s.number, "recorded": s.recorded.isoformat() if s.recorded else "", "filing": s.filing, "effect": s.effect} for s in e.steps],
    }


def _situs(address: str) -> str:
    """The street part of a tax-bill address: before the comma or the city."""
    text = address.split(",")[0]
    upper = text.upper()
    for city in (" SACRAMENTO", " SACTO"):
        if city in upper:
            text = text[: upper.index(city)]
            break
    return text.strip()


def _prices(root: Path, numbers: tuple[str, ...]) -> dict[str, int]:
    """Consideration from each deed extract on disk, by document number."""
    files = _deed_files(root)
    by_number: dict[str, Path] = {}
    for path in files:
        if path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        for number in document_numbers(path.name):
            by_number.setdefault(number, path)
    found: dict[str, int] = {}
    for number in dict.fromkeys(numbers):
        path = by_number.get(number)
        if path is None:
            continue
        price = deed_price(path.read_text(encoding="utf-8", errors="replace"))
        if price is not None and price.price_cents:
            found[number] = price.price_cents
    return found


def jobs_status(job: int = 0, every: bool = False, limit: int = 30, data_dir: Path | None = None) -> dict[str, Any]:
    """jason's job queue (`jason jobs`, run by `jason worker`): each job's command, the resource it uses (gpu, google,
    payhoa, local), its status (queued, running, done, failed, cancelled), attempts, who confirmed a write, and the last
    lines it printed. With ``job``: that job and the end of its log. Reads disk only; it adds, runs, and cancels nothing.
    A job that writes ran only because a person confirmed it, and a failed write waits for a person."""
    root = _data_dir(data_dir)
    if not (root / "jobs.db").is_file():
        return {"found": False, "note": "no job queue yet; add a job with jason jobs add -- <command>"}
    from jason import jobs as queue

    def plain(j: Any) -> dict[str, Any]:
        return {"id": j.id, "command": j.command, "resource": j.job_class.value, "status": j.status.value, "writes": j.writes,
                "confirmedBy": j.confirmed_by, "added": j.created, "attempts": j.attempts, "maxAttempts": j.max_attempts,
                "started": j.started, "finished": j.finished, "exitCode": j.exit_code, "note": j.note, "summary": j.summary}

    if job:
        try:
            one = queue.get(root, int(job))
        except KeyError:
            return {"found": False, "note": f"no job {job}"}
        path = queue.log_path(root, one.id)
        log = path.read_text(encoding="utf-8", errors="replace").splitlines()[-60:] if path.is_file() else []
        return {"found": True, "job": plain(one), "log": log}
    items = queue.jobs(root, every=every, limit=max(1, int(limit)))
    from collections import Counter

    return {"found": True, "jobs": [plain(j) for j in items], "byStatus": dict(Counter(j.status.value for j in items)),
            "note": "queued, running, and failed jobs" if not every else "every job, newest first"}


def _data_dir(data_dir: Path | None) -> Path:
    if data_dir is not None:
        return Path(data_dir)
    return Settings.load().payhoa_catalog.parent


def _store(root: Path) -> OwnershipStore:
    return OwnershipStore(root / "ownership.db")


def _units() -> tuple[str, ...]:
    from jason.community import mystique

    return mystique().units()


def _developers() -> tuple[Developer, ...]:
    from jason.community import mystique

    return mystique().developers()


def _find_record(store: OwnershipStore, apn: str) -> OwnershipRecord | None:
    digits = _digits(apn)
    for record in store.records():
        if _digits(record.apn) == digits:
            return record
    return None


def _record(record: OwnershipRecord) -> dict[str, Any]:
    return {
        "apn": parcel_number(record.apn),
        "number": record.document_number,
        "recorded": record.document_date.isoformat(),
        "grantors": list(record.grantors),
        "grantees": list(record.grantees),
    }


def _brief(item: Conveyance) -> dict[str, Any]:
    return {
        "number": item.number,
        "recorded": item.recorded.isoformat() if item.recorded else "",
        "grantors": list(item.grantors),
        "grantees": list(item.grantees),
        "apn": parcel_number(item.apn) if _digits(item.apn) else "",
    }


def _deed_files(root: Path) -> tuple[Path, ...]:
    """Deed scans and extracts on disk: the Drive export, then the PayHOA library export."""
    found: list[Path] = []
    site = root / "artifacts" / "site-docs" / "deeds"
    if site.is_dir():
        found.extend(sorted(path for path in site.iterdir() if path.is_file()))
    library = root / "payhoa-files" / "documents" / "Grant Deeds"
    if library.is_dir():
        found.extend(sorted(path for path in library.rglob("*") if path.is_file()))
    return tuple(found)


def _deed_file(root: Path, number: str) -> Path | None:
    """The text extract for this number. The scanned PDF is not read.

    A deed folder holds ``GD <number>.pdf`` beside ``GD <number>.pdf.md``.
    The extract is the readable one, so it wins when both are present.
    """
    wanted = "".join(ch for ch in number if ch.isdigit())
    if not wanted:
        return None
    matches = [path for path in _deed_files(root) if wanted in document_numbers(path.name)]
    for path in matches:
        if path.suffix.lower() in _TEXT_SUFFIXES:
            return path
    return matches[0] if matches else None


_TEXT_SUFFIXES = frozenset({".md", ".txt"})


def _digits(apn: str) -> str:
    return "".join(ch for ch in apn if ch.isdigit())
