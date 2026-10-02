"""PayHOA's report packet runs, catalogued so a document can include one that is already built instead of building it
again: "the treasurer's report from last month" is the run PayHOA made, with its own PDF, not a new run.

PayHOA keeps every packet run (``/saved-reports``): the packet ("Treasurer's Report", "Annual Financial Package",
"Pro Forma Budget"), when it completed, its sections and their dates, its page count, and its PDF with the PDF's SHA-256.
``index`` reads that list (read-only, one call) into ``data/payhoa/report-runs.json``, each run with the month it
reports (``ledger_reports.run_period``) and the library copy that is the same file (by hash). ``find`` picks the run
for a packet and a period (``2026-09``, ``previous-month`` counted from a date, or ``latest``); ``pdf`` downloads that
run's PDF once. jason never starts a packet run: building one is the treasurer's, in PayHOA.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

INDEX = "report-runs.json"


def slug(name: str) -> str:
    """A packet's name as a key: "Treasurer's Report" -> "treasurers-report"."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("'", "")).strip("-")


def packet_name(run_name: str) -> str:
    """The packet a run belongs to, from its name ("Treasurer's Report - 2026-08" -> "Treasurer's Report")."""
    return re.sub(r"\s*[-–]\s*(20\d\d-\d\d|[A-Z][a-z]+ 20\d\d)\s*$", "", run_name or "").strip()


def _path(data_dir: Path) -> Path:
    return Path(data_dir) / "payhoa" / INDEX


def index(client: Any, data_dir: Path) -> list[dict[str, Any]]:
    """Read PayHOA's packet runs into the catalog; read-only in PayHOA. Keeps each run's downloaded PDF path."""
    from jason.tasks.ledger_reports import library_reports, run_period

    before = {r["id"]: r for r in load(data_dir)}
    library = {r["sha256"]: r for r in library_reports(data_dir) if r.get("sha256")}
    runs = []
    for run in client.saved_reports():
        if not run.get("completedAt") or run.get("failedAt"):
            continue
        uploaded = run.get("uploadedFile") or {}
        period, notes = run_period(run)
        sha = uploaded.get("fileHash") or ""
        copy = library.get(sha)
        runs.append({
            "id": run["id"], "name": run.get("name") or "", "packet": packet_name(run.get("name") or ""),
            "packetId": run.get("reportPacketId"), "period": period, "notes": notes,
            "completedAt": run.get("completedAt"), "pages": run.get("totalPages"),
            "sections": [c.get("name") for c in run.get("criteria") or []],
            "fileName": uploaded.get("fileName") or "", "sha256": sha,
            "library": {"id": copy["id"], "path": copy["path"]} if copy else None,
            "pdf": (before.get(run["id"]) or {}).get("pdf", ""),
            "driveId": (before.get(run["id"]) or {}).get("driveId", ""),
        })
    out = _path(data_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"indexedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "runs": runs},
                              indent=1), encoding="utf-8")
    return runs


def load(data_dir: Path) -> list[dict[str, Any]]:
    path = _path(data_dir)
    return json.loads(path.read_text(encoding="utf-8"))["runs"] if path.is_file() else []


def indexed_at(data_dir: Path) -> str:
    path = _path(data_dir)
    return json.loads(path.read_text(encoding="utf-8")).get("indexedAt", "") if path.is_file() else ""


def save(data_dir: Path, runs: list[dict[str, Any]]) -> None:
    path = _path(data_dir)
    body = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    body["runs"] = runs
    path.write_text(json.dumps(body, indent=1), encoding="utf-8")


def resolve_period(period: str, on: date) -> str:
    """``2026-09`` as given; ``previous-month`` the month before ``on``; ``latest`` as ""."""
    if period in ("", "latest"):
        return ""
    if period == "previous-month":
        year, month = (on.year, on.month - 1) if on.month > 1 else (on.year - 1, 12)
        return f"{year}-{month:02d}"
    if period == "this-month":
        return f"{on.year}-{on.month:02d}"
    if not re.fullmatch(r"20\d\d-\d\d", period):
        raise ValueError(f"a period is YYYY-MM, previous-month, this-month, or latest, not {period!r}")
    return period


def find(runs: list[dict[str, Any]], packet: str, period: str = "") -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """The newest run of ``packet`` (a name or its slug) for ``period`` (``YYYY-MM``; "" for the newest of any), and
    the newest run of the packet at all (to name when the period has none)."""
    mine = sorted((r for r in runs if slug(r["packet"]) == slug(packet)), key=lambda r: r["completedAt"], reverse=True)
    newest = mine[0] if mine else None
    if not period:
        return newest, newest
    return next((r for r in mine if r["period"] == period), None), newest


def pdf(client: Any, data_dir: Path, run: dict[str, Any]) -> Path:
    """The run's PDF on disk, downloaded once (a fresh signed link from PayHOA's list)."""
    if run.get("pdf") and Path(run["pdf"]).is_file():
        return Path(run["pdf"])
    url = next(((r.get("uploadedFile") or {}).get("downloadUrl") for r in client.saved_reports() if r.get("id") == run["id"]), None)
    if not url:
        raise ValueError(f"PayHOA gives no PDF for run {run['id']}")
    dest = Path(data_dir) / "payhoa" / "saved-reports" / f"{run['id']}-{re.sub(r'[^A-Za-z0-9._() -]', '_', run['fileName'] or 'report.pdf')}"
    if not dest.is_file():
        client.download_signed_url(url, dest)
    run["pdf"] = str(dest)
    return dest


def month_name(period: str) -> str:
    year, month = (int(x) for x in period.split("-"))
    return f"{date(year, month, 1):%B} {year}"


__all__ = ["find", "index", "indexed_at", "load", "month_name", "packet_name", "pdf", "resolve_period", "save", "slug"]
