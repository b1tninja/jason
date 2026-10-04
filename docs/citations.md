# Citations

jason can cite and recite the association's documents and records the way lawlibrary cites the codes: a citation is a
closure that narrows step by step, prints the document's own citation, gives the stored words with where they came
from, and follows its references both ways. A token (`{QUOTE:key#n}`, [embedded-references.md](embedded-references.md)),
`jason cite`, the guide, and the governance tools all read the words through one reader, so they give the same
citation and the same words.

Code: `jason.community.cite` (the grammar, the walk's nodes, the reverse edges; pure), `jason.tasks.cite` (the
`Shelf` and the `Citation` closure, on disk), `jason cite` (the command), and the governance tools `cite_document`
and `section_refs` ([mcp.md](mcp.md)).

Every resolved citation carries its record address (`jason://decl/6.2(a)`) and, for a section, its permanent id
(`decl@base/6.2(a)`): [record-addresses.md](record-addresses.md) has the books, the address grammar, the ids, and the
restricted books.

## The model, from lawlibrary

lawlibrary's `places.Citation` is a code closed over by each unit call: `Citation(Code.CIVIL).section(4600)('b')`.
jason's book is one of the association's documents (`Community.citable_documents()`, the living documents, or any
outline on disk) or one of its records.

| lawlibrary | jason | Notes |
|---|---|---|
| `Citation(code).section(n)('a')(1)` | `cite().doc("Declaration").section("6.2")("a")`, or `.section("6.2(a)")` | `cite(community, data_dir)` opens a `Shelf`; `shelf("Declaration § 6.2(a)")` parses an expression |
| `('a', 'b')`, `.and_(...)` | `("a", "b")`, `.and_("6.3")` | siblings and a series: an outline of each part, found or not |
| `.through(end)` | `.through("6.4")` | a span: an outline, never concatenated words |
| `.session(year)` | `.as_of(day)`, or `key#n@YYYY-MM-DD` | the living text in force on a day; a document not kept as amended is a miss for a date |
| `str()`, `reference()` | `str()` | the document's own style: `CitableDocument.cite_as` (else its title), "Section 6.2(a)", "Article 6" for a top-level section the document heads ARTICLE, a lettered rule's own label ("Handbook R-3(a)") |
| `.text` | `.text` | the stored words: a section's with its subsections', as amended; a statute's, from `data/authorities` |
| (none) | `.version`, `.in_force`, `.history` | who set the words and since when; the instruments that changed them, with dates and standing; an instrument not in force is listed as not applied, never merged into the text |
| `.subdivisions`, `.sentences`, `.words()`, `.containing(phrase)` | the same | sentences by the duty reader's splitter (`jason.community.deontic.sentences`) |
| `.refs`, `.hops(n)`, `.same()`, `.only(*codes)` | the same; `.only("statute", "section", "resolution", "instrument")` | `hops(None)` follows until a target repeats |
| `.tree`, `.md`, `.chart`, `_walk_nodes`, `_walk_edges` | `.tree`, `.md`, `.chart`, `Node.nodes()`, `Node.edges()` | Mermaid; a missing target is dashed |
| (none) | `.cited_by` | the reverse edges: the governing documents and jason's own records (below) |
| handoff `cite(expression)` | `jason.tasks.cite.resolve(expression)`, `cite_document` | `{kind: section | outline | record | statute | miss, found, reason, citation, text, ...}` |

Records cite the same way: `shelf.resolution("20990101-1")` (the Doc that prints the number), `shelf.instrument(
"209901010001")` (a governing instrument the specification names, a library file, or the county index cache),
`shelf.minutes("2099-01-01")` (the meeting catalog's minutes, with their text where it is on disk), and
`shelf.record(AssociationRecord.MINUTES)` (the Civil Code 5200 kind, its statute's words, and where the specification
pins it).

## The forms an expression takes

| Written | Reads as |
|---|---|
| `Declaration § 6.2(a)`, `Declaration, Section 6.2 (a)`, `Section 6.2(a) of the Declaration` | `decl#6.2(a)` |
| `Bylaws Art. 6` | the article, as an outline |
| `Handbook R-3(e)` | a rules book's lettered rule |
| `Declaration 6.2(a) and (b)`, `Declaration Sections 6.2 through 6.4` | siblings; a span |
| `decl#6.2(a)`, `decl#6.2(a)@2099-01-01`, `Declaration 6.2(a) as of 2099-01-01` | the canonical target; the words on a day |
| `Resolution 20990101-1`, `Administrative Resolution No. 20990101-1` | a resolution by the number it prints |
| `Doc. No. 209901010001`, `209901010001`, `Book 20990101, Page 1` | a recorded instrument |
| `minutes 2099-01-01`, `minutes of the meeting of 2099-01-01` | a meeting's minutes |
| `CIV 4920(a)`, `Civil Code § 4920(b)(1)`, `Section 4920 of the Civil Code`, `10 CCR 2792.23` | a statute; a subdivision is split from the section's words |
| `CIV 4000-6150` | a span of the law: the exported pages that cover it |
| `Section 5200` | a bare four-digit section is the Civil Code, as the references grammar reads it |
| `record:minutes` | a 5200 record kind |
| `jason://decl/6.2(a)`, `jason://decl@2099-01-01/6.2(a)`, `jason://decl:2099-06-01/6.2(a)`, `jason://decl/history/6.2(a)`, `jason://res/20990101-1` | a record address ([record-addresses.md](record-addresses.md)) |
| `CC & R's 6.2(a)`, `By-Laws 7.2` | a common name for a book, any case or punctuation (the canon) |

The names are the profile's: each document's key, title, `cite_as`, and aliases, and each outline's key. A form
jason does not read, a number with no document named, or an unknown name is a miss with its reason, never an
exception.

## Misses

| Reason | Means |
|---|---|
| `empty`, `unparsed` | nothing asked; a form jason does not read, or a section with no document named |
| `unknown_document`, `no_outline` | no document by that name; a known document with no outline on disk (`jason outlines`) |
| `not_in_document`, `parent_only`, `ambiguous` | no such section; the section is there but not the subsection; several sections numbered the same |
| `removed` | an amendment removed it: cite it as of an earlier day |
| `not_kept_as_amended` | a date asked of a document with no history |
| `statute_not_on_disk`, `label_not_found`, `edition_not_held`, `prior_numbering` | not exported (lawlibrary's `cite` reads it); the subdivision is not in the stored words; jason holds one edition (lawlibrary's `.session(year)` reads another); a Davis-Stirling number from before 2014 (`jason law-history`) |
| `statute_not_in_library`, `library_unavailable`, `library_failed` | the read-through asked lawlibrary and it does not hold the section; no checkout at `lawlibrary_home`; its worker failed |
| `no_resolution_prints_it`, `printed_by_several` | no resolution Doc prints the number; several do |
| `unknown_instrument`, `no_minutes`, `unknown_record` | not a governing instrument, library file, or indexed instrument; no minutes for the day; not a 5200 kind |
| `unreadable` | a source could not be read |
| `restricted` | a restricted book (executive-session minutes, the membership list, election materials): ask with `private=True` |
| `no_such_version`, `no_book_document` | no version took effect that day, or no such stage on disk; the profile maps no document to the book |

A token fails with the same reason (`SectionRefError.reason`).

## The walk

`.refs` is the target as the root of a walk over `data/outlines/references.json`, which `jason outlines` writes from
the citation grammar (`jason.community.references`) and the model's verified references. A section's edges are the
references its words and its subsections' words make; each child is resolved like any citation, so it is found or a
miss with its reason. A target reached a second time is marked a repeat and not followed again. The grammar also reads
a short form against the section it hangs from: "Section 6.2, subsection (a)" in one sentence is 6.2(a), and
"subsection (b)" inside 6.2(a) is 6.2(b) when the outline has it; "paragraph (1) of subdivision (a) of Section 4920 of
the Civil Code" names another provision and is left to the statute pass.

## What cites it

`.cited_by` lists every record that names the target, with its scope (it names the target exactly, a part of it, or
the section that encloses it; a document named as a whole is not a citation of each of its sections) and its
treatment now:

| Who | What is read |
|---|---|
| governing document | the references the documents' words make (`references.json`) |
| conflict row | `Conflict.provision` and `.authority`; `.says` is jason's reading |
| notice provision | `NoticeProvision.document` and `.section`; `.says` is jason's reading |
| notice requirement | each requirement's statute |
| document duty | each stored duty's section, with its quote |
| schedule assignment | `Assignment.covers` |
| response rule, letter template | `.authority` |
| procedure, lesson | their text |
| embedded reference | `{QUOTE:}`/`{CITE:}` tokens in jason's drafts and templates, and each rendering's record (`OUT.refs.json`) |
| association record kind | `jason.community.records.CITATION` |

| Treatment | Means |
|---|---|
| `current` | the words the record quotes (a duty's quote, a rendering's digest) are the words now |
| `unamended`, `amended` | no amendment has set the section's words; one has, and the record stores no version to compare |
| `words changed since read` | the record quotes words the section no longer has, as amended or in the outline it was read from (a stale duty reading, a rendering to redo) |
| `renumbered, found by its permanent id` | the record's number names the section under another reading (the working copy), as printed twice, or inline in its parent; the permanent id finds it, and its quote is there |
| `numbered differently` | the outline the record was read from numbers the section; the text as amended does not, and no permanent id finds it |
| `removed`, `missing` | the section was removed; the document has no such section |
| `filled when rendered` | a token: always the words in force |
| `not checked` | a statute, a record, or an outline: nothing to compare |

A section named by its title rather than a number ("RECITALS") is `not checked`. A quote the working copy has but the
text as amended reads differently (an OCR slip in the base) is `current`, with a note to compare the two.

`jason cite --stale` lists every citing record whose treatment is `words changed since read`, `numbered
differently`, `removed`, or `missing`, and exits 1 when there is any; `jason cite --renumbered` lists those a permanent
id found again. `jason cite --most-cited` ranks the sections and statutes named most across the documents and jason's
records: where verifying and transcribing the words matters most. `jason cite --survey` resolves every reference the
governing documents make and counts the misses by reason.

## Recite the rule; label the reading

What a citation returns puts the recitation first: the citation, the stored words whole, and the version in force
(`inForce`: who set the words and since when, or the edition of the law), then the caveat. A record's own summary (a
Conflict row's `says`, a notice provision's `says`) is never in the words' place: it is `jasonsReading`, shown beside
the section's `recitedWords` so a person can compare the two. A statute's subdivision is split by jason from the
exported section and says so; the whole section is the official text.

## Caveats

- Only stored words are recited. A living document is consolidated from the instruments' own words: it is not an
  official restatement, and the recorded and adopted documents control. A base read by OCR can carry its slips; the
  version's `note` says when the words differ from the working copy.
- References are read by a grammar from the current outlines, not per version; one it missed stays missed, and
  `jason outlines --model` adds the model's verified ones.
- A treatment compares what a record stores. Most records store a section number and no words, so an amended section
  is `amended`, not `words changed`: the record's author decides whether it still holds.
- Statutes come from `data/authorities` (one edition); lawlibrary reads the rest. A section of a California code no
  page holds is read through (`jason.tasks.statute_fetch.ensure`, under every reader of the shelf: `cite`, the
  evidence resolver, the packets and rule-change notices, the MCP tools): asked of the local lawlibrary checkout, written in the
  export's format with a `Fetched:` line (the day, on demand, what asked), listed under `on_demand` in the manifest,
  and logged in `data/authorities/on-demand.jsonl`. `jason export-authorities` (and `--list`) prints those no curated
  row holds, for a person to promote with a Basis and a reason; the curated list stays the person's. A miss is never
  filled from memory. `JASON_AUTHORITIES_FETCH=0` reads the disk only (the tests set it).
- Reading only: nothing reaches Drive, PayHOA, or the mail.

## Open, against lawlibrary's model

- Statute-to-statute hops: the walk stops at a statute; lawlibrary's `Citation(...).refs` walks the codes.
- `GAPS` (`structure.review`): a reference in the words the grammar cannot place is not reported per section.
- Stable section identity: built ([record-addresses.md](record-addresses.md), Permanent ids). The references the
  governing documents make (`references.json`) still key a section by its number, read from the current outlines.
- Defined terms: built for the terms a profile keeps (`Community.defined_terms()`); a term defined outside a
  definitions article is not read.
- Per-document citation forms beyond `cite_as` (a rules book's "Rule" word, its own self-reference words) are not yet
  profile data.
- Deep links stop at the Doc, the working copy, and the library file; a scan's page and a heading's `headingId` are
  not kept by the outlines.
