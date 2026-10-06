# Owner information and notice delivery preferences: the built form against the standard

Status: mapping (2026-10-05). Key `owner-info`; marker code `NP` (built). This page does **not** redesign the form. It maps the form that exists, `OWNER_INFO` in the profile’s `mystique/forms.py` (the type is `jason.community.forms.FormTemplate`), to the standard in [form-templates.md](../form-templates.md), says what it already meets and what it lacks, and says what the other forms copy from it. The cycle, the tags, and the channels are [owner-information.md](../owner-information.md) (the whole cycle in one place); how it is made, sent, and read back is [forms.md](../forms.md). The inventory row is "Owner information and notice delivery preferences" in [standard-forms.md](../standard-forms.md): required by the law as a solicitation (4041(b)); built.

## 1. Authority

CIV 4041 (a), (b)(1), (b)(2)(A), (b)(2)(B), (c), and (e); CIV 4040(a), (b); CIV 5260(b), (d), (g) for the second address, the membership-list opt-out, and the electronic-ballot choice; CIV 5220 and 5105 for the last two. The operative words are in [delivery-change.md](delivery-change.md), [secondary-address.md](secondary-address.md), and [individual-delivery-request.md](individual-delivery-request.md), which recite them by subdivision. As of: the shelf’s 2025 session publication (`data/authorities/CIV/CIV-4000-4070.md`, read 2026-10-05).

## 2. What it already meets

| Standard | What the form does | Where |
|---|---|---|
| 2. Ask only what is needed, and say why | Each answer the law asks for carries its authority beside it (`FormQuestion.authority`: “Civil Code §4041(a)(1)”, “§4041(a)(2), §4040(b)”, “§4041(a)(3)”, “§4041(a)(4)”, “§5220”). An email is never required: `email` is `required=False`, and its help says “Only if you chose email” | `OWNER_INFO.questions` |
| 2. A required occupancy answer | The law’s own question (4041(a)(4)), worded as the law words it, placed with the sections that must be answered | `occupancy` |
| 3. Say what happens if there is no answer | The preamble says that without an answer notices go to the last written mailing address or the unit (4041(c)), and gives the answer-by day and the 30-day entry rule (4041(b)(1)) | `preamble` |
| 4. The member’s own certification | The `attestation`: “I certify that I am an owner of record of this unit, or am authorized to answer for the owner ...” | `attestation`, `signature`, `dated` |
| 5. A way to change | “You may change your preferences at any time by submitting this form again or by writing to the Association” (4041(b)(2)(B)); `tests/test_packets.py` asserts both the 4041(b)(2)(A) and (b)(2)(B) sentences are in the printed form | `preamble`; the packet test |
| 6. One definition, every channel | The same rows build the PayHOA form, the paper form in the packet, the fillable PDF, the emailed pre-filled copy, and a Google Form; each copy carries its marker (`NP27E`, `NP27M`, `NP27P`) | `GOOGLE_FORMS`; `form_render`; `fillable`; `form_refs` |
| 7. Reading, not guessing | `reads` on each written question; `same_as` for “Same as my unit address”; address in its parts; the return is read, compared with what was sent, and confirmed by a person | `FormQuestion.reads`; `tasks/owner_prefill.py` |
| 7. A procedure | `owner-info-cycle` exists in `src/jason/community/procedures.py`, with the lessons that shaped it | `jason sop owner-info-cycle` |
| 8. Plain language, one value per question | Compound answers are several fields under one heading (representative, second address, manager); the help lines are short | `OWNER_INFO.questions` |
| 9. Tested | The fuzzer, the layout lab, the PayHOA round trip as a test owner, and the packet and form tests | `jason form-fuzz`, `jason forms --payhoa-test`, `tests/test_forms.py`, `tests/test_packets.py` |
| Channels and assurance | The assurance ladder (`SIGNED_IN`, `MATCHED`, `TOKEN`, `CLAIMED`), `RECORD_AT`, and the rule that an answer never overwrites newer information | `Assurance`, `RECORD_AT`; [owner-information.md](../owner-information.md) |
| An acknowledgment of a kind | `OWNER_INFO_COMPLETED_COMMENT` is emailed to the owner once the answer is recorded in full | `mystique/forms.py` |

## 3. What it lacks, against the standard

| Standard or field | What the form has now | The gap | Change (for the template, not for the cycle) |
|---|---|---|---|
| 1. Recite, then ask; `recitals` | A paraphrase in `preamble` that cites sections by name (“Civil Code §4041(a)”); `authority` is a prose string | No operative words, no subdivision text, no as-of date, no “not an official restatement” caveat; the preamble paraphrases in the form’s own words where the standard says the quote comes first. A paraphrase can drift when the subdivision is amended, as the records form’s did | `recitals`: `{QUOTE:CIV 4041(a)}`, `{QUOTE:CIV 4041(b)(1)}`, `{QUOTE:CIV 4041(b)(2)}`, `{QUOTE:CIV 4041(c)}`, `{QUOTE:CIV 4040(b)}`, `{QUOTE:CIV 5260}`, with the paraphrase kept after each as a labeled plain-words note; `authority` becomes a tuple of canonical citations (`("CIV 4041", "CIV 4040", "CIV 5260")`) so the handler registry can join on it ([arrivals-design.md](../arrivals-design.md)) |
| `required_content` | None: the test for the statute’s content is two substring checks in `tests/test_packets.py` | No checklist ties each thing the law says the form carries to the question or the fixed text that carries it; a change that dropped a line of the preamble would fail only the two sentences the test happens to read | a `required_content` table, as in [delivery-change.md](delivery-change.md) section 3: (a) each of 4041(a)(1) to (4) → its question; (b) 4041(b)(2)(A) → fixed text and `email` not required; (c) 4041(b)(2)(B) → fixed text pointing to the short change form; (d) 4041(c) → fixed text; (e) 5260(d), (g) → the designee’s address |
| `member_clock` | The preamble’s answer-by and 30-day sentences | No statement of who decides (nobody), what happens on receipt, or how to reconsider; no “we will tell you the day we received it” | one `member_clock` paragraph in the standard’s form (what happens, by when, who decides, how to reconsider) |
| `acknowledgment` | `OWNER_INFO_COMPLETED_COMMENT` only: “Thank you. Your notice preferences are recorded ...”, sent after recording | No acknowledgment at receipt; no `{RECEIVED}`, `{DUE}`, `{DECIDER}`, `{REFERENCE}`; the owner whose answer needs a person is told nothing | an acknowledgment of the standard’s text on receipt (the same one for every channel), and the existing completion comment kept as the second message |
| `association_clocks` | `OWNER_INFO_CYCLE`: opened, return-by, reports-mailed (an `AnswerCycle`) | Only dates: no row says counted from, number and kind of day, who sets it (statute, documents, proposed policy), and what follows if it passes | rows for the cycle: the solicitation yearly (4041(b)(1)); entry at least 30 days before the reports (4041(b)(1)); the reports 30 to 90 days before the year’s end (5300, 5310); a bounce resent (4041(e)); a received change effective (see [delivery-change.md](delivery-change.md)) |
| 5. Help on the form | Help text on questions | Not found in the template: another format, large print, translation, a reasonable accommodation, a person to write it down, a plain way to make the request without the form. The packet’s cover letter may carry them (not checked here) | a fixed “Help” block in the template, so every channel carries it |
| 4. Where it goes (4035, 5260) | The form says it may be answered online and returned | The `ballots` and `membership-list` questions are requests that, under 5260(d) and (g), are effective only when “delivered in writing to the association, pursuant to Section 4035”; the form does not name the designated person | `{DESIGNATED_PERSON}`, `{RETURN_BY_MAIL}`, `{RETURN_BY_EMAIL}` slots; the form names them |
| 2. 5105’s deadline for the ballot choice | The `ballots` question | 5105(i)(1)(A) lets a member change the method “no later than 90 days before an election”; the form does not say what deadline the election rules set | a fixed line with `{BALLOT_CHOICE_DEADLINE}` filled from the election rules, or the question left out when the rules have none |
| A removal | A blank second address means “no change” | 5260(b) speaks of a request “to add or remove” a second address; a blank cannot remove one | a “Remove my second address” box, or a pointer to [secondary-address.md](secondary-address.md) |
| 4041(a)(4)’s four states | `occupancy` offers three: owner-occupied, rented out, vacant | The statute lists a fourth: “if the parcel is undeveloped land”. Not applicable to a condominium; a base template must carry it, as a slot the profile sets | a `{OCCUPANCY_OPTIONS}` slot with the statute’s four, the profile choosing which apply |
| `procedure`, `handler`, `channels`, `slots` as fields | The procedure, the handler, the channels, and the slots are all real but live outside the template: the procedure in `procedures.py`, the handler as the response inbox with `member_preferences.match` and `owner_info.plan_writes`, the channels in `GOOGLE_FORMS` and `RESPONSE_REQUESTS`, the cycle’s return-by as `{RETURN_BY}` | The registry of [arrivals-design.md](../arrivals-design.md) is designed, not built; “a reference exists only if a handler does” is not yet checked at generation. The only slot is `{RETURN_BY}`; the rest of the text says “the Association” | `procedure="owner-info-cycle"` and `handler=` as template fields; `channels` as a field; slots for the association’s name and where to send |
| A statutory checklist test and a recital-freshness test | None for this form | Standard 9 | the two tests of [delivery-change.md](delivery-change.md) section 14, applied to this template |
| `required_if` | `required=False` on an optional answer; “Only if you chose email” in the help | A paper form cannot require; the PayHOA form can: a conditional rule would let email be required only when email is chosen, on the channels that can enforce it | `required_if`, as the sibling designs need |

**Two findings that are not gaps in the standard but drift in the text.**
- [forms.md](../forms.md) (“Open decisions”) says phone numbers are not asked on the owner form, yet the form asks the representative’s phone and the manager’s phone, both optional. 4041(a)(3) asks the representative’s “name, mailing address, and, if available, valid email address”, so the phone is a convenience; the page or the form changes.
- The module docstring of `mystique/forms.py` cites “Civil Code 5205(e)” for the records charge; the charge is in 5205(f) and (g) ([records-request.md](records-request.md), section 13). Not this form, but the same file.

## 4. What the other forms copy from it

- **A per-question `authority`** beside each question, and no question without a reason.
- **An email that is optional by default**, with the one sentence that says why.
- **An attestation** the member makes by answering, and a signature line only where the channel cannot prove who answered.
- **A marker on every copy** and a campaign per cycle (`NP27E`, `NP27M`, `NP27P`), with a copy marker only for a pre-filled copy.
- **The assurance ladder.** A signed-in answer is the strongest; below `MATCHED` a change is first told to the address on file.
- **“Never over newer information”.** An answer changes the books only when the deed, the owner’s own later edit, and the cycle allow it.
- **One definition, many channels**: PayHOA as the official channel, the PDF and the paper as copies, a person confirming every reading.
- **A completion message** after the writes, kept beside the acknowledgment the standard now asks at receipt.
- **Tests of made-up answers** that read back through a bad scan.

## 5. Changes, in order

1. Add `recitals`, a canonical `authority` tuple, and the `required_content` table; build and test them (they change no question).
2. Add the `member_clock`, the acknowledgment at receipt, and the `association_clocks` rows.
3. Add the help block and the 4035 slots.
4. Add the short change form ([delivery-change.md](delivery-change.md)) and point the preamble’s change sentence to it; add the removal pointer to [secondary-address.md](secondary-address.md).
5. Add `required_if`, the `{OCCUPANCY_OPTIONS}` slot, and the ballot-deadline line.

None of these touches a live PayHOA form’s question ids: the PayHOA form is edited in place with `jason forms --payhoa owner-info --update` and never replaced (AGENTS.md). Items 1 to 3 are text on the printed and fillable form, and the PayHOA form’s preamble.
