"""The rules-and-documents reads in the console (``jason.web.extra.rules_docs``): ``cite``, ``living``, ``conflicts``,
``law-in-force``, and ``check-quotes``. Each is gated, reads disk only (the shelf's read-through to lawlibrary is held off),
writes nothing, gives the stored words verbatim, and answers a missing shelf with a miss.

Every statute ("CIV 9901"), document, rule, and amendment here is made up.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

import webclient
from jason.community import law_text
from jason.community import passage_index as pi
from jason.community.authority_order import Clarity, Conflict, ConflictStatus, Tier
from jason.community.lessons import Area
from jason.community.living import LivingDocument, LivingInstrument, SourceKind, SourceRef
from jason.community.symbols import DocumentKind
from jason.web.app import create_app
from jason.web.extra import rules_docs
from jason.web.sources import default_loaders

NAMES = ("cite", "living", "conflicts", "law-in-force", "check-quotes")
PAGE = "authorities/CIV/CIV-9900-9910.md"
OLD = ("9901. (Added by Stats. 2090, Ch. 1, Sec. 2.)\n\n(a) A notice shall be given in writing.\n\n"
       "(b) The notice is given fifteen days before the hearing.\n\n(c) The notice names the place.")
NEW = ("9901. (Amended by Stats. 2095, Ch. 7, Sec. 1.)\n\n(a) A notice shall be given in writing.\n\n"
       "(b) The notice is given fourteen days before the hearing.\n\n(c) The notice names the place.")
B_NEW = "(b) The notice is given fourteen days before the hearing."
B_OLD = "(b) The notice is given fifteen days before the hearing."
RULES = ("# Kite Rules\n\n## 1.1 Pets\n\nEach unit may keep two pets, and a fish is not counted as a pet.\n\n"
         "## 1.2 Parking\n\nEach unit has one space, and a guest parks on the street for the duration of a visit.\n")
SECRET = "# Counsel's letter\n\nOur office advises the board to settle the made-up kite matter before the spring.\n"
SECRET_WORDS = "Our office advises the board to settle the made-up kite matter before the spring"
SOURCES = (
    pi.IndexSource("records", "governing", pi.Standing.RECORD),
    pi.IndexSource("authorities", "authorities", pi.Standing.AUTHORITY, front_matter=True),
    pi.IndexSource("library", "private", pi.Standing.RECORD, confidential=True),
)
BASE = """ARTICLE 4
4.15 Rental of Condominiums.
(a) Restrictions. Not more than twenty percent (20%) of the Units shall be leased at any time.
(b) Applications. An Owner shall apply in writing.
"""
ROSTER = webclient.ROSTER + (("Rae Roster", "", "rae@example.org", False),)


def _tree(root: Path) -> dict[str, str]:
    """Every file under ``root`` and the digest of its bytes: a read leaves this unchanged."""
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.fixture()
def data(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "data"
    (root / "authorities" / "CIV").mkdir(parents=True)
    (root / PAGE).write_text(
        "# Made-up hearings\n\n- Source: California Legislature, 2097 session publication, read with lawlibrary\n\n"
        f"## CIV 9901\n\n- History: amended by Stats. 2095, Ch. 7\n\n{NEW}\n", encoding="utf-8")
    (root / "authorities" / "manifest.json").write_text(json.dumps({"exported": "2099-01-02", "pages": [{
        "file": PAGE, "citation": "CIV 9900-9910", "title": "Made-up hearings", "code": "CIV", "start": "9900",
        "end": "9910", "sections": ["9901"], "basis": "duty", "why": [], "session": "2097"}]}), encoding="utf-8")
    old_digest = law_text.words_digest(OLD)
    history = root / "authorities" / "history" / "CIV-9901"
    history.mkdir(parents=True)
    (history / f"{old_digest}.md").write_text(
        "# CIV 9901: an earlier version\n\n- Source: California Legislature, 2091 to 2093 session publications, read with "
        "lawlibrary\n- Editions: 2091, 2093\n- Act: Stats. 2090, Ch. 1, Sec. 2 (AB 1)\n- From: 2091-01-01\n"
        "- Until: 2095-06-30\n- Until by: Stats. 2095, Ch. 7, Sec. 1 (AB 7)\n\n## CIV 9901\n\n" + OLD + "\n", encoding="utf-8")
    now = law_text.section_digest("CIV 9901", root)
    (root / "authorities" / "history" / "versions.json").write_text(json.dumps({"sections": {"CIV 9901": {
        "read": "2099-01-02", "editions": ["2091", "2093", "2095", "2097"], "printed": ["2091", "2093", "2095", "2097"],
        "versions": [{"digest": old_digest, "act": "Stats. 2090, Ch. 1, Sec. 2 (AB 1)", "from": "2091-01-01",
                      "until": "2095-06-30", "until_by": "Stats. 2095, Ch. 7, Sec. 1 (AB 7)", "editions": ["2091", "2093"],
                      "newest": False},
                     {"digest": now, "act": "Stats. 2095, Ch. 7, Sec. 1 (AB 7)", "from": "2095-06-30", "until": "",
                      "editions": ["2095", "2097"], "newest": True}]}}}), encoding="utf-8")
    for folder, name, text in (("governing", "rules.md", RULES), ("private", "letter.md", SECRET)):
        (root / folder).mkdir()
        (root / folder / name).write_text(text, encoding="utf-8")
    pi.build(root, sources=SOURCES, kind_of=lambda name: "")
    monkeypatch.setattr(rules_docs, "_root", lambda: root)
    return root


def _living(*, pending: bool = False) -> LivingDocument:
    second = SimpleNamespace(title="Second Amendment", recorded=date(2023, 12, 6), adopted=None, recorder_number="000000000001")
    third = SimpleNamespace(title="Third Amendment", recorded=None, adopted=None, recorder_number="")
    instruments = [LivingInstrument("decl-2nd", second, SourceRef(SourceKind.DOC, "doc-2"))]
    if pending:
        instruments.append(LivingInstrument("decl-3rd", third, SourceRef(SourceKind.DOC, "doc-3")))
    return LivingDocument("decl", "Declaration", DocumentKind.DECLARATION,
                          base=SourceRef(SourceKind.LIBRARY_TEXT, "Governing/Declaration.pdf"), base_from="the recorded copy",
                          instruments=tuple(instruments))


def _row(key="cap", status=ConflictStatus.BOARD, areas=(Area.RENTALS,), **kw) -> Conflict:
    fields = dict(provision="CC&Rs 1.1(a)", tier=Tier.DECLARATION, says="Caps something at 10.", authority="CIV 1234(b)",
                  authority_tier=Tier.STATUTE, since=date(2021, 1, 1), extent="A cap below 25 may not be enforced.",
                  apply="Hold nothing against the cap.", clarity=Clarity.PLAIN, status=status, areas=areas, board_item="item-1")
    fields.update(kw)
    return Conflict(key, **fields)


@pytest.fixture()
def community(monkeypatch, data):
    """A made-up community for the governance tools: one living document, two conflicts."""
    done = _row("done", status=ConflictStatus.RESOLVED, resolved_by="the 2099 amendment")
    fake = SimpleNamespace(living_documents=lambda: (_living(pending=True),),
                           conflicts=lambda: (_row(), done, _row("fine", areas=(Area.ENFORCEMENT,))))
    monkeypatch.setattr("jason.mcp.governance._community", lambda: fake)
    return fake


@pytest.fixture()
def living_files(data):
    """The declaration's text in the library and the second amendment's Doc as the living documents read them."""
    lib = data / "library"
    (lib / "text").mkdir(parents=True)
    with sqlite3.connect(lib / "library.db") as conn:
        conn.execute("CREATE TABLE documents (id TEXT, path TEXT, sha256 TEXT)")
        conn.execute("INSERT INTO documents VALUES ('1', 'Governing/Declaration.pdf', 'abc')")
    (lib / "text" / "1.txt").write_text(BASE, encoding="utf-8")
    from jason.tasks import living_docs as ld

    cache = ld.living_dir(data, "decl") / "sources"
    cache.mkdir(parents=True)

    def run(text, bold=False, strike=False):
        return {"textRun": {"content": text, "textStyle": {"bold": bold, "strikethrough": strike}}}

    paragraphs = [[run("NOW, THEREFORE, the Association declares:\n")],
                  [run("Article 4, Section 4.15, subsection (a) (\"Restrictions\") is hereby amended and restated as follows "
                       "(stricken out wording will be removed, and bolded wording will be added):\n")],
                  [run("Not more than "), run("twenty percent (20%)", strike=True), run(" "), run("twenty-five (25%)", bold=True),
                   run(" of the Units shall be leased at any time.\n")], [run("IN WITNESS WHEREOF, the Board.\n")]]
    (cache / "doc-2.json").write_text(json.dumps({"revisionId": "rev-1", "body": {"content": [
        {"paragraph": {"elements": p}} for p in paragraphs]}}), encoding="utf-8")
    third = [[run("NOW, THEREFORE, the Association declares:\n")],
             [run("Article 4, Section 4.15, subsection (b) (\"Applications\") is hereby amended and restated as follows "
                  "(stricken out wording will be removed, and bolded wording will be added):\n")],
             [run("An Owner shall apply "), run("in writing", strike=True), run("on the form", bold=True), run(".\n")],
             [run("IN WITNESS WHEREOF, the Board.\n")]]
    (cache / "doc-3.json").write_text(json.dumps({"revisionId": "rev-3", "body": {"content": [
        {"paragraph": {"elements": p}} for p in third]}}), encoding="utf-8")
    return data


def _web(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir(exist_ok=True)
    loaders = {k: v for k, v in default_loaders().items() if k in NAMES}
    return create_app(dist, loaders, approvals_live=None, extra_writes=True, sign_in=webclient.roster_sign_in(ROSTER))


def _as(app, who: str | None):
    c = webclient.client(app)
    return webclient.sign_in(c, who, rows=ROSTER) if who else c


@pytest.fixture()
def app(tmp_path, data):
    return _web(tmp_path)


@pytest.fixture()
def web(app):
    return _as(app, "A Manager")


# --- gated ------------------------------------------------------------------------------------------------------------

URLS = {
    "cite": "/api/cite?expression=CIV+9901(b)", "living": "/api/living", "conflicts": "/api/conflicts",
    "law-in-force": "/api/law-in-force?citation=CIV+9901", "check-quotes": "/api/check-quotes",
}


@pytest.mark.parametrize("name", NAMES)
def test_each_loader_is_gated_and_needs_a_sign_in(app, name):
    out = _as(app, None).get(URLS[name])
    assert out.status_code == 401, name


def test_the_roster_reads_the_documents_and_the_law_and_the_offices_alone_read_the_quote_check(app):
    for name in ("cite", "living", "conflicts", "law-in-force"):
        for who in ("Rae Roster", "Ada Admin", "A Manager", "Dana Director"):
            assert _as(app, who).get(URLS[name]).status_code == 200, (name, who)
    for who in ("Rae Roster", "Ada Admin"):
        assert _as(app, who).get(URLS["check-quotes"]).status_code == 403, who
    for who in ("A Manager", "Dana Director", "Pat Example", "Sam Secretary", "Lee President", "Vic Vice"):
        assert _as(app, who).get(URLS["check-quotes"]).status_code == 200, who


CHECK = "/api/write/check-quotes/run"
SAMPLE = 'The rules say "Each unit has one space, and a guest parks on the street for the duration of a visit".'


def test_the_quote_check_post_is_gated_like_its_get(app):
    body = {"text": SAMPLE}
    assert _as(app, None).post(CHECK, json=body).status_code == 401
    for who in ("Rae Roster", "Ada Admin"):
        assert _as(app, who).post(CHECK, json=body).status_code == 403, who
    for who in ("A Manager", "Dana Director", "Pat Example", "Sam Secretary", "Lee President", "Vic Vice"):
        assert _as(app, who).post(CHECK, json=body).status_code == 200, who
    # The owner view is refused, in the address or in the body.
    manager = _as(app, "A Manager")
    assert manager.post(CHECK + "?view=owner", json=body).status_code == 403
    assert manager.post(CHECK, json={**body, "view": "owner"}).status_code == 403
    assert manager.post("/api/write/check-quotes/other", json=body).status_code == 404


def test_the_gate_table_and_the_loaders_agree():
    from jason.web import gates

    assert {n: gates.GATES[n] for n in NAMES} == {"cite": "p0", "living": "p0", "conflicts": "p0", "law-in-force": "p0",
                                                  "check-quotes": "p2"}
    assert all(getattr(default_loaders()[n], "gate", None) == gates.GATES[n] for n in NAMES)


def test_the_owner_view_does_not_serve_them():
    from jason.web.extra.owner_view import OWNER_SOURCES

    assert not set(NAMES) & set(OWNER_SOURCES)


def test_where_sign_in_is_not_set_up_a_gated_loader_answers_as_it_did(tmp_path, data):
    dist = tmp_path / "dist"
    dist.mkdir(exist_ok=True)
    loaders = {k: v for k, v in default_loaders().items() if k in NAMES}
    c = webclient.client(create_app(dist, loaders, approvals_live=None, extra_writes=False,
                                    sign_in=webclient.roster_sign_in(ROSTER, configured=False)))
    assert all(c.get(URLS[n]).status_code == 200 for n in NAMES)


# --- read only --------------------------------------------------------------------------------------------------------

def test_no_loader_writes_anything_and_none_reaches_lawlibrary(web, data, community, living_files, monkeypatch):
    """The read-through to lawlibrary writes a page into data/authorities when a statute is missing; a web read does not."""
    from jason.tasks import statute_fetch

    calls: list[tuple] = []

    def fake_fetch(root, code, start, end, asked_by, library):
        calls.append((code, start, end))
        return statute_fetch.Fetched(code, start, end, False, miss=statute_fetch.Miss.NOT_IN_LIBRARY)

    monkeypatch.setenv(statute_fetch.FETCH_ENV, "1")
    monkeypatch.setattr(statute_fetch, "_fetch", fake_fetch)
    statute_fetch._misses.clear()
    monkeypatch.setattr("jason.tasks.conflict_leads.leads", lambda root, c, **kw: [])
    # The control: the tool asked outside the console does read through, so the check below means something.
    from jason import api

    api.cite_document("CIV 9998", data_dir=data)
    assert calls == [("CIV", "9998", "9998")]
    calls.clear()
    before = _tree(data)
    for url in ("/api/cite?expression=CIV+9997", "/api/cite?expression=CIV+9997-9999", "/api/law-in-force?citation=CIV+9996",
                "/api/living?key=decl", "/api/conflicts?leads=1") + tuple(URLS.values()):
        assert web.get(url).status_code in (200, 400), url
    quoted = 'It says "The notice is given fifteen days before the hearing" under CIV 9995.'
    assert web.post(CHECK, json={"text": quoted}).status_code == 200
    assert calls == [], "a web read asked lawlibrary"
    assert _tree(data) == before, "a web read wrote to the data folder"
    assert statute_fetch.enabled() is True      # the hold is for the call alone


def test_the_hold_on_the_read_through_ends_with_the_call(monkeypatch):
    from jason.tasks import statute_fetch

    monkeypatch.setenv(statute_fetch.FETCH_ENV, "1")
    with statute_fetch.disabled():
        assert statute_fetch.enabled() is False
        with pytest.raises(RuntimeError):
            with statute_fetch.disabled():
                raise RuntimeError
        assert statute_fetch.enabled() is False
    assert statute_fetch.enabled() is True


# --- cite -------------------------------------------------------------------------------------------------------------

def test_cite_recites_the_stored_words_verbatim_with_the_citation(web):
    body = web.get("/api/cite?expression=CIV+9901(b)").json
    assert body["found"] is True and body["kind"] == "statute" and body["citation"] == "CIV 9901(b)"
    assert B_NEW in body["text"] and "fifteen" not in body["text"]               # the words as stored, not a paraphrase
    assert body["caveats"][0].startswith("The words are jason's stored words") and "not an official restatement" in body["caveats"][1]


def test_cite_gives_the_version_in_force_on_a_day_and_the_later_one_today(web):
    early = web.get("/api/cite?expression=CIV+9901(b)&as_of=2092-05-01").json
    assert early["found"] and B_OLD in early["text"] and early["asOf"] == "2092-05-01"
    assert "fifteen" not in web.get("/api/cite?expression=CIV+9901(b)&as_of=2099-01-02").json["text"]


def test_cite_without_the_words_is_an_outline_of_the_citation_only(web):
    body = web.get("/api/cite?expression=CIV+9901(b)&text=0").json
    assert body["found"] is True and not body.get("text")


@pytest.mark.parametrize("expression, reason", [
    ("", "empty"), ("CIV 9877", "statute_not_on_disk"), ("Section 12 of the Nonesuch", None), ("minutes 2099-01-01", "no_minutes"),
])
def test_cite_a_miss_is_an_answer_with_its_reason_not_a_crash(web, expression, reason):
    r = web.get("/api/cite", query_string={"expression": expression})
    body = r.json
    assert r.status_code == 200 and body["found"] is False and body["kind"] == "miss"
    if reason:
        assert body["reason"] == reason
    assert body["caveats"]


@pytest.mark.parametrize("key", ["exec", "members", "ballots"])
def test_cite_refuses_a_restricted_book(web, key):
    body = web.get("/api/cite", query_string={"expression": f"jason://{key}/2099-01-01"}).json
    assert body["found"] is False and body["reason"] == "restricted" and "CIV" in body["detail"]


def test_cite_a_bad_day_or_a_long_expression_is_a_400(web):
    assert web.get("/api/cite?expression=CIV+9901&as_of=yesterday").status_code == 400
    assert web.get("/api/cite?expression=CIV+9901&as_of=2099-02-30").status_code == 400
    assert web.get("/api/cite?expression=CIV+9901&citing_day=1/2/2099").status_code == 400
    assert web.get("/api/cite", query_string={"expression": "x" * 400}).status_code == 400


def test_a_confidential_record_is_named_without_where_it_sits():
    node = {"kind": "minutes", "confidential": True, "where": "PayHOA library", "location": "Board/Exec minutes.pdf"}
    open_node = {"kind": "minutes", "confidential": False, "where": "PayHOA library", "location": "Board/Minutes.pdf"}
    out = rules_docs._hold_confidential({"nodes": [node, open_node], "text": "Board/Exec minutes.pdf"})
    assert out["nodes"][0] == {"kind": "minutes", "confidential": True, "where": "held", "location": "held"}
    assert out["nodes"][1] == open_node and out["text"] == "Board/Exec minutes.pdf"      # words are never touched


# --- living -----------------------------------------------------------------------------------------------------------

def test_living_lists_the_documents_kept_as_amended(web, community):
    body = web.get("/api/living").json
    assert body["found"] is True and body["documents"] == [
        {"key": "decl", "title": "Declaration", "base": "the recorded copy", "instruments": ["decl-2nd", "decl-3rd"]}]
    assert "not an official restatement" in body["caveats"][1]


def test_living_one_document_lists_what_applied_and_what_is_not_in_effect_apart(web, community, living_files):
    body = web.get("/api/living?key=decl&section=4.15(a)").json
    assert body["found"] is True and body["key"] == "decl"
    assert body["section"]["words"].count("twenty-five (25%)") == 1 and "twenty percent" not in body["section"]["words"]
    assert body["section"]["setBy"] == "decl-2nd"
    assert any("Second Amendment" in line for line in body["applied"])
    assert any("Third Amendment" in line for line in body["notInEffect"]) and not any("Third" in l for l in body["applied"])
    assert body["caveat"].startswith("Consolidated by jason from the instruments' own words")


def test_living_on_a_day_before_the_amendment_gives_the_base_words(web, community, living_files):
    body = web.get("/api/living?key=decl&section=4.15(a)&as_of=2020-01-01").json
    assert body["found"] and "twenty percent (20%)" in body["section"]["words"] and body["asOf"] == "2020-01-01"


def test_living_a_missing_document_section_or_base_is_a_miss(web, community, living_files, data):
    unknown = web.get("/api/living?key=zzz").json
    assert unknown["found"] is False and "no living document zzz" in unknown["note"] and unknown["documents"] == ["decl"]
    nosection = web.get("/api/living?key=decl&section=9.9").json
    assert nosection["found"] is True and nosection["section"] == {"error": "no section 9.9"}
    (data / "library" / "text" / "1.txt").unlink()                    # the shelf loses the declaration's text
    base = web.get("/api/living?key=decl")
    assert base.status_code == 200 and base.json["found"] is False and base.json["note"]


def test_living_with_no_shelf_at_all_is_a_miss_not_a_crash(web, community):
    body = web.get("/api/living?key=decl")
    assert body.status_code == 200 and body.json["found"] is False and body.json["note"]


def test_living_asks_for_a_document_before_a_section_and_a_real_day(web, community):
    assert web.get("/api/living?section=4.15(a)").status_code == 400
    assert web.get("/api/living?key=decl&as_of=soon").status_code == 400


# --- conflicts --------------------------------------------------------------------------------------------------------

def test_conflicts_list_the_open_rows_and_say_jason_resolves_none(web, community):
    body = web.get("/api/conflicts").json
    assert body["found"] is True and [c["key"] for c in body["conflicts"]] == ["cap", "fine"]
    first = body["conflicts"][0]
    assert first["authority"] == "CIV 1234(b)" and first["since"] == "2021-01-01" and first["clarity"] == "plain"
    assert first["status"] == "board" and first["boardItem"] == "item-1" and first["meanwhile"] == "Hold nothing against the cap."
    assert body["caveats"][0] == "jason notes a conflict; only the board, counsel, or an amendment resolves one."
    assert all(c["status"] != "resolved" for c in body["conflicts"])      # a row the board has not settled stays open


def test_conflicts_by_area_and_with_the_resolved(web, community):
    assert [c["key"] for c in web.get("/api/conflicts?area=enforcement").json["conflicts"]] == ["fine"]
    every = web.get("/api/conflicts?resolved=1").json["conflicts"]
    assert [c["key"] for c in every] == ["cap", "done", "fine"] and every[1]["resolvedBy"] == "the 2099 amendment"


def test_conflicts_leads_are_asked_for_and_are_not_conflicts(web, community, monkeypatch):
    seen = {}

    def leads(root, c, *, document="", since=""):
        seen.update(document=document, since=since)
        return []

    monkeypatch.setattr("jason.tasks.conflict_leads.leads", leads)
    assert "leads" not in web.get("/api/conflicts").json
    body = web.get("/api/conflicts?leads=1&document=decl&since=2026-01-01").json
    assert body["leads"] == [] and body["leadCount"] == 0 and seen == {"document": "decl", "since": "2026-01-01"}


def test_conflicts_an_unknown_area_or_day_is_a_400_that_names_the_choices(web, community):
    r = web.get("/api/conflicts?area=nonesuch")
    assert r.status_code == 400 and "areas:" in r.json["error"] and "rentals" in r.json["error"]
    assert web.get("/api/conflicts?since=last+year").status_code == 400


def test_conflicts_none_recorded_is_a_miss_that_lists_nothing(web, monkeypatch):
    monkeypatch.setattr("jason.mcp.governance._community", lambda: SimpleNamespace(conflicts=lambda: ()))
    body = web.get("/api/conflicts").json
    assert body["found"] is False and body["conflicts"] == []


# --- law-in-force -----------------------------------------------------------------------------------------------------

def test_law_in_force_gives_the_words_of_the_day_whole(web):
    now = web.get("/api/law-in-force?citation=CIV+9901(b)&as_of=2099-01-02").json
    assert now["found"] is True and now["words"].endswith("(c) The notice names the place.") and B_NEW in now["words"]
    assert now["subdivisionWords"] == B_NEW
    early = web.get("/api/law-in-force?citation=CIV+9901(b)&as_of=2092-05-01").json
    assert early["found"] is True and early["words"] == OLD and early["subdivisionWords"] == B_OLD
    assert (early["from"], early["until"]) == ("2091-01-01", "2095-06-30") and early["asOf"] == "2092-05-01"
    assert [v["place"] for v in early["versions"]] == ["in force", "later"]
    assert "not an official restatement" in early["caveats"][-1]


def test_law_in_force_a_section_the_shelf_lacks_is_a_miss_that_picks_nothing(web):
    body = web.get("/api/law-in-force?citation=CIV+9999").json
    assert body["found"] is False and body["words"] == "" and "not on the shelf" in body["reason"]
    empty = web.get("/api/law-in-force").json
    assert empty["found"] is False and "code and a section" in empty["reason"]


def test_law_in_force_with_no_shelf_at_all_is_a_miss(tmp_path, monkeypatch):
    monkeypatch.setattr(rules_docs, "_root", lambda: tmp_path / "nothing-here")
    c = _as(_web(tmp_path), "A Manager")
    body = c.get("/api/law-in-force?citation=CIV+9901").json
    assert body["found"] is False and body["words"] == ""
    assert c.get("/api/cite?expression=CIV+9901").json["found"] is False


def test_law_in_force_a_bad_day_is_a_400(web):
    assert web.get("/api/law-in-force?citation=CIV+9901&as_of=2099-13-01").status_code == 400


# --- check-quotes -----------------------------------------------------------------------------------------------------

def _check(web, text: str, **more):
    return web.post(CHECK, json={"text": text, **more})


def test_check_quotes_finds_stored_words_and_shows_where(web):
    r = _check(web, 'The rules say "Each unit has one space, and a guest parks on the street for the duration of a visit".')
    body = r.json
    assert r.status_code == 200 and body["available"] is True and body["checked"] is True
    (quote,) = body["quotes"]
    assert quote["verdict"] == "found" and quote["match"] == "exact"
    assert quote["places"][0]["path"] == "governing/rules.md" and quote["places"][0]["standing"] == "record"
    assert body["caveats"][0].startswith("This checks words, not meaning")


def test_check_quotes_an_altered_quotation_shows_both_and_the_difference(web):
    body = _check(web, 'Civil Code 9901 says "The notice is given twenty days before the hearing".').json
    (quote,) = body["quotes"]
    assert quote["verdict"] == "altered" and "given [[fourteen]] days before" in quote["stored"]
    assert "given [[twenty]] days before" in quote["quoted"]
    assert quote["differences"] == [{"quoted": "twenty", "stored": "fourteen"}]
    assert body["counts"]["altered"] == 1 and body["counts"]["found"] == 0


def test_check_quotes_on_a_day_names_the_other_version(web):
    text = 'Civil Code 9901 says "The notice is given fifteen days before the hearing".'
    body = _check(web, text, as_of="2092-05-01").json
    assert body["quotes"][0]["verdict"] == "found" and body["asOf"] == "2092-05-01"     # the version in force that day
    other = _check(web, text).json["quotes"][0]                                         # the words on the shelf now say fourteen
    assert other["verdict"] == "other version" and "earlier version of CIV 9901" in other["note"]


def test_check_quotes_an_invented_quotation_is_not_found(web):
    body = _check(web, 'The rules say "Every owner repaints the mailbox each third summer without fail".').json
    assert body["quotes"][0]["verdict"] == "not found" and body["counts"]["not found"] == 1 and body["counts"]["found"] == 0


def test_check_quotes_never_names_a_confidential_file_or_shows_its_words(web):
    """Nothing of the file reaches the web: no name, path, section, passage, or words, and the verdict is not ``found``."""
    r = _check(web, f'The letter says "{SECRET_WORDS}".')
    body = r.json
    (quote,) = body["quotes"]
    assert quote["verdict"] == "withheld" and quote["note"] == "the words exist only in a restricted record; nothing is shown"
    assert "places" not in quote and "warnings" not in quote and "match" not in quote
    assert body["counts"]["withheld"] == 1 and body["counts"]["found"] == 0 and body["counts"]["warnings"] == 0
    text = r.get_data(as_text=True)
    for leak in ("letter.md", "private/", "Counsel", "confidential file", '"withheld": true'):
        assert leak not in text, leak
    # The writer takes no `sources` and no `include_confidential`: asking for them changes nothing.
    more = _check(web, f'The letter says "{SECRET_WORDS}".', include_confidential=True, sources="private/letter.md#0")
    assert more.json["includeConfidential"] is False and more.json["quotes"][0]["verdict"] == "withheld"
    assert "letter.md" not in more.get_data(as_text=True)


def test_check_quotes_words_in_a_confidential_file_and_in_the_record_show_only_the_record(web, data):
    (data / "governing" / "rules.md").write_text(RULES + "\n## 1.3 Letters\n\n" + SECRET_WORDS + ".\n", encoding="utf-8")
    pi.build(data, sources=SOURCES, kind_of=lambda name: "")
    r = _check(web, f'It says "{SECRET_WORDS}".')
    (quote,) = r.json["quotes"]
    assert quote["verdict"] == "found" and [p["path"] for p in quote["places"]] == ["governing/rules.md"]
    assert "letter.md" not in r.get_data(as_text=True) and not any("confidential" in w for w in quote.get("warnings", []))


def test_check_quotes_the_text_is_never_in_a_web_address_and_nothing_is_written(web, data):
    before = _tree(data)
    r = _check(web, SAMPLE)
    assert r.status_code == 200 and _tree(data) == before                  # nothing under data/ changed, no log made
    assert not (data / "access" / "served.jsonl").exists()
    # The GET refuses a text and says where to send it; the text is not echoed into the answer.
    got = web.get("/api/check-quotes", query_string={"text": SAMPLE})
    assert got.status_code == 400 and "POST /api/write/check-quotes/run" in got.json["error"]
    assert SAMPLE not in got.get_data(as_text=True)
    assert web.get("/api/check-quotes", query_string={"answer": SAMPLE}).status_code == 400


def test_a_file_served_logs_a_path_never_the_pasted_text(web, data, monkeypatch):
    """``served.jsonl`` is written when a file is served; a check in the same session leaves the text out of it."""
    (data / "photos").mkdir()
    (data / "photos" / "a.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d=None: data)
    _check(web, SAMPLE)
    assert web.get("/api/file?path=photos/a.png").status_code == 200
    log = (data / "access" / "served.jsonl").read_text(encoding="utf-8")
    assert "photos/a.png" in log and "Each unit has one space" not in log


def test_check_quotes_no_text_a_long_text_or_a_bad_day(web):
    for empty in (web.get("/api/check-quotes").json, _check(web, "   ").json):
        assert empty["checked"] is False and empty["found"] is False and "paste the text" in empty["note"]
    assert web.get("/api/check-quotes").json["post"] == "/api/write/check-quotes/run"
    assert _check(web, "x" * rules_docs.MAX_QUOTE_TEXT).status_code == 200            # the cap is inclusive
    assert _check(web, "x" * (rules_docs.MAX_QUOTE_TEXT + 1)).status_code == 400
    assert _check(web, 'It says "a quotation that is long enough to be checked here".', as_of="tomorrow").status_code == 400


def test_check_quotes_with_no_passage_index_is_a_miss_not_a_crash(web, data):
    for p in (data / "retrieval").glob("*"):
        p.unlink()
    r = _check(web, 'It says "a quotation that is long enough to be checked here".')
    assert r.status_code == 200 and r.json["available"] is False and r.json["checked"] is False and "jason index --build" in r.json["note"]
