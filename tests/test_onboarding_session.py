"""Onboarding as a session: questions ranked by what each answer unblocks, FACT and MAP questions from the checklist,
and answers that become records (private facts with a backup, Keeper notes, proposed profile patches), with a secret
refused and a high-stakes answer held for a second person. A made-up profile and a made-up queue throughout."""

import importlib.util
import json
import sys
from types import SimpleNamespace

import pytest

from jason import api
from jason.community import Community, intake
from jason.community.base import BoardRule
from jason.community.books import Book, BookEntry, Books
from jason.community.intake import Ask, AskKind, AskStatus
from jason.community.intake_rank import (
    CLOCK, Citing, Unblocks, priority, rank, reading_matters, relation, section_weight,
)
from jason.community.onboarding import (
    ITEMS, Context, Fact, FactRecord, Settled, Stage, Status, Verified, check, gates, item,
)
from jason.community.symbols import AssociationRecord
from jason.tasks import intake as intake_task
from jason.tasks import onboarding_answers as answers
from jason.tasks import onboarding_session as session


def _stub_class():
    members = {name: (lambda self, *a, **k: ()) for name in Community.__abstractmethods__}
    members.update(
        name="Oakview Example Association", slug="oakview", org_id=0, root=None,
        document_sync_rules=lambda self: {"rules": [], "exclude": []},
        board=lambda self: BoardRule(seats=3, minimum=3, maximum=3),
        book_entries=lambda self: (BookEntry("example-declaration", Book.DECL),),
        units=lambda self: ("100 MAIN ST", "102 MAIN ST"),
    )
    return type("Oakview", (Community,), members)


def _ask(kind, subject, **kw):
    return Ask(intake.ask_id(kind, subject, kw.pop("key", "")), kind, subject, "?", **kw)


# --- Ranking ----------------------------------------------------------------------------------------------------------

def test_the_queue_ranks_a_clock_then_a_missing_item_then_a_cited_section_then_quality():
    clock = _ask(AskKind.OCR_READING, "decl#4.2(a)", key="1")
    fact = _ask(AskKind.FACT, "fact:tax-id")
    partial = _ask(AskKind.MAP, "book:arts")
    gate = _ask(AskKind.CLASSIFY, "library:Folder/x.pdf")
    cited = _ask(AskKind.OCR_READING, "decl#7.1", key="2")
    uncited = _ask(AskKind.OCR_READING, "decl#9.9", key="3")
    unblocks = {
        clock.id: Unblocks(clocks=("notice:board-meeting",), sections=("decl#4.2(a)",), weight=3),
        fact.id: Unblocks(items=(("tax-id", "missing"),)),
        partial.id: Unblocks(items=(("articles", "partial"),), records=("book arts",)),
        gate.id: Unblocks(gates=("ingest",)),
        cited.id: Unblocks(sections=("decl#7.1",), weight=40),
        uncited.id: Unblocks(sections=("decl#9.9",), quality=True),
    }
    order = [r.ask.id for r in rank([uncited, cited, gate, partial, fact, clock], unblocks)]
    assert order == [clock.id, fact.id, partial.id, gate.id, cited.id, uncited.id]
    # A lower tier never adds up to a higher one: every citation there is stays under a stage gate, nine missing
    # items under one clock.
    assert priority(Unblocks(weight=10_000)) < priority(Unblocks(gates=("ingest",)))
    assert priority(Unblocks(items=tuple((f"i{n}", "missing") for n in range(20)))) < CLOCK


def test_citations_weigh_a_section_by_what_cites_it():
    citing = [Citing("4.2", "notice provision", "notice:board-meeting"), Citing("4.2(a)", "conflict row", "conflict:x"),
              Citing("4", "governing document"), Citing("4.2(a)(1)", "document duty", "duty:y"),
              Citing("5.1", "governing document")]
    weight, clocks = section_weight("4.2(a)", citing)
    # the enclosing section's notice at half, the section's own conflict in full, the article at a fifth, a part
    # inside it at a quarter; another section not at all
    assert weight == pytest.approx(3.0 * 0.5 + 4.0 + 1.0 * 0.2 + 2.0 * 0.25)
    assert clocks == ("notice:board-meeting",)
    assert relation("4", "4.2(a)") == 0.0                 # an article's own words are its heading, not its sections
    assert section_weight("9.9", citing) == (0.0, ())


def test_an_ocr_reading_that_only_respaces_or_is_likely_sets_no_clock():
    assert not reading_matters({"wrong": "ofthe Units", "right": "of the Units"}, likely=False)
    assert not reading_matters({"wrong": "or", "right": "OR"}, likely=False)
    assert not reading_matters({"wrong": "Condommmms", "right": "Condominiums"}, likely=True)
    assert reading_matters({"wrong": "thirty (3O) days", "right": "thirty (30) days"}, likely=True)   # a digit
    assert reading_matters({"wrong": "its deems", "right": "it deems"}, likely=False)
    cited = {"decl": [Citing("4.2", "notice provision", "notice:board-meeting")]}
    slip = _ask(AskKind.OCR_READING, "decl#4.2", detail={"wrong": "ofthe", "right": "of the"})
    found = session.unblocks_for(slip, status={}, groups={}, gate_results=(), cited=cited)
    assert found.weight == 3.0 and not found.clocks        # still cited, but no clock waits on a respacing


# --- FACT and MAP questions --------------------------------------------------------------------------------------------

@pytest.fixture
def ctx(tmp_path):
    return Context(community=_stub_class()(), library=({"kind": "articles", "path": "Corporate/Articles.pdf", "id": 1},),
                   profile="oakview", private=lambda name: {})


def test_facts_are_asked_for_the_missing_items_a_person_supplies(ctx, tmp_path):
    results = check(ctx)
    facts = {a.serves: a for a in session.fact_asks(results, ctx, tmp_path)}
    status = {r.item.key: r.status for r in results}
    assert {"tax-id", "signers", "keys-and-codes", "loans"} <= set(facts)
    assert all(a.kind is AskKind.FACT and a.subject == f"fact:{k}" for k, a in facts.items())
    assert "board-rule" not in facts and status["board-rule"] is Status.PRESENT       # present: nothing to ask
    assert facts["signers"].stakes and intake.high_stakes(facts["signers"])
    assert facts["keys-and-codes"].detail["record"] == FactRecord.KEEPER.value
    assert "never a password or code" in facts["keys-and-codes"].question
    assert facts["tax-id"].detail["record"] == FactRecord.PRIVATE.value
    assert any("checklist tax-id is missing" in e for e in facts["tax-id"].evidence)


def test_a_book_no_document_fills_is_asked_as_a_map(ctx, tmp_path):
    maps = {a.subject: a for a in session.map_asks(check(ctx), ctx, tmp_path)}
    arts = maps["book:arts"]
    assert arts.kind is AskKind.MAP and arts.serves == "articles"
    assert arts.suggestion == "library:Corporate/Articles.pdf"
    assert "book:decl" not in maps                                       # the declaration is mapped


def test_a_fact_lead_suggests_an_answer_from_the_library(tmp_path):
    (tmp_path / "library" / "text").mkdir(parents=True)
    (tmp_path / "library" / "text" / "7.txt").write_text("Employer identification number 00-0000000", encoding="utf-8")
    ctx = Context(community=_stub_class()(), library=({"kind": "tax_return", "path": "Tax/2099.pdf", "id": 7},),
                  profile="oakview")
    tax = next(a for a in session.fact_asks(check(ctx), ctx, tmp_path) if a.serves == "tax-id")
    assert tax.suggestion == "00-0000000"
    assert any("Tax/2099.pdf" in e for e in tax.evidence)


# --- Answers ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text", ["password: example-only", "the gate code is 4471", "PIN 1234",
                                  "kEy0123456789abcdefGHIJ", "api key: abc"])
def test_a_secret_is_refused_and_never_stored(tmp_path, text):
    ask = _ask(AskKind.FACT, "fact:keys-and-codes")
    intake.save(tmp_path, [ask])
    with pytest.raises(intake.SecretRefused):
        intake.answer([ask], ask.id, text, "A Person")
    out = api.answer_intake_question(ask.id, text, by="A Person", data_dir=tmp_path)
    assert "error" in out and "Keeper" in out["error"]
    assert text not in (tmp_path / "intake" / "asks.json").read_text(encoding="utf-8")
    assert intake.load(tmp_path)[0].status is AskStatus.OPEN


def test_a_keeper_answer_records_the_record_name_and_no_value(tmp_path):
    ask = _ask(AskKind.FACT, "fact:keys-and-codes", serves="keys-and-codes",
               detail={"item": "keys-and-codes", "record": FactRecord.KEEPER.value})
    intake.answer([ask], ask.id, "Keeper record: association keys and codes", "A Person")
    out = answers.apply_fact(ask, profile="oakview", data_dir=tmp_path, spec_dir=tmp_path / "spec")
    stored = json.loads((tmp_path / "spec" / "oakview.json").read_text(encoding="utf-8"))["facts"]["keys-and-codes"]
    assert out.applied and stored["kept_in"] == "Keeper" and stored["record"].startswith("Keeper record")
    assert stored["answered_by"] == "A Person" and "answer" not in stored


def test_a_high_stakes_answer_waits_for_a_second_person(tmp_path):
    ask = _ask(AskKind.FACT, "fact:signers", serves="signers", stakes=True,
               detail={"item": "signers", "record": FactRecord.PRIVATE.value})
    asks = [ask]
    intake.answer(asks, ask.id, "two directors sign; the board approves transfers over the limit", "A Person")
    refused: list = []
    assert intake_task.apply(asks, tmp_path, refused=refused, profile="oakview", spec_dir=tmp_path / "spec") == []
    assert refused and "second person" in refused[0][1] and ask.status is AskStatus.ANSWERED
    with pytest.raises(ValueError):
        intake.confirm(asks, ask.id, "a person")                     # the one who answered, in any case
    intake.confirm(asks, ask.id, "B Person")
    done = intake_task.apply(asks, tmp_path, profile="oakview", spec_dir=tmp_path / "spec")
    assert done == [ask] and ask.status is AskStatus.APPLIED
    fact = json.loads((tmp_path / "spec" / "oakview.json").read_text(encoding="utf-8"))["facts"]["signers"]
    assert fact["answered_by"] == "A Person" and fact["confirmed_by"] == "B Person"
    # A new answer clears the confirmation: the second person confirms what was answered.
    intake.answer(asks, ask.id, "another answer", "A Person")
    assert ask.confirmed_by == ""


def test_a_private_fact_merges_with_a_backup_and_is_never_overwritten_silently(tmp_path):
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "oakview.json").write_text(json.dumps({"other": {"kept": True}}), encoding="utf-8")
    ask = _ask(AskKind.FACT, "fact:tax-id", serves="tax-id", detail={"item": "tax-id", "record": "private facts"})
    intake.answer([ask], ask.id, "00-0000000", "A Person")
    out = answers.apply_fact(ask, profile="oakview", data_dir=tmp_path, spec_dir=spec)
    data = json.loads((spec / "oakview.json").read_text(encoding="utf-8"))
    assert out.applied and data["other"] == {"kept": True} and data["facts"]["tax-id"]["answer"] == "00-0000000"
    assert len(list((spec / "backups").glob("oakview-*.json"))) == 1
    assert out.shown.startswith("--- oakview.json (before)") and '"answer": "00-0000000"' in out.shown
    assert '-{"other": {"kept": true}}\n' in out.shown
    # The same answer again changes nothing; a different one is refused without --replace.
    assert answers.apply_fact(ask, profile="oakview", data_dir=tmp_path, spec_dir=spec).applied
    intake.answer([ask], ask.id, "11-1111111", "B Person")
    held = answers.apply_fact(ask, profile="oakview", data_dir=tmp_path, spec_dir=spec)
    assert not held.applied and "--replace" in held.reason
    assert json.loads((spec / "oakview.json").read_text(encoding="utf-8"))["facts"]["tax-id"]["answer"] == "00-0000000"
    assert answers.apply_fact(ask, profile="oakview", data_dir=tmp_path, spec_dir=spec, replace=True).applied
    # The checklist sees the recorded fact, by count only.
    facts = json.loads((spec / "oakview.json").read_text(encoding="utf-8"))
    ctx = Context(community=_stub_class()(), profile="oakview", private=lambda name: facts if name == "oakview" else {})
    found = Fact("tax-id").run(ctx)
    assert found.passed and "11-1111111" not in found.evidence


PROFILE_BOOKS = '''from jason.community.books import Book, BookEntry

BOOK_ENTRIES: tuple[BookEntry, ...] = (
    BookEntry("example-declaration", Book.DECL),
)
'''

PROFILE_ANCHORS = '''LIBRARY = (
    LibraryFolder(PayhoaFolder.MEETINGS, 1, "Meetings/", records=(AssociationRecord.MINUTES,)),
    LibraryFolder(PayhoaFolder.LEGAL, 2, "Legal/"),
)
'''


@pytest.fixture
def profile_pkg(tmp_path):
    """A made-up profile package on disk, and an object whose class lives in it."""
    pkg = tmp_path / "oakview"
    pkg.mkdir()
    (pkg / "books.py").write_text(PROFILE_BOOKS, encoding="utf-8")
    (pkg / "anchors.py").write_text(PROFILE_ANCHORS, encoding="utf-8")
    (pkg / "community.py").write_text("class Oakview:\n    name = 'Oakview Example Association'\n", encoding="utf-8")
    spec = importlib.util.spec_from_file_location("oakview_community_test", pkg / "community.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[spec.name] = module
    yield pkg, module.Oakview()
    sys.modules.pop(spec.name, None)


def test_a_mapping_answer_becomes_a_patch_and_the_profile_is_not_edited(tmp_path, profile_pkg):
    pkg, community = profile_pkg
    before = (pkg / "books.py").read_text(encoding="utf-8")
    ask = _ask(AskKind.MAP, "book:arts", serves="articles",
               detail={"map": "book", "book": "arts", "item": "articles", "outlines": ["example-articles"], "files": []})
    intake.answer([ask], ask.id, "example-articles", "A Person")
    out = answers.propose(ask, data_dir=tmp_path / "data", community=community)
    patch = tmp_path / "data" / "onboarding" / "proposals" / f"{ask.id}.patch"
    assert out.applied and patch.is_file() and (pkg / "books.py").read_text(encoding="utf-8") == before
    text = patch.read_text(encoding="utf-8")
    assert "diff --git a/oakview/books.py b/oakview/books.py" in text
    assert '+    BookEntry("example-articles", Book.ARTS, note="mapped from intake question' in text
    assert "A Person" in text.split("diff --git", 1)[0]            # the header names who answered
    assert "A Person" not in text.split("diff --git", 1)[1]        # the row in the profile never names a person


def test_a_record_pin_answer_edits_the_folders_row_in_a_patch(tmp_path, profile_pkg):
    pkg, community = profile_pkg
    ask = _ask(AskKind.MAP, "record:vendor_approval", detail={"map": "record", "record": "vendor_approval",
                                                               "folders": ["Meetings/"]})
    intake.answer([ask], ask.id, "Meetings/", "A Person")
    out = answers.propose(ask, data_dir=tmp_path / "data", community=community)
    assert out.record.endswith(".patch")
    assert "records=(AssociationRecord.VENDOR_APPROVAL, AssociationRecord.MINUTES,)" in out.shown
    assert answers.pin_record(pkg, "Legal/", "tax_return")[2].count("records=(AssociationRecord.TAX_RETURN,)") == 1


def test_a_profile_fact_jason_cannot_write_is_proposed_for_a_person(tmp_path, profile_pkg):
    _, community = profile_pkg
    ask = _ask(AskKind.FACT, "fact:board-rule", serves="board-rule",
               detail={"item": "board-rule", "record": FactRecord.PROFILE.value, "method": "board"})
    asks = [ask]
    intake.answer(asks, ask.id, "five seats, two-year terms, quorum three", "A Person")
    shown: list = []
    done = intake_task.apply(asks, tmp_path / "data", shown=shown, community=community)
    proposal = tmp_path / "data" / "onboarding" / "proposals" / f"{ask.id}.md"
    assert done == [ask] and proposal.is_file() and "Community.board()" in proposal.read_text(encoding="utf-8")
    assert not (tmp_path / "spec").exists()                          # a profile fact is not a private fact


# --- The governance tools ---------------------------------------------------------------------------------------------

def test_the_session_tools_read_and_write_nothing(tmp_path):
    status = api.onboarding_status(data_dir=tmp_path)
    assert [g["stage"] for g in status["gates"]] == [s.value for s in Stage]
    assert sum(status["progress"].values()) == len(ITEMS)
    found = api.next_questions(limit=50, data_dir=tmp_path)
    facts = [q for q in found["questions"] if q["kind"] == "fact"]
    assert facts and all(not q["inQueue"] and q["unblocks"]["items"] for q in facts)
    assert found["questions"] == sorted(found["questions"], key=lambda q: -q["priority"])
    assert "error" in api.next_questions(stage="no-such-stage", data_dir=tmp_path)
    assert not [p for p in tmp_path.rglob("*") if p.is_file()]


# --- Gates ------------------------------------------------------------------------------------------------------------

def test_the_establish_gate_waits_on_an_open_question_about_which_text_is_in_force():
    drift = _ask(AskKind.DRIFT, "example-declaration#4.2")
    other = _ask(AskKind.DRIFT, "some-guide#1.1")
    holding = SimpleNamespace(kind=AssociationRecord.GOVERNING_DOCUMENTS, pinned=True, documents=1, gap="",
                              notes=["Declaration.pdf: recorded as 209901010001, recorded", "Copy.pdf: no stamp read; verify the copy"])
    ctx = Context(community=_stub_class()(), asks=(drift, other), holdings=(holding,))
    found = {g.gate.stage: g for g in gates(check(ctx), ctx)}
    establish = found[Stage.ESTABLISH]
    assert not establish.open
    assert "intake: 1 open" in establish.evidence                     # the guide is not a governing document
    assert "1 read without a stamp" in establish.evidence
    assert Settled(("drift",), governing=True).counts(drift, Books.of(ctx.community))
    assert not Verified().run(Context(community=_stub_class()())).passed
    assert item("signers").ask.stakes
