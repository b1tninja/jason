# Meeting records

`jason meetings` catalogs every record of every meeting the association holds, wherever it is held, and checks each meeting. MCP: `meeting_records`.

## Sources

| Source | What it gives | Refreshed by |
|---|---|---|
| Zoom's cloud | what Zoom still holds per meeting: audio (M4A), video (MP4), transcript, chat, AI summary | `jason zoom` (or `jason meetings --sync`) |
| jason's copy, `data/zoom` | the transcripts, chats, AI summaries, and attendance jason downloaded | `jason zoom` |
| Drive | agendas, notices, minutes (Docs and PDFs), transcripts, recordings saved from Zoom | `jason drive --sync` |
| PayHOA library | the posted agendas, minutes, and executive session agendas | `jason library --fetch` |
| PayHOA communications | each meeting notice PayHOA sent to members, one row per mailing: when, how many recipients, and how many were delivered, opened, bounced, or failed; no member's name or address is kept | `jason meetings --sync` |
| Gmail (headers and attachments) | PayHOA's copy of each notice; Zoom's recording, asset, and AI summary emails; replies about an agenda; agenda and minutes attachments | `jason gmail --sync` |
| jason's drafts, `data/board` | the next agenda and minutes template | `jason board --agenda` |

The catalog only reads what is on disk. It moves, copies, and deletes nothing. The output is:
- the catalog, `data/meetings/catalog.json`;
- the report, `data/reports/meetings.md`.

## How a file is placed

**What a file is.** The specification's `RECORD_RULES` (`mystique/meetings.py`) name each file by its name, in order:
1. executive session agenda;
2. transcript;
3. chat;
4. AI summary;
5. video;
6. audio;
7. draft minutes;
8. minutes;
9. agenda;
10. meeting notice.

Audio and video count only when the name or path says meeting, minutes, recording, or Zoom. The phone videos in a violation folder are evidence, not meetings. The bylaws' audio book is excluded.

**Which meeting.** The date comes from the name: `6_17_25`, `9/15/26`, `2022.05.11`, `26-02-17`, `230130`, `083022`, "Apr 14, 2026", "2024 Annual Membership Meeting". Zoom's `GMT20250521-015946` names are in UTC, so that file is the May 20 evening meeting in Sacramento. A file with no readable date is listed as unplaced.

**Emails.** An email is placed by the specification's `EMAIL_RULES`, which look at the subject and the sender's domain. Its meeting date comes from the subject, and a date without a year ("Sep 15th at 7:00 pm") takes the year nearest to when the email was sent. Zoom's emails are dated the evening they arrive.

**One document, many copies.** A file in two places with the same bytes is one document. Drive's listing gives an MD5, Gmail and the library give a SHA-256, and `Digests` (`jason/tasks/digests.py`, cached in `data/digests.json`) computes both for any file on disk. Each meeting lists its `sameFile` groups, such as an agenda PDF in the library that is also a Gmail attachment. A Google Doc and its PDF export have different bytes, so they are joined by kind and date only.

## The checks

- **Notice.** When PayHOA's mailing (or its Gmail copy) went out, against the meeting:
  - **Timing.** Fewer than four days ahead is flagged (CIV 4920(a); two days for a meeting held solely in executive session).
  - **No notice.** A meeting since the log's first mailing with no notice at all is flagged.
  - **Failed delivery.** A mailing that failed or bounced for some members is flagged. Email is notice only to members who chose it (4040, 4041); the rest rely on a posting the annual policy statement designates (4045(a)(3), (5)).

- **Minutes missing.** No minutes, or only a draft, 30 days after the meeting. Members must be able to get the minutes, a draft, or a summary within 30 days (CIV 4950(a)). "Not found" means not found in these places.
- **Recordings kept.** A recording is still held after the minutes, and the report says where. The Decorum Rules say the Secretary's recording is deleted once the minutes are prepared.
- **Where the executive session starts.** The board adjourns to executive session on the same Zoom call, and the members leave. jason finds the break in the transcript. It is the chair's adjournment line, not a passing mention ("we'll talk about that in executive session"). The phrasings the transcripts use are `EXECUTIVE_BREAK_PATTERNS` in `mystique/zoom.py`: "adjourn to the executive session", "adjourn the regular portion", "adjourn the meeting … board members stick around", "if you're not a board member, I'll kick you out", and "open forum … the board we can meet at the end".
  - **Departures confirm it.** The attendance list shows who left from a minute before the break to ten minutes after, and who stayed.
  - **Departures alone.** With no adjournment line, the break is where people left while at least two stayed on and talked for three more minutes.
  - **How it is read.** `zoom_meeting` gives the open portion, through the adjournment line, and holds back the rest. It also holds back Zoom's AI summary and the chat, which cover the whole call.
  - **No break found.** A transcript that mentions an executive session or a hearing but shows no break is held back whole.
- **AI recap in posted minutes.** Posted minutes that carry Zoom's AI recap ("Quick recap", "Next steps") and name executive-session subjects:
  - discipline, hearings, and fines;
  - delinquencies, collections, liens, and foreclosure;
  - lawsuits, attorneys, and counsel.

  The open minutes note executive session matters only generally (CIV 4935(e)). The check also says when a copy is in PayHOA's Resale Documents, which go to buyers.
- **Schedule gaps.** A monthly meeting day since the January 2023 resolution with no record within ten days. Months the resolution did not make regular are labeled.

## Recordings, transcripts, and summaries

What the law says:
- **No duty to keep them.** No statute requires keeping recordings, transcripts, or AI summaries, and none is listed as an association record (CIV 5200(a)).
- **Minutes are permanent.** Approved minutes are kept permanently (5210).
- **Transcripts fall under the rule too.** A transcript is the recording in text, so the Decorum Rule's purpose reaches it.
- **Keeping executive-session text is a risk.** It is exposed to:
  - discovery in a lawsuit;
  - loss of attorney-client privilege for what counsel said;
  - a director's inspection demand (Corp 8334), even where members can be refused (5215(a)(5)).
- **A pending lawsuit comes first.** A suit requires preserving anything about its matter. Deleting it then could be spoliation (*Cedars-Sinai Medical Center v. Superior Court* (1998) 18 Cal.4th 1; Evid. Code 413).
- **A pending bill could change this.** AB 1184 (2026), if enacted, would make open-session recordings association records unless they are kept solely to prepare minutes.

This association's findings are in its private notes (mystique/notes/meetings.md).

jason keeps its copies in `data/zoom`, and they are subject to the same policy and any hold. jason deletes nothing.

## Files the agendas link to

The board's agenda Docs attach each item's papers as smart chips, such as a Drive file, a folder, a Doc, a Sheet, or a Slides deck. They also use hyperlinks: Google Photos albums of a repair, a statute, the court's case page, a vendor's page. `jason meetings --links` reads each agenda Doc in the Drive listing, read-only. It keeps the Docs in `data/meetings/agenda-docs`, and on later runs re-reads only a Doc Drive shows as changed; `--offline-links` rebuilds from what is kept. It also reads the link annotations of the agenda PDFs on disk. A PDF exported from a Doc takes the Doc's item for the same link.

`data/meetings/agenda-links.json` holds two views:
- **By meeting:** each agenda's links under their items and sub-items. `jason meetings --date` and the MCP `meeting_records(date=...)` show them.
- **By file:** each linked target. `jason meetings --file X` and `meeting_records(file=...)` show it with:
  - every meeting and item that used it, newest first;
  - the topics those labels name (`topic_rules`);
  - the document kind its name suggests (`classify_document`);
  - its Drive path, or that it is not in the Drive listing (shared from another account, trashed, or never in this Drive).

The link kinds are the specification's `LINK_RULES` (`mystique/meetings.py`); the Zoom link on every agenda labels nothing. A label says where the board used a file: it is a lead for filing and classifying it, not a classification. A Google Photos album is known only by its link and its labels; jason does not read the album. Nothing is moved, renamed, or shared.

This association's findings are in its private notes (mystique/notes/meetings.md).

## Agenda items and their documents

`jason meetings --items` reads each agenda Doc into its items and sub-items, each with its notes and links (`items_in_doc`). It relates documents to each item three ways, strongest first:
- **linked**: the item's chip resolves to a Drive file;
- **named**: the item's words name a file ("[Proposal 1234-1.pdf]") or a numbered document ("estimate 000123", "claim AZ000001"), and a Drive, library, or Gmail file carries it in its name (`mentions`);
- **received**: a Gmail attachment whose kind the item brings, received in the 45 days before the meeting, sharing a distinctive word with the item. This is a candidate, not a join.

Each item brings document kinds by its title (`AGENDA_ITEM_RULES` in `mystique/meetings.py`): the treasurer's report brings reports and statements, and a claim brings the adjuster's letters, estimates, police report, and photos. A related document's kind by the library's name rules either **agrees** with what the item brings or **differs** from it. When the name rules say nothing, the item **suggests** a kind.

`hints` in `data/meetings/agenda-items.json` gathers, per document, every item that used it and the kinds they suggest. These are leads for the classifier, recorded with their evidence, never the classification.

`jason meetings --date D` includes each item with its related documents.

### Kinds from agenda items: a classification method

`jason meetings --items` also resolves the hints into kinds (`jason.tasks.agenda_kinds`, `data/meetings/agenda-kinds.json`). A kind is recorded, with the method "agenda item that used the file" (`Method.AGENDA` in the library chain, after the phrase rules and before the local model), only when the evidence holds one of two ways:
- **Agenda item and text.** The items narrow the kinds, and a phrase rule over the file's own words picks one of them. A Drive file's words are read from a byte-identical copy on disk: its MD5 matches a Gmail attachment or a PayHOA library file (`Digests`).
- **Every use agrees.** Two or more agenda items used the file, and every one brings the same single kind. One use is where the board put the file once, not what it is.

Anything less stays a suggestion, with its evidence. When a name rule names one kind and an agenda uses the file as another, the name rule stands and the pair is listed as a conflict for a person. A conflict can be a finding in its own right, such as an "Approval of minutes" item that links the prior meeting's agenda instead of its minutes. The library's classification and jason's Drive labels (`jason_kind`) read the recorded kinds.

`--fetch-items` reads the undecided Drive files: a PDF is downloaded, and a Google Doc exported as PDF, into `data/meetings/agenda-files`; nothing in Drive changes. A fetched scan with no text layer is read locally, the text written beside it as `<id>.pdf.md` by `jason.community.ocr.ocr_folder`: by `glm-ocr` through Ollama, else by Tesseract when the vision model times out.

The resolver reads that text. When a file's words match none of the item's kinds, the phrase rules try every kind, with the method "phrase rule over the agenda file's text" and confidence 0.7. That fallback counts only a title's words, and never for an email or letter, since a communication quotes other documents' titles.

Phrase rules taken from the wording of the files left as suggestions (in `jason.community.content`, which the library's own chain uses too) cover:
- counsel's letters marked "client privileged communication";
- engagement letters ("confirm our acceptance and understanding");
- owners' parking permit and home improvement applications;
- a city nuisance-alarm notice and a members' maintenance notice;
- invoices that say "make checks payable to".

A letter's own kind (counsel's letter, an engagement letter, a notice) counts from its title even though the fallback otherwise skips letters.

This association's findings are in its private notes (mystique/notes/meetings.md).

## Cross-checks between agendas and minutes

`jason cross-checks` (`jason.tasks.cross_checks`) sets what each agenda item linked beside what the minutes of that meeting recorded. It reads only what is on disk: the agenda items, the agenda-file kinds and text, the minutes readings (`jason models`) with the model's grounded answers, the meeting catalog, and the Drive and library listings. Two agenda Docs for one date are one agenda. The result is `data/meetings/cross-checks.json`. Every result carries its evidence (file names, ids, quotes) and is a lead for a person, never a finding.

A decision is an action the minutes reading recorded, a minutes item whose notes state an outcome (approved, tabled, denied), or an amount the model answered with a quote found in the text. A decision is about a document when one of these holds:
- the minutes item attaches the document;
- the same amount appears in both, to the dollar;
- two words are shared, one of them from the document's name;
- one rare word of the name is shared (used by three decisions or fewer).

Common words, the minutes' verbs, and the street names never count.

The four checks:
- **Amounts.** Each proposal, estimate, contract, or invoice an item linked, beside its decisions. The document's amount is a total line of its own text: a grand total first, then an amount due, then a named total, then a bare total; a subtotal never counts. The outcome is **matches**, **differs** (both amounts shown), **decided, no amounts to compare**, **tabled or denied**, or **linked, but no decision recorded**. A copy of the same document ("Proposal 1234-1 (2) - signed.pdf") shares its copies' decisions. An approval with an amount that no linked file matches is **approved without a linked document**; fines, prizes, dues, the budget, and reserve investments are not spending on a document.
- **Prior minutes.** The "Minutes of M/D/YY" an approval item names, from its notes and link names. The check reports a link that opens an agenda, a name with no link, minutes of that meeting not held anywhere, and minutes an earlier agenda already listed. It also reports minutes this meeting's reading does not record approving, and a board meeting whose minutes are held but no agenda listed.
- **Insurance renewals.** An item that brings a renewal names its term ("25-26") and lines of coverage (flood, umbrella, fidelity, D&O, the master package). Lines come from the coverage words, then the specification's policy numbers, then its program names. The check says whether the minutes record a decision, and whether a policy or certificate for each line and the new term is on file afterward (Drive, the PayHOA library, or a policy reading's term). A renewal letter, proposal, or invoice is not the policy.
- **Stale items.** An item title, a short note heading, or a document carried on three or more consecutive board agendas with no approval or denial in those meetings' minutes. Standing items (minutes, the treasurer's report, maintenance, open forum, executive session) are left out. A run whose minutes were not read is listed after the rest.

`--ask-model` asks the local model one grounded question for up to `--max-questions` documents with an amount and no matched decision. The question holds the GPU lock and runs the preflight first. Its answer counts only when its quote is in the minutes text, and it never changes the outcome.

This association's findings are in its private notes (mystique/notes/meetings.md).

Minutes not read are not minutes not written. The AI-summary minutes of 2025 and 2026 tell of decisions in their own words, so a miss can be a decision worded differently.

## Reading links from Docs and PDFs

The agendas are Google Docs; the PDFs in PayHOA and Gmail are their exports. Links come from both, and each link keeps the item it sits under.

**Docs (`links_in_doc`).** The parser reads every tab and child tab, and each of these parts:
- **Body and tables:** the items' own links.
- **Headers and footers:** each Doc's Zoom link and calendar-event chip, which belong to the whole meeting, not an item.
- **Footnotes:** a footnote's link takes the item where the footnote is referenced (the Nahrstedt and Bernardo Villas citations).

Four details matter:
- **Split links:** a link Docs splits over several text runs ("A", "genda") is one link.
- **Internal links:** a link to a heading in the same Doc is an internal cross-reference, recorded on the item as `refersTo`. The officers' election items point to Bylaws 10.8 through 10.11.
- **Typed URLs:** a URL typed as plain text counts as a link.
- **Levels:** date chips are part of an item's text. Level 4 is an item; levels 5 and 6 are sub-items.

**PDFs (`links_in_pdf`, PyMuPDF).** Each link keeps the words under its rectangle and its page. It is placed under the heading above it:
- **Numbered agendas:** the items are the lines numbered "I.", "II.", or "1.", in the number's own style. Lines numbered "i." or "a." are sub-items.
- **Unnumbered documents:** the heading style used most is the item. A larger style is the title block, and any other heading style is a sub-item.
- **Never headings:** the running header and footer (a line repeated on pages at the same height), a "See:" line, and a line that is only a link's words (a chip's title set bold).
- **Other links:** a link to another page is internal. A URL typed in the text is found as in a Doc.

Where the PDF's item and the Doc's differ, it is mostly the Docs themselves: a Doc can set sub-items as level-4 headings, which the PDF's numbering shows as sub-items. This association's findings are in its private notes (mystique/notes/meetings.md).

## Minutes read from Drive

The library may hold the minutes of only some meetings. `jason.tasks.drive_minutes.run` reads the rest from Drive:
- **One copy per meeting.** For each meeting whose minutes no reading covers, it takes one Drive copy: the Google Doc, which is the original, else the PDF.
- **Read only.** A PDF is downloaded and a Doc exported as PDF into `data/meetings/minutes-files/`, with the text beside it. Nothing in Drive changes.
- **The minutes model reads it.** The reading goes into `data/documents/readings.json` with `"source": "Drive"` and the id `drive-<id>`, where the minutes questions, the cross-checks, and `text_for` find it. A library run keeps these readings.
- **Confidential.** Executive session minutes are marked confidential.

The minutes model reads these layouts:
- **Titles.** "Regular Board of Director's meeting", "Board of Directors Open Meeting", and "Board Meeting Minutes" are titles. The meeting's kind comes from the title's first word.
- **Outcomes in item titles.** An item titled "... - Approved - $5,427.00" or "... - Tabled" is a decision. So is the manager's "Motion to approve ... - M/S/P". The board secretary's "MSC" is not read: those minutes put it on items with no motion.
- **Rosters.** A "Board Members:" block of "Name, Office" lines is read, and "(Absent)" marks an absent director.
- **Dates.** The closing certification's "held on" date is skipped. The manager's template left a stale year in it.
- **Hand-typed minutes.** "Only one Board member present" means no quorum. An adjournment time without am or pm is read.
- **Emergency meeting by email.** This is a new `written_consent` layout. Each item after the consent is an action. Each director's e-signature and its date is kept. The finding cites Civil Code 4910(b)(2): every director must consent in writing.

An uploaded Word file saved under a `.pdf` name is read as the .docx its bytes are.

Open minutes that name a member's payment plan are a finding: a payment plan is executive-session business (Civil Code 4935(a)).

This association's findings are in its private notes (mystique/notes/meetings.md).

## Paid against approved

`jason paid-vs-approved` follows each approval in the minutes to the payments that answered it (`jason.tasks.paid_vs_approved`, `data/meetings/paid-vs-approved.json`).

**Approvals** are of two kinds:
- the rule reader's approved decisions with an amount of $500 or more;
- the model's grounded answers to "each dollar amount the board approved", which catch an amount stated apart from the approval ("approves the tree pruning plan" … "$9,871").

Investments, reserve loans, delinquencies, fines, deductibles, and rejected offers are left out.

**A payment answers an approval** from the invoice review in one of three ways:
- its invoice cites the approval's proposal number;
- the approval names the payee, and it was paid within nine months;
- it is the one payment of the approved amount (within 1%) in that window.

**The leads:**
- paid more than approved;
- approved, nothing paid yet;
- a one-off payment of $5,000 or more to a vendor not paid monthly, which no read approval explains.

**Insurance premiums** follow their own rule (`Mystique.premium_rules()`, `mystique/insurance.py`). An approval whose words concern insurance links to payments whose payee or bank line names an insurer, program, agent, NFIP debit, or premium finance company, or whose PayHOA category is insurance, paid from 60 days before the meeting to 300 days after. Installments are summed. An approval that names no coverage means the package: master, umbrella, D&O, and crime. Each flood policy renews on its own date. The result's `insurance` section lists each policy term with:
- the premium from the declarations the document model read, or else from the policy sheet;
- the approvals that cover it;
- what was paid, to whom, and in how many installments.

A flood payment is placed by the NFIP number or building it names, or else by a premium amount that only one building's terms carry.

A link is a rule's reading; whether a payment was authorized is the board's to say.

**Approvals with no amount.** The minutes reader counts "accepted the proposal" as a decision. When an approval states no amount, its minutes item (title, notes, attachments) gives the proposal or estimate number, and the approval is followed in one of two ways:
- by an invoice citing that number; a short number such as "000858" repeats across vendors, so the invoice's payee must be named too;
- else to the one vendor the item names that is not paid monthly and was paid within nine months; one payment answers one approval.

Payee words of five letters or more name a payee. A large payment that minutes accepted without stating an amount is explained this way.

This association's findings are in its private notes (mystique/notes/meetings.md).

## Reusable pieces

| Helper | Where | For |
|---|---|---|
| `meeting_date(name, path, reference=)` | `jason.community.meeting_records` | the date a file or subject carries, in every form the association's names use |
| `RecordRule`, `EmailRule`, `record_kind` | `jason.community.meeting_records` | naming a file or email by specification rows, in order |
| `Digests` | `jason.tasks.digests` | MD5 and SHA-256 of any file on disk, cached, to join copies across Drive, Gmail, and PayHOA |
| `same_file(records)` | `jason.tasks.meeting_catalog` | the copies of one file among a meeting's records |
| `find_executive_break(turns, patterns, departures)` | `jason.zoom.models` | where a call's executive session begins, by the chair's line and who left |
| `executive_break(root, row, community)` | `jason.tasks.zoom` | the same for a synced Zoom meeting |
| `links_in_doc(doc)`, `links_in_pdf(path)`, `drive_id(url)` | `jason.community.agenda_links` | a Doc's chips and links under their items, in every tab, header, footer, and footnote; a PDF's links with their anchor words under the heading above them; the Drive id in any Drive or Docs link |
| `propose(data_dir, items)` | `jason.tasks.board_items` | add or refresh board items and propose new ones for the agenda, never overriding the board's status |
| packet `RESEARCHERS` | `jason.tasks.board_packet` | live "what the records show now" lines for an item, from the catalog |
