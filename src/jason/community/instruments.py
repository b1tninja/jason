"""The kinds of instrument that change a governing document, and what each does, how it takes effect, who adopts it,
what notice it needs, and how jason represents it.

An amendment, a restatement, a revocation, a rescission, a repeal, a supersession, an annexation, a correction: the
words get used loosely, but each changes the text differently and takes effect differently. ``INSTRUMENTS`` holds one
``InstrumentType`` row per kind, read from the Act on disk (4225, 4230, 4235, 4260-4276, 4340-4370, 4741(f)); a
declaration's own amendment and restatement clauses add to them in the profile. ``notices`` names the catalog's
requirement keys (``jason.community.notice_catalog``) the kind needs; ``verb`` and ``effect`` are how the living-document
model (``jason.community.living``) represents it today, and ``missing`` what that model does not yet hold.

Not legal advice: where a row's ``caveat`` is set, counsel reads it first.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from jason.community.living import Effect, Verb


class TextEffect(Enum):
    SECTIONS = "sets, adds, or removes named sections; the rest stands"
    WHOLE = "replaces the whole text; the prior instrument and its amendments are superseded"
    ENDS = "ends the instrument from a date forward; what it did before stands"
    VOIDS = "undoes the instrument as though it had not been made (typically before it took hold)"
    ADDS_PROPERTY = "brings more property under the declaration, and may add provisions for that property"
    CITATIONS = "changes no substance: corrects cross-references or deletes what the law already voids"


class Adopter(Enum):
    MEMBERS = "the members, by the vote the declaration (or 4270(b), a majority of all members) requires"
    BOARD = "the board alone"
    BOARD_REQUIRED = "the board, which the statute requires to act, without member approval"
    BOARD_AND_MEMBERS = "the board, with a majority of a quorum of the members (4070)"
    DECLARANT = "the declarant, under the declaration's reserved rights"
    COURT = "the members' vote, confirmed by a court order"


@dataclass(frozen=True)
class InstrumentType:
    key: str
    title: str
    text_effect: TextEffect
    adopter: Adopter
    takes_effect: str                      # when, in the statute's terms
    authority: str
    notices: tuple[str, ...] = ()          # notice_catalog keys
    verb: Verb | None = None               # the living model's verb for its operations, if any
    effect: Effect | None = None           # the living model's rule for when it applies
    represent: str = ""                    # how jason holds it today
    missing: str = ""                      # what the living model lacks for it
    caveat: str = ""


INSTRUMENTS: tuple[InstrumentType, ...] = (
    InstrumentType(
        "amendment", "Amendment of the declaration", TextEffect.SECTIONS, Adopter.MEMBERS,
        "after approval by the required percentage (and anyone else the declaration requires), certification by the "
        "designated officer (else the president), and recording in each county (4270(a))",
        "CIV 4270, 4260, 4265", ("ballots",), Verb.RESTATE, Effect.ON_RECORDING,
        "Amendment mixin and living Instrument operations (RESTATE, ADD, REMOVE), standing RECORDED",
        "Nothing for the text. The standing does not say who certified it, or which ballot approved it; the "
        "election's notices (ballots with the amendment's text, 5115(g)) are not linked to the instrument.",
        caveat="A declaration with no amendment clause may be amended at any time (4260); one with a fixed term and "
               "no extension clause is extended by 4265."),
    InstrumentType(
        "amended-and-restated", "Amended and restated declaration", TextEffect.WHOLE, Adopter.MEMBERS,
        "as an amendment: approved, certified, and recorded (4270(a)); the restated text then replaces the prior "
        "declaration and its amendments", "CIV 4270", ("ballots",), None, Effect.ON_RECORDING,
        "Supersession rows (governing.Supersession) pin the whole instrument it replaced; the living model would "
        "treat it as a new base",
        "An instrument-level 'replaces the base' (a new base outline with a map from old to new section numbers), so "
        "provenance and annotations carry across the renumbering; today a restatement read as section operations "
        "would be many RESTATEs on the old numbering."),
    InstrumentType(
        "restatement-only", "Restatement of an amended declaration (no new substance)", TextEffect.CITATIONS,
        Adopter.BOARD, "on the conditions the declaration sets (often execution by officers and recording)",
        "the declaration's own restatement clause", (), None, Effect.ON_RECORDING,
        "A profile row: the declaration's clause that lets the board consolidate approved amendments",
        "A check that the restated text equals the consolidated text (drift against the recorded restatement), and "
        "the same base-replacement as an amended and restated declaration.",
        caveat="The Act on disk has no general board restatement power; it comes from the declaration, or from 4225, "
               "4235(b), and 4741(f) for their purposes."),
    InstrumentType(
        "unlawful-covenant-deletion", "Deletion of a discriminatory covenant", TextEffect.CITATIONS,
        Adopter.BOARD_REQUIRED,
        "the board amends and restates without the covenant and with no other change, and records the restated "
        "declaration (4225(b), (c))", "CIV 4225", (), Verb.REMOVE, Effect.ON_RECORDING,
        "A REMOVE operation on the covenant's words", "A marker that the instrument is a statutory deletion (so "
        "drift and 'no other change' are checked), and the 30-day clock after a written request under 4225(d)."),
    InstrumentType(
        "rental-restriction-amendment", "Board amendment of an unlawful rental restriction", TextEffect.SECTIONS,
        Adopter.BOARD_REQUIRED,
        "on the board's approval at a board meeting after 28 days' general notice; it restates the document without "
        "the restriction and with no other change (4741(f))", "CIV 4741", ("rental-amendment-4741",), Verb.RESTATE,
        Effect.ON_RECORDING, "A living Instrument with its RESTATE operation, standing RECORDED once recorded",
        "Effect is chosen by document kind, so a declaration's 4741(f) amendment waits for recording; whether it "
        "takes effect on the board's approval is not settled by the text.",
        caveat="4741(f) speaks of approval at a board meeting and does not say recording; the declaration's own "
               "clause and 4270(a) point to recording. For counsel."),
    InstrumentType(
        "developer-provision-deletion", "Deletion of the developer's construction and marketing provisions",
        TextEffect.SECTIONS, Adopter.BOARD_AND_MEMBERS,
        "after 30 days' individual notice and an open meeting, with a majority of a quorum of the members (4230)",
        "CIV 4230", ("developer-amendment-4230",), Verb.REMOVE, Effect.ON_RECORDING,
        "REMOVE operations", "A record of the member approval it still needs (not a board-only act)."),
    InstrumentType(
        "citation-correction", "Correction of cross-references to the recodified Act", TextEffect.CITATIONS,
        Adopter.BOARD,
        "on the board's resolution; a declaration may be restated in corrected form and recorded with the "
        "resolution (4235)", "CIV 4235", (), Verb.RESTATE, Effect.ON_ADOPTION,
        "living.Correction rows refuse a change of meaning; a 4235 resolution is an instrument, not an editor's fix",
        "An instrument kind whose effect is ON_ADOPTION even for the declaration (effect_of picks by document kind), "
        "and a check that it changes only citations.",
        caveat="Whether a corrected declaration's citations are effective before the restated copy is recorded is "
               "not settled by the text."),
    InstrumentType(
        "court-reduced-vote", "Amendment approved under a court order reducing the vote", TextEffect.SECTIONS,
        Adopter.COURT, "when the court order and the amendment are recorded in every county (4275(f))", "CIV 4275",
        ("amendment-petition-hearing", "amendment-recorded-4275"), Verb.RESTATE, Effect.ON_RECORDING,
        "As an amendment", "The court order as a second recorded instrument the amendment depends on."),
    InstrumentType(
        "revocation", "Revocation of the declaration or of an instrument", TextEffect.ENDS, Adopter.MEMBERS,
        "as the declaration provides (most declarations allow it 'amended or revoked' on the same vote, recorded)",
        "the declaration; CIV 4270", ("ballots",), None, Effect.ON_RECORDING,
        "Not represented", "A standing for an instrument that applied until a date and no longer does (REVOKED), so "
        "as_of reads the text in force on a past day."),
    InstrumentType(
        "rescission", "Rescission of a recorded instrument", TextEffect.VOIDS, Adopter.DECLARANT,
        "as the instrument or the later one says; an annexation the declarant rescinded before any unit of the phase "
        "was conveyed", "the instrument's own terms", (), None, Effect.ON_RECORDING,
        "Supersession rows in the profile (governing.Supersession), with the recital as the source",
        "A standing that never applies, for any as_of (RESCINDED), distinct from a revocation's end date; living does "
        "not read the Supersession rows.",
        caveat="Whether a rescission is effective from the start or from its recording turns on the instrument's words "
               "and title law; for counsel when a past day matters."),
    InstrumentType(
        "supersession", "Supersession by a later instrument", TextEffect.WHOLE, Adopter.MEMBERS,
        "when the later instrument takes effect", "the later instrument's own words", (), None, None,
        "governing.Supersession and apply_supersessions place the superseded instrument in the chain",
        "Living reads instruments of one document; a later document that supersedes a whole policy or rule needs an "
        "instrument-level link (SUPERSEDED, with what replaced it)."),
    InstrumentType(
        "annexation", "Declaration of annexation", TextEffect.ADDS_PROPERTY, Adopter.DECLARANT,
        "on recording, for the phase's property, under the declaration's annexation clause", "the declaration",
        (), Verb.ADD, Effect.ON_RECORDING,
        "DocumentKind.ANNEXATION; effect_of treats it as part of the declaration",
        "A scope: provisions an annexation adds apply to its phase's units only; living has no per-provision scope. "
        "Annexing other property usually needs a member vote under the declaration's clause."),
    InstrumentType(
        "annexation-amendment", "Amendment (or amended and restated) declaration of annexation", TextEffect.WHOLE,
        Adopter.DECLARANT, "on recording; the recital says what it replaces", "the declaration; the annexation",
        (), None, Effect.ON_RECORDING, "Supersession rows (role 'annexation')", "As for a supersession."),
    InstrumentType(
        "rule-change", "Adoption, amendment, or repeal of an operating rule", TextEffect.SECTIONS, Adopter.BOARD,
        "on the board's decision at a board meeting after 28 days' general notice (4360(a), (b)); reversible by a "
        "member vote requested within 30 days of the notice of the change (4365)", "CIV 4340-4370",
        ("rule-change-proposed", "rule-change-adopted", "rule-change-reversal-results"), Verb.RESTATE,
        Effect.ON_ADOPTION, "RuleChange and SectionChange rows (rule_changes.py); a living Instrument once adopted",
        "A standing for a change members reversed (REVERSED: not readopted for a year, 4365(f)); the notice "
        "evidence linked to the instrument; 'repeal' of a whole rule document as an instrument-level REMOVE."),
    InstrumentType(
        "emergency-rule", "Emergency rule change", TextEffect.SECTIONS, Adopter.BOARD,
        "immediately, for 120 days unless shorter; not readopted as an emergency rule (4360(d))", "CIV 4360",
        ("rule-change-adopted",), Verb.RESTATE, Effect.ON_ADOPTION, "Not represented",
        "An expiry date on the instrument, so the text in force after 120 days drops it (EXPIRED)."),
    InstrumentType(
        "bylaw-amendment", "Amendment of the bylaws", TextEffect.SECTIONS, Adopter.MEMBERS,
        "on approval as the bylaws provide (or the date the amendment states); not recorded", "the bylaws; CIV 4205",
        ("ballots",), Verb.RESTATE, Effect.ON_ADOPTION, "A living Instrument with standing ADOPTED",
        "Nothing for the text; the ballot's evidence is not linked."),
)


def instrument(key: str) -> InstrumentType:
    for row in INSTRUMENTS:
        if row.key == key:
            return row
    raise KeyError(key)


__all__ = ["Adopter", "INSTRUMENTS", "InstrumentType", "TextEffect", "instrument"]
