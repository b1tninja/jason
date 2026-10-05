# Handoff: what applies to the association, and the questions a person answers

For the design pass on the components that show **whether a rule row reaches this association**, and **what a person must settle when jason cannot tell**. The data exists today: `jason applies` (each life safety obligation's answer for each system, and each building's record under Civil Code 5551), `jason applies --questions` (the questions the undetermined answers raise, with each one's state in the intake queue), and `jason notices --catalog --fact FACT=WORD` (the notice catalog's rows that are required only for some events). Behind them: `jason.community.applicability` (the three answers), `jason.community.applicability_asks` and `jason.tasks.applicability_asks` (the questions and the queue), `jason.community.notice_catalog.applicable` (the catalog's three groups), and `jason.community.elevated_inspections` (the per-building record). The design is settled in [../applicability.md](../applicability.md) and [../notices.md](../notices.md#when-a-row-is-required); the queue in [../intake.md](../intake.md#what-asks). No loader serves them yet ("Where it goes" lists the ones to add), and the intake answer route is built.

The format follows the earlier handoffs ([handoff-held-setup-roster.md](handoff-held-setup-roster.md); `handoff-citations.md`). The words on screen follow [content/style.md](content/style.md), the patterns [content/patterns.md](content/patterns.md), and the components [components.md](components.md). The neighbours this page links to and does not repeat: [screens/notices.md](screens/notices.md) (a notice from its requirement to its proof), [screens/life-safety.md](screens/life-safety.md) (the systems, their schedule, and their reports), [screens/schedule-and-duties.md](screens/schedule-and-duties.md) (the schedule and "record done"), [screens/onboarding.md](screens/onboarding.md) (the session's questions and `QuestionCard`), and [screens/community-facts.md](screens/community-facts.md) (the assumed defaults of every unit, a different kind of fact).

These components pair with what the console already has: `Pill`, `Recitation` and `ReadingLabel`, `QuestionCard` and `SecondConfirm`, `Confirm`, `Command`, `DataTable`, `Card`, `Tabs`, `DueDate` and `SourcedDate`, `Evidence`, `Findings`, `Caveats`, `HeldNote`, `Doc`, `EmptyState`, and `RemoteView`. Build new parts only where the table says so; most rows of it are an arrangement of a built part, and the "Built from" column says which.

**How this page meets the other handoffs.** Each of these shares a component or a question with this page; each is linked where it applies and not repeated.

| Neighbour | What it shares with this page | Where this page says so |
| --- | --- | --- |
| [handoff-confirmations-queue.md](handoff-confirmations-queue.md) | the line between a **fact** (a record states it; answered here) and a **reading** (what words mean; confirmed there); a fact question can wait on a reading | "Facts and readings"; "Where it goes" |
| [handoff-programs.md](handoff-programs.md) | a conditional program row is an `AnswerWord` and a `VerdictRow` over the same facts, and its missing fact is a question in this page's queue; an answer given here moves its rows | the question row's "what it decides"; the recomputation message |
| [handoff-improvement-requests.md](handoff-improvement-requests.md) | `NeedAnswer` ("does this change need approval") is an `AnswerWord` over the profile's change rules, and its undetermined answer is a question in this queue, raised by a request | the question row's "raised by"; "Where it goes" |
| [handoff-as-of-and-quote-check.md](handoff-as-of-and-quote-check.md) | the day control: `?as_of=` is this screen's day, and every recitation on it obeys the one control | "Where it goes"; the Buildings band |
| `handoff-citations.md` (not yet committed) | `CitationChip` for a statute named in a row's authority | `VerdictRow` |

## The idea in one line

A rule row applies, does not apply, or is **undetermined**, and that word is **jason's reading of the row's condition against the facts on hand**, never a ruling. The first two name the facts the reading turns on and where each came from; the third names the fact that is missing and becomes a question a named person answers with the record that states it, after which the reading is computed again. A fact the board decides is the board's to decide: a person records what the board's record says, and where the board has not decided, the question goes to the board. Nothing is read as "does not apply" because nobody has said.

## The components

| Component | Built from | Where it renders | Data | States to design |
| --- | --- | --- | --- | --- |
| `AnswerBand` | `ReadingLabel` (`whose="jason"`) and `Caveats` | the head of every band, list, and catalog group that shows an answer word | the page's fixed label | "jason's reading of each row's condition against the facts on hand. A reading, not legal advice. Where a fact is wrong, the answer is wrong; a person decides." (`Caveats`, verbatim from the loader's `caveats`). It is the one place the three words are explained as jason's. On a screen that borrows `AnswerWord` (`#/life-safety`, `#/notices`, `#/programs`, `#/requests`) the same line appears once under the screen's summary, so no `AnswerWord` is on a screen that does not say whose reading it is |
| `AnswerWord` (a `Pill` preset) | `Pill` | everywhere a row's answer appears: `#/applies`, `#/life-safety`'s schedule, `#/notices?catalog=`, a program row, a request's need | a verdict's `answer` | the three words below; beside each, the fact it turns on or the fact it lacks, in text on the same line (never only in a hover card); focus and activation open its `VerdictRow` |
| `VerdictRow` | `Findings`, `Recitation` for the authority | under any `AnswerWord` that opens; the row's own page | a `verdict` (`describe`, `deciding[]`, `missing[]`, `conflicting[]`) and the row's authority | the authority recited first (a `Recitation` where the shelf holds it, a `CitationChip` otherwise: `handoff-citations.md`), then the condition in words labeled "the row's condition, in jason's words", then **Turns on** each fact with its source; applies; does not apply (the fact it turns on first); undetermined with facts missing (**Lacks**, each fact's topic); undetermined with sources disagreeing (a `Discrepancy` that links to the question, which holds the values: settled under "A disagreement's values are shown once, in the question"); a partial set ("at least inspection, testing"); a row with no condition ("always"); a row whose authority is not on the shelf ("authority not on file; ask counsel") |
| `SourcedFact` | `Pill` for the source word, `Doc` for a record | inside `VerdictRow`, `StandingFacts`, `BuildingInspectionRow` | one `FactValue` (`fact`, `value`, `source`, `where`, `partial`) | from the profile (its `Community` method); from a document (the page or reader); from a person's answer (the question's id, who, when, the record named as a `Doc` chip where the library holds it, or "no record named"); the date asked for; partial ("at least …"); not on record |
| `StandingFacts` | `DataTable` of `SourcedFact` rows | `#/applies`, top card | `facts[]` from the profile and the queue's answers about the association | every fact stated; some answered, some stated; a fact not on record with its question; a fact stated twice (profile and answer) that agree; that disagree (`Discrepancy`); none stated (the profile sets `applicability_facts()` to nothing); the queue absent (`data/intake/asks.json` unread: the facts the profile states are shown, and the answers are "unavailable" with the command) |
| `FactQuestionRow` (a `QuestionCard` preset) | `QuestionCard`, `Confirm`, `SecondConfirm`, `HeldNote`, `Command`, `Evidence` | `#/applies`'s Questions band; the onboarding session's next questions; the dock's Ask | one question from `applies --questions --json` with its queue state | the states in "The question row" below: not filed, open, answered (by whom, when), answered and not read (why), answered and waiting on a second person, answered and in use, applied, disagreement, dismissed, stale; a question with choices; one entered with its record; a many-valued fact; a number; a date; a fact the board decides (with its path to the board); the question of which systems there are; answered by someone else since this page was opened; saved, and the rows could not be read again |
| `EventFactsPicker` | radio groups, `Command` | `#/notices` (the catalog band) and `#/applies`'s Notices band | the per-event facts, each a closed set with the statute's words as labels | nothing said (every conditional row undetermined); one fact said (the three groups, and the rows set aside for another kind of event); two said for one event (a rule change's subject and kind); a standing fact the profile does not state (the row stays undetermined and names the question); a word not in the set (refused, the set listed); the `Command` beside it always shows the facts as said |
| `CatalogGroups` | grouped `DataTable`s | under `EventFactsPicker` | `notice_catalog.applicable` as the three groups, plus the rows set aside | each group with its count, applies first; a group with none, its heading as the command prints it ("Does not apply: not required (0)"), under the band's label that the word is jason's reading on the facts said; the set-aside rows with the fact each turns on; a row's clock and delivery kind as `jason notices --catalog` prints them |
| `BuildingInspectionRow` | `Card`, `AnswerWord`, `SourcedFact`, `Doc` | `#/applies`'s Buildings band; the dock's Deadlines (its row) | one building from `applies --json`'s `buildings[]` | reaches: applies, does not apply (the fact it turns on), undetermined (the fact it lacks); (l) and (k) each a word with its why; last inspected, or "no inspection on record"; next due as `DueUnder`; the questions for this building; a record with no buildings at all; a building whose fields are P3 outside the private view ("opens in the private view": decision 4) |
| `DueUnder` | `DueDate` and `SourcedDate` | inside `BuildingInspectionRow`; the dock's Deadlines | a building's `due` (`day`, `under`, `question`) and its `standing` | computed under (b)(1), (i) from an inspection; under (k) from a certificate of occupancy; under (i), January 1, 2025, for the rest; **date not on record** with the question that stands in the day's place; upcoming, due soon, overdue beside the date. `SourcedDate`'s built word for a missing date is "needs input" and its word for a worked-out one is "implied"; the code's words here are "date not on record" and "computed" (`obligations.Standing`), and the loader's word is shown, so `SourcedDate` needs a `word` override rather than a second component |
| `Discrepancy` | `Findings` rows, one per source | `VerdictRow`, `StandingFacts`, `FactQuestionRow` | two or more `FactValue` for one fact | one component, not three: this page, the inspections-and-portals handoff (`handoff-inspections-and-portals.md`, not yet committed), and the collection workspace's `FactConflictCard` ([handoff-collection-workspace.md](handoff-collection-workspace.md)) each describe sources that disagree. Each value with its source, never a pick; the next step is a question or a correction to the specification |

## The vocabulary

Every state is a word from the code (`Answer`, `Source`, `AskStatus`, `Reach`, `Standing`), so the console and the terminal agree, and no state is color alone. Keep the words.

**The three answers** (`applicability.Answer`):

| Word | `answer` | Meaning (jason's reading, on the facts on hand) | What the row shows beside it |
| --- | --- | --- | --- |
| applies | `applies` | the condition holds for the facts on hand | **Turns on:** the facts, each with its source |
| does not apply | `does not apply` | a fact makes the condition fail | **Turns on:** the fact first ("turns on the system: backflow prevention assembly (profile, …)") |
| undetermined | `undetermined` | a fact is missing, or two sources disagree | **Lacks:** the fact's topic, or "sources disagree:" both values; and the question |

**The console's heading is "Turns on", never "decided by".** The terminal prints "decided by" for the same list (`jason applies`, `jason notices --catalog`). On a screen that word reads as an act, and nothing jason computes is labeled as decided ([content/style.md](content/style.md#who-said-it-recited-read-decided)): "decided" is a person's or the board's act. The loader still sends `deciding[]`; only the heading differs, and the terminal's three strings (`life_safety`, `applicability`, `notice_catalog`) should follow, so the two doors agree.

Undetermined is never styled as a failure and never grouped with "does not apply". Its glyph, if one is used, is a question, not a warning. "Does not apply" is never styled as good news, and "applies" is never styled as a duty met: the word says the condition holds, not that anything is owed or done.

**Where a fact came from** (`applicability.Source`): profile, document, answer, date. Each is written out ("profile, Community.life_safety_systems(): sprinklers-a"), never an icon alone. A set a document gave is "at least …" (`partial`).

**A question's state in the queue** (`applicability_asks._state`): not filed · open · answered by NAME, DATE · answered by NAME, DATE, not read · answered by NAME, DATE; a second person confirms it · answered by NAME, DATE; the sources disagree, so it is not settled · answered by NAME, DATE; noted for the specification · dismissed by NAME, DATE: the rows stay undetermined · stale: filed, and asked again.

Two of these need a meaning the code's words do not give, so the row says it in a line under the word:
- **stale** (`AskStatus.STALE`) is a question the last `--file-questions` run no longer raised: the fact is now stated, or no row reaches it. It is not "overdue" and not "changed since review" ([content/style.md](content/style.md#set-phrases) keeps "changed since review" for a plan whose live state moved). Under it: "No run asks this now; it opens again if one does." Its answer, if any, is kept.
- **applied** (`AskStatus.APPLIED`) reads as "answered by NAME, DATE" with the line `jason intake --apply` recorded ("a fact for jason applies: …", `applied_note`). It is not a state a person sets.

**Two states the built store cannot give, proposed with the loader:** *answered by someone else since this page was opened*, and *answered, and the rows could not be read again*. The first needs the answer route to take the `answeredAt` the person saw and refuse a different one (409; the built route overwrites an earlier answer and clears its confirmation, `intake.answer`). The second is a saved answer whose recomputation failed: "Saved. jason could not read the rows again: reload." with the `Command` `jason applies`.

**A building's subdivisions** (`elevated_inspections.Reach`): (l) applies / does not apply / undetermined, (k) the same, each with its `why` in words.

**A due day** (`obligations.Standing`): upcoming, due soon, overdue, and **date not on record**. The last is a state of its own, not an empty cell: it means a person has a date to enter.

**The catalog's fourth group:** set aside. A row that turns on another kind of event than the one the person described is neither answered nor hidden; it is listed with the fact it turns on.

## The question row

An undetermined condition becomes one question a subject and fact (`applicability_asks.questions`): however many rows wait on the same missing fact for the same system, there is one question, and its id is stable from run to run. The row shows, in this order:

1. **The subject**: the system by name, the association, or a building.
2. **The question**, in the fact's own words (`ASKS`), with the statute it comes from where one does ("… (Civil Code 5115(b)(6))").
3. **What it decides**: the rows waiting on it, by name, each with its condition in words (`rules`), so a person sees why the fact matters before answering. A row is a link into the screen that shows it, whatever its kind: a notice (`#/notices?catalog=KEY`), an obligation (`#/life-safety`, `#/duties`), a program row (`#/programs/<key>`, [handoff-programs.md](handoff-programs.md)), or a request's "does it need approval" (`#/requests?id=ID`, [handoff-improvement-requests.md](handoff-improvement-requests.md)). Where a request or a program raised the question, the row says so ("Raised by request imp-20261001-a1b2"): `raisedBy`, proposed below. One question serves every row that waits on its fact.
4. **What would settle it**: the kinds of record (`settledBy`: "the condominium plan", "the election operating rules, or the board's resolution in its minutes"). Kinds only; which record this association holds is its own. Where the library holds a record of that kind, the row offers it as a `Doc` chip to open and read before answering; it never picks one.
5. **Who answers**, said in the row before the form:
   - **A fact a record states** (a count, a date, a standard): any roster person signed in, with the record named.
   - **A fact the board decides** (seating by acclamation, Civil Code 5103; electronic voting; the directors' election quorum), in the question's own words: "this is the board's decision to record, not a reading of the documents." A person's answer records **what the board's record says**; it never makes the choice. The form therefore has a second path, **The board has not decided: put it on the board's agenda**, **Put it on the board's agenda as Jane Example**, a `Confirm` that proposes a board item (`tasks.board_items.propose`; the question, the rows waiting on it, and the statute cited, with no recommendation; CLI `jason applies --to-board ID --by NAME`, proposed) and leaves the question open ("On the board's agenda for Oct 20" from then on, as `HeldNote` words it). Without that path a person who finds no decision on record must either leave the row undetermined indefinitely or answer "not used" to get on, and the second settles a board question by one person's choice (AGENTS.md: "Don't settle an open question case by case"; "jason proposes; the board adopts"). The vote is recorded where every vote is (`#/room`, `#/decisions`), and the answer then names that decision.
6. **The answer form**, built from what the loader returns in `form` (proposed; the page decides nothing about the shape):
   - **A closed set** (a kind, a standard, a choice): radio buttons, the value's words as labels, **none checked**, and no free-text field. A free-text field on a closed set only produces answers the queue cannot read.
   - **A closed set entered with its record** (`NEEDS_RECORD`: a system's installation standard, electronic voting, acclamation, the directors' election quorum, elevated elements): the same radio buttons, then a required field labelled "The record that states it". The page joins them as `VALUE; RECORD`, the form the built route and `jason intake --answer` already take, so the server stays the one reader (`read_answer`) and refuses what it cannot read. The earlier design had no choice buttons for these facts so that a bare value could not answer without its record; a required field does that without losing the closed set. The `Confirm` stays off until the record is filled, with the reason beside it ("No record named: it is entered with the record that states it").
   - **A many-valued fact** ("at least inspection, testing"): checkboxes, joined with commas.
   - **A number** asks for a whole number; **a date**, `YYYY-MM-DD` in a date field.
   - The record field takes words, or a library document (`Doc` chip) the person chose from the kind's candidates; a chosen document is written into the record text as its name and address.
   - **Nothing is pre-filled and nothing is preselected,** even where the profile states a value or `likely` is true. A value the profile or a document states is shown above the form as "stated (profile, …)", never as jason's suggestion or a default: a pre-filled answer is a recommendation the person signs, shown as if it were the person's.
7. **What the answer becomes**: "Read as a fact with source *answer*. Where it disagrees with the specification, the row stays undetermined with both named." And: "The answer goes in the intake queue (`data/intake/asks.json`), never the specification." Under it, the consequence of a re-answer: where the question already holds an answer, **"This replaces the answer of NAME, DATE, and clears a second person's confirmation."**

**Answering is a write of a person's record.** It goes through the write guard (`X-Jason-Token`, origin and fetch-metadata checks, [security-and-privacy.md](security-and-privacy.md)) as a `Confirm` in the signed-in person's name: **Save the answer as Jane Example** (the name pre-filled from "Signed in as", 3.3.7; 401 with no one signed in), with the question, the answer, and the record restated above the button, and the words "This records what the record says. It decides nothing for the board." for a board fact. The route is the built one, `POST /api/write/intake/<id>` with `{answer, by}` (`jason.web.extra.onboarding_setup.write`, behind `jason.api.answer_intake_question`), which refuses an answer that looks like a secret and stores nothing: "Not stored: it gives a password. jason keeps no secrets. Put it in Keeper, and answer with the Keeper record's name", with the field cleared and the rest of the form kept (the refused text is the one thing never kept: [content/style.md](content/style.md#errors)). The CLI equivalent is `jason intake --answer ID TEXT --by NAME`. Proposed: the body also carries `seen` (the `answeredAt` the person saw), and a mismatch is refused (409): "NAME answered this on DATE, after you opened it. Read their answer, then answer again if you still need to. Nothing was written." Then the band reads `applies` again and the rows that waited on the fact move groups. The design shows the recomputation as a status message, never as a silent change, and names every screen that moved: "Answered by Jane Example. 3 notice rows now apply; 1 obligation is still undetermined; 2 program rows now ask for a document (Programs)."

**A question not yet in the queue** is "not filed": the answer route cannot take it (only onboarding's questions are parked on answer). The row shows the `Command` `jason applies --file-questions` and a `Confirm`, **File 6 questions as Jane Example** (a write to the queue under the store lock; a question already there keeps its answer; the counts new, kept, and stale are shown after, as the command prints them). Filing is a person's act with their name on it, as every write is (README principle 4); the question is jason's proposal, so filing records no answer and decides nothing.

**A second person.** A fact in `CONFIRMED` (empty today) waits for a second person: the row then shows `SecondConfirm` (the field starts empty, refused for the name that answered; `POST /api/write/intake/<id>` with `{confirm: true, by}`; `jason intake --confirm ID --by NAME`). Whether the three board facts join `CONFIRMED` is a decision for a person (decision 2).

**An answer not read** (not one of the set, no record where one is required, not a date) is shown with why, in the queue's words, **with the answer's own words quoted and attributed** ("Jane Example, Oct 2, wrote: 'about a fifth'"), and the form again with nothing pre-filled from it. The words are shown so the person can see what to fix; nothing is guessed from them. They are P1, for roster people only, and the secret check has already refused anything that looks like one. This is a new loader for this kind of question: the built onboarding loader sends no answer's value, and keeps that rule.

**Dismiss** is an answer ("dismiss") and is its own `Confirm`, not a variant of Save: **Dismiss this question as Jane Example**, with the consequence above the button ("The rows that wait on it stay undetermined. A dismissed question can be answered later.") and the CLI `jason intake --answer ID dismiss --by NAME`. Proposed, since the built route takes the word alone: a reason of a few words, kept with the dismissal, so the board can see why a row is still unanswered; the dismissed state then shows NAME, DATE, and the reason.

**What jason never does here.** It never answers a question in its own name, never marks a row "not required" because the question is open, never closes a question as "probably", and has no button that picks between a profile's value and an answer (`Discrepancy`).

## The event facts picker

`jason notices --catalog --fact FACT=WORD` sorts the fifteen conditional notice rows for one event. The picker is one control per per-event fact (`Fact.per_event`), each a closed set whose members are the statute's own distinctions, labelled with the section ([../notices.md](../notices.md#when-a-row-is-required) has the table):

| Fact | Members | Said by |
| --- | --- | --- |
| `election` | directors · recall · assessment · amendment · exclusive use · other | the person describing the election (5100(a)(1), (b); 5115(a)) |
| `rule_scope` | listed subject · not reached | the person (4355(a), (b)) |
| `rule_change` | noticed · emergency | the person (4360(a), (d)) |
| `board_meeting` | ordinary · executive session only · emergency | the person (4920(a), (b)(2), (b)(1)) |
| `meeting_format` | in person · teleconference with a location · entirely by teleconference | the person (4090, 4926(a)) |
| `electronic_voting`, `acclamation`, `director_quorum` | (standing) | **not in the picker**: the profile states them, or a `FactQuestionRow` asks |

The result is `CatalogGroups`, and why a row is in each group is on the row:

- **Applies** (required when its event happens, on its clock): its condition in words held for the facts said ("the election is an election of directors or a recall election (5115(a), (b))").
- **Does not apply** (not required, on the facts said): the fact it turns on ("turns on the election: vote on an assessment").
- **Undetermined** (the facts do not say, which is never "not required"): each missing fact with how it is settled. A per-event fact: "say it with the picker". A standing fact: "a standing fact: the profile states it, or a person answers it", with the question linked. A row can be undetermined for both at once.
- **Set aside**: rows that turn on another kind of event than the one described ("turns on: board_meeting"), listed, not answered.

With nothing said, every conditional row is undetermined and the page reads as `jason notices --catalog --required`. **Leaving a fact unsaid is the honest answer when a person is unsure**, and the picker says so beside it ("Not sure? Leave it. The rows that turn on it stay undetermined."): it is never read as "not reached" or "ordinary". A standing fact the picker cannot set shows as a locked line with its source: "electronic voting: used, with members opting in (profile, the election operating rules)" or "not on record: question d6efe4141c". The picker writes nothing: the facts said are the page's own state (and the query string), never stored.

**What a said fact is.** Each choice is the person's statement for this read, shown as "said by you for this read", not a finding. Where the choice is itself a reading of the statute (whether a rule's subject is one the statute lists; whether a rule change or a meeting is an emergency), the statute's own words for it are recited beside the control (`Recitation`, from the shelf), the choice is labeled "the person's reading, for this read", and a person who is unsure is sent to the board's agenda or to counsel through the board ("Where the law is unclear rather than silent, counsel reads it first", AGENTS.md), not given a third choice. The page decides none of them.

**The picker is a radio group a fact, not a `select`.** Every set has six members or fewer, and a `select` hides its members until it opens, which hides on a phone the very words (the statute's distinctions) the person is choosing between. Each group is a `fieldset` whose legend is the fact in the statute's words; the choices are labeled radio buttons, none checked, with a "Not said" choice that is the default. Two facts for one event (a rule change's subject and kind) are two groups under one heading ("Describe the event"). The standing facts the picker cannot set sit below it as a plain list of locked lines ("stated by the profile" or "not on record: question …"), in text, not as disabled controls.

**The command follows the picker.** The page's `Command` is always the one that reproduces what is on screen, rebuilt on each choice: `jason notices --catalog --fact election=directors --fact rule_change=noticed`. The page's address carries the same facts (`?fact=election=directors`, repeatable), so a person can copy either to a colleague.

## The per-building record

Civil Code 5551 is asked of the association once (`ELEVATED_ELEMENTS_INSPECTION`: a condominium, elevated elements the association maintains or repairs, three or more attached units in a building). Two subdivisions are about one building each, so the record is per building (`Community.elevated_elements_inspections()`, from the private facts). The band recites first, then shows each building.

**Recited words**, from the shelf (`jason cite "CIV 5551"`, read October 5, 2026; the 2025 publication of the code, `authorities/CIV/CIV-5550-5580.md`, amended by Stats. 2025, Ch. 516, Sec. 5). The console takes them from the shelf at render, with the version in force on the screen's day ([handoff-as-of-and-quote-check.md](handoff-as-of-and-quote-check.md)) and the caveat, never from this page:

- (b)(1): "At least once every nine years, the board of an association of a condominium project shall cause a reasonably competent and diligent visual inspection to be conducted by a licensed structural or civil engineer or architect of a random and statistically significant sample of exterior elevated elements for which the association has maintenance or repair responsibility."
- (i): "The first inspection shall be completed by January 1, 2025, and then every nine years thereafter in coordination with the reserve study inspection pursuant to Section 5550. …" (the subdivision's next sentence, on keeping the written reports, is omitted here and recited in the console)
- (k): "The inspection of buildings for which a building permit application has been submitted on or after January 1, 2020, shall occur no later than six years following the issuance of a certificate of occupancy. …" (the next sentence is omitted here and recited in the console)
- (l): "This section shall only apply to buildings containing three or more attached multifamily dwelling units."
- (e)(5)(A), the first page of the report: "The date of inspection."

These were checked against `jason cite "CIV 5551"` on October 5, 2026, and are the only statute words on this page; a design never types one, and the console recites each whole with its omissions marked, as the axiom "Recite the rule; label the reading" asks ([../../AGENTS.md](../../AGENTS.md); [../citations.md](../citations.md)).

**Each building's row** (`BuildingInspectionRow`):

| Line | From | Shown as |
| --- | --- | --- |
| Reaches it | `reaches` (the section's condition with the building's own units and responsibility over the association's facts) | an `AnswerWord` with the deciding or missing fact |
| (l) | `unitsRule` | "(l): applies (the most attached multifamily dwelling units in one building: 12 (profile, …))" or "(l): undetermined (the number of attached multifamily dwelling units is not on record)" |
| (k) | `permitRule` | "(k): applies (the permit application of 2021-02-01 is on or after 2020-01-01)", "does not apply (… is before …)", or "undetermined (the building permit application's date is not on record)" |
| Last inspected | `inspectedOn`, `inspector`, `license`, `licenseNumber`, `report` | "2024-05-06 by Pat Example, licensed architect C-00000; report: Example report 2024", or "no inspection on record"; an inspection with no license: the question. Outside the private view the name and number are masked by the server: "2024-05-06 by a licensed architect; report: Example report 2024" (decision 4) |
| Next due | `due` | `DueUnder`, below |
| Questions | `questions[]` | each as a line, and each a `FactQuestionRow` where it is one fact (the date questions are entered on the record, not in the queue: decision 3) |

**`DueUnder` is a computed clock, labelled so.** It shows the day, the subdivision and count it comes from, and a `ReadingLabel` "computed by jason from the record; the words above govern":

- an inspection on record: nine years from it ("(b)(1), (i): 9 years from the inspection of 2024-05-06" → 2033-05-06);
- none, and (k) applies: six years from the certificate of occupancy ("(k): 6 years from the certificate of occupancy of 2022-08-15" → 2028-08-15); with no certificate date, **date not on record** and "enter it from the certificate";
- none, and (k) does not apply: "(i): the first inspection by 2025-01-01", already past: the standing word is **overdue**, and the line under it is "None on record; the deadline passed", with "None on record is not none done." once on the screen. The day is known; what is not known is whether an inspection happened that nobody recorded, so the row also offers the question "Is there a report? Enter the date of inspection from its first page";
- none, and (k) undetermined: **date not on record**, "under (i) the first inspection was due 2025-01-01, under (k) six years from the certificate of occupancy. Enter the permit application's date, or the date of inspection from the report on file".

**"Date not on record" is a state**, the same row `jason deadlines` prints with that standing. It is never an empty date, never a guessed one, and never "overdue": the day is unknown until a person enters the date from the record the question names (the report's first page, the permit application, the certificate). A report on file whose date has not been read into the record raises that question first.

A building the section does not reach shows "next due: none asked; the section does not reach it", with the deciding fact, and raises no question. A profile with no building rows shows "The specification lists no buildings' inspections (`Community.elevated_elements_inspections()`); the obligation row is asked of the association as a whole."

## The standing facts: stated and answered

`StandingFacts` is the top card of `#/applies`: the association's own facts the rule rows turn on, each with its source. Two kinds sit in one table, told apart in words, not columns of color:

| Fact | Stated by | Where it shows |
| --- | --- | --- |
| the kind of development, the occupancy class, the unit count, whether the association maintains elevated elements, the most attached units in a building | the profile (`Community.applicability_facts()`), each with its `where` | "stated (profile, …)" |
| the state and county | `Community.region`, when the profile does not state them outright | "stated (profile, Community.region)" |
| electronic secret ballots, seating by acclamation, the directors' election quorum | the profile where it states them; else a person's answer from the queue, with the record named | "stated (profile, …)" or "answered by NAME, DATE; the election operating rules" |
| a system's kind and installation standard | the system's record (`Community.life_safety_systems()`), shown on the system's card, not here | — |
| the date asked for | the page (`as_of`, default today) | "the date: 2026-10-05 (date)" |
| a fact of one event (what an election decides, how a meeting is held) | never here: the picker says it for one event | — |

A fact the profile does not state and no one has answered is "not on record", with its `FactQuestionRow` beside it. A fact stated by the profile and answered by a person shows both; when they agree the answer stands, when they disagree the row is a `Discrepancy` and the fact is "not settled: a person corrects the specification, or answers again". A person's answer never overwrites the profile from the console: applying it is `jason intake --apply`, which turns the answer into a record a person reviews, and the card says so (the onboarding caveat, verbatim).

## Data shapes

Made-up samples only: "Example Village HOA", buildings A to D, "Vendor A", "Pat Example". The keys are the payloads the commands print today (`jason applies --json`, `jason applies --questions --json`), key for key; the catalog's shape is proposed, since the command prints lines.

`GET /api/applies` (proposed; `jason.tasks.applicability_asks.evaluate` and `elevated_inspections`), one finding of each kind:

```json
{
  "found": true, "community": "Example Village HOA", "asOf": "2026-10-05",
  "systems": [{"key": "sprinklers-a", "name": "Fire sprinklers, building A", "kind": "fire_sprinkler",
               "standard": "nfpa_13r", "standardFrom": "the approved plans of 2004 (sheet FP-1)", "alsoStated": [],
               "serves": ["A"], "served": "building A", "servicer": "Vendor A", "monitor": "", "note": ""}],
  "applies": [
    {"row": "Fire sprinkler annual inspection and test", "authority": "19 CCR 904 (NFPA 25, California edition)",
     "system": "sprinklers-a", "subject": "Fire sprinklers, building A",
     "verdict": {"answer": "applies",
                 "condition": {"except": {"is": ["system", "fire_sprinkler"]}, "unless": [{"is": ["installation_standard", "nfpa_13d"]}]},
                 "describe": "the system is a fire sprinkler system, except where the installation standard is NFPA 13D",
                 "deciding": [{"fact": "system", "value": "fire_sprinkler", "source": "profile", "where": "Community.life_safety_systems(): sprinklers-a"},
                              {"fact": "installation_standard", "value": "nfpa_13r", "source": "profile", "where": "the approved plans of 2004 (sheet FP-1)"}],
                 "missing": [], "conflicting": []},
     "why": "the system: fire sprinkler system (profile, Community.life_safety_systems(): sprinklers-a); the installation standard: NFPA 13R (profile, the approved plans of 2004 (sheet FP-1))",
     "question": ""}
  ],
  "doesNotApply": [
    {"row": "Backflow assembly test", "authority": "Health and Safety Code 116407", "system": "sprinklers-a", "subject": "Fire sprinklers, building A",
     "verdict": {"answer": "does not apply", "condition": {"is": ["system", "backflow"]}, "describe": "the system is a backflow prevention assembly",
                 "deciding": [{"fact": "system", "value": "fire_sprinkler", "source": "profile", "where": "Community.life_safety_systems(): sprinklers-a"}],
                 "missing": [], "conflicting": []},
     "why": "the system: fire sprinkler system (profile, Community.life_safety_systems(): sprinklers-a)", "question": ""}
  ],
  "undetermined": [
    {"row": "Exterior elevated elements (balconies) inspection", "authority": "Civil Code 5551: first by January 1, 2025, then every nine years",
     "system": null, "subject": "the association",
     "verdict": {"answer": "undetermined",
                 "condition": {"all": [{"is": ["common_interest", "condominium"]}, {"is": ["elevated_elements", "association_responsible"]}, {"at_least": ["attached_units", 3]}]},
                 "describe": "the development is a condominium and maintenance or repair of exterior elevated elements (5551(a)) is the association's responsibility (5551(b)(1)) and the most attached multifamily dwelling units in one building is at least 3",
                 "deciding": [], "missing": ["common_interest", "elevated_elements", "attached_units"], "conflicting": []},
     "why": "", "question": "the association: what kind of common interest development is it? …"}
  ],
  "questions": [{"question": "the association: what kind of common interest development is it? …", "system": null,
                 "waiting": ["Exterior elevated elements (balconies) inspection"]}],
  "unreached": [],
  "facts": [{"fact": "state", "value": "CA", "source": "profile", "where": "Community.region"},
            {"fact": "electronic_voting", "value": "opt_in", "source": "answer",
             "where": "intake question d6efe4141c: Jane Example, 2026-10-02; the election operating rules of 2024"}],
  "buildings": [
    {"building": "A", "label": "building A", "attachedUnits": 12, "responsibility": "association_responsible", "elements": 4,
     "inspectedOn": "2024-05-06", "inspector": "Pat Example", "license": "architect", "licenseNumber": "C-00000",
     "report": "Example report 2024", "permitApplicationOn": "2004-03-01", "occupancyCertificateOn": "2005-09-01",
     "reaches": {"answer": "undetermined", "describe": "…", "deciding": [{"fact": "elevated_elements", "value": "association_responsible", "source": "profile", "where": "Community.elevated_elements_inspections(): building A"},
                                                                          {"fact": "attached_units", "value": 12, "source": "profile", "where": "Community.elevated_elements_inspections(): building A"}],
                 "missing": ["common_interest"], "conflicting": []},
     "unitsRule": {"subdivision": "(l)", "answer": "applies", "why": "the most attached multifamily dwelling units in one building: 12 (profile, Community.elevated_elements_inspections(): building A)"},
     "permitRule": {"subdivision": "(k)", "answer": "does not apply", "why": "the permit application of 2004-03-01 is before 2020-01-01"},
     "due": {"day": "2033-05-06", "under": "(b)(1), (i): 9 years from the inspection of 2024-05-06", "question": ""},
     "questions": [], "note": ""},
    {"building": "B", "label": "building B", "attachedUnits": 8, "responsibility": "association_responsible", "elements": 2,
     "inspectedOn": null, "inspector": "", "license": null, "licenseNumber": "", "report": "",
     "permitApplicationOn": "2021-02-01", "occupancyCertificateOn": "2022-08-15",
     "reaches": {"answer": "undetermined", "describe": "…", "deciding": [], "missing": ["common_interest"], "conflicting": []},
     "unitsRule": {"subdivision": "(l)", "answer": "applies", "why": "…: 8 (profile, …)"},
     "permitRule": {"subdivision": "(k)", "answer": "applies", "why": "the permit application of 2021-02-01 is on or after 2020-01-01"},
     "due": {"day": "2028-08-15", "under": "(k): 6 years from the certificate of occupancy of 2022-08-15", "question": ""},
     "questions": [], "note": ""},
    {"building": "C", "label": "building C", "attachedUnits": 2, "responsibility": "none", "elements": 0,
     "inspectedOn": null, "inspector": "", "license": null, "licenseNumber": "", "report": "", "permitApplicationOn": null, "occupancyCertificateOn": null,
     "reaches": {"answer": "does not apply", "describe": "…", "deciding": [{"fact": "elevated_elements", "value": "none", "source": "profile", "where": "Community.elevated_elements_inspections(): building C"}], "missing": [], "conflicting": []},
     "unitsRule": {"subdivision": "(l)", "answer": "does not apply", "why": "…: 2 (profile, …)"},
     "permitRule": {"subdivision": "(k)", "answer": "undetermined", "why": "the building permit application's date is not on record"},
     "due": {"day": null, "under": "(i) or (k)", "question": "no inspection is on record, and the building permit application's date is not: …"},
     "questions": [], "note": ""},
    {"building": "D", "label": "building D", "attachedUnits": 6, "responsibility": "association_responsible", "elements": 3,
     "inspectedOn": null, "inspector": "", "license": null, "licenseNumber": "", "report": "Example report 2023 (date not read)",
     "permitApplicationOn": null, "occupancyCertificateOn": null,
     "reaches": {"answer": "undetermined", "describe": "…", "deciding": [], "missing": ["common_interest"], "conflicting": []},
     "unitsRule": {"subdivision": "(l)", "answer": "applies", "why": "…: 6 (profile, …)"},
     "permitRule": {"subdivision": "(k)", "answer": "undetermined", "why": "the building permit application's date is not on record"},
     "due": {"day": null, "under": "(i) or (k)", "question": "no inspection is on record, and the building permit application's date is not: under (i) the first inspection was due 2025-01-01, under (k) six years from the certificate of occupancy. Enter the permit application's date, or the date of inspection from the report on file"},
     "questions": ["the report on file (Example report 2023 (date not read)) has not been read into the record: enter the date of inspection from its first page (5551(e)(5)(A))",
                   "no inspection is on record, and the building permit application's date is not: …"],
     "note": ""}
  ],
  "caveats": ["Each answer rests on the facts the specification states, shown with where each comes from. An undetermined answer is a question for a person, not \"does not apply\". A rule's scope is recited from its row; read the authority before relying on it."]
}
```

`GET /api/applies-questions` (proposed; `applicability_asks.questions` with `tasks.applicability_asks.standing` and `stored`), the shape of `jason applies --questions --json`:

```json
{
  "found": true, "community": "Example Village HOA", "asOf": "2026-10-05",
  "questions": [
    {"id": "abdba3a040", "subject": "applies:association", "fact": "acclamation", "system": null,
     "question": "The association: does the board keep seating by acclamation available for an election of directors (Civil Code 5103)? The statute leaves the choice to the association, whatever its documents say, so this is the board's decision to record, not a reading of the documents. Answer with one of kept available (5103), not used and, after a semicolon, the record that states it.",
     "decides": ["notice acclamation-initial", "notice acclamation-reminder", "notice nomination-acknowledgment"],
     "rules": ["the election is an election of directors and seating by acclamation is kept available (5103)"],
     "stated": [], "known": [], "settledBy": "the election operating rules, or the board's resolution in its minutes",
     "values": ["kept available (5103)", "not used"], "choices": [],
     "filed": true, "status": "open", "answer": "", "answeredBy": "", "answeredAt": "", "highStakes": false, "needsConfirmation": false,
     "state": "open"},
    {"id": "ffed5ba700", "subject": "applies:association", "fact": "attached_units", "system": null,
     "question": "The association: how many attached multifamily dwelling units does its largest building contain (Civil Code 5551(l))? Name the record that states it after a semicolon, if one does.",
     "decides": ["Exterior elevated elements (balconies) inspection"], "rules": ["the development is a condominium and …"],
     "stated": [], "known": [], "settledBy": "the condominium plan", "values": [], "choices": [],
     "filed": false, "status": null, "answer": "", "state": "not filed", "file": "jason applies --file-questions"},
    {"id": "3a1b2c3d4e", "subject": "applies:system:sprinklers-b", "fact": "installation_standard", "system": "sprinklers-b",
     "question": "Fire sprinklers, building B: the sources disagree on the installation standard: NFPA 13R (profile, the board's minutes of 2022-09-19); NFPA 13D (answer, intake question 3a1b2c3d4e: Jane Example, 2026-10-01; the installer's certificate). Which is right? jason picks neither: the rows stay undetermined until the specification is corrected or the answer is given again.",
     "decides": ["Fire sprinkler quarterly inspection", "Fire sprinkler annual inspection and test"],
     "rules": ["the system is a fire sprinkler system, except where the installation standard is NFPA 13D"],
     "stated": ["NFPA 13R (profile, the board's minutes of 2022-09-19)", "NFPA 13D (answer, intake question 3a1b2c3d4e: Jane Example, 2026-10-01; the installer's certificate)"],
     "known": [], "settledBy": "the approved plans, the building permit, or the installer's record (its material and test certificate)",
     "values": ["NFPA 13", "NFPA 13R", "NFPA 13D", "NFPA 14", "NFPA 20", "NFPA 72"], "choices": [],
     "filed": true, "status": "answered", "answeredBy": "Jane Example", "answeredAt": "2026-10-01",
     "state": "answered by Jane Example, 2026-10-01; the sources disagree, so it is not settled"}
  ],
  "answersInUse": [{"id": "d6efe4141c", "fact": "electronic_voting", "value": "opt_in", "source": "answer",
                    "where": "intake question d6efe4141c: Jane Example, 2026-10-02; the election operating rules of 2024"}],
  "answersNotRead": [{"id": "4fa72d16c1", "answer": "about a fifth", "why": "not one of: none, 20 percent or more, lower than 20 percent (5115(b)(6)(B))"}],
  "caveats": ["An answer is recorded with who gave it and when, and is read as a fact with source \"answer\". Where it disagrees with the specification, the row stays undetermined with both."]
}
```

`GET /api/notice-catalog?fact=election=directors` (proposed; `notice_catalog.applicable` and `about` over `tasks.applicability_asks.association_facts`, the `--fact` parser of `jason.commands.notices`):

```json
{
  "found": true, "conditional": 15, "total": 73,
  "said": [{"fact": "election", "value": "directors", "source": "answer", "where": "the picker"}],
  "standing": [{"fact": "electronic_voting", "value": "opt_in", "source": "answer", "where": "intake question d6efe4141c: …"},
               {"fact": "acclamation", "value": null, "source": null, "question": "abdba3a040"}],
  "applies": [{"key": "nomination-procedure", "statute": "CIV 5115", "kind": "general notice (4045)",
               "clock": "at least 30 days before the deadline for submitting nominations",
               "rule": "the election is an election of directors or a recall election (5115(a), (b))", "verified": true}],
  "doesNotApply": [],
  "undetermined": [{"key": "acclamation-initial", "statute": "CIV 5103", "kind": "individual delivery (4040)",
                    "clock": "at least 90 days before the deadline for submitting nominations",
                    "rule": "the election is an election of directors and seating by acclamation is kept available (5103)",
                    "unknown": [{"fact": "acclamation", "topic": "whether the association keeps seating by acclamation available (5103)",
                                 "standing": true, "question": "abdba3a040"}], "conflicting": []}],
  "setAside": [{"key": "board-meeting", "statute": "CIV 4920", "turnsOn": ["board_meeting"]}],
  "caveats": ["Undetermined is never \"not required\". Rows about another kind of event are set aside and named, not answered."]
}
```

**Proposed additions to a question** (not in `--questions --json` today; the loader adds them so the page works nothing out):

```json
{
  "form": {"shape": "closed set with record", "values": ["kept available (5103)", "not used"], "many": false,
           "recordRequired": true, "recordKinds": "the election operating rules, or the board's resolution in its minutes"},
  "boardDecision": true,
  "boardItem": null,
  "raisedBy": [{"kind": "request", "id": "imp-20261001-a1b2", "route": "#/requests?id=imp-20261001-a1b2"}],
  "decidesLinks": [{"kind": "notice", "key": "acclamation-initial", "route": "#/notices?catalog=acclamation-initial"},
                   {"kind": "program", "key": "example-program", "route": "#/programs/example-program"}],
  "waitsOnReading": null,
  "answerText": "kept available (5103); the election operating rules of 2024",
  "answeredAt": "2026-10-02T15:04:00+00:00",
  "dismissedWhy": ""
}
```

`form.shape` is one of `closed set`, `closed set with record`, `many`, `number`, `date`, `systems` (the question of which systems there are, which becomes rows a person writes). `boardDecision` is true for a fact the board decides; `boardItem` is the item once a person has taken the question to the board. `waitsOnReading` names a reading by key where the record that would answer is words whose meaning is open ([handoff-confirmations-queue.md](handoff-confirmations-queue.md)). `answerText` is sent for this kind of question only. The write adds `seen` (the `answeredAt` the person saw), so a stale answer is refused (409).

A `FactValue` is always `{fact, value, source, where}` with `partial: true` when a set may leave values out. The console reads the words as they are; it never maps a word to another.

## What the design must keep

- **Three answers, never two** (principle 8, and [../applicability.md](../applicability.md#2-three-answers-never-two)). Undetermined is its own group, its own word, and its own glyph. A screen that counts "applies" and "does not apply" and drops the rest is wrong. A notice row undetermined is never "not required"; an obligation undetermined is never "nothing due".
- **Recite first, label the reading** (principle 2). The section's words come from the shelf through `Recitation`, with the version in force and the caveat, before any row. A condition's `describe` is jason's reading of the row, labelled so ("the rule row's condition, in jason's words"); a due day is "computed". Nothing on these screens is labelled as decided except a person's answer, with the person's name.
- **The facts a word turns on are always shown with their sources.** "Does not apply" without "turns on …" is a bare conclusion; the design never shows the word alone where there is room for the fact, and on a chip the fact is the accessible name and the hover card. The word is jason's reading ("A reading, not legal advice"), never the system's ruling and never "decided".
- **A person's answer is a fact with source *answer*, not a correction.** Where it disagrees with the profile or a document the row stays undetermined with both named (`Discrepancy`); jason picks neither, and the console has no "use this one" control. The fix is a corrected specification or a new answer.
- **Nothing is recommended, pre-filled, or preselected.** A value the profile states is shown as stated. A question's choices start unchecked. A `likely` flag or a `QuestionCard` suggestion is not used for these questions: a suggestion the person signs reads as the person's own answer.
- **A board fact is the board's.** A fact the board decides is answered only with the record that shows the board decided it, and the form's other path is the board's agenda. No person's click makes the board's choice, and none stands in for its vote ([README principle 5](README.md#principles)).
- **A fact entered with its record.** For a `NEEDS_RECORD` fact the form refuses an answer with no record named, in the queue's own words ("no record named: it is entered with the record that states it"), with the choices as radio buttons and the record as a required field beside them. The server reads the joined answer; the page does not.
- **Every write is a `Confirm` in a named person's name, through the write guard, with its CLI equivalent.** Saving an answer (`jason intake --answer`), confirming one as a second person (`jason intake --confirm`), dismissing a question (`jason intake --answer ID dismiss`), filing the questions (`jason applies --file-questions`), and taking a question to the board (`jason applies --to-board ID --by NAME`, proposed, after `jason readings --to-board`) are the five. The picker and the as-of control write nothing; their `Command` is `jason notices --catalog --fact …` and `jason applies --as-of …`. Applying answers to the specification stays a terminal command (`jason intake --apply`), shown with the count, as the onboarding screen does. The console has no approve control anywhere on this page.
- **"Date not on record" is not a date.** `DueUnder` never shows a placeholder date, a dash styled as a date, or "overdue" for a building whose counting date is unknown. The question stands in the day's place. When the day is known and nothing is on record, the row says "None on record; the deadline passed", not "late" or "missed".
- **The event facts are the page's, not the association's.** What one election decides is said for that catalog read and never stored as a standing fact. The standing facts are read-only in the picker and point to their question. A choice that is itself a reading of the statute is the person's, for this read, and is labeled so.
- **Set aside is shown.** The catalog never hides a row because it turns on another kind of event. A fold on a group (settled under "'Does not apply' folds, with its count and heading in text") keeps its count and its heading in text.
- **No color-only meaning.** Every word in "The vocabulary" is text; a count in text beside any bar; a `Discrepancy` is two lines of text, not a red mark.
- **Privacy by level** (principle 6), by what each part shows:

  | What | Level | Shown |
  | --- | --- | --- |
  | the law, a statute's words, a row's authority and condition in words | P0 | always |
  | the association's own facts the profile states as class attributes (kind of development, unit count) | P0 | always on the board's screens; the owner view shows none of this page |
  | a question, its words, what it decides, a person's answer and who gave it (`answeredBy`, `answeredAt`) | P1 | roster people; the answer's own words included, as the person wrote them (the secret check has already refused what looks like one) |
  | a `where` that quotes an email, a note, or a document's page | P1; the document's own level for a `Doc` chip | roster people; a P3 document by kind only outside the private view ("opens in the private view") |
  | a building's inspection row: the dates, the report's name, the inspector's name and license number | P3 by source, since these come from the private facts (`data/spec`) | the building's reach and next due at P1; the report's name, the inspector, and the number in the private view only, logged; outside it "a licensed architect; report on file" (decision 4) |
  | a board item a question is taken to | P1, and by its general subject where the subject is an executive-session one | as every board item is |
  | a secret | P4 | never shown, stored, or asked for: the form has no field for one |

  The screen is board-only (`owner: false`), and none of its bands appears in the owner view.

## Where it goes

Routes are proposed, consistent with [information-architecture.md](information-architecture.md#where-the-proposed-screens-go); none exists yet.

- **Governance → What applies** (proposed): `#/applies`, board-only (`owner: false`). Bands in order, as `Tabs`: **Facts** (`StandingFacts`), **Systems** (each system's card with its three groups, the rows reaching no system listed as "reaches none of the listed systems"), **Buildings** (the 5551 recitation, then a `BuildingInspectionRow` a building), **Notices** (`EventFactsPicker` and `CatalogGroups`), **Questions** (every `FactQuestionRow`, open first, with `answersInUse` and `answersNotRead` below). Query: `?subject=association` | `system:<key>` | `building:<key>` (keys and symbols only, never a name), `?as_of=YYYY-MM-DD`, `?fact=election=directors` (repeatable) for the Notices band. The header's `Command` is `jason applies` (`--questions`, `--as-of`).
- **`#/life-safety`** ([screens/life-safety.md](screens/life-safety.md)): the schedule's rows take an `AnswerWord` with the fact it turns on or lacks. The screen's own status word "needs input" is the same state as **undetermined** and reads "undetermined" (one word for one state, [content/style.md](content/style.md#applicability-and-programs-the-words-the-new-screens-use)); it links to the system's `FactQuestionRow` in `#/applies?subject=system:<key>`.
- **`#/notices?catalog=KEY`** ([screens/notices.md](screens/notices.md)): band 1 (the requirement) takes the row's `AnswerWord` for the facts said, and the catalog band takes `EventFactsPicker`, with the same `?fact=` query as `#/applies`.
- **The onboarding session** ([screens/onboarding.md](screens/onboarding.md)): `next_questions` already lists intake kinds; a question of kind `applicability` renders as `FactQuestionRow` there too, so one answer path serves both.
- **The dock's Deadlines**: a building's row from `elevated_inspections.calendar_rows` shows `DueUnder` with its standing, and opens `#/applies?subject=building:<key>`.
- **The confirmations queue** ([handoff-confirmations-queue.md](handoff-confirmations-queue.md), `#/confirmations`). Fact or reading: a question answered by reading a value off a record is answered here; a question two people could answer differently from the same words is a candidate reading there. A fact question whose record is such words shows "waits on a reading: on the confirmations queue" and links `#/confirmations/reading/<key>` (`waitsOnReading`); until that reading is the board's or counsel's, the fact stays undetermined, and a candidate never answers a fact. In the other direction the reading's page lists "Questions waiting on this reading", each linking `#/applies?subject=…`. A `Discrepancy` between the profile and an answer is never confirmed there: it is settled by a corrected specification or a new answer, here.
- **Programs** ([handoff-programs.md](handoff-programs.md), `#/programs`). A conditional program row is an `AnswerWord` and `VerdictRow` over the same facts, and its missing fact is a `FactQuestionRow` in this queue (the program's `GapQuestionRow` is the same preset: one question, one answer path). The question's "what it decides" lists the program row with a link to `#/programs/<key>`; a program row that is undetermined is a question, never "missing" and never "not required"; and the recomputation message after an answer names the program rows that moved.
- **Improvement requests** ([handoff-improvement-requests.md](handoff-improvement-requests.md), `#/requests?id=ID`). `NeedAnswer` is an `AnswerWord` over the profile's change rules through the same `applicability.evaluate`. Its undetermined answer ("does a floor inside the unit need approval") raises a question here, with `raisedBy` naming the request; the question is the board's or counsel's to answer, never the owner's, and the request page links to it. The owner view shows the answer's words ("Ask the board before you start") and never this page.
- **The day control** ([handoff-as-of-and-quote-check.md](handoff-as-of-and-quote-check.md)): `?as_of=` is `AsOfControl`'s address. On another day, `AsOfBanner` says so, and the Buildings band's recited words, each row's answer (`applicability.evaluate(as_of=)`), and a due day's standing (upcoming, due soon, overdue) are read as of that day; the computed days themselves, the queue's answers, and approvals are the record's and do not move.

**When a loader cannot answer** (principle 8: a miss stays a miss, never an empty table). Each band is its own `RemoteView`, so one failing band does not blank the others. No intake queue on disk: the Questions band says "No questions are filed yet" with the `Command` `jason applies --file-questions`, and the answers are "unavailable", not "none". No life-safety systems in the specification: the Systems band says "The specification lists no systems; the obligations asked of the association as a whole are below" and still shows them. A date refused (`as_of` is not `YYYY-MM-DD`): the tool's own words, and the page keeps today. A building's private facts unreadable: "unavailable", the file named, never an empty row. The shelf lacking CIV 5551: the recitation says "not on file" with `jason cite`, and each building's row still shows its facts.

**Loaders to add** (names only; nothing built; each wraps a function that exists today and derives no fact of its own):

| Loader | Route | Wraps | Notes |
| --- | --- | --- | --- |
| `applies` | `GET /api/applies?system=&as_of=` | `jason.tasks.applicability_asks.evaluate(community, data_dir, as_of)` → `SystemApplicability.as_dict()`; `elevated_inspections.records`, `base_facts`, each row's `as_dict(base)`; `association_facts` for `facts[]` | the `jason applies --json` shape, plus `facts[]` and `caveats` |
| `applies-questions` | `GET /api/applies-questions` | `applicability_asks.questions(result, tasks.applicability_asks.standing(...))`, `stored(data_dir)`, `answered` | the `--questions --json` shape, with each question's queue state as `onboarding_setup._answered` gives it, plus the proposed keys above (`form`, `boardDecision`, `raisedBy`, `decidesLinks`, `answerText`, `answeredAt`). The answer's own words are sent for this kind of question only, to roster people; the onboarding loader keeps its rule of sending no answer's value |
| `notice-catalog` | `GET /api/notice-catalog?fact=FACT=WORD` | `notice_catalog.conditional`, `about`, `applicable`; the `--fact` parser of `jason.commands.notices`; `tasks.applicability_asks.association_facts` | the three groups and the set-aside rows as JSON; `jason.api.notice_requirements(key)` for a row's full requirement |
| `intake` (writer, **built**) | `POST /api/write/intake/<id>` `{answer, by}` / `{confirm: true, by}` | `jason.api.answer_intake_question`, `onboarding_confirm` | the answer, the dismissal (`answer: "dismiss"`), and the second person; refuses a secret; 401 with no one signed in. Proposed on the same route: `seen` (the `answeredAt` the person saw; a mismatch is 409) and `why` for a dismissal |
| `applies` (writer, proposed) | `POST /api/write/applies/file` `{by}` | `tasks.applicability_asks.file_questions(data_dir, asked)` under the store lock | **File N questions as NAME**; the counts new, kept, and stale shown after; CLI `jason applies --file-questions` |
| `applies` (writer, proposed) | `POST /api/write/applies/to-board` `{id, by}` | `tasks.board_items.propose` with the question as evidence | **Put it on the board's agenda as NAME**; makes a board item and nothing else; CLI `jason applies --to-board ID --by NAME` (proposed) |

Every row of this table is behind the write guard (`X-Jason-Token`, origin, fetch metadata), takes `by` (400 without; the signed-in person's name while someone is signed in), answers 401 with no one signed in, and refuses a secret. A refusal says "Nothing was written."

The elevated-elements dates (the inspection date from a report's first page, the permit application, the certificate of occupancy) have no write route: they are rows in the private facts, entered by a person in `data/spec`; the console edits neither the specification nor the private facts, and shows the file to edit as a `Command`-style block (decision 3).

## Accessibility

As [components.md](components.md#accessibility) and [content/patterns.md](content/patterns.md#accessibility-wcag-22-aa):

- **Keyboard.** Every `AnswerWord` that opens a `VerdictRow` is a `button` with `aria-expanded`; the row opens in place under it and Escape closes it, returning focus. `FactQuestionRow`'s form is native fields in a `fieldset` whose legend is the question's subject; choices are radio buttons (checkboxes for a many-valued fact) with the value's words as labels, none checked; the record field is a text input labelled "The record that states it" and marked required where it is, with the `Confirm` disabled by `aria-disabled` and described by the reason. The board path ("The board has not decided: put it on the board's agenda") is its own button after the form, never inside the answer's radio group. `EventFactsPicker` is a set of radio-group `fieldset`s, one a fact, each with a "Not said" choice checked first, and a polite live region for the result ("3 apply, 0 do not apply, 5 undetermined, 7 set aside"). Tabs follow the tabs pattern with arrow keys; a band is reachable by its `?subject=` link too.
- **Screen reader.** The three words are the accessible name of each pill, followed by the deciding or missing fact ("undetermined: unknown: whether the association keeps seating by acclamation available (5103)"). A `DueUnder` with no day has the accessible name "date not on record" and its question; it never reads a placeholder. The recitation is a `figure` with `blockquote` and `figcaption` (the citation and version). `Discrepancy` is a list of two items, each naming its source. The recomputation after an answer is a `role="status"` message; a refused answer is `role="alert"` beside the field, tied by `aria-describedby`, with the queue's words.
- **Phone layout (< 720 px): the words that decide stay on the page.** The deciding or missing fact is the reason a person trusts or doubts a word, so it is never behind a disclosure and never cut to an ellipsis.
  - The tabs become a `select` whose options carry the counts ("Questions (6 open, 1 not filed)"), so the one band that needs a person is not hidden by the control.
  - A system's three groups stack with their counts in the group headings. `DataTable`s of rows become lists: the row's name, then the `AnswerWord` and **the fact it turns on or lacks, wrapped in full under them** ("undetermined: lacks the number of attached multifamily dwelling units"). The disclosure holds only the recitation, the condition in words, and the evidence chips.
  - `BuildingInspectionRow` is a card: the building, its reach **with the deciding or missing fact**, (l) and (k) each as a line of words, the last inspection, and `DueUnder` with its question. Nothing but the inspector's details and the recitation is folded.
  - The picker's radio groups stack with each legend (the statute's words) above its choices; the live `Command` is below the result, not sticky.
  - `FactQuestionRow` reads in the order of "The question row": the question, what it decides, what would settle it, who answers, then the form. The form is full width; the `Confirm` button is at its end and not sticky (2.4.11); the board path is a second button below it with its words in full ("The board has not decided: put it on the board's agenda").
  - A re-answer's consequence ("This replaces the answer of NAME, DATE…") and a refusal sit directly above the button, in text. Nothing scrolls sideways at 320 px.
- **Target size (2.5.8)**: a pill that opens, a radio, and the copy button on a `Command` are 24 by 24 CSS px or spaced to pass. **Redundant entry (3.3.7)**: the answering name comes from "Signed in as"; only `SecondConfirm`'s name starts empty. **Timing (2.2.1)**: nothing times out; a half-typed answer stays in the field across a band change. **Use of color (1.4.1)**: every state above is a word first; the glyph for undetermined is a question mark, for a disagreement two marks, never a warning triangle.

## Decisions for the design

**Settled by the axioms in this pass, and why.** Each was an open decision in the first cut; the axiom that settles it is named, so a later pass does not reopen it without a reason.

- **Filing the questions is a `Confirm`** (was decision 2). README principle 4: "Nothing is sent, posted, recorded, or filed without a person." Filing writes jason's own queue under the store lock, records no answer, and decides nothing, so it is a person's signed act with the `Command` beside it. The counts new, kept, and stale are shown after.
- **A person's answer is shown in their own words** (was decision 3). "Recite the rule; label the reading" and "only stored words": an answer is stored text that a person wrote, so the console quotes it with who and when; it never shows a paraphrase, and never a secret (the check refuses one before it is stored). Roster people only (P1). The built onboarding loader keeps its rule; this kind of question gets its own loader.
- **A fact the board decides is recorded from the board's record, and otherwise goes to the board** (new). "Where the law is silent, write it down: don't settle an open question case by case" and "jason proposes; the board adopts". A person never answers a board's question by choosing; the form's second path is the board's agenda.
- **No pre-filled or preselected answer** (new). "A reading, a match, or a gap is a lead, not a finding" and "a decision brief never recommends": a value the profile states is shown as stated; the person's signature is never put under a suggestion.
- **The console writes neither the specification nor the private facts** (half of decision 4). AGENTS.md: the specification is data a person reviews and commits; applying answers is `jason intake --apply`. Which register or file holds the building dates stays open (decision 3).
- **The picker is a set of radio groups, with "Not said" first** (was decision 5). A `select` hides its members, and the members are the statute's own distinctions. "A miss stays a miss": the unsaid fact leaves the rows undetermined, so there is nothing to disable and no third choice for "unsure". Where a choice is itself a reading, it is the person's, labeled, and the unsure go to the board's agenda or to counsel through the board.
- **A disagreement's values are shown once, in the question** (was decision 7). The `Discrepancy` in `VerdictRow` shows the two sources in one line each and links to the question; the question holds the full values, the sources, and the next step. One fact seen twice is one copy of the values, and "jason picks neither" is said in both.
- **"Does not apply" folds, with its count and heading in text** (was decision 8). Principle 8 forbids hiding a miss, not folding a known answer: the fold keeps "Does not apply: 21", a text heading, and the group's contents one disclosure away. "Applies" and "undetermined" stay open.
- **The console says "Turns on", the terminal says "decided by"** (new). "Nothing jason computes is labeled as decided" ([content/style.md](content/style.md#who-said-it-recited-read-decided)). The terminal's three strings should follow.

**Still open, and a person's to settle.**

1. **One screen or bands elsewhere.** `#/applies` as proposed gathers five bands, and the Systems, Notices, and Questions bands already appear where a person works (`#/life-safety`, `#/notices`, the onboarding session), as "Where it goes" says. What is open is smaller than before: whether `#/applies` is a Governance item of its own, for the manager's weekly check (`jason sop law-review` runs `jason applies` each January), or only the Facts and Buildings bands need a home. The loaders are the same either way. Test the weekly check with the manager.
2. **The board's facts and the second person.** Acclamation, electronic voting, and the directors' election quorum are facts the board decides, and `CONFIRMED` (the set whose answers a second person confirms) is empty. Decide whether they join it, so a record of the board's choice is read by two people, or whether naming the record (the minutes or the resolution) is enough. If they join it, the president or the secretary, who record the board's votes, are the natural second person; that is the board's call.
3. **Where the building dates live.** The inspection date, the permit application date, and the certificate of occupancy are rows in the private facts (P3 by source). AGENTS.md says "Facts the board keeps up to date belong in a register" ([../registers.md](../registers.md)), which points to a register, read back by jason, rather than a file under `data/spec` a person edits. Decide whether a register carries them, or a signed intake kind (the date, the record it was read from, the person), or the terminal task with the row showing the file to edit. Until then the console shows the file and writes nothing.
4. **Which building fields are P1.** The inspection's date and report are records of the association; the inspector's name and license number are on a report presented to the board (5551(f)). The data-level table classes everything from `data/spec` as P3, and the design follows it by default: reach and next due at P1; the report's name, the inspector, and the number in the private view only. Decide with the privacy model whether a licensed professional's name on a report the board holds is P1.
5. **The record field.** A typed record ("the election operating rules of 2024") is free text; a `Doc` chip chosen from the library's candidates links the answer to the file itself. Decide whether the form offers the picker (a better trail, and a second place to get a record wrong when the library's copy is not the recorded one) or the typed words only, and who checks that a chosen file is the record that states the fact.

## Not part of this pass

- Any reading of a fact from a document into the profile (the installation standard from a plan, the attached units from a condominium plan): `jason.community.applicability` takes facts; it does not read them, and the console reads nothing either.
- The rows that keep their condition as prose ([../notices.md](../notices.md#when-a-row-is-required), "Rows that keep their condition as prose"); they stay in `note` until the facts exist.
- The contract reader's gate and a term's scope ([../applicability.md](../applicability.md#4-scope-stated-inside-a-document)).
- A reading for counsel (whether common-area work is a home improvement): it is a canvas item, not an intake question, and has its own screen question.
- Applying answers from the console (`jason intake --apply`) and any edit to the specification or the private facts.
- Any control that approves, adopts, or decides: the board's choice on a fact it decides is its vote at a meeting, recorded where every vote is, and the page offers only a way to put the question on the agenda.
- The confirmations queue, programs, and improvement requests: this page links to each and builds none of them.
- An owner-facing version of any band.
- The previews: the design project's authored preview for each component follows the build; fixtures will be `ui/src/components/answerword.test.tsx` and its siblings, from the sample data above.
