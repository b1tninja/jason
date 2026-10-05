# Taking documents in: questions for a person

Reading a document, jason is often unsure. It may not know which kind of document it is, whether an amendment took effect, what an OCR'd word says, or whether a difference in the hand-kept copy is a correction or a slip. jason doesn't guess. Each uncertainty becomes a question with its evidence; a person answers, and the answer becomes a record that every later run applies.

`jason sop document-intake` is the procedure.

## The queue

```bash
jason intake --scan                      # run the readers; park each uncertainty (answered ones stay answered)
jason intake                             # the open questions (--kind, --subject, --likely, --limit)
jason intake --answer ID 1 --by NAME     # a choice's number, or words; "dismiss" closes it
jason intake --likely --kind "ocr reading"
jason intake --accept-likely --by NAME   # after looking: every likely OCR reading, with its suggestion
jason intake --confirm ID --by OTHER     # a second person, for a high-stakes answer
jason intake --apply                     # answers into records: transcriptions, person-chosen kinds, facts, proposals
```

- **Records:** each question is an `Ask` (`jason.community.intake`), kept in `data/intake/asks.json`, which is private.
- **What an `Ask` holds:**
  - its kind;
  - its subject (`decl#4.15(a)`, `library:Folder/file.pdf`);
  - the question, the choices, and jason's suggestion;
  - whether the suggestion is `likely`;
  - the evidence;
  - the checklist item it serves, for an onboarding question;
  - the answer, who gave it and when, and who confirmed it and when.
- **Ids:** an ask's id comes from what it is about, so a later scan finds the same question rather than a new one.
- **Stale questions:** an open question that a later scan no longer produces is marked stale; its cause went away.

## What asks

| Kind | From | The answer becomes |
|---|---|---|
| `classify` | a library file no rule classified | a person-chosen kind (`data/library/classified-by-person.json`), which outranks every rule on the next `jason library` (`Method.PERSON`) |
| `ocr reading` | the base text's OCR against the working copy, where they differ by a few words | a transcription (`data/living/<key>/transcriptions.json`): a `Correction` of kind `TRANSCRIBED`, applied on every build |
| `before differs` | an amendment whose before words are not the document's | a decision: changed without marks (counsel), misread (transcribe), or noted |
| `readings differ` | two copies of one instrument that disagree | which reading the recorded copy supports |
| `drift` | the working copy differs from the current text in an amended section | fix the working copy, record a correction, or ask counsel |
| `orphaned note` | an annotation whose words are gone | re-anchor, keep as a general note, or resolve |
| `held source` | a source not read (changed since review, or not fetched) | review and pin the new digest, or fetch |
| `section kind` | a section of the owner's manual whose kind no rule settled | the kind the next `jason manual` run reads |
| `fact` | an onboarding checklist item a person supplies, missing or partial ([onboarding.md](onboarding.md#questions-the-checklist-asks)) | a private fact in `data/spec/<profile>.json`, a note that it is kept in Keeper, or a proposed profile change |
| `map` | a book a checklist item looks for that no document fills, or a 5200 record no folder is pinned to hold | a proposed profile change: a `.patch` under `data/onboarding/proposals/` |
| `applicability` | a fact a rule row's condition needs and no record on hand states, or one its sources disagree on (`jason applies --questions`; [applicability.md](applicability.md)) | a fact with source `answer` for the next evaluation, with who answered and when |

**Applicability questions are filed by a person.** `jason intake --scan` does not park them. `jason applies --questions` lists them, and `jason applies --file-questions` parks them.

- **One question a subject and fact.** The same missing fact for the same system is one question, however many rows wait on it. Each names the rows its answer would decide and the kinds of record that would settle it.
- **The association's standing facts.** Some rows turn on a fact about the association itself. The profile states these (`Community.applicability_facts()`); where it does not, each is one question under the subject `applies:association`:
  - its property: the kind of development, the number of units;
  - what its documents and practice settle for the notice catalog ([notices.md](notices.md#when-a-row-is-required)):
    - whether an election operating rule allows electronic secret ballots;
    - whether the governing documents require a quorum for an election of directors;
    - whether the board keeps seating by acclamation available. This one is the board's decision to record, not a reading of the documents.
- **One event's facts are not asked.** What one election decides, or whether one rule change is an emergency one, is said by the caller that knows the event (`jason notices --catalog --fact`, `jason notice-check --event`).
- **The answer.** It is the value, and after a semicolon the record that states it: `NFPA 13R; the 2006 permit`. A system's installation standard is read only with its record named, and so are the three notice facts above: `not used; Election Rules 4.2`.
- **Where an answer is read.** `jason applies`, `jason inspections`, `jason notices --catalog --fact`, and `jason notice-check` read the answers as facts beside the profile's.
- **An answer that cannot be read** as the fact is listed with why and is not used. `--apply` refuses it, and the row stays undetermined.
- **Disagreement.** An answer that disagrees with a document or the profile settles nothing. The row stays undetermined and lists both; jason picks neither.
- **Applying.** `jason intake --apply` checks that the answer reads as the fact and marks it applied. The answer itself is the record.

## Guards on every answer

- **No secret is stored.** An answer that looks like a password, a PIN or code given with its digits, a key or token given with its value, or a long token is refused before anything is written. The person puts it in Keeper and answers with the Keeper record's name. A link is not a token, so a Drive folder is answered with its link. The words of a page may say "code" with a number, so an OCR reading is held only to the token rule.
- **A high-stakes answer needs a second person.** Some answers decide which text is in force or whether an instrument took effect: `standing`, `readings differ`, `before differs`, `drift`, and a fact marked high stakes. `--apply` refuses each until `--confirm ID --by NAME` records a second person, who is not the one who answered. A new answer clears the confirmation.

## The session

The queue is ranked by what each answer unblocks (`jason.community.intake_rank`), and `jason onboard` shows it beside the checklist and the stage gates ([onboarding.md](onboarding.md#the-session)). `jason onboard --questions` lists more.

- **Unblocks.** Each question gets an `Unblocks`. It names:
  - the legal clocks it affects: a schedule assignment, notice requirement, or notice provision that cites the section, or a fact that sets a clock;
  - the checklist items it would move to present;
  - the stage gates it holds closed;
  - the books or 5200 records it fills;
  - the sections it touches, with their weighted citations.
- **Citations.** A section's weight counts what cites it, read as `jason cite --most-cited` reads it: a conflict row 4, a notice provision or requirement 3, a document duty or schedule assignment 2, another document's cross-reference 1, anything else 0.5. A citation of the section itself counts in full, of the section enclosing it half, of its whole article a fifth, and of a part inside it a quarter. A whole article's own words are a heading, so its parts' citations do not count for it.
- **Priority.** One function, `priority`, with its weights as named constants, sorts the queue in tiers:
  1. a legal clock;
  2. a missing checklist item, then a partial one;
  3. a stage gate;
  4. a heavily cited section;
  5. a book or record filled with no item behind it, which counts as fifty citations;
  6. quality alone.

  Each tier's cap stays below the next tier's single step.
- **OCR readings.** An OCR reading reaches the clock tier only when it could change what the section means: a digit differs, or the two readings are words a person must choose between. One that differs only in spacing, case, or punctuation, or a likely real word for a non-word, keeps its citations and gives up the clock. One in a section nothing cites sinks to the bottom. An orphaned note, a section's kind, or a held source decides no words, so it never reaches the clock tier.
- **The same paths.** `jason onboard --answer`, `--confirm`, and `--apply` are this queue's own answer, confirm, and apply paths.

## Manual reading where OCR fails

- **Two readings make the question.** A recorded copy's OCR misreads words ("pcnnitted", "Condommmms"). The hand-kept working copy usually has the right word. Where the two differ by up to three words in a section no amendment set, jason asks which one the page says.
- **When a suggestion is likely:**
  - the working copy has real words that look like the extract's non-words;
  - the difference is spacing only;
  - a deletion removes nothing but non-words, such as a garbled running footer.

  A deletion of real words, such as a caption run into the text, is never likely.
- **The person reads the page.** A `TRANSCRIBED` correction records who read it and when. Unlike an editorial correction, it may restore a number that OCR misread, because it is a reading of the page and not an edit.
- **More readers.** `jason intake --scan` also reads each provision with the text rules ([ocr-correction.md](ocr-correction.md)):
  - an English word list and a language model of clean legal text split run-together words and read misread ones;
  - layout rules drop stray bars and page numbers.

  An OCR question is `likely` only when two independent readers agree (the working copy, the text rules, the local model, the vision model) and the change touches no number or operative word without the page itself. Each question's evidence names every reader and what it read.
- **Copy slips.** Where the working copy keeps the OCR's own slip ("ofthe"), the rules' reading is asked too.
- **One-reader suggestions** are kept in `data/living/<key>/ocr-suggestions.json` rather than asked.
- **Second readers.** `--model` adds the local model as a second reader, and `--vision` adds the page's crop of a number or operative word in doubt.
- **The library.** `jason intake --library-ocr` writes the same suggestions beside the library's OCR texts and ranks the worst-read files.

## Not built yet

- Showing the page's crop beside an OCR question for the person answering it (the vision reader already crops the word).
- Questions from the duties and notice catalogs, and from a new file's standing (is it signed? recorded?).
- Applying the answers to `before differs`, `drift`, and `orphaned note` beyond recording them.
- Applying a profile proposal: a person reviews and applies each patch; jason does not track which were applied, except that a question no scan asks again stays applied.
