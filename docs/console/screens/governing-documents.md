# Governing documents

A new screen, `#/documents` (`?q=` an expression `jason cite` takes, `?address=` a `jason://` address), in the Records group · phase 2 · CLI: `jason cite`, `jason living`, `jason conflicts`

## In the console

`#/records` lists the governing instruments as a timeline, and its **Governing documents** tab lists each governing document with its copies: the recorded PDF on disk ("Recorded copy", page 1 rendered by jason) and the Drive file ("Drive copy", jason's copy), side by side in `DocumentPreview`, with "Read every governing document from Drive" (`governing-documents` loader; [documents.md](../documents.md#statutes-and-the-associations-documents)). `#/duties` opens a duty's brief with the documents' passages. Nothing yet recites a section on request.

**This spec is the whole screen, as proposed.** The loaders to add are `cite` (`jason.api.cite_document`, with `as_of`) and `record` (`read_record`, `section_refs`), plus `living_document` and `document_conflicts` for the bands. The components are being added: `Recitation` and `ReadingLabel`. The same `cite` loader serves the "recite" disclosure on an approval's rule ([approvals.md](approvals.md)). It reads only.

## Purpose and personas

The manager's law library. A person asks "what does the rule say?" and gets the words first, whole, with the citation, the version in force on the day asked about, and the caveat. Then, set apart and labeled, how the words have been read: jason's reading, the board's adopted reading, or counsel's. Then the section's history, its defined terms, what it cites, and what cites it.

- **Manager:** cites a section into a letter or an answer; checks a section in force on a past day.
- **Director, Secretary:** read a section before a decision or a meeting.
- **Counsel:** reads the documents as recited, the history, and the conflicts marked for counsel.
- **Treasurer:** reads the sections about assessments and reserves.
- **Reviewer:** opens a section from an approval item's "recite" link.

Every role can open this screen. A restricted book opens only in the private view, for a role entitled to it.

## Data

| Part | Source |
|---|---|
| The cite box | `jason.api.cite_document(expression, as_of=...)` → `jason.tasks.cite.resolve`: `kind` (section, outline, record, statute, miss), `found`, `citation`, `text` (the stored words whole), `inForce`, `history`, and `reason` on a miss. Any expression `jason cite` takes |
| A section as a sheet | `jason.tasks.reader.sheet(shelf, citation)` → `Sheet`: `title`, `words` (recited whole), `in_force`, `note`, `caveat`, `address`, `pid` (permanent id), `history` (its address), `effective`, `terms[]`, `outline[]`, `versions[]`, `readings[]` (other readings' numbers), `cites[]`, `cited_by[]`, `records[]` |
| The same as Markdown | `jason.api.read_record(address)`: the recitation first |
| References both ways | `jason.api.section_refs(expression, hops=1, direction="both")`: `refs` out (each found or missing with a reason) and `cited_by` in, each with `scope` (exact, within, enclosing) and how the cited words stand now (current, amended, words changed since read, removed, missing). A record's own summary is `jasonsReading`, shown beside `recitedWords` |
| The documents kept living | `jason.api.living_document()`; one: `living_document(key, section=..., as_of=...)`: `applied`, `notInEffect`, `held`, `findings`, `checks`, `amended`, `section` (`words`, `setBy`, `dated`, `history`, `removed`), and the caveat "Consolidated by jason from the instruments' own words; the recorded instruments control." |
| A section's history | `jason://{book}/history/{section}`; `revision_detection.section_history(data_dir, key, number)` for versions found on disk, with the adoption on record or its absence |
| Versions and days in force | `jason://{book}@{version}/{section}`, `jason://{book}:{date}/{section}` |
| Conflicts | `jason.api.document_conflicts(area=..., leads=...)`: each row's `provision`, `says`, `authority`, `since`, `extent`, `meanwhile`, `clarity`, `status`, `boardItem`; the caveat "jason notes a conflict; only the board, counsel, or an amendment resolves one." |
| The documents' duties | `jason.api.document_duties(key)`: each `section`, `kind`, `bearer`, `quote`, `deadline`, `recurrence`, `notice`, `review`. A reading is a lead: about one in five is the wrong kind |
| The books listing | `jason.api.record_resources()` (restricted books by name only) |

## Layout: a section

```
+------------------------------------------------------------------------------------------+
| Governing documents                                                                      |
| Cite [ Declaration 7.3                                    ] As of [ today v ] [Cite]     |
+------------------------------------------------------------------------------------------+
| Declaration for Example Village, Section 7.3 · Leasing                                   |
| jason://decl/7.3 [copy] · permanent id decl@base/7.3 · in force from Mar 12, 2097         |
+------------------------------------------------------------------------------------------+
| RECITED WORDS                                                                            |
| | Section 7.3. Leasing. An Owner may lease the Owner's entire Unit, provided that the   | |
| | term of the lease is not less than thirty (30) days and the lease is in writing. ...  | |
| Declaration for Example Village, Article 7, Section 7.3, as amended Mar 12, 2097,        |
| on Oct 3, 2099 · [Record] Recorded copy                                                  |
| jason's consolidated text, not an official restatement. The recorded instrument governs. |
+------------------------------------------------------------------------------------------+
| DEFINED TERMS (Civil Code 1644: the document's definition governs the word here)         |
| Owner (Declaration 1.20) | Unit (Declaration 1.31) [each recited in a disclosure]         |
+------------------------------------------------------------------------------------------+
| READINGS                                                                                 |
| [The board's reading · adopted Jun 10, 2098] "thirty (30) days" means calendar days ...  |
| [jason's reading] A month-to-month lease in writing meets it. A reading, not legal advice.|
| [Two readings remain] 1. from signing  2. from possession — the board asks counsel.       |
+------------------------------------------------------------------------------------------+
| HISTORY                              | CITES (out)              | CITED BY (in)           |
| base (recorded Jan 2, 2090)          | CIV 4740 [statute]       | Rules R-6 (exact; cur.) |
| amended Mar 12, 2097 (Amendment 2)   | Declaration 1.20         | Conflict C-3 (within)   |
| a draft on file Feb 2099: never in   |                          | Schedule: rental review |
|   force                              |                          |                         |
| words changed Jul 2098 with no       |                          |                         |
|   adoption found [finding]           |                          |                         |
+--------------------------------------+--------------------------+-------------------------+
| CONFLICTS (Civil Code 4205) touching this section: 1 · DUTIES read from it: 2            |
+------------------------------------------------------------------------------------------+
```

Below 768 px the three columns stack: history, cites, cited by.

## Components

`ScreenHeader`, a cite box (`SearchBox` until `CiteBox` exists), `Recitation` (saying so when the words asked for are not the version in force), `ReadingLabel` (jason's; the board's with the adoption date; or two readings remaining), `Evidence`, `Pill`, `Card`, `DataTable` (conflicts, duties), `RemoteView`. Versions side by side wait on `DiffTable` ([components.md](../components.md#still-proposed)).

**The readings band is the only place a reading appears.** It always follows the recitation and the defined terms. A reading is never inline in the recited words, never in the heading, and never in a tooltip on the words. Each reading names whose it is ([style.md](../content/style.md#who-said-it-recited-read-decided)).

## Actions

| Control | Does | Approval? | CLI |
|---|---|---|---|
| Cite | `cite_document(expression, as_of)`. The expression is in the route (`#/documents?q=`): it names a document, never a person | No | `jason cite "EXPR" [--as-of DATE]` |
| As of a date | Re-reads the words in force on that day (`jason://decl:2099-06-01/7.3`) | No | `jason cite EXPR --as-of DATE` |
| Copy the citation | Copies "Declaration § 7.3" in the document's own style | No | — |
| Copy the address | Copies `jason://decl/7.3` | No | — |
| Copy the words with citation | Copies the words whole, the citation, the version, and the caveat together. Never the words alone | No | `jason cite EXPR --md` |
| Open a reference | `#/documents?address=jason://...` | No | `jason cite EXPR --refs` / `--cited-by` |
| Open a version | `#/documents?address=jason://decl@{version}/7.3` | No | — |
| Compare two versions | the two versions' words side by side | No | `jason revisions KEY --diff A B` |
| Read a restricted book | the private view, once it exists; until then the command | No; logged as `private_view.on` | `jason cite EXPR --private` |

No action on this screen writes. A reading cannot be added here: a board reading is adopted at a meeting and enters the profile as a rule row; jason's readings come from its own records.

## States

- **A miss:** the resolver's `reason` in words, and what to try. "No section 7.3a in the Declaration. Did you mean 7.3(a)?" An outline (an article, a span) shows as an outline, never as joined words.
- **A version not in force:** the recitation carries `--not-in-force` and the line "These are not the words in force on Oct 3, 2099. In force: [link]."
- **A document not kept as amended, asked for a date:** "jason keeps this document only as recorded. It cannot give the words on a date."
- **No outline on disk:** "jason has no outline of this document yet. Run `jason outlines KEY`."
- **Cited by: none found:** "Nothing jason reads names this section." With the caveat: "A reference the grammar missed stays missed."
- **No adoption found for a change:** "Words changed between Feb 2098 and Jul 2098 with no adoption found in the board's records." A finding, not a conclusion that the change was invalid.
- **A restricted book with the private view off:** "Restricted (executive session): listed by name only. The association may withhold it. Open the private view to read it here." For a role not entitled: "Not open to the treasurer role."

## Privacy

- The documents and the law are P0.
- Restricted books (`exec`, `members`, `ballots`) are listed by name only. A read is refused unless the private view is open, for an entitled role. This is the `jason cite --private` rule. A URL alone never opens one.
- Counsel reads all P0, and a restricted book only for a granted matter.

## Acceptance criteria

1. For every section, the recitation (words, citation, version in force, caveat) renders before any reading, defined term, or history, and nothing renders between the words and the citation.
2. Every reading block names whose reading it is. A test renders a section with all three kinds and checks each label.
3. `#/documents?address=…` shows the same words and citation as `read_record(address)` for the fixture.
4. Copy-the-words always copies the citation and caveat with the words.
5. An as-of date before an amendment shows the earlier words with the earlier version, and the not-in-force line when the day asked about is not today's version.
6. A restricted address outside the private view returns the restricted state, and the loader's answer holds no words of it.
7. A miss renders the resolver's reason and never an empty recitation.
8. Conflicts show the caveat verbatim, and their status words come from the row.
