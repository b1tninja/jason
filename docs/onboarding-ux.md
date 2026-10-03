# Onboarding a community: the portal, the request list, and ingestion

jason is written once for any California common interest development; one association is a profile. Seen from
the UI, that makes jason a **community management portal**: a list of communities, each at some stage of being
set up, with the one profile checked in today (`mystique`) as the first being onboarded. This page is the UX for
getting a community from "we have a signed management agreement" to "jason serves it": what a manager asks the
board, the prior manager, the developer, and the county for; how what arrives is taken in; and what the screens
show at each step. The catalog it rests on is jason's own: the Civil Code 5200 records (`AssociationRecord`),
the subdivider's deliveries (`DeveloperDelivery`, 10 CCR 2792.23), the document kinds (`DocumentKind`), the
facts a profile supplies (`Community`), and the private facts (`data/spec`).

## How a manager actually onboards an association

The real work is a correspondence: the manager sends the board (and the outgoing manager) a **request list**,
then spends weeks matching what trickles back against it. Three things make it hard, and the UI answers each:

1. **The list is long and the board does not know what half of it is.** A board member knows "the CC&Rs" and
   "the bank"; not "the 5200(a)(7) reserve account statements" or "the 2792.23 condominium plan". The request
   list is written in plain words with the statute beside it, grouped the way a board thinks (money, rules,
   insurance, people, meetings), and says who usually has each thing: the board, the prior manager, the developer,
   the county, a vendor or agent, or counsel.
2. **Things arrive in the wrong shape.** A PDF named `scan0043.pdf`, an email forward, a Drive folder from the
   prior manager, a box of paper. Ingestion is the same pipeline jason already runs: a source (Drive, PayHOA
   library, mail scan, email attachment, photos), then classify by name rule, phrase rule, and the local model,
   shelve by category, pin to the record it satisfies, and surface the gap when nothing arrived. A miss stays a
   miss; a reading is a lead, not a pin.
3. **Nobody knows what is still missing.** The checklist is the one place the manager and the board both see:
   what was asked, of whom, when; what came in and where it was filed; what is pinned to a record; and what is
   still a gap, with the date it was last chased.

## The portal

`#/communities`: one card per profile jason can load, with the active one marked. Each card shows the stage and
the progress behind it: accounts connected (which service credentials are set, as yes/no, never a value), profile
facts supplied (how many `Community` methods return something), records pinned against the 5200 inventory,
developer deliveries found, library files classified, and open gaps. A community is **set up** when the accounts
it uses are connected, the required facts are supplied, and every 5200 record has a holder or a recorded reason
it does not apply.

Switching the active community is a server setting (`JASON_PROFILE`), so the portal reads every profile but acts
on one; a second profile is loaded beside the first only to show its card.

## The onboarding stages (`#/onboarding`)

Each stage is a screen; the checklist spans them.

1. **Accounts.** Which services the community will use and whether each is connected: PayHOA (org id, Keeper
   record), Google (OAuth client, token, the Drive home, groups, the calendar id), Keeper, Zoom, PostScanMail, the
   county portals (recorder, assessor, tax, permits), the utility portals, each vendor portal, AnythingLLM. A row
   shows set or not set and the setup page that explains it; the page never shows a secret. Connecting is a
   person's step (`jason login`, Google consent); the screen shows the command.
2. **Facts.** The profile's facts, grouped by duty: name, corporate name, identity and letterhead, buildings and
   units, parcels and common areas, bank accounts and which is the reserve, the meeting schedule and board rule,
   the insurance catalog, obligations, document rules and sync rules, templates, registers. Each is a `Community`
   method; the screen shows which return something and which are still empty, with the file in the profile that
   sets it. Private facts (`data/spec`) show as present or absent by key, never by value. The facts are written
   in Python by a person; the screen is the map of what is left.
3. **Request list.** The catalog as a checklist the manager sends. Each item: a plain title, the statute, who
   usually has it, the record and the kind it will be filed as, and its status: `not asked`, `asked` (of whom,
   when), `received` (when, where it was filed), `pinned` (the record it satisfies), `gap` (asked, chased, not
   received), or `not applicable` (with the reason, kept as the record of why). The screen writes a request letter
   from the items marked to ask, grouped and in plain words, for the manager to send; it sends nothing.
4. **Ingestion.** What arrived and what the pipeline did with it: the library by method and kind
   (`library_status`), the unclassified files, the recorded copies read (`document_readings`), the Drive-to-PayHOA
   plan (`needs_publish`), and the leads (`#/leads`). A received item on the checklist links to the file jason
   filed; an unclassified file is the first thing to look at when a board member says "I sent that".
5. **Gaps.** The 5200 inventory with its gaps (`records_inventory`), the developer file with its missing
   deliveries (`association_records`), and the checklist items still open, in one list with the last date each
   was chased. This is the standing agenda item for the board until it is empty.

## Who has what

| Group | Usually held by | Examples |
|---|---|---|
| Governing documents and the developer file | the board, the prior manager, the developer, the county recorder | declaration, amendments, annexations, bylaws, articles, rules, election rules, policies, resolutions; the map, the condominium plan, the common-area deed, the public report, plans, maintenance manuals, bonds, warranties |
| Financial | the prior manager, the treasurer, the CPA, the bank | the budget, the reserve study, the reviewed statement, interim statements, the check register, bank and reserve statements, tax returns, the assessment roll, the prior manager's final accounting |
| Insurance | the agent or broker, the prior manager | each policy, evidence of insurance, loss runs, open claims |
| Contracts, vendors, utilities | the prior manager, the vendors, the utilities | executed contracts, leases, the vendor list and portals, utility accounts, the permit portal |
| Membership and owners | the prior manager, the board, escrow | the membership list, owner information and delivery preferences, rentals, resale history |
| Meetings and elections | the secretary, the prior manager, the inspector of elections | minutes, agendas, notices, ballots and results, the schedule, the roster |
| Legal | counsel, the board | cases, liens, settlements, holds, counsel's contact |
| Property | the county, inspectors, the reserve analyst | parcels, units, common areas, inspections, permits, reserve components, photos |
| Accounts | the board, the prior manager | PayHOA, Google, Zoom, mail, county and utility portals, vendor portals, the website and groups |

The full list is `jason.tasks.onboarding.CATALOG`, written once for any association; a profile marks items not
applicable rather than editing it.

## The components

Most of the screens compose what the UI has: `DataTable`, `Pill`, `Findings`, `DueDate`, `Command`, `Markdown`,
`Kanban`, `Confirm`, `Caveats`. Onboarding adds:

- **`ProgressRing`** or a stat row per community: counts with the denominator (records pinned 9 of 15).
- **`RequestList`**: the checklist with a status per item, a filter by group and status, and "mark asked"
  (of whom, when), "mark received" (where filed), "not applicable" (why), each through the store.
- **`RequestLetter`**: the Markdown letter built from the asked items, grouped, in plain words, with the statute
  beside each; a copy button, no send.
- **`FactMap`**: the profile's facts by duty, supplied or empty, with the profile file that sets each.
- **`AccountRow`**: a service, set or not set, the command or page that connects it; never a value.
- **`ConfirmList`** (planned): a checklist that gates a command until every row is ticked, for the apply steps.

## What stays a person's

Writing the profile and `data/spec`; creating Keeper records and `.env`; `jason login` and Google consent;
reviewing year folders and duplicates; confirming a model's reading before a pin; deciding what to scan or
shred; every write with `--yes`. The onboarding screens are the map and the correspondence, not the hands.

## The prior-manager transition

jason already flags mail still addressed to the prior manager, detects mail for another association the prior
manager manages, knows the stored ledger starts at PayHOA adoption (earlier payments and reserve transfers are
missing), reads the prior manager's statement and report layouts, marks a prior manager's contract as ended, and
checks for the manager's own disclosure under CIV 5375 and BPC 11504. The request list carries the transition
items those imply: the final accounting, the reserve account statements before adoption, the prior manager's
Drive archive, the mail forwarding, and the disclosure acknowledgment that the 4528 and 5300 documents belong to
the association.

## Reading the real correspondence

The catalog above is the model's. The association's own onboarding correspondence refines it: on a machine with
the Google token and the stores, `jason gmail --sync --days N` then `jason threads --party <domain> --days N --json`
and `jason topics --json` give the threads with the prior manager or the board around the transition, by topic
and status. What they asked for and sent is the test of this list; the private facts in them stay out of this
page and the catalog.
