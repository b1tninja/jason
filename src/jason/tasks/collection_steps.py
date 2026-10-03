"""The board's collection steps on a delinquent account, recorded once per step, where the delinquency page reads them.

``association_collections`` reads the ledger beside the liens and gives each account a standing and the statute's next
step. The step the board actually takes is written here, in ``data/board/collection-steps.json``, one list per parcel:
the step, the day the board decided, who recorded it, the vote as the board took it, and a note. jason records the
board's step; it submits an account to no collection agency, records no lien, and forecloses on nothing. A lien is
recorded only after a majority vote of the board in an open meeting, by roll call, recorded in the minutes (Civil Code
5673); foreclosure only after a vote in executive session (Civil Code 5705) and when the floor of 5720 is met.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

STORE = Path("board") / "collection-steps.json"


class Step(Enum):
    RELEASE_RECORDED = "release recorded"
    PAYMENT_PLAN_OFFERED = "payment plan offered"
    PRE_LIEN_NOTICE_SENT = "pre-lien notice sent (CIV 5660)"
    LIEN_RECORDED = "lien recorded (CIV 5673, open session roll call)"
    HANDED_TO_AGENCY = "handed to collection agency"
    FORECLOSURE_AUTHORIZED = "foreclosure authorized (CIV 5720)"
    WRITTEN_OFF = "written off"


STEPS = tuple(s.value for s in Step)
VOTE = re.compile(r"^\d+-\d+$")
ROLL_CALL_REMINDER = ("A lien is recorded only after a majority of the board votes for it in an open meeting, by roll call, "
                      "recorded in the minutes (Civil Code 5673); the vote here is the tally as recorded, not the roll call.")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load(data_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """The recorded steps by parcel, oldest first."""
    path = Path(data_dir) / STORE
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8")).get("accounts", {})
    return {apn: list(steps) for apn, steps in raw.items() if isinstance(steps, list)}


def save(data_dir: Path, accounts: dict[str, list[dict[str, Any]]]) -> Path:
    path = Path(data_dir) / STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"savedAt": _now(), "accounts": accounts}, indent=1), encoding="utf-8")
    return path


def _store_lock(fn):
    import functools

    from jason.locks import Resource, hold

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with hold(Resource.STORE, "collection-steps", timeout=60, purpose=f"collection steps: {fn.__name__}"):
            return fn(*args, **kwargs)
    return wrapper


@_store_lock
def record_step(data_dir: Path, apn: str, *, step: str, decided_on: str, by: str, vote: str = "", note: str = "") -> dict[str, Any]:
    """Append the board's step on ``apn``. ``vote`` is empty or ``<ayes>-<noes>``. Returns the account: its steps and latest."""
    apn, step, by, vote, note = apn.strip(), step.strip(), by.strip(), vote.strip(), note.strip()
    if not apn:
        raise ValueError("the step names the parcel")
    if step not in STEPS:
        raise ValueError(f"step is one of: {'; '.join(STEPS)}")
    if not by:
        raise ValueError("the step names who recorded it")
    day = date.fromisoformat(decided_on.strip())
    if vote and not VOTE.match(vote):
        raise ValueError("vote is empty or <ayes>-<noes>, such as 3-0")
    accounts = load(data_dir)
    steps = accounts.setdefault(apn, [])
    now = _now()
    history = (steps[-1].get("history") if steps else None) or []
    row = {"step": step, "decidedOn": day.isoformat(), "by": by, "vote": vote, "note": note, "recorded": now,
           "history": history + [f"{now[:10]}: {step} recorded by {by}"]}
    steps.append(row)
    save(data_dir, accounts)
    return account(data_dir, apn, accounts)


def account(data_dir: Path, apn: str, accounts: dict[str, list[dict[str, Any]]] | None = None) -> dict[str, Any]:
    """One parcel's recorded steps and its latest, or an empty record."""
    steps = (accounts if accounts is not None else load(data_dir)).get(apn, [])
    return {"apn": apn, "steps": steps, "latest": steps[-1] if steps else None}
