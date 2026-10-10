"""Sync a vendor's public report portal to disk: the inspection reports it publishes for the association.

A report carries a QR code to its portal (``jason.community.portal_links``). The portal lists every report the vendor has
filed for the customer, and a person finds the older ones, and any the vendor never emailed, only by looking. This reads
the portal and keeps the list and each report's PDF. Under ``data/vendors/<key>/``:

- ``reports.json``: the portals found (the key, the vendor, the customer, whether it is password protected), and every
  report the portals list: its site, address, template, inspector, dates, the file kept, its sha256, and whether the
  library already holds those bytes;
- ``reports/<date>-<site>-<id>.pdf``: each report as the portal prints it, checked before it is kept: the PDF must print
  the site's name. One that does not goes to ``reports/_mismatch``.

Where the portals come from: the QR codes ``jason ingest`` decoded (``data/onboarding/ingest/codes``), the portals an
earlier sync recorded, and any files named with ``--from``. The sync needs no sign-in. A portal that asks for a password
or a phone code is recorded as protected and skipped: jason enters neither. The reports it keeps are not filed in the
library here: ``jason ingest data/vendors/<key>/reports`` classifies and files them.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from jason.community.portal_links import identify
from jason.community.symbols import PortalPlatform
from jason.firenspec.client import Firenspec, FirenspecError, FirenspecProtected, Report
from jason.tasks.vendor_portals import _json_default, _pdf_text, portal_root

REPORTS = "reports.json"
CODES = Path("onboarding") / "ingest" / "codes"


@dataclass
class ReportSyncResult:
    vendor: str
    portals: int = 0
    protected: list[str] = field(default_factory=list)
    reports: int = 0
    downloaded: int = 0
    present: int = 0
    in_library: int = 0
    mismatches: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def summary(self) -> str:
        extra = "".join(f"; {len(x)} {label}" for x, label in ((self.protected, "protected portal(s) skipped"),
                                                              (self.mismatches, "report(s) refused"),
                                                              (self.problems, "problem(s)")) if x)
        return (f"{self.vendor} reports: {self.portals} portal(s), {self.reports} reports, {self.downloaded} new, "
                f"{self.present} on disk, {self.in_library} already in the library{extra}")


def load_reports(data_dir: Path, key: str) -> dict[str, Any]:
    path = portal_root(data_dir, key) / REPORTS
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def discover(data_dir: Path, platform: PortalPlatform, *, files: Iterable[Path] = ()) -> dict[str, list[str]]:
    """The portal keys on ``platform`` that QR codes name, each with where it was read: the codes ingest decoded,
    and the codes read now from ``files`` (PDFs or images)."""
    found: dict[str, list[str]] = {}
    root = Path(data_dir)
    names = {}
    for note in (root / "onboarding" / "ingest" / "text").glob("*.json"):
        try:
            names[note.stem] = str(json.loads(note.read_text(encoding="utf-8")).get("file") or "")
        except (OSError, ValueError):
            continue
    for cache in (root / CODES).glob("*.json"):
        try:
            codes = json.loads(cache.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for code in codes:
            link = identify(code.get("text", "")) if code.get("link") else None
            if link and link.platform is platform:
                found.setdefault(link.key, []).append(names.get(cache.stem) or cache.stem[:12])
    if files:
        from jason.community.qr_read import read_codes

        for path in files:
            for code in read_codes(path):
                link = identify(code.text) if code.link else None
                if link and link.platform is platform:
                    found.setdefault(link.key, []).append(Path(path).name)
    return {k: list(dict.fromkeys(v)) for k, v in found.items()}


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")[:48] or "report"


def file_name(report: Report) -> str:
    return f"{(report.day or date(1970, 1, 1)).isoformat()}-{_slug(report.site)}-{report.url_uuid[:8]}.pdf"


def pdf_matches(pdf: bytes, report: Report) -> bool:
    """The report's own text names its site (page one: "For <site name>")."""
    words = " ".join(_pdf_text(pdf).split()).lower()
    return bool(report.site) and " ".join(report.site.split()).lower() in words


def sync_reports(client: Firenspec, portal: Any, data_dir: Path, *, files: Iterable[Path] = (), full: bool = False,
                 log: Callable[[str], None] | None = None) -> ReportSyncResult:
    from jason.tasks.ingest import library_hashes, sha256_of

    root = portal_root(data_dir, portal.key)
    (root / "reports").mkdir(parents=True, exist_ok=True)
    result = ReportSyncResult(portal.vendor)
    before = load_reports(data_dir, portal.key)
    keys = discover(data_dir, portal.reports, files=files)
    for known in before.get("portals", []):
        keys.setdefault(known["key"], [])
    held = library_hashes(data_dir)
    portals: list[dict[str, Any]] = []
    listed: set[str] = set()
    customers: dict[tuple[str, str], str] = {}        # (vendor, customer) -> the portal that listed it
    rows: dict[str, dict[str, Any]] = {r["urlUuid"]: r for r in before.get("reports", [])}
    for key, origin in keys.items():
        try:
            details = client.details(key)
            listing = client.reports(details)
        except FirenspecProtected as exc:
            result.protected.append(key)
            portals.append({"key": key, "protected": True, "readFrom": origin, "note": str(exc)})
            continue
        except FirenspecError as exc:
            result.problems.append(f"{key}: {exc}")
            portals.append({"key": key, "readFrom": origin, "note": str(exc)})
            continue
        same = customers.setdefault((details.company_id, details.customer_id), key)
        portals.append({"key": key, "protected": False, "readFrom": origin, "company": details.company,
                        "license": details.license, "customer": details.customer, "customerId": details.customer_id,
                        "companyId": details.company_id, **({"sameCustomerAs": same} if same != key else {})})
        if same != key:
            continue                      # one portal a building, one customer: its reports are listed once
        for report in listing:
            listed.add(report.url_uuid)
            row = rows.get(report.url_uuid, {})
            path = root / "reports" / file_name(report)
            if path.is_file() and not full:
                result.present += 1
            else:
                try:
                    pdf = client.report_pdf(report)
                except FirenspecError as exc:
                    result.problems.append(str(exc))
                    continue
                ok = pdf_matches(pdf, report)
                target = path if ok else path.parent / "_mismatch" / path.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(pdf)
                if not ok:
                    result.mismatches.append(f"{report.url_uuid} ({report.day}, {report.site}): the PDF does not print the site's name")
                    continue
                result.downloaded += 1
                if log and result.downloaded % 5 == 0:
                    log(f"{portal.vendor}: {result.downloaded} reports")
            sha = sha256_of(path)
            in_library = held.get(sha, ("", ""))[1]
            result.in_library += bool(in_library)
            rows[report.url_uuid] = {
                "urlUuid": report.url_uuid, "uuid": report.uuid, "kind": report.kind, "template": report.template,
                "site": report.site, "siteId": report.site_id, "address": report.address, "inspector": report.uploader,
                "day": report.day, "completed": report.completed, "pdfUrl": report.pdf_url, "portal": key,
                "file": f"reports/{path.name}", "sha256": sha, "bytes": path.stat().st_size, "libraryPath": in_library,
                "firstSeen": row.get("firstSeen") or datetime.now(timezone.utc).isoformat(timespec="seconds")}
    result.portals = len(keys)
    result.reports = len(listed | set(rows))
    body = {"vendor": portal.vendor, "platform": portal.reports.value, "fetched": datetime.now(timezone.utc),
            "portals": portals, "reports": sorted(rows.values(), key=lambda r: (str(r["day"]), r["urlUuid"]), reverse=True)}
    (root / REPORTS).write_text(json.dumps(body, indent=1, default=_json_default), encoding="utf-8")
    return result


def drive_name(row: dict[str, Any]) -> str:
    """The name a report is filed under in Drive: its date, site, and the portal's template ("2026-03-11 <site> - <template>.pdf")."""
    text = " - ".join(x for x in (f"{row.get('day')} {row.get('site')}".strip(), row.get("template")) if x)
    return re.sub(r"[\\/:*?\"<>|]+", "-", text).strip() + ".pdf"


def plan_filing(drive: Any, community: Any, portal: Any, data_dir: Path, *, known: dict[str, str]) -> tuple[Any, dict[str, bytes]]:
    """Where each kept report goes in Drive by the profile's filing rules, and what Drive already holds (by content).
    Returns the plan (``vendor_files.VendorPlan``) and the bytes to upload. A report loose in the root of My Drive is
    marked "move", and one Drive holds in another folder (an appeal's exhibits, the prior manager's archive) "copy": it
    stays where it is and a copy is filed in the system's folder, so that folder is whole (``vendor_files.plan_loose``)."""
    import hashlib

    from jason.community.symbols import DocumentKind
    from jason.tasks.vendor_files import Attachment, VendorPlan, fiscal_year, in_drive, plan_loose, rule_label, vendors

    filing = community.email_filing()
    if filing is None:
        raise LookupError("the specification sets no email filing (Community.email_filing)")
    sender = next((s for s in vendors(community) if s.name.lower() in portal.vendor.lower()), None)
    if sender is None:
        raise LookupError(f"no sender in the directory for {portal.vendor!r}")
    root = portal_root(data_dir, portal.key)
    plan, blobs, seen = VendorPlan(portal.vendor, "the vendor's report portal"), {}, set()
    for row in sorted(load_reports(data_dir, portal.key).get("reports", []), key=lambda r: str(r["day"])):
        path = root / row["file"]
        if not path.is_file():
            continue
        data = path.read_bytes()
        att = Attachment(portal.vendor, "", f"{row['day']}T00:00:00+00:00", "the vendor's report portal",
                         f"{row['template']}: {row['site']}", drive_name(row), hashlib.sha256(data).hexdigest(),
                         hashlib.md5(data).hexdigest(), len(data), kind=DocumentKind.INSPECTION_REPORT.value,
                         kind_by="portal", url=row["pdfUrl"])
        if att.sha256 in seen:
            continue
        seen.add(att.sha256)
        att.action, att.where = in_drive(drive, att, known)
        if not att.action:
            folder, rule = filing.path_for(sender, DocumentKind.INSPECTION_REPORT, fiscal_year(att.at, community.fiscal_year_end()))
            att.action, att.path, att.rule = "file", folder, rule_label(rule)
            att.why = filing.explain(sender, DocumentKind.INSPECTION_REPORT)
            att.where = "My Drive/" + "/".join(folder) if filing.root == "root" else "/".join(folder)
            blobs[att.sha256] = data
        plan.attachments.append(att)
    plan_loose(drive, community, plan, sender, data_dir)
    return plan, blobs


def report_brief(data_dir: Path, portal: Any) -> dict[str, Any]:
    """What the portal listed, from disk: the portals, the reports newest first, and which the library lacks."""
    body = load_reports(data_dir, portal.key)
    if not body:
        return {"found": False, "note": f"no {portal.key} report portal data; run jason vendors --reports"}
    from jason.tasks.ingest import library_hashes

    held = library_hashes(data_dir)                 # now, not as of the sync: ingest may have filed them since
    rows = [{**r, "libraryPath": held.get(r.get("sha256"), ("", ""))[1]} for r in body.get("reports", [])]
    return {"found": True, "vendor": portal.vendor, "fetched": body.get("fetched"), "portals": body.get("portals", []),
            "reports": [{k: r.get(k) for k in ("day", "site", "template", "inspector", "file", "libraryPath")} for r in rows],
            "missingFromLibrary": [r["file"] for r in rows if not r.get("libraryPath")]}


def report_lines(brief: dict[str, Any]) -> list[str]:
    if not brief.get("found"):
        return [brief["note"]]
    out = [f"{brief['vendor']} report portal: {len(brief['reports'])} reports, {len(brief['missingFromLibrary'])} not in the library "
           f"(fetched {str(brief['fetched'])[:16]})"]
    for p in brief["portals"]:
        out.append(f"  portal {p['key']}: " + ("password protected, skipped" if p.get("protected") else
                                              p.get("note") or f"{p.get('customer', '')}"))
    for r in brief["reports"]:
        out.append(f"  {r['day']} {r['site']} ({r['inspector']}){'' if r['libraryPath'] else '  [not in the library]'}")
    return out


# --- The console's views ----------------------------------------------------------------------------------------------

PLAN_FILE = "filing-plan.json"
PLAN_ACTIONS = ("file", "move", "copy", "in drive", "filed before", "held")


def plan_as_dict(plan: Any, command: str, *, planned: str | None = None) -> dict[str, Any]:
    """A filing plan as the console reads it (``FilingPlan``): counts by action and each row with its destination, the
    rule's reasoning, and for a copy where the original stays."""
    rows = [{"name": a.name, "action": a.action, "destination": a.where, "why": a.why, "kind": a.kind or "unclassified",
             **({"original": a.copy_of} if a.copy_of else {})} for a in plan.attachments]
    counts = {k: sum(1 for r in rows if r["action"] == k) for k in PLAN_ACTIONS}
    return {"vendor": plan.vendor, "counts": counts, "rows": rows, "command": command,
            "planned": planned or datetime.now(timezone.utc).isoformat(timespec="seconds")}


def save_plan(data_dir: Path, key: str, plan: dict[str, Any]) -> Path:
    path = portal_root(data_dir, key) / PLAN_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=1), encoding="utf-8")
    return path


def filing_plan_view(data_dir: Path, key: str) -> dict[str, Any]:
    """The last plan ``jason vendors --reports --drive`` made, read from disk. Nothing here calls Drive: a plan is a job a
    person runs, and this is what it last found."""
    command = f"jason vendors --reports --drive --key {key}"
    path = portal_root(data_dir, key) / PLAN_FILE
    if not path.is_file():
        return {"found": False, "note": f"No filing plan has been made for {key}. Run `{command}`.", "command": command}
    return {"found": True, **json.loads(path.read_text(encoding="utf-8"))}


def _drive_paths(data_dir: Path) -> dict[str, list[str]]:
    """Each content's paths in the Drive sync, by MD5."""
    path = Path(data_dir) / "drive" / "files.json"
    if not path.is_file():
        return {}
    found: dict[str, list[str]] = {}
    for f in json.loads(path.read_text(encoding="utf-8"))["files"]:
        if f.get("md5"):
            found.setdefault(f["md5"], []).append(f["path"])
    return found


def portal_view(data_dir: Path, portal: Any) -> dict[str, Any]:
    """``GET /api/report-portal``: each portal the vendor's codes named, its reports with where each is held now (the
    library and the Drive sync are read when asked, not as of the sync), and what a check held back. Disk only."""
    import hashlib

    from jason.tasks.ingest import library_hashes

    root = portal_root(data_dir, portal.key)
    command = f"jason vendors --reports --key {portal.key}"
    body = load_reports(data_dir, portal.key)
    if not body:
        return {"found": False, "note": f"No report portal has been read for {portal.vendor}. Run `{command}`.", "command": command}
    held_in_library, on_drive = library_hashes(data_dir), _drive_paths(data_dir)
    reports = []
    for r in body.get("reports", []):
        path = root / r["file"]
        md5 = hashlib.md5(path.read_bytes()).hexdigest() if path.is_file() else ""
        holdings = []
        library = held_in_library.get(r.get("sha256"), ("", ""))[1]
        if library:
            holdings.append({"place": "library", "where": library, "identical": True})
        holdings += [{"place": "drive", "where": p, "identical": True} for p in on_drive.get(md5, [])]
        holdings.append({"place": "portal", "where": r["pdfUrl"], "identical": True})
        in_drive = any(h["place"] == "drive" for h in holdings)
        held = "library and drive" if library and in_drive else "library only" if library else "drive only" if in_drive else "not filed"
        reports.append({"urlUuid": r["urlUuid"], "day": r["day"], "site": r["site"], "template": r["template"],
                        "inspector": r["inspector"], "portal": r["portal"], "holdings": holdings, "held": held,
                        "kind": "record of completion" if "record of completion" in (r["template"] or "").lower() else "inspection"})
    refused = sorted(p.name for p in (root / "reports" / "_mismatch").glob("*.pdf")) if (root / "reports" / "_mismatch").is_dir() else []
    portals = []
    for p in body.get("portals", []):
        mine = [r for r in reports if r["portal"] == p["key"]]
        counts = {"listed": len(mine), "onDisk": len(mine), "inLibrary": sum("library" in r["held"] for r in mine),
                  "notFiled": sum(r["held"] == "not filed" for r in mine)}
        portals.append({"key": p["key"], "vendor": portal.vendor, "customer": p.get("customer") or "", "protected": bool(p.get("protected")),
                        **({"sameCustomerAs": p["sameCustomerAs"]} if p.get("sameCustomerAs") else {}),
                        "readFrom": p.get("readFrom", []), "fetched": str(body.get("fetched") or ""), "reports": mine, "counts": counts,
                        **({"note": p["note"]} if p.get("note") else {})})
    return {"found": True, "vendor": portal.vendor, "key": portal.key, "portals": portals, "refused": refused,
            "command": command, "caveats": ["A report is 'not filed' when neither the library nor the Drive sync holds its content as of their last reads.",
                                            "A portal that asks for a password or a phone code is skipped: jason enters neither."]}


__all__ = ["PLAN_FILE", "ReportSyncResult", "discover", "filing_plan_view", "load_reports", "plan_as_dict", "portal_view",
           "report_brief", "report_lines", "save_plan", "sync_reports"]
