"""The library explorer's routes (docs/pdf-splitter.md, "Choosing a file from the library"). Disk only; the board's.

- ``GET /api/library-files`` (``?kind=&source=&since=&until=&text=&minPages=&draft=&sort=&order=&size=&page=``): the library's PDF
  files, a page at a time (50, at most 100), with the counts a filter chip shows. ``next`` is the token for ``?page=``. A file name
  is never taken from a URL: ``q`` here answers 400 and says to POST.
- ``POST /api/write/library/files`` ``{"q": "...", ...the same filters, "page": ...}``: the same list with a name to search for
  (so the name never sits in a web address, a log, or a history).

The owner view answers 403; a signed-in roster person whose offices open the board's level is needed where console sign-in is set
up. A file the library holds as confidential is named by its kind, carries no id, and is not matched by name outside the private
view. Nothing here calls Drive, PayHOA, or Gmail, or writes anything.
"""

from __future__ import annotations

from typing import Any

Args = dict[str, str]

POST_ONLY = ("A file name searched for is not put in a web address: POST /api/write/library/files with {\"q\": ...}.")
ACTS = ("files",)


def _gate(body: dict[str, Any] | None = None) -> None:
    from jason.web.extra.split import _gate as gate

    gate(body)


def _list(args: dict[str, Any]) -> dict[str, Any]:
    from jason.tasks import library_browse
    from jason.web.extra.record_slots import _private
    from jason.web.extra.split import _root

    return library_browse.files(
        _root(), q=str(args.get("q") or ""), kind=str(args.get("kind") or ""), source=str(args.get("source") or ""),
        since=str(args.get("since") or ""), until=str(args.get("until") or ""), has_text=args.get("text", args.get("hasText")),
        min_pages=args.get("minPages"), draft=args.get("draft"), sort=str(args.get("sort") or "modified"),
        order=str(args.get("order") or ""), size=args.get("size") or library_browse.PAGE, page=str(args.get("page") or ""),
        private=_private())


def library_files(args: Args) -> dict[str, Any]:
    _gate()
    if str(args.get("q") or args.get("text_query") or "").strip():
        raise ValueError(POST_ONLY)
    return _list(args)


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """``POST /api/write/library/files``: the list with a search by name. Reads disk only."""
    if key not in ACTS:
        raise KeyError(key)
    _gate(body)
    return _list(body)
