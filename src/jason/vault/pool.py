"""One Keeper session per community per process (docs/integrations-design.md, docs/tenancy.md section 8).

A Keeper login plus a full ``sync_down`` is the expensive part of reading the vault. A one-shot command pays it once;
a long-lived process (``jason serve``, the daemon, the web sign-in) used to pay it per request or per ``Jason``. The
pool hands every user in a process the same ``VaultSession`` for its (community, interactive) key.

- **Lazy.** The login happens on first use of the session (``online``, ``load_record``, ...), not in ``session_for``.
- **Leased.** ``close()`` and ``with`` on a pooled session do nothing: the pool owns it and closes it at interpreter
  exit (``atexit``) or by ``close_all()``.
- **Idle.** After ``JASON_KEEPER_IDLE_SECONDS`` (default 900; 0 = never) without use the session is closed and the next
  use logs in again, so a long-running server does not hold a stale vault, and a revoked device is noticed.
- **Refresh.** ``session.refresh(min_interval)`` re-syncs (never re-logs-in) at most once per interval, so a write by
  another process shows up.
- **Errors are not cached.** A failed login leaves no half-open session. The next use tries again, but a
  non-interactive session not sooner than ``FAILURE_COOLDOWN`` seconds after a failure (no hammering of Keeper with
  failing logins); it then raises ``KeeperAuthRequired`` without calling Keeper. A person's interactive retry is
  never held back.
- **One community.** The key's community comes from ``jason.community.profile.profile_name()``. A process serves one
  community, so a request for another is refused (``CommunityMismatch``): a session is never reused across
  communities (docs/tenancy.md section 2).
- **No secrets.** The pool stores no credential beyond what the session already holds, logs only counts and the
  community key, and ``stats()`` is counts only.
"""

from __future__ import annotations

import atexit
import logging
import os
import threading
import time
from typing import Any, Callable

from jason.secrets import KeeperAuthRequired, VaultSession

log = logging.getLogger(__name__)

DEFAULT_IDLE_SECONDS = 900
FAILURE_COOLDOWN = 30.0
DEFAULT_REFRESH_SECONDS = 60.0

_clock: Callable[[], float] = time.monotonic   # tests replace it

_lock = threading.RLock()
_sessions: dict[tuple[str, bool], PooledVaultSession] = {}
_stats = {"logins": 0, "reuses": 0, "closes": 0, "failures": 0}
_atexit_registered = False


class CommunityMismatch(RuntimeError):
    """A Keeper session was asked for a community other than the one this process serves."""


def idle_seconds() -> float:
    """``JASON_KEEPER_IDLE_SECONDS`` (environment, .env, user config); default 900; 0 means never."""
    from jason.config import _env_value

    raw = _env_value("JASON_KEEPER_IDLE_SECONDS")
    if not raw:
        return float(DEFAULT_IDLE_SECONDS)
    try:
        return max(0.0, float(raw))
    except ValueError:
        return float(DEFAULT_IDLE_SECONDS)


class PooledVaultSession(VaultSession):
    """A ``VaultSession`` owned by the pool: ``close()`` / ``with`` are leases that leave it open."""

    def __init__(self, *args: Any, community: str = "", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.community = community
        self._guard = threading.RLock()
        self._last_used = 0.0
        self._last_sync = 0.0
        self._failed_at: float | None = None
        self._failed_kind = ""

    def open(self) -> None:
        with self._guard:
            now = _clock()
            if self._vault is not None:
                limit = idle_seconds()
                if limit and now - self._last_used > limit:
                    self._shutdown()
            if self._vault is not None:
                self._last_used = now
                return
            if (not self._interactive and self._failed_at is not None
                    and now - self._failed_at < FAILURE_COOLDOWN):
                raise KeeperAuthRequired(
                    f"Keeper login failed {int(now - self._failed_at)}s ago ({self._failed_kind}); "
                    f"not trying again for {int(FAILURE_COOLDOWN)}s")
            try:
                super().open()
            except BaseException as exc:
                self._release()
                self._failed_at = _clock()
                self._failed_kind = type(exc).__name__
                with _lock:
                    _stats["failures"] += 1
                log.info("keeper session for %s: login failed (%s)", self.community, self._failed_kind)
                raise
            self._failed_at = None
            self._last_used = self._last_sync = _clock()
            with _lock:
                _stats["logins"] += 1
            log.info("keeper session for %s: opened", self.community)

    def refresh(self, min_interval: float = DEFAULT_REFRESH_SECONDS) -> None:
        """Re-sync the vault, at most once per ``min_interval`` seconds, never a new login."""
        with self._guard:
            self.open()
            now = _clock()
            if now - self._last_sync >= min_interval:
                self._vault.sync_down()
                self._last_sync = now

    def close(self) -> None:
        """A lease ends here and nothing else: the pool owns the session (``close_all`` closes it)."""

    def _release(self) -> None:
        try:
            VaultSession.close(self)
        except Exception:  # noqa: BLE001 - closing a half-open session must not hide the login's error
            self._vault = self._auth = self._login = None

    def _shutdown(self) -> None:
        with self._guard:
            if self._vault is None and self._auth is None and self._login is None:
                return
            self._release()
            with _lock:
                _stats["closes"] += 1
            log.info("keeper session for %s: closed", self.community)


def _active_community() -> str:
    from jason.community.profile import profile_name

    return profile_name()


def session_for(settings: Any, *, community: str | None = None, interactive: bool = False) -> PooledVaultSession:
    """The process's one session for (``community``, ``interactive``); not logged in until first used.

    ``community`` defaults to the active one; another raises ``CommunityMismatch``. Only a person passes
    ``interactive=True``."""
    active = _active_community()
    key_community = community or active
    if key_community != active:
        raise CommunityMismatch(
            f"this process serves community {active!r}; a Keeper session for {key_community!r} is refused "
            "(one session belongs to one community)")
    global _atexit_registered
    with _lock:
        key = (key_community, bool(interactive))
        found = _sessions.get(key)
        if found is not None:
            _stats["reuses"] += 1
            return found
        made = PooledVaultSession.from_settings(settings, interactive=bool(interactive))
        made.community = key_community
        _sessions[key] = made
        if not _atexit_registered:
            atexit.register(close_all)
            _atexit_registered = True
        return made


def close_all() -> None:
    """Close every pooled session and forget them (atexit, and tests)."""
    with _lock:
        held = list(_sessions.values())
        _sessions.clear()
    for session in held:
        shutdown = getattr(session, "_shutdown", None)
        if shutdown is not None:
            shutdown()


def stats() -> dict[str, int]:
    """Counts only: ``logins``, ``reuses`` (a ``session_for`` that found its session), ``closes``, ``failures``."""
    with _lock:
        return dict(_stats)


def reset_stats() -> None:
    with _lock:
        for k in _stats:
            _stats[k] = 0


def stats_line() -> str:
    s = stats()
    return f"Keeper sessions this process: {s['logins']} logins, {s['reuses']} reuses"


__all__ = ["CommunityMismatch", "DEFAULT_IDLE_SECONDS", "FAILURE_COOLDOWN", "PooledVaultSession", "close_all",
           "idle_seconds", "reset_stats", "session_for", "stats", "stats_line"]
