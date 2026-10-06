"""The form library's delivery, election, meeting, and accommodation forms (docs/form-library-design.md, build step 2B2):
change my notice delivery, a second address, individual delivery of general notices, candidate nomination, a request to be heard
at a board meeting, and the reasonable accommodation request of the federal pack.

Everything here is made up: a throwaway shelf of short stand-in sentences for the recited subdivisions, stub communities,
made-up owners and answers. No network, no model, no real data folder.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

import pytest

from jason.community import Community, community
from jason.community.form_library import (
    Check,
    Clock,
    FormDefinition,
    Library,
    SetBy,
    Severity,
    Slot,
    Status,
    Tier,
)
from jason.community.form_library.ca import (
    candidate_nomination,
    delivery_change,
    individual_delivery,
    meeting_comment,
    secondary_address,
)
from jason.community.form_library.check import check, check_codes
from jason.community.form_library.resolve import resolve
from jason.community.form_library.us import accommodation
from jason.community.forms import FormKey, QuestionKind

MINE = (delivery_change.DEFINITION, secondary_address.DEFINITION, individual_delivery.DEFINITION,
        candidate_nomination.DEFINITION, meeting_comment.DEFINITION, accommodation.DEFINITION)
KEYS = tuple(d.key for d in MINE)
CODES = {"delivery-change": "NC", "secondary-address": "NA", "individual-delivery-request": "NV",
         "candidate-nomination": "CN", "meeting-comment-request": "HM", "accommodation-request": "AM"}
FORM_KEYS = {"delivery-change": FormKey.DELIVERY_CHANGE, "secondary-address": FormKey.SECONDARY_ADDRESS,
             "individual-delivery-request": FormKey.INDIVIDUAL_DELIVERY_REQUEST,
             "candidate-nomination": FormKey.CANDIDATE_NOMINATION, "meeting-comment-request": FormKey.MEETING_COMMENT_REQUEST,
             "accommodation-request": FormKey.ACCOMMODATION_REQUEST}
ALL_SLOTS = sorted({s for d in MINE for s in d.slots})

# What a sender fills in each time (a receipt's date, the reference), not what a community gives the library.
PER_SEND = {"RECEIVED", "EFFECTIVE", "DUE", "DECIDER", "REFERENCE", "CURRENT_METHOD", "NOMINEE", "SEAT", "QUALIFIED_OR_NOT",
            "STATEMENT_DUE", "APPEAL_BY", "ASKED_FOR", "DECISION_BY"}


def value_of(name: str) -> str:
    return f"made up {name.lower().replace('_', ' ')}"


def given(*names: str, leave: tuple[str, ...] = ()) -> tuple[Slot, ...]:
    return tuple(Slot(n, value_of(n)) for n in (names or ALL_SLOTS) if n not in leave)


class Stub:
    """A community that asks the library for nothing but the chain and the slots a test gives it."""

    def __init__(self, *, chain=("US", "CA"), slots=()):
        self.chain, self._slots = chain, slots

    def jurisdictions(self):
        return self.chain

    def form_slots(self):
        return self._slots

    def form_adjustments(self):
        return ()

    def form_bindings(self):
        return ()

    def custom_forms(self):
        return ()


def mine() -> Library:
    lib = Library()
    for d in MINE:
        lib.register(d)
    return lib


def resolved_form(key: str, **kw):
    return resolve(Stub(slots=given(**kw)), mine()).get(key)


def text_of(template) -> str:
    """Every word a member reads on the form."""
    parts = [template.title, template.authority, template.description, *template.preamble, template.attestation]
    for q in template.questions:
        parts += [q.section, q.title, q.help, q.authority, q.same_as, *q.options]
    return "\n".join(p for p in parts if p)


def plain(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("**", "")).strip()


# -- a made-up shelf --------------------------------------------------------------------------------------------------------

STAND_IN = "A made-up stand-in sentence."


def stand_in_words() -> str:
    """Every subdivision a recital can name, each as one short sentence: (a) to (j), each with (1) to (7), each with (A) to (F)."""
    rows = []
    for letter in "abcdefghij":
        rows.append(f"({letter}) {STAND_IN}")
        for n in range(1, 8):
            rows.append(f"({n}) {STAND_IN}")
            rows += [f"({upper}) {STAND_IN}" for upper in "ABCDEF"]
    return "\n\n".join(rows)


def shelf(tmp_path: Path, citations) -> Path:
    """A data folder whose authorities shelf holds each statute section the citations name, as short stand-in sentences."""
    from jason.community import law_text

    root = tmp_path / "data"
    sections = sorted({tuple(found[0].split()[:2]) for c in citations if "#" not in c and (found := law_text.normal_citation(c))})
    pages = []
    for code, number in sections:
        (root / "authorities" / code).mkdir(parents=True, exist_ok=True)
        file = f"authorities/{code}/{code}-{number}.md"
        (root / file).write_text(f"# {code} {number}: made up\n\n- Source: California Legislature, 2025 session publication, "
                                 f"read with lawlibrary\n\n## {code} {number}\n\n- History: made up\n\n{number}. (Added by "
                                 f"Stats. 2012, Ch. 1, Sec. 1.)\n\n{stand_in_words()}\n", encoding="utf-8")
        pages.append({"file": file, "citation": f"{code} {number}", "title": "Made up", "code": code, "start": number,
                      "end": number, "sections": [number], "basis": "a duty", "why": ["made up"], "session": "2025"})
    (root / "authorities").mkdir(parents=True, exist_ok=True)
    (root / "authorities" / "manifest.json").write_text(json.dumps({"exported": "2026-10-04", "session": "2025", "pages": pages}),
                                                        encoding="utf-8")
    return root


MY_CITATIONS = sorted({c for d in MINE for c in d.recitals})


# -- the definitions ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("d", MINE, ids=KEYS)
def test_each_definition_is_version_one_as_of_the_shelfs_day_with_its_code_authority_and_handler(d):
    assert d.version == "1" and d.as_of == date(2026, 10, 5) and d.tier is Tier.STATE
    assert d.jurisdiction == ("US" if d.key == "accommodation-request" else "CA")
    assert d.template.key is FORM_KEYS[d.key] and d.key == d.template.key.value
    assert d.template.code == CODES[d.key] and d.template.code != "NP"
    assert d.authority and d.recitals and d.required_content and d.association_clocks and d.member_clock and d.acknowledgment
    assert d.template.preamble and d.template.description and d.channels and d.slots
    assert not [r for r in d.required_content if r.deferred], "a new form defers nothing"
    assert d.as_dict()["asOf"] == "2026-10-05"


def test_the_delivery_forms_use_the_owner_information_handler_and_the_rest_the_response_clock():
    by = {d.key: (d.handler, d.procedure) for d in MINE}
    assert by["delivery-change"] == by["secondary-address"] == ("owner-information", "owner-info-cycle")
    assert {by[k] for k in ("individual-delivery-request", "candidate-nomination", "meeting-comment-request",
                            "accommodation-request")} == {("response-clock", "respond")}
    resolved = resolve(Stub(slots=given()), mine())
    assert all(f.handler_problems == () for f in resolved.forms)


@pytest.mark.parametrize("d", MINE, ids=KEYS)
def test_every_required_item_is_carried_and_every_recital_resolves_on_a_throwaway_shelf(d, tmp_path):
    root = shelf(tmp_path, MY_CITATIONS)
    resolved = resolve(Stub(slots=given()), mine())
    report = check(resolved, root)
    assert report.for_form(d.key) == (), [f.line() for f in report.for_form(d.key)]
    assert report.status(d.key) is Status.READY and report.ok
    assert not any(r.carried_by == () for r in d.required_content)


def test_a_recital_the_shelf_lacks_fails_naming_the_form(tmp_path):
    root = shelf(tmp_path, [c for c in MY_CITATIONS if not c.startswith("CIV 5260")])
    findings = [f for f in check(resolve(Stub(slots=given()), mine()), root).failing if f.check is Check.RECITALS]
    assert {(f.form, f.item) for f in findings} == {("secondary-address", "CIV 5260"), ("individual-delivery-request", "CIV 5260(c)")}
    assert all("not on the shelf" in f.message for f in findings)


@pytest.mark.parametrize("d", MINE, ids=KEYS)
def test_the_questions_have_unique_fields_and_each_required_item_points_at_one(d):
    fields = [q.field for q in d.template.questions]
    assert len(fields) == len(set(fields))
    carriers = {c for r in d.required_content for c in r.carried_by}
    assert carriers - set(fields) <= {"signature", "preamble", "description", "attestation"}


def test_the_codes_are_unique_across_the_resolved_set_and_none_is_the_owner_information_code():
    for resolved in (resolve(Stub(slots=given())), resolve(community())):
        codes = [f.template.code for f in resolved.forms if f.template.code]
        assert len(codes) == len(set(codes)) and set(CODES.values()) <= set(codes) and "NP" not in set(CODES.values())
        assert [f for f in check_codes(resolved, Path("no-such-folder")) if f.form in KEYS] == []
    assert len(set(CODES.values())) == 6 and all(len(c) == 2 for c in CODES.values())


# -- slots ----------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("d", MINE, ids=KEYS)
def test_a_slot_is_declared_if_and_only_if_the_form_uses_it(d):
    everything = "\n".join([text_of(d.template), d.member_clock, d.acknowledgment])
    tokens = set(re.findall(r"\{([A-Z][A-Z0-9_]*)\}", everything))
    assert tokens - set(d.slots) <= PER_SEND, f"undeclared slots: {sorted(tokens - set(d.slots) - PER_SEND)}"
    assert set(d.slots) <= tokens, f"declared and never used: {sorted(set(d.slots) - tokens)}"
    assert {"RECEIVED", "DUE", "DECIDER", "REFERENCE"} <= set(re.findall(r"\{([A-Z][A-Z0-9_]*)\}", d.acknowledgment))


@pytest.mark.parametrize("d", MINE, ids=KEYS)
def test_a_form_with_a_missing_slot_is_not_offered_and_the_slot_is_named(d, tmp_path):
    for name in d.slots:
        waiting = resolve(Stub(slots=given(leave=(name,))), mine())
        form = waiting.get(d.key)
        assert form.status is Status.NOT_OFFERED and form.missing == (f"slot {name}",), name
        assert d.template not in waiting.templates() and form.template not in waiting.templates()
        findings = [f for f in check(waiting, tmp_path).findings if f.form == d.key and f.check is Check.SLOTS]
        assert [(f.item, f.severity) for f in findings] == [(f"slot {name}", Severity.NOT_OFFERED)]
    ready = resolve(Stub(slots=given()), mine()).get(d.key)
    assert ready.status is Status.READY and ready.template in resolve(Stub(slots=given()), mine()).templates()
    left = re.findall(r"\{([A-Z][A-Z0-9_]*)\}", text_of(ready.template))
    assert set(left) <= PER_SEND, "a slot was left unfilled in what the member reads"


def test_the_real_profile_gives_the_slots_it_has_and_the_forms_that_need_more_wait():
    names = {s.name for s in community().form_slots()}
    resolved = resolve(community())
    for d in MINE:
        form = resolved.get(d.key)
        need = tuple(f"slot {s}" for s in d.slots if s not in names)
        assert form is not None and form.missing == need
        assert form.status is (Status.NOT_OFFERED if need else Status.READY)


# -- the US pack ----------------------------------------------------------------------------------------------------------

def test_the_us_forms_appear_for_the_default_chain_and_not_for_a_chain_of_california_alone():
    assert Community.jurisdictions(community()) == ("US", "CA")
    both = resolve(Stub(chain=("US", "CA"), slots=given()))
    only_ca = resolve(Stub(chain=("CA",), slots=given()))
    form = both.get("accommodation-request")
    assert form is not None and form.definition.jurisdiction == "US" and form.tier is Tier.STATE and form.status is Status.READY
    assert only_ca.get("accommodation-request") is None
    assert {f.key for f in only_ca.forms if f.definition.jurisdiction == "CA"} >= {k for k in KEYS if k != "accommodation-request"}
    assert all(f.definition.jurisdiction != "US" for f in only_ca.forms)
    assert resolve(Stub(chain=("US",), slots=given())).get("delivery-change") is None
    assert resolve(community()).get("accommodation-request") is not None                  # the real profile's default chain


# -- the delivery forms ---------------------------------------------------------------------------------------------------

def _tags():
    from jason.community.tags import PayhoaTag, TagPurpose, TagScope

    return (PayhoaTag("Notices by Email", TagScope.MEMBER, TagPurpose.NOTICE_DELIVERY, "email"),
            PayhoaTag("Notices by Mail", TagScope.MEMBER, TagPurpose.NOTICE_DELIVERY, "mail"))


def _proposals(template, answers: dict, owned: set[str]) -> list[str]:
    """The tag changes a current owner's answer to ``template`` proposes: the function the owner information plan reads."""
    from jason.community.forms import AnswerCycle, FormAnswers
    from jason.tasks.member_preferences import Owner, UnitOwners, match

    unit = UnitOwners(10, "123 MAIN ST", 123, None, "2020-01-01",
                      [Owner(1, "A. Owner", "a.owner@example.org", {t.casefold() for t in owned})], set())
    response = FormAnswers(template.key, answers, source="payhoa:1", submitted="2026-10-10", membership_id=1, unit_id=10)
    found = match([response], [unit], _tags(), cycle=AnswerCycle(year=2027, opened=date(2026, 10, 1)), today=date(2026, 10, 12))
    return found[0].tag_changes


@pytest.mark.parametrize("chosen,owned,expected", [
    (["By email"], {"Notices by Mail"}, ["+Notices by Email (member)", "-Notices by Mail (member)"]),
    (["By mail"], {"Notices by Email"}, ["-Notices by Email (member)", "+Notices by Mail (member)"]),
    (["By mail", "By email"], set(), ["+Notices by Email (member)", "+Notices by Mail (member)"]),
    (["By email"], {"Notices by Email"}, []),
])
def test_delivery_change_sets_the_same_tags_the_annual_form_sets_for_the_same_answers(chosen, owned, expected):
    annual = community().owner_information().OWNER_INFO
    change = delivery_change.TEMPLATE
    assert change.question("delivery").field == annual.question("delivery").field == "delivery"
    assert change.question("delivery").options == annual.question("delivery").options == ("By mail", "By email")
    assert change.question("email").field == annual.question("email").field
    assert change.question("mailing-address").same_as_field == annual.question("mailing-address").same_as_field
    answers = {"unit-address": "123 Main St, Anytown, CA 90000", "delivery": chosen}
    if "By email" in chosen:
        answers["email"] = "a.owner@example.org"
    assert _proposals(change, answers, owned) == _proposals(annual, answers, owned) == expected


def test_email_is_not_required_unless_the_member_chooses_it_and_no_form_requires_one():
    from jason.community.forms import check as check_answers

    for d in MINE:
        assert [q.field for q in d.template.questions if q.kind is QuestionKind.EMAIL and q.required] == [], d.key
    change = delivery_change.TEMPLATE
    assert change.question("email").required is False and "only if you chose email" in change.question("email").help.lower()
    by_mail = {"name": "A. Owner", "unit-address": "123 Main St", "capacity": ["An owner of this unit"], "delivery": ["By mail"]}
    assert check_answers(change, by_mail) == []                                                # no email asked of a mail choice
    assert check_answers(change, {**by_mail, "delivery": ["By email"], "email": "a.owner@example.org"}) == []
    assert check_answers(change, {**by_mail, "delivery": ["By email"], "email": "not an address"})
    text = plain(text_of(change)).lower()
    assert "you do not have to give us an email address" in text and "4041(b)(2)(a)" in text
    assert "any day of the year" in text and "return by" not in text and "please answer by" not in text
    assert "no one has to approve" in text and "4041(c)" in text and "4041(e)" in text
    assert any(r.item.startswith("Notice that the member does not have to provide an email address") and r.authority ==
               "CIV 4041(b)(2)(A)" for r in delivery_change.DEFINITION.required_content)


def test_delivery_change_asks_no_phone_no_reason_and_no_occupancy_and_says_where_it_goes():
    form = resolved_form("delivery-change").template
    fields = [q.field for q in form.questions]
    assert fields == ["name", "unit-address", "capacity", "delivery", "mailing-address", "email"]
    assert form.signature and form.dated and form.attestation
    text = plain(text_of(form))
    for slot in ("DESIGNATED_PERSON", "RETURN_BY_MAIL", "RETURN_BY_EMAIL", "PORTAL"):
        assert value_of(slot) in text
    ack = resolved_form("delivery-change").acknowledgment
    assert value_of("RETURN_BY_EMAIL") in ack and "{EFFECTIVE}" in ack and "{RECEIVED}" in ack


def test_secondary_address_offers_add_and_remove_requires_no_address_on_its_own_and_names_what_copies_go():
    form = resolved_form("secondary-address").template
    fields = [q.field for q in form.questions]
    assert fields == ["name", "unit-address", "capacity", "action", "second-email", "second-mailing-address", "second-name",
                      "remove-which"]
    assert [q.required for q in form.questions if q.field in ("second-email", "second-mailing-address", "remove-which")] == [False] * 3
    assert form.question("action").options == ("Add or change a second address", "Remove a second address")
    text = plain(text_of(form))
    for section in ("5660", "5675(e)", "5685", "5710(b)", "5300 to 5320"):
        assert section in text
    assert "collection notices can show what is owed" in text.lower()
    assert "does not name a legal representative" in text and "do not have to give an email address" in text
    assert not [f for f in fields if "represent" in f or "phone" in f or "reason" in f or "other-notices" in f]
    assert {"second-email", "second-mailing-address"} == set(secondary_address.REQUIRED[0].carried_by)
    effective = {c.name: c for c in secondary_address.DEFINITION.association_clocks}["effective"]
    assert (effective.set_by, effective.section, effective.number) == (SetBy.STATUTE, "CIV 4040(b)", 0)


def test_a_community_adds_the_other_notices_box_only_when_its_board_adopts_the_policy():
    from jason.community.form_library import Add
    from jason.community.forms import FormQuestion

    box = Add("secondary-address", FormQuestion("Also send the second address copies of the other individual notices",
                                                QuestionKind.CHECKBOX, required=False, key="other-notices",
                                                options=("Yes",)), after="second-name")
    stub = Stub(slots=given())
    stub.form_adjustments = lambda: (box,)
    form = resolve(stub, mine()).get("secondary-address")
    assert form.status is Status.ADJUSTED and [q.field for q in form.template.questions][6:8] == ["second-name", "other-notices"]


def test_individual_delivery_covers_all_general_notices_offers_cancellation_and_asks_no_address():
    form = resolved_form("individual-delivery-request").template
    fields = [q.field for q in form.questions]
    assert fields == ["name", "unit-address", "capacity", "request"]
    assert form.question("request").options == ("Deliver every general notice to me by the delivery method I chose",
                                                "Cancel my earlier request")
    text = plain(text_of(form))
    assert "all general notices" in text and "We charge nothing for it" in text and value_of("GENERAL_NOTICE_LOCATION") in text
    for section in ("4360(a), (c)", "4365(g)", "4741(f)", "4920(c), (d)", "5115", "5120(b)", "5310(a)(4)"):
        assert section in text
    assert not [q for q in form.questions if q.kind in (QuestionKind.EMAIL, QuestionKind.PHONE)]
    assert individual_delivery.ACKNOWLEDGMENT_CANCELLED.startswith("We stopped sending you general notices individually")
    statute = [c for c in individual_delivery.CLOCKS if c.set_by is SetBy.STATUTE]
    assert [(c.name, c.section, c.number) for c in statute] == [("meeting-notice", "CIV 4920(a)", 4)]


# -- the election form ----------------------------------------------------------------------------------------------------

def test_candidate_nomination_offers_self_nomination_and_asks_nothing_about_money_or_a_conviction():
    form = resolved_form("candidate-nomination").template
    assert form.question("self").options == ("I am nominating myself", "I am nominating another member")
    asked = " ".join([q.title + " " + q.help for q in form.questions] + [o for q in form.questions for o in q.options]).lower()
    for word in ("convict", "criminal", "owe", "fine", "late charge", "delinquen", "arrear", "assessment", "photograph", "age"):
        assert not re.search(rf"\b{word}", asked), word
    assert value_of("NOMINATION_DEADLINE") in plain(text_of(form)) and value_of("NOMINATION_RETURN") in plain(text_of(form))
    text = plain(text_of(form))
    assert "will not edit or redact" in text and "a member may nominate themself" in text.lower()
    assert "5105(h)(1)" in text and "5105(a)(7)" in text and value_of("INSPECTOR") in text
    assert "That is the only ground this form states itself" in text
    assert {"statement", "statement-ack"} <= {q.field for q in form.questions}
    assert form.question("accepts").required is False and form.question("nominator-name").required is False


def test_the_nomination_deadline_is_a_slot_so_the_form_is_not_offered_without_one():
    waiting = resolve(Stub(slots=given(leave=("NOMINATION_DEADLINE",))), mine()).get("candidate-nomination")
    assert waiting.status is Status.NOT_OFFERED and waiting.missing == ("slot NOMINATION_DEADLINE",)
    empty = resolve(Stub(slots=(*given(leave=("NOMINATION_DEADLINE",)), Slot("NOMINATION_DEADLINE", "  "))), mine())
    assert empty.get("candidate-nomination").status is Status.NOT_OFFERED


def test_the_nomination_clocks_are_the_statutes_numbers_and_the_policy_is_labeled():
    clocks = {c.name: c for c in candidate_nomination.CLOCKS}
    for name in ("acknowledge-nomination", "tell-nominee"):
        c = clocks[name]
        assert (c.number, c.kind.value, c.set_by) == (7, "business", SetBy.STATUTE) and c.section.startswith("CIV 5103(c)")
    assert (clocks["nomination-notice"].number, clocks["nomination-notice"].section) == (30, "CIV 5115(a)")
    assert (clocks["initial-notice"].number, clocks["initial-notice"].section) == (90, "CIV 5103(b)(1)")
    assert clocks["statement-due"].set_by is clocks["appeal-request"].set_by is SetBy.PROPOSED_POLICY
    assert all(c.section for c in clocks.values() if c.set_by is SetBy.STATUTE)
    assert "{QUALIFIED_OR_NOT}" in candidate_nomination.ACKNOWLEDGMENT and "{INSPECTOR}" in candidate_nomination.ACKNOWLEDGMENT


# -- the meeting form -----------------------------------------------------------------------------------------------------

def test_the_meeting_form_says_plainly_the_act_gives_no_right_to_an_agenda_item_and_labels_the_courtesies():
    form = resolved_form("meeting-comment-request").template
    text = plain(text_of(form))
    assert "You may speak at any open board meeting, without this form." in text
    assert "gives a member no right to have an item placed on the agenda" in text
    assert "are courtesies, not rights the law gives" in text and "does not require the board to place an item" in text
    assert "may not speak in an executive session" in text
    sections = {q.field: q.section for q in form.questions if q.section}
    assert "not a right the Act gives" in sections["comment"] and "not a right the Act gives" in sections["item-what"]
    assert form.signature == "" and form.dated is False
    assert [q.field for q in form.questions if q.kind in (QuestionKind.EMAIL, QuestionKind.PHONE)] == []
    assert form.question("purpose").options == ("Speak at the open forum", "Give the board a written comment",
                                                "Ask the board to consider an item at a future meeting")
    assert form.question("item-personal").options == ("No", "Yes") and form.question("attend-how")
    assert value_of("TIME_LIMIT") in text and value_of("AGENDA_NOTICE_PLACE") in text
    assert not re.search(r"\b\d+ minutes", text), "the form never invents a time limit"


def test_the_meeting_form_states_the_time_limit_the_profile_gives_or_that_none_is_set_and_invents_none():
    none_set = (*given(leave=("TIME_LIMIT",)), Slot("TIME_LIMIT", "none is set yet"))
    form = resolve(Stub(slots=none_set), mine()).get("meeting-comment-request")
    assert form.status is Status.READY and "which is none is set yet" in plain(text_of(form.template))
    assert "the board's time limit for each speaker is none is set yet" in form.acknowledgment
    assert resolve(Stub(slots=given(leave=("TIME_LIMIT",))), mine()).get("meeting-comment-request").status is Status.NOT_OFFERED
    statute = {c.name: (c.number, c.section) for c in meeting_comment.CLOCKS if c.set_by is SetBy.STATUTE}
    assert statute == {"meeting-notice": (4, "CIV 4920(a)"), "executive-session-notice": (2, "CIV 4920(b)(2)"),
                       "minutes": (30, "CIV 4950(a)")}


# -- the accommodation form -----------------------------------------------------------------------------------------------

MEDICAL = re.compile(r"diagnos|condition|medicat|doctor|physician|provider|medical|therap|illness|disease|prescri|health|"
                     r"symptom|impairment", re.IGNORECASE)


def test_the_accommodation_form_has_no_diagnosis_question_and_says_none_is_asked():
    form = resolved_form("accommodation-request").template
    for q in form.questions:
        assert not MEDICAL.search(q.title) and not any(MEDICAL.search(o) for o in q.options), q.field
        for sentence in re.split(r"(?<=[.?!])\s+", q.help):
            if MEDICAL.search(sentence):
                assert re.search(r"\b(not|never|no)\b", sentence, re.IGNORECASE), (q.field, sentence)
    text = plain(text_of(form))
    assert "We do not ask for a diagnosis" in text and "You do not need to name a condition or a diagnosis" in text
    assert "A request in other words is still a request" in text
    assert "We will not turn your request away because it is on the wrong form, or comes from someone other than the owner" in text
    assert "It may come from the owner, a resident who is not an owner, or someone asking for them" in text
    assert "The Association is not giving legal advice" in text and "The board decides, on counsel's reading" in text
    assert form.signature == "" and form.dated is False and form.attestation == ""
    assert [q.field for q in form.questions if q.required] == ["name", "unit-address", "capacity", "kind", "change", "contact-how"]


def test_the_accommodation_form_recites_only_what_the_shelf_holds_and_says_the_fair_housing_statutes_are_not_there():
    d = accommodation.DEFINITION
    assert d.recitals == ("CIV 4765(a)(3)", "CIV 4700", "CIV 4760(a)(2)", "CIV 4715(a)", "CIV 4600(b)(3)(F)")
    assert all(r.startswith("CIV ") for r in d.recitals) and not any("GOV" in r or "USC" in r for r in d.recitals)
    assert d.template.authority.startswith("Pointer: outside the authorities shelf.")
    notes = " ".join(d.notes)
    assert d.notes == accommodation.NOTES and "not on the authorities shelf" in notes and "Fair Employment and Housing Act" in notes and "Fair Housing Act" in notes
    assert d.association_clocks and all(c.set_by is SetBy.PROPOSED_POLICY for c in d.association_clocks)
    assert {c.name for c in d.association_clocks} == {"acknowledge", "counsel-reads", "offer-to-talk", "first-answer", "decision"}
    assert "{DECISION_BY}" in d.acknowledgment and "diagnosis" in d.acknowledgment and "the form it came on" in d.acknowledgment
    assert accommodation.POINTER.lower().startswith("pointer: outside")


# -- the whole library ----------------------------------------------------------------------------------------------------

def test_each_form_renders_the_same_questions_for_the_paper_the_page_and_the_payhoa_sheet():
    from jason.community.form_render import paper_html, paper_markdown, payhoa_sheet

    import html as html_lib

    for d in MINE:
        form = resolve(Stub(slots=given()), mine()).get(d.key).template
        page = html_lib.unescape(paper_html(form))
        markdown, sheet = "\n".join(paper_markdown(form)), "\n".join(payhoa_sheet(form))
        for n, q in enumerate(form.questions, 1):
            title = q.title.replace(" (optional)", "")
            assert f"{n}. {title}" in page and f"{n}. {title}" in markdown, (d.key, q.field)
            assert q.title in sheet or title in sheet, (d.key, q.field)
        assert [q.title for q in form.questions] == [q.title for q in d.template.questions]      # slots change words, never questions


def _story_chrome(args, **kwargs):
    """Stands in for headless Chrome: lays the page's HTML out with PyMuPDF's Story into --print-to-pdf."""
    import pymupdf

    out = next(a.split("=", 1)[1] for a in args if a.startswith("--print-to-pdf="))
    html = Path(url2pathname(urlparse(args[-1]).path)).read_text(encoding="utf-8")
    story = pymupdf.Story(html)
    writer = pymupdf.DocumentWriter(out)
    more = True
    while more:
        device = writer.begin_page(pymupdf.paper_rect("letter"))
        more, _ = story.place(pymupdf.paper_rect("letter") + (54, 54, -54, -54))
        story.draw(device)
        writer.end_page()
    writer.close()


@pytest.mark.parametrize("d", MINE, ids=KEYS)
def test_each_form_renders_a_fillable_pdf_with_its_code_and_a_reference(d, tmp_path, monkeypatch):
    import pymupdf

    import jason.tasks.email_review as email_review
    from jason.community import form_refs
    from jason.community.fillable import stamp_reference
    from jason.tasks.forms import form_pdf

    monkeypatch.setattr(email_review, "browser", lambda: "chrome")
    form = resolve(Stub(slots=given()), mine()).get(d.key).template
    out = tmp_path / f"{d.key}.pdf"
    names = form_pdf(form, out, association="Test Association", run=_story_chrome)
    for q in form.questions:
        assert any(n == q.field or n.startswith(f"{q.field}.") or n.startswith(f"{q.field}#") for n in names), q.field
    marker = form_refs.make(form.code, 2026, form_refs.Channel.MAIL, membership_id=1, unit_id=2)
    stamp_reference(out, marker.text)
    with pymupdf.open(out) as doc:
        text = unicodedata.normalize("NFKC", "\n".join(page.get_text() for page in doc))     # a ligature is two letters
        assert list(doc[0].widgets())
    assert marker.text in text and marker.text.startswith(f"{d.template.code}26M")
    assert any(m.campaign == f"{d.template.code}26M" for m in form_refs.parse(text))
    assert form.title in text


def _data_dir_command(monkeypatch, root: Path):
    from jason.commands import form_library as module

    monkeypatch.setattr(module, "_data_dir", lambda args: root)

    def run(*argv, capsys):
        parser = argparse.ArgumentParser()
        module.register(parser.add_subparsers(), lambda p: None, lambda a: None)
        args = parser.parse_args(["form-library", *argv])
        code = module.cmd_form_library(args)
        out = capsys.readouterr()
        return code, out.out, out.err

    return run


def test_jason_form_library_check_passes_on_a_shelf_that_holds_the_recitals(tmp_path, monkeypatch, capsys):
    from jason.community.form_library import LIBRARY

    every = sorted({c for key in ("US", "CA") for d in LIBRARY.definitions(key) for c in d.recitals if "#" not in c})
    run = _data_dir_command(monkeypatch, shelf(tmp_path, every))
    code, out, err = run("--check", capsys=capsys)
    assert code == 0 and not err, out
    assert "0 failing" in out
    code, out, _ = run("--check", "--json", capsys=capsys)
    body = json.loads(out)
    assert code == 0 and body["ok"] is True
    for key in KEYS:
        assert body["statuses"][key] in ("ready", "not offered"), key
        assert not [f for f in body["findings"] if f["form"] == key and f["severity"] == "fail"], key
    code, out, _ = run("--show", "delivery-change", capsys=capsys)
    assert code == 0 and "delivery-change" in out and "CIV 4041(b)(2)(B)" in out
    code, out, _ = run("--show", "accommodation-request", "--json", capsys=capsys)
    assert code == 0 and json.loads(out)["formKey"] == "accommodation-request"


def test_a_community_that_gives_the_library_nothing_is_offered_none_of_the_new_forms_and_each_names_its_slots():
    resolved = resolve(Stub(chain=("US", "CA"), slots=()))
    for d in MINE:
        form = resolved.get(d.key)
        assert form is not None and form.status is Status.NOT_OFFERED and d.template not in resolved.templates()
        assert set(form.missing) == {f"slot {s}" for s in d.slots}


def test_a_definition_is_a_form_definition_and_a_clock_never_lengthens_a_statute():
    assert all(isinstance(d, FormDefinition) for d in MINE)
    for d in MINE:
        for clock in d.association_clocks:
            assert isinstance(clock, Clock) and clock.number >= 0
            if clock.set_by is SetBy.STATUTE:
                assert clock.section.startswith("CIV ")
