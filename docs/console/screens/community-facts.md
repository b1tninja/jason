# Community facts

A new screen, `#/facts`, in Records · phase 3 · CLI: `jason facts` (to add) · MCP: `community_facts` (to add)

## In the console

None. The owner's manual, the FAQ topics, and the questions owners ask are scattered: the topic report (`thread_topics`) counts them, the governing documents hold the rules, and the library holds the manuals. This screen is the **assumed defaults** of [../../unit-records-design.md](../../unit-records-design.md) as a page: what the association says is true of every unit unless a unit's record says otherwise, with its source.

## Purpose and personas

One place for the answers owners keep asking and the documents behind them: what was originally installed (by plan), who maintains what, how touch-up paint works, where the manuals are. Each fact shows whether it is documented, reported, or only assumed.

- **Manager:** answers an owner by pointing at a fact; adds a source; promotes a reported fact when a document is found.
- **Director:** sees which plans lack documented originals and which questions come up most.
- **Owner (later):** reads the FAQ view; reports a fact they know (an interior color); confirms one.
- **Treasurer, secretary, counsel:** read-only.

## Data

| Part | Source | Level |
|---|---|---|
| The facts | `Community.facts()` (to add): `Fact` rows from the specification, merged with the facts register's rows (`registers.py`, the board's columns: status, sources, notes) | P0 |
| A fact's rule words | `cite_document(expression)` (`jason.mcp.governance`): the operative words whole, the version in force, the caveat. A fact that rests on a provision stores the expression, never the words | P0 |
| A fact's documents | the library and Drive, by address (`DocRef` through `jason.approvals.docref`) | P0 for public documents; per file level otherwise |
| The questions most asked | `thread_topics()`: topics with three or more units in a year (the FAQ candidates), and each fact's `answers` (the questions it settles) | P1 |
| Coverage by plan | computed: for each plan, facts documented, reported, and assumed, from the facts' scope | P1 |
| Open questions | `Community.open_questions()` (to add): the question, with whom (agent, counsel, board), asked and answered dates, the answer's source | P1 |

A fact never copies a provision's words into its statement. A statement that restates a rule is replaced by a recitation of it, then a reading labeled as the board's or jason's.

## Layout

```
+---------------------------------------------------------------------------------+
| Community facts                                    Search [___________] [Search] |
| Topics [All v]  Scope [All v]  Status [All v]                                    |
| 42 facts · 9 documented · 4 reported · 29 assumed · 3 questions open             |
+---------------------------------------------------------------------------------+
| Touch-up paint                                                                  |
|  [documented] The association paints exteriors about every 7 years; an owner may |
|  order a quart by the palette's code.          Scope: community · as of 2026-10  |
|  Sources: [Owner's manual §…] [Palette]     Answers: "Can I get touch-up paint?" |
| Interior paint colors                                                           |
|  [reported · 3 confirmations] Plan A living room: SW 7008      Scope: Plan A     |
| Original flooring                                                               |
|  [assumed] Plan A kitchen: vinyl plank. Not yet documented.    [Add a source]    |
+---------------------------------------------------------------------------------+
| Documents  [Manuals] [Warranties] [Plan sheets] [Product sheets]   [Add a document]|
+---------------------------------------------------------------------------------+
```

## Components

`FactList`, `FactCard`, `FactStatus`, `DocRepository`, `Doc`/`DocList`, `Recitation` and `ReadingLabel` inside a card, `OpenQuestion`, `SearchBox`, `Tabs`, `Stat`, `Command`, `Confirm`.

## Actions

| Action | Effect | How |
|---|---|---|
| Add a source to a fact | links a document to the fact; status becomes documented when the source is a developer or manufacturer document, reported otherwise | the manager's act behind `Confirm`; writes the facts register's board column, never jason's columns |
| Promote or demote a status | documented, reported, assumed | board column, `Confirm`, with a reason |
| Add a fact | a new row in the register, status assumed until sourced | the manager's act; checked against the facts that exist |
| Confirm an owner-reported fact (later) | adds one to the count | the owner's act, one per unit |
| Add a document to the repository | uploads to the library folder for its kind | behind `Confirm`; the file is classified by the library's rules |

## States

No facts yet ("Start with the questions owners already ask." with the topics most asked as suggestions); a fact with no source (assumed, with "Add a source"); a source that has changed since read; two reports that disagree; an open question attached; a search with no result (offers the topics and the owner's manual).

## Privacy

Facts and the repository are for every owner (P0), except a document the library classifies above P0. A reported fact never names who reported it. A fact never contains a unit's private contents; unit-level entries live on the unit record.

## Acceptance criteria

1. Each fact shows its status in words, its scope, its sources as `Doc`, and the questions it answers.
2. A fact resting on a provision shows the provision's words from `cite_document` with the citation and caveat, then any reading labeled with whose it is.
3. Assumed is the default status; promotion needs a source and a named person.
4. Coverage by plan counts only facts scoped to the plan; the page never presents an assumed fact as documented.
5. The questions-most-asked list comes from the topic report and links each to the fact that answers it, or to "no fact yet."
6. Writes touch only the register's board columns, through `Confirm`, and are logged.
7. Search finds facts by statement, topic, and the questions they answer.
