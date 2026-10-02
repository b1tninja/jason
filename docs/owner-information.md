# The owner information cycle (Civil Code 4040, 4041)

Each year the association asks every owner how they want to receive notices, and it delivers by the answer. This page
is the whole cycle in one place: the law, where each answer lives, the channels owners answer through, the commands,
and the rules that keep newer information from being overwritten.

## The law

| Duty | Section |
|---|---|
| Each owner gives, each year, their preferred delivery method (mail, email, or both), a secondary method, a legal representative, and the unit's occupancy | 4041(a) |
| The association asks each owner each year, and enters the answers in its books at least 30 days before the annual budget report and policy statement | 4041(b)(1) |
| The request says an email address is optional, and how to change the answer | 4041(b)(2) |
| An individual notice goes by the owner's choice; with no valid choice, by first-class mail to the address on the books | 4040(a) |
| A secondary address gets copies of the annual reports and the assessment collection notices | 4040(b) |
| A general notice is posted, and delivered individually to an owner who asked for that | 4045 |

## Where each answer lives: PayHOA

PayHOA is the record, because 4041(b)(1) puts the answers in the association's books. Owners also sign in there and
change their own details. Everything else is a way to collect an answer that a person then enters in PayHOA.

| What | In PayHOA | Kept by |
|---|---|---|
| Email, phone, mailing address | the member profile | the owner |
| Notice delivery: email, mail, or both | member tags "Notices by Email", "Notices by Mail" | the board, from the owner's answer |
| Answered this cycle | member tag "Owner Info 2027" | the board |
| Occupancy | unit tags "Rental", "Owner Occupied", "Vacant" (untagged is not known) | the board |
| A second address (4041(a)(2)) | an additional owner record on the unit, added without an invitation, tagged "Additional Deliveries": its email gets the 4040(b) copies by email, its mailing address by mail (either may be empty) | the board |
| A legal representative (4041(a)(3)) | their own person record on the unit, added without an invitation, tagged "Legal Representative": name, email, phone, and address are its profile. A contact, never sent notices | the board, from the answer |
| An address the owner hasn't confirmed (fiscal 2027: the county roll's mailing address where PayHOA had another) | an Additional Deliveries record named exactly as the owner, tagged also "Unconfirmed Address": it gets the owner-information request by mail and nothing else (`NoticeRule.unconfirmed_copies`). The owner's answer confirms it (the tag comes off) or drops it (the record is moved out); unanswered, it is moved out when the cycle closes | the board |
| The owner's property manager | an other contact ("Name (Company), property manager"), unless the owner's form asks for copies or a contact: then the manager's own person record, added without an invitation, tagged "Property Manager" and "Additional Deliveries" or "Legal Representative" | the board, from the owner's answer |
| The membership-list opt-out (Civil Code 5220) | member tag "Membership List Opt-Out" | the board, from the answer |
| Paper billing statements | unit tag "Paper Statements" (PayHOA's billing; for an owner since before PayHOA, also read as a written choice of mail) | the board |

No custom fields. PayHOA's are free text with no type or check, so an answer comes in through a form and jason (or an
admin) sets the tags it calls for: each tag in `mystique/tags.py` names the form question it follows (`answer`).

The vocabulary is `mystique/tags.py`: `PAYHOA_TAGS` and `PAYHOA_FIELDS`. A tag or field marked `exists=False` is
proposed; it is created when first written.

**Only the tags decide delivery.** An owner with no delivery tag gets first-class mail, as the law requires. The tag
"Notices by Mail" makes that visible to PayHOA's own filters.

**An earlier answer** is shown to the owner and confirmed this cycle. It sets the delivery tags as the owner's written
election only when all of these hold (`EARLIER_ELECTIONS` in `mystique/forms.py`):
- the email on the form matches the email PayHOA has for that owner, so it was the owner, at a working address;
- it was sent after the unit's latest deed;
- it is no more than two years old;
- the owner has no delivery election in PayHOA, so nothing newer exists.

Such an owner is still asked to confirm, and gets the year's "Owner Info" tag only when they do. An earlier answer never
changes occupancy tags: tags carry no dates, so there is no way to tell which is newer.

Mystique's findings are in the private notes (mystique/notes/owner-information.md).

## The channels

| Channel | Who answered | How it reaches PayHOA |
|---|---|---|
| The PayHOA form (`jason forms --payhoa owner-info --yes`) | signed in: the member and the unit are known | `jason owner-info --payhoa` reads the submissions |
| The fillable PDF, emailed back | the signature line | `jason forms --read` reads it; a person confirms who sent it |
| The paper form, mailed back | the signature | typed in by a person |
| An earlier outside form (the 2024 Google Form) | unverified | recorded for the owner to see; confirmed this cycle |

## The cycle, as commands

```bash
jason owner-info                       # the deadlines, each owner's standing, and the next actions
jason owner-info --out ledger.csv      # one row an owner (names; no addresses)
jason owner-info --payhoa              # include the PayHOA form's signed-in submissions (live)
jason owner-info --apply               # read PayHOA live and list the writes, each with its reason
jason owner-info --apply --yes         # write them
jason delivery --notice annual-policy-statement --ids ids.json   # who receives a notice, and how
```

The dates are `OWNER_INFO_CYCLE` in `mystique/forms.py`, one cycle per fiscal year:
- the day the solicitation opens;
- the day owners are asked to answer by;
- the day the answers are entered, at least 30 days before the reports;
- the day the annual reports go out.

## Never over newer information

An answer may change PayHOA only if all three dates allow it:

| Date | Rule |
|---|---|
| The unit's latest recorded deed (county index) | An answer sent before it belongs to the prior title, and changes nothing. |
| The owner's last profile update | If the owner updated their profile after the answer, the profile's email and address stand. |
| The answer's cycle | Only this cycle's answer sets tags. Last year's and older answers are recorded and confirmed. |

The earlier-answer field is written only where it is empty or holds an older answer jason wrote. A value with no
answer date was set by a person, and stays.

`--apply` reads PayHOA live before it plans, never from the stored catalog. It adds a delivery tag only where an owner
has none, applies a this-cycle answer's tag changes, and writes the field under the rule above. A tag is removed only
when a this-cycle answer asks for it.

## Occupancy and rental approval are different facts

| Fact | In PayHOA | Source |
|---|---|---|
| The unit is rented now (4041(a)(4)) | unit tag "Rental" | the owner's answer, or the board's knowledge |
| The board approved the rental (the declaration's leasing section) | unit tag "Rental Approved"; the date, lease term, and source are in the board's resolution or minutes | the owner's written application, or the board's recognition of an existing rental |

The declaration's leasing section sets the rules, kept in `mystique/leasing.py`:
- a cap on the share of units rented at once, which Civil Code 4741(b) keeps at 25% or more;
- a minimum lease term;
- a written application;
- how long an approval carries through a vacancy.

`jason rentals` sets the two tags side by side and counts rented units against the cap. Whether to recognize existing
rentals with no approval on file, or to ask their owners to apply, is the board's decision with counsel. jason only
lists them. Proof of a tenant's criminal background check or credit report, where the declaration asks for it, is a
sensitive record: it stays out of jason's shared catalogs, and counsel should confirm its use under fair housing law.

Mystique's findings are in the private notes (mystique/notes/owner-information.md).

## Sending the request

`jason owner-info --send-plan` writes what each owner will be sent (an emailed copy, a mailed letter, or both) and what each copy carries. It reads live and shows no addresses.

- **Email:** each owner with a working email gets their own copy of the form, filled from the record. Where they have made no choice, the association's suggestions (`SUGGESTED_CHOICES` in `mystique/forms.py`) are filled in too: email for an owner who reads the association's email, and a ballot method. Nothing is recorded until the form comes back.
- **Letter:** the same letter for everyone: the cover letter and the blank form.

**A mailing address that is the unit's own.** The form asks for a mailing address only if it is not the unit's, but owners often write their unit anyway, sometimes with a short form, a misspelled street, or an apartment number after it. jason reads such an address as the unit (`owner_prefill.is_unit_address`: the same street number and street with a typo allowed, in the unit's city or ZIP), so the unit's own address is used. It is not a separate mailing address, not a change, and not a sign the owner lives elsewhere. A mailing address at another unit in the community is read as the owner living in that unit.

The plan also reads each unit's occupancy signal. When no owner's mailing address is the unit, the owners most likely live elsewhere: a rental, a vacant unit, or a second home. A unit tagged Owner Occupied whose owners all mail elsewhere, an untagged one, or a Rental whose owner's address is the unit is listed as a lead to confirm.

It goes out as two batches ([batches.md](batches.md)):
1. **The Mailroom** (`jason owner-info --mail-batch`): one send per building to the owners the law sends mail. PayHOA sends co-owners at one address one letter. It folds an owner's two units in one send into one letter, so a second unit goes in a send of its own.
2. **The email supplement** (`jason owner-info --email-batch`): each owner's own filled copy, one at a time.
