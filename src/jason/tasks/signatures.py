"""Signatures: who writes to the association, read from the signature block at the end of their email.

jason's Gmail store (``data/gmail/correspondence.json``) keeps headers only, so a sender is known by its domain, its
display name, and, for a personal address, who the records knew the person to be ("owner of 3006 MAGICAL WALK",
"personal"). The signature says more: a title, a company, a license, a disclaimer. This task reads it, and only it.

- **What is read.** By default the latest two inbound messages from each sender (``plan``): each business address,
  each owner label, and each thread from an unknown personal address. ``domains``, ``threads``, and ``non_owners``
  narrow it; automated mailboxes (``noreply@``, notifications) and the association's own addresses are skipped; a
  message already read is not read again. ``limit`` caps the messages a run reads.
- **How.** ``GoogleGmail.get_body`` (gmail.readonly, the scope jason already holds) returns the sender headers and the
  text and HTML parts. The body is held in memory for one message: ``jason.community.signatures`` splits off the
  signature block and parses its fields, and the text is dropped. No body, no subject, no block is written.
- **What is kept** (``data/gmail/signatures.json``): one row per sender. A business address keeps the signature's
  fields (name, title, company, website, licenses, labeled business lines, link kinds) and the role guess with its
  cues. A personal address is never stored: its row is keyed by a hash, carries the party label correspondence.json
  already holds, and keeps only the provider ("gmail.com"). An owner's row, or any individual's, keeps only the role,
  its confidence, the kinds of cue, and the presence flags (a phone, a street address, a disclaimer, sent from a phone).
- **The summary** joins each row to the directory (``mystique/senders.py`` by domain, else by company words; PayHOA's
  vendor-info report by email or website domain) and to the units in its threads, and lists the candidates: senders
  whose signature reads as a property manager, realtor, vendor, or other professional that the directory does not
  name. A person adds the directory row; jason does not.

Jason sends nothing and changes nothing in Gmail, PayHOA, or Drive.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from jason.google.errors import GoogleError
from jason.tasks.gmail import CORRESPONDENCE, PERSONAL, _load, _senders, gmail_dir, sender_of

SIGNATURES = "signatures.json"
STORE_KEY = "gmail-signatures"
# Mailboxes no person signs: a no-reply or notification word in the mailbox, a machine-made mailbox (a long hex or
# digit run), or a sending platform's host.
_AUTOMATED_BOX = re.compile(
    r"no[._-]?reply|do[._-]?not[._-]?reply|notification|notify|alerts?\b|mailer|postmaster|bounce|newsletter|digest|"
    r"marketing|automated|invitation|receipt|statement|invoic|billing|billpay|payments?\b|orders?\b|order-update|shipment|"
    r"tracking|confirm|updates?\b|drive-shares|calendar|e-?bills?|paperless|[0-9a-f]{12,}|\d{6,}", re.I)
_AUTOMATED_HOST = re.compile(r"^(?:api|app|apps|mail|email|mailer|mailgun|bounce|notify\w*|notifications?|alerts?|em\d*|e)\.|"
                             r"(?:^|\.)(?:docusign\.net|echosign\.com|adobesign\.com|amazonses\.com|sendgrid\.net)$", re.I)


def automated(address: str) -> bool:
    box, _, host = address.lower().partition("@")
    return bool(_AUTOMATED_BOX.search(box) or _AUTOMATED_HOST.search(host))
# Party labels that are an owner (or a board member, a buyer, a former owner): their rows keep no fields.
OWNER_LABEL = re.compile(r"^(?:owner of|buyer of|former owner of|board member|member)\b")
_DOMAIN = re.compile(r"^[a-z0-9.-]+\.[a-z]{2,}$")


def _consumer(host: str) -> bool:
    from jason.community.signatures import CONSUMER_DOMAINS

    return host in PERSONAL or host in CONSUMER_DOMAINS


@dataclass
class Target:
    """One sender to read: a business address, an owner label, or an unknown personal address's thread."""

    key: str
    kind: str                      # "business" or "personal"
    domain: str = ""               # a business sender's domain
    party: str = ""                # a personal sender's label in correspondence.json
    messages: list[str] = field(default_factory=list)   # newest first
    threads: list[str] = field(default_factory=list)
    known: str = ""                # the directory's name for it, when its domain is named
    last: str = ""


def _personal_label(m: dict[str, Any]) -> str:
    labels = [p for p in m.get("parties") or [] if p != "association" and not _DOMAIN.match(p)]
    return labels[0] if labels else ""


def _done(data_dir: Path) -> set[str]:
    return {mid for row in _load(data_dir, SIGNATURES).get("rows") or [] for mid in row.get("messages") or []}


def plan(data_dir: Path, community: Any = None, *, per_sender: int = 2, domains: Iterable[str] = (), threads: Iterable[str] = (),
         non_owners: bool = False, limit: int = 40, include_automated: bool = False, refresh: bool = False) -> list[Target]:
    """The senders a run would read and their latest ``per_sender`` inbound messages, from disk only.

    Unknown business senders come first, then unknown personal senders, then senders the directory names, then
    owners; ``limit`` caps the messages across them. A message already read is skipped unless ``refresh``.
    """
    if community is None:
        from jason.community import mystique

        community = mystique()
    senders = tuple(getattr(community, "senders", lambda: ())())
    own = set(community.email_domains())
    wanted_domains = {d.lower().lstrip("@") for d in domains}
    wanted_threads = set(threads)
    done = set() if refresh else _done(data_dir)
    found: dict[str, Target] = {}
    for m in _load(data_dir, CORRESPONDENCE).get("messages") or []:
        if m.get("direction") != "in" or m["messageId"] in done:
            continue
        if wanted_threads and m.get("threadId") not in wanted_threads:
            continue
        writer = next(((n, a) for n, a, role in m.get("people") or [] if role == "from"), None)
        if writer:
            address = writer[1].lower()
            host = address.rsplit("@", 1)[-1]
            if host in own or (not include_automated and automated(address)):
                continue
            if wanted_domains and not any(host == d or host.endswith("." + d) for d in wanted_domains):
                continue
            named = sender_of([host], senders)
            if named is not None and named.kind.value == "service platform" and not include_automated:
                continue
            target = found.setdefault(address, Target(address, "business", domain=host, known=named.name if named else ""))
        else:
            if wanted_domains:
                continue                     # a personal sender's domain is not in the store
            label = _personal_label(m)
            if not label or (non_owners and OWNER_LABEL.match(label)):
                continue
            key = label if label != "personal" else f"personal:{m['threadId']}"
            target = found.setdefault(key, Target(key, "personal", party=label))
        target.messages.append(m["messageId"])
        target.last = max(target.last, m.get("at") or "")
        if m.get("threadId") and m["threadId"] not in target.threads:
            target.threads.append(m["threadId"])
    at = {m["messageId"]: m.get("at") or "" for m in _load(data_dir, CORRESPONDENCE).get("messages") or []}

    def rank(t: Target) -> tuple:
        owner = t.kind == "personal" and bool(OWNER_LABEL.match(t.party))
        return (owner, bool(t.known), t.kind != "business", _neg(t.last))

    out: list[Target] = []
    budget = limit
    for t in sorted(found.values(), key=rank):
        if budget <= 0:
            break
        t.messages = sorted(t.messages, key=lambda mid: at.get(mid, ""), reverse=True)[:min(per_sender, budget)]
        budget -= len(t.messages)
        out.append(t)
    return out


def _neg(stamp: str) -> str:
    """A sort key that puts the latest timestamp first."""
    return "".join(chr(0x10FFFF - ord(c)) for c in stamp)


def _key_of(address: str) -> str:
    """A personal address is never stored: its row is keyed by a hash of it."""
    return "personal:" + hashlib.sha256(address.strip().lower().encode("utf-8")).hexdigest()[:12]


def fetch(gmail: Any, data_dir: Path, community: Any, targets: list[Target], *, non_owners: bool = False,
          log: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Read each target message's signature (read-only) and update ``data/gmail/signatures.json``.

    Each body is held for one message and dropped once its signature is parsed; only the signature's fields are kept,
    and an owner's or individual's row keeps only the role and presence flags.
    """
    from jason.community.signatures import Signature, read_signature
    from jason.locks import Resource, hold
    from jason.tasks.parties import PartyResolver

    say = log or (lambda _m: None)
    own = set(community.email_domains())
    resolver = PartyResolver(data_dir) if any(t.kind == "personal" for t in targets) else None
    counts: Counter = Counter()
    read: dict[str, dict[str, Any]] = {}
    for t in targets:
        for mid in t.messages:
            try:
                message = gmail.get_body(mid)
            except GoogleError as exc:
                counts["errors"] += 1
                say(f"  {mid}: {str(exc)[:120]}")
                continue
            writers, _via = _senders(message.get("headers") or {}, own)
            if not writers:
                counts["no sender"] += 1
                continue
            display, address = writers[0]
            host = address.rsplit("@", 1)[-1]
            if host in own:
                counts["association"] += 1
                continue
            personal = _consumer(host)
            party = ""
            if personal:
                ms = int(message.get("internalDate") or 0)
                day = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date() if ms else None
                party = resolver.resolve(address, display, day) if resolver else "personal"
                if non_owners and OWNER_LABEL.match(party):
                    counts["owner skipped"] += 1
                    continue
            # The body lives only for these lines: both renderings are read, and the fuller signature is kept.
            found = [read_signature(text, address=address, display_name=display)
                     for text in (message.get("plain") or "", message.get("html") or "") if text]
            message = None
            sig = max(found, key=lambda s: (s.fields, s.confidence), default=Signature())
            counts["read"] += 1
            key = _key_of(address) if personal else address
            row = read.setdefault(key, {"key": key, "personal": personal, "host": host, "party": party, "messages": [],
                                        "threads": [], "signatures": [], "known": t.known})
            row["messages"].append(mid)
            if t.threads:
                row["threads"] = sorted(set(row["threads"]) | set(t.threads))
            if party and not row["party"]:
                row["party"] = party
            row["signatures"].append(sig)
            counts["signature found" if sig.fields else "no signature"] += 1
    with hold(Resource.STORE, STORE_KEY, purpose="jason signatures --fetch"):
        stored = _load(data_dir, SIGNATURES)
        rows = {r["sender"]: r for r in stored.get("rows") or []}
        for key, got in read.items():
            rows[key] = _row(got, rows.get(key))
        _write(data_dir, community, list(rows.values()))
    say(f"signatures: {counts['read']} messages read, {counts['signature found']} with a signature, {len(read)} senders")
    return {"read": counts["read"], "senders": len(read), **{k: v for k, v in counts.items() if k != "read"}}


def _row(got: dict[str, Any], before: dict[str, Any] | None) -> dict[str, Any]:
    """One sender's stored row: the fullest signature's fields (or only flags for an individual), the messages read."""
    sigs = got["signatures"]
    best = max(sigs, key=lambda s: (s.fields, s.confidence))
    roles = Counter(s.role.value for s in sigs if s.fields or s.role.value != "unknown")
    if before:
        roles.update(before.get("roleVotes") or {})
    party = got["party"] or (before or {}).get("party", "")
    private = got["personal"] and (bool(OWNER_LABEL.match(party)) or not best.role.professional)
    row: dict[str, Any] = {"sender": got["key"], "kind": "personal" if got["personal"] else "business"}
    if got["personal"]:
        row.update({"provider": got["host"], "party": party})
    else:
        row["domain"] = got["host"]
    # A fuller signature read earlier is kept when this run's is thinner.
    if before and before.get("fieldCount", 0) > best.fields:
        fields = {k: v for k, v in before.items() if k not in ("sender", "kind", "provider", "party", "domain", "messages",
                                                            "threads", "roleVotes", "readAt", "private")}
    else:
        fields = {**best.to_dict(private=private), "fieldCount": best.fields}
        if private:
            fields["fieldCount"] = best.fields
    row.update(fields)
    row["private"] = private or bool((before or {}).get("private"))
    if row["private"]:
        for k in ("name", "title", "company", "website", "businessPhones", "licenses", "links"):
            row.pop(k, None)
        row["reasons"] = sorted({r.split(":", 1)[0] for r in row.get("reasons") or []})
    row["roleVotes"] = dict(roles)
    row["messages"] = sorted(set((before or {}).get("messages") or []) | set(got["messages"]))
    row["threads"] = sorted(set((before or {}).get("threads") or []) | set(got["threads"]))
    row["readAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return row


def _vendor_domains(data_dir: Path) -> dict[str, str]:
    """PayHOA vendors by the domain of their email and website (``jason contacts --fetch``)."""
    from jason.tasks.contacts import _domain_of, _rows

    out: dict[str, str] = {}
    for r in _rows(data_dir):
        name = str(r.get("vendorName") or r.get("name") or "")
        for value in (str(r.get("email") or ""), str(r.get("website") or "")):
            d = _domain_of(value)
            if d and "." in d and not _consumer(d):
                out.setdefault(d, name)
    return out


def _units(threads: Iterable[str], by_thread: dict[str, set[str]]) -> list[str]:
    return sorted({u for t in threads for u in by_thread.get(t, ())})


def summarize(data_dir: Path, community: Any, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Rows joined to the directory and to the units in their threads, and the summary with the candidates."""
    from jason.community.sources import resolve

    senders = tuple(getattr(community, "senders", lambda: ())())
    vendors = _vendor_domains(data_dir)
    by_thread: dict[str, set[str]] = {}
    for m in _load(data_dir, CORRESPONDENCE).get("messages") or []:
        for p in m.get("parties") or []:
            hit = re.match(r"^(?:owner of|buyer of|former owner of) (.+?)(?: \(conveyed [^)]*\))?$", p)
            if hit:
                for unit in hit.group(1).split(", owner of "):
                    by_thread.setdefault(m["threadId"], set()).add(unit)
    out: list[dict[str, Any]] = []
    candidates: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        row = dict(row)
        directory: dict[str, Any] = {}
        named = sender_of([row["domain"]], senders) if row.get("domain") else None
        how = "domain"
        if named is None and row.get("company"):
            named, kind, _level, _word = resolve(row["company"], "", senders)
            how = "company words"
        if named is not None:
            directory = {"name": named.name, "kind": named.kind.value, "by": how}
        vendor = next((v for d, v in vendors.items() if row.get("domain") and (row["domain"] == d or row["domain"].endswith("." + d))), "")
        if not vendor and row.get("website"):
            vendor = vendors.get(row["website"], "")
        if vendor:
            directory["payhoaVendor"] = vendor
        row["directory"] = directory
        row["units"] = _units(row.get("threads") or [], by_thread)
        out.append(row)
        professional = row.get("role") not in ("individual", "unknown", None)
        if professional and not row.get("private") and not directory:
            where = row.get("domain") or row.get("website") or ""
            group = candidates.setdefault((row["role"], where or (row.get("company") or "").lower()), {
                "role": row["role"], "domain": where, "company": row.get("company") or "", "senders": 0, "units": set(),
                "licenses": set(), "confidence": 0.0})
            group["senders"] += 1
            group["units"] |= set(row["units"])
            group["company"] = group["company"] or row.get("company") or ""
            group["licenses"] |= {lic["kind"] for lic in row.get("licenses") or []}
            group["confidence"] = max(group["confidence"], row.get("confidence") or 0.0)
    order = ["property manager", "realtor", "vendor or contractor", "association manager", "title or escrow", "attorney",
             "insurer or agent", "lender", "government"]
    listed = sorted(({**c, "units": sorted(c["units"]), "licenses": sorted(c["licenses"])} for c in candidates.values()),
                    key=lambda c: (order.index(c["role"]) if c["role"] in order else 99, -c["senders"], c["domain"]))
    roles = Counter(r.get("role") or "unknown" for r in out)
    # A business whose signature names no role is listed apart: a domain to look at, not yet a candidate.
    summary = {"senders": len(out), "messages": sum(len(r.get("messages") or []) for r in out),
               "roles": dict(sorted(roles.items())), "known": sum(1 for r in out if r["directory"]),
               "private": sum(1 for r in out if r.get("private")),
               "candidates": [c for c in listed if c["role"] in order],
               "unclear": [c for c in listed if c["role"] not in order]}
    return out, summary


def _write(data_dir: Path, community: Any, rows: list[dict[str, Any]]) -> Path:
    joined, summary = summarize(data_dir, community, rows)
    path = gmail_dir(data_dir) / SIGNATURES
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                "rows": sorted(joined, key=lambda r: r["sender"]), "summary": summary}, indent=1), encoding="utf-8")
    return path


def report(data_dir: Path, community: Any) -> dict[str, Any]:
    """The stored rows, joined to the directory as it stands now (a sender row added since takes effect here)."""
    rows = _load(data_dir, SIGNATURES).get("rows") or []
    joined, summary = summarize(data_dir, community, rows)
    return {"rows": joined, "summary": summary}


def summary_lines(result: dict[str, Any]) -> list[str]:
    s = result["summary"]
    out = [f"{s['senders']} senders from {s['messages']} messages; {s['known']} named in the directory; "
           f"{s['private']} owners or individuals kept as flags only"]
    if s["roles"]:
        out.append("roles: " + ", ".join(f"{k} {v}" for k, v in s["roles"].items()))
    if s["candidates"]:
        out.append("")
        out.append("Candidates the directory does not name (a person adds the row in mystique/senders.py):")
        for c in s["candidates"]:
            units = f"; units {', '.join(c['units'][:4])}" if c["units"] else ""
            lic = f"; licenses {', '.join(c['licenses'])}" if c["licenses"] else ""
            out.append(f"  {c['role']:24} {c['domain'] or '-':32} {c['company'][:40]}{lic}{units}")
    if s.get("unclear"):
        out.append("")
        out.append("Businesses whose signature names no role: " + ", ".join(c["domain"] or c["company"] for c in s["unclear"]))
    return out


__all__ = ["SIGNATURES", "Target", "plan", "fetch", "report", "summarize", "summary_lines"]
