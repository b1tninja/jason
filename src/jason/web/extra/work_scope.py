"""Who may read a workflow definition and its runs on the Work screens, and who sees a held run in full
(docs/console/screens/work.md, "Held and administrator runs"; docs/workflows-engine.md).

A definition is ``Visibility.BOARD`` (every office that opens P2), ``ADMIN`` (an administrator only), or ``HELD`` (a member's
discipline, a parcel and a balance, or restricted records: CIV 4935(e) lets the open record name the matter only generally).

- **BOARD**: the viewer's offices open P2 (the manager and every board office).
- **ADMIN**: the viewer is an administrator (``Viewer.admin``). An administrator who holds no office reaches the Work
  loaders for these alone; one who also holds an office sees them beside the board's. For anyone else the definition is not
  listed, its runs are not listed or counted, a read of one is the 404 a missing run gets, and starting one is the refusal an
  unknown definition gets.
- **HELD**: a run is shown in full only in the private view (``access.private_window()`` open, for a viewer whose offices open
  P3 in it), and each such opening is a line in ``access/served.jsonl`` under the run's id. Outside it a run is its general
  title, its state, its group, and the basis word of its date, with an opaque handle.

Where no one is signed in because the console has no sign-in set up (the loopback default), the viewer is None: ADMIN
definitions read as they do for the jobs loader, and a held run reads reduced (the private view needs a sign-in). Outside a
request (a script, the Python API) the caller is the person at the terminal and everything reads in full, with no log.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

HELD_NOTE = "Open the private view to see this run."
HELD_START = ("A run of this kind concerns a member's discipline, an account, or a restricted record, so it starts only in the "
              "private view. Open the private view (at the top of the console) for a stated reason.")
NOT_FROM_CONSOLE = "{title} is a terminal procedure: the console never starts it. Start it from a terminal (jason workflow)."
STEP_WORDS = "a step"


@dataclass(frozen=True)
class Scope:
    """What the viewer on this request may read of the workflows: ``board`` (their offices open P2), ``admin`` (an
    administrator), ``private`` (the private view is open and their offices open P3 in it). ``viewer`` is None outside a
    request or where sign-in is not set up."""

    viewer: Any = None
    board: bool = True
    admin: bool = True
    private: bool = True

    def reads(self, wf: Any) -> bool:
        """Whether the definition (and so its runs) is the viewer's to know of at all."""
        from jason.workflows.types import Visibility

        return self.admin if wf.visibility is Visibility.ADMIN else self.board

    def holds_back(self, wf: Any) -> bool:
        """Whether a run of this definition shows reduced: it is held and the private view is not open for this viewer."""
        from jason.workflows.types import Visibility

        return wf.visibility is Visibility.HELD and not self.private

    def opens_held(self, wf: Any) -> bool:
        """Whether a run of this definition is shown in full from the private view (the opening is logged)."""
        from jason.workflows.types import Visibility

        return wf.visibility is Visibility.HELD and self.private and self.viewer is not None


def scope_of(viewer: Any) -> Scope:
    """The viewer's scope. ``viewer`` is ``access.current_viewer()``."""
    from flask import has_request_context

    from jason.web import access

    if viewer is None:
        return Scope(private=not has_request_context())
    board = access.may_see(viewer, access.Level.P2)[0]
    private = bool(access.private_window() is not None and not viewer.acting
                   and access.may_see(viewer, access.Level.P3, private=True)[0])
    return Scope(viewer, board=board, admin=bool(viewer.admin), private=private)


def gate() -> Any:
    """The request's viewer for a Work loader. 401 signed out; 403 with ``access.may_see``'s sentence unless the viewer's
    offices open P2 or the viewer is an administrator (who then reads the ADMIN definitions alone, ``Scope.board`` False)."""
    from werkzeug.exceptions import HTTPException

    from jason.web import access, gates

    try:
        gates.check(gates.P2)
    except HTTPException as exc:
        viewer = access.current_viewer()
        status = getattr(getattr(exc, "response", None), "status_code", 0)
        if viewer is not None and viewer.admin and status == 403:
            return viewer
        raise
    return access.current_viewer()


def log_opening(scope: Scope, address: str, **more: Any) -> None:
    """One line in ``access/served.jsonl`` for a held run opened in full (P3, with the private view's id and reason), or a 503
    that serves nothing when it cannot be written. Nothing outside a request or with no signed-in viewer."""
    if scope.viewer is None:
        return
    from jason.web import access

    access.log_or_refuse(scope.viewer, access.Level.P3, address=address, **more)


__all__ = ["HELD_NOTE", "HELD_START", "NOT_FROM_CONSOLE", "STEP_WORDS", "Scope", "gate", "log_opening", "scope_of"]
