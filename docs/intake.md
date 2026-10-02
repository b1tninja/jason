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
jason intake --apply                     # answers into records: transcriptions, person-chosen kinds
```

- **Records:** each question is an `Ask` (`jason.community.intake`), kept in `data/intake/asks.json`, which is private.
- **What an `Ask` holds:**
  - its kind;
  - its subject (`decl#4.15(a)`, `library:Folder/file.pdf`);
  - the question, the choices, and jason's suggestion;
  - whether the suggestion is `likely`;
  - the evidence;
  - the answer and who gave it.
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

## Manual reading where OCR fails

- **Two readings make the question.** A recorded copy's OCR misreads words ("pcnnitted", "Condommmms"). The hand-kept working copy usually has the right word. Where the two differ by up to three words in a section no amendment set, jason asks which one the page says.
- **When a suggestion is likely:**
  - the working copy has real words that look like the extract's non-words;
  - the difference is spacing only;
  - a deletion removes nothing but non-words, such as a garbled running footer.

  A deletion of real words, such as a caption run into the text, is never likely.
- **The person reads the page.** A `TRANSCRIBED` correction records who read it and when. Unlike an editorial correction, it may restore a number that OCR misread, because it is a reading of the page and not an edit.

## Not built yet

- Crops of the page image beside an OCR question, from Tesseract's word boxes and confidences (the Tesseract command-line tool's `tsv` output gives both).
- Questions from the duties and notice catalogs, and from a new file's standing (is it signed? recorded?).
- Applying the answers to `before differs`, `drift`, and `orphaned note` beyond recording them.
