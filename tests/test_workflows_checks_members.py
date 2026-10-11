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
NEW = ("clock-authority-recited", "references-fill", "notice-elements", "kept-text-unchanged", "form-stale")
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

def test_the_members_module_registers_the_fifteen_reads_and_the_definitions_name_them():
    assert set(NAMES) | set(NEW) <= set(CHECKS)
    named = {s.check.name for b in defs.BUILDERS for s in b().steps if s.check is not None}
    assert named == set(NAMES) | set(NEW) | {"outstanding-read"}
    for b in defs.BUILDERS:
        for s in b().steps:
            if s.check is not None and s.check.name in NAMES + NEW:
                assert s.kind is StepKind.CHECK and s.role is Role.JASON, s.id
    assert not any(n in defs.WANTED for n in ("check " + x for x in NAMES + NEW))
    assert not [w for w in defs.WANTED if w.startswith("check ")]


@pytest.mark.parametrize("name", NAMES + NEW)
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


# --- the owner-document, authority, and stale-form reads (written after the first ten) -----------------------------------

DRAFT = "rule-change-proposed-example-2099-01-02"
TEXT_AND_EFFECT = ("NOTICE OF PROPOSED RULE CHANGE\n\nTHE TEXT OF THE PROPOSED RULE CHANGE\nSection 1: replace with a quiet-hours rule.\n\n"
                   "PURPOSE OF THE PROPOSED CHANGE\nMake the hours plain.\n\nEFFECT OF THE PROPOSED CHANGE\nOwners keep the hours.\n")


class DocCommunity(Community):
    """A profile that keeps no document as amended and states no fact: an outline on disk is the only document there is."""

    def living_documents(self):
        return ()

    def citable_documents(self):
        return ()

    def applicability_facts(self):
        return ()

    region = ""


@pytest.fixture
def docs(folder):
    return StoreReaders(folder, community=DocCommunity(custom_form()), today=TODAY)


def draft(folder, name, text):
    (folder / "drafts").mkdir(exist_ok=True)
    (folder / "drafts" / f"{name}.md").write_text(text, encoding="utf-8")


def rules_outline(folder):
    from jason.community.outlines import DocumentOutline, Section

    text = "B-1. Quiet Hours.\nResidents shall keep quiet hours from ten at night until seven in the morning."
    outline = DocumentOutline("rules", "Rules", kind="operating_rules", text=text, sections=[Section("B-1", "Quiet Hours.", 1, 0, len(text))])
    (folder / "outlines").mkdir(exist_ok=True)
    (folder / "outlines" / "rules.json").write_text(json.dumps(outline.to_dict()), encoding="utf-8")


def shelf(folder, sections, changed=None):
    """The authorities shelf of the folder: each made-up CIV section (its number and its words), and the change log."""
    where = folder / "authorities" / "CIV"
    where.mkdir(parents=True, exist_ok=True)
    pages = []
    for number, words in sections.items():
        file = f"authorities/CIV/CIV-{number}.md"
        (folder / file).write_text(f"# CIV {number}: made up\n\n- Source: California Legislature, 2025 session publication, read with "
                                   f"lawlibrary\n\n## CIV {number}\n\n- History: made up\n\n{number}. (Added by Stats. 2012, Ch. 1, "
                                   f"Sec. 1.)\n\n{words}\n", encoding="utf-8")
        pages.append({"file": file, "citation": f"CIV {number}", "title": "Made up", "code": "CIV", "start": number, "end": number,
                      "sections": [number], "basis": "a duty", "why": ["made up"], "session": "2025"})
    (folder / "authorities" / "manifest.json").write_text(json.dumps({"exported": "2099-01-01", "session": "2025", "pages": pages}),
                                                          encoding="utf-8")
    if changed:
        rows = [{"citation": f"CIV {n}", "old": "a" * 64, "new": "b" * 64, "when": when} for n, when in changed.items()]
        (folder / "authorities" / "changes.json").write_text(json.dumps(rows), encoding="utf-8")


# --- clock-authority-recited -----------------------------------------------------------------------------------------

def test_a_statute_clock_passes_when_the_section_is_on_the_shelf_and_is_never_fetched(folder, readers):
    requests_db(folder, ROWS)
    bare = run("clock-authority-recited", readers, "request:101")
    assert not bare.ok and "cannot recite" in bare.message and "CIV 5210 is not on the authorities shelf" in bare.message
    assert not (folder / "authorities").exists()                       # a miss is a miss: the on-demand export is not asked for
    shelf(folder, {"5210": "A made-up record rule."})
    before = tree(folder)
    out = run("clock-authority-recited", readers, "request:101")
    assert out.ok and "the words can be recited" in out.message and "CIV 5210 is on the shelf" in out.message
    assert out.evidence and tree(folder) == before


def test_a_kind_with_no_clock_row_has_no_authority_to_recite_and_no_due_day_is_made_up(folder, readers):
    requests_db(folder, ROWS)
    out = run("clock-authority-recited", readers, "request:105")
    assert out.ok and "the kind has no clock row" in out.message and "no due day is made up" in out.message
    assert not run("clock-authority-recited", readers, "request:999").ok
    assert not run("clock-authority-recited", readers, "").ok


def test_a_clock_that_is_a_proposed_policy_passes_saying_there_are_no_words_to_recite(folder):
    from jason.community.responses import ClockSource, ResponseKind, ResponseRule

    class Policy(DocCommunity):
        def response_rules(self):
            return (ResponseRule(ResponseKind.RECORDS, ClockSource.POLICY, days=10, authority="proposed policy (example); CIV 9901 asks "
                                 "the documents to say"),)

    requests_db(folder, ROWS)
    readers = StoreReaders(folder, community=Policy(), today=TODAY)
    out = run("clock-authority-recited", readers, "request:101")
    assert out.ok and "no words to recite" in out.message and "CIV 9901 (not on the shelf)" in out.message


def test_a_documents_clause_is_recited_from_the_document_as_kept(folder):
    from jason.community.responses import ClockSource, ResponseKind, ResponseRule

    class Documents(DocCommunity):
        def response_rules(self):
            return (ResponseRule(ResponseKind.RECORDS, ClockSource.DOCUMENTS, days=30, authority="rules#B-1"),)

    requests_db(folder, ROWS)
    rules_outline(folder)
    before = tree(folder)
    readers = StoreReaders(folder, community=Documents(), today=TODAY)
    out = run("clock-authority-recited", readers, "request:101")
    assert out.ok and "is in the document as kept" in out.message
    assert tree(folder) == before
    (folder / "outlines" / "rules.json").unlink()
    gone = run("clock-authority-recited", readers, "request:101")
    assert not gone.ok and "cannot recite" in gone.message


# --- references-fill -------------------------------------------------------------------------------------------------

def test_every_reference_in_the_draft_fills_from_the_document_as_kept(folder, docs):
    rules_outline(folder)
    draft(folder, "welcome", "Quiet hours: {QUOTE:rules#B-1}\n\nSee {CITE:rules#B-1} for more.\n")
    before = tree(folder)
    out = run("references-fill", docs, "document:welcome")
    assert out.ok and out.message == "2 references fill (1 quoted, 1 cited)"
    assert out.evidence and out.evidence[0].startswith("file:drafts/welcome.md@")
    assert tree(folder) == before                                       # nothing was rendered, kept, or cached
    draft(folder, "plain", "No tokens here.\n")
    assert run("references-fill", docs, "document:plain").message == "data/drafts/plain.md has no reference to fill"


def test_references_that_do_not_fill_are_all_named_at_once(folder, docs):
    rules_outline(folder)
    draft(folder, "welcome", "{QUOTE:rules#Z-9} and {CITE:nodoc#1} and {CITE:rules#B-1}\n")
    out = run("references-fill", docs, "document:welcome")
    assert not out.ok and out.message.startswith("2 references of 3 do not fill:")
    assert "rules has no section Z-9" in out.message and "no document 'nodoc'" in out.message


def test_a_draft_that_is_missing_or_is_a_path_is_not_read(folder, docs):
    assert "no draft data/drafts/nothing.md" in run("references-fill", docs, "document:nothing").message
    outside = run("references-fill", docs, "document:../secret")
    assert not outside.ok and "not a draft's name" in outside.message
    draft(folder, "welcome", "{CITE:rules#B-1}")

    class Nobody(StoreReaders):
        @property
        def community(self):
            raise RuntimeError("no community is chosen")

    out = run("references-fill", Nobody(folder, today=TODAY), "document:welcome")
    assert not out.ok and "no community is chosen" in out.message


# --- notice-elements -------------------------------------------------------------------------------------------------

def test_a_notice_draft_named_with_its_requirements_key_has_its_elements_checked(folder, docs):
    draft(folder, DRAFT, TEXT_AND_EFFECT)
    before = tree(folder)
    out = run("notice-elements", docs, "document:" + DRAFT)
    assert out.ok and out.message.startswith("rule-change-proposed: 2 of 2 elements shown, 0 missing")
    assert tree(folder) == before
    draft(folder, DRAFT, "A friendly hello.\n")
    bare = run("notice-elements", docs, "document:" + DRAFT)
    assert not bare.ok and "2 missing" in bare.message and "(CIV 4360(a))" in bare.message and "friendly" not in bare.message


def test_the_item_names_the_requirement_when_the_documents_name_does_not(folder, docs):
    draft(folder, "welcome", TEXT_AND_EFFECT)
    assert "starts with no requirement's key" in run("notice-elements", docs, "document:welcome").message
    assert run("notice-elements", docs, "document:welcome", item="rule-change-proposed").ok
    assert "not a notice requirement" in run("notice-elements", docs, "document:welcome", item="no-such-notice").message
    assert not run("notice-elements", docs, "").ok
    assert "no draft" in run("notice-elements", docs, "document:" + DRAFT).message


# --- kept-text-unchanged ---------------------------------------------------------------------------------------------

def test_the_kept_words_are_unchanged_until_a_kept_file_is_edited_or_gone(folder, docs):
    assert "no text is kept" in run("kept-text-unchanged", docs, "document:" + DRAFT).message
    notice_text.keep(folder, DRAFT, kind="email", state="sent", body="<p>Hello</p>", subject="Subject")
    before = tree(folder)
    out = run("kept-text-unchanged", docs, "document:" + DRAFT)
    assert out.ok and out.message == "1 file kept in 1 keeping, each unchanged since"
    assert tree(folder) == before
    assert run("kept-text-unchanged", docs, "", item=DRAFT).ok                      # the item names the key as well
    assert run("kept-text-unchanged", docs, "notice:" + DRAFT).ok
    (folder / "notices" / DRAFT / "message.html").write_text("<p>Changed</p>", encoding="utf-8")
    edited = run("kept-text-unchanged", docs, "document:" + DRAFT)
    assert not edited.ok and "EDITED or gone since it was kept: message.html" in edited.message
    (folder / "notices" / DRAFT / "message.html").unlink()
    assert not run("kept-text-unchanged", docs, "document:" + DRAFT).ok
    assert not run("kept-text-unchanged", docs, "").ok and "no text is kept" in run("kept-text-unchanged", docs, "document:Bad Key").message


def test_a_markdown_source_newer_than_the_keeping_is_said_and_does_not_fail(folder, docs):
    import os

    notice_text.keep(folder, DRAFT, kind="email", state="sent", body="<p>Hello</p>", subject="Subject")
    draft(folder, DRAFT, "edited later")
    os.utime(folder / "drafts" / f"{DRAFT}.md", (4_102_444_800, 4_102_444_800))         # 2100-01-01
    out = run("kept-text-unchanged", docs, "document:" + DRAFT)
    assert out.ok and "is newer than the last keeping" in out.message


# --- form-stale ------------------------------------------------------------------------------------------------------

def stale_readers(folder, **kw):
    return StoreReaders(folder, community=DocCommunity(custom_form("survey", **kw)), today=TODAY)


def test_a_form_that_recites_nothing_cannot_be_stale(folder):
    out = run("form-stale", stale_readers(folder), "campaign:survey")
    assert out.ok and "recites no statute or clause" in out.message


def test_a_form_whose_recitals_are_unchanged_since_its_day_is_not_stale(folder):
    shelf(folder, {"9901": "The made-up association shall do a thing."}, changed={"9901": "2098-12-01T00:00:00+00:00"})
    before = tree(folder)
    out = run("form-stale", stale_readers(folder, recitals=("CIV 9901",), as_of=date(2099, 1, 1)), "campaign:survey")
    assert out.ok and "recites 1 section as of 2099-01-01" in out.message and "no change logged" in out.message
    assert tree(folder) == before


def test_a_form_is_stale_when_the_shelf_logged_a_change_after_its_day(folder):
    shelf(folder, {"9901": "The made-up association shall do a thing."}, changed={"9901": "2099-02-01T00:00:00+00:00"})
    out = run("form-stale", stale_readers(folder, recitals=("CIV 9901",), as_of=date(2099, 1, 1)), "campaign:survey")
    assert not out.ok and "1 recital changed on the shelf since: CIV 9901" in out.message and "bump its version" in out.message


def test_recitals_that_cannot_be_read_or_have_no_day_cannot_be_judged(folder):
    off = run("form-stale", stale_readers(folder, recitals=("CIV 9902",), as_of=date(2099, 1, 1)), "campaign:survey")
    assert not off.ok and "cannot be read, so staleness is not known: CIV 9902" in off.message
    undated = run("form-stale", stale_readers(folder, recitals=("CIV 9902",)), "campaign:survey")
    assert not undated.ok and "no as-of day" in undated.message
    assert not run("form-stale", stale_readers(folder), "campaign:nothing").ok
    assert not run("form-stale", stale_readers(folder), "").ok


# --- all the new reads, one folder -------------------------------------------------------------------------------------

def test_the_new_reads_change_no_byte_of_a_populated_folder_and_none_is_ok_by_default(folder):
    requests_db(folder, ROWS)
    rules_outline(folder)
    shelf(folder, {"5210": "A made-up record rule.", "9901": "A made-up rule."}, changed={"9901": "2099-02-01T00:00:00+00:00"})
    draft(folder, DRAFT, TEXT_AND_EFFECT + "\n{CITE:rules#B-1}\n")
    notice_text.keep(folder, DRAFT, kind="email", state="sent", body="<p>Hello</p>", subject="Subject")
    readers = StoreReaders(folder, community=DocCommunity(custom_form("survey", recitals=("CIV 9901",), as_of=date(2099, 1, 1))),
                           today=TODAY)
    before = tree(folder)
    subjects = {"clock-authority-recited": "request:101", "references-fill": "document:" + DRAFT,
                "notice-elements": "document:" + DRAFT, "kept-text-unchanged": "document:" + DRAFT, "form-stale": "campaign:survey"}
    got = {name: run(name, readers, subject) for name, subject in subjects.items()}
    assert [n for n, r in got.items() if r.ok] == ["clock-authority-recited", "references-fill", "notice-elements", "kept-text-unchanged"]
    assert not got["form-stale"].ok
    assert tree(folder) == before
    empty = StoreReaders(folder.parent / "nothing-here", community=DocCommunity(), today=TODAY)
    for name in NEW:
        assert CHECKS[name](empty, view(""), "").ok is False
    assert not (folder.parent / "nothing-here").exists()
