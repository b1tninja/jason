"""The form library: forms built in for the law a community is under, forms its documents create, and forms it writes.

The design is docs/form-library-design.md. In short:

- ``tiers``: ``Tier``, ``Jurisdiction``, ``FormDefinition`` (a ``FormTemplate`` plus what makes it a form the law reaches),
  the registry (``register``, ``definitions``), and what a profile gives the library: ``Slot``, ``Adjust``, ``Add``,
  ``Bind``.
- ``resolve``: ``resolve(community)`` applies the community's slots, adjustments, and bindings to the library's forms for
  its jurisdictions, then its own forms. ``Community.forms()`` returns the templates of the forms it offers.
- ``check``: ``check(resolved, data_dir)``, the seven checks (``jason form-library --check``).
- ``handlers``: the handlers a form may name, until the handler registry exists.
- ``us``, ``ca``: the packs, one module a form. ``custom``: templates the library ships for a community's own forms.

A pack holds definitions and nothing else, and no pack imports another. Nothing here names an association: a community's
facts are slots. Importing this package loads no pack and no profile; a pack is imported when a jurisdiction is asked for.
"""

from jason.community.form_library.tiers import (
    ATTESTATION,
    CARRIERS,
    DESCRIPTION,
    LIBRARY,
    PREAMBLE,
    SIGNATURE,
    TOKEN,
    Add,
    Adjust,
    Bind,
    Channel,
    Check,
    Clock,
    DayKind,
    Finding,
    FormDefinition,
    Jurisdiction,
    JURISDICTIONS,
    Library,
    Required,
    SetBy,
    Severity,
    Slot,
    Status,
    Tier,
    definitions,
    question_from_dict,
    register,
)

__all__ = ["ATTESTATION", "Add", "Adjust", "Bind", "CARRIERS", "Channel", "Check", "Clock", "DESCRIPTION", "DayKind",
           "Finding", "FormDefinition", "JURISDICTIONS", "Jurisdiction", "LIBRARY", "Library", "PREAMBLE", "Required",
           "SIGNATURE", "SetBy", "Severity", "Slot", "Status", "TOKEN", "Tier", "definitions", "question_from_dict", "register"]
