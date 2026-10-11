# Incidents

A new screen, `#/incidents` (`?id=` for one record), in the Records group beside Insurance and Life safety · phase 3, after the Work screens · CLI: `jason incidents --record ...` (to add; today `jason incidents` only reads paperwork)

## In the console

None. The paperwork history has no view: `jason incidents` and the MCP tool `incident_history` read the association's repair paperwork and group it into events, and `#/loss-packet?unit=&incident=` ([unit-record.md](unit-record.md)) takes an `incident` key from a caller. Nothing records that an incident happened.

**This spec is the whole screen, as proposed.** Verified in the repo on 2026-10-11: no incident record, no store for one, and no `jason://incident/` address exist (a search for an incident record class or file found none). What is built, and this screen reads: the paperwork report (`data/reports/incidents.json`; `jason.tasks.incidents`; `select`, `load`), `incident_history`, `jason incidents --link` (`data/reports/incident-links.json`), the loss packet loader and its one write (`POST /api/write/loss-packet/confirm`, which keys a packet file by an `incident` string), and the deficiency register (`jason.tasks.deficiencies`, append only, `jason life-safety`). `docs/workflows/property-safety-vendors.md` step `record` of `loss-claim` says it plainly: "to add: today incidents are only read from paperwork". The run library `jason.workflows` is built; no `loss-claim` definition is registered and no `jason workflow` command or Work loader exists.

## Purpose and personas

A person records that something happened, once, in their name: what, where, when it was found, and who recorded it. The record is the subject a `loss-claim` run is about, the key a loss packet is filed under, and a place to point from the deficiency register. It is a **proposal**: a person's own words, not a finding about cause, cover, or fault. jason decides neither coverage nor fault.

- **Manager:** records most incidents, links the paperwork, starts the run.
- **President, vice president, secretary, treasurer, director:** may record and read; they read what the manager reads. The secretary records any decision the board takes about one.
- **Administrator:** holds no office, so only the roster row (P0 and P1): counts, not records. Configures; records nothing on anyone's behalf.
- **Counsel:** reads on grant, no act.
- **Owner, reviewer:** no access. An owner's report to the association arrives as a request or an email and is recorded here by a person.

## Data

| Part | Source |
|---|---|
| The records | `jason.tasks.incident_records.rows(data_dir)` (to add): `data/incidents/records.json`, each row with its `acts`, folded by `state_of`, the latest word on each question winning (the deficiency register's shape) |
| What the paperwork shows | `incident_history(address=...)` (built): events with causes, claim numbers, `standing`; keyed by dates and addresses because an event has no id today |
| Links found by search | `data/reports/incident-links.json` through `jason incidents --links --address` (built) |
| The loss packet | `GET /api/loss-packet?unit=&incident=ID` (built); the record's id is the key |
| The run | `jason.workflows.api.show` for the linked `loss-claim` run |
| The deficiency register | `jason.tasks.deficiencies.load` and `state_of` (built), read only |
| The places | the unit list and the building table through the community (`Community.streets()`, buildings); a common-area place is words |
| The policy's notice words | `insurance_policies`: recited only when the pages are on disk; otherwise "not read" |

**The record** (all fields a person's, none inferred):

```json
{"id": "inc-2099-0007", "state": "open",
 "acts": [
  {"act": "recorded", "by": "A. Manager", "at": "2099-03-02T09:14:00+00:00",
   "what": "Water on the ceiling of the hallway, stain spreading", "cause": "plumbing leak or overflow",
   "place": {"unit": "123 Main St", "building": 4, "element": "unit interior"},
   "happened": "unknown", "found": "2099-03-02", "foundHow": "a resident told the manager",
   "active": "yes", "injury": "no", "photos": ["library:5012"]},
  {"act": "linked", "by": "A. Manager", "at": "2099-03-02T09:30:00+00:00", "to": "run", "address": "work/loss-claim/2099-03-a"}]}
```

`cause` and `element` are the closed sets already in `jason.community.incidents` (`Cause`, `Element`), or "not sure". `active` and `injury` are yes, no, or unknown. `foundHow` is a short word list (a resident told us, a visit, a vendor, a report, other), never a name. **No medical detail is asked or kept:** `injury` is a flag and the detail stays in the carrier's and counsel's files. The id is a sequence kept under the store lock (`inc-YEAR-NNNN`).

**Acts** (append only; a correction is a later act, nothing is edited or deleted): `recorded`, `amended` (a field, the old value, the reason), `linked` (below), `noted`, `closed` (with a reason), `reopened`, `withdrawn` (entered in error; the row stays with the reason). Each carries `by` (the signer, never a body value naming someone else) and `at`.

## Layout: the list

```
+------------------------------------------------------------------------------------------+
| Incidents                                                          [Record an incident]  |
| 5 records · 3 open · 1 with active water or fire · 2 with no run · 1 withdrawn           |
+------------------------------------------------------------------------------------------+
| Filter: [Open v] [Building v] [Cause v] [Has no run]                                     |
| Id             Found      Where                  What (cause)               Links         |
| inc-2099-0007  Mar 2      123 Main St · Bldg 4   plumbing leak (a person's  run · packet  |
|                           unit interior          word)  [ACTIVE: yes]       1 deficiency  |
| inc-2099-0004  Feb 11     common area · gate     vehicle collision          none         |
+------------------------------------------------------------------------------------------+
| A record is a person's word. It is not a finding about cause, cover, or fault.           |
+------------------------------------------------------------------------------------------+
```

## Layout: one record

```
+------------------------------------------------------------------------------------------+
| Incidents > inc-2099-0007                    jason://incident/inc-2099-0007 [copy]       |
| Recorded by A. Manager, Mar 2 09:14 · open · found Mar 2 · age 9 days                    |
+------------------------------------------------------------------------------------------+
| 1 WHAT, WHERE, WHEN   (the person's words, as recorded; amendments listed beneath)       |
| What: Water on the ceiling of the hallway ...   Cause (their word): plumbing leak        |
| Where: 123 Main St, Building 4, unit interior   Found: Mar 2 · happened: unknown         |
| Active: yes (water or fire still going)         Injury reported: no                      |
| Photos: [Doc chip] photo-1.jpg                                                           |
+------------------------------------------------------------------------------------------+
| 2 WHAT THE PAPERWORK SHOWS   read from the repair paperwork, not from this record        |
| 123 Main St: 2 events in the history. Earlier: Jan 2098 plumbing leak, claimed.          |
| Standing: "sudden, cost unknown" (a lead, against the policy's deductible)    [Open]     |
| [Link this event]  (stored as first day + address + claim numbers; events have no id)    |
+------------------------------------------------------------------------------------------+
| 3 LINKS                                                                                  |
| Loss/claim run: work/loss-claim/2099-03-a (step 4 of 11)   Loss packet: 5 steps, 2 confirmed |
| Deficiency register: def-3f9a (open, impairs a scheduled safeguard) [a person linked]    |
| Board item: none                                                                         |
+------------------------------------------------------------------------------------------+
| 4 HISTORY   newest first, who and when: linked deficiency · recorded                     |
+------------------------------------------------------------------------------------------+
```

## Components

Built (checked in `ui/src/components`): `DataTable`, `Card`, `Pill`, `Glyph`, `Doc`, `Confirm`, `Command`, `Findings`, `Caveats`, `Timeline`, `Stat`, `QuestionCard`, `DueDate`. To add: `IncidentForm` (the record behind `Confirm`), `IncidentRow`, `IncidentLinks`, `EventLinkPicker`, `ActiveBanner` (a `Pill` preset). `TerminalStep` and `AgeStamp` are proposed elsewhere and are not in the folder.

## Actions

Each write is a `Confirm` that spells out what is recorded and in whose name; a body `by` naming someone else is a 403, a missing `by` a 400, an admin viewing as someone else cannot act. Each holds the store lock (`jason.locks`) and writes only `data/incidents/records.json`.

| Control | Does | CLI (to add) |
|---|---|---|
| Record an incident | `recorded`: what, cause (or "not sure"), place, found day, how it was found, active, injury flag, photos by library address. Refuses an empty what, place, or found day, with "Say what happened, where, and the day it was found." Emails and phone numbers are masked | `jason incidents --record --what TEXT --unit ADDRESS --found DAY --by NAME` |
| Amend, note, close, reopen, withdraw | A later act, a reason required (not for a note) | `--amend ID`, `--note ID`, `--close ID`, `--reopen ID`, `--withdraw ID` |
| Link a deficiency | `linked` to a register id; the register is not written. Both pages show the other, labeled "a person linked these; it is not a finding about cause or fault" | `--link-deficiency ID DEF --by NAME` |
| Link a paperwork event | `linked`: first day, address, claim numbers (a lead) | `--link-event ID --address A --first DAY --by NAME` |
| Start a loss/claim run | The Work screen's `StartRun`, prefilled (subject = the id, found day); a draft run. Nothing starts without a person | `jason workflow start loss-claim ...` (to add) |
| Open the loss packet | Link to `#/loss-packet?unit=&incident=ID`. Its step confirmations are the existing write, which replaces a step's earlier confirmation (it is not append only; decision 4) | existing |

The record asks no insurer, sends no notice, and starts no claim. `notify` is a `person` step of the run, with its basis `documents` (the policy's words, when its pages are read). A decision to file a claim is the board's and the secretary records it on the Decisions screen; this screen has no vote control and no "file a claim" button.

## States

- **No records:** "No incidents are recorded. `jason incidents --record` records one; the paperwork history is read separately."
- **No paperwork report:** section 2 says "run `jason incidents` first" with the command; the record still stands.
- **Active water or fire:** a banner "Recorded as active by NAME, Mar 2. The run's mitigate step cannot be skipped." The page does not say it was stopped; only a later act does.
- **A record with no unit match** (an address on no parcel): the place reads "no unit matches"; it is recorded as words.
- **A deficiency that was cleared or no longer open:** the link shows its state now, read from the register.
- **Loading, store unreadable:** a skeleton; "could not read records.json" with the loader's reason.
- **Withdrawn:** dimmed, with the reason; never removed from the list or the history.

## Privacy

- A record is P2: it may bear on a claim, as the deficiency register's impairments do. A viewer whose office does not open P2 sees counts only ("5 records, 3 open"), as `life-safety` does for impairments. Directors and officers have the same access to information; a director reads what an officer reads at the same level.
- No resident is named. A reporter is a role word. A unit is the address already on the unit list. Photos keep their own level.
- The paperwork section hides a claim file's snippet as `incident_history` does (confidential unless `private`); it shows counts and claim numbers only at the viewer's level.
- A URL carries an id. No `/api/file` link, no absolute path. Owner view and reviewers are refused.

## Decisions for the user

1. **Who may record.** Any office that opens P2 (recommended, so a director who sees it can say so), or the manager and the secretary only.
2. **Counsel and insurer correspondence.** A `linked` address to a library file, never its words.
3. **Automatic board item.** Whether a recorded incident proposes a board item as a confirmed deficiency does (recommended: no, only when a person asks).
4. **The loss packet's confirmations replace; the register appends.** Whether the packet confirmation write becomes append only before incidents link to it (recommended: yes).
5. **Event ids.** `incident_history` has none. Either the build adds a stable id, or the link stays day + address + claim numbers (recommended for now).
6. **A new `incident` link kind in the run library** (`LinkKind` has none; a `doc` link is the stopgap).

## Acceptance criteria

1. A record cannot be recorded without what, place, found day, and a signed-in name; the refusal says what to supply. Nothing is written on a refusal.
2. A second record gets the next id under the lock; two requests at once never share an id.
3. An amendment keeps the earlier value; a withdrawal keeps the row; no record is edited or deleted.
4. A body `by` naming someone else is a 403; an admin viewing as someone else cannot act.
5. Linking a deficiency changes nothing in `deficiencies.json`; both pages show the link and the label.
6. A record linked to a run and the run's `record` step point at the same address; the loss packet opens under the same id.
7. With P2 closed to the viewer, the list shows counts only and no row.
8. No medical detail, resident name, email, or phone number is stored; masks are tested.
9. The page sends no notice, asks no insurer, files no claim, and states no cause as a finding.
10. A director reads the same page an officer reads at the same level.
