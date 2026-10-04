# The console handoff's third cut, reconciled with what is built

The design agent's third cut (2026-10-04) adds these pieces:
- Set up the community, and the first-run state;
- People and offices;
- the board packet as step 5 of Plan a meeting;
- letterhead print and the owner statement;
- five emails;
- a community record (`community.js`) with a second, made-up association;
- the meeting room's host panel as a bottom sheet on phones.

This page checks each piece against the repo and the rules, for both readers:
- **the design agent:** what to change;
- **the build:** what is new for us.

It extends [handoff-reconciliation.md](handoff-reconciliation.md), whose 28 corrections still stand.

## First: the 28 corrections still stand

The third cut's brief (CLAUDE-CODE-BRIEF.md) repeats most of what the first reconciliation corrected. Before anything new, apply these again:

| # | What the brief still says | The correction |
|---|---|---|
| 1 | Routes and emails in jason-mcp | jason-web's routes; jason-mcp is read-only stdio |
| 2 | The client sets an approval's `stage` | Approval is a transition with `by` |
| 3, 4 | `/api/screens/:id`; screens read once per session | Each loader is the screen's read, with `asOf`; nothing is cached |
| 5 | Log Confirm summaries | Log structured acts only |
| 6 | The administrator lands on Approvals and approves; four role classes | Offices from the roster. The administrator holds no office and approves nothing |
| 8 | Board approval with no meeting | "Waiting on the board's meeting of DATE"; recorded by the president or the secretary |
| 9 | Send moves a letter to `sent` | The terminal command, then `record_sent` with its `sentRef` |
| 11 | Tiers are facts | The tier is labeled as jason's suggestion |
| 12 | A 90-minute meeting, a 3-minute forum, meeting − 5 days, setup + 14 days | `board_meeting_policy()`, `open_forum_limit()`, the board's lead time; no number without its source |
| 13 | 4926 lines for any remote meeting; 4930 as the forum limit; 4935 as a notice line | 4926 only for a meeting held entirely by teleconference; a hybrid meeting is 4090(b) |
| 14 | Recused directors count toward quorum | `BoardRule.interested_in_quorum` with its source, else "not on file; ask counsel" |
| 15 | Table, continue, refer as Confirm acts | Motions the board votes on |
| 17 | "A member" for an unmatched caller | "unidentified caller" and the number's last four digits |
| 18 | Retention = meeting + 30 days | 30 days is 4950(a)'s clock for the minutes, not retention |
| 20 | Promote to `Drive/Board/<Kind>s/<title>.docx` | The letters' approval, then a `google.doc` plan, as a Google Doc |
| 21 | `missing`, `stale` after 3 years, `withheld` for 5215(a) kinds | "Not found" with *not confirmed*; 5550's own conditions; "withheld" only what a person withheld |
| 22 | Balance recomputed; a payment plan offered above one assessment | PayHOA's balance with a mismatch flag; the offer to an owner sent a 5660 notice |
| 23 | Request clocks hardcoded; payment plans to the treasurer; the *filed* seal | Clocks only from `ResponseRule` rows; payment plans to the board; no seal |
| 24 | "Keep my name out" as before | "Ask to keep my name out", on complaints, once the board's policy is adopted |
| 25 | Owners see Records | The request form only |
| 26 | The glyph layer | Built as components ([components.md](components.md#marks-glyphs-stamps-seals-routing-tags)); the layer is not shipped |
| 28 | Fixtures exported from browser storage; "policies (6)" | The loaders' shapes with made-up data in `tests/fixtures` |

The brief's "Decisions still open" (§5) is also unchanged. Its answers are in the first reconciliation's table: quorum from `Community.board()`, the forum from the board's policy, retention from `meeting-records`, owners from PayHOA, and the reviewer and the sender from the roster.

The meeting rules are now built ([meetings-and-minutes.md](screens/meetings-and-minutes.md#the-meeting-rooms-rules-quorum-vote-recusal-open-forum)). The quorum, vote basis, recusal reading, open-forum limit, and notice period each come with their source, or say they are not on file. The marks are built too: Glyph, Stamp, Seal, and RoutingTag, synced to the design project.

## Set up the community, and the first run

**What exists.** Onboarding is jason's setup (`jason.community.onboarding`; [onboarding.md](../onboarding.md), [onboarding-ux.md](../onboarding-ux.md)):
- **The checklist:** 108 items in 15 groups, and five gates (START to ADOPT).
- **Status:** each item's is *computed* from checks (present, partial, missing); no one sets it.
- **The questions:** a `FactAsk` holds the question, where its answer goes (private facts, the profile, or Keeper), the stakes, and the clock.
- **The answers:** they go to the intake queue, and `jason onboard --apply` (by a person) applies them:
  - a private fact merges into `data/spec/<profile>.json`;
  - a profile fact becomes a **proposal** patch, because jason never edits the profile;
  - a high-stakes answer needs a second person.
- **The console already has** `GET /api/onboarding`, `GET /api/communities`, and the onboarding screen.

**The design's twelve parts** map onto the checklist's groups:

| Part | Groups |
|---|---|
| identity | address, website, theme |
| documents | the governing group and the establish gate |
| bylaws | board-rule, meeting-schedule, notice-rules, fiscal-year |
| officers | board-roster, signers |
| roster | units and owners |
| accounts | access |
| money | assessments, bank accounts, collections, budget |
| insurance | insurance |
| reserves | reserves |
| vendors | vendors |
| profile | website |

The design leaves out the recorded, corporate, meetings, elections, enforcement, architectural, records, and maintenance groups.

**Change:**
- **Setup is a view over `/api/onboarding`,** not a store of its own. Show its groups and gates, each item's computed status, and each `FactAsk` with its evidence.
- **A part is never marked "done" by a click.** It is present when its checks pass.
- **An answer is not a `POST /api/write/setup/:part` of values.** It is an intake answer that a person applies. A profile fact becomes a proposal for the profile's maintainer.
- **"Ask the OFFICE for the rest"** is the existing request list and its letter. It carries no "setup + 14 days" due date.
- **"Connect" is never OAuth from the browser.** PayHOA and Zoom credentials are Keeper records, signed in at a terminal (`jason login`). The screen shows the command. The browser never handles a secret (`intake.secret_reason` refuses one).
- **"Send invitations" is not jason's.** jason sends no email (below). A person invites, and the roster records who may sign in.
- **No "jason proposes 3 minutes".** Where the documents are silent, the forum limit is a policy the board adopts (`meeting-schedule` in [policy-catalog-design.md](../policy-catalog-design.md)). Until then: "no limit on record; the board sets it".
- **The "stage" (new or established)** is the five gates, computed.
- **First run:** while a gate is open, a screen's empty state names the item that fills it. That part is right, and it reads from `/api/onboarding`.

**Build (ours):** an intake answer route in jason-web (`POST /api/write/intake/<id>` with `by`, over `answer_intake_question` and its confirmation). None exists yet.

## The community record

**Most of `community.js` exists** in `/api/community-profile` and `/api/theme`:

| Field | Source |
|---|---|
| `wordmark`, `accent` | `Theme` |
| `legal` | `corporate_name()` |
| `short` | `name` |
| `email` | `Identity.official_email` and the groups by purpose |
| `site` | `site()` |
| `address` | `Identity.official_address` |
| `place` | `MeetingSchedule.place` |
| `calendar` | `calendar_id()` |
| `units` | `units()` |
| `fiscalYear` | `fiscal_year_end()` |

`Identity` also carries the signer, the posting location, the designated recipient, the time zone, the meeting platform, and management, which the design lacks.

**Change:**
- **`forum` and `quorum` are not numbers.** They are `open_forum_limit()` (none until adopted) and `BoardRule` (the quorum, the vote basis, and the recusal reading, each with its source).
- **`help` is a role.** The 4926 help contact is required only for a meeting held entirely by teleconference, and a person's phone number is a private fact.
- **`stage` is the gates.**
- **The sample's unit count is not the profile's.** A screen reads `units()`.
- **Switching communities is not a browser setting.** The profile is fixed when jason-web starts (`JASON_PROFILE`). Another association is another installation or profile. `/api/communities` lists the portal.
- **No theme file names a profile.** `themes/<profile>.css` duplicates the profile's own theme, which `/api/theme` serves.

**Build (ours, optional):** one `GET /api/community` that merges `identity()`, `board()`, `board_notice_period()`, `open_forum_limit()`, and `fiscal_year_end()`, each with its source.

## People and offices

**What exists:**
- **Offices:** an office is an `Officer` (role, name, `approves`, email), and one person may hold two offices (`offices_of`).
- **Names and emails:** these are private facts.
- **Sign-in:** the roster is built from the officers, plus the installation's administrators and managers (`jason.web.signin`).
- **Duties:** routing goes to the office that owns the duty (`Community.assignments`), never to a person by default. An unowned question stays unassigned.

**Change:**
- **People is read-only** in the console: each office, who holds it, what it approves, and whether the person can sign in, all from `/api/session`.
- **A change of office is the board's act, recorded in the minutes.** Then a person answers the board-roster question, which is high-stakes, so a second person confirms it. There is no `changeRole`, `addPerson`, `retire`, or `setTerm` from the browser.
- **A person may hold two offices.** One `role` per person is wrong.
- **The administrator is not an office** and approves nothing (correction 6).
- **Terms.** Officer and director terms differ. Officers are elected by the board as the bylaws say; directors serve the terms the members elected them to. Each term is a private fact with its source. jason has no term fields yet.
- **"Offices derived from the minutes' election record" is not built.** At most, a minutes reading is a lead a person confirms.
- **A vacant office does not route to the president.** That rule is invented. The bylaws' vacancy provision governs, recited: typically the board fills the office, and another officer acts only as the bylaws say. Show "No one holds OFFICE" with the provision. A duty whose office is vacant is unassigned.

**Build (ours):** term dates as private facts with their source, and a board-roster question for a recorded change.

## The board packet

**What exists:**
- **The packet:** `jason board --packet` ([board-agenda.md](../board-agenda.md)) gives, per item, the law quoted, the records now, the options, and a draft motion, written as a confidential Doc for directors and counsel.
- **The agenda plan** already keeps each item's `packet` files and executive `subject`, so there is no separate `/api/write/packet/:itemId`.

**Change:**
- **Recusal** follows `BoardRule.interested_in_quorum`, never "counts toward the quorum, not the vote (Corp. Code 7233)" (correction 14).
- **The cover** shows the forum limit only from `open_forum_limit()`.
- **Recite 4930 whole** with its exceptions, not "may act only on items listed".
- **A members' copy is its own review, not a flag.** The directors' packet can hold privileged and confidential material.
- **The rest is right:** the general line for an executive matter, the draft motion's label "for the board's convenience", files flagged when not attached, and a page per item.

**Build (ours):** `jason board --packet` still lists executive items by title. It should name them by their 4935 subject (`meeting_agenda.executive_lines()`), as the agenda and the minutes draft now do (lessons `executive-headings-copied` and `agenda-executive-words-to-minutes-model`).

## Letterhead print and emails

**What exists:**
- **One source per owner document.** The originals are Google Docs, and an owner document is one Markdown source rendered three ways: the email (the letterhead HTML), the letterhead Doc (`jason letter --markdown`, `broadcast --to-doc`), and the PDF.
- **The letterhead's facts** are `LetterheadSpec` and `Identity.signer`.
- **jason sends no email.** Its Gmail access is read-only. Owner email goes through PayHOA, sent by a person (`--email-batch --yes --confirmed-by`, a broadcast in PayHOA), and mail through `jason mailroom --send --yes`. Each sending is logged.

**Change:**
- **No email is "sent by jason-mcp on an officer's Confirm".** jason-mcp is read-only, jason sends nothing, and a send is a person's act at the terminal or in PayHOA, logged. The templates are Markdown the existing pipeline renders.
- **"Print or save as PDF" in the browser is a preview.** The official PDF comes from the Doc, so there is one original.
- **The letterhead's line names the association's signer** (`Identity.signer`), not "jason · records and correspondence, by direction of the board".
- **The meeting notice email:**
  - the notice period from `notice_period()` (the documents' longer period, 4920(b)(3)), not "four days";
  - the forum limit only when adopted;
  - the join, help, and individual-delivery lines only for a meeting held entirely by teleconference (4926); a hybrid meeting names its physical location (4090(b));
  - 4930 recited whole;
  - no "notices cannot be unsubscribed from". Recite 4041 and 4045: a member may ask for individual delivery and choose a delivery method.
  - An email reaches only the members whose 4041 choice is email. General delivery is the posting location or website the annual policy statement names (4045(a), 5310).
- **The weekly digest is not sent on a timer.** It is a read in the console. An email of it is a person's send.
- **Check the sample's own dates:** the digest's 5685 date, and the lien email's board vote before the payment it releases.

## The owner statement and the owner emails

**The owner view is built** as an allowlist of owner loaders (`jason.web.extra.owner_view`, `ui/src/ownerScreens.json`). There is no owner sign-in and no account screen. "My account" stays future, by a board decision (correction 22).

**Change:**
- **The statement** shows PayHOA's balance and flags a mismatch, never a recomputed one. Its clocks come from rows: "5 business days to the treasurer" is not a `ResponseRule`. Recite 5655, 5658, and 5660; do not paraphrase them.
- **Business days.** No "business days weighted 1.4". A date is `add_business_days` over the `ResponseRule`'s count.
- **The payment-plan email misstates 5665.** A plan does not stop a lien from being recorded (5665(d)); only additional late fees stop (5665(c)); and default is 5665(e). Recite the subdivisions; promise nothing beyond them.
- **The lien-released email** promises nothing the statute does not ("corrects at its own cost" is invented).
- **The request-answered email** carries the clock from its `ResponseRule`, has no "reply to reopen" (not built), and no link to a statement.

## The meeting room on a phone

The design is feasible. `HostPanel` can take `sheet` (auto under 720px), `open`, and `onOpenChange`; Previous and Next live in `MeetingRoomView`, which can hold them in a sticky row with 44px targets.

Serving the console to a phone is a deployment decision, not a layout one: jason-web binds 127.0.0.1 until sign-in and the access policy allow more ([security-and-privacy.md](security-and-privacy.md)).

**Build (ours):** the `sheet` and `open` props and the sticky row.

## The package itself

The design files must hold no real facts. This cut's do:
- **CommunityProfile:** a real person's name, a real case number, a real Drive id, and two real group addresses;
- **the real domain** in the community record, the roster seed, and every rendered email;
- **a calendar id** in the shape of a real one.

Replace each with made-up values (`example.org`, "123 Main St", "24CV000123"), and keep fixtures in `tests/fixtures`. A design file names the sample association only.

## The build, from this cut

1. **The packet's executive items by subject.** A fix: it is the same leak, closed for the agenda and the minutes.
2. **Setup over onboarding:** the intake answer route, then the Setup screen as a view of `/api/onboarding`.
3. **People:** read-only from the session; term dates and a recorded board-roster change.
4. **The notice template** from `notice_period()`, `open_forum_limit()`, and the 4090(b) and 4926 split, in the Markdown pipeline.
5. **`HostPanel` as a sheet,** and the sticky Previous and Next row.
6. **Optional:** `GET /api/community`.

The statement, the request picker, and the owner emails wait for the board's decisions (correction 22 and the build order's step 8).
