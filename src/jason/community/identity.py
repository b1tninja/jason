"""Who the association is, what its letterhead looks like, and where its generated documents go.

A base template names no association. These records are what a profile gives the templates instead: `Identity` for
the name, addresses, and contacts a notice prints; `LetterheadSpec` for the frame every rendering (Doc, PDF, email)
puts around it; `DriveHome` for the folders generated Docs are filed in. Each field is the profile's to set and
empty means none, so a template prints the general wording or leaves the token open (docs/base-templates.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Identity:
    """The association as its notices name it."""

    name: str
    corporate_name: str = ""
    # Where an owner mails a form or letter back, one line each, the association named first.
    mailing_address: tuple[str, ...] = ()
    # The official address for notices to the association (Civil Code 4035): a letter's footer.
    official_address: str = ""
    official_email: str = ""
    # The designated recipient of official notices (Civil Code 4035(a)), as the annual reports name it.
    designated_recipient: str = ""
    website: str = ""
    # Where general notices are posted (Civil Code 4045(a)(1)-(2)).
    posting_location: str = ""
    # Where members find the association's documents online ("the owner portal's Documents").
    documents_online: str = ""
    # Every unit's last address line ("City, ST 00000").
    unit_city_state_zip: str = ""
    # Who signs the association's notices, above its name.
    signer: str = "Board of Directors"
    # How the association is managed, one clause ("self-managed by its board", "managed by a company").
    management: str = ""
    time_zone: str = ""
    meeting_platform: str = ""

    @property
    def signature(self) -> str:
        """The closing's two lines: the signer over the association's name."""
        return f"{self.signer}\n{self.name}" if self.signer else self.name

    def values(self) -> dict[str, str]:
        """The identity as template tokens. An empty field is left out, so the token stays open."""
        found = {
            "ASSOCIATION_NAME": self.name,
            "CORPORATE_NAME": self.corporate_name,
            "MAILING_ADDRESS": "\n".join(self.mailing_address),
            "MAILING_ADDRESS_INLINE": ", ".join(self.mailing_address),
            "OFFICIAL_ADDRESS": self.official_address,
            "OFFICIAL_EMAIL": self.official_email,
            "DESIGNATED_RECIPIENT": self.designated_recipient,
            "WEBSITE": self.website,
            "POSTING_LOCATION": self.posting_location,
            "DOCUMENTS_ONLINE": self.documents_online,
            "UNIT_CITY_STATE_ZIP": self.unit_city_state_zip,
            "SIGNER": self.signer,
            "SIGNATURE": self.signature,
            "TIME_ZONE": self.time_zone,
            "MEETING_PLATFORM": self.meeting_platform,
        }
        return {key: value for key, value in found.items() if value}


@dataclass(frozen=True)
class LetterheadSpec:
    """The letterhead every rendering puts around a document.

    ``doc_id`` is a Drive Doc to copy (its footer word ``LETTERHEAD`` becomes ``footer``); without one, a renderer
    builds the header from ``name_line`` and the logo. ``logo`` is a local image for PDFs and Docs; ``logo_url`` is one
    any mail client can load without signing in, for email (empty when the mail service already shows a logo).
    """

    name_line: str
    footer: str = ""
    doc_id: str = ""
    logo: Path | None = None
    logo_url: str = ""
    font: str = "Arial, sans-serif"

    def logo_path(self, data_dir: Path | None = None) -> Path | None:
        """The logo file: the profile's own, else ``<data>/brand/letterhead-logo.png`` when that exists."""
        if self.logo is not None and self.logo.is_file():
            return self.logo
        if data_dir is not None:
            fallback = Path(data_dir) / "brand" / "letterhead-logo.png"
            if fallback.is_file():
                return fallback
        return self.logo

    def email(self):
        """The letterhead as an email frame (`email_html.Letterhead`)."""
        from jason.community.email_html import Letterhead

        return Letterhead(self.name_line, self.logo_url, font=self.font, footer=self.footer)


@dataclass(frozen=True)
class DriveHome:
    """The Drive folders generated documents are filed in. An empty id means jason finds or makes the folder by name
    under ``my_drive``."""

    my_drive: str = ""
    templates: str = ""
    meetings: str = ""
    broadcasts: str = ""
    broadcasts_name: str = "Broadcasts"
    disciplinary: str = ""
