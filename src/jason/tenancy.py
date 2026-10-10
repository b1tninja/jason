"""Which community a process serves, shown before it writes (docs/tenancy.md, section 3).

``write_banner()`` is the one line every write prints first, on standard error::

    community: KEY (from SOURCE); data: PATH

It is called from the places a write passes through: the CLI's argument handling (anything with ``--yes``), the web
console's write guard, and the MCP tools that write a person's record. A person at a terminal whose community was
chosen days ago by ``jason use`` sees which community the write is about to change.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from jason.community.profile import COMMUNITY_VAR, ALIAS_VAR, FLAG_SOURCE, VIA_VAR, announce, resolve_community


def banner(env_file: str | Path | None = None, *, data: str | Path | None = None) -> str:
    """``community: KEY (from SOURCE); data: PATH`` for the community this process serves. Raises
    ``CommunityNotChosen`` when none is chosen, so a write never runs against a guess."""
    from jason.config import data_dir

    resolved = resolve_community()
    announce(resolved)
    return f"community: {resolved.name} (from {resolved.source}); data: {data if data is not None else data_dir(env_file)}"


def write_banner(env_file: str | Path | None = None, *, data: str | Path | None = None, stream: Any = None) -> str:
    """Print ``banner()`` on standard error (or ``stream``) and return it. ``data`` is the folder when a caller was
    given its own rather than the community's."""
    line = banner(env_file, data=data)
    print(line, file=stream if stream is not None else sys.stderr, flush=True)
    return line


def choose_community(key: str) -> None:
    """The global ``--community KEY`` flag: this process, and every program it starts, serves ``key``. It sets both
    spellings of the setting, so a program started from here that still reads the old name agrees."""
    key = key.strip().lower()
    os.environ[COMMUNITY_VAR] = key
    os.environ[ALIAS_VAR] = key
    os.environ[VIA_VAR] = FLAG_SOURCE


def pull_community_flag(argv: list[str]) -> tuple[list[str], str]:
    """``argv`` without a leading ``--community KEY`` (or ``--community=KEY``) and the key ("" when absent). Only the
    options before the subcommand are read: a subcommand's own ``--community`` (``jason cadence``, ``jason vault``) is
    that command's."""
    rest = list(argv)
    key = ""
    i = 0
    while i < len(rest) and rest[i].startswith("-"):
        arg = rest[i]
        if arg == "--community" and i + 1 < len(rest):
            key = rest[i + 1]
            del rest[i:i + 2]
            continue
        if arg.startswith("--community="):
            key = arg.split("=", 1)[1]
            del rest[i]
            continue
        if arg in ("-h", "--help"):
            break
        i += 1
    return rest, key
