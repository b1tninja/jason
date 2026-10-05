"""jason-web's flags, in a module that imports nothing heavy: ``jason-web`` and ``jason serve`` both add them, and the
CLI builds its parser without loading Flask."""

from __future__ import annotations

import argparse
from pathlib import Path


def add_arguments(p: argparse.ArgumentParser) -> None:
    """jason-web's flags, which `jason serve` carries over."""
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--dist", type=Path, default=None, help="built UI folder (default ui/dist)")
    p.add_argument("--allow-apply", action="store_true",
                   help="turn on POST /api/approvals/<id>/apply: an approved plan written to PayHOA, after a live "
                        "re-read, by the named person who echoes its fingerprint. Off by default")
    p.add_argument("--require-sign-in", action="store_true",
                   help="refuse every write until an officer signs in with Google (docs/setup.md, Console sign-in)")
    p.add_argument("--dev", action="store_true",
                   help="not production: a signed-in admin (data/access/admins.json) may view the console as any "
                        "officer or office; writes are refused while they do")


__all__ = ["add_arguments"]
