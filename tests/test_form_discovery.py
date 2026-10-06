"""The form-discovery pass (docs/standard-forms.md, "How to find them") and ``jason discover-forms``.

Everything is made up and offline: a throwaway authorities shelf of a few invented sections, a throwaway documents
outline, a fake ``Reader``, and a tmp data folder. No network, no model, no GPU, and no owner's or association's data.
``LocalModelReader`` is exercised only through a fake model client, and the console and the local-AI preflight are patched
where the command looks them up.
"""

from __future__ import annotations

import argparse
import json

import pytest

from jason.commands import discover_forms as cmd
from jason.community.form_candidates import (
    CandidateSource, CandidateStatus, FormCandidate, JoinBasis,
)
from jason.community.outlines import DocumentOutline, Section
from jason.tasks import form_discovery as fd

SHELF = """# CIV 9001-9005: Chapter 1. Invented

- Source: made up for a test

## CIV 9001

- History: invented

9001. (Added by Stats. 2000, Ch. 1, Sec. 1.)

(a) A member may submit a written request to the association to install a rain barrel on the member's patio.

(b) The association shall approve or deny the request in writing within 60 days of receipt. A request not denied in
writing within that time is deemed approved.

## CIV 9002

9002. (Added by Stats. 2000, Ch. 1, Sec. 2.)

The association shall keep the common area clean and shall mow the lawn each month.

## CIV 9003

9003. (Added by Stats. 2000, Ch. 1, Sec. 3.)

Any report of the association shall be filed within 30 days of the end of the year.
"""

RECORDS_SHELF = """# CIV 5210-5210: Invented stand-in

## CIV 5210

5210. (Amended by Stats. 2000, Ch. 1, Sec. 4.)

A member may submit a written request to inspect the association's records, and the association shall make them
available.
"""

RULES_TEXT = (
    "EXAMPLE RULES OF THE EXAMPLE ASSOCIATION\n\n"
    "4.1 Quiet hours\nOwners shall keep noise down after ten at night and before seven in the morning each day.\n\n"
    "4.2 Rain barrels\nNo owner shall install a rain barrel on a patio without prior written approval of the Board. "
    "An owner who wants to install a rain barrel shall submit an application to the Board on the form it provides.\n\n"
    "4.3 Records\nAn owner who wants to inspect the records of the association shall submit a written request.\n"
)


def _outline() -> DocumentOutline:
    starts = [RULES_TEXT.index(h) for h in ("4.1 Quiet", "4.2 Rain", "4.3 Records")]
    ends = starts[1:] + [len(RULES_TEXT)]
    sections = [Section(number=n, title=t, depth=1, start=s, end=e)
                for n, t, s, e in zip(("4.1", "4.2", "4.3"), ("Quiet hours", "Rain barrels", "Records"), starts, ends)]
    return DocumentOutline(key="rules", title="Example Rules", kind="rules", text=RULES_TEXT, sections=sections)


@pytest.fixture
def data(tmp_path):
    root = tmp_path / "data"
    (root / "authorities" / "CIV").mkdir(parents=True)
    (root / "authorities" / "CIV" / "CIV-9001-9003.md").write_text(SHELF, encoding="utf-8")
    (root / "outlines").mkdir()
    (root / "outlines" / "rules.json").write_text(json.dumps(_outline().to_dict()), encoding="utf-8")
    return root


class FakeReader:
    """A ``Reader`` that answers from a table: a span's reading by a word the span holds."""

    model = "fake-model"

    def __init__(self, answers=None):
        self.answers = answers or {}
        self.asked: list[tuple[str, str]] = []

    def read(self, span_text, citation):
        self.asked.append((citation, span_text))
        for word, answer in self.answers.items():
            if word in span_text:
                return answer
        return {"request": False}


def good(quote="submit a written request to the association"):
    return {"request": True, "who_submits": "a member", "to_whom": "the association", "what": "install a rain barrel",
            "required_content": ["the barrel's size"],
            "clocks": [{"for_whom": "the association", "how_long": "60 days", "if_passes": "deemed approved"}],
            "decision": {"who": "the association", "in_writing": True, "reasons": False, "reconsideration": ""},
            "authority": "CIV 9001", "quote": quote}


# -- the seeds ----------------------------------------------------------------------------------------------------------

def test_the_statute_seed_finds_a_request_span_and_skips_a_section_with_none(data):
    found = fd.seed_statutes(data / "authorities")
    assert [c.citation for c in found] == ["CIV 9001"]                 # 9002 has no request language; 9003 only a weak hit
    c = found[0]
    assert c.source is CandidateSource.STATUTE and c.status is CandidateStatus.NEW
    assert {"written-request", "approve-or-deny", "deemed-approved"} <= set(c.seeds)
    assert "approve or deny the request in writing within 60 days" in " ".join(c.quote.split())
    assert "Added by Stats" not in c.quote and "History" not in c.quote        # the span is the operative words, not the page
    assert c.id.startswith("fc-") and c.id == fd.seed_statutes(data / "authorities")[0].id


def test_a_span_stands_on_one_strong_pattern_or_two_weak_ones():
    weak = [p for p in fd.SEED_PATTERNS if not p.strong]
    one = ["The report is due within 30 days of the end of the year."]
    two = ["Any lease shall be reported within 30 days of signing, and a move-in is logged."]
    assert fd.spans_in(one, weak) == []
    kept = fd.spans_in(two, weak)
    assert len(kept) == 1 and set(kept[0][1]) == {"within-days-of", "move-in-out"}


def test_a_list_item_takes_its_lead_in_and_a_long_span_is_cut_at_a_sentence():
    pars = ["The association shall do all of the following:", "(1) On written request, deliver a copy.", "Unrelated."]
    (text, names), = fd.spans_in(pars, fd.SEED_PATTERNS)
    assert text.startswith("The association shall do all of the following:") and "Unrelated" not in text
    long = ["A member may submit a written request. " + "More words follow here. " * 200]
    (cut, _), = fd.spans_in(long, fd.SEED_PATTERNS)
    assert len(cut) <= fd.MAX_SPAN and cut.endswith(".") and cut in long[0]


def test_the_document_seed_finds_prior_written_approval_by_document_and_section(data):
    found = fd.seed_documents(data)
    cites = [c.citation for c in found]
    assert "rules 4.2" in cites and "rules 4.1" not in cites
    four_two = next(c for c in found if c.citation == "rules 4.2")
    assert four_two.source is CandidateSource.DOCUMENT
    assert "prior-written-approval" in four_two.seeds and "application" in four_two.seeds
    assert "ten at night" not in four_two.quote                       # the section's own words, not its neighbor's


def test_an_annexation_is_not_seeded(data):
    out = _outline()
    out.kind = "annexation"
    assert fd.seed_documents(data, outlines=[out]) == []


# -- known as, and the groups -------------------------------------------------------------------------------------------

def test_known_as_matches_an_existing_request_kind_by_citation_and_by_words(tmp_path):
    (tmp_path / "authorities").mkdir()
    (tmp_path / "authorities" / "CIV-5210.md").write_text(RECORDS_SHELF, encoding="utf-8")
    statute = fd.seed_statutes(tmp_path / "authorities")[0]
    kind, why = fd.known_as(statute)
    assert kind == "records request" and "CIV 5210" in why
    doc = fd.seed_documents(tmp_path, outlines=[_outline()])
    by_cite = {c.citation: c for c in doc}
    assert fd.known_as(by_cite["rules 4.3"])[0] == "records request"           # by its words
    assert fd.known_as(by_cite["rules 4.2"])[0] == ""                          # a miss stays a miss


def test_a_statute_and_a_document_that_share_a_subject_are_grouped_with_the_reason(data):
    cands, joins = fd.annotate(fd.seed_statutes(data / "authorities") + fd.seed_documents(data))
    (join,) = joins
    statute = next(c for c in cands if c.source is CandidateSource.STATUTE)
    doc = next(c for c in cands if c.citation == "rules 4.2")
    assert join.statute == statute.id and join.document == doc.id
    assert join.basis is JoinBasis.TERMS and "barrel" in join.reason and "patio" in join.reason
    assert statute.group == doc.group == "g-" + statute.id[3:]
    assert next(c for c in cands if c.citation == "rules 4.3").group == ""      # nothing in the statute it goes with


def test_a_document_that_cites_the_section_is_joined_by_the_citation():
    statute = FormCandidate("fc-1", CandidateSource.STATUTE, "CIV 9001", "A member may submit a written request.")
    doc = FormCandidate("fc-2", CandidateSource.DOCUMENT, "rules 7.1",
                        "Requests are decided as Civil Code section 9001 requires; see also Section 9001 of the Civil Code.")
    (join,) = fd.group([statute, doc])[1]
    assert join.basis is JoinBasis.CITATION and "CIV 9001" in join.reason
    assert [c.group for c in fd.group([statute, doc])[0]] == ["g-1", "g-1"]


def test_both_read_as_one_kind_of_request_is_a_join_on_kind(tmp_path):
    (tmp_path / "authorities").mkdir()
    (tmp_path / "authorities" / "CIV-5210.md").write_text(RECORDS_SHELF, encoding="utf-8")
    cands, joins = fd.annotate(fd.seed_statutes(tmp_path / "authorities") + fd.seed_documents(tmp_path, outlines=[_outline()]))
    (join,) = joins
    assert join.basis is JoinBasis.KIND and '"records request"' in join.reason


def test_a_pair_with_nothing_in_common_is_not_grouped():
    a = FormCandidate("fc-a", CandidateSource.STATUTE, "CIV 9001", "A member may submit a written request about a fence.")
    b = FormCandidate("fc-b", CandidateSource.DOCUMENT, "rules 2.1", "An owner shall register a vehicle annually.")
    cands, joins = fd.group([a, b])
    assert joins == [] and all(c.group == "" for c in cands)


# -- reading ------------------------------------------------------------------------------------------------------------

def _statute(data):
    return fd.seed_statutes(data / "authorities")[0]


def test_a_reading_whose_quote_is_in_the_span_is_kept_with_the_source_of_its_clock(data):
    read = fd.read_candidate(_statute(data), FakeReader({"rain barrel": good()}))
    r = read.reading
    assert r is not None and r.is_request and r.who_submits == "a member" and r.model == "fake-model"
    assert r.clocks[0].how_long == "60 days" and r.clocks[0].source.value == "statute"
    assert r.decision.in_writing is True and read.status is CandidateStatus.NEW


def test_a_reading_whose_quote_is_not_in_the_span_is_dropped_and_the_candidate_flagged(data):
    read = fd.read_candidate(_statute(data), FakeReader({"rain barrel": good("the board will approve every request")}))
    assert read.reading is None and read.status is CandidateStatus.DROPPED and "quote not found" in read.note


def test_a_quote_is_compared_by_its_words_not_its_spacing(data):
    spaced = "submit  a written\nrequest to the   association"
    assert fd.read_candidate(_statute(data), FakeReader({"rain barrel": good(spaced)})).reading is not None


def test_a_span_with_no_request_and_an_unusable_answer_are_noted_and_left_for_a_person(data):
    none = fd.read_candidate(_statute(data), FakeReader())
    assert none.reading is not None and not none.reading.is_request and none.status is CandidateStatus.NEW
    assert "no request" in none.note
    bad = fd.read_candidate(_statute(data), FakeReader({"rain barrel": {"request": True, "quote": ""}}))
    assert bad.reading is None and bad.status is CandidateStatus.NEW and "not usable" in bad.note
    malformed = fd.read_candidate(_statute(data), FakeReader({"rain barrel": {**good(), "clocks": "60 days"}}))
    assert malformed.reading is None and "malformed" in malformed.note


def test_the_local_model_reader_asks_the_duty_model_and_reads_its_json_answer():
    class Model:
        model = "fake-model"
        asked: list = []

        def _ask(self, prompt, schema):
            self.asked.append((prompt, schema))
            return json.dumps(good())

    model = Model()
    reader = fd.LocalModelReader(duty_model=model)
    assert reader.model == "fake-model"
    assert reader.read("A member may submit a written request.", "CIV 9001")["what"] == "install a rain barrel"
    prompt, schema = model.asked[0]
    assert "CIV 9001" in prompt and "A member may submit a written request." in prompt
    assert "quote" in schema["properties"]

    class Garbled(Model):
        def _ask(self, prompt, schema):
            return "not json"

    assert "_problem" in fd.LocalModelReader(duty_model=Garbled()).read("x", "y")


# -- the store, and a person's word -------------------------------------------------------------------------------------

def test_a_reseed_keeps_a_persons_status_and_note_and_drops_a_stale_unread_candidate(data):
    fd.seed(data, community=None)
    store = fd.load(data)
    statute = next(c for c in store.candidates if c.source is CandidateSource.STATUTE)
    fd.decide(data, statute.id, "hold", by="Pat", why="the law is silent on a clock")
    again = fd.seed(data, community=None)
    kept = fd.load(data).get(statute.id)
    assert kept.status is CandidateStatus.HELD and again.added == 0
    # the shelf loses the section: an unread new document candidate would go, the held statute stays, noted
    (data / "authorities" / "CIV" / "CIV-9001-9003.md").write_text("# empty\n", encoding="utf-8")
    (data / "outlines" / "rules.json").write_text(json.dumps({**_outline().to_dict(), "text": "x", "sections": []}), encoding="utf-8")
    result = fd.seed(data, community=None)
    after = fd.load(data)
    assert result.removed >= 1
    assert [c.id for c in after.candidates] == [statute.id]
    assert after.candidates[0].status is CandidateStatus.HELD and "no longer in the latest seed" in after.candidates[0].note


def test_a_seed_by_source_leaves_the_other_source_alone(data):
    fd.seed(data, community=None)
    docs = {c.id for c in fd.load(data).candidates if c.source is CandidateSource.DOCUMENT}
    fd.seed(data, source="statutes", community=None)
    assert {c.id for c in fd.load(data).candidates if c.source is CandidateSource.DOCUMENT} == docs
    with pytest.raises(fd.DiscoveryError):
        fd.seed(data, source="reference", community=None)


def test_a_changed_span_keeps_its_status_and_loses_its_reading(data):
    fd.seed(data, community=None)
    s = next(c for c in fd.load(data).candidates if c.source is CandidateSource.STATUTE)
    fd.read_new(data, FakeReader({"rain barrel": good()}))
    assert fd.load(data).get(s.id).reading is not None
    fd.decide(data, s.id, "confirm", by="Pat")
    longer = FormCandidate(s.id, s.source, s.citation, s.quote + " More.", s.seeds)
    merged = fd.merge_seed(fd.load(data).candidates, [longer], {CandidateSource.STATUTE})
    row = next(c for c in merged if c.id == s.id)
    assert row.status is CandidateStatus.CONFIRMED and row.reading is None and "words changed" in row.note


def test_acts_need_a_name_and_a_reason_and_are_logged(data):
    fd.seed(data, community=None)
    cid = fd.load(data).candidates[0].id
    with pytest.raises(fd.DiscoveryError, match="--by"):
        fd.decide(data, cid, "confirm", by=" ")
    with pytest.raises(fd.DiscoveryError, match="--why"):
        fd.decide(data, cid, "hold", by="Pat")
    with pytest.raises(fd.DiscoveryError, match="--why"):
        fd.decide(data, cid, "drop", by="Pat", why="")
    fd.decide(data, cid, "confirm", by="Pat")
    with pytest.raises(fd.DiscoveryError, match="already confirmed"):
        fd.decide(data, cid, "confirm", by="Pat")
    fd.decide(data, cid, "drop", by="Lee", why="not a request")
    acts = [a for a in fd.acts(data, cid)]
    assert [(a["by"], a["act"], a["why"]) for a in acts] == [("Pat", "confirm", ""), ("Lee", "drop", "not a request")]
    assert all(a["at"] for a in acts) and acts[1]["detail"] == "confirmed -> dropped"
    with pytest.raises(fd.DiscoveryError, match="no candidate"):
        fd.decide(data, "fc-nope", "confirm", by="Pat")


def test_the_report_puts_the_quote_before_the_reading_and_labels_it(data):
    cands, joins = fd.annotate(fd.seed_statutes(data / "authorities") + fd.seed_documents(data))
    cands = [fd.read_candidate(c, FakeReader({"rain barrel": good()})) if c.source is CandidateSource.STATUTE else c for c in cands]
    text = fd.report(cands, joins)
    assert text.index("approve or deny the request") < text.index("A reading for a person")
    assert text.index("A reading for a person") < text.index("**Status: new.**")
    assert "## Group `g-" in text and "Joined with the statute" in text and "never the rule" in text
    assert "None kept" in fd.report([])


# -- the command --------------------------------------------------------------------------------------------------------

@pytest.fixture
def run(data, monkeypatch, capsys):
    monkeypatch.setattr(cmd, "_data_dir", lambda args: data)
    monkeypatch.setattr(cmd, "_community", lambda: None)
    monkeypatch.setattr(cmd, "at_terminal", lambda: True)

    def go(*argv):
        parser = argparse.ArgumentParser(prog="jason")
        sub = parser.add_subparsers()
        cmd.register(sub, lambda p: p.add_argument("--env"), None)
        args = parser.parse_args(["discover-forms", *argv])
        code = args.func(args)
        out = capsys.readouterr()
        return code, out.out, out.err

    return go


def test_the_command_is_registered_in_modules():
    from jason.commands import MODULES

    assert "discover_forms" in MODULES


def test_no_option_lists_what_is_on_disk_and_says_to_seed_when_nothing_is(run):
    code, out, _ = run()
    assert code == 0 and "No form candidates on disk" in out and "--seed" in out
    run("--seed")
    code, out, _ = run()
    assert "Form candidates on disk: 3" in out and "new 3" in out and "groups" in out
    assert "known as an existing request kind or notice row: 1; not known: 2" in out
    assert json.loads(run("--json")[1])["candidates"] == 3


def test_seed_runs_no_model_and_reports_each_pattern(run, data, monkeypatch):
    def no_model(*a, **k):
        raise AssertionError("a seed never runs a model")

    monkeypatch.setattr("jason.local_ai.preflight", no_model)
    monkeypatch.setattr(cmd, "_reader", no_model)
    code, out, _ = run("--seed")
    assert code == 0 and "3 span(s) found" in out and "No model was run" in out and "prior-written-approval" in out
    assert (data / "forms" / "candidates.json").is_file()
    assert [json.loads(l)["act"] for l in (data / "forms" / "candidate-acts.jsonl").read_text().splitlines()] == ["seed"]
    code, out, _ = run("--seed", "--source", "statutes", "--json")
    assert json.loads(out)["found"] == 1


def test_list_show_and_filters(run):
    run("--seed")
    code, out, _ = run("--list", "--source", "statutes")
    assert "CIV 9001" in out and "rules 4.2" not in out and "1 candidate(s)" in out
    assert "1 candidate(s)" in run("--list", "--known")[1] and "rules 4.3" in run("--list", "--known")[1]
    assert "2 candidate(s)" in run("--list", "--unknown")[1]
    assert "No candidate matches." in run("--list", "--status", "confirmed")[1]
    cid = json.loads(run("--list", "--source", "statutes", "--json")[1])["candidates"][0]["id"]
    code, out, _ = run("--show", cid)
    assert code == 0 and "> (a) A member may submit a written request" in out and "Joined with" in out
    code, _, err = run("--show", "fc-nope")
    assert code == 2 and err.startswith("jason discover-forms: no candidate fc-nope")


def test_confirm_needs_by_and_writes_only_a_status_and_the_log(run, data):
    run("--seed")
    cid = json.loads(run("--list", "--json")[1])["candidates"][0]["id"]
    before = json.loads((data / "forms" / "candidates.json").read_text())
    code, _, err = run("--confirm", cid)
    assert code == 2 and err == "jason discover-forms: --confirm needs --by NAME: a person's act is logged under a name\n"
    code, out, _ = run("--confirm", cid, "--by", "Pat", "--why", "a real request")
    assert code == 0 and "did not create a form, a procedure, or a known-form row" in out
    after = json.loads((data / "forms" / "candidates.json").read_text())
    changed = {c["id"]: c for c in after["candidates"]}
    for old in before["candidates"]:
        new = changed[old["id"]]
        assert {k: v for k, v in new.items() if k != "status"} == {k: v for k, v in old.items() if k != "status"}
    assert changed[cid]["status"] == "confirmed"
    assert sorted(p.name for p in (data / "forms").iterdir()) == ["candidate-acts.jsonl", "candidates.json"]
    last = json.loads((data / "forms" / "candidate-acts.jsonl").read_text().splitlines()[-1])
    assert (last["by"], last["act"], last["why"], last["candidate"]) == ("Pat", "confirm", "a real request", cid)


def test_hold_and_drop_need_a_reason(run):
    run("--seed")
    cid = json.loads(run("--list", "--json")[1])["candidates"][0]["id"]
    for act in ("--hold", "--drop"):
        code, _, err = run(act, cid, "--by", "Pat")
        assert code == 2 and "needs --why TEXT" in err
    code, out, _ = run("--hold", cid, "--by", "Pat", "--why", "the law is silent on a clock")
    assert code == 0 and "kept for the board" in out
    code, out, _ = run("--drop", cid, "--by", "Pat", "--why", "not a request")
    assert code == 0 and "set aside, not deleted" in out
    assert "dropped" in run("--list", "--status", "dropped")[1]
    assert run("--seed")[0] == 0 and "dropped" in run("--list", "--status", "dropped")[1]          # a re-seed keeps it dropped


def test_a_stray_option_is_refused(run):
    assert run("--model", "x")[0] == 2
    code, _, err = run("--seed", "--status", "new")
    assert code == 2 and "--status does not go with --seed" in err
    assert run("--list", "--by", "Pat")[0] == 2


def test_read_needs_a_console(run, monkeypatch):
    run("--seed")
    monkeypatch.setattr(cmd, "at_terminal", lambda: False)
    code, out, err = run("--read")
    assert code == 2 and err.startswith("jason discover-forms: reading spans runs a local model") and out == ""


def test_read_refuses_when_the_local_ai_preflight_fails(run, data, monkeypatch):
    from jason.local_ai import LocalAIUnavailable

    run("--seed")

    def down(model, **kw):
        raise LocalAIUnavailable("Ollama is running without the GPU")

    monkeypatch.setattr("jason.local_ai.preflight", down)
    monkeypatch.setattr(cmd, "_reader", lambda model: pytest.fail("no reader is made when the preflight fails"))
    code, _, err = run("--read")
    assert code == 2 and "the local model is not ready, so nothing was read" in err and "without the GPU" in err
    assert all(c["reading"] is None for c in json.loads((data / "forms" / "candidates.json").read_text())["candidates"])


def test_read_reads_new_candidates_and_logs_each(run, data, monkeypatch):
    run("--seed")
    asked = []
    monkeypatch.setattr("jason.local_ai.preflight", lambda model, **kw: asked.append(model))
    fake = FakeReader({"rain barrel": good()})
    monkeypatch.setattr(cmd, "_reader", lambda model: fake)
    code, out, _ = run("--read", "--model", "tiny", "--limit", "1")
    assert code == 0 and asked == ["tiny"] and "Read 1 candidate(s) with fake-model" in out and len(fake.asked) == 1
    code, out, _ = run("--read")
    assert code == 0 and len(fake.asked) == 3                          # the second run reads only what is left, once each
    assert "Nothing to read" in run("--read")[1]
    stored = json.loads((data / "forms" / "candidates.json").read_text())["candidates"]
    # the fake's one answer quotes the statute's words, so it is not found in the document span that also holds "rain barrel":
    # that candidate is dropped; a "no request" answer is a reading too
    assert {c["citation"]: c["status"] for c in stored} == {"CIV 9001": "new", "rules 4.2": "dropped", "rules 4.3": "new"}
    assert {c["citation"] for c in stored if c["reading"] is None} == {"rules 4.2"}
    assert [json.loads(l)["act"] for l in (data / "forms" / "candidate-acts.jsonl").read_text().splitlines()].count("read") == 3


def test_a_read_that_cannot_reach_the_model_refuses_with_its_reason(run, monkeypatch):
    from jason.community.content import ModelUnavailable

    class Down:
        model = "x"

        def read(self, span_text, citation):
            raise ModelUnavailable("the model server is busy with another jason process")

    run("--seed")
    monkeypatch.setattr("jason.local_ai.preflight", lambda model, **kw: None)
    monkeypatch.setattr(cmd, "_reader", lambda model: Down())
    code, _, err = run("--read")
    assert code == 2 and "busy with another jason process" in err


def test_report_prints_or_writes_a_file(run, tmp_path):
    run("--seed")
    code, out, _ = run("--report")
    assert code == 0 and out.startswith("# Form candidates") and "> (a) A member may submit" in out
    target = tmp_path / "out" / "forms.md"
    code, out, _ = run("--report", "--out", str(target), "--source", "documents")
    assert code == 0 and "2 candidate(s)" in out and "rules 4.2" in target.read_text(encoding="utf-8")
