# Statute alignment: which provision continues which

A governing document or letter that cites a statute by an old number, or by a subdivision letter that has since moved, needs one answer before anyone reads it again: is the provision it names still the same rule under another number (renumbered or reworded, the same effect), a rule that changed in substance, or gone? `jason statute-align` answers provision by provision. It is measured against the Law Revision Commission's own disposition table before any of its answers are used, and its answers are leads, never pins.

The purpose is that a continuation is not treated as a new law. A consumer, such as a sweep of jason's own citations, treats `continued_without_substantive_change` as a change it does not need to review. It reads `continued_with_changes` with the change the model named and the quotes on both sides.

## What it does

| Layer | Where | What |
|---|---|---|
| Text | `LawLibrary.editions` (`jason.sources.lawlibrary`, the worker's `editions` job) | A span's sections and outline as one legislative session printed them, kept under `data/authorities/history/alignment/editions` |
| Units | `statute_alignment.subdivisions` | A section split into its top-level subdivisions: `(a)`, `(b)` (everything nested stays inside), the words before `(a)` as `(intro)`, or the whole section when it has no subdivisions. A lowercase label starts a new unit only when it is the next letter, so `(i)` under `(A)` stays inside its unit |
| Structure | `structure_map`, `candidates` | Each former heading (article, else chapter) is mapped to current headings in two ways: by the table rows of *other* sections (leave-one-section-out, so a section's own rows never shape its candidates), and by the headings' words and text. A former section's candidates are the current units under those headings, plus each unit's top 5 by TF-IDF (and embedding) similarity anywhere in the Act, capped at 80. All of the section's units share one candidate list, so consecutive prompts share their prefix |
| Judge | `OllamaJudge`, `judge_section`, `verify` | One request per former unit: the candidates first, then the unit. The model answers in a JSON schema whose candidate field is an enum of the candidate ids. For each continuation it gives the relation, a 5 to 25 word quote from each side, and for `continued_with_changes` the change in a phrase with the differing words from each side. A match counts only when both quotes are found verbatim in the texts (folded for case, spacing, quotation marks, and dashes). A change phrase is kept only when its words are found too. Thinking is off, temperature is 0, `jason.local_ai.preflight` runs first, and every request holds jason's GPU lock |
| Conclusions | `per_former`, `per_current`, `shapes` | For each former unit: its targets, its relation, and its shape (one to one, split, combined, or split and combined), or `not_continued`. For each current section: its predecessors, the strongest relation among them, and its substantive changes, or `new` |

Relations: `continued_without_substantive_change` (the same effect: renumbered, reworded, or reorganized), `continued_with_changes` (a deadline, an amount, who acts, or a right, duty, or condition added or removed), `generalized`, `superseded`, `not_continued` (former), and `new` (current). Shape is computed from all of a unit's verified matches. The model is not asked for the shape.

The amended case (`--amended 5855 --before 2023 --after 2025`, or `--all-amended` for every amendment in `changes.json`) compares one section's old subdivisions with its new ones. A subdivision whose words are unchanged apart from its letter is matched by the text itself (`source="text_identity"`). The model reads the rest against every new subdivision (`source="model"`). Every row carries its verified quotes and a confidence. A confidence is high when the structure or the lexical top 3 also places the match, and drops a step when a claimed change could not be verified.

## The gold and how it is scored

The gold is the disposition table's rows in `data/authorities/history/former-sections.json` (`source=disposition_table`, act `davis-stirling`). The scores are:

- **Section level.** Pairs of (former section, current section).
- **Unit level.** Pairs of (former unit, current section). These are scored only where the table reads at a unit (`1363(g)`, `1365(a)(2)(A)-(D)` read as `(a)`), or where the table places the whole section in one current section.
- **Current subdivision.** Where the table names one (`CIV 5000(a)`), whether a found pair landed on it.
- **Omitted units.** The table's omitted subdivisions left unmatched.
- **Change class.** The Commission's Comments (`continued without change` and `without substantive change` read as one class, `with changes`, and `generalized`) against the variant's relation, on pairs that are in the table. Most pairs continue without change, so the precision and recall of `continued_with_changes` (chg P, chg R) carry more information than overall accuracy.
- **New.** On a full run only: current sections the table gives no predecessor, against those the variant leaves without one.

The variants are scored on the same units and candidates:

- **structure**: every structure candidate. This gives the candidate set's own precision and recall.
- **lexical**: the best TF-IDF candidate at 0.25 or above, plus any nearly as close.
- **embedding**: the same with `qwen3-embedding:8b`, at 0.6 or above.
- **llm**: the model's verified matches.

The floors were fixed before scoring and were not tuned on the gold. Similarity cannot read substance, so the baselines guess the change class from closeness alone (0.85 or above means no change).

## What it showed (October 1, 2026)

The default model is `qwen3.6:27b`, but it could not be measured. On every attempt, `jason.local_ai.preflight` refused to load it: it needs about 25 GB of Windows commit, and 15 to 21 GB was free. These numbers come from `qwen3:14b` (`--model qwen3:14b`) on the same candidates. Rerun with the default model once commit allows it:

```
jason statute-align --embed --evaluate --label full-27b
```

**The full Act**: 92 former sections, 374 units, 572 current units, candidate recall 0.992 (`recodification-full-qwen3-14b.json`).

| Variant | Section P | Section R | Unit P | Unit R | Class accuracy | chg P | chg R | New F1 |
|---|---|---|---|---|---|---|---|---|
| structure (all candidates) | 0.076 | 0.846 | 0.040 | 0.874 | n/a | n/a | n/a | 0.08 |
| lexical | 0.847 | 0.882 | 0.919 | 0.895 | 0.570 | 0.183 | 0.722 | 0.679 |
| embedding | 0.796 | 0.882 | 0.887 | 0.908 | 0.800 | 0.077 | 0.056 | 0.618 |
| llm (qwen3:14b) | 0.814 | 0.851 | 0.899 | 0.819 | 0.829 | 0.281 | 0.429 | 0.633 |
| llm and lexical agree | **0.928** | 0.790 | **0.977** | 0.774 | 0.816 | 0.276 | 0.400 | 0.563 |
| llm or lexical | 0.762 | **0.933** | 0.861 | **0.940** | 0.811 | 0.268 | 0.458 | 0.766 |

On the fifteen-section sample (`--sample`, before the prompt named the kinds of change that are not substantive), the model scored unit P 0.884 and R 0.844, and the agreement tier scored unit P 0.971.

**Timing.**
- `qwen3:14b`: 12.9 s per former section, 374 requests, and about 20 minutes for the Act. Requests that share a section's candidate prefix are cheap after the first.
- The first sample, with a cold cache, ran 30.7 s per section.
- The embeddings for all 946 units took about a minute.
- Structure and lexical run in seconds.

**The amendments** (`--all-amended`, `amended.json`).
- 83 amendments to 4000-6150, 2013-2025.
- 240 old subdivisions matched by unchanged words, 133 by the model (126 high confidence).
- 23 letter moves, 38 named changes, 40 new subdivisions, and 6 old subdivisions left unmatched.
- 135 model requests, 300 s in all.

CIV 5855, 2023 to 2025:

| Old | New | Reading |
|---|---|---|
| (a) | (a) | Without substantive change (model) |
| (b) | (b) | Unchanged words |
| (c) | (f) | Moved; with changes: "notice period 15 days -> 14 days", the written notice of the board's decision |
| (d) | (g) | Moved; unchanged words |
| none | (c), (d), (e) | New: the opportunity to cure, internal dispute resolution, the written agreement |

CIV 5850, 2023 to 2025: (d) moved to (f), and (d) and (e) are new. CIV 5105, 2021 to 2023: (f), (g), and (h) moved to (g), (h), and (i). CIV 5105, 2023 to 2025: old (i) and new (i) were left unmatched. That is a miss, kept as one.

## What is trustworthy

- **Where a former section went** (the pair). The model alone is no better than TF-IDF on this Act; the recodification kept most of its words. Where the model and the lexical baseline agree, the pair was right 97.7% of the time at the unit level and 92.8% at the section level. Treat that tier as a strong lead. A pair only one of them finds, or a pair in the "or" tier (recall 0.94), is a candidate for a person to read.
- **Without substantive change against with changes.** Neither reading is reliable. The model found 43% of the Comments' "with changes" pairs, and 72% of its "with changes" calls were pairs the Comments call unchanged. A consumer that skips `continued_without_substantive_change` will miss some real changes. Use the Commission's Comment where one exists. Elsewhere, read the verified change phrase and its quotes; the phrase is the evidence.
- **Amended sections.** Unchanged words and letter moves are exact (`text_identity`). The model's change phrases in the amended case quote both editions and were right on 5855. They are still leads.
- **New and not continued** are only as good as the matches. On the full Act, `new` scored F1 0.63 for the model and 0.77 for either reading.

## How jason should use it

- For a former citation, use the disposition table first (`jason.community.succession`), the Comment for the change class, and then this aligner's subdivision and change phrase.
- For an amended current section, read `amended.json`: a moved letter, a new subdivision, and the change in a phrase with both editions' words.
- Never pin a row because the aligner produced it.

## Limits

- **One edition per side.** The former text is the 2011 edition and the current text is the 2013 edition. Amendments to the former sections in 2012 are not in the 2011 text, and the table describes the bill as enacted.
- **Top-level units.** The table often reads finer than the units do, at a paragraph, a sentence, or the "last ¶". Those rows are scored at their top-level letter. Four rows name no letter jason can read (`1358(last ¶)`, `1363.07(except (a)(3)(F))`, and similar), and these are left out of the unit score.
- **Candidates bound recall.** A target the candidates miss cannot be found. The run reports this ceiling as candidate recall.
- **Quotes prove presence, not equivalence.** A verified quote shows that the words are there. It does not show that the model's relation is right. The change class is the weakest part, and the Comments are the check.
- **A miss stays a miss.** `not_continued` and `new` mean no verified reading found a predecessor. They do not mean the law has none.
- **Not the law.** The statute text in force is the law. A board corrects a governing document's cross-references by resolution (CIV 4235). jason only says where they point.
