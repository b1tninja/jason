# Reading OCR into words: post-correction for intake and review

A scanned instrument's OCR is mostly right and wrong in a few repeatable ways. jason reads the OCR again, word by word, with what it knows about the language the document must be in, and turns each doubt into a **suggestion**: a reading of a few tokens, with the method that read it, its evidence, and a guard. A suggestion is never a silent edit. It becomes a question in the intake queue (`jason intake`), and only a person's answer becomes a transcription (`living.Correction`, kind `TRANSCRIBED`). This page is the design, the measurements behind it, and how it plugs into `jason sop document-intake`.

Code: `jason.community.lexicon` (what a word may be; the language model), `jason.community.ocr_correct` (the text rules, the guard, agreement), `jason.community.ocr_models` (the local text and vision models as readers), `jason.tasks.ocr_correct` (the corpus, second readers, the library's sidecars), and `jason.tasks.intake.ocr_reading_asks` (the queue).

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
| local model | the tokens the lexicon doubts, marked in the passage; the model answers only for those | `ocr_models.OllamaTextCorrector.marked` |
| local model as a scorer | the model chooses among the lexicon's readings with one letter, weighted by its token probabilities (Ollama's `top_logprobs`) | `OllamaTextCorrector.choose` |
| vision | the word's crop of the page image, with its line for context | `ocr_models.VisionWordReader` |
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

## Where it runs

- **`jason intake --scan`**: for each living document whose base is a scan, or that has a working copy.
  - The text rules read every unamended provision (`tasks.intake.ocr_reading_asks` with a `lexicon`).
  - Where the working copy differs by a few words, its reading and the rules' are compared. Agreement with a clean guard is likely.
  - Where the copy keeps the OCR's reading against a confident rule (its own slip), the rules' reading is asked.
  - A one-reader suggestion is not asked. It is kept in `data/living/<key>/ocr-suggestions.json`.
- **`--model`** adds the local text model (marked suspects, `qwen3.5:9b`) as a second reader. `preflight` runs first and the model is released after.
  - On the declaration it took 93 s.
  - It turned 333 held suggestions into likely questions that a person can accept in a batch after a look (`jason intake --accept-likely --by NAME`).
- **`--vision`** reads the page's crop for each guarded suggestion: a number or an operative word.
  - The model is `JASON_OCR_MODEL`, else `OllamaVisionOcr`'s.
  - Word boxes are cached as `<scan>.words.json` beside the scan.
- **`jason intake --library-ocr [--library-kind KIND]`** writes `data/library/text/<id>.ocr-suggestions.json` beside each library text an OCR engine or the vision model read. It lists the worst-read files first, by their share of suspects.
  - The `.txt` is never rewritten: a reading is evidence.
  - A file near the top is one to read again with the Tesseract tool or the vision model.

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
- **qwen3.6:27b** as the text and vision reader, when commit allows (`preflight`).
- **`tessdata_best`'s `eng` model** (about 15 MB, from the tesseract-ocr project's `tessdata_best` repository). Downloading it is a person's step.
- **Tesseract's word confidences** (the tool's `tsv`) as a second detector beside the English prior.
- **Structure from a document model** (headings and numbering, the outline's weak spot): PaddleOCR-VL, MinerU, granite-docling, olmOCR. See the trials table in [document-tools.md](document-tools.md).
