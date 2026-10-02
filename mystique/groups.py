"""The association's Google Groups on mystiquecommunity.com, as their List-ID and X-BeenThere headers name them in the
association's Gmail (read September 30, 2026, over 4,723 messages). A group's members and settings are in the Workspace
admin console, not here. hoa@, amazon@, and voicemail@ carry no group headers: they are aliases or mailboxes."""

from jason.community.groups import GoogleGroup, GroupPurpose

GROUPS: tuple[GoogleGroup, ...] = (
    # The City's and SMUD's eBills, Chase's alerts, GovHub, the alarm company, and the insurance agency's invoices. The
    # group rewrites a strict-DMARC sender's From ("'<sender's name>' via Accounts Payable"): 482 of 1,190.
    GoogleGroup("ap@mystiquecommunity.com", "Accounts Payable", GroupPurpose.ACCOUNTS_PAYABLE),
    # Board members among themselves, and the pest vendor's reports, e-signature requests, and the construction and
    # engineering firms.
    GoogleGroup("board@mystiquecommunity.com", "Board", GroupPurpose.BOARD, confidential=True),
    # The manager's mail: vendors, the CPA (hoacpa.com), the title company, and owners' questions.
    GoogleGroup("management@mystiquecommunity.com", "Management", GroupPurpose.MANAGEMENT),
    # PostScanMail's delivery and scan notices and USPS.
    GoogleGroup("mail@mystiquecommunity.com", "Mail", GroupPurpose.MAIL),
)
