"""The California pack: the forms the Davis-Stirling Act and the codes around it require, one module a form.

Importing this package registers each definition in the shipped library (``jason.community.form_library.register``). The
order is the order ``forms()`` lists them. A pack holds definitions and nothing else: a form's facts about one association
are slots, and no module here names an association. The forms to come are listed in docs/form-templates.md.
"""

from jason.community.form_library.ca import idr, records

__all__ = ["idr", "records"]
