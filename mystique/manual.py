"""The Owner's Manual and Rules taken apart (``jason.community.manual``): which of its sections are the operating rules,
which copy the CC&Rs or a statute, which are policies bound in, and which are the guide's own words.

The manual (outline key ``owners-manual``) prints a guide (questions and answers, then contacts and who to call), then
the rules as Parts A (Preamble) and B (Community Regulations, B-1 to B-18), then Part C (Enforcement: the due process
and fine schedule), the Assessment Collection Policy's cover with the notice Civil Code 5730 requires, and the Home
Improvement Request Application. The rows below are read in order and the first match wins (``ManualRow``); a ``Piece``
splits a section where its words change kind. Each row's ``reason`` is the reading; ``question`` marks a kind a person
decides (``jason intake``). Why each policy is its own book: ``CHOICES``; the profile's notes: ``mystique/docs/manual.md``.

The outline reads three things the Doc does not print: Part A's "A." glyph under the guide's "4. Towing" (so "4(A)"),
Part C's "C." under B-18 (so "B-18(C)"), and the Demarcation list's "i." to "iv." under B-12 (so a second "B-12(i)").
The targets give the numbers the Doc prints (A, A-2(a), C(b)(1), Demarcation(i)); the old ones stay in the concordance.
"""

from __future__ import annotations

from datetime import date

from jason.community.manual import (AdoptionAction, AdoptionEvent, BookChoice, BookSource, CopyState, Locator as L,
                                    ManualRow as Row, ManualSpec, Piece, SectionKind as K, Target as T)


def guide(slot: str) -> T:
    return T("manual", slot=slot)


NOTE = T("manual", slot="rules")          # guidance inside a rule: left in the manual, shown beside the rule
RULES = T("rules")
PARKING = T("rules.parking")
DISC_ITEMS = T("disc", renumber=("B-18(C)", "C(b)"))

ROWS: tuple[Row, ...] = (
    # --- The guide -----------------------------------------------------------------------------------------------
    Row(L(title="(front)"), K.GUIDANCE, guide("front"), reason="the cover and the table of contents' heading"),
    Row(L(title="WHAT IS A HOMEOWNER"), K.GUIDANCE, guide("welcome"), through=L(title="IS TOUCH UP PAINT"),
        reason="questions and answers explaining the association, its documents, the board, and assessments",
        pieces=(
            Piece("You have the right to inspect the association records", K.COPY, guide("welcome"),
                  copies=("CIV 5660",),
                  note="the owner's rights 5660(a), (c)-(f) list for a pre-lien notice, edited into the second person; "
                       "CC&Rs 6.12(a) states them in the pre-2014 words (Corporations Code 8333)"),
            Piece("IMPORTANT NOTICE: IF YOUR SEPARATE INTEREST", K.COPY, guide("welcome"), copies=("CIV 5660(a)",),
                  note="the statement 5660(a) prints in capitals"),
            Piece("HOA Emergencies", K.GUIDANCE, guide("contacts"),
                  note="the contacts table: emergencies, the portal, payments, the board, the utilities"),
        )),
    Row(L("1"), K.GUIDANCE, guide("contacts"), through=L("4"),
        reason="who to call, numbered 1-2 and again 1-4 by the Doc (\"2\" is numbered twice)"),

    # --- Part A. Preamble ----------------------------------------------------------------------------------------
    Row(L("4(A)"), K.RULE, T("rules", number="A"),
        reason="Part A's caption; the outline hangs the Doc's \"A.\" from the guide's \"4. Towing\"",
        pieces=(
            Piece("A-1. The authority", K.COPY, T("rules", number="A-1"), copies=("ccrs#2.5",),
                  state=CopyState.PARAPHRASE,
                  note="restates the board's rule-making power under CC&Rs 2.5, and recites that each owner received "
                       "the Declaration"),
            Piece("A-2. The Manager", K.RULE, T("rules", number="A-2"),
                  note="a standing direction to the manager on enforcement: a regulation that applies generally to "
                       "the management and operation of the development (4340(a))"),
        )),
    Row(L("4(A)(a)"), K.RULE, T("rules", number="A-2(a)")),
    Row(L("4(A)(b)"), K.RULE, T("rules", number="A-2(b)")),
    Row(L("4(A)(c)"), K.RULE, T("rules", number="A-2(c)"),
        pieces=(Piece("A-3. The Rules as contained herein", K.RULE, T("rules", number="A-3"),
                      note="the rules' scope, their place under the Declaration, and their purpose"),)),
    Row(L("4(A)(B)"), K.RULE, T("rules", number="B"), reason="Part B's caption (the Doc's \"B.\")"),

    # --- Part B. Community Regulations: the sections that copy or explain ------------------------------------------
    Row(L("B-6"), K.COPY, RULES, copies=("ccrs#4.5",), reason="the first sentence of CC&Rs 4.5"),
    Row(L("B-7(a)"), K.RULE, RULES,
        pieces=(Piece("It is recommended that all Owners", K.GUIDANCE, NOTE,
                      note="a recommendation and a warning: no regulation"),)),
    Row(L("B-7(c)"), K.COPY, RULES, under=True, copies=("CFC 308.1.4",), state=CopyState.UNVERIFIED,
        reason="the Fire Code's open-flame rule and its exceptions, as the board added it in 2022 (\"management is "
               "required to enforce the California Fire Code\"); the code is not on disk, and the rule cites the 2007 "
               "edition"),
    Row(L("B-7(d)"), K.RULE, RULES,
        question="B-7(d) says electric grills are not open-flame devices and which buildings are \"one and two-family "
                 "dwellings\" or sprinklered under the Fire Code's exceptions. Is that the board's determination of "
                 "where grills may be used (an operating rule, Civil Code 4340(a)), or an explanation of the code "
                 "(guidance kept in the manual)?"),
    Row(L("B-8"), K.COPY, RULES, copies=("ccrs#4.7", "ccrs#4.18"), reason="CC&Rs 4.7 (and 4.18), word for word"),
    Row(L("B-12(c)"), K.COPY, PARKING, copies=("ccrs#4.11(a)(ii)",)),
    Row(L("B-12(d)"), K.COPY, PARKING, copies=("ccrs#4.11(a)(i)",)),
    Row(L("B-12(h)"), K.COPY, PARKING, copies=("ccrs#4.12(c)",)),
    Row(L("B-12(j)"), K.COPY, PARKING, copies=("ccrs#4.11(b)",)),
    Row(L("B-12(k)"), K.COPY, PARKING, copies=("ccrs#4.11(b)",)),
    Row(L(title="Example Permits"), K.GUIDANCE, NOTE, reason="an illustration (the permits' pictures)"),
    Row(L(title="Demarcation"), K.RULE, T("rules.parking", number="Demarcation"),
        reason="a heading inside B-12 over the signage list the Doc numbers i. to iv."),
    Row(L("B-12(i)", nth=2), K.RULE, T("rules.parking", number="Demarcation(i)")),
    Row(L("B-12(ii)"), K.COPY, T("rules.parking", number="Demarcation(ii)"), copies=("VEH 22658(a)",),
        state=CopyState.UNVERIFIED, reason="the Vehicle Code's tow-away sign, restated; the code is not on disk"),
    Row(L("B-12(iii)"), K.RULE, T("rules.parking", number="Demarcation(iii)")),
    Row(L("B-12(iv)"), K.RULE, T("rules.parking", number="Demarcation(iv)")),
    Row(L(title="Example Signage"), K.GUIDANCE, NOTE,
        reason="an illustration, how to ask for a permit, and the Doc's insert for the permit application"),
    Row(L("B-12"), K.RULE, PARKING, under=True, reason="B-12 is the parking rules Doc word for word"),
    Row(L("B-16"), K.COPY, RULES, copies=("ccrs#4.10(c)",),
        pieces=(Piece("Trash containers shall be stored", K.RULE, RULES),)),
    Row(L("B-18(b)"), K.RULE, RULES, under=True,
        question="B-18(b) asks an applicant to \"send as much information as you can\" and lists it. Is the list part "
                 "of the architectural review procedure the governing documents must include (Civil Code 4765(a)(1); "
                 "an operating rule), or guidance on applying?",
        pieces=(Piece("Please submit all applications via", K.GUIDANCE, NOTE,
                      note="how to submit (the owner portal) and a reminder of B-18(c)"),)),
    Row(L("B-18(c)"), K.RULE, RULES,
        pieces=(Piece("No Unit shall be altered in any manner", K.COPY, RULES, copies=("ccrs#4.18", "ccrs#4.7")),)),
    Row(L("4(A)(B)"), K.RULE, RULES, through=L("B-18(e)"),
        reason="Part B, the Community Regulations the board adopted and amends by rule change (4360)"),

    # --- Part C. Enforcement: the discipline policy and fine schedule ----------------------------------------------
    Row(L("B-18(C)"), K.POLICY, T("disc", number="C"),
        reason="Part C (the Doc's \"C.\"): the due process and the schedule of monetary penalties (5850); it "
               "reprints the Enforcement Policy Doc with a different schedule"),
    Row(L(title="a) Fine Schedule"), K.POLICY, T("disc", number="C(a)")),
    Row(L(title="b) Due Process Requirements"), K.POLICY, T("disc", number="C(b)")),
    Row(L("B-18(C)(1)"), K.POLICY, DISC_ITEMS, through=L("B-18(C)(7)(d)"),
        pieces=(
            Piece("MYSTIQUE COMMUNITY ASSOCIATION\nASSESSMENT COLLECTION POLICY", K.POLICY, T("coll", number="cover"),
                  note="the Assessment Collection Policy's cover and the Doc's insert for its text"),
            Piece("Civil Code section 5730 requires", K.GUIDANCE, T("coll", number="notice"),
                  note="the sentence that introduces the statutory notice"),
            Piece("NOTICE ASSESSMENTS AND FORECLOSURE", K.COPY, T("coll", number="notice"), copies=("CIV 5730(a)",),
                  note="the notice 5730(a) prints"),
            Piece("[ Insert  ]\nNAME:", K.POLICY, T("arch", number="form"),
                  note="the Home Improvement Request Application"),
        )),

    # --- The architectural application -------------------------------------------------------------------------
    Row(L("B-18(C)(1)", nth=2), K.POLICY, T("arch", renumber=("B-18(C)", "conditions")), through=L("B-18(C)(3)", nth=2),
        question="The application's General Conditions of Approval (comply with the CC&Rs and rules; get the "
                 "permits; no materials or debris on parking areas or streets) apply to every approval. Were they "
                 "adopted as operating rules (Civil Code 4340(a)), or are they the form's terms within the "
                 "architectural procedure (4765)?"),
    Row(L(title="Mystique Community Association Board of Directors"), K.POLICY, T("arch", number="form"),
        reason="the application's block for the board's decision"),
)


CHOICES: tuple[BookChoice, ...] = (
    BookChoice("rules", "Rules and Regulations", "the official document: Parts A and B",
               "Parts A and B are the operating rules the board adopted and changes by notice (4360); they keep "
               "their numbers, so every citation of B-1(d) or B-18(e) still names the same words."),
    BookChoice("rules.parking", "Parking Rules", "a part of rules, read from the parking rules Doc",
               "The parking rules Doc is B-12 word for word. Every operating rule shares one definition (4340(a)), one "
               "procedure (4360), and one rank (4205(d)), so it is a part of the rules, not a book of its own; kept as a "
               "part so the Doc stays the one source and B-12's numbers stay B-12's."),
    BookChoice("disc", "Enforcement Policy and Schedule of Monetary Penalties", "its own book",
               "Part C is the discipline policy and schedule 5850(a) has the board adopt and distribute in the annual "
               "policy statement (5310(a)(8)), with supplements delivered individually (5850(b)): it travels apart "
               "from the rules. Which text is the adopted one (the manual's Part C or the Enforcement Policy Doc) is "
               "the board's question; until it answers, the manual's Part C is the text."),
    BookChoice("coll", "Assessment Collection Policy", "its own book",
               "The collection policy and the 5730 notice go out in the annual policy statement (5310(a)(6), (7)); "
               "the manual carries only its cover and the notice."),
    BookChoice("arch", "Architectural Review Procedure", "its own book for the application; B-18 stays in rules",
               "B-18 is numbered and cited as a rule (B-18(e) is a conflict row), and 4765(a)(1) asks only that the "
               "procedure be in the governing documents, which the rules are. The application form and its general "
               "conditions are the procedure's form: they go to arch, which 4765(c) has noticed each year."),
)

SOURCES: tuple[BookSource, ...] = (
    BookSource("rules.parking", "parking-rules", "the parking rules Doc, B-12 word for word"),
)

# Each recorded step, read from the minutes and the library (no person is named here). ``record`` is the rule-change
# record in rule_changes.py that tracks the change's stages. A detector's dated versions are added from
# data/manual/history.json (jason.tasks.manual.history_path).
ADOPTIONS: tuple[AdoptionEvent, ...] = (
    AdoptionEvent(date(2022, 5, 11), AdoptionAction.TABLED, ("B-7", "B-12"),
                  "minutes of 2022-05-11: the revised B-7 and parking rule drafts in the manual were tabled"),
    AdoptionEvent(date(2022, 8, 30), AdoptionAction.ADOPTED, ("B-7", "B-12", "C(a)"),
                  "minutes of 2022-08-30: after the notice and members' comments, B-7 and B-12 adopted, and the fine "
                  "schedule adopted as amended ($15 a month parking permit)", record="parking-fines-2022"),
    AdoptionEvent(None, AdoptionAction.DELIVERED, ("B-7", "B-12", "C(a)"),
                  "the Notice of Adoption (adopted Aug 30, 2022), listed in the 2022-09-19 meeting's documents and "
                  "printed in the 2023 budget package", record="parking-fines-2022", source="library"),
    AdoptionEvent(date(2022, 12, 27), AdoptionAction.NO_ACTION, ("B-5",),
                  "minutes of 2022-12-27: the board chose not to designate another place for sale signs (B-5(b))"),
    AdoptionEvent(date(2023, 4, 18), AdoptionAction.ADOPTED, ("B-1",),
                  "minutes of 2023-04-18: the proposed changes to the registration regulations adopted (annual resident "
                  "registration; sanctions for failing to keep it current)", record="owners-manual-2023"),
    AdoptionEvent(date(2023, 4, 18), AdoptionAction.ADOPTED, ("C(a)",),
                  "minutes of 2023-04-18: C. Enforcement, a) Fine Schedule adopted", record="owners-manual-2023"),
    AdoptionEvent(date(2023, 4, 18), AdoptionAction.ADOPTED, ("coll",),
                  "minutes of 2023-04-18: the Assessment Collection Policy adopted (the manual prints it effective "
                  "April 18, 2023)", record="owners-manual-2023"),
    AdoptionEvent(date(2023, 4, 18), AdoptionAction.TABLED, ("B-5", "B-14", "B-15", "B-16"),
                  "minutes of 2023-04-18: the proposed changes to these rules were tabled", record="owners-manual-2023"),
    AdoptionEvent(date(2024, 4, 16), AdoptionAction.LISTED, ("C(a)", "B-12"),
                  "agenda of 2024-04-16: \"Revise Owner's Manual and Rules: Fee Schedule, Parking Rules\"; the minutes "
                  "record no action"),
)

MANUAL = ManualSpec(
    document="owners-manual",
    rows=ROWS,
    sources=SOURCES,
    choices=CHOICES,
    adoptions=ADOPTIONS,
    rules_title="Rules and Regulations",
    manual_title="Owner's Manual",
    book_titles={"rules": "Rules and Regulations", "disc": "Part C. Enforcement (the discipline policy and fine schedule)",
                 "coll": "Assessment Collection Policy", "arch": "Home Improvement Request Application",
                 "manual": "Owner's Manual"},
)

__all__ = ["ADOPTIONS", "CHOICES", "MANUAL", "ROWS", "SOURCES"]
