"""``jason delivery``: who receives an individual notice how, from the owners' PayHOA tags (Civil Code 4040, 4041).

``jason delivery`` reads the stored PayHOA catalog and prints, for every current owner, email or mail and why, then
the totals: how many a broadcast reaches, how many the Mailroom mails (to the profile's mailing address or to the
unit), and what is left (no election, an email election with no deliverable email, not yet answered this year).
``--tags`` sets the specification's tag vocabulary (mystique/tags.py) beside the tags PayHOA has: a proposed tag not
created yet, a tag the specification thinks exists that no unit or member carries, and a tag in PayHOA the
specification does not name. ``--out FILE`` writes the per-owner plan as CSV (names; no addresses). Nothing is sent and
nothing in PayHOA changes; a send reads PayHOA live first (``jason broadcast``, ``jason mailroom``).
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Callable


def cmd_delivery(args: argparse.Namespace, agent_factory: Callable[[Any], Any] | None = None) -> int:
    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks.broadcast import catalog_rows
    from jason.tasks.notice_delivery import plan

    community = active()
    tags = community.payhoa_tags()
    units, people, synced = catalog_rows(Settings.load(args.env).payhoa_catalog)
    if args.tags:
        return _tags(tags, units, people)
    found = plan(units, people, tags, synced=synced)
    if args.audit and args.apply:
        return _apply(args, agent_factory, tags)
    if args.audit:
        return _audit(found, tags, args.out)
    if args.notice:
        return _notice(args, community, found, tags)
    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["unit", "owner", "channels", "mail to", "reason", "answered this year", "unit tags"])
            for o in found.owners:
                writer.writerow([o.unit, o.name, " and ".join(c.value for c in o.channels), o.send_to, o.reason,
                                 "yes" if o.answered else "", "; ".join(o.unit_tags)])
        print(f"{len(found.owners)} owners written to {args.out}")
    print(json.dumps(found.summary(), indent=1))
    return 0


def _notice(args: argparse.Namespace, community: Any, found: Any, tags: Any) -> int:
    """One notice's exact recipients, and how a person picks them with PayHOA's filters."""
    from jason.tasks.notice_delivery import audience, filters

    if args.notice == "list":
        for rule in community.notice_rules():
            print(f"  {rule.key:24} {rule.kind.value:28} {rule.authority:28} {rule.reach}"
                  + ("; 4040(b) copies" if rule.secondary_copies else ""))
        return 0
    rule = community.notice_rule(args.notice)
    who = audience(found, rule, tags, unit_tag=args.unit_tag or "")
    print(json.dumps(who.summary(), indent=1))
    print("\nIn PayHOA:")
    for line in filters(rule, tags, unit_tag=args.unit_tag or ""):
        print(f"  {line}")
    if args.ids:
        Path(args.ids).write_text(json.dumps({
            "notice": rule.key, "unitTag": args.unit_tag or "", "emailMembershipIds": who.email_ids,
            "mail": [{"unitId": o.unit_id, "membershipId": o.membership_id, "sendTo": o.send_to} for o in who.mail],
            "secondary": [{"unitId": s.unit_id, "membershipId": s.membership_id} for s in who.secondary],
        }, indent=1), encoding="utf-8")
        print(f"ids for the sending tools: {args.ids}")
    return 0


def _audit(found: Any, tags: Any, out: str | None) -> int:
    """What keeps PayHOA's own filters from finding everyone a notice must reach."""
    from collections import Counter

    from jason.tasks.notice_delivery import audit

    problems = audit(found, tags)
    print(f"{len(problems)} change(s) so PayHOA's filters select what the law requires:")
    for change, count in Counter(p["change"] for p in problems).items():
        print(f"  {change}: {count}")
    if out:
        with open(out, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["unit", "member", "name", "change", "why"])
            writer.writerows([p["unit"], p["member"], p["name"], p["change"], p["why"]] for p in problems)
        print(f"rows written to {out}")
    return 0


APPLY_BATCH = 25


def _apply(args: argparse.Namespace, agent_factory: Any, tags: Any) -> int:
    """Add the delivery tags the audit asks for, read from PayHOA now (never from the stored catalog). Only additions
    the audit names are written; nothing is removed. Without --yes it prints what it would do."""
    from collections import defaultdict

    from jason.tasks.notice_delivery import audit, plan

    with agent_factory(args) as agent:
        client, org = agent.payhoa(), agent.org_id
        units, page = [], 1
        while True:
            body = client.list_units(org, page=page)
            units.extend(body.get("data") or [])
            meta = body.get("meta") or {}
            if page >= int(meta.get("lastPage") or meta.get("last_page") or 1):
                break
            page += 1
        people = list(client.iter_people(org))
        found = plan(units, people, tags)
        additions: dict[str, set[int]] = defaultdict(set)
        for row in audit(found, tags):
            if row["change"].startswith("+"):
                additions[row["change"][1:].split(" [")[0]].add(int(row["member"]))
        for tag, members in additions.items():
            print(f"  add '{tag}' to {len(members)} member(s)")
        if not additions:
            print("nothing to add: every owner carries a delivery tag")
            return 0
        if not args.yes:
            print("Dry run: add --yes to write these tags in PayHOA (read live just now; nothing is removed).")
            return 0
        for tag, members in additions.items():
            ids = sorted(members)
            for i in range(0, len(ids), APPLY_BATCH):
                client.update_member_tags(org, ids[i:i + APPLY_BATCH], add=[tag])
            print(f"added '{tag}' to {len(ids)} member(s)")
    return 0


def _tags(tags: Any, units: list[dict[str, Any]], people: list[dict[str, Any]]) -> int:
    from collections import Counter

    from jason.community.tags import TagScope, tag_names

    carried = {TagScope.UNIT: Counter(n for u in units for n in tag_names(u)),
               TagScope.MEMBER: Counter(n for p in people for n in tag_names(p))}
    named = {(t.scope, t.name.casefold()) for t in tags}
    for t in tags:
        count = carried[t.scope].get(t.name.casefold(), 0)
        state = ("to create" if not t.exists else f"{count} {t.scope.value}s") + (" (none carry it)" if t.exists and not count else "")
        print(f"  {t.scope.value:6} {t.name:24} {t.purpose.value:22} {state}" + (f"  {t.note}" if t.note else ""))
    for scope, counts in carried.items():
        for name, count in counts.items():
            if (scope, name) not in named:
                print(f"  {scope.value:6} {name:24} not in mystique/tags.py ({count})")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("delivery", help="Who receives an individual notice how, from the owners' PayHOA tags (CIV 4040)")
    add_common(p)
    p.add_argument("--tags", action="store_true", help="the tag vocabulary beside the tags PayHOA has")
    p.add_argument("--out", help="write the per-owner plan as CSV (names; no addresses)")
    p.add_argument("--notice", metavar="KEY", help="one notice's recipients and PayHOA filters ('list' for the notices)")
    p.add_argument("--unit-tag", help="with --notice: only the owners of the units carrying this tag ('Building 3')")
    p.add_argument("--ids", metavar="FILE", help="with --notice: write the recipients' ids for the sending tools")
    p.add_argument("--audit", action="store_true", help="the tag changes that let PayHOA's own filters find everyone")
    p.add_argument("--apply", action="store_true", help="with --audit: add those tags in PayHOA, read live (--yes writes)")
    p.add_argument("--yes", action="store_true", help="with --audit --apply: write the tags")
    p.set_defaults(func=lambda a: cmd_delivery(a, agent_factory))
