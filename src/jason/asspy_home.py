"""Where asspy keeps its per-county files, and a way to name it from jason's own settings.

asspy (the county assessor and clerk-recorder package) keeps its index caches, association directories, roll downloads,
and browser samples under one folder: ``ASSPY_HOME`` in the process environment, else asspy's own user config
(``~/.asspy/.env``), else ``~/.asspy``. asspy does not read jason's ``.env``, so a project ``.env`` or jason's user config
that names ``ASSPY_HOME`` moved nothing. ``apply`` copies that value into the environment before jason first asks asspy
for a county's file, so a checkout can name its own folder. The machine's one folder belongs in asspy's own config.

Nothing set means nothing changes: the environment's own ``ASSPY_HOME`` wins, and with neither asspy's default stands.
"""

from __future__ import annotations

import os


def apply() -> str:
    """Make ``ASSPY_HOME`` (process environment, else jason's ``.env``) the folder asspy uses; the folder named, or
    "" when none is (asspy then uses its own default). Call it before asking asspy for a county's file."""
    current = (os.environ.get("ASSPY_HOME") or "").strip()
    if current:
        return current
    from jason.config import _env_value

    named = _env_value("ASSPY_HOME")
    if named:
        os.environ["ASSPY_HOME"] = named
    return named
