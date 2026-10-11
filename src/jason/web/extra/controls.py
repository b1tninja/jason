"""The Controls screen's loaders and its one write (docs/console/screens/controls.md):

- ``GET /api/controls[?family=&state=]``: every control, grouped by family, with its state in words, the provision's
  words whole, the floor, jason's reading (labeled as jason's), what it changes, the roster check (offices and counts, never
  a person), and its history; the last reading's questions; the counts.
- ``GET /api/control?key=``: one control with its provision as the documents hold it now, and a ``changed`` block when the
  words changed since the control was recorded (the control stays as the board left it).
- ``GET /api/control-notices?subject=KIND``: the one-line "required by a control" data for an approval kind (the effective
  rule and where it came from), a workflow step, or a send; read only.
- ``POST /api/write/controls/<key>`` with ``{act: "propose"}``: put the control before the board as a board item with the
  provision as evidence, in the signer's name. That is the only write. Adopting, declining, deferring, and retiring are the
  board's decisions, recorded by the secretary; this screen reads them. jason turns nothing on.

Who may open them: a signed-in person whose offices open P2 (the board's offices and the manager); 401 signed out, 403
with ``access.may_see``'s sentence otherwise. The owner view never reads them (``OWNER_SOURCES`` does not list them). A
write is the signed-in person's own: refused while an admin views as someone else, and a ``by`` in the body naming another
person is refused by the write guard. Disk only: nothing here calls PayHOA, Google, or a model.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

Args = dict[str, str]

ACTS = ("propose",)
ACTING_REFUSED = "Viewing as {who} (admin view): go back to yourself first. A control is put before the board in a person's own name."
NOT_YOURS = ("act is propose. Adopting, declining, deferring, and retiring a control are the board's decisions, recorded by "
             "the secretary in Decisions; this screen does not take them.")


def _root() -> Path:
    from jason.mcp.county import _data_dir

    return Path(_data_dir(None))


def _viewer(*, writing: bool = False):
    """The signed-in viewer whose offices open P2, or abort: 401 signed out, 403 where the offices do not open P2 (and, for a
    write, while an admin views as someone else). None outside a request (a script, or the Python API, where the caller is
    the person at the terminal)."""
    from flask import abort, has_request_context

    from jason.web import access

    if not has_request_context():
        return None
    viewer = access.signed_in()
    if writing and viewer.acting:
        abort(access.refusal(403, ACTING_REFUSED.format(who=viewer.label)))
    access.allow(viewer, access.Level.P2)
    return viewer


def _today() -> date:
    return date.today()


def controls(args: Args) -> dict[str, Any]:
    from jason.community import community
    from jason.controls import view

    _viewer()
    return view.compose(community(), _root(), family=(args.get("family") or "").strip(),
                        state=(args.get("state") or "").strip(), today=_today())


def control(args: Args) -> dict[str, Any]:
    from jason.community import community
    from jason.controls import view

    _viewer()
    return view.one(community(), _root(), (args.get("key") or "").strip(), today=_today())


def control_notices(args: Args) -> dict[str, Any]:
    from jason.community import community
    from jason.controls import view

    _viewer()
    amount = (args.get("amount") or "").strip()
    return view.notices(community(), _root(), (args.get("subject") or "").strip(), today=_today(),
                        amount_cents=int(amount) if amount.isdigit() else None)


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """``POST /api/write/controls/<key>`` with ``{act: "propose"}``: create or refresh the control's board item and record who
    put it before the board. 404 for a key with no control; 400 for another act, or a control whose state does not allow it.
    Changes no control to adopted, and records no decision."""
    from jason.community import community
    from jason.controls import view
    from jason.controls.propose import propose

    viewer = _viewer(writing=True)
    act = str(body.get("act") or "").strip()
    if act not in ACTS:
        raise ValueError(NOT_YOURS)
    by = viewer.account if viewer is not None else str(body.get("by") or "").strip()
    home, root = community(), _root()
    done = propose(key, by=by, data_dir=root, community=home)
    return {**done, "control": view.one(home, root, key, today=_today())["control"]}


__all__ = ["ACTS", "control", "control_notices", "controls", "write"]
