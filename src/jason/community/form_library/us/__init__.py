"""The federal pack: forms that federal law reaches in every state (the reasonable accommodation request; fair housing).

Importing this package registers each definition in the shipped library. The accommodation request is its first form: the
fair-housing statutes are not on the authorities shelf, so the definition recites only the Davis-Stirling Act's own references to
them and says so (docs/form-templates/accommodation-request.md). A community whose chain is ``("US", "CA")`` resolves it; one
whose chain is ``("CA",)`` does not.
"""

from jason.community.form_library.us import accommodation

__all__ = ["accommodation"]
