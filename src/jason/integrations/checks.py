"""An integration's check: the read that proves it works (docs/integrations-design.md: a connection counts as connected
only after a read succeeds).

- **From disk** (always): what ``connections.state_of`` reads: the credential configured or not, the vault's login, and
  each source's last read and failures from the Status screen's rows. No service is called.
- **Live** (``--live``, a person at a terminal): one small read through the service, where one exists today: the
  Drive root and one Gmail message id (Google Workspace), the organization among the account's (PayHOA), one meeting
  (Zoom), the model server's version (local models). It signs in non-interactively, so a missing sign-in fails fast
  and is recorded as needing one. Its outcome, masked, is recorded on the connection.

Nothing here prints or keeps a secret value: an error's words are masked (``jason.approvals.audit.mask``).
"""

from __future__ import annotations

import re
from typing import Any, Callable

from jason.integrations.registry import ConnectionState

_SIGN_IN = re.compile(r"AuthRequired|AuthError|not signed in|jason login|--interactive|sign in again|401|"
                      r"invalid_grant|unauthori[sz]ed", re.IGNORECASE)


def _google(agent: Any) -> str:
    agent.drive(interactive=False).root_id()
    agent.gmail(interactive=False).list_messages("", max_results=1)
    return "the Drive root and one Gmail message id were read"


def _payhoa(agent: Any) -> str:
    client = agent.payhoa()
    orgs = client.list_organizations()
    want = agent.org_id
    if not any(str(o.get("id")) == str(want) for o in orgs if isinstance(o, dict)):
        raise LookupError(f"signed in, but the profile's organization is not among the {len(orgs)} the account sees")
    return f"signed in; the profile's organization is among the {len(orgs)} the account sees"


def _zoom(agent: Any) -> str:
    client = agent.zoom()
    try:
        next(iter(client.meetings()), None)
    finally:
        client.close()
    return "a token was issued and the meetings were listed"


def _local_models(agent: Any) -> str:
    from jason.local_ai import status

    s = status()
    if not s.get("ollama", {}).get("up"):
        raise ConnectionError("the model server did not answer (jason local-ai)")
    return f"the model server answered ({len(s['ollama'].get('installed') or {})} models installed)"


LIVE: dict[str, Callable[[Any], str]] = {
    "google-workspace": _google,
    "payhoa": _payhoa,
    "zoom": _zoom,
    "local-models": _local_models,
}

NEEDS_AGENT = {"google-workspace", "payhoa", "zoom"}


# Anything shaped like a credential an error might echo: a bearer token, a Google access or refresh token, a long key.
SECRET_SHAPED = re.compile(r"(?i)bearer\s+\S+|ya29\.[\w.-]+|1//[\w.-]+|(?<![\w/\\.-])[A-Za-z0-9_-]{32,}(?![\w/\\.-])")


def _mask(text: str) -> str:
    from jason.approvals.audit import mask

    return SECRET_SHAPED.sub("[redacted]", str(mask(str(text or ""))))[:300]


def run_live(key: str, agent: Any, checks: dict[str, Callable[[Any], str]] | None = None
             ) -> tuple[bool, str, ConnectionState]:
    """Run the live check ``key``: (ok, its words masked, the state it shows). A sign-in failure is "needs sign-in",
    any other failure "failing"; neither is retried."""
    fn = (checks if checks is not None else LIVE)[key]
    try:
        words = fn(agent)
    except Exception as exc:  # noqa: BLE001 - a check reports its failure; it never raises past the command
        said = f"{type(exc).__name__}: {exc}"
        state = ConnectionState.NEEDS_SIGN_IN if _SIGN_IN.search(said) else ConnectionState.FAILING
        return False, _mask(said), state
    return True, _mask(words), ConnectionState.CONNECTED


__all__ = ["LIVE", "NEEDS_AGENT", "SECRET_SHAPED", "run_live"]
