"""The console's setup view over onboarding, and the intake answer route (docs/onboarding-ux.md, Setting up in the
console; docs/console/screens/onboarding.md).

- ``GET /api/onboarding-session``: the session ``jason onboard`` builds, read-only. The five stage gates, each
  checklist item with its *computed* status (present, partial, missing: from its checks, never from a click), each
  item's ``FactAsk`` as a question with where its answer goes, the next questions ranked by what each answer unblocks,
  and the answers waiting to be applied. An item that is a connection (a Keeper-held sign-in, a credential setting) is
  ``connect``: the terminal command, never a field for a secret. No answer's value is ever in it: an answered question
  says who answered and when.
- ``POST /api/write/intake/<id>``: ``{answer, by}`` records a signed-in roster person's answer in the intake queue
  (``jason.api.answer_intake_question``); ``{confirm: true, by}`` is a second person's confirmation of a high-stakes
  answer (``jason.api.onboarding_confirm``). It writes only ``data/intake/asks.json``: applying stays a person's
  ``jason onboard --apply`` (or ``jason intake --apply``) in a terminal, which merges a private fact into
  ``data/spec`` and turns a profile fact into a proposal. An answer that looks like a secret is refused with the
  reason, and the value is neither stored nor echoed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

Args = dict[str, str]

APPLY = "jason onboard --apply"
APPLY_INTAKE = "jason intake --apply"
LOGIN = "jason login"
NEXT_LIMIT = 20
CAVEATS = (
    "A gate is jason's reading of the checklist; the board decides what is done. An item is present when its checks "
    "pass, never by a click.",
    "An answer goes to the intake queue and nothing more. A person applies it in a terminal (jason onboard --apply): a "
    "private fact merges into the private facts, and a profile fact becomes a proposal for the profile's maintainer.",
    "A suggestion is jason's lead, not an answer. A secret is never typed here: it goes in Keeper, and the answer is the "
    "Keeper record's name.",
)


# --- the read ----------------------------------------------------------------------------------------------------------

def _settings() -> Any:
    """The settings, so the checks that read a Keeper record UID see it set; None without a .env."""
    try:
        from jason.config import Settings

        return Settings.load()
    except Exception:  # noqa: BLE001 - no .env: those checks read as not set
        return None


def connect_of(item: Any, ask_id: str = "") -> dict[str, Any] | None:
    """How a connection item is connected, when it is one: an item checked by a credential setting, or whose answer
    is only the Keeper record's name (a sign-in, the keys and codes). The commands run in a terminal; the browser never
    handles a secret, nor a field where one could be typed."""
    from jason.community.onboarding import FactRecord, Setting

    setting = any(isinstance(c, Setting) for c in item.checks)
    keeper = item.ask is not None and item.ask.record is FactRecord.KEEPER
    if not (setting or keeper):
        return None
    commands: list[str] = []
    if setting:
        commands.append(LOGIN)
        if item.fetch and item.fetch != LOGIN:
            commands.append(item.fetch)
    if keeper and ask_id:
        commands.append(f'jason onboard --answer {ask_id} "KEEPER RECORD NAME" --by "YOUR NAME"')
    return {"commands": commands,
            "note": "Credentials are Keeper records, signed in at a terminal. The console never takes a password, a "
                    "code, or a token; a Keeper record is named by its title only."}


def _answered(a: Any) -> dict[str, Any]:
    """A question's queue state, never its answer's value."""
    from jason.community import intake

    high = intake.high_stakes(a)
    return {"state": a.status.value, "answeredBy": a.answered_by, "answeredAt": a.answered_at,
            "confirmedBy": a.confirmed_by, "confirmedAt": a.confirmed_at, "highStakes": high,
            "needsConfirmation": bool(high and a.status is intake.AskStatus.ANSWERED and not a.confirmed_by)}


def _apply_for(kind: Any) -> str:
    from jason.community.intake import AskKind

    return APPLY if kind in (AskKind.FACT, AskKind.MAP) else APPLY_INTAKE


def onboarding_session(args: Args) -> dict[str, Any]:
    """The setup view: gates, items with their computed status, the next questions, and what waits to be applied.
    ``limit`` caps the next questions (default 20); ``group`` and ``stage`` narrow them; ``kinds`` (default
    ``fact,map``, onboarding's own questions; ``all`` for every kind) picks them, and ``otherOpen`` counts the rest."""
    from jason.community import community
    from jason.community.intake import AskKind, AskStatus, ask_id
    from jason.community.onboarding import stages_of
    from jason.mcp.county import _data_dir
    from jason.tasks import onboarding_session as task

    root = _data_dir(None)
    try:
        session = task.build(community(), root, settings=_settings())
    except Exception as exc:  # noqa: BLE001 - the screen says why, with the command that checks the profile
        return {"found": False, "note": f"The onboarding session could not be built: {type(exc).__name__}: {exc}",
                "command": "jason spec"}
    try:
        limit = max(1, min(200, int(args.get("limit") or NEXT_LIMIT)))
    except ValueError:
        limit = NEXT_LIMIT
    queue = {a.id: a for a in session.queue}
    items, connect_keys = [], {}
    for r in session.results:
        ident = ask_id(AskKind.FACT, f"fact:{r.item.key}", "") if r.item.ask else ""
        connect = connect_of(r.item, ident)
        if connect:
            connect_keys[r.item.key] = connect
        ask = None
        if r.item.ask is not None:
            stored = queue.get(ident)
            ask = {"id": ident, "question": r.item.ask.question, "record": r.item.ask.record.value,
                   "stakes": r.item.ask.stakes, "inQueue": ident in session.stored,
                   **(_answered(stored) if stored is not None else {"state": "not asked"})}
        items.append({"key": r.item.key, "group": r.item.group.value, "groupTitle": r.item.group.title,
                      "title": r.item.title, "why": r.item.why, "status": r.status.value,
                      "findings": [{"passed": f.passed, "evidence": f.evidence} for f in r.findings],
                      "fetch": r.item.fetch, "byPerson": r.item.by_person,
                      "stages": [s.value for s in stages_of(r.item.key)], "ask": ask, "connect": connect})
    ranked = session.questions(group=str(args.get("group") or ""), stage=str(args.get("stage") or ""))
    kinds = str(args.get("kinds") or "fact,map").strip()
    wanted = None if kinds == "all" else {k.strip() for k in kinds.split(",") if k.strip()}
    rows = [q for q in ranked if wanted is None or q.ask.kind.value in wanted]
    nxt = []
    for q in rows[:limit]:
        row = task.question_dict(q, session.stored)
        row["record"] = str(q.ask.detail.get("record") or "")
        row["connect"] = connect_keys.get(q.ask.serves)
        nxt.append(row)
    waiting = [{"id": a.id, "kind": a.kind.value, "subject": a.subject, "question": a.question, "serves": a.serves,
                "apply": _apply_for(a.kind), **_answered(a)}
               for a in session.queue if a.status is AskStatus.ANSWERED]
    out = task.status_dict(session)
    out["counts"] = out.pop("questions")
    out.update(found=True, asOf=datetime.now(timezone.utc).isoformat(timespec="seconds"), items=items, next=nxt,
               nextTotal=len(rows), otherOpen={"count": len(ranked) - len(rows), "command": "jason intake"},
               answered=waiting,
               apply={"command": APPLY, "note": "Applies every answered question a second person has confirmed where "
                                                "one must: a private fact merges into the private facts with a backup "
                                                "and a diff; a profile fact becomes a proposal. Run by a person."},
               caveats=list(CAVEATS))
    return out


# --- the write ---------------------------------------------------------------------------------------------------------

def _person(body: dict[str, Any]) -> str:
    """The signed-in roster person who writes, as themselves: 401 when no one is signed in (or sign-in is not set up),
    403 while an admin views the console as someone else or for another name; ``ValueError`` when ``by`` is not given."""
    from flask import abort

    from jason.web import access

    viewer = access.signed_in()
    if viewer.acting:
        abort(access.refusal(403, f"Viewing as {viewer.label} (admin view): an answer goes on the record only as "
                                  "yourself. Go back to yourself to answer."))
    by = " ".join(str(body.get("by") or "").split())
    if not by:
        raise ValueError("An answer names who gave it: give by (your name).")
    if by.casefold() != viewer.name.casefold():
        abort(access.refusal(403, f"Signed in as {viewer.name}: an answer goes on the record under the signed-in "
                                  f"name, not {by}."))
    return viewer.name


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """``POST /api/write/intake/<id>``: a signed-in person's answer (``{answer, by}``) or second-person confirmation
    (``{confirm: true, by}``). Queued, never applied."""
    from jason.community import intake
    from jason.mcp.county import _data_dir
    from jason.mcp.governance import answer_intake_question, onboarding_confirm

    ident = str(key or "").strip()
    if not ident or "/" in ident:
        raise KeyError(key)
    by = _person(body)
    root = _data_dir(None)
    if body.get("confirm") is True:
        done = onboarding_confirm(ident, by, data_dir=root)
        if "error" in done:
            _raise(done["error"], ident)
        return {"id": done["id"], "status": "answered", "answeredBy": done["answeredBy"],
                "answeredAt": done["answeredAt"], "confirmedBy": done["confirmedBy"],
                "confirmedAt": done["confirmedAt"], "highStakes": done["highStakes"], "needsConfirmation": False,
                "applied": False, "apply": APPLY, "next": f"Confirmed. A person applies it in a terminal: {APPLY}."}
    answer = " ".join(str(body.get("answer") or "").split())
    if not answer:
        raise ValueError("Give an answer: a choice, or your own words (dismiss closes the question).")
    why = intake.secret_reason(answer)
    if why:
        raise ValueError(f"Not stored: {why}. jason keeps no secrets. Put it in Keeper, and answer with the Keeper "
                         "record's name (its title, not its value or id).")
    done = answer_intake_question(ident, answer, by, data_dir=root)
    if "error" in done:
        _raise(done["error"], ident)
    stored = next((a for a in intake.load(root) if a.id == ident), None)
    state = _answered(stored) if stored is not None else {"highStakes": bool(done.get("highStakes")),
                                                          "needsConfirmation": bool(done.get("highStakes"))}
    apply = _apply_for(stored.kind) if stored is not None else APPLY
    out = {"id": done["id"], "status": done["status"], "answeredBy": done["answeredBy"],
           "answeredAt": state.get("answeredAt", ""), "highStakes": state["highStakes"],
           "needsConfirmation": state["needsConfirmation"], "applied": False, "apply": apply}
    if done["status"] == "dismissed":
        out["next"] = "Dismissed. Nothing is applied."
    elif out["needsConfirmation"]:
        out["confirm"] = f'jason onboard --confirm {ident} --by "SECOND PERSON"'
        out["next"] = ("Answered, waiting on a second person: someone other than "
                       f"{done['answeredBy']} confirms it here or with {out['confirm']}; then a person runs {apply}.")
    else:
        out["next"] = f"Answered, waiting to be applied: a person runs {apply} in a terminal."
    return out


def _raise(error: str, ident: str) -> None:
    """The answer path's refusal as the route's: an unknown question a 404, any other a 400 with its words."""
    if error.rstrip().endswith(repr(ident)):
        raise KeyError(ident)
    raise ValueError(error)


__all__ = ["APPLY", "connect_of", "onboarding_session", "write"]
