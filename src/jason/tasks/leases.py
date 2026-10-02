"""The leases the Association holds, read for two things only: who lives in a rented unit now (so they are listed as
the unit's other contacts, and a tenant who has left is not), and whether an owner works with a property manager
(the manager an other contact; a Property Manager record only at the owner's ask).

Leases come from the Drive folders where owners uploaded them (the 2024 Resident Registration Form's "Copy of Lease
Agreement" answers, and My Drive/Leases) and the PayHOA library's "Lease Agreements". Each is read on this machine by
the local model (``local_ai``; the GPU lock held, the model unloaded after), for the unit, the term, the landlord, an
agent or property manager, and the tenants' names; nothing else is kept. A rental application or screening report is
never opened: its name says what it is, and it is skipped.

A reading is evidence: ``proposals`` sets it beside PayHOA's owners and other contacts and says what a person might
change. Nothing is written to PayHOA here.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

LEASE_FOLDERS = ("Copy of Lease Agreement (File responses)", "My Drive/Leases")
SKIP = re.compile(r"application|screening|credit|background|criminal|transunion|smartmove", re.I)
MODEL = "qwen3.5:9b"
FIELDS = {"unit_address": "the rented property's street address",
          "start": "the lease's start date, YYYY-MM-DD, or empty",
          "end": "the lease's end date, YYYY-MM-DD, or empty for month to month",
          "month_to_month": "true when the lease continues month to month after its term (or has no end)",
          "landlord": "the landlord or owner named in the lease (a person or company)",
          "manager": "the property manager or landlord's agent, if one is named (a company or a person), else empty",
          "manager_company": "the property management company's name, if any, else empty",
          "tenants": "every tenant's full name"}


@dataclass
class Lease:
    file: str
    source: str
    unit_address: str = ""
    start: str = ""
    end: str = ""
    month_to_month: bool = False
    landlord: str = ""
    manager: str = ""
    manager_company: str = ""
    tenants: list[str] = field(default_factory=list)
    error: str = ""

    def current(self, today: date) -> bool | None:
        """True while the term runs (its end on or after today); False when it ended; None when the reading gives no
        end, or the term ended and the lease would go on month to month: whether the tenant stayed is not in the lease,
        so a person (or the owner's answer this year) says."""
        try:
            end = date.fromisoformat(self.end[:10]) if self.end else None
        except ValueError:
            return None
        if end is None:
            return None
        if end >= today:
            return True
        return None if self.month_to_month else False


def lease_files(drive_files: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """The Drive catalog's leases: PDFs and images in the lease folders, not applications or screening reports."""
    out = []
    for f in drive_files:
        path, name = f.get("path") or "", f.get("name") or ""
        if any(folder in path for folder in LEASE_FOLDERS) and not SKIP.search(name) and \
                (name.lower().endswith((".pdf", ".png", ".jpg", ".jpeg")) or "pdf" in (f.get("mimeType") or "")):
            out.append(f)
    return out


def _pages(path: Path, *, first: int = 2, last: int = 1, dpi: int = 120) -> list[str]:
    """The first and last pages as PNG (base64): the parties and term are near the start, the agent's signature block
    near the end."""
    import pymupdf

    if path.suffix.lower() in (".png", ".jpg", ".jpeg"):
        return [base64.b64encode(path.read_bytes()).decode("ascii")]
    with pymupdf.open(path) as doc:
        wanted = sorted(set(list(range(min(first, doc.page_count))) + list(range(max(0, doc.page_count - last), doc.page_count))))
        return [base64.b64encode(doc[i].get_pixmap(dpi=dpi).tobytes("png")).decode("ascii") for i in wanted]


def read(path: Path, *, model: str = MODEL, source: str = "") -> Lease:
    """One lease read by the local model into ``Lease`` (the fields above, nothing more)."""
    from jason.community.ollama_extractor import OLLAMA_URL, _post

    lease = Lease(file=path.name, source=source)
    try:
        images = _pages(path)
    except Exception as exc:                       # an unreadable file is reported, not guessed
        lease.error = f"unreadable: {exc}"
        return lease
    schema = {"type": "object", "required": list(FIELDS),
              "properties": {k: ({"type": "array", "items": {"type": "string"}} if k == "tenants" else
                                 {"type": "boolean"} if k == "month_to_month" else {"type": "string"})
                             for k in FIELDS}}
    prompt = ("These are pages of a residential lease. Read only what the lease states; leave a field empty when the "
              "pages do not say it. Fields:\n" + "\n".join(f"- {k}: {v}" for k, v in FIELDS.items()))
    try:
        answer = _post(f"{OLLAMA_URL}/api/chat", {"model": model, "stream": False, "think": False, "format": schema,
                                                  "options": {"temperature": 0},
                                                  "messages": [{"role": "user", "content": prompt, "images": images}]}, 300)
        got = json.loads((answer.get("message") or {}).get("content") or "{}")
    except (OSError, ValueError) as exc:
        lease.error = f"model: {exc}"
        return lease
    for k in FIELDS:
        if k in got:
            setattr(lease, k, got[k] if k in ("tenants", "month_to_month") else str(got[k] or "").strip())
    lease.tenants = [t.strip() for t in lease.tenants if t and t.strip()]
    lease.start, lease.end = _iso(lease.start), _iso(lease.end)
    # the unit from the lease's own words when it prints a community address: a model can take the manager's office
    # address for the premises
    unit = community_address(path)
    if unit:
        lease.unit_address = unit
    return lease


def _iso(text: str) -> str:
    """A date as YYYY-MM-DD from the forms leases print it in (11/16/2025, November 16, 2025, 2025-11-16)."""
    from datetime import datetime

    text = (text or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text


def community_address(path: Path) -> str:
    """The community unit address a lease's text layer (or its file name) prints most, if any."""
    from collections import Counter

    import pymupdf

    from jason.community.base import read_unit_address
    from jason.community.symbols import Street

    text = path.name
    if path.suffix.lower() == ".pdf":
        try:
            with pymupdf.open(path) as doc:
                text += "\n" + "\n".join(p.get_text() for p in doc)
        except Exception:
            pass
    streets = "|".join(re.escape(s.value.split()[0]) for s in Street)
    found = Counter()
    for m in re.finditer(rf"\b(\d{{4}})\s+({streets})\w*\s+(?:dr|drive|walk|ln|lane)\b", text, re.I):
        number, street = read_unit_address(f"{m.group(1)} {m.group(2)} {m.group(0).split()[-1]}")
        if number and street:
            found[f"{number} {street.value}"] += 1
    return found.most_common(1)[0][0] if found else ""


def _words(name: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", (name or "").casefold()) if len(w) > 1}


@dataclass
class Proposal:
    unit: str
    kind: str          # "add other contact", "other contact may have left", "property managed", "manager contact"
    who: str
    why: str


def proposals(leases: list[Lease], units: list[dict[str, Any]], contacts: dict[int, list[dict[str, Any]]],
              owners: dict[int, list[str]], today: date, deeds: dict[str, date] | None = None) -> list[Proposal]:
    """What the leases suggest beside PayHOA: ``units`` PayHOA's units, ``contacts`` each unit's other contacts,
    ``owners`` each unit's owner names. A tenant on a current lease who is no other contact is to be added; an other
    contact named only on an ended lease, with a newer lease for the unit naming others, may have left; a manager or
    agent named on a current lease is the unit's manager contact, and its owner is asked what the manager may receive."""
    from jason.community.base import read_unit_address

    by_address = {read_unit_address(str(u.get("label") or u.get("title") or "")): u for u in units}
    out: list[Proposal] = []
    per_unit: dict[int, list[Lease]] = {}
    for lease in leases:
        unit = by_address.get(read_unit_address(lease.unit_address))
        if unit is not None:
            per_unit.setdefault(int(unit["id"]), []).append(lease)
    for unit_id, found in per_unit.items():
        unit = next(u for u in units if int(u["id"]) == unit_id)
        label = str(unit.get("label") or unit.get("title"))
        found.sort(key=lambda l: l.start or l.end or "")
        listed = contacts.get(unit_id, [])
        latest = found[-1]
        current = latest.current(today)
        deed = (deeds or {}).get(label.upper())
        sold = (f"; the unit changed hands {deed.isoformat()}, after this lease began"
                if deed and latest.start and deed.isoformat() > latest.start else "")
        term = f"{latest.start or '?'} to {latest.end or 'no end given'}"
        for tenant in latest.tenants:
            if any(len(_words(tenant) & _words(c.get("name"))) >= 2 for c in listed):
                continue                                       # already an other contact
            if any(len(_words(tenant) & _words(o)) >= 2 for o in owners.get(unit_id, [])):
                continue                                       # an owner named as tenant: not an other contact
            if current and not sold:
                out.append(Proposal(label, "add other contact", tenant,
                                    f"a tenant on the lease of {term} ({latest.file}), not among the unit's other contacts"))
            elif current is None or (current and sold):
                out.append(Proposal(label, "ask: tenant may remain", tenant,
                                    f"the lease of {term} ({latest.file}) "
                                    + ("ended and goes month to month" if current is None else "runs")
                                    + f"{sold}: confirm with the owner before listing"))
        for c in listed:
            older = [l for l in found[:-1] if any(len(_words(t) & _words(c.get("name"))) >= 2 for t in l.tenants)]
            on_latest = any(len(_words(t) & _words(c.get("name"))) >= 2 for t in latest.tenants)
            if older and not on_latest:
                out.append(Proposal(label, "other contact may have left", str(c.get("name")),
                                    f"named on an earlier lease ({older[-1].file}); the latest ({latest.file}) names "
                                    "other tenants: a person confirms before removing"))
        if latest.manager or latest.manager_company:
            person, company = latest.manager.strip(), latest.manager_company.strip()
            who = f"{person} ({company})" if person and company and company not in person else (person or company)
            sure = current and not sold
            if not any(_words(company or person) & _words(c.get("name")) for c in listed):
                out.append(Proposal(label, "manager contact" if sure else "ask: manager contact", who,
                                    f"the agent or property manager on the lease of {term} ({latest.file}){sold}; "
                                    "listed as an other contact: 'Name (Company), property manager'"
                                    + ("" if sure else ": confirm with the owner first")))
            for owner in owners.get(unit_id, []):
                # a lease names the manager; only the owner can ask for the manager to get notices or be their
                # contact (the owner-information form's property manager section), so this is a question for them
                out.append(Proposal(label, "ask: manager's role", owner,
                                    f"the lease of {term} names a property manager ({who}){sold}: the owner's form "
                                    "says whether the manager gets copies of notices or is their contact"))
    return out


def save(leases: list[Lease], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(l) for l in leases], indent=1), encoding="utf-8")
    return path


__all__ = ["LEASE_FOLDERS", "Lease", "Proposal", "lease_files", "proposals", "read", "save"]
