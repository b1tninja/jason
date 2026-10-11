# The owner view

The member's side of the console, `?view=owner` on any owner screen (landing `#/digest?view=owner`, "Overview"), in every group the nav shows an owner · phase 2 · CLI: none (a member has no CLI; the same loaders are `GET /api/<source>?view=owner`)

## In the console

**Built, in part.** `jason.web.extra.owner_view` answers every `GET /api/<source>?view=owner` from `OWNER_SOURCES` alone, each loader an allowlist of fields (never a filter of the board's answer), and refuses any other read under `/api/` with 403 (`PASSED_ENDPOINTS`: the session, a document's bytes and thumbnail). The screens an owner sees are named in `ui/src/ownerScreens.json`: Overview (`OwnerDigestView`), Live meeting, Meetings and minutes, Annual disclosures (`OwnerDisclosures`), Reserves and budget, Records (the request form), Insurance, and the Owner page. The guard is `tests/test_web_owner_view.py` (made-up delinquent owner, lien, hearing, executive item: none may come back) and `ui/src/views/ownerview.test.tsx`.

**This spec is the whole owner side, as proposed.** It keeps the built screens and adds the three a member still lacks: adopted rules and proposed rule changes, elections, and the general notices the association has given. Each source is marked built or to add below.

**Who a member is here: nobody.** Sign-in admits only the roster (`Community.officers()`, managers, jason's admins; `account_for` refuses any other email: "is not on the roster"). `role_class` returns "" for anyone else, and the console treats that as the owner view. The owner view is therefore **a view, not a sign-in**: the manager's preview of what a member is shown. No loader may say "your", look up a unit, or take a member's id, because the server cannot know who is asking. A member's own request, own hearing notice, and own balance are not here and cannot be until owners have accounts (open decision 1).

## Purpose and personas

What the association has already given or posted to members, in one place and in the order a member needs it: the next open meeting, the minutes, what arrived in the mail or inbox and the day it went out, the rules in force and those proposed, the election calendar and its reported results, and how to ask for a record. Nothing is shown that the association has not already given or posted.

- **Member (owner):** the audience. Today reaches it by a shared link or a printed packet a person delivers, not by sign-in.
- **Manager, secretary:** preview the view before a notice or an agenda goes out, to read it as a member would. The owner view is how they check that nothing private leaks.
- **Director, treasurer, counsel, reviewer:** no role here. A board member reads the board's screens.

## Data

| Part | Source (`OWNER_SOURCES` key) | Status |
|---|---|---|
| Overview: next open meeting and posted agenda, latest approved minutes, disclosures, standards, how to ask for a record | `owner-digest` (`owner_digest`) | Built |
| Open-session records by meeting: notice, agendas, minutes (draft or approved) where posted (PayHOA library, Drive, a PayHOA communication), never confidential, titles left empty | `meetings` (`owner_meetings`) | Built |
| Annual disclosures: statute, window, the day the delivery ledger shows each went out (`delivered`, `deliveredAs`), what each carries | `calendar` (`owner_disclosures`) | Built |
| Record kinds a member may ask for, with citation, meaning, retention; the 5210 clocks; never a request | `records-requests` (`owner_records`) | Built |
| Reserve funding summary and insurance summary the budget report carries | `reserves`, `insurance` | Built |
| The open session's stage: open items, current item, directors present, motions on open items; executive item as "Executive session" alone | `meeting-room` (`owner_meeting_room`) | Built |
| The public owner page (names, site pages, mailing address, group addresses by purpose) and the brand | `community-profile`, `theme` | Built (passed through) |
| **Rules in force and proposed rule changes.** Adopted: title, document, the adopted text, the day adopted, the day the adoption notice went out. Proposed: title, purpose and effect, the text, the day the proposal notice went out, the comment window, the meeting that decides. Only a change whose notice the delivery ledger shows as given | `owner-rules` | **To add.** Over `Community.rule_changes()` (as `rule_changes` in `sources.py`), `notice_evidence.ledger` for requirements `rule-change-proposed` and `rule-change-adopted`, and `Community.meeting_schedule()`. `OwnerDigest.policies.adopted` is `[]` today |
| **Elections.** Per election: kind (directors, recall, a member vote), the dates as the general notices gave them (nomination deadline, ballot distribution, return deadline and address, count meeting), the tabulated results once the inspector's report is recorded and the 15-day notice is given, the day each notice went out | `owner-elections` | **To add**, after the election store of [elections.md](elections.md) (not built; `data/elections/` does not exist). Reads only that store's notices and `results` |
| **General notices given to all members**, newest first: title, requirement, the day it went out, how (post, email, mail), the text as sent (`notice_record` `text.words`) | `owner-notices` | **To add.** Over `notice_ledger.notices` and `notice_record.build(key)` with `private=False`; only requirements whose recipients are all members, and counts never shown |
| The statutes a member is told about, as stored | `data/authorities` (`CIV-4340-4370.md`, `CIV-4900-4955.md`, `CIV-5100-5145.md`, `CIV-5200-5240.md`) | Recited, never paraphrased; no loader |

## Layout

The owner shell is the board's with the nav cut to the owner screens, the wordmark from `theme`, and a banner "Owner view: what a member receives. A view of the console, not a sign-in." The Overview, top to bottom:

```
+------------------------------------------------------------------------------------------+
| Oakview HOA · Owner view: what a member receives. A view, not a sign-in.   [Board view]  |
+------------------------------------------------------------------------------------------+
| NEXT OPEN MEETING                      | LATEST MINUTES                                  |
| Jun 9, 2099 at 7:00 pm, 123 Main St    | Approved minutes of May 12, 2099                |
| Notice (posted) · Agenda (posted)      | Minutes (2)  [open]                             |
| or: "The agenda is posted with the     | Draft minutes are within 30 days (CIV 4950).    |
| meeting's notice, at least four days   |                                                 |
| before the meeting (CIV 4920)."        |                                                 |
+------------------------------------------------------------------------------------------+
| RULES AND PROPOSED CHANGES (to add)                                                      |
| Proposed: Quiet hours · notice went out Apr 1, 2099 · comments through Jun 9, 2099       |
|   Decided at the board meeting Jun 9, 2099 [Recitation 4360(a),(b)]  [Text as sent]      |
| Adopted: Parking rules · adopted May 12, 2099 · notice went out May 20, 2099 [4360(c)]   |
+------------------------------------------------------------------------------------------+
| ELECTIONS (to add)  Board election 2099 · nominations close Feb 1 · ballots out Mar 2    |
|   Count meeting Apr 7, 2099 · Results: "waiting on the inspector's report" or the        |
|   tabulated results as reported, notice went out Apr 15, 2099 [Recitation 5120(b)]       |
+------------------------------------------------------------------------------------------+
| ANNUAL DISCLOSURES   Disclosure · Civil Code · Due · Went out (delivered Apr 28, 2099)   |
| NOTICES YOU HAVE BEEN GIVEN (to add)   newest first: title · day · how · [Text as sent]  |
| STANDARDS AND POLICIES · ASK FOR A RECORD (5210 clocks, link to the form)                |
+------------------------------------------------------------------------------------------+
| NEVER HERE  (collapsed card, always present)  The caveats, verbatim                      |
+------------------------------------------------------------------------------------------+
```

The other owner screens keep their built layouts (`MeetingsView`, `CalendarView`, `RecordsRequestsView`, `ReservesView`, `InsuranceView`, `MeetingRoomView`, `OwnerPageView`). Under 720 px every card stacks; the "Went out" column becomes a line under each disclosure.

## Components

Built: `ScreenHeader`, `Card`, `DataTable`, `DocList` (variant `row`), `Badge`, `Caveats`, `RemoteView`, `Recitation`, `ReadingLabel`, `Clock`, `StageSteps`. To add: `GivenLine` (a notice, its day, its method, and the text as sent in a quoted block with its sha256, styled apart from a recitation so the notice's words are never taken for the law's), `ElectionCalendar` (dates as the notices gave them, each beside the statute that forces the notice, results only when reported), `NeverHere` (the collapsed list below). Every reading is a `ReadingLabel`: "The association reads this to mean ...", never in the statute's voice.

**Recite first.** A card that names a statute opens a `Recitation` before any sentence of jason's. Stored words:

- CIV 4360(a): "The board shall provide general notice pursuant to Section 4045 of a proposed rule change at least 28 days before making the rule change. The notice shall include the text of the proposed rule change and a description of the purpose and effect of the proposed rule change."
- CIV 4360(b): "A decision on a proposed rule change shall be made at a board meeting, after consideration of any comments made by association members."
- CIV 4360(c) (first sentence): "As soon as possible after making a rule change, but not more than 15 days after making the rule change, the board shall deliver general notice pursuant to Section 4045 of the rule change."
- CIV 4920(a): "Except as provided in subdivision (b), the association shall give notice of the time and place of a board meeting at least four days before the meeting."
- CIV 4950(a) (first sentence): "The minutes, minutes proposed for adoption that are marked to indicate draft status, or a summary of the minutes, of any board meeting, other than an executive session, shall be available to members within 30 days of the meeting."
- CIV 5120(b) (first two sentences): "The tabulated results of the election shall be promptly reported to the board and shall be recorded in the minutes of the next meeting of the board and shall be available for review by members of the association. Within 15 days of the election, the board shall give general notice pursuant to Section 4045 of the tabulated results of the election."
- CIV 5230(a) (first sentence): "The association records, and any information from them, may not be sold, used for a commercial purpose, or used for any other purpose not reasonably related to a member’s interest as a member."

**Readings, labeled (the association's, not the statutes').** (1) The comment window runs from the day the proposal notice went out through the day of the deciding meeting: 4360(a) fixes 28 days before the rule change and (b) fixes consideration of comments at the meeting, but neither names a "comment deadline"; an earlier cutoff the board sets is a policy shown as PROPOSED until adopted. (2) The 28 days are counted by jason from the ledger's day; how a court counts is for counsel. (3) Whether a rule is within 4355's list is the board's call with counsel, so a change shows no "valid" or "in effect" stamp, only the days on record.

## Actions

None write. A member reads, follows a link, and (in the one place a form exists) opens the records request form.

| Control | Does | Writes? |
|---|---|---|
| Open a posted notice, agenda, or minutes | `DocList` link to the document's bytes (`local_file`, own sign-in and data-level checks) | No |
| Ask for a record | Opens `#/records-requests?view=owner`; the form's submission is the built records flow, recorded by the association and answered by a person | Built flow, not this spec |
| Board view / Owner view | Switch in the header; a view, not a check | No |
| Comment on a proposed rule change | **Not a console action.** The card names how the association receives comments (the address from `community-profile`, by purpose) | No |

## States

- **No next meeting:** "No meeting is scheduled on file." (built). **Agenda not posted:** the 4920 sentence above (built).
- **No approved minutes:** "No approved minutes are on file yet." (built).
- **No rule change given notice:** "No proposed rule change has been noticed to members." Never "no changes are planned": jason does not know. A change drafted, or noticed only in a Gmail draft, is not shown.
- **Fiscal year unset:** "The association's fiscal year is not set here, so the windows are not dated." (built).
- **No delivery shown:** "not shown yet" beside the disclosure (built). The ledger's day is evidence of delivery, not proof.
- **No election on record:** "No election is on record." Never "no election was held".
- **Count not yet done:** results read "waiting on the inspector's report". No count, tally, turnout, or lead appears before the inspector's report is recorded.
- **Source refused (403):** the owner shell shows the built message "{name} is the board's: it is not served in the owner view."
- **Source error:** the built 500 text in a `RemoteView` error, with a reload; never the board's answer as a fallback.

## Privacy

Nothing about another member, ever. A member sees only what the association has already given or posted to members.

**Never here (the `NeverHere` card, and the allowlist's meaning).** Another owner's name, unit, email, phone, or mailing address. Any balance, delinquency, lien, payment plan, or collection step. Discipline, a hearing, a fine, a cure, or a member's request for executive session. Any executive-session agenda, minutes, transcript, recording, chat, or AI summary (CIV 4935; the executive item reads "Executive session" and its general words only). A call's title. jason's drafts, the board's checks, schedule gaps, and board items, decisions, and registers. Any request, owner-information answer, or form response. The roster, the log, the polls, and admitted names in a live meeting. Policy numbers, premiums, and claims. A proposed policy or an unnoticed rule change. A ballot, an envelope, a voter list, a candidate registration list, how any member voted, whether one member has voted, and any running count (CIV 5100, 5120). The document library (some records are withheld, CIV 5215). The dock, Ask, Approvals, Inbox, and every board screen.

- **Hearings:** the owner view has no hearings loader. A member's own notice arrives by personal or individual delivery (CIV 5855(a), 4040); a member sees it there, not here.
- **Requests:** a member's own request, its status, and its clock are in PayHOA's portal and thread. `requests.md` and `personas-and-jobs.md` both exclude `member-requests` from the owner view; this spec keeps it excluded.
- **Elections:** a member's ballot comes from the independent inspector. The page shows dates and the results the inspector reported once the 15-day notice is given; never a ballot or tally before the count.
- **Addresses:** the owner page shows a group's address by purpose, never a person's. Nothing in a URL names a person: a screen, a date, or a key only.
- **Use of records:** the page repeats CIV 5230(a) (above) on the records card.
- **Each new source is an allowlist.** `owner-rules`, `owner-elections`, and `owner-notices` are built as `owner_meetings` is: copy the named fields from the store; never filter a board loader. Each is added to `ownerScreens.json` and to the poison test with a made-up draft rule, an unnoticed change, a nominee, a ballot count, and a returned-mail follow-up, none of which may come back. Each is in `OWNER_SOURCES` and in no other table.
- **Gates:** `owner-digest`, `theme`, and `community-profile` are open by design (security-and-privacy.md); the new sources answer only in the owner view and refuse with 403 elsewhere unless the board's own loader is also gated at P2.

## Acceptance criteria

1. Every read from an owner screen carries `view=owner`; a source not in `OWNER_SOURCES` answers 403 with the built sentence; a write is refused.
2. The Overview renders the next meeting, latest minutes, rules, elections, disclosures, notices, standards, and the records card in that order, and shows the "Never here" card with `owner_view.CAVEATS` verbatim.
3. The poison test finds none of: a delinquent owner, a unit, a lien, a hearing, an executive item, a draft rule, a nominee, a ballot count, or a returned-mail follow-up, in any owner source's JSON or in the page.
4. A proposed rule change appears only after the ledger shows its notice given, with its notice day, decision day, and 4360(a) and (b) recited before any reading; the reading is a `ReadingLabel`.
5. An adopted rule shows its adoption notice day, and "adoption notice not shown yet" when the ledger has none inside 15 days, as a fact, not a violation.
6. An election with no inspector's report shows dates only and "waiting on the inspector's report"; no count appears.
7. A notice's text is shown as sent, with its sha256, in a block styled apart from a recitation.
8. No owner screen shows a name, unit, balance, or request of any member; the ownerview test passes for every screen in `ownerScreens.json`.
9. At 375 px width nothing scrolls sideways; the banner and "Board view" switch stay reachable.
10. A statute shown is the stored text, checked with `jason verify-quotes`.

## Decisions for the user

1. **Owner accounts.** Today an owner cannot sign in and the owner view is the manager's preview. Do owners get accounts (and which proof: a PayHOA login, an email on the roster of members, a link a person delivers)? Until then, nothing may say "your", and the member's own request, hearing notice, and balance stay in PayHOA and by mail.
2. **Rules source.** Show an adopted rule's text from the governing-documents record or from `rule_changes` only? And is a change shown to members only from the day its notice went out (as specified), or also from the day the board posts the draft?
3. **Comment window.** Show only the statutory span (notice day through the deciding meeting), or also an earlier cutoff once the board adopts one as a policy?
4. **Elections.** Build `owner-elections` only after the election store exists (specified in elections.md), or give the owner view a minimal dates-and-results record now?
5. **Notices given.** Show the text of every general notice, or only the dates and a link? A notice of a rule change and an election carry their statutory words, so those are always shown.
6. **A "what the law gives you" page** (the recited notice, minutes, hearing, and records rights, no data): wanted, or is the annual policy statement enough?
7. **Where a member comments** on a proposed rule: which address, which purpose group, and does the association say it will include the comment in the board's consideration (a policy, shown PROPOSED until adopted)?
