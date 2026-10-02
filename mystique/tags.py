"""Mystique's PayHOA tags: what each one means, on units or on members.

In use as of October 1, 2026 (read from the PayHOA catalog): the eight building tags; "Rental" (16 units), "Paper
Statements" (12 units), and "Paper Ballot" (1 unit) on units; "Board Member" on members; and PayHOA's own "Missing
Email Address" and "Never Logged In" on members.

For the Civil Code 4041 answers: a notice election is per owner, so it is a member tag ("Notices by Email" and "Notices
by Mail", created October 1, 2026), and co-owners may choose differently; occupancy is per unit ("Rental", "Owner
Occupied", "Vacant"; no occupancy tag means not known). The mailing address is the member profile's, which PayHOA's
Mailroom uses; a second address is an additional owner record on the unit, tagged "Additional Deliveries"; a legal
representative is their own person record tagged "Legal Representative"; the membership-list opt-out is a member
tag set from its form answer (``answer``).
No custom fields: PayHOA's are untyped text. "Owner Info <year>" marks the owners who answered that year's
solicitation, so a reminder can go to the rest. ``exists=False`` marks what PayHOA does not have yet.
"""

from __future__ import annotations

from jason.community.symbols import Building
from jason.community.tags import PayhoaField, PayhoaTag, TagPurpose, TagScope

from .forms import OWNER_INFO_CYCLE

U, M = TagScope.UNIT, TagScope.MEMBER

# The owners who answer this year's solicitation are tagged "Owner Info <year>".
OWNER_INFO_YEAR = OWNER_INFO_CYCLE.year

PAYHOA_TAGS: tuple[PayhoaTag, ...] = (
    *(PayhoaTag(f"Building {int(b)}", U, TagPurpose.BUILDING, str(int(b))) for b in Building),
    PayhoaTag("Rental", U, TagPurpose.OCCUPANCY, "Rented out", answer="occupancy",
              note="occupancy (4041(a)(4)): the unit is rented now, whether or not the board approved it"),
    PayhoaTag("Rental Approved", U, TagPurpose.RENTAL_APPROVAL, exists=False,
              note="the board approved the owner's written application under CC&Rs 4.15, or recognized an existing "
                   "rental; it carries through a vacancy of up to 60 days (4.15(i)). The date and source are the unit "
                   "board's resolution or minutes, not PayHOA"),
    # An address the owner has not confirmed (the county roll's mailing address for them, October 1, 2026): kept on an
    # Additional Deliveries record that also carries this tag, so it gets the owner-information request and nothing
    # else (NoticeRule.unconfirmed_copies). The owner's answer confirms it (the tag comes off) or drops it (the record
    # is moved out); unanswered, it is moved out when the cycle closes.
    PayhoaTag("Unconfirmed Address", M, TagPurpose.UNCONFIRMED,
              note="an Additional Deliveries record whose address the owner has not confirmed: the owner-information "
                   "request only"),
    # An owner's property manager, when the owner has asked (the owner-information form's property manager section,
    # October 1, 2026): the manager's own person record on the unit, added without an invitation, carrying this tag and
    # the role the owner chose: Additional Deliveries (copies of notices, 4041(a)(2)) or Legal Representative (contact in
    # the owner's absence, 4041(a)(3)). Never an owner: no vote, no membership-list entry, out of owner counts and
    # jason's sends (tags.NOT_OWNERS). PayHOA treats every person on a unit as an owner, so without the owner's say-so
    # the manager stays an other contact ("Name (Company), property manager") and gets nothing.
    PayhoaTag("Property Manager", M, TagPurpose.PROPERTY_MANAGER, exists=False,
              note="the owner's property manager, a person record the owner asked for; it also carries Additional "
                   "Deliveries or Legal Representative, the role the owner chose"),
    # Made October 1, 2026 on the 19 units whose owners said so (2024-26 answers, screened against the county roll).
    PayhoaTag("Owner Occupied", U, TagPurpose.OCCUPANCY, "Owner-occupied", answer="occupancy",
              note="occupancy (4041(a)(4)): an owner said they live in the unit; no occupancy tag means not known"),
    PayhoaTag("Vacant", U, TagPurpose.OCCUPANCY, "Vacant (not occupied)", exists=False, answer="occupancy"),
    PayhoaTag("Paper Statements", U, TagPurpose.STATEMENTS, "paper",
              note="billing statements by mail; not a 4041 notice election, though an owner who asked for paper "
                   "statements may want notices by mail too"),
    PayhoaTag("Paper Ballot", U, TagPurpose.BALLOT, "Paper ballot by mail", answer="ballots",
              note="the Election Rules' paper ballot choice"),
    PayhoaTag("Notices by Email", M, TagPurpose.NOTICE_DELIVERY, "email",
              note="4041(a)(1)(B); the member's consent to email delivery"),
    PayhoaTag("Notices by Mail", M, TagPurpose.NOTICE_DELIVERY, "mail", note="4041(a)(1)(A)"),
    # A legal representative (4041(a)(3)) is their own person record on the unit, added without an invitation to sign
    # in: their name, email, phone, and address are that record's profile. Someone to contact in the owner's extended
    # absence, not a recipient of notices: no delivery tag, no vote, left out of owner counts.
    PayhoaTag("Legal Representative", M, TagPurpose.LEGAL_REPRESENTATIVE, exists=False,
              note="4041(a)(3): the person record of an owner's legal representative (power of attorney, or whom to "
                   "contact in the owner's extended absence)"),
    PayhoaTag("Membership List Opt-Out", M, TagPurpose.MEMBERSHIP_LIST,
              "Opt me out of sharing my name and addresses (Civil Code §5220)", exists=False, answer="membership-list",
              note="5220: leave the owner's name and addresses out of the membership list; requests to contact them go "
                   "through the association"),
    # A second address an owner gives (4041(a)(2)) is an additional owner record on the unit, added without an
    # invitation to sign in: PayHOA's Mailroom mails owners only, and the tag lets a broadcast or the Mailroom select
    # these records alone. The record holds only what the owner gave, an email, a mailing address, or both, and its
    # fields are its channel. Not an owner of title: no election, no vote, left out of owner counts, and never given an
    # owners' delivery tag (the owners' filters would select it).
    PayhoaTag("Additional Deliveries", M, TagPurpose.SECONDARY_CONTACT, exists=False,
              note="an additional owner record for the second address an owner gave (4041(a)(2)): the 4040(b) copies "
                   "go to its email, its mailing address, or both"),
    PayhoaTag("General Notices Individually", M, TagPurpose.GENERAL_INDIVIDUALLY, exists=False,
              note="4045(b): the member asked for general notices by individual delivery"),
    PayhoaTag(f"Owner Info {OWNER_INFO_YEAR}", M, TagPurpose.ANSWERED, str(OWNER_INFO_YEAR), exists=False,
              note="answered the solicitation for this year (4041(b)(1))"),
    PayhoaTag("Board Member", M, TagPurpose.ROLE),
    PayhoaTag("Missing Email Address", M, TagPurpose.SYSTEM, managed="payhoa"),
    PayhoaTag("Never Logged In", M, TagPurpose.SYSTEM, managed="payhoa"),
)


# Custom fields: none in use. PayHOA's are free text with no type or check, so the answers live in tags (set from each form
# answer by jason or an admin), the profile (mailing address, email), and person records on the unit tagged
# "Additional Deliveries" (a second address) or "Legal Representative" (who to contact). A field is fine for one specific value of
# one member or unit, where no tag or profile entry can hold it; never a summary sentence (one, "Notice preference on
# file (earlier answer)", was created and deleted on October 1, 2026).
PAYHOA_FIELDS: tuple[PayhoaField, ...] = ()
