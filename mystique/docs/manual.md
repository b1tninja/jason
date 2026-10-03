# The Owner's Manual and Rules, taken apart

This page is the profile's notes for `jason manual` ([docs/owners-manual.md](../../docs/owners-manual.md)). It covers the Owner's Manual and Rules Doc (outline key `owners-manual`). The rows are `mystique/manual.py`. The outputs are not checked in; they are under `data/manual/owners-manual/` and `data/drafts/`.

## What the manual holds

In the Doc's order:

1. **The cover.**
2. **The guide.** Seventeen questions and answers, the personal insurance check-list, and a contacts table. Then "who to call", numbered 1-2 and again 1-4.
3. **Part A. Preamble** (A-1 to A-3).
4. **Part B. Community Regulations** (B-1 to B-18). B-12 is the parking rules Doc word for word.
5. **Part C. Enforcement.** The courtesy-letter steps, a) Fine Schedule, and b) Due Process Requirements 1-7.
6. **The Assessment Collection Policy.** The manual has only its cover ("EFFECTIVE: April 18, 2023") and the Doc's insert marker. Then comes the notice Civil Code 5730 requires.
7. **The Home Improvement Request Application.** It includes its General Conditions of Approval 1-3.

The outline reads three things the Doc does not print:

- Part A's "A." hangs from the guide's "4. Towing", so the outline calls it `4(A)`.
- Part C's "C." hangs from B-18, so it is `B-18(C)`.
- The signage list under the "Demarcation" heading in B-12 becomes a second `B-12(i)`, then `B-12(ii)` to `(iv)`.

The application's conditions 1-3 are read again as `B-18(C)(1)` to `(3)`. The new numbers are the printed ones: `A`, `A-2(a)`, `C(b)(1)`, `Demarcation(i)`, `conditions(1)`. The old numbers resolve in the concordance.

## The classification (outline revision of October 2026)

There are 146 sections: the outline's 145, and the cover.

| Kind | Sections |
|---|---|
| (a) rule | 68 |
| (b) copy | 12 |
| (c) policy | 23 |
| (d) guidance | 23 |
| (e) mixed | 6 |
| unclear (questions) | 14 sections, 6 questions |

**The mixed sections:**

- The guide's "What happens if I don't pay my assessment?": guidance, then an edited copy of the owner's rights Civil Code 5660 lists, then 5660(a)'s capitalized statement, verbatim.
- Part A's caption: the caption, A-1 (a paraphrase of CC&Rs 2.5), and A-2.
- B-7(a): the rule, then a recommendation and a warning (guidance).
- B-16: the first sentence is an edited copy of CC&Rs 4.10(c); the second is the rule.
- B-18(c): the rule, then CC&Rs 4.18 (and 4.7) word for word.
- `B-18(C)(7)(d)`: Part C's last item, the collection policy's cover, the 5730 notice's introduction, the notice, and the application form.

**The questions,** each asked once (`jason manual --classify --asks` puts them in `jason intake`):

1. **"Who maintains exclusive use common areas?"**: "Each owner shall maintain ..." with no source. Is it guidance restating the CC&Rs, or a rule?
2. **"2. Interior Home"**: the same question, for the interior maintenance duties.
3. **"3. Utility, Water, Gas, Fire Problems"**: "Owners must pay any Sewer, Garbage & Recycling, Gas, and Electrical bills". Is this a rule, or how the utilities are billed?
4. **B-7(d)**: electric grills, and which buildings the Fire Code's exceptions reach. Is it the board's determination (a rule) or an explanation? Suggested: rule. It was in B-7's adopted text in 2022.
5. **B-18(b) and (b)(1)-(6)**: the application's contents. Are they part of the 4765 procedure (a rule) or guidance? Suggested: rule.
6. **The General Conditions of Approval**: were they adopted as rules, or are they the form's terms? Suggested: the form's terms (arch).

**Grammar leads** are rule rows where the deontic grammar reads no norm: A-2, A-2(c), A-3, B-1(a)-(c), B-4, B-9, B-12(n), B-13, B-18(d). The words use "are to be", "requires", "will be", and definitions. These are leads for `jason.community.deontic`, not questions.

## The books

| Book | Holds | Why |
|---|---|---|
| `rules` | Parts A and B | the operating rules, keeping their numbers |
| `rules.parking` | B-12, read from the parking rules Doc | the Doc is B-12 word for word; a part of the rules, not a book (one definition, procedure, and rank) |
| `disc` | Part C | 5850(a) and 5310(a)(8) have it adopted and distributed apart; it reprints the Enforcement Policy Doc with a different schedule |
| `coll` | the collection policy's cover and the 5730 notice | 5310(a)(6), 5730 |
| `arch` | the application and its conditions | the form of the 4765 procedure; B-18 stays a rule, numbered and cited as one |
| `manual` | the guide | not a governing document |

## The official rules (data/drafts/rules-and-regulations.md)

The official rules are Parts A and B as written:

- **Copies kept.** The copies the board adopted as rules' words stay, each with a note naming its source and state. They are A-1, B-6, B-7(c) and (c)(1)-(3), B-8, B-12(c), (d), (h), (j), (k), Demarcation(ii), B-16's first sentence, and B-18(c)'s second and third sentences.
- **Guidance left out.** Four guidance pieces stay in the manual, each named in a note: B-7(a)'s recommendation, "Example Permits", "Example Signage" with the permit how-to and the insert marker, and B-18(b)(6)'s "Please submit all applications via the Requests section ...".
- **Open questions.** The two in the rules (B-7(d) and B-18(b)) are printed as written, with a note.
- **Policies.** Parts C, coll, and arch are named, not reprinted.

**The adoption history** is read from the minutes and the library. No person is named in it.

| Date | Step | Parts |
|---|---|---|
| 2022-05-11 | tabled | the revised B-7 and parking drafts |
| 2022-08-30 | adopted | B-7, B-12, and the fine schedule as amended ($15 a month parking permit); rule-change record `parking-fines-2022` |
| by 2022-09-19 | delivered | the Notice of Adoption; it is also printed in the 2023 budget package |
| 2022-12-27 | no action | no other place designated for sale signs (B-5(b)) |
| 2023-04-18 | adopted | B-1 (registration), C. Enforcement a) Fine Schedule, and the Assessment Collection Policy (`owners-manual-2023`) |
| 2023-04-18 | tabled | B-5, B-14, B-15, B-16 |
| 2024-04-16 | listed | "Revise Owner's Manual and Rules: Fee Schedule, Parking Rules"; no action recorded |

Parts A and B were otherwise adopted before the minutes on file. The original rules' adoption is not found. A detector's dated versions of the manual (the PDFs in Gmail, the site copy, the Doc's revisions) go into `data/manual/owners-manual/history.json`.

## The generated manual (data/drafts/owners-manual.md)

The manual is rendered from the base template with this profile's slots: `front`, `welcome`, `contacts`, `rules`, `disc`, `coll`, and `arch`.

- **The result.** Every word is placed, in order. 159 pieces are the same as the Doc.
- **The one labeled change.** The 5730 notice is read from the statute, which restores the closing parenthesis the Doc's copy dropped ("(Section 5665 of the Civil Code)").
- **The 5660(a) statement** is also read from the statute, and it is the same.
- **B-12** is read from the parking rules Doc, and it is the same.

The diff is `data/drafts/owners-manual.diff`.

**The text has gaps where the Doc has chips.** The outline's text has no file or person chips, so the Doc's links are blanks in it. Examples: "submit a  .", "Completed .", "Email , or leave a voicemail", "the Association's adopted .", and the "[ Insert ]" markers. A rendering for owners needs the chips: read the Doc again (read-only) and carry its links.

## For the board (jason lists; the board decides)

1. **Whether publishing the rules as their own document needs adoption.**
   - The rules' subjects are in 4355(a) (common area, separate interests, discipline, the architectural procedure).
   - Under one reading, publishing them merely repeats the governing documents (4355(b)(5)).
   - Under the other, leaving the four guidance pieces out of the official text, and publishing Part C apart, changes the adopted document (4340(b)).
   - The course lawful under either reading is a 4360 notice of the extraction, with the list of what stays in the manual, and adoption at a meeting (`jason rule-change`).
2. **The six open questions** above.
3. **The copies of the CC&Rs:**
   - **Verbatim.** B-8 is CC&Rs 4.7 word for word, and B-18(c) repeats it a second time inside the rules.
   - **Edited:**
     - B-6 (4.5: "Community" for "Development");
     - B-12(c) (4.11(a)(ii): adds moving as an exception, and drops "subject to any Rules");
     - B-12(d) (4.11(a)(i): drops the board's power to permit temporary parking);
     - B-12(h) (4.12(c): "the number of vehicles for which the garage was originally designed");
     - B-12(j) and (k) (4.11(b));
     - B-16 (4.10(c)).
   - **Unverified.** B-7(c) cites "California Fire Codes § 308.1.4 adopted by the state in 2007". The code has been re-adopted since and is not on disk. Demarcation(ii) restates Vehicle Code 22658(a), which is also not on disk.
   - **Stale.** None of the copied CC&R sections has been amended. CC&Rs 6.12(a), which the guide's 5660 rights also match, is itself in the pre-2014 words (Corporations Code 8333 for Civil Code 5205).
   - Keep each rule's words, or cite the CC&Rs instead. The second choice is a rule change.
4. **The rules a higher authority displaces** (`jason conflicts`):
   - `per-day-fines` (B-18(e); also C(a)'s "Continuing Violations $25 per day" and "Failure to maintain registration $1 per day");
   - `hearing-procedure`, with the notice provision `owners-manual-due-process` (C(b)(1), (3), (5));
   - `fines-over-the-cap` (C(a): the safety violation up to $300, and the late fee and interest listed beside the fines).
   - **Leads for new rows (not yet rows):**
     - C(b)(4)(b) lists "Suspension of rights to vote", which Civil Code 5105(h)(1) reaches as `ballot-not-suspended` does the CC&Rs;
     - B-18 states no maximum time to respond to an application, which 4765(a)(1) requires.
5. **The duplicate parking rules.** B-12 and the parking rules Doc are word for word the same. Proposed: the Doc is the source (`rules.parking`), and the manual includes it.
6. **Which fine schedule is adopted.** The manual's Part C and the Enforcement Policy Doc differ:
   - the permit is $25 in the manual and $15 a month in the Doc;
   - the interest wording differs;
   - the Doc lists management fees (administrative, architectural application, demand and transfer, lender certificates, coupon book, move-in) that the manual does not;
   - the Doc prices copies of the governing documents and the statement history ($175, $35) beside "available free online"; the manual says only "Available free online".

   The 2022 minutes adopted the $15 permit. Which schedule the 2023 adoption carried is for the version timeline.

## Follow-ups for the profile (not made here)

- **The collections assignment** (`mystique/schedule.py`) cites `owners-manual#B-18(C)(7)(d)` for the collection notice. That number's span holds the notice, but the item itself is C(b)(7)(d). The notice is now `coll#notice`.
- **The aliases.** The `owners-manual` CitableDocument's aliases "Rules and Regulations" and "Operating Rules" belong to a Rules Doc once the board publishes one.
- **The guide's stale words.** The guide names one towing company and the contacts table another. The assessment answers describe the developer's first-year pro forma budget. "When the Community is totally developed" is also the developer's wording.
- **Drafting slips, kept verbatim** (extraction is not amendment): B-5(a)'s incomplete first clause, B-16's trailing "before 6:00 pm on the day of collection.", and B-12(k)'s "with the Community".
