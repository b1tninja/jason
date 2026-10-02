"""PostScanMail: the virtual mailbox that receives, scans, and holds the association's paper mail."""

from jason.postscanmail.client import PostScanMail, PostScanMailError
from jason.postscanmail.models import MailItem, MailKind, Urgency, classify

__all__ = ["PostScanMail", "PostScanMailError", "MailItem", "MailKind", "Urgency", "classify"]
