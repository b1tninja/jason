"""The step panel's guide, enable state, and nudge for a run page (docs/console/screens/work-guide.md, "Data").

``attach`` puts three objects on each person step of ``jason.web.extra.work.compose_run``'s steps: ``enable`` (the first of the ten states
that applies to this viewer, who holds the step, what is missing), ``nudge`` (the band, the date and whose it is, who else sees it, a
claim), and ``guide`` (the sections of the panel, each derived where the definition wrote nothing). The composing is
``jason.tasks.step_guide``, shared with ``jason workflow --guide`` and ``--due``; this module only supplies the web's viewer, the roster,
and the last recorded state of the integrations.

It reads the run already folded, the roster, the stores a guide read asks, the authorities shelf (the read-through to the outside held
off), and ``integrations.json``; it writes nothing and calls no outside system. A held run outside the private view never reaches it:
``held_page`` has no steps.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Iterable

from jason.tasks import step_guide
from jason.workflows import api, guide as guide_mod, nudge
from jason.workflows.types import Workflow


def holders_now() -> step_guide.Holders:
    """The roster by office from the community's officers and its administrators. A roster that cannot be read is an unknown one (no
    office is then called vacant)."""
    try:
        from jason import access

        officers = tuple(access.community_officers())
    except Exception:  # noqa: BLE001 - no community chosen, or officers that cannot be read: unknown, not vacant
        officers = ()
    try:
        from jason import access

        admins = tuple(access.admins())
    except Exception:  # noqa: BLE001
        admins = ()
    return step_guide.Holders.from_officers(officers, admins)


def integration_states(keys: Iterable[str]) -> dict[str, str]:
    """Each integration's last *recorded* state (``integrations.json``, read from disk): ``ok`` when connected, the state's words when
    it is not signed in, ``unknown`` when nothing is recorded. Names only; nothing is probed and no credential is read."""
    keys = list(dict.fromkeys(keys))
    if not keys:
        return {}
    try:
        from jason.community.profile import profile_name
        from jason.integrations import connections
        from jason.integrations.registry import ConnectionState

        rows = connections.load(profile_name())
    except Exception:  # noqa: BLE001 - a store that cannot be read is unknown, not a refusal
        return {k: "unknown" for k in keys}
    out = {}
    for k in keys:
        row = rows.get(k)
        out[k] = "unknown" if row is None else ("ok" if row.state is ConnectionState.CONNECTED else row.state.value)
    return out


def integration_names(keys: Iterable[str]) -> dict[str, str]:
    try:
        from jason.integrations.registry import integration

        return {k: integration(k).name for k in keys}
    except Exception:  # noqa: BLE001 - an unknown key is shown as it is
        return {k: k for k in keys}


def procedure_of(wf: Workflow, community: Any) -> Any:
    if not wf.procedure:
        return None
    try:
        from jason.community.procedures import find

        return find(wf.procedure, community)
    except Exception:  # noqa: BLE001 - no procedure is no derived text, never an error on the page
        return None


def attach(root: Path, wf: Workflow, view: Any, events: list[Any], steps: list[dict[str, Any]], who: Any, day: date, readers: Any, *,
           acting_as: str = "", community: Any = None) -> None:
    """Add ``enable``, ``nudge`` and ``guide`` to each person step's dict (a check, a job, and a plan have none: they are jason's)."""
    holders = holders_now()
    claims = nudge.claims_of(events)
    proc = procedure_of(wf, community)
    backup_for = getattr(community, "backup_for", None) if community is not None else None
    cache: dict[str, dict[str, Any]] = {}
    wanted = [s for s in wf.steps if guide_mod.spec(s, proc).integrations]
    keys = [k for s in wanted for k in guide_mod.spec(s, proc).integrations]
    states = integration_states(keys)
    names = integration_names(keys)
    by_id = {s["id"]: s for s in steps}
    for sd in wf.steps:
        if not nudge.is_person_step(sd):
            continue
        row, sv = by_id.get(sd.id), view.step(sd.id)
        if row is None or sv is None:
            continue
        offices = {r.value for r in sd.acting_roles if r.value not in ("anyone", "jason", "scheduler")}
        n = nudge.step_nudge(wf, sd, view, day, vacant=holders.vacant(offices), claims=claims)
        row["nudge"] = step_guide.nudge_dict(n, who_account=who.account)
        row["enable"] = step_guide.enable_dict(
            wf, sd, sv, view, who, holders, acting_as=acting_as, controls=row.get("controls") or (), integrations=states,
            first_by=api.pending_first(events, sd.id, "attest"), backup_for=backup_for, procedure=proc, integration_names=names)
        row["guide"] = step_guide.guide_dict(
            root, wf, sd, view, sv, day=day, readers=readers, roster=holders, who=who, name=who.account, run_id=view.id,
            community=community, procedure=proc, backup_for=backup_for, cache=cache)


__all__ = ["attach", "holders_now", "integration_names", "integration_states", "procedure_of"]
