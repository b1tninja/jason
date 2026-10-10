"""Rule records, read (jason.community.rule_records, jason.tasks.rule_records, the command, the MCP tools and the web loaders),
on made-up rules: status words from the events, the version in force across a supersession and on a given day, the four
comparison words, a rule with no grant found as a question, and that nothing is written."""

from __future__ import annotations

import json
import sys
from datetime import date

import pytest

from jason.community import rule_authority as ra
from jason.community import rule_records as rr
from jason.community.manual import AdoptionAction, AdoptionEvent
from jason.community.rules_document import RuleAct, RuleBook, RuleRecord, RuleVersion

D = date


def v(words, adopted=None, **kw):
    return RuleVersion(words, words, adopted, **kw)


def rec(id_="rules#R-12", number="R-12", title="Quiet hours", versions=(), **kw):
    return RuleRecord(id_, number, title, 2, versions=tuple(versions), **kw)


def event(action, on, *sections, evidence="minutes"):
    return AdoptionEvent(on, action, tuple(sections), evidence)


# --- Status, from the events ----------------------------------------------------------------------------------------------

def test_an_imported_first_version_is_in_force_with_its_adoption_not_on_record():
    r = rec(versions=[v("No noise after 10.")])
    st = rr.status_on(r, D(2026, 1, 1))
    assert st.status is rr.Status.ADOPTED and st.adoption_on_record is False
    assert st.word == rr.NOT_ON_RECORD and st.word != "adopted"
    assert st.to_dict()["adoptionOnRecord"] is False


def test_an_adopted_version_with_its_day_is_adopted_and_before_it_the_record_shows_nothing():
    r = rec(versions=[v("No noise after 10.", D(2025, 4, 14), board_item="BI-1")])
    assert rr.status_on(r, D(2025, 4, 14)).word == "adopted"
    before = rr.status_on(r, D(2025, 4, 13))
    assert before.status is None and "does not show" in before.note
    assert rr.version_on(r, D(2025, 4, 13)) is None


def test_a_proposed_version_is_proposed_then_noticed_and_in_force_on_no_day():
    r = rec(versions=[v("Draft.", proposed=True)])
    assert rr.status_on(r, D(2026, 6, 1)).status is rr.Status.PROPOSED
    assert rr.version_on(r, D(2026, 6, 1)) is None
    noticed = event(AdoptionAction.NOTICED, D(2026, 5, 1), "R-12")
    assert rr.status_on(r, D(2026, 6, 1), [noticed]).status is rr.Status.NOTICED
    assert rr.status_on(r, D(2026, 6, 1), [event(AdoptionAction.NOTICED, D(2026, 5, 1), "R-99")]).status is rr.Status.PROPOSED
    ledger = rec(versions=[v("Draft.", proposed=True, notice=("rule-change-proposed-x",))])
    assert rr.status_on(ledger, None).status is rr.Status.NOTICED


def test_suspension_repeal_and_expiry_come_from_what_a_person_recorded():
    base = [v("Old.", D(2020, 1, 1))]
    suspended = rec(versions=base, acts=(RuleAct("suspension", D(2026, 2, 1), D(2026, 3, 1)),))
    assert rr.status_on(suspended, D(2026, 2, 15)).status is rr.Status.SUSPENDED
    assert rr.status_on(suspended, D(2026, 3, 2)).status is rr.Status.ADOPTED
    repealed = rec(versions=base, acts=(RuleAct("repeal", D(2026, 5, 1), evidence="minutes"),))
    assert rr.status_on(repealed, D(2026, 4, 30)).status is rr.Status.ADOPTED
    assert rr.status_on(repealed, D(2026, 5, 1)).status is rr.Status.REPEALED
    assert rr.version_on(repealed, D(2026, 6, 1)).words == "Old."          # its last words stay addressable
    emergency = rec(versions=[v("Short.", D(2026, 1, 1), expires=D(2026, 4, 1))])
    assert rr.status_on(emergency, D(2026, 3, 1)).status is rr.Status.ADOPTED
    assert rr.status_on(emergency, D(2026, 4, 2)).status is rr.Status.EXPIRED


def test_the_version_in_force_changes_across_a_supersession_and_a_proposal_is_never_in_force():
    r = rec(versions=[v("One.", D(2024, 1, 1)), v("Two.", D(2025, 6, 1)), v("Three.", proposed=True)])
    assert rr.version_on(r, D(2024, 12, 31)).words == "One."
    assert rr.version_on(r, D(2025, 6, 1)).words == "Two."
    assert rr.version_on(r, D(2030, 1, 1)).words == "Two."
    assert rr.open_proposals(r) == ["v3"]
    h = rr.history(r, [], D(2024, 12, 31))
    assert [x["id"] for x in h["versions"]] == ["v3", "v2", "v1"]                # newest first
    assert [x["id"] for x in h["versions"] if x["inForce"]] == ["v1"]
    v2 = next(x for x in h["versions"] if x["id"] == "v2")
    assert v2["supersedes"] == "v1" and v2["diffTo"] == "v1"
    assert {"op": "removed", "text": "One."} in v2["diff"] and {"op": "added", "text": "Two."} in v2["diff"]
    assert h["gaps"] and "2024-01-01" in h["gaps"][0]["note"]
    assert "not on record" in v2["whoNote"]                                      # who recorded it is a miss, not blank


def test_the_source_of_each_version_is_one_of_the_named_sources_and_never_a_working_draft():
    r = rec(versions=[v("a"), v("b", D(2025, 1, 1)), v("c", D(2026, 1, 1), source=rr.SOURCE_ADOPTED, source_file="lib-9"),
                      v("d", proposed=True)])
    assert [rr.source_of(r, i).kind for i in range(4)] == [rr.SOURCE_IMPORTED, rr.SOURCE_AS_READ, rr.SOURCE_ADOPTED,
                                                           rr.SOURCE_PROPOSED]
    assert rr.source_of(r, 2).file == "lib-9"
    noticed = rec(versions=[v("d", proposed=True)])
    assert rr.source_of(noticed, 0, [event(AdoptionAction.NOTICED, D(2026, 1, 1), "R-12")]).kind == rr.SOURCE_NOTICED
    assert not any("draft" in s and "working" in s for s in rr.SOURCES)


def test_the_new_fields_round_trip_and_an_old_stored_record_still_loads():
    old = {"id": "r1", "number": "1", "versions": [{"text": "x", "words": "x", "adopted": "2025-01-02"}]}
    got = RuleRecord.from_dict(old)
    assert got.to_dict()["versions"] == old["versions"] and "subjects" not in got.to_dict()
    full = rec(versions=[v("x", D(2025, 1, 2), version="v7", decision="d-1", recorded_by="Pat Example", supersedes="v6",
                          notice=("k",), effective=D(2025, 2, 1))],
               subjects=("noise",), authority=("ra-0001",), confidentiality="open", acts=(RuleAct("repeal", D(2026, 1, 1)),))
    assert RuleRecord.from_dict(json.loads(json.dumps(full.to_dict()))) == full


# --- The Doc beside the record --------------------------------------------------------------------------------------------

def test_the_four_comparison_words_and_the_two_that_are_not_comparisons():
    r = rec(versions=[v("No noise after ten.", D(2025, 1, 1)), v("No noise after nine.", proposed=True)])
    same = rr.compare(r, D(2026, 1, 1), rr.DocReading("**No** noise after ten."))
    assert same.word is rr.CompareWord.SAME and same.acts == ()
    behind = rr.compare(r, D(2026, 1, 1), rr.DocReading("No noise after eleven.", later_adoption="2026-02-01, minutes"))
    assert behind.word is rr.CompareWord.RECORD_BEHIND and behind.acts == ("record-adoption",)
    ahead = rr.compare(r, D(2026, 1, 1), rr.DocReading("No noise after nine."))
    assert ahead.word is rr.CompareWord.DOC_AHEAD and ahead.acts == ("link-proposal",)
    nothing = rr.compare(r, D(2026, 1, 1), rr.DocReading("No noise after eight.", suggested=True, pending=2))
    assert nothing.word is rr.CompareWord.NO_ADOPTION and "not accepted" in nothing.note
    assert nothing.to_dict()["doc"]["suggestionNote"] == rr.SUGGESTION_NOTE and nothing.to_dict()["actsBuilt"] is False
    assert nothing.to_dict()["adopted"]["words"] == "No noise after ten."          # the adopted words stay the rule
    missing = rr.compare(r, D(2026, 1, 1), rr.DocReading(in_doc=False))
    assert missing.word is None and missing.standing == "not in the Doc"
    unread = rr.compare(r, D(2026, 1, 1), None)
    assert unread.word is None and unread.standing == "the Doc was not read"


def test_a_day_with_no_version_in_force_compares_to_the_proposals_only():
    r = rec(versions=[v("Later.", D(2030, 1, 1))])
    c = rr.compare(r, D(2026, 1, 1), rr.DocReading("Else."))
    assert c.word is rr.CompareWord.NO_ADOPTION and c.standing == "no version in force"


# --- Grounds ---------------------------------------------------------------------------------------------------------------

def grant(id_="ra-0001", subjects=(ra.Subject.NOISE,)):
    return ra.RuleAuthority(id_, "bylaws", "7.8", "Powers", ra.Answer.GRANT, ra.Holder.BOARD, tuple(subjects), (), (), "",
                            "The board may adopt rules on quiet hours.", "", ra.Tier.LIKELY, ("rules", "model"))


def test_grounds_name_the_grant_recited_and_a_missing_one_is_a_question_not_no_authority():
    r = rec(versions=[v("No noise after ten.", D(2025, 1, 1))], subjects=("noise",))
    g = grant()
    rows = ra.by_subject([g], [ra.RuleOnFile("rules", "R-12", "Quiet hours", (ra.Subject.NOISE,), "x")])
    got = rr.grounds_for(r, r.versions[0], rows, [g])
    assert got.standing == "authority named, rules on file" and got.grants[0]["id"] == "ra-0001"
    assert got.grants[0]["recital"]["words"] == "The board may adopt rules on quiet hours."
    assert got.grants[0]["tier"] == "likely" and not got.no_grant_found
    assert any(x["reach"] == "depends" for x in got.reach)                      # jason's labeled reading of Civil Code 4355

    none = rr.grounds_for(r, r.versions[0], ra.by_subject([], [ra.RuleOnFile("rules", "R-12", "q", (ra.Subject.NOISE,), "x")]), [])
    assert none.no_grant_found and none.standing == "rules on file, no grant found"
    assert "question" in none.note and "no authority" not in none.note.replace("never an accusation", "")
    unread = rr.grounds_for(r, r.versions[0], None, [])
    assert unread.standing == "not read" and not unread.no_grant_found and not unread.read
    nosubject = rr.grounds_for(rec(title="", versions=[v("x")]), None, ra.by_subject([], []), [])
    assert nosubject.standing == "no subject read" and not nosubject.no_grant_found


def test_a_subject_is_read_from_the_heading_when_none_is_stored():
    r = rec(title="Quiet hours and noise", versions=[v("No loud noise.")])
    subjects, how = rr.subjects_of(r)
    assert "noise" in subjects and "read by jason" in how
    assert rr.subjects_of(rec(versions=[v("x")], subjects=("pets",))) == (("pets",), "stored (a person confirmed)")


# --- Uses ------------------------------------------------------------------------------------------------------------------

def test_a_use_is_a_list_with_the_version_of_its_day_and_none_linked_is_not_a_finding():
    r = rec(versions=[v("One.", D(2024, 1, 1)), v("Two.", D(2025, 6, 1))])
    out = rr.uses_view(r, [rr.Use("hearing", D(2025, 2, 1), "decision recorded", {"route": "#/hearings?id=x"}),
                           rr.Use("decision", D(2026, 2, 1), "carried", {"route": "#/decisions?id=y"}),
                           rr.Use("hearing", D(2020, 1, 1), "hearing planned")], D(2026, 3, 1))
    assert [(u["on"], u["version"]) for u in out["uses"]] == [("2020-01-01", ""), ("2025-02-01", "v1"), ("2026-02-01", "v2")]
    assert out["uses"][1]["isCurrent"] is False and out["uses"][2]["isCurrent"] is True
    assert "no version of the rule is in force" in out["uses"][0]["versionNote"]
    assert out["count"] == 3 and out["note"] == rr.USE_NOTE
    empty = rr.uses_view(r, [], None)
    assert empty["count"] == 0 and "not a finding" in empty["note"] and empty["byOutcome"] == []


# --- The book --------------------------------------------------------------------------------------------------------------

def book():
    return RuleBook([rec("rules#R-1", "R-1", "Pets", versions=[v("Pets on leash.")], subjects=("pets",)),
                     rec("rules#R-2", "R-2", "Quiet hours", versions=[v("Quiet.", D(2025, 1, 1))], subjects=("noise",)),
                     rec("rules#R-3", "R-3", "Signs", versions=[v("Draft.", proposed=True)], subjects=("signs",))],
                    document="manual", source="stored in x")


def test_the_book_counts_statuses_over_all_records_and_filters_the_rows():
    out = rr.book_view(book(), D(2026, 1, 1), [])
    c = out["counts"]
    assert (c["records"], c["adopted"], c["adoptionNotOnRecord"], c["proposed"], c["noVersionInForce"]) == (3, 2, 1, 1, 0)
    only = rr.book_view(book(), D(2026, 1, 1), [], status="adoption-not-on-record")
    assert [r["id"] for r in only["records"]] == ["rules#R-1"] and only["counts"]["records"] == 3
    assert [r["id"] for r in rr.book_view(book(), D(2026, 1, 1), [], subject="noise")["records"]] == ["rules#R-2"]
    assert rr.book_view(book(), D(2026, 1, 1), [], status="adopted")["records"][0]["statusWord"] == rr.NOT_ON_RECORD
    assert out["stored"] is True and rr.CAVEAT in out["caveats"]


def test_a_rule_on_a_day_is_recited_first_with_its_citation_source_and_adoption():
    lines = rr.recite(rec(versions=[v("No noise after ten.", D(2025, 1, 1))]), D(2026, 1, 1))
    assert lines[1].startswith("  jason://rules/rules#R-12 v1, adopted 2025-01-01") and lines[3].strip() == "No noise after ten."
    gone = rr.recite(rec(versions=[v("x", D(2030, 1, 1))]), D(2026, 1, 1))
    assert "no version of the rule is in force" in gone[1]


# --- On disk: the task, the command, the tool and the loaders ------------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    from jason.community import community
    from jason.tasks import manual as manual_task

    key = manual_task.spec_of(community()).document
    path = tmp_path / "rule-records" / f"{key}.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(book().to_dict()), encoding="utf-8")
    return tmp_path


def tree(root):
    return sorted((str(p.relative_to(root)), p.stat().st_size) for p in root.rglob("*") if p.is_file())


def test_the_task_reads_the_stored_records_and_writes_nothing(store):
    from jason.tasks import rule_records as task

    before = tree(store)
    loaded = task.load(store, records="stored", doc=False, grants=False)
    assert [r.id for r in loaded.book.records] == ["rules#R-1", "rules#R-2", "rules#R-3"]
    assert loaded.record("R-2").id == "rules#R-2" and loaded.record("nope") is None
    assert loaded.authorities is None and loaded.rows is None and not loaded.doc_read
    with pytest.raises(Exception, match="no stored rule records"):
        task.load(store / "elsewhere", records="stored", doc=False, grants=False)
    assert tree(store) == before


def test_the_views_have_the_handoffs_shapes_and_a_miss_is_a_miss(store):
    from jason.tasks import rule_records as task

    before = tree(store)
    listing = task.list_view(store, as_of="2026-01-01", records="stored")
    assert listing["found"] and listing["counts"]["records"] == 3 and listing["asOf"] == "2026-01-01"
    assert set(listing["records"][0]) >= {"id", "number", "title", "kind", "subjects", "status", "statusWord", "adoptionOnRecord",
                                          "inForce", "grounds", "openProposals", "uses", "compare"}
    assert any("no grants are stored" in n for n in listing["notes"])
    assert listing["grantsRead"] is False and listing["records"][0]["grounds"]["standing"] == "not read"

    one = task.record_detail("R-2", store, as_of="2026-01-01", records="stored")
    assert one["version"]["words"] == "Quiet." and one["version"]["source"]["kind"] == rr.SOURCE_AS_READ
    assert one["status"]["statusWord"] == "adopted" and one["compare"]["standing"] == "the Doc was not read"
    assert one["caveats"] == [rr.CAVEAT] and one["address"] == "jason://rules/rules#R-2"
    early = task.record_detail("R-2", store, as_of="2024-01-01", records="stored")
    assert early["version"] is None and any("does not show which words" in g for g in early["gaps"])

    assert [x["id"] for x in task.history_detail("R-3", store, records="stored")["versions"]] == ["v1"]
    assert task.compare_detail("R-1", store, records="stored")["standing"] == "the Doc was not read"
    uses = task.uses_detail("R-1", store, records="stored")
    assert uses["count"] == 0 and "no use linked" in uses["note"]
    assert task.events_detail("R-1", "", store, records="stored")["note"] == "nothing recorded since jason first read it"
    assert task.events_detail("", "rc-1", store)["found"] is False
    assert task.record_detail("zzz", store, records="stored")["found"] is False
    assert task.record_detail("R-1", store, as_of="yesterday", records="stored")["found"] is False
    assert tree(store) == before


def test_a_use_is_linked_only_where_the_use_cites_the_rule(store):
    from jason.tasks import rule_records as task

    hearings = store / "zoom"
    hearings.mkdir()
    (hearings / "hearings.json").write_text(json.dumps({"hearings": [
        {"start": "2026-02-10T18:00:00", "address": "1 Example St", "statement": "see jason://rules/rules#R-2 for the hours"},
        {"start": "2026-03-10T18:00:00", "address": "2 Example St", "statement": "no rule cited"}]}), encoding="utf-8")
    out = task.uses_detail("R-2", store, records="stored")
    assert out["count"] == 1 and out["uses"][0]["kind"] == "hearing" and out["uses"][0]["version"] == "v1"
    assert "1 Example" not in json.dumps(out) and out["uses"][0]["ref"]["route"].startswith("#/hearings?id=2026-02-10|")
    assert task.uses_detail("R-1", store, records="stored")["count"] == 0


def test_the_command_lists_shows_and_writes_nothing(store, monkeypatch, capsys):
    import argparse

    from jason.commands import rule_records as cmd
    from jason.tasks import rule_records as task

    monkeypatch.setattr(cmd, "_data_dir", lambda args: store)
    real = task.load
    monkeypatch.setattr(task, "load", lambda *a, **k: real(*a, **{**k, "doc": False, "grants": False}))

    def run(**kw):
        base = dict(list=False, status="", subject="", as_of="2026-01-01", show="", history="", compare="", uses="",
                    records="stored", no_doc=True, no_grants=True, json=False, env=None)
        return cmd.cmd_rule_records(argparse.Namespace(**{**base, **kw}))

    before = tree(store)
    assert run() == 0
    out = capsys.readouterr().out
    assert "3 rule records" in out and "in force, adoption not on record" in out and "R-2" in out
    assert run(show="R-2") == 0
    shown = capsys.readouterr().out
    assert shown.index("Quiet.") < shown.index("jason's readings")                     # the words first, then the readings
    assert run(history="R-2", json=True) == 0 and json.loads(capsys.readouterr().out)["found"] is True
    assert run(compare="R-2") == 0 and "the Doc was not read" in capsys.readouterr().out
    assert run(uses="R-2") == 0 and "no use linked" in capsys.readouterr().out
    assert run(show="missing") == 2 and run(show="R-2", history="R-2") == 2 and run(as_of="x") == 2
    assert tree(store) == before


def test_the_mcp_tools_are_read_only_and_serve_the_board_and_governance(store):
    from jason import api
    from jason.mcp.server import tools_for

    for profile in ("board", "governance"):
        assert {"rule_records", "rule_record"} <= {t.__name__ for t in tools_for(profile)}
    import inspect

    assert all("by" not in inspect.signature(getattr(api, n)).parameters for n in ("rule_records", "rule_record"))   # none writes
    before = tree(store)
    out = api.rule_records(as_of="2026-01-01", records="stored", data_dir=store)
    assert out["counts"]["records"] == 3
    assert api.rule_record("R-2", as_of="2026-01-01", records="stored", data_dir=store)["version"]["words"] == "Quiet."
    assert api.rule_record("R-3", view="history", records="stored", data_dir=store)["versions"][0]["stage"] == "proposed"
    assert api.rule_record("R-2", view="compare", records="stored", data_dir=store)["standing"] == "the Doc was not read"
    assert api.rule_record("R-2", view="uses", records="stored", data_dir=store)["count"] == 0
    assert api.rule_record("R-2", view="edit", data_dir=store)["found"] is False
    assert (api.rule_records.__doc__ or "") and "writes nothing" in api.rule_records.__doc__
    assert tree(store) == before


def test_the_web_loaders_serve_the_six_sources_from_disk(store, monkeypatch):
    from jason.web import sources

    monkeypatch.setattr(sys.modules["jason.mcp.county"], "_data_dir", lambda _: store, raising=False)
    loaders = sources.default_loaders()
    for name in ("rule-records", "rule-record", "rule-record-history", "rule-record-compare", "rule-uses", "rule-events"):
        assert name in loaders
    before = tree(store)
    got = loaders["rule-records"]({"records": "stored", "as_of": "2026-01-01"})
    assert got["counts"]["records"] == 3
    assert loaders["rule-record"]({"id": "R-2", "records": "stored"})["found"] is True
    assert loaders["rule-record-history"]({"id": "R-2", "records": "stored"})["versions"][0]["id"] == "v1"
    assert loaders["rule-record-compare"]({"id": "R-2", "records": "stored"})["found"] is True
    assert loaders["rule-uses"]({"id": "R-2", "records": "stored"})["count"] == 0
    assert loaders["rule-events"]({"id": "R-2", "records": "stored"})["found"] is True
    assert loaders["rule-record"]({"id": "", "records": "stored"})["found"] is False
    assert tree(store) == before
