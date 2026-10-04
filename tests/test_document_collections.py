"""A collection in the context pack: a legal case's file as its own tier, refused to a member's task, and reviews kept
side by side. Everything here is made up."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from jason.community import passage_index as pi
from jason.community import retrieval
from jason.community.context_pack import COLLECTION_PASSAGES, COLLECTION_PER_FILE, CORPUS, assemble
from jason.community.document_collections import Collection, CollectionKind, ad_hoc, collection, collections
from jason.community.legal_cases import CaseDuty, CaseEvent, CaseRole, CaseStatus, Forum, LegalCase
from jason.community.prompts import Audience, FactSource, TaskKind, TaskPrompt, system_prompt, task_text, verify
from jason.community.symbols import DocumentKind
from jason.tasks import review_store
from jason.tasks.case_files import catalog_name, index_sources
from jason.tasks.manager_review import messages, save_pack, save_review

GOVERNING = CORPUS[1][0]
GOLDEN = Path(__file__).parent / "fixtures" / "context_pack" / "no_collection.md"

KEY = "example-26cv000001"
CASE = LegalCase(
    KEY, "Example v. Example Commons", Forum.SUPERIOR_COURT, CaseRole.DEFENDANT, CaseStatus.PENDING,
    case_number="26CV000001", drive_folder="26CV000001 - Example",
    events=(CaseEvent(date(2026, 1, 5), "complaint served on the association", "the case file: Complaint.pdf"),
            CaseEvent(date(2026, 3, 2), "hearing on the demurrer first set")),
    duties=(CaseDuty("CIV 4935(a)", "litigation is considered in executive session", met=True, evidence="minutes of January 12, 2026"),
            CaseDuty("CCP 430.40(a)", "respond to the complaint", due=date(2026, 2, 4))))
NO_FOLDER = LegalCase("other", "A lien with no case file", Forum.RECORDED_LIEN, CaseRole.CLAIMANT, CaseStatus.CLOSED)

NOTICE = ("## Notice\n\nThe hearing on the demurrer is set for March 2, 2026 at 9:00 a.m. in Department 53.\n\n"
          "## Tentative ruling\n\nA tentative ruling on the demurrer hearing is posted the court day before the hearing.\n\n"
          "## Appearance\n\nA party may appear at the hearing on the demurrer by remote means with notice.\n\n"
          "## Service\n\nThe notice of the hearing on the demurrer was served by mail on February 3, 2026.\n")
ORDER = "The court continued the hearing on the demurrer to April 6, 2026 and ordered the parties to meet and confer."
PHOTOS = "Photographs of the garage door taken on January 2, 2026, numbered one to twelve."
CCR = "Each Owner shall keep refuse containers inside the Unit except on the day of collection."
RULE = "Rule 4. Refuse containers shall be returned to the garage by evening on the day of collection."
ASK = "When is the hearing on the demurrer, and was the hearing continued?"

TASK = TaskPrompt(TaskKind.RULE_REMINDER, "A reminder of a rule.", Audience.BOARD,
                  topics=("where refuse containers are kept", "the hearing before a fine"),
                  documents=(DocumentKind.DECLARATION, DocumentKind.OPERATING_RULES, DocumentKind.CORRESPONDENCE),
                  facts=(FactSource("open_items", why="what is open"),),
                  considerations=("Does it say how an owner can respond?",))
LETTER = ("Courtesy letter.pdf", "2025-06", "A courtesy reminder about refuse containers left out after collection.")


class FakeEmbedder:
    def _vec(self, text: str) -> list[float]:
        v = [0.0] * 16
        for word in text.lower().split():
            v[int(hashlib.md5(word.encode()).hexdigest(), 16) % 16] += 1.0
        return retrieval._normalize(v)

    def embed_passages(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


class Community:
    """A made-up association: its context lines, a file's kind, and one legal case with a case file."""

    def prompt_context(self):
        return ["Example Commons, 12 units"]

    def classify_document(self, name, folder=None):
        if name.startswith("CCRs"):
            return DocumentKind.DECLARATION
        if "Rules" in name:
            return DocumentKind.OPERATING_RULES
        return None

    def legal_cases(self):
        return (CASE, NO_FOLDER)


def _page(data: Path, file: str, citation: str, title: str, sections: dict[str, str]) -> dict:
    body = f"# {citation}: {title}\n\n- Source: a made-up session\n\n" + "".join(f"## {c}\n\n{t}\n\n" for c, t in sections.items())
    (data / file).parent.mkdir(parents=True, exist_ok=True)
    (data / file).write_text(body, encoding="utf-8")
    return {"file": file, "citation": citation, "title": title, "code": citation.split()[0], "start": "", "end": "",
            "sections": list(sections), "basis": "duty", "why": [], "session": "2025"}


def _kind(name: str) -> str:
    return "notice" if name.startswith("Notice") else "order" if name.startswith("Minute") else ""


@pytest.fixture()
def data(tmp_path: Path) -> Path:
    pages = [_page(tmp_path, "authorities/CIV/CIV-5850-5875.md", "CIV 5850-5875", "Article 2. Discipline", {
        "CIV 5850": "The board shall adopt and distribute a schedule of monetary penalties.",
        "CIV 5855": "The member shall be notified of the hearing before a fine is imposed.",
    })]
    (tmp_path / "authorities" / "manifest.json").write_text(json.dumps({"pages": pages}), encoding="utf-8")
    governing = tmp_path / GOVERNING
    governing.mkdir(parents=True)
    (governing / "CCRs.md").write_text(CCR, encoding="utf-8")
    (governing / "Owner Rules.md").write_text(RULE, encoding="utf-8")
    files = tmp_path / "cases" / KEY / "files"
    files.mkdir(parents=True)
    (files / "Notice of hearing.txt").write_text(NOTICE, encoding="utf-8")
    (files / "Minute order.md").write_text(ORDER, encoding="utf-8")
    (files / "Minute order (copy).md").write_text(ORDER, encoding="utf-8")
    (files / "Photo log.txt").write_text(PHOTOS, encoding="utf-8")
    return tmp_path


SOURCES = (pi.IndexSource("records", GOVERNING, pi.Standing.RECORD),
           pi.IndexSource("authorities", "authorities", pi.Standing.AUTHORITY),
           *index_sources((CASE, NO_FOLDER)))


def _build(data: Path) -> None:
    pi.build(data, sources=SOURCES, embedder=FakeEmbedder(), kind_of=_kind)


def _pack(data: Path, task: TaskPrompt = TASK, **kw):
    return assemble(Community(), task, data, mode="keyword",
                    files=lambda kind: [LETTER] if kind is DocumentKind.CORRESPONDENCE else [],
                    fact_runner=lambda tool, args: {"tool": tool, "open": 2}, **kw)


def _after_task(page: str) -> str:
    return page[page.index("## Task"):]


def test_without_a_collection_the_pack_is_what_it_was(data):
    """The page below was written by the pack as it stood before collections (JASON_WRITE_GOLDEN=1 writes it again
    after a change to the prompts or the pack that is meant to move it)."""
    _build(data)
    pack = _pack(data, draft="Dear Owners, the refuse containers go back in the garage by evening.")
    page = pack.markdown()
    told = _after_task(page) + "\n=== sources_text ===\n" + pack.sources_text() + "\n"
    if os.environ.get("JASON_WRITE_GOLDEN"):
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(told, encoding="utf-8", newline="\n")
    assert told == GOLDEN.read_text(encoding="utf-8")
    assert page.startswith("# Courtesy reminder of a rule\n\n## Base prompt\n\n" + system_prompt(("Example Commons, 12 units",)) + "\n\n## Task\n")
    assert not pack.gaps and not any(s.id.startswith("C") for s in pack.sources)
    assert pack.task_prompt() == task_text(TASK, draft=pack.draft)


# --- the record -----------------------------------------------------------------------------------------------------

def test_a_legal_case_with_a_case_file_is_a_collection():
    (found,) = collections(Community())                       # the case with no Drive folder has no file to review
    assert (found.key, found.kind, found.confidential) == (KEY, CollectionKind.LEGAL_CASE, True)
    assert found.scope.catalogs == (catalog_name(CASE),) == found.scope.confidential_in
    assert "neither the record nor the law" in found.label
    assert found.context[:4] == ("Matter: Example v. Example Commons", "Forum: Superior Court",
                                 "The association's role: defendant", "Status: pending")
    assert "2026-01-05: complaint served on the association (recorded: the case file: Complaint.pdf)" in found.context
    assert "2026-03-02: hearing on the demurrer first set" in found.context
    assert ("Duty (CIV 4935(a)): litigation is considered in executive session. The record shows it met. "
            "(minutes of January 12, 2026)") in found.context
    assert ("Duty (CCP 430.40(a)), due 2026-02-04: respond to the complaint. The record does not show it either way."
            in found.context)
    # Only what the record holds for the whole matter: no number, party, counsel, or figure is added.
    assert not any("26CV000001" in line for line in found.context)


def test_a_collection_is_found_by_its_case_key_or_its_catalog_name():
    assert collection(Community(), KEY).key == KEY
    assert collection(Community(), f" CASE-{KEY} ").key == KEY
    assert collection(Community(), "other") is None and collection(Community(), "") is None     # a miss stays a miss


def test_an_ad_hoc_collection_is_the_filters_a_person_names():
    found = ad_hoc(catalogs=("records",), kinds=(DocumentKind.MINUTES, "notice"), folders=("governing",))
    assert found.kind is CollectionKind.AD_HOC and not found.confidential
    assert found.scope == pi.Scope(catalogs=("records",), kinds=("minutes", "notice"), folders=("governing",))
    assert found.key.startswith("ad-hoc-") and found.key == ad_hoc(catalogs=["records"], kinds=["minutes", "notice"], folders=["governing"]).key
    assert found.title == "catalogs records; kinds minutes, notice; folders governing" and not found.context
    assert ad_hoc(kinds=("minutes",), title="The minutes").title == "The minutes"
    # A case's catalog named opens that case's files, and no other catalog's; the collection is then confidential.
    case = ad_hoc(catalogs=("library", catalog_name(CASE)))
    assert case.confidential and case.scope.confidential_in == (catalog_name(CASE),) and not case.scope.confidential
    held = ad_hoc(catalogs=("library",), confidential=True)
    assert held.confidential and held.scope.confidential_in == ("library",) and held.key != ad_hoc(catalogs=("library",)).key
    with pytest.raises(ValueError, match="a catalog, a kind, or a folder"):
        ad_hoc()
    with pytest.raises(ValueError, match="name the catalogs"):
        ad_hoc(kinds=("minutes",), confidential=True)


# --- the pack -------------------------------------------------------------------------------------------------------

def _case() -> Collection:
    return collection(Community(), KEY)


def test_a_board_task_s_pack_gives_the_case_file_its_own_tier(data):
    _build(data)
    pack = _pack(data, ask=ASK, collection=_case())
    c = [s for s in pack.sources if s.id.startswith("C")]
    assert c and pack.collection_included and not pack.gaps
    assert all(s.label == "evidence gathered for this matter: neither the record nor the law" for s in c)
    assert all(s.standing is pi.Standing.EVIDENCE and s.file.startswith(f"cases/{KEY}/files/") and "confidential" in s.note for s in c)
    assert any("April 6, 2026" in s.text for s in c) and all(s.text in NOTICE or s.text == ORDER for s in c)
    # One file gives two passages at most, and a near copy of a kept passage is folded.
    by_file: dict[str, int] = {}
    for s in c:
        by_file[s.title] = by_file.get(s.title, 0) + 1
    assert by_file["Notice of hearing.txt"] == COLLECTION_PER_FILE and len(c) <= COLLECTION_PASSAGES
    assert sum(1 for s in c if ORDER in s.text) == 1
    assert "Photo log.txt" not in by_file                     # nothing in it answers the questions
    assert c[0].section and c[0].place.endswith(f"passage {c[0].place.rsplit(' ', 1)[1]}")
    # No other tier took a passage of the case file.
    assert not any(ORDER in s.text or "Department 53" in s.text for s in pack.sources if not s.id.startswith("C"))

    page = pack.markdown()
    assert "*Collection: evidence gathered for this matter: neither the record nor the law — standing: evidence;" in page
    assert page.index("[R1]") < page.index("[C1]") < page.index("[F1]")       # after the records, before the facts
    assert "tier 10" not in next(b for b in pack.sources_text().split("\n\n") if b.startswith("[C1]"))
    assert pack.sources_text().count("[C1] collection (evidence gathered for this matter") == 1
    told = pack.task_prompt()
    assert f"COLLECTION: Example v. Example Commons (legal case). Sources C1 to {c[-1].id} are evidence gathered" in told
    assert "never a rule" in told and told.index("COLLECTION:") < told.index("QUESTION:")

    # The specification's record of the matter rides with the facts, labeled as what it is.
    record = [s for s in pack.sources if s.title.startswith("the specification's record of the matter")]
    assert [s.id for s in record] == ["F2"] and record[0].place == "the specification"
    assert "2026-03-02: hearing on the demurrer first set" in record[0].text and "Status: pending" in record[0].text
    assert "not the documents' own words" in record[0].note


def test_a_member_s_task_is_refused_a_confidential_collection_and_told_so(data):
    _build(data)
    pack = _pack(data, replace(TASK, audience=Audience.MEMBERS), ask=ASK, collection=_case())
    assert pack.gaps == ["the collection is confidential; this task's audience is all members: nothing from it is in this pack"]
    assert not pack.collection_included and not any(s.id.startswith("C") for s in pack.sources)
    page = pack.markdown() + pack.sources_text() + pack.task_prompt()
    for held in ("demurrer first set", "Department 53", "April 6, 2026", "Example v. Example Commons", "COLLECTION:"):
        assert held not in page
    assert "the collection is confidential" in page


def test_an_audience_that_may_not_see_held_files_never_gets_them_from_an_open_collection(data):
    _build(data)
    # A collection that says it is open but whose scope would open a case's files: the pack strips that for a member.
    loose = replace(_case(), confidential=False)
    pack = _pack(data, replace(TASK, audience=Audience.OWNER), ask=ASK, collection=loose)
    assert not any(s.id.startswith("C") for s in pack.sources)
    assert any("holds no indexed passages" in g for g in pack.gaps)      # none that this audience may be shown


def test_without_an_index_or_with_an_empty_collection_the_pack_says_so(data):
    pack = _pack(data, ask=ASK, collection=_case())
    assert any("was not searched: there is no passage index to read" in g for g in pack.gaps)
    assert any(s.title.startswith("the specification's record") for s in pack.sources)      # the record still holds
    _build(data)
    empty = ad_hoc(catalogs=("vendors",))
    pack = _pack(data, ask=ASK, collection=empty)
    assert any("holds no indexed passages" in g for g in pack.gaps) and not any(s.id.startswith("C") for s in pack.sources)
    quiet = _pack(data, ask="zzzz qqqq", task=replace(TASK, topics=()), collection=_case())
    assert any("matched the task's questions (4 files, " in g for g in quiet.gaps)


def test_files_with_no_text_in_the_index_are_counted_not_passed_over(data):
    files = data / "cases" / KEY / "files"
    (files / "Complaint.pdf").write_bytes(b"%PDF-1.4 no text layer")
    (files / "Answer.pdf").write_bytes(b"%PDF-1.4 with an extract beside it")
    (files / "Answer.pdf.md").write_text("The association answers the complaint and denies each allegation.", encoding="utf-8")
    _build(data)
    assert _case().folder == f"cases/{KEY}/files"
    pack = _pack(data, ask=ASK, collection=_case())
    assert pack.gaps == ["the passage index lacks 1 of the 7 files of the collection (Example v. Example Commons) on disk "
                         "(no text to search): the pack cannot show them"]
    assert any(s.id.startswith("C") for s in pack.sources)


def test_a_case_file_changed_since_the_cut_is_said(data):
    _build(data)
    order = data / "cases" / KEY / "files" / "Minute order.md"
    later = order.stat().st_mtime + 60
    os.utime(order, (later, later))
    notice = data / "cases" / KEY / "files" / "Notice of hearing.txt"
    os.utime(notice, (later, later))
    pack = _pack(data, ask=ASK, collection=_case())
    assert sorted(g.split(" changed after the index cut it")[0] for g in pack.gaps) == [
        f"cases/{KEY}/files/Minute order.md", f"cases/{KEY}/files/Notice of hearing.txt"]      # once a file, not once a passage


def test_an_ad_hoc_collection_s_passages_keep_their_own_standing(data):
    _build(data)
    pack = _pack(data, collection=ad_hoc(catalogs=("records",), title="The governing documents"))
    c = [s for s in pack.sources if s.id.startswith("C")]
    assert c and all(s.standing is pi.Standing.RECORD and "standing: record; catalog: records" in s.note for s in c)
    assert all("a scope a person named" in s.label for s in c)
    assert not any(s.place == "the specification" for s in pack.sources)                    # no context lines to add


def test_hybrid_ranks_the_collection_with_the_index_s_vectors(data):
    _build(data)
    pack = assemble(Community(), TASK, data, ask=ASK, mode="hybrid", embedder=FakeEmbedder(), files=lambda kind: [],
                    fact_runner=lambda tool, args: {}, collection=_case())
    assert any("April 6, 2026" in s.text for s in pack.sources if s.id.startswith("C"))


def test_the_run_s_messages_carry_the_collection_and_its_quotes_check(data):
    _build(data)
    pack = _pack(data, ask=ASK, collection=_case())
    system, user = messages(pack)
    assert "COLLECTION: Example v. Example Commons" in user["content"] and "[C1] collection (" in user["content"]
    order = next(s.id for s in pack.sources if ORDER in s.text)
    checked = verify({"issues": [{"issue": "i", "rules": [], "facts": [
        {"source": order, "quote": "continued the hearing on the demurrer to April 6, 2026"},
        {"source": "F2", "quote": "hearing on the demurrer first set"}], "application": "", "conclusion": ""}]}, pack.texts())
    assert checked.grounded == 2 and not checked.ungrounded


# --- reviews kept ---------------------------------------------------------------------------------------------------

DRAFT = "Dear Owners, the hearing on the demurrer was continued."
ANSWER = {"issues": [{"issue": "the date", "rules": [], "facts": [{"source": "D1", "quote": "the hearing on the demurrer was continued"}],
                      "application": "a", "conclusion": "c"}], "considerations": [], "conflicts": [], "board_decisions": [],
          "open_questions": [], "draft": ""}


def test_two_reviews_of_one_draft_under_two_collections_are_both_kept(data):
    _build(data)
    day = date(2026, 10, 4)
    plain = _pack(data, draft=DRAFT)
    case = _pack(data, draft=DRAFT, collection=_case())
    records = _pack(data, draft=DRAFT, collection=ad_hoc(catalogs=("records",)))
    paths = [review_store.store(p, data, as_of=day) for p in (plain, case, records)]
    assert len(set(paths)) == 3 and all(p.is_file() for p in paths)
    assert [p.parent.name for p in paths] == ["none", KEY, records.collection.key]
    assert all(p.parent.parent == data / "reviews" / "rule-reminder" for p in paths)
    assert review_store.store(case, data, as_of=date(2027, 1, 1)) == paths[1]                # the same pack, the same record

    kept = json.loads(paths[1].read_text(encoding="utf-8"))
    assert kept["asOf"] == "2026-10-04" and kept["collection"] == KEY and kept["collectionIncluded"]
    assert kept["confidential"] and "directors and counsel" in kept["confidentialWhy"] and kept["runs"] == []
    assert kept["digest"] == review_store.review_digest(case) and paths[1].stem == kept["digest"][:16]
    assert kept["draftDigest"] == hashlib.sha256(DRAFT.encode()).hexdigest()
    by_id = {row["id"]: row for row in kept["sources"]}
    c1 = next(s for s in case.sources if s.id == "C1")
    assert by_id["C1"] == {"id": "C1", "tier": 10, "standing": "evidence", "file": c1.file, "section": c1.section,
                           "digest": hashlib.sha256(c1.text.encode()).hexdigest()}
    assert by_id["S1"]["standing"] == "authority" and by_id["S1"]["file"] == "authorities/CIV/CIV-5850-5875.md"
    assert by_id["G1"]["standing"] == "record" and by_id["D1"]["standing"] == ""
    assert ORDER not in paths[1].read_text(encoding="utf-8")                                 # digests, never the words
    assert not json.loads(paths[0].read_text(encoding="utf-8"))["confidential"]

    # A run is added to the pack's record; a second run is kept beside the first.
    checked = verify(ANSWER, case.texts())
    review_store.store(case, data, checked=checked, model="example-model")
    review_store.store(case, data, checked=verify({"issues": []}, case.texts()), model="other-model")
    kept = json.loads(paths[1].read_text(encoding="utf-8"))
    assert [r["model"] for r in kept["runs"]] == ["example-model", "other-model"] and kept["asOf"] == "2026-10-04"
    assert kept["runs"][0]["grounded"] == 1 and kept["runs"][0]["answer"] == ANSWER

    # A changed source is a new record, not the old one written over.
    (data / "cases" / KEY / "files" / "Minute order.md").write_text(ORDER.replace("April 6", "April 13"), encoding="utf-8")
    _build(data)
    assert review_store.store(_pack(data, draft=DRAFT, collection=_case()), data, as_of=day) != paths[1]

    shared = review_store.history(data, "rule-reminder")
    assert {r["collection"] for r in shared} == {"none", records.collection.key}             # the case's are held back
    everything = review_store.history(data, "rule-reminder", include_confidential=True)
    assert len(everything) == 4 and sum(r["confidential"] for r in everything) == 2
    ran = next(r for r in everything if r["runs"])
    assert (ran["runs"], ran["model"], ran["verified"], ran["grounded"]) == (2, "other-model", False, 0)
    assert next(r for r in everything if r["collection"] == "none")["verified"] is None
    assert review_store.history(data, "question") == []


def test_a_refused_collection_s_review_is_kept_as_confidential_too(data):
    _build(data)
    pack = _pack(data, replace(TASK, audience=Audience.MEMBERS), draft=DRAFT, collection=_case())
    kept = json.loads(review_store.store(pack, data).read_text(encoding="utf-8"))
    assert kept["confidential"] and not kept["collectionIncluded"] and kept["audience"] == "all members"
    assert not any(row["id"].startswith("C") for row in kept["sources"])


def test_the_brief_s_review_json_is_what_it_was(data, tmp_path):
    _build(data)
    pack = _pack(data, draft=DRAFT, collection=_case())
    json_path, md_path = save_review(pack, verify(ANSWER, pack.texts()), save_pack(pack, tmp_path / "briefs" / "x.md"))
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert list(saved) == ["task", "ask", "answer", "grounded", "ungrounded", "sources", "gaps"]
    assert all(list(row) == ["id", "tier", "title", "text", "place", "score", "note"] for row in saved["sources"])
    assert md_path.is_file() and (tmp_path / "briefs" / "x.md").read_text(encoding="utf-8") == pack.markdown()


def test_the_command_s_listings_read_the_index_and_the_store(data):
    from jason.commands.review import collection_lines, history_lines

    (line,) = collection_lines(Community(), data)
    assert KEY in line and "no passage index" in line
    _build(data)
    (line,) = collection_lines(Community(), data)
    counted = pi.count(data, _case().scope)
    assert counted[0] == 4 and f"4 files, {counted[1]} passages" in line and "confidential" in line and "legal case" in line
    assert pi.count(data, pi.Scope(catalogs=(catalog_name(CASE),))) == (0, 0)                # held unless named to open

    assert history_lines(data, "rule-reminder") == []
    pack = _pack(data, draft=DRAFT, collection=_case())
    review_store.store(pack, data, as_of=date(2026, 10, 4))
    (line,) = history_lines(data, "rule-reminder")
    assert line.startswith(f"2026-10-04  {KEY} (confidential)  {review_store.review_digest(pack)[:16]}") and "no answer" in line
    review_store.store(pack, data, checked=verify(ANSWER, pack.texts()), model="example-model")
    assert "verified: 1 quotes found, 0 not found (example-model; 1 runs)" in history_lines(data, "rule-reminder")[0]


def test_the_command_names_a_collection_or_builds_an_ad_hoc_one():
    import argparse

    from jason.commands.review import chosen_collection, register

    parser = argparse.ArgumentParser()
    register(parser.add_subparsers(), lambda p: None, lambda args: None)
    parse = lambda *argv: parser.parse_args(["review", "question", *argv])       # noqa: E731
    assert chosen_collection(Community(), parse()) is None
    assert chosen_collection(Community(), parse("--collection", f"case-{KEY}")).key == KEY
    found = chosen_collection(Community(), parse("--catalog", "records", "--kind", "notice", "--folder", "governing"))
    assert found.kind is CollectionKind.AD_HOC and found.scope.kinds == ("notice",)
    for argv, why in ((("--collection", "nothing"), "--collections lists them"),
                      (("--collection", KEY, "--kind", "notice"), "not both"),
                      (("--confidential",), "goes with --catalog")):
        with pytest.raises(ValueError, match=why):
            chosen_collection(Community(), parse(*argv))
    assert parse("--history").history and parser.parse_args(["review", "--collections"]).collections


# --- the MCP tools --------------------------------------------------------------------------------------------------

def test_document_search_filters_by_kind_and_folder(data):
    from jason.mcp.county import document_search

    _build(data)
    name = catalog_name(CASE)
    everything = document_search("hearing on the demurrer", data_dir=data, mode="keyword", catalog=name)
    assert {h["kind"] for h in everything["hits"]} == {"notice", "order"}
    orders = document_search("hearing on the demurrer", data_dir=data, mode="keyword", catalog=name, kind="order")
    assert orders["hits"] and {h["kind"] for h in orders["hits"]} == {"order"}
    both = document_search("hearing on the demurrer", data_dir=data, mode="keyword", catalog=name, kind="order, notice")
    assert {h["kind"] for h in both["hits"]} == {"notice", "order"}
    # A kind narrows; it opens nothing: the case's files stay held when its catalog is not named.
    assert document_search("hearing on the demurrer", data_dir=data, mode="keyword", kind="order")["hits"] == []
    governing = document_search("refuse containers", data_dir=data, mode="keyword", folder=f"/{GOVERNING}/")
    assert governing["hits"] and {h["catalog"] for h in governing["hits"]} == {"records"}
    assert document_search("refuse containers", data_dir=data, mode="keyword", folder="authorities")["hits"] == []


def test_manager_context_names_a_collection(data, monkeypatch):
    import jason.community
    from jason.mcp.county import manager_context
    from jason.tasks import manager_review

    class Profile(Community):
        def task_prompt(self, kind):
            return TASK

    monkeypatch.setattr(jason.community, "community", lambda: Profile())
    real = manager_review.build
    monkeypatch.setattr(manager_review, "build", lambda community, task, data_dir, **kw: real(
        community, task, data_dir, **{**kw, "mode": "keyword"}))
    _build(data)
    missing = manager_context(task="rule-reminder", ask=ASK, data_dir=data, collection="nothing")
    assert missing["found"] is False and missing["collection"] == "nothing"
    served = manager_context(task="rule-reminder", ask=ASK, data_dir=data, collection=f"case-{KEY}")
    assert served["collection"] == KEY and served["collectionIncluded"] and served["confidential"]
    assert "[C1]" in served["pack"] and any("directors and counsel" in c for c in served["caveats"])
    assert not (data / "reviews").exists() and not (data / "briefs").exists()               # the tool writes nothing
    plain = manager_context(task="rule-reminder", ask=ASK, data_dir=data)
    assert set(plain) == {"task", "sources", "gaps", "pack"} and "[C1]" not in plain["pack"]
