# Rule citations: which document, which section

A citation of the association's own rules fails to resolve for a few reasons, and most are not about the section: they are
about the **document**. "Section 7.8" in the minutes is a section of the declaration and of the bylaws; "R-3(e)" is a rule
of the owner's manual and of a rule document adopted apart; "the Rules" is one document or several; "this Declaration" is
the document it is written in. This page is how jason decides which document a citation means, what it says when it
cannot, how a rule document's sections are addressed, how jason's own rule rows are recited, what was measured, and what
remains. The citation grammar and the shelf are in [citations.md](citations.md); the addresses are in
[record-addresses.md](record-addresses.md).

The code: `jason.community.scoping` (pure: what is written, where, and which document), `jason.tasks.cite_scope` (the index
of the documents on disk, and `read_text`, a whole text's citations), `jason.tasks.rule_rows` (jason's own rule rows), and
`jason.tasks.cite.Shelf` / `resolve`, which apply them. The profile's part is data only: its documents, their names, their
books, and the owner's manual's rows.

## The idea in one line

**Say how the document was chosen, or say that it was not.** A citation that names its document is read as it always was.
A number with no document is scoped from where it is written; where one document fits, the answer says why; where two fit,
the answer names both and no one is picked. A reading is never a recitation: what jason recites is the stored words of the
section it found, and the basis is a label on how it found them.

## Why citations failed

Measured on the association's corpus (below), before this work, the misses were, by weight:

| Cause | Weight | Fixed by |
|---|---|---|
| No document is written, and none was asked from ("Section 7.8", "R-3(e)", "Article 4") | 348 of the 493 bare citations in the association's own documents (71%) were unresolved: all 308 in letters and notices, all 35 in the minutes | scoping from the citing document, its date, and the form; the ambiguity state |
| A self-reference ("this Declaration", "these Bylaws", "Section 5 of this Policy") | 163 unresolved, 13 resolved | self basis; the citing document |
| A rule's own number style ("R-3(e)", "Rule 2.1") not read as a rule of a rules document | every lettered rule written without its document (281) | the form narrows the documents; the lettered style is read from the outlines |
| A book's common name read as one document ("the Rules" meant the first rules document) | silent wrong-document resolutions | the book basis: the document of the book that has the section |
| Jason's own rule rows cited as a plan item writes them | all of them (`unknown_document`) | the rule-row registry |
| A section a document prints twice ("R-3(i)" under the rule and again under a heading) | `ambiguous`, with no way to say which | `~n`: the n-th printing |
| A section named by its heading ("covenants#USE") | not found | the one section whose title is those words |
| A number the document had (renumbered, or a working copy's) | not found | the permanent id places it; the answer says so |
| A rule document read from a text extract had no sections | the document had no outline | the lettered and "Rule N" headings are outlined |
| A list that numbers its own sections ("18." with "a." under it) numbered "18(18)(a)" | an address no citation could write | the sublist hangs from the section once |

## The forms

| Form | Example | Read as |
|---|---|---|
| named section | `Bylaws 7.8`, `Section 7.8 of the Bylaws`, `CC&R 7.8 (a)` | the document's name is the specification's (key, title, `cite_as`, alias, or the canon); a trailing "as amended" is dropped |
| bare section | `Section 7.8`, `§ 7.8(a)` | scoped |
| named article | `Article IV of the Bylaws`, `Bylaws Art. 4` | the article, by its number (a roman numeral is read as its number) |
| bare article | `Article 4` | scoped, among the documents that have articles |
| named rule | `Handbook R-3(e)`, `Rule 2.1 of the Lot Rules` | a lettered rule ("R-3(e)") or a dotted one ("2.1") of a rules document |
| bare rule | `R-3(e)`, `Rule 2.1` | scoped, among the rules documents |
| self-reference | `this Declaration`, `these Bylaws`, `Section 5 of this Policy` | the citing document, whatever noun the author used |
| whole document | `the Rules and Regulations`, `the Declaration` | the document; a name that stands for a book of several documents is the book |
| address | `decl#6.2(a)`, `rules#R-3~2`, `covenants#USE` | exact: a key and a number; `~n` the n-th section a document numbers alike; a heading |
| jason's rule row | `owner_responses.RULES: delivery`, `owner_info.FOR_A_PERSON` | one of jason's own rows, as data (below) |

A name written in lower case in running prose ("the rules require ...") is not a mention of a document. A section of a code
or a statute ("Section 5 of the Civil Code") is the law's, read by the references grammar. A number whose whole part is 100 or
more is a code's section, not one of the association's documents' (they number their sections from 1 to under 100). A
heading line ("ARTICLE 5 - ASSESSMENTS", "R-3. PARKING") is the document's own, not a citation of it.

## Which document: the scoping rules

`scoping.scope` reads a citation and the context it is written in (`Citing`: the document key, its kind, the day it was
written, the document it amends) against the `Index` of documents. The result is a `Scoped`: a standing, the document, the
**basis**, every document considered with whether it has the section, any document named nearby (a lead), and any other
document that prints the same words.

| Basis | When | Example |
|---|---|---|
| **named** | the citation names the document | `Bylaws 7.8` |
| **self** | "this X" or "these X" in the document X (or the one it amends); with a generic noun, the citing document | `these Bylaws` in the Bylaws |
| **citing** | a bare number, written in a document that has it (or a part of it) | `Section 7.8` in the Bylaws |
| **amends** | a bare number in an amendment or annexation that has no such section itself: the document it amends | `Section 4.15` in an amendment |
| **only** | a bare number outside the documents (minutes, a letter, a rule row), and exactly one document has it | `Section 4.15` in the minutes, when only the declaration has a 4.15 |
| **form** | the kind of thing cited narrows the documents, and one has the number | a lettered rule belongs to the rules documents that number their rules so; "Article" to the documents that have articles; "Rule" to the rules documents |
| **book** | a common name for a book of several documents; the document that has the section | `Rules R-4` when only one rules document has an R-4 |
| **part** | the same rule is printed in a part of one document and in the document adopted apart, with the same words | the document adopted apart; the other is listed as a reprint (`alsoPrintedIn`) |

The order is the table's: the citing document's own section first (an annexation that numbers its own "1.3(d)(ii)" cites
it as its own), then the document it amends, then the others by form. A number the citing document does not have is looked
for in the others, never in itself.

**The date.** A document kept as amended is read in the version in force on the citing document's day (`citing_day`): the
number the declaration had that day. The answer's words are those of that day, with the version shown; a document with no
history is read as it is. A section the version of that day does not have is looked for by its permanent id (below). A
document's `written` date is not a filter: it is when the text was last restated, not when it first existed.

**What is never done.**

- No pick between two documents that both have the section and print different words: the miss is `ambiguous_document`, with
  `scope.candidates` naming each (and each as it would be cited: "Bylaws Section 7.8", "Declaration Section 7.8").
- A document named near the citation ("CC&R" earlier in the paragraph) is `scope.leads`, a lead: it narrows nothing.
- No document is chosen because it is the first: "the Rules" is the book, the answer says it is, and lists the book's other
  documents (`alsoInBook`).
- "these Rules" in a text that is not one of the rules means the document it is written in, and nothing says which: ambiguous.

## The states

| State | `found` | Reason | What it means | What to do |
|---|---|---|---|---|
| resolved | yes | | one document, with its `scope.basis` | recite the words; repeat the basis when it is not "named" |
| ambiguous (documents) | no | `ambiguous_document` | no document is named and more than one has the section | a person picks; name each candidate |
| ambiguous (twice) | no | `ambiguous` | one document numbers two sections alike | cite by place: `R-3(i)~2` |
| unknown document | no | `unknown_document` or `unparsed` | no document is named, or the name is not one of the association's ("Section 3 of the Master Plan") | a lead: a document jason does not hold |
| not on the shelf | no | `not_in_document`, `parent_only`, `no_outline` | a known document has no such section (the detail says how it numbers: "numbers its sections R-n"), or no outline | read the document; a missing outline is `jason outlines` |
| jason's rule row | yes | | one of jason's own rows, `kind` `row` | recite it as jason's, never as the association's |

## Rule documents as addressable sections

A rules document's sections are addressed by the number it prints: a lettered rule ("R-3"), its subsections ("R-3(e)",
"R-3(e)(ii)"), or a dotted number ("2.1"). `outline_from_doc` reads the numbers a Google Doc draws; `outline_from_text` reads
a text extract's, and now reads a lettered heading ("R-3. Parking", "Rule R-3 Parking") and "Rule 2.1 Noise" as sections, so
"(e)" under them is "R-3(e)". `jason cite "Handbook R-3(e)"` recites it.

Where a document prints a number twice (a list that restarts under a heading), the section is cited by place, `R-3(i)~2`; the
miss lists the places. A section with no number is cited by the words of its heading when exactly one section's title is those words
("covenants#USE"; a single word that only begins several titles is a miss). A rule document's outline quality is measured by the round trip: each number the outline holds is
written as a citation of its document and resolved; a number that does not resolve, or resolves to two sections, is a defect
of the outline, not of the citation.

Two defects the measurement found in the readers are fixed (a list that numbers the sections itself hung its sublist from the
section twice; a text outline had no lettered rules). Outlines already on disk keep their numbers until they are read again
(`jason outlines`), and a re-read renumbers the sections that had the defect; `jason cite --migrate-ids` then re-places the
records that cite them.

## Parts: the interface scoping expects

A rule is often a **part** of a document: the rules inside an owner's manual, a policy bound into it, an exhibit of an
instrument, one document in a scanned PDF that holds several. `scoping.Part` is the record scoping reads:

| Field | Meaning |
|---|---|
| `document` | the outline's key (the document the part is in) |
| `anchor` | the outline section the part starts at: its number, or its title when it has none; the part is that section and what is under it |
| `through` | the last section, when the part is a run of sections rather than one section's subtree |
| `book` | the address key the part is cited by (`rules.lot`), the book and the part's name |
| `label` | what a person calls it ("the Lot Rules") |
| `aliases` | the other names it goes by |

`Index.parts` holds them; `Index.part_of(document, number)` says which part a section falls in. Two sources fill them,
and each part says which (`Part.source`):

- **`classification`**: the owner's manual's rows (`Community.owners_manual()`, `jason.community.manual`;
  `jason.tasks.cite_scope.manual_parts`): each row's anchor and the book its target names. A classification part
  names no document: the book's common name and the rules' own numbers do the scoping, and the `part` basis is the one place
  such a part changes an answer.
- **`segments`**: the parts and labeled exhibits of a stored segmentation ([document-segmentation.md](document-segmentation.md);
  `jason.tasks.cite_scope.segment_parts`). These carry more: `numbers` (the outline sections that sit inside the part),
  `path` (the names from the document down to the part), `ref` (its address in the file, `library:ID#seg=s1/s1.1`), `pages`,
  and `kind`.

### The stored readings that are used

`cite_scope.segment_readings` takes a stored reading (`data/library/segments/<id>.json`) only when all of these hold; each
reading left out says why (`jason cite --scan` prints a line for each, and `--json` carries them as `segments`):

| Reading | Used | Why not |
|---|---|---|
| the file is in the library (`library.db`) and on disk | yes | "the file is not in the library, so its bytes and its document cannot be checked", "not on disk" |
| its bytes are those it was read from | yes | "stale: the file's bytes changed since it was read" (`segments.stale`) |
| the file holds one top-level document, or an outline is bound to it and holds every top-level document's title (a policy or a form bound in) | yes | "the file holds N documents, and none is known to be the outline's", "the outline X does not hold N of them" |
| the file is one outline's document | yes | "no outline's words are the file's", "the file's words fit more than one outline", "too short to match" |

The last row is `bind_outline`: an outline read from the file (`DocumentOutline.library`) is bound by its path; otherwise
twenty short windows of the file's text (`data/library/text/<id>.txt`) are looked for in each outline's words, and an outline
is the file's when at least half are found, the texts are of like length, and no other outline comes within 0.3. A miss is a
miss: never the nearest outline. `jason cite --no-segments` (`Shelf(segments=False)`) scopes without them.

### What a part's name does

A name a stored part or exhibit goes by ("Exhibit A", "Ex. A", a part's title of two words or more) joins the scanner's names,
unless a document or a book already goes by it: an existing name always wins, so a citation that resolved before resolves
the same. The name then scopes (`scoping._scope_part`, basis `segment`):

- **One document holds it**: the result is that document, with `scope.path` the way down (`document, exhibit, part`:
  `instrument > Exhibit B > Schedule 1`), `scope.part` the part's book or title, and `scope.source` `segments`. The target
  is the document; the path says which part of it.
- **Two documents hold it** ("Exhibit A" in two instruments): `ambiguous_document`, naming both with each one's path. A text
  written in one of them means that one's own, as a bare section does (the note says so). The same label at two depths of one
  document stays ambiguous, since nothing says which.
- **With a section number** ("Section 7.3 of the Community Regulations"): the part's own `numbers` decide. The section must be
  one of them and the document must have it; a section the document has but the part does not is `not_in_document`, and the
  miss says so. An exhibit (or a part inside one) has no outline, so "Section 3 of Exhibit A" is a miss that says its sections
  are not an outline on the shelf: the document's own section 3 is never read in its place.
- **A part stops at an exhibit**: a part's `numbers` are the sections between its heading line and the next part or the first
  exhibit heading found at the start of a line inside it (`place_parts`, which places the parts in page order: a heading
  printed again is a running header inside the part); a part whose heading is not a line of the text has no numbers. A cover or
  contents part gives no name to a document (the association's own name is a cover's title).

Where a stored reading gives a document parts with sections, those parts **replace** the manual classification's for that
document (`Index.part_of` returns the segment part); where it gives only names, or none is stored, the classification stays.

## jason's own rule rows

A plan item names the rule it rests on. When that rule is a row jason keeps (a decision written as data), `jason cite`
recites the row, in `jason.tasks.rule_rows`:

- **Addresses.** `owner_responses.RULES: delivery` (one row of a table), `owner_info.FOR_A_PERSON` (a whole table), and
  `Community.owner_information: EARLIER_ELECTIONS` (one attribute the specification holds, through a no-argument `Community`
  method). The tables are a closed list (`rule_rows.TABLES`): an address never names an arbitrary module's attribute. The
  address may sit in a sentence ("the response policy's delivery row (owner_responses.RULES: delivery)").
- **The recital.** The row's own words (`words`), its key, the action it gives, the condition it tests (the function's name,
  where it is written, and its own source), and where the row is written. `text` carries these, so a screen that recites a
  section recites a row the same way; `row` carries them as data.
- **The label.** `kind` is `row`; `caveat` says: jason's own rule row, a decision kept as data, not a rule of the
  association; the association's rules are its governing documents.
- **The adoption.** A row that names the board item it rests on has `adoption` with the item's address
  (`board-item:KEY`). A row that names none has none: a missing adoption is shown as missing, not guessed.
- **A miss.** An unknown table (`unknown_document`, with the registered tables), or a row the table does not have
  (`not_in_document`, with the rows it has).

An attribute the specification keeps in a module is recited with the comment written above it, where the decision and its
date are written, and where it is written (`comment`, `where`). So the owner-information completion rule is cited as
`Community.owner_information: OWNER_INFO_COMPLETED_COMMENT`: the comment the owner is sent, with the board's rule above it.

A rule the item writes as prose ("the board's rule (AGENTS.md)") is not an address: it stays a miss until the item cites the
row or the document it means. Every plan kind's rule is an address; a test holds them to it.

## Using it

- `jason cite EXPRESSION [--in KEY] [--on DAY]`: cite one expression, from where it is written. The answer prints the
  document chosen and its basis, or each document considered.
- `jason cite --scan FILE [--in KEY] [--on DAY]` (`-` for standard input; `--json`): every citation of the association's
  documents in a text, each resolved, counted by form and status; the ones that are not resolved are listed with the
  documents that fit.
- `Shelf(...)(expression, citing=KEY, day=DAY)`, `jason.tasks.cite.resolve(expression, citing=, citing_day=)`, and
  `jason.tasks.cite_scope.read_text(shelf, text, citing=, day=)`.
- The MCP tool `cite_document` takes `citing` and `citing_day` and returns `scope` ([mcp.md](mcp.md)); the approvals screen
  recites a plan item's rule through the same call (`jason.web.approvals.recite`).

## Measurements

Dated 2026-10-05, on the association's corpus read for this work: its governing documents, its minutes and agendas, its
letters, notices and drafts, jason's own documents, the profile's rule rows (a row's authority, a template's, a conflict's
provision and authority, an assignment's coverage), and the plan items' rules. 2,671 citations of the association's
documents in 742 texts and strings (`scoping.scan` finds them; `jason cite --scan` runs the same function). "Before" is the
resolver as it stood (`parse`, and the references grammar for a governing document's own text); "after" is the shelf with
scoping. Each cell is before to after.

The association's own documents and records (jason's own documents left out, since their section numbers are examples):

| Form | n | resolved | ambiguous (documents) | ambiguous (twice) | unknown document | not on the shelf |
|---|---:|---:|---:|---:|---:|---:|
| address | 197 | 133 to 133 | 0 to 0 | 0 to 0 | 4 to 4 | 60 to 60 |
| article, bare | 53 | 28 to 31 | 0 to 16 | 3 to 6 | 22 to 0 | 0 to 0 |
| article, named | 26 | 26 to 26 | 0 to 0 | 0 to 0 | 0 to 0 | 0 to 0 |
| jason's rule row | 23 | 0 to 23 | 0 to 0 | 0 to 0 | 23 to 0 | 0 to 0 |
| rule, lettered, bare | 281 | 0 to 265 | 0 to 5 | 0 to 4 | 281 to 0 | 0 to 7 |
| rule, lettered, named | 99 | 99 to 99 | 0 to 0 | 0 to 0 | 0 to 0 | 0 to 0 |
| section, bare | 159 | 117 to 119 | 0 to 31 | 0 to 0 | 40 to 0 | 2 to 9 |
| section, named | 282 | 266 to 275 | 0 to 0 | 0 to 0 | 10 to 1 | 6 to 6 |
| self-reference | 176 | 13 to 170 | 0 to 6 | 0 to 0 | 163 to 0 | 0 to 0 |
| unknown document | 5 | 0 to 0 | 0 to 0 | 0 to 0 | 5 to 5 | 0 to 0 |
| whole document | 824 | 818 to 821 | 0 to 0 | 0 to 0 | 6 to 3 | 0 to 0 |
| **all** | **2,125** | **1,500 to 1,962** | **0 to 58** | **3 to 10** | **554 to 13** | **68 to 82** |

Including jason's own documents (their section numbers are examples: "Section 7.8", "R-3(e)"): 2,671 citations, 1,794 to
2,346 resolved, 0 to 162 ambiguous across documents, 764 to 13 unknown document.

How to read it:

- **Unknown document fell from 554 to 13.** Those were numbers with no document that the resolver could not scope. They are
  now resolved (462 more), named as ambiguous with their candidates (58 more), found twice in one document (7 more), or no
  document has the section (14 more not on the shelf). The 13 left are names that are not the association's documents.
- **Resolved to the wrong document.** Every citation resolved before and after resolves to the same document (1,807 of
  1,807): the changes are all new resolutions or new ambiguities. The one that changed from resolved to ambiguous was a
  wrong resolution before: "these Rules" in a policy resolved to the owner's manual, because the book's name stood for its
  first document. All 43 new resolutions outside the generated drafts, jason's own documents, and the self-references were
  read in their sentences, and so were a sample of about 60 from the drafts and the self-references: no wrong document.
  Three kinds are judgment calls and are labeled so: a rule printed in a part and in the document adopted apart (`part`), a
  rule cited by a rendered draft of the rules (scoped to the document it renders: an assumption the draft states nowhere
  on disk), and a section that only one document has (`only`: elimination, with every document considered listed).
- **Not on the shelf rose from 68 to 82** because a citation that was unscoped before is now asked of its documents and found
  absent: sections a generated draft numbers by the rules' new numbering, a bare number a document does not have, and an
  example number in a draft.
- **The 60 addresses not on the shelf** (`disc#C(b)(1)`-style keys and numbers) are the generated rules' new numbering: the
  documents they name have no outline with those numbers. That is an outline gap, not a citation one.

Outline quality of the rule documents (the round trip: each number an outline holds, written as a citation of its document,
resolved): the documents of a book number their sections consistently, with a few exceptions. A guide list that numbers
twice ("1", "2" twice), and a list that restarts under an unnumbered heading ("R-3(i)" under the rule and again under a
heading), made 7 numbers `ambiguous` with no way to say which; each is now addressable by place. A policy's sublist
numbers on disk are doubled (4 sections, an address no citation could write); the reader is fixed and the disk outline is
stale until it is read again. The declaration's outline holds 5 sections its text as amended does not (an amendment removed
them: `parent_only`, not a defect).

## What remains

- **Parts from segmentation, measured on little.** The wiring is built and tested on made-up files. How much it helps on the
  archive depends on stored readings of the rule documents' PDFs, which are few (a profile's page says how many); and a
  part found only by name is a document-level answer: a section of an exhibit is a miss until the exhibit has an outline.
  `Part.outline` (the outline sections a part holds) is filled from a heading match (`numbers`), not yet from the manual's
  own locators.
- **Several documents in one file.** A file whose reading holds more than one top-level document is left out: nothing says
  which of them an outline's text is. Reading the outline per segment (page range) is what would use it.
- **Title-numbered sections.** A section known only by its heading (an unnumbered policy, a fine schedule) is addressed by
  words, or not at all; an outline that numbers it is the fix, and the address of its sections belongs to the document's
  own numbering.
- **The roman-numeral lists and the heading-hung lists.** A document that restarts a list under an unnumbered heading is
  still numbered as a repeat (`R-3(i)~2`): numbering by the heading's title would be the fix, and it renumbers the
  records that cite them (a migration a person runs, not a code change).
- **OCR of a lettered rule document.** `outline_from_ocr` (a scan's labels) reads articles, dotted sections, and
  subsections; a scanned rules document with lettered rules is read by `outline_from_text` only when its text is clean.
- **A citing day is not a first-in-force day.** A document's `written` date is when it was last restated. A citation of a
  document that did not yet exist on the citing day is not excluded (a document kept as amended is read in its version of
  that day, which is as far as the date goes).
- **Prose rules in a plan item.** An item that cites "the board's rule (AGENTS.md)" is a miss: the item should cite a row or a
  document.
- **Rule rows of the profile.** `Community.<method>: ATTRIBUTE` reads one attribute; the profile's own tables (its schedule,
  its response rules) are cited by their rows only through the registered tables. A profile that wants its table cited names
  it in `rule_rows.TABLES` through a `Community` method that returns it.
- **The corpus is read by a grammar.** A citation the grammar does not read stays unread (a name in lower case, a section
  sign lost to an encoding error is read as one; a citation that wraps across a heading is not).
