"""The members' family's reads (docs/workflows/members-cycles.md, sections 2.2 to 2.6): the ``check`` steps of
``notice-delivery``, ``mailroom-letter``, ``respond-sweep``, ``respond-request``, ``form-campaign``, and ``owner-document`` that an existing read
function or store answers.

Each one is read-only: it reads a store on disk (the delivery ledger, the notices folder, the Mailroom's saved previews and
send log, the PayHOA requests store, the campaigns, the notice catalog, the form library) and writes nothing. It reaches no
network and calls no PayHOA, Google, or Keeper. A store it cannot read gives ``ok=False`` with the reason, never an exception
and never ``ok`` by default. A check reports what it read in one sentence; it decides nothing for a person (it never sends,
mails, approves, denies, or assigns).

The subject a run carries tells a check what to read: ``notice:KEY`` (the delivery ledger's key), ``letter:ID`` (a saved
preview's id, or the first characters of its fingerprint), ``request:ID`` (a PayHOA request's id, or ``email:THREAD``), and
``campaign:CODE`` (a campaign code, or the library's key for the form), and ``document:NAME`` (an owner document: its Markdown
source ``data/drafts/NAME.md``, and its notice's key under ``data/notices/NAME`` once it is kept). A subject of another shape
reads the newest of its kind where that makes sense (a letter), and otherwise fails the check, saying what was missing.

A document's statutes are read from the authorities shelf **on disk** (``jason.community.law_text``), never fetched: the
on-demand export of a missing section writes a page, so no read here asks for it. A governing document's section is read
through the tokens' own resolver with its versions cache read, not built.
"""

from __future__ import annotations

import functools
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from jason.workflows.checks import check
from jason.workflows.readers import StoreReaders, day_of
from jason.workflows.types import CheckResult, RunView

MAX_LETTER_PAGES = 4
"""The PDF letter's pages, at most, unless a person chooses otherwise (AGENTS.md; billing by printed page, with PayHOA's address
page counted, and a sixth billed page adds postage)."""

SHOWN = 5
"""How many keys or messages a result names; the rest are counted."""

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_STATUTE = re.compile(r"\b(?P<code>[A-Z]{2,5})\s+(?P<number>\d+(?:\.\d+)?[a-z]?)(?P<subs>(?:\([A-Za-z0-9]+\))*)")
_DOCUMENT = re.compile(r"\b(?P<key>[a-z0-9]+(?:-[a-z0-9]+)*)#(?P<section>[A-Za-z0-9][A-Za-z0-9.()\-]*)")

BAD_LETTER = frozenset({"failed", "cancelled", "canceled", "error", "returned", "undeliverable", "rejected"})
"""A letter's status that is not "processing or better" (jason's reading of the vendor's words)."""


# --- helpers ----------------------------------------------------------------------------------------------------------

def _guarded(fn: Callable[[StoreReaders, RunView, str], CheckResult]) -> Callable[[StoreReaders, RunView, str], CheckResult]:
    """A read that raises is a read that failed: ``ok=False`` with the reason."""

    @functools.wraps(fn)
    def run(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
        try:
            return fn(readers, view, item)
        except Exception as exc:  # noqa: BLE001 - an unreadable store fails the check with its reason
            return CheckResult(False, (), f"cannot be read: {type(exc).__name__}: {exc}")

    return run


def _subject(view: RunView, kind: str, item: str = "") -> str:
    """The id after ``KIND:`` in the run's subject (or the item, when one is given)."""
    if str(item or "").strip():
        return str(item).strip()
    head, _, rest = str(view.subject or "").partition(":")
    return rest.strip() if head.strip() == kind else ""


def _community(readers: StoreReaders) -> Any:
    try:
        return readers.community
    except Exception:  # noqa: BLE001 - no community chosen: what needs one says so
        return None


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def _no_key(kind: str, example: str) -> CheckResult:
    return CheckResult(False, (), f"the run's subject names no {kind} ({example})")


# --- notice-delivery ----------------------------------------------------------------------------------------------------

@check("notice-requirement-read")
@_guarded
def notice_requirement_read(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The notice's key names a catalog requirement, with the requirement's key and a date in it (lesson
    ``notice-key-names-requirement``): recipients, methods, the clock made stricter by the documents, content, and evidence."""
    from jason.community.notice_catalog import effective
    from jason.tasks import notice_record

    key = _subject(view, "notice", item)
    if not key:
        return _no_key("notice", "notice:KEY")
    row, how = notice_record.requirement_for(key)
    if row is None:
        return CheckResult(False, (), f"no catalog row for the key {key}: it starts with no requirement's key "
                                      "(jason notices REQUIREMENT --catalog lists them)")
    if key == row.key:
        return CheckResult(False, (), f"the key {key} is the requirement's alone: name the batches REQUIREMENT-DATE so the "
                                      "record finds the notice")
    _, clocks, notes, _ = effective(row.key, _community(readers))
    words = (f"{row.title} [{row.key}; {row.statute}] ({how}): recipients {row.recipients.value}; "
             f"methods {', '.join(m.value for m in row.methods) or 'not limited'}; "
             f"clock {'; '.join(t.describe() for t in clocks) or 'none in the catalog'}; "
             f"{_plural(len(row.content), 'required element')}; {_plural(len(row.proof()), 'evidence item')} to keep")
    if notes:
        words += "; " + " ".join(notes)
    return CheckResult(True, (), words)


def _ledger_record(readers: StoreReaders, key: str):
    """(the notice's delivery record or None, the day of its last sync, the ledger's address)."""
    from jason.tasks import notice_evidence as ev

    attempts_by, kinds, synced = ev.read(readers.data_dir)
    rows = attempts_by.get(key, [])
    general, posted = kinds.get(key, (False, ""))
    rec = ev.weigh(key, rows, general=general, posted=posted)
    if rec is None and general and posted:
        rec = ev.posting(key, posted)
    return rec, synced.get(key, "")[:10], "file:" + ev.LEDGER.as_posix()


@check("notice-owed-zero")
@_guarded
def notice_owed_zero(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """No member is owed a resend and no outcome is still unknown, as the ledger was last synced. A ledger with nothing under
    the key fails the check: the sync has not run."""
    key = _subject(view, "notice", item)
    if not key:
        return _no_key("notice", "notice:KEY")
    rec, synced, address = _ledger_record(readers, key)
    if rec is None:
        return CheckResult(False, (), f"the ledger holds nothing under {key}: jason notices {key} --sync reads it")
    day = f"; last synced {synced}" if synced else ""
    evidence = readers.evidence_entries((address,))
    says = rec.describe() + day + (f"; {_plural(rec.asks, 'member')} to ask for a working address" if rec.asks else "")
    if rec.owed or rec.unsynced:
        return CheckResult(False, evidence, f"{_plural(rec.owed, 'member')} owed a resend and {rec.unsynced} with no outcome yet: "
                                            + says)
    return CheckResult(True, evidence, "owed is zero: " + says)


@check("notice-proof")
@_guarded
def notice_proof(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The proof of notice the catalog's requirement asks for is complete: each evidence item on file, the send in its
    window, and no member reached late or not at all. The windows are judged only with the run's ``event_on`` date. Whether
    the proof is sufficient is for counsel."""
    from jason.community.notices import Evidence
    from jason.tasks import notice_evidence as ev
    from jason.tasks import notice_record, notice_text

    key = _subject(view, "notice", item)
    if not key:
        return _no_key("notice", "notice:KEY")
    row, _ = notice_record.requirement_for(key)
    if row is None:
        return CheckResult(False, (), f"no catalog row for the key {key}, so no proof is defined for it "
                                      f"(jason notices {key} --proof --requirement R)")
    attempts_by, kinds, _ = ev.read(readers.data_dir)
    general, posted = kinds.get(key, (False, ""))
    kept = notice_text.read(readers.data_dir, key)
    have = {Evidence.TEXT_AS_SENT} if kept and kept["entries"] and not kept["edited"] else set()
    event = day_of(view.dates.get("event_on", ""))
    found = notice_record.proof(row, _community(readers), attempts_by.get(key, []), general=general, posted=posted,
                                event=event, have=have, key=key, private=False)
    evidence = readers.evidence_entries((f"file:{ev.LEDGER.as_posix()}", f"file:notices/{key}/kept.json"))
    open_items = [f"{i['evidence']} ({i['status']}{': ' + i['detail'] if i['detail'] else ''})"
                  for i in found["items"] if i["status"] != "on file"]
    said = [f"{found['reached']} of {found['members']} members reached"]
    if event is None and found["windows"]:
        said.append("no event_on date, so the windows are not judged")
    elif found["onTime"] is not None:
        said.append("went out " + ("in time" if found["onTime"] else "OUTSIDE the window"))
    if found["unreached"]:
        said.append(f"{found['unreached']} not reached")
    if found["late"]:
        said.append(f"{found['late']} reached after the last day")
    if open_items:
        said.append("not on file: " + "; ".join(open_items))
    if found["complete"]:
        return CheckResult(True, evidence, "the proof is complete: " + "; ".join(said) + " (counsel reads sufficiency)")
    return CheckResult(False, evidence, "the proof is not complete: " + "; ".join(said))


@check("notice-kept-text")
@_guarded
def notice_kept_text(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The words as sent are kept under ``data/notices/KEY`` and unedited since, and the ledger has a record that the notice
    went out. A file alone is never proof: the strength reads from the ledger, and is named."""
    from jason.tasks import notice_text

    key = _subject(view, "notice", item)
    if not key:
        return _no_key("notice", "notice:KEY")
    kept = notice_text.read(readers.data_dir, key)
    if not kept or not kept["entries"]:
        return CheckResult(False, (), f"no text is kept under data/notices/{key}: the send keeps it (jason.tasks.notice_text)")
    files = [f for e in kept["entries"] for f in e.get("files") or ()]
    edited = kept["edited"]
    rec, _, ledger = _ledger_record(readers, key)
    evidence = readers.evidence_entries((f"file:notices/{key}/kept.json", ledger))
    if edited:
        return CheckResult(False, evidence, f"EDITED since it was kept: {', '.join(edited)} - the words on file are not the "
                                            "words sent")
    if rec is None:
        return CheckResult(False, evidence, f"{_plural(len(files), 'file')} kept, unedited, but the ledger has no record that "
                                            "it went out: a file alone is not proof")
    return CheckResult(True, evidence, f"{_plural(len(files), 'file')} kept, unedited; strength: {rec.describe()}")


# --- mailroom-letter ----------------------------------------------------------------------------------------------------

def _preview(readers: StoreReaders, ref: str) -> tuple[dict[str, Any] | None, str]:
    from jason.tasks import mailroom

    rows = mailroom.saved_previews(readers.data_dir)
    if not rows:
        return None, "no saved preview (jason mailroom --pdf FILE --units UNITS saves one)"
    if not ref:
        return rows[0], ""
    found = [r for r in rows if r["id"] == ref or r["id"].startswith(ref) or (len(ref) >= 4 and r["fingerprint"].startswith(ref.lower()))]
    if len(found) != 1:
        return None, f"{ref} names {len(found)} saved previews" if found else f"no saved preview {ref}"
    return found[0], ""


@check("mailroom-pages")
@_guarded
def mailroom_pages(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The letter's PDF is within the page limit and its price is known, from the saved preview (the newest when the run
    names none). When the PDF is still where the preview saw it, its pages are counted again: a PDF changed since the preview
    needs a new one."""
    from jason.tasks import mailroom

    record, why = _preview(readers, _subject(view, "letter", item))
    if record is None:
        return CheckResult(False, (), why)
    pdf = record.get("pdf") or {}
    pages = int(pdf.get("pages") or 0)
    ran = record.get("printed") or {}
    cents = ran.get("centsEach")
    evidence = readers.evidence_entries((f"file:mailroom/previews/{record['id']}.json",))
    path = Path(str(pdf.get("path") or ""))
    now = None
    if path.is_file():
        try:
            now = mailroom.page_count(path)
        except Exception:  # noqa: BLE001 - a PDF that cannot be counted keeps the preview's count
            now = None
    if now is not None and now != pages:
        return CheckResult(False, evidence, f"the PDF has {now} pages now and the preview saw {pages}: preview it again")
    if pages <= 0:
        return CheckResult(False, evidence, "the preview records no page count")
    if cents is None:
        return CheckResult(False, evidence, f"{pages} pages, but the preview records no price a letter")
    printed = int(ran.get("pages") or pages + mailroom.ADDRESS_PAGES)
    said = (f"{pages} pages ({printed} billed with PayHOA's address page), {cents} cents a letter"
            + (" including the extra postage of a heavy letter" if ran.get("heavy") else ""))
    if pages > MAX_LETTER_PAGES:
        return CheckResult(False, evidence, f"over the limit of {MAX_LETTER_PAGES} pages unless a person chooses otherwise: {said}")
    return CheckResult(True, evidence, said)


def _sent_log(readers: StoreReaders) -> list[dict[str, Any]]:
    path = readers.data_dir / "mailroom" / "sent.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


@check("mailroom-batch-read")
@_guarded
def mailroom_batch_read(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Every letter of the sending is "processing or better": the send log's record of it (the run's letter, else the newest
    sending) lists its letters and their status, and the Mailroom status read, if it is newer, its batch's failed and
    cancelled counts. A letter that is not processing is a finding, never a retry."""
    ref = _subject(view, "letter", item)
    log = _sent_log(readers)
    if not log:
        return CheckResult(False, (), "the send log holds no sending (data/mailroom/sent.jsonl)")
    if ref:
        rows = [r for r in log if str(r.get("previewId") or "") == ref or str(r.get("fingerprint") or "").startswith(ref.lower())]
        if not rows:
            return CheckResult(False, (), f"no sending in the log is for the letter {ref}")
    else:
        rows = log
    record = rows[-1]
    letters, batches = record.get("letters") or [], record.get("batches") or []
    evidence = readers.evidence_entries(("file:mailroom/sent.jsonl", "file:mailroom/status.json"))
    if record.get("readBackError") or not letters:
        return CheckResult(False, evidence, "the sending was not read back: "
                                            + (str(record.get("readBackError") or "the log lists no letters")
                                               + " (jason mailroom --batch ID reads it)"))
    bad = [str(x.get("id")) for x in letters if str(x.get("status") or "").lower() in BAD_LETTER or not x.get("status")]
    ids = {b.get("id") for b in batches}
    status = {}
    path = readers.data_dir / "mailroom" / "status.json"
    if path.is_file():
        try:
            status = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            status = {}
    now = [b for b in (status.get("pdfBatches") or []) if b.get("id") in ids]
    problems = [f"batch {b.get('id')}: {b.get('failed') or 0} failed, {b.get('cancelled') or 0} cancelled"
                for b in now if (b.get("failed") or 0) or (b.get("cancelled") or 0)]
    tally: dict[str, int] = {}
    for x in letters:
        tally[str(x.get("status") or "unknown")] = tally.get(str(x.get("status") or "unknown"), 0) + 1
    said = f"{_plural(len(letters), 'letter')} in {_plural(len(batches), 'batch')}: " + ", ".join(
        f"{n} {w}" for w, n in sorted(tally.items()))
    if bad:
        problems.append(f"letter(s) {', '.join(bad)} not processing or better")
    if problems:
        return CheckResult(False, evidence, said + "; " + "; ".join(problems) + " (a finding, not a retry)")
    return CheckResult(True, evidence, said)


# --- the respond family -----------------------------------------------------------------------------------------------

def _handled(readers: StoreReaders, *, email: bool = True) -> tuple[list[Any], str]:
    """(the requests handled, a note on what was not read). Raises when the PayHOA requests store is missing or the
    community cannot be asked."""
    from jason.tasks import responses

    community = _community(readers)
    if community is None:
        raise LookupError("no community is chosen, so the requests' kinds and clocks cannot be derived")
    if not (readers.data_dir / "payhoa.db").is_file():
        raise FileNotFoundError("the PayHOA requests have not been synced (jason sync-catalog)")
    found = responses.handle(community, readers.data_dir, today=readers.today)
    note = ""
    if email:
        from jason.tasks.gmail import CORRESPONDENCE, gmail_dir

        if (gmail_dir(readers.data_dir) / CORRESPONDENCE).is_file():
            try:
                found = found + responses.email_requests(community, readers.data_dir, today=readers.today)
            except Exception as exc:  # noqa: BLE001 - the emailed requests are left out, and the note says so
                note = f"; the emailed requests could not be read ({type(exc).__name__})"
        else:
            note = "; no mail is synced, so emailed requests are not included"
    return found, note


@check("requests-read")
@_guarded
def requests_read(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The open requests can be read with their kinds and clocks: how many are open, overdue, due soon, and read as another
    kind (decided in the request's own run). It passes when it reads; the counts are information for a person."""
    from jason.community.responses import ResponseKind

    found, note = _handled(readers)
    opened = [h for h in found if h.closed is None]
    overdue = sum(1 for h in opened if h.standing.startswith("OVERDUE"))
    soon = sum(1 for h in opened if h.standing == "due soon")
    other = sum(1 for h in opened if h.kind is ResponseKind.OTHER)
    evidence = readers.evidence_entries(("file:payhoa.db",))
    return CheckResult(True, evidence, f"{_plural(len(opened), 'request')} open of {len(found)} read: {overdue} overdue, "
                                       f"{soon} due soon, {other} read as other (its kind to decide){note}")


@check("answers-on-time")
@_guarded
def answers_on_time(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The answers on time against late, by kind, can be read for the board. Counts only, never a rate: a count under five
    stays a count. It passes when it reads."""
    from jason.tasks import responses

    found, note = _handled(readers)
    figures = responses.summary(found)
    on_time, late = figures["onTime"], figures["late"]

    def by_kind(counts: dict[str, int]) -> str:
        return ", ".join(f"{k} {n}" for k, n in sorted(counts.items())) or "none"

    evidence = readers.evidence_entries(("file:payhoa.db",))
    return CheckResult(True, evidence, f"answered on time: {sum(on_time.values())} ({by_kind(on_time)}); answered late: "
                                       f"{sum(late.values())} ({by_kind(late)}); open: {sum(figures['open'].values())}{note}")


@check("request-classified")
@_guarded
def request_classified(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The run's request is in the store and has been classified: its kind, the clock row that kind has, and the due day the row
    computes (PayHOA's own date beside it, never in its place). A kind read as other, or one with no clock row, passes with
    that said and no made-up due day: deciding the kind and holding the question are the next steps' work."""
    from jason.community.responses import ResponseKind

    ident = _subject(view, "request", item)
    if not ident:
        return _no_key("request", "request:ID")
    found, _ = _handled(readers, email=ident.startswith("email:"))
    mine = next((h for h in found if str(h.request["id"]) == ident), None)
    if mine is None:
        return CheckResult(False, (), f"request {ident} is not in the requests read (jason sync-catalog brings the PayHOA "
                                      "requests; jason request-links joins emailed ones)")
    evidence = readers.evidence_entries(("file:payhoa.db",)) if not ident.startswith("email:") else ()
    if mine.rule is None:
        due = "no clock row for the kind: the question is held for the board, no due day is made up"
    elif mine.due:
        due = f"due {mine.due.isoformat()} ({mine.clock})"
    else:
        due = f"no clock: {mine.clock or 'the row sets none'}; no due day is made up"
    undecided = "; the kind is other: a person decides its kind" if mine.kind is ResponseKind.OTHER else ""
    beside = f"; PayHOA's own due date {mine.payhoa_due.isoformat()}" if mine.payhoa_due else ""
    got = day_of(view.dates.get("received_on", ""))
    differs = (f"; the run's received_on {got.isoformat()} is not the request's {mine.received.isoformat()}"
               if got and mine.received and got != mine.received else "")
    source = f"clock row from {mine.rule.source.value}; " if mine.rule is not None else ""
    return CheckResult(True, evidence, f"kind {mine.kind.value} ({mine.why}){undecided}; {source}"
                                       f"received {mine.received.isoformat() if mine.received else 'unknown'}; {due}{beside}"
                                       f"; standing {mine.standing}{differs}")


# --- form-campaign ------------------------------------------------------------------------------------------------------

def _form_of(readers: StoreReaders, view: RunView, item: str) -> tuple[Any, Any, Any] | CheckResult:
    """(the form, the resolved library, the community) the run's subject names, or the failing result."""
    from jason.community.form_library.resolve import resolve
    from jason.tasks import campaigns

    ident = _subject(view, "campaign", item)
    if not ident:
        return _no_key("form", "campaign:CODE or campaign:FORM-KEY")
    community = _community(readers)
    if community is None:
        return CheckResult(False, (), "no community is chosen, so its forms cannot be resolved")
    resolved = resolve(community)
    form = resolved.get(ident)
    if form is None:
        row = campaigns.load(readers.data_dir).get(ident)
        form = resolved.get(row.form) if row is not None else None
    if form is None:
        return CheckResult(False, (), f"{ident} names no form in this community's library "
                                      "(jason form-library --check lists them)")
    return form, resolved, community


@check("form-offered")
@_guarded
def form_offered(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The form is offered: ready or adjusted in the library as this community has it, with no failing finding. A form not
    offered names the missing slot or binding. The run's subject is the campaign's code or the library's key for the form."""
    from jason.community.form_library.check import check as library_check

    got = _form_of(readers, view, item)
    if isinstance(got, CheckResult):
        return got
    form, resolved, community = got
    report = library_check(resolved, readers.data_dir, community=community)
    mine = report.for_form(form.key)
    status = report.status(form.key) or form.status
    failing = [f.line() for f in mine if f.severity.value == "fail"]
    tier = form.tier.value
    if failing:
        return CheckResult(False, (), f"{form.key} ({tier}) is failing: " + "; ".join(failing[:3])
                           + (f"; and {len(failing) - 3} more" if len(failing) > 3 else ""))
    if not form.offered:
        return CheckResult(False, (), f"{form.key} ({tier}) is {status.value}: " + ("; ".join(form.missing) or "not offered"))
    return CheckResult(True, (), f"{form.key} ({tier}) is {status.value}, version {form.definition.version}")


@check("form-stale")
@_guarded
def form_stale(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The form's recitals still read the words on the shelf: no statute it recites has had a change logged to its words
    after the form's as-of day (the library's check 2, read for staleness alone). A change is for a person to read: the
    amendment first, then the definition and its version. A recital that cannot be read, or a form with recitals and no as-of
    day, cannot be judged and fails."""
    from jason.community.form_library.check import check_recitals

    got = _form_of(readers, view, item)
    if isinstance(got, CheckResult):
        return got
    form, _, community = got
    recitals = tuple(form.definition.recitals)
    if not recitals:
        return CheckResult(True, (), f"{form.key} recites no statute or clause, so no amendment can make it stale")
    as_of = form.definition.as_of
    if as_of is None:
        return CheckResult(False, (), f"{form.key} recites {_plural(len(recitals), 'section')} and has no as-of day, so a change "
                                      "to their words cannot be told from the form's own")
    found = check_recitals(form, readers.data_dir, community)
    stale = [f for f in found if f.message.startswith("stale:")]
    unread = [f for f in found if not f.message.startswith("stale:")]
    evidence = readers.evidence_entries(("file:authorities/manifest.json", "file:authorities/changes.json"))
    said = f"{form.key} recites {_plural(len(recitals), 'section')} as of {as_of.isoformat()} (version {form.definition.version})"
    if stale:
        names = sorted({f.item for f in stale})
        return CheckResult(False, evidence, said + f"; {_plural(len(names), 'recital')} changed on the shelf since: {', '.join(names)} "
                                                   "(read the amendment, update the definition, bump its version)")
    if unread:
        names = sorted({f.item for f in unread})
        return CheckResult(False, evidence, said + f"; {_plural(len(names), 'recital')} cannot be read, so staleness is not known: "
                                                   f"{', '.join(names)}")
    return CheckResult(True, evidence, said + "; no change logged to any of them since")


# --- reading a document's words without building anything -----------------------------------------------------------------

def _doc_name(view: RunView, item: str, *kinds: str) -> str:
    """The name after ``KIND:`` in the run's subject for any of ``kinds`` (or the item, when one is given)."""
    if str(item or "").strip():
        return str(item).strip()
    head, _, rest = str(view.subject or "").partition(":")
    return rest.strip() if head.strip() in kinds else ""


def _draft(readers: StoreReaders, name: str) -> tuple[Path | None, str]:
    """(the Markdown under ``data/drafts``, why not). The name is a file name, never a path."""
    if not _SAFE_NAME.match(name) or ".." in name:
        return None, f"{name!r} is not a draft's name (a file name under data/drafts)"
    path = readers.data_dir / "drafts" / (name if name.endswith(".md") else name + ".md")
    if not path.is_file():
        return None, f"no draft data/drafts/{path.name}: the document's one source is written there first"
    return path, ""


def _reader(readers: StoreReaders) -> Any:
    """The tokens' own resolver with its versions cache read and never built: building a living document's versions writes."""
    from jason.community.section_refs import SectionRefError
    from jason.tasks import section_refs as sr

    community = _community(readers)
    if community is None:
        raise LookupError("no community is chosen, so the documents cannot be read")

    class ReadOnly(sr.DiskResolver):
        def versions(self, key: str) -> Any:
            if key not in self._versions:
                living = self.living(key)
                if living is None:
                    raise SectionRefError(f"{key} is not kept as amended", "not_kept_as_amended")
                path = sr.store_dir(self.data_dir) / f"versions-{key}.json"
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError) as exc:
                    raise SectionRefError(f"{key}: its versions are not built (jason cite builds them)", "unreadable") from exc
                if raw.get("format") != sr.VERSIONS_FORMAT or raw.get("fingerprint") != sr._fingerprint(living, self.data_dir):
                    raise SectionRefError(f"{key}: its versions are older than its sources (jason cite builds them again)",
                                          "unreadable")
                self._versions[key] = sr.Versions.from_dict(raw)
            return self._versions[key]

    return ReadOnly(readers.data_dir, community)


def _on_shelf(readers: StoreReaders, citation: str) -> tuple[bool, str]:
    """(whether the section's words are on the authorities shelf, a short phrase). The disk only: nothing is fetched."""
    from jason.community import law_text

    found = law_text.normal_citation(citation)
    if found is None:
        return False, f"{citation} is not a code and a section"
    held = law_text.versions(found[0], readers.data_dir)
    if not held:
        return False, f"{found[0]} is not on the authorities shelf"
    return True, f"{found[0]} is on the shelf"


def _cited(text: str) -> tuple[list[str], list[tuple[str, str]]]:
    """(the statute sections a string cites, once each; the governing documents' ``key#section`` it names)."""
    statutes = list(dict.fromkeys(f"{m['code']} {m['number']}" for m in _STATUTE.finditer(text or "")))
    documents = list(dict.fromkeys((m["key"], m["section"]) for m in _DOCUMENT.finditer(text or "")))
    return statutes, documents


@check("clock-authority-recited")
@_guarded
def clock_authority_recited(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The authority behind the request's clock can be recited from stored words: a statute section is on the authorities
    shelf, a governing document's clause (``key#section``) is in the document as it is kept. The words themselves are recited
    by ``jason cite``; this passes when they are there to recite. A clock that is a proposed policy, or a kind with no clock row,
    has no authority to recite: it passes saying so, and the next step holds the question for the board."""
    from jason.community.responses import ClockSource
    from jason.community.section_refs import SectionRefError

    ident = _subject(view, "request", item)
    if not ident:
        return _no_key("request", "request:ID")
    found, _ = _handled(readers, email=ident.startswith("email:"))
    mine = next((h for h in found if str(h.request["id"]) == ident), None)
    if mine is None:
        return CheckResult(False, (), f"request {ident} is not in the requests read (jason sync-catalog brings the PayHOA requests)")
    evidence = readers.evidence_entries(("file:payhoa.db",)) if not ident.startswith("email:") else ()
    rule = mine.rule
    if rule is None or rule.source in (ClockSource.POLICY, ClockSource.NONE):
        why = "the kind has no clock row" if rule is None else f"the clock is a {rule.source.value}"
        statutes, _ = _cited(rule.authority if rule is not None else "")
        beside = ""
        if statutes:
            beside = "; cited beside it: " + ", ".join(
                f"{s} ({'on the shelf' if _on_shelf(readers, s)[0] else 'not on the shelf'})" for s in statutes)
        return CheckResult(True, evidence, why + ": no statute or clause sets it, so there are no words to recite; the next step "
                                           "holds the question for the board, and no due day is made up" + beside)
    authority = rule.authority
    if rule.source is ClockSource.STATUTE and rule.notice:
        from jason.community.notice_catalog import requirement

        try:
            authority = f"{authority} {requirement(rule.notice).statute}"
        except KeyError:
            pass
    statutes, documents = _cited(authority)
    if not statutes and not documents:
        return CheckResult(False, evidence, f"the {rule.source.value} the clock rests on names no section to recite "
                                            "(a statute as CIV NNNN, or a clause as key#section)")
    heard: list[str] = []
    missed: list[str] = []
    for citation in statutes:
        ok, phrase = _on_shelf(readers, citation)
        (heard if ok else missed).append(phrase)
    if documents:
        reader = _reader(readers)
        for key, number in documents:
            try:
                got = reader.section(key, number)
                heard.append(f"{got.citation} is in the document as kept")
            except SectionRefError as exc:
                missed.append(str(exc))
    if missed:
        return CheckResult(False, evidence, "cannot recite: " + "; ".join(missed[:SHOWN]) + ("; " + "; ".join(heard) if heard else ""))
    return CheckResult(True, evidence, "the words can be recited: " + "; ".join(heard) + " (jason cite recites them; any reading is "
                                       "labeled and whose)")


# --- owner-document -----------------------------------------------------------------------------------------------------

@check("references-fill")
@_guarded
def references_fill(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Every ``{QUOTE:key#n}`` and ``{CITE:key#n}`` in the document's Markdown (``data/drafts/NAME.md``) fills from the
    documents as they are kept. Nothing is rendered or kept: the tokens are resolved and every failure is named at once. A
    document with no token passes saying so."""
    from jason.community.section_refs import TOKEN, SectionRefError, expand_markdown

    name = _doc_name(view, item, "document")
    if not name:
        return _no_key("document", "document:NAME")
    path, why = _draft(readers, name)
    if path is None:
        return CheckResult(False, (), why)
    text = path.read_text(encoding="utf-8")
    tokens = list(TOKEN.finditer(text))
    evidence = readers.evidence_entries((f"file:drafts/{path.name}",))
    if not tokens:
        return CheckResult(True, evidence, f"data/drafts/{path.name} has no reference to fill")
    try:
        _, records = expand_markdown(text, _reader(readers), caveat=False)
    except SectionRefError as exc:
        bad = [m for m in str(exc).split("; ") if m]
        return CheckResult(False, evidence, f"{_plural(len(bad), 'reference')} of {len(tokens)} do not fill: "
                           + "; ".join(bad[:SHOWN]) + (f"; and {len(bad) - SHOWN} more" if len(bad) > SHOWN else ""))
    quotes = sum(1 for r in records if r.verb == "QUOTE")
    noted = sum(1 for r in records if r.note)
    said = f"{_plural(len(records), 'reference')} fill ({quotes} quoted, {len(records) - quotes} cited)"
    if noted:
        said += f"; {noted} carry a note to check against the recorded copy"
    return CheckResult(True, evidence, said)


@check("notice-elements")
@_guarded
def notice_elements(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """When the document is a notice the Act requires, each element its catalog row requires is in its words (``jason
    notice-check``): present, supplied by a token, or said to be enclosed. The row is the one the document's name starts with
    (the ledger-key convention), or the one the ``item`` names. An element only some notices need is read against the
    profile's facts and a person's answers; one they do not settle is never read as not required. Elements words cannot settle
    are counted for a person to read. A document that serves no requirement fails, saying which names to use."""
    from jason.community import notice_catalog
    from jason.community.notice_elements import Status, check as elements
    from jason.tasks import notice_record

    name = _doc_name(view, "", "document")
    row = None
    if str(item or "").strip():
        try:
            row = notice_catalog.requirement(str(item).strip())
        except KeyError:
            return CheckResult(False, (), f"{item} is not a notice requirement in the catalog (jason notices --catalog lists them)")
    if not name:
        return _no_key("document", "document:NAME")
    if row is None:
        row, _ = notice_record.requirement_for(name)
    if row is None:
        return CheckResult(False, (), f"{name} starts with no requirement's key, so no elements are checked (jason notices "
                                      "REQUIREMENT --catalog; name the document with the requirement's key)")
    path, why = _draft(readers, name)
    if path is None:
        return CheckResult(False, (), why)
    facts = None
    community = _community(readers)
    if community is not None:
        from jason.tasks.applicability_asks import association_facts

        try:
            facts = association_facts(community, readers.data_dir)
        except AttributeError:               # a profile that states no facts: every condition stays undetermined
            facts = None
    found = elements(row, path.read_text(encoding="utf-8"), facts)
    missing = [f for f in found if f.status is Status.MISSING]
    unread = sum(1 for f in found if f.status is Status.UNCHECKED)
    spared = sum(1 for f in found if f.status is Status.NOT_REQUIRED)
    shown = sum(1 for f in found if f.ok)
    evidence = readers.evidence_entries((f"file:drafts/{path.name}", "file:intake/asks.json"))
    if not found:
        return CheckResult(False, evidence, f"{row.key} lists no element to check")
    said = (f"{row.key}: {shown} of {len(found)} elements shown, {len(missing)} missing, {unread} for a person to read"
            + (f", {spared} that do not apply" if spared else ""))
    if missing:
        names = [f"{f.element} ({f.cite})" + (f" [{f.needs()}]" if f.needs() else "") for f in missing]
        return CheckResult(False, evidence, said + ": missing " + "; ".join(names[:SHOWN])
                           + (f"; and {len(names) - SHOWN} more" if len(names) > SHOWN else ""))
    return CheckResult(True, evidence, said)


@check("kept-text-unchanged")
@_guarded
def kept_text_unchanged(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The words kept under the notice's key (``data/notices/KEY``) are the words that were kept: every kept file still has the
    digest it was kept with. An edit since means the words on file are not the words sent. A source Markdown newer than the last
    keeping is said, not failed: the sent words are the kept ones. The key is the run's document name, or the ``item``."""
    from jason.tasks import notice_text

    key = _doc_name(view, item, "document", "notice")
    if not key:
        return _no_key("document", "document:NAME")
    kept = notice_text.read(readers.data_dir, key)
    if not kept or not kept["entries"]:
        return CheckResult(False, (), f"no text is kept under data/notices/{key}: the send keeps it (jason.tasks.notice_text)")
    files = [f for e in kept["entries"] for f in e.get("files") or ()]
    evidence = readers.evidence_entries((f"file:notices/{key}/kept.json",))
    if kept["edited"]:
        return CheckResult(False, evidence, f"EDITED or gone since it was kept: {', '.join(kept['edited'])} - the words on file are "
                                            "not the words kept")
    said = f"{_plural(len(files), 'file')} kept in {_plural(len(kept['entries']), 'keeping')}, each unchanged since"
    source = readers.data_dir / "drafts" / f"{key}.md"
    when = []
    for e in kept["entries"]:
        try:
            when.append(datetime.fromisoformat(str(e["kept"])))
        except (KeyError, ValueError):
            continue
    if source.is_file() and when and source.stat().st_mtime > max(when).timestamp() + 1:
        said += f"; the Markdown source data/drafts/{source.name} is newer than the last keeping (the kept words are the ones sent)"
    return CheckResult(True, evidence, said)


__all__ = ["answers_on_time", "clock_authority_recited", "form_offered", "form_stale", "kept_text_unchanged", "mailroom_batch_read",
           "mailroom_pages", "notice_elements", "notice_kept_text", "notice_owed_zero", "notice_proof", "notice_requirement_read",
           "references_fill", "request_classified", "requests_read"]
