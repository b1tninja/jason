"""Google APIs used by jason. Sign-in, Drive, and Docs.

Settings such as the Keeper record UID stay on ``jason.config.Settings``.
Jason's agent calls ``open_drive``, then ``GoogleDrive.docs`` for document edits.
"""

from jason.google.docs import GoogleDocs
from jason.google.drive import GoogleDrive
from jason.google.gmail import GoogleGmail
from jason.google.sheets import GoogleSheets
from jason.google.errors import GoogleAuthRequired, GoogleError
from jason.google.scopes import (
    DOCS_SCOPE,
    DRIVE_FILE_SCOPE,
    DRIVE_READONLY_SCOPE,
    GMAIL_SCOPE,
    GOOGLE_SCOPES,
    SHEETS_SCOPE,
)
from jason.google.session import open_drive

__all__ = [
    "DOCS_SCOPE",
    "DRIVE_FILE_SCOPE",
    "DRIVE_READONLY_SCOPE",
    "GMAIL_SCOPE",
    "GOOGLE_SCOPES",
    "GoogleAuthRequired",
    "GoogleDocs",
    "GoogleDrive",
    "GoogleGmail",
    "GoogleSheets",
    "GoogleError",
    "SHEETS_SCOPE",
    "open_drive",
]
