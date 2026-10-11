"""The members' family's reads (src/jason/workflows/checks/members.py), in a temporary data folder with made-up stores.

Nothing here reads a real store, reaches the network, or loads a profile. Every read is checked three ways: it passes on a
store that shows what it looks for, it fails with its reason on one that does not (a missing store, an unreadable one, a
wrong subject), and it leaves the data folder byte-identical. Everything is made up ("123 Main St", 2099).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from jason.community.form_library import FormDefinition, Tier
from jason.community.forms import FormKey, FormQuestion, FormTemplate, QuestionKind
from jason.tasks import notice_ledger, notice_text
from jason.workflows import checks
from jason.workflows.defs import members as defs
from jason.workflows.readers import CHECKS, StoreReaders, named_check
from jason.workflows.types import CheckResult, Role, StepDef, StepKind
from test_workflows_support import data  # noqa: F401 - the `data` fixture

checks.load_all()

NAMES = ("notice-requirement-read", "notice-owed-zero", "notice-proof", "notice-kept-text", "mailroom-pages",
         "mailroom-batch-read", "requests-read", "answers-on-time", "request-classified", "form-offered")
TODAY = date(2099, 3, 10)
D = notice_ledger.Delivery
MEETING = "board-meeting-2099-01-14"
OWNER_INFO = "owner-info-2099"


def tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def view(subject="", **dates):
    return SimpleNamespace(id="run-test", subject=subject, dates=dict(dates), opened_at="2020-01-01T00:00:00Z")


def custom_form(key="survey", **kw):
    template = FormTemplate(FormKey.OWNER_INFO, "Demo survey", "A made-up form.", "Use this made-up form.",
                            (FormQuestion("Your name", key="name"), FormQuestion("What do you want?", QuestionKind.PARAGRAPH)))
    return FormDefinition(**{"template": template, "tier": Tier.CUSTOM, "key": key, "handler": "collect-only",
                             "procedure": "respond", **kw})


class Community:
    """A profile's say on the few things the reads ask: topic rules, senders, and its own forms."""

    def __init__(self, *forms):
        self.forms = forms

    def topic_rules(self):
        return ()

    def senders(self):
        return ()

    def jurisdictions(self):
        return ()

    def custom_forms(self):
        return self.forms


@pytest.fixture
def folder(data):
    data.mkdir(parents=True, exist_ok=True)
    return data


@pytest.fixture
def readers(folder):
    return StoreReaders(folder, community=Community(custom_form()), today=TODAY)


def run(name, readers, subject="", item="", **dates) -> CheckResult:
    return CHECKS[name](readers, view(subject, **dates), item)


# --- the ledger and the notices folder ---------------------------------------------------------------------------------

def attempt(n, status, notice=MEETING, channel="email"):
    return notice_ledger.Attempt(notice, n, n, f"{n} Main St", channel, "batch", f"ref-{n}", sent_at="2099-01-01T10:00:00Z",
                                 status=status)


def sync(folder, *statuses, notice=MEETING):
    notice_ledger.save(folder, [attempt(i, s, notice) for i, s in enumerate(statuses, 1)])


# --- the registration ------------------------------------------------------------------------------------------------

def test_the_members_module_registers_the_ten_reads_and_the_definitions_name_them():
    assert set(NAMES) <= set(CHECKS)
    named = {s.check.name for b in defs.BUILDERS for s in b().steps if s.check is not None}
    assert named == set(NAMES) | {"outstanding-read"}
    for b in defs.BUILDERS:
        for s in b().steps:
            if s.check is not None and s.check.name in NAMES:
                assert s.kind is StepKind.CHECK and s.role is Role.JASON, s.id
    assert not any(n in defs.WANTED for n in ("check " + x for x in NAMES))


@pytest.mark.parametrize("name", NAMES)
def test_a_read_with_no_subject_and_no_stores_fails_with_a_reason_and_creates_nothing(name, tmp_path):
    missing = tmp_path / "no-data-folder"
    out = CHECKS[name](StoreReaders(missing, community=Community(), today=TODAY), view(""), "")
    assert out.ok is False and out.message and not missing.exists()


@pytest.mark.parametrize("name,subject", [
    ("notice-requirement-read", "notice:" + MEETING), ("notice-owed-zero", "notice:" + MEETING),
    ("notice-proof", "notice:" + OWNER_INFO), ("notice-kept-text", "notice:" + MEETING), ("mailroom-pages", "letter:x"),
    ("mailroom-batch-read", "letter:x"), ("requests-read", ""), ("answers-on-time", ""), ("request-classified", "request:101"),
    ("form-offered", "campaign:survey"),
])
def test_a_named_step_reaches_its_read_through_the_readers_and_an_empty_folder_is_not_ok(name, subject, folder):
    step = StepDef("w.1", "A step", StepKind.CHECK, role=Role.JASON, check=named_check(name))
    readers = StoreReaders(folder, community=Community(), today=TODAY)
    before = tree(folder)
    out = readers.check(step, view(subject), "")
    assert isinstance(out, CheckResult)
    assert tree(folder) == before


# --- notice-requirement-read ---------------------------------------------------------------------------------------

def test_the_requirement_is_read_when_the_key_starts_with_a_catalog_key_and_carries_a_date(readers):
    out = run("notice-requirement-read", readers, "notice:" + MEETING)
    assert out.ok and "board-meeting" in out.message and "CIV 4920" in out.message and "evidence item" in out.message
    assert run("notice-requirement-read", readers, "notice:" + OWNER_INFO).ok                     # a form's request


def test_a_key_that_names_no_requirement_or_no_date_fails(readers):
    assert not run("notice-requirement-read", readers, "notice:made-up-notice-2099").ok
    bare = run("notice-requirement-read", readers, "notice:board-meeting")
    assert not bare.ok and "REQUIREMENT-DATE" in bare.message
    assert not run("notice-requirement-read", readers, "campaign:OI-2099").ok


def test_the_item_names_the_key_when_there_is_one(readers):
    assert run("notice-requirement-read", readers, "", item=MEETING).ok


# --- notice-owed-zero -----------------------------------------------------------------------------------------------

def test_owed_is_zero_when_every_member_has_an_outcome_and_none_is_owed_a_resend(folder, readers):
    assert "holds nothing" in run("notice-owed-zero", readers, "notice:" + MEETING).message
    sync(folder, D.DELIVERED, D.OPENED)
    before = tree(folder)
    out = run("notice-owed-zero", readers, "notice:" + MEETING)
    assert out.ok and out.message.startswith("owed is zero") and "2 of 2" in out.message
    assert out.evidence and out.evidence[0].startswith("file:notices/deliveries.db@")
    assert tree(folder) == before


def test_a_bounce_owed_a_resend_or_an_outcome_not_yet_read_is_not_zero(folder, readers):
    sync(folder, D.DELIVERED, D.BOUNCED)
    out = run("notice-owed-zero", readers, "notice:" + MEETING)
    assert not out.ok and "1 member owed a resend" in out.message
    sync(folder, D.DELIVERED, D.PENDING)
    out = run("notice-owed-zero", readers, "notice:" + MEETING)
    assert not out.ok and "1 with no outcome yet" in out.message


def test_a_ledger_that_cannot_be_read_fails_the_read(folder, readers):
    (folder / "notices").mkdir()
    (folder / "notices" / "deliveries.db").write_bytes(b"this is not a database" * 40)
    before = tree(folder)
    out = run("notice-owed-zero", readers, "notice:" + MEETING)
    assert not out.ok and out.message
    assert tree(folder) == before


# --- notice-proof ---------------------------------------------------------------------------------------------------

def test_the_proof_is_complete_with_the_text_kept_the_ledger_and_the_event_day(folder, readers):
    sync(folder, D.DELIVERED, D.DELIVERED, notice=OWNER_INFO)
    out = run("notice-proof", readers, "notice:" + OWNER_INFO, event_on="2099-01-14")
    assert not out.ok and "the notice as sent" in out.message                                        # no text kept yet
    notice_text.keep(folder, OWNER_INFO, kind="email", state="sent", body="<p>Hello</p>", subject="Subject")
    before = tree(folder)
    out = run("notice-proof", readers, "notice:" + OWNER_INFO, event_on="2099-01-14")
    assert out.ok and out.message.startswith("the proof is complete") and "2 of 2 members reached" in out.message
    assert len(out.evidence) == 2
    assert tree(folder) == before


def test_the_proof_is_not_complete_without_the_event_day_a_member_reached_or_a_text_unedited(folder, readers):
    sync(folder, D.DELIVERED, D.BOUNCED, notice=OWNER_INFO)
    notice_text.keep(folder, OWNER_INFO, kind="email", state="sent", body="<p>Hello</p>", subject="Subject")
    out = run("notice-proof", readers, "notice:" + OWNER_INFO)
    assert not out.ok and "no event_on date" in out.message and "not reached" in out.message
    sync(folder, D.DELIVERED, D.DELIVERED, notice=OWNER_INFO)
    kept = next((folder / "notices" / OWNER_INFO).glob("message*.html"))
    kept.write_text("<p>Changed</p>", encoding="utf-8")                                              # edited since kept
    out = run("notice-proof", readers, "notice:" + OWNER_INFO, event_on="2099-01-14")
    assert not out.ok and "the notice as sent" in out.message


def test_a_key_with_no_requirement_has_no_proof(readers):
    out = run("notice-proof", readers, "notice:made-up-notice-2099")
    assert not out.ok and "no catalog row" in out.message


# --- notice-kept-text -----------------------------------------------------------------------------------------------

def test_the_kept_text_is_read_with_the_ledgers_strength(folder, readers):
    out = run("notice-kept-text", readers, "notice:" + MEETING)
    assert not out.ok and "no text is kept" in out.message
    notice_text.keep(folder, MEETING, kind="email", state="sent", body="<p>Hello</p>", subject="Subject")
    out = run("notice-kept-text", readers, "notice:" + MEETING)
    assert not out.ok and "a file alone is not proof" in out.message
    sync(folder, D.DELIVERED, D.DELIVERED)
    before = tree(folder)
    out = run("notice-kept-text", readers, "notice:" + MEETING)
    assert out.ok and "1 file kept, unedited" in out.message and "delivered: 2 of 2" in out.message
    assert tree(folder) == before


def test_a_text_edited_since_it_was_kept_is_not_the_text_sent(folder, readers):
    sync(folder, D.DELIVERED)
    notice_text.keep(folder, MEETING, kind="email", state="sent", body="<p>Hello</p>", subject="Subject")
    next((folder / "notices" / MEETING).glob("message*.html")).write_text("<p>Edited</p>", encoding="utf-8")
    out = run("notice-kept-text", readers, "notice:" + MEETING)
    assert not out.ok and out.message.startswith("EDITED since it was kept")
    (folder / "notices" / MEETING / "kept.json").write_text("{ not json", encoding="utf-8")
    assert not run("notice-kept-text", readers, "notice:" + MEETING).ok


# --- the Mailroom ---------------------------------------------------------------------------------------------------

def preview(folder, pid="20990101-packet", pages=3, cents=145, path="", fingerprint=None, heavy=False):
    where = folder / "mailroom" / "previews"
    where.mkdir(parents=True, exist_ok=True)
    record = {"id": pid, "fingerprint": fingerprint or "ab" * 32, "pdf": {"name": "packet.pdf", "path": path, "pages": pages},
              "printed": {"pages": pages + 1, "centsEach": cents, "heavy": heavy}, "lettersExpected": 2}
    (where / f"{pid}.json").write_text(json.dumps(record), encoding="utf-8")
    return record


def pdf(path: Path, pages: int) -> Path:
    import pymupdf

    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page()
    doc.save(str(path))
    doc.close()
    return path


def test_the_pages_are_within_the_limit_and_the_price_is_known(folder, readers):
    assert "no saved preview" in run("mailroom-pages", readers).message
    preview(folder, pages=4, cents=185)
    before = tree(folder)
    out = run("mailroom-pages", readers)
    assert out.ok and "4 pages (5 billed" in out.message and "185 cents a letter" in out.message
    assert out.evidence[0].startswith("file:mailroom/previews/20990101-packet.json@")
    assert tree(folder) == before


def test_a_letter_over_four_pages_or_without_a_price_fails(folder, readers):
    preview(folder, pages=5, cents=230, heavy=True)
    out = run("mailroom-pages", readers)
    assert not out.ok and "limit of 4 pages" in out.message and "extra postage" in out.message
    preview(folder, pages=2, cents=None)
    assert "no price a letter" in run("mailroom-pages", readers).message
    (folder / "mailroom" / "previews" / "20990101-packet.json").write_text("{ not json", encoding="utf-8")
    assert not run("mailroom-pages", readers).ok


def test_the_pages_are_counted_again_when_the_pdf_is_still_there(folder, readers):
    file = pdf(folder / "packet.pdf", 3)
    preview(folder, pages=3, path=str(file))
    assert run("mailroom-pages", readers).ok
    pdf(folder / "packet.pdf", 5)
    out = run("mailroom-pages", readers)
    assert not out.ok and "5 pages now and the preview saw 3" in out.message


def test_the_letter_in_the_subject_picks_its_preview(folder, readers):
    preview(folder, pid="20990101-a", pages=2, fingerprint="aa" * 32)
    preview(folder, pid="20990102-b", pages=6, fingerprint="bb" * 32)
    assert run("mailroom-pages", readers, "letter:20990101-a").ok
    assert not run("mailroom-pages", readers, "letter:bbbb").ok
    assert "no saved preview" in run("mailroom-pages", readers, "letter:zzzzzz").message


def sending(folder, *, statuses=("processing", "processing"), preview_id="20990101-a", fingerprint="aa" * 32, extra=None,
            batch=None):
    log = folder / "mailroom"
    log.mkdir(parents=True, exist_ok=True)
    record = {"sent": "2099-01-02T10:00:00+00:00", "pages": 3, "previewId": preview_id, "fingerprint": fingerprint,
              "batches": [{"id": 900, "kind": "pdf", "sent": len(statuses), "failed": 0, "cancelled": 0}],
              "letters": [{"id": 1000 + i, "status": s} for i, s in enumerate(statuses)], **(extra or {})}
    with (log / "sent.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    if batch is not None:
        (log / "status.json").write_text(json.dumps({"read": "2099-01-03T00:00:00+00:00", "pdfBatches": [batch]}), encoding="utf-8")


def test_every_letter_processing_or_better_passes_the_batch_read(folder, readers):
    assert "holds no sending" in run("mailroom-batch-read", readers).message
    sending(folder, statuses=("processing", "in_transit"))
    before = tree(folder)
    out = run("mailroom-batch-read", readers, "letter:20990101-a")
    assert out.ok and "2 letters in 1 batch" in out.message and "1 in_transit" in out.message
    assert run("mailroom-batch-read", readers).ok                                                    # the newest sending
    assert tree(folder) == before


def test_a_letter_that_is_not_processing_or_a_batch_that_failed_is_a_finding(folder, readers):
    sending(folder, statuses=("processing", "failed"))
    out = run("mailroom-batch-read", readers)
    assert not out.ok and "letter(s) 1001 not processing or better" in out.message and "not a retry" in out.message
    sending(folder, statuses=("processing",), preview_id="b", fingerprint="bb" * 32,
            batch={"id": 900, "sent": 1, "failed": 1, "cancelled": 0})
    out = run("mailroom-batch-read", readers, "letter:b")
    assert not out.ok and "batch 900: 1 failed" in out.message
    sending(folder, statuses=(), preview_id="c", fingerprint="cc" * 32, extra={"readBackError": "OSError: down"})
    out = run("mailroom-batch-read", readers, "letter:c")
    assert not out.ok and "not read back" in out.message
    assert "no sending in the log is for the letter" in run("mailroom-batch-read", readers, "letter:nobody").message


# --- the requests ----------------------------------------------------------------------------------------------------

def requests_db(folder, rows):
    con = sqlite3.connect(folder / "payhoa.db")
    con.execute("create table units(id integer, label text)")
    con.execute("create table requests(id integer, form_name text, unit_id integer, status text, created_at text, raw_json text)")
    con.execute("insert into units values (1, '101 Main St')")
    for rid, form, title, message, created, status, comments, done in rows:
        raw = {"createdAt": created, "answers": [{"question": {"label": "Title"}, "answer": title},
                                                 {"question": {"label": "Message"}, "answer": message}],
               "comments": [{"createdAt": c, "isAdmin": True} for c in comments]}
        if done:
            raw["completionDate"] = done
        con.execute("insert into requests values (?, ?, 1, ?, ?, ?)", (rid, form, status, created, json.dumps(raw)))
    con.commit()
    con.close()


ROWS = [
    (101, "General Request", "Records request", "I would like copies of the budget records", "2099-03-02T18:00:00Z", "open", (), ""),
    (102, "General Request", "Records request", "I would like to inspect the minutes", "2099-02-01T18:00:00Z", "open", (), ""),
    (103, "General Request", "Records request", "Copies of the budget records please", "2099-01-05T18:00:00Z", "complete",
     ("2099-01-07T18:00:00Z",), "2099-01-08T18:00:00Z"),
    (104, "General Request", "Records request", "Copies of the budget records please", "2099-01-05T18:00:00Z", "complete",
     ("2099-02-20T18:00:00Z",), "2099-02-21T18:00:00Z"),
    (105, "Other Form", "Hello", "Nothing in particular", "2099-03-01T18:00:00Z", "open", (), ""),
    (106, "General Request", "Records request", "Copies of the minutes please", "2099-02-25T18:00:00Z", "open", (), ""),
]


def test_the_open_requests_are_read_with_their_standing(folder, readers):
    out = run("requests-read", readers)
    assert not out.ok and "have not been synced" in out.message
    requests_db(folder, ROWS)
    before = tree(folder)
    out = run("requests-read", readers)
    assert out.ok and out.evidence[0].startswith("file:payhoa.db@")
    assert "4 requests open of 6 read: 1 overdue, 1 due soon, 1 read as other" in out.message, out.message
    assert "no mail is synced" in out.message
    assert tree(folder) == before


def test_the_answers_on_time_are_counted_by_kind_and_never_as_a_rate(folder, readers):
    requests_db(folder, ROWS)
    before = tree(folder)
    out = run("answers-on-time", readers)
    assert out.ok and "answered on time: 1 (records request 1)" in out.message
    assert "answered late: 1 (records request 1)" in out.message and "%" not in out.message
    assert tree(folder) == before


def test_the_requests_need_a_community_and_a_store_that_reads(folder):
    nobody = StoreReaders(folder, community=Community(), today=TODAY)
    requests_db(folder, ROWS)
    (folder / "payhoa.db").write_bytes(b"not a database" * 50)
    assert not run("requests-read", nobody).ok and not run("answers-on-time", nobody).ok

    class Broken(StoreReaders):
        @property
        def community(self):
            raise RuntimeError("no community is chosen")

    assert "no community" in run("requests-read", Broken(folder, today=TODAY)).message


def test_a_request_is_classified_with_its_kind_clock_row_and_due_day(folder, readers):
    requests_db(folder, ROWS)
    before = tree(folder)
    out = run("request-classified", readers, "request:101", received_on="2099-03-02")
    assert out.ok and "kind records request" in out.message and "due 2099-03-16" in out.message
    assert "clock row from statute" in out.message and "is not the request's" not in out.message
    assert "is not the request's 2099-03-02" in run("request-classified", readers, "request:101", received_on="2099-03-05").message
    assert tree(folder) == before


def test_a_kind_read_as_other_is_classified_and_shows_no_made_up_due_day(folder, readers):
    requests_db(folder, ROWS)
    out = run("request-classified", readers, "request:105")
    assert out.ok and "kind other" in out.message and "a person decides its kind" in out.message
    assert "no due day is made up" in out.message


def test_a_request_not_in_the_store_is_not_classified(folder, readers):
    assert not run("request-classified", readers, "request:101").ok                               # no store yet
    requests_db(folder, ROWS)
    out = run("request-classified", readers, "request:999")
    assert not out.ok and "not in the requests read" in out.message
    assert not run("request-classified", readers, "request:email:EXAMPLE1").ok
    assert not run("request-classified", readers, "campaign:X").ok


# --- form-offered ----------------------------------------------------------------------------------------------------

def test_a_form_the_library_offers_is_ready(folder, readers):
    before = tree(folder)
    out = run("form-offered", readers, "campaign:survey")
    assert out.ok and "survey (custom) is ready" in out.message
    assert tree(folder) == before


def test_a_form_that_fails_or_is_unknown_is_not_offered(folder):
    nameless = StoreReaders(folder, community=Community(custom_form("bare", handler="")), today=TODAY)
    out = run("form-offered", nameless, "campaign:bare")
    assert not out.ok and "is failing" in out.message
    assert "names no form" in run("form-offered", nameless, "campaign:nothing").message
    assert not run("form-offered", nameless, "").ok
    assert not run("form-offered", StoreReaders(folder, community=Community(), today=TODAY), "campaign:survey").ok


def test_a_form_in_a_state_pack_without_its_statutes_on_the_shelf_fails_naming_the_recital(folder):
    class State(Community):
        def jurisdictions(self):
            return ("CA",)

    out = run("form-offered", StoreReaders(folder, community=State(), today=TODAY), "campaign:records-request")
    assert not out.ok and "not on the shelf" in out.message


def test_a_campaign_code_finds_its_form(folder, readers):
    from jason.tasks import campaigns

    path = folder / "forms"
    path.mkdir()
    (folder / campaigns.STORE).write_text(json.dumps({"SU99E": {"code": "SU99E", "form": "survey", "channel": "email", "year": 2099}}),
                                          encoding="utf-8")
    assert run("form-offered", readers, "campaign:SU99E").ok


# --- all of them, together --------------------------------------------------------------------------------------------

def test_no_read_changes_a_byte_of_a_populated_data_folder(folder, readers):
    sync(folder, D.DELIVERED, D.BOUNCED)
    sync(folder, D.DELIVERED, D.DELIVERED, notice=OWNER_INFO)
    notice_text.keep(folder, MEETING, kind="email", state="sent", body="<p>Hello</p>", subject="Subject")
    notice_text.keep(folder, OWNER_INFO, kind="email", state="sent", body="<p>Hello</p>", subject="Subject")
    requests_db(folder, ROWS)
    preview(folder, pages=3)
    sending(folder)
    before = tree(folder)
    subjects = {"notice-requirement-read": "notice:" + MEETING, "notice-owed-zero": "notice:" + MEETING,
                "notice-proof": "notice:" + OWNER_INFO, "notice-kept-text": "notice:" + MEETING, "mailroom-pages": "",
                "mailroom-batch-read": "", "requests-read": "", "answers-on-time": "", "request-classified": "request:101",
                "form-offered": "campaign:survey"}
    results = {name: run(name, readers, subject, event_on="2099-01-14") for name, subject in subjects.items()}
    assert set(results) == set(NAMES) and all(isinstance(r, CheckResult) and r.message for r in results.values())
    assert [n for n, r in results.items() if r.ok] == ["notice-requirement-read", "notice-proof", "notice-kept-text",
                                                       "mailroom-pages", "mailroom-batch-read", "requests-read", "answers-on-time",
                                                       "request-classified", "form-offered"]
    assert tree(folder) == before
