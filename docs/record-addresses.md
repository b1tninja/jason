# Record addresses

One name for a section, a version, or a record of the association, in the same form for every California common
interest development. The keys are the Davis-Stirling Act's own kinds of record; the addresses follow Akoma Ntoso's
naming (https://docs.oasis-open.org/legaldocml/akn-nc/v1.0/cs01/akn-nc-v1.0-cs01.html), simplified; and a section
keeps a permanent id through amendments, renumberings, and new readings of its text.

Code: `jason.community.books` (the keys, the canon of common names), `jason.community.addresses` (the grammar),
`jason.community.permanent_ids` (the ids; pure), `jason.community.definitions` (defined terms), and
`jason.tasks.permanent_ids` (the tables on disk, finding a cited section again, the migration). `jason cite` reads an
address as one more expression ([citations.md](citations.md)), and every citation it resolves carries its address.

## The books

A book is to the association's records what a code is to the law. Each key cites the section that defines or requires
it, read from the statute's text on disk (`jason export-authorities`).

| Key | Book | Statute | Shape |
|---|---|---|---|
| `decl` | the declaration; an annexation (a supplementary declaration) is a part of it | CIV 4135 | living |
| `arts` | the articles of incorporation | CIV 4150 (its statement: 4280) | living |
| `bylaws` | the bylaws | CIV 4150 | living |
| `rules` | the operating rules; a separately adopted set is a part (`rules.parking`) | CIV 4340(a) | living |
| `elec` | the election rules (operating rules the association must adopt) | CIV 5105(a) | living |
| `disc` | the discipline policy and schedule of monetary penalties | CIV 5850(a) | living |
| `coll` | the assessment collection policy | CIV 5310(a)(6), 5730 | living |
| `arch` | the architectural review procedure | CIV 4765(a)(1) | living |
| `plan` | the condominium plan and maps | CIV 4120, 4285 | living |
| `res` | the board's resolutions, by number | CIV 5200(a)(8) (no section defines a resolution) | series |
| `min`, `agenda` | minutes and agendas, by the meeting's day | CIV 5200(a)(8), 4950(a), 4920(d) | series |
| `exec` | executive-session minutes | CIV 4935(e) | series, restricted: 5215(a)(5)(D) |
| `budget` | the annual budget report, by fiscal year | CIV 5300(a) | series |
| `aps` | the annual policy statement, by fiscal year | CIV 5310(a) | series |
| `rsv` | the reserve study | CIV 5550(a) | series |
| `insp` | the inspector's reports on exterior elevated elements | CIV 5200(a)(15), 5551 | series |
| `tax`, `fin`, `contract` | tax returns, interim financial statements, executed contracts | CIV 5200(a)(6), (3), (4) | series |
| `inst` | recorded instruments, by the county's document number | CIV 4270(a)(3) (no section defines one) | series |
| `members` | the membership list | CIV 5200(a)(9) | series, restricted: 5215(a)(4), 5220 |
| `ballots` | the association election materials | CIV 5200(c) | series, restricted: 5200(c), 5125 |
| `notice` | each notice given to members, by its delivery ledger's key; jason's own record, so no profile maps it | CIV 4050 (delivery: 4040, 4045) | series; counts only, a member's unit only privately |
| `gov` | the governing documents as a set | CIV 4150 | group |
| `manual` | an owner's manual: a guide, not a governing document | (not in the Act) | living |

`jason cite --books` prints the table with the profile's documents in each book.

### Which document fills which book

That is profile data: `Community.book_entries()` returns `BookEntry(document, book, part, role, note, cite_as)` rows,
one per document. A row is the one place to change a mapping. The roles are:

- **text**: the book's text, or a part's;
- **amendment**: a version of the book, never a part;
- **supplement**: a supplementary declaration, kept as a part.

A part (`rules.parking`) keeps the numbers of a separately adopted document apart from the main text. All operating
rules share one definition (4340(a)), one notice procedure (4360), and one rank (4205(d)), but each adopted document
numbers its own sections.

A document no row maps is still addressed by its own key (`jason://bylaws/7.2`): the document keys stay aliases
everywhere, so nothing that cites by key breaks.

A policy that is not one of the Act's named kinds goes by what it is:

- A plate-reader or other common-area policy the board adopted is an operating rule. It applies generally (4340(a)) and
  governs the use of the common area (4355(a)(1)), so it is a part of `rules`.
- A fiscal or other policy adopted by resolution stays in `res` under its number. Whether it is also an operating rule
  ("the conduct of the business and affairs of the association", 4340(a)) is a reading for the board and counsel, not
  a filing decision.

### Names, in three layers

1. **Keys** are the statute's terms, the same for any association.
2. **The canon** (`CANON`) is the common names any profile's documents use for a book: "CC&Rs", "CC&R's", "Covenants,
   Conditions and Restrictions", "By-Laws", "Rules and Regulations", "House Rules". They are matched without regard to
   case or punctuation (`book_named`), and they name no association. `jason cite "CC & R's 6.2(a)"` reads the
   declaration's document.
3. **A community's own names** are profile data. Its citation form for a book is `BookEntry.cite_as` (or
   `CitableDocument.cite_as`). The terms its documents define are `Community.defined_terms()`.

### Defined terms

A document's definitions article ('"Rules" shall mean ...') is read by a small general reader
(`jason.community.definitions.read`). A person checks what it finds, and the profile keeps the result as
`DefinedTerm(term, document, section)` rows.

A word a document defines takes that document's meaning where the document uses it (Civil Code 1644). So reciting a
section that uses one carries the definition beside it, as `terms`: each term with the definition's own words and
address. These are recited words from another section, not a reading. A section is read with its own document's
definitions.

### The governing documents

`jason://gov` gives two sets side by side:

- the Act's list (CIV 4150: "the declaration and any other documents, such as bylaws, operating rules, articles of
  incorporation, or articles of association"), with the profile's documents in each book;
- what the association's own documents define "the Governing Documents" to be (`Community.governing_set()`, with the
  defining section).

4150's list is not closed ("such as"). The document's own term governs where the document uses it, and the law's term
governs the law. The difference is reported, never resolved.

## The address grammar

```
jason://KEY[@VERSION|:DAY][/history][/SECTION][#FRAGMENT]      a living book
jason://KEY/ITEM[@VERSION][/SECTION][#FRAGMENT]                a series book
```

| Address | Names |
|---|---|
| `jason://decl/6.2(a)` | the current text |
| `jason://decl@2099-01-01/6.2(a)` | the version made effective that day (a miss, with the versions, when none was) |
| `jason://decl:2099-06-01/6.2(a)` | the version in force on that day |
| `jason://decl@base/6.2(a)` | the text as first recorded or adopted |
| `jason://decl/history/6.2(a)` | the section's timeline: each version, the number it went by, whether its words changed, a draft that would change it, and the numbers other readings give it |
| `jason://rules@proposed-2099-11-01` | a stage version (`RecordVersion.label()`, `jason.community.revisions`): cited as itself, never merged into the text in force |
| `jason://decl@draft/6.2(b)` | a draft amendment's words for the section |
| `jason://rules.parking/B-1` | a part of a book |
| `jason://decl/6.2..6.4`, `jason://decl/6.2(a),6.2(b)` | a span; siblings |
| `jason://res/20990101-1` | a resolution by its number |
| `jason://min/2099-01-01#item-4` | minutes by the meeting's day, and an item in them |
| `jason://inst/209901010001` | a recorded instrument |
| `jason://budget/2099` | a series item: its record kind and statute, and where the profile keeps it |
| `jason://notice/board-meeting-2099-01-14` | a notice given to members, by its delivery ledger's key (below) |
| `jason://notice/board-meeting-2099-01-14/proof` | that notice's proof-of-notice record alone |
| `jason://notice` | every notice in the ledger, newest first, with how strongly the record shows it given |
| `jason://bylaws/7.2` | a document's own key standing for its book |

A stage version jason holds on disk today is a living document's draft amendment. Any other stage (a proposed rule
change, draft minutes) is a miss naming the record's stages, which their own reader keeps.

In Python, `jason.community.addresses.parse(text)` returns an `Address`, and `Address.format()` prints it back.
`jason.tasks.cite.resolve(address)` resolves one.

### A notice as a record

A notice given to members is a record in the series book `notice`, keyed by its delivery ledger's key
(`jason notices KEY --sync`, [notices.md](notices.md)). `jason cite jason://notice/KEY` (`jason.tasks.notice_record`)
gives, read only:

- **the requirement** the key names: the longest catalog key it starts with (`board-meeting-2099-01-14` is a
  `board-meeting` notice), or the form whose request it is (`owner-info-2099` is the 4041 solicitation). It is recited
  from the catalog with its statute's words from `data/authorities`, its clocks made stricter by the governing
  documents (`notice_catalog.effective`), and each document clause recited from its own text. The profile's
  paraphrase of a clause is labeled as jason's reading, never the clause;
- **the text sent**, if jason has it: a rendered Markdown or HTML file kept in `data/notices/KEY/`, else the body or
  message file a batch names; with the subject and the letter's PDF;
- **the fill records** of its `{QUOTE:}` and `{CITE:}` tokens (`*.refs.json` beside the text), each with the
  version's digest and whether the words now differ;
- **the recipients plan's counts**: `data/notices/KEY/recipients.json` (`jason delivery --notice RULE --ids ...`) and
  the notice's batches;
- **the delivery standing**: delivered, sent with follow-ups owed, sent, or a file (`jason.tasks.notice_evidence`),
  with the counts by channel and outcome and the follow-ups owed;
- **the proof-of-notice record** (`notice_proof.build`), dated by the stage it served;
- **the stage it served**: a rule change's `proposed` or `distributed` stage (with its version and clock), a board
  meeting's notice (with `jason://agenda/DAY` and `jason://min/DAY`), or the minutes' availability. A key that names
  no requirement but carries a meeting's day is read as that meeting's notice, and says it is a reading.

Reading a notice is not restricted, but a member's identity never appears in what is shared: counts only. A member's
unit and ledger id appear only with `private` (`jason cite --private`); the ledger holds no names. The record's
words are the text as sent; everything else is jason's record of it, and whether notice was sufficient is for the
board or counsel.

### Reading an address

- **As an MCP resource.** `jason-mcp` serves every address as a resource, with templates for each form above and a
  listing of the books, the 20 most recent notices, and the books' top-level articles ([mcp.md](mcp.md#resources)).
  A read returns Markdown, the recitation first. A restricted book is listed by name only and never read there.
- **As pages.** `jason cite --html` writes the record reader into `data/reader`: a static page per book, part,
  section, history, version, and notice (each with its proof), linked by address (`jason.tasks.reader`). Serve it
  with `python -m http.server -d data/reader 8765`. Restricted books are written only with `--private`; a notice's
  page carries counts only unless `--private`.

## Permanent ids

In Akoma Ntoso, an element's work-level id is fixed by its place in a master expression. Here a section's permanent id
is its address, without the scheme, at the version where it first appeared:

- `decl@base/6.2(a)` was in the base text;
- `decl@2099-03-01/6.2(c)` was added by the instrument that took effect that day.

A section numbered differently later keeps its id. Each number it went by is a name in its history, never a new id:

- **from a version**: "known as 4.17 from 2099-06-01", when an amendment renumbered it;
- **under a reading**: "known as 6.2(ii) under the outline reading", when another reading numbers the same words
  differently. The outline is the working copy as read. An earlier OCR reading is kept the same way when the base is
  re-read.
- **within**: a reading's subsection that the text as amended runs inline inside its parent is a `within` name of the
  parent.
- **printed twice**: a document that prints one number twice keeps both apart. The second is `~2` (`rules@base/B-2~2`),
  in reading order.

Sections are paired by their opening words (letters and digits), in order, within an article of each other. The same
number helps the pairing, and a section an instrument restated keeps its id whatever its new words. A miss stays a
miss.

### The interface

`IdTable.permanent_id(number, as_of=None, reading="")` and its inverse `IdTable.number_of(pid, as_of=None, reading="")`
are the two directions. A table comes from any history source:

- `from_versions(key, [(effective day or None for the base, provisions), ...])`, where a provision is anything with
  `number`, `caption`, and `body` (and optionally `dated` and `removed`). Living documents use this, and so can any
  other source of a document's versions.
- `from_lineages(key, [(pid, born, [Name, ...]), ...], source=...)`, for a source that already pairs sections across
  versions (a revision detector). Its ids follow the same rule.
- `add_reading(table, name, provisions, current)` names another reading's numbers.
- `carry(previous, fresh, reading_was=...)` keeps the stored ids when a rebuild numbers the same words differently.

The tables are kept in `data/section-refs/ids-<document>.json` (`IdTable.to_dict()`). jason rebuilds only its own
tables (`source` `versions` or `outline`). A table another history source writes, with its own `source`, is read and
never rebuilt.

### Records that cite sections

`jason cite --migrate-ids` adds each citing record's permanent id and the version it cites, keeping the number as
written. It is a dry run unless `--apply`, and nothing is removed or renamed.

- **Data records** get new fields in place (`pid`, `version`, and `reading` when another reading numbered it). These
  are the stored document duties, the transcriptions, and the records of `{QUOTE:}` renderings. Each file is backed up
  once beside itself (`NAME.pre-ids.bak`).
- **The specification's rows** are Python: Conflict rows, notice provisions, and the profile's corrections. Their ids
  go in a register, `data/section-refs/cited.json`, keyed by the row.
- **A record that names a number more than one section answers to**, with no quote to tell them apart, gets no id. Its
  candidates are listed for a person to pick.

`jason cite --stale` then finds a renumbered section by its permanent id and reports it as renumbered
(`renumbered, found by its permanent id`), not missing. `jason cite --renumbered` lists those records. A record whose
quote is not in the section it was found as is still `words changed since read`.

## Privacy

`exec`, `members`, and `ballots` hold what the association may withhold (Civil Code 5215) or may not let be copied
(5200(c)). A read of one is refused with reason `restricted`, naming the statute, unless the caller opens the shelf
with `private=True` (`jason cite --private`). The refusal is the default for every tool and agent. A confidential
library file stays held back as before. A notice (`notice`) is read by anyone, but shares counts only; a member's
unit appears only with `private`.

## Caveats

- An address names jason's copy of a record. A living document's text is consolidated from the instruments' own words:
  it is not an official restatement, and the recorded and adopted documents control.
- A permanent id is a pairing of words, made by a program. A pairing across readings is evidence a person can check
  (`jason cite jason://decl/history/N`), not a finding.
- The register keys the specification's rows by their keys. A row that is renamed loses its entry until the migration
  runs again.
