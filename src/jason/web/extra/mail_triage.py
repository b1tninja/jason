"""The mail-triage page: the mail brief's lanes, each letter with the person's recorded choice beside it.

The loader reads ``mail_brief`` (act, review, unscanned) and joins ``tasks.mail_triage``. The write records one
choice. jason scans, forwards, shreds, and discards nothing; the choice is recorded for the person to carry out at the
mail service.
"""

from __future__ import annotations

import inspect
from typing import Any

Args = dict[str, str]

LANES = ("act", "review", "unscanned")
CAVEATS = (
    "jason scans, forwards, shreds, and discards nothing. The choice is recorded here for the person who acts on it at the mail service, which may bill for a scan or a forward.",
    "A letter's kind and urgency are a sort by the sender's name and the letter's words, not a reading of what it means.",
)


def _brief(days: str) -> dict[str, Any]:
    from jason.mcp.county import mail_brief

    kwargs: dict[str, Any] = {}
    if days.strip():
        try:
            params = inspect.signature(mail_brief).parameters
        except (TypeError, ValueError):
            params = {}
        if "days" in params:
            kwargs["days"] = int(days)
    return mail_brief(**kwargs)


def mail_triage(args: Args) -> dict[str, Any]:
    """The brief's lanes with each letter's recorded choice and its document (``scan``, a ``DocRef``: the scanned PDF,
    else the envelope; docs/console/doc-component.md); ``days`` is forwarded when the tool takes it."""
    from jason.mcp.county import _data_dir
    from jason.tasks import mail_triage as store
    from jason.tasks.mail import scan_ref

    out = _brief(args.get("days", ""))
    root = _data_dir(None)
    choices = store.load(root)
    lanes = {lane: [{**row, "choice": choices.get(str(row.get("mailId", ""))), "scan": scan_ref(root, row)}
                    for row in (out.get(lane) or [])] for lane in LANES}
    return {**out, **lanes, "choices": list(store.CHOICES), "chosen": sum(1 for lane in lanes.values() for r in lane if r["choice"]),
            "caveats": [*CAVEATS, *(out.get("caveats") or [])]}


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """Record a person's ``choice`` for mail item ``key``, with ``by`` and a ``note``."""
    from jason.mcp.county import _data_dir
    from jason.tasks.mail_triage import choose

    return choose(_data_dir(None), key, choice=str(body.get("choice", "")), by=str(body.get("by", "")), note=str(body.get("note", "") or ""))
