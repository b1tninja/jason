"""``jason google``: a community sets up its own Google Workspace (docs/google-workspace-setup.md).

- ``status``: for the active community, whether its OAuth client is in ITS vault path (or still the installation's
  ``.env`` record, said plainly), the project id when the record carries one, and each token (drive, tasks, vault,
  photos): where it is read from and which scopes are covered or missing.
- ``scopes``: what each token asks for, what each scope is used for, and the API to enable.
- ``setup [--from-file client_secret.json | hidden prompt] [--project ID] [--replace] [--yes]``: store the community's
  OAuth client at ``jason/community/<profile>/google-workspace/oauth-client`` (fields ``client_id``, ``client_secret``,
  ``project_id``). Without ``--yes`` a dry run that writes nothing. Create only unless ``--replace``. ``--yes`` runs
  only for a person at a terminal.
- ``adopt-installation-record [--yes]``: copy the client the ``.env`` record names into the community's path.
- ``sign-in [--name drive|tasks|vault|photos|all] --interactive [--again]``: a person's browser consent; the token is
  saved to the vault and nowhere else on disk. A token already held that covers the scopes is "already signed in".

A secret (the client's id and secret, a token) is never printed or logged here: messages carry names, counts and paths.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial
from typing import Any, Callable

from jason.google.auth import authorize_in_browser

ACTIONS = ("status", "scopes", "setup", "adopt-installation-record", "sign-in")
TOKEN_LIMIT_NOTE = ("Each consent counts toward Google's limit of 100 refresh tokens for one account on one OAuth client; "
                    "past it, the oldest silently stops working. A token already held needs no new consent.")


def _settings(args: argparse.Namespace) -> Any:
    from jason.config import Settings

    return Settings.load(getattr(args, "env", None))


@contextmanager
def _vault(settings: Any, *, interactive: bool = False) -> Iterator[tuple[Any, Any]]:
    """The credential vault (Keeper) as ``(store, session)``; never prompts unless ``interactive``."""
    from jason.secrets import VaultSession
    from jason.vault.keeper import KeeperStore

    with VaultSession.from_settings(settings, interactive=interactive) as session:
        yield KeeperStore.from_session(session), session


def _community() -> str:
    from jason.community.profile import profile_name

    return profile_name()


def _pins() -> Any:
    try:
        from jason.community import community

        return community().google_workspace()
    except Exception:  # noqa: BLE001 - a profile that cannot load pins nothing
        from jason.community.base import GoogleWorkspace

        return GoogleWorkspace()


def _person_at_terminal() -> bool:
    from jason.commands import integrations

    return integrations.at_terminal()


def _short(scope: str) -> str:
    return scope.rsplit("/", 1)[-1]


# ----- status / scopes -----


def _status(args: argparse.Namespace) -> int:
    from jason.google import workspace
    from jason.google.tokens import token_store
    from jason.secrets import KeeperAuthRequired

    settings, key, pins = _settings(args), _community(), _pins()
    print(f"Google Workspace for community {key}:")
    if pins.domain:
        print(f"  expected Workspace domain: {pins.domain}")
    if pins.note:
        print(f"  note: {pins.note}")
    try:
        with _vault(settings) as (store, _session):
            state = workspace.client_state(store, settings, key, pins.client)
            for line in workspace.status_text(state):
                print(line)
            print("Tokens (where each is read from; a token is never shown):")
            for line in workspace.token_lines(token_store(settings, store, key)):
                print(line)
    except KeeperAuthRequired:
        print("The vault needs a sign-in (run `jason login` in a terminal); local token files only:")
        state = workspace.client_state(None, settings, key, pins.client)
        for line in workspace.status_text(state):
            print(line)
        for line in workspace.token_lines(token_store(settings, None, key)):
            print(line)
    return 0


def _scopes(args: argparse.Namespace) -> int:
    from jason.google.scopes import SCOPE_PURPOSES
    from jason.google.tokens import NAMES, scopes_of

    for name in NAMES:
        asked = scopes_of(name)
        print(f"{name} ({len(asked)} scopes); sign in with `jason google sign-in --name {name} --interactive`:")
        for scope in asked:
            api, purpose = SCOPE_PURPOSES.get(scope, ("(an API)", "(no purpose recorded)"))
            print(f"  {_short(scope)}: {purpose}  [enable: {api}]")
    return 0


# ----- setup -----


def _prompt_client(project: str) -> Any:
    from jason.google.workspace import Client

    client_id = getpass.getpass("OAuth client id (hidden): ").strip()
    client_secret = getpass.getpass("OAuth client secret (hidden): ").strip()
    if not client_id or not client_secret:
        raise ValueError("an OAuth client needs both its id and its secret")
    return Client(client_id, client_secret, project)


def _exists(store_check: Callable[[], bool]) -> str:
    try:
        return "yes" if store_check() else "no"
    except Exception as exc:  # noqa: BLE001
        return f"not checked ({type(exc).__name__})"


def _setup(args: argparse.Namespace) -> int:
    from jason.google import workspace
    from jason.vault.store import VersionConflict

    settings, key, pins = _settings(args), _community(), _pins()
    path = workspace.client_path(key, pins.client)
    client = None
    if args.from_file:
        try:
            client = workspace.read_client_file(args.from_file)
        except workspace.ClientFileError as exc:
            print(f"jason google setup: {exc}", file=sys.stderr)
            return 2
        if args.project:
            client = workspace.Client(client.client_id, client.client_secret, args.project)
    elif args.yes:
        if not _person_at_terminal():
            print("jason google setup --yes asks for the client at a hidden prompt, and runs only for a person at a "
                  "terminal; or pass --from-file client_secret.json.", file=sys.stderr)
            return 2
        try:
            client = _prompt_client(args.project)
        except ValueError as exc:
            print(f"jason google setup: {exc}", file=sys.stderr)
            return 2
    print(f"Community {key}: the OAuth client goes to {path} (fields client_id, client_secret, project_id).")
    if args.from_file:
        print(f"Read {args.from_file}: an installed (Desktop) client with its id and secret; project "
              f"{client.project_id or '(none named)'}.")
    else:
        print("The client id and secret are asked for at a hidden prompt (or pass --from-file client_secret.json).")
    if not args.yes:
        try:
            with _vault(settings) as (store, _s):
                held = _exists(lambda: store.get(path) is not None)
        except Exception as exc:  # noqa: BLE001
            held = f"not checked ({type(exc).__name__})"
        print(f"Already stored there: {held}. Create only unless --replace.")
        print("Nothing written. A person at a terminal runs it again with --yes to store it in the vault.")
        return 0
    if not _person_at_terminal():
        print("jason google setup --yes writes the vault, and runs only for a person at a terminal.", file=sys.stderr)
        return 2
    from jason.secrets import KeeperAuthRequired

    try:
        with _vault(settings, interactive=bool(getattr(args, "interactive", False))) as (store, _s):
            try:
                store.put(path, client.fields(), None if args.replace else 0, by=getpass.getuser())
            except VersionConflict:
                print(f"jason google setup: the vault already holds {path}. --replace overwrites it (tokens signed in "
                      "under a different client id stop working, and must be signed in again).", file=sys.stderr)
                return 2
    except KeeperAuthRequired:
        print("Keeper needs a sign-in: run `jason login` in a terminal, or add --interactive.", file=sys.stderr)
        return 2
    print(f"Stored the OAuth client at {path}.")
    if args.replace:
        print("Replaced. A refresh token belongs to the client that issued it: if the client id changed, sign in again "
              "with `jason google sign-in --again --interactive`.")
    if args.from_file:
        print(f"Delete {args.from_file} when you have checked `jason google status`: the vault holds the client now.")
    print("Next: `jason google sign-in --name drive --interactive`.")
    return 0


def _adopt(args: argparse.Namespace) -> int:
    from jason.google import workspace
    from jason.secrets import KeeperAuthRequired
    from jason.vault.store import VersionConflict

    settings, key, pins = _settings(args), _community(), _pins()
    path = workspace.client_path(key, pins.client)
    if not workspace.installation_uid(settings):
        print("jason google adopt-installation-record: .env names no google_oauth_record_uid; nothing to copy. "
              "`jason google setup` stores a community's own client.", file=sys.stderr)
        return 2
    print(f"Plan: copy the client the installation's .env record names to {path} for community {key} "
          "(create only: a client already there is left alone).")
    print("The record's id and secret are copied unchanged; the project id too if the record carries it.")
    if not args.yes:
        print("Nothing written. A person at a terminal runs it again with --yes.")
        return 0
    if not _person_at_terminal():
        print("jason google adopt-installation-record --yes writes the vault, and runs only for a person at a "
              "terminal.", file=sys.stderr)
        return 2
    try:
        with _vault(settings, interactive=bool(getattr(args, "interactive", False))) as (store, session):
            found = workspace.installation_client(session, settings, store)
            if found is None:
                print("The .env record could not be read.", file=sys.stderr)
                return 2
            try:
                store.put(path, found.fields(), 0, by=getpass.getuser())
            except VersionConflict:
                print(f"The vault already holds {path}; left alone.")
                return 0
    except KeeperAuthRequired:
        print("Keeper needs a sign-in: run `jason login` in a terminal, or add --interactive.", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - a record missing client_id or client_secret, by name
        print(f"jason google adopt-installation-record: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(f"Copied to {path}. Check `jason google status`, then remove google_oauth_record_uid from .env.")
    print("Tokens already signed in under this client keep working.")
    return 0


# ----- sign-in -----


def _sign_in(args: argparse.Namespace) -> int:
    from jason.google import session, workspace
    from jason.google.errors import GoogleAuthRequired, GoogleError
    from jason.google.scopes import SCOPE_PURPOSES
    from jason.google.tokens import NAMES, covers, scopes_of, token_store
    from jason.secrets import KeeperAuthRequired

    if not args.interactive:
        print(GoogleAuthRequired(session.NEEDS_BROWSER), file=sys.stderr)
        print("A person at a terminal runs: jason google sign-in --name NAME --interactive", file=sys.stderr)
        return 2
    if not _person_at_terminal():
        print("jason google sign-in opens a browser for a person's consent, and runs only at a terminal.",
              file=sys.stderr)
        return 2
    names = NAMES if args.name == "all" else (args.name,)
    settings, key, pins = _settings(args), _community(), _pins()
    try:
        with _vault(settings, interactive=True) as (store, vault_session):
            try:
                client_id, client_secret = session.oauth_client(settings, vault_session, store=store, community=key)
            except GoogleError as exc:
                print(f"jason google sign-in: {exc}", file=sys.stderr)
                return 2
            tokens = token_store(settings, store, key)
            for name in names:
                asked = scopes_of(name)
                try:
                    held = tokens.locate(name, asked).token
                except Exception:  # noqa: BLE001
                    held = None
                if covers(held, asked) and not args.again:
                    print(f"{name}: already signed in (the token covers all {len(asked)} scopes). --again signs in anew.")
                    continue
                print(f"{name}: a browser will open for consent to {len(asked)} scopes"
                      + (f" on {pins.domain}" if pins.domain else "") + ":")
                for scope in asked:
                    print(f"  {_short(scope)}: {SCOPE_PURPOSES.get(scope, ('', '(no purpose recorded)'))[1]}")
                print(TOKEN_LIMIT_NOTE)
                session._sign_in(partial(authorize_in_browser, scopes=asked), client_id, client_secret, tokens, name,
                                 asked, True)
                where = tokens.locate(name).where
                if where == "vault":
                    print(f"{name}: signed in; the token is saved in the vault.")
                else:
                    print(f"{name}: signed in; the vault did not take the token, so it is kept in the local file "
                          "(`jason google status` flags it). Run `jason vault migrate --yes` when the vault answers.")
    except KeeperAuthRequired:
        print("Keeper needs a sign-in: run `jason login` in a terminal first.", file=sys.stderr)
        return 2
    except GoogleError as exc:
        print(f"jason google sign-in: {exc}", file=sys.stderr)
        return 1
    return 0


def run(args: argparse.Namespace) -> int:
    return {"status": _status, "scopes": _scopes, "setup": _setup, "adopt-installation-record": _adopt,
            "sign-in": _sign_in}[args.action](args)


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    from jason.google.tokens import NAMES

    p = sub.add_parser("google", help="A community's own Google Workspace: OAuth client, sign-in, status")
    add_common(p)
    p.add_argument("action", choices=ACTIONS, help="status, scopes, setup, adopt-installation-record, or sign-in")
    p.add_argument("--from-file", metavar="FILE", help="setup: the client_secret_*.json the Cloud console downloads")
    p.add_argument("--project", default="", help="setup: the Cloud project id, when the client has none of its own")
    p.add_argument("--replace", action="store_true", help="setup: overwrite a client already stored")
    p.add_argument("--yes", action="store_true", help="setup, adopt-installation-record: write the vault (a person at a "
                                                       "terminal); without, the plan only")
    p.add_argument("--name", choices=(*NAMES, "all"), default="drive", help="sign-in: which token (default drive)")
    p.add_argument("--again", action="store_true", help="sign-in: consent anew although a token is held")
    # --interactive comes from add_common: for sign-in it is the person at a browser (and Keeper's prompts).
    p.set_defaults(func=run)


__all__ = ["ACTIONS", "register", "run"]
