"""Approvals: a write outside jason, planned from a live read, decided item by item by a named person, checked
against a second live read, and applied only as approved, every step in an append-only audit log.

- ``model``: the records (``Approval``, ``PlanItem``, ``DecisionRecord``, ``Signature``), the statuses and their
  transitions, and the fingerprints. Pure data.
- ``store``: one JSON file an approval in ``approvals/`` under the profile's data folder, under the store lock.
- ``audit``: ``audit.jsonl`` beside it, hash-chained and append only.
- ``registry``: the action kinds, each with its planner, applier, approver rule, and cost.
- ``engine``: ``plan``, ``decide``, ``submit``, ``confirm``, ``decline``, ``withdraw``, ``check``, and ``apply``.
- ``kinds``: the adapters over the task functions the CLI already calls (``owner-info-tags``).

The CLI is ``jason approvals``; ``jason-mcp`` reads approvals and never decides or applies one. The JSON contracts
for a console are in ``schemas/``. The design is docs/console/approval-workflow.md.
"""

from jason.approvals.engine import (Applied, Live, Planned, Recheck, Refused, apply, check, confirm, decide, decline,
                                    plan, submit, withdraw)
from jason.approvals.model import Approval, ApprovalStatus, Decision, ItemClass, PlanItem, Result

__all__ = ["Applied", "Approval", "ApprovalStatus", "Decision", "ItemClass", "Live", "PlanItem", "Planned", "Recheck",
           "Refused", "Result", "apply", "check", "confirm", "decide", "decline", "plan", "submit", "withdraw"]
