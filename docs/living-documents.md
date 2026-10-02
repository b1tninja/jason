# Living documents

A governing document is amended over time. The declaration is restated, then amended once, then again; the bylaws, the operating rules, and the policies change too. A reader needs the document **as it stands today**, and for each section **which instrument last set its words, when, and whether that instrument ever took effect**. This page is the design for keeping that text: computed from the base document and the amendments' own words, checked against the copy a person keeps by hand, with editorial corrections and annotations kept apart from both.

The code is `jason.community.living` (records, readers, and the apply step) with tests in `tests/test_living.py`. Commands and the profile's rows are proposed below and not built yet.

## What jason already has

| Piece | Where | Use here |
| --- | --- | --- |
| `Amendment` mixin on `Document`: the sections an instrument changes, adoption and recording dates, recorder number | `src/jason/community/documents.py`; the profile's rows in `mystique/ccrs.py` | the instrument's standing and dates; the sections it says it changes check the operations read from its text |
| `GoverningDocument.instruments`: the original, then each amendment in order | same | the order the operations apply |
| Outlines: each Doc's sections, numbered as documents cite them, with char spans into the text | `src/jason/community/outlines.py`, `src/jason/tasks/outlines.py`, `data/outlines/*.json` | the base document's sections (`provisions_of`) and the working copy's sections (`drift`) |
| `outline_from_text`: sections from a PDF's extract | same | the base from a recorded copy's OCR |
| `CitableDocument.amends`: which outline an amendment's outline amends | the profile's `outlines.py` | which document an instrument's operations apply to |
| `AmendmentRecord`, `amended_sections`, `Approval`: an amendment's sections, authority, ordinal, witness clause, blank date | `src/jason/community/models/governing_recorded.py` | evidence for the standing (a blank `DATED: ____` is a draft) |
| `Supersession`, `apply_supersessions` | `src/jason/community/governing.py` | whole instruments replaced; this page is the same idea per section |
| `Conflict.resolved_by` | `src/jason/community/authority_order.py` | an amendment that resolves a conflict must be in effect and must have changed the conflict's section |
| `LeasingRules` and other rule rows | `src/jason/community/leasing.py`, the profile's `leasing.py` | hand copies of amended terms, to be checked against the current text |
| Text copies | `data/governing/*.md`, `data/library/text/*.txt` | search and quoting; they lose the typographic marks (below) |

What was missing: an amendment as **operations** (not a list of section numbers), a reader for the marks that carry the change, the apply step, per-section provenance, and any check that the hand-kept copy matches.

## How an amendment says what it changes

An instrument states each change with a verb on a cited section, in its operative part (after "NOW, THEREFORE", before "IN WITNESS WHEREOF"):

| Words | `Verb` | Effect |
| --- | --- | --- |
| "is hereby amended and restated as follows", "is amended to read" | `RESTATE` | the section's words become the instrument's words |
| "is amended to add the following subsection", "is hereby added" | `ADD` | a new section after its parent's last subsection |
| "is hereby removed", "deleted", "repealed" | `REMOVE` | the section's words go; often replaced by "Intentionally omitted." |

Many instruments also print the change in type, with a legend: "(stricken out wording will be removed, and bolded wording will be added)". The restated section then reads, for example:

> Not more than ~~two (2)~~ **three (3)** pets may be kept in a Unit at any time.

The struck words are the old text, the bold the new. Unmarked plus struck is the **before**; unmarked plus bold is the **after**. A legend may name underline instead of bold; with no legend, bold means nothing and every run is plain.

## Reading the marks, by source

| Source | Strike | Bold | Notes |
| --- | --- | --- | --- |
| Google Doc (Docs API) | `textStyle.strikethrough` on a text run | `textStyle.bold` | exact. `doc_paragraphs` keeps the styles; `outline_from_doc` and the stored outlines drop them, so the operations read the Doc itself (read-only `documents.get`) |
| Text PDF (a Doc's export) | a thin horizontal drawing (`page.get_drawings()`, a line or a short rectangle) across a glyph's middle band | the span's font flags (`flags & 16`) or a "Bold" font name | the strike is not a font property; match it per character (`rawdict` chars) or a span that starts before the strike reads struck too |
| Scan (image only) | OCR the characters with their boxes; a dark horizontal run longer than about 1.5 line heights in a line's middle band is a rule; a character under it is struck | stroke width: the median horizontal run inside a character against the page's median | OCR garbles struck words ("twenty" read with its rule through it) and can drop a heavily struck line entirely. That is harmless for the after words, which drop struck words anyway; bold can also be inferred as the after words the base does not have |
| Plain text, OCR without boxes, Markdown copies | lost | lost | reads both versions run together ("two (2) three (3)"). An instrument whose legend promises marks, read from such a copy, gets `marks_lost`: its restatements are held out, never applied |

Two details from real instruments: the legend's own example words are themselves struck and bold ("~~stricken~~ out wording ... **bolded** wording"), so the legend paragraph is an instruction, never an operation's words, and a scan's OCR garbles "stricken" (the legend is also recognized by "wording will be removed ... bold"). And the trailing paragraph mark of a removed section can carry both styles; whitespace alone always reads plain.

A trial on a recorded, image-only amendment (300 dpi, PyMuPDF's Tesseract): the measured rules and stroke widths marked every struck and bolded phrase, and the scan's after words matched the Doc draft's after words exactly in two of three operations; the third differed only by a struck letter OCR had glued to the word before it. The drafts and the recorded copy can differ, so a scan's reading is how the Doc draft is confirmed as the recorded text, or not.

## Records

`jason.community.living`:

- `Mark` (`PLAIN`, `STRUCK`, `ADDED`) and `Run(text, mark)`. `StyledRun(text, struck, bold, underlined)` is a run as the source draws it, before the legend says what the styles mean.
- `Operation(section, verb, runs, caption, instruction, marks_lost)` with `before`, `after`, `marked`, and `redline()` (`~~struck~~ **added**`).
- `Standing`: `DRAFT` (unsigned or undated), `ADOPTED` (approved, not recorded), `RECORDED` (number and date on the county's stamp).
- `Effect`: `ON_RECORDING` for the declaration and an annexation (an amendment takes effect once approved, certified, and recorded, Civil Code 4270(a)); `ON_ADOPTION` for bylaws, operating rules, and policies. `effect_of(kind)` picks it.
- `Instrument(key, amends, standing, operations, title, adopted, recorded, number, effective)` with `in_effect(effect, as_of)`. Only an instrument in effect applies; a draft's operations never do.
- `Provision(number, caption, body, depth, set_by, dated, standing, history, removed)`: one section's own words (not its subsections'), and who set them.
- `CurrentDocument`: the provisions, the instruments applied and pending, the findings; `provision`, `text_of` (a section with its subsections), `through`, `markdown()`.

Readers: `read_instruction` (section, verb, quoted caption from "Article 4, Section 4.2 (“Use”), subsection (b), subpart (ii) is hereby ..."), `legend`, `read_operations` over paragraphs of styled runs, `operations_from_doc`, `operations_from_text`.

## Applying

`consolidate(base, instruments, as_of=, corrections=)`:

1. The base outline becomes provisions: the preamble, then each section's own words, its caption split off (a Doc puts it on its own line; an extract runs "Caption. Words" together).
2. Editorial corrections apply to the base (below), so the before words meet a clean reading.
3. Instruments apply in date order (effective, else recorded, else adopted), each operation in its own order. One not in effect is listed as pending.
   - `RESTATE` sets the section's words. A section whose subsections run inline ("shall provide (i) that ..., (ii) that ..., and (iii) that ...") is split when an operation cites one of them. A restated section's existing subsections give way to the new words (a finding), and subsections the new words list a line each are split out.
   - `ADD` inserts after the parent's last subsection, or replaces a section already there (a finding when the words differ). OCR's "(0)" is "(o)": no subsection is numbered zero.
   - `REMOVE` sets the words the instrument gives ("Intentionally omitted.") or marks the section removed, with its subsections.
4. Remaining corrections apply; one whose words are gone is stale.

Each provision keeps its `history` ("base", "split inline", "<instrument>: restate", "correction (ocr)") and the last setter's key, date, and standing.

### Findings

A finding is a lead for a person, never silently resolved.

| `FindingKind` | Meaning |
| --- | --- |
| `NOT_IN_EFFECT` | a draft, or an amendment to the declaration not yet recorded: listed, not applied |
| `MARKS_LOST` | the legend promises marks; this copy has none: read the Doc or a PDF that keeps them |
| `TARGET_MISSING` | restates or removes a section the base does not have (with the section whose words it quotes, if any) |
| `BEFORE_DIFFERS` | the words the instrument shows as before are not the base's: applied anyway (a restatement adopts its words), with the word changes |
| `QUOTED_ELSEWHERE` | its before words are another section's: a drafting error in the instrument |
| `ALREADY_APPLIED` | the base reads closer to the after words: the base is a copy already amended by hand |
| `ALREADY_PRESENT`, `NO_CHANGE`, `SUBSECTIONS_REPLACED` | as named |
| `DRIFT` | a copy of the document differs from the consolidated text |
| `EDITORIAL` | a copy carries an editor's bracketed note among the words |
| `CORRECTION_REFUSED`, `CORRECTION_STALE` | a correction that would change meaning, or whose words are gone |

`BEFORE_DIFFERS` matters most. A restatement replaces the whole section, so words the drafter left out of the restated text without marking them are removed all the same. The check shows them: `"be kept [in a Unit] at" -> "be kept [] at"`. Whether that was intended is a question for the board or counsel, not for jason.

## Verifying

- **The before check**, above, on every marked operation.
- **The instrument against its draft.** When the operations are read from a Doc draft, read the recorded copy (a scan, as above) and compare the after words. The recorded copy is the instrument; the draft is evidence of it.
- **The working copy.** `drift(current, copy, amended_only=)` compares a copy kept by hand, section by section, with the consolidated text. Its first run on a real declaration found a numeral changed without its words, words the amendment dropped still present, an article dropped twice, and a copy that carried an amendment's change a year before the amendment was signed (its provenance comments were dated before adoption).
- **Rule rows.** A row that hand-copies an amended term (a rental cap, a minimum lease term) names its section; a check reads the number from the current text and reports a row that disagrees. The row keeps the number (facts are data); the living text checks it, as statute passages check theirs.
- **Conflicts.** A `Conflict` resolved by an amendment is checked: the amendment is in effect, and one of its operations changed the conflict's provision.

## The working copy, corrections, and annotations

The person who keeps the association's documents keeps a text version of each as a Google Doc, applies an amendment to it only after confirming the amendment took effect, fixes small errors in it, and annotates it with comments. The design keeps that practice and makes it checkable:

- **The working Doc stays the reading copy.** jason does not rewrite it. It computes the current text independently and reports drift: each difference is either the person's correction (record it as one) or a mistake (fix the Doc).
- **Corrections** are `Correction(section, wrong, right, kind, source, note)` rows with a `CorrectionKind` (`OCR`, `TYPO`, `PUNCTUATION`, `SPACING`). A correction cites what was wrong and how it is known (the page of the recorded copy). `changes_meaning` refuses one that changes a number or an operative word ("shall", "may", "not", "or", "any") or more than two words: that is an amendment's work, or a question for counsel. A spacing fix ("ofanyprovisions") always passes. Corrections are the profile's data, kept with the document they correct.
- **Editorial notes in the text.** A bracketed insertion ("[ Absent from the recorded text. ]") is an editor's note, not the instrument's words. `drift` reports it as `EDITORIAL` and leaves it out of the comparison; generated text prints notes apart from the words, never inline.
- **Annotations** are `Annotation(section, quote, kind, text, author, written, source, resolved)` with an `AnnotationKind`: `QUESTION`, `VAGUE`, `INTERPRETATION`, `CONTEXT`, `DEFINITION`, `OUTDATED_CITATION`, `POLICY_CANDIDATE`, `ACTION_ITEM`, `PROVENANCE`. An annotation is anchored by section and quoted words, never by offset, so it survives a regenerated text: `place` finds it `ANCHORED` in its section, `MOVED` to wherever its words now are, `SECTION` (a note on the whole section), or `ORPHANED` (a finding, never dropped). A `PROVENANCE` note is checked against the computed provenance. A `POLICY_CANDIDATE` or `VAGUE` note is a lead for the board's rule proposals ("where the law is silent, write it down"); an `OUTDATED_CITATION` note joins the citation conflicts.
- **The seam with Doc comments.** Annotations are imported from the working Doc's comments, read-only: the Drive API's `comments.list` (with an explicit `fields`) gives each comment's text, its quoted text (`quotedFileContent.value`), replies, and whether it is resolved; `source` keeps the comment id so the next import updates rather than duplicates. A comment whose quote is empty had its passage edited away; it imports as orphaned, and the Drive revisions API could recover what it was attached to (an option, not built). Writing comments back is a later, gated step: Docs does not render the anchor of a comment created through the Drive API, and the Docs API's anchored comment request is in developer preview, so a written comment would be unanchored with its quote until that changes. The annotations themselves are private working notes: `data/annotations/<key>.json`, never checked in.

## Specification

The profile pins what a person has confirmed; jason reads the rest.

- **Standing from the pins already there.** An `Amendment` with a recording date and number is recorded; with only an adoption date, adopted; with neither, a draft (`living.standing_of`). A declaration's amendment takes effect on recording (`Effect`).
- **A living document row.** `LivingDocument(key, title, kind, base, base_from, instruments, corrections, checks, working_doc)`, returned by `Community.living_documents()` (empty by default):
  - `base` and each `LivingInstrument.source` is a `SourceRef`: a Google Doc read with its runs (`SourceKind.DOC`, by Drive id) or a library text extract (`SourceKind.LIBRARY_TEXT`, by library path). A library source pins the `sha256` a person reviewed; a file whose digest changed is held out until it is reviewed again. A Doc is read at its current revision, which the report names.
  - `corrections` are the `Correction` rows for the base's OCR slips.
  - `checks` are `TextCheck(section, expect, rule)` rows: a rule row that copies a term of the document (a rental cap, a minimum lease) must find its words in the current text, or the two disagree and a person decides which is wrong.
  - `working_doc` is the reading copy a person keeps by hand.
- **Stores** (private): `data/living/<key>/current.md` (the generated text), `data/living/<key>/report.json` (applied, pending, held, findings, checks, drift, the Docs' revisions), `data/living/<key>/sources/<drive id>.json` (each Doc as last read), `data/annotations/<key>.json` (the annotations; a person may change a `kind` and mark `kind_set_by_person`, which a later import keeps).

## Surfaces

```bash
jason living                              # the living documents
jason living ccrs --fetch --working       # read the Docs again (read-only), build, compare the amended sections
jason living ccrs --all-sections          # compare every section (mostly the base's OCR slips until reconciled)
jason living ccrs --redline ccrs-2nd-amendment
jason living ccrs --section "4.15(a)"     # one provision with its history
jason living ccrs --as-of 2023-01-01      # the text in force on a date
jason living ccrs --annotations           # the working copy's comments, read-only, placed on the text
```

- The generated text reads "as amended through" its last instrument, with a note under each amended section and a list of what is not in effect. It is not an official restatement; the recorded instruments control.
- An annotation is placed on the current text, else on the working copy (where a base read by OCR garbles the quoted words), else reported as orphaned. A comment's kind is first read from its words (`living_docs.kind_of`) and a person corrects it.
- Not built yet: the scan reader in `jason.community` (the rule and stroke measures above) and a text-PDF reader; the generated Doc; an MCP tool.

## Failure modes

- **The base is a hand-amended copy.** Applying an amendment to a copy that already carries it gives `ALREADY_APPLIED` and `BEFORE_DIFFERS`. Consolidate from the recorded base, then compare the working copy with `drift`.
- **The before words differ from the base.** Applied and reported; the person decides whether the drafter changed words silently, the base copy is wrong, or OCR misread it (a correction).
- **Two amendments touch one section.** They apply in date order; each sets the words and the history shows both. A later instrument's before words should equal the earlier one's after words; when they do not, `BEFORE_DIFFERS` names the gap.
- **A draft, or an unrecorded amendment to the declaration.** Never applied, listed as pending. A copy that already carries its change is drift.
- **A draft with copy-paste errors.** An operation whose section is absent and whose words are another section's gets `TARGET_MISSING` with that section named.
- **Scans.** Struck words OCR badly or not at all; read the rules and stroke widths, and confirm against a draft. Page furniture (running footers) must be dropped before the words are read.
- **The instrument's own slips.** A witness clause naming the wrong ordinal or a lower-case defined term in restated words: the instrument's identity comes from its title, recitals, and recording, and its words are applied as recorded. A correction can fix a slip in the reading copy, never in the operative text.
- **A miss stays a miss.** An instruction jason cannot parse yields no operation; the profile's list of sections the instrument changes then disagrees with the operations read, which is itself a finding.

## Open questions for the person

- Which copy is the base for each document: the recorded instrument's extract (authoritative, noisy OCR) or the working Doc after a person reconciles it with the recorded copy? The design assumes the recorded copy, with corrections for OCR.
- When the working Doc differs from the consolidated text, which differences are the person's intended corrections? Each becomes a `Correction` row or a fix to the Doc.
- Should the generated current text become the Doc others read, with the working Doc retired, or should the working Doc stay the reading copy with jason only checking it?
- Should a restatement that drops words without marking them go to counsel before the current text is published?

## Phases

1. Done: the records, the readers for Doc runs and plain text, the apply step, the before check, drift, corrections, annotation placement (`jason.community.living`).
2. Done: the profile rows (`LivingDocument`, sources with reviewed digests, corrections, checks) and `jason living`.
3. The scan reader in `jason.community` (the rule and stroke measures above), and the text-PDF reader.
4. Done: annotations imported from Doc comments, and rule rows checked against the current text. Conflicts checked against it: not yet.
5. The generated Doc, and the MCP tool.
