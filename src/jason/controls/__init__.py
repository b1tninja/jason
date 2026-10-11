"""Controls: the safeguards a board opts into. jason suggests; the board adopts; the approvals engine enforces only
what was adopted, and only ever the stricter of a kind's own rule and a control (docs/controls.md).

- ``types``: ``ControlType``, ``Control``, their states and acts, and the parameter algebra (what is stricter).
- ``catalog``: the control types, written once for any association.
- ``store``: the adopted controls (a private fact) and the append-only log of acts on them.
- ``effective``: ``validate``, ``in_force``, ``effective_approver``, and ``requires_second``, which the approvals engine asks.

Importing this package loads no profile and reads no file.
"""
