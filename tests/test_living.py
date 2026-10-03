"""Living documents: an amendment's operations read from its own words and marks, applied in order to the base."""

from datetime import date

from jason.community.living import (Annotation, AnnotationKind, Correction, CorrectionKind, Effect, FindingKind,
                                    Instrument, Mark, Placement, Standing, Verb, changes_meaning, consolidate, drift,
                                    operations_from_doc, operations_from_text, place, read_instruction)
from jason.community.outlines import outline_from_text

BASE = """ARTICLE 2 USE
2.4 Pets. Owners may keep pets subject to this Section.
(a) Number. Not more than two (2) pets may be kept in a Unit at any time.
(b) Leashes. Pets shall be leashed in the Common Area.
(c) Rental Agreement. Any lease shall provide (i) that it is subject to the Governing Documents, (ii) that the tenants shall comply with them, and (iii) that the term is at least six (6) months.
2.5 Signs. No sign may be displayed except as the law allows.
"""


def _base():
    return outline_from_text(BASE, key="decl", title="Declaration", kind="declaration")


def _run(text, bold=False, strike=False):
    style = {}
    if bold:
        style["bold"] = True
    if strike:
        style["strikethrough"] = True
    return {"textRun": {"content": text, "textStyle": style}}


def _para(*runs):
    return {"paragraph": {"paragraphStyle": {"namedStyleType": "NORMAL_TEXT"}, "elements": list(runs)}}


def _amendment_doc():
    return {"documentId": "A", "tabs": [{"documentTab": {"body": {"content": [
        _para(_run("WHEREAS, the Declaration should be amended (stricken text is not operative).\n")),
        _para(_run("NOW, THEREFORE, Section 2.4 of the Declaration is hereby amended as follows:\n")),
        _para(_run("Article 2, Section 2.4 (“Pets”), subsection (a) (“Number”) is hereby amended and "
                   "restated as follows ("), _run("stricken", strike=True), _run(" out wording will be removed, and "),
              _run("bolded", bold=True), _run(" wording will be added):\n")),
        _para(_run("\t\tNot more than "), _run("two (2)", strike=True), _run(" "), _run("three (3)", bold=True),
              _run(" pets may be kept in a Unit at any time.\n")),
        _para(_run("Article 2, Section 2.4, subsection (c), subpart (iii) is hereby amended and restated as follows:\n")),
        _para(_run("that the term is at least "), _run("six (6) months", strike=True), _run(" thirty (30) days", bold=True),
              _run(".\n")),
        _para(_run("Article 2, Section 2.4 (“Pets”), subsection (b) is hereby removed as follows:\n")),
        _para(_run("Pets shall be leashed in the Common Area.", strike=True), _run(" "),
              _run("Intentionally omitted.", bold=True), _run("\n", bold=True, strike=True)),
        _para(_run("IN WITNESS WHEREOF, the Board adopts this amendment.\n")),
    ]}}}]}


def test_an_instruction_names_its_section_verb_and_caption():
    assert read_instruction("Article 2, Section 2.4 (“Pets”), subsection (c) (“Rental Agreement”), "
                            "subpart (iii) is hereby amended and restated as follows:") == ("2.4(c)(iii)", Verb.RESTATE, "")
    assert read_instruction("Section 2.4 of the Declaration is amended to add the following subsection:")[1] is Verb.ADD
    assert read_instruction("Section 2.4(b) is hereby removed.")[:2] == ("2.4(b)", Verb.REMOVE)
    assert read_instruction("The Owners shall comply with Section 2.4.") is None


def test_the_doc_runs_carry_strike_and_bold_into_before_and_after():
    ops = operations_from_doc(_amendment_doc())
    assert [(o.section, o.verb) for o in ops] == [("2.4(a)", Verb.RESTATE), ("2.4(c)(iii)", Verb.RESTATE),
                                                  ("2.4(b)", Verb.REMOVE)]
    first = ops[0]
    assert first.before == "Not more than two (2) pets may be kept in a Unit at any time."
    assert first.after == "Not more than three (3) pets may be kept in a Unit at any time."
    assert first.redline() == "Not more than ~~two (2)~~ **three (3)** pets may be kept in a Unit at any time."
    assert [r.mark for r in first.runs] == [Mark.PLAIN, Mark.STRUCK, Mark.PLAIN, Mark.ADDED, Mark.PLAIN]
    # The legend's own marked words ("stricken", "bolded") are the instruction's, not an operation's.
    assert ops[1].after == "that the term is at least thirty (30) days."
    assert ops[2].after == "Intentionally omitted."


def test_a_plain_text_copy_that_lost_the_marks_is_not_applied():
    text = ("NOW, THEREFORE, the Declaration is amended.\n\nSection 2.4, subsection (a) is hereby amended and restated "
            "as follows (stricken out wording will be removed, and bolded wording will be added):\n\nNot more than two "
            "(2) three (3) pets may be kept in a Unit at any time.\n\nIN WITNESS WHEREOF\n")
    ops = operations_from_text(text)
    assert ops[0].marks_lost
    current = consolidate(_base(), [Instrument("amend-1", "decl", Standing.RECORDED, ops, recorded=date(2024, 1, 5))])
    assert [f.kind for f in current.findings] == [FindingKind.MARKS_LOST]
    assert "two (2) pets" in current.provision("2.4(a)").body


def test_only_an_instrument_in_effect_applies_and_each_section_keeps_its_provenance():
    ops = operations_from_doc(_amendment_doc())
    draft = Instrument("amend-2", "decl", Standing.DRAFT, ops)
    adopted = Instrument("amend-1", "decl", Standing.ADOPTED, ops, adopted=date(2024, 1, 5))
    current = consolidate(_base(), [draft, adopted])
    # A declaration changes only on recording.
    assert {f.instrument for f in current.findings if f.kind is FindingKind.NOT_IN_EFFECT} == {"amend-1", "amend-2"}
    assert "two (2)" in current.provision("2.4(a)").body

    recorded = Instrument("amend-1", "decl", Standing.RECORDED, ops, "First Amendment", recorded=date(2024, 2, 1),
                          number="2024000123")
    current = consolidate(_base(), [draft, recorded])
    a = current.provision("2.4(a)")
    assert a.body == "Not more than three (3) pets may be kept in a Unit at any time."
    assert (a.set_by, a.dated, a.caption) == ("amend-1", date(2024, 2, 1), "Number.")
    assert a.history == ["base", "amend-1: restate"]
    # (iii) ran inline in (c); it is split out to be restated.
    assert current.provision("2.4(c)(iii)").body == "that the term is at least thirty (30) days."
    assert current.provision("2.4(c)(i)").set_by == "decl"
    assert current.provision("2.4(b)").body == "Intentionally omitted."
    assert current.provision("2.5").set_by == "decl"
    assert current.through.key == "amend-1" and [i.key for i in current.pending] == ["amend-2"]
    assert "As amended through the First Amendment, recorded 2024-02-01 as No. 2024000123." in current.markdown()
    # The bylaws change on adoption.
    assert adopted.in_effect(Effect.ON_ADOPTION) and not adopted.in_effect(Effect.ON_RECORDING)
    assert not recorded.in_effect(Effect.ON_RECORDING, as_of=date(2024, 1, 31))


def test_before_words_that_differ_from_the_base_are_applied_and_reported():
    ops = operations_from_doc(_amendment_doc())
    base = outline_from_text(BASE.replace("may be kept in a Unit at any time", "may be kept in any Unit at any time"),
                             key="decl", kind="declaration")
    current = consolidate(base, [Instrument("amend-1", "decl", Standing.RECORDED, ops, recorded=date(2024, 2, 1))])
    differs = [f for f in current.findings if f.kind is FindingKind.BEFORE_DIFFERS]
    assert [f.section for f in differs] == ["2.4(a)"]
    assert "[any]" in differs[0].detail and "[a]" in differs[0].detail
    assert current.provision("2.4(a)").body.startswith("Not more than three (3)")


def test_an_added_subsection_lands_after_its_parent_with_its_own_subsections():
    text = ("NOW, THEREFORE, the Declaration is amended as follows:\n\n1. Amendment.\n\nSection 2.4 of the Declaration "
            "is amended to add the following subsection:\n\n(0) Lenders. To the extent any provision conflicts with a "
            "lender's program, it shall not apply to any Unit that is:\n\n(i) encumbered by such a loan, or\n\n(ii) owned "
            "by the lender.\n\n2. Miscellaneous. The rest of the Declaration remains in effect.\n\nN. WITNESS WHEREOF\n")
    ops = operations_from_text(text)
    assert [(o.section, o.verb, o.caption) for o in ops] == [("2.4(o)", Verb.ADD, "Lenders.")]
    current = consolidate(_base(), [Instrument("amend-1", "decl", Standing.RECORDED, ops, recorded=date(2020, 1, 2))])
    numbers = [p.number for p in current.provisions if p.number]
    assert numbers.index("2.4(o)") == numbers.index("2.4(c)") + 1
    assert numbers[numbers.index("2.4(o)") + 1: numbers.index("2.5")] == ["2.4(o)(i)", "2.4(o)(ii)"]
    assert current.provision("2.4(o)(ii)").body == "owned by the lender."
    assert "Miscellaneous" not in current.text_of("2.4(o)")


def test_a_caption_belongs_to_the_label_it_follows_with_any_quotes():
    # Straight quotes, curly quotes, and the mix OCR makes of them (an opening read as a single quote, a closing
    # parenthesis the instrument left out): each caption is its own part's, and the target's is the last label's.
    for left, right in (('"', '"'), ("“", "”"), ("‘", "”"), ("“", "’"), ("'", "'")):
        named = (f"Article 2, Section 2.4 ({left}Pets{right}), subsection (c) ({left}Rental Agreement{right}) is hereby "
                 "amended and restated as follows:")
        assert read_instruction(named) == ("2.4(c)", Verb.RESTATE, "Rental Agreement"), named
        deeper = (f"Article 2, Section 2.4 ({left}Pets{right}, subsection (c) ({left}Rental Agreement{right}), subpart "
                  "(iii) is hereby amended and restated as follows:")
        assert read_instruction(deeper) == ("2.4(c)(iii)", Verb.RESTATE, ""), deeper
    assert read_instruction("Section 2.4(c), entitled “Rental Agreement,” is hereby amended to read as follows:") == (
        "2.4(c)", Verb.RESTATE, "Rental Agreement")
    assert read_instruction("Section 2.4 (“Pets”), subsection (b) is hereby removed.") == ("2.4(b)", Verb.REMOVE, "")
    assert read_instruction("Section 2.4(d) (‘Owner’s Indemnity”) is hereby amended to read as follows:")[2] == \
        "Owner’s Indemnity"


def test_an_instructions_lead_in_never_joins_the_restated_words():
    """The lead-in names the section and a subsection with captions (OCR's mixed quotes); the words start after "as
    follows:", even in the instruction's own paragraph, and end before the signature block when OCR lost "IN WITNESS
    WHEREOF"."""
    text = ("NOW, THEREFORE, Section 2.4 of the Declaration is hereby amended as follows:\n\n"
            "1. Article 2, Section 2.4 (“Pets’, subsection (c) (‘Rental Agreement”), subpart (iii) is hereby amended "
            "and restated as follows: that the term is at least thirty (30) days.\n\n"
            "2. Article 2, Section 2.4 (“Pets”), subsection (a) (‘Number”) is hereby amended and restated as follows:\n\n"
            "Not more than three (3) pets may be kept in a Unit at any time.\n\n"
            "Exhibit B shall list the pets kept.\n\n"
            "DATED: January 5, 2024 EXAMPLE HOMES ASSOCIATION\n\nPresident\n\nEXHIBIT A\n\nLegal Description\n")
    ops = operations_from_text(text)
    assert [(o.section, o.caption, o.after) for o in ops] == [
        ("2.4(c)(iii)", "", "that the term is at least thirty (30) days."),
        ("2.4(a)", "Number", "Not more than three (3) pets may be kept in a Unit at any time.\n"
                             "Exhibit B shall list the pets kept.")]
    assert ops[0].instruction.endswith("restated as follows:")
    current = consolidate(_base(), [Instrument("amend-1", "decl", Standing.RECORDED, ops, recorded=date(2024, 2, 1))])
    iii = current.provision("2.4(c)(iii)")
    assert (iii.caption, iii.body) == ("", "that the term is at least thirty (30) days.")
    whole = current.text_of("2.4(c)")
    assert "Rental Agreement." in whole and "subsection" not in whole and "Pets" not in whole
    assert current.provision("2.4(a)").caption == "Number."            # the base's own caption stays


def test_a_hand_amended_copy_is_drift_and_its_bracketed_notes_are_not_text():
    ops = operations_from_doc(_amendment_doc())
    current = consolidate(_base(), [Instrument("amend-1", "decl", Standing.RECORDED, ops, recorded=date(2024, 2, 1))])
    copy = outline_from_text(BASE.replace("two (2) pets", "two (3) pets").replace(
        "No sign may", "[ Editor: see the sign rules. ] No sign may"), key="decl", kind="declaration")
    found = drift(current, copy, label="the working copy")
    by_section = {f.section: f for f in found if f.kind is FindingKind.DRIFT}
    assert '"more than [three] (3) pets" -> "more than [two] (3) pets"' in by_section["2.4(a)"].detail
    assert "2.5" not in by_section
    assert [(f.section, f.detail) for f in found if f.kind is FindingKind.EDITORIAL] == [("2.5", "Editor: see the sign rules.")]


def test_a_correction_fixes_a_reading_but_never_meaning():
    assert changes_meaning("tenn", "term") == ""
    assert changes_meaning("six (6)", "six (8)") == "a number changes"
    assert "operative word" in changes_meaning("may keep", "shall keep")
    base = outline_from_text(BASE.replace("leashed in the", "leashcd in the"), key="decl", kind="declaration")
    corrections = [Correction("2.4(b)", "leashcd", "leashed", CorrectionKind.OCR, source="the recorded copy, page 3"),
                   Correction("2.5", "No sign", "A sign", CorrectionKind.TYPO),
                   Correction("2.4(a)", "pets  may", "pets may", CorrectionKind.SPACING)]
    current = consolidate(base, [], corrections=corrections)
    assert current.provision("2.4(b)").body == "Pets shall be leashed in the Common Area."
    assert current.provision("2.4(b)").history == ["base", "correction (ocr)"]
    kinds = {(f.kind, f.section) for f in current.findings}
    assert (FindingKind.CORRECTION_REFUSED, "2.5") in kinds and (FindingKind.CORRECTION_STALE, "2.4(a)") in kinds


def test_annotations_follow_their_words_or_are_orphaned():
    ops = operations_from_doc(_amendment_doc())
    current = consolidate(_base(), [Instrument("amend-1", "decl", Standing.RECORDED, ops, recorded=date(2024, 2, 1))])
    notes = [Annotation("2.4(a)", "pets may be kept", AnnotationKind.QUESTION, "Does a service animal count?"),
             Annotation("2.4(a)", "except as the law allows", AnnotationKind.INTERPRETATION, "Which law?"),
             Annotation("2.4(b)", "leashed in the Common Area", AnnotationKind.CONTEXT, "The dog park too."),
             Annotation("2.5", "", AnnotationKind.POLICY_CANDIDATE, "Adopt a sign rule.")]
    placed = [(p.placement, p.section) for p in place(current, notes)]
    assert placed == [(Placement.ANCHORED, "2.4(a)"), (Placement.MOVED, "2.5"), (Placement.ORPHANED, ""),
                      (Placement.SECTION, "2.5")]


def test_outline_from_text_survives_a_roman_subsection_before_any_letter():
    text = "1.3 Terms. These words.\n(iv) A roman item first.\n(d) A letter after it.\n"
    outline = outline_from_text(text, key="x")
    assert [s.number for s in outline.sections][:2] == ["1.3", "1.3(iv)"]
