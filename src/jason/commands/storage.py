"""``jason storage``: where jason reads and writes, and how much room each drive has.

For each place jason keeps something it prints the path, the drive, the drive's free space, and the size of what jason
keeps there: the data directory and its big subfolders (the retrieval index and vectors, the library, the mail, the Gmail
files, cases, reports, the Drive mirror, the authorities), the temp folder (``JASON_TEMP_DIR``, else the system's),
``ASSPY_HOME``, the Ollama models folder (``OLLAMA_MODELS``), ``HF_HOME``, jason's lock folder, and the Google token and
Keeper config (path and drive only).

- ``--check`` exits 1 and says why when a place is on a drive with less than ``--min-free-gb`` free (default 20), when the
  system temp shares the data directory's low drive, when ``JASON_TEMP_DIR`` is unset and the system temp's drive has less
  room than the data directory's, or when ``JASON_TEMP_DIR`` cannot be used.
- ``--no-sizes`` skips measuring the folders (free space and drives only); ``--json`` prints JSON.

It reads only, and it reads no file's contents. ``JASON_TEMP_DIR`` is explained in docs/setup.md (Where jason writes).
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Callable

from jason.storage import DEFAULT_MIN_FREE_GB


def cmd_storage(args: argparse.Namespace) -> int:
    from jason import storage
    from jason.commands._shared import data_dir

    rep = storage.report(data_dir(args), env_file=getattr(args, "env", None), sizes=not args.no_sizes,
                         min_free_gb=args.min_free_gb)
    if args.json:
        print(json.dumps(rep, indent=1))
    else:
        print("\n".join(storage.lines(rep)))
    return 1 if args.check and rep["problems"] else 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("storage", help="Where jason writes: each place's path, drive, free space, and size; --check flags a "
                                       "drive short of room and scratch on the small drive")
    add_common(p)
    p.add_argument("--check", action="store_true", help="exit 1 and say why when a drive is short of room")
    p.add_argument("--min-free-gb", type=float, default=DEFAULT_MIN_FREE_GB, metavar="GB",
                   help=f"free space below which a drive is a problem (default {DEFAULT_MIN_FREE_GB:g})")
    p.add_argument("--no-sizes", action="store_true", help="skip measuring the folders")
    p.add_argument("--json", action="store_true", help="print JSON")
    # A folder JASON_TEMP_DIR names that cannot be used is a finding here, not a failure to start.
    p.set_defaults(func=cmd_storage, reports_temp_dir=True)
