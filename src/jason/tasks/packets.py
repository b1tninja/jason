"""Assemble a packet (``jason.community.packets``) into one PDF: plan, fill, fetch, generate, merge.

``plan`` resolves each part for a year without writing anything: a template has a Doc, a library or Drive pattern
finds this year's file (the newest match), a generator exists. It also gathers the token values: the packet's standing
values, the year's computed ones (``FISCAL_YEAR``, ``UNIT_COUNT``), the statutory passages cut from the law on hand
(``statute_passages``), and the year's own values file, ``data/packets/<packet>-<year>/values.json``, where a person
records what only the board can say. Every token still empty is listed: those are the decisions left.

``build`` fills each template as a copy in Drive (``replaceAllText``), exports it, downloads each found file (the
listed pages only), renders the generated pages (HTML printed by the installed Chrome or Edge), and merges the parts in
order with ``merge``: a bookmark per part, and "Page n of N" in the footer. ``manifest.json`` beside the PDF records each
part's source, pages, and SHA-256, so the packet that was mailed can be shown later.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

from jason.community.packets import Packet, Part, SourceKind, page_list

TOKEN = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")
QR_TOKEN = re.compile(r"\{QR:([A-Z][A-Z0-9_]*)\}")
# jason's base packet templates; a profile's own packet_templates/ folder overrides one by file name.
BASE_TEMPLATES = Path(__file__).resolve().parents[1] / "templates" / "packets"


def template_file(name: str) -> Path:
    """A packet template by file name: the active profile's own (``<profile>/packet_templates/``), else jason's base."""
    from jason.community.profile import profile_root

    root = profile_root()
    if root is not None:
        own = root / "packet_templates" / name
        if own.is_file():
            return own
    return BASE_TEMPLATES / name


@dataclass
class Resolved:
    part: Part
    found: bool
    ref: str = ""               # a Doc id, a library document id, a Drive file id, or a generator's name
    where: str = ""             # the library or Drive path, or what the source is
    reason: str = ""


@dataclass
class Plan:
    packet: Packet
    year: int
    parts: list[Resolved] = field(default_factory=list)
    values: dict[str, str] = field(default_factory=dict)
    tokens: list[str] = field(default_factory=list)          # every token the templates carry
    gaps: list[str] = field(default_factory=list)

    @property
    def unfilled(self) -> list[str]:
        return [t for t in self.tokens if not self.values.get(t)]

    @property
    def missing(self) -> list[Resolved]:
        return [r for r in self.parts if not r.found and r.part.source.kind is not SourceKind.ADDENDUM]


def packet_dir(data_dir: Path, packet: Packet, year: int) -> Path:
    return data_dir / "packets" / f"{packet.key}-{year}"


def _newest(rows: list[dict[str, Any]], pattern: str, *, path_key: str, date_key: str) -> dict[str, Any] | None:
    rx = re.compile(pattern)
    hits = [r for r in rows if rx.search(str(r.get(path_key) or "")) and not r.get("directory")]
    return max(hits, key=lambda r: str(r.get(date_key) or "")) if hits else None


GENERATORS = ("insurance-summary", "fha-statement", "va-statement")
# A generated part ``letter:<file>`` is an HTML letter (`template_file`: the profile's, else jason's base), its tokens filled and printed on
# the letterhead. The tokens below are a variant's own (one building's flood policy).
VARIANT_TOKENS = ("BUILDING", "FLOOD_STANDING", "FLOOD_CARRIER", "FLOOD_NUMBER", "FLOOD_TERM", "FLOOD_LIMIT",
                  "FLOOD_DEDUCTIBLE", "FLOOD_CHANGE")


def _is_letter(source: Any) -> bool:
    return source.kind is SourceKind.GENERATED and source.ref.startswith("letter:")


def letter_text(ref: str) -> str:
    return template_file(ref.split(":", 1)[1]).read_text(encoding="utf-8")


# The label printed beside a token's QR code (``{QR:TOKEN}``; jason.community.qr).
QR_LABELS = {"OWNER_FORM_LINK": "Scan to answer online in PayHOA", "MEETING_LINK": "Scan to join the meeting",
             "PAYHOA_SIGN_UP": "Scan to sign in to PayHOA or create your account"}


def fill_letter(ref: str, values: dict[str, str]) -> tuple[str, list[str]]:
    """A letter's HTML with its tokens filled (each value escaped), each ``{QR:TOKEN}`` printed as a code with its
    link beside it, and its citations, web addresses, and email addresses made links (``links.linkify``; the email
    carries ``EMAIL_SUBJECT`` when the values have one), and the tokens left open (a QR token whose value is not a link
    yet among them)."""
    from jason.community.qr import fill_qr_tokens
    from jason.tasks.section_refs import fill_html

    text, _ = fill_html(letter_text(ref))       # {QUOTE:ccrs#4.2(b)}, {CITE:...}: raises on a reference that cannot be filled
    left = [t for t in dict.fromkeys(TOKEN.findall(text)) if not values.get(t)]
    # a value of several lines (an address block) keeps its lines; a ``*_LIST`` token's lines are list items
    def value(name: str) -> str:
        lines = values[name].split("\n")
        if name.endswith("_LIST"):
            return "".join(f"<li>{html.escape(line)}</li>" for line in lines if line.strip())
        return "<br>".join(html.escape(line) for line in lines)

    filled = TOKEN.sub(lambda m: value(m.group(1)) if values.get(m.group(1)) else m.group(0), text)
    filled, no_link = fill_qr_tokens(filled, values, labels=QR_LABELS)
    from jason.community import community as active
    from jason.community.links import fill_help_tokens, linkify

    filled, no_help = fill_help_tokens(filled, active().help_articles())   # {HELP:key}: the vendor's own guides
    filled = linkify(filled, subject=values.get("EMAIL_SUBJECT", ""))      # clickable in the PDF; the same in print
    return filled, left + [t for t in no_link if t not in left] + [f"HELP:{k}" for k in no_help]


def for_variant(part: Part, variant: str) -> Part:
    """The part as it stands for one variant: ``{building}`` in its title, pattern, and ref filled in."""
    if not variant:
        return part
    from dataclasses import replace

    fill = lambda text: text.replace("{building}", variant)                      # noqa: E731
    return replace(part, title=fill(part.title),
                   source=replace(part.source, pattern=fill(part.source.pattern), ref=fill(part.source.ref)))


def varies(part: Part) -> bool:
    """Whether a part differs between variants (so it is made once per building, not once per packet)."""
    if for_variant(part, "0") != part:
        return True
    if _is_letter(part.source):
        return any(t in VARIANT_TOKENS for t in TOKEN.findall(letter_text(part.source.ref)))
    return False


def year_pattern(pattern: str, year: int) -> str:
    """``{year}`` is the fiscal year; ``{prior}`` the one before it; ``{term}`` the insurance term ending in it ("26-27")."""
    return (pattern.replace("{year}", str(year)).replace("{prior}", str(year - 1))
            .replace("{term}", f"{(year - 1) % 100:02d}-{year % 100:02d}"))


def resolve(part: Part, year: int, *, library: list[dict[str, Any]], drive: list[dict[str, Any]], variant: str = "") -> Resolved:
    part = for_variant(part, variant)
    source = part.source
    pattern = year_pattern(source.pattern, year)
    if source.kind is SourceKind.TEMPLATE:
        return Resolved(part, bool(source.ref), source.ref, "template Doc",
                        "" if source.ref else "the template Doc is not made yet (--make-templates --yes)")
    if source.kind is SourceKind.LIBRARY:
        row = _newest(library, pattern, path_key="path", date_key="updatedAt")
        return Resolved(part, row is not None, str(row["id"]) if row else "", str(row.get("path")) if row else "",
                        "" if row else f"no PayHOA library file matches {pattern}")
    if source.kind is SourceKind.DRIVE and source.ref:              # a linked document, pinned by its link
        file_id = drive_id(source.ref)
        row = next((r for r in drive if r.get("id") == file_id), None)
        return Resolved(part, bool(file_id), file_id, str((row or {}).get("path") or source.ref),
                        "" if file_id else f"not a Drive or Docs link: {source.ref}")
    if source.kind is SourceKind.DRIVE:
        row = _newest(drive, pattern, path_key="path", date_key="modified")
        return Resolved(part, row is not None, str(row["id"]) if row else "", str(row.get("path")) if row else "",
                        "" if row else f"no Drive file matches {pattern}")
    if _is_letter(source):
        known = template_file(source.ref.split(":", 1)[1]).is_file()
        return Resolved(part, known, source.ref, "letter printed by jason", "" if known else f"no letter {source.ref}")
    if source.kind is SourceKind.GENERATED:
        known = source.ref in GENERATORS
        return Resolved(part, known, source.ref, "generated by jason", "" if known else f"no generator {source.ref}")
    return Resolved(part, False, source.ref, "added per recipient", "an addendum is added in a mailing run")


# The form prints the way to the online form, not its link: PayHOA opens a form for an owner only by a link naming the
# unit, and one printed form serves every unit. An emailed copy makes "online in PayHOA" its unit's link
# (fillable.link_phrase). The first 2027 copies printed the bare link, which an owner can't open (October 1, 2026).
ONLINE_PHRASE = "online in PayHOA"
FORM_PREAMBLE = [
    "**Please return this form by {RETURN_BY}**, by mail to {MAILING_ADDRESS_INLINE}; by email to "
    "{OFFICIAL_EMAIL}; or " + ONLINE_PHRASE + ": sign in, choose Requests, then Owner Information and Notice Delivery "
    "Preferences.",
]
# No closing line: the preamble already says what the information is used for, and the line cost the letter a fifth
# billed page (October 1, 2026).
FORM_CLOSING: list[str] = []


def template_markdown(source: str) -> list[str]:
    """A template part's text: a Markdown file (`template_file`), or ``form:<key>`` for a form rendered for
    paper (``form_render.paper_markdown``)."""
    if source.startswith("form:"):
        from jason.community.form_render import paper_markdown
        from jason.community.spec import spec_module

        key = source.split(":", 1)[1]
        form = next(f for f in spec_module("forms").FORM_TEMPLATES if f.key.value == key)
        return paper_markdown(form, preamble=FORM_PREAMBLE, closing=FORM_CLOSING)
    from jason.tasks.section_refs import fill_markdown

    text, _ = fill_markdown(template_file(source).read_text(encoding="utf-8"))   # {QUOTE:...}/{CITE:...}; raises on a bad one
    return text.splitlines()


LINE_BOX = 11.0          # points a line of underscores takes at the template's 11 point text; the rest of a writing
                         # line's height is room above it


def template_style(source: str) -> Any:
    """The Doc style a template part is written in: a form's writing lines get the room and the pale ink its
    ``FormStyle`` gives them (``docs_markdown.DocStyle.write_above``, ``write_ink``); anything else the report style."""
    from dataclasses import replace

    from jason.google.docs_markdown import REPORT

    if not source.startswith("form:"):
        return REPORT
    from jason.community.spec import spec_module

    key = source.split(":", 1)[1]
    form = next(f for f in spec_module("forms").FORM_TEMPLATES if f.key.value == key)
    gray = form.style.line_gray
    # the room to write goes to the writing lines; the rest of the form sits a little closer than a report
    return replace(REPORT, write_above=max(0.0, form.style.write_height - LINE_BOX), write_ink=(gray, gray, gray),
                   text_below=4, heading_above=(6, 12, 8, 6, 6, 6))


def template_tokens(packet: Packet) -> list[str]:
    """The tokens in the packet's template texts (the Markdown each template Doc was made from)."""
    seen: dict[str, None] = {}
    for part in packet.parts:
        if part.source.kind is SourceKind.TEMPLATE and part.source.markdown:
            text = "\n".join(template_markdown(part.source.markdown))
        elif _is_letter(part.source) and template_file(part.source.ref.split(":", 1)[1]).is_file():
            text = letter_text(part.source.ref)
        else:
            continue
        for token in TOKEN.findall(text) + QR_TOKEN.findall(text):
            seen.setdefault(token, None)
    return list(seen)


DRIVE_LINK = re.compile(r"(?:/d/|[?&]id=)([A-Za-z0-9_-]{20,})")


def drive_id(link: str) -> str:
    """The file id in a Docs or Drive link ("https://docs.google.com/document/d/<id>/edit"), or the id itself."""
    m = DRIVE_LINK.search(link)
    if m:
        return m.group(1)
    return link if re.fullmatch(r"[A-Za-z0-9_-]{20,}", link or "") else ""


def linked_parts(packet: Packet, data_dir: Path, year: int) -> Packet:
    """The packet with the year's linked documents stubbed in: ``"_links": {"<part title>": "<Docs or Drive link>"}`` in
    the year's values.json makes that part the linked document, exported or downloaded at build, in place of where the
    specification looks for it. A title the packet lacks is ignored here and named by ``plan``."""
    links = _links(data_dir, packet, year)
    if not links:
        return packet
    from dataclasses import replace

    from jason.community.packets import PartSource

    parts = tuple(replace(p, source=PartSource(SourceKind.DRIVE, ref=links[p.title], keep=p.source.keep, drop=p.source.drop))
                  if p.title in links else p for p in packet.parts)
    return replace(packet, parts=parts)


def values_for(community: Any, packet: Packet, year: int, data_dir: Path, *,
               passages: Callable[[Path], tuple[dict[str, str], list[str]]] | None = None) -> tuple[dict[str, str], list[str]]:
    """The token values for a year: the profile's (`template_values.profile_values`), standing, computed (the mailing
    date is today unless the values file names it), statutory, then the year's values file (which wins)."""
    from jason.community.statute_passages import passages as statute
    from jason.community.template_values import profile_values

    values = profile_values(community)
    values.update(packet.values)
    values.update({"FISCAL_YEAR": str(year), "UNIT_COUNT": str(len(community.units())), "MAILING_DATE": today_long()})
    words, gaps = (passages or statute)(data_dir)
    values.update(words)
    own = packet_dir(data_dir, packet, year) / "values.json"
    if own.is_file():
        values.update({k: str(v) for k, v in json.loads(own.read_text(encoding="utf-8")).items()
                       if v not in (None, "") and not k.startswith("_")})
    return values, gaps


def plan(community: Any, packet: Packet, year: int, data_dir: Path, *, library: list[dict[str, Any]] | None = None,
         drive: list[dict[str, Any]] | None = None, passages: Callable[..., Any] | None = None, variant: str = "") -> Plan:
    if library is None:
        raw = json.loads((data_dir / "payhoa-documents.json").read_text(encoding="utf-8")) if (data_dir / "payhoa-documents.json").is_file() else []
        library = raw if isinstance(raw, list) else raw.get("documents", [])
    if drive is None:
        raw = json.loads((data_dir / "drive" / "files.json").read_text(encoding="utf-8")) if (data_dir / "drive" / "files.json").is_file() else []
        drive = raw if isinstance(raw, list) else raw.get("files", [])
    unknown = [t for t in _links(data_dir, packet, year) if t not in {p.title for p in packet.parts}]
    packet = linked_parts(packet, data_dir, year)
    out = Plan(packet, year)
    out.parts = [resolve(part, year, library=library, drive=drive, variant=variant) for part in packet.parts]
    out.values, out.gaps = values_for(community, packet, year, data_dir, passages=passages)
    if variant:
        out.values["BUILDING"] = variant
    out.tokens = template_tokens(packet)
    out.gaps += [f"values.json links a part the packet does not have: {t}" for t in unknown]
    return out


def _links(data_dir: Path, packet: Packet, year: int) -> dict[str, str]:
    own = packet_dir(data_dir, packet, year) / "values.json"
    return (json.loads(own.read_text(encoding="utf-8")).get("_links") or {}) if own.is_file() else {}


def plan_lines(p: Plan) -> list[str]:
    lines = [f"{p.packet.title}, fiscal year {p.year}", ""]
    for r in p.parts:
        mark = "ok  " if r.found else ("add " if r.part.source.kind is SourceKind.ADDENDUM else ("MISS" if r.part.required else "skip"))
        lines.append(f"  {mark} {r.part.title}" + (f"  [{r.part.authority}]" if r.part.authority else "")
                     + (f"\n         {r.where}" if r.found and r.where else "") + (f"\n         {r.reason}" if r.reason else ""))
    lines += ["", f"tokens: {len(p.tokens) - len(p.unfilled)} of {len(p.tokens)} filled"]
    if p.unfilled:
        lines.append("  to fill (values.json): " + ", ".join(p.unfilled))
    lines += [f"  gap: {g}" for g in p.gaps]
    return lines


# -- rendering -------------------------------------------------------------------------------------------------------

PAGE_STYLE = """<style>@page{size:letter;margin:0.6in 0.75in 0.7in}body{font:10.5pt/1.38 Arial,Helvetica,sans-serif;color:#222}
p{margin:0 0 6pt} ul,ol{margin:0 0 6pt;padding-left:22pt} li{margin:0 0 2pt}
a{color:inherit;text-decoration:underline;text-decoration-thickness:0.5pt}
h1{font-size:15pt;margin:0 0 6pt} h2{font-size:11.5pt;margin:10pt 0 3pt} .letterhead img{height:0.75in;margin-bottom:4pt} .letterhead{text-align:center;font:bold 14pt 'Century Gothic',
Futura,Arial,sans-serif;letter-spacing:1px;margin-bottom:10pt} table{border-collapse:collapse;width:100%;font-size:9.5pt;margin-bottom:6pt}
th,td{border:1px solid #bbb;padding:3pt 5pt;text-align:left;vertical-align:top} .statement{font-weight:bold;font-size:10pt}
.small{font-size:9pt;color:#555}</style>"""


LOGO_PIXELS = 300                       # the logo's height for print: 0.9 inch at about 330 dots per inch


def print_logo(path: Path) -> bytes:
    """The logo scaled down for print, so every printed page does not carry the full-size original."""
    import pymupdf

    pix = pymupdf.Pixmap(str(path))
    step = 0
    while pix.height >> (step + 1) >= LOGO_PIXELS:
        step += 1
    if step:
        pix.shrink(step)
    return pix.tobytes("png")


def page_html(title: str, body: str, *, association: str, logo: Path | None = None) -> str:
    """A printed page on the letterhead: the logo (when given) over the association's name, as the template Docs'
    Letterhead sets it, then the title and the body."""
    mark = ""
    if logo is not None and logo.is_file():
        import base64

        mark = f"<img src='data:image/png;base64,{base64.b64encode(print_logo(logo)).decode()}' alt=''><br>"
    return (f"<!doctype html><html><head><meta charset='utf-8'>{PAGE_STYLE}</head><body>"
            f"<div class='letterhead'>{mark}{html.escape(association.upper())}</div><h1>{html.escape(title)}</h1>{body}</body></html>")


def statement_html(words: str, *, condominium: bool = True, certified: str = "") -> str:
    """An FHA or VA statement in the statute's form; the circled choices filled when the status is known."""
    text = html.escape(words)
    text = text.replace("[is/is not (circle one)]", "is" if condominium else "is not", 1)
    if certified in ("is", "is not"):
        text = text.replace("[is/is not (circle one)]", certified, 1)
    return "".join(f"<p>{p}</p>" for p in text.split("\n\n"))


def short_date(iso: Any) -> str:
    """2026-04-05 as Apr 5, 2026."""
    try:
        d = date.fromisoformat(str(iso))
    except ValueError:
        return str(iso or "")
    return f"{d:%b} {d.day}, {d.year}"


def money(cents: Any) -> str:
    return f"${int(cents) / 100:,.0f}" if isinstance(cents, (int, float)) and cents else "—"


# Which policies the 5300(b)(9) summary lists, and which of a term's limits is the policy limit, by kind of policy.
SUMMARY_LIMITS: dict[str, tuple[tuple[str, str], ...]] = {
    "master": (("Property (master policy)", "building_limit"), ("General liability", "each_occurrence")),
    "umbrella": (("Umbrella liability", "each_occurrence"),),
    "directors_and_officers": (("Directors and officers liability", "limit"),),
    "fidelity": (("Crime and fidelity", "Employee Theft"),),
    "flood": (("Flood", "limit"),),
}


def insurance_rows(policies: list[dict[str, Any]], fiscal_year: int, *,
                   not_carried: tuple[str, ...] = ()) -> tuple[list[list[str]], list[str]]:
    """Each policy's insurer, type, number, term, limit, and deductible for the term in force on the first day of the
    fiscal year; a policy with no such term on file is a gap, never last year's figures. ``not_carried`` are the kinds
    of insurance the profile says the association does not carry (`Community.coverages_not_carried`)."""
    start = f"{fiscal_year}-01-01"
    rows: list[list[str]] = []
    gaps: list[str] = []
    for policy in policies:
        kinds = SUMMARY_LIMITS.get(str(policy.get("kind")))
        if not kinds:
            continue
        name = str(policy.get("key"))
        term = next((t for t in policy.get("terms") or [] if str(t.get("start") or "") <= start < str(t.get("end") or "")), None)
        if term is None:
            gaps.append(f"insurance summary: {name} has no term on file in force on {start}; run jason policies once its "
                        "declarations are in Drive")
            continue
        limits = term.get("limits") or {}
        for label, key in kinds:
            if policy.get("kind") == "flood" and policy.get("building"):
                label = f"Flood (Building {policy['building']})"
            deductible = term.get("deductible") if key in ("building_limit", "limit", "Employee Theft") else None
            carrier = str(term.get("carrier") or policy.get("carrier") or "")
            rows.append([label, carrier.title() if carrier.isupper() else carrier, str(term.get("number") or ""),
                         f"{short_date(term.get('start'))} to {short_date(term.get('end'))}", money(limits.get(key)), money(deductible)])
    rows += [[kind.capitalize(), "None", "", "", "", f"The Association does not carry {kind} insurance."] for kind in not_carried]
    return rows, gaps


def insurance_html(rows: list[list[str]], statement: str) -> str:
    """The 5300(b)(9) summary: a table, then the statute's statement in at least 10-point bold."""
    cells = "".join("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in row) + "</tr>" for row in rows)
    return ("<table><tr><th>Coverage</th><th>Insurer</th><th>Policy</th><th>Term</th><th>Limit</th><th>Deductible</th></tr>"
            + cells + "</table>" + f"<p class='statement'>{html.escape(statement)}</p>")


NFIP_UNIT_LIMIT = 25_000_000            # the RCBAP's federal maximum per residential unit, in cents ($250,000)


def long_date(iso: Any) -> str:
    try:
        day = date.fromisoformat(str(iso)[:10])
    except ValueError:
        return str(iso or "")
    return f"{day:%B} {day.day}, {day.year}"


def flood_values(policies: list[dict[str, Any]], building: int, units: int, *, fiscal_year: int,
                 today: date | None = None) -> tuple[dict[str, str], list[str]]:
    """One building's flood notice tokens from the newest term on file: the policy, where it stands (renewed, in force,
    or ending before the fiscal year with no renewal on file), and what changed from the term before."""
    today = today or date.today()
    policy = next((p for p in policies if p.get("kind") == "flood" and str(p.get("building")) == str(building)), None)
    terms = sorted((policy or {}).get("terms") or [], key=lambda t: str(t.get("start") or ""))
    if not terms:
        return {}, [f"flood notice, Building {building}: no flood policy terms on file (jason policies)"]
    term, prior = terms[-1], (terms[-2] if len(terms) > 1 else None)
    gaps: list[str] = []
    limit = (term.get("limits") or {}).get("limit")
    carrier = str(term.get("carrier") or "")
    span = f"{long_date(term.get('start'))} through {long_date(term.get('end'))}"
    if str(term.get("end") or "") <= f"{fiscal_year}-01-01":
        standing = (f"The Association's flood policy for Building {building} runs {span}. It is due to renew before it "
                    "ends; the Association will send the renewed policy's declarations page when the insurer issues it. "
                    "The current declarations page is enclosed.")
        gaps.append(f"flood notice, Building {building}: the term on file ends {term.get('end')}; no renewal on file")
    elif str(term.get("start") or "") > today.isoformat():
        standing = (f"The Association has renewed the flood policy for Building {building}. The renewed policy begins "
                    f"{long_date(term.get('start'))}; its declarations page is enclosed.")
    else:
        standing = f"The Association's flood policy for Building {building} is in force; its declarations page is enclosed."
    if isinstance(limit, int) and units and limit == units * NFIP_UNIT_LIMIT:
        limit_text = f"{money(limit)} ({units} units at {money(NFIP_UNIT_LIMIT)} each, the federal maximum)"
    else:
        limit_text = money(limit)
    change = ""
    if prior:
        before = ((prior.get("limits") or {}).get("limit"), prior.get("deductible"))
        if before == (limit, term.get("deductible")):
            change = "This term keeps the same limit and deductible as the one before it."
        else:
            change = (f"Compared with the term before it, the limit went from {money(before[0])} to {money(limit)} and the "
                      f"deductible from {money(before[1])} to {money(term.get('deductible'))}.")
            gaps.append(f"flood notice, Building {building}: the limit or deductible changed; a lower limit or a higher "
                        "deductible is a Civil Code 5810 notice to every member")
    return {
        "BUILDING": str(building),
        "FLOOD_STANDING": standing,
        "FLOOD_CARRIER": carrier.title() if carrier.isupper() else carrier,
        "FLOOD_NUMBER": str(term.get("number") or ""),
        "FLOOD_TERM": span,
        "FLOOD_LIMIT": limit_text,
        "FLOOD_DEDUCTIBLE": money(term.get("deductible")),
        "FLOOD_CHANGE": change,
    }, gaps


def print_pdf(page: str, out: Path, *, run: Callable[..., Any] = subprocess.run) -> Path:
    """Print an HTML page to PDF with the installed Chrome or Edge (headless)."""
    from jason.tasks.email_review import browser

    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "page.html"
        src.write_text(page, encoding="utf-8")
        run([browser(), "--headless=new", "--disable-gpu", f"--user-data-dir={tmp}", "--no-pdf-header-footer",
             f"--print-to-pdf={out}", src.as_uri()], check=True, capture_output=True, timeout=120)
    if not out.is_file():
        raise RuntimeError(f"the browser printed no PDF for {out.name}")
    return out


# -- merging ---------------------------------------------------------------------------------------------------------

BLANK = "This page is intentionally left blank."


def merge(parts: list[tuple[Any, ...]], out: Path, *, footer: str = "") -> list[dict[str, Any]]:
    """Merge (title, pdf, pages[, own_sheet]) in order into ``out``: a bookmark per part, "Page n of N" (and ``footer``)
    at the foot of every page. A part on its own sheet starts on a front (odd) page and ends with its back filled, by a
    blank page where needed, so a double-sided print puts nothing else on its paper. Returns each part's first page,
    page count, and SHA-256."""
    import pymupdf

    merged = pymupdf.open()
    toc: list[list[Any]] = []
    record: list[dict[str, Any]] = []

    def blank() -> None:
        page = merged.new_page(width=612, height=792)
        page.insert_textbox(pymupdf.Rect(72, 380, 540, 410), BLANK, fontsize=10, align=pymupdf.TEXT_ALIGN_CENTER,
                            color=(0.35, 0.35, 0.35))

    for title, path, pages, *rest in parts:
        own_sheet = bool(rest and rest[0])
        source = pymupdf.open(path)
        chosen = page_list(pages, source.page_count)
        if own_sheet and merged.page_count % 2:
            blank()
        first = merged.page_count + 1
        for number in chosen:
            merged.insert_pdf(source, from_page=number, to_page=number)
        if own_sheet and merged.page_count % 2:
            blank()
        toc.append([1, title, first])
        record.append({"title": title, "file": str(path), "pages": pages or "all", "firstPage": first, "pageCount": len(chosen),
                       "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()})
    total = merged.page_count
    for index, page in enumerate(merged):
        text = f"{footer}   Page {index + 1} of {total}" if footer else f"Page {index + 1} of {total}"
        rect = page.rect
        page.insert_textbox(pymupdf.Rect(36, rect.height - 28, rect.width - 36, rect.height - 12), text, fontsize=8,
                            align=pymupdf.TEXT_ALIGN_CENTER, color=(0.35, 0.35, 0.35))
    merged.set_toc(toc)
    out.parent.mkdir(parents=True, exist_ok=True)
    merged.save(out, garbage=4, deflate=True)     # one copy of an image every part repeats (the letterhead's logo)
    return record


FILLED_FROM = "jason_filled_from"          # appProperty on a filled copy: the template it was made from
QUESTION_START = re.compile(r"^(\d{1,2}\.\s|Certification\.)")


def keep_together_requests(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Docs requests that keep each of a form's questions on one page: from a numbered question ("3. How should ...")
    or the certification, through its help, choices, and lines, to the paragraph before the next question, heading, or
    (for the certification) after its signature line. Every paragraph of a group keeps its lines together and all but
    the last keep with the next. Text is unchanged."""
    paragraphs = []
    tabs = doc.get("tabs") or []                       # read with tabs: the body is the first tab's
    body = doc.get("body") or (((tabs[0] or {}).get("documentTab") or {}).get("body") if tabs else None) or {}
    for item in body.get("content") or []:
        para = item.get("paragraph")
        if para is None:
            continue
        text = "".join((e.get("textRun") or {}).get("content", "") for e in para.get("elements") or []).strip()
        style = (para.get("paragraphStyle") or {}).get("namedStyleType", "")
        paragraphs.append((item["startIndex"], item["endIndex"], text, style.startswith("HEADING") or style == "TITLE"))
    groups: list[list[tuple[int, int, str]]] = []
    current: list[tuple[int, int, str]] | None = None
    for start, end, text, heading in paragraphs:
        if heading or QUESTION_START.match(text):
            current = None if heading else []
            if current is not None:
                groups.append(current)
        if current is not None:
            current.append((start, end, text))          # a blank line inside a question is part of it
            if text.startswith("Signature"):
                current = None
    requests = []
    for whole in groups:
        group = list(whole)
        while group and not group[-1][2]:                # trailing blank lines are not
            group.pop()
        group = [(start, end) for start, end, _ in group]
        for n, (start, end) in enumerate(group):
            style = {"keepLinesTogether": True, "keepWithNext": n < len(group) - 1}
            requests.append({"updateParagraphStyle": {"range": {"startIndex": start, "endIndex": end},
                                                      "paragraphStyle": style, "fields": "keepLinesTogether,keepWithNext"}})
    return requests


def filled_copies(drive: Any, template_id: str, *, name: str, folder_id: str) -> list[dict[str, Any]]:
    """The filled copies of a template already in ``folder_id`` under ``name``, newest first: those jason marked with
    the template's id, and copies made before the mark (same name, a Google Doc, in the folder)."""
    from jason.google.drive import GOOGLE_DOC_MIME_TYPE

    safe = name.replace("\\", "\\\\").replace("'", "\\'")
    hits = drive.list_files(f"'{folder_id}' in parents and name = '{safe}' and mimeType = '{GOOGLE_DOC_MIME_TYPE}' "
                            "and trashed = false", fields="id,name,modifiedTime,appProperties")
    mine = [h for h in hits if (h.get("appProperties") or {}).get(FILLED_FROM) in (None, template_id)]
    return sorted(mine, key=lambda h: str(h.get("modifiedTime") or ""), reverse=True)


def fill_doc(drive: Any, docs: Any, template_id: str, values: dict[str, str], *, name: str, folder_id: str,
             extras: list[str] | None = None) -> tuple[str, list[str]]:
    """The template Doc filled in its copy under ``name`` in ``folder_id``: the copy an earlier run made is refreshed in
    place (the template's current text imported over it, as Word, so it keeps its id, link, and sharing), and a copy is
    made only when there is none. Then the tokens are replaced. Returns the copy's id and the tokens left in it; other
    copies of the same name (older runs) are added to ``extras`` for a person to remove, never deleted here."""
    from jason.google.drive import DOCX_MIME_TYPE
    from jason.google.drive_properties import set_app_properties
    from jason.tasks.letters import document_text

    found = filled_copies(drive, template_id, name=name, folder_id=folder_id)
    if found:
        doc_id = str(found[0]["id"])
        drive.replace_content(doc_id, drive.export_bytes(template_id, DOCX_MIME_TYPE), mime_type=DOCX_MIME_TYPE)
        if extras is not None:
            extras.extend(str(h["id"]) for h in found[1:])
    else:
        doc_id = drive.copy(template_id, name, folder_id)
    set_app_properties(drive, doc_id, {FILLED_FROM: template_id})
    requests = [{"replaceAllText": {"containsText": {"text": "{" + k + "}", "matchCase": True}, "replaceText": v}}
                for k, v in values.items() if v]
    for i in range(0, len(requests), 200):
        docs.batch_update(doc_id, requests[i:i + 200])
    left = sorted(set(TOKEN.findall(document_text(docs.get(doc_id)))))
    return doc_id, left


def today_long(day: date | None = None) -> str:
    d = day or date.today()
    return f"{d:%B} {d.day}, {d.year}"


__all__ = ["GENERATORS", "Plan", "Resolved", "fill_doc", "insurance_html", "merge", "packet_dir", "page_html", "plan",
           "plan_lines", "print_pdf", "resolve", "statement_html", "template_tokens", "values_for"]
