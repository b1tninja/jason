"""The theme and community-profile sources: brand tokens by scheme from the profile, a neutral answer without one, and
the public page's facts read through ``Community`` methods alone."""

import os
import sys
import types
from enum import Enum
from pathlib import Path

import pytest

import jason  # noqa: E402

os.environ["JASON_SPEC_DIR"] = str(Path(jason.__path__[0]).resolve().parents[1] / "tests" / "fixtures" / "spec")

from jason.community.base import Theme  # noqa: E402
from jason.web.extra import community_profile as profile_web  # noqa: E402
from jason.web.extra import theme as theme_web  # noqa: E402

# A fictional second community, in the test only: never a member of the checked-in profile.
CEDAR_HOLLOW = Theme(wordmark="Cedar Hollow", accent="#2f6b55", on_accent="#fff", accent_2="#c98a3a", on_accent_2="#1d1a14",
                     brand_font='"Bricolage Grotesque", system-ui, sans-serif', brand_weight=700, brand_case="none", brand_tracking="-.01em",
                     hero="#1f3a30", hero_ink="#f2f5ef", hero_muted="#bfd0c5", hero_line="#3b5a4d",
                     dark={"accent": "#7fcba8", "on_accent": "#10241c"})


class _Page(Enum):
    HOME = "home"
    RECORDS = "records"


class _Purpose(Enum):
    GENERAL = "the association's general inbox"
    ACCOUNTS_PAYABLE = "accounts payable"


class _Kind(Enum):
    CURRENT = "current mailing address"
    FORMER_MANAGER = "former manager's address"


class _Row:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Fake:
    """A profile with only what the public page asks for; ``theme`` is set per test."""

    name = "Small Community Association"
    corporate_name = "SMALL COMMUNITY ASSOCIATION"
    slug = "small"
    site = "https://small.example"

    def __init__(self, theme=None):
        self._theme = theme

    def theme(self):
        return self._theme

    def site_pages(self):
        return (_Row(page=_Page.HOME, path="/"), _Row(page=_Page.RECORDS, path="/records"))

    def mail_addresses(self):
        return (_Row(kind=_Kind.FORMER_MANAGER, label="old manager", zip=""), _Row(kind=_Kind.CURRENT, label="PO Box 1, Anytown", zip="90000"))

    def google_groups(self):
        return (_Row(name="HOA", purpose=_Purpose.GENERAL, address="hoa@small.example"), _Row(name="AP", purpose=_Purpose.ACCOUNTS_PAYABLE, address="ap@small.example"))

    def calendar_id(self):
        return "cal-1@group.calendar.google.com"


@pytest.fixture
def fake_community(monkeypatch):
    import jason.community as pkg

    def use(fake):
        monkeypatch.setattr(pkg, "community", lambda: fake)
        return fake

    return use


@pytest.fixture
def county(monkeypatch):
    saved = {k: sys.modules.get(k) for k in ("jason.mcp", "jason.mcp.county")}
    fake = types.ModuleType("jason.mcp.county")
    fake.records_inventory = lambda data_dir=None: {"records": [
        {"record": "minutes", "citation": "CIV 5200(a)(8)", "meaning": "minutes", "documents": 12, "files": [], "gap": ""},
        {"record": "tax_return", "citation": "CIV 5200(a)(6)", "meaning": "returns", "documents": 0, "files": [], "gap": "nothing pinned"},
    ]}
    pkg = types.ModuleType("jason.mcp")
    pkg.__path__ = []
    pkg.county = fake
    monkeypatch.setitem(sys.modules, "jason.mcp", pkg)
    monkeypatch.setitem(sys.modules, "jason.mcp.county", fake)
    yield fake
    for k, v in saved.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v


def test_the_checked_in_profile_has_a_theme_with_dark_overrides():
    from jason.community import community

    t = community().theme()
    assert isinstance(t, Theme) and t.wordmark
    out = theme_web.theme({})
    assert out["found"] is True and out["slug"] == community().slug and out["wordmark"] == t.wordmark
    light, dark = out["light"], out["dark"]
    for key in ("accent", "on-accent", "brand-font", "brand-weight", "brand-case", "brand-tracking", "hero"):
        assert light[key], key
    assert dark["accent"] != light["accent"], "the dark accent is lighter, so it differs"
    assert dark["on-accent"] != light["on-accent"], "near-black text sits on the lighter dark accent"
    assert set(dark) == set(light), "dark carries the same keys with overrides"
    assert out["surface"]["bg"] and out["surface"]["panel"] and out["surfaceDark"]["bg"]
    assert out["fontUrl"].startswith("https://")


def test_tokens_drop_empty_values_and_map_dark_keys():
    assert "accent-2" not in Theme(wordmark="X", accent="#000").tokens("light")
    dark = CEDAR_HOLLOW.tokens("dark")
    assert dark["accent"] == "#7fcba8" and dark["on-accent"] == "#10241c" and dark["hero"] == "#1f3a30"
    assert CEDAR_HOLLOW.tokens("light")["accent"] == "#2f6b55"


def test_a_profile_without_a_theme_answers_neutral(fake_community):
    fake_community(_Fake(theme=None))
    out = theme_web.theme({})
    assert out["found"] is False and out["slug"] == "small" and out["wordmark"] == "jason"
    assert out["light"] == {} and out["dark"] == {} and out["surface"] == {} and out["surfaceDark"] == {} and out["fontUrl"] == ""


def test_a_second_theme_goes_through_the_loader_unchanged(fake_community):
    fake_community(_Fake(theme=CEDAR_HOLLOW))
    out = theme_web.theme({})
    assert out["found"] and out["wordmark"] == "Cedar Hollow" and out["light"]["brand-case"] == "none"
    assert out["dark"]["accent"] == "#7fcba8" and out["surface"] == {}


def test_theme_and_profile_refuse_writes():
    with pytest.raises(ValueError):
        theme_web.write("", {"accent": "#000"})
    with pytest.raises(ValueError):
        profile_web.write("", {"name": "x"})


def test_community_profile_reads_only_through_methods(fake_community, county, monkeypatch):
    fake_community(_Fake(theme=CEDAR_HOLLOW))
    from jason.web import sources

    monkeypatch.setattr(sources, "embeds", lambda args: {"calendarId": "cal-1@group.calendar.google.com", "timeZone": "America/Los_Angeles"})
    out = profile_web.community_profile({})
    assert out["found"] and out["slug"] == "small" and out["name"] == "Small Community Association" and out["wordmark"] == "Cedar Hollow"
    assert out["pages"] == [{"page": "home", "label": "Home", "path": "/", "url": "https://small.example/"},
                            {"page": "records", "label": "Records", "path": "/records", "url": "https://small.example/records"}]
    assert out["mailing"] == [{"kind": "current mailing address", "label": "PO Box 1, Anytown", "zip": "90000"}], "the former manager's address stays off"
    assert out["contacts"] == [{"label": "HOA", "purpose": "the association's general inbox", "kind": "general", "email": "hoa@small.example"}], "accounts payable is internal"
    assert out["calendarId"] == "cal-1@group.calendar.google.com" and out["timeZone"] == "America/Los_Angeles"
    rec = out["records"]
    assert rec["total"] == 2 and rec["onFile"] == 1 and rec["kinds"][0] == {"record": "minutes", "citation": "CIV 5200(a)(8)", "meaning": "minutes", "onFile": True}
    assert "folders" not in rec["kinds"][0] and "gap" not in rec["kinds"][1], "the shelf's internals stay off the public page"
    assert out["asOf"] and out["caveats"]


def test_community_profile_with_nothing_set_is_empty_not_a_crash(fake_community, monkeypatch):
    class Bare:
        name = "Bare Association"
        slug = "bare"

        def theme(self):
            return None

    fake_community(Bare())
    from jason.web import sources

    monkeypatch.setattr(sources, "embeds", lambda args: (_ for _ in ()).throw(RuntimeError("no store")))
    monkeypatch.setitem(sys.modules, "jason.mcp.county", None)  # the inventory import fails; the page shows no records
    out = profile_web.community_profile({})
    assert out["wordmark"] == "Bare Association" and out["corporateName"] == "" and out["site"] == ""
    assert out["pages"] == [] and out["mailing"] == [] and out["contacts"] == [] and out["calendarId"] == ""
    assert out["records"]["kinds"] == [] and "unavailable" in out["records"]["note"]
