"""Templates the library ships for a community's own forms (a survey, a volunteer list), each a ``FormDefinition`` of the
``CUSTOM`` tier with a default handler. None yet (docs/form-library-design.md, build order 4): a community's own forms are
returned by its ``Community.custom_forms()``.
"""

from __future__ import annotations

from jason.community.form_library.tiers import FormDefinition

TEMPLATES: tuple[FormDefinition, ...] = ()

__all__ = ["TEMPLATES"]
