"""``jason sign-in``: how people sign in to the console (``jason-web``), and putting a Google client in Keeper.

``jason sign-in`` shows the setup, writing nothing: the community's sign-in clients and the installation's, which one
the .env falls back to, how many people on the roster can sign in, and jason's admins and portfolio managers.

``jason sign-in --import-client FILE`` reads a Google OAuth client downloaded from the Cloud console (the
``client_secret_*.json`` file), and with ``--yes`` puts it in a new Keeper login record and records that record as a
sign-in client: the community's (``--for community``, the default: ``data/spec/<profile>/sign_in.json``) or the
installation's (``--for jason``: ``data/access/sign_in.json``). The secret goes from the file to Keeper and is never
printed. ``--delete-file`` deletes the download once Keeper has it. Without ``--yes`` it says what it would do.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable


def _read_client(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    body = data.get("web") or data.get("installed") or {}
    kind = "web" if "web" in data else "installed" if "installed" in data else ""
    cid, secret = str(body.get("client_id") or ""), str(body.get("client_secret") or "")
    if not cid or not secret:
        raise ValueError(f"{path.name} is not a Google OAuth client download (no web or installed client_id and secret)")
    return {"client_id": cid, "client_secret": secret, "project_id": str(body.get("project_id") or ""), "kind": kind}


def _target(where: str) -> Path:
    from jason.access import access_dir
    from jason.community.private import path_of

    return access_dir() / "sign_in.json" if where == "jason" else path_of("sign_in")


def _show(args: argparse.Namespace) -> int:
    from jason.access import access_dir, admins, installation_sign_in, managers
    from jason.community import community
    from jason.community.profile import profile_name
    from jason.web import signin

    c, key = community(), profile_name()
    own = c.sign_in()
    print(f"Console sign-in for {key}:")
    print(f"  the community's clients ({_target('community')}): " + (", ".join(
        f"{p.key} [{p.provider.value}; domains {', '.join(p.domains) or 'the community email domains'}]" for p in own)
        or "none"))
    inst = installation_sign_in()
    print(f"  the installation's clients ({access_dir() / 'sign_in.json'}): " + (", ".join(
        f"{p.key} [{p.provider.value}; domains {', '.join(p.domains) or 'any'}]" for p in inst) or "none"))
    if not own and not inst:
        uid, env_key = signin.client_record(signin._settings())
        print(f"  the .env fallback: {env_key or 'none: neither ' + signin.RECORD_KEY + ' nor ' + signin.DESKTOP_KEY}")
    roster = signin.default_roster()
    print(f"  the roster: {len(roster)} people, {sum(1 for p in roster if p.email)} with an address to sign in with")
    portfolio = [m for m in managers() if m.manages(key)]
    print(f"  jason's admins: {len(admins())}; managers whose portfolio holds {key}: {len(portfolio)}")
    return 0


def cmd_sign_in(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    if not args.import_client:
        return _show(args)
    from jason.access import write_sign_in
    from jason.community.base import IdentityProvider, SignInProvider
    from jason.community.profile import profile_name

    path = Path(args.import_client)
    client = _read_client(path)
    target = _target(args.for_)
    key = args.key or ("google" if args.for_ == "community" else "jason-google")
    title = args.title or f"jason Google sign-in ({profile_name() if args.for_ == 'community' else 'jason'})"
    domains = tuple(d.strip().lower() for d in (args.domain or []) if d.strip())
    print(f"A Google {client['kind']} client, project {client['project_id'] or '(none named)'}, id ending "
          f"...{client['client_id'][-30:]}.")
    print(f"Keeper: a new login record \"{title}\" (the id as the login, the secret in the password field).")
    print(f"Sign-in: the {'community' if args.for_ == 'community' else 'installation'}'s client \"{key}\" in {target}"
          + (f", accepting {', '.join(domains)}" if domains else "") + ".")
    if client["kind"] == "installed":
        print("Note: a Desktop client returns only to loopback addresses; a Web application client is the one for a "
              "console served beyond this machine.")
    if not args.yes:
        print("Nothing written. Run again with --yes to put it in Keeper and record it.")
        return 0
    with agent_factory(args) as agent:
        uid = agent.store_google_client(client["client_id"], client["client_secret"], title=title,
                                        project_id=client["project_id"],
                                        notes="A Google OAuth client for console sign-in (jason-web). docs/setup.md, "
                                              "Console sign-in.")
    write_sign_in(target, SignInProvider(key=key, record_uid=uid, provider=IdentityProvider.GOOGLE, domains=domains,
                                         label=args.label or ""))
    print(f"Stored in Keeper as record {uid}, and recorded in {target}. Restart jason-web to use it.")
    if args.delete_file:
        path.unlink()
        print(f"Deleted {path.name}: Keeper holds the client now.")
    else:
        print(f"Delete {path.name} once you have checked the record: Keeper holds the client now.")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("sign-in", help="How people sign in to the console (jason-web); put a Google client in Keeper")
    add_common(p)
    p.add_argument("--import-client", metavar="FILE", help="a client_secret_*.json downloaded from the Cloud console")
    p.add_argument("--for", dest="for_", choices=("community", "jason"), default="community",
                   help="whose sign-in client it is: this community's (default) or the installation's (admins, managers)")
    p.add_argument("--key", help="its name when there is more than one (default google, or jason-google)")
    p.add_argument("--label", help="the button's words when there is more than one, e.g. \"Management company\"")
    p.add_argument("--domain", action="append",
                   help="an email domain whose accounts it accepts (repeat; default: the community's email domains)")
    p.add_argument("--title", help="the Keeper record's title")
    p.add_argument("--delete-file", action="store_true", help="delete the downloaded file once Keeper has the client")
    p.add_argument("--yes", action="store_true", help="put it in Keeper and record it (without: say what it would do)")
    p.set_defaults(func=lambda a: cmd_sign_in(a, agent_factory))


__all__ = ["cmd_sign_in", "register"]
