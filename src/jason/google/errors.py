"""Errors for any Google API call, not only Drive."""


class GoogleError(RuntimeError):
    """A Google token or API request failed."""


class GoogleAuthRequired(GoogleError):
    """No human is present, so a browser sign-in is not started. Pass interactive=True."""


class GoogleHttpError(GoogleError):
    """An API request Google answered with an error: its HTTP ``status`` and Google's first ``reason``
    (``exportSizeLimitExceeded``, ``fileNotDownloadable``, ``badRequest``), when it gave one."""

    def __init__(self, message: str, *, status: int = 0, reason: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.reason = reason


class GoogleExportTooLarge(GoogleHttpError):
    """Google refused to export a file because the export would be over its limit (10 MB)."""
