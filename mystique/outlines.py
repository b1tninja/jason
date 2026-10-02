"""The association's documents that other documents cite, as the Google Docs jason outlines, and the names they go by.

Each governing document, policy, and rule set is a Google Doc in "My Drive/Governing Documents" (the PDFs in PayHOA and
the library are exports of these Docs). ``aliases`` are the names another document uses for it ("Section 6.5(b) of the
Declaration", "Bylaws 7.2"); a document's own "these Bylaws" or "this Declaration" is added by the reader. The
resolutions are read from their folder, each named by the resolution number its header prints.

The Enforcement Policy has two Docs: the one in Governing Documents (last changed November 2023) is outlined here as
the adopted policy; "My Drive/Enforcement Policy" (April 2026) reads as a revision in progress and is left out until
the board adopts it. The CC&R amendments are Docs without headings; they are outlined by their numbered paragraphs.
"""

from __future__ import annotations

from jason.community.documents import DocumentKind
from jason.community.outlines import CitableDocument

RESOLUTIONS_FOLDER = "1DHFt7PHrm3ggCTEntFzxuF3BclAuzDHp"     # My Drive/Governing Documents/Resolutions

CITABLE_DOCUMENTS: tuple[CitableDocument, ...] = (
    CitableDocument("ccrs", "Restated Declaration (CC&Rs)", "1hJcV7Vs2mu2IqMalANdsmE4gOA_RhgupNLwwXjHyfE8", DocumentKind.DECLARATION,
                    aliases=("Restated Declaration of Covenants, Conditions and Restrictions",
                             "Declaration of Covenants, Conditions and Restrictions", "Restated Declaration", "Declaration",
                             "CC&Rs", "CC&R", "CCRs", "CC & Rs")),
    CitableDocument("ccrs-2nd-amendment", "Second Amendment to the CC&Rs", "1G2GgTJjpJ1N3ZFAT7XJ9K6NI5RrqP7FyM7SclFhdWRE",
                    DocumentKind.AMENDMENT, aliases=("Second Amendment",), amends="ccrs"),
    CitableDocument("ccrs-3rd-amendment", "Third Amendment to the CC&Rs", "1Sz8Wq_4cOhkVj75lSc7wCXobUEs5LPsJm4zI2PkDBcQ",
                    DocumentKind.AMENDMENT, aliases=("Third Amendment",), amends="ccrs"),
    CitableDocument("bylaws", "Bylaws", "1v9MqoGnOvEajRySi9sZJzB6SdaVJqfw4Tbi4ZB1JBFk", DocumentKind.BYLAWS, aliases=("Bylaws",)),
    CitableDocument("election-rules", "Election Rules", "1UuuNYH4OCjICBAQeTzV4WCzCWILTCILrSuR5v5o_oe4", DocumentKind.ELECTION_RULES,
                    aliases=("Election Rules", "Election and Voting Rules")),
    CitableDocument("enforcement-policy", "Enforcement Policy", "102vrT0lk2UDERTkQpSB776aGqKg9Gm4YCRjACcz80q0", DocumentKind.POLICY,
                    aliases=("Enforcement Policy", "Fine Schedule", "Schedule of Monetary Penalties")),
    CitableDocument("owners-manual", "Owner's Manual and Rules", "1cX1NqF21iVn2bSk8KF4l6MWKWxPqlqndgcAVJustRfo", DocumentKind.OPERATING_RULES,
                    aliases=("Owner's Manual and Rules", "Owner's Manual", "Owners Manual", "Rules and Regulations", "Operating Rules")),
    CitableDocument("collection-policy", "Assessment Collection Policy", "1tBy3gBPoyJOCr-R9QDafEA323eYWl-aTfCgLozsuKAg", DocumentKind.POLICY,
                    aliases=("Assessment Collection Policy", "Collection Policy")),
    CitableDocument("alpr-policy", "ALPR Policy", "1tRv7GEG9WjJSBd71s1Yu3rgwTYgQWhcRbYZeSdmsiyI", DocumentKind.POLICY,
                    aliases=("ALPR Policy", "ALPR Usage and Privacy Policy")),
    CitableDocument("parking-rules", "Parking Rules", "1-oIaJSvoaz7aK7kENehg3AoJw3sbhfYx-SsBHQOvHjY", DocumentKind.OPERATING_RULES,
                    aliases=("Parking Rules",)),
)

# Library documents outlined from their text extracts (the recorded PDFs have no Doc), each with the document it
# supplements: an annexation's unqualified "Articles 3, 9, and 14" and "Section 6.5(b)" are the Declaration's, while its
# 1.3 names subsections of its own that other subsections cite ("1.3(d)(ii), below").
LIBRARY_OUTLINED_KINDS: dict[DocumentKind, str] = {DocumentKind.ANNEXATION: "ccrs"}

__all__ = ["CITABLE_DOCUMENTS", "RESOLUTIONS_FOLDER", "LIBRARY_OUTLINED_KINDS"]
