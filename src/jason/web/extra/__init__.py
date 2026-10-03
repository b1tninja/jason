"""Per-feature sources and writers for the web UI, one module each, registered lazily in ``jason.web.sources``.

A module here exposes loaders (``args -> dict``) and, when the feature records a person's decision, a
``write(key, body) -> dict`` into jason's own store. Nothing here writes outward.
"""
