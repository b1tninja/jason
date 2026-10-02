"""`jason registers`: the registers kept as Google Sheets; create one, shape it, or list them."""

from __future__ import annotations

import argparse
from typing import Any, Callable


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    parser = sub.add_parser("registers", help="Registers kept as Google Sheets: list them, --create KEY --yes, --shape KEY")
    add_common(parser)
    parser.add_argument("--create", metavar="KEY", help="Create the register's Sheet in the registers folder (needs --yes)")
    parser.add_argument("--shape", metavar="KEY", help="Shape the register's Sheet again (header, dropdowns, protection)")
    parser.add_argument("--yes", action="store_true", help="Confirm creating a Sheet in the association's Drive")
    parser.set_defaults(func=lambda args: run(args, agent_factory))


def run(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.community import mystique
    from jason.config import Settings
    from jason.tasks import registers as task

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    community = mystique()
    if args.create:
        reg = task.register(community, args.create)
        if not args.yes:
            print(f"would create \"{reg.title}\" in the Drive folder \"{community.registers_folder()}\" (tabs {reg.tab}, Log, About), "
                  f"shared with no one{'; confidential: share with directors only' if reg.confidential else ''}; add --yes")
            return 0
        with agent_factory(args) as agent:
            drive = agent.drive()
            entry = task.ensure(drive.sheets(), drive, reg, data_dir, folder=community.registers_folder())
            task.shape(drive.sheets(), reg, data_dir)
        print(f"{reg.title}: https://docs.google.com/spreadsheets/d/{entry['spreadsheetId']}")
        return 0
    if args.shape:
        reg = task.register(community, args.shape)
        with agent_factory(args) as agent:
            print(f"{task.shape(agent.drive().sheets(), reg, data_dir, force=True)} formatting requests applied to {reg.title}")
        return 0
    for reg in task.registers(community):
        sid = task.spreadsheet_id(data_dir, reg)
        where = f"https://docs.google.com/spreadsheets/d/{sid}" if sid else "no Sheet yet"
        owners = ", ".join(f"{c.name}" for c in reg.columns if c.owner.value == "board")
        print(f"{reg.key}: {reg.title} ({'confidential' if reg.confidential else 'board'}); the board writes {owners}; {where}")
    return 0
