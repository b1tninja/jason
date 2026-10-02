# Registers in Google Sheets

A register is a running record that people keep and jason helps fill. Examples are the board's action items, the legal hold's notices and acknowledgments, the approvals set beside their payments, the insurance terms, and the rule changes under Civil Code 4360. This page says where each register lives and how jason and the board share it without overwriting each other.

## Where each kind of record lives

Everything here is built and kept through APIs jason already holds (`spreadsheets`, `drive`, `forms.body`, `forms.responses.readonly`, Google Tasks). Nothing is built by hand.

| Home | What goes there | Why |
|---|---|---|
| **A Sheet (a Table)** | Every register: board action items, the legal hold's custodians and notices, paid against approved, insurance terms, rule changes, minutes status, the board roster | Typed columns, dropdowns, protected key and jason columns, version history; in Drive under the Vault hold and the 5200 record rules |
| **A Google Form** | What a director signs or answers: a legal-hold acknowledgment, a vote by written consent, a records request | Restricted to the association's domain, a response carries the signer's verified email and the time; jason creates the form and moves each response into the register's log |
| **Google Tasks** | A director's open action items on a phone | Already synced: a task checked off closes its item |
| **jason only** (local stores, a restricted Drive folder) | Executive session matters, delinquencies with owners' names, legal case detail, privilege flags, the hold's suspensions, callers' numbers | Never shared beyond what a register needs |

**AppSheet Core is not used.** It is included in the Workspace, but its API is Enterprise Plus only. An app would have to be built and changed by hand in its editor, and it adds nothing a Sheet, a Form, and Tasks do not. AppSheet Databases are also outside Vault and out of reach of the Sheets API.

## How jason and the board share a Sheet

The board action items Sheet today reads the board's columns, then rewrites the whole tab from A1. An edit made in an app between the read and the write is lost. Registers follow these rules instead:

1. **A key column.** Every row has an immutable `id` (jason's key; a row a director adds by hand gets one at the next sync). jason finds rows by key, never by row number.
2. **Owned columns.** Each column belongs to jason or to the board. jason writes only its own columns, row by row (`values.batchUpdate` with one range per changed cell run), and appends new rows. It never writes a board column, and never clears or reorders.
3. **One header row, never moved.** No merged cells. A new column is added at the end. Renaming or reordering a column means regenerating the app's table structure.
4. **Logs are append-only.** Acknowledgments, notices sent, and status changes are rows in a log tab (who, when, what), with the current state on another tab. This is the durable audit, beside the Sheet's version history.
5. **Typed and guarded.** Each register is a Sheets Table: dropdowns from jason's enums, dates as dates, money in dollars and cents with jason converting to integer cents. jason's columns are protected ranges, so a person editing in Sheets cannot overwrite them.
6. **Quota-aware.** The Sheets API allows 60 requests a minute per user. A register sync is one read and one batched write.
7. **Follow-up is jason's.** A register changes when jason syncs; jason's own run does the follow-up: a new lead becomes a board item and a draft, never an email.

A register is a specification row, in the `Community` spec with generic code:
- its title and tabs;
- its columns, each with its owner (jason or board), type, and dropdown values;
- whether it is confidential (director-only sharing, no app);
- its key.

One sync task, `jason registers --sync NAME`, applies the rules above to any register.

## The framework (built October 2, 2026)

- **Spec rows.** A register is a `Register` row (`jason.community.registers`): key, title, records tab, and columns. Each `Column` has an owner (jason or the board), a kind (text, date, number, money, choice, checkbox, link) with its dropdown choices, a width, and a note. Mystique's are in `mystique/registers.py`. The Community hooks are `registers()` and `registers_folder()` ("Registers").
- **`jason registers`** lists the registers and their Sheets. `--create KEY --yes` creates one in the Drive folder "Registers" (made when missing, shared with no one), with its records tab, a `Log` tab, and an `About` tab. `--shape KEY` shapes it again.
- **Shaping** happens once per Sheet: a bold frozen header with each column's owner in its note; widths; a dropdown for a choice column (strict for the board's columns); dates shown as yyyy-mm-dd; money as dollars. A warning-only protection covers each of jason's columns and the header row.
- **Syncing** (`jason.tasks.registers.sync`) works by key:
  - reads the board's non-empty edits, hands them to the register's owner to apply, and logs each as a row in `Log`;
  - writes only jason's changed cells in one `values:batchUpdate`;
  - appends new records;
  - reports rows it does not know.

  It never clears, reorders, or deletes. A renamed or moved column stops the sync with an error.
- **The board action items** are the first register. `jason board --sheet spec` adopted the existing "Mystique Board Action Items" Sheet: it added the Log and About tabs and shaped it. A sync with nothing new writes nothing.

## The registers

| Register | Home | jason writes | The board writes | Notes |
|---|---|---|---|---|
| Board action items | Sheet + Tasks (exist) | title, ask, authority, evidence, priority, category | status, owner, meeting, notes | change the sync to by-key writes |
| Legal hold 26CV016125 | Sheet (directors only) + an acknowledgment Form; scope stays jason-only | the custodians, the notice draft ids, custody checks (counts only) | sent date, acknowledged (the Form's response), suspensions done | confidential: directors only; the scope and privilege flags stay in `data/holds` |
| Paid against approved | Sheet | approvals, linked payments, how linked, outcome | explained (yes/no), board note | a lead, not a finding |
| Insurance terms | Sheet | term, premium, paid, payees, mailing-address findings | renewal decision, agent follow-up | from `jason paid-vs-approved` and the policy readers |
| Rule changes (4360) | Sheet | proposed text link, notice deadline, decision date, adoption deadline | notice sent, comments, adopted, adopted text link | one row per change |
| Minutes status | Sheet | read, gaps, privacy hits, cross-check leads | approved date, correction posted | the AI-summary gaps by meeting |
| Board roster | Sheet | PayHOA tag, last login | office, term start and end | read by the minutes drafter |
| Callers and contacts | jason only | — | — | personal phone numbers stay off Sheets |

## Order of work

1. **The register framework.** The spec rows, the by-key sync with owned columns, Tables and dropdowns, protected ranges, and an append-only log tab. Move the board action items onto it.
2. **The legal hold register.** A directors-only Sheet with Custodians, Notices, and Acknowledgments tabs. An acknowledgment Form restricted to the domain, linked from each notice draft; each response is logged with its signer and time.
3. **Plain Sheets** for paid-against-approved, insurance terms, rule changes, and the roster.
4. **The minutes status register**, once the next minutes are drafted from the sectioned template.
