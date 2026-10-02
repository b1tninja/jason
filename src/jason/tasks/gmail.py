"""The association's Gmail as a second source: PostScanMail's notices, and correspondence with named senders.

PostScanMail sends each item to the association's Google Group "Mail", which lands in Gmail. "New Mail Delivered"
carries the envelope image; "Scan Complete" carries the same image and the scan, whose file name ends with the
PostScanMail id ("LaBarreOksnee-Insurance-Agency,-LLC_Envelope-124638.pdf"). The two are joined by the image's name.
Read against the mail the API synced, the notices show:

- items the API sync does not hold (a missed page, or a key that stopped working);
- items delivered to the box and never scanned (an envelope image with no scan);
- how long each scan took after delivery.

Business email is any message with an address outside the association's domain and the personal providers: its date,
direction, domains, subject, and attachment names, never its body. Each business address is a contact (display name,
first and last date, counts each way). The named sender is resolved when the email is read (``Sender.domains``), so
the insurance agent's renewal proposal, a signed renewal letter, or a carrier's claim payment joins its sender's
letters. A personal address (an owner's) is only counted; no personal address is kept.

Everything is read-only and stays under ``data/gmail``. Jason sends no email and changes no label.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import getaddresses
from pathlib import Path
from typing import Any, Callable

from jason.google.errors import GoogleError

GMAIL_DIR = "gmail"
NOTICES = "postscanmail.json"
CORRESPONDENCE = "correspondence.json"
READ_IDS = "read-ids.json"
NOTICE_QUERY = 'subject:"PostScan Mail"'
PERSONAL = ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "aol.com", "comcast.net", "att.net",
            "sbcglobal.net", "live.com", "msn.com", "me.com", "ymail.com")
_SCAN = re.compile(r"(?:^|_)Envelope-(\d+)\.pdf$", re.I)


def gmail_dir(data_dir: Path) -> Path:
    return Path(data_dir) / GMAIL_DIR


def _when(meta: dict[str, Any]) -> str:
    ms = int(meta.get("internalDate") or 0)
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat(timespec="seconds") if ms else ""


def parse_notice(meta: dict[str, Any]) -> dict[str, Any]:
    """One PostScanMail email: its event (the subject after the dash), the envelope image, and the scan's mail id."""
    subject = meta["headers"].get("Subject", "")
    event = re.split(r"\s[–-]\s", subject, maxsplit=1)[-1].strip() if "PostScan" in subject else subject
    images = [f["name"] for f in meta["attachments"] if f["type"].startswith("image/")]
    scans = [f["name"] for f in meta["attachments"] if _SCAN.search(f["name"])]
    mail_id = _SCAN.search(scans[0]).group(1) if scans else ""
    return {"messageId": meta["id"], "at": _when(meta), "event": event, "image": images[0] if images else "", "mailId": mail_id,
            "scan": scans[0] if scans else ""}


def _people(value: str) -> list[tuple[str, str]]:
    """(display name, address) for each address in a header, the address in lower case."""
    return [(name.strip().strip('"'), addr.lower()) for name, addr in getaddresses([value or ""]) if "@" in addr]


def _host(address: str) -> str:
    return address.rsplit("@", 1)[-1]


# A Google Group ("'Veronica Repato' via Accounts Payable" <AP@...>) rewrites From to its own address and keeps the
# writer in these headers.
ORIGINAL_SENDER = ("X-Original-From", "X-Original-Sender")
# Every message a Google Group delivers carries its List-ID ("<AP.mystiquecommunity.com>"), rewritten or not, and
# X-BeenThere names the group too.
GROUP_HEADERS = ("List-Id", "X-BeenThere")
# The version of what a stored message holds; a message stored under an earlier one is read again once.
MESSAGE_VERSION = 3


def _header(head: dict[str, str], name: str) -> str:
    """A header by name in any case: Google writes "List-ID" where the RFC writes "List-Id"."""
    wanted = name.lower()
    return next((value for key, value in head.items() if key.lower() == wanted), "")


def _groups(head: dict[str, str], own: set[str], via: str) -> list[str]:
    """The association's Google Groups a message came through, as addresses: its List-Id, and the group that rewrote
    its sender."""
    found = {via} if via else set()
    match = re.search(r"<?([A-Za-z0-9._+-]+)\.((?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})>?\s*$", _header(head, "List-Id").strip())
    if match and match.group(2).lower() in own:
        found.add(f"{match.group(1).lower()}@{match.group(2).lower()}")
    # X-BeenThere: "ap@mystiquecommunity.com; h=..." (one per group a message passed through, joined by the client).
    for address in re.findall(r"([A-Za-z0-9._+-]+@[A-Za-z0-9.-]+)", _header(head, "X-BeenThere")):
        if _host(address.lower()) in own:
            found.add(address.lower())
    return sorted(found)


def _senders(head: dict[str, str], own: set[str]) -> tuple[list[tuple[str, str]], str]:
    """Who wrote the message, and the association's group it came through ("" when it came directly). A message the
    group rewrote is the original writer's; one the association wrote itself stays the association's."""
    written = _people(_header(head, "From"))
    if not written or _host(written[0][1]) not in own:
        return written, ""
    original = _people(_header(head, "X-Original-From")) or _people(_header(head, "X-Original-Sender"))
    if original and _host(original[0][1]) not in own:
        return original[:1], written[0][1]
    return written, ""


def sync(gmail: Any, data_dir: Path, community: Any, *, days: int = 730, limit: int = 20000, workers: int = 8,
         log: Callable[[str], None] | None = None) -> dict[str, int]:
    """Read the notices and the business email of the last ``days`` into ``data/gmail`` (headers only).

    Business email is any message with an address outside the association's own domain and the personal providers.
    Each keeps its date, direction, the business domains on it, subject, and attachment names; each business address
    becomes a contact with its display name, first and last date, and counts in and out. A personal address is only
    counted.
    """
    say = log or (lambda _m: None)
    root = gmail_dir(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    # A notice already read is not read again.
    known = {n["messageId"]: n for n in _load(data_dir, NOTICES).get("notices") or []}
    notices = [known.get(row["id"]) or parse_notice(gmail.get_metadata(row["id"]))
               for row in gmail.iter_messages(f"{NOTICE_QUERY} newer_than:{days}d", limit=limit)]
    (root / NOTICES).write_text(json.dumps({"syncedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "notices": notices},
                                           indent=1), encoding="utf-8")
    say(f"PostScanMail notices: {len(notices)}")
    own = set(community.email_domains())
    # Resumable: every message read is noted (business, personal, or neither), and the store is saved every 500, so a
    # dropped connection loses at most the last few hundred and the next run skips what is already read.
    stored = _load(data_dir, CORRESPONDENCE)
    kept: list[dict[str, Any]] = list(stored.get("messages") or [])
    read: dict[str, str] = dict(_load(data_dir, READ_IDS).get("read") or {})
    new = 0

    def save() -> None:
        (root / READ_IDS).write_text(json.dumps({"read": read}), encoding="utf-8")
        (root / CORRESPONDENCE).write_text(json.dumps({
            "syncedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "days": days, "read": len(read),
            "personal": sum(1 for m in kept if any(not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", p) and p != "association"
                                                   for p in m.get("parties") or [])),
            "messages": kept, "contacts": _contacts_of(kept)}, indent=1),
            encoding="utf-8")

    from jason.tasks.parties import PartyResolver

    resolver = PartyResolver(data_dir)

    def take(message_id: str, meta: dict[str, Any]) -> None:
        head = meta["headers"]
        outgoing = "SENT" in meta["labels"]
        senders, via = _senders(head, own)
        groups = _groups(head, own, via)
        people = [(n, a, "from") for n, a in senders]
        people += [(n, a, "to") for field in ("To", "Cc") for n, a in _people(head.get(field, ""))]
        business = [(n, a, role) for n, a, role in people if _host(a) not in own and _host(a) not in PERSONAL]
        # Every message is kept for its thread. A personal address is never stored: it becomes who the records knew
        # the sender to be on that day (an owner, a former owner after a conveyance, a buyer, a board member), else
        # "personal". The association's own addresses are kept.
        sent = datetime.fromtimestamp(int(meta.get("internalDate") or 0) / 1000, tz=timezone.utc).date() if meta.get("internalDate") else None
        parties = sorted({resolver.resolve(a, n, sent) if _host(a) in PERSONAL else "association" if _host(a) in own else _host(a)
                          for n, a, role in people if not (role == "from" and outgoing)})
        read[message_id] = "t"
        kept.append({"messageId": meta["id"], "threadId": meta["threadId"], "at": _when(meta), "direction": "out" if outgoing else "in",
                     "domains": sorted({_host(a) for _, a, _ in business}), "parties": parties, "subject": head.get("Subject", ""),
                     "people": [list(p) for p in business], "via": via, "groups": groups, "origin": MESSAGE_VERSION,
                     # The association's own addresses it went to: a group, or a person's association mailbox.
                     "addressed": sorted({a for _, a, role in people if role == "to" and _host(a) in own}),
                     "attachments": [f["name"] for f in meta["attachments"] if not f["type"].startswith("image/")]})

    # A message read before threads were kept (marked business, personal, or neither) is read again once, and so is
    # one stored before the groups and the group's original sender were read.
    regroup = {m["messageId"] for m in kept if m.get("origin") != MESSAGE_VERSION}
    kept[:] = [m for m in kept if "parties" in m and m["messageId"] not in regroup]
    read = {k: v for k, v in read.items() if v == "t" and k not in regroup}
    todo = [row["id"] for row in gmail.iter_messages(f"newer_than:{days}d -{NOTICE_QUERY}", limit=limit) if row["id"] not in read]
    say(f"email: {len(todo)} messages to read, {len(read)} already read")

    def fetch(message_id: str) -> dict[str, Any]:
        return gmail.get_metadata(message_id, headers=("From", "To", "Cc", "Subject", "Date", *ORIGINAL_SENDER, *GROUP_HEADERS))

    # Several at a time, under the one pace the client keeps; saved every 100, and a refusal that outlasts the retries
    # stops the run cleanly: what was read is kept, and the next run starts from there.
    stopped = ""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        try:
            for message_id, meta in zip(todo, pool.map(fetch, todo)):
                take(message_id, meta)
                new += 1
                if new % 100 == 0:
                    save()
                if new % 500 == 0:
                    say(f"  {len(read)} read ({new} new)")
        except GoogleError as exc:
            stopped = str(exc)[:160]
            pool.shutdown(wait=False, cancel_futures=True)
    save()
    if stopped:
        say(f"stopped after {new} new messages ({stopped}); run again to continue")
    business = sum(1 for m in kept if m["domains"])
    say(f"email: {len(read)} read ({new} new), {business} business, {len(kept) - business} owner, board, or internal")
    return {"notices": len(notices), "read": len(read), "new": new, "business": business, "remaining": len(todo) - new}


def group_lines(messages: list[dict[str, Any]], groups: tuple) -> list[str]:
    """Mail by the association's Google Group it came through, with each group's purpose; a group the specification
    does not name is listed for a person to add."""
    from jason.community.groups import group_of

    counts: dict[str, list[int]] = {}
    for m in messages:
        for address in m.get("groups") or []:
            row = counts.setdefault(address, [0, 0])
            row[0] += 1
            row[1] += bool(m.get("via"))
    if not counts:
        return []
    out = ["", "Mail by Google Group (List-Id; rewritten = the group replaced the sender, whom jason reads from X-Original-From):"]
    for address, (n, rewritten) in sorted(counts.items(), key=lambda kv: -kv[1][0]):
        group = group_of(address, groups)
        label = f"{group.name} ({group.purpose.value})" if group else "not in mystique/groups.py"
        out.append(f"  {address}: {n} messages, {rewritten} rewritten; {label}")
    return out


def _contacts_of(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each business address across the stored messages: display names, first and last date, and counts each way."""
    found: dict[str, dict[str, Any]] = {}
    for m in messages:
        outgoing = m["direction"] == "out"
        for name, address, role in m.get("people") or []:
            c = found.setdefault(address, {"address": address, "domain": _host(address), "names": [], "first": m["at"], "last": m["at"],
                                           "wroteUs": 0, "weWrote": 0})
            if name and name not in c["names"]:
                c["names"].append(name)
            c["first"], c["last"] = min(c["first"], m["at"]), max(c["last"], m["at"])
            if role == "from" and not outgoing:
                c["wroteUs"] += 1
            elif role == "to" and outgoing:
                c["weWrote"] += 1
    return sorted(found.values(), key=lambda c: (c["domain"], c["address"]))


def _load(data_dir: Path, name: str) -> dict[str, Any]:
    path = gmail_dir(data_dir) / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def sender_of(domains: list[str], senders: tuple[Any, ...]) -> Any:
    """The named sender that writes from one of a message's domains, or None."""
    return next((s for s in senders if s.domains for d in domains if s.writes_from("x@" + d)), None)


def correspondence(data_dir: Path, names: tuple[str, ...] = (), community: Any = None) -> list[dict[str, Any]]:
    """The stored business email, each with the named sender its domains resolve to now; optionally only these senders.

    The sender is resolved when read, so a domain added to ``mystique/senders.py`` takes effect without a new sync.
    """
    if community is None:
        from jason.community import mystique

        community = mystique()
    senders = tuple(getattr(community, "senders", lambda: ())())
    rows = []
    for m in _load(data_dir, CORRESPONDENCE).get("messages") or []:
        named = sender_of(m.get("domains") or [], senders)
        if named is None or (names and named.name not in names):
            continue
        rows.append({**m, "sender": named.name})
    return sorted(rows, key=lambda r: r["at"])


def contacts(data_dir: Path) -> list[dict[str, Any]]:
    return _load(data_dir, CORRESPONDENCE).get("contacts") or []


FILES = "files"
FILE_INDEX = "files.json"
# An attachment worth keeping: a PDF whose name or message says it is a bill, invoice, statement, receipt, or policy paper.
DOCUMENT_WORDS = re.compile(r"(?i)invoice|inv\b|bill|statement|receipt|renewal|declaration|dec page|policy|proposal|estimate|quote|"
                            r"premium|notice|report|certificate|coi\b|contract|agreement|w-?9|1099|confirmation")


def fetch_documents(gmail: Any, data_dir: Path, community: Any, *, log: Callable[[str], None] | None = None) -> dict[str, int]:
    """Save the PDF attachments of business email that look like documents to ``data/gmail/files/<message id>/``.

    A message qualifies when its sender is named (``Sender.domains``) or its subject or an attachment's name carries a
    document word, or when it came through an accounts payable group (``mystique/groups.py``), whoever forwarded it. A
    file already saved is not fetched again. The index records each file's message, date, domains, groups, subject,
    name, and content hash.
    """
    import hashlib

    say = log or (lambda _m: None)
    root = gmail_dir(data_dir)
    index_path = root / FILE_INDEX
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.is_file() else {"files": []}
    have = {(f["messageId"], f["name"]) for f in index["files"]}
    senders = tuple(community.senders())
    from jason.community.groups import GroupPurpose, groups_for

    payable = groups_for(GroupPurpose.ACCOUNTS_PAYABLE, tuple(community.google_groups()))
    saved = skipped = 0
    for m in _load(data_dir, CORRESPONDENCE).get("messages") or []:
        pdfs = [a for a in m.get("attachments") or [] if a.lower().endswith(".pdf")]
        # Mail to accounts payable is a bill to pay, even when a board member forwards it.
        to_payable = m.get("direction") == "in" and bool(payable.intersection(m.get("groups") or []))
        # Otherwise only business email: an owner's or board member's attachments are theirs, not a vendor's document.
        if not pdfs or not (m.get("domains") or to_payable):
            continue
        named = sender_of(m.get("domains") or [], senders)
        if named is None and not to_payable and not DOCUMENT_WORDS.search(" ".join([m.get("subject", ""), *pdfs])):
            continue
        if all((m["messageId"], a) in have for a in pdfs):
            skipped += len(pdfs)
            continue
        meta = gmail.get_metadata(m["messageId"])
        for part in meta["attachments"]:
            name = part["name"]
            if not name.lower().endswith(".pdf") or (m["messageId"], name) in have or not part.get("attachmentId"):
                continue
            data = gmail.get_attachment(m["messageId"], part["attachmentId"])
            dest = root / FILES / m["messageId"] / re.sub(r'[<>:"/\\|?*]', "_", name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            index["files"].append({"messageId": m["messageId"], "at": m["at"], "direction": m["direction"], "domains": m.get("domains") or [],
                                   "groups": m.get("groups") or [],
                                   "subject": m.get("subject", ""), "name": name, "path": str(dest.relative_to(Path(data_dir))),
                                   "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
            have.add((m["messageId"], name))
            saved += 1
            if saved % 50 == 0:
                say(f"  {saved} attachments saved")
                index_path.write_text(json.dumps(index, indent=1), encoding="utf-8")
    index_path.write_text(json.dumps(index, indent=1), encoding="utf-8")
    say(f"email attachments: {saved} saved, {skipped} already on disk, {len(index['files'])} in all")
    return {"saved": saved, "onDisk": len(index["files"])}


def email_files(data_dir: Path) -> list[dict[str, Any]]:
    return _load(data_dir, FILE_INDEX).get("files") or []


def notice_check(data_dir: Path) -> dict[str, Any]:
    """The Gmail notices against the mail the API synced: missing items, unscanned deliveries, and scan times."""
    from jason.tasks.mail import load_items

    stored = _load(data_dir, NOTICES)
    notices = stored.get("notices") or []
    items = load_items(data_dir)
    delivered = {n["image"]: n for n in notices if n["event"].lower().startswith("new mail") and n["image"]}
    scanned = {n["image"]: n for n in notices if n["mailId"]}
    by_id = {n["mailId"]: n for n in scanned.values()}
    first = min((n["at"] for n in notices), default="")
    missing = sorted(({"mailId": m, "scannedAt": n["at"], "scan": n["scan"]} for m, n in by_id.items() if m not in items),
                     key=lambda r: r["scannedAt"], reverse=True)
    unscanned = sorted(({"deliveredAt": n["at"], "image": image} for image, n in delivered.items() if image not in scanned),
                       key=lambda r: r["deliveredAt"], reverse=True)
    waits = []
    for image, n in scanned.items():
        if image in delivered:
            start = datetime.fromisoformat(delivered[image]["at"])
            waits.append((datetime.fromisoformat(n["at"]) - start).total_seconds() / 86400)
    no_notice = sorted(m for m, row in items.items() if m not in by_id and (row.get("received") or "") >= first[:10] and row.get("text"))
    events: dict[str, int] = {}
    for n in notices:
        events[n["event"]] = events.get(n["event"], 0) + 1
    return {
        "found": bool(notices),
        "syncedAt": stored.get("syncedAt"),
        "notices": len(notices),
        "events": dict(sorted(events.items(), key=lambda kv: -kv[1])),
        "since": first[:10],
        "notInApiSync": missing,
        "deliveredNotScanned": unscanned,
        "scannedWithoutNotice": no_notice,
        "medianDaysToScan": round(sorted(waits)[len(waits) // 2], 1) if waits else None,
        "caveats": [
            "A delivered item with no scan may be waiting for a scan request, or was forwarded, shredded, or discarded; "
            "PostScanMail is where that is decided.",
            "Gmail keeps what the group received; a notice deleted from the inbox is not seen.",
        ],
    }


def check_lines(check: dict[str, Any], corr: dict[str, Any] | None = None) -> list[str]:
    out = [f"PostScanMail notices in Gmail since {check['since'] or '-'}: {check['notices']} ("
           + ", ".join(f"{k} {n}" for k, n in check["events"].items()) + ")"]
    if check["medianDaysToScan"] is not None:
        out.append(f"  median days from delivery to scan: {check['medianDaysToScan']}")
    out.append(f"  scanned items the API sync does not hold: {len(check['notInApiSync'])}")
    for m in check["notInApiSync"][:10]:
        out.append(f"    mail {m['mailId']} scanned {m['scannedAt'][:10]} ({m['scan']})")
    out.append(f"  delivered and not scanned: {len(check['deliveredNotScanned'])}")
    for d in check["deliveredNotScanned"][:10]:
        out.append(f"    delivered {d['deliveredAt'][:10]}")
    if check["scannedWithoutNotice"]:
        out.append(f"  synced items with no Gmail notice: {len(check['scannedWithoutNotice'])}")
    if corr:
        from jason.community import mystique

        senders = tuple(mystique().senders())
        messages = [m for m in corr.get("messages") or [] if m.get("domains")]
        by_sender: dict[str, int] = {}
        unnamed: dict[str, int] = {}
        for m in messages:
            named = sender_of(m.get("domains") or [], senders)
            if named is not None:
                by_sender[named.name] = by_sender.get(named.name, 0) + 1
            else:
                for d in m.get("domains") or []:
                    unnamed[d] = unnamed.get(d, 0) + 1
        out.append("")
        out.append(f"Email read: {corr.get('read', 0)} over {corr.get('days', '?')} days; {len(messages)} business; "
                   f"{sum(by_sender.values())} with a named sender; {corr.get('personal', 0)} with a personal address")
        for name, n in sorted(by_sender.items(), key=lambda kv: -kv[1]):
            out.append(f"  {name}: {n}")
        if unnamed:
            out.append("  domains no sender names (see jason contacts): "
                       + ", ".join(f"{d} {n}" for d, n in sorted(unnamed.items(), key=lambda kv: -kv[1])[:25]))
        out.extend(group_lines(corr.get("messages") or [], tuple(mystique().google_groups())))
    out.append("")
    out.extend(f"* {c}" for c in check["caveats"])
    return out


__all__ = ["sync", "notice_check", "check_lines", "correspondence", "contacts", "sender_of", "parse_notice", "fetch_documents", "email_files"]
