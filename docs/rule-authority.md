# Who may make rules: finding the grants of rule-making power

An operating rule "is valid and enforceable only if" it "is within the authority of the board conferred by law or by the declaration, articles of incorporation or association, or bylaws of the association" (Civil Code 4350(b), the statute's words from the shelf). A rule is only as good as the grant behind it, so onboarding finds the grants: the provisions of the governing documents that give the association, the board, a committee, or the members the power to adopt, amend, or repeal rules. For each one jason records who holds the power, the subjects it reaches, its limits and conditions, the procedure it names, the words (recited, never paraphrased), and whether rules on that subject are on file.

This page is general. The association's own findings are the profile's: [mystique/docs/rule-authority.md](../mystique/docs/rule-authority.md), and the private reading in `mystique/notes/`. The examples here are made up.

Code: `jason.community.rule_authority` (records, candidates, the two readers, agreement, subjects, measurement), `jason.tasks.rule_authority` (the stores and the lines), `jason.commands.rules` (`jason rules`).

## What it is, and what it is not

- **A reading, never a rule row.** Every row is a lead for a person (`Review`: unreviewed, confirmed, corrected, rejected, kept by reading id). jason proposes; the board adopts. Nothing here makes, adopts, or changes a rule.
- **The authority side of an adopted rule.** [programs.md](programs.md) is the catalog of what an association must adopt and carry out; an operating rule is its `OPERATING_RULE` instrument, adopted by an act on record under authority. This module reads the authority. It does not read the adoption act (the catalog's `AdoptionEvidence`) and does not duplicate the catalog: a `ProgramRequirement` row whose instrument is an operating rule would take its authority element from these rows, and its `adoption-formalities` check ("within the authority of the board", 4350(b)) would read them.
- **Quoted words first, then a labeled reading.** The recited words are the document's, checked verbatim. "The board holds it" and "its subjects" are the reader's reading and are printed as one.
- **A miss stays a miss.** "No grant found" is not "no authority": the power may be in the law itself, in a document not read, or in words the collector does not look for.

## Method

### 1. Candidates by rule

`rule_authority.candidates` reads every sentence of every governing document (declaration, bylaws, articles, amendments, the board's own rules and policies; not resolutions or annexations) and collects those that may grant, limit, or refer to rule-making power. Each candidate keeps why it was collected:

| Reason | The sentence |
|---|---|
| `verb+object` | has an adoption verb (adopt, make, establish, promulgate, amend, repeal, modify, publish, enact, prescribe, create, reverse, and the like) within 90 characters of a rule-type noun (rules, regulations, policies, procedures, guidelines, standards, a schedule of fines, limitations or restrictions on ...) |
| `duty: permission of the board` | the duty grammar (`jason.community.deontic`) reads a permission, right, or duty whose head verb is one of those verbs and whose object is one of those nouns |
| `refers: ...` | "subject to the Rules", "pursuant to rules", "as the Board may adopt", "in accordance with the rules", "adopted rules", "the authority for ... rules" |
| `definition` | a definition of "Rules" or of a guidelines term |
| `scope` | "the Rules may concern ..." (the subjects a grant names) |
| `applicability` | "this section applies only to a Rule that relates to ..." |
| `delegation` | a standard left to the board without the word rule ("a reasonable number, as determined by the Board", "a time limit shall be established by the Board"), collected only when the sentence is about a standard |

Stops are data: an insurance policy, parliamentary procedure, "rules of order", "policy statement". A rule that speaks of itself ("these rules are effective on adoption") is collected and read as no grant. A section's own heading is not a candidate. A sentence that opens a list ("including, without limitation, Rules" and the items under it) carries its items, so the subjects the items name go with the grant.

### 2. Two readers

- **The rules** (`rule_reading`, the default; no model): a grant when a power or a duty with an adoption head verb has a rule-type noun for its object; a limit when the sentence conditions how rules are made (notice, the meeting, a reversal vote, readoption, emergency, applicability); a reference when it only names rules adopted elsewhere, defines the word, or lists a scope. The holder is the duty's bearer; subjects come from a word list over the sentence and its list items; conditions and the procedure are phrases, each a quote of the sentence.
- **The local model** (`RuleModel`, behind `--model`): qwen3.5:9b through Ollama, after `local_ai.preflight`, under the GPU lock (it waits for another job's hold, up to `--wait` seconds), unloaded when done. It sees the section with the candidate marked and answers a JSON schema of closed lists: grant (`yes`, `no`, `limits`, `refers`), holder, subjects (the closed list, and `other` with the word), conditions (a closed list of kinds, each with the exact words), the procedure's words, and the operative words. The prompt names kinds and questions, never a section number or a figure ([prompts convention](../AGENTS.md)). Free generation over-corrects ([ocr-correction.md](ocr-correction.md)), so the model chooses among given labels and quotes.
  - **Quotes are checked.** A quote that is not verbatim in the section is dropped and noted (`reference_model.find_quote`: case, spacing, and quotation marks aside). A grant whose operative words are not in the *marked sentence* is a no: the model answered for a neighbor, which is its own candidate. A condition whose words are in the section but not the sentence is shown as "elsewhere in the section". A subject no word of the section reaches is dropped (asked what a general power covers, the model lists every subject).
  - **Self-consistency.** The greedy answer, then three more samples at temperature 0.3; the share that agree with it on answer and holder is its consistency. The raw answer is saved (`data/rules/authority.json`, `answers`, keyed by model, prompt version, and candidate) so a rerun, or a change in how an answer is read, asks nothing.

### 3. Agreement sets the tier

| Tier | Meaning |
|---|---|
| `likely` | both readers read a grant (or both a limit), with the same holder (an unstated holder agrees with a stated one) |
| `suggested` | one reader alone (the only tier without `--model`) |
| `conflict` | one reader reads a grant and the other reads no, a reference, or a limit; kept as a lead, with the reader that found it |

This is the idea in [ocr-correction.md](ocr-correction.md): agreement between independent readers, not a model's stated confidence, sets confidence. A row is stored with the readers that read it and its consistency.

### 4. The subjects, and the rules on file

`by_subject` sets each subject beside the rules on file. A *grant that names the subject* is kept apart from a *general power* ("the use, occupancy, management, and operation of the development"), which reaches every subject and says nothing of one in particular. Standings: authority named and rules on file; authority named, no rules; general power only, rules on file; general power only, no rules; rules on file, no grant found; neither found. "Rules on file" are the sections of the rules documents (operating rules, election rules, policies) that state a norm, with the subjects of their heading and first norm sentences; for a document with parts, only its rule and policy parts. The documents' own restrictions (a prohibition in the declaration) are listed beside them: a restriction the declaration states itself needs no rule.

**Parts.** An owner's manual holds rules, copies of the declaration, policies bound in, and guidance (`jason.community.manual`; [owners-manual.md](owners-manual.md)). `RulePart` carries a part's kind and offsets; `parts_from_manual` builds it from `jason manual`'s classification. A candidate keeps the part it sits in. A grant stated in a guidance part is listed apart and not counted, and the guidance is never a rule on file. A stored segmentation ([document-segmentation.md](document-segmentation.md)) gives the same record: `parts_from_segments` finds each part in the outline's text by its heading (`part_span`), keeps its kind (a rules part is "rule", a policy or procedure "policy", anything else its own word), and makes each exhibit a part of kind "exhibit" from its heading to the next exhibit or part. A grant stated in an exhibit counts as the exhibit's and is listed apart, and a rule there is not a rule on file. The reading is used only for a file in the library whose bytes are those it was read from and that is one outline's document (the same binding and the same reasons for leaving a reading out as citation scoping: [rule-citations.md](rule-citations.md)); `rule_authority.rule_parts` returns the parts and, in `notes`, each reading left out and why.

**Two readings of one document.** Where the manual's classification and a segmentation both cover a stretch, `merge_parts` sets them beside each other. Where one covers the text and the other does not, that reading's part stands. Where both cover it and agree on the kind, or both read it as something that is neither a rule nor a policy, the segmentation's part is kept, so the part says it came from the segments. Where they **disagree** (one reads a rule, the other a policy or guidance), the classification's part is kept and the segmentation's kind is written on it (`RulePart.contested`): a reading that would count more text as rules than the other does is a question for a person, never a way to enlarge the rules on file. Every candidate, grant, and rule on file says where its part came from (`part_source`: `segments` or `classification`), and the recital shows it:

```
  part: guidance (from the manual's classification); the stored segmentation takes it to be rule; the classification is kept
```

The grants and the rules on file of a document the classification already covers are therefore the same with or without a stored segmentation; the tests hold the made-up case to it (`tests/test_segment_scoping.py`), and the profile's page reports the real counts. `jason rules` reads the merged parts.

### 5. Civil Code 4355 and 4360

A rule on a subject 4355(a) lists needs 4360's notice to the members before adoption. The statute lists seven subjects: use of the common area or of an exclusive use common area; use of a separate interest, including aesthetic or architectural standards; member discipline, including a schedule of monetary penalties and any procedure for imposing penalties; standards for delinquent assessment payment plans; procedures for resolving disputes; procedures for reviewing a proposed physical change; procedures for elections. 4355(b) takes five actions out of 4360 and 4365, among them "a decision regarding maintenance of the common area" and "a decision on a specific matter that is not intended to apply generally".

`reach(subject)` gives, for each subject, a **labeled reading**: `listed` (it falls under a listed subject), `depends` (it turns on what the rule does, so two readings remain and counsel reads them), or `not listed` (none of the seven; 4355(b) may apply as well). Parking, pets, noise, trash, signs, and registration depend on whether the rule governs the common area or a separate interest. Leasing has two readings (a use of a separate interest, or a restraint on transfer that is not a use). The table is data (`REACH`) with the sections it cites; a test reads the subjects against the statute's words on the shelf. The reading decides nothing. A document may also set its own list: a bylaw may repeat 4355(a) as the matters its rule-change procedure covers, and that list is a limit row whose list items the candidate carries.

The general limits found in the documents (notice, the meeting, reversal, readoption, emergency changes) are `limits` rows linked to the grants they bear on, as leads. `jason rule-change` is the path for a proposed change on a listed subject.

## Measurements (October 5, 2026)

**The gold set.** 82 candidates of one association's governing documents, each labeled by hand (one reader: the author of this module), 19 grants, 15 limits, 18 references, 30 no. The labels are `data/rules/gold.json` (private, git-ignored; each item a quote, a label, a holder, and subjects, with `hard: true` on the five grants that have no rule noun or are a judgment call: three delegated standards, a power to establish fines, and a polling period). Made-up twins are in `tests/fixtures/rules`. Two cautions. The rules' patterns were tuned while looking at these candidates, so their figures are optimistic and the model's first run is the only blind reading. The set is one association's; a second would measure how far it carries.

| Reader | Precision | Recall | F1 | Four-way answer right |
|---|---:|---:|---:|---:|
| the collector, grants found as candidates | | 19 of 19 | | |
| the rules alone | 1.000 | 0.737 (14 of 19) | 0.848 | 61 of 82 |
| the model, first prompt (blind), qwen3.5:9b | 0.773 | 0.895 (17 of 19) | 0.829 | 64 of 82 |
| the model, final prompt and the sentence guard | 0.842 | 0.842 (16 of 19) | 0.842 | 63 of 82 |
| both agree (the likely tier's grants) | 1.000 | 0.737 | 0.848 | |
| either reads a grant | 0.842 | 0.842 | 0.842 | |

- **Without the five hard items** (14 of the 19 grants) the rules read 14 of 14 with no false grant, and the model 14 of 14 with three false ones. On the five hard items the rules read none and the model two (the power to establish fines, and the polling period); it read the three delegated standards as no.
- **The rules' misses** are the five hard items: three delegations ("a reasonable number, as determined by the Board", and a time limit "established by the Board" twice), a polling period "determined by the Board", and a power to "establish and impose fines ... in accordance with a schedule of fines adopted by the Board". They have no rule noun or name the schedule as adopted elsewhere, so the rules read them as references.
- **The model's false grants** are three: a list of what Rules may include; a power to impose conditions on a variance (a decision in one case, not a rule); and a guide's description of the board.
- **Holder and subjects.** On the grants each reader read right, the holder was right every time. Subject recall against the labeled subjects: rules 0.85, model 0.87. The model's first run listed every subject for a general power; the grounding guard cut that.
- **Tiers.** Of 23 `likely` rows (14 grants, 9 limits), 23 were right. The 5 `suggested` rows (limits read by the rules alone) were right. Of 5 `conflict` rows (the model read a grant, the rules did not), 2 were. So the tier orders trust: agreement, then one reader, then disagreement.
- **Self-consistency.** Where all three extra samples agreed with the greedy answer (66 candidates), 82% were right (54); where they did not (16), 56% (9). It is a filter, not a second reader.
- **Limits are where the model is weak.** The first prompt read 7 of 14 limits right (the rest as no or a reference); naming the kinds of limit (the meeting, readoption, applicability) in the method and adding an example gave 9 of 15, with 5 still read as no. The rules read 14 of 15.
- **Time.** The rules run in under a second. The model, with the greedy answer and three samples, took 3 minutes 24 seconds for 83 candidates: 2.5 seconds a candidate, about 0.6 second a request, a 1,600-character context and 16k window, thinking off. A rerun from saved answers takes seconds. The model is unloaded when the run ends. The row is in the trials table of [document-tools.md](document-tools.md).

The collector's recall is measured on the candidates the gold set labeled, which includes the words added after the first pass found two grants it did not collect (a power to adopt "limitations on" a subject, and "readopt"). A grant stated in words the collector does not look for ("the Board shall designate quiet hours") is not collected; the made-up fixture has one so a test says so.

## Using it

```
jason rules --find                      # the rules' reading, every document; writes data/rules/authority.json
jason rules --find --model              # add the local model (preflight, GPU lock, unloaded after)
jason rules                             # the grants, with words, holder, subjects, conditions, procedure
jason rules --all --tier conflict       # the limits too; one tier
jason rules --subjects                  # each subject: authority, rules on file, the 4355 reading
jason rules --measure                   # precision and recall against data/rules/gold.json
jason rules --review ID --status confirmed --note "read the section" --by NAME
```

A reading kept by id survives a reread while the words stay the same; a review whose reading is gone is kept under `orphaned`. As an onboarding step (proposed; the onboarding queue does not carry it yet) it runs `--find --model` once the outlines are read, and puts each `conflict` row and each subject whose standing is "rules on file, no grant found" in front of a person.

## What to do with a finding

- **Authority and no rule.** The board may adopt one, as a written policy where the law is silent. A rule on a 4355(a) subject takes `jason rule-change`. Where the grant delegates a standard ("a reasonable number, as determined by the Board"), the board's determination is the rule row that is missing, and until it is written the standard is open.
- **A rule and no grant named.** Read the general power first. If it reaches the subject, the rule stands on it (and on 4350's other tests). If no grant reaches it, the question is the board's and counsel's: the rule may rest on the law itself, or on a document not read. It is never an accusation.
- **A grant in guidance.** A guide's description of the board's power is not the power. Cite the document it points to.
- **Two readings.** Where `depends` leaves a subject on both sides of 4355(a), the board asks counsel, and the course lawful under either reading (the 4360 notice) is the default.

## Not done yet

- **A second association's gold set**, and a held-out half of this one.
- **The collector's vocabulary** for grants with no rule noun and no delegation phrase.
- **Linking each grant to the adoption act** that used it (`AdoptionEvidence` in [programs.md](programs.md), when built) and to the procedure's own limits as findings rather than leads.
- **Subject lists for the closed vocabulary** the model reads as `other`: insurance and maintenance were added, and fees, access, and safety are next if a second association needs them.
- **Segments, measured on little.** Parts from a stored segmentation are read beside the classification's (above); the real archive has few stored readings of its rule documents, so the effect on the grants and the rules on file is measured on a rendering of the outlines' text, not on scans. A document with no classification (a policy, the election rules) gets parts only from a reading; its standing does not change unless the reading finds parts in it.
- **A part inside an exhibit** counts as the exhibit's; a rules part inside an exhibit is not read as rules.
