# Handoff: what applies to the association, and the questions a person answers

For the design pass on the components that show **whether a rule row reaches this association**, and **what a person must settle when jason cannot tell**. The data exists today: `jason applies` (each life safety obligation's answer for each system, and each building's record under Civil Code 5551), `jason applies --questions` (the questions the undetermined answers raise, with each one's state in the intake queue), and `jason notices --catalog --fact FACT=WORD` (the notice catalog's rows that are required only for some events). Behind them: `jason.community.applicability` (the three answers), `jason.community.applicability_asks` and `jason.tasks.applicability_asks` (the questions and the queue), `jason.community.notice_catalog.applicable` (the catalog's three groups), and `jason.community.elevated_inspections` (the per-building record). The design is settled in [../applicability.md](../applicability.md) and [../notices.md](../notices.md#when-a-row-is-required); the queue in [../intake.md](../intake.md#what-asks). No loader serves them yet ("Where it goes" lists the ones to add), and the intake answer route is built.

The format follows the earlier handoffs ([handoff-held-setup-roster.md](handoff-held-setup-roster.md); `handoff-citations.md`). The words on screen follow [content/style.md](content/style.md), the patterns [content/patterns.md](content/patterns.md), and the components [components.md](components.md). The neighbours this page links to and does not repeat: [screens/notices.md](screens/notices.md) (a notice from its requirement to its proof), [screens/life-safety.md](screens/life-safety.md) (the systems, their schedule, and their reports), [screens/schedule-and-duties.md](screens/schedule-and-duties.md) (the schedule and "record done"), [screens/onboarding.md](screens/onboarding.md) (the session's questions and `QuestionCard`), and [screens/community-facts.md](screens/community-facts.md) (the assumed defaults of every unit, a different kind of fact).

These components pair with what the console already has: `Pill`, `Recitation` and `ReadingLabel`, `QuestionCard` and `SecondConfirm`, `Confirm`, `Command`, `DataTable`, `Card`, `Tabs`, `DueDate`, `Evidence`, `Caveats`, `EmptyState`, and `RemoteView`. Build new parts only where the table says so.

## The idea in one line

A rule row applies, does not apply, or is **undetermined**; the first two name the fact that decided them and where it came from, the third names the fact that is missing and becomes a question a named person answers with the record that states it, after which the reading is computed again. Nothing is read as "does not apply" because nobody has said.

## The components

| Component | Where it renders | Data | States to design |
| --- | --- | --- | --- |
| `AnswerWord` (a `Pill` preset) | everywhere a row's answer appears: `#/applies`, `#/life-safety`'s schedule, `#/notices?catalog=` | a verdict's `answer` | the three words below; beside each, the deciding or missing fact in text |
| `VerdictRow` | under any `AnswerWord` that opens; the row's own page | a `verdict` (`describe`, `deciding[]`, `missing[]`, `conflicting[]`) | applies (the condition in words, then "decided by" each fact with its source); does not apply (the same, the deciding fact first); undetermined with facts missing ("unknown:" each fact's topic); undetermined with sources disagreeing (a `Discrepancy`, both values with their sources, "jason picks neither"); a partial set ("at least inspection, testing"); a row with no condition ("always") |
| `SourcedFact` | inside `VerdictRow`, `StandingFacts`, `BuildingInspectionRow` | one `FactValue` (`fact`, `value`, `source`, `where`, `partial`) | from the profile (its `Community` method); from a document (the page or reader); from a person's answer (the question's id, who, when, the record named, or "no record named"); the date asked for; partial ("at least …"); not on record |
| `StandingFacts` | `#/applies`, top card | `facts[]` from the profile and the queue's answers about the association | every fact stated; some answered, some stated; a fact not on record with its question; a fact stated twice (profile and answer) that agree; that disagree (`Discrepancy`); none stated (the profile sets `applicability_facts()` to nothing) |
| `FactQuestionRow` (a `QuestionCard` preset) | `#/applies`'s Questions band; the onboarding session's next questions; the dock's Ask | one question from `applies --questions --json` with its queue state | the states in "The question row" below: not filed, open, answered (by whom, when), answered and not read (why), answered and waiting on a second person, answered and in use, disagreement, dismissed, stale; a question with choices; one entered with its record (no choices, the semicolon rule shown); the question of which systems there are |
| `EventFactsPicker` | `#/notices` (the catalog band) and `#/applies`'s Notices band | the per-event facts, each a closed set with the statute's words as labels | nothing said (every conditional row undetermined); one fact said (the three groups, and the rows set aside for another kind of event); two said for one event (a rule change's subject and kind); a standing fact the profile does not state (the row stays undetermined and names the question); a word not in the set (refused, the set listed) |
| `CatalogGroups` | under `EventFactsPicker` | `notice_catalog.applicable` as the three groups, plus the rows set aside | each group with its count, applies first; a group with none ("Does not apply: not required (0)"); the set-aside rows with the fact each turns on; a row's clock and delivery kind as `jason notices --catalog` prints them |
| `BuildingInspectionRow` | `#/applies`'s Buildings band; the dock's Deadlines (its row) | one building from `applies --json`'s `buildings[]` | reaches: applies, does not apply (the deciding fact), undetermined (the missing fact); (l) and (k) each a word with its why; last inspected, or "no inspection on record"; next due as `DueUnder`; the questions for this building; a record with no buildings at all |
| `DueUnder` | inside `BuildingInspectionRow`; the dock's Deadlines | a building's `due` (`day`, `under`, `question`) and its `standing` | computed under (b)(1), (i) from an inspection; under (k) from a certificate of occupancy; under (i), January 1, 2025, for the rest; **date not on record** with the question that stands in the day's place; upcoming, due soon, overdue beside the date |
| `Discrepancy` | `VerdictRow`, `StandingFacts`, `FactQuestionRow` | two or more `FactValue` for one fact | the same component the life-safety handoff proposes for sources that disagree: each value with its source, never a pick; the next step is a question or a correction to the specification |

## The vocabulary

Every state is a word from the code (`Answer`, `Source`, `AskStatus`, `Reach`, `Standing`), so the console and the terminal agree, and no state is color alone. Keep the words.

**The three answers** (`applicability.Answer`):

| Word | `answer` | Meaning | What the row shows beside it |
| --- | --- | --- | --- |
| applies | `applies` | the condition holds for the facts on hand | the deciding facts, each with its source |
| does not apply | `does not apply` | a fact decided it does not | the deciding fact first ("decided by the system: backflow prevention assembly (profile, …)") |
| undetermined | `undetermined` | a fact is missing, or two sources disagree | "unknown: " the fact's topic, or "sources disagree: " both values; and the question |

Undetermined is never styled as a failure and never grouped with "does not apply". Its glyph, if one is used, is a question, not a warning.

**Where a fact came from** (`applicability.Source`): profile, document, answer, date. Each is written out ("profile, Community.life_safety_systems(): sprinklers-a"), never an icon alone. A set a document gave is "at least …" (`partial`).

**A question's state in the queue** (`applicability_asks._state`): not filed · open · answered by NAME, DATE · answered by NAME, DATE, not read · answered by NAME, DATE; a second person confirms it · answered by NAME, DATE; the sources disagree, so it is not settled · answered by NAME, DATE; noted for the specification · dismissed by NAME, DATE: the rows stay undetermined · stale: filed, and asked again.

**A building's subdivisions** (`elevated_inspections.Reach`): (l) applies / does not apply / undetermined, (k) the same, each with its `why` in words.

**A due day** (`obligations.Standing`): upcoming, due soon, overdue, and **date not on record**. The last is a state of its own, not an empty cell: it means a person has a date to enter.

**The catalog's fourth group:** set aside. A row that turns on another kind of event than the one the person described is neither answered nor hidden; it is listed with the fact it turns on.

## The question row

An undetermined condition becomes one question a subject and fact (`applicability_asks.questions`): however many rows wait on the same missing fact for the same system, there is one question, and its id is stable from run to run. The row shows, in this order:

1. **The subject**: the system by name, the association, or a building.
2. **The question**, in the fact's own words (`ASKS`), with the statute it comes from where one does ("… (Civil Code 5115(b)(6))").
3. **What it decides**: the rows waiting on it, by name, and each one's condition in words (`rules`), so a person sees why the fact matters before answering.
4. **What would settle it**: the kinds of record (`settledBy`: "the condominium plan", "the election operating rules, or the board's resolution in its minutes"). Kinds only; which record this association holds is its own.
5. **Who can answer**: the roster person signed in; for a fact the board decides (seating by acclamation, Civil Code 5103) the row says so in the question's own words: "this is the board's decision to record, not a reading of the documents".
6. **The answer form.** A fact with a closed set offers its values as choices, except a fact that is entered with its record (`NEEDS_RECORD`: a system's installation standard, electronic voting, acclamation, the directors' election quorum, elevated elements): those show the values in the words and one field, with the rule "Answer with one of … and, after a semicolon, the record that states it". A number asks for a whole number; a date for `YYYY-MM-DD`. The record field is labelled "The record that states it" and is required for those facts; for the rest, "if one does".
7. **What the answer becomes**: "Read as a fact with source *answer*. Where it disagrees with the specification, the row stays undetermined with both named." And: "The answer goes in the intake queue (`data/intake/asks.json`), never the specification."

**Answering is a write of a person's record.** It goes through the write guard as a `Confirm` in the signed-in person's name: **Save the answer as Jane Example** (the name pre-filled from "Signed in as"; 3.3.7), with the question, the answer, and the record restated above the button. The route is the built one, `POST /api/write/intake/<id>` with `{answer, by}` (`jason.web.extra.onboarding_setup.write`, behind `jason.api.answer_intake_question`), which refuses an answer that looks like a secret and stores nothing. The CLI equivalent is `jason intake --answer ID TEXT --by NAME`. Then the band reads `applies` again and the rows that waited on the fact move groups: the design shows the recomputation as a status message ("Answered by Jane Example. 3 rows now apply; 1 still undetermined."), never as a silent change.

**A question not yet in the queue** is "not filed": the answer route cannot take it (only onboarding's questions are parked on answer). The row shows the `Command` `jason applies --file-questions`, or, if the design takes decision 2, **File 6 questions as Jane Example** behind `Confirm` (a write to the queue under the store lock; a question already there keeps its answer).

**A second person.** A fact in `CONFIRMED` (empty today) waits for a second person: the row then shows `SecondConfirm` (the field starts empty, refused for the name that answered; `POST /api/write/intake/<id>` with `{confirm: true, by}`; `jason intake --confirm ID --by NAME`).

**An answer not read** (not one of the set, no record where one is required, not a date) is shown with why, in the queue's words, and the form again. Nothing is guessed from it.

**Dismiss** is an answer ("dismiss"): the rows stay undetermined, and the row says so.

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
- **Does not apply** (not required): the fact that decided it ("decided by the election: vote on an assessment").
- **Undetermined** (the facts do not say, which is never "not required"): each missing fact with how it is settled. A per-event fact: "say it with the picker". A standing fact: "a standing fact: the profile states it, or a person answers it", with the question linked. A row can be undetermined for both at once.
- **Set aside**: rows that turn on another kind of event than the one described ("turns on: board_meeting"), listed, not answered.

With nothing said, every conditional row is undetermined and the page reads as `jason notices --catalog --required`. A standing fact the picker cannot set shows as a locked line with its source: "electronic voting: used, with members opting in (profile, the election operating rules)" or "not on record: question d6efe4141c". The picker writes nothing: the facts said are the page's own state (and the query string), never stored.

## The per-building record

Civil Code 5551 is asked of the association once (`ELEVATED_ELEMENTS_INSPECTION`: a condominium, elevated elements the association maintains or repairs, three or more attached units in a building). Two subdivisions are about one building each, so the record is per building (`Community.elevated_elements_inspections()`, from the private facts). The band recites first, then shows each building.

**Recited words**, from the shelf (`jason cite "CIV 5551"`, read October 5, 2026; the 2025 publication of the code, `authorities/CIV/CIV-5550-5580.md`, amended by Stats. 2025, Ch. 516, Sec. 5). The console takes them from the shelf at render, with the version in force and the caveat, never from this page:

- (b)(1): "At least once every nine years, the board of an association of a condominium project shall cause a reasonably competent and diligent visual inspection to be conducted by a licensed structural or civil engineer or architect of a random and statistically significant sample of exterior elevated elements for which the association has maintenance or repair responsibility."
- (i): "The first inspection shall be completed by January 1, 2025, and then every nine years thereafter in coordination with the reserve study inspection pursuant to Section 5550."
- (k): "The inspection of buildings for which a building permit application has been submitted on or after January 1, 2020, shall occur no later than six years following the issuance of a certificate of occupancy."
- (l): "This section shall only apply to buildings containing three or more attached multifamily dwelling units."
- (e)(5)(A), the first page of the report: "The date of inspection."

**Each building's row** (`BuildingInspectionRow`):

| Line | From | Shown as |
| --- | --- | --- |
| Reaches it | `reaches` (the section's condition with the building's own units and responsibility over the association's facts) | an `AnswerWord` with the deciding or missing fact |
| (l) | `unitsRule` | "(l): applies (the most attached multifamily dwelling units in one building: 12 (profile, …))" or "(l): undetermined (the number of attached multifamily dwelling units is not on record)" |
| (k) | `permitRule` | "(k): applies (the permit application of 2021-02-01 is on or after 2020-01-01)", "does not apply (… is before …)", or "undetermined (the building permit application's date is not on record)" |
| Last inspected | `inspectedOn`, `inspector`, `license`, `licenseNumber`, `report` | "2024-05-06 by Pat Example, licensed architect C-00000; report: Example report 2024", or "no inspection on record"; an inspection with no license: the question |
| Next due | `due` | `DueUnder`, below |
| Questions | `questions[]` | each as a line, and each a `FactQuestionRow` where it is one fact (the date questions are entered on the record, not in the queue: decision 4) |

**`DueUnder` is a computed clock, labelled so.** It shows the day, the subdivision and count it comes from, and a `ReadingLabel` "computed by jason from the record; the words above govern":

- an inspection on record: nine years from it ("(b)(1), (i): 9 years from the inspection of 2024-05-06" → 2033-05-06);
- none, and (k) applies: six years from the certificate of occupancy ("(k): 6 years from the certificate of occupancy of 2022-08-15" → 2028-08-15); with no certificate date, **date not on record** and "enter it from the certificate";
- none, and (k) does not apply: "(i): the first inspection by 2025-01-01", already past, overdue;
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

A `FactValue` is always `{fact, value, source, where}` with `partial: true` when a set may leave values out. The console reads the words as they are; it never maps a word to another.

## What the design must keep

- **Three answers, never two** (principle 8, and [../applicability.md](../applicability.md#2-three-answers-never-two)). Undetermined is its own group, its own word, and its own glyph. A screen that counts "applies" and "does not apply" and drops the rest is wrong. A notice row undetermined is never "not required"; an obligation undetermined is never "nothing due".
- **Recite first, label the reading** (principle 2). The section's words come from the shelf through `Recitation`, with the version in force and the caveat, before any row. A condition's `describe` is jason's reading of the row, labelled so ("the rule row's condition, in jason's words"); a due day is "computed". Nothing on these screens is labelled as decided except a person's answer, with the person's name.
- **The deciding fact is always shown with its source.** "Does not apply" without "decided by …" is a bare conclusion; the design never shows the word alone where there is room for the fact, and on a chip the fact is the accessible name and the hover card.
- **A person's answer is a fact with source *answer*, not a correction.** Where it disagrees with the profile or a document the row stays undetermined with both named (`Discrepancy`); jason picks neither, and the console has no "use this one" control. The fix is a corrected specification or a new answer.
- **A fact entered with its record.** For a `NEEDS_RECORD` fact the form refuses an answer with no record named, in the queue's own words ("no record named: it is entered with the record that states it, after a semicolon"). No choice buttons for those facts: a number would answer without the record.
- **Nothing writes without a named person** (principle 4). Saving an answer, confirming one, and filing the questions are `Confirm`s in the signed-in person's name through the write guard, or `Command`s. The picker writes nothing. Applying answers to the specification stays a terminal command (`jason intake --apply`), shown with the count, as the onboarding screen does.
- **"Date not on record" is not a date.** `DueUnder` never shows a placeholder date, a dash styled as a date, or "overdue" for a building whose counting date is unknown. The question stands in the day's place.
- **The event facts are the page's, not the association's.** What one election decides is said for that catalog read and never stored as a standing fact. The standing facts are read-only in the picker and point to their question.
- **Set aside is shown.** The catalog never hides a row because it turns on another kind of event.
- **No color-only meaning.** Every word in "The vocabulary" is text; a count in text beside any bar; a `Discrepancy` is two lines of text, not a red mark.
- **Privacy by level** (principle 6). The association's facts and the law are P0. A `where` that quotes an email or a note may name a vendor or a person: P1, shown to roster people. A person's answer names a roster person (`answeredBy`): P1. A building's inspector and license number come from the private facts (`data/spec`): shown as "a licensed architect" with the report's name outside the private view, the name and number inside it, logged (decision 6). A document's page in a `where` is a `DocRef` where the loader can give one. Nothing here is P4. The owner view shows none of these bands.

## Where it goes

Routes are proposed, consistent with [information-architecture.md](information-architecture.md#where-the-proposed-screens-go); none exists yet.

- **Governance → What applies** (proposed): `#/applies`, board-only (`owner: false`). Bands in order, as `Tabs`: **Facts** (`StandingFacts`), **Systems** (each system's card with its three groups, the rows reaching no system listed as "reaches none of the listed systems"), **Buildings** (the 5551 recitation, then a `BuildingInspectionRow` a building), **Notices** (`EventFactsPicker` and `CatalogGroups`), **Questions** (every `FactQuestionRow`, open first, with `answersInUse` and `answersNotRead` below). Query: `?subject=association` | `system:<key>` | `building:<key>` (keys and symbols only, never a name), `?as_of=YYYY-MM-DD`, `?fact=election=directors` (repeatable) for the Notices band. The header's `Command` is `jason applies` (`--questions`, `--as-of`).
- **`#/life-safety`** ([screens/life-safety.md](screens/life-safety.md)): the schedule's rows take an `AnswerWord` with the deciding fact; "needs input" there links to the system's `FactQuestionRow` in `#/applies?subject=system:<key>`.
- **`#/notices?catalog=KEY`** ([screens/notices.md](screens/notices.md)): band 1 (the requirement) takes the row's `AnswerWord` for the facts said, and the catalog band takes `EventFactsPicker`, with the same `?fact=` query as `#/applies`.
- **The onboarding session** ([screens/onboarding.md](screens/onboarding.md)): `next_questions` already lists intake kinds; a question of kind `applicability` renders as `FactQuestionRow` there too, so one answer path serves both.
- **The dock's Deadlines**: a building's row from `elevated_inspections.calendar_rows` shows `DueUnder` with its standing, and opens `#/applies?subject=building:<key>`.

**Loaders to add** (names only; nothing built; each wraps a function that exists today and derives no fact of its own):

| Loader | Route | Wraps | Notes |
| --- | --- | --- | --- |
| `applies` | `GET /api/applies?system=&as_of=` | `jason.tasks.applicability_asks.evaluate(community, data_dir, as_of)` → `SystemApplicability.as_dict()`; `elevated_inspections.records`, `base_facts`, each row's `as_dict(base)`; `association_facts` for `facts[]` | the `jason applies --json` shape, plus `facts[]` and `caveats` |
| `applies-questions` | `GET /api/applies-questions` | `applicability_asks.questions(result, tasks.applicability_asks.standing(...))`, `stored(data_dir)`, `answered` | the `--questions --json` shape, with each question's queue state as `onboarding_setup._answered` gives it (never the raw answer of a question not read, unless decision 3 says so) |
| `notice-catalog` | `GET /api/notice-catalog?fact=FACT=WORD` | `notice_catalog.conditional`, `about`, `applicable`; the `--fact` parser of `jason.commands.notices`; `tasks.applicability_asks.association_facts` | the three groups and the set-aside rows as JSON; `jason.api.notice_requirements(key)` for a row's full requirement |
| `intake` (writer, **built**) | `POST /api/write/intake/<id>` `{answer, by}` / `{confirm: true, by}` | `jason.api.answer_intake_question`, `onboarding_confirm` | the answer and the second person; refuses a secret; 401 with no one signed in |
| `applies` (writer, proposed) | `POST /api/write/applies/file` `{by}` | `tasks.applicability_asks.file_questions(data_dir, asked)` under the store lock | decision 2: a `Confirm`, or the `Command` only |

The elevated-elements dates (the inspection date from a report's first page, the permit application, the certificate of occupancy) have no write route: they are rows in the private facts, entered by a person in `data/spec` (decision 4).

## Accessibility

As [components.md](components.md#accessibility) and [content/patterns.md](content/patterns.md#accessibility-wcag-22-aa):

- **Keyboard.** Every `AnswerWord` that opens a `VerdictRow` is a `button` with `aria-expanded`; the row opens in place under it and Escape closes it, returning focus. `FactQuestionRow`'s form is native fields in a `fieldset` whose legend is the question's subject; choices are radio buttons with the value's words as labels; the record field is a text input labelled "The record that states it" and marked required where it is. `EventFactsPicker` is a group of labelled `select`s (or radio groups), one a fact, with a polite live region for the result ("3 apply, 0 do not apply, 5 undetermined, 7 set aside"). Tabs follow the tabs pattern with arrow keys; a band is reachable by its `?subject=` link too.
- **Screen reader.** The three words are the accessible name of each pill, followed by the deciding or missing fact ("undetermined: unknown: whether the association keeps seating by acclamation available (5103)"). A `DueUnder` with no day has the accessible name "date not on record" and its question; it never reads a placeholder. The recitation is a `figure` with `blockquote` and `figcaption` (the citation and version). `Discrepancy` is a list of two items, each naming its source. The recomputation after an answer is a `role="status"` message; a refused answer is `role="alert"` beside the field, tied by `aria-describedby`, with the queue's words.
- **Phone layout (< 720 px).** The tabs become a `select`; a system's three groups stack with their counts in the group headings; `DataTable`s of rows become lists of name, `AnswerWord`, and the deciding fact on one line each; the picker's selects stack with their labels above them; `BuildingInspectionRow` collapses to the building, its reach, its next due (`DueUnder`), and a disclosure for (l), (k), and the last inspection; `FactQuestionRow`'s form is full width with the `Confirm` button at the end and not sticky (2.4.11). Nothing scrolls sideways at 320 px.
- **Target size (2.5.8)**: a pill that opens, a radio, and the copy button on a `Command` are 24 by 24 CSS px or spaced to pass. **Redundant entry (3.3.7)**: the answering name comes from "Signed in as"; only `SecondConfirm`'s name starts empty. **Timing (2.2.1)**: nothing times out; a half-typed answer stays in the field across a band change. **Use of color (1.4.1)**: every state above is a word first; the glyph for undetermined is a question mark, for a disagreement two marks, never a warning triangle.

## Decisions for the design

1. **One screen or bands elsewhere.** `#/applies` as proposed gathers five bands; the alternative is no new screen, with the Systems band on `#/life-safety`, the Notices band on `#/notices`, the Buildings band in the dock, and the Questions band in the onboarding session. Decide which reads better for the manager's weekly check (`jason sop law-review` runs `jason applies` each January); the loaders are the same either way.
2. **Filing the questions.** `jason applies --file-questions` is a person's command today. Decide whether the console offers **File 6 questions as Jane Example** behind `Confirm` (a write to the queue under the store lock, with the counts new, kept, and stale shown after), or shows the `Command` only. Until filed, a question has no answer route.
3. **The answer's text.** The built onboarding loader never sends an answer's value, only who answered and when; `jason applies --questions` prints the answer. Decide whether `FactQuestionRow` shows the raw text of an answer that could not be read (needed to fix it) or only the fact it became and why it was not read, with the person who answered re-entering it.
4. **The building dates.** The inspection date, the permit application date, and the certificate's date are private-facts rows with no write route; the row's question says which record states each. Decide whether to propose a signed write (the date, the record it was read from, the person) as a new intake kind, or to keep it a terminal task with the row showing the file to edit.
5. **The picker's shape.** One `select` a fact, or the five facts as radio groups under "Describe the event". A rule change needs two facts at once; an election one, plus the standing facts it cannot set. Decide how the locked standing facts read beside the picker ("stated by the profile" versus "not on record, question …") without looking like disabled controls.
6. **The inspector's name.** 5551(f) has the report stamped or signed by the inspector and presented to the board, yet the row comes from the private facts (P3). Decide with the privacy model whether a licensed professional's name on a report presented to the board is P1 in the console; until then the design masks it outside the private view.
7. **Disagreement at a glance.** A `Discrepancy` inside a `VerdictRow` and the same disagreement as a `FactQuestionRow` are one fact seen twice. Decide how the two link without a third copy of the values.
8. **Weight of "does not apply".** Twenty-one of the fixture's thirty-six findings do not apply, most trivially (a backflow row asked of a sprinkler system). Decide whether a system's card folds that group by default with its count, keeping applies and undetermined open, so the page reads as what is owed and what is unknown.

## Not part of this pass

- Any reading of a fact from a document into the profile (the installation standard from a plan, the attached units from a condominium plan): `jason.community.applicability` takes facts; it does not read them, and the console reads nothing either.
- The rows that keep their condition as prose ([../notices.md](../notices.md#when-a-row-is-required), "Rows that keep their condition as prose"); they stay in `note` until the facts exist.
- The contract reader's gate and a term's scope ([../applicability.md](../applicability.md#4-scope-stated-inside-a-document)).
- A reading for counsel (whether common-area work is a home improvement): it is a canvas item, not an intake question, and has its own screen question.
- Applying answers from the console (`jason intake --apply`) and any edit to the specification or the private facts.
- An owner-facing version of any band.
- The previews: the design project's authored preview for each component follows the build; fixtures will be `ui/src/components/answerword.test.tsx` and its siblings, from the sample data above.
