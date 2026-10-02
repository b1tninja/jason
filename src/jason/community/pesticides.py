"""A pesticide product by its registration number: what EPA and California have on record, and what its safety data sheet says.

The vendor's software records the number as the applicator sees it. EPA's number is
``firm-product`` (with a numeric distributor suffix on a distributor's label); California adds a
two-letter revision code for each brand it registers (``499-561-ZA`` is Alpine WSG in California,
``-AA`` the first brand registered). ``EpaNumber`` keeps both: ``epa`` for EPA's product API,
``california`` for DPR. A FIFRA 25(b) minimum-risk product ("EPA EXEMPT") has no EPA record.

The label governs use (directions, restrictions, re-entry, water). The safety data sheet is the
OSHA/GHS document a label cannot be: hazard statements, first aid, toxicology, ecology, and
state regulations such as Proposition 65. ``read_sds`` splits an SDS into its sixteen sections
and reads what a board needs: the product it names, its revision date, the GHS signal word and
hazard statements, first aid, the emergency number, the ecological statements, and Prop 65.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

_REG = re.compile(r"^(\d+)-(\d+)(?:-([A-Z]{2}))?(?:-(\d+))?$")


@dataclass(frozen=True)
class EpaNumber:
    raw: str
    firm: str = ""
    product: str = ""
    california_code: str = ""
    distributor: str = ""

    @classmethod
    def parse(cls, raw: str) -> EpaNumber:
        text = re.sub(r"^EPA\s*(REG\.?)?\s*(NO\.?)?\s*", "", (raw or "").upper().strip())
        text = re.sub(r"\s+", "", text)
        match = _REG.match(text)
        if not match:
            return cls(raw or "")
        return cls(raw, match.group(1), match.group(2), match.group(3) or "", match.group(4) or "")

    @property
    def registered(self) -> bool:
        return bool(self.firm and self.product)

    @property
    def exempt(self) -> bool:
        return "EXEMPT" in (self.raw or "").upper() or "25(B)" in (self.raw or "").upper()

    @property
    def epa(self) -> str:
        """EPA's key: firm-product."""
        return f"{self.firm}-{self.product}" if self.registered else ""

    @property
    def california(self) -> str:
        """DPR's number when the vendor recorded the revision code; else EPA's key (DPR's search accepts it)."""
        if not self.registered:
            return ""
        return f"{self.epa}-{self.california_code}" if self.california_code else self.epa

    @property
    def key(self) -> str:
        """A folder name: the EPA key, or the raw text made safe for an exempt product."""
        return self.epa or re.sub(r"[^A-Za-z0-9]+", "-", self.raw).strip("-").lower() or "unregistered"


def epa_date(text: str) -> date | None:
    """EPA's "September 29, 1999" as a date."""
    try:
        return datetime.strptime((text or "").strip(), "%B %d, %Y").date()
    except ValueError:
        return None


@dataclass(frozen=True)
class Registration:
    """EPA's record of a product (the PPLS API) and California's (CalPEST)."""

    epa_number: str
    name: str
    brand_names: tuple[str, ...]
    registrant: str
    status: str
    signal_word: str
    restricted_use: bool
    active_ingredients: tuple[tuple[str, str], ...]
    label_file: str = ""
    label_date: date | None = None
    california_number: str = ""
    california_status: str = ""
    california_first: str = ""

    @classmethod
    def from_ppls(cls, item: dict) -> Registration:
        files = sorted((f for f in item.get("pdffiles") or [] if f.get("pdffile")),
                       key=lambda f: epa_date(f.get("pdffile_accepted_date") or "") or date.min)
        newest = files[-1] if files else {}
        company = (item.get("companyinfo") or [{}])[0]
        return cls(
            epa_number=str(item.get("eparegno") or ""),
            name=str(item.get("productname") or "").strip(),
            brand_names=tuple(str(b.get("altbrandname") or "").strip() for b in item.get("altbrandnames") or [] if b.get("altbrandname")),
            registrant=str(company.get("name") or "").strip(),
            status=str(item.get("product_status") or ""),
            signal_word=str(item.get("signal_word") or "").strip(),
            restricted_use=str(item.get("rup_yn") or "").upper().startswith("Y"),
            active_ingredients=tuple((str(a.get("active_ing") or "").strip(), str(a.get("active_ing_percent") or ""))
                                     for a in item.get("active_ingredients") or []),
            label_file=str(newest.get("pdffile") or ""),
            label_date=epa_date(newest.get("pdffile_accepted_date") or ""),
        )


SECTIONS = {
    1: "identification", 2: "hazards", 3: "composition", 4: "first aid", 5: "fire", 6: "spills", 7: "handling and storage",
    8: "exposure and protection", 9: "properties", 10: "stability", 11: "toxicology", 12: "ecology", 13: "disposal",
    14: "transport", 15: "regulatory", 16: "other",
}
_HEADING = re.compile(r"(?im)^\s*(?:SECTION\s*)?(\d{1,2})\s*[:.]\s*(product and company identification|identification|hazard|composition|first[- ]?aid|fire|accidental|"
                      r"handling|exposure|physical|stability|toxicolog|ecolog|disposal|transport|regulatory|other)")


def sds_sections(text: str) -> dict[int, str]:
    """The sixteen sections, by number, from their headings ("SECTION 2: HAZARD(S)" or "2. Hazards Identification")."""
    marks: list[tuple[int, int]] = []
    seen: set[int] = set()
    for match in _HEADING.finditer(text):
        number = int(match.group(1))
        if 1 <= number <= 16 and number not in seen and (not marks or number > marks[-1][0]):
            marks.append((number, match.start()))
            seen.add(number)
    found = {}
    for i, (number, start) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        found[number] = text[start:end]
    return found


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


@dataclass(frozen=True)
class SdsReading:
    product: str
    revised: str
    signal_word: str
    hazards: tuple[tuple[str, str], ...]
    emergency: tuple[str, ...]
    first_aid: dict[str, str] = field(default_factory=dict)
    ecology: tuple[str, ...] = ()
    prop65: str = ""
    sections: int = 0


_FIRST_AID = (("swallowed", r"IF SWALLOWED|If swallowed|Ingestion"), ("skin", r"IF ON SKIN|On skin contact|Skin contact|If on skin"),
              ("eyes", r"IF IN EYES|On contact with eyes|Eye contact|If in eyes"), ("inhaled", r"IF INHALED|If inhaled|Inhalation"))
_ECO_HEADINGS = re.compile(r"(?i)SECTION\s*12\s*:?|ECOLOGICAL INFORMATION|Environmental Hazards Statement from FIFRA Regulated "
                           r"Pesticide Label\s*:?|Toxicity\s+Aquatic toxicity|Assessment of aquatic toxicity\s*:?")
_ECOLOGY = re.compile(r"[^.]*\b(?:toxic|harmful)\b[^.]*\b(?:aquatic|fish|bees?|birds?|wildlife|invertebrates)\b[^.]*\.", re.I)


def read_sds(text: str) -> SdsReading:
    """What a board needs from a safety data sheet. A field the sheet does not state stays empty."""
    parts = sds_sections(text)
    ident = parts.get(1, text[:3000])
    product = None
    # Most specific label first: "Product Name:" can sit under a "Product identifier" line.
    for pattern in (r"Product\s*Name\s*:?[\s:]*([^\n:]{2,80})", r"(?m)^\s*(?:Trade\s*)?Name\s*\n?\s*:\s*([^\n]{2,80})",
                    r"Product identifier(?: used on the label)?[\s:]*([^\n]{2,80})"):
        product = re.search(pattern, ident, re.I)
        if product:
            break
    if not product:
        product = re.search(r"Safety Data Sheet\s*\n\s*([^\n]{2,80})", text)
    revised = re.search(r"(?:Revision date|Date of (?:last )?revision|Revised|Issue date|Date Issued)\s*:?\s*"
                        r"([0-9]{1,4}[/.-][0-9]{1,2}[/.-][0-9]{2,4}|\d{1,2}-[A-Z][a-z]{2}-\d{4}|[A-Z][a-z]+ \d{1,2},? \d{4})", text, re.I)
    hazards_text = parts.get(2, "")
    signal = re.search(r"Signal\s*Word\s*:?\s*\n?\s*([A-Za-z][A-Za-z ]{1,20})", hazards_text, re.I)
    if not signal:
        # Some sheets print the GHS word alone on a line under "Label elements".
        signal = re.search(r"(?m)^\s*(DANGER|WARNING)\s*$", hazards_text)
    unclassified = re.search(r"no need for classification|does not require a hazard warning label|not (?:classified|considered) "
                             r"(?:as )?hazardous|does not meet the (?:regulatory )?definition of a hazardous", hazards_text, re.I)
    statements: list[tuple[str, str]] = []
    for match in re.finditer(r"\b(H\d{3}(?:\s*\+\s*H\d{3})*)\b\s*[:\-]?\s*\n?\s*([^\n]{5,160})", hazards_text):
        pair = (match.group(1).replace(" ", ""), _flat(match.group(2)).lstrip("- "))
        if pair not in statements:
            statements.append(pair)
    if not statements:
        # Hazard statements printed without their H-codes, between the heading and the precautionary statements.
        block = re.search(r"Hazard Statement\(?s?\)?\s*:?\s*(.*?)(?:Precautionary|$)", hazards_text, re.S | re.I)
        if block:
            for line in block.group(1).splitlines():
                line = _flat(line).lstrip(": ")
                if len(line) > 5 and not line.startswith("(") and not line.lower().startswith(("no statement", "none")):
                    statements.append(("", line))
    emergency = tuple(dict.fromkeys(_flat(m.group(0)) for m in re.finditer(
        r"(?:1-8\d\d-\d{3}-\d{4}|\(8\d\d\)\s*\d{3}-\d{4}|8\d\d-\d{3}-\d{4})", parts.get(1, ""))))
    aid = parts.get(4, "")
    first_aid: dict[str, str] = {}
    for name, pattern in _FIRST_AID:
        match = re.search(rf"(?:{pattern})\s*:?\s*(.{{10,420}}?)(?=\n\s*(?:IF |If |On |Ingestion|Inhalation|Skin|Eye|Most important|Note to|Indication)|$)",
                          aid, re.S)
        if match:
            first_aid[name] = _flat(match.group(1))[:400]
    eco_text = _ECO_HEADINGS.sub(". ", parts.get(12, "")[:6000])
    ecology = tuple(dict.fromkeys(_flat(m.group(0)).lstrip(". ") for m in _ECOLOGY.finditer(eco_text)))[:6]
    regulatory = parts.get(15, "")
    prop65 = re.search(r"(?:Prop(?:osition)?\s*65|California Proposition)[^\n]*(?:\n[^\n]*){0,3}", regulatory, re.I)
    return SdsReading(
        product=_flat(product.group(1)) if product else "",
        revised=revised.group(1) if revised else "",
        signal_word=_signal(signal.group(1) if signal else "", bool(unclassified)),
        hazards=tuple(statements),
        emergency=emergency,
        first_aid=first_aid,
        ecology=ecology,
        prop65=_flat(prop65.group(0))[:300] if prop65 else "",
        sections=len(parts),
    )


def _signal(word: str, unclassified: bool) -> str:
    """The GHS signal word; a sheet that states no classification (or "None required") reads "Not classified"."""
    word = _flat(word).split(" ")[0].title() if word else ""
    if word in ("Danger", "Warning"):
        return word
    return "Not classified" if unclassified or word == "None" else word


def names_product(sds_product: str, product: str) -> bool:
    """The sheet names the vendor's product: every word of the product's name (less its form words) appears."""
    words = [w for w in re.findall(r"[a-z0-9]+", product.lower()) if w not in {"for", "general", "pest", "the"}]
    folded = re.sub(r"[^a-z0-9]+", " ", sds_product.lower())
    return bool(words) and all(w in folded.split() or w in folded for w in words[:2])


@dataclass(frozen=True)
class DocumentSource:
    """Where a product's safety data sheet and specimen label are kept, when no API names them.

    ``cdms`` is the manufacturer's id in CDMS's label and SDS library (BASF 82, Syngenta 83, Envu 686, MGK 164);
    otherwise ``sds`` and ``label`` are the manufacturer's own links. Checked September 29, 2026.
    """

    cdms: int = 0
    sds: str = ""
    label: str = ""


# By EPA key ("firm-product"), or by product name for a 25(b) product with no EPA number.
DOCUMENT_SOURCES: dict[str, DocumentSource] = {
    "499-561": DocumentSource(cdms=82),
    "499-570": DocumentSource(cdms=82),
    "7969-382": DocumentSource(cdms=82),
    "7969-210": DocumentSource(cdms=82),
    "100-1066": DocumentSource(cdms=83),
    "101563-143": DocumentSource(cdms=686),
    "1021-2574": DocumentSource(cdms=164),
    "53883-118": DocumentSource(sds="https://agrian.com/pdfs/Bifen_IT_MSDS1i.pdf",
                                label="https://www.controlsolutionsinc.com/hubfs/Specimen%20Labels/Specimen-BifenIT-53883-118.pdf"),
    "53883-229": DocumentSource(sds="https://agrian.com/pdfs/Dominion_2L_MSDS1p.pdf",
                                label="https://www.controlsolutionsinc.com/hubfs/Specimen%20Labels/Specimen-Dominion2L-53883-229.pdf"),
    "ESSENTRIA IC PRO": DocumentSource(
        sds="https://www.zoecon.com/-/media/project/oneweb/zoecon/files/product-labels/sds/pco-essentria-ic-pro-sds-label.pdf",
        label="https://www.zoecon.com/-/media/project/oneweb/zoecon/files/product-labels/specimen/pco-22-007_essentria-ic-pro_-specimen-label.pdf"),
}


def document_source(number: EpaNumber, product: str) -> DocumentSource | None:
    return DOCUMENT_SOURCES.get(number.epa) or DOCUMENT_SOURCES.get(product.strip().upper())


__all__ = ["EpaNumber", "Registration", "SdsReading", "read_sds", "sds_sections", "names_product", "epa_date", "SECTIONS",
           "DocumentSource", "DOCUMENT_SOURCES", "document_source"]
