# Directory publication consent: which contact details may reach which readers, who agreed, and how it is kept

Status: **design** (October 2026). Nothing here is built except what [document-templates.md](document-templates.md#5-the-directory-and-privacy) already has: a directory block with a publish flag on each contact field, `(not published)` and `(vacant)` lines, and an `audience` of `board` or `owners`. This page gives that flag a record, an audience, a history, and a way to be taken back. The console's side is [console/handoff-directory-consent.md](console/handoff-directory-consent.md).

A document that goes to owners lists the people an owner may need to reach: the board's officers, committee members, the manager, and the vendors whose contact an owner is given. Each detail is a person's private fact ([AGENTS.md](../AGENTS.md): names, emails, and phone numbers live in `data/spec`, never in the specification). Printing one is a disclosure. This design says when it is allowed, who allows it, how that is recorded, how it is taken back, and what a generated document keeps so a later change can find it.

## 1. The rule in one line

**A detail is printed for a reader only when a record says that reader may have it, from a day that has come and before a day that has not, and the record is the person's own, or the board's for the association's own contacts. With no such record the detail is a miss: it is not printed, and the document does not say whether it exists.**

jason proposes the list; the person consents or the board decides; nothing is worked out on the client; a miss stays a miss.

## 2. What the law says, recited, and what is a reading

Recited from jason's copy of the code (`jason cite`), with its caveat: this is jason's copy of the publication, not an official restatement. What follows each recital is a **reading for the board and counsel**, labeled as one. It is not legal advice.

**Association records and members' information.** Civil Code 5200(a)(9) lists among association records "Membership lists, including name, property address, mailing address, email address, as collected by the association in accordance with Section 4041 where applicable, but not including information for members who have opted out pursuant to Section 5220." Section 5215(a)(4) lets the association withhold or redact information if "The release of the information is reasonably likely to compromise the privacy of an individual member of the association." Section 5220 reads "A member of the association may opt out of the sharing of that member's name, property address, email address, and mailing address by notifying the association in writing that the member prefers to be contacted via the alternative process described in subdivision (c) of Section 8330 of the Corporations Code. This opt-out shall remain in effect until changed by the member."

- *Reading (the board's and counsel's to confirm).* Those sections govern what a member may inspect and what the association may withhold. They are not a list of what a directory may print, and they do not make an officer's contact details public. An officer is also a member, so the member's own opt-out record (5220) is a fact this design reads and never overrides (section 4.4). A consent to appear in a directory is a separate act from the membership list and is recorded apart from it.

**The designated recipient.** Civil Code 4035(a) reads "If a provision of this act requires that a document be delivered to an association, the document shall be delivered to the person designated in the annual policy statement, prepared pursuant to Section 5310, to receive documents on behalf of the association. If no person has been designated to receive documents, the document shall be delivered to the president or secretary of the association." Section 5310(a)(1) requires the annual policy statement to include "The name and address of the person designated to receive official communications to the association, pursuant to Section 4035."

- *Reading.* This is the one contact the law itself puts in a document that goes to every member. It is the association's designation, made by the board, so it rests on the board's decision and the law, not on one individual's consent to publish a personal detail. Where the person designated is an individual who has not agreed to be named, two readings remain: the board designates an office, the manager, or a role address in the individual's place; or the section calls for a named person regardless. **Two readings remain; the board asks counsel.** Until then jason prints the designation exactly as the board recorded it and adds nothing to it. (Sections 4041 and 4045, which the question also names, concern a member's own delivery preferences and general notice; they do not set the association's address, so this design leaves them to the notice catalog.)

**Information practices.** The Information Practices Act's chapter defines "agency" as "every state office, officer, department, division, bureau, board, commission, or other state agency", with exceptions (Civil Code 1798.3(b)). The consumer privacy chapter asks a business that the chapter covers to keep collection and use "reasonably necessary and proportionate to achieve the purposes for which the personal information was collected" (Civil Code 1798.100(c)).

- *Reading.* Whether either chapter reaches an association is not decided here. It is a question for counsel. The idea in them (collect and disclose only what the purpose needs, tell the person the purpose when asking, keep it no longer than the purpose lasts) is one a community may adopt as its **own written policy** whatever the answer, and this design follows it as a policy for the board to adopt: the purpose is stated on the request, a detail is published for the readers it names, and a detail not needed is not asked for. Adopting it is the board's act, under the "where the law is silent, write it down" axiom ([AGENTS.md](../AGENTS.md)); whether the rule needs notice to members first is for counsel (Civil Code 4355, 4360, `jason rule-change`).

**Cited, not recited.** Corporations Code 8330, whose alternative process 5220 names, is on the shelf and is not recited here; the board reads it with `jason cite "CORP 8330"` if it needs it. No provision on this page is recited from memory.

## 3. The model

```
DirectoryEntry   one seat or contact: a stable id, a kind, a role label, the holder, the values
   ContactField    email | phone | address | hours | group | portal  (a value; no flag)
ConsentRecord    one line: person, field, audience, from, until, given how, by whom
Published(entry, field, audience, day) -> value | a miss      (the one function every document asks)
```

### 3.1 Entries

An entry is one **seat or contact**, not a person: a role the association lists (an office, a committee seat, the manager, a vendor contact) with the person who holds it today. Each has a stable `id` that is not the person's name (`dir-0004`), so a part map, a log, and a consent can name an entry without naming anyone.

| Entry kind | Who it is | Whose consent |
|---|---|---|
| `officer` | an office of the board and the person who holds it | the person, for their own fields |
| `director` | a director with no office | the person |
| `committee` | a committee seat and its member | the person |
| `manager` | the management contact an owner may call | the person, for personal fields; the board, for the company's and the association's fields |
| `role` | a role address or the association's own contact (a group address, the association's mailing address, office hours) | the board, by a decision on record |
| `vendor` | a vendor or the manager's portal contact an owner is given | the vendor's named contact, in writing, recorded by a person; the board decides that the vendor is listed |

The **shape** of a directory (which roles a document lists, in what order, with which fields) is the document definition's, and so the board's: a person cannot add a seat to a document by consenting. The **values** come from the private facts topic `directory` (`jason.community.private.facts("directory", profile=...)`, `data/spec/<profile>/directory.json`), which holds each entry's id, kind, role label, holder, and values, with no publish flags in it. Today's `DirectoryEntry.publish` and `ContactField.publish` become the answer to `Published(...)`, read from consents; the topic's flags, where a profile has them, are read once as the first consent records (section 8, decision 2).

### 3.2 Fields

| Field | What it is | Default | Preference |
|---|---|---|---|
| `role` | the seat's label ("President") | printed: the seat is the association's, not the person's | |
| `name` | the holder's name | **not published** | a seat with no published name still prints its role and its role address |
| `email` | the holder's own address | **not published** | prefer the role address (`group`) |
| `phone` | the holder's own number | **not published** | prefer the association's or the manager's number |
| `address` | a mailing address | **not published** | prefer the association's or the designated recipient's address; a home address is never proposed |
| `hours` | office hours or a time to call | **not published** | the association's or the manager's |
| `group` | a role mailbox (a group address that reaches whoever holds the seat) | **not published** until the board decides it | the preferred way to reach a seat: it survives an election, reveals no person, and is the association's to give |
| `portal` | a link or route to a vendor's or manager's own portal | **not published** | a link, not a person |

**Prefer the role address.** A role mailbox is the association's: the board decides it, no person's consent is needed for it, and an election changes who reads it without changing the document. jason proposes a role address first for every seat that has one, and asks for a personal detail only for a reader whose purpose a role address does not serve (a phone number for an urgent matter, for instance), saying so on the request.

### 3.3 Audiences

An **audience** is who a document goes to, and each is separate: publishing to one publishes to no other.

| Audience | A document that goes to | Example |
|---|---|---|
| `board` | the board and the manager only; never distributed | a draft, a roster for the board's own use |
| `owners` | owners, as a document they receive or may open | the owner's manual, the annual policy statement's directory |
| `site` | the public: a page on the association's website | the contact page |
| `notice` | a letter or notice sent to owners by a method that names a sender or contact | a meeting notice's "questions to", a letter's signature block |
| `vendor` | a vendor or the manager | a packet that names the board's contact for an invoice |

A document **declares its audience** in its definition (`audience="owners"`), and the directory block asks `Published(entry, field, audience, day)` for exactly that one. A person may consent to several audiences in one act (the console writes one record for each); the record is never "all". `board` fields are the one audience a draft may show in full, and the output is marked not for distribution (as the block does today).

### 3.4 The fallback when nothing is published

The reader is never left with no way to reach the association:

1. **The designated recipient** (Civil Code 4035, 5310(a)(1); section 2): always printed where a document carries a directory, exactly as the board's decision records it. It is not a consent field.
2. **A role address** the board has published for the seat, or the association's own contact.
3. **The manager's contact**, where the board has decided the manager is listed.
4. **The line**: "Not published. To reach this office, write to the association's designated address above." jason words it; the board adopts the wording with the directory.

An owner can still send a document to the association; they can no longer pick the person.

## 4. The consent record

### 4.1 Who may consent

| For | By | The proof |
|---|---|---|
| a person's own field | that person | their sign-in at the console (`Officer.email` is the Google account they sign in with), or a form they sign, or their email kept as evidence |
| a role address, the association's address, hours, a portal link | the board | a decision on record (`data/board/decisions.json`), whose id the record carries; read from the decision, never typed (the way the confirmations queue reads an adoption) |
| a vendor's or the manager's company contact | the vendor's or company's named contact | their email kept as evidence, recorded by a roster person |

**Nobody consents for someone else without their word.** A roster person may *record* another's consent only with the evidence attached (their email, a signed form), and the record then says who gave it and who recorded it. Consent is never inferred from silence, a role, an earlier directory, or an office's holding a seat.

### 4.2 What a record carries

One line of an append-only store. A record is never edited or deleted; a change is a new line.

| Field | Meaning |
|---|---|
| `id` | `cns-0001`, stable |
| `entry` | the entry id (`dir-0004`), never a name |
| `field` | `name`, `email`, `phone`, `address`, `hours`, `group`, `portal` |
| `audience` | `board`, `owners`, `site`, `notice`, `vendor` |
| `act` | `give` or `revoke` |
| `basis` | `person` (their own consent), `board` (a decision on record), `evidence` (given by another's recorded email or form) |
| `from` | the day it takes effect (a day, never "now") |
| `until` | the day it ends, or empty: it holds until revoked or the seat changes |
| `how` | `console` (signed in as the person), `form`, `email` |
| `evidence` | the library reference of the kept email or signed form (P3); the board's decision id |
| `purpose` | the words the person was shown (section 4.5) |
| `givenBy`, `recordedBy`, `recordedAt` | who consented, who wrote the line, when |
| `revokes` | for a revoke, the id it ends |

**State is computed, never stored.** `Published(entry, field, audience, day)` takes the latest `give` for the key whose `from` is on or before the day and whose `until` has not passed, unless a later `revoke` on or before the day ends it. The states are `in force`, `not yet` (a future `from`), `ended` (past its `until`, or revoked), and `none`.

### 4.3 Revocation, expiry, and the seat

- **Revoking.** A person may revoke any of their own consents on any day, for any reason, and need not give one. The record takes effect from its `from` (today by default). **For a document generated after it, the field is a miss at once.**
- **Documents already generated or sent.** A revocation does not reach into a sent letter. jason lists each document whose part map (section 5) names the revoked consent: the ones **not yet sent** are marked stale to regenerate; the ones **sent or published** are listed for a person, who decides whether to reissue, update a page, or leave it, and records which. jason never recalls, edits, or deletes a sent document.
- **Expiry.** A consent may carry an `until` the person chose. It also **ends with the seat**: when the board-roster answer records that the person left the seat or the term's recorded end passes, the consents tied to that seat end that day (jason sets no end the record does not give: `Term.ended`). A person's consent to appear as "Treasurer" is not a consent to appear in another role or after leaving.
- **A new holder starts with nothing.** An election result is a change of holder, never a transfer of consents.

### 4.4 The member's own opt-out

An officer who has opted out of sharing under 5220 is read as having done so: the console shows "opted out of sharing as a member (5220)" on the person's entry when the association keeps that record, and a consent to a directory field is asked again in words that say it is a separate act ("This is a different permission from the membership list."). jason never treats a 5220 opt-out as a refusal of the directory, or the reverse.

### 4.5 The words the person is shown

Every request states the **purpose, the reader, the field, and the period**, and that saying no costs nothing: "Example Village HOA would like to print your email address in documents sent to owners (the owner's manual and the annual policy statement) until the end of your term. You may say no, or change your mind at any time. If you say no, owners will see the association's address in its place." The text is a base template, rendered by the profile, never typed per person. A request that does not state its purpose is not a request this design accepts, and a consent recorded against one is flagged.

### 4.6 Where it is kept

**Decision: the consents are an append-only store, `data/directory/consents.jsonl`; the entries and their values stay in the private facts topic `directory`.** Not checked in; both are P3 ([console/security-and-privacy.md](console/security-and-privacy.md#data-levels): `spec/` is P3, so is the store by a new `PATH_RULES` row).

Why not one file in `data/spec/<profile>/directory.json`:

- A private-facts topic is read whole and rewritten whole (`private.write`). A consent is a **history**: who agreed on which day, who revoked, the order. Rewriting a file loses that, and "never rewriting history" is the point.
- A store jason appends to holds its store lock (`jason.locks`) and is read by the audit and the part map's check; a topic file is read by the profile.
- The values and the permissions answer different questions (what is the number; may it be printed) and change at different times (an election; a mood).

Why not a store for the values too: the topic is already how the roster, the sign-in, and the directory block read the association's people, and a profile that already has the file keeps it.

### 4.7 The audit trail

Every line is its own trail: who consented (`givenBy`), who wrote it (`recordedBy`), when, how, on what evidence, which earlier line it ends. The log's masking applies (`audit.mask`): a value is never written to a log, only an entry id, a field name, and a consent id. A reveal of a value on screen is logged as any P2 reveal is. The store has no delete and no edit; a mistaken line is ended by a `revoke` that says so in `purpose`, and the correction is a new `give`. `jason directory --history ENTRY` prints an entry's lines in order.

## 5. How a document uses it

1. **The directory block reads only `Published`.** For each seat it asks, for the document's audience and the document's day, `role` (always), `name`, then each field. A field with a value in force prints; any other state prints the same word, whether a value exists, a person declined, or a consent has not arrived: **"not published"**, in the cell, never "declined", "pending", or "unknown", and never a partial value (no `j•••@`).
2. **A vacancy and a seat with no consent differ, and say so.** The vacancy is the association's fact, from the records of who holds a seat (`Community.officers()`, the terms and the board-roster answer): the row prints `(vacant)` and, where the profile keeps it, the governing documents' vacancy provision recited ([console/screens/people.md](console/screens/people.md)). A held seat whose holder has not consented prints the role, `(not published)` in the name cell, and any role address the board has published. A held seat is never printed as vacant to avoid saying a name is withheld, and a vacancy is never printed as `(not published)`.
3. **The part map records the fields, by field, not by value.** The part map written beside a generated document ([document-templates.md](document-templates.md#62-what-the-document-template-model-adds-or-replaces)) gains, for a directory block, the list `{entry, field, audience, consent, day}` of every field that printed, and the list of fields that did not (entry and field only). It carries no name, no value, and no digest of one (a hash of an email is guessable). The consent ids make a later change findable.
4. **A generated document whose consent lapsed is stale.** When a consent in a part map ends (revoked, expired, the seat changed), the document is marked **stale for the directory** with the consent and the field named, and the console lists it. A not-yet-sent document is regenerated; a sent one is a reissue question for a person (section 4.3). A document is also stale when a field it printed was `not yet` in force (`from` in the future) on its day: the check reads the same function.
5. **No value in logs, part maps, screenshots, or the console's lists.** A value is shown only in a document's own text and in the one view that edits it, masked by the server by level (P2: `a•••@example.com`; revealed one field at a time, logged by kind). A screenshot or recording tool never captures an unmasked value because the server never sent one.
6. **The check.** The document check ([document-templates.md](document-templates.md#7-the-check)) gains one line: every field printed in a directory block has a consent in force on the document's day for its audience, or is a role-address or designated-recipient row; a printed field with none is a defect and exits 1.

## 6. The workflows

Each is a person's act, with a name and a day; jason proposes the step and records it.

### 6.1 Onboarding

The roster is collected first ([onboarding.md](onboarding.md): the officers and their change of office). Directory consent is collected with it: for each seat the roster names, jason proposes the role address first, then asks the holder for any personal field the board's directory shape lists, stating the purpose and reader. A seat the holder has not answered stays not published. An onboarding gate does not wait on consent: an unanswered seat is a miss, and the checklist item says how many seats are answered, never "done" on a person's behalf.

### 6.2 A new officer after an election

The election's result is the board-roster answer (`OFFICE; PERSON; YYYY-MM-DD; MINUTES`) or a director's seat from the inspector's report. When it is applied, jason proposes a **consent task** for the new holder: the same request as onboarding, for the seats and fields the directory lists. The outgoing holder's consents for that seat end on the day the record gives. Until the new holder answers, the seat prints its role and role address and is not published by name; no document waits on it.

### 6.3 A resignation or a removal

The record of the change ends the person's consents on its day. jason lists the documents that carried them (section 5, item 4). The seat prints `(vacant)` until a holder is recorded, with the vacancy provision. A person decides, for each sent document, whether to reissue; a document still in draft is regenerated.

### 6.4 The annual re-confirmation

Before the documents that carry the directory are generated each year (the annual policy statement, the owner's manual, a refreshed contact page), jason proposes a re-confirmation request to each holder whose consents are in force: "Here is what is printed, for whom, since when. Keep, change, or end it." The lead time is the profile's. What an unanswered request does to a consent in force is a decision for the board (section 8, decision 3).

## 7. What this design does not do

- It does not decide what a directory must contain: the board does, as the document's shape.
- It does not make a rule, and it does not decide whether a rule on this subject needs notice to members first (Civil Code 4355, 4360): the board asks counsel.
- It does not decide whether a statute requires a person to be named: that is for counsel (section 2).
- It does not send, post, or recall a document.
- It does not reach beyond jason's own stores: a person's detail already in PayHOA, Gmail, a Google Group, or a recorded instrument is not changed by a revocation here; the console lists those places as "not controlled by this record", and a person acts there.
- It does not treat a vendor's business contact as private by default: a vendor's public contact is the vendor's own to list, and the record exists so the board can show the vendor's word.

## 8. Decisions for the board and the design

Each decision lists its options and does not recommend one.

1. **Who may record another person's consent** when the person is not at the console: any roster person with the evidence attached; only the secretary; or only the person.
2. **The first records.** Where a profile's `directory` topic already carries publish flags: (a) read each flag once as a consent dated the day of the migration, with `how: form`, `basis: person`, and a note that it was carried; (b) ask each person again; (c) read none, and start from nothing.
3. **An unanswered annual re-confirmation:** (a) the consent stays in force, flagged "re-confirmation overdue"; (b) it ends on a day the board names; (c) it ends when the next document is generated and is not renewed.
4. **The designated recipient when an individual has not consented:** the board asks counsel (section 2); until then the board's recorded designation is printed as it stands.
5. **The default `until`:** the recorded end of the term, or none (until revoked or the seat changes).
6. **Whether the board adopts this as a written directory policy**, with the purpose words of section 4.5 attached, and whether it needs notice first.
7. **Role address as the default for every seat**, or only where a group address already exists.
8. **Vendors:** whether a vendor's consent is recorded at all when its contact is its public business line, or only when the contact is a named individual.

## 9. Phases

- **Phase 1 (design, this page).**
- **Phase 2:** `jason.community.directory_consent` (pure: `Entry`, `Consent`, `published`), the append-only store and `jason directory` (read: list, `--history`, `--published AUDIENCE --on DAY`; write: `--give`, `--revoke`, each with `--by` and `--yes`), the directory block reading `published`, and the part map's field list.
- **Phase 3:** the stale-for-directory check, the reissue list, the consent task from an election result, and the annual request.
- **Phase 4:** the console ([console/handoff-directory-consent.md](console/handoff-directory-consent.md)).
