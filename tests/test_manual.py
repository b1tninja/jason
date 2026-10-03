"""The owner's manual taken apart (jason.community.manual), on a made-up manual: every word in one piece, each piece's
kind by its row and checked by the evidence, the concordance, and the renderings beside the source."""

from __future__ import annotations

from datetime import date

import pytest

from jason.community.manual import (AdoptionAction, AdoptionEvent, BookSource, CopyHit, CopyState, Excerpt, Locator as L,
                                    ManualError, ManualRow as Row, ManualSpec, Norm, Piece, SectionKind as K, Target as T,
                                    asks, check, classify, compare, concordance, places, render, resolve_old, segments)
from jason.community.outlines import DocumentOutline, Section

PARTS = [
    ("EXAMPLE COMMONS OWNERS ASSOCIATION\nOWNER'S MANUAL\n", None),
    ("WHAT IS AN ASSOCIATION?\nThe association maintains the common area. Each owner shall keep the patio clean.\n",
     ("", "WHAT IS AN ASSOCIATION?", 2, "")),
    ("WHO DO I CALL?\nCall the manager at 555-0100.\n", ("", "WHO DO I CALL?", 2, "")),
    ("PREAMBLE\nA-1. These rules are adopted by the board.\n", ("4(A)", "PREAMBLE", 2, "A.")),
    ("R-1. PETS\nPets shall be leashed in the common area.\n", ("R-1", "R-1. PETS", 1, "")),
    ("No pet shall be left alone on a deck. It is recommended that owners carry bags.\n",
     ("R-1(a)", "No pet shall be left alone on a deck.", 2, "a.")),
    ("R-2. NOISE\nNo Unit shall be altered so as to increase sound transmission.\n", ("R-2", "R-2. NOISE", 1, "")),
    ("R-3. EXAMPLES\nAn example of a permitted sign follows.\n", ("R-3", "R-3. EXAMPLES", 1, "")),
    ("ENFORCEMENT\nThe board shall give notice before a hearing.\n", ("R-3(C)", "ENFORCEMENT", 2, "C.")),
    ("First violation $25.\nTHE NOTICE\nYou may pay under protest (Section 1 of the Code\n",
     ("R-3(C)(1)", "First violation $25.", 3, "1.")),
]


def outline() -> DocumentOutline:
    text, sections, at = "", [], 0
    for words, sec in PARTS:
        if sec is not None:
            number, title, depth, label = sec
            sections.append(Section(number, title, depth, at, label=label))
        text += words
        at += len(words)
    out = DocumentOutline(key="example-manual", title="Example Manual", revision="rev1", text=text, sections=sections)
    for k, s in enumerate(out.sections):
        s.end = next((t.start for t in out.sections[k + 1:] if t.depth <= s.depth), len(text))
    return out


def spec(**kw) -> ManualSpec:
    rows = (
        Row(L(title="(front)"), K.GUIDANCE, T("manual", slot="front")),
        Row(L(title="WHAT IS AN"), K.GUIDANCE, T("manual", slot="welcome")),
        Row(L(title="WHO DO I CALL"), K.GUIDANCE, T("manual", slot="contacts")),
        Row(L("4(A)"), K.RULE, T("rules", number="A")),
        Row(L("R-1(a)"), K.RULE, T("rules"),
            pieces=(Piece("It is recommended", K.GUIDANCE, T("manual", slot="rules")),)),
        Row(L("R-2"), K.COPY, T("rules"), copies=("decl#4.7",)),
        Row(L("R-3"), K.RULE, T("rules"), question="Is R-3 a rule or an illustration?"),
        Row(L("R-3(C)"), K.POLICY, T("disc", number="C")),
        Row(L("R-3(C)(1)"), K.POLICY, T("disc", renumber=("R-3(C)", "C(b)")),
            pieces=(Piece("THE NOTICE", K.COPY, T("coll", number="notice"), copies=("CODE 1",)),)),
        Row(L("R-1"), K.RULE, T("rules"), through=L("R-3")),
    )
    return ManualSpec("example-manual", kw.pop("rows", rows), **kw)


NORMS = [Norm(PARTS[0][0].__len__() + 60, "duty", "owner", "Each owner shall keep the patio clean.")]


def hits(o: DocumentOutline) -> list[CopyHit]:
    at = o.text.index("No Unit shall be altered")
    return [CopyHit(at, at + 62, "decl#4.7", "verbatim", "unamended", 1.0, 1.0)]


def law(citation, segment):
    return "THE NOTICE You may pay under protest (Section 1 of the Code)" if citation == "CODE 1" else ""


def test_every_word_is_in_one_piece_in_order():
    o = outline()
    segs = segments(o, spec())
    assert "".join(o.text[s.start:s.end] for s in segs) == o.text
    assert [s.start for s in segs] == sorted(s.start for s in segs)


def test_a_section_no_row_matches_is_named():
    with pytest.raises(ManualError, match="no row matches"):
        segments(outline(), spec(rows=(Row(L(title="(front)"), K.GUIDANCE, T("manual")),)))


def test_a_piece_whose_words_are_missing_is_named():
    rows = spec().rows[:4] + (Row(L("R-1(a)"), K.RULE, T("rules"), pieces=(Piece("Not there", K.GUIDANCE, T("manual")),)),) \
        + spec().rows[5:]
    with pytest.raises(ManualError, match="not in the section"):
        segments(outline(), spec(rows=rows))


def test_kinds_by_row_with_evidence_and_questions():
    o = outline()
    result = classify(o, spec(), NORMS, hits(o), law=law)
    kinds = {c.old: c.kind for c in result.sections}
    assert kinds["(front)"] is K.GUIDANCE
    assert kinds["R-1"] is K.RULE
    assert kinds["R-1(a)"] is K.MIXED                     # a rule with a sentence of guidance
    assert kinds["R-2"] is K.COPY
    assert kinds["R-3(C)"] is K.POLICY
    assert kinds["R-3(C)(1)"] is K.MIXED                  # a policy item and a statute's notice
    # The row asks about R-3; the evidence asks about guidance that states an owner's duty and cites nothing.
    assert kinds["R-3"] is K.UNCLEAR and kinds["WHAT IS AN ASSOCIATION?"] is K.UNCLEAR
    r2 = next(c for c in result.sections if c.old == "R-2").segments[0]
    assert r2.state is CopyState.VERBATIM                 # from the scan
    notice = next(s for s in result.segments if s.copies == ("CODE 1",))
    assert notice.state is CopyState.VERBATIM             # the law's words on disk, a parenthesis apart
    questions = asks(result)
    assert {a.subject for a in questions} == {"example-manual#R-3", "example-manual#WHAT IS AN ASSOCIATION?"}
    assert next(a for a in questions if a.subject.endswith("R-3")).suggestion == "rule"


def test_an_answer_is_the_kind():
    o = outline()
    result = classify(o, spec(), NORMS, hits(o), answers={"R-3": "guidance", "WHAT IS AN ASSOCIATION?": "guidance"})
    kinds = {c.old: c.kind for c in result.sections}
    assert kinds["R-3"] is K.GUIDANCE and kinds["WHAT IS AN ASSOCIATION?"] is K.GUIDANCE
    assert not asks(result)


def test_a_rule_row_over_a_verbatim_copy_is_a_question():
    o = outline()
    rows = tuple(Row(L("R-2"), K.RULE, T("rules")) if r.at == L("R-2") else r for r in spec().rows)
    result = classify(o, spec(rows=rows), NORMS, hits(o))
    assert next(c for c in result.sections if c.old == "R-2").kind is K.UNCLEAR


def test_the_concordance_keeps_printed_numbers_and_resolves_the_readers():
    o = outline()
    rows = concordance(classify(o, spec(), NORMS, hits(o), law=law), o.text)
    assert resolve_old(rows, "R-1(a)") == "rules#R-1(a)"
    assert resolve_old(rows, "example-manual#R-3(C)(1)") == "disc#C(b)(1)"
    assert resolve_old(rows, "R-3(C) (courtesy letter)") == "disc#C"
    assert resolve_old(rows, "4(A)") == "rules#A"
    assert resolve_old(rows, "R-9") == ""
    first = next(r for r in rows if r.old == "R-1(a)" and r.piece == 1)
    assert first.new.startswith("manual#") and not first.official
    assert next(r for r in rows if r.old == "R-1").official


def test_numbers_read_twice_are_told_apart():
    o = outline()
    o.sections.append(Section("R-1", "R-1 again", 1, len(o.text)))
    o.text += "R-1 again\n"
    found = [p.locator for p in places(o) if p.number == "R-1"]
    assert found == [L("R-1"), L("R-1", nth=2)] and found[1].text() == "R-1 (2nd)"


class Source:
    def __init__(self, o):
        self.o = o

    def words(self, s):
        if s.copies == ("CODE 1",):
            return law("CODE 1", s), "CODE 1 on disk"
        return self.o.text[s.start:s.end], ""

    def law(self, citation, quoted):
        return "The law's words.", citation

    def excerpt(self, ref):
        return f"> quoted {ref}"

    def history(self):
        return [AdoptionEvent(date(2020, 1, 2), AdoptionAction.ADOPTED, ("R-1",), "minutes of 2020-01-02")]


MANUAL = "{PART:front}\n\n{PART:welcome}\n\n{PART:contacts}\n\n{EXCERPTS}\n\n{INCLUDE:rules}\n\n{INCLUDE:disc}\n\n" \
         "{INCLUDE:coll optional}\n\n{INCLUDE:arch optional}\n"


def test_the_generated_manual_is_the_manual_apart_from_layout_and_labeled_changes():
    o = outline()
    result = classify(o, spec(excerpts=(Excerpt("decl#2.5"),)), NORMS, hits(o), law=law,
                      answers={"R-3": "rule", "WHAT IS AN ASSOCIATION?": "guidance"})
    md, chunks = render(MANUAL, result, spec(excerpts=(Excerpt("decl#2.5"),)), Source(o), o.text)
    found = check(chunks, o.text)
    assert found.covered and not found.out_of_order and not found.unlabeled
    assert [d.label for d in found.labeled] == ["CODE 1 on disk"]
    assert "> quoted decl#2.5" in md and "**a.** No pet shall be left alone" in md
    assert "### R-1. PETS" in md and "## A. PREAMBLE" in md


def test_the_official_rules_hold_the_rule_text_and_name_what_was_left():
    o = outline()
    result = classify(o, spec(), NORMS, hits(o), law=law, answers={"R-3": "rule", "WHAT IS AN ASSOCIATION?": "guidance"})
    md, chunks = render("# {RULES_TITLE}\n\n{ADOPTION_HISTORY}\n\n{INCLUDE:rules official}\n", result,
                        spec(rules_title="Example Rules"), Source(o), o.text)
    assert md.startswith("# Example Rules")
    assert "Pets shall be leashed" in md and "No pet shall be left alone on a deck." in md
    assert "\n\nIt is recommended" not in md                         # not printed as rule text ...
    assert "_[Guidance left in the Owner's Manual: “It is recommended" in md        # ... but named where it was
    assert "Restates decl#4.7 (verbatim)" in md                      # a copy the board adopted stays, named
    assert "The board shall give notice" not in md and "published as its own document (disc)" in md
    assert "| 2020-01-02 | adopted | R-1 |" in md


RULES = "# {RULES_TITLE}\n\n{ADOPTION_HISTORY}\n\n{INCLUDE:rules official}\n"
WORKING_R1 = "R-1. PETS Pets shall be leashed in the common area."


def _passages():
    from jason.community.manual import Passage

    return [
        # known: an adoption on record covers the earlier words
        Passage("rules#R-1", "R-1", "reworded", "2098-01-01", "2098-06-01", "R-1. PETS Pets shall be leashed everywhere.",
                WORKING_R1, "2097-09-01, rc-2097", segments=("R-1",), book_title="Example Rules"),
        # not known: no adopted version on record
        Passage("rules#R-2", "R-2", "reworded", "2098-01-01", "2098-06-01", "R-2. NOISE No Unit shall be altered.",
                "R-2. NOISE No Unit shall be altered so as to increase sound transmission.", "", segments=("R-2",),
                book_title="Example Rules"),
        # removed, with its adopted words known
        Passage("rules#R-1(c)", "R-1(c)", "removed", "2098-01-01", "2098-06-01",
                "Residents may opt out of the visitor log.", "", "2097-09-01, rc-2097", follows="R-1(a)",
                book_title="Example Rules"),
        # a policy bound in the manual: listed in the history, not in the rules
        Passage("disc#C(b)", "R-3(C)(1)", "added", "2098-01-01", "2098-06-01", "", "First violation $25.", "",
                book_title="Discipline Policy"),
    ]


def _rule_lines(md: str) -> list[str]:
    """The lines printed as rule text: not a note, not the history's table."""
    return [ln for ln in md.splitlines() if ln.strip() and not ln.startswith(("_[", "_", "|", "#"))]


def test_the_official_rules_print_the_last_adopted_words_with_jasons_note():
    o = outline()
    result = classify(o, spec(), NORMS, hits(o), law=law, answers={"R-3": "rule", "WHAT IS AN ASSOCIATION?": "guidance"})
    md, chunks = render(RULES, result, spec(rules_title="Example Rules"), Source(o), o.text, passages=_passages())
    rules = "\n".join(_rule_lines(md))
    # (b) with adopted words on record: those words are the rule; the working words only in jason's note
    assert "R-1. PETS Pets shall be leashed everywhere." in rules and "in the common area" not in rules
    assert ("_[jason's note, not rule text: Changed between 2098-01-01 and 2098-06-01; no adoption found. The words "
            "printed are the last adopted (adopted 2097-09-01, rc-2097). The working text reads: “" + WORKING_R1 + "”]_"
            ) in md
    # no adopted version on record: no rule words, and the note says so without guessing
    assert "sound transmission" not in rules and "No Unit shall be altered" not in rules
    assert "No adopted version of this passage is on record, so its adopted words are not known and none are " \
           "printed as a rule. The version of 2098-01-01 reads: “R-2. NOISE No Unit shall be altered.”" in md
    # a removed passage keeps its adopted words, after the piece it followed
    assert "Residents may opt out of the visitor log." in rules
    assert "Removed (the manual's R-1(c)) between 2098-01-01 and 2098-06-01; no adoption found." in md
    assert md.index("No pet shall be left alone") < md.index("Residents may opt out")
    # the history lists every (b) passage, the policies' too
    assert "| Example Rules R-1 | reworded, 2098-01-01 to 2098-06-01 | adopted 2097-09-01, rc-2097 |" in md
    assert "| Discipline Policy C(b) | added, 2098-01-01 to 2098-06-01 | not known: no adopted version on record |" in md
    assert all(c.kind != "adopted" or c.start < 0 for c in chunks)          # the adopted words are not the Doc's span


def test_current_renders_the_working_words_with_the_same_notes():
    o = outline()
    result = classify(o, spec(), NORMS, hits(o), law=law, answers={"R-3": "rule", "WHAT IS AN ASSOCIATION?": "guidance"})
    md, _ = render(RULES, result, spec(rules_title="Example Rules"), Source(o), o.text, passages=_passages(),
                   current=True)
    rules = "\n".join(_rule_lines(md))
    assert "Pets shall be leashed in the common area." in rules and "leashed everywhere" not in rules
    assert "The last adopted words (adopted 2097-09-01, rc-2097) read: “R-1. PETS Pets shall be leashed everywhere.”" in md
    assert "No Unit shall be altered so as to increase sound transmission." in rules
    assert "so its adopted words are not known. The version of 2098-01-01 reads:" in md
    assert "Residents may opt out" not in rules and "The working text leaves them out." in md
    assert "the working words are printed and jason's note recites the last adopted words" in md


def test_pending_insertions_are_taken_out_together():
    from types import SimpleNamespace as S

    from jason.tasks.manual import strip_inserts

    text = "Pets such as birds, cats, or dogs may be kept maintained in a unit."
    inserts = [S(words="cats, or dogs", where="Pets such as birds,"), S(words="kept", where="birds, cats, or dogs may be")]
    out, removed = strip_inserts(text, inserts)
    assert out == "Pets such as birds, may be maintained in a unit." and sorted(removed) == ["cats, or dogs", "kept"]


def test_a_book_the_profile_does_not_fill_fails_unless_optional():
    o = outline()
    result = classify(o, spec(), NORMS, hits(o), law=law)
    with pytest.raises(ManualError, match="maps nothing to 'arch'"):
        render("{INCLUDE:arch}", result, spec(), Source(o), o.text)
    assert render("{INCLUDE:arch optional}", result, spec(), Source(o), o.text)[0].strip() == ""


def test_a_book_read_from_its_own_document_is_labeled():
    o = outline()
    s = spec(sources=(BookSource("rules", "example-rules"),))
    assert s.source_of("rules") == "example-rules" and s.source_of("disc") == ""


def test_compare_reads_verbatim_edited_and_paraphrase():
    src = "No Unit shall be altered in any manner which would increase sound transmission."
    assert compare(src.replace("transmission.", "transmission"), src)[0] is CopyState.VERBATIM
    assert compare("No Unit shall be altered in any way which would increase sound.", src)[0] is CopyState.EDITED
    assert compare("Keep it quiet for your neighbors.", src)[0] is CopyState.PARAPHRASE


def test_an_adoption_event_round_trips_for_a_detector():
    e = AdoptionEvent(date(2022, 8, 30), AdoptionAction.IN_FORCE, ("R-1",), "a dated copy", source="detector",
                      version="copy.pdf", digest="abc")
    assert AdoptionEvent.from_dict(e.to_dict()) == e


def test_the_profile_keeps_its_manual_and_the_base_has_none():
    from jason.community import community
    from jason.community.base import Community

    assert Community.owners_manual(community()) is None                 # the base's default
    found = community().owners_manual()
    assert isinstance(found, ManualSpec) and found.rows


def test_the_base_templates_exist_and_name_their_parts():
    from jason.tasks.manual import template

    manual = template("owners-manual.md")
    for token in ("{PART:front}", "{INCLUDE:rules}", "{EXCERPTS}", "{INCLUDE:disc optional}"):
        assert token in manual
    assert "{INCLUDE:rules official}" in template("rules.md")


def test_statute_helpers_take_the_quoted_passage():
    from jason.tasks.manual import quoted, unwrap

    text = "(a) The notice shall read:\n\n“NOTICE\nline one\nwraps here.”\n"
    assert quoted(text) == "NOTICE\nline one\nwraps here."
    assert unwrap("a\nb\n\nc") == "a b\n\nc"
