# Correspondence

The `correspondence` kind holds what the association sends or receives that is not a legal letter, a bill, a statement, or a meeting record. In the library that means a bank's letters about an account, the association's instructions to buyers and to escrow, its contact sheet and welcome packet, a newsletter and a flyer to the members, a vendor's certified record, and third parties' guides the association passed along. The models live in `jason.community.models.correspondence`.

## Models

The module registers five models for the kind, tried in this order. Each recognizes one form and returns `None` for any other, so a text none of them knows stays unread.

| Model | Form | Recognizes | Required |
|---|---|---|---|
| `certified-record` | certified record | a custodian of records' declaration that the record is a true copy | sender, dated, subject |
| `letter` | letter | a "Dear …" salutation, or a closing or a RE: line with a date | dated, sender, recipient, subject |
| `member-notice` | notice | a newsletter, an announcement, a contest, a reminder, in the association's voice | dated, sender, recipient, subject |
| `handout` | handout | instructions, a how-to, a checklist, a contact sheet, a welcome packet, in the association's voice | sender, recipient, subject |
| `publication` | publication | a guide, an ebook, or a manual section | sender, subject |

A missing field's finding says what the text prints in its place. For example, a flyer with no date of issue gets "no date of issue is printed in the text; the dates it prints (October 30, 2025) are what it refers to".

## The record

**`CorrespondenceRecord`** has these fields:

- `form`, `title`, `subject`, `dated`;
- `sender` and `sender_role`, `recipient` and `recipient_role` (`Role`: association, board, manager, owner, members, buyer, seller, escrow, lender, bank, insurer, vendor, utility, agency, counsel, and others), and `direction` (to the association, from it, or neither);
- what it refers to:
  - `addresses` and `buildings`: the development's street addresses and the buildings the specification places them in;
  - `accounts`: the last four digits of an account;
  - `statutes`: Civil Code sections;
  - `document_sections`: CC&Rs, bylaws, or declaration sections;
  - `dates`, and `deadlines` (`Deadline`: the words before the date, and the date);
  - `amounts` (`Amount`: label and cents);
- `requests` (`Request`): records (CIV 5205), IDR (5910), a Request for Resolution (5935), a hearing notice or a decision (5855), a payment plan (5665), the resale documents (4525, 4530);
- `response_requested` and `respond_by`, from a stated deadline or "within N (business) days" of the letter's date;
- `enclosures`: the attachments a letter lists and the PDFs it names;
- `closing` and `signer_role` ("Customer Service", "Board of Directors", "Custodian of Records");
- for a Request for Resolution, `adr_article_included`; for a hearing notice, `hearing_on` and `hearing_elements`.

**Who wrote it.**

- A counterparty the specification names (`mystique/senders.py`), read from the letterhead above the salutation and the signature block. The body's words ("bank statements") do not count.
- For a guide, the counterparty the text names most, or a known publisher (the NFIP).
- The association itself, when its name heads or foots the page or the text speaks for it ("the HOA", "we"). The role is board when "Board of Directors" signs.
- An owner only by role: `sender` is "an owner". The record never keeps a private person's name, and a salutation to a person becomes a role.

## Findings

A finding cites the statute where the law shapes the letter. The texts cannot show when a letter was received, served, or answered, so every clock is a lead.

| Code | When | Severity | Authority |
|---|---|---|---|
| `response-deadline` | the letter gives a date to act by (marked "past" after today) | info | |
| `records-request` | a member asks for association records: current-year records within 10 business days of receipt, the prior two years' within 30 days, at the direct and actual cost of copying and mailing | check | CIV 5205(f), 5210(b) |
| `idr-request` | a member asks for IDR: the association must take part, may not refuse to meet and confer, and may not charge | check | CIV 5910(c), (g); 5915(b) |
| `idr-offer` | the association invokes IDR: the member may decline, and may appeal to the board | info | CIV 5910(d), (g) |
| `request-for-resolution` | 30 days after service to accept, or deemed rejected | check | CIV 5935(c) |
| `adr-article-not-included` | a Request for Resolution to a member without the ADR article | check | CIV 5935(a)(4) |
| `hearing-notice-days` | a hearing notice dated fewer than 10 days before the hearing (problem), or at least 10 (info) | problem / info | CIV 5855(a) |
| `hearing-notice-elements` | the notice lacks the date, time, place, violation, or right to attend | check | CIV 5855(b) |
| `decision-notice` | a notice of a disciplinary decision: within 14 days of the action | check | CIV 5855(f) |
| `payment-plan-meeting` | an owner asks to meet about a payment plan: within 45 days, in executive session | check | CIV 5665(b) |
| `resale-documents` | the resale documents: within 10 days of a written request, at actual cost, estimated first, no extra charge for electronic delivery | info | CIV 4530(a), (b) |
| `reserve-account` | the letter is about a reserve account the specification names | info | CIV 5200(a)(7), 5510, 5515 |
| `unknown-account` | a bank's letter names an account the specification does not list | check | |

## Coverage

Per-form counts come from `jason models`. A newsletter or flyer that prints no date of issue keeps its missing-date finding: a missing date is a miss, not a defect of the parser. The records request, IDR request, hearing notice, and Request for Resolution findings are tested on synthetic letters (`tests/test_models_correspondence.py`).

This association's findings are in its private notes (mystique/notes/document-models/correspondence.md).
