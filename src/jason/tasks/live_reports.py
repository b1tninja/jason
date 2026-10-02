"""Reports that stand as documents of their own: run one when its facts may have changed, and every document that
names it (``{REPORT:key}`` in a board item's notes) shows that run, with when it was made and where to refresh it.

A ``Report`` is what documentation would print as "run this command; it reads these; here is the output": the command
a person can run, what it reads, and the function that produces the rows. A reference can carry settings:
``{REPORT:treasurers-report period=previous-month}``. Running it (``refresh``, or ``jason report KEY``) saves a
snapshot under ``data/reports/live``: the rows as Markdown, and beside them when it ran, the command, what it read, and
any error. With ``--doc`` the snapshot is also its own Google Doc on the letterhead, rewritten in place on each
refresh, so the packet links to it and a director opens the latest run.

Two kinds:

- **Run reports** (``occupancy-signals``) read live sources. The board packet does not run them: it shows each one's
  last run and says when that was. A report never run before is run once. ``jason board --packet --refresh-reports``
  refreshes them first; ``jason report --list`` shows each report's age.
- **Catalog reports** (``treasurers-report``, the other PayHOA packets) point at something already built: PayHOA's own
  packet runs, catalogued by ``report_runs``. They resolve from the catalog on disk each time a document is built
  (``offline``), against the document's date (``previous-month`` of the meeting), and never build anything. A refresh
  re-reads the catalog from PayHOA first (``prepare``); ``--doc`` files the run's own PDF in Drive for the board.

A report that cannot run (no network, a login needed) keeps its last good rows and records the error. Reports for the
packet never print names, addresses, or emails: an open-session item is read aloud.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

TOKEN = re.compile(r"\{REPORT:(?P<key>[a-z0-9-]+)(?P<args>(?:\s+[a-z][a-z-]*=[^\s{}]+)*)\s*\}")
STALE_DAYS = 7          # a snapshot older than this is flagged in a document that embeds it


@dataclass(frozen=True)
class Report:
    key: str
    title: str
    command: str                                   # how a person runs it themselves
    reads: str                                     # what it reads, in a phrase
    run: Callable[..., list[str]]                  # (data_dir, community, params, context) -> Markdown lines
    offline: bool = False                          # reads disk only: a document resolves it each time it is built
    prepare: Callable[[Path, Any], Any] | None = None   # the network step a refresh does first (re-read a catalog)
    attach: Callable[..., Any] | None = None       # with --doc: file what it points at (a PDF) for the board
    caveat: str = "A lead to confirm, not a finding."   # how to read it: jason's own reading, or the record itself


def parse_args(text: str) -> dict[str, str]:
    return dict(pair.split("=", 1) for pair in (text or "").split())


def stem(key: str, params: dict[str, str] | None = None) -> str:
    """A snapshot's file name: the key, then its settings ("treasurers-report--period-previous-month")."""
    return key + "".join(f"--{k}-{re.sub(r'[^a-z0-9-]', '', v.lower())}" for k, v in sorted((params or {}).items()))


def command_for(report: Report, params: dict[str, str] | None = None) -> str:
    return report.command + "".join(f" {k}={v}" for k, v in sorted((params or {}).items()))


@dataclass
class Snapshot:
    key: str
    title: str
    command: str
    reads: str
    params: dict[str, str] = field(default_factory=dict)
    ran_at: str = ""                               # ISO time of the last good run
    tried_at: str = ""                             # ISO time of the last attempt
    error: str = ""                                # why the last attempt failed ("" when it ran)
    doc_id: str = ""                               # its Google Doc, when published
    rows: list[str] = field(default_factory=list)
    caveat: str = "A lead to confirm, not a finding."

    @property
    def url(self) -> str:
        return f"https://docs.google.com/document/d/{self.doc_id}/edit" if self.doc_id else ""

    def age_days(self, now: datetime | None = None) -> float | None:
        if not self.ran_at:
            return None
        return ((now or datetime.now()) - datetime.fromisoformat(self.ran_at)).total_seconds() / 86400

    def heading(self, *, titled: bool = True) -> list[str]:
        """Where the facts came from and when: the command, its inputs, the run, and the Doc."""
        when = datetime.fromisoformat(self.ran_at) if self.ran_at else None
        made = f"as of {when:%B} {when.day}, {when.year} {when:%H:%M}" if when else "not yet run"
        doc = f"; [the report]({self.url})" if self.doc_id and titled else ""
        lead = f"**{self.title}**, {made}" if titled else made[0].upper() + made[1:]
        return [f"{lead} (`{self.command}`; reads {self.reads}{doc}).{' ' + self.caveat if self.caveat else ''}", ""]


def _occupancy_signals(data_dir: Path, community: Any, params: dict[str, str], context: dict[str, Any]) -> list[str]:
    """The units whose evidence and occupancy tag disagree, or whose tag may describe a former owner: every unit the
    signals flag (``owner_send.occupancy_signals``), with the evidence as words, never an owner's name or address."""
    from jason.agent import Jason
    from jason.community.spec import spec_module
    from jason.tasks.owner_send import live_signals

    forms = spec_module("forms")
    with Jason(interactive=False) as agent:
        _, signals, _ = live_signals(agent.payhoa(), agent.org_id, community, forms, data_dir)
    readings = {r: sum(1 for s in signals if s.reading == r) for r in ("owner-occupied", "not owner-occupied", "unclear")}
    flagged = [s for s in signals if s.finding]
    out = [f"{len(signals)} units read: {readings['owner-occupied']} owner-occupied, "
           f"{readings['not owner-occupied']} not owner-occupied, {readings['unclear']} unclear. "
           f"{len(flagged)} to confirm:", ""]
    # a list, not a table: the Doc writer sets list items in the house style and a table row as plain text
    exemption = {True: "claimed", False: "none", None: "not known"}
    for s in flagged:
        out.append(f"- **{s.unit.title()}** (tag: {s.tag or 'none'}): owners' mail {s.mail}; county homeowners' "
                   f"exemption {exemption[s.exemption]}; reads {s.reading}. To confirm: {s.finding}.")
    if not flagged:
        out.append("- None.")
    return out


def _index_runs(data_dir: Path, community: Any) -> None:
    from jason.agent import Jason
    from jason.tasks.report_runs import index

    with Jason(interactive=False) as agent:
        index(agent.payhoa(), data_dir)


def _packet_run(packet: str) -> Callable[..., list[str]]:
    """A PayHOA packet run as a document includes it: the run for the period, already built, with its PDF."""
    def rows(data_dir: Path, community: Any, params: dict[str, str], context: dict[str, Any]) -> list[str]:
        from jason.tasks.report_runs import find, indexed_at, load, month_name, resolve_period

        runs = load(data_dir)
        if not runs:
            return [f"_No PayHOA packet runs are catalogued yet: `jason report {params.get('_key', '')}` reads them._"]
        on = context.get("on") or date.today()
        period = resolve_period(params.get("period", "latest"), on)
        run, newest = find(runs, packet, period)
        catalogued = indexed_at(data_dir)[:10]
        if run is None:
            last = (f"the newest is {month_name(newest['period'])} (run {newest['completedAt'][:10]})" if newest
                    else "none is catalogued")
            return [f"PayHOA has no {packet} run for {month_name(period) if period else 'any month'} in the catalog of "
                    f"{catalogued}; {last}. jason does not build packets: the treasurer runs it in PayHOA (Reports, "
                    "Report Packets), then `jason report` catalogs it."]
        out = [f"{run['packet']}, {month_name(run['period'])}: PayHOA's packet run of {run['completedAt'][:16]}, "
               f"{run['pages'] or '?'} pages: {'; '.join(s for s in run['sections'] if s)}."]
        if run.get("driveId"):
            out.append(f"The board's copy: [{run['fileName']}](https://drive.google.com/file/d/{run['driveId']}/view) "
                       "(PayHOA's own PDF, unchanged).")
        elif run.get("library"):
            out.append(f"The library holds the same file (by its SHA-256): {run['library']['path']}.")
        else:
            out.append("Not yet filed for the board: `jason report` with `--doc --yes` files PayHOA's PDF in "
                       "My Drive/Meetings/Reports.")
        out += [f"Note: {n}." for n in run.get("notes") or []]
        return out

    return rows


def _attach_packet_run(packet: str) -> Callable[..., None]:
    def attach(client: Any, drive: Any, data_dir: Path, params: dict[str, str], context: dict[str, Any],
               folder: str) -> None:
        from jason.tasks.report_runs import find, load, pdf, resolve_period, save

        runs = load(data_dir)
        run, _ = find(runs, packet, resolve_period(params.get("period", "latest"), context.get("on") or date.today()))
        if run is None or run.get("driveId"):
            return
        path = pdf(client, data_dir, run)
        run["driveId"] = drive.upload_bytes(run["fileName"] or path.name, path.read_bytes(), mime_type="application/pdf",
                                            parent_id=folder, description=f"PayHOA packet run {run['id']} "
                                            f"({run['completedAt'][:10]}), SHA-256 {run['sha256']}",
                                            app_properties={"jason_payhoa_run": str(run["id"])})
        save(data_dir, runs)

    return attach


def _packet_report(key: str, packet: str) -> Report:
    return Report(key, packet, f"jason report {key}",
                  f"the catalog of PayHOA's own packet runs (read with `jason report {key}`)",
                  _packet_run(packet), offline=True, prepare=_index_runs, attach=_attach_packet_run(packet),
                  caveat="PayHOA's own report as the treasurer ran it; jason finds it and files it, and changes nothing.")


REPORTS: dict[str, Report] = {r.key: r for r in (
    Report("occupancy-signals", "Occupancy signals",
           "jason report occupancy-signals",
           "PayHOA's tags and owners' mailing addresses (live), the county's secured roll (homeowners' exemption, tax "
           "bill address), and the recorded deeds",
           _occupancy_signals),
    _packet_report("treasurers-report", "Treasurer's Report"),
    _packet_report("annual-financial-package", "Annual Financial Package"),
    _packet_report("pro-forma-budget", "Pro Forma Budget"),
)}


def store(data_dir: Path) -> Path:
    return Path(data_dir) / "reports" / "live"


def snapshot(key: str, data_dir: Path, params: dict[str, str] | None = None) -> Snapshot | None:
    """The last saved run of ``key`` with ``params``, or None."""
    path = store(data_dir) / f"{stem(key, params)}.json"
    if not path.is_file():
        return None
    return Snapshot(**json.loads(path.read_text(encoding="utf-8")))


def _save(snap: Snapshot, data_dir: Path) -> None:
    folder = store(data_dir)
    folder.mkdir(parents=True, exist_ok=True)
    name = stem(snap.key, snap.params)
    (folder / f"{name}.json").write_text(json.dumps(asdict(snap), indent=1), encoding="utf-8")
    (folder / f"{name}.md").write_text("\n".join(markdown(snap)) + "\n", encoding="utf-8")


def markdown(snap: Snapshot) -> list[str]:
    """The report as a document of its own (the Markdown file, and its Doc)."""
    out = [f"# {snap.title}", ""] + snap.heading(titled=False)
    if snap.error:
        out += [f"_The last attempt ({snap.tried_at[:16].replace('T', ' ')}) could not run: {snap.error}. The rows "
                "below are from the last good run._", ""]
    return out + (snap.rows or ["_(no rows yet)_"])


def _run(report: Report, data_dir: Path, community: Any, params: dict[str, str], context: dict[str, Any],
         now: datetime, *, prepare: bool) -> Snapshot:
    snap = snapshot(report.key, data_dir, params) or Snapshot(report.key, report.title, command_for(report, params),
                                                               report.reads, dict(params))
    snap.title, snap.command, snap.reads, snap.caveat = report.title, command_for(report, params), report.reads, report.caveat
    snap.tried_at = now.isoformat(timespec="seconds")
    try:
        if prepare and report.prepare is not None:
            report.prepare(Path(data_dir), community)
        snap.rows = report.run(Path(data_dir), community, {**params, "_key": report.key}, context)
        snap.ran_at, snap.error = snap.tried_at, ""
    except Exception as exc:  # the document keeps its last facts and says they could not be refreshed
        snap.error = str(exc)[:300]
    _save(snap, data_dir)
    return snap


def refresh(key: str, data_dir: Path, community: Any, params: dict[str, str] | None = None, *,
            context: dict[str, Any] | None = None, now: datetime | None = None) -> Snapshot:
    """Run ``key`` now (re-reading its catalog first, for a catalog report) and save it; a failed run keeps the last
    good rows and records why."""
    return _run(REPORTS[key], data_dir, community, dict(params or {}), context or {}, now or datetime.now(), prepare=True)


def publish(key: str, data_dir: Path, drive: Any, *, folder_id: str, letterhead_id: str, footer: str,
            params: dict[str, str] | None = None) -> Snapshot:
    """The snapshot as its own Google Doc on the letterhead, rewritten in place on each refresh (private, like the
    packet)."""
    from jason.tasks.letters import markdown_doc

    snap = snapshot(key, data_dir, params)
    if snap is None:
        raise ValueError(f"{key} has not been run: jason report {key}")
    made = markdown_doc(drive, drive.docs(), markdown(snap), name=f"Report - {snap.title} (confidential)",
                        folder_id=folder_id, letterhead_id=letterhead_id, footer=footer, doc_id=snap.doc_id,
                        continuation=f"{snap.title} · Confidential: for the directors and counsel")
    snap.doc_id = made["id"]
    _save(snap, data_dir)
    return snap


def references(text: str) -> list[tuple[str, dict[str, str]]]:
    """Each report ``text`` names, with its settings, once."""
    seen: dict[str, tuple[str, dict[str, str]]] = {}
    for m in TOKEN.finditer(text or ""):
        params = parse_args(m.group("args"))
        seen.setdefault(stem(m.group("key"), params), (m.group("key"), params))
    return list(seen.values())


def keys_in(text: str) -> list[str]:
    return list(dict.fromkeys(k for k, _ in references(text)))


def embed(key: str, data_dir: Path, community: Any, params: dict[str, str] | None = None, *,
          context: dict[str, Any] | None = None, now: datetime | None = None) -> list[str]:
    """One report as a document that names it shows it. A catalog report resolves now from disk; a run report shows
    its snapshot (run once if it never has been), with a word when it is stale or its last refresh failed."""
    report = REPORTS.get(key)
    if report is None:
        return [f"_(no report named {key}: the reports are {', '.join(sorted(REPORTS))})_"]
    params = dict(params or {})
    now = now or datetime.now()
    snap = snapshot(key, data_dir, params)
    if report.offline or snap is None:
        snap = _run(report, data_dir, community, params, context or {}, now, prepare=snap is None and not report.offline)
    out = snap.heading()
    age = snap.age_days(now)
    if not report.offline and age is not None and age > STALE_DAYS:
        out += [f"_This run is {int(age)} days old: refresh it with `{snap.command}`._", ""]
    if snap.error:
        out += [f"_The last refresh could not run ({snap.error}); these rows are from the run above._", ""]
    return out + (snap.rows or [f"_(could not run: {snap.error})_" if snap.error else "_(no rows)_"])


def expand(text: str, data_dir: Path, community: Any, *, context: dict[str, Any] | None = None,
           now: datetime | None = None) -> list[str]:
    """``text`` as Markdown lines, each ``{REPORT:key ...}`` replaced by that report. Text around a token stays as the
    board wrote it: the commentary. ``context["on"]`` is the document's date (a meeting), for relative periods."""
    out: list[str] = []
    at = 0
    for m in TOKEN.finditer(text or ""):
        before = text[at:m.start()].strip()
        if before:
            out += [before, ""]
        out += embed(m.group("key"), data_dir, community, parse_args(m.group("args")), context=context, now=now) + [""]
        at = m.end()
    rest = (text or "")[at:].strip()
    if rest:
        out.append(rest)
    return out


__all__ = ["REPORTS", "Report", "STALE_DAYS", "Snapshot", "TOKEN", "command_for", "embed", "expand", "keys_in",
           "markdown", "parse_args", "publish", "references", "refresh", "snapshot", "stem", "store"]
