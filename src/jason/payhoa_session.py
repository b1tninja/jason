"""Back-compat wrapper — prefer ``Jason.payhoa()``."""

from __future__ import annotations

from pathlib import Path

from payhoa import PayhoaClient

from jason.config import Settings
from jason.secrets import get_payhoa_credentials


def authenticated_payhoa_client(
    *,
    keeper_config: str | Path | None = None,
    site_id: int = 2,
) -> PayhoaClient:
    """Create an authenticated PayhoaClient (uses Settings / .env)."""
    settings = Settings.load()
    config = keeper_config or settings.keeper_config
    creds = get_payhoa_credentials(
        settings=settings,
        config=config,
    )
    client = PayhoaClient(site_id=site_id)
    client.login(creds.email, creds.password, totp_code=creds.totp_code)
    return client
