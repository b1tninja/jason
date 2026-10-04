"""The JSON sources the UI reads, and the one thing it writes.

Each loader wraps a read-only tool from ``jason.mcp`` and reads disk only. ``leads`` gathers the places where the
stores show something a person has not yet pinned: a lead is evidence, not a pin, and the UI repeats that.
The one write is the board's own columns on a board item (status, owner, meeting, notes), the same fields
``jason board --set`` changes; jason's columns stay jason's.
"""

from __future__ import annotations

from typing import Any

Args = dict[str, str]


def _flag(args: Args, key: str) -> bool:
    return args.get(key, "").lower() in ("1", "true", "yes")


def board_digest(args: Args) -> dict[str, Any]:
    from jason.mcp.county import board_digest as tool

    return tool(since=args.get("since", ""), days=int(args.get("days", "30") or 30))


def _with_evidence_refs(item: dict[str, Any], root: Any = None) -> dict[str, Any]:
    """A board item with ``evidenceRefs`` beside its ``evidence`` strings (docs/console/doc-component.md): a ``DocRef``
    for each string that names a document jason keeps, ``{command}`` for a ``jason ...`` command, ``{text}`` otherwise.
    The strings stay for the callers that read them."""
    from jason.approvals.docref import refs_from_strings

    return {**item, "evidenceRefs": refs_from_strings(item.get("evidence") or [], data_dir=root)}


def board_items(args: Args) -> dict[str, Any]:
    from jason.mcp.county import _data_dir, board_items as tool

    out = tool(include_closed=_flag(args, "closed"))
    if not out.get("items"):
        return out
    root = _data_dir(None)
    return {**out, "items": [_with_evidence_refs(i, root) for i in out["items"]]}


LIENS_HELD = ("Liens the association placed are delinquency detail (restricted): open the private view to list "
              "them.")


def association_records(args: Args) -> dict[str, Any]:
    """The association's recorded instruments. The liens it placed on owners (``placed``) are delinquency detail
    beyond the unit, P3 by the data levels: they are listed only while the person's private view is open
    (``jason.web.access.private_open``), and otherwise counted (``placedHeld``) and held back on the server."""
    from jason.mcp.county import association_records as tool

    out = tool()
    placed = out.get("placed") if isinstance(out, dict) else None
    if not placed:
        return out
    try:
        from jason.web.access import private_open

        shown = private_open()
    except Exception:  # noqa: BLE001 - no request, no sign-in: closed
        shown = False
    if shown:
        return out
    return {**out, "placed": [], "placedHeld": len(placed), "placedNote": LIENS_HELD}


def records_inventory(args: Args) -> dict[str, Any]:
    from jason.mcp.county import records_inventory as tool

    return tool()


def library_status(args: Args) -> dict[str, Any]:
    from jason.mcp.county import library_status as tool

    return tool()


def document_readings(args: Args) -> dict[str, Any]:
    from jason.mcp.county import document_readings as tool

    return tool()


def jobs_status(args: Args) -> dict[str, Any]:
    from jason.mcp.county import jobs_status as tool

    return tool(job=int(args.get("job", "0") or 0), every=_flag(args, "all"))


def duties(args: Args) -> dict[str, Any]:
    """The manager's duty anchors (docs/community-manager.md): each with what it keeps straight, its sections, artifact,
    cadence, the CIV 5200 records it rests on, what jason produces, and its limit. ``anchor`` gives one duty's full
    brief with the passages retrieval found; without it, the list (no retrieval)."""
    from jason.community.duties import DUTIES

    anchor = args.get("anchor", "").strip()
    if anchor:
        from jason.mcp.county import duty_brief

        return duty_brief(anchor)
    return {"found": True, "count": len(DUTIES), "duties": [
        {"anchor": d.anchor, "keepsStraight": d.keeps_straight, "sections": d.sections, "artifact": d.artifact,
         "cadence": d.cadence.value, "when": d.when, "records": [r.value for r in d.records], "produce": d.produce, "limit": d.limit}
        for d in DUTIES]}


def calendar(args: Args) -> dict[str, Any]:
    from jason.mcp.county import association_calendar as tool

    return tool()


def meetings(args: Args) -> dict[str, Any]:
    """Every meeting's records as the catalog keeps them; with ``date``, one meeting's, and its documents as
    references grouped by kind (``docs``, ``jason.web.extra.meeting_docs.record_refs``)."""
    from jason.mcp.county import _data_dir, meeting_records as tool

    out = tool(date=args.get("date", ""))
    if args.get("date") and out.get("found"):
        from jason.web.extra.meeting_docs import record_refs

        out = {**out, "docs": record_refs(out.get("records") or [], _data_dir(None))}
    return out


def insurance(args: Args) -> dict[str, Any]:
    from jason.mcp.county import insurance_review as tool

    return tool()


def budget(args: Args) -> dict[str, Any]:
    from jason.mcp.county import budget_status as tool

    return tool(year=int(args.get("year", "0") or 0))


def reconciliations(args: Args) -> dict[str, Any]:
    from jason.mcp.county import bank_reconciliations as tool

    return tool()


def invoices(args: Args) -> dict[str, Any]:
    """The invoice review, each payment's attachments with ``doc``, the ``DocRef`` of jason's copy (P2,
    ``transactions/``)."""
    from jason.mcp.county import _data_dir, invoice_review as tool
    from jason.tasks.invoice_review import document_refs

    out = tool(payee=args.get("payee", ""), problems_only=not _flag(args, "all"), since=args.get("since", ""),
               limit=int(args.get("limit", "80") or 80))
    if out.get("payments"):
        document_refs(_data_dir(None), out["payments"])
    return out


def collections(args: Args) -> dict[str, Any]:
    from jason.mcp.county import association_collections as tool

    return tool()


def reserves(args: Args) -> dict[str, Any]:
    """The reserve transfers (each borrowing's 5515 documents carry ``doc``), with ``study``, the latest reserve
    study's ``DocRef`` (P1), when one is on disk."""
    from jason.mcp.county import _data_dir, reserve_transfers as tool
    from jason.tasks.reserves import latest_study_ref

    out = tool()
    try:
        study = latest_study_ref(_data_dir(None))
    except Exception:  # noqa: BLE001 - a study that cannot be read leaves the transfers as they are
        study = None
    return {**out, "study": study} if study else out


def hearings(args: Args) -> dict[str, Any]:
    """The hearings as `jason hearing` saved them, each with its key (its day and address), the 5855 clock as stages,
    and the decision recorded on it when there is one, and its notice as references (``noticeRefs``: the Doc, then
    jason's draft; P3). Confidential: for directors."""
    from jason.mcp.county import _data_dir, hearings as tool
    from jason.tasks.hearing_decisions import key_of
    from jason.web.extra.meeting_docs import hearing_refs

    out = tool()
    root = _data_dir(None)
    rows = []
    for h in out.get("hearings", []):
        decision = h.get("decision") or None
        stages = [{"key": "noticeBy", "label": "Notice delivered by", "date": str(h.get("noticeBy", ""))[:10], "authority": "CIV 5855(a)", "done": bool(h.get("noticeOn"))},
                  {"key": "hearing", "label": "Hearing", "date": str(h.get("start", ""))[:10], "done": bool(decision)}]
        if decision:
            stages.append({"key": "noticeDueBy", "label": "Written decision to the owner by", "date": decision["noticeDueBy"], "authority": "CIV 5855(f)"})
        elif h.get("decisionByIfHeld"):
            stages.append({"key": "decisionBy", "label": "Written decision by, if the board acts at the hearing", "date": str(h["decisionByIfHeld"])[:10], "authority": "CIV 5855(f)"})
        rows.append({**h, "key": key_of(h), "stages": [st for st in stages if st["date"]], "decision": decision,
                     "noticeRefs": hearing_refs(h, root)})
    return {**out, "hearings": rows}


def title_watch(args: Args) -> dict[str, Any]:
    from jason.mcp.county import title_watch as tool

    return tool(apn=args.get("apn", ""), standing=args.get("standing", ""), attention=_flag(args, "attention"))


def open_items(args: Args) -> dict[str, Any]:
    from jason.mcp.county import open_items as tool

    return tool(days=int(args.get("days", "30") or 30))


def utility_payments(args: Args) -> dict[str, Any]:
    """The utility payments' audit, each attachment with ``doc``, the ``DocRef`` of jason's copy (P2,
    ``transactions/``)."""
    from jason.mcp.county import _data_dir, utility_payments as tool
    from jason.tasks.utility_payments import attachment_refs

    out = tool(problems_only=not _flag(args, "all"), since=args.get("since", ""), limit=int(args.get("limit", "80") or 80))
    if out.get("payments"):
        attachment_refs(_data_dir(None), out["payments"])
    return out


def ledger_validation(args: Args) -> dict[str, Any]:
    """The ledger validation, each library copy as a ``DocRef`` (``libraryDocs`` on a run, ``doc`` on a row)."""
    from jason.mcp.county import _data_dir, ledger_validation as tool
    from jason.tasks.ledger_reports import library_refs

    out = tool()
    return library_refs(_data_dir(None), out) if out.get("found") else out


def legal_cases(args: Args) -> dict[str, Any]:
    from jason.mcp.county import legal_cases as tool

    return tool()


def audit_chains(args: Args) -> dict[str, Any]:
    from jason.mcp.county import audit_chains as tool

    return tool(apn=args.get("apn", ""))


def request_links(args: Args) -> dict[str, Any]:
    from jason.mcp.county import request_links as tool

    return tool(unit=args.get("unit", ""), drafts_only=_flag(args, "drafts"), limit=int(args.get("limit", "40") or 40))


def canvases(args: Args) -> dict[str, Any]:
    """The canvases on disk; ``key`` gives one in full."""
    from jason.mcp.county import _data_dir
    from jason.tasks import canvases as store

    key = args.get("key", "").strip()
    if key:
        try:
            root = _data_dir(None)
            return {"found": True, "canvas": store.with_refs(store.encode(store.load(root, key)), root)}
        except KeyError:
            return {"found": False, "note": f"no canvas {key}"}
    items = store.load_all(_data_dir(None))
    return {"found": True, "count": len(items), "statuses": [s.value for s in store.CanvasStatus],
            "canvases": [{**store.encode(c), "clips": len(c.clips), "notes": ""} for c in items]}


def _community():
    from jason.community import community

    return community()


def templates(args: Args) -> dict[str, Any]:
    """The letter templates: each with its tokens sorted by who fills them (the profile, a general citation, or the run).
    With ``kind`` and ``V_<TOKEN>`` args, the body as Markdown with those values over the profile's, the tokens still
    open, and the command that fills a Drive copy. The body is the same text the Doc is built from; the page copies
    nothing in Drive."""
    import os
    import shlex

    from jason.community.template_values import lint, profile_values
    from jason.community.templates import TemplateKind, body_markdown
    from jason.mcp.county import _data_dir
    from jason.tasks.template_gen import load_state
    from jason.tasks.template_gen import templates as rows

    community = _community()
    state = load_state(_data_dir(None), os.environ.get("JASON_PROFILE", "mystique"))
    found = rows(community, state)
    kind = args.get("kind", "").strip()
    if not kind:
        root = _data_dir(None)

        def template_doc(t: Any) -> dict[str, Any]:
            """The template's Doc as a document reference (``drive:<id>``), its original "Open in Google"."""
            from jason.approvals.docref import drive_ref

            try:
                return {"doc": drive_ref(t.drive_id, name=t.title, data_dir=root)} if t.drive_id else {}
            except ValueError:
                return {}

        return {"found": bool(found), "templates": [
            {"kind": t.kind.slug, "title": t.title, "driveId": t.drive_id, "folderId": t.folder_id, "authority": t.authority,
             "optional": list(t.optional), "linkTokens": list(t.link_tokens), "tokens": list(t.tokens),
             "lint": {"profile": list(l.profile), "general": list(l.general), "run": list(l.run)}, **template_doc(t)}
            for t in found for l in [lint(t.title, t.tokens, community)]]}
    try:
        tk = TemplateKind.from_slug(kind) if hasattr(TemplateKind, "from_slug") else next(k for k in TemplateKind if k.slug == kind)
    except (StopIteration, ValueError):
        return {"found": False, "note": f"no template {kind}; one of {', '.join(k.slug for k in TemplateKind)}"}
    t = next((x for x in found if x.kind is tk), None)
    run = {k[2:]: v for k, v in args.items() if k.startswith("V_") and v.strip()}
    values = {**profile_values(community), **run}
    optional = tuple(t.optional) if t else ()
    markdown = body_markdown(tk, values, optional)
    tokens = list(t.tokens) if t else []
    open_tokens = [x for x in tokens if not values.get(x) and x not in optional]
    name = args.get("name", "").strip() or f"{t.title if t else kind} draft"
    cmd = " ".join(["jason letter", "--template", kind, "--name", shlex.quote(name)] + [f"--set {shlex.quote(f'{k}={v}')}" for k, v in run.items()] + ["--yes"])
    return {"found": True, "kind": kind, "title": t.title if t else kind, "driveId": t.drive_id if t else "", "markdown": markdown,
            "tokens": tokens, "open": open_tokens, "command": cmd,
            "note": "the body as the Doc is built from it; the command copies the template in Drive and fills it, and sends nothing"}


def drive_files(args: Args) -> dict[str, Any]:
    """The Drive catalog on disk (`jason drive --sync`): files whose name or path contains ``q``, with the kind a canvas
    would embed them as. Reads disk only."""
    import json

    from jason.mcp.county import _data_dir

    path = _data_dir(None) / "drive" / "files.json"
    if not path.is_file():
        return {"found": False, "note": "no Drive catalog; run jason drive --sync"}
    raw = json.loads(path.read_text(encoding="utf-8"))
    q = args.get("q", "").strip().lower()
    limit = int(args.get("limit", "30") or 30)
    kinds = {"application/vnd.google-apps.document": "doc", "application/vnd.google-apps.spreadsheet": "sheet",
             "application/vnd.google-apps.presentation": "slides", "application/vnd.google-apps.form": "form", "application/pdf": "drive"}
    rows_ = []
    for f in raw.get("files", []):
        hay = f"{f.get('name', '')} {f.get('path', '')}".lower()
        if q and q not in hay:
            continue
        mime = f.get("mimeType", "")
        kind = kinds.get(mime) or ("image" if mime.startswith("image/") else "drive")
        rows_.append({"id": f.get("id"), "name": f.get("name"), "path": f.get("path"), "mimeType": mime, "kind": kind, "link": f.get("link"), "modified": f.get("modified")})
    rows_.sort(key=lambda r: str(r.get("modified") or ""), reverse=True)
    return {"found": True, "syncedAt": raw.get("syncedAt"), "matching": len(rows_), "files": rows_[:limit]}


def photos(args: Args) -> dict[str, Any]:
    """The photo albums saved under data/photos (`jason photos --pick`): each with its label and items, whose ``path``
    is relative to data/ and served by /api/file. Reads disk only."""
    import json

    from jason.mcp.county import _data_dir

    folder = _data_dir(None) / "photos"
    if not folder.is_dir():
        return {"found": False, "note": "no albums; run jason photos --pick"}
    albums = []
    for manifest in sorted(folder.glob("*/manifest.json")):
        m = json.loads(manifest.read_text(encoding="utf-8"))
        items = [{"filename": i.get("filename"), "path": i.get("path"), "createTime": i.get("createTime"), "mimeType": i.get("mimeType")}
                 for i in m.get("items", []) if str(i.get("mimeType", "")).startswith("image/")]
        albums.append({"slug": m.get("slug", manifest.parent.name), "label": m.get("label", ""), "count": len(items), "items": items,
                       "labels": m.get("labels", []), "driveFolderId": (m.get("drive") or {}).get("folderId")})
    return {"found": bool(albums), "albums": albums}


def meeting(args: Args) -> dict[str, Any]:
    """One board meeting as the board sees it: the date (default the schedule's next), the last days to give notice
    (CIV 4920: four days; two for an executive-only meeting), the items proposed or on the agenda by session, the agenda
    draft, the packet (each item's background, the law, what the records show now, options, a draft motion), the
    minutes frame the Secretary fills, and the commands that write the Doc, the packet, and the minutes draft. Reads
    disk only; the page writes none of them."""
    from datetime import date as _date

    from jason.community.board_items import ItemStatus, agenda_session
    from jason.mcp.county import _data_dir
    from jason.tasks.board_items import _encode, agenda, load, notice_date, notice_period
    from jason.tasks.meeting_agenda import minutes_template

    community = _community()
    root = _data_dir(None)
    today = _date.today()
    raw = args.get("date", "").strip()
    try:
        day = _date.fromisoformat(raw) if raw else community.next_meeting(today)
    except ValueError:
        return {"found": False, "note": "date is YYYY-MM-DD"}
    items = [i for i in load(root) if i.status in (ItemStatus.PROPOSED, ItemStatus.ON_AGENDA)]
    rows = [{**_encode(i), "agendaSession": agenda_session(i).value} for i in items]
    agenda_lines = agenda(items, day, community=community)
    notes: list[str] = []
    try:
        from jason.tasks.board_packet import packet as build_packet

        packet_md = "\n".join(build_packet(root, community, day))
    except Exception as exc:  # a packet needs the stores its items cite; the meeting page stands without it
        packet_md, notes = "", [f"packet: {type(exc).__name__}: {exc}"]
    try:
        minutes_md = "\n".join(minutes_template(day, [], agenda_lines))
    except Exception as exc:
        minutes_md, notes = "", notes + [f"minutes frame: {type(exc).__name__}: {exc}"]
    iso = day.isoformat()
    try:
        from jason.tasks.board_members import current_names

        directors = current_names(root)
    except Exception:
        directors = []
    from jason.tasks import decisions as decided

    recorded = decided.for_meeting(root, day)
    return {
        "found": True, "date": iso, "today": today.isoformat(), "directors": directors,
        # An executive-session decision is noted only generally here (CIV 4935(e)); its record is the private view's.
        "decisions": [decided.as_dict(d) for d in decided.open_only(recorded)], "executiveDecisions": decided.general_notes(recorded),
        "noticeBy": notice_date(day, community=community).isoformat(),
        "executiveNoticeBy": notice_date(day, executive_only=True, community=community).isoformat(),
        # How many days, and from where: the statute's floor, or the governing documents' longer period (CIV 4920(b)(3)).
        "noticeDays": notice_period(community=community)[0], "noticeAuthority": notice_period(community=community)[1],
        "executiveNoticeDays": notice_period(executive_only=True, community=community)[0],
        "executiveNoticeAuthority": notice_period(executive_only=True, community=community)[1],
        "items": rows, "openCount": sum(1 for r in rows if r["agendaSession"] == "open session"),
        "executiveCount": sum(1 for r in rows if r["agendaSession"] != "open session"),
        "agendaMarkdown": "\n".join(agenda_lines), "packetMarkdown": packet_md, "minutesTemplate": minutes_md, "notes": notes,
        "commands": {
            "agendaDoc": f"jason board --agenda <previous agenda Doc id> --date {iso} --doc --yes",
            "packetDoc": f"jason board --packet --date {iso} --doc --yes",
            "minutesDraft": f"jason board --minutes {iso}",
            "notice": f"jason board --set <item id> --status \"on agenda\" --meeting {iso}",
        },
        "caveats": ["No action may be taken on an item not on the noticed agenda (CIV 4930). The agenda, packet, and minutes are drafts a person finishes; the board decides."],
    }


def _time_zone(community: Any) -> str:
    for name in ("time_zone", "timezone"):
        value = getattr(community, name, None)
        if callable(value):
            try:
                value = value()
            except Exception:
                value = None
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "America/Los_Angeles"


def embeds(args: Args) -> dict[str, Any]:
    """What a canvas can embed beside Drive files and photos: the Google calendar ``jason calendar`` writes to, the
    association's time zone, and the Zoom meetings on disk (`jason zoom --sync`) that have a recording, newest first,
    each with the files present under its folder as paths relative to data/ and each file's ``doc``, its ``DocRef``
    (``file:<path>``, at the level ``jason.web.access`` gives it: P3 for a call its record shows ran into executive
    session). An executive session's or a hearing's recording is confidential (Civil Code 4935) and listed only with
    ``confidential=1``. Reads disk only; calls neither Zoom nor Google."""
    from jason.approvals.docref import file_ref
    from jason.mcp.county import _data_dir
    from jason.tasks.zoom import FILE_NAMES, MEDIA_NAMES, ZOOM_DIR, load_index

    community = _community()
    calendar_id = str(getattr(community, "calendar_id", lambda: "")() or "")
    root = _data_dir(None)
    limit = int(args.get("limit", "24") or 24)
    notes: list[str] = []
    index = load_index(root)
    rows = index.get("meetings", []) if isinstance(index, dict) else []
    if not index:
        notes.append("no Zoom index; run jason zoom --sync")
    show_confidential = _flag(args, "confidential")
    held_back = 0
    recordings: list[dict[str, Any]] = []
    # what sync saves in a meeting folder: the media and Zoom's files by their fixed names, plus the derived text files
    kinds = {MEDIA_NAMES["M4A"]: "audio", MEDIA_NAMES["MP4"]: "video", FILE_NAMES["TRANSCRIPT"]: "transcript",
             "transcript.txt": "transcript", "summary.md": "summary", FILE_NAMES["CHAT"]: "chat"}
    for row in sorted(rows, key=lambda r: str(r.get("start") or r.get("date") or ""), reverse=True):
        folder_rel = str(row.get("folder") or "")
        folder = root / ZOOM_DIR / folder_rel if folder_rel else None
        files: list[dict[str, str]] = []
        if folder is not None and folder.is_dir():
            for name, kind in kinds.items():
                if (folder / name).is_file():
                    files.append({"type": kind, "name": name, "path": f"{ZOOM_DIR}/{folder_rel}/{name}"})
        if not files and not row.get("cloud"):
            continue  # a meeting with no recording
        if row.get("confidential") and not show_confidential:
            held_back += 1
            continue
        for f in files:
            try:
                f["doc"] = file_ref(f["path"], name=f"{row.get('topic') or 'Meeting'} ({f['type']})", data_dir=root)
            except ValueError:
                pass
        recordings.append({
            "date": row.get("date") or (str(row.get("start") or "")[:10] or None), "topic": row.get("topic") or "", "uuid": row.get("uuid") or "",
            "kind": row.get("kind") or "", "confidential": bool(row.get("confidential")),
            "shareUrl": str(row.get("shareUrl") or row.get("share_url") or ""), "playUrl": str(row.get("playUrl") or row.get("play_url") or ""),
            "cloud": list(row.get("cloud") or []), "files": files,
        })
    if held_back:
        notes.append(f"{held_back} confidential recording(s) held back (Civil Code 4935); pass confidential=1 to list them")
    return {"found": True, "calendarId": calendar_id, "timeZone": _time_zone(community), "syncedAt": index.get("syncedAt") if isinstance(index, dict) else None,
            "recordings": recordings[:limit], "maps": {}, "notes": notes}


def decisions(args: Args) -> dict[str, Any]:
    """The board's recorded decisions (`tasks.decisions`), all or for one ``meeting``, with each vote's tally and what the
    votes say on their face; the outcome is the board's word. Reads disk only.

    A decision made in executive session is listed only in the private view (``meeting_room.private_view``, logged);
    otherwise it is left out and counted in ``heldBack``, with its meetings' general notes (CIV 4935(e))."""
    from jason.mcp.county import _data_dir
    from jason.tasks import decisions as store
    from jason.web.extra.meeting_room import private_view

    root = _data_dir(None)
    day = args.get("meeting", "").strip()
    rows = store.for_meeting(root, day) if day else store.load(root)
    held = [d for d in rows if store.is_executive(d)]
    if held and not private_view(day, path="board/decisions.json"):
        rows = store.open_only(rows)
    else:
        held = []
    out = {"found": True, "count": len(rows), "outcomes": list(store.OUTCOMES), "votes": list(store.VOTES),
           "decisions": [store.as_dict(d) for d in sorted(rows, key=lambda d: (d.meeting, d.recorded), reverse=True)]}
    if held:
        meetings = sorted({d.meeting for d in held}, reverse=True)
        out.update(heldBack=len(held), executiveNotes=[{"meeting": m, "notes": store.general_notes([d for d in held if d.meeting == m])} for m in meetings],
                   note=f"{len(held)} executive-session decision(s) held back (Civil Code 4935(e)); open the private view to see them.")
    return out


# The facts a profile supplies, by duty, as Community methods with empty defaults; supplied when the call returns
# something. General names only; the profile file that sets each is the profile's own layout.
FACTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("identity", ("name", "corporate_name", "identity", "letterhead", "email_domains", "google_groups", "drive_home")),
    ("property", ("buildings", "units", "parcels", "common_areas", "association_common_areas", "floor_plans", "cost_centers")),
    ("governing documents", ("ccrs", "pins", "developers", "public_reports", "supersessions", "citations", "document_rules", "kind_rules")),
    ("money", ("bank_accounts", "transaction_rules", "reserve_components", "reserve_budget_lines", "obligations", "vendor_portals", "utility_accounts", "utility_budget_lines")),
    ("insurance", ("insurance", "insurance_workbook_id", "premium_rules", "coverages_not_carried")),
    ("meetings and board", ("meeting_schedule", "board", "board_items_sheet", "zoom_meeting_rules", "meeting_record_rules", "calendar_policy", "calendar_id", "hearing_policy")),
    ("records and library", ("document_sync_rules", "sync_rules", "library_folders", "known_files", "drive_roots", "site_pages", "registers", "registers_folder", "photo_album_rule")),
    ("letters and forms", ("document_templates", "packets", "notice_rules", "request_forms", "help_articles", "payhoa_tags", "payhoa_fields", "task_prompts")),
    ("mail and email", ("mail_addresses", "senders", "topic_rules", "intent_rules", "meeting_email_rules", "communication_search")),
    ("legal", ("legal_cases", "legal_holds", "privilege_parties", "leasing_rules", "rule_changes")),
)

ACCOUNTS: tuple[tuple[str, str, str], ...] = (
    ("PayHOA", "payhoa_record_uid", "jason login; data/payhoa"),
    ("Google", "google_oauth_record_uid", "docs/setup.md: the OAuth client and consent"),
    ("Keeper", "keeper_username", ".env: keeper_username; jason login"),
    ("SMUD (utility portal)", "smud_record_uid", "jason sync-bills"),
    ("City utility (i-doxs)", "idoxs_record_uid", "jason sync-bills"),
    ("City permits (Accela)", "accela_record_uid", "jason permit-status --sync"),
)


def _fact_supplied(community: Any, name: str) -> bool | None:
    fn = getattr(community, name, None)
    if fn is None:
        return None
    try:
        value = fn() if callable(fn) else fn
    except Exception:
        return False
    if value is None or value == "" or value == () or value == [] or value == {}:
        return False
    return True


def _accounts() -> list[dict[str, Any]]:
    try:
        from jason.config import Settings

        settings = Settings.load()
    except Exception as exc:  # no .env here; every account reads as unknown
        return [{"service": s, "set": None, "how": how, "note": f"settings not loaded: {type(exc).__name__}"} for s, _, how in ACCOUNTS]
    return [{"service": s, "set": bool(getattr(settings, attr, "") or ""), "how": how} for s, attr, how in ACCOUNTS]


def communities(args: Args) -> dict[str, Any]:
    """The portal: every profile this checkout can load, the active one marked, with its onboarding progress (facts
    supplied, accounts connected, records pinned, deliveries found, library files, open requests). Loads only the
    active profile; the others are listed from where they were found."""
    from jason.community.profile import profiles

    rows = profiles()
    out = []
    for row in rows:
        card: dict[str, Any] = {**row}
        if row["active"]:
            card["progress"] = onboarding({"summary": "1"})["summary"]
        out.append(card)
    return {"found": True, "count": len(out), "communities": out}


def onboarding(args: Args) -> dict[str, Any]:
    """The active community's onboarding: the accounts, the facts by duty, the request list with what a person
    recorded and what the stores already show (a 5200 record with a holder, a delivery found), and the gaps.
    ``summary=1`` gives the counts only."""
    from jason.mcp.county import _data_dir
    from jason.tasks import onboarding_requests as ob

    root = _data_dir(None)
    community = _community()
    facts = [{"duty": duty, "facts": [{"name": n, "supplied": _fact_supplied(community, n)} for n in names]} for duty, names in FACTS]
    supplied = sum(1 for d in facts for f in d["facts"] if f["supplied"])
    total_facts = sum(len(d["facts"]) for d in facts)
    accounts = _accounts()
    recorded = ob.load(root)
    held: dict[str, bool] = {}
    gaps: list[str] = []
    try:
        for rec in records_inventory({}).get("records", []):
            held[rec["record"]] = not rec.get("gap")
            if rec.get("gap"):
                gaps.append(f"{rec['record']}: {rec['gap']}")
    except Exception as exc:
        gaps.append(f"records inventory not read: {type(exc).__name__}")
    found_deliveries: dict[str, bool] = {}
    try:
        for d in association_records({}).get("deliveries", []):
            found_deliveries[d["delivery"]] = bool(d.get("found")) and not d.get("missing")
    except Exception:
        pass
    items = []
    for c in ob.catalog_dicts():
        r = recorded.get(c["key"])
        store_says = ""
        if c["record"] and c["record"] in held:
            store_says = "a holder is pinned for this record" if held[c["record"]] else "the inventory shows a gap for this record"
        if c["delivery"] and c["delivery"] in found_deliveries:
            store_says = (store_says + "; " if store_says else "") + ("the delivery is found" if found_deliveries[c["delivery"]] else "the delivery is missing")
        items.append({**c, "status": r.status if r else ob.RequestStatus.NOT_ASKED.value, "askedOf": r.asked_of if r else "", "askedOn": r.asked_on if r else "",
                      "chasedOn": r.chased_on if r else "", "receivedOn": r.received_on if r else "", "filed": r.filed if r else "", "reason": r.reason if r else "",
                      "note": r.note if r else "", "history": r.history if r else [], "storeSays": store_says})
    counts: dict[str, int] = {}
    for it in items:
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    summary = {"factsSupplied": supplied, "factsTotal": total_facts, "accountsSet": sum(1 for a in accounts if a["set"]), "accountsTotal": len(accounts),
               "recordsHeld": sum(1 for v in held.values() if v), "recordsTotal": len(held), "deliveriesFound": sum(1 for v in found_deliveries.values() if v),
               "deliveriesTotal": len(found_deliveries), "requests": counts, "gaps": len(gaps)}
    if _flag(args, "summary"):
        return {"found": True, "summary": summary}
    return {"found": True, "summary": summary, "accounts": accounts, "facts": facts, "items": items, "gaps": gaps,
            "statuses": [s.value for s in ob.RequestStatus], "holders": [h.value for h in ob.Holder], "groups": [g.value for g in ob.Group],
            "caveats": ["The request list is sent by a person; the page writes what was asked and what came back, and files nothing.",
                        "A store's reading (a holder pinned, a delivery found) is what the profile and the library show; the person's entry is the record."]}


def request_letter(args: Args) -> dict[str, Any]:
    """The request letter from the items marked ``asked`` (or the ``keys`` given, comma-separated), in plain words."""
    from jason.mcp.county import _data_dir
    from jason.tasks import onboarding_requests as ob

    keys = {k.strip() for k in args.get("keys", "").split(",") if k.strip()}
    recorded = ob.load(_data_dir(None))
    chosen = [c for c in ob.catalog_dicts() if (c["key"] in keys) or (not keys and recorded.get(c["key"]) and recorded[c["key"]].status == ob.RequestStatus.ASKED.value)]
    name = getattr(_community(), "name", "the association")
    name = name() if callable(name) else name
    return {"found": True, "count": len(chosen), "markdown": ob.request_letter(chosen, association=str(name or "the association"), to=args.get("to", "the board"))}


def library(args: Args) -> dict[str, Any]:
    from jason.mcp.county import library_search as tool

    return tool(kind=args.get("kind", ""), record=args.get("record", ""), period=args.get("period", ""), words=args.get("words", ""),
                include_confidential=_flag(args, "confidential"), limit=int(args.get("limit", "25") or 25))


def owner_info(args: Args) -> dict[str, Any]:
    """The owner-information plan the last `jason owner-info` run computed (`tasks.owner_info_plan`): each PayHOA tag
    write an answer calls for, with a person's confirmation beside it; the requests left to complete; the owners by
    standing; and the apply command once every write is confirmed. Reads disk only."""
    from jason.mcp.county import _data_dir
    from jason.tasks.owner_info_plan import status

    return status(_data_dir(None))


def rule_changes(args: Args) -> dict[str, Any]:
    """The proposed rule changes in the specification (`jason rule-change --list`). With ``key``: the change's sections
    as current and proposed text (from the outline on disk), its placeholders ``[in brackets]`` with any ``V_`` values
    filled for the preview, the decisions the board and counsel settle first, and the Civil Code 4360 timeline from
    ``notice`` (default today) to ``decision`` (default the first meeting 28 days out) with ``comment``. Reads disk only;
    the member notice is a Gmail draft a person saves with --yes and sends."""
    import re
    from datetime import date as _date

    from jason.mcp.county import _data_dir
    from jason.tasks import rule_change as rc

    community = _community()
    changes = tuple(community.rule_changes())
    key = args.get("key", "").strip()
    if not key:
        return {"found": bool(changes), "changes": [
            {"key": c.key, "slug": c.slug, "title": c.title, "document": c.document, "documentTitle": c.document_title, "purpose": c.purpose,
             "effect": c.effect, "sections": len(c.sections), "placeholders": list(c.placeholders()), "decisions": list(c.decisions),
             "authorities": list(c.authorities)} for c in changes]}
    try:
        change = rc.find_change(changes, key)
    except LookupError as exc:
        return {"found": False, "note": str(exc)}
    root = _data_dir(None)
    try:
        current = rc.current_sections(root, change.document)
    except Exception as exc:  # no outline on disk: the proposed text still shows
        current = {}
        current_note = f"the current text is not on disk ({type(exc).__name__}); run jason outlines"
    else:
        current_note = ""
    values = {k[2:]: v for k, v in args.items() if k.startswith("V_") and v.strip()}

    def fill(text: str) -> str:
        return re.sub(r"\[([^\[\]]+)\]", lambda m: values.get(m.group(1), m.group(0)), text)

    blocks = [fill(b) for b in rc.section_blocks(change, current)]
    today = _date.today()
    try:
        notice = _date.fromisoformat(args["notice"]) if args.get("notice") else today
        decision = _date.fromisoformat(args["decision"]) if args.get("decision") else None
        comment = _date.fromisoformat(args["comment"]) if args.get("comment") else None
        schedule = community.meeting_schedule()
        when = rc.timeline(schedule, notice_date=notice, decision=decision, comment_deadline=comment)
        stages = [
            {"key": "notice", "label": "Member notice goes out", "date": when.notice_date.isoformat(), "authority": "CIV 4360(a)"},
            {"key": "noticeBy", "label": "Last day for the notice", "date": when.notice_by.isoformat(), "authority": "28 days before the decision"},
            {"key": "agendaNoticeBy", "label": "Agenda notice for the decision meeting", "date": when.agenda_notice_by.isoformat(), "authority": "CIV 4920"},
            {"key": "comment", "label": "Members' comments due", "date": when.comment_deadline.isoformat(), "authority": "CIV 4360(a)"},
            {"key": "decision", "label": "Board decides", "date": when.decision.isoformat(), "authority": "CIV 4360(a)"},
            {"key": "adoptionNoticeBy", "label": "Notice of adoption to members", "date": when.adoption_notice_by.isoformat(), "authority": "CIV 4360(c)"},
            {"key": "reversalBy", "label": "Members' reversal request window closes", "date": when.reversal_request_by.isoformat(), "authority": "CIV 4365"},
        ]
        timeline_note = ""
    except (ValueError, KeyError) as exc:
        stages, timeline_note = [], str(exc)
    cmd = " ".join(["jason rule-change", change.key, *([f"--notice-date {notice.isoformat()}"] if args.get("notice") else []),
                    *([f"--decision {args['decision']}"] if args.get("decision") else []), "--draft-email --yes"])
    return {"found": True, "key": change.key, "title": change.title, "documentTitle": change.document_title, "purpose": change.purpose, "effect": change.effect,
            "authorities": list(change.authorities), "decisions": list(change.decisions), "placeholders": list(change.placeholders()),
            "open": [p for p in change.placeholders() if p[1:-1] not in values], "sectionsMarkdown": "\n\n".join(blocks), "currentNote": current_note,
            "stages": stages, "timelineNote": timeline_note, "today": today.isoformat(), "command": cmd,
            "caveats": list(change.caveats) + ["A bracketed choice is the board's; jason never fills it. Whether CIV 4355 covers the rule is the board's call with counsel.",
                                               "The member notice is saved as a Gmail draft with no recipients; a person addresses and sends it."]}


def leads(args: Args) -> dict[str, Any]:
    """Everything the stores show that no person has pinned yet, in one shape: ``source`` names the tool, ``kind``
    the sort of lead, ``title`` the thing, ``detail`` why it is a lead, and ``next`` what a person would do."""
    rows: list[dict[str, Any]] = []
    notes: list[str] = []

    def attempt(source: str, fn) -> None:
        try:
            fn()
        except Exception as exc:  # a missing store is a note, not a crash
            notes.append(f"{source}: {type(exc).__name__}: {exc}")

    def _library() -> None:
        status = library_status({})
        for path in status.get("unclassified", []):
            rows.append({"source": "library_status", "kind": "unclassified file", "title": path,
                         "detail": "no name rule, phrase rule, or model placed it", "next": "classify it, or add a rule row"})

    def _inventory() -> None:
        for rec in records_inventory({}).get("records", []):
            if rec.get("gap"):
                rows.append({"source": "records_inventory", "kind": "records gap", "title": rec["record"],
                             "detail": rec["gap"], "next": "pin where the record is kept, or gather it",
                             "authority": rec.get("citation", "")})

    def _readings() -> None:
        for p in document_readings({}).get("supersessions", []):
            if not p.get("pinned"):
                rows.append({"source": "document_readings", "kind": "supersession not pinned",
                             "title": f"{p['number']} superseded by {p['supersededBy']}",
                             "detail": f"the text of {p['source']} says so (phase {p.get('phase') or '?'})",
                             "next": "read both instruments, then pin it in the profile"})

    def _association() -> None:
        rec = association_records({})
        for d in rec.get("deliveries", []):
            for missing in d.get("missing", []):
                rows.append({"source": "association_records", "kind": "delivery missing", "title": d["delivery"],
                             "detail": missing, "next": "order the copy, or find it in the files"})
        for r in rec.get("unplaced", []):
            rows.append({"source": "association_records", "kind": "unplaced instrument", "title": r["number"],
                         "detail": f"{r['filing']} recorded {r['recorded'] or '?'} by {r['recordedBy'] or '?'}; tied to no delivery or phase",
                         "next": "read it and place it, or mark it as not the association's"})

    attempt("library_status", _library)
    attempt("records_inventory", _inventory)
    attempt("document_readings", _readings)
    attempt("association_records", _association)
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["kind"]] = counts.get(r["kind"], 0) + 1
    return {"count": len(rows), "counts": counts, "rows": rows, "notes": notes,
            "caveats": ["A lead is evidence, not a pin: a reading, a match, or a gap is something to read, never a finding."]}


# Features in their own modules (jason.web.extra.<module>), resolved on first call so a missing one is a 500 for
# that source alone, never a failed import of the app.
EXTRA_LOADERS: dict[str, str] = {
    "registers": "jason.web.extra.registers:registers",
    "delinquency": "jason.web.extra.delinquency:delinquency",
    "minutes-review": "jason.web.extra.minutes_review:minutes_review",
    "insurance-renewals": "jason.web.extra.insurance_renewals:insurance_renewals",
    "reserve-findings": "jason.web.extra.reserve_findings:reserve_findings",
    "records-requests": "jason.web.extra.records_requests:records_requests",
    "mail-triage": "jason.web.extra.mail_triage:mail_triage",
    "approvals": "jason.web.approvals:approvals",  # the letters inbox with the engine's approvals beside it
    "agenda-plan": "jason.web.extra.agenda_plan:agenda_plan",
    "meeting-room": "jason.web.extra.meeting_room:meeting_room",
    "dock": "jason.web.extra.dock:dock",
    "people": "jason.web.extra.people:people",  # who holds each office: a signed-in roster person only, read-only
    "theme": "jason.web.extra.theme:theme",
    "community-profile": "jason.web.extra.community_profile:community_profile",
    "associations": "jason.web.extra.discovery:associations",
    "documents-located": "jason.web.extra.discovery:documents_located",
    "key-documents": "jason.web.extra.key_documents:key_documents",
    "instrument-graph": "jason.web.extra.key_documents:instrument_graph",
    "governing-documents": "jason.web.extra.governing_documents:governing_documents",  # with recorded and Drive copies
    "owner-digest": "jason.web.extra.owner_view:owner_digest",  # the owner's Overview, in place of the board's digest
    "onboarding-session": "jason.web.extra.onboarding_setup:onboarding_session",  # gates, computed statuses, questions
}
EXTRA_WRITERS: dict[str, str] = {
    "registers": "jason.web.extra.registers:write",
    "delinquency": "jason.web.extra.delinquency:write",
    "minutes-review": "jason.web.extra.minutes_review:write",
    "insurance-renewals": "jason.web.extra.insurance_renewals:write",
    "reserve-findings": "jason.web.extra.reserve_findings:write",
    "records-requests": "jason.web.extra.records_requests:write",
    "mail-triage": "jason.web.extra.mail_triage:write",
    "approvals": "jason.web.extra.approvals:write",
    "agenda-plan": "jason.web.extra.agenda_plan:write",
    "meeting-room": "jason.web.extra.meeting_room:write",
    "dock": "jason.web.extra.dock:write",
    "documents-located": "jason.web.extra.discovery:write",  # queues a locate job; the county is never read here
    "key-documents": "jason.web.extra.key_documents:write",  # link, upload, unlink, status: jason's own store
    "instrument-graph": "jason.web.extra.key_documents:reveal",  # owners' names for a named person, logged
    "intake": "jason.web.extra.onboarding_setup:write",  # a signed-in person's answer, queued; applied in a terminal
}


def _lazy(spec: str):
    import importlib

    module, _, name = spec.partition(":")

    def call(*a, **kw):
        return getattr(importlib.import_module(module), name)(*a, **kw)
    call.__name__ = name
    return call


def extra_writer(store: str):
    """The writer for an extra store, or None when there is none."""
    spec = EXTRA_WRITERS.get(store)
    return _lazy(spec) if spec else None


def default_loaders() -> dict[str, Any]:
    return {**{name: _lazy(spec) for name, spec in EXTRA_LOADERS.items()},
        "board-digest": board_digest,
        "board-items": board_items,
        "association-records": association_records,
        "records-inventory": records_inventory,
        "library-status": library_status,
        "document-readings": document_readings,
        "jobs": jobs_status,
        "leads": leads,
        "duties": duties,
        "calendar": calendar,
        "meetings": meetings,
        "insurance": insurance,
        "budget": budget,
        "reconciliations": reconciliations,
        "invoices": invoices,
        "collections": collections,
        "reserves": reserves,
        "hearings": hearings,
        "title-watch": title_watch,
        "open-items": open_items,
        "utility-payments": utility_payments,
        "ledger-validation": ledger_validation,
        "legal-cases": legal_cases,
        "audit-chains": audit_chains,
        "request-links": request_links,
        "canvases": canvases,
        "templates": templates,
        "meeting": meeting,
        "decisions": decisions,
        "communities": communities,
        "onboarding": onboarding,
        "request-letter": request_letter,
        "library": library,
        "owner-info": owner_info,
        "rule-changes": rule_changes,
        "drive-files": drive_files,
        "photos": photos,
        "embeds": embeds,
    }


BOARD_FIELDS = ("status", "owner", "meeting", "notes")


def set_board_item(item_id: str, changes: dict[str, Any]) -> dict[str, Any]:
    """Change a board item's board-owned fields. Anything else is refused (``ValueError``), as ``jason board --set`` refuses it."""
    from jason.mcp.county import _data_dir
    from jason.tasks.board_items import _encode, set_fields

    unknown = sorted(set(changes) - set(BOARD_FIELDS))
    if unknown:
        raise ValueError(f"{', '.join(unknown)}: jason's; the board sets {', '.join(BOARD_FIELDS)}")
    clean = {k: str(v) for k, v in changes.items() if v is not None}
    if not clean:
        raise ValueError("nothing to change")
    root = _data_dir(None)
    return _with_evidence_refs(_encode(set_fields(root, item_id, **clean)), root)


def write_canvas(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """The canvas writes: ``key`` empty creates one from ``body.title``; a body with ``clip`` adds a clip; otherwise the
    editable fields change in place. A person's scratchpad, jason's own store; nothing outward."""
    from jason.mcp.county import _data_dir
    from jason.tasks import canvases as store

    root = _data_dir(None)
    if not key:
        return store.encode(store.create(root, str(body.get("title", "")), question=str(body.get("question", "")),
                                         duty=str(body.get("duty", "")), matter=str(body.get("matter", ""))))
    clip = body.get("clip")
    if clip is not None:
        if not isinstance(clip, dict):
            raise ValueError("clip is an object with source and text")
        return store.with_refs(store.encode(store.add_clip(root, key, source=str(clip.get("source", "")), text=str(clip.get("text", "")),
                                           label=str(clip.get("label", "")), args=clip.get("args") if isinstance(clip.get("args"), dict) else None)), root)
    changes = {k: v for k, v in body.items() if v is not None}
    if not changes:
        raise ValueError("nothing to change")
    return store.with_refs(store.encode(store.update(root, key, **changes)), root)


def write_decision(decision_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Record a decision (``decision_id`` empty: ``meeting``, ``title``, ``motion`` and the rest) or change one in place.
    jason's own store; the board's decision in the board's words, never jason's."""
    from jason.mcp.county import _data_dir
    from jason.tasks import decisions as store

    root = _data_dir(None)
    clean = {k: v for k, v in body.items() if v is not None}
    if not decision_id:
        meeting, title, motion = str(clean.pop("meeting", "")), str(clean.pop("title", "")), str(clean.pop("motion", ""))
        return store.as_dict(store.record(root, meeting, title, motion, **clean))
    if not clean:
        raise ValueError("nothing to change")
    return store.as_dict(store.update(root, decision_id, **clean))


def write_request(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """Record what a person did about one request-list item. jason's own store; it sends nothing."""
    from dataclasses import asdict

    from jason.mcp.county import _data_dir
    from jason.tasks import onboarding_requests as ob

    clean = {k: v for k, v in body.items() if v is not None}
    if not clean:
        raise ValueError("nothing to change")
    return asdict(ob.update(_data_dir(None), key, **clean))


def confirm_owner_info_write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """A person's confirmation of one planned owner-information write (``by``; ``confirmed`` false withdraws it)."""
    from jason.mcp.county import _data_dir
    from jason.tasks.owner_info_plan import confirm, status

    root = _data_dir(None)
    confirm(root, key, by=str(body.get("by", "")), confirmed=bool(body.get("confirmed", True)))
    return status(root)


def write_hearing_decision(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """The board's decision after a hearing, onto the hearing's row: findings, the day decided, who recorded it."""
    from jason.mcp.county import _data_dir
    from jason.tasks.hearing_decisions import record

    return record(_data_dir(None), key, findings=str(body.get("findings", "")), decided_on=str(body.get("decidedOn", "")), by=str(body.get("by", "")))
