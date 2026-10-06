# Two views of a request: what we ask, and what we do next

Status: design (2026-10-05); build steps 1 and 2 built (2026-10-05): the derivation, the funnel, the act log, `jason followups`, the funnel on `jason campaigns`, the `followups` and `campaign_status` tools, and the `manual` intake channel ([Steps 1 and 2, as built](#steps-1-and-2-as-built) lists the deviations). Steps 3 to 5 are not built. A request to members has two lives, and two people look at it for two reasons. This page designs both views and the record behind the second. It builds on [form-library-design.md](form-library-design.md) (the forms), [arrivals-design.md](arrivals-design.md) (the campaign and the handler), [responses-design.md](responses-design.md) (the inbox), and [notices.md](notices.md) (the delivery follow-ups).

## The two views

**1. Forms and campaigns: what we ask.** The forms the association provides, and each campaign that sent one: which form and version, which handler processes the answers, the cycle's dates, and how many copies went out, came back, were read, were confirmed, and were recorded, **by the way each came in**. It is the view of the thing itself, and it changes when a form or a campaign does. A board member asks it: "What forms do we have, and how is this year's request going?"

**2. Follow-ups: what we do next, and when.** Dated actions, in date order, with the count still outstanding: remind the owners who have not answered, the day answers are due, the day they must be entered in the books, resend a bounced notice by mail, review a returned form, answer a request on its clock. It is the view of the work, and it changes every day. A manager asks it: "What is due this week, and who has not answered?"

The two views read the same stores and never copy one into the other. A campaign's row links to its follow-ups; a follow-up links back to its campaign.

## One intake, many methods

An owner can answer in more than one way, and the outstanding count must not depend on how. The intake methods are the channels of the response inbox: **PayHOA's form**, **an emailed reply** (typed or scanned), **a mailed return** (scanned by the mail service), **a Google Form**, and **keyed from paper by a person** (a form handed in at the office, or read over the phone, which a person types as an arrival with the method named). The count has two parts:

- **Outstanding** is by owner and unit and is channel-agnostic: an owner who has answered by any method is no longer outstanding. The list names who, never what they said.
- **How they answered** is by channel: so many by PayHOA, so many by email, and so on. It says which doors owners use, and so which ones to keep open.

An owner whose every delivery failed (an email that bounced and a letter that came back) is **unreachable**, not outstanding: no ask has reached them, so a reminder cannot. They are listed apart, with the follow-up the law asks (Civil Code 4041(e): resend by mail), until something reaches them.

## The follow-up record

A follow-up is a dated action for a person. jason computes it, shows it, and tracks it; it never carries it out.

| Field | Holds |
|---|---|
| `id` | stable: the same item has the same id on every run, so a person's note on it survives |
| `kind` | `remind`, `return-by`, `enter-by`, `reports-mailed`, `resend`, `acknowledge`, `review`, `decide`, `answer-due`, `close`, `manual` |
| `due` | the date; and for a window, the last day |
| `subject` | a campaign, an owner and unit, an arrival, or a request |
| `what` | the action in a line ("Remind the 41 owners who have not answered") |
| `basis` | **law** (with the citation), **documents** (with the section), **proposed policy** (labeled), or **a person's** note |
| `outstanding` | the count it is about, and the names (units and names, never addresses) |
| `state` | `upcoming`, `due` (today), `overdue`, `done`, `deferred` (to a date, with the reason), `dropped` (with the reason) |
| `by` and `at` | who changed its state, and when |
| `command` | the command a person runs to do it ("jason owner-info --email-batch --follow-up reminder ...") |

**Derived, not entered.** Most follow-ups come from what jason already holds, so there is no second list to keep:

| From | Follow-up | Basis |
|---|---|---|
| A campaign's cycle | the reminder (days before the return-by date that the campaign sets), the return-by date, the day answers must be entered in the books (30 days before the annual reports, 4041(b)(1)), the reports' mailing date | the statute for the entry day; the campaign's own for the rest |
| The notice ledger | a bounced or undelivered email: resend by first-class mail and ask for a working address; a returned letter: ask for a current address | 4041(e), 4040(a)(2); the day counted from is the day the outcome was read, and the number of days is **proposed policy** until the board adopts one |
| The response inbox | an arrival nobody has read, a reading nobody has confirmed, an answer confirmed and not recorded | proposed policy (days to read and confirm) |
| A request on its clock | an acknowledgment, a decision, an answer due, from the form's association clocks | the statute or the documents, else proposed policy |
| The form library | a form stale against an amendment: read the amendment before the next campaign | `jason form-library --check` |
| A person | anything else ("call the printer on Thursday") | the person's |

A person's act on a derived item (`done`, `deferred`, `dropped`) is kept in an append-only log keyed by the item's id, so the next run shows the item with its state and does not make it again.

**Where the law or the documents are silent**, the follow-up carries the proposed policy and says so ("proposed: remind 7 days before"); the board adopts it, and an adopted number moves the item's basis to the board's rule row. jason proposes; the board decides.

## What each view shows

**Forms and campaigns**
- The forms, by tier, with each form's status (ready, adjusted, not offered, or failing: a form stale against an amendment is a failing recitals finding that starts "stale:") and the campaigns that used it.
- Each campaign: form and version, handler, cycle dates, status, and a **funnel**: asked (copies sent, by channel), answered (by channel), read, confirmed, recorded, and outstanding and unreachable. Each count carries its source's age.
- A campaign's copies: the references sent, to whom (units and names), when, and whether each has an answer.
- The commands to open or close a campaign, as commands.

**Follow-ups**
- A date-ordered list: overdue first, then today, this week, later; a filter by campaign and by kind; a count of what is overdue.
- Each item with its basis, its outstanding count, and the command.
- A calendar strip of the next 30 days with the dated actions; the same items appear in the dock's Deadlines.
- The same items can be put on the board's calendar and as tasks for a role (as `jason schedule --tasks --calendar` does for the duties), by a person's yes.

## What must not change

- **jason sends nothing, resends nothing, and completes nothing.** A follow-up is a plan for a person; every send stays a person's `--yes`.
- **No count without its age, and no zero without the time it was true.**
- **Outstanding is by owner, not by channel,** and an owner who answered by any method is not on it.
- **An unreachable owner is never shown as outstanding,** and is never hidden.
- **A policy that is proposed is labeled proposed.** The board's adoption is recorded where jason reads it.
- **No private facts in a list that others see:** names and units, never addresses, never answers; directors see counts.

## Interfaces

- **CLI:** `jason followups` lists (`--campaign`, `--kind`, `--within DAYS`, `--overdue`, `--json`); `--done ID --by NAME [--note]`, `--defer ID --to DATE --by NAME --why`, `--drop ID --by NAME --why`, `--add --date D --text T --by NAME [--campaign C]`. `jason campaigns` shows each campaign's funnel and its next follow-up.
- **MCP** (board profile, disk only): `followups` (the list, with ages and counts) and `campaign_status` (a campaign's funnel by channel, outstanding, unreachable, next action).
- **Console:** the Forms and Campaigns screen and the Follow-ups screen, with the dock's Deadlines carrying the dated items ([console/handoff-followups.md](console/handoff-followups.md)).

## Build order

1. The derivation: `tasks/followups.py` (the items from the campaign, the notice ledger, the inbox, and the clocks), the funnel counts by channel (outstanding, answered, unreachable), the act log, and `jason followups`; the funnel on `jason campaigns`; the MCP tools.
2. The `manual` intake channel (a person keys a paper or phone return, with the method named) and its arrival.
3. The cycle board's per-owner join (asked, delivered, responded, reachable), which the funnel's counts reuse.
4. Putting follow-ups on the board calendar and tasks, by a person's yes.
5. The two console screens and the dock.

## Steps 1 and 2, as built

The items are `jason.tasks.followups`, the funnel is `jason.tasks.campaign_funnel`, the command is `jason.commands.followups` (and a funnel and next follow-up on `jason.commands.campaigns`), the tools are `jason.mcp.followups`, and the manual channel is `Channel.MANUAL` with `response_inbox.add_manual` and `jason responses --add-manual`. Tests: `tests/test_followups.py`, `tests/test_followups_command.py`. What differs from the design above:

- **The funnel is its own module** (`campaign_funnel`), which `followups` and `jason campaigns` both read. It reuses `response_outstanding.outstanding` (narrowed to the campaign's copies and without the unreachable) and the notice ledger. Its counts are `None`, never a bare zero, when a source is missing, and `missing` says why.
- **Answers are the request's.** An arrival is not attributed to a campaign unless it names a copy, so when one request is watched by several campaigns (a form's emailed copies and its mailing) each funnel shows the request's answers and says so in `notes`. "Asked" is the campaign's own copies by the channel each went by (email, mail); "answered" is by the inbox's channels (`payhoa`, `gmail`, `mail`, `forms`, `manual`). A structured arrival (PayHOA, a Google Form) counts as read and confirmed, since its source is its confirmation.
- **Unreachable** is an owner none of whose attempts for the campaign arrived (the ledger's `ARRIVED`: mailed, delivered, opened, forwarded) and at least one of which bounced, failed, was not shown delivered, was never mailed, or came back. An attempt still pending leaves the owner outstanding; an owner who answered is not unreachable. A letter is attributed to a campaign by its mailing's batch, so a returned letter shows on the mailing's campaign, an emailed copy's bounce on the email campaign.
- **The kinds.** A returned letter or a bounced email whose follow-up is to ask the member for an address (the ledger's `ASK_ADDRESS`, `ASK_EMAIL`, a policy) is kind `resend`, its `what` says "ask". `close` (the watch window ends a week past the return-by date) is derived for each open campaign. The form library's "stale against an amendment" item is not derived yet.
- **The numbers are proposed policy** (`followups.PROPOSED_DAYS`): remind 7 days before the return-by date (a campaign sets its own with `jason campaigns --open --option remind-days=N`, which is then a person's setting, not a proposal), resend 3 days and ask 7 days after the outcome was read, read and confirm 3 days and record 7 days after an arrival was kept or its stage reached, close 7 days after the return-by date. There is no profile hook yet to adopt one: that is the rule row the design describes, still open.
- **A ledger item is counted from the day the outcome happened** (the attempt's `status_at`), not the day it was synced, because the sync day moves on every sync and the id would move with it. One item is made for each notice, follow-up, and outcome day.
- **Nothing is marked done by jason.** When nobody is outstanding a reminder says so ("mark this done, or drop it") and stays until a person acts.
- **A campaign the profile's request already runs but whose row is not written** is derived from like a stored one (`campaigns.view`).
- **Item fields beyond the design's:** `cite` (the citation, the section, or whose setting it is), `due_note` (non-empty when the date is a proposed number of days from a recorded day), `reason` (why a count is not known), `campaign`, `source`, `why`, and `deferred_to`. A deferred item is `deferred` until its day, then due or overdue from it. An act on an item that is no longer derived stays in `acts.jsonl` and is not shown.
- **The manual channel** is never checked (`ri.check` and `uses` leave it out; `jason responses` and the tools list it as "keyed by a person (nothing to check)"). A scan is copied to `files/<id>/`; with none, `--read` makes a reading `keyed by a person` with no fields and a person keys each answer at `--confirm --set`. Its answers' source is `manual:<id>`.
- **Not built:** the board calendar and tasks (step 4), the per-owner cycle board (step 3), the console screens (step 5), and a `--state` filter on the command (the tool has one).

## Open decisions

- The board's numbers where the law is silent: days before the return-by date to remind, how soon to resend by mail after a bounce, how soon an arrival is read and confirmed.
- Whether a second reminder after the return-by date is sent, and to whom.
- Whether follow-ups go to the board calendar and Google Tasks by default or only when a person asks.
