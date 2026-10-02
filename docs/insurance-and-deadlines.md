# Insurance terms and recurring deadlines

Two views built from what jason already keeps on disk: the mail (`data/mail`), PayHOA's transactions (`data/payhoa/transactions.json`), and the reserve studies. Neither calls PayHOA, PostScanMail, or a carrier, and neither buys, renews, files, or pays anything.

## Insurance (`jason insurance`, `insurance_review`)

The policy sheet is the specification: `mystique/insurance.py` has one `Policy` per line of coverage. Each policy records:

- its kind, and its building for flood;
- the number in force and the numbers of earlier terms (`prior_numbers`);
- the end of the term in force (`renewal`);
- the carrier, the program or wholesaler, and the agent;
- the PayHOA categories its premium is booked to.

A number can change every term: a suffix goes from `-00` to `-01`, or the number starts with the term's year. So the letters are matched on every number the policy has carried, with letters and digits only and the letter O read as zero.

For each policy the review gives:

- **The letters** that print one of its numbers, with renewal bills, conditional renewals, non-renewals, cancellations, and claims picked out by their headings.
- **Premiums by term.** A term runs from 90 days before its start to 275 days after, because premiums are often paid ahead or financed monthly. A flood payment is placed on the building whose NFIP policy number (current or prior) its bank line carries ("IND NAME:<ASSOCIATION NAME> <payee id>"), else the building its memo or an attachment's name gives ("Invoice Flood Bldg 5 24-25.pdf"), else the building whose renewal bill prints its amount. When the line and the names say nothing, the attached notice is read: its text layer if it reads as characters, else the OCR text `jason invoices` cached for the same file (`best_text`, the vision model's reading first). Some renewal notices are drawn with a font that has no character map, so their text layer extracts as glyph codes; for those, the vision model's reading supplies the policy number and the building. Payments none of this places are listed separately.
- **A standing:**
  - in term;
  - renewal notice received;
  - next term paid;
  - the term ended with no premium in PayHOA for the next one.

  A renewal notice that states an earlier term end than the sheet is raised, since the sheet may carry the next term's date. So is a conditional renewal inside the current term.
- **Claims** the mail acknowledges: date of loss, claim number, and policy.

## Recurring deadlines (`jason deadlines`, `association_calendar`)

`mystique/obligations.py` lists the association's recurring deadlines as `Obligation` rows. Each row has an authority and a due rule:

- a **fixed yearly date**, such as a property tax installment delinquent after December 10;
- an **interval** from the last time it was done, such as a balcony inspection every nine years.

It also names the evidence that shows it done: PayHOA payments booked to its categories, or to a payee carrying its words. Money coming in (a wire, a deposit) is never evidence. Insurance terms come from the insurance review. The reserve study's three-year site visit comes from the studies on disk.

A fixed deadline is judged for each year PayHOA covers: done on time, done late (and by how many days), or no evidence. The next deadline is:

- **due soon** within 60 days;
- **overdue** once it passes with no evidence.

A deadline no store shows, such as the annual budget report or the reviewed financial statement, is listed as such, not guessed. Income tax payments are listed and not judged: they mix estimated payments and balances due, and a date alone does not say which deadline a payment met.

A payment is evidence, not proof. The filing, the inspection report, the receipt, or the notice is the record; a payment PayHOA posted days after the county received it can read as late when it was not.

This association's findings are in its private notes (mystique/notes/insurance-and-deadlines.md).
