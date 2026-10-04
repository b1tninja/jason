# Mail: triage, the Inbox's letters, and insurance letters

## In the console

Built screens, each showing its documents with `Doc` ([doc-component.md](../doc-component.md)):
- **Mail triage** (`#/mail-triage`, `MailTriageView`): the mail brief's lanes (act, review, not scanned), each letter with a person's recorded choice (scan, forward, shred, discard, keep).
- **Inbox** (`#/inbox`, `InboxView`): the letters to act on and the PayHOA requests pending, among everything waiting on the association.
- **Insurance** (`#/insurance`, `InsuranceView`) and **renewals** (`#/renewals`, `InsuranceRenewalsView`): each policy against what PayHOA paid and what the mail says, with the notices and the claims the mail acknowledges. The owner view of `#/insurance` is the insurance summary (CIV 5300(b)(9)) from its own loader (`insurance?view=owner`): each policy's kind, carrier, term, and deductible when the profile records it; no policy number, premium, standing, letter, notice, finding, or claim.

This spec names the documents those screens show and how. It adds no screen.

## Purpose and personas

The manager (M) and the Secretary (S) read a letter before choosing what the mail service does with it, and before acting on a deadline it states. A director (D) or the Treasurer (T) reads an insurer's notice beside the renewal decision.

## Data

Each letter carries its document as a `DocRef`, built by `jason.tasks.mail.scan_ref` with `jason.approvals.docref.file_ref`:
- a scanned letter: `file:mail/<mail id>/contents.pdf`, kind `pdf`;
- a letter not scanned: its envelope, `file:mail/<mail id>/cover.jpg`, kind `image`;
- neither on disk: the reference still names the file, and `Doc` says "Not on disk".

`mail/` is P2 (`access.PATH_RULES`), so the source is "Scan" and the level P2.

| Screen | Loader | Field | Document |
|---|---|---|---|
| Mail triage | `jason.web.extra.mail_triage` (over `mail_brief`) | each lane row's `scan` | The letter's scan, else its envelope |
| Inbox, letters to act on | `jason.tasks.party.open_items` | `lettersToAct[].scan` | The letter's scan |
| Inbox, requests pending | `jason.tasks.party.open_items` | `requestsPending[].doc` | The request's submission, `payhoa:submission:<n>` (`submission_ref`), the same evidence the plans carry |
| Insurance, renewals | `jason.tasks.insurance.review` | `policies[].letters[].scan` (so each notice's), `claims[].scan` | The notice's or claim letter's scan |

The old fields (`mailId`, `folder`, `scanned`, `id`, `form`) stay beside the references.

The Inbox's email threads stay links to Gmail, said as "Open in Gmail", until Gmail messages have a resolver (`gmail:`, a later step in [doc-component.md](../doc-component.md#building-it)).

## Documents and their variants

| Where | Variant | Why |
|---|---|---|
| Mail triage, each letter | `row` | A list of letters, each with View |
| Mail triage, the letter being read | `inline`, beside the five choices | The letter is the subject while a person chooses. P2: "Show the document" first, then one logged view |
| Inbox, letters to act on (Letter column) | `chip` | A table cell |
| Inbox, requests pending (Request column) | `chip` | A table cell |
| Insurance, "Notices in the mail" under the policies | `row` (`DocList`), each scan once | A letter that prints two policies' numbers is one scan |
| Insurance, "Claim letters" under the claims | `row` (`DocList`) | A list of letters |
| Renewals, the opened policy's "On the record" | `row` (`DocList`) | The notices beside the board's decision |

## Actions

- **Read it beside the choices** (mail triage) opens the selected letter inline; one letter at a time. "Close the letter" closes it. Nothing is viewed until "Show the document".
- **View**, a chip's click, and **Show the document** are each one `POST /api/evidence/view`, logged under the signed-in person.
- Nothing here asks PostScanMail to scan, forward, shred, or discard. A recorded choice is for the person who acts at the mail service.

## States

`Doc`'s own ([doc-component.md](../doc-component.md#states)): signed out ("Sign in with Google to open this", or "Sign in with Google to view it." on a list), not allowed (the server's sentence), not on disk, and an error in the server's words.

## Privacy

A scanned letter is P2: it can carry a sender's or owner's name, an address, an account number. Its reference carries the name masked and no contents; the scan is shown only on a person's click, signed in, logged. A letter jason sorts as carrying a credential, or another association's misdirected mail, is still P2 by its folder. Whether such a letter should be held higher is open: the level comes from `access.PATH_RULES`, which places by path, not by the letter's sort.

## Acceptance criteria

1. Each screen's tests render the variant from a static reference, post one view on opening, and say the signed-out and not-allowed words (`ui/src/views/mailtriage.test.tsx`, `ui/src/views/maildocs.test.tsx`).
2. No screen renders an `/api/file` href, an iframe of another host, or an absolute path.
3. Each loader's references resolve (`resolve(address)["found"]`) on a made-up data folder (`tests/test_mail_docrefs.py`).
