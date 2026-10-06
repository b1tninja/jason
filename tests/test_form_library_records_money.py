"""The California library definitions for records, disputes, and money (docs/form-library-design.md, build step 2A):
``records-request`` (RR), ``idr-request`` (MC), ``adr-request`` (RV), ``resale-documents`` (RT), ``membership-list`` (MN),
``payment-plan`` (PP), and ``disputed-charge`` (PR).

Everything here is made up: a throwaway shelf of statutes under ``tmp_path`` that holds each recital the forms cite with a
short stand-in for its words, stub communities, and made-up answers. No network, no model, no real data folder. The PDFs
are laid out by pymupdf's Story in place of the browser the command prints with, and made fillable by the same
``jason.tasks.forms.form_pdf`` ``jason forms --pdf`` uses.
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
from pathlib import Path

import pytest

from jason.community import form_refs
from jason.community import law_text
from jason.community.form_library import Library, Severity, Slot, Status, Tier, definitions
from jason.community.form_library.check import check
from jason.community.form_library.ca import adr, disputed_charge, idr, membership_list, payment_plan, records, resale
from jason.community.form_library.resolve import resolve
from jason.community.forms import FormKey, FormStyle, QuestionKind, check as check_answers, option_key

MODULES = (records, idr, adr, resale, membership_list, payment_plan, disputed_charge)
KEYS = ("records-request", "idr-request", "adr-request", "resale-documents", "membership-list", "payment-plan", "disputed-charge")
CODES = {"records-request": "RR", "idr-request": "MC", "adr-request": "RV", "resale-documents": "RT", "membership-list": "MN",
         "payment-plan": "PP", "disputed-charge": "PR"}
FORM_KEYS = {"records-request": FormKey.RECORDS, "idr-request": FormKey.IDR, "adr-request": FormKey.ADR_REQUEST,
             "resale-documents": FormKey.RESALE_DOCUMENTS, "membership-list": FormKey.MEMBERSHIP_LIST,
             "payment-plan": FormKey.PAYMENT_PLAN, "disputed-charge": FormKey.DISPUTED_CHARGE}

# The values a community gives. Every one is made up.
SLOTS = (Slot("ASSOCIATION", "The Test Association"), Slot("RETURN_BY_MAIL", "1 Main St, Anytown, CA 90000"),
         Slot("RETURN_BY_EMAIL", "ask@example.test"), Slot("BOARD_CONTACT", "board@example.test"),
         Slot("FEE_SCHEDULE", "a made-up schedule: ten cents a page"),
         Slot("PAYMENT_PLAN_STANDARDS", "a made-up standard: a plan of up to twelve months"))
NO_FEE = tuple(s for s in SLOTS if s.name != "FEE_SCHEDULE")
NO_STANDARDS = tuple(s for s in SLOTS if s.name != "PAYMENT_PLAN_STANDARDS")
# What a send fills in each time (never a slot).
PER_SEND = {"REFERENCE", "RECEIVED", "DUE", "DECIDER", "PROPERTY", "SENT", "RECORDED", "REQUEST_KIND"}


class Stub:
    """A community that gives the library its slots and nothing else."""

    name = "The Test Association"

    def __init__(self, slots=SLOTS):
        self._slots = slots

    def jurisdictions(self):
        return ("CA",)

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
    for module in MODULES:
        lib.register(module.DEFINITION)
    return lib


def shelf(tmp_path: Path) -> Path:
    """A throwaway data folder whose shelf holds every section the seven forms recite, each with a short made-up stand-in
    (never the statute's words) for each subdivision cited and for a whole section cited whole."""
    wanted: dict[str, set[str]] = {}
    for module in MODULES:
        for citation in module.DEFINITION.recitals:
            base, subdivisions = law_text.normal_citation(citation)
            letters = re.findall(r"\(([a-z]+)\)", subdivisions)[:1]
            wanted.setdefault(base, set()).update(letters)
    root = tmp_path / "data"
    pages = []
    for base, letters in sorted(wanted.items()):
        code, _, number = base.rpartition(" ")
        words = ("\n\n".join(f"({c}) A short made-up stand-in for the operative sentence." for c in sorted(letters))
                 or "A short made-up stand-in for the whole section.")
        file = f"authorities/{code}/{code}-{number}.md"
        (root / file).parent.mkdir(parents=True, exist_ok=True)
        (root / file).write_text(f"# {base}: made up\n\n- Source: California Legislature, 2025 session publication, read with "
                                 f"lawlibrary\n\n## {base}\n\n- History: made up\n\n{number}. (Added by Stats. 2012, Ch. 1, "
                                 f"Sec. 1.)\n\n{words}\n", encoding="utf-8")
        pages.append({"file": file, "citation": base, "title": "Made up", "code": code, "start": number, "end": number,
                      "sections": [number], "basis": "a duty", "why": ["made up"], "session": "2025"})
    (root / "authorities" / "manifest.json").write_text(json.dumps({"exported": "2026-10-04", "session": "2025", "pages": pages}),
                                                        encoding="utf-8")
    return root


def resolved(slots=SLOTS):
    return resolve(Stub(slots), mine())


def form(key: str, slots=SLOTS):
    return resolved(slots).get(key)


def plain(text: str) -> str:
    """Words as a reader sees them: bold marks gone, runs of space made one."""
    return " ".join(text.replace("**", "").split())


def words_of(template) -> str:
    return plain(" ".join([template.title, template.description, *template.preamble,
                           *(f"{q.title} {q.help} {q.authority} {' '.join(q.options)}" for q in template.questions)]))


def statement(template, field: str) -> str:
    """The one box's own words."""
    return template.question(field).options[0]


# -- what each definition is -----------------------------------------------------------------------------------------------

def test_each_definition_is_a_state_form_of_the_california_pack_with_its_code_version_and_handler():
    by_key = {m.DEFINITION.key: m.DEFINITION for m in MODULES}
    assert tuple(by_key) == KEYS
    for key, d in by_key.items():
        assert (d.tier, d.jurisdiction, d.template.code) == (Tier.STATE, "CA", CODES[key])
        assert d.template.key is FORM_KEYS[key] and d.as_of.isoformat() == "2026-10-05"
        assert d.version == ("2" if key in ("records-request", "idr-request") else "1")
        assert d.handler == "response-clock" and d.procedure == "respond"
        assert d.authority and d.recitals and d.member_clock and d.acknowledgment and d.association_clocks
        assert "{REFERENCE}" in d.acknowledgment and "{RECEIVED}" in d.acknowledgment and "{DUE}" in d.acknowledgment
        assert d.template.preamble and d.template.signature
    # the shipped library registers them under CA, in the order the pack imports them, beside the others
    shipped = {d.key: d for d in definitions("CA")}
    assert all(shipped[k] is by_key[k] for k in KEYS)


def test_the_marker_codes_are_unique_across_the_whole_library_and_none_is_the_owner_information_code():
    codes = [d.template.code for jurisdiction in ("US", "CA") for d in definitions(jurisdiction) if d.template.code]
    assert len(codes) == len(set(codes)) and "NP" not in codes
    assert set(CODES.values()) <= set(codes)
    for key, code in CODES.items():
        form_refs.campaign(code, 2026, form_refs.Channel.PAYHOA)            # a code the marker can print
    shelved = resolved()
    assert len({f.template.code for f in shelved.forms}) == len(shelved.forms)


def test_the_version_notes_record_each_question_kept_added_or_removed_in_version_two():
    for module, kept, added in (
            (records, ("name", "unit-address", "records-requested", "time-period-the-records-cover", "inspect-or-receive-copies",
                       "how-should-copies-be-delivered"),
             ("capacity", "member-name", "designation", "designation-signature", "record-sets", "period", "inspect-times", "email",
              "mailing-address", "cost-ceiling", "explanation")),
            (idr, ("name", "unit-address", "email", "what-is-the-dispute-about", "what-outcome-are-you-asking-for",
                   "preferred-meeting-days-and-times"),
             ("contact-method", "phone", "mailing-address", "related-notice", "meeting-place", "assisted-by"))):
        notes = module.VERSION_NOTES["2"]
        fields = {q.field for q in module.TEMPLATE.questions}
        assert set(kept) | set(added) == fields                             # nothing is on the form that the notes do not name
        assert all(k in notes for k in (*kept, *added)) and "removed none" in notes
        assert module.DEFINITION.version == "2" and set(module.VERSION_NOTES) == {"1", "2"}
    for module in (adr, resale, membership_list, payment_plan, disputed_charge):
        assert module.DEFINITION.version == "1" and set(module.VERSION_NOTES) == {"1"}


def test_the_two_generic_forms_keep_every_field_kind_and_option_a_return_or_a_payhoa_record_could_depend_on():
    old_idr = {"name": "short", "unit-address": "short", "email": "email", "what-is-the-dispute-about": "paragraph",
               "what-outcome-are-you-asking-for": "paragraph", "preferred-meeting-days-and-times": "paragraph"}
    old_records = {"name": "short", "unit-address": "short", "records-requested": "paragraph", "time-period-the-records-cover": "short",
                   "inspect-or-receive-copies": "choice", "how-should-copies-be-delivered": "choice"}
    old_options = {"inspect-or-receive-copies": {"Inspect", "Copies"}, "how-should-copies-be-delivered": {"Email", "Mail", "Pick up in person"}}
    for module, old in ((idr, old_idr), (records, old_records)):
        have = {q.field: q for q in module.TEMPLATE.questions}
        for field, kind in old.items():
            assert have[field].kind.value == kind
            assert set(old_options.get(field, ())) <= set(have[field].options)
        assert have["unit-address"].prefill == "UNIT_ADDRESS"
    assert [q.field for q in idr.TEMPLATE.questions][:2] == ["name", "unit-address"]


# -- required content, recitals, and the checks -----------------------------------------------------------------------------

def test_every_required_item_is_carried_by_a_question_or_the_text_or_named_as_a_gap_and_the_recitals_resolve(tmp_path):
    root = shelf(tmp_path)
    report = check(resolved(), root)
    assert report.ok, [f.line() for f in report.failing]
    assert dict(report.statuses) == {k: Status.READY for k in KEYS}
    findings = {k: report.for_form(k) for k in KEYS}
    for key in ("payment-plan", "disputed-charge"):
        assert findings[key] == ()                                             # the check's finding is empty for the form
    for key, count in (("records-request", 1), ("idr-request", 1), ("adr-request", 1), ("membership-list", 1), ("resale-documents", 3)):
        assert len(findings[key]) == count and {f.severity for f in findings[key]} == {Severity.DEFERRED}
    for module in MODULES:
        for r in module.DEFINITION.required_content:
            assert bool(r.carried_by) != bool(r.deferred), r.item               # carried, or a named gap, never both or neither
            assert r.authority


def test_a_subdivision_that_moves_fails_the_check_and_names_the_form(tmp_path):
    root = shelf(tmp_path)
    (root / "authorities" / "CIV" / "CIV-5665.md").write_text("# CIV 5665: made up\n\n- Source: made up\n\n## CIV 5665\n\n"
                                                              "- History: made up\n\n5665. (Added.)\n\n(a) Only this is left.\n",
                                                              encoding="utf-8")
    failing = check(resolved(), root).failing
    assert {(f.form, f.item) for f in failing} == {("payment-plan", "CIV 5665(b)"), ("payment-plan", "CIV 5665(c)"),
                                                   ("payment-plan", "CIV 5665(d)"), ("payment-plan", "CIV 5665(e)")}


def test_a_statutory_clock_is_the_numbers_the_sections_state_and_a_proposed_one_says_so():
    def clock(key, name):
        return next(c for c in form(key).clocks if c.name == name)

    for key, name, number, kind, section in (
            ("records-request", "current-year", 10, "business", "CIV 5210(b)(1)"),
            ("records-request", "prior-years", 30, "calendar", "CIV 5210(b)(2)"),
            ("records-request", "committee-minutes", 15, "calendar", "CIV 5210(b)(5)"),
            ("adr-request", "respond", 30, "calendar", "CIV 5935(a)(3), (c)"),
            ("adr-request", "complete", 90, "calendar", "CIV 5940(a)"),
            ("resale-documents", "documents", 10, "calendar", "CIV 4530(a)(1)"),
            ("membership-list", "inspect", 5, "business", "CORP 8330(a)(1)"),
            ("membership-list", "list", 10, "business", "CIV 5210(b)(6); CORP 8330(a)(2)"),
            ("membership-list", "alternative", 10, "business", "CORP 8330(c)"),
            ("payment-plan", "window", 15, "calendar", "CIV 5665(b)"),
            ("payment-plan", "meeting", 45, "calendar", "CIV 5665(b); CIV 4935(c)"),
            ("disputed-charge", "lien-release", 21, "calendar", "CIV 5685(b)")):
        c = clock(key, name)
        assert (c.number, c.kind.value, c.set_by.value, c.section) == (number, kind, "statute", section)
    for key in KEYS:
        for c in form(key).clocks:
            assert c.set_by.value in ("statute", "proposed policy")             # nothing is called the documents' without a section
            if c.set_by.value == "proposed policy":
                assert "proposed policy" in c.words()
    # the page's test (i): every clock of the disputed-charge form is a proposal except the lien release
    assert {c.name for c in form("disputed-charge").clocks if c.set_by.value == "statute"} == {"lien-release"}
    # the meet-and-confer form states no statutory number: the maximum time is the association's to state (5910(b))
    assert {c.set_by.value for c in form("idr-request").clocks} == {"proposed policy"}


# -- the words the law requires, word for word ------------------------------------------------------------------------------

def test_the_request_for_resolution_carries_what_5935_says_it_shall_include_item_by_item():
    t = form("adr-request").template
    text = words_of(t)
    assert "REQUEST FOR RESOLUTION" in text
    assert "required to respond within 30 days of receipt or the request will be deemed rejected" in text          # 5935(a)(3)
    assert "A party on whom a Request for Resolution is served has 30 days following service to accept or reject" in text
    assert "not required when the request is sent to the association" in text                                       # 5935(a)(4)
    assert adr.SUMMARY_SENTENCE in text                                                                             # 5965(a)
    assert t.question("dispute").required and t.question("adr-request").required                                    # (a)(1), (a)(2)
    assert t.question("adr-request").options == ("I request alternative dispute resolution (mediation, arbitration, conciliation, or "
                                                 "another nonjudicial procedure with a neutral person) of this dispute",)
    assert {r.item for r in adr.DEFINITION.required_content if r.authority.startswith("CIV 5935(a)(")} == {
        "A brief description of the dispute between the parties", "A request for alternative dispute resolution",
        "A notice that the party receiving the Request for Resolution is required to respond within 30 days of receipt or the "
        "request will be deemed rejected", "If the party on whom the request is served is the member, a copy of this article"}
    assert "date-sent" in {c for r in adr.DEFINITION.required_content for c in r.carried_by}
    assert t.code == "RV" and "NP" != t.code


def test_the_sale_documents_request_offers_exactly_the_22_rows_of_4528_and_holds_the_billing_form_words():
    t = form("resale-documents").template
    assert len(resale.DOCUMENTS) == 22 and resale.NAMES == tuple(n for n, _ in resale.DOCUMENTS)
    assert t.question("documents").options == resale.NAMES == t.question("seller-provides").options        # and no "other"
    assert len({option_key(o) for o in resale.NAMES}) == 22                                                # each box its own field
    assert not any("other" in o.lower() and "document" in o.lower() for o in t.question("documents").options)
    assert resale.DOCUMENTS[0] == ("Articles of Incorporation or statement that not incorporated", "Section 4525(a)(1)")
    assert resale.DOCUMENTS[-1][1] == "Sections 4525(a)(11) and 5551"
    assert resale.BILLING_TITLE == "CHARGES FOR DOCUMENTS PROVIDED AS REQUIRED BY SECTION 4525*"
    assert resale.BILLING_NOT_ALL.endswith("shall not be required to purchase ALL of the documents listed on this form.")
    assert resale.BILLING_ASTERISK.startswith("The information provided by this form may not include all fees")
    text = words_of(t)
    assert "within 10 days of the mailing or delivery of the request" in text                                # 4530(a)(1)
    assert "may not be bundled with it" in text and "on the form described in Civil Code 4528" in text
    # nothing asked that the law does not need: the buyer, the price, a fee paid
    assert not any(w in " ".join(q.title.lower() for q in t.questions) for w in ("buyer", "price", "escrow date", "deposit"))
    # the 10-point rule: FormStyle holds no smallest size, so it is a named rendering requirement and a deferred required item
    assert resale.BILLING_MIN_POINT_SIZE == 10 and "min_point_size" not in FormStyle.__dataclass_fields__
    assert any(r.item.startswith("B1") and r.deferred for r in resale.DEFINITION.required_content)


def test_the_membership_list_form_carries_the_opt_out_in_5220s_words_and_asks_the_purpose_5225_requires():
    t = form("membership-list").template
    assert t.question("optout-statement").options == (membership_list.OPT_OUT_STATEMENT,)
    assert membership_list.OPT_OUT_STATEMENT == ("I prefer to be contacted via the alternative process described in subdivision (c) of "
                                                 "Section 8330 of the Corporations Code")
    assert "reasonably related to your interest as a member" in plain(t.question("purpose").help)
    text = words_of(t)
    assert "This opt-out remains in effect until changed by the member" in text
    assert "leaves out the members who have opted out" in text
    assert t.question("action").options == membership_list.ACTIONS and len(membership_list.ACTIONS) == 3


def test_the_meet_and_confer_form_recites_the_sections_words_and_states_the_proposed_time_as_proposed():
    text = words_of(form("idr-request").template)
    assert "The association shall not refuse a request to meet and confer" in text                           # 5915(b)(2)
    assert "The board shall designate a director to meet and confer" in text                                  # 5915(b)(3)
    assert "You are not charged a fee to take part" in text and "Civil Code 5910(g), 5915(d)" in text
    assert "assisted by an attorney or another person" in text and "at your own cost" in text                # 5910(f)
    assert "signed by you and the board's designee for the association" in text                               # 5915(b)(5)
    assert "is either consistent with the authority the board gave its designee or ratified by the board" in text   # 5915(c)(2)
    assert "Proposed until the board adopts a time" in text and "30 calendar days" in text                   # never printed as the law's
    assert "A board member will contact you" not in text


def test_the_payment_plan_and_disputed_charge_forms_recite_the_sections_times_and_protest_words():
    plan = words_of(form("payment-plan").template)
    assert "within 45 days of the postmark of the request" in plan
    assert "within 15 days of the date of the postmark of the notice" in plan
    assert "a made-up standard: a plan of up to twelve months" in plan                                       # the slot, filled
    protest = form("disputed-charge").template
    text = words_of(protest)
    assert "pay under protest the disputed amount and all other amounts levied" in text                     # 5658(a)
    assert "Nothing in this section shall impede an association’s ability to collect delinquent assessments" in text    # 5658(b)
    assert "Do not write a card, bank, or account number on this form." in plain(" ".join(protest.preamble))
    assert "all other amounts" in protest.question("paid-amount").title
    assert protest.question("protest").required and "under protest" in protest.question("protest").options[0]
    for q in protest.questions:                                                                              # nothing it should not ask
        assert not any(w in q.title.lower() for w in ("card number", "bank", "routing", "income", "sue"))


def test_the_records_form_recites_the_designation_the_cost_the_electronic_option_the_timeframes_and_the_explanation():
    t = form("records-request").template
    text = words_of(t)
    assert "the member shall make this designation in writing" in text.replace("The member", "the member")      # 5205(b)
    assert "tell you the amount, and you agree to pay it, before anything is copied or sent" in text           # 5205(f)
    assert "up to $10 an hour, and not more than $200" in text                                                # 5205(g)
    assert "electronic transmission or on machine-readable storage media" in text                           # 5205(h)
    assert "within 10 business days" in text and "30 calendar days" in text                                  # 5210(b)
    assert "written explanation specifying the legal basis" in text                                          # 5215(d)
    assert "5205(f)" in t.description and "5205(g)" in t.description and "5205(e)" not in t.description
    # no purpose is asked, no phone, no occupancy, and no Safe at Home question (5216(b)): the page's test (d)
    titles = " ".join(q.title.lower() for q in t.questions)
    assert not any(w in titles for w in ("why do you", "purpose", "safe at home", "occupan"))


# -- email only when email is chosen ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("key", KEYS)
def test_no_email_or_phone_is_ever_required_and_the_question_says_when_it_is_needed(key):
    t = form(key).template
    for q in t.questions:
        if q.kind in (QuestionKind.EMAIL, QuestionKind.PHONE):
            assert not q.required, q.field
            assert "only if" in q.help.lower(), q.field
        if q.field == "mailing-address":
            assert not q.required and "only if" in q.help.lower()
    assert any(q.kind is QuestionKind.EMAIL for q in t.questions)


def test_the_records_form_asks_for_email_only_if_delivery_by_email_is_chosen():
    t = form("records-request").template
    mail = {"name": "A. Owner", "unit-address": "123 Main St", "capacity": "A member (owner) of the association",
            "record-sets": ["Executed contracts"], "records-requested": "The roofing contract", "period": ["Last fiscal year"],
            "inspect-or-receive-copies": "Copies", "how-should-copies-be-delivered": "Mail"}
    assert check_answers(t, mail) == []                                       # copies by mail: no email asked, none missing
    assert check_answers(t, {**mail, "how-should-copies-be-delivered": "Email", "email": "a.owner@example.test"}) == []
    assert check_answers(t, {**mail, "how-should-copies-be-delivered": "Email", "email": "not an address"}) == [
        "Email address for the electronic copies: not an email address: not an address"]
    # the old form required an email nowhere on the records form; the meet-and-confer form required one and no longer does
    old_email = next(q for q in idr.TEMPLATE.questions if q.field == "email")
    assert not old_email.required and next(q for q in idr.TEMPLATE.questions if q.field == "contact-method").required


# -- the page's made-up answers, read against the form ---------------------------------------------------------------------

def _answers():
    rec, i, a, rs, ml, pp, dc = (form(k).template for k in KEYS)
    sets = records.RECORD_SETS
    return {
        "records-request": (rec, [
            {"name": "A. Owner", "unit-address": "123 Main St, Anytown, CA 90000", "capacity": "A member (owner) of the association",
             "record-sets": ["Executed contracts", "Check registers"], "records-requested": "The landscape and roofing contracts",
             "period": ["Last fiscal year"], "inspect-or-receive-copies": "Copies", "how-should-copies-be-delivered": "Email",
             "email": "a.owner@example.test", "explanation": [statement(rec, "explanation")]},
            {"name": "A. Owner", "unit-address": "123 Main St", "capacity": "A member (owner) of the association",
             "record-sets": [sets[6]], "records-requested": "Board minutes since January",
             "period": ["Minutes of member or board meetings, any date"], "inspect-or-receive-copies": "Inspect"},
            {"name": "B. Agent", "unit-address": "456 Elm St", "capacity": "A person the member has designated in writing",
             "member-name": "C. Owner", "designation": [statement(rec, "designation")], "designation-signature": "C. Owner, 2026-10-01",
             "record-sets": [sets[10]], "records-requested": "Invoices and canceled checks for the pool repair",
             "period": ["This fiscal year", "Last fiscal year"], "inspect-or-receive-copies": "Inspect, then copies",
             "how-should-copies-be-delivered": "Mail", "mailing-address": "456 Elm St", "cost-ceiling": "$40"}]),
        "idr-request": (i, [
            {"name": "A. Owner", "unit-address": "123 Main St", "contact-method": "By email", "email": "a.owner@example.test",
             "what-is-the-dispute-about": "I was fined for a parking violation I believe did not occur", "what-outcome-are-you-asking-for":
             "Withdraw the fine", "related-notice": "A notice of a violation or a hearing", "preferred-meeting-days-and-times":
             "Weekday evenings", "meeting-place": "By video"},
            {"name": "A. Owner", "unit-address": "123 Main St", "contact-method": "By phone", "phone": "(555) 010-0100",
             "what-is-the-dispute-about": "The landscaping near my unit is not being maintained"},
            {"name": "B. Owner", "unit-address": "456 Elm St", "contact-method": "By mail", "mailing-address": "456 Elm St",
             "what-is-the-dispute-about": "I dispute the late charges on my account", "assisted-by": "D. Lawyer"}]),
        "adr-request": (a, [
            {"name": "A. Owner", "unit-address": "123 Main St", "contact-method": "By email", "email": "a.owner@example.test",
             "other-parties": "The association", "dispute": "The association has not removed a fence it approved",
             "adr-request": [statement(a, "adr-request")], "adr-kind": "Mediation", "date-sent": "2026-10-05"},
            {"name": "A. Owner", "unit-address": "123 Main St", "contact-method": "By mail", "mailing-address": "123 Main St",
             "other-parties": "The association", "dispute": "A dispute over the cost of a repair",
             "adr-request": [statement(a, "adr-request")], "date-sent": "2026-10-05"},
            {"name": "A. Owner", "unit-address": "123 Main St", "contact-method": "By mail", "mailing-address": "123 Main St",
             "other-parties": "The association and another member", "other-party-names": "B. Neighbor, 456 Elm St",
             "dispute": "A fence on the line", "adr-request": [statement(a, "adr-request")], "urgent": [statement(a, "urgent")],
             "date-sent": "2026-09-30"}]),
        "resale-documents": (rs, [
            {"action": "Ask for the documents", "requester-name": "E. Escrow", "requester-role":
             "A person the owner has authorized (agent, escrow, title, attorney)", "owner-name": "A. Owner",
             "property-address": "123 Main St, Anytown, CA 90000", "authorization": [statement(rs, "authorization")],
             "authorization-signature": "A. Owner, 2026-10-01", "documents": list(resale.NAMES), "date-sent": "2026-10-05",
             "recipient-name": "E. Escrow", "delivery": "By electronic transmission", "email": "e.escrow@example.test"},
            {"action": "Ask for the documents", "requester-name": "A. Owner", "requester-role": "The owner of the unit",
             "owner-name": "A. Owner", "property-address": "123 Main St", "documents": list(resale.NAMES[:4]),
             "date-sent": "2026-10-05", "recipient-name": "A. Owner", "delivery": "I will collect them"}]),
        "membership-list": (ml, [
            {"action": membership_list.ACTIONS[0], "name": "A. Owner", "unit-address": "123 Main St", "how": membership_list.HOW[1],
             "purpose": "To ask members to sign a petition to put a rule change on the agenda",
             "delivery": "By electronic transmission", "email": "a.owner@example.test"},
            {"action": membership_list.ACTIONS[1], "name": "A. Owner", "unit-address": "123 Main St", "for-whom": "Me only",
             "optout-statement": [membership_list.OPT_OUT_STATEMENT]}]),
        "payment-plan": (pp, [
            {"name": "A. Owner", "unit-address": "123 Main St", "request": [statement(pp, "request")], "notice-date": "2026-09-20",
             "date-sent": "2026-09-28", "contact-method": "By email", "email": "a.owner@example.test", "proposal": "Twelve monthly payments",
             "include-accruing": [statement(pp, "include-accruing")], "availability": "Evenings"},
            {"name": "A. Owner", "unit-address": "123 Main St", "request": [statement(pp, "request")], "date-sent": "2026-09-28",
             "contact-method": "By mail", "mailing-address": "123 Main St"}]),
        "disputed-charge": (dc, [
            {"name": "A. Owner", "unit-address": "123 Main St", "charge-kind": "A late fee",
             "charge-description": "The late fee on the October statement", "charge-amount": "$25.00",
             "why": "I paid on the 10th and have a receipt dated the 10th", "paid-amount": "$325.00", "paid-date": "2026-10-05",
             "protest": [statement(dc, "protest")], "receipt": [statement(dc, "receipt")], "contact-method": "By email",
             "email": "a.owner@example.test"},
            {"name": "A. Owner", "unit-address": "123 Main St", "charge-kind": "An assessment",
             "charge-description": "The special assessment of 2026", "charge-amount": "$500.00", "why": "The notice was not sent",
             "paid-amount": "$1,250.00", "paid-date": "2026-10-05", "protest": [statement(dc, "protest")],
             "contact-method": "By mail", "mailing-address": "123 Main St"}]),
    }


@pytest.mark.parametrize("key", KEYS)
def test_the_pages_typical_and_minimal_answers_read_clean_against_the_form(key):
    template, fixtures = _answers()[key]
    for answers in fixtures:
        assert check_answers(template, answers) == []


def test_a_request_with_a_required_item_left_blank_is_reported():
    adr_form = form("adr-request").template
    blank = {"name": "A. Owner", "unit-address": "123 Main St", "contact-method": "By mail", "other-parties": "The association",
             "date-sent": "2026-10-05"}
    assert check_answers(adr_form, blank) == ["A brief description of the dispute: required, left blank",
                                              "Request for alternative dispute resolution: required, left blank"]
    plan = form("payment-plan").template
    assert check_answers(plan, {"name": "A. Owner", "unit-address": "123 Main St", "contact-method": "By mail"}) == [
        "Request to meet with the board: required, left blank", "The date you mailed or delivered this request: required, left blank"]


# -- the form is built from its definition: slots, tokens, questions -------------------------------------------------------

@pytest.mark.parametrize("key", KEYS)
def test_every_slot_a_form_uses_is_declared_and_every_declared_slot_fills_the_forms_words(key):
    d = next(m.DEFINITION for m in MODULES if m.DEFINITION.key == key)
    t = d.template
    texts = [t.title, t.description, t.attestation, *t.preamble, d.member_clock, *(q.help for q in t.questions)]
    used = {tok for text in texts for tok in re.findall(r"\{([A-Z][A-Z0-9_]*)\}", text)}
    assert used <= set(d.slots), used - set(d.slots)                               # a slot the form uses is declared (so it can be missing)
    ack = {tok for tok in re.findall(r"\{([A-Z][A-Z0-9_]*)\}", d.acknowledgment)} - PER_SEND
    assert ack <= set(d.slots)
    done = form(key).template
    left = {tok for text in [done.description, *done.preamble, *(q.help for q in done.questions)]
            for tok in re.findall(r"\{([A-Z][A-Z0-9_]*)\}", text)}
    assert not left, left                                                          # nothing a person would read as a token on paper
    assert "ask@example.test" in " ".join(done.preamble) and "1 Main St, Anytown, CA 90000" in " ".join(done.preamble)
    fields = [q.field for q in t.questions]
    assert len(fields) == len(set(fields))
    for q in t.questions:
        assert len({option_key(o) for o in q.options}) == len(q.options)


def test_a_form_whose_slot_is_missing_is_not_offered_and_the_slot_is_named_not_a_crash(tmp_path):
    no_fee = resolved(NO_FEE)
    sale = no_fee.get("resale-documents")
    assert sale.status is Status.NOT_OFFERED and sale.missing == ("slot FEE_SCHEDULE",)
    no_standards = resolved(NO_STANDARDS)
    plan = no_standards.get("payment-plan")
    assert plan.status is Status.NOT_OFFERED and plan.missing == ("slot PAYMENT_PLAN_STANDARDS",)
    for other in KEYS:
        if other not in ("resale-documents",):
            assert no_fee.get(other).status is Status.READY
        if other not in ("payment-plan",):
            assert no_standards.get(other).status is Status.READY
    assert "resale-documents" not in [t.key.value for t in no_fee.templates()]
    assert FormKey.PAYMENT_PLAN not in [t.key for t in no_standards.templates()]
    root = shelf(tmp_path)
    findings = [(f.form, f.item, f.severity) for f in check(no_fee, root).findings if f.check.title == "slots"]
    assert findings == [("resale-documents", "slot FEE_SCHEDULE", Severity.NOT_OFFERED)]
    assert check(no_fee, root).ok and check(no_standards, root).ok                  # not offered is a report, not a failure
    bare = resolve(Stub(()), mine())                                               # a community that gives nothing
    assert all(f.status is Status.NOT_OFFERED for f in bare.forms) and bare.templates() == ()
    assert {m for f in bare.forms for m in f.missing} == {"slot RETURN_BY_MAIL", "slot RETURN_BY_EMAIL", "slot BOARD_CONTACT",
                                                          "slot FEE_SCHEDULE", "slot PAYMENT_PLAN_STANDARDS"}


def test_the_forms_the_first_profile_already_offered_are_still_offered_by_it():
    from jason.community import community

    offered = {t.key.value for t in community().forms()}
    assert {"idr", "records"} <= offered                                           # today's three keys keep working
    # the form that waits for a fact the profile does not give is named, not guessed (never an invented fee or standard)
    shelved = resolve(community())
    for key, slot in (("resale-documents", "slot FEE_SCHEDULE"), ("payment-plan", "slot PAYMENT_PLAN_STANDARDS")):
        assert slot in shelved.get(key).missing


# -- the form renders to a fillable PDF with its marker and a reference -----------------------------------------------------

@pytest.fixture
def laid_out(monkeypatch):
    """The printed page laid out by pymupdf in place of the browser ``jason forms --pdf`` prints with."""
    import pymupdf

    from jason.tasks import packets

    def print_pdf(page, out, *, run=None):
        story = pymupdf.Story(html=page)
        writer = pymupdf.DocumentWriter(str(out))
        where = pymupdf.paper_rect("letter") + (54, 54, -54, -54)
        more = 1
        while more:
            device = writer.begin_page(pymupdf.paper_rect("letter"))
            more, _ = story.place(where)
            story.draw(device)
            writer.end_page()
        writer.close()
        return out

    monkeypatch.setattr(packets, "print_pdf", print_pdf)


@pytest.mark.parametrize("key", KEYS)
def test_each_form_renders_to_a_fillable_pdf_with_every_question_its_marker_and_a_reference(key, tmp_path, laid_out):
    import pymupdf

    from jason.community.fillable import read_answers, stamp_reference
    from jason.tasks.forms import form_pdf

    template = form(key).template
    out = tmp_path / f"{key}.pdf"
    names = form_pdf(template, out, association="The Test Association")
    for q in template.questions:                                                   # every question is a field (a choice's boxes, an
        assert any(n == q.field or n.startswith((q.field + ".", q.field + "#")) for n in names), q.field   # address's parts)
    assert names[-2:] == ["signature", "date"]
    marker = form_refs.make(template.code, 26, form_refs.Channel.PAYHOA)
    assert marker.text.startswith(template.code + "26P") and form_refs.parse(marker.text)[0].text == marker.text
    stamp_reference(out, marker.text)
    with pymupdf.open(out) as doc:
        page_text = " ".join(" ".join(page.get_text().split()) for page in doc)
    assert marker.text in page_text and template.title in page_text                 # printed on the page, with the form's own title
    returned = read_answers(out, template, source=out.name)
    assert returned.reference == marker.text                                       # and read back from the returned copy
    # one filled copy reads back by field
    from jason.community import pdf_fields as pf

    filled = tmp_path / f"{key}-filled.pdf"
    typed = next(q for q in template.questions if q.kind is QuestionKind.SHORT and q.field == "name" or q.field == "requester-name")
    pf.fill(out, {typed.field: "A. Owner", "signature": "A. Owner", "date": "10/5/2026"}, filled)
    again = read_answers(filled, template)
    assert again.answers[typed.field] == "A. Owner" and again.signature == "A. Owner" and again.reference == marker.text


def test_the_adr_pdf_prints_the_statutes_notice_in_its_own_words(tmp_path, laid_out):
    import pymupdf

    from jason.tasks.forms import form_pdf

    out = tmp_path / "adr.pdf"
    form_pdf(form("adr-request").template, out, association="The Test Association")
    with pymupdf.open(out) as doc:
        text = " ".join(" ".join(page.get_text().split()) for page in doc)
    assert "REQUEST FOR RESOLUTION" in text
    assert "required to respond within 30 days of receipt or the request will be deemed rejected" in text


# -- the command ------------------------------------------------------------------------------------------------------------

@pytest.fixture
def library_command(monkeypatch, tmp_path):
    """``jason form-library`` on a community built for the test, over the seven forms and the throwaway shelf."""
    from jason.commands import form_library as module

    root = shelf(tmp_path)
    monkeypatch.setattr(module, "_data_dir", lambda args: root)
    monkeypatch.setattr(importlib.import_module("jason.community.form_library.resolve"), "LIBRARY", mine())
    monkeypatch.setattr(module, "_community", lambda: Stub())

    def run(*argv, capsys):
        parser = argparse.ArgumentParser()
        module.register(parser.add_subparsers(), lambda p: None, lambda a: None)
        args = parser.parse_args(["form-library", *argv])
        code = module.cmd_form_library(args)
        out = capsys.readouterr()
        return code, out.out, out.err

    return run


def test_jason_form_library_check_passes_with_the_new_forms_and_reports_only_the_named_gaps(library_command, capsys):
    code, out, err = library_command("--check", capsys=capsys)
    assert code == 0 and not err
    assert "7 form(s) checked: 0 failing, 0 not offered, 7 deferred" in out
    code, out, _ = library_command("--check", "--json", capsys=capsys)
    body = json.loads(out)
    assert code == 0 and body["ok"] is True and set(body["statuses"].values()) == {"ready"}
    code, out, _ = library_command(capsys=capsys)
    assert code == 0 and "7 ready, 0 adjusted, 0 not offered, 0 failing" in out
    for key in KEYS:
        assert key in out
    code, out, _ = library_command("--show", "adr-request", capsys=capsys)
    assert code == 0 and "marker code RV" in out and "respond: 30 calendar days from receipt or service, whichever is earlier" in out


def test_jason_form_library_names_the_missing_slot_for_a_community_that_has_not_given_it(library_command, capsys, monkeypatch):
    from jason.commands import form_library as module

    monkeypatch.setattr(module, "_community", lambda: Stub(NO_FEE))
    code, out, _ = library_command(capsys=capsys)
    assert code == 0 and "6 ready, 0 adjusted, 1 not offered, 0 failing" in out
    assert "not offered, missing: slot FEE_SCHEDULE" in out
    code, out, _ = library_command("--check", capsys=capsys)
    assert code == 0 and "slot FEE_SCHEDULE" in out and "1 not offered" in out


# -- jason forms: the keys come from the community, at run time ------------------------------------------------------------

def test_the_forms_command_builds_its_parser_without_asking_the_community_for_its_forms(monkeypatch):
    import jason.community as comm
    from jason.commands import drafts_forms

    def refuse():
        raise AssertionError("the profile was read while the parser was built")

    monkeypatch.setattr(comm, "community", refuse)
    parser = argparse.ArgumentParser()
    drafts_forms.register(parser.add_subparsers(), lambda p: None, lambda a: None)
    args = parser.parse_args(["forms", "--pdf", "no-such-form", "--form", "anything"])    # any word parses; the run refuses it
    assert (args.pdf, args.form) == ("no-such-form", "anything")


def test_the_forms_command_refuses_a_form_the_community_does_not_offer_and_lists_the_ones_it_does(monkeypatch, capsys, tmp_path):
    from jason.commands import drafts_forms

    monkeypatch.setattr(drafts_forms, "_data_dir", lambda args: tmp_path)
    for option, extra in (("create", {}), ("pdf", {}), ("payhoa", {}), ("payhoa_test", {}), ("payhoa_submissions", {}),
                          ("form", {"read": ["x.pdf"]})):
        args = argparse.Namespace(**{option: "no-such-form", "yes": False, **extra})
        assert drafts_forms.cmd_forms(args, lambda a: None) == 2
        err = capsys.readouterr().err
        assert "jason forms: no form 'no-such-form'" in err and "offers: idr, records" in err
    # a form the library has and the community cannot offer says what it waits for
    args = argparse.Namespace(pdf="resale-documents", yes=False)
    assert drafts_forms.cmd_forms(args, lambda a: None) == 2
    assert "resale-documents is not offered" in capsys.readouterr().err


def test_the_forms_command_still_takes_the_three_keys_it_always_did_and_the_librarys_own_spelling(monkeypatch, capsys, tmp_path):
    from jason.commands import drafts_forms

    monkeypatch.setattr(drafts_forms, "_data_dir", lambda args: tmp_path)
    for key, title in (("idr", "Request for Internal Dispute Resolution"), ("records", "Request to Inspect Association Records"),
                       ("owner-info", None), ("idr-request", "Request for Internal Dispute Resolution"),
                       ("records-request", "Request to Inspect Association Records")):
        args = argparse.Namespace(create=key, yes=False)
        assert drafts_forms.cmd_forms(args, lambda a: None) == 0
        out = capsys.readouterr().out
        assert "Dry run" in out and (title is None or f"Form: {title}" in out)
        assert args.create in ("idr", "records", "owner-info")                       # read back in the template's own words
