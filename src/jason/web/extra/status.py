"""The administrator's Status screen (``GET /api/status``; docs/console/screens/status.md): which sources jason keeps on
disk and when each was last read, who signed in, where setup's five gates stand, and what failed. Read-only.

Answers only one of jason's admins, signed in as themselves (``jason.web.access.signed_in``: 401 with no sign-in, 403
for anyone else and while an admin views the console as someone else), and never the owner view
(``owner_view.OWNER_SOURCES`` does not list it, so the owner view's guard refuses it).

It reads disk only: no Google, PayHOA, Keeper, or network call, and nothing is written (a SQLite store is opened
read-only, and one that is not there is "never read", not created).

- **Sources** are ``SOURCES``, one row a store jason keeps from an outside system: where its own last-read stamp lives
  (a ``syncedAt``/``fetchedAt`` in its JSON, a ``synced_at`` column, a store's ``sync_runs``), the command that
  refreshes it, and the queued jobs that run that command. ``lastRead`` is that stamp, never a file's modified time and
  never a guess.
- **Standing** is a word only where the records say it: ``failed`` (the newest queued job that runs its command
  failed after its last read), ``not signed in`` (that failure, or a live refresh of its system since its last read,
  failed at the sign-in; or a Google source with no Google token on disk), ``never read`` (no stamp in its store). ``current`` and ``stale`` need a threshold the source declares
  (``Source.stale_after_days`` with ``stale_source``, where it is written); a source that declares none shows its age
  and no word. No threshold is invented here: each row in ``SOURCES`` takes its integration's ``stale_after``
  (``jason.integrations.registry``, the defaults of docs/integrations-design.md), and ``stale_source`` names it.
- **Sign-ins** are the newest lines of ``web/sign-ins.jsonl``: who, when, what happened; the account's email and Google
  ``sub`` are left out and a refusal's words are masked (``jason.approvals.audit.mask``).
- **Gates** are onboarding's five stage gates (``jason.tasks.onboarding_session.status_dict``), as setup shows them.
- **Failures** are the newest failed jobs in the queue (``data/jobs.db``), failed live refreshes
  (``evidence/refreshes.jsonl``), and store sync runs that logged errors (``sync_runs.errors_json``), each masked.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

Args = dict[str, str]

FAILED = "failed"
NOT_SIGNED_IN = "not signed in"
NEVER_READ = "never read"
CURRENT = "current"
STALE = "stale"

SIGN_IN_LIMIT = 20
FAILURE_LIMIT = 20
JOB_SCAN = 500                          # the newest jobs read to find each source's last run
HEAD_BYTES = 4096                       # a JSON store's stamp is its first key: read the head before the whole file
GOOGLE_LOGIN = "{fix} --interactive"    # Google signs in at a terminal, in a browser a person opens
KEEPER_LOGIN = "jason login"
SETUP_SCREEN = "#/onboarding"
JOBS_COMMAND = "jason jobs"

REFUSED = ("Status is the administrator's: it opens for one of jason's admins (data/access/admins.json), signed in as "
           "themselves.")
ACTING = "Viewing as {who} (admin view): Status is the administrator's own. Go back to yourself to open it."
CAVEATS = (
    "Read from disk only: each last read is the store's own stamp. Nothing here calls Google, PayHOA, Keeper, or the "
    "network, and nothing here retries or writes.",
    "A source says current or stale only by a threshold it declares (its integration's default stale-after, a "
    "default the board or the administrator may change); without one it shows its age and no word.",
    "Sources sign in at a terminal (jason login, or the command with --interactive); the browser never holds a "
    "credential.",
)

_SIGN_IN_WORDS = re.compile(r"AuthRequired|not signed in|jason login|--interactive|sign in again", re.IGNORECASE)


# --- reading a store's own stamp ---------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Read:
    """What a store says of its last read: the stamp (ISO, or "" when it has none), and errors a sync run logged."""

    at: str = ""
    errors: tuple[str, ...] = ()
    error_at: str = ""


Reader = Callable[[Path], Read]


def _connect_ro(path: Path) -> sqlite3.Connection | None:
    """A read-only connection, or None when the store is not there (never created here)."""
    if not path.is_file():
        return None
    try:
        return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error:
        return None


def json_stamp(rel: str, key: str) -> Reader:
    """The ``key`` stamp of a JSON store under the data folder (its head first: the stamp is written first)."""
    pattern = re.compile(r'"' + re.escape(key) + r'"\s*:\s*"([^"]*)"')

    def read(root: Path) -> Read:
        path = Path(root) / rel
        if not path.is_file():
            return Read()
        try:
            with path.open("rb") as fh:
                head = fh.read(HEAD_BYTES).decode("utf-8", errors="replace")
            hit = pattern.search(head)
            if hit:
                return Read(hit.group(1))
            got = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return Read()
        return Read(str(got.get(key) or "") if isinstance(got, dict) else "")
    return read


def newest_json_stamp(pattern: str, key: str) -> Reader:
    """The newest ``key`` stamp among the JSON stores matching ``pattern`` (one a year, say)."""
    def read(root: Path) -> Read:
        stamps = [json_stamp(str(p.relative_to(root)), key)(root).at for p in sorted(Path(root).glob(pattern))]
        return Read(max((s for s in stamps if s), default=""))
    return read


def column_stamp(rel: str, column: str, tables: tuple[str, ...] = ()) -> Reader:
    """The newest ``column`` value across a SQLite store's tables that have it (``tables`` narrows them)."""
    def read(root: Path) -> Read:
        conn = _connect_ro(Path(root) / rel)
        if conn is None:
            return Read()
        try:
            names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
            stamps = []
            for t in names:
                if tables and t not in tables:
                    continue
                cols = {r[1] for r in conn.execute(f'PRAGMA table_info("{t}")')}
                if column in cols:
                    stamps.append(conn.execute(f'SELECT MAX("{column}") FROM "{t}"').fetchone()[0])
            return Read(max((str(s) for s in stamps if s), default=""))
        except sqlite3.Error:
            return Read()
        finally:
            conn.close()
    return read


def sync_runs(path_of: Callable[[Path], Path], column: str = "") -> Reader:
    """A store's ``sync_runs``: the newest finished run is the last read; the newest run's logged errors are its
    failures (a run with errors still read what it could). With no finished run, the newest ``column`` stamp in its
    rows (a store filled before it kept runs)."""
    def read(root: Path) -> Read:
        path = path_of(Path(root))
        conn = _connect_ro(path)
        if conn is None:
            return Read()
        try:
            conn.row_factory = sqlite3.Row
            done = conn.execute("SELECT MAX(finished_at) FROM sync_runs WHERE finished_at IS NOT NULL "
                                "AND finished_at != ''").fetchone()[0]
            last = conn.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
        except sqlite3.Error:
            done, last = None, None
        finally:
            conn.close()
        if not done and column:
            done = column_stamp(str(path.resolve()), column)(Path(root)).at   # an absolute path joins as itself
        errors: tuple[str, ...] = ()
        error_at = ""
        if last is not None:
            try:
                raw = json.loads(last["errors_json"] or "[]")
            except (ValueError, IndexError, KeyError):
                raw = []
            errors = tuple(str(e) for e in raw) if isinstance(raw, list) else ()
            error_at = str(last["finished_at"] or last["started_at"] or "") if errors else ""
        return Read(str(done or ""), errors, error_at)
    return read


SMUD_STAMP = "last_synced_at"           # smud's accounts table, for a store filled before it kept runs


def _smud_db(root: Path, settings: Any = None) -> Path:
    path = getattr(settings, "smud_db", None)
    return Path(path) if path else Path(root) / "smud.db"


# --- the sources -------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Source:
    """One store jason keeps from an outside system: where its stamp is, the command that refreshes it, the job
    command lines that run that command (each a tuple of words the job's argv starts with or holds), how it signs in
    (``google``: a Google token on disk; ``keeper``: a Keeper record, signed in with ``jason login``; "" none), and the
    threshold past which it is stale, only when the source declares one (and where: ``stale_source``)."""

    key: str
    name: str
    what: str
    read: Reader
    fix: str
    jobs: tuple[tuple[str, ...], ...] = ()
    system: str = ""                       # the word evidence/refreshes.jsonl names it by
    sign_in: str = ""
    stale_after_days: float | None = None
    stale_source: str = ""
    store: str = ""                        # where its stamp is, for the screen
    settings_path: bool = False            # the store's path comes from the settings (SMUD)


def _sources() -> tuple[Source, ...]:
    return (
        Source("payhoa-catalog", "PayHOA catalog", "units, people, requests, violations, and documents",
               column_stamp("payhoa.db", "synced_at"), "jason sync-catalog", (("sync-catalog",),), "PayHOA", "keeper",
               store="payhoa.db (synced_at)"),
        Source("payhoa-transactions", "PayHOA transactions", "payments and their attached invoices",
               json_stamp("payhoa/transactions.json", "syncedAt"), "jason invoices --fetch", (("invoices", "--fetch"),),
               "PayHOA", "keeper", store="payhoa/transactions.json (syncedAt)"),
        Source("payhoa-ledger", "PayHOA general ledger", "the books, month by month",
               column_stamp("payhoa/ledger.db", "fetched_at", ("months",)), "jason books --sync",
               (("books", "--sync"),), "PayHOA", "keeper", store="payhoa/ledger.db (months.fetched_at)"),
        Source("payhoa-budget", "PayHOA budget", "budget against actual, and the bank balances",
               newest_json_stamp("payhoa/finance-*.json", "syncedAt"), "jason budget", (("budget",),), "PayHOA",
               "keeper", store="payhoa/finance-YEAR.json (syncedAt)"),
        Source("payhoa-reconciliations", "PayHOA reconciliations", "bank reconciliations and their reports",
               json_stamp("payhoa/reconciliations.json", "fetchedAt"), "jason reconcile --fetch",
               (("reconcile", "--fetch"),), "PayHOA", "keeper", store="payhoa/reconciliations.json (fetchedAt)"),
        Source("payhoa-reports", "PayHOA saved reports", "saved report runs and month-end balance sheets",
               json_stamp("payhoa/saved-reports.json", "fetchedAt"), "jason ledger --fetch", (("ledger", "--fetch"),),
               "PayHOA", "keeper", store="payhoa/saved-reports.json (fetchedAt)"),
        Source("payhoa-notices", "PayHOA meeting notices", "the notices PayHOA sent",
               json_stamp("payhoa/communications.json", "syncedAt"), "jason meetings --sync",
               (("meetings", "--sync"),), "PayHOA", "keeper", store="payhoa/communications.json (syncedAt)"),
        Source("utility-payments", "Utility payments", "utility payments in PayHOA and their bills",
               json_stamp("payhoa/utility-transactions.json", "syncedAt"), "jason utilities --payments --fetch",
               (("utilities", "--payments", "--fetch"),), "PayHOA", "keeper",
               store="payhoa/utility-transactions.json (syncedAt)"),
        Source("drive", "Google Drive", "every file in the association's Drive, read-only",
               json_stamp("drive/files.json", "syncedAt"), "jason drive --sync", (("drive", "--sync"),), "Google Drive",
               "google", store="drive/files.json (syncedAt)"),
        Source("gmail", "Gmail", "the association's mail, headers only",
               json_stamp("gmail/correspondence.json", "syncedAt"), "jason gmail --sync", (("gmail", "--sync"),),
               "Gmail", "google", store="gmail/correspondence.json (syncedAt)"),
        Source("zoom", "Zoom", "meetings, recordings, transcripts, and summaries",
               json_stamp("zoom/meetings.json", "syncedAt"), "jason zoom", (("zoom",),), "Zoom", "keeper",
               store="zoom/meetings.json (syncedAt)"),
        Source("mail", "Scanned mail", "the mailbox's scanned letters",
               json_stamp("mail/items.json", "syncedAt"), "jason mail", (("mail",),), "PostScanMail", "keeper",
               store="mail/items.json (syncedAt)"),
        Source("permits", "City permits", "the association's permits in Citizen Access",
               json_stamp("accela/collection.json", "syncedAt"), "jason permit-status --sync",
               (("permit-status", "--sync"),), "Accela", "keeper", store="accela/collection.json (syncedAt)"),
        Source("county-tax", "County tax bills", "each parcel's tax bill",
               sync_runs(lambda root: root / "tax.db", "synced_at"), "jason sync-tax", (("sync-tax",),), "County", "",
               store="tax.db (sync_runs)"),
        Source("county-secured", "County secured roll", "each parcel's assessed values",
               sync_runs(lambda root: root / "secured.db", "synced_at"), "jason sync-secured", (("sync-secured",),), "County", "",
               store="secured.db (sync_runs)"),
        Source("smud", "SMUD", "electric bills, payments, and usage",
               sync_runs(lambda root: root / "smud.db", SMUD_STAMP), "jason sync-smud", (("sync-smud",),), "SMUD", "keeper",
               store="smud.db (sync_runs)", settings_path=True),
    )


def _declared(sources: Iterable[Source]) -> tuple[Source, ...]:
    """Each source with the threshold its integration declares (``jason.integrations.registry``): its cadence's
    ``stale_after``, and ``stale_source`` naming the integration's default. A source that already declares one, or
    whose integration gives none, is left as it is."""
    from jason.integrations.registry import cadence_for, integration_of

    out = []
    for s in sources:
        cad, integ = cadence_for(s.key), integration_of(s.key)
        if s.stale_after_days is None and cad is not None and integ is not None and cad.stale_after_days is not None:
            s = replace(s, stale_after_days=cad.stale_after_days,
                        stale_source=f"{integ.name}'s default, {cad.stale_after} (jason.integrations)")
        out.append(s)
    return tuple(out)


SOURCES: tuple[Source, ...] = _declared(_sources())


# --- the job queue, read-only ------------------------------------------------------------------------------------------

def _jobs(root: Path, limit: int = JOB_SCAN) -> list[dict[str, Any]]:
    """The newest jobs, newest first, from ``jobs.db`` opened read-only; none when there is no queue."""
    conn = _connect_ro(Path(root) / "jobs.db")
    if conn is None:
        return []
    try:
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,))]
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    for r in rows:
        try:
            r["argv"] = list(json.loads(r.get("argv") or "[]"))
        except ValueError:
            r["argv"] = []
    return rows


def _runs(source: Source, argv: list[str]) -> bool:
    """Whether a job's command line is one that refreshes ``source`` (an ``--offline`` run reads nothing)."""
    if not argv or "--offline" in argv:
        return False
    return any(argv[0] == words[0] and all(w in argv[1:] for w in words[1:]) for words in source.jobs)


def _mask(text: Any) -> str:
    from jason.approvals.audit import mask

    return str(mask(str(text or "")))


def _last_line(text: str) -> str:
    lines = [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]
    return lines[-1][:300] if lines else ""


def _job_row(job: dict[str, Any]) -> dict[str, Any]:
    return {"id": job.get("id"), "command": "jason " + " ".join(job.get("argv") or []), "status": job.get("status"),
            "at": job.get("finished") or job.get("started") or job.get("created") or "",
            "summary": _mask(_last_line(job.get("summary") or "")), "note": _mask(job.get("note") or "")}


# --- the refresh log ---------------------------------------------------------------------------------------------------

def _refreshes(root: Path) -> list[dict[str, Any]]:
    """Each live refresh a person ran (``evidence/refreshes.jsonl``), newest first."""
    path = Path(root) / "evidence" / "refreshes.jsonl"
    if not path.is_file():
        return []
    out = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                out.append(row)
    except OSError:
        return []
    return sorted(out, key=lambda r: str(r.get("at") or ""), reverse=True)


# --- standing ----------------------------------------------------------------------------------------------------------

def _when(value: str) -> datetime | None:
    try:
        at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def _after(a: str, b: str) -> bool:
    """Whether ``a`` is later than ``b`` (an empty ``b`` is never read, so anything is later)."""
    ta, tb = _when(a), _when(b)
    if ta is None:
        return False
    return tb is None or ta > tb


def _google_token(settings: Any) -> Path | None:
    path = getattr(settings, "google_oauth_token_file", None)
    return Path(path) if path else None


def _reader(source: Source, settings: Any = None) -> Reader:
    """The source's reader; a store whose path the settings name (SMUD) is read there."""
    if source.settings_path:
        return sync_runs(lambda r: _smud_db(r, settings), SMUD_STAMP)
    return source.read


def _span(days: float | None) -> str:
    """A threshold in words: ``1h`` under a day, ``2d`` otherwise; "" for none."""
    if days is None:
        return ""
    hours = days * 24
    return f"{hours:g}h" if hours < 24 else f"{days:g}d"


def source_row(source: Source, root: Path, *, jobs: list[dict[str, Any]], refreshes: list[dict[str, Any]],
               now: datetime, settings: Any = None) -> dict[str, Any]:
    """One source's row: its last read from its own stamp, its age, its standing word only where the records say it,
    its newest job, and the fix."""
    got = _reader(source, settings)(root)
    last = next((j for j in jobs if _runs(source, j.get("argv") or [])), None)
    refresh = next((r for r in refreshes if source.system and str(r.get("system") or "") == source.system), None)
    failure: tuple[str, str] | None = None                 # (when, the words)
    if last is not None and last.get("status") == "failed" and _after(str(last.get("finished") or ""), got.at):
        failure = (str(last.get("finished") or ""), f"{_job_row(last)['command']} failed: "
                                                     f"{_last_line(last.get('summary') or '') or 'see its log'}")
    # A live refresh reads one record, so its failure speaks for the source only when it was the sign-in.
    if refresh is not None and refresh.get("ok") is False and _after(str(refresh.get("at") or ""), got.at) \
            and _SIGN_IN_WORDS.search(str(refresh.get("error") or "")):
        if failure is None or _after(str(refresh.get("at") or ""), failure[0]):
            failure = (str(refresh.get("at") or ""), str(refresh.get("error") or "a refresh failed"))
    token = _google_token(settings) if source.sign_in == "google" else None
    sign_in_fix = GOOGLE_LOGIN.format(fix=source.fix) if source.sign_in == "google" else KEEPER_LOGIN
    note, fix = "", source.fix
    if failure is not None and _SIGN_IN_WORDS.search(failure[1]):
        standing, note, fix = NOT_SIGNED_IN, _mask(failure[1]), sign_in_fix
    elif failure is not None:
        standing, note = FAILED, _mask(failure[1])
    elif token is not None and not token.is_file():
        standing, note, fix = NOT_SIGNED_IN, "No Google token on this machine.", sign_in_fix
    elif not got.at:
        standing, note = NEVER_READ, "Its store holds no last read."
    elif source.stale_after_days is not None:
        at = _when(got.at)
        old = at is not None and (now - at).total_seconds() > source.stale_after_days * 86400
        standing = STALE if old else CURRENT
    else:
        standing = ""
    at = _when(got.at)
    return {"key": source.key, "name": source.name, "what": source.what, "store": source.store,
            "lastRead": got.at, "ageSeconds": int((now - at).total_seconds()) if at else None,
            "standing": standing, "note": note, "fix": fix,
            "staleAfterDays": source.stale_after_days, "staleAfter": _span(source.stale_after_days),
            "staleSource": source.stale_source,
            "lastJob": _job_row(last) if last is not None else None,
            "signIn": source.sign_in}


def _sync_errors(sources: Iterable[Source], root: Path, settings: Any = None) -> list[dict[str, Any]]:
    out = []
    for s in sources:
        got = _reader(s, settings)(root)
        if got.errors:
            out.append({"kind": "sync", "source": s.key, "name": s.name, "at": got.error_at,
                        "title": f"{s.name}: the last sync logged {len(got.errors)} "
                                 f"{'error' if len(got.errors) == 1 else 'errors'}",
                        "detail": _mask(got.errors[0])[:300], "fix": s.fix})
    return out


def failures(root: Path, *, jobs: list[dict[str, Any]], refreshes: list[dict[str, Any]], settings: Any = None,
             sources: Iterable[Source] = SOURCES, limit: int = FAILURE_LIMIT) -> list[dict[str, Any]]:
    """The newest failures, newest first: failed jobs, failed live refreshes, and sync runs that logged errors."""
    rows = list(sources)
    out: list[dict[str, Any]] = []
    for j in jobs:
        if j.get("status") != "failed":
            continue
        row = _job_row(j)
        src = next((s for s in rows if _runs(s, j.get("argv") or [])), None)
        out.append({"kind": "job", "source": src.key if src else "", "name": src.name if src else "", "at": row["at"],
                    "title": f"Job {row['id']}: {row['command']} failed", "detail": row["summary"],
                    "fix": JOBS_COMMAND, "job": row["id"]})
    for r in refreshes:
        if r.get("ok") is not False:
            continue
        system = str(r.get("system") or "")
        src = next((s for s in rows if s.system == system), None)
        out.append({"kind": "refresh", "source": src.key if src else "", "name": system, "at": str(r.get("at") or ""),
                    "title": f"{system or 'A source'}: a live refresh failed", "detail": _mask(r.get("error"))[:300],
                    "fix": ""})
    out.extend(_sync_errors(rows, root, settings))
    out.sort(key=lambda f: str(f.get("at") or ""), reverse=True)
    return out[:limit]


# --- sign-ins ----------------------------------------------------------------------------------------------------------

def sign_ins(path: Path | None, limit: int = SIGN_IN_LIMIT) -> list[dict[str, Any]]:
    """The newest sign-in lines, newest first: when, what, who, their roles, whom an admin viewed as, the provider, and
    a refusal's words masked. Never the account's email or Google ``sub``."""
    if path is None or not Path(path).is_file():
        return []
    rows = []
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    rows.sort(key=lambda r: str(r.get("at") or ""), reverse=True)
    out = []
    for r in rows[:limit]:
        item = {"at": str(r.get("at") or ""), "event": str(r.get("event") or ""), "name": str(r.get("name") or "")}
        for k in ("role", "as", "provider"):
            if r.get(k):
                item[k] = str(r[k])
        if r.get("why"):
            item["why"] = _mask(r["why"])[:200]
        out.append(item)
    return out


# --- gates -------------------------------------------------------------------------------------------------------------

def gates(root: Path, settings: Any = None) -> dict[str, Any]:
    """Onboarding's five stage gates and its progress, as setup shows them; ``found`` False with why when the session
    cannot be built."""
    from jason.community import community
    from jason.tasks import onboarding_session as task

    try:
        session = task.build(community(), root, settings=settings)
        out = task.status_dict(session)
    except Exception as exc:  # noqa: BLE001 - the screen says why, with the command that checks the profile
        return {"found": False, "note": f"The onboarding session could not be built: {type(exc).__name__}",
                "command": "jason onboard", "setup": SETUP_SCREEN}
    return {"found": True, "stage": out.get("stage", ""), "progress": out.get("progress", {}),
            "gates": out.get("gates", []), "command": "jason onboard", "setup": SETUP_SCREEN}


# --- the answer --------------------------------------------------------------------------------------------------------

def source_rows(root: Path, *, settings: Any = None, now: datetime | None = None, sources: Iterable[Source] = SOURCES,
                jobs: list[dict[str, Any]] | None = None,
                refreshes: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Each source's row from the data folder ``root`` (disk only), as Status lists them; ``jason.integrations`` reads
    its connections' states from them."""
    root = Path(root)
    at = now or datetime.now(timezone.utc)
    jobs = _jobs(root) if jobs is None else jobs
    refreshes = _refreshes(root) if refreshes is None else refreshes
    return [source_row(s, root, jobs=jobs, refreshes=refreshes, now=at, settings=settings) for s in sources]


def status_of(root: Path, *, settings: Any = None, sign_in_log: Path | None = None, now: datetime | None = None,
              gate_view: Callable[[Path, Any], dict[str, Any]] | None = None,
              sources: Iterable[Source] = SOURCES) -> dict[str, Any]:
    """The Status answer from the data folder ``root``: sources, sign-ins, gates, failures, and ``asOf``."""
    root = Path(root)
    at = now or datetime.now(timezone.utc)
    rows = tuple(sources)
    jobs = _jobs(root)
    refreshes = _refreshes(root)
    listed = source_rows(root, settings=settings, now=at, sources=rows, jobs=jobs, refreshes=refreshes)
    counts: dict[str, int] = {}
    for r in listed:
        word = r["standing"] or "no threshold"
        counts[word] = counts.get(word, 0) + 1
    return {"found": True, "asOf": at.isoformat(timespec="seconds"), "sources": listed, "counts": counts,
            "signIns": sign_ins(sign_in_log if sign_in_log is not None else root / "web" / "sign-ins.jsonl"),
            "gates": (gate_view or gates)(root, settings),
            "failures": failures(root, jobs=jobs, refreshes=refreshes, settings=settings, sources=rows),
            "caveats": list(CAVEATS)}


def _settings() -> Any:
    try:
        from jason.config import Settings

        return Settings.load()
    except Exception:  # noqa: BLE001 - no .env: the default paths
        return None


def require_admin() -> Any:
    """The signed-in admin viewing as themselves, or abort: 401 with no sign-in, 403 for anyone else and while an
    admin views the console as someone else."""
    from flask import abort

    from jason.web import access

    viewer = access.signed_in()
    if viewer.acting:
        abort(access.refusal(403, ACTING.format(who=viewer.label)))
    if not viewer.admin:
        abort(access.refusal(403, REFUSED))
    return viewer


def status(args: Args) -> dict[str, Any]:
    """``GET /api/status``: the administrator's Status, read from disk."""
    from flask import current_app

    from jason.mcp.county import _data_dir

    require_admin()
    sign_in = current_app.extensions.get("jason_sign_in")
    log = getattr(sign_in, "log", None)
    return status_of(Path(_data_dir(None)), settings=_settings(), sign_in_log=Path(log) if log else None)


__all__ = ["CAVEATS", "CURRENT", "FAILED", "NEVER_READ", "NOT_SIGNED_IN", "REFUSED", "Read", "SOURCES", "STALE",
           "Source", "column_stamp", "failures", "gates", "json_stamp", "newest_json_stamp", "require_admin",
           "sign_ins", "source_row", "source_rows", "status", "status_of", "sync_runs"]
