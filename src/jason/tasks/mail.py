"""The association's paper mail, as PostScanMail received and scanned it: synced to disk, read, and sorted.

``sync`` pages through PostScanMail's items (newest first, stopping at a page it already has unless
``full``), keeps each item's record in ``data/mail/items.json``, and downloads each scanned item's
PDF to ``data/mail/<mail id>/contents.pdf`` (an unscanned item keeps only its envelope image,
``cover.jpg``). The PDF's text layer is read, or OCR'd when there is none, into ``text.txt``.

``classify`` sorts each item by ``MAIL_RULES``: legal notices, insurance cancellations and renewals,
government notices, escrow requests, bank statements, utility bills, checks, invoices, advertising.
Legal notices, cancellations, government notices, and escrow requests are for a person to read now,
and any date the letter ties to an action ("respond by", "due", "effective") is listed.

Nothing is sent to PostScanMail but reads: jason never requests a scan, forward, shred, or discard.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from jason.postscanmail.client import PostScanMail, PostScanMailError
from jason.postscanmail.models import CONFIDENTIAL_KINDS, MailItem, MailKind, Urgency, classify, letter_facts

MAIL_DIR = "mail"
ITEMS = "items.json"


def mail_dir(data_dir: Path) -> Path:
    return Path(data_dir) / MAIL_DIR


def load_items(data_dir: Path) -> dict[str, dict[str, Any]]:
    path = mail_dir(data_dir) / ITEMS
    if not path.is_file():
        return {}
    return {row["mailId"]: row for row in json.loads(path.read_text(encoding="utf-8")).get("items", [])}


SCAN = "contents.pdf"
COVER = "cover.jpg"
_MAIL_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


def scan_ref(data_dir: Path, row: dict[str, Any]) -> dict[str, Any] | None:
    """A letter's document as a reference for the console's ``Doc`` (docs/console/doc-component.md): its scan,
    ``mail/<id>/contents.pdf``, when PostScanMail scanned it (or the scan is on disk), else its envelope,
    ``mail/<id>/cover.jpg``. Neither on disk is still a reference, which the ``Doc`` says is not on disk. The level is
    ``jason.web.access``'s for ``mail/`` (P2). Reads metadata only; None for a row without a usable mail id."""
    from jason.approvals.docref import file_ref

    mail_id = str(row.get("mailId") or "").strip()
    if not _MAIL_ID.fullmatch(mail_id):
        return None
    scanned = bool(row.get("scanned")) or (mail_dir(data_dir) / mail_id / SCAN).is_file()
    who = " ".join(str(row.get("from") or row.get("sender") or "").split())
    day = str(row.get("received") or "")[:10]
    name = ("Letter" if scanned else "Envelope") + (f" from {who}" if who else "") + (f", {day}" if day else "")
    return file_ref(f"{MAIL_DIR}/{mail_id}/{SCAN if scanned else COVER}", name=name, data_dir=data_dir)


def _text_of(pdf: Path) -> tuple[str, str]:
    """The PDF's text layer, else OCR; with where it came from."""
    from jason.tasks.utilities import pdf_text

    try:
        text = pdf_text(pdf)
    except Exception:  # a damaged download reads as nothing
        text = ""
    if len(text.strip()) >= 100:
        return text, "text layer"
    from jason.community.ocr import engines

    for engine in engines():
        if engine.name == "anythingllm-collector":
            continue
        try:
            read = engine.text_of(pdf)
        except Exception:
            continue
        if read.strip():
            return read, f"ocr: {engine.name}"
    return text, "no text"


def sync(client: PostScanMail, data_dir: Path, *, full: bool = False, log: Callable[[str], None] | None = None,
         community: Any = None) -> dict[str, int]:
    """Read new mail from PostScanMail, download the scans, read their text, and sort them."""
    root = mail_dir(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    known = load_items(data_dir)
    stop_at = None if full else {k for k, v in known.items() if v.get("scanned") == bool(v.get("text"))}
    counts = {"seen": 0, "new": 0, "downloaded": 0, "read": 0, "failed": 0}
    for raw in client.iter_items(stop_at=stop_at):
        item = MailItem.from_api(raw)
        counts["seen"] += 1
        if item.mail_id not in known:
            counts["new"] += 1
        row = {**known.get(item.mail_id, {}), **item.record()}
        folder = root / item.mail_id
        pdf, cover = folder / "contents.pdf", folder / "cover.jpg"
        try:
            if item.scanned and not pdf.is_file():
                client.download(item.pdf_url, pdf)
                counts["downloaded"] += 1
            elif not item.scanned and item.cover_url and not cover.is_file():
                client.download(item.cover_url, cover)
                counts["downloaded"] += 1
        except PostScanMailError as exc:
            counts["failed"] += 1
            if log:
                log(f"mail {item.mail_id}: {exc}")
        text_file = folder / "text.txt"
        if pdf.is_file() and not text_file.is_file():
            text, source = _text_of(pdf)
            text_file.write_text(text, encoding="utf-8")
            row["textSource"] = source
            counts["read"] += 1
        row["text"] = text_file.is_file() and text_file.stat().st_size > 0
        known[item.mail_id] = sort(row, text_file.read_text(encoding="utf-8") if text_file.is_file() else "", community)
        if log and counts["seen"] % 50 == 0:
            log(f"read {counts['seen']} items")
    items = sorted(known.values(), key=lambda r: r.get("received") or "", reverse=True)
    (root / ITEMS).write_text(json.dumps({"syncedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "items": items},
                                         indent=1, default=str), encoding="utf-8")
    write_letters(data_dir)
    write_report(data_dir)
    return counts


LETTER = "letter.md"


def shareable(row: dict[str, Any], *, include_confidential: bool = False) -> bool:
    """Whether a letter may go to a shared catalog: never one carrying a credential; a confidential kind only when asked."""
    if row.get("credential") or not row.get("text"):
        return False
    # Another association's mail (an owner's statement that came to the box) is someone else's record, and an owner's
    # own account (a statement mailed back with a payment) is not for other members to read.
    if (row.get("source") or {}).get("misdirected") or (row.get("source") or {}).get("kind") == "owner or resident":
        return False
    kind = next((k for k in MailKind if k.value == row.get("kind")), MailKind.OTHER)
    return include_confidential or kind not in CONFIDENTIAL_KINDS


def letter_page(row: dict[str, Any], text: str) -> str:
    """One letter as a page for AnythingLLM: a heading that names it, the sort and the facts, then the scanned text."""
    day = (row.get("received") or "")[:10]
    who = row.get("from") or row.get("sender") or "unknown sender"
    facts = row.get("facts") or {}
    lines = [f"# {day} {who[:70]} ({row.get('kind')}) [mail {row.get('mailId')}]", ""]
    lines.append(f"- mail id: {row.get('mailId')}; received {row.get('received')}; PostScanMail status {row.get('status')}, folder {row.get('folder')}")
    lines.append(f"- sender as PostScanMail recorded it: {row.get('sender') or 'none (the letterhead is shown above)'}")
    lines.append(f"- sort: {row.get('kind')}; urgency {row.get('urgency')}; matched on {', '.join(row.get('evidence') or []) or 'nothing'}")
    for d in row.get("deadlines") or []:
        lines.append(f"- date the letter states: {d['date']} ({d['label']})")
    for label, key in (("parcels", "parcels"), ("our parcels", "ourParcels"), ("addresses", "addresses"), ("policy numbers", "policies"),
                       ("escrow numbers", "escrows"), ("account endings", "accounts")):
        if facts.get(key):
            lines.append(f"- {label}: {', '.join(str(v) for v in facts[key])}")
    for b in facts.get("ourBuildings") or []:
        lines.append(f"- building: {b['address']} is in building {b['building']}")
    for start, end in facts.get("policyPeriods") or []:
        lines.append(f"- policy period: {start} to {end}")
    if row.get("aiSummary"):
        lines += ["", "## PostScanMail's summary", ""] + [str(s) for s in row["aiSummary"]]
    lines += ["", "## Scanned text", "", f"(from the {row.get('textSource') or 'PDF text layer'}; OCR can misread words and numbers)", "", text.strip(), ""]
    return "\n".join(lines)


def write_letters(data_dir: Path, *, include_confidential: bool = False) -> dict[str, int]:
    """Write ``letter.md`` beside each shareable letter, and remove it where a letter is no longer shareable."""
    root = mail_dir(data_dir)
    counts = {"written": 0, "withheld": 0}
    for mail_id, row in load_items(data_dir).items():
        page = root / mail_id / LETTER
        text_file = root / mail_id / "text.txt"
        if shareable(row, include_confidential=include_confidential) and text_file.is_file():
            page.write_text(letter_page(row, text_file.read_text(encoding="utf-8")), encoding="utf-8")
            counts["written"] += 1
        else:
            if page.is_file():
                page.unlink()
            counts["withheld"] += 1
    return counts


def sort(row: dict[str, Any], text: str, community: Any = None) -> dict[str, Any]:
    """The item's kind, urgency, evidence, stated deadlines, and facts, from its sender, AI summary, and scanned text.

    With ``community``, the facts join the association's records: a parcel number that is one of its parcels, and a
    street address that falls in one of its buildings.
    """
    received = date.fromisoformat(row["received"][:10]) if row.get("received") else None
    body = "\n".join(row.get("aiSummary") or []) + "\n" + text
    found = classify(row.get("sender", ""), body, received=received)
    facts = letter_facts(text).record()
    source: dict[str, Any] = {}
    kind, urgency = found.kind, found.urgency
    if community is not None:
        from jason.community.sources import SourceKind, other_associations, resolve

        named, source_kind, level, word = resolve(row.get("sender", ""), text, community.senders())
        # A preliminary notice is a form: its sender is the claimant the form names, below the statutory text.
        at = text.upper().find("CLAIMANT")
        if named is None and kind is MailKind.LIEN_NOTICE and at >= 0:
            named, source_kind, level, word = resolve("", text[at:at + 600], community.senders(), wide=600)
        source = {"name": named.name if named else "", "kind": source_kind.value, "level": level.value if level else None,
                  "role": named.role if named else "", "payhoaVendor": named.payhoa_vendor if named else "", "matched": word,
                  "otherAssociations": list(other_associations(text[:3000]))}
        # A letter the words left unsorted takes its kind from a known source.
        by_source = {SourceKind.UTILITY: MailKind.UTILITY, SourceKind.INSURER: MailKind.INSURANCE, SourceKind.BANK: MailKind.BANK,
                     SourceKind.TITLE_ESCROW: MailKind.ESCROW, SourceKind.GOVERNMENT: MailKind.GOVERNMENT}
        if kind is MailKind.OTHER and source_kind in by_source:
            kind = by_source[source_kind]
            urgency = Urgency.REVIEW if urgency is Urgency.FILE else urgency
        # Mail naming another association is for a person to look at: misdirected mail, or a record under the wrong name.
        if source["otherAssociations"] and urgency is Urgency.FILE:
            urgency = Urgency.REVIEW
        # A letter that never names Mystique (OCR spells it "lystique", "Mystque") but names another association is that
        # association's mail: an owner's statement or a notice that came to the box. It is not the association's record.
        addressed_to_us = bool(re.search(r"(?i)m?y?st[il1]?que|mystique", text))
        source["misdirected"] = bool(source["otherAssociations"]) and not addressed_to_us
        if source["misdirected"] and source_kind is SourceKind.UNKNOWN:
            source["kind"] = SourceKind.OTHER_ASSOCIATION.value
    if community is not None:
        ours = set(community.parcels())
        facts["ourParcels"] = [p for p in facts["parcels"] if p in ours]
        buildings = []
        for address in facts["addresses"]:
            hit = community.building_for_address(address)
            if hit is not None:
                buildings.append({"address": address, "building": int(hit.number)})
        facts["ourBuildings"] = buildings
    # PostScanMail leaves most senders blank; the letterhead's first readable lines stand in for display.
    letterhead = " / ".join(line.strip() for line in text.splitlines() if len(line.strip()) >= 4 and re.search(r"[A-Za-z]{3}", line))
    shown_as = source.get("name") or row.get("sender") or letterhead[:60]
    return {**row, "from": shown_as, "source": source, "kind": kind.value, "urgency": urgency.value,
            "evidence": list(found.evidence), "deadlines": [{"label": label, "date": day.isoformat()} for label, day in found.deadlines],
            "facts": facts, "credential": carries_credential(text)}


def reread_ocr(data_dir: Path, community: Any = None, *, source: str = "ocr: pymupdf-tesseract", limit: int = 0,
               log: Callable[[str], None] | None = None) -> dict[str, int]:
    """Read again the scans an older OCR engine read (Tesseract, before the local vision model), then sort everything.

    The old text stays beside the new as ``text.<engine>.txt``; no call to PostScanMail."""
    root = mail_dir(data_dir)
    known = load_items(data_dir)
    counts = {"candidates": 0, "reread": 0, "unchanged": 0, "failed": 0}
    for mail_id, row in known.items():
        if row.get("textSource") != source:
            continue
        counts["candidates"] += 1
        if limit and counts["reread"] + counts["unchanged"] + counts["failed"] >= limit:
            continue
        folder = root / mail_id
        pdf, text_file = folder / "contents.pdf", folder / "text.txt"
        if not pdf.is_file():
            counts["failed"] += 1
            continue
        text, how = _text_of(pdf)
        if how == source or not text.strip():
            counts["unchanged"] += 1
            continue
        if text_file.is_file():
            text_file.replace(folder / f"text.{source.split(': ', 1)[-1]}.txt")
        text_file.write_text(text, encoding="utf-8")
        row["textSource"] = how
        counts["reread"] += 1
        if log:
            log(f"mail {mail_id}: {how}, {len(text)} chars")
    body = json.loads((root / ITEMS).read_text(encoding="utf-8"))
    body["items"] = sorted(known.values(), key=lambda r: r.get("received") or "", reverse=True)
    (root / ITEMS).write_text(json.dumps(body, indent=1, default=str), encoding="utf-8")
    resort(data_dir, community)
    return counts


def resort(data_dir: Path, community: Any = None) -> int:
    """Sort every stored item again (after a rule changes), from the text already on disk."""
    root = mail_dir(data_dir)
    known = load_items(data_dir)
    for mail_id, row in known.items():
        text_file = root / mail_id / "text.txt"
        known[mail_id] = sort(row, text_file.read_text(encoding="utf-8") if text_file.is_file() else "", community)
    body = json.loads((root / ITEMS).read_text(encoding="utf-8"))
    body["items"] = sorted(known.values(), key=lambda r: r.get("received") or "", reverse=True)
    (root / ITEMS).write_text(json.dumps(body, indent=1, default=str), encoding="utf-8")
    write_letters(data_dir)
    write_report(data_dir)
    return len(known)


def policy_readings(rows) -> list[dict[str, Any]]:
    """Each insurance policy number the mail prints, with the buildings its letters place and the latest letter's date.

    A reading, not a pin: the building a flood policy covers is pinned on ``BuildingRange.policy_number`` only after a
    person confirms it. A policy whose letters place one building consistently is the candidate.
    """
    found: dict[str, dict[str, Any]] = {}
    for r in rows:
        if r.get("kind") not in (MailKind.INSURANCE.value, MailKind.INSURANCE_CANCELLATION.value):
            continue
        facts = r.get("facts") or {}
        buildings = sorted({b["building"] for b in facts.get("ourBuildings") or []})
        for policy in facts.get("policies") or []:
            entry = found.setdefault(policy, {"policy": policy, "letters": 0, "buildings": {}, "latest": "", "dates": set()})
            entry["letters"] += 1
            for b in buildings:
                entry["buildings"][b] = entry["buildings"].get(b, 0) + 1
            entry["latest"] = max(entry["latest"], (r.get("received") or "")[:10])
            entry["dates"].update(d["date"] for d in r.get("deadlines") or [])
    out = []
    for entry in found.values():
        if entry["letters"] < 2:
            continue
        buildings = entry["buildings"]
        top = max(buildings, key=buildings.get) if buildings else None
        out.append({"policy": entry["policy"], "letters": entry["letters"], "latestLetter": entry["latest"],
                    "building": top if top is not None and len(buildings) == 1 else None, "buildingsSeen": buildings,
                    "latestStatedDate": max(entry["dates"]) if entry["dates"] else None})
    return sorted(out, key=lambda e: (e["building"] is None, e["building"] or 0, e["policy"]))


def mail_brief(data_dir: Path, *, days: int = 30, today: date | None = None, kind: str = "", urgency: str = "") -> dict[str, Any]:
    """Mail received in the last ``days``: what to act on (with deadlines), what to review, and counts by kind."""
    known = load_items(data_dir)
    if not known:
        return {"found": False, "note": "no mail on disk; run jason mail --sync"}
    day = today or date.today()
    since = (day - timedelta(days=days)).isoformat()
    rows = [r for r in known.values() if (r.get("received") or "") >= since
            and (not kind or r.get("kind") == kind) and (not urgency or r.get("urgency") == urgency)]
    rows.sort(key=lambda r: r.get("received") or "", reverse=True)
    upcoming = sorted(({"date": d["date"], "label": d["label"], "sender": r.get("from") or r["sender"], "mailId": r["mailId"]}
                       for r in known.values() for d in r.get("deadlines", []) if d["date"] >= day.isoformat()),
                      key=lambda d: d["date"])
    by_kind: dict[str, int] = {}
    for r in rows:
        by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + 1

    def brief(r: dict[str, Any]) -> dict[str, Any]:
        return {k: r.get(k) for k in ("mailId", "received", "sender", "from", "kind", "urgency", "evidence", "deadlines", "status", "folder", "scanned")} | {
            "summary": [line for line in r.get("aiSummary") or [] if line.strip()][:6]}

    return {
        "found": True,
        "since": since,
        "items": len(rows),
        "byKind": dict(sorted(by_kind.items(), key=lambda kv: -kv[1])),
        "act": [brief(r) for r in rows if r.get("urgency") == Urgency.ACT.value],
        "review": [brief(r) for r in rows if r.get("urgency") == Urgency.REVIEW.value],
        "upcomingDeadlines": upcoming[:20],
        "unscanned": [brief(r) for r in rows if not r.get("scanned")],
        "policyReadings": policy_readings(known.values()),
        "caveats": [
            "The kind comes from the sender's name and the letter's words; it is a sort, not a reading of what the letter means.",
            "A deadline is a date the letter places next to 'due', 'respond', 'effective', or 'expires'; read the letter for the real one.",
            "An unscanned item shows only its envelope; asking PostScanMail to open it is a person's decision (it may be billed).",
        ],
    }


def mail_text(data_dir: Path, mail_id: str) -> dict[str, Any]:
    """One item's record and its scanned text (from the PDF's text layer or OCR)."""
    row = load_items(data_dir).get(str(mail_id))
    if row is None:
        return {"found": False, "note": f"no mail item {mail_id} on disk"}
    text_file = mail_dir(data_dir) / str(mail_id) / "text.txt"
    body = text_file.read_text(encoding="utf-8") if text_file.is_file() else ""
    if carries_credential(body):
        body = ("[withheld: this letter carries a PIN, passcode, or access code; OCR scatters the value, so the text is "
                "not shown. Read the PDF.]")
    return {"found": True, **row, "textBody": body,
            "pdf": str(mail_dir(data_dir) / str(mail_id) / "contents.pdf")}


# A letter can carry a credential: the county's ownership-verification PIN, an online access code, a password.
_CREDENTIAL = re.compile(r"(?i)\b(your\s+pin\b|\bpin\s*(?:number|#)?\s*:|passcode|temporary\s+password|access\s+code|verification\s+code)")


def carries_credential(text: str) -> bool:
    """The letter names a PIN, passcode, password, or access code; its text is withheld from the MCP and the terminal."""
    return bool(_CREDENTIAL.search(text))


def write_report(data_dir: Path, *, days: int = 365, today: date | None = None) -> Path:
    """``data/reports/mail.md``: the year's mail brief as a page (it joins the jason-pages catalog as a summary)."""
    brief = mail_brief(data_dir, days=days, today=today)
    path = Path(data_dir) / "reports" / "mail.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = ["# Mail: what arrived, what to act on, and the insurance policies the letters print", "",
            f"Jason's summary of the association's PostScanMail mail for the {days} days before {(today or date.today()).isoformat()}. "
            "A summary, not the letters: each line names a letter by its date and sender; the letter's own text is in the mail catalog.",
            "", "```"] + brief_lines(brief) + ["```", ""]
    try:
        from jason.community import mystique
        from jason.tasks.mail_links import links_lines, mail_links

        body += ["## The mail checked against jason's records", "", "```"] + links_lines(mail_links(data_dir, mystique(), today=today)) + ["```", ""]
    except Exception as exc:  # the checks read other stores; a missing one does not stop the page
        body += [f"(the checks against jason's records did not run: {exc})", ""]
    path.write_text("\n".join(body), encoding="utf-8")
    return path


def brief_lines(brief: dict[str, Any]) -> list[str]:
    if not brief.get("found"):
        return [brief.get("note", "no mail")]
    out = [f"{brief['items']} items since {brief['since']}: " + ", ".join(f"{k} {n}" for k, n in brief["byKind"].items())]

    def line(r: dict[str, Any]) -> str:
        due = "; ".join(f"{d['label']} ({d['date']})" for d in r.get("deadlines") or [])
        return f"  {(r['received'] or '')[:10]} {(r.get('from') or r['sender'] or '-')[:40]:<40} {r['kind']}" + (f" | {due}" if due else "")

    if brief["act"]:
        out.append("")
        out.append("Act on")
        out.extend(line(r) for r in brief["act"])
    if brief["review"]:
        out.append("")
        out.append("Review")
        out.extend(line(r) for r in brief["review"])
    if brief["upcomingDeadlines"]:
        out.append("")
        out.append("Upcoming dates the letters state")
        out.extend(f"  {d['date']} {d['sender'][:40]:<40} {d['label']}" for d in brief["upcomingDeadlines"])
    if brief["unscanned"]:
        out.append("")
        out.append(f"{len(brief['unscanned'])} items not scanned (envelope only)")
    readings = brief.get("policyReadings") or []
    if readings:
        out.append("")
        out.append("Insurance policies the mail prints (a reading; a building's policy is pinned only after a person confirms it)")
        for p in readings:
            where = f"building {p['building']}" if p["building"] else f"buildings {p['buildingsSeen'] or 'not placed'}"
            due = f"; latest stated date {p['latestStatedDate']}" if p["latestStatedDate"] else ""
            out.append(f"  {p['policy']:<14} {where:<22} {p['letters']} letters, latest {p['latestLetter']}{due}")
    out.append("")
    out.extend(f"* {c}" for c in brief["caveats"])
    return out


__all__ = ["sync", "sort", "resort", "mail_brief", "mail_text", "brief_lines", "load_items", "mail_dir", "write_letters",
           "write_report", "letter_page", "shareable", "policy_readings", "carries_credential"]
