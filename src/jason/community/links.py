"""Links in the association's letters, forms, and emails: statute citations to the official text, and web addresses and
email addresses made clickable, without changing what prints.

A citation the documents write ("Civil Code §4041(b)(2)(A)", "Civil Code 5220", "CIV 4041") links to the section on
leginfo.legislature.ca.gov (``authorities.LEGINFO_SECTION``); the subdivision stays in the text, since the official page
is the section. A bare web address or email address links to itself (an email with an optional subject). Only text
outside tags and outside an existing link is touched, so a template's own links stand. In a printed letter the visible
text is unchanged; in the PDF and the email it can be clicked.
"""

from __future__ import annotations

import html
import re
from urllib.parse import quote

from jason.community.authorities import LEGINFO_SECTION
from jason.community.references import LETTER     # "Civil Code 2924f" links to 2924f, never to 2924

# The code names the documents write, to the Legislature's abbreviations.
CODE_NAMES = {
    "Civil Code": "CIV", "Corporations Code": "CORP", "Government Code": "GOV", "Health and Safety Code": "HSC",
    "Code of Civil Procedure": "CCP", "Business and Professions Code": "BPC", "Evidence Code": "EVID",
    "Insurance Code": "INS", "Vehicle Code": "VEH", "Probate Code": "PROB", "Revenue and Taxation Code": "RTC",
}
_NAMES = "|".join(sorted((re.escape(n) for n in CODE_NAMES), key=len, reverse=True))
_ABBREVIATIONS = "|".join(sorted(set(CODE_NAMES.values()), key=len, reverse=True))
CITATION = re.compile(
    rf"(?P<cite>(?:(?P<name>{_NAMES})|\b(?P<abbr>{_ABBREVIATIONS}))\s+(?:§§?\s*)?(?P<section>\d{{2,5}}(?:\.\d+)?{LETTER})"
    rf"(?P<sub>(?:\([a-zA-Z0-9]{{1,4}}\))*))")
URL = re.compile(r"(?<![\"'=/\w])(?P<url>https?://[^\s<>\"']+?)(?=[.,;:!?)]*(?:\s|$|<))")
EMAIL = re.compile(r"(?<![\w.:/@-])(?P<email>[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)(?![\w@])")
# A tag, or a whole existing link: neither is touched.
_SKIP = re.compile(r"(<a\b.*?</a>|<[^>]+>)", re.IGNORECASE | re.DOTALL)


def statute_url(code: str, section: str) -> str:
    """The official page of one section, by the code's abbreviation ("CIV") and the section number ("4041")."""
    return LEGINFO_SECTION.format(code=code, section=section)


def _text_only(text: str, change) -> str:
    parts = _SKIP.split(text)
    return "".join(part if i % 2 else change(part) for i, part in enumerate(parts))


def link_citations(text: str) -> str:
    """Each statute citation in ``text`` (HTML) linked to the official section."""
    def one(m: re.Match) -> str:
        code = CODE_NAMES.get(m.group("name") or "", m.group("abbr") or "")
        return f'<a href="{html.escape(statute_url(code, m.group("section")))}">{m.group("cite")}</a>'

    return _text_only(text, lambda part: CITATION.sub(one, part))


def mailto(address: str, subject: str = "") -> str:
    return f"mailto:{address}" + (f"?subject={quote(subject)}" if subject else "")


def link_contacts(text: str, *, subject: str = "") -> str:
    """Each bare web address and email address in ``text`` (HTML) made a link; an email link carries ``subject``."""
    def change(part: str) -> str:
        part = URL.sub(lambda m: f'<a href="{html.escape(m.group("url"))}">{m.group("url")}</a>', part)
        return _text_only(part, lambda p: EMAIL.sub(
            lambda m: f'<a href="{html.escape(mailto(m.group("email"), subject))}">{m.group("email")}</a>', p))

    return _text_only(text, change)


def linkify(text: str, *, subject: str = "") -> str:
    """Citations, web addresses, and email addresses in ``text`` (HTML) made links."""
    return link_contacts(link_citations(text), subject=subject)


HELP_TOKEN = re.compile(r"\{HELP(?P<steps>_STEPS)?:(?P<key>[a-z0-9-]+)\}")


def fill_help_tokens(text: str, articles) -> tuple[str, list[str]]:
    """``{HELP:key}`` replaced by a link to that help article with its title, and ``{HELP_STEPS:key}`` by its steps
    (for print, where a link cannot be clicked). Returns the text and the keys no article has, left in place."""
    by_key = {a.key: a for a in articles}
    missing: list[str] = []

    def one(m: re.Match) -> str:
        article = by_key.get(m.group("key"))
        if article is None:
            missing.append(m.group("key"))
            return m.group(0)
        if m.group("steps"):
            return html.escape(article.steps or article.title)
        return f'<a href="{html.escape(article.url)}">{html.escape(article.title)}</a>'

    return HELP_TOKEN.sub(one, text), missing


# In Markdown: an existing link ``[text](url)`` or picture ``![alt](file)``, or code in backticks, is left alone.
_MD_SKIP = re.compile(r"(!?\[[^\]]*\]\([^)]*\)|`[^`]*`)")


def link_citations_markdown(text: str) -> str:
    """Each statute citation in ``text`` (Markdown) made a link to the official section, as ``link_citations`` does
    for HTML: a Doc written from Markdown links them as the email does."""
    def one(m: re.Match) -> str:
        code = CODE_NAMES.get(m.group("name") or "", m.group("abbr") or "")
        return f"[{m.group('cite')}]({statute_url(code, m.group('section'))})"

    parts = _MD_SKIP.split(text)
    return "".join(part if i % 2 else CITATION.sub(one, part) for i, part in enumerate(parts))


def fill_help_markdown(text: str, articles) -> tuple[str, list[str]]:
    """``fill_help_tokens`` for Markdown: ``{HELP:key}`` becomes a link to the help article by its title, and
    ``{HELP_STEPS:key}`` its steps. Returns the text and the keys no article has, left in place."""
    by_key = {a.key: a for a in articles}
    missing: list[str] = []

    def one(m: re.Match) -> str:
        article = by_key.get(m.group("key"))
        if article is None:
            missing.append(m.group("key"))
            return m.group(0)
        return (article.steps or article.title) if m.group("steps") else f"[{article.title}]({article.url})"

    return HELP_TOKEN.sub(one, text), missing


def pdf_targets(text: str, *, subject: str = "") -> list[tuple[str, str]]:
    """Each linkable span of plain ``text`` and its target: a citation's official section, a web address, or an email."""
    out = []
    for m in CITATION.finditer(text):
        out.append((m.group("cite"), statute_url(CODE_NAMES.get(m.group("name") or "", m.group("abbr") or ""),
                                                 m.group("section"))))
    out += [(m.group("url"), m.group("url")) for m in URL.finditer(text)]
    out += [(m.group("email"), mailto(m.group("email"), subject)) for m in EMAIL.finditer(text)]
    return out


def link_pdf(path, out=None, *, subject: str = "") -> int:
    """Lay a link over each citation, web address, and email address a PDF's pages print (a Doc export, a scanned-in
    form's text layer), where no link already covers it. Writes ``out`` (or the file in place) and returns the links
    added. What prints is unchanged."""
    from pathlib import Path

    import pymupdf

    path = Path(path)
    added = 0
    with pymupdf.open(path) as doc:
        for page in doc:
            have = [pymupdf.Rect(link["from"]) for link in page.get_links() if link.get("from")]
            text = " ".join(page.get_text().split())
            for span, target in dict.fromkeys(pdf_targets(text, subject=subject)):
                for rect in page.search_for(span):
                    if any(rect.intersects(r) for r in have):
                        continue
                    page.insert_link({"kind": pymupdf.LINK_URI, "from": rect, "uri": target})
                    have.append(rect)
                    added += 1
        target = Path(out or path)
        if target == path:
            tmp = path.with_suffix(".linking.pdf")
            doc.save(tmp, garbage=3, deflate=True)
        else:
            doc.save(target, garbage=3, deflate=True)
    if target == path:
        tmp.replace(path)
    return added


__all__ = ["CITATION", "CODE_NAMES", "HELP_TOKEN", "fill_help_tokens", "link_citations", "link_contacts", "link_pdf", "linkify", "mailto", "pdf_targets",
           "statute_url"]
