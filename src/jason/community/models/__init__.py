"""The document models, one module per group of kinds. Importing the package imports every module in it, and each
module registers its models (``jason.community.document_models.register``). A new module needs no entry here."""

from __future__ import annotations

import importlib
import pkgutil

for _info in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
    if not _info.name.startswith("_"):
        importlib.import_module(f"{__name__}.{_info.name}")
