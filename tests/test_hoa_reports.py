"""An association's page from the land: its maps, common parcels and the deeds that conveyed them, its homes and
turnover, its recordings, and its maps drawn; owners named only when asked. Made-up names and numbers throughout."""

from datetime import date
from types import SimpleNamespace

from asspy.associations import Sighting
from asspy.core import IndexedInstrument
from asspy.land import LandStore
from asspy.sacramento.gis import MappedParcel

from jason.tasks.hoa_reports import _Context, association_page

ASSOCIATION = "EXAMPLE TERRACE OWNERS ASSOCIATION"


def _parcel(apn, number, *, land_use="A1G00A", lot="1"):
    return MappedParcel(apn, "ACTIVE", land_use, "S401012", "EXAMPLE TERRACE", lot, "", "", "", "GD", number)


def _context(store: LandStore) -> _Context:
    ctx = object.__new__(_Context)
    ctx.land = store
    ctx.associations = {ASSOCIATION: SimpleNamespace(key=ASSOCIATION, name=ASSOCIATION, kind=SimpleNamespace(value="homeowners"),
                                                     standing=SimpleNamespace(value="confirmed"), first=date(2015, 1, 2),
                                                     last=date(2024, 5, 6), evidence=__import__("collections").Counter({"assessment lien": 2}),
                                                     names=(ASSOCIATION,))}
    ctx.sightings = {ASSOCIATION: (Sighting(ASSOCIATION, ASSOCIATION, "201501020100", "NOTICE OF ASSOCIATION LIEN", date(2015, 1, 2)),)}
    ctx.governing, ctx.links, ctx.plans, ctx.by_name, ctx.choosable = {}, {}, {}, {}, [ASSOCIATION]
    ctx.divisions = []
    ctx.maps = {"S401012": {"name": "EXAMPLE TERRACE UNIT 1", "number": "199001020100", "recorded": "1990-01-02", "lots": 3, "lettered_lots": 1}}
    from asspy.land import common_area_owners

    ctx.owners = common_area_owners(store)
    return ctx


class _Gis:
    def features(self, where):
        square = {"type": "Polygon", "coordinates": [[[-121.5, 38.5], [-121.5, 38.5001], [-121.4999, 38.5001], [-121.5, 38.5]]]}
        return [{"type": "Feature", "geometry": square, "properties": {"APN_DASH": "000-0000-001-0000", "LANDUSE": "AQ000A", "LOT": "A"}},
                {"type": "Feature", "geometry": square, "properties": {"APN_DASH": "000-0000-002-0000", "LANDUSE": "A1G00A", "LOT": "1"}}]

    def land_use(self, code):
        return None


def test_a_page_ties_the_common_parcel_to_its_association_and_names_no_owner(tmp_path):
    with LandStore(tmp_path / "land.db") as store:
        seen = "2026-10-01T00:00:00+00:00"
        for parcel in (_parcel("000-0000-001-0000", "199001030200", land_use="AQ000A", lot="A"),
                       _parcel("000-0000-002-0000", "202105060300"), _parcel("000-0000-003-0000", "202205060400")):
            store.put_parcel(parcel, seen=seen)
        store.put_deed(IndexedInstrument("199001030200", date(1990, 1, 3), "0200", "685", "GRANT DEED",
                                         ("(R) EXAMPLE BUILDERS LLC", f"(E) {ASSOCIATION}")))
        store.put_deed(IndexedInstrument("202105060300", date(2021, 5, 6), "0300", "685", "GRANT DEED",
                                         ("(R) EXAMPLE PERSON A", "(E) SAMPLE OWNER B")))
        ctx = _context(store)
        page = association_page(ctx, ASSOCIATION, tmp_path / "page", gis=_Gis(), today=date(2026, 10, 10))
        text = page.path.read_text(encoding="utf-8")
        assert (page.parcels, page.owned, page.maps) == (3, 1, ["S401012"])
        assert "EXAMPLE TERRACE UNIT 1" in text and "| 000-0000-001-0000 | A |" in text and "199001030200" in text
        assert "| 2021 | 1 |" in text and "notice of association lien 1" in text
        assert "SAMPLE OWNER B" not in text and "EXAMPLE PERSON A" not in text      # no owner named unless asked
        assert (tmp_path / "page" / "map.svg").read_text().startswith("<svg") and "<kml" in (tmp_path / "page" / "footprint.kml").read_text()
        named = association_page(ctx, ASSOCIATION, tmp_path / "named", names=True, deeds=True, today=date(2026, 10, 10))
        assert "SAMPLE OWNER B" in named.path.read_text(encoding="utf-8")
