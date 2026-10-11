"""Put a suggested control before the board: a board item with the provision as its evidence, and a ``propose`` act.

This is the one thing a person may do with a suggestion here. It creates (or refreshes) the board item
``control-<key>`` (``jason.tasks.board_items.propose``: the board's own fields on an existing item are never overwritten),
and moves the control from *suggested* (or *deferred*, or *declined* once the date the board set has come) to *proposed*. It
adopts nothing, declines nothing, defers nothing, and retires nothing: those are the board's decisions, recorded by the
secretary (``jason.controls.store.record`` with the decision id). A control already *proposed* refreshes its item and
records no further act.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from jason.community.board_items import BoardItem, ItemCategory, Priority
from jason.controls import store
from jason.controls.types import Control, ControlAct, ControlState

ITEM_PREFIX = "control-"


def item_id(key: str) -> str:
    return f"{ITEM_PREFIX}{key}"


def item_for(control: Control) -> BoardItem:
    """The board item a proposal makes: the provision whole as its evidence, jason's reading labeled as jason's, and the
    ask in the board's own terms (decide; the floor stays, a control only adds)."""
    title = control.type.title
    cite = control.basis.citation or "the governing documents"
    evidence = [f'{cite}: "{control.basis.words}"' if control.basis.words else cite, f"jason controls --show {control.key}"]
    return BoardItem(
        id=item_id(control.key), title=f"Control to consider: {title}",
        summary=(f"jason read {cite} and suggests the {title.lower()} control. " + control.reading).strip(),
        ask=(f"Decide whether to adopt the {title.lower()} control, change it, or decline it. A control only adds to what "
             "the provision sets; jason adopts nothing, and the secretary records the board's decision."),
        category=ItemCategory.GOVERNANCE, priority=Priority.NORMAL, authority=cite, evidence=tuple(evidence))


def propose(key: str, *, by: str, data_dir: Path | None = None, community: Any = None, profile: str = "",
            today: date | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Create or refresh the control's board item, in ``by``'s name, and record the ``propose`` act. ``KeyError`` for a key
    with no control; ``ControlRefused`` (a ``ValueError``) when the control's state does not allow it, or a declined or
    deferred one may not be asked again yet. The item is made only after that check, so a refusal leaves nothing behind."""
    from jason.tasks import board_items

    by = (by or "").strip()
    if not by:
        raise ValueError("putting a control before the board names the person (by)")
    now = now or datetime.now(timezone.utc)
    current = store.get(key, data_dir, profile, community)
    item = item_for(current)
    again = current.state is ControlState.PROPOSED
    if not again:
        store.apply_act(current, {"key": key, "act": ControlAct.PROPOSE.value, "by": by, "why": "check",
                                  "at": now.isoformat(timespec="seconds")})       # pure: refused here writes nothing
    root = Path(data_dir) if data_dir is not None else _data_dir()
    counts = board_items.propose(root, [item], today=today)
    after = current if again else store.record(
        ControlAct.PROPOSE, key, by=by, why=f"put before the board as board item {item.id}", data_dir=data_dir,
        profile=profile, community=community, now=now)
    return {"key": key, "item": item.id, "state": after.state.value, "refreshed": again, "board": counts, "by": by}


def _data_dir() -> Path:
    from jason.config import data_dir

    return Path(data_dir())


__all__ = ["ITEM_PREFIX", "item_for", "item_id", "propose"]
