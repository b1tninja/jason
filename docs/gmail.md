# Gmail as a source

The association's Google Workspace mailbox is a second source beside the paper mail and PayHOA. Jason reads it with the read-only Gmail scope, keeps headers only, and stores them under `data/gmail` (git-ignored). It sends no email and changes no label. The sync reads no message body; only `jason signatures --fetch` reads the bodies of a few selected messages, for their signature block, and keeps none of them ([Signatures](#signatures)).

A thread here is Gmail's `threadId` in the one mailbox read. How jason should rejoin split conversations, tell who answered whom, and detect forwards (the threading headers, RFC 5256, a local conversation catalog) is proposed in [gmail-conversations.md](gmail-conversations.md).

```bash
jason gmail --sync          # two years of headers (throttled under Gmail's per-minute quota)
jason gmail                 # the PostScanMail check and the correspondence summary, from disk
jason contacts --fetch      # PayHOA's vendor-info report, then the contact directory
```

**The window.** The store holds the messages of the last sync's window: 730 days by default (`tasks.gmail.sync(days=730)`), counted back from that sync, and kept in `data/gmail` with the `days` the sync used. A question about anything older, such as a change of manager years ago, is a live read-only Gmail search, not a search of the store; say which one an answer came from.

## PostScanMail's notices

PostScanMail sends each item to the association's Google Group "Mail", so it lands in Gmail twice:

- **"New Mail Delivered"** carries the envelope image.
- **"Scan Complete"** carries the same image and the scan PDF. The PDF's name ends with the PostScanMail id (`<Sender>_Envelope-<id>.pdf`).

The two messages are joined on the image's name. Read against the items the API synced (`data/mail`), the notices show:

- scanned items the API sync does not hold;
- items delivered to the box and never scanned (they wait for a scan request, or were forwarded, shredded, or discarded);
- the median time from delivery to scan.

The notices are a check on the API sync and a fallback if the key stops working.

## Business email

Every message is kept for its thread: date, direction, subject, attachment names, and its parties.

A message is business email when it carries an address outside the association's domain (`mystique/mail.py`, `EMAIL_DOMAINS`) and outside the personal providers. For business email jason also keeps the business domains on it, and each business address becomes a contact: display name, first and last date, and counts in each direction.

A personal address, such as an owner's, is never kept. It is resolved to who the records knew the sender to be on the day the message was sent (`jason.tasks.parties`):

- **A current PayHOA member** is "owner of <unit>", or "board member".
- **A current member who wrote before the unit's latest deed recorded** is a buyer.
- **A sender PayHOA does not know** is matched by display name to the grantees on each unit's deeds (`data/ownership.db`). A grantee owns from the recording until the next deed on the parcel. So the message reads as from the owner then, a former owner after the conveyance, or a buyer before the deed recorded.
- **Anyone else** is "personal".

A unit joins its parcel by address, since the tax store's situs address is PayHOA's unit label.

A message's sender is resolved when it is read, from the `domains` on the sender rows in `mystique/senders.py`. So adding a domain there takes effect without another sync.

## Google Groups

Much of the association's mail reaches it through a Google Group, a shared address such as accounts payable. The groups are rows in `mystique/groups.py` (`GoogleGroup`: address, name, and a `GroupPurpose`), read through `google_groups()`.

- **The writer behind a rewritten From.** A group that forwards mail from a domain with a strict DMARC policy replaces the From line with its own address: `'A Writer' via Accounts Payable <ap@example.org>`. The writer is kept in `X-Original-From` and `X-Original-Sender`, and jason reads the sender from there. So a vendor's invoice sent through the group reads as from the vendor's domain, not from the association. The group is kept as the message's `via`.
- **The groups a message came through.** Every message a group delivers carries its `List-ID` (`<ap.example.org>`) and an `X-BeenThere` naming the group, whether or not the group rewrote the sender. Google writes `List-ID` where the RFC writes `List-Id`, so headers are matched in any case. jason keeps each message's `groups`, and the association addresses it was sent to (`addressed`).
- **What a group's purpose changes.** Mail that comes into an accounts payable group is a bill to pay: `jason gmail --files` saves its PDFs even when a board member forwarded it and no business domain is on it. The report under `jason gmail` counts mail by group, and lists a group the specification does not name.
- **A message stored before these headers were read is read again once** (`MESSAGE_VERSION` in `jason.tasks.gmail`).

The group's members and settings are in the Google Workspace admin console. jason does not read them: that needs the Admin SDK's directory scope, which jason's sign-in does not ask for.

The email is where some things happen that the paper mail never shows:

- The insurance agent's renewal proposal is negotiated by email.
- A renewal letter is signed through Adobe Sign or DocuSign.
- A carrier's claim payment arrives from its payment processor.

The insurance review (`jason insurance`) reads the agent's, program's, and carrier's messages. A term that ended with no premium in PayHOA but has renewal email after it reads "renewal handled by email", not missing.

## Vendor contacts

`jason contacts` (and the `vendor_contacts` MCP tool) reads three sources side by side:

- PayHOA's vendor-info report: contact name, email, phone, website, and address;
- the contacts from Gmail;
- the sender rows.

A vendor's domains are its sender row's domains, plus the domain of its PayHOA email and of its website. For each vendor the directory lists the people who wrote from those domains, and proposes changes:

- an email or contact name PayHOA lacks;
- an address on file that no message carries;
- a contact name on no message;
- a domain the sender row does not list.

A department mailbox such as `accounting@` is shown, but never proposed as a contact name. A business domain no vendor claims is matched to a vendor by name where the words agree, and otherwise listed.

A person makes the changes in PayHOA or in `mystique/senders.py`. Jason changes neither.

## Signatures

The headers say a sender's domain and display name. The signature block at the end of a message says what kind of party wrote: a title, a company, a license, a disclaimer. `jason signatures` reads it to tell owners and residents apart from property managers, realtors, vendors, title and escrow, attorneys, insurers, lenders, and agencies.

```bash
jason signatures                          # dry: which senders a run would read, and how many messages
jason signatures --fetch --non-owners     # read them (read-only) and store the signature fields
jason signatures --domains example.com    # only senders at a domain; --threads ID ... for threads
```

**What is read.** By default, the latest two inbound messages from each sender (`--per-sender`), at most 40 a run (`--limit`):

- each business address;
- each owner label ("owner of <unit>"), unless `--non-owners`;
- each thread from a personal address the records don't know.

Unknown business senders go first. No-reply and notification mailboxes, service platforms, and the association's own addresses are skipped. A message already read is not read again (`--refresh` reads it again).

**How.** `GoogleGmail.get_body` asks for the message under `gmail.readonly`, the scope jason already holds. It returns the sender headers and the text and HTML parts; no attachment is downloaded. The body stays in memory for one message:

1. `jason.community.signatures.split_signature` cuts the quoted chain ("On ... wrote:", "-----Original Message-----", an Outlook "From: ... Sent:" block, `>` lines) and a list or shared-inbox footer.
2. It finds the block: a `--` line, the last sign-off ("Best regards", "Thanks,", "Sincerely"), "Sent from my iPhone", or the short lines around the last phone, website, or license before any disclaimer. HTML is read as text, with Gmail's signature and quote marks.
3. `parse_signature` reads the block's fields and guesses a role, with a confidence and the cues that fired: titles, company words, license numbers (DRE, CalBRE, CSLB, NMLS, State Bar, insurance, escrow), a business disclaimer, and the domain (a consumer provider leans individual, a company's domain business, `.gov` government).

Then the text is dropped.

**What is kept** (`data/gmail/signatures.json`): one row per sender, with the message ids read.

- **A business address** keeps the signature's fields: name, title, company, website, licenses, link kinds (LinkedIn, Calendly), and a number only for a labeled office, direct, fax, or toll-free line. A mobile or unlabeled number is only a flag.
- **A personal address is never stored.** Its row is keyed by a hash and carries the party label `correspondence.json` already holds and the provider ("gmail.com").
- **An owner, or anyone whose signature reads as an individual,** keeps only the role, its confidence, the kinds of cue, and flags: a phone, a street address, a disclaimer, sent from a phone. No name, no employer, no number.
- **No body, subject, or signature text is stored.**

**The summary** joins each row to the directory as it stands when read: `mystique/senders.py` by domain, else by company words, and PayHOA's vendor-info report by email or website domain. It adds the units in the sender's threads. It lists the **candidates**: senders whose signature reads as a property manager, realtor, vendor, or other professional that the directory doesn't name. A person adds the sender row (a property manager as `SourceKind.PROPERTY_MANAGER`, once a lease or the owner says so); jason doesn't.

A role is a guess. A sender row outranks it, and an owner who writes from work reads as a business. A bare name at a company's domain stays unknown.

## Threads

`jason threads` (and the `email_threads` MCP tool) groups the messages by Gmail thread. The last message decides whose move it is:

- **awaiting us**: the last message came in and nothing went out after it;
- **awaiting them**: the last message went out and nothing came back;
- **notice**: an automated sender with nothing asked of us in the subject;
- **internal**: only the association's own addresses.

Each thread is read beside the association's other records, from 14 days before its first message to 60 days after its last:

- the PayHOA payments to its named sender;
- that sender's paper letters;
- the invoices among its attachments, and the payment each is matched to (`jason copies`);
- the files saved from it to Drive (`jason drive --gmail`);
- for an owner's thread, the PayHOA requests and violations on that unit, with their status.

A related item is a lead for a person, not a finding. A reply by phone, in person, or from another mailbox is not seen, so a thread awaiting us may already be handled. The report is `data/reports/threads.json`.

## Drive files saved from email

Neither side records a save. Drive keeps no source for a file saved from Gmail, and Gmail marks no attachment as saved. `jason drive --gmail` makes the link by content:

1. For each Drive file outside the path rules, or duplicated, it searches Gmail for an attachment of the same name (`filename:`).
2. It fetches that attachment and compares MD5s.
3. A Drive copy created after the message arrived is saved from it.

Attachments of the same name with different content are listed: another version, or a file never saved. The result is `data/drive/gmail-links.json`, and the attachment hashes are cached, so a run resumes where the last one stopped.

## Filing vendors' attachments

`jason gmail --file-vendor NAME|all` files the documents a vendor sent in Drive by the profile's filing rules (`Community.email_filing`): the document's kind first, its source second. It runs in two ways.

- **Upload (the default).** jason reads each attachment, classifies it by name and by its words, skips content Drive already holds, and uploads the rest with the message in the file's `appProperties`. `--yes` uploads; `--hold GLOB` keeps back a document a person must verify first, such as emailed wire instructions.
- **Gmail's own Add to Drive (`--via-gmail`).**
  - jason reads Gmail's metadata only (names and sizes). It lists in `data/gmail/save-to-drive.md` what a person saves with Gmail's button, each with a link to its message and its folder.
  - With `--yes`, it finds the saved copies in the root of My Drive, moves each into its folder, and tags it with its message.
  - Nothing is downloaded or uploaded.
  - Matching by name and size misses a copy renamed in Drive, which the upload mode's content check catches.

`jason gmail --filters-xml` writes Gmail's own filters, one per vendor with a known address, labeling its mail `Vendors/<vendor>`, for a person to import in Gmail's settings.

### The gap: no API for Gmail's Save to Drive

Gmail links an attachment to its Drive copy (the attachment then offers "Organize in Drive") only when a person saves it with Gmail's button. No API makes that link, so a file jason uploads, or moves into place, is not shown as linked in Gmail. jason records the link on the Drive file instead: `appProperties` and the description name the message.

**Checked on October 4, 2026:**
- The Gmail API's release notes, through June 24, 2026, have nothing on saving attachments to Drive.
- Google's Gmail MCP server (developer preview, April 22, 2026) has tools for search, reading, labels, and drafts, and none for attachments.
- The Workspace MCP server (public developer preview, May 2026) uploads to Drive, which is a copy, not Gmail's link.
- Workspace Studio (Flows) has a step that saves an arriving email's attachments to a Drive folder. It is a flow a person builds in Google's interface, not an API. Whether its copies show as linked in Gmail, and which editions have it, is not documented; test before relying on it.

**If Google publishes an endpoint, or Studio's copies prove linked:**
- Replace the person's click in the `--via-gmail` path (`plan_saves` and `adopt_plan` in `jason.tasks.vendor_files`) with the call, or with a Studio flow saving into a folder `adopt_plan` also watches.
- Keep the filing rules, the duplicate checks, and the `appProperties` tag as they are.
- Re-check the release notes at each Gmail API or Workspace MCP announcement.

## Pace

Every Gmail request in the process shares one pace: 40 a second, under the 15,000 quota units a minute a user is allowed. A refusal or a dropped connection is retried for up to about seven minutes. The sync saves its progress every 500 messages and skips what it has already read. An access token lasts an hour; when Google answers 401, the client exchanges the refresh token for a new one and asks again, once, and parallel workers share that renewal.

## Topics, parties, new owners, and open items

These views read the threads beside every other store (`jason.tasks.party`):

- **`jason topics`** (`thread_topics`) counts what the association hears about, by topic: parking, bins, solar, insurance, assessments, maintenance, landscaping, pests, architecture, neighbors, escrow, governance, security, and utilities. A topic is read from subject words (`mystique/topics.py`). A topic three or more units raised in a year is an FAQ candidate, for a notice, a rule clarification, or the new-owner packet.
- **`jason party <unit or name>`** (`party_brief`) puts one unit or one counterparty on a page.
  - A unit gets its owners by deed, its PayHOA balance and members, its requests and violations, its threads with their topics, the letters naming it, and the unit brief.
  - A vendor or agency gets its payments by year (by PayHOA vendor, or its words in the bank line), its invoices and whether each is paid, its threads, its letters, the people who write from its domains, and the Drive files saved from its email.
- **`jason new-owners`** (`new_owners`) lists the units conveyed in the window. For each: whether the buyer is linked in PayHOA, the balance, the buyer's threads and topics from 60 days before the deed, and the requests since.
- **`jason open-items`** (`open_items`) lists what is waiting on the association:
  - email threads awaiting us;
  - PayHOA requests pending;
  - deadlines due soon or overdue;
  - insurance findings;
  - mail delivered and not scanned;
  - letters to act on;
  - lien notices not paid.

`party_brief` and `open_items` are on the board profile.

## Requests by email

`jason request-links` (and the `request_links` MCP tool) reads each PayHOA request, with its title, message, comments, and dates, beside the email about it:

- **PayHOA's own notices** ("Maintenance Request Submission", "New Comment", "Request Status Change") are joined to the request that was created, commented on, or updated within 15 minutes.
- **An owner's thread about the same unit** is scored from 30 days before the request to 45 days after its last change:
  - 2 for a shared topic;
  - 1 for each shared subject word, up to 3;
  - 1 for being within three days of the request.

  A score of 2 or more joins the thread, and the join keeps its reasons. For example, an owner's thread about a garage door joins a maintenance request about the garage door spring filed two days later for the same unit.

A thread between the association and an owner that raises a request topic, with no vendor or agency on it and no request joined, is an emailed request PayHOA does not have. The request topics are maintenance, landscaping, pests, architecture, parking, bins, neighbors, security, and utilities.

For each such thread, a draft names:

- the form (`mystique/requests.py`: architecture to the Architectural Request; maintenance, landscaping, pests, utilities, and bins to the Maintenance Request; the rest to the General Request);
- the unit;
- a title from the subject;
- a message pointing at the thread.

The email is read by its headers, so a person reads the thread and supplies the owner's request in full:

```bash
jason request-links --create THREAD_ID                                   # show the draft
jason request-links --create THREAD_ID --message "..." --yes             # enter it in PayHOA
```

A draft is entered only when a person names it with `--yes`. PayHOA notifies the owner only with `--notify-owner`. Jason never approves, denies, or assigns a request.

`jason open-items` lists the emailed requests of the last 30 days.

## What an email asks, and where the answer is

`jason inbox` (and the `email_intents` MCP tool) is a first pass over each thread's subject (`jason.tasks.intents`):

- **Intent** (`INTENT_RULES` in `mystique/topics.py`, in order): the association's own enforcement notice ("Courtesy Notice", "Notice of Violation", "Disciplinary Hearing"), a complaint (noise, unauthorized parking, parked in front of a garage, cans left out, an attack, smoking, "issues with"), a maintenance request, a request for information or records (a copy of a document, the certificate of insurance or master policy, an HOA demand), a billing matter, or a question. A subject can carry several intents. A subject that names none takes "maintenance request" from a maintenance, landscaping, or pests topic, and is otherwise unclear.
- **Where the answer is likely written** (`TOPIC_SOURCES`), for a complaint, question, or request for information:
  - the governing documents' passages matching the topic's query and the subject's words (the same BM25 search as `passage_search`);
  - the library's documents of the kinds that speak to the topic;
  - the PayHOA violations that are its precedents, with the notice text each carried (the restriction and the hearing language).

  For example, a complaint about trash cans left out points to the CC&R section on trash containers and to the earlier "Trash Cans Left Out" violations, and a parking complaint points to the CC&R parking section.

`jason case WORDS...` (and `case_file`) gathers one matter across the stores by the words that name it: the threads, the PayHOA violations and requests, the letters, the Drive files, and the library's documents, in date order. For a dispute that reached court, the words can be the subject, a party's name, the case number, and the claim number, and the result runs from the violations through:

- the notices of violation and of the disciplinary hearing;
- the hearing recordings and transcripts;
- the minutes;
- the preservation letter, the complaint, the summons, and the proof of service;
- the insurer's claim;
- defense counsel's case analysis.

This association's findings are in its private notes (mystique/notes/gmail.md).

PayHOA's violations are synced with every status (`jason sync-catalog --only violations`). Closed violations are the association's precedents; the old default kept only the outstanding ones.

## What the association answers

`jason replies` (and the `reply_needed` MCP tool) learns from the association's own replies which email needs an answer (`jason.tasks.replies`). A thread that came in was answered when a message went out after its first inbound message. The history is the threads that came in more than 14 days ago.

Reply rates are kept by sender, by kind of party and what the subject asks, and by kind of party. This association's findings are in its private notes (mystique/notes/gmail.md).

An open thread (its last message came in) takes the rate of the most specific level with five threads of history:

- It **likely needs a response** when that rate is one half or more, or when the association already answered it once and the other side wrote again.
- It is **past the usual time** when it is older than three replies in four took at that level, and at least two days old.

`jason open-items` lists its threads awaiting us with this judgment, the likely ones first.

The rates say what the association has done, not what it must do. A reply by phone, in person, from another mailbox, or through PayHOA is not seen, so the rates understate what was answered.
