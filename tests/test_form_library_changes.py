"""The California forms for changes to a unit and the protected uses (docs/form-library-design.md, build step 2, part B1): the
architectural application, the request for reconsideration, the electric vehicle charging station, the solar energy system,
and the protected use. Each is checked against a throwaway shelf of short made-up stand-in sentences for the subdivisions it
recites, never the real data folder; the one test that reads the real shelf skips when it is not there. No network, no model.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

import pytest

from jason.community.form_library import Add, Slot, Status, Tier, definitions
from jason.community.form_library.check import check
from jason.community.form_library.resolve import resolve
from jason.community.form_library.tiers import TOKEN, Check, Severity
from jason.community.forms import FormKey

KEYS = ("architectural-application", "reconsideration-request", "ev-charger", "solar", "protected-use-application")
CODES = {"architectural-application": "AP", "reconsideration-request": "RC", "ev-charger": "EV", "solar": "PV",
         "protected-use-application": "PX"}
FORM_KEYS = {"architectural-application": FormKey.ARCHITECTURAL_APPLICATION, "reconsideration-request": FormKey.RECONSIDERATION_REQUEST,
             "ev-charger": FormKey.EV_CHARGER, "solar": FormKey.SOLAR, "protected-use-application": FormKey.PROTECTED_USE_APPLICATION}
DATA = Path(__file__).resolve().parents[1] / "data"


def mine():
    by = {d.key: d for d in definitions("CA")}
    return {k: by[k] for k in KEYS}


# -- a made-up shelf: a short stand-in sentence for every subdivision a definition recites ---------------------------------

def _order(label: str):
    return (0, int(label)) if label.isdigit() else (1, label)


def _render(tree: dict) -> list[str]:
    out: list[str] = []
    for label in sorted(tree, key=_order):
        out.append(f"({label}) A made-up stand-in sentence for {label}.")
        out += _render(tree[label])
    return out


def stand_in_shelf(root: Path, citations) -> Path:
    from jason.community import law_text

    wanted: dict[str, dict] = {}
    for citation in citations:
        found = law_text.normal_citation(citation) if "#" not in citation else None
        if found is None:
            continue
        base, subs = found
        code, _, number = base.partition(" ")
        node = wanted.setdefault((code, number), {})
        for label in re.findall(r"\(([^)]+)\)", subs):
            node = node.setdefault(label, {})
    pages = []
    for (code, number), tree in wanted.items():
        (root / "authorities" / code).mkdir(parents=True, exist_ok=True)
        words = "\n\n".join(_render(tree) or ["(a) A made-up stand-in sentence."])
        file = f"authorities/{code}/{code}-{number}.md"
        (root / file).write_text(f"# {code} {number}: made up\n\n- Source: California Legislature, 2025 session publication, "
                                 f"read with lawlibrary\n\n## {code} {number}\n\n- History: made up\n\n{number}. (Added by Stats. "
                                 f"2012, Ch. 1, Sec. 1.)\n\n{words}\n", encoding="utf-8")
        pages.append({"file": file, "citation": f"{code} {number}", "title": "Made up", "code": code, "start": number, "end": number,
                      "sections": [number], "basis": "a duty", "why": ["made up"], "session": "2025"})
    (root / "authorities" / "manifest.json").write_text(json.dumps({"exported": "2026-10-04", "session": "2025", "pages": pages}),
                                                        encoding="utf-8")
    return root


class Giving:
    """A community that gives every slot a form declares, except the ones it is told to leave out."""

    def __init__(self, *, leave=(), changes=()):
        names = {s for d in mine().values() for s in d.slots}
        self.values = [Slot(n, f"made up {n}") for n in sorted(names - set(leave))]
        self.changes = tuple(changes)

    def jurisdictions(self):
        return ("CA",)

    def form_slots(self):
        return tuple(self.values)

    def form_adjustments(self):
        return self.changes

    def form_bindings(self):
        return ()

    def custom_forms(self):
        return ()


@pytest.fixture
def shelf(tmp_path):
    return stand_in_shelf(tmp_path / "data", [r for d in definitions("CA") for r in d.recitals])


def resolved(**kw):
    return resolve(Giving(**kw))


# -- what each definition is --------------------------------------------------------------------------------------------

def test_each_definition_is_a_state_form_of_the_california_pack_with_its_code_and_authority():
    for key, d in mine().items():
        assert (d.tier, d.jurisdiction, d.version, d.as_of) == (Tier.STATE, "CA", "1", date(2026, 10, 4)), key
        assert d.template.key is FORM_KEYS[key] and d.template.code == CODES[key] and d.authority and d.recitals
        assert (d.handler, d.procedure) == ("response-clock", "respond") and d.member_clock and d.acknowledgment and d.channels
        assert d.association_clocks and d.required_content
        assert any("improvement-request" in n for n in d.notes), f"{key}: the page's own procedure key is noted"


def test_each_forms_required_content_is_carried_on_a_shelf_of_stand_in_sentences(shelf):
    both = resolved()
    report = check(both, shelf)
    for key in KEYS:
        assert both.get(key).status is Status.READY, (key, both.get(key).missing)
        assert [f.line() for f in report.for_form(key)] == [], key               # no failure, no deferral, nothing not offered
        assert report.status(key) is Status.READY


def test_what_a_form_prints_between_braces_is_a_slot_it_declares():
    """A token on a blank form that no slot fills would print as braces: every one is declared (the per-request values live
    in the acknowledgment, which the handler fills)."""
    for key, d in mine().items():
        t = d.template
        text = [t.description, t.attestation, *t.preamble, *(q.help for q in t.questions)]
        tokens = {m for part in text for m in TOKEN.findall(part)}
        assert tokens <= set(d.slots), (key, tokens - set(d.slots))
        done = resolved().get(key).template
        shown = " ".join([done.description, done.attestation, *done.preamble])
        assert not TOKEN.findall(shown), (key, TOKEN.findall(shown))             # given every slot, none is left in the words


def test_every_question_says_why_and_a_field_is_named_once():
    for key, d in mine().items():
        fields = [q.field for q in d.template.questions]
        assert len(fields) == len(set(fields)), key
        for q in d.template.questions:
            assert q.authority, f"{key}: {q.title!r} has no why"
        assert d.template.signature and d.template.attestation


def test_no_question_asks_for_an_email_unless_email_is_chosen_nor_anything_about_a_tenant_or_a_health_condition():
    for key, d in mine().items():
        email = [q for q in d.template.questions if q.field == "contact_email"]
        assert all(not q.required and "chose email" in q.help for q in email), key
        words = " ".join(f"{q.title} {q.help} {' '.join(q.options)}" for q in d.template.questions).lower()
        for banned in (r"tenants?\b", r"lease\b", r"diagnos", r"disability of", r"religion", r"faith", r"income", r"vehicle you"):
            assert not re.search(rf"\b{banned}", words), (key, banned)


# -- the codes ------------------------------------------------------------------------------------------------------------

def test_codes_are_unique_across_the_resolved_set_and_none_is_np():
    from jason.community import community, form_refs

    codes = [f.template.code.upper() for f in resolve(community()).forms if f.template.code]       # the library's and the profile's own
    assert len(codes) == len(set(codes)) and "NP" in codes                                            # owner information keeps NP
    assert {CODES[k] for k in KEYS} <= set(codes) and "NP" not in CODES.values()
    for code in CODES.values():
        marker = form_refs.make(code, 2027, form_refs.Channel.EMAIL, membership_id=1, unit_id=2)
        assert form_refs.parse(f"Ref {marker.text}") == [marker]


def test_the_check_finds_no_clash_among_the_codes(shelf):
    report = check(resolved(), shelf)
    assert [f.line() for f in report.findings if f.check is Check.CODES] == []


# -- the fillable PDF, with its code and a reference ----------------------------------------------------------------------

def _story_chrome(args, **kwargs):
    """Stands in for headless Chrome: lays the page's HTML out with PyMuPDF's Story into --print-to-pdf."""
    from urllib.parse import urlparse
    from urllib.request import url2pathname

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


@pytest.mark.parametrize("key", KEYS)
def test_each_form_renders_to_a_fillable_pdf_that_carries_its_code_and_a_reference(key, tmp_path, monkeypatch):
    import pymupdf

    import jason.tasks.email_review as email_review
    from jason.community import form_refs
    from jason.community import pdf_fields as pf
    from jason.community.fillable import stamp_reference
    from jason.tasks.forms import form_pdf

    monkeypatch.setattr(email_review, "browser", lambda: "chrome")
    template = resolved().get(key).template
    out = tmp_path / f"{key}.pdf"
    names = form_pdf(template, out, association="Test Association", run=_story_chrome)
    for q in template.questions:                                            # a field for every question, by its own name
        assert any(n == q.field or n.startswith(q.field + ".") or n.startswith(q.field + "#") for n in names), (key, q.field)
    assert names[-2:] == ["signature", "date"]
    marker = form_refs.make(template.code, 2027, form_refs.Channel.EMAIL, membership_id=7, unit_id=9)
    stamp_reference(out, marker.text)
    with pymupdf.open(out) as doc:
        text = doc[0].get_text()
    assert marker in form_refs.parse(text) and marker.campaign == f"{CODES[key]}27E"       # a long page may read an accidental extra
    assert pf.values(out)["unit"] == "" and "unit" in pf.values(out)


# -- a form with a missing slot is not offered, and the slot is named ------------------------------------------------------

def test_a_form_with_a_missing_slot_is_not_offered_and_the_slot_is_named(shelf):
    gap = resolved(leave=("PROCEDURE_CITATION",))
    for key in KEYS:
        form = gap.get(key)
        assert form.status is Status.NOT_OFFERED and form.missing == ("slot PROCEDURE_CITATION",), key
        assert form.template not in gap.templates()
    named = [(f.form, f.item, f.severity) for f in check(gap, shelf).findings if f.check is Check.SLOTS and f.form in KEYS]
    assert named == [(k, "slot PROCEDURE_CITATION", Severity.NOT_OFFERED) for k in KEYS]


def test_each_form_waits_only_for_the_slots_it_uses():
    gap = resolved(leave=("MAX_DAYS_APPLICATION",))
    asked = {k: d.slots for k, d in mine().items()}
    for key in KEYS:
        want = "MAX_DAYS_APPLICATION" in asked[key]
        assert (gap.get(key).status is Status.NOT_OFFERED) is want, key
    assert gap.get("ev-charger").status is Status.READY and gap.get("architectural-application").missing == ("slot MAX_DAYS_APPLICATION",)


def test_the_real_profile_gives_none_of_the_page_specific_slots_so_none_of_these_forms_is_offered_yet():
    from jason.community import community

    real = resolve(community())
    for key in KEYS:
        assert real.get(key).status is Status.NOT_OFFERED
        assert all(m.startswith("slot ") for m in real.get(key).missing)
    assert not {t.key for t in community().forms()} & {FORM_KEYS[k] for k in KEYS}


# -- the clocks -----------------------------------------------------------------------------------------------------------

def test_a_statutory_clock_is_set_by_statute_and_one_the_law_is_silent_on_is_a_labeled_proposal():
    from jason.community.form_library import SetBy

    for key, d in mine().items():
        for clock in d.association_clocks:
            assert clock.set_by in (SetBy.STATUTE, SetBy.PROPOSED_POLICY), (key, clock.name)
            assert clock.section, (key, clock.name)
            if clock.set_by is SetBy.STATUTE:
                assert clock.section.startswith("CIV "), (key, clock.name)
    clocks = {k: {c.name: c for c in d.association_clocks} for k, d in mine().items()}
    assert (clocks["ev-charger"]["decision-station"].number, clocks["ev-charger"]["decision-station"].counted_from) == \
           (60, "the date of receipt of the application")
    assert clocks["ev-charger"]["decision-meter"].set_by.value == "statute" and clocks["ev-charger"]["decision-meter"].number == 60
    assert (clocks["solar"]["decision"].number, clocks["solar"]["decision"].section) == (45, "CIV 714(e)(2)(B)")
    for text in (clocks["ev-charger"]["decision-station"].if_passes, clocks["solar"]["decision"].if_passes):
        assert "deemed approved" in text and "reasonable request for additional information" in text
    # the rebuild's 30, 45, and 60 are the Act's, in every form that carries them, and equal the notice catalog's rows
    from jason.community.notice_catalog import requirement

    for key in ("architectural-application", "protected-use-application"):
        c = clocks[key]
        assert [(c[n].number, c[n].set_by.value) for n in ("rebuild-completeness", "rebuild-review", "rebuild-appeal")] == \
               [(30, "statute"), (45, "statute"), (60, "statute")]
    assert clocks["reconsideration-request"]["rebuild-appeal"].number == 60
    for row, name in (("disaster-rebuild-completeness", "rebuild-completeness"), ("disaster-rebuild-review", "rebuild-review"),
                      ("disaster-rebuild-appeal", "rebuild-appeal")):
        assert requirement(row).timing[0].most == clocks["architectural-application"][name].number
    # what the Act does not state is labeled proposed policy, including the maximum response times of 4765(a)(1)
    ap = clocks["architectural-application"]
    for name in ("acknowledgment", "completeness", "decision", "reconsideration-window", "reconsideration-response"):
        assert ap[name].set_by is SetBy.PROPOSED_POLICY, name
    assert ap["meeting-notice"].set_by is SetBy.STATUTE and ap["meeting-notice"].number == 4


def test_a_community_may_make_a_proposed_clock_stricter_and_cannot_touch_the_statutes():
    from jason.community.form_library import Adjust, Clock

    stricter = Clock("decision", "the day the application is complete", 30, "calendar", "documents", "bylaws#7.2")
    refused = Clock("decision-station", "the date of receipt of the application", 90, "calendar", "documents", "bylaws#7.2")
    both = resolve(Giving(changes=(Adjust("architectural-application", clocks=(stricter,)),
                                   Adjust("ev-charger", clocks=(refused,)))))
    ap = both.get("architectural-application")
    assert ap.status is Status.ADJUSTED and next(c for c in ap.clocks if c.name == "decision").number == 30
    ev = both.get("ev-charger")
    assert ev.refused and "never lengthened" in ev.refused[0].message
    assert next(c for c in ev.clocks if c.name == "decision-station").number == 60


# -- the electric vehicle form --------------------------------------------------------------------------------------------

def test_the_charger_form_carries_the_four_agreements_each_in_its_own_box_in_the_statutes_words():
    d = mine()["ev-charger"]
    asked = {q.field: q for q in d.template.questions}
    sentences = {
        "agree_standards": "comply with the association's architectural standards for the installation of the charging station",
        "agree_licensed_contractor": "engage a licensed contractor to install the charging station",
        "agree_certificate_14_days": "within 14 days of approval, I will give the association a certificate of insurance as required by "
                                     "paragraph (3)",
        "agree_pay_costs": "pay for both the costs associated with the installation of, and the electricity usage associated with, "
                           "the charging station",
        "meter_agree_standards": "comply with the association's architectural standards for the installation of the meter",
        "meter_agree_utility_contractor": "engage the relevant electric utility to install the meter",
    }
    for field, words in sentences.items():
        q = asked[field]
        assert len(q.options) == 1 and words in q.options[0] and q.authority.startswith("Civil Code 4745"), field
    assert [asked[f].authority for f in ("agree_standards", "agree_licensed_contractor", "agree_certificate_14_days",
                                         "agree_pay_costs")] == ["Civil Code 4745(f)(1)(A)", "Civil Code 4745(f)(1)(B)",
                                                                  "Civil Code 4745(f)(1)(C), (f)(3)", "Civil Code 4745(f)(1)(D)"]
    for field in ("ack_damage_costs", "ack_maintenance_restoration", "ack_electricity", "ack_disclose_buyers", "meter_ack_damage",
                  "meter_ack_maintenance", "meter_ack_disclose", "plug_only"):
        assert field in asked
    text = " ".join(d.template.preamble)
    assert "If an application is not denied in writing within 60 days from the date of receipt of the application" in text
    assert "unless that delay is the result of a reasonable request for additional information" in text
    assert "significantly increase the cost of the station or significantly decrease its efficiency or specified performance" in text


def test_the_charger_form_asks_for_no_additional_insured_endorsement_and_no_coverage_amount():
    """CIV 4745(f)(1)(C) changed on 2026-01-01: the certificate is 'as required by paragraph (3)', and the statute names neither."""
    d = mine()["ev-charger"]
    everything = " ".join([d.template.description, d.template.attestation, *d.template.preamble,
                           *(f"{q.title} {q.help} {q.authority} {' '.join(q.options)}" for q in d.template.questions)]).lower()
    for banned in ("additional insured", "endorsement", "coverage amount", "policy limit", "amount of coverage", "in the amount",
                   "per occurrence", "neighbor", "the vehicle"):
        assert banned not in everything, banned
    for q in d.template.questions:
        assert "amount" not in q.title.lower() and "limit" not in q.title.lower(), q.title
    assert any("SB 770" in n and "additional-insured" in n for n in d.notes)
    assert "as required by paragraph (3)" in " ".join(d.template.questions[0].options + tuple(
        o for q in d.template.questions for o in q.options))


# -- the solar form -------------------------------------------------------------------------------------------------------

def test_the_solar_form_carries_the_45_days_the_shared_roof_notice_and_asks_only_what_it_may():
    d = mine()["solar"]
    asked = {q.field: q for q in d.template.questions}
    for field in ("owners_notified", "owners_notified_on", "owners_notified_how", "notice_copy_attached", "agree_liability_policy",
                  "system_kind", "where_installed", "roof_shared", "system_cost"):
        assert field in asked, field
    text = " ".join(d.template.preamble)
    assert "within 45 days from the date of receipt of the application" in text and "deemed approved" in text
    assert "You do not need a vote of the members" in text and "\"shall require\"" in text
    assert "(Civil Code 714(b))" in text and "714.1(b)" in text
    # what the statutes let a community require is asked only where it adopts it: not on the base form, and each is addable
    from jason.community.form_library.ca.solar import ADOPTABLE

    assert not set(ADOPTABLE) & set(asked)
    adds = tuple(Add("solar", q) for q in ADOPTABLE.values())
    done = resolve(Giving(changes=adds)).get("solar")
    assert done.status is Status.ADJUSTED and not done.refused
    assert set(ADOPTABLE) <= {q.field for q in done.template.questions}
    for body in ("neighbor", "vote of the members", "consent"):
        assert body not in " ".join(q.title.lower() for q in d.template.questions)
    assert "coverage amount" not in text.lower() and not any("amount" in q.title.lower() for q in asked.values())


def test_the_architectural_form_accepts_the_two_questions_a_communitys_documents_may_add_and_never_requires_them():
    from jason.community.form_library.ca.architectural import FEE_ACKNOWLEDGMENT, NEIGHBOR_ACKNOWLEDGMENT

    done = resolve(Giving(changes=(Add("architectural-application", NEIGHBOR_ACKNOWLEDGMENT),
                                   Add("architectural-application", FEE_ACKNOWLEDGMENT)))).get("architectural-application")
    assert done.status is Status.ADJUSTED and not done.refused
    assert not NEIGHBOR_ACKNOWLEDGMENT.required and not FEE_ACKNOWLEDGMENT.required and "consent" in NEIGHBOR_ACKNOWLEDGMENT.help
    base = {q.field for q in mine()["architectural-application"].template.questions}
    assert not {"neighbor_ack", "fee_ack"} & base                                    # absent unless the documents ask


def test_the_architectural_form_states_both_maximum_times_the_written_decision_and_the_rebuild_clocks():
    d = mine()["architectural-application"]
    text = " ".join(d.template.preamble)
    for words in ("{MAX_DAYS_APPLICATION}", "{MAX_DAYS_RECONSIDERATION}", "in writing", "describes how to ask the board to reconsider",
                  "open board meeting", "30 calendar days", "45 calendar days", "60 calendar days",
                  "may not subject you to any appeals or additional hearings", "{ANNUAL_NOTICE_LINK}",
                  "Not the only door", "Help."):
        assert words in text, words
    rebuild = {q.field for q in d.template.questions}
    assert {"disaster_rebuild", "disaster_declared_by", "rebuild_old_sqft", "rebuild_new_sqft", "rebuild_height",
            "rebuild_footprint", "rebuild_permit", "accessibility", "plans_attached"} <= rebuild
    assert all(not q.required for q in d.template.questions if q.field.startswith("rebuild_"))      # no rebuild fact starts the clocks
    assert "MAX_DAYS_APPLICATION" in d.slots and "MAX_DAYS_RECONSIDERATION" in d.slots and "PROCEDURE_CITATION" in d.slots


def test_the_reconsideration_form_makes_no_reason_a_condition_and_says_where_and_how_long():
    d = mine()["reconsideration-request"]
    text = " ".join(d.template.preamble)
    asked = {q.field: q for q in d.template.questions}
    assert not asked["what_to_look_at"].required and "do not need to give a reason" in asked["what_to_look_at"].title
    for words in ("entitled to ask the board to reconsider, at an open meeting", "You do not need a new reason to ask",
                  "at least four days before the meeting", "may attend", "{MAX_DAYS_RECONSIDERATION}", "60 calendar days",
                  "written appeal", "does not use up your other rights"):
        assert words in text, words
    assert set(asked["decision_kind"].options) >= {"My rebuild application was found incomplete",
                                                   "My rebuild application was found not compliant"}
    assert len(asked["submitted_by"].options) == 3                                              # no contractor on a request to reconsider


# -- the protected-use form -----------------------------------------------------------------------------------------------

def test_the_protected_use_form_lists_for_each_use_its_section_its_mode_and_what_the_section_leaves():
    from jason.community.form_library.ca.protected_use import USES, Mode

    d = mine()["protected-use-application"]
    asked = {q.field: q for q in d.template.questions}
    assert asked["protected_use"].options == tuple(u.option for u in USES) and len(USES) == 14
    sections = {s for u in USES for s in u.sections}
    assert sections == {"CIV 4705", "CIV 4706", "CIV 4710", "CIV 4715", "CIV 4720", "CIV 4725", "CIV 4735", "CIV 4736", "CIV 4750",
                        "CIV 4751", "CIV 4752", "CIV 4753", "CIV 4766"}
    assert set(d.authority) == sections
    for use in USES:
        for recital in use.recitals:
            assert recital in d.recitals, (use.key, recital)
        if not use.sections:
            continue
        paragraph = next(p for p in d.template.preamble if p.startswith(f"**{use.option}**"))
        assert use.cites() in paragraph and "How the section's words read" in paragraph and "still may do" in paragraph, use.key
        for section in use.sections:
            assert section.removeprefix("CIV ") in paragraph
    modes = {u.key: u.mode for u in USES}
    assert modes["flag"] is Mode.NOTICE and modes["religious-item"] is Mode.NOTICE and modes["sign"] is Mode.NOTICE
    assert modes["pet"] is Mode.NOTICE and modes["pet-other"] is Mode.AGREEMENT and modes["roof"] is Mode.APPLICATION
    assert modes["antenna"] is Mode.APPLICATION and modes["landscape"] is Mode.APPLICATION and modes["drought"] is Mode.NOTICE
    assert modes["agriculture"] is Mode.APPLICATION and modes["adu"] is Mode.APPLICATION and modes["rebuild"] is Mode.APPLICATION
    assert modes["clothesline"] is Mode.NOTICE
    # the limit each section allows is shown beside the use (the table's quoted words)
    flag = next(p for p in d.template.preamble if p.startswith("**A flag of the United States**"))
    assert "\"as required for the protection of the public health or safety\"" in flag and "This is a notice, not a request" in flag
    sign = next(p for p in d.template.preamble if p.startswith("**A sign, poster"))
    assert "nine square feet" in sign and "15 square feet" in sign
    for question in ("yard_exclusive", "display_size", "antenna_size", "physical_change", "pet_other_description"):
        assert question in asked


def test_a_use_that_is_a_right_is_a_notice_not_a_request_and_has_its_own_acknowledgment():
    d = mine()["protected-use-application"]
    text = " ".join(d.template.preamble)
    assert "You do not need our permission" in text and "nothing here asks for approval" in text
    assert "no clock runs" in text and "This is a notice, not a request" in text
    assert d.notes[0].startswith("kind: one form, three modes") and "never a condition of the right" in d.notes[0]
    notice, application = d.acknowledgment.split("For an application or a request for an agreement:")
    assert "none is needed" in notice and "nothing for us to decide" in notice and "no time is running" in notice
    assert "{MAX_DAYS_APPLICATION}" in application and "nothing for us to decide" not in application
    assert "It is not a decision." in application
    assert "A notice has no attestation" in d.template.attestation and "A notice needs no signature" in text
    assert d.member_clock.startswith("A notice opens no clock")
    from jason.community.form_library.ca.protected_use import NOTICE_USES, USES

    assert {u.key for u in NOTICE_USES} == {"flag", "religious-item", "sign", "pet", "drought", "clothesline"}
    assert {u.key for u in USES} - {u.key for u in NOTICE_USES} >= {"roof", "antenna", "pet-other"}


# -- the recitals against the real shelf, where there is one -------------------------------------------------------------

def test_the_statute_words_the_forms_quote_are_on_the_shelf_when_it_is_here():
    from jason.tasks.export_authorities import authority_text

    if not (DATA / "authorities" / "CIV").is_dir():
        pytest.skip("the shelf is not exported here (jason export-authorities)")
    cited = {c.split("(")[0] for d in mine().values() for c in (*d.authority, *d.recitals)} | {"CIV 5300"}
    shelf_text = ""
    for citation in sorted(cited):
        found = authority_text(DATA, citation, fetch=False)
        shelf_text += " " + re.sub(r"\s+", " ", found.get("text") or "")
    if len(shelf_text) < 2000:
        pytest.skip("the sections are not on this shelf")
    shelf_text = shelf_text.replace("’", "'")
    not_statute = {"please reconsider the decision on", "shall require"}
    checked = 0
    for key, d in mine().items():
        pieces = [*d.template.preamble, d.template.attestation]
        for piece in pieces:
            for quote in re.findall(r"\"([^\"]{12,})\"", piece):
                quoted = re.sub(r"\s+", " ", quote).strip().rstrip(".,;").replace("’", "'")
                if quoted.lower() in not_statute or quoted.lower().startswith("please reconsider"):
                    continue
                checked += 1
                assert re.search(re.escape(quoted), shelf_text, re.I), f"{key}: not in the statutes on the shelf: {quote!r}"
    assert checked > 20


# -- the response kinds and their clocks --------------------------------------------------------------------------------

def test_the_new_response_kinds_classify_a_made_up_request_and_carry_the_right_clock_source():
    from jason.community.responses import ClockSource, ResponseKind, classify, rules_for

    kinds, rules = rules_for(None)
    cases = {
        "Please reconsider the decision on 123 Main St. A. Owner": ResponseKind.RECONSIDERATION,
        "I ask the board to reconsider the denial of my solar application": ResponseKind.RECONSIDERATION,
        "I want to install an EV-dedicated time-of-use meter at 123 Main St": ResponseKind.EV_METER,
        "I plan to fly a flag of the United States from a pole at 123 Main St": ResponseKind.PROTECTED_USE,
        "May I put a satellite dish on my balcony railing?": ResponseKind.PROTECTED_USE,
        "I want to rebuild my home after the wildfire destroyed it": ResponseKind.DISASTER_REBUILD,
        "Application under 4766 for a substantially similar reconstruction": ResponseKind.DISASTER_REBUILD,
        # the kinds that were there still classify as they did
        "I want to install a charging station in my carport": ResponseKind.EV_CHARGER,
        "I want to install solar panels on my roof": ResponseKind.SOLAR,
    }
    for text, kind in cases.items():
        assert classify("General Request", text, kinds)[0] is kind, text
    ev = rules[ResponseKind.EV_METER]
    assert (ev.source, ev.notice, ev.authority) == (ClockSource.STATUTE, "ev-meter-decision", "CIV 4745.1")
    rebuild = rules[ResponseKind.DISASTER_REBUILD]
    assert (rebuild.source, rebuild.notice, rebuild.authority) == (ClockSource.STATUTE, "disaster-rebuild-completeness", "CIV 4766")
    recon = rules[ResponseKind.RECONSIDERATION]
    assert (recon.source, recon.days, recon.business_days) == (ClockSource.POLICY, 45, False) and "proposed policy" in recon.authority
    assert recon.first_step == "Put it on the next open meeting that can be noticed."
    use = rules[ResponseKind.PROTECTED_USE]
    assert use.source is ClockSource.POLICY and "notice opens no clock" in use.note.lower().replace("a notice", "notice")
    from jason.community.notice_catalog import requirement

    for rule in (ev, rebuild):
        assert requirement(rule.notice).statute == rule.authority


def test_the_reworded_first_steps_count_from_receipt_and_say_nothing_of_a_complete_application():
    from jason.community.responses import ResponseKind, rules_for

    _, rules = rules_for(None)
    for kind, days, section in ((ResponseKind.SOLAR, "45", "714(e)(2)(B)"), (ResponseKind.EV_CHARGER, "60", "4745(e)"),
                                (ResponseKind.EV_METER, "60", "4745.1(e)")):
        step = rules[kind].first_step
        assert f"within {days} days from the date of receipt of the application" in step, kind
        assert "receipt" in step and "complete" not in step.lower(), kind
        assert "unless that delay is the result of a reasonable request for additional information" in step
        assert section in step
    assert rules[ResponseKind.DISASTER_REBUILD].first_step.startswith("Tell the applicant in writing, within 30 calendar days")


# -- the notice catalog rows --------------------------------------------------------------------------------------------

def test_the_reconsideration_answer_row_counts_from_the_request_within_the_procedures_maximum():
    from jason.community.notice_catalog import requirement
    from jason.community.notices import Anchor, Recipients

    row = requirement("architectural-reconsideration")
    assert (row.statute, row.recipients, row.verified) == ("CIV 4765", Recipients.APPLICANT, True)
    clock = row.timing[0]
    assert clock.anchor is Anchor.RECONSIDERATION_REQUESTED and clock.after and clock.most is None
    assert clock.words == "within the maximum time the procedure states"
    assert re.search(row.words, "The procedure shall state the maximum time for response to an application or a request for "
                                "reconsideration by the board.")
    assert "CIV 4920" in row.also


def test_the_rebuild_review_row_is_45_calendar_days_from_the_day_the_application_is_complete():
    from jason.community.notice_catalog import requirement
    from jason.community.notices import Anchor, Recipients, Unit

    row = requirement("disaster-rebuild-review")
    assert (row.statute, row.recipients) == ("CIV 4766", Recipients.APPLICANT)
    clock = row.timing[0]
    assert (clock.anchor, clock.after, clock.most, clock.unit) == (Anchor.APPLICATION_COMPLETE, True, 45, Unit.CALENDAR_DAYS)
    assert clock.window(date(2026, 10, 12)) == (date(2026, 10, 12), date(2026, 11, 26))
    assert re.search(row.words, "the body shall conduct any review and do either of the following within 45 calendar days:")


def test_the_rebuild_appeal_row_is_60_calendar_days_from_the_written_appeal():
    from jason.community.notice_catalog import requirement
    from jason.community.notices import Anchor, Recipients, Unit

    row = requirement("disaster-rebuild-appeal")
    assert (row.statute, row.recipients) == ("CIV 4766", Recipients.APPLICANT)
    clock = row.timing[0]
    assert (clock.anchor, clock.after, clock.most, clock.unit) == (Anchor.APPEAL_RECEIVED, True, 60, Unit.CALENDAR_DAYS)
    assert clock.window(date(2026, 10, 12)) == (date(2026, 10, 12), date(2026, 12, 11))
    assert re.search(row.words, "no later than 60 calendar days after receipt of the applicant’s written appeal")


# -- the command and the boundary -----------------------------------------------------------------------------------------

def test_jason_form_library_check_passes_with_these_forms_in_the_library(tmp_path, monkeypatch, capsys):
    from jason.commands import form_library as module

    root = stand_in_shelf(tmp_path / "data", [r for d in definitions("CA") for r in d.recitals]
                          + [r for d in definitions("US") for r in d.recitals])
    monkeypatch.setattr(module, "_data_dir", lambda args: root)

    def run(*argv):
        parser = argparse.ArgumentParser()
        module.register(parser.add_subparsers(), lambda p: None, lambda a: None)
        code = module.cmd_form_library(parser.parse_args(["form-library", *argv]))
        return code, capsys.readouterr().out

    code, out = run("--check", "--json")
    body = json.loads(out)
    assert code == 0 and body["ok"] is True
    mine_found = [f for f in body["findings"] if f["form"] in KEYS and f["severity"] == "fail"]
    assert mine_found == []
    for key in KEYS:
        assert body["statuses"][key] in ("not offered", "ready")
    code, out = run("--show", "ev-charger")
    assert code == 0 and "ev-charger: " in out and "CIV 4745(f)(1)(C)" in out
    code, out = run("--check")
    assert code == 0
