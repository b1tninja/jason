# A manager's review: the base prompt, the task prompts, and the context pack

jason reads a task the way a professional community manager who knows the law would. It first works out what governs
the task. It then reads the law, the CC&Rs, the bylaws, and the rules, in that order. It applies them to the
association's own facts, and it names what the board must decide.

**A task prompt names no statute section, no document section, and no figure.** Laws are amended, CC&Rs are restated,
policies are replaced, and premiums change. A prompt that said "Civil Code 5810" or "CC&Rs 4.10" or "$285 a month" would
be wrong the day one of them changed. Instead, a task says what it turns on and which kinds of documents to read.
Retrieval then finds the words in force, and the review cites and quotes them. The same prompt still works after the
documents or the law change, and that is the point: when the law or a document changes, run the review again over the
templates. A test (`test_task_prompts_name_no_sections_and_no_figures`) keeps section numbers and figures out of the rows.

## The layers

| Layer | Where | What it is |
|---|---|---|
| Order of authority | `jason.community.authority_order` | `Tier`: federal law, statutes, regulations, local ordinances, the declaration (CC&Rs, amendments, annexations), articles, bylaws, operating rules and policies, contracts, records, guidance. A document's tier comes from its kind. |
| Base prompt | `jason.community.prompts.BASE_PROMPT` | The method, the same for every task. **Role:** a manager well read in Davis-Stirling, the nonprofit corporation law, and the other codes that reach an association; jason prepares and the board decides; legal questions go to counsel. **Work out what governs** before reading. **The text controls** over memory of numbers and rules, and a difference from expectation is worth reporting. **Sources:** only the numbered ones, quoted from their text, never the task's own instructions. Then the order of authority, the method (issue, rule highest tier first, facts, application, conclusion), and the rules for writing to members. |
| The association | `Community.prompt_context()` | Read from the specification: name, units, buildings, the board's group address, the mailing address. The one stated fact is how it is managed (`MANAGEMENT` in `mystique/prompts.py`). |
| Task prompt | `mystique/prompts.py` `TASK_PROMPTS` | One row per kind of task, holding:<br>• purpose and audience;<br>• **topics**: what it turns on, in plain words;<br>• **documents**: the kinds of governing documents and records to read;<br>• **facts**: the jason tools that hold them;<br>• **considerations**: the questions an experienced manager asks, with no answers;<br>• guidance: the task's own cautions;<br>• subjects: patterns that tie a PayHOA template to the task. |
| Context pack (the RAG) | `jason.community.context_pack` | The questions are the topics plus **the matter**: the question asked, or the subject and opening of the text under review. The pack has five kinds of source, and a sixth when a collection is named ([Collections](#collections)):<br>• **S, the law:** sections of the law on hand (`data/authorities`), ranked for each question, fused by reciprocal rank so every topic counts, and drawn first from the leading articles (a manager reads around the section that led there). The statutes a retrieved document cites come too. A pre-2014 number is a gap.<br>• **G, the governing documents:** passages of the kinds the task names, each with its tier; copies of one passage are folded.<br>• **R, the records:** the best passages of the latest library files of each other kind named (inspection reports, agendas, insurance policies).<br>• **F:** jason's tools.<br>• **D1:** the text under review.<br>The law on hand is also listed by chapter, so a reader can see what was available and say when expected law is missing. |
| Check | `prompts.verify` | A quote counts only when it is found in the source it cites. Every source a consideration names must exist. A quote of a reading attached to a source is refused, and says why ([The quote check and readings](#the-quote-check-and-readings)). |

## Commands

```bash
jason review --list
jason review --subject "Trash cans left out" --draft FILE          # the pack: data/briefs/<task>.md
jason review --subject "Trash cans left out" --draft FILE --run    # and the local model's review, quotes checked
jason review question --ask "Who pays the master deductible after a leak from a unit?"
jason review hearing-notice --draft FILE --as-of 2022-03-01        # the law and the documents as of the letter's day
```

The pack page is useful on its own: it holds the base prompt, the task prompt, and the sources. A person, Claude,
or another agent can work from it, and the `manager_context` MCP tool (board profile) serves it.

**Retrieval.** It is hybrid by default: BM25 fused with the local embedder `qwen3-embedding:8b`. The first build embeds
the 497 law sections once into the vector cache; after that a pack takes seconds. If the embedder cannot load, the
build releases the chat model and tries once more. If it still cannot, it falls back to keyword and records that in
the gaps.

**The model run.** `--run` releases the embedder, runs the preflight, and asks `qwen3.6:27b` under the GPU lock (no
thinking, temperature 0, the answer held to `ANSWER_SCHEMA`). It writes `<task>.review.json` and `<task>.review.md`.
Nothing leaves the machine.

BM25's tokens fold trailing punctuation and plain plurals: "fines." matches "fine" and "policies" matches "policy".

## Collections

A collection is a set of documents reviewed together, with what holds for all of them
(`jason.community.document_collections`; [ingestion-and-review.md](ingestion-and-review.md), "A collection"). The first
kind is a legal case's file: its catalog in the passage index and its record in the specification.

```bash
jason review --collections                                     # each collection, with its files and passages in the index
jason collection case-24cv000123 --write                       # its summary page: data/collections/<key>/summary.md
jason review question --collection case-24cv000123 --ask "..." # the case file as its own tier
jason review question --catalog library --kind minutes --ask "..."   # an ad hoc collection, from the index's columns
```

| Part | What it is |
|---|---|
| Members | An index `Scope`: catalogs, kinds, folders. The collection is whatever the index holds under it today, less the pages jason generated for a collection (`data/collections/`). |
| Context | What holds for the whole collection. For a legal case: its title, forum, role, and status, each event with its date, and each duty with whether the record shows it met, from the `LegalCase` record and nothing else. |
| Label | What its material is, shown on every passage in place of a tier. For a legal case: "evidence gathered for this matter: neither the record nor the law". |
| Confidential | The strictest of its members' and its matter's. A case's catalog is confidential in the index, so its collection is. |
| Companion page | Its summary page, `data/collections/<key>/summary.md` (`jason collection KEY --write`; [collections.md](collections.md), "The summary page"). Generated, indexed in the collection's own catalog as a page, and never a member. |

**In the pack.** A collection adds three things:
- **C, the collection's material:** the passages of its scope that best answer the task's questions (the same
  questions the other tiers use, fused by reciprocal rank). Near copies are folded. One file gives at most 2 passages
  and the pack takes at most 8 (`COLLECTION_PER_FILE`, `COLLECTION_PASSAGES`). They sit after the association's
  records and before the facts.
- **The context lines,** as one more F source, titled "the specification's record of the matter".
- **The summary page,** when the collection has one, as one more F source, labeled "jason's summary of the
  collection: a summary, not the record" (`document_collections.companion_summary`). It carries the page's files,
  what is missing or unread, the open questions, and the conflicts, cut at 16,000 characters
  (`COLLECTION_SUMMARY_CHARS`). Three parts of the page are left out:
  - the line with the date it was generated, which moves to the source's note, so the same page written again on
    another day is the same source and the same kept review;
  - the specification's record, which is already its own source;
  - the chronology, which quotes the documents. The pack reads the documents' own passages instead.

  A collection with no summary page has no such source. That is not a gap: nothing of the evidence is missing.

**The summary is never a C source.** The page quotes every document, so a tier that ranked it would give it the
places of the documents themselves. A collection's scope therefore leaves the generated pages out, and a test holds
it: with the page written and indexed, the C sources are the ones the pack had before the page existed, and a scope
that does not leave the pages out takes the page as evidence
(`test_the_pack_carries_the_summary_once_labeled_and_the_evidence_is_what_it_was`).

The task's prompt then tells the reader what a C source is: what a document in the collection says is its author's
statement. It is not a finding, and it is never a rule. When the pack carries the summary, the prompt says what it
is too: not a document of the collection, and never cited as the record or a rule.

**Confidentiality.** A confidential collection goes only into a board task's pack. For any other audience the pack
holds nothing from it, and a gap line says so: "the collection is confidential; this task's audience is all members".
It is never left out silently.

**Gaps.** A gap line also says when there is no passage index, when the index holds nothing under the scope, when no
passage matched, and when a file changed after the index cut it. C reads only the index. A PDF with no text extract
is not in the index, so it is not in the tier: for a legal case the pack counts the files in the case's folder that the
index does not hold ("the passage index lacks 3 of the 9 files ...").

**Without a collection the pack is what it was.** A test holds it to a page written before collections existed
(`tests/fixtures/context_pack/no_collection.md`).

## As of a day

A review of an older letter turns on the law and the documents as they stood on the letter's day ([AGENTS.md](../AGENTS.md),
"Recite the version that governs"). `--as-of DATE` (`assemble(as_of=)`, `manager_context(as_of=)`) builds the pack for
that day. Each law source and each governing source is then recited through `law_readings.recite`
([law-readings.md](law-readings.md)). Without a day the pack is today's, byte for byte what it was before: a test holds
it to a page written before the change (`tests/fixtures/context_pack/law_no_as_of.md`).

**S, the law.** The sections are found as before, by searching the law as it stands now. Each is then recited as of
the day. Above its words the source says what they are:

| The disk shows | The source gives | Its label |
|---|---|---|
| an earlier version whose recorded range holds the day | those earlier words | "In force on DAY: from A until B; made by ACT; ended by ACT", and a caveat that they are not the words on the shelf now |
| a record that places the current words in force by the day | the current words | "In force on DAY: from A; made by ACT" |
| two versions printed under one number, and their own words say which operates | that version | "In force on DAY", with each deciding sentence quoted |
| nothing that decides it | the words on the shelf now, every version when the shelf prints several | "Not shown to be in force on DAY", with what is held and what would bring the earlier words (`jason law-history --versions`) |

- Every label carries the source line and the digest of the words.
- Today's words are never given silently for an earlier day. The gaps count the law sources not shown in force.
- A section printed in two versions is one source, not two.
- jason's `- History:` note is printed above the words, marked as jason's. It is not part of them.

**A former section number.** A governing passage, the draft, or a collection's document may cite a section by a
number a renumbering retired (the Davis-Stirling Act's 1350 to 1378, now 4000 to 6150). With a day, such a citation
is not reported as a section not on hand: it is read through the successor table `jason law-history --export` keeps
on disk (`law_citations.resolve`; [collections.md](collections.md), "Citations of the law"):

- **A day on or after the renumbering.** The successor the table names comes into the pack as a law source, recited
  as of the day, with the note "cites former X, now Y (disposition table ...)". Where the history holds the former
  section's own words (a version a person added), they come in too, recited as of the last day the former number
  was the law, so both are recited. Where they are not held, a gap says so and the successor stands alone.
- **A day before the renumbering.** The cited number was the section in force. Its words come in where the history
  holds them; otherwise a gap says a person adds them (`jason law-history --add-version`).
- **A number the table does not place** (not continued, omitted, or no row) stays an open gap. No successor is guessed.
- **A collection's documents** also bring in the current sections they cite, recited as of the day, up to
  `law_citations.MAX_CITED_SECTIONS`; the rest are named in a gap. The law sources keep their place before the
  governing and collection sources.

Without a day the pack reads a former number as it did: a gap line, "find the section in force".

**G, the governing documents.** The tier ranks passages, not sections, and a passage is its file's words as the file
reads now. With a day, jason names the section a passage falls in and recites that:

- **Naming the section.** A passage the index cut on its sections carries the section's path in its heading. The
  document is the one whose outline matches the passage's file. Each number the heading names is tried, innermost
  first, and counts only when the document has that section and its words overlap the passage's.
- **A document kept as amended** (`Community.living_documents()`). Where the passage is the section's words on that
  day, the passage is labeled in force. Where it is not, the section's words on that day are given under the passage
  with their digest, and those are the words to recite.
- **A document kept only as it reads now.** The passage is labeled "Not shown to be in force on DAY": its words may
  differ from the words of that day. The section's digest now is recorded.
- **No section named.** The same label, with why: the passage was cut by words, no outline matches its file, or its
  heading names no numbered section. Nothing is looked up for it.

**Readings.** Each stored reading (`Community.law_readings()`) of a provision is listed under the provision's words:

- a current one, labeled with whose it is, its standing (plain, a reading, or two readings remain), and its date;
- a stale, missing, or misquoted one apart, as not applied;
- one dated after the day apart, as no reading on that day.

A reading is never part of a source's text. A governing passage also lists the readings of each section around its
own that the heading names. A reading reaches a governing passage only through a section named for it.

**The task's prompt** gains four lines (`prompts.as_of_lines`), general for any association: recite the words as the
source gives them for the day; where a source says they are not shown to be in force, say so and do not rely on them
as the law of that day; a reading is a reading, labeled with whose it is, never the provision's words; where two
readings remain, the board asks counsel. The base prompt is unchanged.

**What is not covered:**

- **The search is today's.** A section repealed between the day and now is not found by the topics, so it is among
  the sources only where a source cites it and the history holds its words. The prompt says so. A renumbered one is
  found through its citation (above), not by the topics.
- **R, C, and F are as they are now.** The records, a collection's material, and jason's facts are not filtered or
  recited by date.
- **A governing passage with no section named** gets no as-of words and no reading.
- **A document not kept as amended** has no words for an earlier day. Keeping it as amended (a `LivingDocument`
  row) is what would give them.
- **A day before a kept document existed** is not detected: the base text is given.
- **The pack's own quote check accepts a near match.** `prompts.verify` passes a quote that is nine tenths the
  source's words, so a quote of today's words can pass against a source that gives an earlier version differing by a
  word. `jason verify-quotes --as-of DAY` is strict: it checks a statute's quotation against the version in force
  that day and names a quotation of another version ([law-readings.md](law-readings.md), "Checking an answer's
  quotations").

## Reviews are kept

`data/briefs/<name>.md` and `.review.json` are the latest pack and review, written over each time. Every pack written
is also kept under `data/reviews/<task>/<collection or "none">/<digest>.json` (`jason.tasks.review_store`), under the
store lock.

- **The digest** is over the question, the draft, the collection's key, and each source's id with a digest of its
  words. The same pack is the same record. A pack whose sources changed is a new record, so a change in the law or a
  document shows as two reviews to compare.
- **With a day, the digest also covers the day and what each source recites:** the provision's digest, whether it was
  shown in force, and each reading's key, standing, whose it is, and state. So the same question as of two days is
  two reviews, and so is the same day after a statute or a reading changed. A pack with no day keeps the digest it
  always had.
- **The record** holds the as-of date, the task and its audience, the collection, each source (id, tier, standing,
  file, section, and a digest of its passage, never the words), the gaps, and `runs`: each model answer for that pack,
  with its model and how its quotes checked. A second run is added beside the first.
- **The as-of date** is the day a person named (`asOfNamed`), else the day the record was first kept.
- **A law source's row carries `provision`:** the citation and the digest of the provision's words, the digest
  `jason readings` prints. With a day it also says whether the words were shown in force and how (`shown`,
  `decided`), and lists the readings attached. A governing source's row carries the same for its section. The
  record never holds what a reading says.
- **A review of a confidential collection is confidential,** and its record says so. `review_store.history` leaves
  such records out unless asked.

```bash
jason review --history question      # the as-of date, collection, digest, and whether the answer's quotes were found
```

A review with a named day ends its line with "as of DAY (named; written DAY)", the law sources not shown in force
that day, and the readings attached.

## The quote check and readings

`--run` checks every quote against the words of the source it cites (`prompts.verify`).

- **The recited words check.** A source's text is the provision's words for the day, and for a governing passage the
  section's words given under it. A quote of either is found.
- **A reading quoted as the rule is flagged.** A reading is not in any source's text, so a quote of one is not
  found. With the pack's readings in hand (`ContextPack.reading_texts`), the reason says so: "a reading attached to
  the source, not the provision's words". The report marks it.
- **`jason verify-quotes` does not know readings.** It checks an answer against the passage index and the shelf.
  A reading is profile data and is in neither, so a quoted reading is "not found" there, with no word that it is a
  reading.

## What the runs showed (October 1, 2026)

**First version.** The task rows named the statutes and the CC&R sections, and the reviews were good. But every fact
in a row was a fact that would go stale.

**General rows, same templates.** The reviews found the same things from the documents themselves: the governing
documents' deadlines and sections from a template's own words and the task's topics, the records of a kind the task
names (a vendor's inspection report, jason's calendar), and conflicts between two copies of one rule. The check caught
bad citations: titles quoted as text, and quotes of the task's own instructions.

This association's findings are in its private notes (mystique/notes/manager-review.md).

The research behind these templates is in `data/briefs/research/`, one file per template group. Its findings are
findings, not prompt text.
