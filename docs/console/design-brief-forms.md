# Design brief: forms, campaigns, arrivals, responses, follow-ups, the form library, and the administrator's service

One page of orientation for the design agent, for the whole area below. It does not repeat the handoffs; it says what to read in what order, which screens there are and how much of each can be drawn from real data today, which components are shared, which glyphs are asked for, every question the design is asked to answer (in one list), and a made-up community to draw against. Written 2026-10-05, after each handoff was checked against the code: every handoff now ends its data and component sections with an **As built** section, and where a handoff's first draft differed from the code the code won and the handoff's text was corrected.

The design project may use the association's real details. What comes back into the repository is general: no association's name, street, vendor, bank, case number, or private fact, and made-up samples only ("oakview", "123 Main St", "A. Owner").

## A. The idea, and the rules that run through it

**The idea, in six sentences.**

1. jason asks members for things through forms (the law's own, the governing documents', the community's), and this area is where a person sees what was asked, what has come back, and what to do next.
2. A form is built once for the law and kept current by the library; a community adjusts it only within the law; a campaign sends one form, for one cycle, by one channel, with the handler that will process the answers chosen when the form is made.
3. Whatever comes back (PayHOA's form, an email, a mailed scan, a Google Form, a return keyed from paper) is an arrival: recognized by the reference on its copy, read by jason into a reading that is evidence, and the owner's answer only once a person confirms it.
4. Who is still outstanding is counted by owner whichever way they answered, an owner no ask has reached is shown apart as unreachable, and every number says how old its source is.
5. What to do next is a dated follow-up for a person, with its basis (the law, the documents, a proposed number, or a person's own) and the command that does it; the screen only shows it.
6. Behind all of it the administrator connects each community's services, decides how often jason reads them, and watches the service run, and sees a credential only as set or not set.

**The rules** (each is in the handoffs' "What must not change"; a screen that breaks one is wrong):

- **Nothing here sends, resends, replies, files, or completes.** Every act is a person's command, shown as a `Command` or `TerminalStep` with "A person runs this", until a console write exists, and then a `Confirm` recorded by name. No `Stamp`: nothing here is a decision.
- **Counts carry ages.** No count without the time it was true; no zero without it; a source never read is a dash with its reason, never a bare zero (the code returns `null` for a count it cannot make).
- **Names and units only.** Never an address, a phone number, an email address, or an owner's answer in a list. A scan and a reading are private (level P3); a director sees counts and states.
- **A reading is evidence.** "The form says ...", never "the owner said ..." until a person confirms. Confidence is a word and a mark, never color alone.
- **A proposed number is labeled proposed,** in words ("proposed: 7 days before"). The law's number is the law's, with its citation; the board's adoption is the board's. jason proposes; the board adopts.
- **No secret on a screen.** A credential is `set` or `not set` with its vault path; no value is shown, copied, logged, or put in a URL.
- **A miss stays a miss.** A missing store shows the tool's own note and the command that fills it, never an empty table; a held or private item is a calm line, not an error.
- **Outstanding is by owner,** whichever way they answered; an unreachable owner is never counted as outstanding and never hidden.

## B. Reading order

1. [README.md](README.md) (the principles) and [components.md](components.md) (what is built; the `Glyph`, `Seal`, `Stamp` vocabulary).
2. [handoff-responses.md](handoff-responses.md): one returned form, its reading, and the count. Its As built section is the model for the rest.
3. [handoff-forms-and-arrivals.md](handoff-forms-and-arrivals.md): arrivals in lanes, recognition, the cycle board, the forms register, needs development, form candidates.
4. [handoff-form-library.md](handoff-form-library.md): the form a member sees, the request center, the library the administrator keeps.
5. [handoff-followups.md](handoff-followups.md): campaigns and their funnel; follow-ups.
6. [handoff-admin-components.md](handoff-admin-components.md), then [handoff-instance-and-integrations.md](handoff-instance-and-integrations.md): the administrator's integrations, schedules, service, vault, and setup dialogs.
7. [handoff-held-setup-roster.md](handoff-held-setup-roster.md), only for the four components this area shares from it (`HeldRow`, `PersonSteps`, `RecitalBlock`, `ScrollRow`).
8. The designs behind them, when a question needs the reason: [responses-design.md](../responses-design.md), [arrivals-design.md](../arrivals-design.md), [form-library-design.md](../form-library-design.md), [form-templates.md](../form-templates.md), [standard-forms.md](../standard-forms.md), [followups-design.md](../followups-design.md), [integrations-design.md](../integrations-design.md), [scheduler-daemon-design.md](../scheduler-daemon-design.md).

## C. The screens

"Data today" is a command and an MCP tool that already return the shape (the tool's JSON is the nearer to the console's: masked, camelCase, with ages). **Built** means the data exists and can be drawn from real JSON; **proposed** means it does not, and the handoff's As built section says what is missing. No console route exists for any of these; the routes in the last column are proposals (the loader pattern is `src/jason/web/extra/<name>.py`, `args -> dict`).

| Screen | Route (handoff) | Who sees it | Owner view | Data today | Console route to add | Data |
|---|---|---|---|---|---|---|
| Responses (list and one arrival) | `#/responses`, `?id=`, `?request=`, `?state=` | manager, Secretary, administrator; a director sees counts and states only | no | `jason responses --list --json`, `--show ID --json`; tools `new_responses`, `response` | `GET /api/responses`, `/api/responses/<id>` | built; page geometry per field, `ChangesPreview`, "stale" proposed |
| Responses: the acts (seen, confirm, dismiss) | in the screen | the same | no | `jason responses --seen`, `--confirm ID --by NAME [--set F=V]`, `--dismiss ID --by NAME --why TEXT` | writes behind the sign-in guard | built as commands; no console write |
| New-responses count | the dock, the digest, the nav | the same | no | `inbox` and `checked` of `new_responses` | in the dock and digest loaders | proposed (no loader) |
| Arrivals (lanes) | `#/arrivals` (the Inbox becomes lanes) | manager, Secretary, administrator | no | none beyond the forms lane (the inbox) | `GET /api/arrivals`, `/api/arrivals/<id>` | proposed (no catalog, triage, or route) |
| Cycle board | `#/cycle`, a tab of `#/owner-info` | manager, Secretary, board (directors: counts) | no | pieces only: `jason responses --outstanding --json` (`outstanding_responses`), `/api/owner-info`, `jason followups --json` | `GET /api/cycle` | the join is proposed; each piece is built |
| Forms register and the form library | `#/forms` (the register and the library are one table) | administrator; board read-only | no (the library is never in it) | `jason form-library --json`, `--show KEY --json`, `--check --json`; `jason campaigns --json` for the campaigns column | `GET /api/forms`, `/api/forms/<key>`, `/api/form-library` | built; the diff, the stale amendment's words, "unknown references seen" proposed |
| Form candidates | `#/forms/candidates` | administrator; board read-only | no | `jason discover-forms --list --json`, `--show ID --json`; `--confirm`, `--hold`, `--drop` (each `--by`) | `GET /api/form-candidates` | built |
| Needs development | a band on `#/status`, and `#/instance/gaps` | administrator only | no | none | `GET /api/instance/gaps` | proposed (no handler registry, no gap record) |
| Forms and campaigns | no route named; `#/campaigns` proposed | manager, Secretary, administrator; directors: counts | no | `jason campaigns --json`, `--show CODE --json`; tool `campaign_status` | `GET /api/campaigns`, `/api/campaigns/<code>` | built |
| Follow-ups | no route named; `#/followups` proposed | manager, Secretary, administrator; directors: counts | no | `jason followups --json`; tool `followups`; acts `--done`, `--defer`, `--drop`, `--add` | `GET /api/followups` | built; "mine", "done stays a day", the strip proposed |
| The form page (paper, PDF, email, PayHOA, portal) | every channel | the member | the portal form | `jason form-library --show KEY --json`: recitals' words, required content, clocks; the questions, `member_clock`, and `acknowledgment` are in Python, not in the JSON | a loader for the viewer | partly built; recitals are not yet rendered into a printed form |
| Request center and My requests | proposed `#/requests`, which is taken (the manager's Requests screen); the design names the owner's route | an owner | yes | none (records requests only: `/api/records-requests`) | `GET /api/my-requests` | proposed |
| Instance overview | `#/instance` | administrator | no | `jason daemon status --json`, `jason integrations list --instance --json`, `GET /api/status` (built) | `GET /api/instance/*` | partly built |
| Instance: Communities | `#/instance/communities` | administrator | no | the `communities` loader (`#/communities`) | the same | partly built |
| Integrations (instance and community) | `#/instance/integrations`, `#/setup/integrations` | administrator; an officer sees chips (proposed) | no | `jason integrations list [--instance] --json`; `check KEY [--live]` | `GET /api/instance/integrations?community=` | built; steps, capability notes, instances proposed |
| Setup dialogs (Google, Zoom, PayHOA, the rest) | from an `IntegrationCard` | administrator | no | the registry's `setup_steps` (not in the JSON) | with the integrations route | proposed; `jason integrations import\|connect` do not exist |
| Instance: Service | `#/instance/service` | administrator | no | `jason daemon status --json` | `GET /api/instance/service` | built |
| Instance: Schedules | `#/instance/schedules` | administrator | no | `jason cadence --json` (and `--every`, `--cron`, `--window`, `--pause`, `--resume`, `--restore`, `--run-now`) | `GET /api/instance/schedules?community=` | built; no console write |
| Instance: People | `#/instance/people` | administrator | no | the built `#/people` (offices, terms, admins, managers) | none | built |
| The vault and its migration plan | in Integrations | administrator | no | `jason vault status` (text only) | `GET /api/instance/vault` | proposed (no JSON) |
| Status (existing) | `#/status` | administrator | no | `GET /api/status` | built | built |

## D. The shared components, each once

A name is defined in one place; every other handoff points to it. What was fixed in this pass: `StandingWord` (the administrator's) is now `SourceStanding`, because the programs handoff already uses `StandingWord` and `StandingPill` is the statute's; `ChannelMark` has five marks, defined in the responses handoff only; `AgeStamp` is defined once (forms-and-arrivals) and is not the built `Freshness` of `CitedSections`; `TerminalStep` is the administrator page's `Command`-with-who-and-why and `PersonSteps` is the ordered list of them; the Forms register and the library table are one `FormRegister`; the form page's recital is the one `RecitalBlock`; the six integration components are defined in the administrator page and the instance page points to it; `CampaignCopies` is defined with the funnel. `FunnelBar` is not a name in any handoff: the drawing is `CampaignFunnel`.

Built and reused throughout: `Tabs`, `DataTable`, `RegisterGrid`, `Doc`/`DocumentViewer`, `Seal`, `Pill`, `Command`, `Confirm`, `ConfirmList`, `Evidence`, `Findings`, `Caveats`, `Recitation`, `Glyph`, `ScreenHeader`, `Card`. `Stamp` is never used here.

| Component | Defined in | Used also in | State |
|---|---|---|---|
| `CheckedStrip` | responses | dock, digest | proposed |
| `ArrivalRow` (widened in forms-and-arrivals) | responses | arrivals lanes | proposed |
| `ArrivalState` | responses | `ArrivalRow` | proposed |
| `ChannelMark` (five marks, one order) | responses | forms-and-arrivals, followups (funnel) | proposed |
| `WhoMatch`, `ReferenceMatch` | responses | forms-and-arrivals (`RecognitionChip`) | proposed |
| `ScanReview`, `FieldReading` | responses | | proposed |
| `ChangesPreview` | responses | | proposed |
| `DismissForm` | responses | | proposed |
| `NewResponsesCount` | responses | forms-and-arrivals | proposed |
| `AgeStamp` | forms-and-arrivals | every handoff | proposed |
| `LaneTabs` (a `Tabs` with counts and ages) | forms-and-arrivals | | proposed |
| `RecognitionChip` | forms-and-arrivals | responses | proposed |
| `CycleRow`, `CycleLens`, `DeadlineStrip`, `ObligationNote` | forms-and-arrivals | | proposed |
| `GapRow`, `HandledByHand`, `CoverageMap` | forms-and-arrivals | | proposed |
| `CandidateReview`, `ClockList`, `SourceJoin` | forms-and-arrivals | | proposed |
| `FormRegister`, `LibraryRow` | form-library | forms-and-arrivals, followups (Forms tab) | proposed |
| `TierBadge`, `VersionStamp`, `StaleNote`, `AdjustmentDiff` | form-library | | proposed |
| `CheckFinding` (one row of the built `Findings`) | form-library | | proposed |
| `FormPage`, `MemberClockPanel`, `QuestionWithWhy`, `HelpFooter` | form-library | | proposed |
| `AcknowledgmentReceipt` | form-library | | proposed |
| `FormPicker`, `RequestTracker` | form-library | | proposed |
| `CampaignCard`, `CampaignFunnel`, `CampaignCopies` | followups | forms-and-arrivals | proposed |
| `OutstandingList`, `UnreachablePanel` | followups | the dock (unreachable) | proposed |
| `FollowUpRow`, `FollowUpBand`, `FollowUpStrip`, `BasisChip` | followups | the dock's Deadlines | proposed |
| `ConnectionChip` | admin-components | instance, Status, Setup | proposed |
| `IntegrationCard`, `CredentialLine`, `CapabilityList`, `RateLimitNote`, `CheckResult` | admin-components | instance | proposed |
| `CadenceTable`, `ScheduleRow`, `CadenceEditor`, `PauseBanner` | admin-components | instance | proposed |
| `ServiceStatus`, `LaneRow` | admin-components | instance | proposed |
| `VaultStatus`, `MigrationPlan` | admin-components | instance | proposed |
| `SourceStanding` (a `Pill` preset; was `StandingWord`) | admin-components | Status | proposed |
| `TerminalStep` | admin-components | every handoff | proposed (built: `Command`) |
| `CommunityRow`, `ConnectDialog`, `StepCheck`, `RedirectUri`, `SecretDrop`, `FileDrop`, `DisconnectConfirm` | instance-and-integrations | | proposed |
| `HeldRow`, `PersonSteps`, `RecitalBlock`, `ScrollRow` | held-setup-roster | responses (held), instance, form-library | proposed (`HeldNote`, `Recitation`, `Tabs` built) |

## E. Glyphs

The existing vocabulary (`GLYPH_META`, one meaning per glyph; names only): attention (`info`, `clock`, `triangle-alert`, `octagon-alert`, `circle-check`, `circle-dashed`, `circle-question-mark`), provenance (`proposal`, `stamp`, `signature`, `cosign`, `badge-check`, `send`, `circle-pause`, `held-proposed`, `undo-2`, `history`, `lock`), governance (`calendar`, `list-ordered`, `gavel`, `vote`, `rollcall`, `quorum`, `users`, `user-x`, `megaphone`, `bell`, `bell-ring`, `flag`, `board`, `exec-session`, and others), records (`file-text`, `paperclip`, `folder-search`, `inbox`, `mail`, `notice`, `link`, `qr-code`, `eye-off`, `eye`, `upload`, `clipboard-check`, `file-check`, `file-x`, `file-clock`, and others), property (`mailbox`, `key-round`, `unit`, `owner`, `building`), money (`hourglass`, `receipt`, `vendor`, and others), nav (`calendar-clock`, `repeat`, `list-checks`, `search`, `external-link`, `copy`, `download`), actions (`check`, `plus`, `pencil`, `refresh-cw`, `log-in`).

The handoffs ask for these. One meaning per glyph; a request that reuses a taken glyph is a conflict the design resolves.

| # | Meaning asked for | Asked in | Candidate and conflict |
|---|---|---|---|
| 1 | An arrival that is new | responses | proposed `circle-question-mark`, which means "needs an answer from a person" (conflict) |
| 2 | An arrival seen and left | responses | "a plain dot", not `eye-off` (hidden) |
| 3 | Confirmed by a person (`keyed`) versus recorded in PayHOA | responses | `circle-check` and a filled `circle-check`; `circle-check` already means "on the record and complete"; two meanings need two marks, and `badge-check` is "approved" |
| 4 | Five channels: PayHOA form, email, mailed scan, Google Form, keyed from paper (four new marks) | responses | email can be `mail` (Correspondence); `mailbox` is the property's mailboxes; `inbox` is incoming mail; an attachment is drawn with `paperclip`, which means "attached to an agenda item" (conflict) |
| 5 | Confidence: high, medium, low (three marks beside words) | responses | none |
| 6 | Needs development | forms-and-arrivals | none |
| 7 | Recognized (a form jason sent) | forms-and-arrivals | none |
| 8 | A reference we did not send | forms-and-arrivals | none; not `triangle-alert` (overdue) |
| 9 | An arrival's party and kind (a government notice, a form, an unknown) | forms-and-arrivals | the sketch uses a flag, a sheet, and a question mark: `flag` is "flagged by a person", `circle-question-mark` is taken; `notice`, `file-text` are free |
| 10 | The three tiers: state, family, custom (three marks) | form-library | none |
| 11 | Follow-up kinds: remind, deadline, resend, review (four marks) | followups | `bell` ("jason reminded someone"), `calendar-clock` (Deadlines), `send` (Sent, conflict), `clipboard-check` (Checked) are near |
| 12 | Unreachable | followups | none |
| 13 | A connection is failing | admin-components | a new glyph; not `triangle-alert` (overdue) or `octagon-alert` (stop) |
| 14 | A connection or schedule is paused / not scheduled | admin-components | `circle-pause`, which means "held for the board" (conflict) |
| 15 | A connection needs sign-in | admin-components | `key-round`, which means "access: keys, fobs, gate codes" (conflict) |
| 16 | A connection is connected; not set up | admin-components | `circle-check` (shared with 3) and `circle-dashed` ("missing") |

That is 16 requests for 31 marks (counting the five channel marks, the three confidence marks, the three tiers, and so on). Three already exist in the vocabulary (`mail` for email, `circle-check` for connected, `circle-dashed` for not set up). Six propose a glyph whose meaning is taken (requests 1, 3, 14, 15, the paperclip in 4, and the flag in 9).

## F. Decisions that are the design's, in one list

Each handoff's list, kept in its own words, numbered by screen. Answer them in one pass. Where several handoffs ask the same thing in different words, the entries are adjacent.

**1. Responses** (handoff-responses)
1.1 Whether the open arrival is a right panel or its own page on a wide screen.
1.2 Whether the page and the reading are tied by highlight alone, or also by a numbered pin on the page. (The reading carries no per-field page position today; the link needs one built.)
1.3 How a low-confidence field is surfaced: a band of "Check these" above the form, or a mark in the form's order. (Confidence is a number from 0 to 1; the design chooses the three words' thresholds.)
1.4 The glyph for email, and whether the four (now five) channel marks share a frame.
1.5 Whether directors see the list's counts and states without the scan (the proposal), or nothing.
1.6 Whether `NewResponsesCount` lives on the dock, the digest, or both.

**2. Arrivals, the cycle board, the forms register, needs development, form candidates** (handoff-forms-and-arrivals)
2.1 Whether Arrivals replaces the Inbox or sits beside it, and how a letter from the mail service and an email from a vendor share a row.
2.2 Whether a lane is a tab, a section, or a filter, on a phone.
2.3 How the cycle board's seven columns collapse on a narrow screen (a card per owner, or a list of lenses first).
2.4 How a required follow-up is told apart from a policy one at a glance.
2.5 Whether Forms and Needs development are two screens or two tabs of one administrator page.
2.6 The glyph for "needs development", for "recognized", and for "a reference we did not send" (one meaning per glyph).

**3. The form page, the request center, the library** (handoff-form-library)
3.1 How much of the recital shows by default on a phone, and how the full section is reached from paper (a short link, or a QR code the Mailroom's page budget allows).
3.2 Whether "What happens next" sits above the questions (the proposal: the member should know the clock before committing) or beside them on a wide screen.
3.3 How the request center groups forms when a community has many custom forms.
3.4 Whether the library is its own page or a tab of Forms (`#/forms`), and how a diff reads on a narrow screen. (The Forms register and the library are now one table; the question is whether it is a page or a tab.)
3.5 The glyphs for a form's three tiers (one meaning per glyph).
3.6 How a member who prefers paper reaches "My requests" (a reference lookup on the receipt).

**4. Campaigns and follow-ups** (handoff-followups)
4.1 Whether the two views are two screens or two tabs of one page, and how the funnel and the next follow-up link to each other.
4.2 How the funnel draws "by how asked" and "by how answered" so a person never mistakes them for stages.
4.3 How the bands read on a phone (a single list with sticky band headings, or a week strip first).
4.4 How a deferred item shows its old and new date without looking overdue.
4.5 Whether `FollowUpStrip` belongs in the dock only, in the screen only, or both.
4.6 The glyphs for the follow-up kinds (remind, deadline, resend, review) and for "unreachable" (one meaning per glyph).

**5. The administrator's components** (handoff-admin-components)
5.1 The glyph for "failing" (one meaning per glyph; the overdue and stop glyphs are taken).
5.2 Whether a community row shows five dots or a summary ("6 connected, 1 needs sign-in").
5.3 How a sign-in pause covering many schedules reads in the `CadenceTable`: one banner over the group, or a marker on each row.
5.4 How `ServiceStatus` shows two communities sharing one machine's GPU lane.
5.5 Whether `MigrationPlan` lives on the vault's panel or as its own step in onboarding.

**6. Instance administration and the setup dialogs** (handoff-instance-and-integrations)
6.1 Whether Instance is its own nav group or Status grows into it.
6.2 How `ConnectDialog` resumes: from the step that failed, or from the start with completed steps collapsed.
6.3 How a long provider-console step (Google's nine) stays readable: one step per page, or a checklist with expanding steps.
6.4 How the five connection states read at a glance in a community row. (Close to 5.2; answer them together.)

**7. Raised while checking the handoffs against the code** (not in a handoff; each needs an answer before it is built)
7.1 The owner's request center cannot be `#/requests` (it is the manager's Requests screen): name its route.
7.2 Name the routes for Forms and campaigns and for Follow-ups (and `#/cycle`'s place among the owner-information tabs).
7.3 Resolve the six glyph conflicts in the table above (new, confirmed and recorded, attachment, a government notice's flag, paused, needs sign-in) by a new mark or by a stated shared meaning.
7.4 A manual arrival (a return keyed from paper) with no scan has no reading: `ScanReview`'s correction input starts empty, every answer keyed. Draw that state.
7.5 The funnel's "asked" counts emailed copies and lists no mailed recipients; "asked 107 owners" cannot be drawn. Draw asked as copies sent plus mailings, with owners "never sent a copy" as its own count.
7.6 A closed campaign's funnel is read live from disk and is not frozen; say so, or ask for it to be frozen at close.
7.7 `AgeStamp` against the built `Freshness` of `CitedSections`: keep two components or fold one into the other.
7.8 A director's counts-only view is the same list with names withheld, not a held item: name that state of `OutstandingList`, `ArrivalRow`, and `FollowUpRow`.

That is 33 decisions from the handoffs (6 + 6 + 6 + 6 + 5 + 4) and 8 more raised here.

## G. What can be designed now, and what waits

**Design now, from real JSON** (copy a tool's output; the sample set in section H has the same field names):

- The responses list and one arrival: the arrival row, the five-channel `checked` strip, the tab counts (`inbox`), a reading with its fields, `how`, confidence, the reference and the copy compared with the unit and owner, the notes, the keyed answers, the acts, and `left` (the next step as a command).
- The campaign card and its funnel, `OutstandingList` and `UnreachablePanel`, and the follow-ups list with its basis, its outstanding count, its command, its source's age, and the states done, deferred, and dropped.
- The form library table (tier, version, status, adjusted, not offered, failing, the stale finding, the seven checks, a form's recitals, clocks, and required content) and the form candidates review.
- The integrations cards, the schedule table, the service panel, the Status standing rows.

**Waits on a build** (propose the design; mark it proposed):

- Every console route above (`/api/responses*`, `/api/campaigns*`, `/api/followups`, `/api/forms*`, `/api/form-candidates`, `/api/instance/*`, `/api/my-requests`, `/api/arrivals*`, `/api/cycle`, `/api/instance/gaps`), and every console **write**: confirm, dismiss, seen, done, defer, drop, add, open or close a campaign, confirm, hold, or drop a candidate, change or pause a schedule, check live, move a credential. Today each is a command with `--by NAME`.
- The arrivals catalog (party, kind, lane, clock, route, correction) and the handler registry with its gaps and coverage map. Both are designed and not written.
- The per-owner cycle board join, and a "second addresses" count.
- A field's page position and crop (the page-to-reading link, "could not read this" with its image), two readings that disagree, a per-field blank, and a per-arrival `ChangesPreview`.
- A restore for a dismissed arrival; a "stale" word on a channel; "mine" and "yours" on follow-ups; a done follow-up that stays visible for a day; the board's-rule basis (no adoption hook yet); a form stale against an amendment as a follow-up.
- The form page's questions, member clock, and receipt in the command's JSON; the request center's groups; `AdjustmentDiff`; the amendment's words in a stale note.
- The integrations' setup steps, capability notes, and instances in the JSON; the vault as JSON; `jason integrations import` and `connect`; an officer's read-only chips.
- Per-check "who ran it" (only the first successful check records a person).

## H. A made-up community to design against

One community, **oakview**: eight units, one open campaign, five arrivals in five states, two bounced notices, three follow-ups, one form not offered, one form stale. Every value is plainly fake; every field name is copied from the command or tool that returns it (a sent copy: `SentCopy`; an arrival: `new_responses`; the funnel: `campaign_status`; a follow-up: `followups`; a form: `jason form-library --json`). The day is 2099-10-07 and the time 12:00 UTC. The owner of each unit is joined from the owner list (in the catalog itself there are only ids). Tiers in the form table are illustrative.

```json
{
  "now": "2099-10-07T12:00:00+00:00",
  "community": {"key": "oakview", "name": "Oakview Example HOA", "zone": "America/Los_Angeles"},

  "campaign": {"code": "NP99E", "form": "owner-info", "formKey": "owner-info", "version": "1", "asOf": "2099-01-01",
               "authority": ["CIV 4041"], "handler": "owner-information", "options": {}, "procedure": "owner-info-cycle",
               "channel": "email", "year": 2099, "cycle": {"opened": "2099-10-01", "returnBy": "2099-10-23"},
               "by": "A. Admin", "chosenAt": "2099-09-30T17:00:00+00:00", "status": "open", "closedBy": "", "closedAt": "",
               "adopted": false, "written": true,
               "copies": 8, "mailings": 0, "returned": 4, "recorded": 1, "request": "owner-information-2099"},

  "sentCopies": [
    {"reference": "NP99E-1A1A1-A1", "form": "owner-info", "year": 2099, "channel": "email", "identity": "copy", "unit": "123 Main St", "unitId": 1, "membershipId": 5001, "owner": "A. Owner", "firstSent": "2099-10-01T15:00:00+00:00", "lastSent": "2099-10-01T15:00:00+00:00", "campaign": "NP99E", "handler": "owner-information", "formVersion": "1"},
    {"reference": "NP99E-2B2B2-B2", "form": "owner-info", "year": 2099, "channel": "email", "identity": "copy", "unit": "456 Oak Ln", "unitId": 2, "membershipId": 5002, "owner": "B. Owner", "firstSent": "2099-10-01T15:00:00+00:00", "lastSent": "2099-10-01T15:00:00+00:00", "campaign": "NP99E", "handler": "owner-information", "formVersion": "1"},
    {"reference": "NP99E-3C3C3-C3", "form": "owner-info", "year": 2099, "channel": "email", "identity": "copy", "unit": "789 Elm Ct", "unitId": 3, "membershipId": 5003, "owner": "C. Owner", "firstSent": "2099-10-01T15:00:00+00:00", "lastSent": "2099-10-01T15:00:00+00:00", "campaign": "NP99E", "handler": "owner-information", "formVersion": "1"},
    {"reference": "NP99E-4D4D4-D4", "form": "owner-info", "year": 2099, "channel": "email", "identity": "copy", "unit": "101 Example Way", "unitId": 4, "membershipId": 5004, "owner": "D. Owner", "firstSent": "2099-10-01T15:00:00+00:00", "lastSent": "2099-10-01T15:00:00+00:00", "campaign": "NP99E", "handler": "owner-information", "formVersion": "1"},
    {"reference": "NP99E-5E5E5-E5", "form": "owner-info", "year": 2099, "channel": "email", "identity": "copy", "unit": "102 Example Way", "unitId": 5, "membershipId": 5005, "owner": "E. Owner", "firstSent": "2099-10-01T15:00:00+00:00", "lastSent": "2099-10-01T15:00:00+00:00", "campaign": "NP99E", "handler": "owner-information", "formVersion": "1"},
    {"reference": "NP99E-6F6F6-F6", "form": "owner-info", "year": 2099, "channel": "email", "identity": "copy", "unit": "103 Example Way", "unitId": 6, "membershipId": 5006, "owner": "F. Owner", "firstSent": "2099-10-01T15:00:00+00:00", "lastSent": "2099-10-01T15:00:00+00:00", "campaign": "NP99E", "handler": "owner-information", "formVersion": "1"},
    {"reference": "NP99E-7G7G7-G7", "form": "owner-info", "year": 2099, "channel": "email", "identity": "copy", "unit": "104 Example Way", "unitId": 7, "membershipId": 5007, "owner": "G. Owner", "firstSent": "2099-10-01T15:00:00+00:00", "lastSent": "2099-10-01T15:00:00+00:00", "campaign": "NP99E", "handler": "owner-information", "formVersion": "1"},
    {"reference": "NP99E-8H8H8-H8", "form": "owner-info", "year": 2099, "channel": "email", "identity": "copy", "unit": "105 Example Way", "unitId": 8, "membershipId": 5008, "owner": "H. Owner", "firstSent": "2099-10-01T15:00:00+00:00", "lastSent": "2099-10-01T15:00:00+00:00", "campaign": "NP99E", "handler": "owner-information", "formVersion": "1"}
  ],

  "checked": [
    {"channel": "payhoa", "lastOk": "2099-10-07T10:00:40+00:00", "lastTried": "2099-10-07T10:00:40+00:00", "ended": "ok", "reason": "", "ageHours": 2.0},
    {"channel": "gmail", "lastOk": "2099-10-07T10:00:12+00:00", "lastTried": "2099-10-07T10:00:12+00:00", "ended": "ok", "reason": "", "ageHours": 2.0},
    {"channel": "mail", "lastOk": "2099-10-07T10:00:44+00:00", "lastTried": "2099-10-07T10:00:44+00:00", "ended": "ok", "reason": "", "ageHours": 2.0},
    {"channel": "forms", "lastOk": "", "lastTried": "2099-10-07T10:00:12+00:00", "ended": "skipped", "reason": "no request is answered by this channel", "ageHours": null},
    {"channel": "manual", "lastOk": "", "lastTried": "", "ended": "keyed by a person (nothing to check)", "reason": "", "ageHours": null}
  ],

  "inbox": {"new": 1, "seen": 0, "read": 1, "keyed": 1, "recorded": 1, "dismissed": 1},

  "arrivals": [
    {"id": "gmail:18f0a1b2c3d4e5f6", "request": "owner-information-2099", "channel": "gmail", "at": "2099-10-03T19:24:26+00:00", "ageHours": 88.6, "who": "A. Owner", "unit": "123 Main St", "summary": "Form attached", "attachments": ["Scan 2099-10-03.pdf"], "state": "new", "supersededBy": "", "note": "", "keptAt": "2099-10-04T16:30:12+00:00"},
    {"id": "gmail:27a1b2c3d4e5f607", "request": "owner-information-2099", "channel": "gmail", "at": "2099-10-04T09:10:00+00:00", "ageHours": 74.8, "who": "D. Owner", "unit": "101 Example Way", "summary": "Re: Owner information [Ref NP99E-4D4D4-D4]", "attachments": ["Scan 2099-10-04.pdf"], "state": "read", "supersededBy": "", "note": "its subject carries the reference of a copy jason sent", "keptAt": "2099-10-04T16:30:12+00:00"},
    {"id": "mail:7731", "request": "owner-information-2099", "channel": "mail", "at": "2099-10-05T14:00:00+00:00", "ageHours": 46.0, "who": "E. Owner", "unit": "102 Example Way", "summary": "Mailed return, marker NP99E", "attachments": ["contents.pdf"], "state": "keyed", "supersededBy": "", "note": "", "keptAt": "2099-10-05T16:30:44+00:00"},
    {"id": "payhoa:1001", "request": "owner-information-2099", "channel": "payhoa", "at": "2099-10-02T20:00:00+00:00", "ageHours": 112.0, "who": "F. Owner", "unit": "103 Example Way", "summary": "Owner information request", "attachments": [], "state": "recorded", "supersededBy": "", "note": "PayHOA status: unknown", "keptAt": "2099-10-03T16:30:40+00:00"},
    {"id": "gmail:3b9c0d1e2f3a4b5c", "request": "owner-information-2099", "channel": "gmail", "at": "2099-10-05T21:40:00+00:00", "ageHours": 38.3, "who": "G. Owner", "unit": "104 Example Way", "summary": "Question about the form", "attachments": [], "state": "dismissed", "supersededBy": "", "note": "", "keptAt": "2099-10-06T10:00:12+00:00"}
  ],

  "reading_of_gmail:27a1b2c3d4e5f607": {
    "label": "evidence for a person, never an answer: nothing here is an owner's answer until a person confirms it",
    "readAt": "2099-10-05T17:02:00+00:00", "by": "A. Admin", "model": "", "how": "scan", "isTheForm": true,
    "files": [{"name": "Scan 2099-10-04.pdf", "how": "scan", "linesMatched": 31}],
    "reference": {"text": "NP99E-4D4D4-D4", "how": "text and bars", "campaign": "NP99E", "campaignMatchesRequest": true,
      "copy": {"found": true, "reference": "NP99E-4D4D4-D4", "channel": "email", "year": 2099, "firstSent": "2099-10-01T15:00:00+00:00",
               "sentToUnit": "101 Example Way", "readUnit": "101 Example Way", "sentToOwner": "D. Owner",
               "matchesUnit": true, "matchesOwner": true, "matchesWrittenUnit": true, "foundBy": "mark", "sure": "high", "putRight": false,
               "says": "a hint checked against what was sent, not a reading"}},
    "owner": {"unit": "101 Example Way", "name": "D. Owner", "matchedBy": "the sender's address"},
    "fields": {"name": {"value": "D. Owner", "how": "ocr", "confidence": 0.92},
               "unit-address": {"value": "101 Example Way", "how": "ocr", "confidence": 0.88},
               "email": {"value": "[email]", "how": "model", "confidence": 0.52},
               "delivery.email": {"value": true, "how": "mark", "confidence": 0.97}},
    "answers": {"name": "D. Owner", "unit-address": "101 Example Way", "email": "[email]", "delivery": ["By email"]},
    "signed": "2099-10-04", "signature": "Signed", "residual": 0.8, "notes": []
  },

  "noticeAttempts": [
    {"notice": "owner-information-2099", "unit": "456 Oak Ln", "owner": "B. Owner", "channel": "email", "key": "NP99E-2B2B2-B2", "sentAt": "2099-10-01T15:00:00+00:00", "status": "bounced", "statusAt": "2099-10-03T08:00:00+00:00", "reason": "the receiving server refused it: no such mailbox"},
    {"notice": "owner-information-2099", "unit": "789 Elm Ct", "owner": "C. Owner", "channel": "email", "key": "NP99E-3C3C3-C3", "sentAt": "2099-10-01T15:00:00+00:00", "status": "bounced", "statusAt": "2099-10-03T08:00:00+00:00", "reason": "the receiving server refused it: mailbox full"}
  ],

  "funnel": {"found": true, "campaign": "NP99E", "form": "owner-info", "version": "1", "year": 2099, "channel": "email", "status": "open",
             "returnBy": "2099-10-23", "request": "owner-information-2099", "at": "2099-10-07T12:00:00+00:00",
    "asked": {"total": 8, "byChannel": {"email": 8}, "mailings": 0, "source": "the sent-copy catalog", "ageHours": 141.0, "newestSent": "2099-10-01T15:00:00+00:00"},
    "answered": {"request": "owner-information-2099", "answered": 4, "read": 3, "confirmed": 2, "recorded": 1,
      "byChannel": {"payhoa": {"answered": 1, "read": 1, "confirmed": 1, "recorded": 1, "checkedHoursAgo": 2.0, "checked": "last succeeded 2099-10-07T10:00:40+00:00; last try ended ok"},
                    "gmail": {"answered": 2, "read": 1, "confirmed": 0, "recorded": 0, "checkedHoursAgo": 2.0, "checked": "last succeeded 2099-10-07T10:00:12+00:00; last try ended ok"},
                    "mail": {"answered": 1, "read": 1, "confirmed": 1, "recorded": 0, "checkedHoursAgo": 2.0, "checked": "last succeeded 2099-10-07T10:00:44+00:00; last try ended ok"},
                    "forms": {"answered": 0, "read": 0, "confirmed": 0, "recorded": 0, "checkedHoursAgo": null, "checked": "never checked"},
                    "manual": {"answered": 0, "read": 0, "confirmed": 0, "recorded": 0, "checkedHoursAgo": null, "checked": "keyed by a person: nothing to check"}},
      "inboxExists": true, "inboxAgeHours": 2.0, "source": "the response inbox, as the last check and the people who keyed returns kept it"},
    "outstanding": {"count": 2, "owners": [{"unit": "104 Example Way", "name": "G. Owner", "channel": "email", "sentAt": "2099-10-01T15:00:00+00:00", "daysSinceSent": 6},
                                           {"unit": "105 Example Way", "name": "H. Owner", "channel": "email", "sentAt": "2099-10-01T15:00:00+00:00", "daysSinceSent": 6}],
                    "neverAsked": 0, "source": "the sent-copy catalog less the answers kept", "ageHours": 141.0},
    "unreachable": {"count": 2, "owners": [{"unit": "456 Oak Ln", "why": "email bounced"}, {"unit": "789 Elm Ct", "why": "email bounced"}],
                    "source": "the notice ledger", "ageHours": 28.0, "syncedAt": "2099-10-06T08:00:00+00:00", "attempts": 2},
    "ages": {"catalogHours": 141.0, "inboxHours": 2.0, "checks": {"payhoa": 2.0, "gmail": 2.0, "mail": 2.0, "forms": null, "manual": null},
             "ledgerHours": 28.0, "ledgerSyncedAt": "2099-10-06T08:00:00+00:00"},
    "missing": [], "notes": []},

  "followUps": [
    {"id": "fu-6a7b8c9d01", "kind": "resend", "due": "2099-10-06", "windowEnd": "", "subject": "owner-information-2099",
     "what": "2 members (email outcome read 2099-10-03): resend by first-class mail and ask for a working email", "basis": "law",
     "cite": "CIV 4041(e), 4040(a)(2)", "dueNote": "proposed: 3 days after the outcome was read (2099-10-03); the law sets no day",
     "outstanding": 2, "names": ["456 Oak Ln", "789 Elm Ct"], "reason": "", "state": "overdue", "by": "", "at": "", "why": "", "deferredTo": "",
     "command": "jason owner-info --mail-batch --only \"456 Oak Ln\" --only \"789 Elm Ct\" --resend (a dry run; --yes with --confirmed-by NAME sends)",
     "campaign": "", "source": "ledger"},
    {"id": "fu-1b2c3d4e5f", "kind": "review", "due": "2099-10-07", "windowEnd": "", "subject": "gmail:18f0a1b2c3d4e5f6",
     "what": "Read the returned form that came by gmail from A. Owner (123 Main St)", "basis": "proposed policy",
     "cite": "no number is adopted: the board decides how soon an arrival is read, confirmed, and recorded", "dueNote": "proposed: 3 days after 2099-10-04",
     "outstanding": 1, "names": ["A. Owner (123 Main St)"], "reason": "", "state": "due", "by": "", "at": "", "why": "", "deferredTo": "",
     "command": "jason responses --read gmail:18f0a1b2c3d4e5f6 --by NAME", "campaign": "", "source": "inbox"},
    {"id": "fu-9e8d7c6b5a", "kind": "remind", "due": "2099-10-16", "windowEnd": "2099-10-23", "subject": "NP99E",
     "what": "Remind 2 owners who have not answered the NP99E request", "basis": "proposed policy",
     "cite": "proposed: remind 7 days before the return-by date (the board has not adopted a number)", "dueNote": "proposed: 7 days before 2099-10-23",
     "outstanding": 2, "names": ["104 Example Way (G. Owner)", "105 Example Way (H. Owner)"], "reason": "", "state": "upcoming", "by": "", "at": "", "why": "", "deferredTo": "",
     "command": "jason owner-info --email-batch --follow-up reminder --message FILE.md (a dry run; --yes sends)", "campaign": "NP99E", "source": "campaign"}
  ],

  "forms": [
    {"key": "owner-info", "tier": "state", "jurisdiction": "CA", "version": "1", "asOf": "2099-01-01", "title": "Owner information request", "authority": ["CIV 4041"],
     "handler": "owner-information", "procedure": "owner-info-cycle", "status": "ready", "missing": [], "applied": [], "refused": [], "findings": []},
    {"key": "records-request", "tier": "state", "jurisdiction": "CA", "version": "2", "asOf": "2099-01-01", "title": "Request to inspect records", "authority": ["CIV 5205", "CIV 5210"],
     "handler": "response-clock", "procedure": "respond", "status": "adjusted", "missing": [],
     "applied": ["clock replaced: acknowledge: 3 business days from receipt (documents: ccrs#4.15)"], "refused": [], "findings": []},
    {"key": "adr-request", "tier": "state", "jurisdiction": "CA", "version": "1", "asOf": "2099-01-01", "title": "Request for resolution", "authority": ["CIV 5925"],
     "handler": "response-clock", "procedure": "respond", "status": "failing", "missing": [], "applied": [], "refused": [],
     "findings": [{"form": "adr-request", "check": "recitals", "checkNumber": 2, "severity": "fail", "item": "CIV 5925",
                   "message": "stale: the shelf logged a change to its words on 2099-06-01, after the form's as-of 2099-01-01; read the amendment, update the definition, and bump its version (now 1)"}]},
    {"key": "rental-application", "tier": "family", "jurisdiction": "CA", "version": "1", "asOf": "2099-01-01", "title": "Rental application", "authority": [],
     "handler": "response-clock", "procedure": "respond", "status": "not offered",
     "missing": ["binding: section", "binding: decider", "binding: clock decide"], "applied": [], "refused": [],
     "findings": [{"form": "rental-application", "check": "slots", "checkNumber": 3, "severity": "not offered", "item": "binding: section", "message": "not given: the form is not offered until it is"}]}
  ]
}
```

Reading that sample set: `oakview` has asked eight owners by email and four have answered (one by PayHOA and recorded, one by a mailed scan and confirmed, one by email read and waiting for a person to confirm, one by email not yet looked at); a fifth message was a question and was dismissed. Two owners' emails bounced, so they are unreachable and not outstanding; the two who have not answered are the outstanding ones. Three follow-ups are open: the law's resend by mail (overdue, with a proposed day count), reading A. Owner's scan (due today, proposed), and the reminder (a week before the return-by date, proposed). One form is not offered (a family form with no binding), and one is failing because a section it cites was amended after the form's as-of day.
