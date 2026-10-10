"""Which vendor portal a link points at: a QR code on a report, an invoice, or a notice names one.

``identify(link)`` reads a link against the known report and customer portals and returns the platform and the key
that names the portal on it (``PortalLink``), or ``None``. A reusable table, one row per platform: the host, and the
pattern that pulls the key from the link. Which vendor a portal belongs to is the profile's (``VendorPortal.reports``);
this only says where the link goes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from jason.community.symbols import PortalPlatform


@dataclass(frozen=True)
class PortalLink:
    platform: PortalPlatform
    host: str
    key: str                        # what names the portal on that platform (a UUID for firenspec)

    def as_dict(self) -> dict[str, str]:
        return {"platform": self.platform.value, "host": self.host, "key": self.key}


# platform: (hosts, a pattern over the link's fragment or path whose first group is the key)
PORTALS: dict[PortalPlatform, tuple[tuple[str, ...], re.Pattern[str]]] = {
    PortalPlatform.FIRENSPEC: (("reports.firenspec.com",),
                               re.compile(r"(?:#/?|/)([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/?$", re.I)),
}


def identify(link: str) -> PortalLink | None:
    parts = urlparse((link or "").strip())
    host = (parts.hostname or "").lower()
    for platform, (hosts, pattern) in PORTALS.items():
        if host in hosts:
            found = pattern.search("#" + parts.fragment if parts.fragment else parts.path)
            if found:
                return PortalLink(platform, host, found.group(1).lower())
    return None


@dataclass(frozen=True)
class MeetingLink:
    platform: str                   # "zoom"
    host: str
    id: str                         # the meeting number, digits only

    def as_dict(self) -> dict[str, str]:
        return {"platform": self.platform, "host": self.host, "id": self.id}


ZOOM_MEETING = re.compile(r"^/(?:j|w|wc/join)/(\d{9,11})(?:/|$)")


def identify_meeting(link: str) -> MeetingLink | None:
    """The video meeting a link joins (a Zoom ``/j/<number>`` link), or ``None``. The passcode in the link is not read."""
    parts = urlparse((link or "").strip())
    host = (parts.hostname or "").lower()
    found = ZOOM_MEETING.match(parts.path) if host == "zoom.us" or host.endswith(".zoom.us") else None
    return MeetingLink("zoom", host, found.group(1)) if found else None


__all__ = ["MeetingLink", "PORTALS", "PortalLink", "identify", "identify_meeting"]
