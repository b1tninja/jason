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
| Check | `prompts.verify` | A quote counts only when it is found in the source it cites. Every source a consideration names must exist. |

## Commands

```bash
jason review --list
jason review --subject "Trash cans left out" --draft FILE          # the pack: data/briefs/<task>.md
jason review --subject "Trash cans left out" --draft FILE --run    # and the local model's review, quotes checked
jason review question --ask "Who pays the master deductible after a leak from a unit?"
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
jason review question --collection case-24cv000123 --ask "..." # the case file as its own tier
jason review question --catalog library --kind minutes --ask "..."   # an ad hoc collection, from the index's columns
```

| Part | What it is |
|---|---|
| Members | An index `Scope`: catalogs, kinds, folders. The collection is whatever the index holds under it today. |
| Context | What holds for the whole collection. For a legal case: its title, forum, role, and status, each event with its date, and each duty with whether the record shows it met, from the `LegalCase` record and nothing else. |
| Label | What its material is, shown on every passage in place of a tier. For a legal case: "evidence gathered for this matter: neither the record nor the law". |
| Confidential | The strictest of its members' and its matter's. A case's catalog is confidential in the index, so its collection is. |

**In the pack.** A collection adds two things:
- **C, the collection's material:** the passages of its scope that best answer the task's questions (the same
  questions the other tiers use, fused by reciprocal rank). Near copies are folded. One file gives at most 2 passages
  and the pack takes at most 8 (`COLLECTION_PER_FILE`, `COLLECTION_PASSAGES`). They sit after the association's
  records and before the facts.
- **The context lines,** as one more F source, titled "the specification's record of the matter".

The task's prompt then tells the reader what a C source is: what a document in the collection says is its author's
statement. It is not a finding, and it is never a rule.

**Confidentiality.** A confidential collection goes only into a board task's pack. For any other audience the pack
holds nothing from it, and a gap line says so: "the collection is confidential; this task's audience is all members".
It is never left out silently.

**Gaps.** A gap line also says when there is no passage index, when the index holds nothing under the scope, when no
passage matched, and when a file changed after the index cut it. C reads only the index. A PDF with no text extract
is not in the index, so it is not in the tier: for a legal case the pack counts the files in the case's folder that the
index does not hold ("the passage index lacks 3 of the 9 files ...").

**Without a collection the pack is what it was.** A test holds it to a page written before collections existed
(`tests/fixtures/context_pack/no_collection.md`).

## Reviews are kept

`data/briefs/<name>.md` and `.review.json` are the latest pack and review, written over each time. Every pack written
is also kept under `data/reviews/<task>/<collection or "none">/<digest>.json` (`jason.tasks.review_store`), under the
store lock.

- **The digest** is over the question, the draft, the collection's key, and each source's id with a digest of its
  words. The same pack is the same record. A pack whose sources changed is a new record, so a change in the law or a
  document shows as two reviews to compare.
- **The record** holds the as-of date, the task and its audience, the collection, each source (id, tier, standing,
  file, section, and a digest of its passage, never the words), the gaps, and `runs`: each model answer for that pack,
  with its model and how its quotes checked. A second run is added beside the first.
- **A review of a confidential collection is confidential,** and its record says so. `review_store.history` leaves
  such records out unless asked.

```bash
jason review --history question      # date, collection, digest, and whether the answer's quotes were found
```

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
