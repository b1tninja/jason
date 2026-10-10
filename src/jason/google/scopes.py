"""Scopes requested together on one consent."""

DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
# Full Drive access, granted by the board (September 29, 2026) so jason can file documents into the folders they belong
# in (a move, when a person asks). drive.file alone only reaches files jason created or opened.
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
DOCS_SCOPE = "https://www.googleapis.com/auth/documents"
SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
# Added September 29, 2026 with the board's APIs: the board calendar (meetings, hearings, deadlines); who changed,
# moved, or deleted a file (for legal holds); Drive label definitions; drafts in Gmail (Google has no drafts-only scope:
# gmail.compose could also send, and jason only ever creates drafts; a person sends); and Forms and their responses.
CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"
DRIVE_ACTIVITY_SCOPE = "https://www.googleapis.com/auth/drive.activity.readonly"
DRIVE_LABELS_SCOPE = "https://www.googleapis.com/auth/drive.labels.readonly"
GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
FORMS_BODY_SCOPE = "https://www.googleapis.com/auth/forms.body"
FORMS_RESPONSES_SCOPE = "https://www.googleapis.com/auth/forms.responses.readonly"
GOOGLE_SCOPES = (
    DRIVE_SCOPE,
    DRIVE_READONLY_SCOPE,
    DRIVE_FILE_SCOPE,
    DOCS_SCOPE,
    SHEETS_SCOPE,
    GMAIL_SCOPE,
    CALENDAR_EVENTS_SCOPE,
    DRIVE_ACTIVITY_SCOPE,
    DRIVE_LABELS_SCOPE,
    GMAIL_COMPOSE_SCOPE,
    FORMS_BODY_SCOPE,
    FORMS_RESPONSES_SCOPE,
)

# Google Photos, on a token of its own (secrets/google-photos-token.json) so adding it never asks Drive to consent again.
# The Picker reads only what a person picks; the Library API since March 31, 2025 reaches only what jason created.
PHOTOS_PICKER_SCOPE = "https://www.googleapis.com/auth/photospicker.mediaitems.readonly"
PHOTOS_APPEND_SCOPE = "https://www.googleapis.com/auth/photoslibrary.appendonly"
PHOTOS_READ_APP_SCOPE = "https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata"
PHOTOS_EDIT_APP_SCOPE = "https://www.googleapis.com/auth/photoslibrary.edit.appcreateddata"
PHOTOS_SCOPES = (PHOTOS_PICKER_SCOPE, PHOTOS_APPEND_SCOPE, PHOTOS_READ_APP_SCOPE, PHOTOS_EDIT_APP_SCOPE)

# Google Tasks, on a token of its own (secrets/google-tasks-token.json): the board's action items as a task list.
# Enabled by the treasurer September 29, 2026.
TASKS_SCOPE = "https://www.googleapis.com/auth/tasks"
TASKS_SCOPES = (TASKS_SCOPE,)

# Google Vault, on a token of its own (secrets/google-vault-token.json): matters and legal holds.
VAULT_SCOPE = "https://www.googleapis.com/auth/ediscovery"
VAULT_SCOPES = (VAULT_SCOPE,)

# What each scope is used for, and the API to enable in the Cloud project for it (``jason google scopes``;
# docs/google-workspace-setup.md). One line each; kept here as data so the command and the guide agree with the code.
SCOPE_PURPOSES: dict[str, tuple[str, str]] = {
    DRIVE_SCOPE: ("Google Drive API", "read, create and file documents in the association's folders"),
    DRIVE_READONLY_SCOPE: ("Google Drive API", "read files the signed-in account can see"),
    DRIVE_FILE_SCOPE: ("Google Drive API", "work with files jason created or opened"),
    DOCS_SCOPE: ("Google Docs API", "read and write Docs: agendas, letters, templates"),
    SHEETS_SCOPE: ("Google Sheets API", "read and write the registers kept in Sheets"),
    GMAIL_SCOPE: ("Gmail API", "read the association mailbox into the mail catalog"),
    CALENDAR_EVENTS_SCOPE: ("Google Calendar API", "meetings, hearings and deadlines on the board calendar"),
    DRIVE_ACTIVITY_SCOPE: ("Drive Activity API", "who changed, moved or deleted a file (legal holds)"),
    DRIVE_LABELS_SCOPE: ("Google Drive Labels API", "read Drive label definitions"),
    GMAIL_COMPOSE_SCOPE: ("Gmail API", "create drafts for a person to review and send (jason never sends)"),
    FORMS_BODY_SCOPE: ("Google Forms API", "create and edit forms"),
    FORMS_RESPONSES_SCOPE: ("Google Forms API", "read form responses"),
    PHOTOS_PICKER_SCOPE: ("Google Photos Picker API", "read only the photos a person picks"),
    PHOTOS_APPEND_SCOPE: ("Photos Library API", "add photos to jason's own albums"),
    PHOTOS_READ_APP_SCOPE: ("Photos Library API", "read what jason created"),
    PHOTOS_EDIT_APP_SCOPE: ("Photos Library API", "edit what jason created"),
    TASKS_SCOPE: ("Google Tasks API", "the board's action items as a task list"),
    VAULT_SCOPE: ("Google Vault API", "matters and legal holds"),
}
