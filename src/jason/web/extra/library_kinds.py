"""The document kinds screen's loader: ``GET /api/library-kinds`` (the shelf) and ``?kind=`` (one kind's files).

Reads the classified library on disk; no network and no model. A confidential file is counted and never named unless a
person asks with ``confidential=1`` (the same switch ``/api/library`` has).
"""

from __future__ import annotations

from typing import Any

Args = dict[str, str]


def library_kinds(args: Args) -> dict[str, Any]:
    from jason.mcp.county import _data_dir
    from jason.tasks import library_kinds as lk

    kind = args.get("kind", "").strip()
    if kind:
        held = args.get("confidential", "").lower() in ("1", "true", "yes")
        return lk.kind_detail(_data_dir(None), kind, include_held=held)
    return lk.shelf(_data_dir(None))
