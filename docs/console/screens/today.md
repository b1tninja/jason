# Today

`/` · phase 1 · CLI: `jason attention`

## Purpose and personas

The first screen after sign-in. It answers one question: what needs a person now? It puts the approvals waiting, the clocks that are running, and the questions whose answers unblock the most in one place, most urgent first.

- **Manager:** the daily start. Opens approvals, follows each digest line to its screen, starts the syncs.
- **Director, Secretary, Treasurer:** the same digest, narrowed by role to the sections they answer for.
- **Reviewer:** sees only "Waiting on you as second person".
- **Counsel:** no Today screen. Counsel lands on Governing documents.

## Data

| Part | Source | Notes |
|---|---|---|
| Approvals waiting | `jason.approvals.store.pending()` | Each approval's kind, status, item counts (approvable, held, for a person), requester, age, and whether it waits on a second person |
| The attention digest | `jason.api.governance_digest(limit=8, private=not private_view)` → `attention.digest(...).as_dict()` | `totals` by urgency, `unavailable`, and `sections[]`: `key`, `title`, `command`, `tool`, `available`, `error`, `summary`, `counts`, `notes`, `items[]` (`urgency`, `text`, `due`, `command`), `more`. The digest's `caveat` is shown at the foot |
| The next questions | `jason.api.next_questions(limit=5)` | `questions[]`: `id`, `kind`, `question`, `priority`, `unblocks`, `highStakes`, `inQueue`. Shown only while an onboarding gate is closed, or when an open question carries a clock |
| Running work | `jason.jobs.jobs(data_dir)`, `jason.batches.batches(data_dir)`, `jason.locks.holders()` | Running and failed jobs from the last 24 hours, open batches, and who holds each lock |
| Freshness | Each digest section's `counts` and `notes`, and the catalog's sync time | One line per store, oldest first |

**Section order.** The digest's own order (`Digest.ordered`): sections with something urgent first, quiet ones next, unavailable ones last. Within a section, `Item.key`: urgency, then a statute's clock before the documents' before a policy's, then the due day.

**By role.** The role narrows which digest sections show, using `governance_digest(section=...)` for each:

| Role | Sections |
|---|---|
| Manager | All nine |
| Director | meetings, conflicts, requests, notices, living |
| Secretary | meetings, schedule (role `secretary`), notices, living |
| Treasurer | schedule (role `treasurer`, through `schedule_agenda(role="treasurer")`), requests of a finance kind |

## Layout

```
+--------------------------------------------------------------------------------------------+
| jason · Example Village HOA                     Acting as Jane Example (manager) · change   |
|                                                 Private view: off · Audit log               |
+-------------+------------------------------------------------------------------------------+
| Today     < | Today                                                    As of Oct 3, 2026   |
| Approvals 2 | 1 on a legal clock · 3 overdue · 4 due soon · 6 waiting on a person · 2 noted |
| Members     +------------------------------------------------------------------------------+
| Requests  3 | WAITING FOR APPROVAL                                                         |
| Notices     | +--------------------------------------------------------------------------+ |
| Meetings    | | Owner information: PayHOA tags      In review   planned 2 h ago          | |
| Documents   | | 10 writes · 4 owners · 2 held for the board · 1 for a person            | |
| Schedule    | +--------------------------------------------------------------------------+ |
| Records     | | Mailroom letters                    Waiting on a second person        | |
| Finance     | | 4 letters · $8.16 estimated                                             | |
| Onboarding  | +--------------------------------------------------------------------------+ |
| Settings    |                                                                              |
|             | NEEDS ATTENTION                                                              |
|             | Meetings · synced Oct 3, 08:40 · jason schedule-evidence --watch [copy]      |
|             |  [LEGAL] Notice of the Oct 7 meeting: 4 days left (Civil Code 4920) >      |
|             |  [due soon] Minutes of Sep 9 due Oct 9: none on record yet >               |
|             | Requests · synced Oct 3, 06:00 · jason respond [copy]                        |
|             |  [OVERDUE] Request 1042, architectural: 6 days late >                      |
|             |  ... 4 more: jason respond                                                    |
|             | Notices                                                                      |
|             |  [LEGAL] owner-info-2099: 2 owed a resend by law (CIV 4041(e)) >           |
|             | Intake · unavailable: no intake queue on disk. Run jason intake --scan.      |
|             |                                                                              |
|             | NEXT QUESTIONS (onboarding)                                                  |
|             |  Which version of the declaration is in force?   unblocks: 2 clocks, 1 gate |
|             |                                                                              |
|             | RUNNING WORK                                                                 |
|             |  Sync notices (job 41) · started by Jane Example 3 min ago · PayHOA lock    |
|             |                                                                              |
|             | Read from the stores on disk. jason decides nothing: a clock is computed...  |
+-------------+------------------------------------------------------------------------------+
```

Below 768 px the navigation collapses to a menu button. The totals line wraps. Approval cards and digest lines stack full width.

## Components

`app-shell`, `nav` (counts with words for a screen reader: "2 approvals waiting"), `page-header` (title, the "As of" date, the totals line), `approval-card` in `jc-approval-list`, `status-badge`, `deadline-badge` (`--legal` for a statute's clock), `section-card`, `freshness`, `cli-hint`, `states` (unavailable), `queue-item` (compact), `job-status` (compact), `person-chip`.

The urgency labels are the digest's own: LEGAL, OVERDUE, due soon, open, noted. Each is a word, and its color only repeats it.

## Actions

| Control | Does | Approval? |
|---|---|---|
| An approval card | Opens `/approvals/{id}` | No |
| A digest line | Opens the screen that owns it: a meeting, a request, a notice, a conflict on Governing documents, a duty on Schedule. Where no screen exists yet, it shows the line's command to copy | No |
| Copy command | Copies the section's or line's `command` | No |
| "… N more" | Opens the owning screen, filtered | No |
| Answer (next question) | Opens the question on `/onboarding#q-{id}` | No |
| Refresh a store | Starts the sync as a job (`jason sync-catalog`, `jason notices KEY --sync`, `jason meetings --sync`). A read: no approval. Each sync takes its lock, and a second press while it runs opens the running job | No |
| Open a job | Opens the job's log | No |

Today has no write action of its own.

## States

- **First run, nothing on disk:** every digest section is unavailable. The page shows one panel instead of nine: "jason has no stores for this profile yet. Start with Onboarding." with a link.
- **A section unavailable:** it sits last, with "Unavailable:" and its error (`Section.error`). The rest of the digest stands.
- **A section with nothing owed:** "Nothing needs attention." under its heading, with its summary line (for example "12 notices in the ledger; none with follow-ups owed").
- **No approvals waiting:** "No approvals are waiting." The section stays, so its absence is never mistaken for a failure to load.
- **Digest fails as a whole** (the profile cannot load): an `states` (error) naming the profile and the error, and "Check `JASON_PROFILE` and run `jason spec`."

## Privacy

- With the private view off, the digest is read with `private=True`. Units are left out of request lines, and people's task titles are replaced by their rule's label. A line never names an owner.
- With the private view on, `private=False`, and the banner "Private view on: units and task titles shown" stays at the top until it is turned off.
- Approval cards show counts, never names.
- P2 and P3 values never appear on Today.

## Acceptance criteria

1. With fixture stores, the digest sections render in `Digest.ordered` order, and lines within a section in `Item.key` order.
2. The totals line matches `Digest.totals()` exactly, with the urgency words as labels.
3. A missing store renders its section as unavailable, last, with its error and command. No other section is affected.
4. With the private view off, no rendered line contains a fixture unit label or an owner's name.
5. Each digest line links to its owning screen, or offers its command to copy.
6. The page makes no network call to PayHOA, Google, or Zoom on load. A test with those clients patched to raise passes.
7. A reviewer-only session sees only approvals waiting on a second person.
8. The digest's caveat is shown verbatim at the foot.
