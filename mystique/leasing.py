"""Mystique's leasing rules (jason.community.leasing).

CC&Rs 4.15 as amended by the Second Amendment, recorded under Civil Code 4741(f) (data/governing/ccrs-2nd-amendment.md):
at most 25 percent of the units may be rented at any one time (4.15(a), raised from 20 percent to meet the 25 percent
floor of 4741(b)), with a minimum lease of 30 days (4.15(m)(iii), cut from six months). An owner applies in writing to
the board (4.15); an approval carries through a vacancy of up to 60 days without reapplying (4.15(i)). The amended
4.15(m)(iii) also asks for proof of a tenant's criminal background check and credit report: sensitive records that stay
out of jason's shared catalogs, and whose use counsel should confirm under fair housing law.
"""

from __future__ import annotations

from jason.community.leasing import LeasingRules

LEASING = LeasingRules(cap_percent=25, min_term_days=30, reapply_after_days=60,
                       authority="CC&Rs 4.15(a) as amended by the Second Amendment; Civil Code 4741(b)")
