# Duties in the governing documents

What the governing documents require, forbid, and allow, read from their words: each duty, prohibition, permission, right, and condition, with who bears it, what sets it off, and when it is due. A reading is a lead for a person to review. It is never a rule row, and nothing here decides what a provision means: where the words are unclear, it is a question for the board or counsel ("Where the law is silent, write it down" in [AGENTS.md](../AGENTS.md)).

| Piece | Where | What it does |
| --- | --- | --- |
| `DocumentDuty`, `DutyKind`, `Bearer`, `Deadline`, `ReviewStatus` | `src/jason/community/deontic.py` | one norm read from a section: kind, bearer, marker, action, trigger, deadline, recurrence, conditions, quote, offsets, provenance, review |
| the phrase grammar | `deontic.read_passage`, `deontic.read_outline` | reads a section's sentences for the drafting forms below |
| the model reader | `src/jason/community/duty_model.py` | the free reading and the hybrid review, with the quote check |
| the store and the checks | `src/jason/tasks/document_duties.py` | `data/duties/<key>.json`, reviews, provenance, what tracks a timed duty, the scorer |
| the command | `jason duties --documents KEY` (`src/jason/commands/document_duties.py`) | lists, filters, reviews |
| the measurements | `scripts/eval_duties.py`, the gold sets in `data/duties/gold/` | precision and recall of each strategy |

## How it relates to the other duty records

- `jason.community.obligations.Obligation` is a **recurring deadline the association tracks**, with the evidence that shows it done (PayHOA payments, a report's date). It is a specification row a person writes.
- `jason.community.duties.Duty` is a **manager's duty anchor** (meetings, records, assessments ...) mapped to the statutes and the questions to ask the documents.
- `DocumentDuty` is a **reading of a document's words**. It is a sibling of `Obligation`, not an extension: it has a quote, offsets, a marker, and a review status, and most readings have no deadline at all. A timed `DocumentDuty` is checked against the `Obligation` rows, the board calendar, and the notice catalog (below); when a person decides one should be tracked, the decision becomes an `Obligation` row in the profile, written by a person.
- The notice catalog ([notices.md](notices.md)) holds what the statutes require of each notice (`NoticeRequirement`) and what the governing documents say about notice (`NoticeProvision`, `Community.notice_provisions()`). A duty to give notice found here is a lead for that catalog: `jason duties --documents KEY --notices` lists each one with the notice provision or rule that already covers its section, and leaves the catalog to the people who keep it.

## The phrase grammar

A section's own words (its subsections are separate passages, `reference_model.passages`) are split into sentences, at a line break or a full stop that does not end an abbreviation ("Sec.", "Cal.") or an initial. In each sentence the grammar finds its markers and classifies each one.

| Kind | Markers |
| --- | --- |
| duty | shall, must, is required to, is obligated to, is responsible for, agrees to, covenants to, it is the duty of, shall be responsible for, is due and payable, will be required; a passive "shall be given", "shall be made available" |
| prohibition | shall not, must not, may not, cannot, No ... shall, nor shall, in no event shall, is prohibited, is not permitted, shall be prohibited |
| permission | may, can (with a party as subject), shall have the power or authority to, is or shall be authorized to, is permitted, the power and authority to, in its discretion |
| right | shall have the right to, is entitled to, has the right to, the right of the Board to, shall have the opportunity to, shall not be denied |
| condition | shall be subject to, shall be effective or valid or binding, shall be delinquent, shall become effective; a list item under "if all of the following conditions are met:"; agrees to receive |
| definition (not a norm) | shall mean, means, shall have the meaning, shall be deemed, shall be treated as, shall be a ..., shall be appurtenant to, shall have one vote, shall pass, shall remain, shall not include, shall only apply to, shall hold office |

The traps it is written around, each with a test in `tests/test_deontic.py`:

- **"shall" in a definition or a status.** "'Member' shall mean an Owner", "shall be a Member", "shall be appurtenant to", "Membership shall pass", "shall have an undivided interest" are not norms. After "shall be" the next word decides: an article, a status word, or a capitalized noun is a status; a participle is a passive duty; "responsible", "liable", "required", "current", "in writing", "in the custody of" are duties; "subject to", "effective", "valid" are conditions. "Shall include" is a duty when the subject is a notice, statement, report, ballot, agreement, or the like (it sets what the document must contain), and a definition otherwise.
- **A power is not a duty.** "The Board may", "shall have the power to", "shall have the absolute discretion to", and "in its sole discretion" are permissions. A bylaw that defines "may" as discretion and "shall" as mandatory, as many do, states the same convention.
- **A modal inside a relative or conditional clause.** "as the Board may from time to time establish", "which may become a nuisance", "any service he or she may render", "where these rules may be accessed", "Unless the Board shall designate otherwise", "stating that the owner may address the Board", and a modal inside quotation marks (words a notice must print) are skipped. "may be exposed", "may occur", "may be obtainable" are possibilities, not powers.
- **Passive duties.** "Notice shall be given" has no bearer in its words: the reading is a duty with bearer `unstated` and `passive` set, unless an agent follows ("by the Secretary"). When a party is the subject of a passive that delivers something to it ("Members shall be given notice", "a committee member may be reimbursed", "no director may be removed"), the party receives the act and is not its bearer. Assessments that "shall be paid" or are "due and payable" are the owners'.
- **Negation scoped over a subject or a list.** "No Owner shall", "no Unit, or any portion thereof, shall" after a leading clause, "nor shall anything be done", "Under no circumstances shall" are prohibitions; a "which shall" inside such a sentence describes what is forbidden and is not a norm of its own.
- **Lead-ins.** A sentence ending in a colon or breaking off unfinished ("The Inspector of Elections shall:", "the Association may:") passes its kind and bearer to the list items under it, whether they are subsections ("(a) Deliver the ballots ...") or lines in the same section. A table's cells ("$25 or warning") are not items. A list under "if all of the following conditions are met" is a list of conditions.
- **Recitals and headings.** "WHEREAS" sentences, all-capital headings, and a section's caption line are not read for norms; "May" followed by a date is the month.

For each norm the grammar also reads:

- **bearer**: the first party named in the subject (after a leading clause, the words after its last comma); a pronoun takes the bearer of the clause before it. Parties: association, board (or a director), officer, committee, inspector of elections, manager, owner, member, occupant (resident, tenant, guest), candidate, declarant, mortgagee, person, other (a court or public agency), unstated.
- **deadline** (`Deadline`): within N days after an event; at least N days before an event; between N and M days before; not later than; N days' notice; on the first day of each month; for a period of N years; for the current year and the prior N years. Number words and "(30)" forms are read. The relation, amount, unit, and event are kept with the words.
- **recurrence**: annually, each year, on an annual basis, an annual report or budget or meeting, quarterly, semiannually, monthly, at least once every N years. The words after the marker are read first, so "levied on an annual basis and shall be paid in monthly installments" gives the payment a monthly recurrence; a duty coordinated with the one before it ("review the study annually and shall consider adjustments") shares its timing.
- **trigger** (upon, after, following, once, when, if, in the event, prior to), **conditions** (unless, except, provided that, subject to, without the prior approval of, only if, notwithstanding), **discretionary** (in its sole discretion, as it deems), and **notice** (the act's own verb gives, mails, delivers, posts, distributes, or transmits something, or the subject is a notice or ballot whose content is set; "without notice" is not one).

**Provenance.** When the document is kept as amended ([living-documents.md](living-documents.md)), each reading carries `set_by`: the instrument that last set its section's words, from the living document built from the copies on disk. A reading of a section an amendment restated is marked with that amendment. The words read are the outline's (the working Doc); where the working copy and the amended text differ, `jason living KEY --working` says so.

## The local-model strategies

`duty_model.METHOD` is the shared part of both prompts: the kinds with their markers, the things that are not norms, the bearers and the passive rule, and the fields. It names kinds and questions, never a section number or a figure (`tests/test_deontic.py` checks), following [the prompt convention](../src/jason/community/prompts.py). The examples are invented.

- **Free reading** (`DutyModel.read`): the method, four worked examples, where the section sits (its document, number, caption, and the lead-in of the list it belongs to), and its words. The answer is JSON (`READ_SCHEMA`, through Ollama's `format`), one object per norm with a verbatim quote of 4 to 25 words.
- **Hybrid review** (`DutyModel.review`): the method, the section, and the grammar's candidates, each sentence with its marker in `[[ ]]`. For each candidate the model says whether it is a norm, its kind, bearer, trigger, deadline, recurrence, and notice, and it lists in `missed` any norm no candidate covers (`REVIEW_SCHEMA`).
- **Hybrid fill** (`merge_review(..., fill_only=True)`): the same review, but only the bearer is taken, and only where the grammar left it unstated. The grammar's kinds and timing stay.

Nothing the model says is kept on its word: a proposal is kept only when its quote is in the section (folded for case, spacing, quotation marks, and dashes, `reference_model.find_quote`) and its kind and bearer are ones `deontic` defines. The model is asked only through an Ollama on this machine, one request at a time under the GPU lock, after `jason.local_ai.preflight`; answers are cached by passage and words in `data/duties/model/`, with the markers of the candidates asked, so a later change to the grammar cannot shift the verdicts onto other candidates.

## The gold sets and the measurements

**`data/duties/gold/gold.json`**: 59 passages labelled by hand on October 2, 2026, before the grammar was written. 24 were drawn at random from the declaration, bylaws, election rules, owner's manual, policies, and a resolution (seed 7); 35 were chosen for variety and traps: definitions, statements of status, "may" powers, passive notices, lists under lead-ins, deadlines, disclaimers, a precatory "should". By document: declaration 20, bylaws 16, owner's manual and rules 9, election rules 7, policies 6 (collection, enforcement, parking, a license-plate camera policy), resolution 1. 143 items: 125 scored (72 duties, 35 permissions, 10 prohibitions, 5 rights, 3 conditions; 24 with a deadline, 14 with a recurrence, 30 notices) and 18 optional (a restrictive clause's "which the Owner is obligated to pay", a content requirement, a precatory "should"), which count neither way. Six passages state no norm. Even-numbered passages were used to tune the grammar (dev); odd-numbered ones were held out (test). One label was corrected afterwards for consistency (a records-retention period labelled as a deadline, as the same pattern was elsewhere).

**`data/duties/gold/gold-fresh.json`**: 18 passages drawn at random (seed 2026) after the grammar was frozen and labelled before any reader saw them: 39 items, 26 scored. Five state no norm.

**Scoring** (`document_duties.evaluate`): a reading matches a gold item when its marker lies inside the item's quote (three characters either side), one to one, same kind first. Precision and recall count a match only when the kind agrees (or is one of the item's defensible alternatives); a reading of the wrong kind is a false finding and a miss. Bearer, deadline (present or not), recurrence (months), and notice are scored on the matched readings. Definitions a reader reports as definitions are not scored; a definition reported as a norm is a false finding.

| Strategy | Gold, held-out half | Gold, all 59 | Fresh 18 | Bearer right | Deadline right | Notice right |
| --- | --- | --- | --- | --- | --- | --- |
| Grammar, first frozen version | P 0.90, R 0.92 | (tuned on dev) | | 29/47 | 44/47 | 45/47 |
| Grammar, final | P 1.00, R 0.98 | P 1.00, R 0.98 | **P 1.00, R 0.92** | 88/123; fresh 15/24 | 121/123; 24/24 | 121/123; 20/24 |
| Model, free reading | P 0.82, R 0.82 | P 0.78, R 0.80 | P 0.80, R 0.77 | 87/100; 17/20 | 94/100; 19/20 | 87/100; 16/20 |
| Hybrid review (model's kinds) | P 0.90, R 0.88 | P 0.89, R 0.86 | P 0.91, R 0.77 | 94/107; 18/20 | 99/107; 20/20 | 86/107; 13/20 |
| **Hybrid fill (grammar's kinds, model's bearer where unstated)** | P 1.00, R 0.98 | P 1.00, R 0.98 | **P 1.00, R 0.92** | **114/123; fresh 20/24** | 121/123; 24/24 | 121/123; 20/24 |

The model: `qwen3.5:9b` on Ollama 0.35.0 (CUDA, Q4_K_M), thinking off, temperature 0, a 16,384-token window, the JSON schema as `format`. Median 1.1 seconds a passage, at most 8.5; 77 passages in under two minutes of model time for each strategy. The shared `qwen3.6:27b` was not tried: `preflight` refused it (about 25 GB of Windows commit needed, 17.4 GB free, with no model loaded). Rows are in the trials table of [document-tools.md](document-tools.md).

**The gold sets overstate the grammar across the whole corpus.** Three random samples of 40 readings from all the governing documents, judged by reading each sentence, had 34, 29, and 35 of 40 of the right kind (about 82%); the first two were drawn before the fixes they prompted, the third after. The gold sets hold few of the sentences that go wrong: a list item under a lead-in that states a purpose, a scope, or a set of methods ("the assessments shall be used for: ...", "the following methods:"); a consequence stated as "shall bear interest"; a negative scope inherited from a parent section. Read precision as about four in five for a document no one has reviewed, and higher for the kinds of sentence the gold sets cover.

**What the numbers say.**

- The grammar is the reader. On the passages it was not tuned on it found 92% of the norms with no false finding of the wrong kind, and its deadlines and recurrences are nearly always right (it reads them from the words).
- Its weak field is the bearer: about a third of the norms state their bearer only by implication (passive notices, "the hearing shall be held", "minutes shall be made available"). The model is good at exactly that. Filling only the unstated bearers lifts bearer accuracy from 72% to 93% on the gold set and from 62% to 83% on the fresh set, without moving precision or recall.
- The model is not good at deciding what is a norm. Free, it splits a prohibition's descriptive clauses into separate prohibitions, reports statements of status and "shall include" definitions as duties, calls passive duties conditions, misses list items under a lead-in, and gives "annually" as a deadline. As a reviewer of the grammar's candidates it is better (P 0.89) but still drops true norms the grammar kept. Hence the hybrid fill.
- Notices are under-flagged by every model strategy (it reads "distribute ... annually" or "provide a copy" as not a notice).

## The command

```
jason duties --documents bylaws                     # read (the first time) and list the norms
jason duties --documents --read                     # reread every governing outline; reviews are kept
jason duties --documents --fill-bearers --model qwen3.5:9b   # the hybrid fill for unstated bearers
jason duties --documents --timed --untracked        # timed duties nothing tracks
jason duties --documents ccrs --notices             # duties to give notice, with the notice provision or rule that covers each
jason duties --documents ccrs --bearer owner --kind prohibition
jason duties --documents bylaws --review "bylaws#9.3:90605e5bc1" --status confirmed --tracked-by "jason reserve-study"
jason duties --documents bylaws --review ID --status corrected --set-bearer board --note "the board holds its hearings"
```

The store is `data/duties/<key>.json` (private, with the rest of `data/`): the readings, and the reviews by reading id. A reading's id is a digest of its document, section, words, marker, kind, and action, so a reread keeps the reviews of readings whose words did not change; a review whose reading is gone (the words changed) moves to `orphaned` for a person rather than vanishing. A bearer the model filled stays with its reading across rereads.

**What tracks a timed duty.** `--timed` and `--untracked` list duties with a deadline or a recurrence and what carries each, in order: a person's `--tracked-by`; for a notice duty, a `NoticeProvision` the notice catalog holds for its section; an `Obligation` row whose name shares two words with the duty; a board calendar event (meeting notice, hearing notice, hearing decision, regular meetings); jason's reserve-study and insurance models; a `NoticeRule` whose title shares two words. Word overlap is a lead, not a match: a person confirms it with `--tracked-by`, or adds the `Obligation` row the duty needs.

## How a person reviews

1. List a document's unreviewed norms (`--unreviewed`), or start with what matters: `--timed --untracked`, `--notices`, `--kind prohibition --bearer owner`.
2. Read the sentence in the document, not only the quote: a lead-in, a definition elsewhere, or an amendment can change it. The `set by` field names the amendment that set an amended section.
3. Record the verdict: `--status confirmed`; `--status corrected` with `--set-kind`, `--set-bearer`, or a note; `--status rejected` for a reading that is not a norm. A correction is kept beside the reading, not written into it.
4. For a timed duty, say what tracks it (`--tracked-by`), or propose the `Obligation` row it needs to the person who keeps the specification. For a notice duty, hand it to the notice catalog ([notices.md](notices.md)).
5. A discretionary power read as a duty, or a duty read as a power, is the most consequential error: "may" binds no one, and "shall" does. When two documents disagree on that point (a bylaw's "shall" and a resolution's "may" on the same act), it is a finding for the conflict register, not a reading to correct.

## Failure modes to expect

- **Lists.** A lead-in's kind passes to items that are not norms when the lead-in states a purpose, a scope, or a set of methods; a long list's items are fragments ("solar devices, and"). Review list items with their lead-in.
- **OCR and run-together text.** A full stop followed by an OCR'd "ln" for "In" does not split the sentence, so a deadline of the next sentence attaches to the norm before it.
- **Present-tense rules.** "Parking is permitted in garages only", "Owners leasing their unit retain their voting right", "Any assessment is delinquent if not received ..." state rules without a modal; the grammar reads "is permitted" and "is due and payable" but not the rest.
- **"will" and "should".** Owner's manuals often write rules with "will" ("vehicles will be towed") or "should". The grammar reads only "will be required"; "will not be accepted" is missed. "Should" is treated as precatory.
- **Bearers by inference.** A pronoun takes the bearer of the clause before it, which is sometimes the wrong party ("it must be sent by mail" after a sentence about the owner's right to attend).
- **Model drift.** A different model or prompt needs a new run of `scripts/eval_duties.py`; record it in the trials table.
