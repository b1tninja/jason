"""A legal hold, kept: its scope, the Vault matter and holds, the labels, the notices, the suspensions, and the checks.

``scope`` lists what the hold reaches from what jason already has on disk, each item with why it is in scope:

- Drive: every file in a held folder, and every file whose name carries one of the hold's terms;
- meetings: every Zoom meeting since ``relevant_from`` whose transcript or summary carries a term, with what Zoom's cloud
  still holds for it, jason's copies, and the Drive recordings and transcripts of that day;
- Gmail: every message since ``relevant_from`` whose subject carries a term (headers only), and its attachments on disk;
- photo albums the agendas link under an item that carries a term (held in a personal account, outside Vault);
- the local copies of all of these, each with its SHA-256, so the register can show a copy is unchanged.

``register`` keeps ``data/holds/<key>/register.json``: the hold, the scope, the Vault matter and hold ids, the files
labeled ``jason_hold``, the notices sent and acknowledged, the suspensions, and each custody check. A rebuild keeps those.

Writes are a person's: ``vault_apply`` creates the matter and its holds, ``label`` sets ``jason_hold`` on the held Drive
files, each only with ``yes``. jason never releases a hold, closes a matter, or deletes anything; counsel releases a hold
in writing, and a person does it in Vault.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from jason.community.holds import LegalHoldSpec

HOLDS = Path("holds")
HOLD_KEY = "jason_hold"
LOCAL_COPY = "jason's copy"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _pattern(spec: LegalHoldSpec) -> re.Pattern[str]:
    return re.compile(r"(?<![\w])(?:" + "|".join(re.escape(t) for t in spec.terms) + r")(?![\w])", re.I)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def hold_spec(community: Any, key: str = "") -> LegalHoldSpec:
    holds = tuple(community.legal_holds())
    if not holds:
        raise ValueError("the specification sets no legal hold (legal_holds)")
    found = next((h for h in holds if h.key == key), None) if key else holds[0]
    if found is None:
        raise ValueError(f"no legal hold {key!r}; the specification has {', '.join(h.key for h in holds)}")
    return found


def scope(data_dir: Path, community: Any, spec: LegalHoldSpec) -> dict[str, Any]:
    data_dir = Path(data_dir)
    words = _pattern(spec)
    since = spec.relevant_from.isoformat()
    items: list[dict[str, Any]] = []

    # Drive: held folders whole, and any file whose name carries a term.
    raw = _json(data_dir / "drive" / "files.json") or []
    rows = raw if isinstance(raw, list) else raw.get("files", [])
    folder_paths = {r["path"].rsplit("/", 1)[0] for r in rows if r.get("folderId") in spec.drive_folders}
    drive_ids: list[str] = []
    for r in rows:
        in_folder = any(r["path"].startswith(p + "/") or r["path"].rsplit("/", 1)[0] == p for p in folder_paths)
        named = words.search(r["name"])
        if in_folder or named:
            why = "in the held folder" if in_folder else f"its name carries \"{named.group(0)}\""
            items.append({"where": "Drive", "ref": r["id"], "name": r["name"], "path": r["path"], "md5": r.get("md5"), "why": why})
            drive_ids.append(r["id"])

    # Meetings: transcripts or summaries that carry a term, and what is kept of each.
    from jason.tasks.zoom import load_index, zoom_dir

    root = zoom_dir(data_dir)
    catalog = _json(data_dir / "meetings" / "catalog.json") or {}
    by_date = {m["date"]: m for m in catalog.get("meetings", [])}
    for m in load_index(data_dir).get("meetings", []):
        if (m.get("date") or "") < since or not m.get("folder"):
            continue
        folder = root / m["folder"]
        text = " ".join(p.read_text(encoding="utf-8", errors="replace") for p in (folder / "transcript.txt", folder / "summary.md")
                        if p.is_file())
        hits = sorted({h.group(0).lower() for h in words.finditer(text)})
        if not hits:
            continue
        why = f"its transcript carries {', '.join(hits[:5])}"
        for kind in m.get("cloud") or []:
            items.append({"where": "Zoom cloud", "ref": m["uuid"], "name": f"{m['date']} {m['topic']} ({kind})", "why": why,
                          "kind": kind})
        for name, rel in (m.get("files") or {}).items():
            items.append({"where": LOCAL_COPY, "ref": m["uuid"], "name": f"{m['date']} {name}", "path": f"data/zoom/{rel}",
                          "why": why, "local": str(root / rel)})
        for rec in (by_date.get(m["date"]) or {}).get("records", []):
            if rec["where"] == "Drive" and rec["kind"] in ("transcript", "audio recording", "video recording", "chat", "minutes") \
                    and rec["ref"] not in drive_ids:
                items.append({"where": "Drive", "ref": rec["ref"], "name": rec["name"], "path": rec["location"], "why": why})
                drive_ids.append(rec["ref"])

    # Gmail: subjects that carry a term (headers only), and their attachments on disk.
    corr = _json(data_dir / "gmail" / "correspondence.json") or {}
    held_messages = {}
    for msg in corr.get("messages", []):
        if (msg.get("at") or "")[:10] >= since and words.search(msg.get("subject") or ""):
            held_messages[msg["messageId"]] = msg
    threads = {m.get("threadId") for m in held_messages.values()}
    items.append({"where": "Gmail", "ref": "headers", "name": f"{len(held_messages)} messages in {len(threads)} threads since {since}",
                  "why": "subjects carry the hold's terms; Vault's mail hold is the full reach (bodies too)"})
    files = _json(data_dir / "gmail" / "files.json") or []
    for f in files if isinstance(files, list) else files.get("files", []):
        if f.get("messageId") in held_messages:
            local = data_dir / str(f.get("path", "")).replace("\\", "/")
            items.append({"where": "Gmail attachment", "ref": f["messageId"], "name": f["name"], "path": str(f.get("path")),
                          "why": f"attached to \"{held_messages[f['messageId']]['subject'][:60]}\"", "local": str(local),
                          "sha256": f.get("sha256")})

    # Photo albums the agendas link under an item that carries a term.
    links = _json(data_dir / "meetings" / "agenda-links.json") or {}
    for t in links.get("targets", []):
        if t["kind"] != "Google Photos album":
            continue
        hit = next((l for l in t["labels"] if words.search(f"{l['item']} {l['subitem']}")), None)
        if hit:
            items.append({"where": "Google Photos (personal account)", "ref": t.get("shareUrl") or t["url"], "name": f"{hit['date']} {hit['item']}",
                          "why": "linked under an agenda item that carries a term; outside Vault: export by Google Takeout"})

    _annotate(data_dir, community, items, corr)
    counts: dict[str, int] = {}
    for i in items:
        counts[i["where"]] = counts.get(i["where"], 0) + 1
    return {"builtAt": _now(), "items": items, "counts": counts, "driveIds": drive_ids}


def mail_pdf(names: tuple[str, ...]) -> re.Pattern[str]:
    """The name of an email printed to PDF, with its subject captured: "<name> Mail - <subject>.pdf", where the name is
    one the association's Workspace has had (``Community.gmail_print_names()``). With none, no file name matches."""
    from jason.community.base import alternation

    return re.compile(rf"^(?:{alternation(names)}) Mail - (.+?)(?:\.pdf)?$", re.I)


def _annotate(data_dir: Path, community: Any, items: list[dict[str, Any]], corr: dict[str, Any]) -> None:
    """Each item's likely privilege (from the email parties it came from or went to, and its name) and whether it is an
    association record (the Civil Code 5200 record its kind is, by the library's name rules)."""
    from jason.community.documents import profile
    from jason.community.privilege import PrivilegeCall, PrivilegeKind, classify

    def hook(name: str, default: Any) -> Any:
        found = getattr(community, name, None)
        return found() if callable(found) else default

    parties, rules = tuple(hook("privilege_parties", ())), tuple(hook("privilege_name_rules", ()))
    communication_names, sensitive_names = hook("privilege_names", ("", ()))
    printed = mail_pdf(tuple(hook("gmail_print_names", ())))
    messages = {m["messageId"]: m for m in corr.get("messages", [])}
    by_subject: dict[str, set[str]] = {}
    for m in messages.values():
        key = re.sub(r"^(?:re|fwd?|fw):\s*", "", (m.get("subject") or "").strip(), flags=re.I).casefold()
        by_subject.setdefault(key, set()).update(m.get("domains") or [])
    links = _json(data_dir / "drive" / "gmail-links.json") or {}
    saved = {l["driveId"]: [x["messageId"] for x in l.get("messages", [])] for l in links.get("links", [])}
    for i in items:
        domains: set[str] = set()
        if i["where"] == "Drive":
            for mid in saved.get(i["ref"], []):
                domains.update((messages.get(mid) or {}).get("domains") or [])
            m = printed.match(i["name"])
            if m:                                   # an email printed to PDF: its subject finds the thread
                subject = re.sub(r"^(?:re|fwd?|fw)[_:]\s*", "", m.group(1).replace("_", ":"), flags=re.I).casefold()
                for key, doms in by_subject.items():
                    if key and (key.startswith(subject[:40]) or subject.startswith(key[:40])):
                        domains.update(doms)
        elif i["where"] == "Gmail attachment":
            domains.update((messages.get(i["ref"]) or {}).get("domains") or [])
        if i["where"] in ("Zoom cloud", LOCAL_COPY):
            call = PrivilegeCall(PrivilegeKind.REVIEW, "a meeting recording: confidential where it is an executive session "
                                 "(4935); privileged only where counsel advised", True)
        else:
            communication = bool(re.search(communication_names, i["name"], re.I)) if communication_names else True
            call = classify(i["name"], sorted(domains), parties, rules, communication=communication)
        i.update(call.record())
        sensitive = next((label for pattern, label in sensitive_names if re.search(pattern, i["name"], re.I)), "")
        if sensitive:
            i["sensitive"] = sensitive
        i["privilegeLabel"] = call.label() + (f"; {sensitive}" if sensitive else "")
        if domains:
            i["parties"] = sorted(domains)
        kind = community.classify_document(i["name"], path=i.get("path") or "") if i["where"] in ("Drive", "Gmail attachment") and hasattr(community, "classify_document") else None
        record = profile(kind).record if kind is not None else None
        i["documentKind"] = kind.value if kind else None
        i["associationRecord"] = record.value if record is not None else ("not a listed record (5200)" if kind else "unclassified")


def _digest_locals(data_dir: Path, items: list[dict[str, Any]]) -> None:
    from jason.tasks.digests import Digests

    digests = Digests(data_dir)
    for i in items:
        if i.get("local"):
            md5, sha = digests.of(Path(i["local"]))
            if sha:
                i["sha256"], i["md5"] = sha, md5
            else:
                i["missing"] = True
    digests.save()


def register_path(data_dir: Path, key: str) -> Path:
    return Path(data_dir) / HOLDS / key / "register.json"


def load_register(data_dir: Path, key: str) -> dict[str, Any]:
    return _json(register_path(data_dir, key)) or {}


def save_register(data_dir: Path, reg: dict[str, Any]) -> Path:
    path = register_path(data_dir, reg["hold"]["key"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reg, indent=1, default=str), encoding="utf-8")
    return path


def build_register(data_dir: Path, community: Any, spec: LegalHoldSpec) -> dict[str, Any]:
    """The register with a fresh scope; the Vault ids, labels, notices, suspensions, and checks already kept stay."""
    old = load_register(data_dir, spec.key)
    found = scope(data_dir, community, spec)
    _digest_locals(data_dir, found["items"])
    previous = {(i["where"], i.get("ref"), i.get("path") or i["name"]): i.get("sha256") for i in (old.get("scope") or {}).get("items", [])}
    changed = [i["name"] for i in found["items"] if i.get("sha256") and previous.get((i["where"], i.get("ref"), i.get("path") or i["name"]))
               not in (None, i["sha256"])]
    reg = {
        "hold": {"key": spec.key, "case": spec.case, "title": spec.title, "dutyFrom": spec.duty_from.isoformat(),
                 "relevantFrom": spec.relevant_from.isoformat(), "custodians": list(spec.custodians), "terms": list(spec.terms),
                 "counsel": spec.counsel, "custodianOfRecord": spec.custodian_of_record,
                 "released": spec.released.isoformat() if spec.released else None},
        "scope": found,
        "changedSinceLastScope": changed,
        "vault": old.get("vault") or {},
        "labels": old.get("labels") or {},
        "notices": old.get("notices") or [{"to": n, "sent": None, "acknowledged": None} for n in spec.notice_to],
        "suspensions": old.get("suspensions") or [{"rule": s, "suspended": None, "by": None} for s in spec.suspends],
        "outsideVault": list(spec.outside_vault),
        "checks": old.get("checks") or [],
    }
    save_register(data_dir, reg)
    return reg


# --- Vault ----------------------------------------------------------------------------------------------------------

def vault_plan(spec: LegalHoldSpec) -> dict[str, Any]:
    """The matter and holds Vault should have: Drive whole for each custodian, and Mail by the terms since the start."""
    start = f"{spec.relevant_from.isoformat()}T00:00:00Z"
    return {"matter": {"name": spec.title, "description": f"Legal hold for {spec.case}; duty from {spec.duty_from}; counsel: {spec.counsel}"},
            "holds": [{"name": f"{spec.key} Drive", "corpus": "DRIVE", "accounts": list(spec.custodians)},
                      {"name": f"{spec.key} Mail", "corpus": "MAIL", "accounts": list(spec.custodians), "terms": spec.mail_query(),
                       "start": start}]}


def vault_apply(vault: Any, data_dir: Path, spec: LegalHoldSpec, *, yes: bool) -> dict[str, Any]:
    """Create the matter (or find it by name) and each planned hold not yet in it. Only with ``yes``."""
    from jason.google.vault import Corpus

    plan = vault_plan(spec)
    if not yes:
        return {"dryRun": True, "plan": plan}
    reg = load_register(data_dir, spec.key)
    matter = next((m for m in vault.matters(state="OPEN") if m.get("name") == plan["matter"]["name"]), None) or \
        vault.create_matter(plan["matter"]["name"], plan["matter"]["description"])
    existing = {h.get("name"): h for h in vault.holds(matter["matterId"])}
    made = []
    for h in plan["holds"]:
        if h["name"] in existing:
            continue
        corpus = Corpus(h["corpus"])
        made.append(vault.create_hold(matter["matterId"], h["name"], corpus, h["accounts"], terms=h.get("terms", ""), start=h.get("start", "")))
    holds = list(vault.holds(matter["matterId"]))
    reg["vault"] = {"matterId": matter["matterId"], "matter": matter.get("name"), "holds": [
        {"holdId": h.get("holdId"), "name": h.get("name"), "corpus": h.get("corpus"),
         "accounts": [a.get("email") for a in h.get("accounts") or []], "updated": h.get("updateTime")} for h in holds],
        "appliedAt": _now()}
    save_register(data_dir, reg)
    return {"dryRun": False, "matterId": matter["matterId"], "created": [h.get("name") for h in made], "holds": reg["vault"]["holds"]}


# --- labels and custody checks --------------------------------------------------------------------------------------

PRIVILEGE_KEY = "jason_privilege"


def hold_labels(reg: dict[str, Any], key: str, community: Any = None) -> dict[str, dict[str, str]]:
    """Each held Drive file's legal-hold keys: ``jason_hold`` (the hold) and ``jason_privilege`` (the likely privilege,
    trimmed to Drive's limit by the schema's rule)."""
    from jason.community.drive_labels import Label, fit
    from jason.tasks.drive_labels import schema

    row = next((r for r in schema(community) if r.label is Label.PRIVILEGE), None)
    out: dict[str, dict[str, str]] = {}
    for i in (reg.get("scope") or {}).get("items", []):
        if i["where"] != "Drive" or i["ref"] in out:
            continue
        props = {HOLD_KEY: key}
        value = fit(row, i.get("privilegeLabel") or "") if row is not None and i.get("privilegeLabel") else None
        if value:
            props[PRIVILEGE_KEY] = value
        out[i["ref"]] = props
    return out


def label(drive: Any, data_dir: Path, spec: LegalHoldSpec, *, yes: bool, limit: int = 0, community: Any = None) -> dict[str, Any]:
    """Set ``jason_hold`` and ``jason_privilege`` on each held Drive file (the only keys this writes), then jason's
    ordinary labels (kind, 5200 records, meetings, item, topics) on the same files through ``jason drive-labels``.
    Only with ``yes``."""
    from jason.google.drive_properties import set_app_properties

    reg = load_register(data_dir, spec.key)
    wanted = hold_labels(reg, spec.key, community)
    ids = [i for i in wanted if reg.get("labels", {}).get(i, {}).get(PRIVILEGE_KEY) != wanted[i].get(PRIVILEGE_KEY)
           or i not in reg.get("labels", {})]
    if limit:
        ids = ids[:limit]
    if not yes:
        return {"dryRun": True, "wouldLabel": len(ids), "sample": {i: wanted[i] for i in ids[:3]}}
    done, failed = 0, []
    for file_id in ids:
        try:
            set_app_properties(drive, file_id, wanted[file_id])
            reg.setdefault("labels", {})[file_id] = {**wanted[file_id], "at": _now()}
            done += 1
        except Exception as exc:  # a file the account cannot edit is recorded, not skipped silently
            failed.append({"id": file_id, "error": str(exc)[:160]})
    save_register(data_dir, reg)
    ordinary: dict[str, Any] = {}
    try:
        from jason.tasks import drive_labels

        plan_body = drive_labels.plan(data_dir, community)
        held = set(wanted)
        plan_body["files"] = [f for f in plan_body["files"] if f["id"] in held]
        ordinary = drive_labels.apply(drive, plan_body, yes=True, data_dir=data_dir)
        ordinary = {k: ordinary[k] for k in ("written", "unchanged") if k in ordinary} | {"failed": len(ordinary.get("failed", []))}
    except Exception as exc:  # the hold labels stand even if the ordinary ones fail
        ordinary = {"error": str(exc)[:200]}
    return {"dryRun": False, "labeled": done, "failed": failed, "ordinaryLabels": ordinary}


def watch(client: Any, data_dir: Path, spec: LegalHoldSpec, *, since: str = "") -> dict[str, Any]:
    """Since the duty arose (or ``since``): which held Drive files were deleted, moved, renamed, or re-shared, and by
    whom. A check is appended to the register; jason changes nothing."""
    from jason.google.drive_activity import CUSTODY_ACTIONS, ActionType
    from jason.tasks.drive_activity import activity_for

    reg = load_register(data_dir, spec.key)
    ids = (reg.get("scope") or {}).get("driveIds", [])
    start = since or spec.duty_from.isoformat()
    found = activity_for(client, ids, start, actions=CUSTODY_ACTIONS)
    events = []
    for file_id, act in found.items():
        for a in act.activities:
            events.append({"id": file_id, "time": a.time, "action": a.action.value, "anyoneLink": a.link_shared,
                           "byCurrentUser": any(getattr(x, "is_current_user", False) for x in a.actors),
                           "standing": act.standing.value})
    events.sort(key=lambda e: e["time"] or "", reverse=True)
    check = {"at": _now(), "since": start, "files": len(ids), "events": len(events),
             "deleted": sum(1 for e in events if e["action"] == ActionType.DELETE.value),
             "moved": sum(1 for e in events if e["action"] == ActionType.MOVE.value),
             "linkShared": sum(1 for e in events if e["anyoneLink"]), "recent": events[:25]}
    reg.setdefault("checks", []).append(check)
    save_register(data_dir, reg)
    return check


# --- notices --------------------------------------------------------------------------------------------------------

CONFIDENTIAL = "CONFIDENTIAL - EXECUTIVE SESSION MATTER (Civil Code 4935(a)). Do not forward outside the board and counsel."


def _long(d: date) -> str:
    return f"{d:%B} {d.day}, {d.year}"


def _discussed(spec: LegalHoldSpec) -> str:
    return f"As the board discussed in {spec.board_discussed}, " if spec.board_discussed else ""


def notices(spec: LegalHoldSpec, reg: dict[str, Any]) -> list[dict[str, Any]]:
    """The drafts a hold needs: one written notice for each role in ``notice_to`` (recipients left to the person), and
    the note to counsel describing the method and asking for written approval. Nothing here is sent."""
    case = spec.title.split(" - ", 1)[-1]
    since, duty = _long(spec.relevant_from), _long(spec.duty_from)
    keeper = spec.custodian_of_record or "the Secretary"
    keeper_name, _, keeper_role = keeper.partition(", ")
    signed = f"{keeper_name}, the {keeper_role}," if keeper_role else keeper_name
    reach = "; ".join(spec.outside_vault)
    scope_words = ", ".join(t for t in spec.terms)
    body = [
        CONFIDENTIAL, "",
        f"{_discussed(spec)}the association is a defendant in {case}. The association has had a duty to preserve evidence "
        f"about this matter since {duty}, and that duty reaches you{{AS}}. This notice puts in writing what the board has "
        "already discussed; it is not new information.", "",
        "What to keep",
        f"Everything, from {since} on, about the June 2025 dog attack, the dogs, the unit and its owner and residents, the notices "
        "of violation and the disciplinary hearing, the insurance claims, and the lawsuit: email, text and chat messages, "
        "photos and video, voicemail, notes, calendar entries, documents, and meeting recordings, transcripts, chats, and "
        f"summaries. (For searching: {scope_words}.)", "",
        "Where",
        "The association's Google account is already under a Google Vault hold. Your own accounts and devices are not, and "
        "only you can keep them: your personal email, text and chat messages, photos (including any shared or personal photo "
        "albums), notes, and any copies on your phone or computer.", "",
        "What to do",
        "- Do not delete, edit, or move any of it, and do not empty the trash in any account that holds it.",
        "- Turn off any automatic deletion that would reach it (disappearing messages, photo cleanup, email auto-delete).",
        "- Keep a device you replace until counsel says otherwise.",
        "- Discuss the matter only with the board in executive session and with counsel.",
        "- The Decorum Rules' deletion of the Secretary's meeting recordings is suspended while the hold stands.", "",
        f"{signed} keeps the hold's register. Tell {keeper_name} of anything you hold, and anything already lost, so it can "
        "be recorded. The hold stays in place until counsel releases it in writing.", "",
"Please reply to acknowledge that you received this notice and will follow it.", "",
        keeper,
    ]
    subject = f"Litigation hold notice - {case} - confidential"
    drafts: list[dict[str, Any]] = []
    for role in spec.notice_to:
        offices = [o.strip().lower() for o in re.split(r",| and ", keeper_role) if o.strip()]
        if any(o in role.lower() for o in offices):
            continue                       # the custodian's own duties are the register's checklist, not a letter to self
        who = " as a director" if "director" in role.lower() else " as the association's agent" if "manager" in role.lower() else ""
        text = "\n".join(body).replace("{AS}", who)
        drafts.append({"for": role, "to": [], "subject": subject, "text": text})
    held = reg.get("scope", {}).get("counts", {})
    labels = len(reg.get("labels", {}))
    vault = reg.get("vault") or {}
    counsel_text = [
        "Privileged and confidential - attorney-client communication", "",
        f"Dear {spec.counsel_attention}," if spec.counsel_attention else "Dear Counsel,", "",
        f"{_discussed(spec)}the association is preserving evidence for {case}, from the June 24, 2025 preservation letter on. "
        "I am writing, as Secretary and the custodian of the hold's records, to describe what we have done and ask for your "
        "written approval or further instructions.", "",
        "Done:",
        f"- Google Vault: a matter ({spec.title}) with holds on the association's Workspace account "
        f"({', '.join(spec.custodians)}): all of Drive, and mail matching the matter's terms since {since}. "
        f"Created {(vault.get('appliedAt') or '')[:10] or 'September 30, 2026'}.",
        f"- A register of what is held: {held.get('Drive', 0)} Drive files, {held.get('Zoom cloud', 0)} Zoom cloud recording "
        f"files, {held.get('Gmail attachment', 0)} email attachments and the matching mail, and {held.get(LOCAL_COPY, 0)} "
        "local copies of meeting records, "
        f"with SHA-256 values for the local copies and a record of who moved or re-shared any held Drive file since {duty}. "
        "No held file has been deleted.",
        f"- The {labels} held Drive files are labeled with the hold and a preliminary privilege flag for your review "
        "(attorney-client, insurer communications, documents received through counsel, and the other side's papers). "
        "The flags are ours, not a determination.",
        "- Written hold notices going to each director (current and since April 2025); each acknowledgment will be recorded.",
        "", f"The Secretary is keeping the meeting recordings, transcripts, and AI summaries since {since}, with their "
        "deletion under the Decorum Rules suspended, and will download the Zoom originals.", "",
        "Outside Vault, kept by notice and export: " + reach + ".", "",
        "Suspended while the hold stands: " + "; ".join(spec.suspends) + ".", "",
        "Questions:",
        "1. Do you approve this method, or should we do more (for example, an export of the Vault matter to you)?",
        "2. Should the hold reach anything else, such as other units, the other disciplinary matters since June 2025, or "
        "additional people?",
        "3. Please confirm in writing when the hold may be released.", "",
        "Thank you,", keeper,
    ]
    drafts.append({"for": "defense counsel", "to": [spec.counsel_email] if spec.counsel_email else [],
                   "subject": f"{case} - litigation hold: method for your approval", "text": "\n".join(counsel_text)})
    return drafts


def draft_notices(gmail: Any, data_dir: Path, spec: LegalHoldSpec, *, yes: bool) -> dict[str, Any]:
    """Save each notice as a Gmail draft (never sent) and record the draft in the register. Only with ``yes``."""
    from jason.google.gmail_drafts import DraftMessage

    reg = load_register(data_dir, spec.key)
    planned = notices(spec, reg)
    if not yes:
        return {"dryRun": True, "drafts": planned}
    from jason.google.gmail_drafts import DraftNotFound

    existing = {row["to"]: row.get("draftId") for row in reg.get("notices", []) if row.get("draftId") and not row.get("sent")}
    if reg.get("counselNote") and not reg["counselNote"].get("sent"):
        existing["defense counsel"] = reg["counselNote"].get("draftId")
    made = []
    for n in planned:
        message = DraftMessage(to=tuple(n["to"]), subject=n["subject"], text=n["text"])
        draft, how = None, "created"
        if existing.get(n["for"]):
            try:                                   # a redraft updates the saved draft; recipients typed in Gmail stay
                draft, how = gmail.update(existing[n["for"]], message), "updated"
            except DraftNotFound:                  # sent or discarded in Gmail: a new draft
                draft = None
        if draft is None:
            draft = gmail.create(message)
        made.append({"for": n["for"], "draftId": draft.get("id"), "to": n["to"], "at": _now(), "how": how})
        for row in reg.get("notices", []):
            if row["to"] == n["for"]:
                row["drafted"] = made[-1]["at"]
                row["draftId"] = draft.get("id")
    drafted_for = {m["for"] for m in made}
    for row in reg.get("notices", []):
        if row["to"] not in drafted_for and not row.get("sent"):
            row["drafted"] = "no letter: the Secretary is the custodian and keeps the register's checklist"
    reg["counselNote"] = next((m for m in made if m["for"] == "defense counsel"), None)
    save_register(data_dir, reg)
    return {"dryRun": False, "drafts": made}


def lines(reg: dict[str, Any]) -> list[str]:
    h = reg["hold"]
    out = [f"Legal hold {h['key']}: {h['title']}", f"  duty to preserve from {h['dutyFrom']}; records from {h['relevantFrom']}; "
           f"counsel: {h['counsel']}; register kept by: {h['custodianOfRecord'] or '(the board names a custodian)'}",
           "  scope: " + ", ".join(f"{v} {k}" for k, v in sorted(reg["scope"]["counts"].items(), key=lambda kv: -kv[1]))]
    missing = [i for i in reg["scope"]["items"] if i.get("missing")]
    if missing:
        out.append(f"  {len(missing)} local copies listed but not on disk")
    if reg.get("changedSinceLastScope"):
        out.append(f"  CHANGED since the last scope: {', '.join(reg['changedSinceLastScope'][:5])}")
    v = reg.get("vault") or {}
    out.append(f"  Vault: matter {v['matterId']} with {len(v.get('holds', []))} holds" if v.get("matterId")
               else "  Vault: no matter yet (`jason hold --vault --yes` creates it and its holds)")
    out.append(f"  jason_hold labels: {len(reg.get('labels', {}))} of {len(reg['scope'].get('driveIds', []))} held Drive files")
    sent = sum(1 for n in reg["notices"] if n.get("sent"))
    out.append(f"  notices: {sent} of {len(reg['notices'])} sent; " + "; ".join(n["to"] for n in reg["notices"] if not n.get("sent")))
    todo = [s["rule"] for s in reg["suspensions"] if not s.get("suspended")]
    out.append(f"  suspensions not yet recorded: {len(todo)}" + (f" ({todo[0]} ...)" if todo else ""))
    out.append("  outside Vault (export and keep): " + "; ".join(reg["outsideVault"]))
    if reg.get("checks"):
        c = reg["checks"][-1]
        out.append(f"  last custody check {c['at'][:10]} since {c['since']}: {c['events']} events on {c['files']} files "
                   f"({c['deleted']} deleted, {c['moved']} moved, {c['linkShared']} opened to anyone with the link)")
    return out


__all__ = ["HOLD_KEY", "build_register", "hold_spec", "label", "lines", "load_register", "scope", "vault_apply", "vault_plan", "watch"]
