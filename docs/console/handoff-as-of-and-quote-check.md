# Handoff: reading the law as of a day, and checking a quotation before it is given

For the design pass on the components that show **which words of a statute governed on a day** and **whether each quotation in an answer is jason's stored words of that version**. The data exists today, with no loader and no component:

- **The version in force on a day:** `jason.community.law_text` (`in_force`, `version_on` and its `VersionOn` record, `every_version`, `place_of`, `quoted`), read from the shelf (`data/authorities`) and its history (`data/authorities/history`, with the ledger `versions.json`). `jason.api.law_in_force` and the governance MCP tool `law_in_force` serve it ([mcp.md](../mcp.md)); `jason cite CIV-9901@2092-05-01` and `jason readings --recite CIV-9901 --as-of DAY` recite through it.
- **A former section number:** `jason.community.law_citations.resolve` (`Resolution`: current, former, then current, unresolved, not held) over the successor table `jason law-history --export` keeps (`jason.community.succession`). `jason collection KEY --as-of DAY` prints it ([collections.md](../collections.md#citations-of-the-law)).
- **The quote check:** `jason.community.quote_check.check` behind `jason verify-quotes FILE --as-of DAY` (`jason.commands.verify_quotes`) and the MCP tool `verify_quotes` (`jason.mcp.county`), each quotation `FOUND`, `ALTERED`, `MISATTRIBUTED`, `OTHER VERSION`, or `NOT FOUND`.
- **A term's value on a day:** `jason.community.statutory_terms` (`Term.prior`, each a `Prior` with its value, the day the current value took effect, and the act; `in_force(name, day)`).
- **The history shelf:** `jason law-history` (`--export`, `--versions`, `--add-version`), which a person runs.

The rules are settled in [law-readings.md](../law-readings.md) (the words, the version store, the range, which words `recite` gives for a day, and the quote check) and in AGENTS.md's "Recite the rule; label the reading": recite the version that governs, with the caveat that jason's consolidated text is not an official restatement; a renumbered citation is not a conflict, it is read as its successor; only stored words.

The neighbours this page links to and does not repeat: [screens/governing-documents.md](screens/governing-documents.md) (the reader, its "As of" control, and its state "A version not in force": this page builds on them), [documents.md](documents.md#statutes-and-the-associations-documents) (a statute as a document: its caveat and the version in force), [components.md](components.md#still-proposed) (built `Recitation` and `ReadingLabel`; proposed `CiteBox` and `DiffTable`), [handoff-confirmations-queue.md](handoff-confirmations-queue.md) (`ProvisionRecital` and `StaleWordsBanner`: words that changed since a reading read them, a different question from a day), and [handoff-applicability-questions.md](handoff-applicability-questions.md) (`#/applies` already takes `?as_of=`). `handoff-citations.md` (being written; not yet in this tree) settles what a document cites and whether the shelf holds it: `StandingPill` and its seven words, `CitationChip`, and `Successor`. The components here compose with those and never repeat them. Two neighbours in this wave use the rows below: `handoff-collection-workspace.md` (a collection's citations of the law) and `handoff-context-pack-workbench.md` (the as-of review's law sources).

These components pair with what the console already has: `Recitation` and `ReadingLabel`, `Pill`, `Caveats`, `Command`, `Confirm`, `DataTable`, `Card`, `Tabs`, `Timeline`, `EmptyState`, and `RemoteView`, with `CiteBox` and `DiffTable` once built. Build new parts only where the table says so.

## The idea in one line

Every recitation is of one day's words: the screen shows the day, names the version the disk places in force on it and how that is known, or picks nothing and says what would bring the words; and a quotation leaves jason as stored words of that version, marked with its verdict, unless a named person gives it as written, on the record.

## The components

| Component | Where it renders | Data | States to design |
| --- | --- | --- | --- |
| `AsOfControl` | the header of each screen that recites or checks: `#/documents`, `#/documents/check`, `#/applies`, a collection's page | the loader's echoed `asOf` and `today` (the association's day) | today (the default); another day; a day typed in an expression (`CIV 9901@2092-05-01` sets the control); a day not yet come; a day the tool refuses ("as_of is a day as YYYY-MM-DD", the tool's words); back to today |
| `AsOfBanner` | under `ScreenHeader` when the day is not today; one line in the shell's header beside "Records as of" | `asOf`, `today` | hidden on today; shown ("The law on this screen is read as of Mar 1, 2092. Deadlines, records, and approvals stay today's."), with **Back to today** |
| `VersionLine` | in `Recitation`'s caption, after the citation | one `VersionOn` (`decided`, `basis`, `from`, `printedBy`, `until`, `untilBy`, `act`, `source`, `digest`, `addedByHand`, `decidingWords`) | an earlier version (prior); the words on the shelf now (current); one of two versions under one number (own words, the deciding sentences quoted); added by hand (who, when); one version and today (the short form); not shown (below) |
| `NotShownNotice` | in place of the words when `found` is false | `reason`, `caveats`, the commands | not on the shelf; a day before any version held; a day in a gap between held versions; the version store never read for the section; read before the shelf changed; two held ranges both hold the day; not a citation |
| `VersionTimeline` | `#/documents`, the Versions band of a statute; opened from `VersionLine`; inside an `OTHER VERSION` row | `versions[]` (`Held`), `gaps[]`, `acts[]`, `asOf` | one version; earlier and current; two printed under one number; the day in a gap; the day before every version; a hand-added version; an end not recorded; the same words under two credits; its table twin, always |
| `SubdivisionWords` | under the `Recitation` when the citation names a subdivision | `subdivisions`, `subdivisionWords`, the split caveat | split ("(b), split from the section as jason splits it; the section is the source"), with the whole section a disclosure away; no paragraph opens with it (the whole section is given, and the line says so); two versions not decided (split from each) |
| `TermOnDay` | beside a computed clock or a figure that rests on a statutory term; in `VersionLine`'s band | a term's `name`, its value on the day, `prior[]` | the current value; a prior value on the day, with the day it ended and the act; a term with no prior value |
| `FormerSectionRow` | a collection's citations of the law; the as-of review's law sources; `CitationChip`'s card for a renumbered section; a quote check's citation of a former number | one `Resolved` | current; former, both recited; former with its own words not held; former with two successors; then current (words held, or not held); unresolved (the table says omitted, no row, or no table on disk); not held |
| `QuoteCheck` | `#/documents/check`; under an answer in `AskPanel`; under a draft in `DraftLetter`; under a candidate reading's quote | the report (`Report.as_dict()`), `textDigest`, `asOf` | not checked yet; checking; clean; not clean; changed since the check; no passage index (the command); nothing of four words or more to check; short quotations listed as not checked |
| `QuoteMark` | inline in the answer, on each quotation | one `quotes[]` row | each verdict word, with `exact` or `normalized` for `FOUND`; "not checked" for a short one; focus and its row |
| `QuoteVerdictRow` | under the text, one a quotation, in the answer's order | one `quotes[]` row, plus `checkedNearest` for `OTHER VERSION` | the cases in "The quote check" below |
| `QuoteDiff` (a `DiffTable` preset) | inside `QuoteVerdictRow` | `quoted`, `stored`, `differences[]` | one word differs; several; the punctuation only; parts an ellipsis joins from separate places; the stored words held back (confidential) |
| `CitationCheckRow` | under the verdicts | one `citations[]` row | a statute on the shelf, checked against the version in force (its label); not shown on the day (checked against the words on the shelf now, said); two versions under the number; not on the shelf; a former number (opens `FormerSectionRow`); a document's section held or not; not checked (a span, another unit) |
| `GiveGate` | at the control that gives the text: copy an answer, save a draft for approval, confirm a reading's quote | `clean`, `counts`, the signed-in person | clean (the control as usual, with the check's line); not clean (the control replaced by the fixes and **Give it as written**); changed since the check; given as written (the record, shown to whoever reads or approves next) |

## The vocabulary

Every state is a word from the code, so the console and the terminal agree, and no state is color alone. Keep the words.

**How the version on a day is known** (`law_text.Decided`):

| Word | `decided` | Meaning | `VersionLine` shows |
| --- | --- | --- | --- |
| an earlier version | `prior` | an earlier version on disk whose recorded range holds the day | its range in words (`range_words`), the act that made it, what ended it, its source, and that these are not the words on the shelf now |
| the words on the shelf now | `current` | a record places the shelf's words in force by that day: the ledger's day, the section's own operative words, or, for a day on or after the export, the publication itself | the basis sentence as the loader gives it |
| the versions' own words | `own_words` | one of the versions printed under one number, picked by their own operative words, never by position | the basis, and each deciding sentence quoted |
| not shown | `not_shown` | the disk does not show which words governed that day: nothing is picked | `NotShownNotice` |

**Where a held version stands** (`Held.place`): earlier · in force · later · and, where its recorded range does not say, "its range does not say". The last is a word of its own, never a blank cell.

**A range in words** is `range_words` as the loader sends it: "from 2091-01-01 until 2095-06-30; made by …; ended by …". "From a day not recorded" and an absent "until" stay as written; jason infers no day, and the timeline draws none.

**A former section number** (`law_citations.Resolution`):

| Word | `resolution` | The row says |
| --- | --- | --- |
| current | `current` | "cites CIV 9903(a): on the shelf (digest …), in force on DAY" |
| former | `former` | "cites former CIV 9803(g), now CIV 9901 (…)", then both recited |
| then current | `then_current` | "cites CIV 9803(g), the number in force on DAY (…)" |
| unresolved | `unresolved` | "an open finding, and no successor is guessed" |
| not held | `not_held` | "not on the shelf", with what brings it down |

Unresolved is styled as open, not as an error, and never sorted with "not held".

**A quotation's verdict** (`quote_check.Verdict`), in capitals as the command prints them, with the meaning in the accessible name:

| Word | `verdict` | Meaning |
| --- | --- | --- |
| FOUND (exact) / FOUND (normalized) | `found` | the words are in a stored text: character for character, or the same after folding |
| ALTERED | `altered` | no stored text has the words, and one has nearly those words; the difference is shown |
| MISATTRIBUTED | `misattributed` | the answer names one provision, and the words are stored only elsewhere |
| OTHER VERSION | `other version` | the answer names a statute, and the words are another version's than the one checked |
| NOT FOUND | `not found` | no stored text has the words or nearly the words |
| not checked | (`skipped`) | fewer than four words: listed, not checked |

**A quotation against a citation** (`inItsWords`, the command's own phrases): is in its words · is not in its words · is nearly its words (altered) · is in another version of it, not the one checked (other version).

Only `FOUND` is clean. A warning (a page, a reference, evidence, a confidential file, outside the sources given) leaves a `FOUND` clean and is shown beside it, in its own words.

## The day control

**One day a screen, and every recitation on it obeys it.** Each `Recitation`, `VersionLine`, `TermOnDay`, `FormerSectionRow`, and `QuoteCheck` on a screen reads the one day `AsOfControl` holds. No component carries a day of its own, except where the record fixes one and says so: a former section's own words are read as they last stood, the day before the renumbering ("as last in force (to 2093-12-31)"), whatever the screen's day.

**Where it lives: on each screen, in the address.** The day is a question about one letter, one event, or one review, so it is the screen's, carried as `?as_of=YYYY-MM-DD` (as `#/applies` already does), and a link that leaves the screen drops it unless the link carries it. A day set for one letter never silently changes the answer on another screen. The shell does not hold a global day (decision 1).

**Its default is today**, the association's day, as the loader echoes it (`asOf` in every answer). The control shows the loader's day, never the browser's clock: the loader decides what today is ([content/style.md](content/style.md#dates-and-times)).

**How it is announced.** On today the control reads "As of today, Oct 5, 2026" and nothing else is shown. On another day:

- `AsOfBanner` under the header: "The law on this screen is read as of Mar 1, 2092. Deadlines, records, and approvals stay today's." with **Back to today**;
- each `Recitation`'s caption names the day ("in force on Mar 1, 2092");
- the change itself is a status message, in place ("Read as of Mar 1, 2092: 3 sections read again; 1 not shown").

**What changes when it moves**, each by its loader reading again with `as_of`:

- the words recited, and their `VersionLine` (`version_on`);
- a citation's resolution (`resolve`): before a renumbering's operative day a former number is "then current";
- a term's value (`statutory_terms.in_force`);
- the version a quotation is checked against (`check(as_of=)`), and so a verdict: the same quotation can be `FOUND` on one day and `OTHER VERSION` on another;
- the readings shown: a reading dated after the day is set apart (`recite` with `as_of`);
- on `#/applies`, the date fact its rows turn on.

**What does not move:** the dock's deadlines, the records, approvals, a governing document kept only as recorded ("jason keeps this document only as recorded. It cannot give the words on a date." from [governing-documents.md](screens/governing-documents.md#states)), and the stored check records, each of which keeps the day it was made on.

**A day typed in an expression.** `jason cite` takes `CIV 9901@2092-05-01`. Typed into the cite box, the day moves the control, and the address shows `?as_of=` rather than the `@` (decision 9).

**A day not yet come** is allowed: the code reads it, and two versions under one number often turn on a day ahead. The banner adds the loader's caveats as they are; the screen adds no forecast of its own.

**When the disk does not show it.** The sentence is the tool's, verbatim, as the headline of `NotShownNotice`: "the disk does not show which words of CIV 9901 were in force on 2089-01-01". Then "Nothing is picked." Then the caveats, verbatim (`Caveats`), which say what is held, why none covers the day, and what would bring the words; then each command as a `Command`. The versions held are still listed (`VersionTimeline`), each with its range, for a person to read. If a person asks for the words on the shelf now (decision 3), they are a second `Recitation` under the label "Not shown to be in force on Jan 1, 2089", never "in force", and never the first thing on the screen.

## One section's versions

`VersionTimeline` draws every version jason holds of one section, oldest first (`every_version`), the shelf's and the history's, each a row of the table and, where its range allows, a bar on a time axis.

| Part | From | Shown as |
| --- | --- | --- |
| A version | `versions[]`: `digest`, `current`, `from`, `printedBy`, `until`, `act`, `source`, `addedByHand` | a row: the first 12 characters of the digest, "on the shelf now" or "held in the history", the range in words, the act, the source |
| The one in force | `inForce: true`, `place: "in force"` | the row marked "in force on DAY" in words; its bar carries the word too |
| Earlier, later | `place` | the word on the row; the bars to either side of the day |
| Its range does not say | `place: ""` | the word, and no bar: a row with no recorded range has nothing to draw |
| An open end | `from` empty (with `printedBy` where the publications show the words by a day), or `until` empty | "from a day not recorded (the session publications show them as the section's words by 2011-01-01)"; an open end has no cap, and the bar fades to the word "not recorded", never to an edge that looks like a day |
| A gap | `gaps[]`: days no held range covers, between two versions or before the first | a band of its own, with the words "no version held for these days" and the command that would bring one; a range not recorded is a gap of its own kind, "not recorded", never closed by drawing the neighbour across it |
| Two printed under one number | two rows with `current: true` | both listed, each labelled by the loader (`Quoted.label`: "version 1 of 2 the publication prints under CIV 9902 …"); the publication's order is shown and said not to be the order they operate in |
| The same words under two credits | the caveat "the publications print these words 2 times, each under its own credit line …" | one row, the caveat verbatim under the table |
| Added by hand | `addedByHand` | "added by hand (A. Person, 2099-02-03)", with its source as that person recorded it |
| Acts the Act's history names | `acts[]` (`succession.changes`, a civil code section only) | a tick on the axis with the act and its operative day, labelled "an act the Act's history names"; the caveat says the words on disk may differ from the words in force on that day |
| The day asked | `asOf` | a line on the axis with the day in text |

**Compare two versions** opens the two versions' words side by side: `DiffTable` once built, two `Recitation`s until then (as `StaleWordsBanner` falls back). Each side keeps its own `VersionLine` and the caveat.

The table is the timeline; the bars repeat it. A screen reader and a phone get the table, and lose nothing.

## The recitation, its version line, and a subdivision

The order is fixed, and nothing sits between the words and their caption:

1. **The words**, whole, in `Recitation` (`words` from `version_on`).
2. **The caption:** the citation, then `VersionLine`: "In force on Mar 1, 2092: from 2091-01-01 until 2095-06-30; made by Stats. 2090, Ch. 1, Sec. 2 (AB 1); ended by Stats. 2095, Ch. 7, Sec. 1 (AB 7). Source: California Legislature, 2091 to 2093 session publications, read with lawlibrary. Digest 5b1e0c4a9d27." For `own_words`, the deciding sentences follow, quoted, each labelled as the section's own words. For a hand-added version: "Added by hand by A. Person, 2099-02-03; its range and source are as that person recorded them."
3. **The caveat**, verbatim, always (`NOT_RESTATEMENT`): "jason's consolidated text is not an official restatement: the words are the Legislature's session publication as lawlibrary read it, or a version a person added from an official source, never the chaptered act. Where the exact enacted text matters, counsel reads the Statutes."
4. **The loader's other caveats**, verbatim (`Caveats`).
5. **Then any reading**, in a `ReadingLabel`, never before.

`Recitation` today knows two states: in force, and not in force (`version.inForce: false`, "Recited words · not in force"). This pass adds a third, **not shown**: words recited for a day the disk does not decide are captioned "Not shown to be in force on DAY", never "not in force", which would claim what the disk does not show. It is a prop on the built component, not a new one.

**A subdivision's words are jason's split.** When the citation names one ("CIV 9901(b)"), `SubdivisionWords` gives the subdivision's words first, under the label "(b), split from the section as jason splits it; the section is the source", and the whole section is one disclosure away, open by default on a wide screen (decision 4). Where no paragraph of the version opens with the subdivision, the whole section is given and the line says so in the tool's words: "no paragraph of this version opens with (z) as jason splits the section; the whole section is given". A split is never made from the first of two versions alone: where the disk does not decide between them, it is made from each, each under its label.

**`TermOnDay`.** Where a clock or a figure on the screen rests on a statutory term (a number of days, a cap), the value read for the day is shown with where it comes from: "14 days (the value in force on Mar 1, 2096)", or "15 days on Mar 1, 2092: the value before 2095-06-30, when Stats. 2095, Ch. 7 changed it". It is jason's constant, labelled "computed" as a clock is; the recited words above carry the number, marked with `Recitation`'s `mark`.

## The former-section row

A document written under a retired numbering cites a section that no longer exists by that number. It is not a missing section and not a conflict: it is read as its successor. `FormerSectionRow` takes one `Resolved` and shows, in this order:

1. **The note**, verbatim, as the row's heading: "cites former CIV 9803(g), now CIV 9901 (commission comment and disposition table: continued, continued with changes; renumbered to CIV 9900 to 9910 by Stats. 2093, Ch. 1 (AB 1), operative 2094-01-01); its own words recited from the history as last in force (to 2093-12-31); CIV 9901 recited".
2. **Where the successor comes from:** the table's source and its succession words, as `Successor` (`handoff-citations.md`) renders a successor, so the two pages read alike. Two successors are two, each recited; a successor the table maps to a subdivision keeps the table's own target ("CIV 9903(a)").
3. **The successor's words in force on the day**, each a `Recitation` with its `VersionLine`, under "Now CIV 9901".
4. **The former section's own words as they last stood**, a `Recitation` under "Former CIV 9803, its own words as last in force (to 2093-12-31)", with the label "Not the law of DAY: the words this number carried until the renumbering". Never captioned as in force on the screen's day.

Each other resolution:

| Resolution | The row | What brings what is missing |
| --- | --- | --- |
| former, its own words not held | the note ends "its own words not held"; the successor recited; in the former's place, "not held", with the reason | a person adds the words from an official source: `Command` `jason law-history --add-version FILE --citation CIV-9803 --source "…" --by NAME --from DAY --until DAY` |
| then current | "cites CIV 9803(g), the number in force on 2092-03-01 (renumbered to …)": the cited number was the law that day, recited as of it where held | where not held, the note says so in its own words, with the same `--add-version` command |
| unresolved: the table says omitted | "cites former CIV 9805; the table says omitted: an open finding, and no successor is guessed" | nothing jason can run: a question for a person, listed with the open questions |
| unresolved: no row | "… the law history on disk places nothing under that number …" | the same |
| unresolved: no table on disk | "cites former CIV 1363(g); the law history is not on disk (jason law-history --export), so nothing places it" | `Command` `jason law-history --export`: a person runs it; it asks lawlibrary again and writes `data/authorities/history` |
| current | "cites CIV 9903(a): on the shelf (digest …), in force on DAY"; the words recited only on request | none |
| not held | "cites CIV 9909: not on the shelf (…)" | `Command` `jason cite "CIV 9909"` or `jason export-authorities`, as the reason names |

An open finding is never closed by the screen: there is no "pick a successor" control. In a list (`in_scope`'s order), unresolved rows come first, then former, then current, as the loader sorts them.

## The quote check

A person (or the assistant behind `AskPanel`) writes an answer, a draft, or a reading from passages. Before it is given, `QuoteCheck` reads it as `check` does and marks each quotation in place.

**The text first, marked.** Each quotation in the text carries a `QuoteMark`: the quotation's span, and right after it the verdict word as a small chip ("OTHER VERSION"), linked to its row. The text is never changed by the check.

**Then one `QuoteVerdictRow` a quotation**, in the answer's order:

| Verdict | The row shows |
| --- | --- |
| FOUND (exact or normalized) | where the words are: each place's standing (authority, record, evidence, reference, page), file, section, passages, and digest; for a statute, "matches the version in force on 2092-05-01 (digest …, from … until …)", the place's own `note`; the stored words around it (`context`); more places counted |
| FOUND, with a warning | the same, and each warning verbatim beside it: found only in a page jason generated, only on the reference shelf, only in a case's file, only in a confidential file, outside the sources given, or attributed to a document as a whole whose copy does not hold the words. The row stays clean; the warning is read |
| ALTERED | `QuoteDiff`: "Quoted" and "Stored" on two lines, each difference marked, and the differences listed in text ("quoted: every · stored: each"); where the stored words are (`comparedWith`); "the words are the same; the punctuation differs" where that is all; a splice ("each part is stored, but the parts are not in order within one passage or section: the quotation joins separate places"); a near match in a confidential file, its words held back |
| MISATTRIBUTED | the citation the answer names, that its words do not hold the quotation, and the places that do |
| OTHER VERSION | see below |
| NOT FOUND | "No stored text has these words or nearly these words."; where some parts of an ellipsis are stored, "2 of its 3 parts are stored; the others are not" |
| not checked | the short quotations, listed under the rows: "Fewer than four words: not checked" |

**`OTHER VERSION` is explained, not just named.** The row says, in the tool's own note, which version the words are and which was checked: "the words you quote are a later version of CIV 9901 (digest 9f8e7d6c5b4a, from 2095-06-30; made by Stats. 2095, Ch. 7), on the shelf now; the version checked, the version in force on 2092-05-01 (digest 5b1e0c4a9d27, …), reads differently". Then:

- a small `VersionTimeline` of the section, with the version quoted and the version checked both marked in words;
- `QuoteDiff` of the quotation against the nearest words of the version checked (`checkedNearest`, which the loader computes with `quote_check.align`), so a person sees what that day's words say instead;
- if the words as quoted are also stored elsewhere (the law page, say), those places, with the warning "none is the version checked";
- the ways forward, as text and not as one-click fixes: quote the version checked; say in the answer which version is quoted and why; or, where the answer itself speaks of a day in the quoted version's range, set that day. The day is a fact of the question, never a fix: the row says so.

**The citations, after the quotations.** `CitationCheckRow` lists each provision the answer cites, in its order: the citation as a `CitationChip` (`handoff-citations.md`), whether jason holds it with its digest, "checked against the version in force on 2092-05-01 (…)" or, where the disk does not show that day, the caveat verbatim that the words on the shelf now were checked instead, both versions where the shelf prints two, and each quotation attributed to it with its `inItsWords` phrase. A pre-2014 number carries its caveat and opens `FormerSectionRow`. A span of sections or another unit is "not checked", with the tool's reason.

**The check's caveats** close the panel, verbatim (`Caveats`), starting with "This checks words, not meaning". They are never folded away.

### Keeping a failing answer from being given

Decided for this pass: **the console never gives a failing answer on its own, never edits it on its own, and never takes the choice from the person.**

- **Clean.** The giving control (copy the answer, save the draft for approval, confirm the reading) works as it does today, with the check's line beside it: "Quotations checked as of Mar 1, 2092: 3 found." A clean check is a line, not a stamp: it says words, not meaning.
- **Not clean.** The giving control is replaced, not greyed out, by the list of what failed ("1 OTHER VERSION, 1 ALTERED, 1 NOT FOUND"), each linking to its row, and two ways on:
  1. **Fix it.** Each row offers its edit: **Use the stored words** (`ALTERED`: the quotation replaced by the stored words, as an edit in the person's editor that the person sees and can undo); **Quote the version checked** (`OTHER VERSION`: the nearest words of that version); **Remove the quotation** (`NOT FOUND`). Nothing is saved by these: the person saves, and the text is checked again.
  2. **Give it as written, as Jane Example.** A `Confirm` in the signed-in person's name that restates each failing quotation and its verdict, and requires **Where these words are from** (the source, as a citation a reader can check: a court's opinion, counsel's letter, a version the person read). The text is given unchanged. The record keeps the person, the day, the as-of day, the text's digest, and each failing verdict with the source named, behind the write guard: `POST /api/write/quote-checks` (proposed). Its terminal equivalent is proposed too: `jason verify-quotes FILE --as-of DAY --given --by NAME --source TEXT`.
- **Changed since the check.** An edit after the check marks the report "changed since the check", and the giving control asks for a check again first. The write refuses (409) a text whose digest is not the one checked, and writes nothing: "The text changed since it was checked. Check it again."
- **Given as written, downstream.** The next reader sees it: a draft's approver in `DraftLetter` reads "Given as written by Jane Example, Oct 5, 2026: 1 quotation NOT FOUND (source named: …)" above the approval controls. It blocks nothing and is never hidden.

Why not a hard block: `NOT FOUND` means not in jason's stored words, not false. A person may quote a source jason does not hold, and the console cannot stop a copy anyway; a lock it cannot keep would only teach people to work around it. The record is what keeps the answer honest: who gave it, against what verdict, from what source. Whether a `NOT FOUND` given as written needs a second person is decision 5.

## States

| State | What the loader returns | What the screen says | The command |
| --- | --- | --- | --- |
| **No version history exported for the section** | `version_ledger` empty; `in_force` falls to the shelf's words where a record places them, else `not_shown`, with "jason law-history --versions --citation CIV-9901 reads the earlier session publications lawlibrary holds, with each version's range" | `NotShownNotice` for an earlier day; today's words recite as usual; `VersionTimeline` shows one row and the line "Earlier versions have not been read for this section." | `jason law-history --versions --citation CIV-9901` |
| **No successor table exported** | `recodifications` empty; a former number is `unresolved` | `FormerSectionRow`'s open state with the note's own words | `jason law-history --export` |
| **History partial** | a range with an end not recorded; the ledger read before the shelf changed ("the words on the shelf changed since the versions were read on …"); a day after the last publication that printed the words, before the next act jason knows | the open end drawn as "not recorded"; the stale ledger as a caveat at the top of `VersionTimeline`; the publications caveat verbatim under `VersionLine` | `jason law-history --versions --citation …` again; words no publication holds: `--add-version` |
| **Statute not on the shelf** | `found: false`; `basis` "CIV 9909 is not on the shelf (jason cite or jason export-authorities brings its current words down), and …" | `Recitation`'s miss ("Nothing is quoted."), then `NotShownNotice`; any earlier versions held still listed | `jason cite "CIV 9909"` |
| **A day before any held version** | `not_shown`; every `Held` row `place: "later"` | `NotShownNotice`; the timeline with the day to the left of every bar and the gap before the first; "The earliest version held is from 2091-01-01." | the `--versions` command, or `--add-version` from an official source, as the caveat names |
| **Two versions printed under one number, decided** | `own_words`, `decidingWords`, each `Held` placed | the version in force recited; its deciding sentence quoted under it; the other named in a caveat with its digest and why it is not the one | none |
| **Two versions printed under one number, not decided** | `not_shown` (or `Quoted.undecided`) | every version, each under its loader label, in the publication's order, with the line that this is not the order they operate in; a quotation's citation row lists both | the `--versions` command |
| **Two held ranges both hold the day** | `not_shown`; "jason holds 2 earlier versions of CIV 9901 whose recorded ranges each include …; a person reads which governed" | both rows marked on the timeline; nothing picked | none: a person reads them |
| **Not a citation** | "say a code and a section, such as CIV 5855 or CIV 5855(a)" | the tool's words under the cite box | none |
| **No passage index** | the check raises: "no passage index at …: build it with jason index --build" | `QuoteCheck` unavailable, with the note | `jason index --build` |
| **Nothing to check** | `quotes: []`, perhaps `skipped` | "No quotation of 4 words or more to check." and the short ones listed | none |

A state is a word and a sentence from the tool, never an empty table, a dash styled as a date, or a guessed range.

## Data shapes

Made-up samples only: sections CIV 9801 to 9910, acts "Stats. 2090" to "Stats. 2095", and "A. Person", as in the tests (`tests/test_law_in_force.py`, `tests/test_law_citations.py`, `tests/test_quote_check.py`). The words below are those tests' made-up words, not any statute's. Digests are shortened here; the loader sends them whole and the screen shows the first 12 characters.

`GET /api/law-in-force?citation=CIV%209901(b)&as_of=2092-05-01` (proposed; `jason.api.law_in_force`, which is `version_on(...).as_dict()` and `caveat`), an earlier version in force, with the loader's additions `gaps`, `acts`, `terms`, and `history` (each from a function that exists, named under "Where it goes"):

```json
{
  "citation": "CIV 9901", "subdivisions": "(b)", "asOf": "2092-05-01", "today": "2099-10-05",
  "found": true, "decided": "prior",
  "basis": "from 2091-01-01 until 2095-06-30; made by Stats. 2090, Ch. 1, Sec. 2 (AB 1); ended by Stats. 2095, Ch. 7, Sec. 1 (AB 7)",
  "reason": "", "digest": "5b1e0c4a9d27…",
  "words": "9901. (Added by Stats. 2090, Ch. 1, Sec. 2.)\n\n(a) A notice shall be given in writing.\n\n(b) The notice is given fifteen days before the hearing.\n\n(c) The notice names the place.",
  "subdivisionWords": "(b) The notice is given fifteen days before the hearing.",
  "from": "2091-01-01", "printedBy": "", "until": "2095-06-30", "untilBy": "Stats. 2095, Ch. 7, Sec. 1 (AB 7)",
  "act": "Stats. 2090, Ch. 1, Sec. 2 (AB 1)",
  "source": "California Legislature, 2091 to 2093 session publications, read with lawlibrary",
  "current": false, "addedByHand": "", "decidingWords": [],
  "caveats": ["the words of (b) are split from the section as jason splits it; the section itself is the source",
              "jason's consolidated text is not an official restatement: … Where the exact enacted text matters, counsel reads the Statutes."],
  "versions": [
    {"digest": "5b1e0c4a9d27…", "current": false, "from": "2091-01-01", "printedBy": "", "until": "2095-06-30",
     "act": "Stats. 2090, Ch. 1, Sec. 2 (AB 1)", "source": "California Legislature, 2091 to 2093 session publications, read with lawlibrary",
     "addedByHand": "", "inForce": true, "place": "in force",
     "range": "from 2091-01-01 until 2095-06-30; made by Stats. 2090, Ch. 1, Sec. 2 (AB 1)"},
    {"digest": "9f8e7d6c5b4a…", "current": true, "from": "2095-06-30", "printedBy": "", "until": "",
     "act": "Stats. 2095, Ch. 7, Sec. 1 (AB 7)", "source": "California Legislature, 2097 session publication, read with lawlibrary",
     "addedByHand": "", "inForce": false, "place": "later", "range": "from 2095-06-30; made by Stats. 2095, Ch. 7, Sec. 1 (AB 7)"}
  ],
  "gaps": [{"until": "2091-01-01", "kind": "before the first version held"}],
  "acts": [],
  "terms": [{"name": "notice before a hearing", "value": 15, "unit": "days", "current": 14,
             "prior": [{"value": 15, "until": "2095-06-30", "statute": "Stats. 2095, Ch. 7"}]}],
  "history": {"read": "2099-01-02", "editions": ["2091", "2093", "2095", "2097"], "printed": ["2091", "2093", "2095", "2097"], "stale": false},
  "caveat": "jason's consolidated text is not an official restatement: …"
}
```

The same section asked for a day the disk does not cover (`as_of=2089-01-01`): nothing is picked, and every version is still listed.

```json
{
  "citation": "CIV 9901", "subdivisions": "", "asOf": "2089-01-01", "found": false, "decided": "not_shown",
  "basis": "the disk does not show which words of CIV 9901 were in force on 2089-01-01",
  "reason": "the disk does not show which words of CIV 9901 were in force on 2089-01-01",
  "digest": "", "words": "", "subdivisionWords": "",
  "caveats": ["the words on the shelf now (digest 9f8e7d6c5b4a) came into force on 2095-06-30, after 2089-01-01",
              "an earlier version is held (digest 5b1e0c4a9d27): in force from 2091-01-01 until 2095-06-30; made by Stats. 2090, Ch. 1, Sec. 2 (AB 1); ended by Stats. 2095, Ch. 7, Sec. 1 (AB 7), which does not include 2089-01-01",
              "the words in force on 2089-01-01 are not held as such. lawlibrary's session publications were read on 2099-01-02 (the 2091 to 2097 session publications print it); words they do not hold are added by a person from an official source (docs/law-readings.md)",
              "jason's consolidated text is not an official restatement: …"],
  "versions": [{"digest": "5b1e0c4a9d27…", "inForce": false, "place": "later", "…": "…"},
               {"digest": "9f8e7d6c5b4a…", "inForce": false, "place": "later", "…": "…"}],
  "gaps": [{"until": "2091-01-01", "kind": "before the first version held"}],
  "commands": ["jason law-history --add-version FILE --citation CIV-9901 --source \"…\" --by NAME --from DAY --until DAY"]
}
```

Two versions printed under one number (`citation=CIV%209902&as_of=2098-06-01`), decided by their own words:

```json
{
  "citation": "CIV 9902", "asOf": "2098-06-01", "found": true, "decided": "own_words",
  "basis": "of the 2 versions the shelf holds under the number, the versions' own words leave this one in effect on 2098-06-01",
  "words": "(Amended by Stats. 2090, Ch. 3, Sec. 3.)\n\n(a) The hearing is held in a closed session.\n\n(b) This section shall remain in effect only until January 1, 2099, and as of that date is repealed.",
  "until": "2099-01-01", "untilBy": "its own provisions",
  "decidingWords": ["This section shall remain in effect only until January 1, 2099, and as of that date is repealed.",
                    "This section shall be operative January 1, 2099."],
  "caveats": ["the other version the shelf holds under the number (digest 0c3d2e1f4a5b) came into force on 2099-01-01, after 2098-06-01: \"This section shall be operative January 1, 2099.\"",
              "jason has no record of the day these words came into force (their credit line: \"(Amended by Stats. 2090, Ch. 3, Sec. 3.)\"); if that day is after 2098-06-01, earlier words governed. jason law-history --versions --citation CIV-9902 reads the earlier session publications lawlibrary holds, with each version's range",
              "jason's consolidated text is not an official restatement: …"],
  "versions": [{"digest": "0c3d2e1f4a5b…", "current": true, "from": "2099-01-01", "until": "", "inForce": false, "place": "later"},
               {"digest": "7a6b5c4d3e2f…", "current": true, "from": "", "until": "2099-01-01", "inForce": true, "place": "in force"}],
  "labels": {"7a6b5c4d3e2f…": "version 2 of 2 the publication prints under CIV 9902 (digest 7a6b5c4d3e2f); the one in force on 2098-06-01: …"}
}
```

`GET /api/law-citations?collection=example-hearing&as_of=2096-01-01` (proposed; `law_citations.in_scope` over the collection's scope, each `Use.as_dict()`), one row of each kind:

```json
{
  "found": true, "asOf": "2096-01-01", "collection": "example-hearing",
  "citations": [
    {"cited": "CIV 9805", "base": "CIV 9805", "subdivisions": "", "resolution": "unresolved", "open": true,
     "renumbered": "renumbered to CIV 9900 to 9910 by Stats. 2093, Ch. 1 (AB 1), operative 2094-01-01",
     "successors": [], "succession": "omitted", "source": "",
     "note": "cites former CIV 9805; the table says omitted: an open finding, and no successor is guessed",
     "former": null, "formerAsOf": null, "words": [],
     "citedBy": [{"document": "letter-2092-03-01.pdf", "passage": 0}],
     "quotes": ["The board gives notice under Civil Code Section 9803(g) and Section 9805 of the Civil Code that a hearing will be held."]},
    {"cited": "CIV 9803(g)", "base": "CIV 9803", "subdivisions": "(g)", "resolution": "former", "open": false,
     "renumbered": "renumbered to CIV 9900 to 9910 by Stats. 2093, Ch. 1 (AB 1), operative 2094-01-01",
     "successors": ["CIV 9901"], "succession": "continued, continued with changes", "source": "commission comment and disposition table",
     "note": "cites former CIV 9803(g), now CIV 9901 (commission comment and disposition table: continued, continued with changes; renumbered to CIV 9900 to 9910 by Stats. 2093, Ch. 1 (AB 1), operative 2094-01-01); its own words recited from the history as last in force (to 2093-12-31); CIV 9901 recited",
     "former": {"citation": "CIV 9803", "found": true, "digest": "e4d3c2b1a098…", "source": "Statutes of 2080, chapter 2 (a made-up volume)",
                "decided": "prior", "basis": "from 2081-01-01 until 2094-01-01; made by Stats. 2080, Ch. 2", "reason": "",
                "words": "9803. (Added by Stats. 2080, Ch. 2, Sec. 1.)\n\n(f) A fine is imposed only after a hearing.\n\n(g) A notice of the hearing is given fourteen days before it."},
     "formerAsOf": "2093-12-31",
     "words": [{"citation": "CIV 9901", "found": true, "digest": "9f8e7d6c5b4a…", "source": "A made-up Legislature, 2097 session publication",
                "decided": "current", "basis": "…", "reason": "", "words": "9901. (Added by Stats. 2093, Ch. 1, Sec. 2.)\n\n(a) A notice of the hearing shall be given in writing.\n\n(b) The notice is given fifteen days before the hearing."}],
     "citedBy": [{"document": "letter-2092-03-01.pdf", "passage": 0}], "quotes": ["…"]},
    {"cited": "CIV 9903(a)", "base": "CIV 9903", "subdivisions": "(a)", "resolution": "current", "open": false,
     "note": "cites CIV 9903(a): on the shelf (digest 1a2b3c4d5e6f), in force on 2096-01-01", "words": [{"…": "…"}],
     "citedBy": [{"document": "letter-2096-03-01.pdf", "passage": 0}], "quotes": ["…"]}
  ],
  "commands": {"export": "jason law-history --export", "addVersion": "jason law-history --add-version FILE --citation CIV-9805 --source \"…\" --by NAME"}
}
```

The same number asked for a day before the renumbering (`as_of=2092-03-01`) is `"resolution": "then_current"`, with the note "cites CIV 9803(g), the number in force on 2092-03-01 (renumbered to CIV 9900 to 9910 by Stats. 2093, Ch. 1 (AB 1), operative 2094-01-01)".

`POST /api/check/quotes` (proposed; read-only, `quote_check.check` as `verify_quotes` serves it, plus `textDigest` and, for each `OTHER VERSION`, `checkedNearest` from `quote_check.align`). The body is `{"answer": "…", "sources": "", "asOf": "2092-05-01", "private": false}`; the answer is never in the address. The answer checked:

> Civil Code 9901(b) says "The notice is given ten days before the hearing". The rules say "Each unit may keep two pets, and a fish is not counted as a pet". Civil Code 9901(a) requires "A notice shall be given in writing to every member". The summary says "the board always warns a member a month ahead".

```json
{
  "textDigest": "c0ffee00aa11…", "asOf": "2092-05-01", "minimumWords": 4,
  "counts": {"found": 1, "altered": 1, "misattributed": 0, "other version": 1, "not found": 1, "warnings": 1},
  "quotes": [
    {"quote": "The notice is given ten days before the hearing", "at": 26, "style": "straight", "verdict": "other version", "match": "exact",
     "attributedTo": ["CIV 9901(b)"],
     "note": "the words you quote are a later version of CIV 9901 (digest 9f8e7d6c5b4a, from 2095-06-30; made by Stats. 2095, Ch. 7), on the shelf now; the version checked, the version in force on 2092-05-01 (digest 5b1e0c4a9d27, from 2091-01-01 until 2095-06-30; made by Stats. 2090, Ch. 1, Sec. 2; ended by Stats. 2095, Ch. 7), reads differently",
     "places": [{"file": "CIV-9900-9910.md", "path": "authorities/CIV/CIV-9900-9910.md", "passages": [1], "section": "CIV 9901",
                 "catalog": "authorities", "standing": "authority", "kind": "", "generated": false, "confidential": false, "match": "exact"}],
     "warnings": ["the words as quoted are also stored in the place(s) listed; none is the version checked"],
     "checkedNearest": {"quoted": "The notice is given [[ten]] days before the hearing",
                        "stored": "The notice is given [[fifteen]] days before the hearing",
                        "differences": [{"quoted": "ten", "stored": "fifteen"}]}},
    {"quote": "Each unit may keep two pets, and a fish is not counted as a pet", "at": 98, "style": "straight", "verdict": "found", "match": "exact",
     "places": [{"file": "rules.md", "path": "governing/rules.md", "passages": [1], "section": "1.1 Pets", "catalog": "governing",
                 "standing": "record", "kind": "", "generated": false, "confidential": false, "match": "exact",
                 "context": "Each unit may keep two pets, and a fish is not counted as a pet."}]},
    {"quote": "A notice shall be given in writing to every member", "at": 188, "style": "straight", "verdict": "altered",
     "attributedTo": ["CIV 9901(a)"],
     "quoted": "A notice shall be given in writing to [[every]] member",
     "stored": "A notice shall be given in writing to [[each]] member",
     "differences": [{"quoted": "every", "stored": "each"}],
     "comparedWith": {"file": "", "path": "", "passages": [], "section": "CIV 9901(a)", "catalog": "authorities", "standing": "authority",
                      "match": "normalized", "citation": "CIV 9901(a)", "digest": "5b1e0c4a9d27…"}},
    {"quote": "the board always warns a member a month ahead", "at": 262, "style": "straight", "verdict": "not found"}
  ],
  "citations": [
    {"citation": "CIV 9901(b)", "kind": "statute", "at": 0, "checked": true, "found": true, "onShelf": true, "digest": "5b1e0c4a9d27…",
     "source": "A made-up Legislature, 2091 to 2093 session publications",
     "inForce": {"asOf": "2092-05-01", "shown": true, "decided": "prior", "digest": "5b1e0c4a9d27…", "from": "2091-01-01", "until": "2095-06-30",
                 "basis": "from 2091-01-01 until 2095-06-30; …",
                 "label": "the version in force on 2092-05-01 (digest 5b1e0c4a9d27, from 2091-01-01 until 2095-06-30; made by Stats. 2090, Ch. 1, Sec. 2; ended by Stats. 2095, Ch. 7)"},
     "quotes": [{"quote": 1, "inItsWords": "other version"}]},
    {"citation": "CIV 9901(a)", "kind": "statute", "at": 152, "checked": true, "found": true, "onShelf": true, "digest": "5b1e0c4a9d27…",
     "inForce": {"…": "…"}, "quotes": [{"quote": 3, "inItsWords": "altered"}]}
  ],
  "skipped": [], "includeConfidential": false, "passagesSearched": 14, "seconds": 0.21,
  "caveats": ["This checks words, not meaning: FOUND says the quoted words are jason's stored words. It does not say the answer reads them rightly, that they answer the question, or that they were in force on a given day.", "…"]
}
```

`POST /api/write/quote-checks` (proposed; behind the write guard, `X-Jason-Token`), giving a text as written:

```json
{"where": "draft:example-hearing-letter", "textDigest": "c0ffee00aa11…", "asOf": "2092-05-01", "by": "Jane Example",
 "given": [{"at": 26, "verdict": "other version", "source": "the version in force when the letter was sent, quoted on purpose: Stats. 2095, Ch. 7"},
           {"at": 188, "verdict": "altered", "source": "…"},
           {"at": 262, "verdict": "not found", "source": "counsel's letter of 2092-04-20 (a made-up letter)"}]}
```

The answer is the record written: `{written: "quotes/given.jsonl", at: "2099-10-05T15:02:00Z"}`. A `textDigest` that is not the draft's on disk is 409 and nothing is written; a missing `by` or a failing quotation with no `source` is 400.

## What the design must keep

- **One day a screen, shown.** Every recitation, version line, term, citation row, and quote check on a screen reads the day `AsOfControl` holds, and that day is in the caption of every recitation. A day other than today is announced in words above the screen's first band. No component reads its own day except where the record fixes one, labelled with it.
- **The disk decides, or nothing is picked** (principle 8). `not_shown` is a state with the tool's sentence and what would bring the words, never the shelf's words captioned as in force, never "the first version", never a range drawn past what is recorded.
- **Recite the version that governs, with the caveat** (principle 2). The words, then `VersionLine` (the range, the act, the source, the digest, how it is known), then the not-a-restatement caveat verbatim, then the loader's caveats, then any reading. Nothing sits between the words and the caption.
- **A split is jason's.** A subdivision's words are labelled as split by jason, the whole section one step away. A deciding sentence is the section's own words, quoted; the version label ("version 2 of 2 …") is jason's, set apart from the words.
- **A former number is read as its successor, never as a missing section or a conflict.** Both are recited where held, the former as it last stood and labelled not the law of the day asked. An unresolved number stays open: no control picks a successor.
- **A quotation leaves as stored words, or with a name on it.** The check marks every quotation in place; only `FOUND` is clean; `OTHER VERSION` says which version and which was checked; `ALTERED` shows the difference in text. A failing answer is given only by a person's **Give it as written**, with the source named, recorded, and shown to the next reader. The check never edits the text, and a fix is the person's own edit.
- **Words, not meaning.** A clean check says "found", never "verified", "correct", or "approved". The caveats close every panel.
- **Nothing writes without a named person** (principle 4). Reading a version, resolving a citation, and checking quotations write nothing. Bringing words onto the disk (`jason law-history --versions`, `--export`, `--add-version`, `jason export-authorities`, `jason cite`) is a `Command` a person runs. The one write here is the give-as-written record, a `Confirm` in the signed-in person's name through the write guard.
- **Privacy by level** (principle 6). The law, its versions, and the successor table are P0. An answer or a draft being checked may name owners (P1 to P3): it is sent in a request body, never in the address, and the check stores nothing. A place in a confidential file is shown by standing alone ("in a confidential file: its name and words are held back unless confidential files are asked for") outside the private view; asking for confidential files is opening the private view, for an entitled role, logged as `private_view.on`. The give-as-written record is P1: it keeps the text's digest and the sources named, not the text. The owner view shows none of this.
- **No color-only meaning.** Each verdict, each place, each resolution, and each `decided` is a word; a bar on the timeline repeats a row of its table twin; a difference in `QuoteDiff` is listed in text as well as marked.

## Where it goes

Routes are proposed, consistent with [information-architecture.md](information-architecture.md#where-the-proposed-screens-go); none exists yet.

- **Records → Governing documents** (`#/documents`, [screens/governing-documents.md](screens/governing-documents.md)): `AsOfControl` replaces its "As of [today v]" select, and the day is `?as_of=` beside `?q=`. A statute cited there gets a **Versions** band after the recitation (`VersionTimeline`), in the place a document's HISTORY band takes. Its "A version not in force" state gains "not shown" beside it.
- **Records → Governing documents → Check quotations** (proposed): `#/documents/check?as_of=`. A person pastes or opens a text (an answer, a draft) and reads `QuoteCheck`. The address carries the day and never the text. Its `Command` is `jason verify-quotes FILE --as-of DAY`.
- **The dock's Ask** (`AskPanel`): an answer's quotations are marked by `QuoteCheck` as of today, and copying the answer goes through `GiveGate`. A question about another day is taken to `#/documents/check`.
- **Drafts** (`#/drafts`, `DraftLetter`): "Save for approval" goes through `GiveGate`; the approver sees the check line or the give-as-written record.
- **Confirmations** (`#/confirmations/reading/<key>`, [handoff-confirmations-queue.md](handoff-confirmations-queue.md)): `ProvisionRecital` carries `VersionLine`; a reading's `quote` is checked as of the reading's day. A stale digest stays `StaleWordsBanner`'s, a separate question from the day.
- **What applies** (`#/applies`, [handoff-applicability-questions.md](handoff-applicability-questions.md)): its `?as_of=` is the same `AsOfControl`.
- **A collection's page and the as-of review** (`handoff-collection-workspace.md`, `handoff-context-pack-workbench.md`): their citations of the law are `FormerSectionRow`s, unresolved first.
- **Document ingestion's citations** (`handoff-citations.md`'s `IngestCitations` and `CitationChip`): a row whose standing is renumbered opens `FormerSectionRow` as of today.

**Loaders and writes to add** (names only; nothing built; each wraps a function that exists, except where marked "to write"):

| Name | Route | Wraps | Notes |
| --- | --- | --- | --- |
| `law-in-force` | `GET /api/law-in-force?citation=&as_of=` | `jason.api.law_in_force` (`law_text.version_on`); `law_text.quoted(...).labels()` for two versions; `version_ledger` and `changes` for `history`; `statutory_terms.TERMS` for the section with `in_force(name, day)` for `terms`; `succession.changes` for `acts` | `gaps` (to write): the days no recorded range covers, from the `Held` ranges only, a range not recorded given as its own kind and never closed |
| `law-text` | `GET /api/law-text?citation=&digest=` | `law_text.law_text(citation, data_dir, digest=)` | one held version's words, for **Compare two versions** |
| `law-citations` | `GET /api/law-citations?collection=&as_of=` or `?citation=&as_of=` | `law_citations.in_scope(data_dir, scope, as_of)`, or `resolve(data_dir, citation, as_of)` | needs the passage index for a collection; its absence is the tool's note with `jason index --build` |
| `check-quotes` | `POST /api/check/quotes` `{answer, sources, asOf, private}` | `quote_check.check` (as `jason.mcp.county.verify_quotes` calls it); `quote_check.align` against the checked version's words for `checkedNearest` | reads only; the body carries the text so it is never in a URL; `private` only in the private view for an entitled role, logged |
| write `quote-checks` (to write) | `POST /api/write/quote-checks` `{where, textDigest, asOf, by, given[]}` | appends `data/quotes/given.jsonl` under the store lock; refuses a digest that is not the draft's on disk (409), no `by`, or a failing quotation with no `source` (400) | the CLI equivalent is proposed with it: `jason verify-quotes FILE --as-of DAY --given --by NAME --source TEXT` |

No loader fetches. The commands that bring words onto the disk stay a person's, shown as `Command`s: `jason law-history --versions --citation CIV-9901`, `jason law-history --export`, `jason law-history --add-version FILE --citation … --source … --by …`, `jason export-authorities`, and `jason cite "CIV 9909"`.

## Accessibility

As [components.md](components.md#accessibility) and [content/patterns.md](content/patterns.md#accessibility-wcag-22-aa):

- **The day control.** A native `<input type="date">` labelled "Read the law as of", with a **Today** button beside it. Changing the day reads again; the result is a polite `role="status"` message ("Read as of Mar 1, 2092: 3 sections read again; 1 not shown"). Focus stays on the control. `AsOfBanner` is text under the header, not `role="alert"`, and never sticky.
- **Dates.** Every day is a `<time datetime="…">` with the console's form shown ("Mar 1, 2092"); a range is "from … until …" in words, never a dash.
- **The recitation.** A `figure` with `blockquote` and `figcaption`, as `Recitation` renders it; `VersionLine` is part of the caption, so a screen reader meets the words, then the citation and the version, then the caveat. "Not shown to be in force" is in the caption's text, not only its style.
- **The timeline.** The `DataTable` is the component; the bars are decorative (`aria-hidden`). The day asked, each place word, each gap, and each open end are cells with text. **Compare two versions** is a button on each row, in DOM order.
- **Quotations in the text.** Each `QuoteMark` is the quotation's text followed by a link whose text is the verdict ("OTHER VERSION, quotation 1"), pointing to its row; the row's heading repeats the quotation's first words. `<mark>` is not relied on to announce anything.
- **`QuoteDiff`.** Two labelled lines ("Quoted", "Stored"), each difference marked visually and the differences listed in text beneath ("quoted: ten; stored: fifteen"), so the difference is read without the marks.
- **`GiveGate`.** When the check fails, the giving control is replaced by a region headed "Not given: 3 quotations need a person", each failure a link to its row. **Give it as written** opens a `Confirm` whose fields are labelled ("Where these words are from, for quotation 1"); an error names the field ("Name the source for quotation 3: where the words are from"). After the act, the result in `role="status"`, in place.
- **Target size (2.5.8).** The day control's button, each verdict link, and each row's actions are 24 by 24 CSS px or spaced to pass. **Timing (2.2.1):** nothing times out; a half-typed source stays across a re-check. **Use of color (1.4.1):** every state above is a word.

### The phone layout (under 720 px)

- `AsOfControl` becomes one button in the header, "As of today" or "As of Mar 1, 2092", that opens the date field and **Today** below the header; `AsOfBanner` is one line with **Back to today**.
- A recitation's words wrap; nothing scrolls sideways at 320 px. `VersionLine` stacks under the citation, one fact a line (in force, range, act, source, digest), and the loader's caveats follow in full.
- `VersionTimeline` is its table as cards, oldest first: the in-force card open, the others with their place word and range on one line; a gap is a card of its own; the axis is not drawn.
- `FormerSectionRow` stacks the note, the successor's recitation, then the former's words in a disclosure labelled with their day.
- `QuoteCheck` shows the text with its marks first, then the verdict rows as cards, then the citations, then the caveats. `GiveGate` sits at the foot, not sticky (2.4.11): it is one decision after reading, not a bar over the text.

## Decisions for the design

1. **A day for a session.** This page puts the day on each screen, in its address. A review of one old letter may cross several screens (the reader, the check, a collection). Decide whether a person can pin a day for a working session, shown in the shell until unpinned, without any screen changing its day silently.
2. **The timeline's scale.** Ranges span decades and a gap may be days; a version with an open end has no length. Decide whether the bars use a time axis (with the open ends faded to words), equal-width steps in order, or no bars at all beside the table.
3. **The shelf's words on a day not shown.** `recite` gives the shelf's words under "Not shown to be in force on DAY"; `version_on` gives none. Decide whether the screen recites them under that label by default, on request, or not at all on the version band.
4. **The subdivision and the section.** Decide whether the whole section opens beside the split by default (wide screens) or stays a disclosure everywhere, and how the split reads when two versions are not decided.
5. **Giving a NOT FOUND quotation as written.** This page lets the person give any failing quotation with its source named. Decide whether `NOT FOUND` (unlike `ALTERED` and `OTHER VERSION`) needs a second person, and whether the record keeps the quotation's words or only its place and verdict.
6. **When the check runs.** On request, or on every answer `AskPanel` writes and every draft saved. Loading the passage index takes a moment; decide the trigger and how "checking" reads.
7. **Adding a version by hand from the console.** `jason law-history --add-version` writes the history with `--source` and `--by`. Decide whether the console offers it as a signed write (the words, the source, the range, the person, behind `Confirm`) or keeps it a `Command`.
8. **A day not yet come.** The code reads it. Decide how the banner marks a day ahead, so a person does not read the shelf's words for a later day as settled.
9. **The `@` in an expression.** `jason cite` takes `CIV 9901@2092-05-01`. Decide whether the cite box rewrites it into the control and the address, or keeps the expression as typed and shows the control following it.
10. **Two versions not decided.** Decide whether both are shown side by side (`DiffTable`) or stacked with their labels, and which comes first, given that the publication's order is not the order they operate in.

## Not part of this pass

- Fetching or exporting from the console: `jason law-history --versions`, `--export`, `jason export-authorities`, and `jason cite`'s fetch stay commands a person runs.
- Adding a version by hand from the console (decision 7).
- A governing document's own words on a day: [screens/governing-documents.md](screens/governing-documents.md) covers `jason://decl:DATE/7.3` and a document kept only as recorded.
- A reading's staleness against changed words: [handoff-confirmations-queue.md](handoff-confirmations-queue.md) (`StaleWordsBanner`).
- Checking meaning: whether a quotation answers the question, whether a paraphrase is faithful, or a figure outside quotation marks. The check reads words only.
- Versions of regulations and federal law, which lawlibrary's California shelf does not hold ([law-readings.md](../law-readings.md#the-gap-october-4-2026)).
- An owner-facing version of any band.
- The previews: the design project's authored preview for each component follows the build; fixtures will be `ui/src/components/asofcontrol.test.tsx` and its siblings, from the sample data above.
