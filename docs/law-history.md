# The Davis-Stirling Act's history: former sections, successors, and every change since 2011

The association's governing documents were written before 2014 and cite the Act by its old numbers: "Civil Code 1363(g)", "Section 1365 of the Civil Code". Stats. 2012, Ch. 180 (AB 805), operative January 1, 2014, repealed former Civil Code 1350–1378 and continued the Act at 4000–6150, rewording and rearranging it as it went. The Act has been amended since, for example CIV 5850 and 5855 by Stats. 2025, Ch. 22 (AB 130). jason reads both kinds of change from lawlibrary.

## Where it comes from

lawlibrary (`../lawlibrary`, its `history.py` and `succession.py`, see its `docs/history.md`) holds one index per legislative session from 2011.

**Section history.** For each edition: whether the section exists, the official history note ("Added by Stats. 2012, Ch. 180, Sec. 2"), and the change from the edition before (added, amended, repealed), with a word-level summary.

**Successors.** These come from the California Law Revision Commission's own documents. Each row says which reading it is:

| Source | What it is | How jason treats it |
|---|---|---|
| Disposition table | The enacted table, AB805DispoTable.pdf | The pin |
| Commission Comment | The Comment on each new section, 40 Cal. L. Revision Comm'n Reports 235 | A second reading, kept beside the table |
| Similarity | A lexical match | A candidate, used only where both official sources are silent; none was needed for this Act |

## In jason

| Piece | What it does |
|---|---|
| `jason law-history --export` (`jason.tasks.law_history`) | Asks lawlibrary through the worker in `jason.sources.lawlibrary` (`recodification`, `changes`). It writes `data/authorities/history/former-sections.json` and `changes.json`, and two pages the passage index's `authorities` catalog holds: `davis-stirling-recodification.md` and `davis-stirling-changes.md`. |
| `jason law-history --section 1363(g)` | Where a former section went. |
| `jason law-history --section 5855` | A current section's changes by edition. |
| `jason law-history --versions` (`jason.tasks.statute_fetch.prior_versions`) | Reads each section's earlier versions from the session publications lawlibrary holds and keeps them, each with the range it was in force, under `data/authorities/history/<citation>`. With no `--citation` it reads the sections the documents cite; `--since` adds those this history says changed since; `--shelf` adds every section on the shelf. A former section's last version ends on the repeal day this history gives. See [law-readings.md](law-readings.md#the-words-in-force-on-a-day). |
| `jason law-history --add-version FILE` | Keeps a version a person read from an official source, with its citation and range. |
| `jason.community.succession` | Reads the export from disk: `successors`, `now_at` ("1363(g) is now CIV 5855"), and `changes`. It never calls lawlibrary. |
| The `authorities` MCP tool | Given a former section, returns its successors and the caveat. Given a current one, adds its history to the text. |
| Document models | The governing documents' `cites-repealed-sections` and the letters' `cites-former-sections` findings name each cited section's successor. The citation keeps the subdivision the document prints (`repealed_sections` returns "1363(g)", not "1363"). |

## What it showed (September 30, 2026)

**Coverage.**
- 92 former sections: 89 placed by the table, 3 omitted (1350.7, 1363.005, and 1367).
- 516 Davis-Stirling successor rows, all from the official sources.
- 413 changes since 2011.

**Former citations in the governing documents.** Each former section a governing document cites is listed with its successor, for example 1363(g) (the hearing), now 5855. This association's findings are in its private notes (mystique/notes/law-history.md).

**Changes since:**
- CIV 5855 was rewritten in 2025 (151 words inserted). Among the changes, the written decision is due in 14 days where it was 15.
- CIV 5850 gained 130 words the same year.

## A change of law, not of number

The 2014 recodification renumbered the whole Act, but most sections kept their law. jason reads the Commission's Comment on each new section (`succession.standing`):

| The Comment says | Origin | A change to review? |
|---|---|---|
| "without change" or "without substantive change" (210 rows) | `continued` | No, unless the section was amended since |
| "with changes" (26 rows), "generalized" (7 rows) | `continued_with_changes` | Yes |
| No predecessor, added by Stats. 2012, Ch. 180 | `new` | Yes |
| Added by a later act (CIV 5551, SB 326 of 2019) | `added` | Yes |

The table's own word, "continued" (254 rows), says nothing about substance; the Comment decides. Amendments after 2014 are always changes.

## How the changes reach jason's reference material

- **The sweep.** `jason law-history --sweep --since 2025` (`jason.tasks.law_sweep`) lists each changed Davis-Stirling section jason cites, with every citation (file and line), and writes `data/reports/law-sweep.md`.
  - It scans the docs, the code, the specification, AGENTS.md, SKILLS.md, and the README.
  - A citation of a former section is listed with its successor.
  - A renumbering with the same effect and no amendment since is left out.
  - On September 30, 2026, the sweep since the 2025 edition listed 17 amended sections cited 366 times, and 5 former sections still cited:
    - AB 2159 (2024) rewrote the election sections 5105-5125;
    - SB 410 (2025) amended the records sections 5200 and 5210, the resale sections 4525 and 4528, and 5551;
    - SB 900 (2024) amended 4775 and 5550;
    - AB 130 (2025) amended 5850 and 5855.
- **Version stamps.** `succession.version_note` writes one line per section, for example: "continues former CIV 1363(g) with changes (2014); amended by Stats. 2025, Ch. 22 (AB 130), operative 2025-06-30".
  - Each statute page under `data/authorities` carries it as "History:" under each section (234 sections), and so does the passage index's `authorities` catalog once built.
  - Each duty brief in `duties.md` lists its cited sections whose law changed as "Law changes" (`succession.changed_in`).
- **Statutory terms.** `jason.community.statutory_terms.TERMS` holds 28 deadlines and caps. Each row gives its section, its value, the words the current text must carry with that value, and every constant in jason that holds it.
  - `tests/test_statutory_terms.py` fails when a constant differs from its term or the exported statute no longer carries the value.
  - A changed term keeps its prior value and effective day; `in_force(name, day)` gives the law of a document's date. A hearing decision letter from 2024 is judged against 15 days, one from after June 30, 2025 against 14.

## Leads for the conflict register

The sweep checks jason's own material. `jason conflicts --leads` (`jason.tasks.conflict_leads`) checks the association's: each governing document, rule, policy, and resolution, as `jason outlines` stored it, against each change to the Act since the 2014 recodification. A provision a later law displaces is followed only as far as the law allows (AGENTS.md, "Follow what is written"). A real conflict becomes a `Conflict` row, which `jason conflicts` lists.

```bash
jason conflicts --leads --since 2026-01-01
jason conflicts --leads --document enforcement-policy
```

- **Two routes.**
  - *Cites:* a section of the document cites the changed section, by its current number or a former one.
  - *Subject:* the section is among the passages that best match the changed section's words. BM25 runs over the section's current text and the words the change inserted, leaving out words most of the Act uses ("separate interest", "association").
  - Many documents never cite the statute that governs them. A fine schedule may cite nothing, yet 5850 caps it.
- **Only changes that may postdate the document.** Each citable document carries the date its text was written (`CitableDocument.written`, with its evidence).
  - A year alone counts that same year's changes.
  - A document with no date counts every change since 2014, so pin the date when the evidence allows.
  - Recodification rows, and amendments of fewer than ten words, are left out.
- **One lead per document and change**, citation first, then the best-matching section. A change already on a `Conflict` row is marked with it.
- **A lead is a reason to read two texts side by side.** Most are not conflicts: the document may already comply, or ask more than the law's minimum. Some subject matches are loose, and the section text in the lead shows which.
- **On October 2, 2026:**
  - There were 252 leads across the documents, 26 of them from the laws operative in 2026.
  - The subject route found AB 130 in five places: the bylaws' rule-making on member discipline, the CC&Rs' power to fine, the Enforcement Policy's due process, and the owner's manual's fine schedule and enforcement page. Most of these cite neither 5850 nor 5855.
  - It also found 4741 at CC&Rs 4.15, the rental section.

`jason sop law-review` is the yearly procedure.

## Limits

- **One note per edition.** An edition carries only the latest history note. An act amended twice between two editions shows only the later one, and the shelf starts in 2011.
- **The words of an earlier day** come from the same editions, so they have the same limit: [law-readings.md](law-readings.md#the-gap-october-4-2026) lists what is missing and how a person adds it.
- **A reading, not the law.** A successor row reads the Commission's table and Comments. The statute text in force is the law.
- **No automatic correction.** The board corrects a governing document's former cross-references by resolution (CIV 4235); jason only says where they point.
