"""Errors for any Google API call, not only Drive."""


class GoogleError(RuntimeError):
    """A Google token or API request failed."""


class GoogleAuthRequired(GoogleError):
    """No human is present, so a browser sign-in is not started. Pass interactive=True."""
