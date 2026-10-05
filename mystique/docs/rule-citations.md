# Mystique: rule citations

How this association's rule documents number their sections, which numbers more than one document prints, and what the
citation scoping ([docs/rule-citations.md](../../docs/rule-citations.md)) reads for this profile. No private fact is here:
the real inventory, with where each citation sits, is in `mystique/notes/rule-citations.md` (not checked in).

## The documents and how each numbers its sections

| Document (outline key) | Book | Numbers its sections | Notes |
|---|---|---|---|
| `ccrs` (the Restated Declaration) | `decl` | dotted ("4.15", "4.15(a)"); 16 articles | kept as amended by the second amendment; the third is a draft |
| `bylaws` | `bylaws` | dotted ("7.8"); 14 articles | |
| `owners-manual` | `rules` (the rules), `manual` (the whole) | the guide's two numbered lists ("1", "2"), then lettered rules ("B-12", "B-12(o)"), Part C under B-18 | the rules and the guide are in one outline; `mystique/manual.py` classifies each section |
| `parking-rules` | `rules.parking` | lettered ("B-12", "B-12(a)" to "(q)"), then a roman list under the unnumbered heading "Demarcation" | the manual's B-12 is the same rule |
| `alpr-policy` | `rules.alpr` | whole numbers ("1" to "8"), two lettered headings under 3 | |
| `election-rules` | `elec` | dotted ("2.3.2(a)"); 8 articles | |
| `enforcement-policy` | `disc` | two unnumbered headings | its numbers (C(a), C(b)(1)) are the manual's concordance's, not an outline's |
| `collection-policy` | `coll` | dotted, one level ("1" to "21") | its disk outline numbers one sublist "18(18)(a)"; read again, it is "18(a)" |

"The Rules" (and "Rules and Regulations", "Operating Rules", "Association Rules", "House Rules") is the `rules` book:
`owners-manual`, `parking-rules`, and `alpr-policy` (`Community.book_entries()`). A bare name does not pick one: the
document of the book that has the section is the one, and the whole book is the main document with the others listed.
`elec`, `disc`, and `coll` are books of their own, so "the Election Rules" is its own document.

## Parts of the owner's manual

`Community.owners_manual()` is the one source of parts today (`jason.tasks.cite_scope.manual_parts` reads its rows): the
rules by section (A, B-1 and on), the parking rule (B-12 and what is under it, book `rules.parking`), the discipline
policy and its schedule (Part C, book `disc`), the architectural application (book `arch`), and the guide (book `manual`).
The scoping uses a part for one thing: when the manual prints a rule in a part and the document adopted apart prints it with
the same words, the section means the document adopted apart (the `part` basis) and the manual is listed as a reprint.
`B-12(o)` is the case here: the manual and the parking rules print the same words, so "B-12(o)" with no document is the
parking rules, with the manual as `alsoPrintedIn`. `B-12` itself is printed with other words in the two, so a bare "B-12" is
ambiguous and names both.

### Parts from stored segmentations (October 5, 2026)

Counts only. The archive holds no stored segmentation of a rule document (`data/library/segments` is empty), and 20 of the 22
rule and policy files in the library are not mirrored on this machine as PDFs, so citation scoping and rule authority run
on the manual's classification alone. Measured two ways:

- **The 19 rule-document texts** (6 outlines and 13 library extracts; 512 citations): `jason cite --scan` with and without
  segments gives 512 unchanged, none improved, none worse. The two readings made from the PDFs that are on disk (4 and 3
  pages, no parts or exhibits) are left out ("the file's text is too short to match to an outline" and "no outline's words are
  the file's").
- **A rendering of the 6 outlines' text as PDFs, read by the segmenter** (a stand-in, not a scan): all 6 bind to their own
  outline; the manual's reading finds 2 parts and no exhibits, the others none. Scoping: 194 citations before and after, 194
  unchanged, none worse, none to another document, 1 new whole-document mention that resolves through a part's title. Rule
  authority: the manual's 83 candidates, 14 grants, and 176 rules on file (40 policy, 136 rule) are the same with the parts
  merged; 15 pieces of the merged parts come from the segmentation, where it and the classification both read a rule.

How much stored readings of the real scans change is not measured: it needs the rule documents' PDFs read once
(`jason segments ID`).

## Numbers printed twice

| Document | Number | Why | Cite by place |
|---|---|---|---|
| `owners-manual` | `1`, `2` | the guide's second numbered list ("Common Area Problems", "Problems With Neighbors") restarts | `owners-manual#2~2` |
| `owners-manual` | `B-12(i)` | a letter under the rule, and the roman list under "Demarcation" | `owners-manual#B-12(i)~2` |
| `owners-manual` | `B-18(C)(1)` to `(3)` | Part C's list and the architectural application's | `owners-manual#B-18(C)(1)~2` |
| `parking-rules` | `B-12(i)` | the same as the manual's | `parking-rules#B-12(i)~2` |

The manual module's targets give the numbers the Doc prints for these (`Demarcation(i)`, `C(b)(1)`); the outline reader's
numbers are the ones a citation of the working copy uses, and `~n` is how to say which. Numbering a list under an unnumbered
heading by the heading's title is the fix at the reader, and it renumbers records that cite them: a decision for a person.

## What the scoping reads for this profile

| Written | Reads as | Basis |
|---|---|---|
| `CC&R 7.8 (a)` | `ccrs` 7.8(a) | named (CC&R is the declaration's name) |
| `Section 7.8` in the minutes | ambiguous: `ccrs`, `bylaws` | the minutes' own "CC&R" nearby would be a lead, not a pick |
| `Section 7.8` in the bylaws | `bylaws` | citing |
| `Rule B-5` in the minutes | `owners-manual` | form (only the manual has a B-5) |
| `B-12(o)` | `parking-rules` | part (the manual prints the same words) |
| `Rules R-3(e)` | not on the shelf: the rules here number their rules B-n | |
| `Rule 2.1 of the Parking Rules` | not on the shelf: `parking-rules` numbers its sections B-n | |
| `Article IV` in the Declaration | `ccrs` Article 4 | citing |
| `this Declaration` in an annexation | the Declaration it supplements | self |
| `these Rules` in the collection policy | ambiguous: the policy is not in the `rules` book | |

## Open

- The rendered drafts of the rules (`data/drafts/rules-and-regulations*.md`, the rule-change notice) cite "B-7" and "B-12"
  as their own: the draft states nowhere which document it renders. Scoping reads a draft as written in the owner's manual
  when a harness says so; a draft that carried the document key would not need that.
- The manual's concordance numbers (`disc#C(b)(7)(a)`, `rules.parking#Demarcation(iv)`, `arch#form`) have nothing to resolve
  against: the enforcement policy's outline has two unnumbered sections and the architectural application has no document.
  Segmentation of the manual into its parts (the document segments work) gives each part its own outline, and these then
  resolve.
- A PDF of the collection policy in the library or an email attachment is a copy of `collection-policy`; its own "these
  Rules" and "Article 6" are read as the policy's only when the citing document is given (`--in collection-policy`). A
  library file is not yet known to be a copy of an outline.
- The collection policy's outline on disk (`18(18)(a)`) reads again with `jason outlines`; then `jason cite --migrate-ids`.
