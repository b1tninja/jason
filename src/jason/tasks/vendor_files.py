"""File a vendor's email attachments in Drive, by the profile's filing rules: the document's kind first, its source second.

For each vendor in the sender directory (kind ``VENDOR`` only), Gmail is searched over all time (read-only) for its
known addresses: the sender row's domains, and the email and website on its PayHOA vendor record (a PayHOA email at a
personal domain, such as gmail.com, counts as that one address). An attachment is filed only when one of those
addresses sent it; a vendor's invoice sent through a shared service (QuickBooks, Adobe Sign) is not, and a vendor
with no known address is skipped. Images and signature parts are left out; a document is a PDF, a Word or Excel
file, or a CSV.

Each attachment is classified (``Community.classify_document`` by name, then ``jason.community.content`` by the PDF's
own words, kept only when the words give a kind a vendor sends). The profile's ``EmailFiling`` rules then place it:
the first rule whose kind and source (named senders, or kinds of source) take it gives the folder path from the
filing root, with ``{vendor}`` and ``{year}`` (the fiscal year the message came in) filled in; a document no rule takes
goes to the fallback, the vendor's own folder. The folders are made as needed.

**No duplicates.** An attachment is not uploaded when Drive already holds the same content: a file in the Drive sync
(``drive/files.json``) or a file of the same name found now, with the same MD5; or a file jason filed before, found by
its ``appProperties`` (``gmailSha256``). The same content in several messages is filed once, from the earliest.

**The link.** Each upload keeps its original name and carries the message in ``appProperties`` (``gmailMessageId``,
``gmailSha256``, ``vendor``, ``kind``) and in its description (date, sender, subject), so the file names its source,
which a file a person saves from Gmail does not. Each filing is logged in ``data/drive/vendor-files.jsonl``.

Nothing is uploaded without ``yes``: the plan is printed first. Nothing in Gmail changes.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

LOG = "vendor-files.jsonl"
APP_SHA = "gmailSha256"
DOCUMENT = re.compile(r"(?i)\.(pdf|docx?|xlsx?|csv)$")
MIME = {"pdf": "application/pdf", "doc": "application/msword", "csv": "text/csv",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xls": "application/vnd.ms-excel", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


@dataclass
class Attachment:
    vendor: str
    message_id: str
    at: str
    sender: str
    subject: str
    name: str
    sha256: str
    md5: str
    size: int
    kind: str = ""
    kind_by: str = ""
    action: str = ""                 # "file", "in drive", "filed before", "repeat"
    where: str = ""                  # the Drive path it is in, or the folder it will go to
    path: tuple[str, ...] = ()       # the folder names from the filing root, for a document to file
    rule: str = ""                   # the rule that placed it: its kind and source, or "fallback"
    file_id: str = ""


@dataclass
class VendorPlan:
    vendor: str
    query: str
    messages: int = 0
    attachments: list[Attachment] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        found: dict[str, int] = {}
        for a in self.attachments:
            found[a.action] = found.get(a.action, 0) + 1
        return found


def vendors(community: Any, name: str = "") -> list[Any]:
    """The sender directory's vendors, or the one named (case ignored)."""
    from jason.community.sources import SourceKind

    rows = [s for s in community.senders() if s.kind is SourceKind.VENDOR]
    if name and name.lower() != "all":
        rows = [s for s in rows if s.name.lower() == name.lower()]
    return rows


@dataclass(frozen=True)
class Known:
    """A vendor's known addresses: whole domains, and single addresses at personal domains."""

    domains: tuple[str, ...] = ()
    emails: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.domains or self.emails)


def known_addresses(sender: Any, data_dir: Path | None = None) -> Known:
    """The sender row's domains, with the email and website on its PayHOA vendor record (``jason contacts --fetch``)."""
    from jason.tasks.contacts import _domain_of, _rows
    from jason.tasks.gmail import PERSONAL

    domains = {d.lower() for d in sender.domains}
    emails: set[str] = set()
    for row in _rows(Path(data_dir)) if data_dir else []:
        if not sender.payhoa_vendor or str(row.get("vendorName") or row.get("name") or "") != sender.payhoa_vendor:
            continue
        email = str(row.get("email") or "").strip().lower()
        for value in (email, str(row.get("website") or "")):
            host = _domain_of(value)
            if host and host not in PERSONAL:
                domains.add(host)
        if email and _domain_of(email) in PERSONAL:
            emails.add(email)
    return Known(tuple(sorted(domains)), tuple(sorted(emails)))


def query_for(known: Known) -> str:
    """Mail from or to its known domains and addresses."""
    return " OR ".join(f"from:{a} OR to:{a}" for a in (*known.domains, *known.emails))


def sent_by(known: Known, from_header: str) -> bool:
    """One of its known addresses sent it: an address at a known domain (or a subdomain), or a known address."""
    address = from_header.rsplit("<", 1)[-1].strip(" >").lower()
    host = address.rsplit("@", 1)[-1]
    return address in known.emails or any(host == d or host.endswith("." + d) for d in known.domains)


def vendor_kinds() -> frozenset[Any]:
    """The kinds a vendor's document can be. A reading of its words as another kind (an owner's statement, a ballot)
    is a miss: a vendor's statement of account reads like an owner's."""
    from jason.community.symbols import DocumentKind as K

    return frozenset({K.INVOICE, K.PROPOSAL, K.CONTRACT, K.INSPECTION_REPORT, K.ELEVATED_ELEMENT_INSPECTION,
                      K.EVIDENCE_OF_INSURANCE, K.NOTICE, K.CORRESPONDENCE, K.FORM, K.TAX_RETURN})


def pdf_words(name: str, data: bytes) -> str:
    """A PDF's text (the first 20,000 characters), or empty for another format or an unreadable file."""
    if not name.lower().endswith(".pdf"):
        return ""
    try:
        from jason.tasks.vendor_portals import _pdf_text

        return _pdf_text(data)[:20000]
    except Exception:  # an unreadable PDF has no words
        return ""


def classify(community: Any, name: str, words: str) -> tuple[Any, str]:
    """The kind by name (the profile's rules), then by the PDF's own words when they give a vendor's kind; (None, "")
    when neither says."""
    kind = community.classify_document(name)
    if kind is not None:
        return kind, "name"
    if not words:
        return None, ""
    from jason.community.content import classify_text

    kind, why = classify_text(words)
    return (kind, why) if kind in vendor_kinds() else (None, "")


def same_document(a_name: str, a_words: str, b_name: str, b_words: str) -> bool:
    """Two copies of one document sent twice (an invoice "for review" and again "paid"): the same name and, apart from
    figures and spacing, nearly the same words."""
    from difflib import SequenceMatcher

    if a_name.casefold() != b_name.casefold() or not a_words or not b_words:
        return False
    strip = lambda t: re.sub(r"[\d\s]+", " ", t).strip()[:4000]
    return SequenceMatcher(None, strip(a_words), strip(b_words)).ratio() >= 0.9


def drive_index(data_dir: Path) -> tuple[dict[str, str], dict[str, str]]:
    """From the Drive sync: each content's path by MD5, and each folder's path by id."""
    path = Path(data_dir) / "drive" / "files.json"
    if not path.is_file():
        return {}, {}
    files = json.loads(path.read_text(encoding="utf-8"))["files"]
    return ({f["md5"]: f["path"] for f in files if f.get("md5")},
            {f["folderId"]: f["path"].rsplit("/", 1)[0] for f in files if f.get("folderId")})


def _quote(text: str) -> str:
    return text.replace("\\", "\\\\").replace("'", "\\'")


def in_drive(drive: Any, att: Attachment, known: dict[str, str]) -> tuple[str, str]:
    """(action, where) when Drive already holds it; ("", "") when it does not."""
    if att.md5 in known:
        return "in drive", known[att.md5]
    filed = drive.list_files(f"appProperties has {{ key='{APP_SHA}' and value='{att.sha256}' }} and trashed = false",
                             fields="id,name")
    if filed:
        return "filed before", filed[0]["id"]
    same = drive.list_files(f"name = '{_quote(att.name)}' and trashed = false", fields="id,name,md5Checksum")
    hit = next((f for f in same if f.get("md5Checksum") == att.md5), None)
    if hit:
        return "in drive", hit["id"]
    return "", ""


def fiscal_year(at: str, year_end: tuple[int, int] | None) -> int:
    """The fiscal year a date falls in, named by the year it ends: the calendar year when the year ends December 31."""
    year, month, day = int(at[:4]), int(at[5:7]), int(at[8:10])
    if year_end and (month, day) > tuple(year_end):
        return year + 1
    return year


def rule_label(rule: Any) -> str:
    if rule is None:
        return "fallback"
    who = ", ".join(rule.senders) or ", ".join(getattr(k, "value", str(k)) for k in rule.source_kinds) or "any source"
    return f"{getattr(rule.kind, 'value', 'any kind')} from {who}"


def plan_vendor(gmail: Any, drive: Any, community: Any, sender: Any, *, known: dict[str, str], seen: set[str],
                data_dir: Path | None = None,
                limit: int = 2000) -> tuple[VendorPlan, dict[str, bytes]]:
    """Every document the vendor sent from a known address, classified and checked against Drive. Returns the plan and
    the bytes to file; a vendor with no known address has an empty plan."""
    filing = community.email_filing()
    addresses = known_addresses(sender, data_dir)
    result = VendorPlan(sender.name, query_for(addresses))
    blobs: dict[str, bytes] = {}
    if not addresses:
        return result, blobs
    rows = list(gmail.iter_messages(result.query, limit=limit))
    result.messages = len(rows)
    found: list[tuple[str, Attachment, bytes]] = []
    for row in rows:
        meta = gmail.get_metadata(row["id"], headers=("From", "Subject"))
        head = meta["headers"]
        if not sent_by(addresses, head.get("From", "")):
            continue
        at = datetime.fromtimestamp(int(meta["internalDate"]) / 1000, tz=timezone.utc).isoformat(timespec="seconds")
        for part in meta["attachments"]:
            if not part.get("attachmentId") or not DOCUMENT.search(part["name"] or ""):
                continue
            data = gmail.get_attachment(meta["id"], part["attachmentId"])
            att = Attachment(sender.name, meta["id"], at, head.get("From", ""), head.get("Subject", ""), part["name"],
                             hashlib.sha256(data).hexdigest(), hashlib.md5(data).hexdigest(), len(data))
            found.append((at, att, data))
    # Group the copies: the same content, or the same document sent again. A group Drive holds is not filed; otherwise
    # its latest copy is filed (it carries the document's last state, such as "paid").
    groups: list[list[tuple[Attachment, bytes, str]]] = []
    for _, att, data in sorted(found, key=lambda t: t[0]):
        words = pdf_words(att.name, data)
        kind, why = classify(community, att.name, words)
        att.kind, att.kind_by = (kind.value if kind is not None else ""), why
        group = next((g for g in groups if any(o.sha256 == att.sha256 or same_document(o.name, w, att.name, words)
                                               for o, _, w in g)), None)
        if group is None:
            groups.append([(att, data, words)])
        else:
            group.append((att, data, words))
    for group in groups:
        holder = ""
        for att, _, _ in group:
            if att.sha256 in seen:
                att.action, att.where = "repeat", "an earlier vendor's plan"
                continue
            seen.add(att.sha256)
            att.action, att.where = in_drive(drive, att, known)
            holder = holder or (att.where if att.action else "")
        pending = [(a, d) for a, d, _ in group if not a.action]
        for att, _ in pending:
            att.action, att.where = ("copy in drive", holder) if holder else ("earlier copy", "a later copy is filed")
        if pending and not holder:
            att, data = pending[-1]
            from jason.community.symbols import DocumentKind

            kind = DocumentKind(att.kind) if att.kind else None
            path, rule = filing.path_for(sender, kind, fiscal_year(att.at, community.fiscal_year_end()))
            att.action, att.path, att.rule = "file", path, rule_label(rule)
            att.where = "My Drive/" + "/".join(path) if filing.root == "root" else "/".join(path)
            blobs[att.sha256] = data
        result.attachments.extend(a for a, _, _ in group)
    result.attachments.sort(key=lambda a: a.at)
    return result, blobs


def _folder(drive: Any, parent: str, name: str, made: dict[tuple[str, str], str]) -> str:
    key = (parent, name)
    if key not in made:
        made[key] = drive.child_folder(parent, name) or drive.create_folder(name, parent)
    return made[key]


def file_plan(drive: Any, community: Any, plan: VendorPlan, blobs: dict[str, bytes], data_dir: Path,
              log: Callable[[str], None] | None = None) -> int:
    """Upload each attachment the plan marks "file" and log it. Returns how many were filed."""
    filing = community.email_filing()
    made: dict[tuple[str, str], str] = {}
    log_path = Path(data_dir) / "drive" / LOG
    log_path.parent.mkdir(parents=True, exist_ok=True)
    done = 0
    for att in plan.attachments:
        if att.action != "file":
            continue
        parent = filing.root
        for name in att.path:
            parent = _folder(drive, parent, name, made)
        ext = att.name.rsplit(".", 1)[-1].lower()
        description = f"From Gmail, {att.at[:10]}: {att.sender} — {att.subject}"[:900]
        att.file_id = drive.upload_bytes(att.name, blobs[att.sha256], mime_type=MIME.get(ext, "application/octet-stream"),
                                         parent_id=parent, description=description,
                                         app_properties={"gmailMessageId": att.message_id, APP_SHA: att.sha256,
                                                         "vendor": att.vendor[:100], "kind": att.kind or "unclassified"})
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({**asdict(att), "filedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                 "parent": parent}) + "\n")
        done += 1
        if log:
            log(f"filed {att.name} -> {att.where}")
    return done


def plan_lines(plan: VendorPlan) -> list[str]:
    counts = plan.counts()
    if not plan.query:
        return [f"{plan.vendor}: no known domain or email (mystique/senders.py, PayHOA's vendor record); skipped"]
    out = [f"{plan.vendor}: {plan.messages} messages; " + ", ".join(f"{n} {k}" for k, n in sorted(counts.items()))
           if counts else f"{plan.vendor}: {plan.messages} messages; no documents it sent"]
    for a in plan.attachments:
        if a.action == "repeat":
            continue
        kind = a.kind or "unclassified"
        why = f"  [{a.rule}]" if a.action == "file" else ""
        out.append(f"  {a.at[:10]} {a.action:<13} {kind:<18} {a.name}  ->  {a.where}{why}")
    return out


__all__ = ["Attachment", "Known", "VendorPlan", "vendors", "known_addresses", "query_for", "sent_by", "classify", "in_drive", "plan_vendor",
           "file_plan", "plan_lines", "drive_index", "fiscal_year", "rule_label", "LOG", "APP_SHA"]
