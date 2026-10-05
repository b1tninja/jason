# Handoff: the document kinds, the shelf, and how a file got its kind

For the design pass on a set of components that do not exist yet. The library's behavior is settled in
[screens/records-and-library.md](screens/records-and-library.md), [documents.md](documents.md), and [doc-component.md](doc-component.md);
this page is what the design needs to draw the part they leave out: **the document kinds themselves**. Today a person sees a library as
a list of files with a kind word in one column. This pass gives the kinds a face: a shelf of every kind jason knows, what is and is not
on it, how each file came to be called what it is, and what jason read from it. Nothing here is built. The first build will use the
sample data below as test fixtures (made-up names only), and the real payloads will have the same shapes.

The screen's data, actions, privacy, and acceptance criteria are in [screens/document-kinds.md](screens/document-kinds.md).

## The idea in four sentences

jason knows a closed set of **document kinds** (a declaration, minutes, a bank statement, a grant deed, an insurance policy, and sixty
more), each on one **shelf** (governing, meeting, membership, insurance, contract, financial, property, election, legal, reference) and
some of them an association record the law requires it to keep (Civil Code 5200). Every file in the library has a kind, and **how it got
that kind is the thing worth showing**: by its name or folder, by phrases in its text, by an agenda item that used it, by a local model, by a person, or not at all. A kind with
nothing on its shelf is a gap, and a file no rule placed is a miss: both are shown as what they are, never guessed. When a person sees a
file in the wrong kind, there are two honest fixes: that person's answer for this one file (it outranks every rule and
says who chose it), or a proposed rule for review when the same mistake will recur.

## Where it lives in the console

| Surface | Route (proposed) | Audience today | Audience later |
|---|---|---|---|
| Kinds | `#/ingestion/kinds` (a tab beside the library search) | manager, board | the board's secretary, a records custodian |
| A kind's page | `#/ingestion/kinds/<kind>` | manager, board | same |
| The kind chip | everywhere a file is named (`Doc`, `DocList`, `DocRepository`, the packet) | everyone who sees a `Doc` | owners, for the documents they may see |

The console is loopback and manager-only today ([security-and-privacy.md](security-and-privacy.md)). The `KindBadge` must also work in
an owner's page at phone width, because owners will see a document's kind beside the unit manual's documents.

## The components

Existing jason-ui parts are reused where named (`Doc`/`DocList`, `Card`, `Tabs`, `DataTable`, `SearchBox`, `Pill`, `Badge`,
`Timeline`, `Findings`, `Caveats`, `HeldNote`, `Evidence`, `Recitation`, `ReadingLabel`, `Confirm`, `Command`, `Stat`, `EmptyState`,
`Glyph`, `Seal`, `RoutingTag`). New ones:

| Component | Where it renders | Data | States to design |
| --- | --- | --- | --- |
| `KindBadge` | beside any file name | `KindRef` | a kind word with its shelf's glyph; compact (glyph and word) and tiny (glyph, word on focus); unclassified ("no kind yet"); a kind jason holds back for confidentiality (lock glyph, the word still shown) |
| `KindShelf` | Kinds, top | `KindShelfData` | ten shelves in a fixed order, each a row of `KindTile`; a shelf collapsed to its count; filters applied; the whole library empty; library unavailable |
| `KindTile` | in a shelf | `KindSummary` | has files (count, newest period, the record it is); no files (a gap, dashed); a required record with no files (a gap with its citation); files held back (count shown, none opened); selected |
| `KindPage` | a kind's page | `KindDetail` | what the kind is in a sentence jason wrote, the record it satisfies and its retention, the files (a `DocList`), how they were classified, what jason reads from this kind; no files; every file confidential |
| `ClassificationTrace` | a file's drawer, a `KindPage` row | `Classification` | the steps in the order jason takes them, each marked tried and matched, tried and missed, or not tried; the winner highlighted; "no rule placed this" (a miss); a model's answer labeled as a reading with its confidence; two steps that disagree |
| `MethodMix` | a `KindTile`, a `KindPage` | `Record<ClassifyMethod, number>` | a single bar of the six methods with a text list under it (never color alone); all by name; any by none |
| `FacetBar` | above a file list | `FacetState` | kind, shelf, record, period, how classified, confidence band, confidential; each a menu with counts; chips for what is applied; "clear"; a facet with no results shown disabled with "0" |
| `SampleStrip` | a `KindPage`, the Kinds header | `SampleThumb[]` | first-page thumbnails of up to three files of the kind; a file held back is a lock tile, never a blurred thumbnail; no thumbnail available (a kind glyph on a page outline); loading |
| `ReadingFields` | a file's drawer, a `KindPage` | `KindReading` | the fields jason read for this kind (the date of a statement, the carrier of a policy), each with the words it came from and a `ReadingLabel`; a field not found shown as not found; a scan read by OCR flagged with its quality; not read yet |
| `KindGap` | Kinds, a `KindTile`, the records screen | `KindGapData` | a kind with no file and where one would come from (the sources jason knows: PayHOA, the Drive, the mail), whether a law requires it ("a record under CIV 5200(a)(6)") or it simply is not on file; a person's note that none exists |
| `KindCorrection` | a file's drawer | `KindProposal` | pick the kind you think it is and a reason; "use for this file" (a person's answer: that file only, with who and when, and the method reads "by a person"), or "propose a rule" (a preview of the rule row it would add and how many other files it would change); chosen; proposed; decided; applied |
| `CoverageNote` | the Kinds header | `{ kinds: number; withFiles: number; gaps: number; misses: number }` | one sentence and four numbers; no gaps; many misses |

### Data shapes (TypeScript)

```ts
type Shelf = "governing" | "meeting" | "membership" | "insurance" | "contract" | "financial" | "property" | "election" | "legal" | "reference";

// library.Method: the stored word for how a kind was decided. "name" is the name-or-folder rule, "content" a phrase rule
// over the text, "agenda" an agenda item that used the file, "model" the local model, "person" a person's answer
// (`jason intake`; it outranks every rule), "none" no stage placed it.
type ClassifyMethod = "name" | "content" | "agenda" | "model" | "person" | "none";

interface KindRef {
  kind: string;                 // the closed set's word: "bank_statement"
  label: string;                // what a person calls it: "Bank statement"
  shelf: Shelf;
  held?: boolean;               // the file is confidential and held back
}

interface KindSummary extends KindRef {
  files: number;
  held: number;                 // files held back from this person
  newest?: string;              // the newest period on the shelf, "2099-09", "2099"
  record?: { citation: string; label: string };   // "CIV 5200(a)(3)", "Interim financial statements"
  methods: Record<ClassifyMethod, number>;
}

interface KindShelfData {
  shelves: { shelf: Shelf; label: string; kinds: KindSummary[] }[];
  unclassified: number;         // files no rule placed
  total: number;
  generated: string;            // ISO, when the library was last classified
}

interface Classification {
  fileId: string;
  kind?: KindRef;               // absent when no rule placed it
  method: ClassifyMethod;
  confidence?: number;          // 0..1, only for "content" and "model"
  evidence: string;             // the rule's pattern, the phrase found, or the model's one-line reason
  steps: { method: ClassifyMethod; outcome: "matched" | "missed" | "not tried"; note?: string }[];
}

interface SampleThumb {
  fileId: string;
  name: string;
  thumb?: string;               // a server URL, never a path under data/
  held?: boolean;
}

interface KindReading {
  fileId: string;
  kind: KindRef;
  fields: { label: string; value?: string; words?: string; page?: number; found: boolean }[];
  by: "text layer" | "OCR" | "local model";
  ocrQuality?: "good" | "fair" | "poor";
  readAt: string;
}

interface KindGapData {
  kind: KindRef;
  required?: { citation: string; label: string };
  sources: { system: "payhoa" | "drive" | "mail" | "other"; where: string }[];
  note?: { text: string; by: string; at: string };
}

interface KindProposal {
  fileId: string;
  from?: string;
  to: string;
  reason: string;
  wouldChange: number;          // other files the rule would also reclassify
  status: "proposed" | "decided" | "applied";
}
```

### Sample data for the design

Use these, not real names. A shelf with all four tile states:

```ts
const shelf: KindShelfData = {
  generated: "2099-10-01T09:00:00Z", total: 712, unclassified: 10,
  shelves: [
    { shelf: "governing", label: "Governing", kinds: [
      { kind: "declaration", label: "Declaration", shelf: "governing", files: 2, held: 0, newest: "2099",
        record: { citation: "CIV 5200(a)(1)", label: "Governing documents" }, methods: { name: 2, content: 0, agenda: 0, model: 0, person: 0, none: 0 } },
      { kind: "annexation", label: "Annexation", shelf: "governing", files: 9, held: 0, methods: { name: 9, content: 0, agenda: 0, model: 0, person: 0, none: 0 } },
    ]},
    { shelf: "financial", label: "Financial", kinds: [
      { kind: "bank_statement", label: "Bank statement", shelf: "financial", files: 79, held: 79, newest: "2099-09",
        methods: { name: 79, content: 0, agenda: 0, model: 0, person: 0, none: 0 } },
      { kind: "tax_return", label: "Tax return", shelf: "financial", files: 0, held: 0,
        record: { citation: "CIV 5200(a)(6)", label: "Tax returns" }, methods: { name: 0, content: 0, agenda: 0, model: 0, person: 0, none: 0 } },
    ]},
  ],
};
```

A classification with a miss and a model's answer:

```ts
const trace: Classification = {
  fileId: "5001", method: "model", confidence: 0.62, evidence: "Page one reads like a vendor's estimate for tile repair.",
  kind: { kind: "proposal", label: "Proposal", shelf: "contract" },
  steps: [
    { method: "name", outcome: "missed", note: "No name rule matches \"2099-02-18 tile repairs 3970.00.pdf\"" },
    { method: "content", outcome: "missed", note: "No phrase rule matched the first pages" },
    { method: "model", outcome: "matched", note: "local model" },
  ],
};
```

## What the design must keep

1. **How it was classified is always visible.** A kind word alone looks like a fact. Beside it (on focus and in the drawer, not necessarily
   in the row) the method is a word: "by name or folder", "by its text", "by an agenda item", "by a model", "by a person", "no rule". A model's answer is a **reading**: it
   carries `ReadingLabel` and its confidence, and it is never styled like a rule match.
2. **A miss stays a miss.** A file no rule placed shows "no kind yet", in the same place a kind would be. Never a guessed kind, never a
   fallback "Other". The unclassified list is a first-class view with the same facets as any shelf.
3. **A gap is not an accusation.** A kind with no files says what it is and where a file would come from. It says a law requires the
   record only where the specification carries that citation. "No tax return on file" and "the association must keep a tax return" are two
   different sentences, and the second appears only with its citation. The design never shows a missing kind in a warning color on its own.
4. **Confidential files are counted, never opened.** A held file contributes to the count and shows a lock; it has no thumbnail, no
   snippet, no text, no reading fields. A kind whose files are all held shows its count and "held back" in place of a sample strip.
5. **A correction is a person's answer or a proposal.** A person's answer changes one file and says who chose it; `KindCorrection` never changes a rule. It previews the rule it would add and how many other
   files the rule would move, and a person with the right role decides. The word "applied" appears only once a rule row exists.
6. **Words, not color.** The shelves, the method mix, the confidence band, and the gap states each carry a word or glyph. The ten shelves
   keep a fixed order so a person learns where things are.
7. **Server-decided access.** The client never infers a level from a path, never gets an absolute path, and never gets contents from the
   shelf endpoints: thumbnails are served URLs; text and readings come from their own loaders ([doc-component.md](doc-component.md)).

## States for the whole screen

| State | What shows |
| --- | --- |
| Library unavailable | "The library is unavailable: nothing in `data/library`. Run `jason library --fetch`." The shelf is not drawn. |
| Never classified | the shelves with every tile empty and one `Command` for `jason library` |
| Classifying | the last good shelf with "reclassifying" on the header; no tile flickers |
| Everything classified | `CoverageNote` says so; the unclassified chip is absent, not "0" |
| Phone width | shelves stack as one list per shelf, a tile is a row (glyph, word, count, a chevron); the `FacetBar` becomes one "Filters" button into a sheet; the `SampleStrip` scrolls sideways |
| Print | the shelf as a table: shelf, kind, files, newest, record; no thumbnails |

## Decisions the design is asked to make

1. **Shelf glyphs.** One glyph per shelf (ten), from the existing set where one fits, with any new ones named so they can be added to
   `GLYPHS`. Do the sixty-odd kinds get their own glyph? Recommendation: no; the shelf's glyph and the kind's word are enough.
2. **Tile or table.** A grid of tiles reads well for browsing; a dense table reads well for a records custodian who wants every kind and
   count at once. Draw both and say which is the default. (Both read `KindShelfData`.)
3. **Where the method shows in a row.** Always, on hover, or only in the drawer? The risk of hiding it is the first rule above; the risk
   of showing it is a crowded row.
4. **The model's confidence.** Show a number, a band ("low", "fair", "good"), or only the word "reading"? Recommendation: the band and
   the reason sentence, with the number on focus.
5. **How a gap and a required gap differ** without a warning color alone.
6. **`KindCorrection`'s preview.** How a person sees "this rule would move 14 other files" without it reading as a threat: a short list
   of the 14 names with a checkbox each is one answer.
7. **`SampleStrip` on a phone.** Three thumbnails sideways, one thumbnail with a count, or none.

## What pairs with the paint, facts, and unit-record components

- `DocRepository` ([handoff-unit-records.md](handoff-unit-records.md)) groups a unit's or a community's documents "by kind and scope".
  It should use `KindBadge` and the shelf order here, so a kind looks the same in the library, the unit manual, and a loss packet.
- A `Fact`'s sources and an improvement's receipts are `Doc` chips; each should show its `KindBadge` in the compact form.
- The loss packet's "what the record says" step lists the kinds it needs (the policy, the declarations page, the claim letter). A kind
  the unit's record lacks is a `KindGap`, not a blank.
