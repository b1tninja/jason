"""``GET /api/drive-held``: the files a board member picked in their own Google Drive and jason holds (docs/google-picker.md).

Read-only, disk only, the board's (P2). A row is a number, a size, a page count, and the day of the last pick: no file name (none is
kept) and no Drive id. A confidential copy's size, pages and id are withheld unless the private view is open. A held copy opens as a
split draft through the splitter's usual open (``{"kind": "held", "id": ...}``); this source only lists them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

Args = dict[str, str]
OWNER_REFUSED = "Held copies are the board's: they are not served in the owner view."


def _root() -> Path:
    from jason.mcp.county import _data_dir

    return Path(_data_dir(None))


def _gate() -> None:
    """In a request: the owner view is refused, and where console sign-in is set up the board's level (P2) is required."""
    from flask import abort, current_app, has_request_context, request

    if not has_request_context():
        return
    from jason.web import access

    if request.args.get("view") == "owner":
        abort(access.refusal(403, OWNER_REFUSED))
    sign_in = current_app.extensions.get("jason_sign_in")
    if sign_in is not None and getattr(sign_in, "configured", False):
        access.require(access.Level.P2)


def drive_held(args: Args) -> dict[str, Any]:
    from jason.tasks import drive_pick, split_mask

    _gate()
    return drive_pick.listing(_root(), private=split_mask.private_open())
