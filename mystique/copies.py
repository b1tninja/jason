"""Which copy of a document to read first, when the same invoice or bill reached the association more than one way.

The issuer's own record comes first: the i-doxs and SMUD portal PDFs and the vendor portal's invoices are what the
issuer holds, fetched by jason, and the misfiled-download check verifies them. An email attachment is the issuer's
original file, sent to the association. A PayHOA attachment is a file a person chose and attached, which is why a bill
can hang on the wrong payment. A paper scan is read by OCR. The library is a person's filing.

Every copy stays in the catalog; the order only chooses which one is read.
"""

from __future__ import annotations

from jason.community.copies import Channel

COPY_PRIORITY: tuple[Channel, ...] = (
    Channel.ISSUER_PORTAL,
    Channel.EMAIL,
    Channel.PAYHOA,
    Channel.PAPER,
    Channel.LIBRARY,
)
