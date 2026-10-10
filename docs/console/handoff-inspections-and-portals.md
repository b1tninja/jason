# Handoff: documents that point elsewhere, report portals, program notices, and the life-safety watchlist

For the design pass on a set of components that do not exist yet. The behavior is settled in
[../vendor-portals.md](../vendor-portals.md) (public report portals and filing in Drive),
[../document-tools.md](../document-tools.md) (QR codes read off documents), [../cross-connection-control.md](../cross-connection-control.md)
(the annual backflow test), and [../life-safety-inspections.md](../life-safety-inspections.md). The screen they join is
[screens/life-safety.md](screens/life-safety.md). This page is what the design needs to draw them: the components, their states,
sample data, what the design must keep, and the decisions it is asked to make. Nothing here is built. The first build will use the
sample data below as test fixtures (made-up names only), and the real payloads will have the same shapes.

## The idea in five sentences

A page of paper often **points somewhere else**: a QR code on an inspection report leads to the vendor's own list of every report it
has filed, and the vendor emails only some of them. jason reads the code, finds the **portal**, keeps the reports it lists, and
shows which the association already holds. A water supplier's annual **notice** starts clocks that run from different dates (the
letter's date, its postmark, the day it was scanned) and each assembly it names has its own history. The law behind each duty comes
in grades: the Legislature's own words, a digest of a code reader, a notice's quotation, or nothing found. jason informs and never
decides: it files nothing without a person's `Confirm`, enters no password or phone code on a portal, tells no insurer, and calls no tester.

## Where it lives in the console

| Surface | Route (proposed) | Audience today | Audience later |
|---|---|---|---|
| A document's codes | the document drawer (`Doc` or `DocumentViewer`), a "Codes" tab | manager, board | the same |
| A report portal | a section of `#/life-safety` and of a vendor's card under Finance | manager, board | the same |
| A filing plan | opened from a portal or from a vendor card, as a drawer | manager | the manager only: it writes to Drive |
| The annual program notice and its assemblies | a section of `#/life-safety` (backflow card) and the dock's Deadlines | manager, board | the same |
| The tester check | beside the assemblies | manager | the same |
| The watchlist | `#/life-safety`, below the schedule | manager, board | directors |

The console is loopback and manager-only today ([security-and-privacy.md](security-and-privacy.md)). Each component works without
`ConsoleShell` at phone width, and renders from a payload alone (no fetch inside it), so it can be previewed with the fixtures.

## The components

Existing jason-ui parts are reused where named: `Pill`, `Badge`, `Card`, `DataTable`, `Doc`/`DocRef`, `Recitation`, `ReadingLabel`,
`Clock`, `DueDate`, `SourcedDate`, `Timeline`, `Findings`, `Caveats`, `Checklist`, `Confirm`, `ConfirmList`, `ApplyResult`,
`Command`, `EmptyState`, `QuestionCard`, `OpenQuestion` (from the unit-records handoff), `Seal`, `Stamp`. New ones:

| Component | Where it renders | Data | States to design |
|---|---|---|---|
| `DocumentCodes`, `CodeRow` | a document's drawer | `DocumentCode[]` | none read; one code; several; a link (shows the **host first** and the full link second, never an open button on the first line); a vendor portal (offers "Open the portal's reports"); a video meeting (shows the meeting number and whether the Zoom index has a record); a payload with a secret (shown masked, "a passcode is in the link"); a payload that is not a link (plain text); the decoder not installed ("Codes are not read: install the extra", with the command) |
| `ReportPortalCard` | `#/life-safety`, a vendor's card | `ReportPortal` | not found yet (names the command that finds it); found, not synced; synced (counts, last read); **protected** (a person's step: "This portal asks for a password or a phone code. jason enters neither."); two portals for one customer (one is "the same customer as" the other, listed once); unreachable (the error and the command); a portal whose vendor row says it has none |
| `PortalReportRow` | inside `ReportPortalCard` | `PortalReport` | held (library and Drive both), in the library only, in Drive only, **not filed**; a report the site's name check refused ("held back: its text does not name the site"); a record of completion kind shown as such, not as an inspection |
| `HoldingChips` | `PortalReportRow`, `Doc`, any document row | `Holding[]` | one chip per place the same content lives: library, Drive (the path), PayHOA library, an email attachment, the vendor's portal; a copy that is not byte-identical is marked "a different copy"; none |
| `FilingPlan` | a drawer from `ReportPortalCard` or a vendor card | `FilingPlan` | plan only (the default and the first thing shown): counts by action, each row with its action word, its destination folder, and a "why" disclosure that recites the rule's condition; confirmed and running; done (`ApplyResult`); nothing to do ("everything is filed"); a row held for a person (a document a person must verify first); the original left in place is always said |
| `NoticeClock` | the backflow card, the dock | `NoticeClockData` | the notice's days (15, 20, 5, 30) with **each date it could run from** side by side (dated, postmarked, scanned, the failed test); how many days elapsed against each; "which date counts is the program's to say"; met, running, passed, unknown; the statute's own clock vs a program's notice (cited differently) |
| `AssemblyRegister` | the backflow card | `Assembly[]` | a row per device with its service, size, serial, the IDs each source gives it (County, City, the reserve study), last passed and last failed, test due, tag, and the account and meter it matches; expands to its history; a count that differs between sources shows a `Discrepancy` row; a device no source has; a failed device with its repair clock |
| `Discrepancy` | `AssemblyRegister`, any reconciliation | `Discrepancy` | two or more sources and what each says ("the County and the City list four on the fire service; the reserve study lists five"); never picks a side; the next step as a `Command` or a question |
| `TesterCheck` | beside the register | `TesterCheck` | listed on every list checked; listed on one only; listed under a different business ("matched on the tester's name"); not listed; a list older than a year ("this list is dated 2025-06-01"); lists not fetched; contact details **masked** by default |
| `TextGrade` | the corner of a `Recitation` | a grade word | `legislature` ("the Legislature's text"), `official` (a regulation or handbook read in full), `digest` ("a summary of a code reader: confirm at the source"), `quoted by a notice`, `not found`; a word first, a glyph second, never a color alone |
| `NotOursNotice` | a mail row, a thread, a notice list | `NotOurs` | mail addressed to another party at a shared address; names what is visible without exposing the other party's details; "mark not ours" behind `Confirm`; "return to the manager" as a draft only |
| `WatchRow` | `#/life-safety`, the watchlist | `WatchItem` | a standing in words: **overdue**, **unknown**, **partly answered**, **current**, **not applicable**; its evidence as `DocRef` chips; "what would change this" as one line; "a record under another name is not seen" always visible on `unknown` |

### What each component must keep

- **`DocumentCodes`.** A code is where paper points, not a fact about the paper. The row never opens a link on its own: opening is a
  second step that shows the host again ("reports.example.com") and a line saying jason has not opened it. A masked payload is masked
  by the server. The component never receives the secret, so there is nothing to unmask on the client.
- **`ReportPortalCard`.** It renders the loader's counts and never works out "missing" itself. A protected portal is a **stop** with a
  person's step, not an error. The sync is a job a person starts (`Command`, and a `Confirm` where it writes).
- **`FilingPlan`.** The plan is on screen before any button that writes. The action words are the code's (`file`, `move`, `copy`, `in
  drive`, `filed before`). A `move` says the file keeps its id, link, and sharing. A `copy` says the original stays. Nothing deletes.
  The primary button says what it will do in numbers ("File 8, copy 5, move 2"), behind `Confirm`.
- **`NoticeClock`.** It never picks the date a clock runs from. The three dates sit beside one another with the days each gives. A
  program's notice and a statute's clock look different: the statute carries its citation, the notice carries its sender and date.
- **`AssemblyRegister` and `Discrepancy`.** Sources are columns, not a merged value. A difference between sources is shown, not
  settled. A figure from a scan the reading could not make out shows "not read", never a guess.
- **`TesterCheck`.** It says "listed on the list dated D", never "certified". Phone and email are masked in a shared view and shown to
  a role that may see them, and the lists are kept as a dated snapshot, not fetched on load.
- **`TextGrade`.** A grade is attached to the words it describes. A `digest` grade is always visible beside the words, never in a tooltip.
- **`WatchRow`.** `unknown` never reads as "not done". The row says what jason searched and by what (a subject line, a file name).

### Data shapes (TypeScript)

```ts
interface DocumentCode {
  text: string;                       // the payload; a secret value is already "***" when the server masked it
  format: "QR Code" | "MicroQRCode";
  page: number;
  link: boolean;
  host: string;                       // "reports.example.com", or ""
  masked: boolean;                    // true when the server hid a secret in `text`
  portal?: { platform: "firenspec"; host: string; key: string };       // names a vendor's report portal
  meeting?: { platform: "zoom"; host: string; id: string; recorded: boolean };   // a meeting; `recorded`: the Zoom index has it
}

interface ReportPortal {
  key: string;                        // the portal's id on its platform (a UUID)
  vendor: string;
  customer: string;
  protected: boolean;
  sameCustomerAs?: string;            // another portal key
  readFrom: string[];                 // the documents whose codes named it
  fetched: string;                    // ISO time of the last sync
  reports: PortalReport[];
  counts: { listed: number; onDisk: number; inLibrary: number; notFiled: number };
  note?: string;                      // an error, or why it was skipped
}

interface PortalReport {
  urlUuid: string;
  day: string;                        // ISO date
  site: string;
  template: string;                   // the portal's own name for the report
  inspector: string;
  kind: "inspection" | "record of completion";
  holdings: Holding[];
  held: "library and drive" | "library only" | "drive only" | "not filed";
  refused?: string;                   // why a check held it back
}

interface Holding { place: "library" | "drive" | "payhoa" | "email" | "portal"; where: string; identical: boolean }

interface FilingPlan {
  vendor: string;
  counts: Record<"file" | "move" | "copy" | "in drive" | "filed before" | "held", number>;
  rows: {
    name: string;
    action: "file" | "move" | "copy" | "in drive" | "filed before" | "held";
    destination: string;              // "My Drive/Reports/Fire Protection/Fire Alarm"
    why: string;                      // the rule's condition and the facts that decided it
    original?: string;                // for a copy: where the original stays
    kind: string;
  }[];
  command: string;                    // the CLI that does it with --yes
}

interface NoticeClockData {
  program: string;                    // "City cross-connection program"
  basis: string;                      // a notice's own words, or a statute's citation
  days: number;                       // 15
  runsFrom: { label: "dated" | "postmarked" | "scanned" | "failed test"; date: string; elapsed: number; met: boolean | null }[];
  standing: "met" | "running" | "passed" | "unknown";
  caveat: string;                     // "Which date counts is the program's to say."
}

interface Assembly {
  service: "irrigation" | "domestic" | "fire";
  type: "RP" | "DC" | "PVB" | "AG";
  sizeIn: number;
  serial: string;
  ids: { source: string; id: string }[];          // County assembly id, City backflow id
  location: string;
  account?: string; meter?: string;
  lastPassed?: string; lastFailed?: string; testDue: string; tag?: string;
  history: { date: string; result: "passed" | "failed" | "repaired" | "not read"; document: DocRefData }[];
}

interface Discrepancy { subject: string; sources: { source: string; says: string; doc?: DocRefData }[]; next?: string }

interface TesterCheck {
  tester: string;                     // as printed on the report
  certificate?: string;               // as printed, not verified
  lists: { name: string; dated?: string; found: "listed" | "listed under another business" | "not listed" | "not fetched"; id?: string }[];
  contactsMasked: boolean;
}

type TextGradeWord = "legislature" | "official" | "digest" | "quoted by a notice" | "not found";

interface WatchItem {
  item: string;
  standing: "overdue" | "unknown" | "partly answered" | "current" | "not applicable";
  evidence: DocRefData[];
  changes: string;                    // what would change the standing
  searched: string;                   // "by email subject and Drive file name"
}
```

### Sample data

Plainly fake. Use these in the fixtures and the previews.

```ts
const portal: ReportPortal = {
  key: "00000000-0000-0000-0000-00000000000a", vendor: "Example Alarm Co.", customer: "Example Village HOA",
  protected: false, readFrom: ["Bldg. 1 inspection report 9.19.29.pdf"], fetched: "2030-10-04T05:43:00Z",
  counts: { listed: 3, onDisk: 3, inLibrary: 2, notFiled: 1 },
  reports: [
    { urlUuid: "r3", day: "2030-03-11", site: "Example Village HOA, Bldg. 1", template: "Fire Alarm System - NFPA 72 (2013)",
      inspector: "Inspector A", kind: "inspection", held: "not filed", holdings: [{ place: "portal", where: "viewReport?id=r3", identical: true }] },
    { urlUuid: "r2", day: "2029-09-19", site: "Example Village HOA, Bldg. 1", template: "Fire Alarm System - NFPA 72 (2013)",
      inspector: "Inspector B", kind: "inspection", held: "library and drive",
      holdings: [{ place: "library", where: "Email Attachments/…", identical: true }, { place: "drive", where: "My Drive/Reports/Fire Protection/Fire Alarm", identical: true }] },
    { urlUuid: "r1", day: "2027-01-12", site: "Example Village HOA, Bldg. 1", template: "Fire Alarm System - Record of Completion NFPA 72 (2016)",
      inspector: "Inspector C", kind: "record of completion", held: "library only", holdings: [{ place: "library", where: "Email Attachments/…", identical: true }] },
  ],
};
const deadline: NoticeClockData = {
  program: "Example City cross-connection program", basis: "the City's notice of 2030-06-02: \"within 15 days of the date of this Notice\"", days: 15,
  runsFrom: [
    { label: "failed test", date: "2030-05-05", elapsed: 44, met: false },
    { label: "dated", date: "2030-06-02", elapsed: 16, met: false },
    { label: "postmarked", date: "2030-06-11", elapsed: 7, met: true },
    { label: "scanned", date: "2030-07-03", elapsed: 0, met: null },
  ],
  standing: "unknown", caveat: "Which date counts is the program's to say.",
};
```

## What the design must keep

1. **Words before colors.** Every standing, action, and grade is a word, with its meaning on focus and hover.
2. **A plan before a write.** `FilingPlan` shows every row and every count before the one button that writes, and that button is a
   `Confirm` naming the numbers. The original is never touched.
3. **No clock picks a date.** `NoticeClock` shows each reading and the days it gives, side by side.
4. **No source wins.** `Discrepancy` and `AssemblyRegister` keep each source in its own column.
5. **Unknown is not "not done".** `WatchRow`, `DocumentCodes` (decoder missing), and a protected portal each say what was not read and why.
6. **Private values stay masked.** A passcode in a link, a tester's phone and email, and another party's mail show masked or as a
   role-gated reveal (`MaskedField`, still proposed).
7. **Nothing opens, sends, or enters.** jason does not open a decoded link, enter a portal password, send a notice, or call a tester.
   Each is a person's act, recorded after it happens.
8. **At 320 px** the tables become cards, the register's source columns stack under the device, and `NoticeClock`'s dates become a list.

## Decisions asked of the design

1. **How does `unknown` differ from `overdue` without color,** in a table of twelve rows where a person scans for the red ones? A
   word and a glyph are given; the question is the weight, and whether `unknown` sorts above `current`.
2. **The guarded open.** Two steps feels right for a decoded link; is a popover, an inline reveal, or a drawer less likely to be
   clicked through? It must show the host twice.
3. **Where `TextGrade` sits** on a `Recitation` so a `digest` is never missed and a `legislature` grade does not read as an endorsement.
4. **`NoticeClock` with four dates.** A strip, a small table, or four tiles? It must not suggest a winner.
5. **`FilingPlan` for forty rows.** Group by action or keep the date order? The counts need to be readable at a glance.
6. **Whether `HoldingChips` replace the copies column** the documents screen draws today, or sit beside it.

## Loaders (built)

All five are registered in `jason.web.sources.EXTRA_LOADERS` (`jason.web.extra.inspections`), read disk only, and answer
`{found: false, note, command}` when a store is missing. None calls Gmail, Drive, PayHOA, or a portal on load, and none returns a path.

| Loader | Returns | Reads |
|---|---|---|
| `GET /api/document-codes` (`?doc=` the start of a file's hash, or part of its name) | `{found, documents: [{sha256, name, codes: DocumentCode[]}], decoder, command, caveats}`; a link's payload is masked by the server, and a meeting link carries `recorded` (and `indexed: false` when there is no Zoom index to look in) | `data/onboarding/ingest/codes`, `data/zoom/meetings.json` (`jason.tasks.document_codes`) |
| `GET /api/report-portal` (`?key=` the vendor's key) | `{found, vendor, key, portals: ReportPortal[], refused: string[], command, caveats}`; each report's `holdings` and `held` are read now from the library and the Drive sync, and a second portal for one customer lists no reports and says `sameCustomerAs` | `data/vendors/<key>/reports.json`, `data/library/library.db`, `data/drive/files.json` (`report_portals.portal_view`) |
| `GET /api/filing-plan` (`?key=`) | `{found, vendor, counts, rows, command, planned}`: the last plan `jason vendors --reports --drive` made, saved as `data/vendors/<key>/filing-plan.json`. **It never calls Drive**: the plan is a job a person runs | `report_portals.filing_plan_view` |
| `GET /api/backflow` | `{found, program, supplier, asOf, assemblies: Assembly[], notices: NoticeClockData[], discrepancies: Discrepancy[], tester: TesterCheck, caveats, command}` | the profile's `BackflowProgram` (`Community.backflow_program()`), the library, and the dated tester-list snapshot (`jason backflow --fetch-testers`) (`jason.tasks.backflow`) |
| `GET /api/watchlist` | `{found, items: WatchItem[], command, caveats}`, worst standing first; an item tied to an obligation takes the deadlines calendar's standing | the profile's `WatchEntry` rows (`Community.life_safety_watch()`) and `jason.tasks.deadlines.calendar` |

`NoticeClockData.runsFrom[].elapsed` and `.met` are computed by the loader, to the day the notice's request was settled or to today;
a reading that came after that day has `elapsed: 0` and `met: null`. The standing is "met" or "passed" only when every reading with an
answer agrees, otherwise "unknown". The view never counts days. `TesterCheck` carries the snapshot's date, and its lists are
`listed`, `listed under another business`, `not listed`, or `not fetched`.

The command line shows the same data: `jason backflow` (and `--fetch-testers` to keep the lists), `jason vendors --reports --drive`
for the filing plan, `jason ingest` for the codes, and `jason deadlines` for the watchlist's obligations.
