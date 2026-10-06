"""The campaign record and the generation gate (docs/arrivals-design.md, "The handler is chosen when the form is made"; build
step 1a): a reference exists only if a handler does.

Everything is made up: stub communities with made-up forms (no profile's facts), temporary data folders, no network, no model.
The last tests use the real profile only to check that it adopts the campaigns its running request already carries.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone

import pytest

from jason.community.form_library import FormDefinition, Tier
from jason.community.form_refs import Channel, make
from jason.community.forms import AnswerCycle, FormKey, FormQuestion, FormTemplate
from jason.community.response_inbox import ResponseRequest
from jason.tasks import campaigns, form_references
from jason.tasks.campaigns import CampaignRefusal, CampaignStatus
from jason.tasks.recognize import Catalog, recognize

CYCLE = AnswerCycle(2027, date(2026, 10, 1), return_by=date(2026, 10, 23))
AS_OF = date(2026, 9, 1)
NOW = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)


def template(key, code, title="Made-up form"):
    return FormTemplate(key, title, "Civil Code 9900: made up.", "Use this made-up form.",
                        (FormQuestion("Your name", key="name"),), code=code)


# a general form: tied to no law, so a person chooses its handler
SURVEY = FormDefinition(template=template(FormKey.IDR, "AC"), tier=Tier.CUSTOM, key="survey", version="3", as_of=AS_OF,
                        procedure="respond")
# a process form: its authority names its handler
PROCESS = FormDefinition(template=template(FormKey.OWNER_INFO, "KM"), tier=Tier.CUSTOM, key="annual-info", version="2",
                         as_of=AS_OF, authority=("CIV 4041",), procedure="owner-info-cycle", handler="owner-information")
# a form with an authority and no handler, one that names a handler nobody registered, and one whose procedure is missing
NO_HANDLER = FormDefinition(template=template(FormKey.RECORDS, "HR"), tier=Tier.CUSTOM, key="no-handler", authority=("CIV 5210",),
                            procedure="respond")
UNREGISTERED = FormDefinition(template=template(FormKey.RECORDS, "NP"), tier=Tier.CUSTOM, key="unregistered",
                              handler="send-to-the-moon", procedure="respond")
NO_PROCEDURE = FormDefinition(template=template(FormKey.RECORDS, "EF"), tier=Tier.CUSTOM, key="no-procedure",
                              handler="collect-only", procedure="no-such-procedure")
# a form that waits on a slot the community has not given
WAITING = FormDefinition(template=template(FormKey.IDR, "VX"), tier=Tier.CUSTOM, key="waiting", handler="collect-only",
                         procedure="respond", slots=("FEE_SCHEDULE",))
REQUEST = ResponseRequest("annual-2027", "Annual information", PROCESS.template, CYCLE,
                          marker_campaigns=("KM27E", "KM27M", "KM27P"))


class Stub:
    """A community that asks the library for nothing but the forms and requests a test gives it."""

    def __init__(self, *forms, requests=()):
        self._forms, self._requests = forms or (SURVEY, PROCESS, NO_HANDLER, UNREGISTERED, NO_PROCEDURE, WAITING), requests

    def jurisdictions(self):
        return ()

    def form_slots(self):
        return ()

    def form_adjustments(self):
        return ()

    def form_bindings(self):
        return ()

    def custom_forms(self):
        return self._forms

    def response_requests(self):
        return self._requests


def open_one(tmp_path, form="survey", *, channel="email", by="Pat Example", handler="collect-only", community=None, **kw):
    return campaigns.open_campaign(community or Stub(), form, channel=channel, cycle=CYCLE, by=by, data_dir=tmp_path,
                                   handler=handler, now=NOW, **kw)


def refused(tmp_path, **kw):
    with pytest.raises(CampaignRefusal) as why:
        open_one(tmp_path, **kw)
    assert not (tmp_path / campaigns.STORE).exists(), "a refused campaign writes nothing"
    return why.value.reason


# -- opening a campaign ---------------------------------------------------------------------------------------------------

def test_a_form_that_is_not_offered_is_refused_with_what_is_missing(tmp_path):
    assert "no form 'nowhere'" in refused(tmp_path, form="nowhere") and "survey" in refused(tmp_path, form="nowhere")
    assert "'waiting' is not offered: slot FEE_SCHEDULE" in refused(tmp_path, form="waiting")


def test_a_form_whose_cited_section_changed_after_its_day_of_the_law_is_refused_as_stale(tmp_path, monkeypatch):
    from jason.community.form_library import check as lib_check
    from jason.community.form_library.tiers import Check, Finding, Severity

    stale = Finding("survey", Check.RECITALS, Severity.FAIL, "CIV 9900(a)",
                    "stale: the shelf logged a change to its words on 2026-09-30, after the form's as-of 2026-09-01")
    monkeypatch.setattr(lib_check, "check_recitals", lambda form, data_dir, community=None: [stale])
    reason = refused(tmp_path)
    assert "'survey' is stale" in reason and "CIV 9900(a)" in reason and "bump its version" in reason
    monkeypatch.setattr(lib_check, "check_recitals", lambda form, data_dir, community=None: [])
    assert open_one(tmp_path).form == "survey"              # a form whose sections are unchanged opens as before


def test_a_form_with_no_registered_handler_or_procedure_is_refused_and_the_reason_names_it(tmp_path):
    assert "no handler chosen" in refused(tmp_path, form="no-handler", handler=None)
    assert "'send-to-the-moon' is not registered" in refused(tmp_path, form="unregistered", handler=None)
    assert "procedure 'no-such-procedure' does not exist" in refused(tmp_path, form="no-procedure", handler=None)


def test_a_general_form_has_no_handler_until_a_person_chooses_one_from_the_general_handlers(tmp_path):
    reason = refused(tmp_path, handler=None)
    assert "no authority" in reason and "--handler KEY" in reason and "collect-only" in reason and "sheet-register" in reason
    assert "owner-information" not in reason                                        # a process handler is not on the list
    assert "not registered" in refused(tmp_path, handler="send-to-the-moon")
    assert "is for a form with an authority" in refused(tmp_path, handler="owner-information")   # a process handler is not general


def test_a_process_form_takes_only_the_handler_its_authority_names(tmp_path):
    reason = refused(tmp_path, form="annual-info", handler="collect-only")
    assert "serves CIV 4041" in reason and "owner-information" in reason and "'collect-only'" in reason
    assert "serves CIV 4041" in refused(tmp_path, form="annual-info", handler="response-clock")


def test_a_campaign_needs_a_person_and_a_channel_and_a_usable_marker_code(tmp_path):
    assert "--by NAME" in refused(tmp_path, by="  ")
    with pytest.raises(CampaignRefusal, match="not one of email, mail, payhoa"):
        open_one(tmp_path, channel="carrier-pigeon")
    coded = FormDefinition(template=template(FormKey.IDR, ""), tier=Tier.CUSTOM, key="uncoded", handler="collect-only", procedure="respond")
    with pytest.raises(CampaignRefusal, match="no usable marker code"):
        open_one(tmp_path, form="uncoded", community=Stub(coded))


def test_a_lawful_open_writes_the_row_with_the_version_and_the_day_of_the_law_and_nothing_else(tmp_path):
    row = open_one(tmp_path, options={"sheet": "Register", "tab": "2027"})
    assert (row.code, row.form, row.version, row.as_of, row.handler, row.procedure) == (
        "AC27E", "survey", "3", "2026-09-01", "collect-only", "respond")
    assert row.authority == () and row.kind == "general" and row.is_open and not row.adopted
    assert (row.channel, row.year, row.opened, row.return_by, row.by, row.chosen_at) == (
        "email", 2027, "2026-10-01", "2026-10-23", "Pat Example", "2026-10-05T12:00:00+00:00")
    stored = json.loads((tmp_path / campaigns.STORE).read_text(encoding="utf-8"))
    assert list(stored) == ["AC27E"] and stored["AC27E"]["options"] == {"sheet": "Register", "tab": "2027"}
    assert stored["AC27E"]["cycle"] == {"opened": "2026-10-01", "returnBy": "2026-10-23"} and stored["AC27E"]["authority"] == []
    assert campaigns.load(tmp_path)["AC27E"] == row
    assert sorted(p.name for p in tmp_path.rglob("*") if p.is_file()) == ["campaigns.json"]        # no copy, no reference
    process = open_one(tmp_path, form="annual-info", channel=Channel.MAIL, handler=None)
    assert process.code == "KM27M" and process.authority == ("CIV 4041",) and process.handler == "owner-information"
    assert process.kind == "process" and process.procedure == "owner-info-cycle"
    assert sorted(campaigns.load(tmp_path)) == ["AC27E", "KM27M"]


def test_a_campaign_is_opened_once_and_closed_by_a_person(tmp_path):
    open_one(tmp_path)
    with pytest.raises(CampaignRefusal, match="already exists.*close it first"):
        open_one(tmp_path)
    closed = campaigns.close_campaign(tmp_path, "ac27e", by="Pat Example", now=NOW)
    assert closed.status is CampaignStatus.CLOSED and closed.closed_by == "Pat Example" and not closed.is_open
    with pytest.raises(CampaignRefusal, match="already closed"):
        campaigns.close_campaign(tmp_path, "AC27E", by="Pat Example")
    with pytest.raises(CampaignRefusal, match="--by NAME"):
        campaigns.close_campaign(tmp_path, "AC27E", by="")
    with pytest.raises(CampaignRefusal, match="no campaign 'NOPE'"):
        campaigns.close_campaign(tmp_path, "NOPE", by="Pat Example")
    with pytest.raises(CampaignRefusal, match="already exists \\(closed"):
        open_one(tmp_path)                                         # a code names one cycle: its copies already carry it


# -- the gate -------------------------------------------------------------------------------------------------------------

def test_the_gate_blocks_a_form_with_no_open_campaign_and_names_how_to_open_one(tmp_path, capsys):
    stub = Stub()
    with pytest.raises(CampaignRefusal, match="no campaign is open for form 'survey' by email.*--open survey"):
        campaigns.require(stub, tmp_path, "survey", "email", 2027)
    for form in ("nowhere", "waiting", "no-handler", "unregistered"):
        with pytest.raises(CampaignRefusal):
            campaigns.require(stub, tmp_path, form, "email", 2027)
    assert campaigns.gate(stub, tmp_path, "survey", "email", 2027) == 2
    assert capsys.readouterr().err.startswith("jason: no campaign is open for form 'survey'")
    open_one(tmp_path)
    assert campaigns.gate(stub, tmp_path, "survey", "email", 2027) == 0 and capsys.readouterr().err == ""
    with pytest.raises(CampaignRefusal, match="no campaign is open for form 'survey' by mail"):
        campaigns.require(stub, tmp_path, "survey", "mail", 2027)           # another channel is another campaign
    with pytest.raises(CampaignRefusal, match="no campaign is open for form 'survey' by email for 2028"):
        campaigns.require(stub, tmp_path, "survey", "email", 2028)
    campaigns.close_campaign(tmp_path, "AC27E", by="Pat Example")
    with pytest.raises(CampaignRefusal, match="AC27E is closed"):
        campaigns.require(stub, tmp_path, "survey", "email", 2027)


def test_the_cycle_already_running_goes_through_and_a_dry_run_writes_nothing(tmp_path):
    stub = Stub(requests=(REQUEST,))
    row = campaigns.require(stub, tmp_path, "annual-info", "email", 2027)             # a dry run: reads, writes nothing
    assert row.code == "KM27E" and row.adopted and not row.stored and row.handler == "owner-information"
    assert not (tmp_path / campaigns.STORE).exists()
    assert campaigns.require(stub, tmp_path, "annual-info", "mail").code == "KM27M"      # no year given: the open one
    row = campaigns.require(stub, tmp_path, "annual-info", "email", 2027, adopt=True)   # a real send writes the three rows
    assert row.stored and sorted(campaigns.load(tmp_path)) == ["KM27E", "KM27M", "KM27P"]
    assert campaigns.require(stub, tmp_path, "annual-info", Channel.PAYHOA, 2027).code == "KM27P"
    # a form no running request names still needs a campaign
    with pytest.raises(CampaignRefusal, match="no campaign is open for form 'survey'"):
        campaigns.require(stub, tmp_path, "survey", "email", 2027)


def test_adopting_reads_the_requests_and_the_library_and_rewrites_no_data(tmp_path):
    form_references.record(tmp_path, make("KM", 2027, Channel.EMAIL, membership_id=1, unit_id=2).text, form="annual-info",
                           year=2027, membershipId=1, unitId=2, unit="1 Example Way", channel="email")
    before = (tmp_path / form_references.STORE).read_text(encoding="utf-8")
    rows = campaigns.adopt_existing(Stub(requests=(REQUEST,)), tmp_path, now=NOW)
    assert [r.code for r in rows] == ["KM27E", "KM27M", "KM27P"]
    first = rows[0]
    assert (first.form, first.version, first.as_of, first.authority, first.handler, first.procedure) == (
        "annual-info", "2", "2026-09-01", ("CIV 4041",), "owner-information", "owner-info-cycle")
    assert (first.channel, first.year, first.opened, first.return_by, first.adopted, first.chosen_at) == (
        "email", 2027, "2026-10-01", "2026-10-23", True, "2026-10-05T12:00:00+00:00")
    assert (tmp_path / form_references.STORE).read_text(encoding="utf-8") == before
    assert campaigns.adopt_existing(Stub(requests=(REQUEST,)), tmp_path) == []                   # once; nothing is written twice
    # a request whose form the community cannot make is not adopted, and says why
    planned, skipped = campaigns.plan_adoption(Stub(SURVEY, requests=(REQUEST,)), tmp_path / "other")
    assert planned == [] and len(skipped) == 3 and "not offered" in skipped[0]


# -- the sent copy points at its campaign -----------------------------------------------------------------------------------

def test_a_sent_copys_entry_carries_its_campaign_and_the_form_version(tmp_path):
    open_one(tmp_path, form="annual-info", handler=None)
    ref = make("KM", 2027, Channel.EMAIL, membership_id=1, unit_id=2).text
    assert campaigns.stamp(tmp_path, ref) == {"campaign": "KM27E", "formVersion": "2"}
    entry = form_references.record(tmp_path, ref, form="annual-info", year=2027, membershipId=1, unitId=2, unit="1 Example Way",
                                   channel="email", **campaigns.stamp(tmp_path, ref))
    assert entry["campaign"] == "KM27E" and entry["formVersion"] == "2"
    assert form_references.load(tmp_path)[ref]["campaign"] == "KM27E"
    other = make("AC", 2027, Channel.EMAIL, membership_id=1, unit_id=2).text
    assert campaigns.stamp(tmp_path, other) == {}                                   # no campaign row: recorded as it always was


def test_an_old_entry_with_no_campaign_belongs_to_the_campaign_its_marker_names(tmp_path):
    ref = make("KM", 2027, Channel.EMAIL, membership_id=7, unit_id=9).text
    form_references.record(tmp_path, ref, form="annual-info", year=2027, membershipId=7, unitId=9, unit="2 Example Way",
                           channel="email")
    assert "campaign" not in form_references.load(tmp_path)[ref]
    assert campaigns.campaign_of(tmp_path, ref) is None                             # no row yet
    campaigns.adopt_existing(Stub(requests=(REQUEST,)), tmp_path, now=NOW)
    assert campaigns.campaign_of(tmp_path, ref).code == "KM27E"                     # by the marker's prefix
    assert campaigns.campaign_of(tmp_path, "km27e").handler == "owner-information"  # or by the code
    assert campaigns.campaign_of(tmp_path, "no marker here") is None


# -- recognition and the inbox read the catalog through it ---------------------------------------------------------------------

def test_recognition_returns_the_campaign_and_its_handler_and_still_recognizes_a_copy_with_no_row(tmp_path):
    newer = make("KM", 2027, Channel.EMAIL, membership_id=1, unit_id=2).text
    older = make("KM", 2027, Channel.EMAIL, membership_id=3, unit_id=4).text
    form_references.record(tmp_path, older, form="annual-info", year=2027, membershipId=3, unitId=4, unit="4 Example Way",
                           channel="email")
    plain = recognize(tmp_path, REQUEST, subject=f"Re: [Ref {older}]", images=False)
    assert plain.outcome.value == "recognized" and plain.copy.handler == "" and plain.copy.campaign == "KM27E"
    assert "handler" not in plain.copy.to_json()                                     # no row, no pointers
    campaigns.adopt_existing(Stub(requests=(REQUEST,)), tmp_path, now=NOW)
    form_references.record(tmp_path, newer, form="annual-info", year=2027, membershipId=1, unitId=2, unit="1 Example Way",
                           channel="email", **campaigns.stamp(tmp_path, newer))
    for ref, version in ((newer, "2"), (older, "")):
        found = recognize(tmp_path, REQUEST, subject=f"Re: [Ref {ref}]", images=False)
        assert found.outcome.value == "recognized" and found.copy.reference == ref
        assert (found.copy.campaign, found.copy.handler, found.copy.form_version) == ("KM27E", "owner-information", version)
        assert found.to_json()["copy"]["handler"] == "owner-information"
    assert Catalog.load(tmp_path).copy(newer).recorded_campaign == "KM27E"


def test_the_outstanding_list_names_each_requests_handler(tmp_path):
    from jason.tasks.response_outstanding import outstanding

    ref = make("KM", 2027, Channel.EMAIL, membership_id=1, unit_id=2).text
    form_references.record(tmp_path, ref, form="annual-info", year=2027, membershipId=1, unitId=2, unit="1 Example Way",
                           channel="email")
    body = outstanding(tmp_path, Stub(requests=(REQUEST,)), units=[])                  # the cycle already runs, row unwritten
    req = body["requests"][0]
    assert req["handler"] == "owner-information" and [c["code"] for c in req["campaigns"]] == ["KM27E", "KM27M", "KM27P"]
    assert all(c["recorded"] is False for c in req["campaigns"]) and req["sent"] == 1
    from jason.commands.responses import _outstanding_lines

    assert any("handler: owner-information (campaigns KM27E, KM27M, KM27P)" in line for line in _outstanding_lines(body))
    campaigns.adopt_existing(Stub(requests=(REQUEST,)), tmp_path)
    assert all(c["recorded"] for c in outstanding(tmp_path, Stub(requests=(REQUEST,)), units=[])["requests"][0]["campaigns"])
    assert outstanding(tmp_path, Stub(SURVEY, requests=(REQUEST,)), units=[])["requests"][0]["handler"] == "owner-information"


# -- jason campaigns ------------------------------------------------------------------------------------------------------

@pytest.fixture
def cli(tmp_path, monkeypatch):
    from jason.commands import campaigns as command

    stub = Stub(requests=(REQUEST,))
    monkeypatch.setattr("jason.community.community", lambda: stub)
    monkeypatch.setattr("jason.commands._shared.data_dir", lambda args=None: tmp_path)
    parser = argparse.ArgumentParser()
    command.register(parser.add_subparsers(), lambda p: p.add_argument("--env", default=None), None)

    def run(*argv):
        args = parser.parse_args(["campaigns", *argv])
        return args.func(args)

    return run


def test_jason_campaigns_lists_shows_opens_and_closes(cli, tmp_path, capsys):
    assert cli() == 0
    listing = capsys.readouterr().out
    assert "Campaigns: 3" in listing and "KM27E" in listing and "owner-information" in listing and "not written yet" in listing
    assert cli("--open", "survey", "--channel", "email", "--cycle-year", "2027", "--handler", "collect-only", "--by", "Pat Example",
               "--option", "sheet=Register", "--return-by", "2026-11-01") == 0
    opened = capsys.readouterr().out
    assert "opened AC27E" in opened and "No copy was made" in opened
    assert cli() == 0
    listing = capsys.readouterr().out
    assert "Campaigns: 4" in listing and "AC27E" in listing and "collect-only" in listing and "return by 2026-11-01" in listing
    assert cli("--show", "ac27e") == 0
    shown = capsys.readouterr().out
    assert "AC27E: survey v3, the law as of 2026-09-01" in shown and "none (a general form)" in shown and "sheet" in shown
    assert "chosen by Pat Example" in shown and "no request watches this campaign" in shown
    assert cli("--show", "KM27E", "--json") == 0
    body = json.loads(capsys.readouterr().out)
    assert body["handler"] == "owner-information" and body["written"] is False and body["copies"] == 0 and body["returned"] == 0
    assert cli("--close", "AC27E", "--by", "Pat Example") == 0 and "closed AC27E by Pat Example" in capsys.readouterr().out
    assert cli("--json") == 0
    rows = {r["code"]: r for r in json.loads(capsys.readouterr().out)["campaigns"]}
    assert rows["AC27E"]["status"] == "closed" and rows["KM27P"]["status"] == "open"
    assert cli("--adopt") == 0 and "adopted 3 campaign(s)" in capsys.readouterr().out
    assert sorted(campaigns.load(tmp_path)) == ["AC27E", "KM27E", "KM27M", "KM27P"]


def test_jason_campaigns_refuses_with_the_reason_and_exit_2_and_a_dry_run_is_the_same(cli, tmp_path, capsys):
    base = ["--channel", "email", "--cycle-year", "2027", "--by", "Pat Example"]
    for argv, words in (
            (["--open", "nowhere", *base], "there is no form 'nowhere'"),
            (["--open", "waiting", *base], "'waiting' is not offered: slot FEE_SCHEDULE"),
            (["--open", "no-handler", *base], "no handler chosen"),
            (["--open", "survey", *base], "no authority, so a person chooses its handler"),
            (["--open", "annual-info", *base, "--handler", "collect-only"], "serves CIV 4041"),
            (["--open", "survey", "--channel", "email", "--cycle-year", "2027", "--handler", "collect-only"], "--by NAME"),
            (["--open", "survey", "--cycle-year", "2027", "--by", "x", "--handler", "collect-only"], "--channel is required"),
            (["--open", "survey", "--channel", "email", "--by", "x", "--handler", "collect-only"], "--cycle-year is required"),
            (["--open", "survey", *base, "--option", "novalue"], "NAME=VALUE"),
            (["--close", "NOPE", "--by", "x"], "no campaign 'NOPE'"),
            (["--show", "NOPE"], "no campaign 'NOPE'"),
            (["--channel", "email"], "--channel does not go with the listing")):
        assert cli(*argv) == 2, argv
        out = capsys.readouterr()
        assert out.err.startswith("jason: ") and words in out.err and out.out == "", (argv, out.err)
    assert not (tmp_path / campaigns.STORE).exists()


def test_the_owner_information_command_is_gated_before_it_makes_a_reference(tmp_path, capsys):
    """The gate the batch commands call: the cycle already running passes; a form with no campaign is refused as
    ``jason: <reason>`` with exit 2, dry run or not."""
    stub = Stub(requests=(REQUEST,))
    assert campaigns.gate(stub, tmp_path, "annual-info", Channel.EMAIL, 2027, adopt=False) == 0
    assert not (tmp_path / campaigns.STORE).exists()
    assert campaigns.gate(stub, tmp_path, "annual-info", Channel.EMAIL, 2027, adopt=True) == 0
    assert (tmp_path / campaigns.STORE).is_file()
    assert campaigns.gate(stub, tmp_path, "survey", Channel.EMAIL, 2027, adopt=True) == 2
    assert capsys.readouterr().err.startswith("jason: no campaign is open for form 'survey' by email for 2027")


def test_the_owner_info_commands_that_make_a_reference_refuse_first_and_a_dry_run_says_the_same(tmp_path, capsys):
    from types import SimpleNamespace

    from jason.commands import owner_info

    forms = SimpleNamespace(OWNER_INFO=PROCESS.template, OWNER_INFO_CYCLE=CYCLE)
    never = lambda args: pytest.fail("a refused command asks nothing of PayHOA")            # noqa: E731
    stub = Stub()                                                                          # no running request, no campaign
    for run, args in ((owner_info._email_batch, SimpleNamespace(yes=False)), (owner_info._email_batch, SimpleNamespace(yes=True)),
                      (owner_info._mail_batch, SimpleNamespace(yes=False)), (owner_info._mail_batch, SimpleNamespace(yes=True)),
                      (owner_info._prefill, SimpleNamespace(emailed=True, out="x", prefill=["1 Example Way"]))):
        if run is owner_info._prefill:
            (tmp_path / "packets" / "owner-information-2027").mkdir(parents=True, exist_ok=True)
            (tmp_path / "packets" / "owner-information-2027" / "packet.pdf").write_bytes(b"%PDF-")
        assert run(args, never, stub, forms, tmp_path) == 2
        err = capsys.readouterr().err
        assert err.startswith("jason: no campaign is open for form 'annual-info'") and "--open annual-info" in err
    assert not (tmp_path / campaigns.STORE).exists()


# -- the real profile -----------------------------------------------------------------------------------------------------

def test_the_real_profile_adopts_its_three_owner_information_campaigns(tmp_path):
    from jason.community import community

    rows = campaigns.adopt_existing(community(), tmp_path)
    assert [r.code for r in rows] == ["NP27E", "NP27M", "NP27P"]
    assert {r.handler for r in rows} == {"owner-information"} and {r.procedure for r in rows} == {"owner-info-cycle"}
    assert {r.authority for r in rows} == {("CIV 4041",)} and {r.form for r in rows} == {"owner-info"}
    assert all(r.version and r.adopted and r.is_open for r in rows) and {r.year for r in rows} == {2027}
    for channel in ("email", "mail", "payhoa"):
        assert campaigns.require(community(), tmp_path, "owner-info", channel, 2027).handler == "owner-information"
    assert campaigns.gate(community(), tmp_path, "owner-info", Channel.EMAIL, 2027) == 0
    # a reference an older entry carries (no campaign) resolves to its campaign by its marker's prefix
    ref = make("NP", 2027, Channel.EMAIL, membership_id=1, unit_id=2).text
    assert campaigns.campaign_of(tmp_path, ref).code == "NP27E"
