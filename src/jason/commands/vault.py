"""``jason vault status`` and ``jason vault migrate``: the credential vault (docs/integrations-design.md, The vault).

``jason vault`` with no action is still Google Vault's matters and holds (``cli.cmd_vault``); this module adds the two
actions to that parser (``add_arguments``) rather than registering its own, so it is not in ``MODULES``.

- ``status``: the backend, whether it answers (never prompting: a Keeper that wants a sign-in says so), every vault
  path by community, and the ``.env`` keys still read in their place. Names only, never a value or a record UID.
- ``migrate [--community C]``: the plan, each ``*_record_uid`` key in ``.env`` and the vault path its record moves to.
  ``--yes``, run by a person at a terminal, copies them in Keeper (create only: a path already set is left alone).
  The ``.env`` keys stay until the person has checked each entry and removed them. The plan and the copy also cover the
  local Google token files (``jason.google.tokens``: each to ``google-workspace/token/<name>``), and ``status`` says where
  each Google token would be read from (vault, file, or missing) with its scope count, never the token.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable, Mapping
from typing import Any

from jason.google.tokens import migrate_tokens, plan_token_lines, plan_token_migration, token_store
from jason.google.tokens import status_lines as token_status_lines
from jason.vault.keeper import FOLDER
from jason.vault.paths import Scope, parse_path
from jason.vault.resolver import MigrationResult, MigrationState, MigrationStep, migrate, plan_migration
from jason.vault.store import SecretStore

ACTIONS = ("status", "migrate")


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("action", nargs="?", choices=ACTIONS,
                        help="status or migrate: the credential vault (Keeper); none: Google Vault's matters and holds")
    parser.add_argument("--community", default="",
                        help="With migrate: the community whose paths the records go under (default: the active profile)")
    parser.add_argument("--yes", action="store_true",
                        help="With migrate: copy the records in Keeper (a person at a terminal); without, the plan only")


def _backend_line(store: SecretStore) -> str:
    where = f" (a Keeper record titled with each path, in the folder \"{FOLDER}\")" if store.name == "keeper" else ""
    return f"Vault backend: {store.name}{where}"


def _answer(store: SecretStore) -> tuple[list[str] | None, str]:
    """Every path in the vault, or None and why it did not answer."""
    from jason.secrets import KeeperAuthRequired

    try:
        return store.list("jason/"), ""
    except KeeperAuthRequired:
        return None, "no: Keeper needs a sign-in (run `jason login` in a terminal)"
    except Exception as exc:  # noqa: BLE001 - a backend that does not answer is reported, not raised
        return None, f"no ({type(exc).__name__})"


def status_lines(store: SecretStore, record_uids: Mapping[str, str], community: str,
                 portal_keys: Iterable[str] = ()) -> list[str]:
    lines = [_backend_line(store)]
    paths, problem = _answer(store)
    lines.append(f"Answers: yes, {len(paths)} entries" if paths is not None else f"Answers: {problem}")
    if paths:
        groups: dict[tuple[str, str], list[str]] = {}
        for path in paths:
            vp = parse_path(path)
            groups.setdefault((vp.scope.value, vp.owner), []).append(path)
        for (scope, owner), names in sorted(groups.items(), key=lambda kv: (kv[0][0] != Scope.INSTANCE.value, kv[0])):
            lines.append("Instance:" if scope == Scope.INSTANCE.value else f"Community {owner}:")
            lines.extend(f"  {name}" for name in names)
    steps, _ = plan_migration(community, record_uids, portal_keys=portal_keys)
    held = set(paths or ())
    waiting = [s for s in steps if s.state is MigrationState.UNMAPPED or s.path not in held]
    if waiting:
        lines.append("Still named in .env" + (" (`jason vault migrate` plans the move):" if paths is not None
                                               else " (the vault was not read, so some may already be moved):"))
        lines.extend(f"  {s.env_key} -> {s.path or '(no vault path: a person decides)'}" for s in waiting)
    return lines


def plan_lines(steps: list[MigrationStep], community: str, problem: str = "") -> list[str]:
    lines = [f"Plan: copy each Keeper record .env names to its vault path, for community {community}."]
    if problem:
        lines.append(f"The vault did not answer ({problem}); a path already set would be left alone.")
    if not steps:
        lines.append("  .env names no *_record_uid: nothing to move.")
    for s in steps:
        what = {MigrationState.COPY: "copy", MigrationState.IN_VAULT: "already in the vault",
                MigrationState.NOT_CHECKED: "copy unless already set",
                MigrationState.UNMAPPED: "no vault path: a person decides"}[s.state]
        lines.append(f"  {s.env_key} -> {s.path or '-'}: {what}")
    return lines


def result_lines(results: list[MigrationResult]) -> list[str]:
    lines = [f"  {r.step.env_key} -> {r.step.path}: {r.outcome}" for r in results]
    moved = [r.step.env_key for r in results if r.outcome in ("copied", "already in the vault")]
    if moved:
        lines.append("Check each entry in Keeper, then remove these keys from .env: " + ", ".join(moved) + ".")
    return lines


def _context(args: argparse.Namespace) -> tuple[Any, str, tuple[str, ...]]:
    from jason.community.profile import profile_name
    from jason.config import Settings

    settings = Settings.load(getattr(args, "env", None))
    key = getattr(args, "community", "") or profile_name()
    try:
        from jason.community import community

        portals = tuple(p.key for p in community().vendor_portals())
    except Exception:  # noqa: BLE001 - a profile that cannot load names no portals
        portals = ()
    return settings, key, portals


def run(args: argparse.Namespace) -> int:
    """``jason vault status`` or ``jason vault migrate``."""
    import getpass

    from jason.secrets import KeeperAuthRequired
    from jason.vault.pool import session_for, stats_line
    from jason.vault.keeper import KeeperStore

    settings, key, portals = _context(args)
    if args.action == "status":
        with session_for(settings, interactive=False) as session:   # status never prompts
            store = KeeperStore.from_session(session)
            for line in status_lines(store, settings.record_uids, key, portals):
                print(line)
            print("Google tokens (where each is read from; the token is never shown):")
            for line in token_status_lines(token_store(settings, store, key)):
                print(line)
        print(stats_line())
        return 0

    if not args.yes:
        with session_for(settings, interactive=False) as session:
            store = KeeperStore.from_session(session)
            steps, problem = plan_migration(key, settings.record_uids, portal_keys=portals, store=store)
            token_steps = plan_token_migration(token_store(settings, store, key), key, checked=not problem)
        for line in plan_lines(steps, key, problem):
            print(line)
        for line in plan_token_lines(token_steps):
            print(line)
        print("Nothing written. A person at a terminal runs it again with --yes to copy them in Keeper.")
        return 0
    from jason.commands.integrations import at_terminal   # NUL also says it is a tty on Windows

    if not at_terminal():
        print("jason vault migrate --yes copies records in Keeper, and runs only for a person at a terminal.",
              file=sys.stderr)
        return 2
    try:
        with session_for(settings, interactive=bool(getattr(args, "interactive", False))) as session:
            store = KeeperStore.from_session(session)
            steps, problem = plan_migration(key, settings.record_uids, portal_keys=portals, store=store)
            if problem:
                print(f"The vault did not answer: {problem}", file=sys.stderr)
                return 2
            for line in plan_lines(steps, key):
                print(line)
            results = migrate(steps, store, settings.record_uids, store.load_by_uid, by=getpass.getuser())
            tokens = token_store(settings, store, key)
            token_steps = plan_token_migration(tokens, key)
            for line in plan_token_lines(token_steps):
                print(line)
            token_results = migrate_tokens(token_steps, tokens, by=getpass.getuser())
    except KeeperAuthRequired:
        print("Keeper needs a sign-in: run `jason login` in a terminal, or add --interactive.", file=sys.stderr)
        return 2
    print("Done:")
    for line in result_lines(results):
        print(line)
    for step, outcome in token_results:
        print(f"  Google token {step.name} -> {step.path}: {outcome}")
    if any(o == "copied" for _, o in token_results):
        print("The local token files stay (a per-checkout cache); a worktree reads the vault copy.")
    return 1 if any(r.outcome.startswith("source") for r in results) else 0


__all__ = ["ACTIONS", "add_arguments", "plan_lines", "result_lines", "run", "status_lines"]
