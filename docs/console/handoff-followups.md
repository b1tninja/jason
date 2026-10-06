# Handoff: forms and campaigns, and follow-ups

For a design pass on the two views in [followups-design.md](../followups-design.md): **Forms and campaigns** (what we ask, and how it is going, by the way each answer came in) and **Follow-ups** (what we do next, and when, with the count still outstanding). It builds on [handoff-forms-and-arrivals.md](handoff-forms-and-arrivals.md) (arrivals, the cycle board, the forms register), [handoff-form-library.md](handoff-form-library.md) (the form a member sees and the library), and [handoff-responses.md](handoff-responses.md) (one returned form). Read [handoff-reconciliation.md](handoff-reconciliation.md) and its third and fourth cuts first. The component names are proposals; the data shapes follow the design and the build corrects this page.

## The idea in six sentences

A request to members has two lives. The first is the thing itself: a form, sent in a campaign, answered by some owners in some ways. The second is the work around it: the dates the law and the board set, and the owners who have not answered. The two views read the same records and never copy one into the other. The count that matters is who is **still outstanding**, and an owner who answered by any method is not on it; how many answered by each method is a separate fact about which doors owners use. Nothing here sends a reminder, resends a notice, or completes a request: a follow-up is a plan for a person, with the command that does it. Every number says how old its source is.

## Who sees what

| Viewer | Sees |
|---|---|
| A manager, the Secretary, an administrator | both views in full: names (units and names, never addresses or answers) |
| A director | both views with counts and dates; the lists of names are held back |
| An owner | nothing here; their own requests are in the request center ([handoff-form-library.md](handoff-form-library.md)) |

## View 1: Forms and campaigns

```text
+----------------------------------------------------------------------------------------------+
| Forms and campaigns                                                       as of Oct 5, 4:30 PM |
| [ Campaigns 3 ] [ Forms 19 ] [ Closed ]                                                          |
+----------------------------------------------------------------------------------------------+
| Owner information 2027 · form v1 · handler: owner information · answers asked by Oct 23   Open |
|   asked        107 owners   (email 90 · mailed 17 · PayHOA —)                                    |
|   answered      47          (PayHOA 20 · email 18 · mailed scan 7 · Google Form 0 · keyed 2)       |
|   read 3 · confirmed 6 · recorded 38                                                              |
|   outstanding   58 owners   unreachable 2          next: remind Oct 16 · answers due Oct 23     |
+----------------------------------------------------------------------------------------------+
| Request to inspect records · form v2 · handler: response clock                        Not opened |
+----------------------------------------------------------------------------------------------+
```

- **A campaign card** (`CampaignCard`): the form and its version, the handler in plain words, the cycle's dates, its status, and the **funnel** (below). One line says the next action and its date, linked to View 2.
- **The Forms tab** is the register from [handoff-forms-and-arrivals.md](handoff-forms-and-arrivals.md) (`FormRegister`): each form by tier, with a campaign count and "not offered (the missing slot)" where that is so.
- **Opening a campaign** is a command (`jason campaigns --open`), shown as a `TerminalStep`; the screen offers it for a form that is ready and has no open campaign.
- **A campaign opens** to its copies: each reference sent, the unit and owner it went to, when, the channel, and whether it has an answer (`CampaignCopies`). No addresses.

### The funnel (`CampaignFunnel`)

One drawing, used on the card, the campaign page, and the dock. Four stages left to right, each a count and a bar against what was asked:

```text
Asked 107 ──▶ Answered 47 ──▶ Confirmed 44 ──▶ Recorded 38
  by how asked: email 90 · mail 17 · PayHOA —     by how answered: PayHOA 20 · email 18 · mailed scan 7 · keyed 2
Outstanding 58      Unreachable 2 (apart)
```

- **Outstanding** is the headline and is **by owner, whichever way**: it is "asked" minus "answered by any method". It is a number and a list of names (units and names), never a share of channels.
- **By how asked** and **by how answered** are two small breakdowns, each channel a word and a count, never a color alone. They are different questions: an owner emailed a copy may answer on the PayHOA form, and that is one answer.
- **Unreachable** is drawn apart, with its own count and the follow-up the law asks (resend by first-class mail, CIV 4041(e)). It is never counted in outstanding and never hidden; the owners on it are the ones a reminder cannot reach.
- **A channel with nothing** is "—" in a quiet face, not "0", unless it was checked and found empty ("0 as of 2 h ago").
- **Each count carries its age:** the sent-copy catalog, the last check per channel, the delivery sync. A stale source is said on the stage it feeds, not only on hover.
- **States:** a campaign not yet sent (no funnel: "Not opened"); open, none answered; mid-cycle; past return-by with outstanding; complete (all answered or unreachable); closed (the funnel frozen with the date).

## View 2: Follow-ups

```text
+----------------------------------------------------------------------------------------------+
| Follow-ups                                                          2 overdue · 3 this week   |
| [ All ] [ Reminders ] [ Deadlines ] [ Resend ] [ Review ] [ Mine ]        Campaign: [ all v ]   |
+----------------------------------------------------------------------------------------------+
| OVERDUE                                                                                         |
|  ⚑ Oct 3   Resend by mail: 2 notices that bounced                CIV 4041(e)  required   [cmd] |
|            2 owners · the law's resend (no day count: proposed 5 days)                          |
| TODAY                                                                                            |
|  ☑ Oct 5   Read 3 returned forms                                 proposed policy         [cmd] |
| THIS WEEK                                                                                        |
|  ✉ Oct 16  Remind the 58 owners who have not answered            proposed: 7 days before         |
|  ▤ Oct 23  Answers asked by                                      the campaign's date             |
| LATER                                                                                            |
|  ▤ Nov 1   Enter the answers in PayHOA                           CIV 4041(b)(1) · the law        |
|  ▤ Dec 1   Annual reports mailed                                 CIV 5300, 5310                  |
+----------------------------------------------------------------------------------------------+
```

- **Date order, in bands:** overdue, today, this week, later. A band with nothing is not drawn; "Nothing overdue as of 4:30 PM" is said once.
- **A row** (`FollowUpRow`): a kind glyph, the date, the action in a line, the **basis** as a labeled chip (the law with its citation, the documents with the section, the board's rule, **proposed** where the law is silent, or a person's), the outstanding count when there is one, and the command.
- **Basis is always shown.** "Required" (the law's) and "proposed" (not yet the board's) look different at a glance; the colors are not the only mark. A proposed number says so in words ("proposed: 7 days before"), and the board's adoption moves it to "the board's rule".
- **Acts on a row:** done, defer to a date (with a reason), drop (with a reason), each by name; until console writes exist each is a `TerminalStep`. A done row says who and when and stays visible for a day, then goes to the log.
- **Add one:** "call the printer on Thursday" with a date, by name; it appears among the others, labeled "yours".
- **The outstanding count on a row** opens the list of owners it is about (units and names). For a director it is a number only.
- **The calendar strip** (`FollowUpStrip`): the next 30 days as a line of dots by date with the kinds; the same items appear in the dock's Deadlines.
- **Filters:** by campaign, by kind, "mine". The default is everything in the next 14 days plus what is overdue.
- **States:** nothing due ("Nothing due in the next 14 days as of …"); a source not read ("The delivery sync has not run since Oct 2, so bounced notices are not shown": shown on the band, never silent); an item deferred (its new date and reason); an item dropped (the reason).

### What a follow-up never does

It never sends the reminder, never resends the notice, never records the answer, and never marks a request complete. The row's command is what a person runs, and the screen says "A person runs this".

## Intake methods, drawn once

The channels have one set of marks used everywhere (`ChannelMark`, from [handoff-responses.md](handoff-responses.md)): **PayHOA's form**, **email**, **mailed scan**, **Google Form**, and **keyed from paper** (a form handed in or taken by phone, which a person types as an arrival with the method named). A channel in a breakdown is its mark and a word; the order is fixed so a person learns it.

## Components

| Component | On | Job |
|---|---|---|
| `CampaignCard`, `CampaignFunnel`, `CampaignCopies` | View 1 | A campaign, its funnel by how asked and how answered, and its sent copies |
| `OutstandingList` | both | The owners still outstanding, units and names; counts only for a director |
| `UnreachablePanel` | View 1, the dock | Owners no ask has reached, with the follow-up the law asks |
| `FollowUpRow`, `FollowUpBand`, `FollowUpStrip` | View 2 | A dated action, the bands by date, and the 30-day strip |
| `BasisChip` | View 2 | Law (with citation), documents (with section), the board's rule, proposed, or a person's |
| `AgeStamp` | everywhere | "as of Oct 5, 4:30 PM": the time a number was true |

Reuse what is built: `Tabs`, `RegisterGrid`, `Seal`, `Pill`, `Command`/`TerminalStep`, `Confirm`, `Glyph`, `Caveats`, `ChannelMark`, `Recitation`, `HeldRow` (for what a director may not see). No `Stamp`: a follow-up is not a decision.

## Words

| Say | Not |
|---|---|
| Outstanding (has not answered) | Pending, missing |
| Unreachable (no ask has reached them) | Bounced, failed |
| Asked, answered, confirmed, recorded | Sent, completed |
| Answers asked by | Deadline (the association's request date; the law's dates are named for what they are) |
| Proposed: 7 days before | Default, recommended |
| Required (the law) / the board's rule / proposed | Mandatory, optional |
| Keyed from paper | Manual entry |
| A person runs this | Click to send |

## What must not change

- jason sends nothing, resends nothing, and completes nothing from either view.
- Outstanding is by owner, whichever way they answered; an unreachable owner is never counted as outstanding and never hidden.
- No count without its age; no zero without the time it was true; a dash for a source never read.
- A proposed policy is labeled proposed, in words; the board's adoption is shown as the board's.
- Names and units only; never an address or an answer; directors see counts.
- Attention is never color alone; the bands and chips are readable in print.

## Decisions that are the design's

1. Whether the two views are two screens or two tabs of one page, and how the funnel and the next follow-up link to each other.
2. How the funnel draws "by how asked" and "by how answered" so a person never mistakes them for stages.
3. How the bands read on a phone (a single list with sticky band headings, or a week strip first).
4. How a deferred item shows its old and new date without looking overdue.
5. Whether `FollowUpStrip` belongs in the dock only, in the screen only, or both.
6. The glyphs for the follow-up kinds (remind, deadline, resend, review) and for "unreachable" (one meaning per glyph).

## Open (the build's or a person's)

- The console routes (proposed): `GET /api/campaigns`, `/api/campaigns/<code>` (the funnel), `GET /api/followups`, and the acts as writes behind the sign-in guard, recorded by name.
- The numbers where the law is silent (days to remind, to resend by mail, to read and confirm) are the board's to adopt.
- Whether follow-ups go to the board calendar and tasks by default or when a person asks.
