# The owner's manual: the rules apart, the guide generated

Many associations keep one document that is both a guide for owners and the board's rules: questions and answers, contacts, then the rules, then the enforcement policy and its fine schedule, a collection notice, and an architectural application. The rules bind; the guide does not. Kept in one document, an edit to the guide can look like a rule change, and a rule change can be lost in a rewrite of the guide.

`jason manual` takes such a manual apart. It decides what each section is, by rule rows and evidence. It writes the operating rules as their own official document, word for word. It also makes the manual a base template that is filled from those sources, so the guide never keeps a stale copy. The code is `jason.community.manual` (pure) and `jason.tasks.manual` (disk). The profile's rows come from `Community.owners_manual()`.

## The kinds

**The rule (Civil Code 4340(a)):** "“Operating rule” means a regulation adopted by the board that applies generally to the management and operation of the common interest development or the conduct of the business and affairs of the association."

Each section of the manual's outline is one of these:

| Kind | What it is | Where it goes |
|---|---|---|
| (a) rule | a regulation the board adopted that applies generally | the `rules` book (or a part, `rules.parking`) |
| (b) copy | a copy or restatement of the declaration, the bylaws, or a statute | stays where the board adopted it, named with its source and state |
| (c) policy | a separately adopted policy bound in: the discipline policy and fine schedule (5850), the collection policy and its notice (5730), the architectural procedure and its form (4765) | its own book: `disc`, `coll`, `arch` |
| (d) guidance | contacts, how-to, explanations, recommendations | the manual (`manual`) |
| (e) mixed | a section split at the sentence level | each piece as its kind |

A copy's state is read from evidence, never assumed:

- **verbatim:** the source's words; a punctuation slip at most.
- **edited:** the source's words with some changed, added, or left out.
- **paraphrase:** restated in other words.
- **stale:** matches words the source no longer has.
- **unverified:** the source is not on disk, for example a code jason has not exported.

A section whose kind is open is **unclear**. It becomes a question for a person (`jason intake`, `AskKind.SECTION_KIND`), with jason's suggestion. It is never decided by a guess.

## How a section is classified

**The rows** (`ManualRow`) are the profile's reading. They are matched to the outline's sections in order, and the first match wins.

- **Matching.** A row matches one section; with `through`, a run of sections; with `under`, a section and everything inside its span.
- **Splitting.** A `Piece` splits a section where a sentence starts. A recommendation inside a rule is one example; a statute's notice inside a policy is another.
- **Questions.** A row with a `question` marks the kind as open. The row's kind is the suggestion.
- **Reasons.** A row's `reason` says why.

**The evidence** is attached to every piece, and it checks the rows:

- **Norms.** The deontic grammar reads the duties, prohibitions, and permissions in the words (`jason.community.deontic`).
- **Copies.** The embedded-copy scan reports what it found, with coverage, fidelity, and currency (`data/section-refs/copies.json`, `jason section-refs --scan`).
- **The law.** A copy of a statute is compared with the statute's words on disk (`data/authorities`). Where the statute prints a notice in quotation marks, the comparison uses that passage.

**When the evidence and a row disagree, jason asks.** It does not override the row. A question is asked when:

- a guidance piece states an owner's, member's, or occupant's duty or prohibition and cites no source;
- a rule row covers words the scan finds to be a verbatim or near-verbatim copy;
- a copy row names no source and the scan finds none.

A person's answer becomes the section's kind on the next run.

**A rule row with no norm is only a lead.** It is listed as a grammar lead, not a question. The grammar does not know every drafting form ("are to be", "requires", imperatives).

## Books and numbers

Each piece has a target: its book and its number there. The books come from the closed set in [record-addresses.md](record-addresses.md):

| Book | Holds |
|---|---|
| `rules` | the operating rules |
| `disc` | the discipline policy and schedule (5850(a)) |
| `coll` | the collection policy (5310(a)(6), 5730) |
| `arch` | the architectural review procedure (4765(a)(1)) |
| `manual` | the guide's own words; not a governing document |

**Separately adopted operating rules are parts of `rules`**, such as `rules.parking`. Every operating rule shares one definition (4340(a)), one procedure (4360), and one rank (4205(d)). A part keeps its own numbers. Its words can be read from its own document (`BookSource`).

**A policy goes to its own book** when the law has it travel apart from the rules, or names it apart:

- The fine schedule goes out in the annual policy statement, and a supplement is delivered individually (5850(a), (b)).
- The collection notice goes out each year (5310(a)(6), 5730).
- The architectural procedure is noticed each year (4765(c)).

Each choice is a `BookChoice` row with its reason, so a person can revisit it.

### Numbers

Every number the manual prints is kept: a rule cited as R-7(c) stays R-7(c). The outline reader can make up a number the document does not print. Three cases occur:

- a part's letter glyph is read under the section before it;
- a list under an unnumbered heading is hung from the last numbered section;
- one number is read twice.

The target then gives the number the document prints, and the old number resolves through the concordance (`resolve_old`). `jason manual --concordance` checks every existing citation of the manual through it:

- the notice provisions;
- the assignments;
- the conflict rows;
- the duties store's sections;
- other documents' references.

## The official rules document

Its base is `src/jason/templates/manual/rules.md`, and it renders to `data/drafts/rules-and-regulations.md`. It holds only what the board adopted as its rules, verbatim, in the last adopted words (below):

- **Rule text** (a) is printed as written.
- **A copy the board adopted as a rule's words** (b) stays in place, followed by a bracketed note naming its source and state. Leaving it out would read as a repeal (4340(b)).
- **Guidance inside a rule** (d) is left out. A bracketed note names it and says it stays in the manual.
- **A policy published apart** is named, not reprinted.
- **An open question** is printed as written, with a note.

Bracketed notes are editorial and are not part of the rules.

### The last adopted words, not the working ones

The manual's Doc is edited between adoptions, so its current words are not all adopted text. The revision history (`jason revisions KEY`, `data/revisions/KEY.json`) separates them, as `jason rule-change --from-manual` does (`jason.tasks.manual_rule_change.partition`):

- **(a) adopted, or unchanged since the earliest version on disk**: printed as written;
- **(b) changed with no adoption found**: the official rules print the passage's **last adopted words**, then jason's bracketed note: `_[jason's note, not rule text: Changed between DATE and DATE; no adoption found. The words printed are the last adopted (adopted DATE, RECORD). The working text reads: “…”]_`. A removed passage keeps its adopted words, after the piece it followed, and its note says the working text leaves them out;
- **(c) pending suggestions** in the Doc: never printed, not in the rules' words and not in the working words a note recites. A suggested deletion's words stand until a person accepts it.

**Whose words the earlier ones are.** They are the last adopted words only when an adoption on record covers them: an adoption that cured an earlier change of the passage, an adoption naming the section (or one that holds it, or its book) before the change was first saved, or a change the detector itself tied to an adoption. That adoption must be no later than the version the earlier words are read from: one that falls between that version and the change may have adopted other words, which no version on disk shows. **Where no adopted version is on record**, the note says so ("its adopted words are not known and none are printed as a rule"), recites the earlier version's words as that version's, and recites the working words. jason does not guess which words are adopted.

**`--current`** renders the working words instead, to `data/drafts/rules-and-regulations-current.md`, with the same notes: each (b) passage is followed by a note reciting its last adopted words, or saying that none are on record. This is the text `jason rule-change --from-manual` proposes; it reads it in memory (`jason.tasks.manual.working_rules`).

The template's `{TEXT_BASIS}` says which words a rendering holds. `data/manual/KEY/render.json` records the separation under `adoption`: the mode, the (b) passages with their basis and the pieces they are placed on, and the suggestions left out. With no revision history on disk the rules are the working words, and the rendering says so.

Where a passage sits: the concordance names its piece, and the passage covers every other piece of rule text its working words run over (`place_passages`). A passage the concordance cannot place is shown at the end of the rules; a policy's passage (the fine schedule) is listed in the adoption history only.

**The adoption history** (`{ADOPTION_HISTORY}`) lists each recorded step: noticed, adopted, delivered, tabled, listed, no action, in force; then each (b) passage, the policies' too, with when it changed and whether its last adopted words are on record. Its sources are:

- the profile's `AdoptionEvent` rows, read from the minutes and the library;
- the rule-change records that name the manual, when no row names them (`Community.rule_change_records()`);
- a detector's dated versions.

A detector writes `data/manual/KEY/history.json` (`jason.tasks.manual.history_path`). The file is a list of `AdoptionEvent.to_dict()` rows. Each row has `on`, `action` (`in force` for a dated copy), `sections` (as the manual's outline numbers them, or the new numbers), `evidence`, `source` (`detector`), `version`, and `digest`.

## The generated manual

The base is `src/jason/templates/manual/owners-manual.md`. It is general, and the profile fills it. Its tokens:

| Token | Fills |
|---|---|
| `{PART:slot}` | the guidance the profile puts in a slot: `front`, `welcome`, `contacts`, `guidance` |
| `{EXCERPTS}` | the governing-document sections the profile quotes (`Excerpt` rows), each a `{QUOTE:key#n}` ([embedded-references.md](embedded-references.md)) |
| `{INCLUDE:book}`, `{INCLUDE:book#N}` | a whole book or one section with its subsections; `official` renders the rule text only; `optional` renders nothing for a book the profile does not fill |
| `{LAW:CIV 5730(a) quoted}` | a statute's words from disk, or the passage the subdivision prints in quotation marks |
| `{ADOPTION_HISTORY}` | the history table, and the passages changed with no adoption found |
| `{ASSOCIATION_NAME}` and the other identity tokens; `{RULES_TITLE}`, `{MANUAL_TITLE}`, `{SOURCE_TITLE}`, `{SOURCE_REVISION}` | the profile's values |
| `{TEXT_BASIS}` | in the official rules: which words the rendering holds (the last adopted, or the working words) |

Each piece's words come from its source:

- a part with its own document is read from that document;
- a verbatim copy of a statute outside the rules is read from the statute on disk;
- everything else is read from the manual.

Rule text is never filled from the declaration by reference. A rule changes only by a rule change, even when it restates the declaration.

**The check (`check`).** Every rendered piece carries the span of the manual it stands for. The rendering is identical to the manual when:

- every word is placed, in order;
- each piece's words are the manual's, apart from layout;
- or the piece's difference is labeled (for example, "the statute's words on disk, in place of the copy").

An unlabeled difference is a defect, and `--render` exits 1. The words are compared line by line in `data/drafts/owners-manual.diff`. The check itself is in `data/manual/KEY/render.json`.

## The Rules document and the manual template

The rules can also stand as one document that other documents refer to, kept as **rule records** with stable ids ([document-templates.md](document-templates.md), section 11). Two documents come from definitions:

- **`rules-and-regulations`**: the Rules document. The rules book only, each rule its own block, a status line (`{ADOPTION_STATUS}`) that is the draft banner until an adoption event for the whole document is on record, the adoption history, and an appendix that names the bound-in policies by their book keys without copying them.
- **`owners-manual-template`**: the manual with no rules in it. A reference block links the Rules document and indexes its numbers and titles (the Doc form), or renders the rules from the same records (the Markdown and HTML forms).

The existing manual can read its rule words from the Rules document too, as an option that is off unless asked: `jason document-template owners-manual --rules-from-document`. The rule and copy words then come from the records, each piece labeled where it differs from the working Doc (the Rules document holds no pending suggestion). Rule text is still never filled from the declaration by reference.

```bash
jason document-template rules-and-regulations      # the Rules document, and its proof against the official rules
jason document-template owners-manual-template     # the manual that refers to it
jason document-template owners-manual --rules-from-document
jason document-template rules-and-regulations --export-records   # the records as data, never over an existing file
jason document-template --doc plan                 # what the two Google Docs would be: a dry run
jason document-template --doc create --yes         # write them (the Rules Doc first); a person's edit to a Doc is left alone
```

## Commands and files

```bash
jason manual --classify             # data/manual/KEY/classification.{json,md}
jason manual --classify --asks      # also the open questions into the intake store
jason manual --concordance          # concordance.{json,md}, and every existing citation resolved
jason manual --render               # data/drafts/rules-and-regulations.md, owners-manual.md, owners-manual.diff
jason manual --render --current     # the rules in the working words: rules-and-regulations-current.md
```

The manual's text is the outline on disk (`jason outlines --fetch`, read-only). Nothing is written to Drive, PayHOA, or the mail, and the Doc is never edited.

## What the board decides

jason lists these decisions; it never makes them.

### Whether publishing the rules as their own document needs a rule change

**The rule (Civil Code 4340(b)):** "“Rule change” means the adoption, amendment, or repeal of an operating rule by the board."

**The exception (4355(b)(5)):** sections 4360 and 4365 do not apply to the "Issuance of a document that merely repeats existing law or the governing documents."

**The procedure (4360(a)):** "The board shall provide general notice pursuant to Section 4045 of a proposed rule change at least 28 days before making the rule change."

The two readings:

- **Reading 1.** A rules document that reprints the adopted rules word for word, and leaves out only words that regulate nothing, merely repeats the governing documents (4355(b)(5)). It adopts, amends, and repeals nothing. On this reading no 28-day notice is needed.
- **Reading 2.** Leaving any adopted words out of the official text could be a repeal of them. Separating a policy that was adopted inside the rules could be an amendment of where it governs. Guidance sentences inside a rule, copies, and examples are the cases. On this reading 4360 applies when the subject is in 4355(a).

**The course that is lawful under either reading:** notice the extraction under 4360(a), with the text and the list of what was left in the manual, and adopt it at a meeting under 4360(b). This is `jason rule-change`. Counsel reads first if the board prefers reading 1.

### Other decisions

- **Each open question.** Whether a section is a rule, guidance, or a policy's terms (`jason intake`).
- **Each edited or stale copy of the declaration.** Keep the rule's own words, or replace them with a citation of the declaration (itself a rule change). Where the rule's words and the declaration's conflict, the declaration prevails (4205(d)).
- **Each rule in a conflict row.** These are rules that yield to the law (`jason conflicts`).
- **Duplicates.** A part kept in two documents, and which one is the source.
- **Which text is a policy's.** Where the manual's copy of a policy differs from the policy's own document.

## Extending `{QUOTE:}` (not done)

`jason.community.section_refs` quotes one section of a document the profile keeps. Whole-book and whole-part includes, and slots of guidance, are built in `jason.community.manual` instead of changing it.

**To fold them in:**

1. Add `INCLUDE` to `section_refs.TOKEN`'s verbs.
2. Add `Resolver.include(key, number)` returning the ordered provisions with their subsections, so `expand_markdown` can render a part.

**A second gap.** `DiskResolver.provision` rightly refuses a number an outline reads twice ("ambiguous"). The concordance's disambiguated numbers (`Signs(i)` style: a heading's title, then the printed list number) are the fix to adopt there when the outline reader learns to hang a list from an unnumbered heading.
