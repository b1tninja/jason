# Reading OCR into words: post-correction for intake and review

A scanned instrument's OCR is mostly right and wrong in a few repeatable ways. jason reads the OCR again, word by word, with what it knows about the language the document must be in, and turns each doubt into a **suggestion**: a reading of a few tokens, with the method that read it, its evidence, and a guard. A suggestion is never a silent edit. It becomes a question in the intake queue (`jason intake`), and only a person's answer becomes a transcription (`living.Correction`, kind `TRANSCRIBED`). This page is the design, the measurements behind it, and how it plugs into `jason sop document-intake`.

Code: `jason.community.lexicon` (what a word may be; the language model), `jason.community.ocr_correct` (the text rules, their `Options`, the guard, agreement), `jason.community.ocr_channel` (the confusions a recognizer makes, learned from aligned text), `jason.community.ocr_vocab` (candidates by search of the vocabulary), `jason.community.ocr_models` (the local text and vision models as readers and scorers), `jason.tasks.ocr_correct` (the corpus, routing to the page, second readers, the library's sidecars), `jason.tasks.ocr_synth` (rendered statutes read back, for the channel), and `jason.tasks.intake.ocr_reading_asks` (the queue).

## Why an English prior holds

A recorded instrument in California is in English. The recorder may not accept for record an instrument "executed or certified in whole or in part in a language other than English" unless a certified English translation goes with it (Gov. Code 27293(a), (b)). English is the state's official language (Cal. Const. art. III, sec. 6(b)), and court proceedings are in English (Code Civ. Proc. 185(a)). So every token of the declaration, an amendment, an annexation, a deed, or a lien should be one of a few things:

- an English word: the clean legal corpus on disk (the statutes jason exported, the governing documents kept as Docs) and a general English word list (`wordfreq`, an optional extra);
- a number, date, amount, or citation ("4.15(a)", "$1,250.00");
- a section label ("(iv)");
- an abbreviation ("FHLMC", "U.S.");
- a defined term or proper noun the document itself uses: its quoted defined terms and the capitalized words it repeats (`lexicon.document_terms`);
- a legal term of art in Latin or law French ("et seq.", "pro rata", "lis pendens", "mutatis mutandis").

Anything else is an OCR suspect (`Lexicon.classify`). For an unrecorded rule or policy the prior is practical, not legal: those are English in practice, and a translated notice is not. So `lexicon.language_of` names a passage's language first (the share of its words each language's list knows, or its script), and a passage in another language is never "corrected" into English.

A word list alone is not enough. General English lists are built from web text and carry run-together noise ("ofthe" is in one at about two in a million words), so a string the list knows only weakly, and that splits into words far likelier together, is a suspect too (`TokenClass.RUN_TOGETHER`). A word of the clean corpus is never split ("therein").

## The readers

| Method | What it reads | Where |
|---|---|---|
| layout | a word broken at a line's end, a stray bar or speck, a page number in the running text (`- 12 -`), a curly quote the OCR could not encode, a label's bracket (`{c)`), a label misread in its series (`(il)` after `(i)`), a word and its punctuation run together | `ocr_correct.layout_suggestions` |
| lexicon | run-together words split by Viterbi over the language model; a non-word read as the likeliest word one or two OCR confusions away (`rn`/`m`, `li`/`h`, `1`/`l`), ranked by the words around it (a noisy channel) | `ocr_correct.correct_token`, `readings` |
| lexicon, with `Options` | the same, with a learned channel (`ocr_channel`), a vocabulary search for words within three edits (`ocr_vocab`), a corrected word's capitals from its sentence and the document's defined terms (`case_for`), a defined term ranked up, and a real word read as another where the channel and the context favor it (`real_word_readings`); each is an option, and no option is the first version | `ocr_correct.Options`, `intake --ocr-options` |
| local model | the tokens the lexicon doubts, marked in the passage; the model answers only for those | `ocr_models.OllamaTextCorrector.marked` |
| local model as a scorer | the model chooses among the lexicon's readings with one letter, weighted by its token probabilities (Ollama's `top_logprobs`) | `OllamaTextCorrector.choose` |
| vision | the word's crop of the page image, with its line for context; sent every word the English prior doubts and the real words the channel doubts (`routed`) | `ocr_models.VisionWordReader`, `tasks.ocr_correct.routed` |
| vision as a scorer | the crop and the lexicon's readings; one letter back, weighted by its token probabilities (Ollama returns `top_logprobs` on a request that carries images) | `ocr_models.VisionChooser` |
| vision, a line | the line's crop; the reading is taken only on the tokens the rules doubt | `ocr_models.VisionLineReader`, `line_suggestions` |
| working copy | a person's hand-kept transcription of the same text | `tasks.intake.ocr_reading_asks` |

The lexicon and layout rules read the same OCR with the same knowledge, so they count as one reader ("text rules"). The others each read something different.

## The guard and the tiers

`ocr_correct.guard` says why a suggestion may not be taken without a person reading the page. It reuses `living.changes_meaning`:

- a number changes, or an operative word (shall, may, not, or, and, any, no, except, unless, more, less, than, and the rest of `_OPERATIVE_WORDS`);
- a word is added or dropped beyond the suggestion's span (the spirit of Code Civ. Proc. 1858: insert nothing omitted, omit nothing inserted). A run-in caption the working copy leaves out is never junk;
- spacing alone always passes: it changes no character.

`ocr_correct.tier` sets the queue's confidence:

- **likely**: two independent readers agree and the guard passes. For a guarded change, one of the two must be the page itself: the vision model's crop, or a person.
- **suggested**: one reader, or a guarded change without the page.
- **conflict**: readers disagree; each reading is a choice.

Agreement among independent readers as a training-free confidence is the idea of "Consensus Entropy" (Zhang et al., 2025, arXiv:2504.11101): right readings converge, errors scatter.

## Measurements (October 2, 2026)

**The test set.** The county's recorded copy of the restated declaration (56 pages of crisp type), against the working copy a person keeps as a Doc. Both are aligned whole, and the scoring leaves out the sections an amendment set and any block of more than six words that differs (structure: captions, the table of contents, page furniture). That leaves 26,736 reference words. The working copy has slips of its own ("ofCalifornia", "Iease"), so a "harm" where the copy keeps the OCR's reading is counted apart. The language model never saw the declaration's own text. Scripts are in the session scratchpad (`ocr/`).

**Strategies on the cached OCR text** (word error rate and character error rate against the working copy; a suggestion is right when removing it, with the others applied, adds errors):

| Strategy | WER | CER | Suggestions | Right | Harm | Harm where the copy keeps the OCR's reading | Time |
|---|---:|---:|---:|---:|---:|---:|---|
| The OCR as cached (PyMuPDF page OCR, 300 dpi) | 8.63% | 1.20% | | | | | |
| 1. Word segmentation (lexicon) | 3.37% | 0.75% | 718 | 704 | 1 | 8 | 12 s cold |
| 2. + noisy channel for non-words | 3.22% | 0.73% | 763 | 743 | 1 | 8 | |
| 3a. Layout rules alone | 7.93% | 0.99% | 166 | 145 | 0 | 1 | under 1 s |
| 3. Text rules: layout + lexicon | **2.49%** | **0.52%** | 927 | 897 | 1 | 9 | under 1 s warm |
| 3, only what the guard passes | 2.80% | 0.64% | 880 | 851 | 1 | 9 | |
| 3 without `wordfreq` (the corpus only) | 2.75% | 0.58% | 1,003 | 899 | 1 | 74 | |

- The one true harm split "toService" where the copy reads "to.service". The nine copy-kept harms are the copy's own slips ("ofRecord", "orby"); the text rules read them right.
- No suggestion changed a number or an operative word that was right. 46 right suggestions were guarded (page numbers, "shail" to "shall") and wait for the page.
- Without the general word list, the noisy channel "corrected" 62 real words the small corpus lacks. `wordfreq` earns its place.

**The English prior alone, as a detector.** It flags 65% of the OCR's wrong tokens and 0.22% of its right ones; several of those are the copy's own slips. Most of what it misses is punctuation, labels, and real-word errors ("maybe" for "may be"). The share of a passage's words no English list knows tracks its error rate: Spearman 0.66 over 199 passages, with a mean WER of 6.5% in the cleanest quarter and 14.0% in the worst. It flags a page to read again. Told a made-up Spanish notice, a Vietnamese one, and an English sentence with Latin terms of art, `language_of` named each correctly.

**The source: Tesseract's own words.** Most of the error was not Tesseract's. PyMuPDF's page OCR takes Tesseract's characters and builds words itself, losing the narrow spaces of justified type. Tesseract's command-line tool, with the same `eng` model at the same 300 dpi, keeps them:

| Reading of the whole declaration | WER | CER | Run-together joins |
|---|---:|---:|---:|
| PyMuPDF page OCR (`get_textpage_ocr`), its words | 8.12% | 1.00% | 784 |
| Tesseract tool (`tsv`), its words | 2.23% | 0.46% | 63 |
| The tool through `scan_marks.scan_text(engine="tesseract-cli")` | 2.28% | 0.47% | |
| The tool, then the text rules | **1.76%** | **0.40%** | 102 suggestions, 93 right, 0 harm |

On ten pages, the tool's options changed little: 300 dpi 1.82%, 200 dpi 2.49%, 400 dpi 1.84%, a 3,481-word legal `--user-words` list 1.82%, label `--user-patterns` 1.80%, `--psm 6` 2.08%. PyMuPDF on the same pages read 7.94%. `ocr.TesseractCli` is now an engine, ahead of `PyMuPdfTesseract` in `ocr.engines`, and `scan_text` uses it when the tool is installed. A base text already cached keeps its reading and its transcriptions; reading it again is a person's decision.

**Local text models** (qwen3.5:9b; 60 passages, 8,282 reference words, the OCR at 8.89%):

| Variant | WER | Suggestions | Right | Harm | Edits to right words, cleanest quarter |
|---|---:|---:|---:|---:|---|
| Text rules, for comparison | 2.66% | 280 | 267 | 1 (+3 copy slips) | 0.4 per 1,000 |
| 4a. Marked suspects | 2.75% | 298 | 275 | 3 (+3), one adding a word | 0.4 per 1,000 |
| 4a, minimal edits that pass the guard | 2.99% | 265 | 254 | 0 (+3) | |
| 4b. Explicit expectations (below) | 4.88% | 226 | 196 | 2 (+12) | 3.6 per 1,000 |
| 4b, minimal edits that pass the guard | 4.90% | 192 | 173 | 1 (+6) | 1.8 per 1,000 |
| Likely tier: text rules and a model agree, guard passes | | 249 | 241 (96.8%) | 1 (+3) | |

- **Marked suspects** is the model at its best: 0.6 s a passage, as good as the text rules, and it confirms them. The text rules' suggestions the model also made were 96.9% right; the ones it did not make, 76.2%.
- **Explicit expectations.** The model was told what the text is, what OCR errors look like (made-up examples of each), and what never to do. It was asked for JSON corrections with a kind, a reason, and a confidence. It missed run-together words and quoted 52 "originals" that were not in the passage. It also "fixed" the drafting: "is not apportioned" to "are", an article number to a roman numeral, a garbled commission number to an invented one, and a whole sentence to another. On clean passages it changed right words nine times as often as the rules. Free generation over-corrects. The ICDAR 2026 post-OCR report names this as the recurring failure.
- **Calibration of 4b's corrections:**
  - Stated confidence of 0.99 or more: 97% right (150 corrections). From 0.95 to 0.99: 67% right and 18% harmful (55). Below 0.95: under half right.
  - Self-consistency (three more samples at temperature 0.3): all three agreeing, 94% right; fewer, 64 to 73%.
  - The text rules making the same correction: 96% right (170); not making it: 57% (56).
- **Which signal separates right from wrong** (AUC; precision at the threshold that keeps 90% of the right corrections):

  | Signal | AUC | Precision at 90% kept |
  |---|---:|---:|
  | stated confidence | 0.82 | 0.89 |
  | self-consistency | 0.73 | 0.89 |
  | agreement with the text rules | 0.82 | 0.87 |
  | the original holds a non-word (the English prior) | 0.77 | 0.94 |
  | self-consistency and agreement together | **0.88** | **0.93** |

  **Agreement between independent readers sets the likely tier.** A model's stated confidence is a filter, not a second reader.
- **The model as a scorer** (4c): over 212 suspect tokens, the model chose among the lexicon's top readings and the token as read. It took 0.08 s a token, read from the letter's probability.
  - The lexicon's top reading was right 194 times, the model's 195, and their product 197.
  - All three over-corrected 3 of 7 right tokens, mostly the copy's slips.
  - The model's probability is calibrated: 0.95 or more, 98% right; 0.8 to 0.95, 93%; under 0.8, about 40%.
  - It never writes a reading it was not given.
- qwen3.6:27b was not tried: `preflight` refused it, about 25 GB of commit needed and 17.9 GB free with nothing loaded.

**Vision re-read of a word's crop** (qwen3.5:9b, the word and its line from PyMuPDF's word boxes at 300 dpi; 50 sampled suspects):

- Of 36 misread words, it read 30 as the working copy has them. Its misses were a damaged glyph, two words it left as the OCR read them, and a cut-off word.
- It kept 10 of 10 rare but right words ("reoccupy", "unenforceability"): no over-correction.
- It read 4 of 4 of the copy's run-together slips as two words.
- It read the notary's commission number that no text rule could.
- It took 0.22 s a crop.
- Anchoring (giving it the OCR's line and the word in doubt, after olmOCR) read 28 of 36: the anchor pulled it toward the OCR's mistake. The plain crop is the default.
- Where the lexicon and the vision model agreed (38 of 50), both were right every time.

**Other scans.** Four governing instruments that AnythingLLM's collector OCR'd (tesseract.js):

- Their suspect share fell from 3.1% to 0.7% after the editorial suggestions, mostly stray bars and specks.
- Vision transcriptions of 25 files are cleaner (0.9% suspects). There the rules find mostly the drafters' own typos ("contactor"). Those stay single-reader suggestions that a crop settles. A vision transcription's bars, bullets, and checkboxes are text (`tables=True`).

## Measurements, October 5, 2026: the word layer

The question: make the obvious misreads the right English words, using the local models for candidate selection, context, and image-to-text. The line that started it (made up here, with the same faults): "the integrity ot Lhe tJnit and the roof". The text rules left all three: "ot" is a word the list knows, so it is never a suspect; "Lhe" was read "The" (the OCR's capital L copied onto the right word, mid-sentence); "tJnit" had no candidate (a wide "U" read as two glyphs, "tJ", which the hand list has no rule for, and the candidate search lowercased the "J" and allowed only one arbitrary edit).

**The test sets.** The same alignment and scoring as October 2 (the restated declaration against the working copy; WER and CER; a suggestion is right when removing it, with the others applied, adds errors, harm when keeping it does; harm where the copy keeps the OCR's reading counted apart, written "+N"; the cleanest quarter of sections for edits to right words), rebuilt in scratch because the first scripts were gone. The numbers differ a little from October 2's table because the sections are numbered as builds now number them (`aligned`); today's rules read 2.22% where that table read 2.49%, with 1 harm and 9 copy-kept, as then. About 26,500 reference words, and six readings of the same scan, so the noise is varied:

| Reading | WER as read | Today's text rules |
|---|---:|---:|
| PyMuPDF's page OCR, 300 dpi (the cached original) | 7.94% | 2.22% |
| The Tesseract tool, 300 dpi (what `scan_text` reads now) | 1.99% | 1.59% |
| The tool at 150 dpi | 2.31% | 1.89% |
| The tool at 110 dpi | 4.00% | 3.23% |
| The tool at 85 dpi | 11.52% | 7.23% |
| The embedded text layer of the certified copy's PDF (a different scan and an older engine; natural errors like the line above) | 5.06% | 4.31% |

Only resolution was varied. No preprocessing (binarization, despeckle, deskew) was measured; that is the preflight work's. The word layer reads what the engine gives it, so the order is: preflight rendition, Tesseract, then these readers.

Anything learned (a channel, a threshold) was scored on sections it never saw: five folds of contiguous sections, a stand-in for pages, with the other four folds and every reading's aligned misreads as training data.

**What the errors are.** Each differing block of the raw reading, by kind (edits; the share today's rules remove in brackets):

| Class | Tool 300 dpi | Certified copy | Tool 85 dpi | PyMuPDF 300 dpi |
|---|---:|---:|---:|---:|
| segmentation (run together, split) | 116 (53%) | 157 (66%) | 849 (92%) | 1,508 (92%) |
| digit (numbers, "two(2)", "1/12th") | 105 (2%) | 499 (6%) | 312 (11%) | 119 (10%) |
| punctuation | 71 (8%) | 53 (8%) | 614 (7%) | 209 (54%) |
| label ("(i)" for "(a)", structure) | 51 (0%) | 113 (0%) | 124 (2%) | 49 (0%) |
| non-word, one slip ("shail") | 39 (67%) | 122 (45%) | 200 (70%) | 41 (68%) |
| real word for another ("ot" for "of") | 40 (0%) | 87 (0%) | 285 (0%) | 41 (0%) |
| two glyphs for one, a letter added ("concem") | 8 (50%) | 38 (29%) | 68 (46%) | 7 (57%) |
| case | 18 (0%) | 49 (0%) | 21 (0%) | 13 (0%) |
| dropped or added word, other | 85 | 239 | 617 | 135 |

Much of "label", "digit", "dropped", and part of "real word" and "case" is the working copy's own structure and slips ("ln" for "In", "alI" for "all"), a floor no reader reaches. On the clean reading what is left for a word-level reader after today's rules is a few dozen words in 26,700 (about 0.1%); on the noisy ones it is 1% to 2%, mostly real-word errors (285 raw at 85 dpi), non-words, and two-glyph misreads.

**Candidate recall** (how often the right word is among the candidates; it caps any chooser, text or vision), on words read wrongly one for one:

| Source of candidates | Certified copy, non-words | Certified copy, two glyphs | 85 dpi, non-words | 85 dpi, real words |
|---|---:|---:|---:|---:|
| the hand list (today) | 47 of 68 | 11 of 25 | 83.7% | 80.0% |
| + the learned channel | 49 of 68 | 14 of 25 | 90.3% | 85.2% |
| search of the vocabulary within three edits, scored by the channel | 64 of 68 | 20 of 25 | 92.4% | |
| Tesseract's own glyph alternatives (`lstm_choice_mode`, hOCR) | | | 35.8% | 25.2% |
| union of all | | | 93.4% | 85.5% |

Tesseract's alternatives add about one point beyond the channel and the search: the per-glyph choices do not line up with the characters of the word the engine finally printed (the dictionary and the beam search change it), so they are a weak source. The misses left are words far from the read ("irnvrng" for "having").

**The learned channel.** `ocr_channel.learn` counts, from each misread word aligned with the word printed, the letter groups the recognizer read for what was printed ("tj" for "u", "rn" for "m"), and divides by the chances it had to misread those letters. Trained on the aligned readings by folds, it learned 117 rules from 744 pairs; trained on rendered statutes (40 pages of statute text, set in a serif face, degraded five ways, read by the tool, aligned: 2,546 pairs, no leakage because it never sees a scan or a record) it learned 197. The likeliest rules, as read > as printed, with the probability the recognizer misreads them:

| Learned from the readings (by folds) | | From rendered statutes | |
|---|---|---|---|
| i > ii | 2.6% | i > ii | 18.9% |
| m > rn | 2.5% | th > fb | 6.3% |
| g > gs | 2.3% | m > rn | 5.8% |
| g > ge | 1.0% | p > pd | 5.4% |
| t > dat | 0.8% | d > db | 3.9% |
| o > to | 0.6% | a > aa | 3.6% |
| f > fa | 0.5% | i > tt | 3.5% |
| b > ble | 0.4% | b > htt | 3.4% |
| a > ad | 0.3% | w > tw | 2.4% |
| i > ir | 0.3% | u > htt | 2.3% |
| a > al | 0.3% | t > htt | 2.3% |
| i > l | 0.2% | b > sb | 1.9% |
| a > q | 0.2% | e > c | 1.8% |
| a > ai | 0.2% | u > tt | 1.8% |
| i > li | 0.2% | f > r | 0.95% |

Many are a letter the engine dropped or doubled ("i" for "ii"); the rendered text's faults are of that low-resolution kind ("th" for "fb"). WER with each channel (the hand list stays beside it):

| Channel | Certified copy | 85 dpi | PyMuPDF | Tool 300 dpi |
|---|---:|---:|---:|---:|
| hand list (today) | 4.31% | 7.23% | 2.22% | 1.59% |
| + learned from the readings, by folds | 4.29% | 7.20% | 2.22% | 1.59% |
| + rendered statutes | 4.25% | 7.18% | 2.22% | 1.59% |
| + both | 4.26% | 7.17% | | |

A small gain, positive on every noisy reading and nothing on the clean ones; the rendered text is the better source and the only one that does not need a scan with a working copy.

**The methods, one switch at a time on top of the one before** (WER; "harm" is right words changed; "clean" is edits to right words per 1,000 in the cleanest quarter; time is cold, per token, on a machine with other jobs running):

| Reader | Tool 300 dpi | Certified copy | 85 dpi | PyMuPDF 300 dpi | Right / harm (certified copy) | Time per token |
|---|---:|---:|---:|---:|---|---|
| OCR as read | 1.99% | 5.06% | 11.52% | 7.94% | | |
| 0 today's text rules | 1.59% | 4.31% | 7.23% | 2.22% | 160 / 3 | 0.1 to 0.6 ms |
| 1 + learned channel (hand list + rendered statutes) | 1.59% | 4.25% | 7.18% | 2.22% | 174 / 3 | 0.4 to 2.8 ms |
| 2 + search of the vocabulary | 1.59% | 4.20% | 7.16% | 2.21% | 188 / 3 | +0.1 to 0.5 ms |
| 3 + case by context, defined terms | 1.59% | 4.22% | 7.14% | 2.21% | 190 / 3 | none |
| 4 + real-word detection, posterior 0.95 | 1.57% | 4.16% | 6.75% | 2.19% | 209 / 3 (+4) | about +0.1 ms |
| 5 = 3 + the page's crop at every suspect | 1.55% | 3.82% | 6.68% | | 321 / 1 | 0.25 to 0.4 s a crop |
| 6 = 4 + the page's crop at every suspect | 1.54% | 3.76% | 6.28% | | 340 / 1 (+4) | |
| 7 = 6 + the page's crop at real words the channel doubts | 1.53% | 3.66% | 6.00% | | 367 / 1 (+4) | |

Harm in the cleanest quarter, per 1,000 words: 0.00 for every step on the certified copy, and on the 85 dpi reading 0.24 today, 0.00 with the crop at suspects, 0.73 at step 4 alone and 0.49 with the crop. On the tool's 300 dpi reading step 4 is 0.41 (3 copy-kept words changed), the crop steps 0.00 to 0.41. Today's rules on the PyMuPDF reading read 0.22.

What each class gains at the end (edits removed of the raw, certified copy / 85 dpi): non-words 55 to 110 of 122 and 140 to 177 of 200; two glyphs 11 to 35 of 38 and 31 to 55 of 68; real words 0 to 36 of 87 and 1 to 151 of 285; digits and labels (where the crop reads a suspect among them) 32 to 87 of 499 and 2 to 44 of 124; segmentation, case, and punctuation did not change. A count of "new" errors rises (23 to 58 on the certified copy) because the crop changes where the alignment cuts a block (page furniture, headings); the per-suggestion count of right words changed (1, +4 copy-kept) is the harm.

**Switch by switch.**
- **Learned channel and search.** Zero added harm everywhere. Words fixed, of the raw errors in a class (certified copy; 85 dpi): non-words 55, 64 with the channel, 70 with the search of 122 (140, 145, 145 of 200); two glyphs 11, 15, 18 of 38 (31, 36, 41 of 68). The search finds words two and three edits away that the old candidate step cannot (it allowed one arbitrary edit, plus a confusion). Cost: a one-time index of about 40,000 words (numpy; about 10 s) and about 0.3 ms a token.
- **Case by context.** `case_for` takes the token's own case when its first letter was read right (a heading's "Restrictinns" is "Restrictions"), and only otherwise a defined term's capitals, a capital after a sentence's end, or the form the clean text mostly writes. A first version that always replaced the token's case lost 17 words to 4; this one is 4 won and 1 lost on the certified copy, 5 and 0 at 85 dpi. WER moves by 0.02 either way. "Lhe" mid-sentence is "the"; "tJnit" is "Unit" only with the next switch.
- **Defined terms.** `lexicon.document_terms` leaves out a word the general list also knows, so "unit" was never a term. `document_term_forms` takes a different test, the words a document writes with a capital in the middle of its sentences nearly every time (in the corpus, "Unit"), and `term_bonus` ranks a candidate in that set up. With the rendered-statute channel and the bonus the line above reads "Unit" (posterior 0.88 against 0.11 for "tJnit"); without it the posterior was 0.51, under the 0.6 bar. The bonus alone moved no whole-document WER.
- **Real-word errors.** The word list knows "ot", so the English prior never doubts it. The noisy channel over real words (Mays, Damerau and Mercer) compares the word as read, with a prior of 0.995 that a real word was printed as read, against the words one confusion away that are at least five times likelier by themselves, in the context of the bigram model. Swept (posterior to take a reading; ratio 5 or 30; the prior; certified copy / 85 dpi / tool 300 dpi, WER and clean-quarter harm per 1,000):

  | Posterior | Certified copy | 85 dpi | Tool 300 dpi |
  |---|---|---|---|
  | none (step 3) | 4.29% / 0.00 | 7.20% / 0.24 | 1.59% / 0.00 |
  | 0.5, ratio 30 | 4.25% / 2.15 | 6.67% / 1.95 | 1.65% / 1.64 |
  | 0.8, ratio 30 | 4.26% / 0.72 | 6.75% / 1.70 | 1.62% / 0.82 |
  | **0.95**, ratio 30 | 4.25% / 0.00 | 6.81% / 0.49 | 1.57% / 0.21 |

  Below 0.95 it loses on a clean reading (the tool's own at 0.5 reads 1.65% for 1.59%) and above it gains only where the noise is high. So it is an option, on at 0.95 for a noisy reading. The line's "ot" is 0.46 for "of" and 0.31 for "at": the bigram model cannot choose between twins; the page can. The English prior alone flags 383 of 1,389 wrong tokens at 85 dpi; Tesseract's own word confidence (`tsv`) separates wrong tokens at AUC 0.80 to 0.85, and real-word errors among known words at 0.78 to 0.79 (below 60 confidence: 99 right words a thousand at 85 dpi, 4 a thousand on the tool's 300 dpi reading), a useful second detector for gating the channel's suggestion but it needs the engine's confidences kept beside the reading, which the cached text does not.
- **Routing to the page.** A suspect with no candidate, a low posterior, or a real word the channel doubts at 0.2 goes to the crop. The routes are `guarded` (today's), `doubts`, and `suspects` (every one; also the doubted real words). See the next section.

**The page's crop, read by qwen3.5:9b, against the text rules** (token level; the suspects with a known right reading; "fixes" are wrong tokens read right, "harms" right tokens changed to wrong):

| Reading | Wrong as read | Text rules fix | The crop fixes | The crop harms (right tokens) |
|---|---:|---:|---:|---:|
| Certified copy | 263 | 91 (35%) | 222 (84%) | 0 of 20 |
| 85 dpi | 389 | 198 (51%) | 298 (77%), 294 with a known-word gate | 5 of 19 without the gate, 0 with |
| Tool, 300 dpi | 54 | 34 (63%) | 38 (70%) | 0 of 19 |

The gate is `tasks.ocr_correct.usable_reading`: a reading with a "?", spanning lines, of several words where the OCR read one (a crop that took in a neighbour: "reoccupy his"), or that is itself a suspect is not taken. Its five 85 dpi harms were a changed letter ("hypothebate") and four crops that took in a neighbour. A crop read before the rules wins everywhere ("vision first, then rules": certified copy 3.82% against 3.91% for "rules first, the crop where they abstain"; 85 dpi 6.70% against 6.71%; tool 1.55% against 1.56%), so the rules are the fallback.

On the real words the channel flags at 0.2 (certified copy 117 with a known right reading, 63 wrong; 85 dpi 261, 218 wrong; tool 62, 12 wrong):

| Reader | Certified copy | 85 dpi | Tool 300 dpi |
|---|---:|---:|---:|
| the channel alone at 0.95 | 15 of 63 fixed, 6 of 54 right words changed | 96 of 218, 3 of 43 | 6 of 12, 3 of 50 |
| the channel at 0.5 | 27 of 63, 52 of 54 changed | 140 of 218, 41 of 43 | 9 of 12, 48 of 50 |
| the text model choosing among the twins (letter, p >= 0.9) | 11 of 63, 0 | 46 of 218, 0 | 2 of 12, 0 |
| **the page's crop** | **47 of 63, 1 changed** | **161 of 218, 0** | **9 of 12, 0** |
| the vision model choosing among the twins (crop and letter) | 27 of 63, 1 | 160 of 218, 0 | 8 of 12, 0 |

The one right word the crop changed is the working copy's own slip ("tum" for "turn"). The page is the right judge of a real-word error; a language model with no image is not (qwen3.5:9b at p >= 0.9 fixes 11 of 63), and the bigram model is a flagger, not a judge.

**The image-conditioned chooser** (the user's "image-text-to-text candidate selection"): the crop and its line, the token as read and the lexicon's top readings as lettered options and a last "none of these", one letter back, its `top_logprobs` the weights (`ocr_models.VisionChooser`). **Ollama 0.35.0 returns `logprobs` and `top_logprobs` on a chat request that carries images** (qwen3.5:9b: checked on a crop, "B" at 0.95). On the example line it works: "tJnit" among {tJnit, Unit, unit, tunit}: "Unit" at 0.97; "ot" among {ot, of, or, on}: "of" at 0.97 (the plain crop read "ot" back; it read "the" and "Unit" right). Over the suspects it does not beat the plain crop, and does not beat the text chooser either:

| Where the right word is among the options | Certified copy (99) | 85 dpi (213) | Tool (36) |
|---|---:|---:|---:|
| the text rules' top reading | 91 | 198 | 34 |
| the text chooser (qwen3.5:9b, letter) | 97 | 209 | 36 |
| the vision chooser | 77 | 185 | 21 |
| the plain crop | 88 | 166 | 28 |

and its calibration is poor (certified copy: p >= 0.95 right 22 of 36; 0.8 to 0.95 right 27 of 114), against the text chooser's (p >= 0.95: 56 of 65). It is bounded by candidate recall (the suspects' right word is among the options for 101 of 268 at best), which is why the free crop reading is the default and the chooser is for the case where a person wants a reading that can only be a given one. Its guarantee, that it never writes a reading it was not given, is the same as the text chooser's, at the price of that recall.

**A line, re-read** (`VisionLineReader`, `line_suggestions`): the line's crop is read, diffed with the OCR's tokens, and an edit is taken only where it falls on a doubted token and is minimal. Certified copy: 4.29% alone, 4.18% (221 edits), rules plus the line 4.01%; with every edit and no gate 4.08% (255 edits, 2 right words changed). Tool 300 dpi: 1.52% with the gate, 1.51% without (1 right word changed). The line's re-reading drifts little (a 9B model copies a line closely) and the gate costs about nothing, but the word's crop is the better reader (3.82%). 0.44 s a line alone, 3.7 s with the machine busy. The lines the model could not read (an HTTP 500 from Ollama on two readings) were skipped.

**Voting across Tesseract streams** (ROVER style, lexicon-gated; five resolutions, 150 to 400 dpi, against the 300 dpi backbone): 1.99% to 1.86% as read (82 words changed) and 1.58% to 1.53% with the rules after. A gain of 0.05 points; the streams' errors are alike, so it is the preflight's variants (different binarization, deskew) that have room to differ, not resolution.

**qwen3.6:27b was not tried**: `preflight` refused it again, 25.1 GB of commit needed and 17.5 GB free with no model loaded. qwen3.5:9b is Q4_K_M; a higher-precision build (Q8, FP8) is a download a person makes. The crops here are of typed text; the NVFP4 digit loss seen earlier is not tested by them (the crop route reads suspects, never a number).

**The example line under each reader** (a line of the certified copy's text layer, the tokens "ot Lhe tJnit"; qwen3.5:9b for the model rows):

| Reader | "ot Lhe tJnit" becomes | Time |
|---|---|---:|
| OCR as read | ot Lhe tJnit | |
| 0 today's rules | ot The tJnit | 0.4 s the line |
| 1 + learned channel | ot The tJnit | 0.05 s |
| 2 + search | ot The tJnit | 0.2 s |
| 3 + case by context | ot the tJnit | 2 ms |
| 4 + defined terms | ot the Unit | 1 ms |
| 5 + real words (0.95 or 0.5) | ot the Unit | 14 ms |
| the channel's readings of "ot" | of 0.46, at 0.31, ot 0.06, or 0.03 | |
| the page's crop, each word | ot, the, Unit | 1.6 s a word (first load) |
| the vision chooser | Unit 0.97; of 0.97 | 0.14 s |
| the text chooser | of 0.76 (or 0.15); Unit 0.50 against unit 0.48 | 4.4 s (first load) |
| a line re-read | of the Unit, taken on all three | 5 s |

## Where it runs

- **`jason intake --scan`**: for each living document whose base is a scan, or that has a working copy.
  - The text rules read every unamended provision (`tasks.intake.ocr_reading_asks` with a `lexicon` and `Options`).
  - `--ocr-options` (default `search,case,terms`; an empty string is the October 2 rules; `real-words` adds the real-word reader and sends those words to the page) and `data/ocr/channel.json`, if `jason intake --learn-channel` wrote one, set the readings. Search needs numpy and is skipped without it.
  - Where the working copy differs by a few words, its reading and the rules' are compared. Agreement with a clean guard is likely.
  - Where the copy keeps the OCR's reading against a confident rule (its own slip), the rules' reading is asked.
  - A one-reader suggestion is not asked. It is kept in `data/living/<key>/ocr-suggestions.json`.
- **`--model`** adds the local text model (marked suspects, `qwen3.5:9b`) as a second reader. `preflight` runs first and the model is released after.
  - On the declaration it took 93 s.
  - It turned 333 held suggestions into likely questions that a person can accept in a batch after a look (`jason intake --accept-likely --by NAME`).
- **`--vision`** reads the page's crop. `--vision-route` says for which tokens: `suspects` (the default since October 5: every word the English prior doubts, and the real words the channel doubts when `real-words` is on), `doubts` (only the suspects the text rules cannot settle), or `guarded` (the first version's: a guarded suggestion, a number or an operative word, which is always read).
  - A crop's reading must pass `usable_reading` (no "?", one line, one word where the OCR read one, and not itself a suspect) before it is a suggestion; it enters the queue as the vision reader's, so it makes a question likely when the text rules agree with it, and a reading it alone makes is kept in `ocr-suggestions.json` like any one-reader suggestion.
  - The model is `JASON_OCR_MODEL`, else `OllamaVisionOcr`'s. `preflight` runs first and the model is released after.
  - Word boxes are cached as `<scan>.words.json` beside the scan.
- **`jason intake --learn-channel`** counts the letter groups OCR misread in each scanned living document against its working copy, and in statute text rendered, degraded, and read back by the Tesseract tool (`tasks.ocr_synth`; about two and a half minutes), into `data/ocr/channel.json`. The file holds letters and probabilities, no word of any document, and the next `--scan` reads it.
- **Not wired to the queue:** the vision chooser (`VisionChooser`) and the line reader (`VisionLineReader`, `line_suggestions`) are measured above and are in the code for a person's own use; the default route is the word's crop.
- **`jason intake --library-ocr [--library-kind KIND]`** writes `data/library/text/<id>.ocr-suggestions.json` beside each library text an OCR engine or the vision model read. It lists the worst-read files first, by their share of suspects.
  - The `.txt` is never rewritten: a reading is evidence.
  - A file near the top is one to read again with the Tesseract tool or the vision model.

- **`jason preflight FILE|FOLDER`** ([pdf-preflight.md](pdf-preflight.md)) comes before all of the above for a box of scans.
  - It says which pages are blank (kept in the original, never dropped), which scanner text layers read as English and which to read again, and writes a cleaned page image of each page beside the library (`--render`, never in place of the original).
  - `--ocr` reads that rendition with `ocr.TesseractCli` and keeps each word's box and confidence in `ocr.words.json`, a second detector for the word layer here. The rendition's page images are gray, so the vision model's crops can come from them.
  - The cleaning (`auto`) changes only a page with a measured defect (shading, dust, a tilt over one degree), so on a clean page the reading is the one measured above. Binarizing (Otsu, Sauvola) made the reading worse on every clean set measured.

The language model never learns from the document it reads, nor from that document's working copy (`tasks.ocr_correct.lexicon_for(..., exclude=(key,))`): the copy is a second reader, and a reader that learned from it would only agree with it.

## What the prompts say

The explicit-expectations prompt (`ocr_models.EXPECTATIONS_PROMPT`) is kept for measuring and for a person who wants a model's whole-passage view.

- **It tells the model what the text is:** the OCR of a recorded California governing document, legal drafting in English.
- **It lists what to fix, with made-up examples:** run-together words, a word broken in two, misread letters, misidentified punctuation and brackets, a broken section label, stray marks.
- **It lists what never to do:**
  - change a real word, even one the drafter seems to have meant differently ("shall" and "may", "or" and "and", "any" and "all");
  - change a number or a section number;
  - change a defined term's capitals;
  - modernize, paraphrase, improve, or fix the drafter's grammar;
  - add or drop words.
- **It asks for JSON:** one row per correction, with the original quoted exactly, the corrected text, a kind, a reason, and a confidence.

Measured, it is the least faithful reader (above), so intake uses the marked-suspects prompt (`MARKED_PROMPT`) and the chooser (`CHOOSE_PROMPT`), and holds every model edit to `ocr_models.minimal` and the guard.

## Not done yet

- **Reading the declaration again with the Tesseract tool** would cut its OCR error by three quarters. It is a person's decision: the transcriptions already applied to the cached text name its words, and would go stale.
- **qwen3.6:27b** as the text and vision reader, when commit allows (`preflight` refused it again on October 5: 25.1 GB of commit needed, 17.5 GB free with nothing loaded; raising the page file is a system setting a person makes). Every vision number above is qwen3.5:9b at Q4_K_M; a Q8 or FP8 build is a download a person makes, and the crops should be checked on digits again if the quantization drops.
- **`tessdata_best`'s `eng` model** (about 15 MB, from the tesseract-ocr project's `tessdata_best` repository). Downloading it is a person's step.
- **Tesseract's word confidences** (the tool's `tsv`) kept beside a reading, to gate the real-word reader (AUC 0.78 to 0.79 for real-word errors; measured above, not wired: the cached text carries none).
- **A surprisal map from a causal model** (vLLM `prompt_logprobs`, or a masked model's pseudo-log-likelihood) for the real-word errors: Ollama returns probabilities for the tokens it generates, not for the prompt, so it cannot give one. The measurement above says the page, not a language model, is the judge of a real-word error; a map would only improve the flagging, which with the channel and the bigram model reaches 218 of the 285 real-word errors at 85 dpi (the flagged ones, with a known right reading, among the raw blocks).
- **A page-level transcript from the 27B as a disagreement map** (Consensus Entropy): not run, for the same commit reason.
- **Voting across preflight variants** (binarization, despeckle, deskew), after the preflight work: resolution streams alone gave 0.05 points.
- **Fine-tuned correctors** (ByT5 on the rendered pairs): the measured headroom on a clean reading is a few dozen words, so there is no case for one yet; on a noisy reading the page's crop already reads about three quarters of the misreads.
- **Structure from a document model** (headings and numbering, the outline's weak spot): PaddleOCR-VL, MinerU, granite-docling, olmOCR. See the trials table in [document-tools.md](document-tools.md).
