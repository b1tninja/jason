"""The form library: tiers, the chain, slots, adjustments, bindings, and the seven checks (docs/form-library-design.md).

Everything here is made up: a throwaway shelf of statutes under ``tmp_path``, stub communities, and a throwaway second
profile. No network, no model, no real data folder.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import textwrap
from datetime import date

import pytest

from jason.community import Community, community
from jason.community import profile as profiles
from jason.community.form_library import (
    Add,
    Adjust,
    Bind,
    Channel,
    Check,
    Clock,
    DayKind,
    FormDefinition,
    Library,
    Required,
    SetBy,
    Severity,
    Slot,
    Status,
    Tier,
)
from jason.community.form_library.check import check, read_recital
from jason.community.form_library.resolve import fill_slots, resolve
from jason.community.forms import FormKey, FormQuestion, FormTemplate, QuestionKind, ReadAs

AS_OF = date(2026, 10, 5)


# -- a made-up shelf, a made-up form, a made-up community ----------------------------------------------------------------

def shelf(tmp_path, sections: dict[str, str], *, changed: dict[str, str] | None = None):
    """A data folder whose authorities shelf holds each made-up CIV section (its number and its words)."""
    root = tmp_path / "data"
    folder = root / "authorities" / "CIV"
    folder.mkdir(parents=True)
    pages = []
    for number, words in sections.items():
        file = f"authorities/CIV/CIV-{number}.md"
        (root / file).write_text(f"# CIV {number}: made up\n\n- Source: California Legislature, 2025 session publication, "
                                 f"read with lawlibrary\n\n## CIV {number}\n\n- History: made up\n\n{number}. (Added by Stats. "
                                 f"2012, Ch. 1, Sec. 1.)\n\n{words}\n", encoding="utf-8")
        pages.append({"file": file, "citation": f"CIV {number}", "title": "Made up", "code": "CIV", "start": number, "end": number,
                      "sections": [number], "basis": "a duty", "why": ["made up"], "session": "2025"})
    (root / "authorities" / "manifest.json").write_text(json.dumps({"exported": "2026-10-04", "session": "2025", "pages": pages}),
                                                        encoding="utf-8")
    if changed:
        rows = [{"citation": f"CIV {n}", "old": "a" * 64, "new": "b" * 64, "when": when} for n, when in changed.items()]
        (root / "authorities" / "changes.json").write_text(json.dumps(rows), encoding="utf-8")
    return root


WORDS = "(a) The made-up association shall do a thing.\n\n(b) The made-up association shall do another thing."


def template(form=FormKey.IDR, title="Demo request", code="", **kw):
    return FormTemplate(form, title, "Civil Code 9900: a made-up request.", "Use this made-up form.",
                        (FormQuestion("Your name", key="name"), FormQuestion("What do you want?", QuestionKind.PARAGRAPH)),
                        code=code, **kw)


def definition(key="demo", tier=Tier.STATE, jurisdiction="CA", **kw):
    base = dict(template=template(), tier=tier, key=key, jurisdiction=jurisdiction, as_of=AS_OF, handler="collect-only",
                procedure="respond")
    return FormDefinition(**{**base, **kw})


class Stub:
    """A community that asks the library for nothing but its defaults and what a test gives it."""

    def __init__(self, *, chain=("CA",), slots=(), changes=(), bindings=(), custom=()):
        self.chain, self._slots, self._changes, self._bindings, self._custom = chain, slots, changes, bindings, custom

    def jurisdictions(self):
        return self.chain

    def form_slots(self):
        return self._slots

    def form_adjustments(self):
        return self._changes

    def form_bindings(self):
        return self._bindings

    def custom_forms(self):
        return self._custom


def library(*definitions) -> Library:
    lib = Library()
    for d in definitions:
        lib.register(d)
    return lib


# -- the shipped library: the chain, the two moved forms ------------------------------------------------------------------

def test_the_default_chain_is_us_then_ca_and_the_two_generic_forms_are_the_first_state_definitions():
    assert Community.jurisdictions(community()) == ("US", "CA")
    resolved = resolve(community())
    assert resolved.chain == ("US", "CA")
    ca = [f for f in resolved.forms if f.definition.jurisdiction == "CA"]
    assert [f.key for f in ca] == ["idr-request", "records-request"]
    assert all(f.tier is Tier.STATE and f.status is Status.READY for f in ca)
    assert [t.key for t in community().forms()] == [FormKey.IDR, FormKey.RECORDS, FormKey.OWNER_INFO]
    us = resolve(Stub(chain=("US",)))
    assert us.forms == () and us.problems == ()                                    # the federal pack is registered, and empty


def test_importing_the_library_loads_no_pack_and_no_profile():
    code = ("import sys, jason.community.form_library as f\n"
            "assert 'jason.community.form_library.ca' not in sys.modules\n"
            "assert not [m for m in sys.modules if m.startswith('jason_')]\n"
            "f.definitions('CA')\n"
            "assert 'jason.community.form_library.ca.idr' in sys.modules\n"
            "assert not [m for m in sys.modules if m.startswith('jason_')]\n")
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


def test_an_unknown_jurisdiction_is_a_finding_not_a_crash():
    resolved = resolve(Stub(chain=("US", "ZZ")))
    assert [p.item for p in resolved.problems] == ["jurisdiction ZZ"] and resolved.problems[0].severity is Severity.FAIL
    assert not check(resolved, "no-such-folder").ok


# What the generic forms were on October 5, 2026, before they moved into the library: each question's title, kind,
# whether required, options, field, prefill, and what its written answer reads as.
TODAY = {
    "idr": (
        "Request for Internal Dispute Resolution", "Civil Code 5910 and 5915: a written request to meet and confer with the board.",
        "Use this form to ask the association to meet and confer about a dispute. A board member will contact you to set a meeting.",
        [("Your name", "short", True, (), "name", "", "text"),
         ("Unit address", "short", True, (), "unit-address", "UNIT_ADDRESS", "address"),
         ("Email address", "email", True, (), "email", "", "email"),
         ("What is the dispute about?", "paragraph", True, (), "what-is-the-dispute-about", "", "text"),
         ("What outcome are you asking for?", "paragraph", True, (), "what-outcome-are-you-asking-for", "", "text"),
         ("Preferred meeting days and times", "paragraph", False, (), "preferred-meeting-days-and-times", "", "text")]),
    "records": (
        "Request to Inspect Association Records", "Civil Code 5205: a member's written request to inspect or copy association records.",
        None,
        [("Your name", "short", True, (), "name", "", "text"),
         ("Unit address", "short", True, (), "unit-address", "UNIT_ADDRESS", "address"),
         ("Records requested", "paragraph", True, (), "records-requested", "", "text"),
         ("Time period the records cover", "short", True, (), "time-period-the-records-cover", "", "text"),
         ("Inspect or receive copies?", "choice", True, ("Inspect", "Copies"), "inspect-or-receive-copies", "", "text"),
         ("How should copies be delivered?", "choice", True, ("Email", "Mail", "Pick up in person"),
          "how-should-copies-be-delivered", "", "text")]),
}


@pytest.mark.parametrize("value", ["idr", "records"])
def test_the_resolved_generic_forms_equal_what_they_were(value):
    resolved = next(t for t in community().forms() if t.key.value == value)
    title, authority, description, questions = TODAY[value]
    assert (resolved.title, resolved.authority) == (title, authority)
    assert [(q.title, q.kind.value, q.required, q.options, q.field, q.prefill, q.reads_as.value) for q in resolved.questions] == questions
    assert [q.key for q in resolved.questions][:2] == ["name", "unit-address"]
    assert resolved.code == "" and resolved.signature == "Signature of owner" and resolved.dated is True
    assert resolved.preamble == () and resolved.attestation == "" and resolved.style.write_height == 22.0
    if description is not None:
        assert resolved.description == description


def test_the_records_description_cites_the_subdivisions_the_text_on_disk_has():
    """The old form said 5205(e) for the charge; on disk the charge is 5205(f) and the redaction charge 5205(g)."""
    records = next(t for t in community().forms() if t.key is FormKey.RECORDS)
    assert "5205(e)" not in records.description and "5205(f)" in records.description and "5205(g)" in records.description


def test_owner_information_stays_the_profiles_own_form_and_is_the_same_template():
    from jason.community.spec import spec_module

    resolved = resolve(community())
    owner = resolved.get("owner-info")
    assert owner is not None and owner.tier is Tier.CUSTOM and owner.template is spec_module("forms").OWNER_INFO
    assert owner.definition.handler == "owner-information" and owner.status is Status.READY
    assert resolved.get("records") is resolved.get("records-request")           # by the form's own key or the library's


def test_the_profile_gives_the_library_its_slots_and_no_made_up_ones():
    names = {s.name: s.value for s in community().form_slots()}
    assert {"ASSOCIATION", "RETURN_BY_MAIL", "RETURN_BY_EMAIL", "PORTAL", "BOARD_CONTACT"} <= set(names)
    assert names["ASSOCIATION"] == community().name and "FEE_SCHEDULE" not in names


# -- slots, adjustments, bindings -----------------------------------------------------------------------------------------

def test_a_slot_is_filled_and_a_missing_one_is_named():
    spoken = template(preamble=("Send it to {RETURN_BY_MAIL}, or answer by {RETURN_BY}.",))
    lib = library(definition(template=spoken, slots=("RETURN_BY_MAIL",)))
    waiting = resolve(Stub(), lib)
    form = waiting.forms[0]
    assert form.status is Status.NOT_OFFERED and form.missing == ("slot RETURN_BY_MAIL",) and waiting.templates() == ()
    findings = check(waiting, "none").findings
    assert [(f.check, f.severity, f.item) for f in findings if f.check is Check.SLOTS] == [
        (Check.SLOTS, Severity.NOT_OFFERED, "slot RETURN_BY_MAIL")]
    ready = resolve(Stub(slots=(Slot("RETURN_BY_MAIL", "1 Main St"), Slot("UNUSED", "x"))), lib)
    # the slot the form declared is filled; a per-send token the form did not declare is left for the sender
    assert ready.forms[0].status is Status.READY and ready.templates()[0].preamble == ("Send it to 1 Main St, or answer by {RETURN_BY}.",)
    assert fill_slots("{A} {B}", {"A": "1"}) == "1 {B}"
    with pytest.raises(ValueError):
        Slot("lower case", "x")
    assert resolve(Stub(slots=(Slot("RETURN_BY_MAIL", "  "),)), lib).forms[0].status is Status.NOT_OFFERED     # an empty value is not given


def test_an_adjustment_that_adds_a_question_and_a_paragraph_is_applied_and_recorded():
    lib = library(definition())
    extra = FormQuestion("Which section of the documents?", key="section")
    change = (Add("demo", extra, after="name"), Adjust("demo", preamble=("The documents also ask this.",), channels=(Channel.PAPER,)))
    form = resolve(Stub(changes=change), lib).forms[0]
    assert form.status is Status.ADJUSTED and form.refused == ()
    assert [q.field for q in form.template.questions] == ["name", "section", "what-do-you-want"]
    assert form.template.preamble == ("The documents also ask this.",) and form.channels == (Channel.PAPER,)
    assert form.applied[0] == "question added: section (Which section of the documents?)"
    assert any("preamble" in line for line in form.applied) and any("channels set: paper" in line for line in form.applied)
    # the library's own definition is untouched
    assert lib.definitions("CA")[0].template.preamble == ()


def test_an_adjustment_that_removes_or_rewords_a_required_item_or_drops_a_recital_is_refused():
    req = Required("Say what you want", ("what-do-you-want",), "CIV 9900(a)")
    lib = library(definition(required_content=(req,), recitals=("CIV 9900(a)",)))
    bad = Adjust("demo", remove=("what-do-you-want",), reword=(("name", "Whoever you are"),), drop_recitals=("CIV 9900(a)",))
    resolved = resolve(Stub(changes=(bad,)), lib)
    form = resolved.forms[0]
    assert form.status is Status.READY and form.applied == ()                      # the form keeps the law's words
    assert [q.title for q in form.template.questions] == ["Your name", "What do you want?"]
    assert [r.item for r in form.refused] == ["question what-do-you-want", "question name", "recital CIV 9900(a)"]
    assert "Say what you want" in form.refused[0].message                          # the refusal names what the question carries
    report = check(resolved, "none")
    assert not report.ok and report.status("demo") is Status.FAILING
    assert {f.check for f in report.failing} >= {Check.ADJUSTMENTS}


def test_a_statutory_clock_is_never_lengthened_and_a_stricter_one_is_recorded_with_its_section():
    statute = Clock("current", "receipt", 10, DayKind.BUSINESS, SetBy.STATUTE, "CIV 5210(b)(1)")
    lib = library(definition(association_clocks=(statute,)))

    def run(*clocks):
        return resolve(Stub(changes=(Adjust("demo", clocks=clocks),)), lib).forms[0]

    longer = run(Clock("current", "receipt", 15, DayKind.BUSINESS, SetBy.DOCUMENTS, "ccrs#4.2"))
    assert longer.clocks == (statute,) and "never lengthened" in longer.refused[0].message
    business_for_calendar = run(Clock("current", "receipt", 10, DayKind.BUSINESS, SetBy.DOCUMENTS, "ccrs#4.2"),
                                Clock("current", "receipt", 12, DayKind.CALENDAR, SetBy.DOCUMENTS, "ccrs#4.2"))
    assert business_for_calendar.clocks[0].number == 10 and len(business_for_calendar.refused) == 1     # 12 calendar days: not shown shorter
    elsewhere = run(Clock("current", "the meeting", 5, DayKind.BUSINESS, SetBy.DOCUMENTS, "ccrs#4.2"))
    assert elsewhere.clocks == (statute,) and elsewhere.refused                    # counted from another event: cannot be compared

    stricter = run(Clock("current", "receipt", 7, DayKind.CALENDAR, SetBy.DOCUMENTS, "ccrs#4.2"))
    assert stricter.status is Status.ADJUSTED and stricter.refused == ()
    governing = stricter.clocks[0]
    assert (governing.number, governing.kind, governing.section) == (7, DayKind.CALENDAR, "ccrs#4.2")
    assert governing.note == f"stricter than {statute.words()}" and "stricter clock governs" in stricter.applied[0]

    assert "names the section" in run(Clock("current", "receipt", 7, DayKind.CALENDAR, SetBy.DOCUMENTS)).refused[0].message
    assert "cannot set a statutory clock" in run(Clock("x", "receipt", 1, DayKind.CALENDAR, SetBy.STATUTE)).refused[0].message
    added = run(Clock("acknowledge", "receipt", 2, DayKind.BUSINESS, SetBy.PROPOSED_POLICY))
    assert [c.name for c in added.clocks] == ["current", "acknowledge"] and added.status is Status.ADJUSTED


def test_a_question_a_binding_forbids_is_refused_and_one_on_the_form_fails_the_check():
    bind = Bind("demo", section="ccrs#4.15", decider="the board", forbidden=("who-are-the-tenants",))
    lib = library(definition(tier=Tier.FAMILY, bindable=()))
    ask = Add("demo", FormQuestion("Who are the tenants?", key="who-are-the-tenants"))
    resolved = resolve(Stub(bindings=(bind,), changes=(ask,)), lib)
    assert resolved.forms[0].refused and "forbids" in resolved.forms[0].refused[0].message
    assert [q.field for q in resolved.forms[0].template.questions] == ["name", "what-do-you-want"]
    # the library's own form that asks it is caught by the seventh check
    asks = definition(tier=Tier.FAMILY, template=template(), bindable=())
    forbidden = Bind("demo", section="ccrs#4.15", decider="the board", forbidden=("what-do-you-want",))
    report = check(resolve(Stub(bindings=(forbidden,)), library(asks)), "none")
    assert [(f.check, f.item) for f in report.failing] == [(Check.FORBIDDEN, "what-do-you-want")]
    assert "ccrs#4.15 bars it" in report.failing[0].message


def test_a_family_form_with_no_binding_is_not_offered_and_with_one_it_is_ready():
    lib = library(definition(key="rental", tier=Tier.FAMILY, bindable=("decision", "rehearing")))
    nothing = resolve(Stub(), lib).forms[0]
    assert nothing.status is Status.NOT_OFFERED
    assert nothing.missing == ("binding: section", "binding: decider", "binding: clock decision", "binding: clock rehearing")
    part = Bind("rental", section="ccrs#4.15", decider="the board", clocks=(Clock("decision", "receipt", 30, DayKind.CALENDAR,
                                                                                  SetBy.DOCUMENTS, "ccrs#4.15(a)"),))
    assert resolve(Stub(bindings=(part,)), lib).forms[0].missing == ("binding: clock rehearing",)
    full = Bind("rental", section="ccrs#4.15", decider="the board", clocks=(*part.clocks, Clock("rehearing", "decision", 10, DayKind.CALENDAR,
                                                                                               SetBy.DOCUMENTS, "ccrs#4.15(c)")),
                required=(Required("the lease term", ("name",)),))
    ready = resolve(Stub(bindings=(full,)), lib).forms[0]
    assert ready.status is Status.ADJUSTED and ready.missing == () and [c.name for c in ready.clocks] == ["decision", "rehearing"]
    assert [r.item for r in ready.required_content] == ["the lease term"] and any("bound to ccrs#4.15" in a for a in ready.applied)
    # a bound clock that names no section is refused, so the binding is still incomplete
    sectionless = Bind("rental", section="ccrs#4.15", decider="the board",
                       clocks=(Clock("decision", "receipt", 30, DayKind.CALENDAR, SetBy.DOCUMENTS),
                               Clock("rehearing", "decision", 10, DayKind.CALENDAR, SetBy.PROPOSED_POLICY)))
    assert resolve(Stub(bindings=(sectionless,)), lib).forms[0].missing == ("binding: clock decision (refused)",)
    assert [t for t in resolve(Stub(), lib).templates()] == []                     # nothing offered, nothing made


def test_a_change_or_binding_for_a_form_the_community_does_not_have_is_a_finding():
    resolved = resolve(Stub(changes=(Adjust("nothing"),), bindings=(Bind("nowhere"),)), library(definition()))
    assert [(p.form, p.item) for p in resolved.problems] == [("nothing", "adjustment"), ("nowhere", "binding")]


def test_a_custom_form_needs_a_handler_and_a_procedure_that_exist():
    def custom(**kw):
        return FormDefinition(**{"template": template(FormKey.OWNER_INFO), "tier": Tier.CUSTOM, "key": "survey", **kw})

    def only(*forms):
        return resolve(Stub(chain=(), custom=forms), Library())

    none = only(custom()).forms[0]
    assert none.status is Status.FAILING and none.handler_problems[0].startswith("no handler chosen")
    assert only(custom()).templates() == ()                                         # a form nobody can process is not made
    assert "not registered" in only(custom(handler="invented", procedure="respond")).forms[0].handler_problems[0]
    assert "does not exist" in only(custom(handler="collect-only", procedure="no-such-procedure")).forms[0].handler_problems[0]
    law = only(custom(handler="collect-only", procedure="respond", authority=("CIV 4041",))).forms[0]
    assert "takes a process handler" in law.handler_problems[0]
    wrong = only(custom(handler="owner-information", procedure="respond", authority=("CIV 5205",))).forms[0]
    assert "serves CIV 4040, CIV 4041" in wrong.handler_problems[0]
    fine = only(custom(handler="collect-only", procedure="respond"))
    assert fine.forms[0].status is Status.READY and len(fine.templates()) == 1
    report = check(only(custom()), "none")
    assert [f.item for f in report.failing] == ["handler", "procedure"] and {f.check for f in report.failing} == {Check.HANDLER}
    assert report.status("survey") is Status.FAILING
    # a bare template is a custom form with no handler, and a library form's key is not taken
    bare = only(template())
    assert bare.forms[0].tier is Tier.CUSTOM and bare.forms[0].status is Status.FAILING
    taken = resolve(Stub(custom=(custom(handler="collect-only", procedure="respond", key="demo"),)), library(definition()))
    assert [f.key for f in taken.forms] == ["demo"] and taken.problems[0].item == "key"


# -- the checks: recitals, required content, marker codes ------------------------------------------------------------------

def test_a_recital_is_read_from_the_shelf_and_a_missing_section_or_subdivision_fails_without_an_exception(tmp_path):
    root = shelf(tmp_path, {"9900": WORDS})
    ok = read_recital("CIV 9900(b)", root)
    assert ok.found and ok.words.startswith("(b) The made-up association") and "2025 session publication" in ok.source
    assert not read_recital("CIV 9900(c)", root).found
    assert "opens with (c)" in read_recital("CIV 9900(c)", root).problem and "(a), (b)" in read_recital("CIV 9900(c)", root).problem
    assert read_recital("CIV 9901(a)", root).problem.startswith("CIV 9901 is not on the shelf")
    assert "not a statute citation" in read_recital("nonsense", root).problem
    assert "none was given" in read_recital("ccrs#4.15", root).problem
    whole = read_recital("CIV 9900", root).words
    assert "(a) The made-up" in whole and "(b) The made-up" in whole               # a section with no subdivision is the whole words
    lib = library(definition(recitals=("CIV 9900(a)", "CIV 9900(z)", "CIV 9901(a)")))
    report = check(resolve(Stub(), lib), root)
    assert [(f.check, f.item) for f in report.failing] == [(Check.RECITALS, "CIV 9900(z)"), (Check.RECITALS, "CIV 9901(a)")]
    assert "moved or was repealed" in report.failing[0].message and "not on the shelf" in report.failing[1].message
    assert not check(resolve(Stub(), lib), tmp_path / "an-empty-folder").ok        # no shelf at all: findings, no exception


def test_a_recital_the_shelf_has_since_changed_is_stale_until_the_definition_is_read_again(tmp_path):
    lib = library(definition(recitals=("CIV 9900(a)",), version="3"))
    fresh = shelf(tmp_path / "fresh", {"9900": WORDS}, changed={"9900": "2026-09-01T10:00:00"})
    assert check(resolve(Stub(), lib), fresh).ok                                   # changed before the form's as-of: it was read after
    stale = shelf(tmp_path / "later", {"9900": WORDS}, changed={"9900": "2026-11-01T10:00:00"})
    report = check(resolve(Stub(), lib), stale)
    assert not report.ok and "stale" in report.failing[0].message and "bump its version (now 3)" in report.failing[0].message


def test_required_content_must_be_carried_or_named_as_deferred(tmp_path):
    root = shelf(tmp_path, {"9900": WORDS})
    required = (Required("carried by a question", ("what-do-you-want",), "CIV 9900(a)"),
                Required("carried by the signature", ("signature",)),
                Required("points at a question that is not there", ("no-such-question",)),
                Required("carried by nothing"),
                Required("a gap named", authority="CIV 9900(b)", deferred="the full form closes it"),
                Required("an attestation the form lacks", ("attestation",)))
    report = check(resolve(Stub(), library(definition(required_content=required, recitals=("CIV 9900(a)",)))), root)
    got = {f.item.split(" (")[0]: (f.severity, f.message) for f in report.findings if f.check is Check.REQUIRED}
    assert set(got) == {"points at a question that is not there", "carried by nothing", "a gap named", "an attestation the form lacks"}
    assert got["points at a question that is not there"] == (Severity.FAIL, "not carried: no question 'no-such-question'")
    assert got["carried by nothing"][0] is Severity.FAIL and "no question or text carries it" in got["carried by nothing"][1]
    assert got["a gap named"][0] is Severity.DEFERRED and got["an attestation the form lacks"][0] is Severity.FAIL
    assert len(report.failing) == 3 and report.status("demo") is Status.FAILING


def test_marker_codes_must_be_unique_printable_and_not_another_forms_sent_codes(tmp_path):
    a = definition(key="a", template=template(FormKey.IDR, code="RR"))
    b = definition(key="b", template=template(FormKey.RECORDS, code="rr"))
    report = check(resolve(Stub(), library(a, b)), tmp_path)
    assert [(f.check, f.form) for f in report.failing] == [(Check.CODES, "b")] and "also a's" in report.failing[0].message
    bad = definition(key="c", template=template(FormKey.IDR, code="ZZ"))
    assert "two letters" in check(resolve(Stub(), library(bad)), tmp_path).failing[0].message
    assert check(resolve(Stub(), library(definition(key="d", template=template(FormKey.IDR, code="")),
                                         definition(key="e", template=template(FormKey.RECORDS, code="")))), tmp_path).ok   # no code, no clash
    sent = tmp_path / "forms"
    sent.mkdir()
    (sent / "references.json").write_text(json.dumps({"NP27E-AAAAA-00": {"form": "owner-info"}}), encoding="utf-8")
    taken = definition(key="f", template=template(FormKey.IDR, code="NP"))
    assert "already sent under this code for owner-info" in check(resolve(Stub(), library(taken)), tmp_path).failing[0].message
    same = definition(key="owner-info", template=template(FormKey.OWNER_INFO, code="NP"))
    assert check(resolve(Stub(), library(same)), tmp_path).ok                      # the form that sent them may keep its code


def test_two_forms_may_not_share_one_form_key():
    twin = definition(key="twin")
    resolved = resolve(Stub(), library(definition(), twin))
    assert resolved.problems[0].item == "template key idr" and "demo, twin" in resolved.problems[0].message


def test_the_shipped_forms_and_the_profile_pass_every_check_on_a_shelf_that_holds_their_recitals(tmp_path):
    sections = {"5205": "\n\n".join(f"({c}) made up." for c in "abcdefgh"), "5210": "(a) made up.\n\n(b) made up.",
                "5910": "(a) made up.\n\n(b) made up.", "5915": "(a) made up.\n\n(b) made up.\n\n(c) made up."}
    root = shelf(tmp_path, sections)
    report = check(resolve(community()), root, community=community())
    assert report.ok, [f.line() for f in report.failing]
    assert {f.severity for f in report.findings} == {Severity.DEFERRED}
    assert dict(report.statuses) == {"idr-request": Status.READY, "records-request": Status.READY, "owner-info": Status.READY}
    # a subdivision that moved (5205(f) gone) fails the build and names the form
    moved = shelf(tmp_path / "moved", {**sections, "5205": "\n\n".join(f"({c}) made up." for c in "abcde")})
    failing = check(resolve(community()), moved, community=community()).failing
    assert [(f.form, f.item) for f in failing] == [("records-request", "CIV 5205(f)"), ("records-request", "CIV 5205(g)")]


def test_json_words_become_symbols():
    clock = Clock.from_dict({"name": "n", "counted_from": "receipt", "number": 5, "kind": "business", "set_by": "documents",
                             "section": "ccrs#1"})
    assert (clock.kind, clock.set_by) == (DayKind.BUSINESS, SetBy.DOCUMENTS) and Clock("n", "r", 1, "calendar", "statute").kind is DayKind.CALENDAR
    change = Adjust.from_dict({"form": "x", "channels": ["paper", "portal"], "clocks": [{"name": "n", "counted_from": "r", "number": 1}],
                               "reword": {"name": "Other"}})
    assert change.channels == (Channel.PAPER, Channel.PORTAL) and change.clocks[0].set_by is SetBy.PROPOSED_POLICY
    assert change.reword == (("name", "Other"),)
    add = Add.from_dict({"form": "x", "question": {"title": "Pick", "kind": "choice", "options": ["a"], "reads": "name"}})
    assert add.question.kind is QuestionKind.CHOICE and add.question.reads is ReadAs.NAME
    bind = Bind.from_dict({"form": "x", "section": "s", "decider": "d", "forbidden": ["f"], "required": [{"item": "i", "carried_by": "q"}]})
    assert bind.required[0].carried_by == ("q",) and bind.missing(("a",)) == ("clock a",)
    with pytest.raises(ValueError):
        Clock.from_dict({"name": "n", "counted_from": "r", "number": 1, "kind": "fortnight"})


# -- a throwaway second profile -------------------------------------------------------------------------------------------

_PROFILE = """
    from pathlib import Path

    from jason.community.base import Community
    from jason.community.form_library import Add, Adjust, Bind, Clock, Slot
    from jason.community.forms import FormKey, FormQuestion, FormTemplate


    class Small(Community):
        name = "Small Community Association"
        slug = "small"
        org_id = 1
        root = Path(__file__).parent

        def document_sync_rules(self):
            return {"rules": [], "exclude": []}

        def buildings(self):
            return ()

        def document_rules(self):
            return ()

        def transaction_rules(self):
            return ()

        def insurance_workbook_id(self):
            return ""

        def form_slots(self):
            return (Slot("ASSOCIATION", self.name),)

        def form_adjustments(self):
            return (Add("records-request", FormQuestion("Which unit's records?", key="which-unit")),
                    Adjust("records-request", clocks=(Clock("current-year", "receipt", 7, "calendar", "documents", "bylaws#3.2"),)))
"""


def _stubs():
    return "".join(f"\n        def {m}(self, *args, **kwargs):\n            return ()\n" for m in sorted(Community.__abstractmethods__)
                   if m not in {"name", "slug", "org_id", "root", "document_sync_rules", "buildings", "document_rules",
                                "transaction_rules", "insurance_workbook_id"})


@pytest.fixture
def small(tmp_path, monkeypatch):
    def make(extra: str = ""):
        package = tmp_path / "small"
        package.mkdir()
        source = textwrap.dedent(_PROFILE + _stubs() + textwrap.indent(textwrap.dedent(extra), "        ") + "\n    PROFILE = Small\n")
        (package / "__init__.py").write_text(source, encoding="utf-8")
        (package / "forms.py").write_text("OWNER_INFO = {}\n", encoding="utf-8")
        monkeypatch.setenv("JASON_PROFILE", "small")
        monkeypatch.setenv("JASON_PROFILE_DIR", str(package))
        return package

    yield make
    for module in [m for m in sys.modules if m == "jason_small" or m.startswith("jason_small.")]:
        del sys.modules[module]
    profiles._LOADED.pop("small", None)


def test_another_profile_gets_the_library_with_its_own_slots_and_adjustments_and_none_of_the_first_ones(small):
    small()
    mine = community()
    assert mine.name == "Small Community Association" and mine.custom_forms() == () and mine.form_bindings() == ()
    resolved = resolve(mine)
    assert [f.key for f in resolved.forms] == ["idr-request", "records-request"]            # no owner information: it is mystique's own
    records = resolved.get("records-request")
    assert records.status is Status.ADJUSTED and [q.field for q in records.template.questions][-1] == "which-unit"
    governing = next(c for c in records.clocks if c.name == "current-year")
    assert (governing.number, governing.kind, governing.section) == (7, DayKind.CALENDAR, "bylaws#3.2")
    assert governing.note.startswith("stricter than current-year: 10 business days")
    assert [t.key for t in mine.forms()] == [FormKey.IDR, FormKey.RECORDS]
    assert resolved.get("idr-request").status is Status.READY


def test_every_consumer_reads_the_communitys_forms_not_a_profile_module(small, tmp_path, monkeypatch, capsys):
    small("""
        def forms(self):
            return (FormTemplate(FormKey.IDR, "The Small Association's own request", "Civil Code 0", "Made up.",
                                 (FormQuestion("Your name", key="name"),), code="SQ"),)
    """)
    from jason.tasks import forms as forms_task
    from jason.tasks import packets

    assert [t.title for t in community().forms()] == ["The Small Association's own request"]
    assert forms_task.template("idr").title == "The Small Association's own request"
    with pytest.raises(LookupError):
        forms_task.template("records")                                              # the profile's forms() does not have it
    assert "The Small Association's own request" in "\n".join(packets.template_markdown("form:idr"))
    assert packets.template_style("form:idr").write_above == 22.0 - packets.LINE_BOX
    with pytest.raises(StopIteration):
        packets.template_markdown("form:records")

    from jason.commands import drafts_forms
    from jason.commands import packet as packet_cmd

    monkeypatch.setattr(drafts_forms, "_data_dir", lambda args: tmp_path)
    args = argparse.Namespace(create="idr", yes=False)
    assert drafts_forms.cmd_forms(args, lambda a: None) == 0
    out = capsys.readouterr().out
    assert "Form: The Small Association's own request" in out and "Your name" in out and "Dry run" in out

    seen = {}

    def stop(pdf, **kwargs):
        seen["form"] = kwargs["form"]
        raise RuntimeError("stop")

    import jason.community.fillable as fillable

    monkeypatch.setattr(fillable, "make_fillable", stop)
    part = argparse.Namespace(title="Request", source=argparse.Namespace(markdown="form:idr"))
    packet = argparse.Namespace(parts=[part])
    with pytest.raises(RuntimeError, match="stop"):
        packet_cmd._fillable_forms(packet, [{"title": "Request", "firstPage": 1, "pageCount": 1, "file": "x.pdf"}], tmp_path / "x.pdf", tmp_path)
    assert seen["form"].title == "The Small Association's own request"


def test_a_profile_without_form_methods_gets_the_default_library(small):
    small()
    plain = Community.forms
    assert [t.key.value for t in plain(community())] == ["idr", "records"]


# -- the command ----------------------------------------------------------------------------------------------------------

@pytest.fixture
def cmd(monkeypatch, tmp_path):
    from jason.commands import form_library as module

    root = shelf(tmp_path, {"5205": "\n\n".join(f"({c}) made up." for c in "abcdefgh"), "5210": "(a) made up.\n\n(b) made up.",
                            "5910": "(a) made up.\n\n(b) made up.", "5915": "(a) made up.\n\n(b) made up."})
    monkeypatch.setattr(module, "_data_dir", lambda args: root)

    def run(*argv, capsys):
        parser = argparse.ArgumentParser()
        module.register(parser.add_subparsers(), lambda p: None, lambda a: None)
        args = parser.parse_args(["form-library", *argv])
        code = module.cmd_form_library(args)
        out = capsys.readouterr()
        return code, out.out, out.err

    run.module, run.root = module, root
    return run


def test_the_command_lists_the_forms_by_tier_and_status_and_names_what_is_deferred(cmd, capsys):
    code, out, err = cmd(capsys=capsys)
    assert code == 0 and not err
    assert "3 ready, 0 adjusted, 0 not offered, 0 failing" in out and "ready (3)" in out
    assert "idr-request" in out and "state, CA" in out and "v1, as of 2026-10-05" in out and "owner-info" in out and "custom" in out
    assert "5 required item(s) not carried yet" in out
    _, out, _ = cmd("--tier", "custom", capsys=capsys)
    assert "owner-info" in out and "idr-request" not in out
    _, out, _ = cmd("--tier", "family", capsys=capsys)
    assert "No forms in the family tier." in out
    code, out, _ = cmd("--json", capsys=capsys)
    body = json.loads(out)
    assert code == 0 and body["chain"] == ["US", "CA"] and [f["key"] for f in body["forms"]] == ["idr-request", "records-request", "owner-info"]
    assert body["forms"][1]["status"] == "ready" and body["forms"][1]["clocks"][0]["words"].startswith("current-year: 10 business days")


def test_check_exits_zero_on_deferrals_and_one_on_a_failing_form(cmd, capsys, monkeypatch, tmp_path):
    code, out, _ = cmd("--check", capsys=capsys)
    assert code == 0 and "0 failing, 0 not offered, 10 deferred" in out and "1. required content" in out
    code, out, _ = cmd("--check", "--json", capsys=capsys)
    assert code == 0 and json.loads(out)["ok"] is True
    # a shelf that has lost 5205(f): the records form fails, and the exit says so
    moved = shelf(tmp_path / "moved", {"5205": "(a) made up.\n\n(b) made up."})
    monkeypatch.setattr(cmd.module, "_data_dir", lambda args: moved)
    code, out, _ = cmd("--check", capsys=capsys)
    assert code == 1 and "2. recitals" in out and "CIV 5205(f)" in out
    code, out, _ = cmd("--check", "--json", capsys=capsys)
    body = json.loads(out)
    assert code == 1 and body["ok"] is False and body["statuses"]["records-request"] == "failing"
    code, out, _ = cmd("--check", "--tier", "custom", capsys=capsys)
    assert code == 0 and "1 form(s) checked" in out


def test_show_reads_one_form_by_either_key_with_the_words_and_their_caveat(cmd, capsys):
    code, out, _ = cmd("--show", "records", capsys=capsys)
    assert code == 0
    assert "records-request: Request to Inspect Association Records" in out and "status ready" in out and "the form's own key records" in out
    assert "(b) made up." in out or "(f) made up." in out
    assert "-> records-requested" in out and "[deferred: not carried yet; the full form's cost estimate and agreement]" in out
    assert "current-year: 10 business days from receipt (statute: CIV 5210(b)(1))" in out
    assert "the law as of 2026-10-05" in out and "not an official restatement" in out
    code, out, _ = cmd("--show", "idr-request", "--json", capsys=capsys)
    body = json.loads(out)
    assert code == 0 and body["formKey"] == "idr" and body["recitalWords"][0]["found"] is True and body["required"][0]["carriedBy"] == ["signature"]


def test_the_command_refuses_what_does_not_go_together_and_a_form_it_does_not_have(cmd, capsys):
    code, _, err = cmd("--show", "no-such-form", capsys=capsys)
    assert code == 2 and "jason form-library: no form 'no-such-form'" in err and "idr-request" in err
    code, _, err = cmd("--show", "idr", "--check", capsys=capsys)
    assert code == 2 and "does not go with" in err


def test_the_command_is_registered_and_changes_nothing(cmd, capsys, tmp_path):
    from jason.commands import MODULES

    assert "form_library" in MODULES
    before = sorted(p.relative_to(cmd.root.parent).as_posix() for p in cmd.root.parent.rglob("*"))
    cmd("--check", capsys=capsys)
    cmd("--show", "idr", capsys=capsys)
    assert sorted(p.relative_to(cmd.root.parent).as_posix() for p in cmd.root.parent.rglob("*")) == before


# -- the boundary ---------------------------------------------------------------------------------------------------------

def test_the_library_names_no_association_and_imports_no_profile(tmp_path):
    """The whole-repository boundary tests (tests/test_profile.py) cover this too; this one reads the library's own files, the
    wide way (every string, not only patterns and tables), so a name in a docstring or a message is found."""
    import shutil

    from jason.community.boundary import instance_terms, profile_imports, repo_root, scan, scan_code

    terms = instance_terms(community())
    assert terms
    here = tmp_path / "src" / "jason" / "community"
    shutil.copytree(repo_root() / "src" / "jason" / "community" / "form_library", here / "form_library",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(repo_root() / "src" / "jason" / "commands" / "form_library.py", tmp_path / "src" / "jason" / "form_library_command.py")
    (tmp_path / "docs").mkdir()
    shutil.copy(repo_root() / "docs" / "form-library-design.md", tmp_path / "docs" / "form-library-design.md")
    assert scan_code(tmp_path, terms, wide=True) == {}
    assert profile_imports(tmp_path, community().slug) == []
    assert scan(tmp_path, terms) == {}
