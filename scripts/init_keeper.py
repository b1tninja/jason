#!/usr/bin/env python3
"""Interactive Keeper login — prefer ``jason login``.

Kept for compatibility; delegates to the same flow as ``jason login``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jason.cli import cmd_login  # noqa: E402


class _Args:
    env = None
    no_persist_password = False


if __name__ == "__main__":
    raise SystemExit(cmd_login(_Args()))
