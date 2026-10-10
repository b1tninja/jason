"""The console's Drive chooser: three reads over jason's own Drive token (docs/record-intake.md, docs/console/handoff-record-intake.md).

- ``GET /api/drive-list`` (``?parent=ID_OR_LINK&drive=&page=&size=``): a folder's children, a page at a time; with no parent, the
  top of My Drive and the shared drives. ``drive_list(args)``.
- ``POST /api/write/drive/search`` ``{"q": "..."}`` (optional ``page``, ``drive``): files whose name holds the text. The text goes to
  Google, so it is a POST body and never in a URL; the GET loader ``drive-search`` only says so.
- ``POST /api/write/drive/resolve`` ``{"ref": "<link or id>"}``: a pasted link read for its name, type, size, and who owns it;
  a link is not put in a URL either.
- ``POST /api/write/drive/list`` ``{"parent": ...}``: the same as the GET list, for a client that keeps a folder's id out of a URL.
- ``POST /api/write/drive/bound`` ``{"slot": KEY, "folder": ...}``: the files in a folder bound to a slot, each read by name as
  a kind and placed here, elsewhere, or nowhere; nothing is pinned.

Board only: the owner view answers 403 (``?view=owner`` on a loader, and on a POST); a signed-in roster person is needed where
console sign-in is set up. A file read as a confidential kind is named by its kind and carries no id outside the private view.
When Drive is not connected the answer is ``{"found": false, "driveConnected": false, "why": ..., "command": ...}`` and a
browser is never opened. Reads Google and disk; nothing here writes to Drive or to jason's stores.
"""

from __future__ import annotations

from typing import Any, Callable

Args = dict[str, str]

POST_ONLY = ("Searching sends the file's name to Google, so it is a POST and the name never sits in a URL: "
             "POST /api/write/drive/search with {\"q\": ...}.")
RESOLVE_POST = "A pasted link is not put in a URL: POST /api/write/drive/resolve with {\"ref\": ...}."
ACTS = ("list", "search", "resolve", "bound")
OWNER_REFUSED = "The Drive chooser is the board's: it is not served in the owner view."


def _community() -> Any:
    from jason.community import community

    return community()


def _root() -> Any:
    from jason.mcp.county import _data_dir

    return _data_dir(None)


def _private() -> bool:
    from jason.web.extra.record_slots import _private as private

    return private()


def _open() -> Any:
    """The Drive client: jason's server token, never a browser. Replaced in a test."""
    from jason.tasks import drive_choose

    return drive_choose.open_client()


def _gate(body: dict[str, Any] | None = None) -> None:
    """The chooser is the board's. In a request: the owner view is refused, and a signed-in roster person is required where
    console sign-in is set up. Outside a request (a script, a test) there is no one to refuse."""
    from flask import abort, current_app, has_request_context, request

    if not has_request_context():
        return
    from jason.web import access

    if request.args.get("view") == "owner" or str((body or {}).get("view") or "") == "owner":
        abort(access.refusal(403, OWNER_REFUSED))
    sign_in = current_app.extensions.get("jason_sign_in")
    if sign_in is not None and getattr(sign_in, "configured", False):
        access.require(access.Level.P1)


def _with_drive(call: Callable[[Any], dict[str, Any]]) -> dict[str, Any]:
    from jason.tasks import drive_choose

    try:
        client = _open()
    except drive_choose.DriveUnavailable as exc:
        return drive_choose.unavailable_answer(exc)
    try:
        return call(client)
    finally:
        closer = getattr(client, "close", None)
        if callable(closer):
            closer()


def _page(args: dict[str, Any]) -> dict[str, Any]:
    return {"page_token": str(args.get("page") or ""), "drive_id": str(args.get("drive") or ""),
            "page_size": args.get("size") or 50}


def _list(args: dict[str, Any]) -> dict[str, Any]:
    from jason.tasks import drive_choose

    return _with_drive(lambda drive: drive_choose.list_folder(
        drive, folder=str(args.get("parent") or args.get("folder") or ""), community=_community(), root=_root(),
        private=_private(), **_page(args)))


def drive_list(args: Args) -> dict[str, Any]:
    _gate()
    return _list(args)


def drive_search(args: Args) -> dict[str, Any]:
    """The GET loader only explains: a name searched for goes in a POST body."""
    _gate()
    if any(str(args.get(k) or "").strip() for k in ("q", "text", "query")):
        raise ValueError(POST_ONLY)
    return {"found": False, "post": "/api/write/drive/search", "why": POST_ONLY}


def drive_resolve(args: Args) -> dict[str, Any]:
    _gate()
    if any(str(args.get(k) or "").strip() for k in ("ref", "link", "id")):
        raise ValueError(RESOLVE_POST)
    return {"found": False, "post": "/api/write/drive/resolve", "why": RESOLVE_POST}


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """``POST /api/write/drive/<act>``: ``list``, ``search``, ``resolve``, or ``bound`` (see the module). Reads Drive only."""
    from jason.tasks import drive_choose

    if key not in ACTS:
        raise KeyError(key)
    _gate(body)
    if key == "list":
        return _list(body)
    if key == "search":
        return _with_drive(lambda drive: drive_choose.search(
            drive, str(body.get("q") or body.get("text") or ""), community=_community(), root=_root(), private=_private(),
            **_page(body)))
    if key == "resolve":
        return _with_drive(lambda drive: drive_choose.resolve(
            drive, str(body.get("ref") or body.get("link") or ""), community=_community(), root=_root(), private=_private()))
    slot = str(body.get("slot") or "").strip()
    if not slot:
        raise ValueError("name the slot the folder is bound to (slot)")
    return _with_drive(lambda drive: drive_choose.bound_files(
        drive, str(body.get("folder") or ""), slot, community=_community(), root=_root(), private=_private()))
