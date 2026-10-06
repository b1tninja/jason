"""The California pack: the forms the Davis-Stirling Act and the codes around it require, one module a form.

Importing this package registers each definition in the shipped library (``jason.community.form_library.register``). The
order is the order ``forms()`` lists them. A pack holds definitions and nothing else: a form's facts about one association
are slots, and no module here names an association. The forms to come are listed in docs/form-templates.md.
"""

from jason.community.form_library.ca import idr, records
from jason.community.form_library.ca import architectural
from jason.community.form_library.ca import reconsideration
from jason.community.form_library.ca import ev_charger
from jason.community.form_library.ca import solar
from jason.community.form_library.ca import protected_use
from jason.community.form_library.ca import delivery_change
from jason.community.form_library.ca import secondary_address
from jason.community.form_library.ca import individual_delivery
from jason.community.form_library.ca import candidate_nomination
from jason.community.form_library.ca import meeting_comment
from jason.community.form_library.ca import adr, disputed_charge, membership_list, payment_plan, resale

__all__ = ["idr", "records"]
