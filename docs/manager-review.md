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
| Context pack (the RAG) | `jason.community.context_pack` | The questions are the topics plus **the matter**: the question asked, or the subject and opening of the text under review. The pack has five kinds of source:<br>• **S, the law:** sections of the law on hand (`data/authorities`), ranked for each question, fused by reciprocal rank so every topic counts, and drawn first from the leading articles (a manager reads around the section that led there). The statutes a retrieved document cites come too. A pre-2014 number is a gap.<br>• **G, the governing documents:** passages of the kinds the task names, each with its tier; copies of one passage are folded.<br>• **R, the records:** the best passages of the latest library files of each other kind named (inspection reports, agendas, insurance policies).<br>• **F:** jason's tools.<br>• **D1:** the text under review.<br>The law on hand is also listed by chapter, so a reader can see what was available and say when expected law is missing. |
| Check | `prompts.verify` | A quote counts only when it is found in the source it cites. Every source a consideration names must exist. |

## Commands

```bash
jason review --list
jason review --subject "Trash cans left out" --draft FILE          # the pack: data/briefs/<task>.md
jason review --subject "Trash cans left out" --draft FILE --run    # and the local model's review, quotes checked
jason review question --ask "Who pays the master deductible after a leak from a unit?"
```

The pack page is useful on its own: it holds the base prompt, the task prompt, and the sources. A person, Claude,
AnythingLLM, or another agent can work from it, and the `manager_context` MCP tool (board profile) serves it.

**Retrieval.** It is hybrid by default: BM25 fused with the local embedder `qwen3-embedding:8b`. The first build embeds
the 497 law sections once into the vector cache; after that a pack takes seconds. If the embedder cannot load, the
build releases the chat model and tries once more. If it still cannot, it falls back to keyword and records that in
the gaps.

**The model run.** `--run` releases the embedder, runs the preflight, and asks `qwen3.6:27b` under the GPU lock (no
thinking, temperature 0, the answer held to `ANSWER_SCHEMA`). It writes `<task>.review.json` and `<task>.review.md`.
Nothing leaves the machine.

BM25's tokens fold trailing punctuation and plain plurals: "fines." matches "fine" and "policies" matches "policy".

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
