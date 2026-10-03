# Content style

How the console's words read. jason's CLI already has a voice: short, plain, exact about what it knows and what it does not. The console keeps that voice. Most of the phrases below are jason's own, taken from the task modules the screens render (`onboarding_session`, `notice_record`, `owner_info`, `minutes_draft`, `meeting_watch`, `attention`, `responses`), so the browser and the terminal say the same thing in the same words.

## Voice

- **Plain.** Say what happened and what to do. "Nothing to write. Every owner's tags already match their answers."
- **Short.** One idea to a sentence. A label is a word or two; a message is a sentence or two.
- **Exact.** Say what the record shows, not what it suggests. "No answer this cycle", not "did not answer". "None on record yet", not "missing".
- **No jargon.** Not "sync failed (E_AUTH)", but "jason could not sign in to PayHOA: no Keeper session." A term of art the law uses is fine when the law uses it: "general notice", "executive session", "quorum".
- **No "AI" voice.** jason does not chat, apologize, hedge, or cheer. No "I", "I'm sorry", "Great!", "Let me", "It looks like you're trying to", "Oops". No exclamation marks. No emoji.
- **jason in the third person.** jason names itself as "jason", lowercase, as the CLI does: "jason re-plans before it applies." It never says "I" or "we". "We" is the association only in text written for owners (an acknowledgment draft), never in the console's own words.
- **Active, with the actor named.** "Jane Example approved 8 changes." "jason planned 10 writes." Not "8 changes were approved."
- **Sentence case** for headings, buttons, and labels. "Plan the cycle's writes", not "Plan The Cycle's Writes".

## Who said it: recited, read, decided

Every screen keeps three kinds of words apart, and labels each. This is the console's form of "recite the rule; label the reading" ([citations.md](../../citations.md)).

| Kind | What it is | Label | Component |
|---|---|---|---|
| **Recited** | A rule's own words, quoted whole from the stored copy: a statute, a governing document's section, a rule row the board adopted | "Recited words", with the citation, the version in force, and the caveat under them | `recitation` |
| **Read** | How someone reads those words | "jason's reading", "The board's reading" (with the date adopted), "Counsel's reading", or "Two readings remain" | `reading-label` |
| **Decided** | A person's or the board's act: an approval, a confirmation, an answer, a board decision recorded in minutes | The person's name and the time; for the board, the meeting and where it is recorded | `person-chip`, the audit timeline |

The rules:
- **Recited comes first.** A reading never appears without the recitation above it on the same screen.
- **Every reading names whose it is.** An unlabeled sentence about what a rule means is a bug.
- **jason's reading says what it is not.** Under each one: "A reading, not legal advice. The words above govern." Where jason's own text uses its phrasing: "jason's reading, not the clause."
- **Nothing jason computes is labeled as decided.** A gate is "jason's reading of the checklist; the board decides what is done." A clock is "computed". A conflict is "noted".
- **jason's summary of a record** sits beside the record's recited words, never in their place (`section_refs`' `jasonsReading` beside `recitedWords`).
- **A caveat is shown, not paraphrased.** "jason's consolidated text, not an official restatement. The recorded instrument governs." The caveat strings in the code are rendered verbatim.

## Set phrases

These phrases carry a precise meaning. Use them as written, and do not use near-synonyms that blur it.

| Say | Means | Do not say |
|---|---|---|
| **Held for the board** | A question of policy no rule answers. jason does not act on it, and approving a plan never approves it. Shown with its board item and next meeting. When a person, not jason's policy, refers an item: **held for the board by Jane Example**, with the reason | "pending", "needs review", "flagged", "blocked" |
| **For a person** / **A person does this** | jason cannot write it; a person enters it in the system itself. "A person enters the mailing address in PayHOA." | "manual step", "action required", "todo" |
| **Confirm with the owner** | Ask the owner before relying on it. A message is its own kind | "verify" |
| **None on record** | jason read the store and did not find it. Not proof it did not happen. Always paired, at least once on the screen, with **"None on record is not none given."** | "missing", "not done", "not given", "failed" |
| **None on record yet** | The same, with the deadline still ahead | "pending" |
| **None on record; the deadline passed** | The same, after the deadline | "late", "missed" |
| **No adoption found** | A change in a document's words for which jason found no adoption in the board's records. "Words changed between v2 and v3 with no adoption found in the board's records." A finding, not a ruling | "unauthorized", "invalid", "illegal" |
| **An adoption on record** | The minutes or a rule-change row show the board adopted it | "approved version" |
| **Proposed, not adopted** | An assignment, clock, or rule jason proposes until the board adopts it. "A proposed clock is a target until the board adopts it." | "default", "standard" |
| **A lead, not a finding** | A source to read, not a conclusion. "Each source is a lead to read, not a ruling." | "match", "answer" |
| **Unavailable** | jason could not read the store. Always with the reason and the command that fills it | "empty", "none", "error" |
| **Nothing needs attention** | The store was read and nothing is owed | "all clear!", "you're all caught up" |
| **Changed since review** | The live state moved after a person reviewed the plan; nothing was written | "conflict", "stale" in user-facing text |
| **Superseded** | A newer plan replaced this one | "expired", "cancelled" |
| **Withdrawn** | A person withdrew it before apply | "deleted", "cancelled" |
| **Test** | A test account, never counted as an owner | "dummy", "fake" |

## Dates and times

- **Prose and tables:** "Oct 3, 2099". Within the current year, a table may drop the year: "Oct 3". Never "10/3", which reads differently to different people.
- **Times:** "Oct 3, 15:02" in the console's own logs and timelines. In text written for owners or the board, a clock time the way the minutes write it: "7:02 PM".
- **Machine form:** `<time datetime="2099-10-03">` on every date, ISO 8601 inside. A stored date is ISO; a displayed date is the form above.
- **Time zone:** the association's. A request's received day is the day in the association's time zone, as `responses` computes it. The audit log is UTC and labeled so.
- **Relative time beside the date, never instead of it:** "5 days left · Oct 8", "Passed 3 days ago · Sep 30". The `deadline-badge` does this.
- **Business days:** say so. "10 business days (weekends skipped, holidays not): the earliest the deadline can fall."
- **Ranges:** "from Sep 2 through Oct 1". Not "Sep 2 – Oct 1", which hides whether the ends count.
- **Ages in queues:** "2 h", "1 d", "3 d" in a table column; "planned 2 hours ago" in a header.

## Amounts

- **Stored in integer cents, shown as dollars.** `6120` shows as "$61.20". The template formats cents; it never does float arithmetic.
- **Always two decimals** in finance and costs: "$1,236.00". A thousands separator always.
- **Negative:** a minus sign, "−$1,587.50". A credit is labeled: "−$40.00 (credit)". No parentheses, which a screen reader does not voice as negative.
- **Estimates say so:** "$8.16 estimated". Who is charged says so: "charged to the association".
- **No cost is stated, not left blank:** "No cost: tag writes and a status change."
- **Counts with units:** "4 letters", "4 pages each", "2 members". Not "4x".

## Names and pronouns

- **Use the person's name, as recorded.** "Approved by Jane Example." An approval names a person, never "admin", "user", or "you" alone.
- **Never "he" or "she".** Repeat the name, or use the role: "the Secretary", "the second person", "the owner". This is the rule jason's minutes draft follows, and its checks flag a line that calls a person he or she.
- **"They" for a person not named:** "The person who answered cannot confirm their own answer."
- **The board is "the board"**, an "it". A director is a person with a name.
- **"You"** only on controls and hints addressed to the person at the screen: "Your full name". Not in status text: "Waiting on a second person", not "You're waiting".
- **Owners in examples are "Owner A", "Owner B".** People in examples have plainly fake names. Units are "Unit 12"; streets are "123 Main St".

## Errors

An error says what did not happen, why, and what to do next. It never blames the person, and never shows a traceback.

| Instead of | Say |
|---|---|
| "Error 500" | "jason could not read the requests: the PayHOA catalog on disk is unreadable. Run `jason sync-catalog`. (Reference 7c2e in the server log.)" |
| "Authentication required" | "jason could not sign in to PayHOA: no Keeper session. Run `jason login` in a terminal, then plan again." |
| "Invalid input" | "Give a reason of a few words for rejecting this change." |
| "Name already used" | "Jordan Example gave this answer, so Jordan Example cannot confirm it. A second person confirms." |
| "Conflict (409)" | "This plan changed since you opened it. Reload to see the new plan." |
| "Forbidden" | "This screen is not open to the treasurer role. Ask the manager if you need it." |
| "Secret detected" | "This looks like a secret: it gives a password. jason keeps no secrets. Put it in Keeper, and answer with the Keeper record's name." |
| "Lock timeout" | "Another job holds the PayHOA lock: Sync notices, started by Jane Example 3 minutes ago. Wait for it, or open it." |

The rules:
- **Say what was kept.** After a refusal: "Nothing was written." After a partial failure: "3 of 5 written; 2 failed. The written ones stay written." Never hide a partial result.
- **The command that fixes it,** copyable, when one exists.
- **Keep what the person typed,** except a refused secret, which is cleared and never stored.
- **One error, in place,** next to the field or the section, tied with `aria-describedby`. A summary at the top of a form when there are several.
- **An uncertain write is named as uncertain:** "The request went out and no answer came back. The next plan's live read will show whether it was written. Do not apply again until then."

## Confirmations and approvals

The words on a button are what the person signs. They say the action, the count, and the name.

| Moment | Copy |
|---|---|
| Submit, some approved | **Approve 8 of 10 changes as Jane Example** |
| Submit, all approved | **Approve all 10 changes as Jane Example** |
| Submit, undecided left | Disabled, with beside it: "Decide 2 more changes to submit." |
| Reject an item | **Reject** opens a reason field: "Why? A few words, for the log." |
| Second person | **Confirm as Casey Sample** (the field starts empty), and the rule above it in words |
| Second person declines | **Decline and send back**, with a reason |
| Apply, reversible | **Apply 8 changes now** |
| Apply, irreversible | "This mails 4 letters and charges the association $8.16. A letter cannot be recalled once it is mailed. Type 4 to apply." Then **Mail 4 letters** |
| Withdraw | **Withdraw this plan**, with a reason |
| Record done | **Record done as Casey Sample** |
| Save an answer | **Save the answer**, with "Answered by" pre-filled |

The rules:
- **No "Are you sure?"** A confirmation restates what will happen, with the numbers.
- **Name what is not included.** Beside the approve bar: "2 held for the board and 1 for a person are not part of this approval."
- **Name the record.** Under the bar: "Your name, the time, and the plan's fingerprint 3f9a02c1d4e7 are recorded. jason re-plans before it applies; if the plan changed, nothing is applied."
- **Say which part cannot be undone,** in the plan, before anyone approves: "Status yes; the owner's email no."
- **After the act, the result in a status message:** "Approved 8 of 10 changes. Submitted as Jane Example." "Applied 8 of 8 writes."

## Empty states

An empty state says what was read, that it holds nothing, and the next useful step. It is never a blank table.

| Situation | Copy |
|---|---|
| Nothing owed | "No open requests. 41 answered in the last 12 months, 37 on time." |
| A plan with nothing to write | "Nothing to write. Every owner's tags already match their answers." |
| No approvals | "No approvals are waiting." |
| A section with nothing urgent | "Nothing needs attention." with the section's summary |
| A store not read yet | "Requests are unavailable: no PayHOA requests on disk. Run `jason sync-catalog`." (unavailable, not empty) |
| A thing not on record | "None on record yet." with "None on record is not none given." |
| A new profile | "jason has no stores for this profile yet. Start with Onboarding." |
| A search with no results | "No library file matches those words. The library holds 1,204 files; 38 wait for a kind." |

## Labels and status words

Status words come from the code, so the console and the CLI agree:
- **Plans:** Planned, In review, Approved, Partially approved, Applying, Applied, Failed, Superseded, Withdrawn (`ApprovalStatus`).
- **Items:** Approvable, Held for the board, For a person, Confirm with the owner (`ItemClass`); Undecided, Approved, Rejected, Held for the board by NAME (`Decision`); Applied, Not applied, Changed since review, Blocked, Failed, Uncertain (`Result`).
- **Urgency:** LEGAL, OVERDUE, due soon, open, noted (`attention.Urgency.label`). LEGAL and OVERDUE are capitals in the code to stand out in a terminal; the console shows them as badges with the word, and may set them in small caps, but keeps the words.
- **Owner status:** `OwnerStatus`'s values, in full in the accessible name.
- **Clock standing:** `meeting_watch.Standing`'s values.
- **Request standing:** `responses._standing`'s values.

Color and icon repeat the word; they never replace it.

## Citations

- **In prose:** "Civil Code 4040(a)(2)", "Declaration § 7.3" in the document's own style (`jason cite` prints it).
- **In badges and table cells:** "CIV 4040(a)(2)".
- **Addresses** in code style: `jason://decl/7.3`, with a copy button.
- **Never invent a citation** for a badge or a hint. A clock shows the citation its row carries.
