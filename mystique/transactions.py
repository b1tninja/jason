"""Utility identity. SMUD is listed first and blocks the city rule."""

from jason.community.base import TransactionRule
from jason.community.symbols import Utility

RULES: tuple[TransactionRule, ...] = (
    TransactionRule(
        utility=Utility.SMUD,
        category_id=1245405,
        rule_names=("SMUD",),
        description_contains=("SMUD",),
    ),
    TransactionRule(
        utility=Utility.CITY_OF_SACRAMENTO,
        category_id=1245485,
        rule_names=("SACRAMENTO",),
        description_contains=("SACRAMENTO UTIL",),
        description_contains_all=("CITY OF", "SACRAMEN"),
        description_requires="SACRAMENTO",
        description_any=("UTIL", "WATER", "CITY OF", "CASH CONCENTRAT"),
        blocked_by=(Utility.SMUD,),
    ),
)
