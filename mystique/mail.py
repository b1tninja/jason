"""Where letters to Mystique are addressed, and which address is the one to keep on file.

The association's mailing address is its PostScanMail box, 901 H St Ste 120, PMB 188, Sacramento,
CA 95814: the address on the current mail and on the PostScanMail account (read September 29, 2026).
3000 Macon Dr is the association's site address (the common-area parcel 201-1170-018-0000, and the
service address on its utility accounts); no mail is received there. A letter a sender addresses there
never arrives, so the box cannot show it: the mailing address a counterparty has on file is read from
its own bills and statements instead. A letter addressed to The Helsing Group, a prior manager, means
the sender has an old address on file, and one to 901 H St without "PMB 188" reaches the box only if
the mail center routes it by name: each should be given the full current address. The Helsing addresses are the ones its letters to and for the association
carried: 6101 Bollinger Canyon Rd Ste 200 and 4000 Executive Pkwy Ste 100, San Ramon, and 8340
Auburn Blvd Ste 100, Citrus Heights.

The addresses were confirmed by a board member on September 29, 2026.

Words are matched against the addressee block (the lines after the association's name); the first
row that matches wins.
"""

from __future__ import annotations

from jason.postscanmail.models import AddressKind, MailAddress

MAIL_ADDRESSES: tuple[MailAddress, ...] = (
    # PostScanMail's building holds many boxes: the PMB number is what routes a letter to the association's.
    MailAddress(AddressKind.CURRENT, "PostScanMail box, 901 H St Ste 120 PMB 188, Sacramento", ("901 H ST", "PMB 188", "PMB188", "901 H STREET"),
                requires=("PMB 188", "PMB188", "PMB #188", "PMB# 188", "PMBI88", "PMBL88", "PMB 1 88"), zip="95814"),
    MailAddress(AddressKind.FORMER_MANAGER, "The Helsing Group, San Ramon", ("BOLLINGER CANYON", "EXECUTIVE PKWY", "EXECUTIVE PARKWAY", "SAN RAMON")),
    MailAddress(AddressKind.FORMER_MANAGER, "The Helsing Group, Citrus Heights", ("AUBURN BLVD", "CITRUS HEIGHTS")),
    MailAddress(AddressKind.PROPERTY, "the site, 3000 Macon Dr (no mail is received there)", ("3000 MACON",)),
)

# The association's name word as letters print it: OCR reads "Mystique" as "lystique" or "Mystque".
NAME_PATTERN = r"m?y?st[il1]?que|mystique"

# The association's own email domain (Google Workspace): its board members' and groups' addresses, never a counterparty.
EMAIL_DOMAINS: tuple[str, ...] = ("mystiquecommunity.com",)

# What Gmail prints at the head of a message printed to PDF ("<name> Mail - <subject>"): the Workspace organization's
# name, and the one it had before it was renamed (files printed then still carry it).
GMAIL_PRINT_NAMES: tuple[str, ...] = ("Mystique Community Association", "Mystique Community Organization")
