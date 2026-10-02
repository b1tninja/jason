"""Flood buildings. Odd and even numbers on one street are different buildings."""

from jason.community.base import BuildingRange
from jason.community.symbols import Building, Parity, Street

BUILDINGS: tuple[BuildingRange, ...] = (
    BuildingRange(Building.BLDG_1, Street.MACON_DR, 3024, 3044, Parity.EVEN),
    BuildingRange(Building.BLDG_2, Street.ENCHANTED_WALK, 3007, 3039, Parity.ODD),
    BuildingRange(Building.BLDG_3, Street.ENCHANTED_WALK, 3006, 3048, Parity.EVEN),
    BuildingRange(Building.BLDG_4, Street.MAGICAL_WALK, 3007, 3039, Parity.ODD),
    BuildingRange(Building.BLDG_5, Street.MAGICAL_WALK, 3006, 3040, Parity.EVEN),
    BuildingRange(Building.BLDG_6, Street.MESMERIZING_WALK, 3007, 3039, Parity.ODD),
    BuildingRange(Building.BLDG_7, Street.MESMERIZING_WALK, 3010, 3040, Parity.EVEN),
    BuildingRange(Building.BLDG_8, Street.WHIMSICAL_LN, 5607, 5651, Parity.ANY),
)
