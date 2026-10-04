# The redesign's twelve rethinks, reviewed against the work

The design project's redesign (`templates/redesign/REDESIGN-SPEC.md`, "the clerk's desk") ends with twelve
"rethinks", component changes beyond the look. The design agent wrote them from the screens. It did not have what an
association's manager has to work within: the Davis-Stirling Act, the governing documents, the roster's authority, the
approvals engine, and the rule that jason drafts and records but never decides or sends on its own. This page reads each
rethink against those, and keeps it, corrects it, or holds it. The look itself is built (`ui/src/styles.css`, the
clerk's desk section).

| # | Rethink | Verdict | What changes |
|---|---|---|---|
| 1 | Confirm gains a visible label, summary first | **Keep** (built) | `Confirm` takes `label` |
| 2 | ApproveBar is "Your move" for the signed-in person and shows nothing to anyone else | **Correct** | Never blank; see below |
| 3 | DraftLetter ends with the approval line | **Keep, corrected** | The console's record, not printed text; replies go to the 4035 recipient |
| 4 | ApprovalsInbox groups by whose turn | **Keep, extended** | A board approval waits on a meeting, not a person |
| 5 | DecisionBrief never recommends | **Keep, corrected** | Never recommends, but always states the law's limits on each option |
| 6 | DecisionCard: outcome in the board's word; recused directors count toward quorum, not the vote | **Keep, corrected** | The quorum treatment is the bylaws' rule or counsel's reading, labeled |
| 7 | DataTable `kind: "money"` | **Keep** | Right-aligned, tabular, from cents |
| 8 | RegisterGrid shows who last changed a cell on hover | **Correct** | Not on hover only |
| 9 | AgendaWizard: readiness as a checklist, a session badge only for executive matters | **Keep, corrected** | The badge names the 4935 subject |
| 10 | MeetingStage and HostPanel: three join modes, polls as member input only | **Keep, corrected** | jason never runs a poll; a poll is never a vote or an election |
| 11 | ConsoleShell roles, landing screens, and a role strip | **Correct** | The roles are the roster's; see below |
| 12 | The dock as text in the bar | **Keep** (built) | |

## The corrections

**2. ApproveBar.** "Shows nothing to anyone else" removes the record from the people who need it.
- **What's wrong.** An engine plan names no approver. Any officer with authority decides its items, and a two-person kind needs a second, distinct person who must see what the first signed. Hiding the bar also controls nothing, because the server enforces who may act, not the page.
- **The correction.** "Your move" titles the bar for a person who may act: decide, sign, or be the second person. Everyone else sees the same plan read-only, with one line saying who it waits on ("Waiting on a second person", "Waiting on the treasurer").

**3. The approval line.** It is the console's record of the letter: who drafted it, who approved it and how (for the board, the meeting and who recorded its vote), that jason is automated and officers sign. It is not text added to the mailed letter.
- **Disclosure is a board policy.** Whether letters themselves disclose that jason drafted them is a question the law leaves open. It is a written policy for the board to adopt, not a UI default.
- **Replies go to the designated recipient.** That is the association's designated recipient and address for official communications (Civil Code 4035), which the annual policy statement discloses (5310(a)(1)). jason holds it in `Community.identity()` (the designated recipient, the official address, and the official email), which the onboarding item `official-address` answers. jason-web carries it to each letter as `replyTo`, never stored with the letter. Where the profile has no official address, the line says so and names the onboarding item; it never falls back to another address. The letter body's own return address comes from the letter template, from the same fact.

**4. Whose turn.** Keep it, and finish the thought:
- **A letter whose approver is "the board"** waits on a meeting, not on a person. The board can act only on an item on the posted agenda (Civil Code 4930). So it shows as "Waiting on the board's meeting of DATE", or "Not on an agenda yet".
- **"Approved, not sent"** is the turn of the person who sends. That is a terminal command (`jason mailroom --send --yes`); jason never mails on its own.

**5. DecisionBrief.** "Never recommends" is right: the board decides, in its business judgment. But a brief is not neutral about the law:
- **Each option states its legal limits.** For example: a reserve transfer needs the findings and the repayment plan (5515); a rule change needs member notice (4360); a contract needs whatever bidding the governing documents require. Each is quoted from the stored text with its citation, and any reading is labeled (AGENTS.md, "Recite the rule; label the reading").
- **An option the law rules out says so.** That is a constraint, not a recommendation.

**6. Quorum and recusal.** Recusal is not uniform:
- **What the statute covers.** Civil Code 5350 lists the matters on which an interested director "shall not vote".
- **Quorum comes from the documents.** Whether an interested director counts toward the quorum turns on the bylaws and the Corporations Code.
- **The correction.** The DecisionCard and RollCall should show the quorum rule they apply as the bylaws' provision, quoted, or as counsel's reading, labeled. Today it is a fixed comment citing Corp. Code 7233 and CIV 5350. Where the bylaws are silent and the reading is unsettled, the board asks counsel.

**8. Last changed.** A register is a board record. Who changed a cell, and when, belongs in the row's log, visible on focus and in print, not only on hover. Keyboard and touch users never hover (WCAG 2.2, 1.4.13 and 2.1.1).

**9. Executive matters.** An executive-session badge names the subject that permits it:
- the subjects are litigation, a matter related to the formation of contracts with third parties, member discipline, personnel, and a member's payment plan request (Civil Code 4935(a) and (b), 5665);
- the open minutes note it generally.

An agenda item that is none of these cannot be executive.

**10. Polls.** jason's live-meeting acts are pausing or resuming the recording and posting a caption a person chose, from a terminal (AGENTS.md); it never runs a poll. A poll the host runs is member input, never a vote:
- **Board votes** are the directors' roll call.
- **Elections and member votes** go by secret ballot under Civil Code 5100–5145, never by a poll.

**11. Roles.** The spec's four roles do not match the roster, and two of its landing rules would give the wrong people the wrong powers. The roles are the roster's (`docs/setup.md`, Console sign-in):
- **Officer.** Each office approves what `Officer.approves` names: the president or the secretary records the board's votes, the treasurer approves money items, and a vice president or director approves nothing alone. The role strip counts what *this* person may act on, not a generic "officer".
- **Manager.** The manager of a portfolio, and of this community. Managers prepare briefs, agendas, and letters, so they see Decisions; what they cannot do is record the board's vote. The spec's "everything but Decisions" would stop the manager preparing the board's decisions. Executive-session material follows the data levels ([security-and-privacy.md](security-and-privacy.md)).
- **Admin.** jason's overall administrator. An admin holds no office and approves nothing, so the spec's "administrator approves plans" is wrong. An admin lands on the setup and status screens (sign-in, sources, sync health), sees what is waiting on anyone read-only, and under `--dev` may view as any role.
- **Owner.** A view, not a sign-in, until the board decides on owner accounts; owners use PayHOA's portal. The owner view shows what a member is entitled to:
  - open-session meetings and minutes (4925, 4950);
  - the annual disclosures, including the budget report and reserve summary (5300) and the insurance summary (5300(b)(9));
  - the records request form and what the board has produced under it (5200–5215). It is not the document library, because some records are withheld (5215).

  No delinquency, discipline, or another owner's facts.

## The plan from here

1. **In progress:** 4 (whose turn) and 3 (the approval line), as corrected above.
2. **Next:**
   - 2, as corrected;
   - 11, the roles from the roster and the role strip. It needs the server to say the signed-in person's role and what they may act on (`/api/session`), and each screen to declare its roles.
3. **Then:**
   - 5 and 6, the law's limits on options and the quorum rule quoted, which need the governing documents' text;
   - 8, the last-change log;
   - 9, the executive-session subject;
   - 10, the poll wording.
4. **Already done:** 1, 7 (in part), and 12.

The design project should hear the corrections, so its next round starts from them. That can be a `DOMAIN-REVIEW.md` beside `REDESIGN-SPEC.md` in `templates/redesign/`, written there only with the person's approval.
