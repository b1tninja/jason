# Legal holds

A legal hold keeps what the association must preserve for a matter. The duty starts when litigation is pending or reasonably anticipated, not when a hold is written down. No rule requires a particular tool; the standard is reasonable, good-faith, proportionate steps, documented (*Cedars-Sinai Medical Center v. Superior Court* (1998) 18 Cal.4th 1; Evid. Code 413; Code Civ. Proc. 2031.060(i)(2); The Sedona Conference, *Commentary on Legal Holds*, 2d ed. 2019). Defense counsel directs the hold and releases it in writing. This is research, not legal advice.

## The hold

A hold is a `LegalHoldSpec` row in `mystique/holds.py`. It gives:
- the matter;
- the day the duty arose, and the earliest records in scope;
- the Workspace accounts Vault holds;
- the words that put a mail, file, or meeting in scope;
- the Drive folders held whole;
- who gets a written notice;
- what lies outside Vault;
- the rules suspended while the hold stands;
- counsel, and who keeps the register.

The duty often begins with a preservation letter, and the hold can reach records from before that day, back to the first notices about the same matter.

Mystique's findings are in the private notes (mystique/notes/legal-hold.md).

## `jason hold`

- **`jason hold`** builds the register, `data/holds/<key>/register.json`:
  - the scope, with why each item is in it: the held folder and the files named with a term, the Zoom meetings whose transcripts carry a term (what Zoom's cloud holds, jason's copies, and that day's Drive recordings), matching mail subjects and their attachments, and matching photo albums;
  - a SHA-256 for each local copy, and which copies changed since the last scope;
  - the Vault ids, the labels, the notices, the suspensions, and the custody checks. A rebuild keeps these.
- **`--vault [--yes]`** plans, then creates, the Vault matter and two holds: the custodians' whole Drive, and their Mail matching the terms since the start date.
- **`--label [--yes]`** sets `jason_hold` on each held Drive file. It is the one appProperty `jason drive-labels` never writes.
- **`--watch [--since DATE]`** reads Drive Activity and reports which held files were deleted, moved, renamed, or re-shared since the duty arose, and by whom. It changes nothing.

- **`--notices [--yes]`** previews, then saves as Gmail drafts, the written hold notices and the note to counsel. The drafts are never sent.
  - There is one notice per role in `notice_to`, with the recipients left for a person to fill in.
  - Each notice is marked confidential as an executive-session matter (Civil Code 4935(a)). It says the board has already discussed the matter (`board_discussed`), so it puts that direction in writing rather than announcing news.
  - The custodian gets no letter; their duties are the register's checklist.
  - The note to counsel, addressed to `counsel_attention`, describes the method and asks for written approval.
  - Each draft id is recorded in the register. Record the sent and acknowledged dates yourself.

jason never releases a hold, closes a matter, or deletes anything.

## Privilege and record labels

Each held item carries a likely privilege, a lead for counsel's review and never the determination (`jason.community.privilege`; parties and names in `mystique/privilege.py`). The call comes from the email parties the item came from or went to: the Drive-to-Gmail links, and the subject of an email printed to PDF. It also uses the item's name.

- **Attorney-client** (Evid. Code 954): a communication with the association's counsel (their domains are in `mystique/privilege.py`).
- **Work product** (CCP 2018.030): a communication from counsel that is counsel's analysis.
- **Insurer-defense**: a communication with the carrier or claims administrator (also named by domain in `mystique/privilege.py`). It may share the privilege when made for the defense (*Soltani-Rastegar* (1989) 208 Cal.App.3d 424).
- **Sent through counsel**: a document that already existed (medical records and bills, vet invoices, photos) and reached the association through counsel or the carrier. The forwarding email may be privileged; the document itself is privileged only if counsel made it.
- **Not privileged**:
  - anything exchanged with the plaintiff's counsel;
  - court filings and the court's public record;
  - the demand and the preservation letter;
  - the association's own violation and hearing letters to the owner;
  - the broker's and outside parties' letters.
- **Review**: a request for defense or coverage, or a meeting or hearing record. A recording or transcript is confidential where it is an executive session (Civil Code 4935), and privileged only where counsel advised.
- **None found**: no counsel, insurer, or telling name. This does not mean "not privileged".

A medical record is also marked `medical`.

`jason hold --label --yes` writes two appProperties on each held Drive file:
- `jason_hold` (the hold's key);
- `jason_privilege` (for example `sent through counsel: via counsel.example; review; medical`).

It then writes jason's ordinary labels on the same files through `jason drive-labels`: kind, the Civil Code 5200 record (`jason_records`), meetings, item, and topics. `jason drive-labels --search jason_hold=<key>` lists the held files.

## Outside Vault

Vault holds Workspace accounts only, and only from the moment a hold is set. It cannot bring back anything deleted before. These sources are kept by written notice and export:
- directors' personal email and text messages;
- the treasurer's personal Google Photos (Google Takeout, with its JSON metadata);
- Zoom cloud recordings, transcripts, chats, and AI summaries: turn off auto-delete, keep the trash on, and download the originals;
- copies on personal devices.

Record each notice (sent and acknowledged) and each suspension in the register:
- the Decorum Rules' recording deletion;
- Zoom auto-delete;
- emptying trash;
- removing a custodian's account.

Never use "Make a copy" to preserve a Drive file. It makes a new file, with a new owner and date and no history.
