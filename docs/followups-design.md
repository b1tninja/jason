# Two views of a request: what we ask, and what we do next

Status: design (2026-10-05). A request to members has two lives, and two people look at it for two reasons. This page designs both views and the record behind the second. It builds on [form-library-design.md](form-library-design.md) (the forms), [arrivals-design.md](arrivals-design.md) (the campaign and the handler), [responses-design.md](responses-design.md) (the inbox), and [notices.md](notices.md) (the delivery follow-ups).

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
- The forms, by tier, with each form's status (ready, not offered, stale) and the campaigns that used it.
- Each campaign: form and version, handler, cycle dates, status, and a **funnel**: asked (copies sent, by channel), answered (by channel), read, confirmed, recorded, and outstanding and unreachable. Each count carries its source's age.
- A campaign's copies: the references sent, to whom (units and names), when, and whether each has an answer.
- The commands to open or close a campaign, as commands.

**Follow-ups**
- A date-ordered list: overdue first, then today, this week, later; a filter by campaign, by kind, by who; a count of what is overdue.
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

## Open decisions

- The board's numbers where the law is silent: days before the return-by date to remind, how soon to resend by mail after a bounce, how soon an arrival is read and confirmed.
- Whether a second reminder after the return-by date is sent, and to whom.
- Whether follow-ups go to the board calendar and Google Tasks by default or only when a person asks.
