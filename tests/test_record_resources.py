"""The record addresses as MCP resources and as the HTML reader, on made-up books: the listing (books, a part, the
top-level articles, a restricted book by name only), template reads (current, base, in force on a day, history), a
miss and a restricted refusal as not-found errors, the profiles that serve them, and the reader's link closure."""

import json
import posixpath
import sqlite3
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote

import anyio
import pytest

from jason.community.books import Book, BookEntry
from jason.community.definitions import DefinedTerm
from jason.community.living import LivingDocument, LivingInstrument, SourceKind, SourceRef
from jason.community.outlines import CitableDocument, DocumentOutline, Section
from jason.community.symbols import DocumentKind
from jason.mcp import resources
from jason.tasks.cite import Shelf
from jason.tasks.reader import links_in, write

OLD = "No more than ten percent (10%) of the Lots shall be let at any one time without the Board's written consent."
NEW = "No more than fifteen percent (15%) of the Lots shall be let at any one time without the Board's written consent."
BIRDS = "No poultry or livestock shall be kept on any Lot. The Board may adopt Rules for birds kept as pets."
BASE = f"""ARTICLE 1
1.1 Rules. "Rules" shall mean the regulations the Board adopts for the use of the Common Area.
ARTICLE 6
6.2 Letting of Lots.
(a) Limit. {OLD}
6.3 Animals. {BIRDS}
"""


def _run(text, bold=False, strike=False):
    return {"textRun": {"content": text, "textStyle": {"bold": bold, "strikethrough": strike}}}


def _amendment():
    paragraphs = [
        [_run("NOW, THEREFORE, the Association declares:\n")],
        [_run("Article 6, Section 6.2, subsection (a) (\"Limit\") is hereby amended and restated as follows "
              "(stricken out wording will be removed, and bolded wording will be added):\n")],
        [_run("No more than "), _run("ten percent (10%)", strike=True), _run(" "),
         _run("fifteen percent (15%)", bold=True), _run(OLD.split("(10%)", 1)[1] + "\n")],
        [_run("IN WITNESS WHEREOF, the Board.\n")],
    ]
    return {"revisionId": "rev-1", "body": {"content": [{"paragraph": {"elements": p}} for p in paragraphs]}}


def _outline(key, title, kind, lines):
    text, sections = "", []
    for number, caption, words in lines:
        start = len(text)
        text += f"{number} {caption} {words}\n"
        sections.append(Section(number, caption, 1 + number.count(".") + number.count("("), start, len(text)))
    return DocumentOutline(key, title, kind=kind, text=text, sections=sections)


@pytest.fixture
def books(tmp_path):
    lib = tmp_path / "library"
    (lib / "text").mkdir(parents=True)
    with sqlite3.connect(lib / "library.db") as conn:
        conn.execute("CREATE TABLE documents (id TEXT, path TEXT, kind TEXT, confidential INTEGER, sha256 TEXT)")
        conn.execute("INSERT INTO documents VALUES ('1', 'Governing/Covenants.pdf', 'declaration', 0, 'abc')")
    (lib / "text" / "1.txt").write_text(BASE, encoding="utf-8")
    sources = tmp_path / "living" / "cov" / "sources"
    sources.mkdir(parents=True)
    (sources / "doc-2.json").write_text(json.dumps(_amendment()), encoding="utf-8")
    first = SimpleNamespace(title="First Amendment", recorded=date(2099, 3, 1), adopted=None,
                            recorder_number="209903010001")
    living = LivingDocument("cov", "Covenants", DocumentKind.DECLARATION,
                            base=SourceRef(SourceKind.LIBRARY_TEXT, "Governing/Covenants.pdf", sha256="abc"),
                            base_from="the recorded copy",
                            instruments=(LivingInstrument("cov-1st", first, SourceRef(SourceKind.DOC, "doc-2")),))
    outlines = tmp_path / "outlines"
    outlines.mkdir()
    rules = _outline("rules", "Handbook", "operating_rules", [
        ("B-1", "Letting.", "Owners who let a Lot follow the Covenants."),
        ("B-2", "Pets.", "Birds are pets under the Covenants.")])
    (outlines / "rules.json").write_text(json.dumps(rules.to_dict()), encoding="utf-8")
    refs = [{"source": "cov", "source_section": "6.3", "kind": "section", "target": "cov#6.2(a)", "relation": "cites",
             "quote": "as 6.2(a) allows", "offset": 0},
            {"source": "cov", "source_section": "6.3", "kind": "section", "target": "cov#9.9", "relation": "cites",
             "quote": "under 9.9", "offset": 0},
            {"source": "rules", "source_section": "B-1", "kind": "section", "target": "cov#6.2", "relation": "cites",
             "quote": "follow the Covenants", "offset": 0}]
    (outlines / "references.json").write_text(json.dumps(refs), encoding="utf-8")
    community = SimpleNamespace(
        living_documents=lambda: (living,),
        citable_documents=lambda: (CitableDocument("cov", "Covenants", "doc-1", DocumentKind.DECLARATION,
                                                   aliases=("Covenants",), cite_as="Covenants"),
                                   CitableDocument("rules", "Handbook", "doc-4", DocumentKind.OPERATING_RULES,
                                                   aliases=("Handbook",))),
        book_entries=lambda: (BookEntry("cov", Book.DECL), BookEntry("rules", Book.RULES, part="handbook"),
                              BookEntry("rules", Book.MANUAL)),
        defined_terms=lambda: (DefinedTerm("Rules", "cov", "1.1"),),
        governing_set=lambda: None, conflicts=lambda: (), notice_provisions=lambda: ())
    return community, tmp_path


def _server(community, data_dir, profile="governance"):
    from jason.mcp.server import build

    return build(profile, community=community, data_dir=data_dir)


def _ask(server, *calls):
    """Run client calls against the server in memory; each call is (method, argument) and returns its result or the
    error raised."""
    from mcp.client import Client

    out = []

    async def go():
        async with Client(server) as client:
            for method, arg in calls:
                try:
                    out.append(await (getattr(client, method)(arg) if arg is not None else getattr(client, method)()))
                except Exception as exc:  # the error is the answer under test
                    out.append(exc)

    anyio.run(go)
    return out


def test_the_listing_names_every_book_a_part_the_articles_and_a_restricted_book_by_name_only(books):
    community, root = books
    rows = resources.listing(community=community, data_dir=root)
    by_uri = {r["uri"]: r for r in rows}
    assert len(by_uri) == len(rows)                                   # nothing listed twice
    assert {f"jason://{b.value}" for b in Book} <= set(by_uri)
    assert "jason://rules.handbook" in by_uri
    assert {"jason://decl/1", "jason://decl/6"} <= set(by_uri)         # the top-level articles
    assert "jason://rules.handbook/B-1" in by_uri
    restricted = by_uri["jason://exec"]
    assert "Restricted" in restricted["description"] and "refused" in restricted["description"]
    assert restricted["audience"] == ["user"] and restricted["priority"] < by_uri["jason://decl"]["priority"]
    assert by_uri["jason://decl"]["lastModified"] == "2099-03-01"     # the version in force took effect then
    capped = resources.listing(community=community, data_dir=root, cap=5)       # the books and parts stay
    assert [r["uri"] for r in capped] == [r["uri"] for r in rows if r["uri"].count("/") == 2]


def test_template_reads_recite_first_then_the_address_terms_and_history(books):
    community, root = books
    server = _server(community, root)
    listed, templates, now, base, before, after, history, terms = _ask(
        server, ("list_resources", None), ("list_resource_templates", None),
        ("read_resource", "jason://decl/6.2(a)"), ("read_resource", "jason://decl@base/6.2(a)"),
        ("read_resource", "jason://decl:2099-02-01/6.2(a)"), ("read_resource", "jason://decl:2099-04-01/6.2(a)"),
        ("read_resource", "jason://decl/history/6.2(a)"), ("read_resource", "jason://decl/6.3"))
    uris = {t.uri_template for t in templates.resource_templates}
    assert {"jason://{book}", "jason://{book}/{+section}", "jason://{book}@{version}/{+section}",
            "jason://{book}:{date}/{+section}", "jason://{book}/history/{+section}", "jason://res/{number}",
            "jason://min/{day}", "jason://inst/{number}"} <= uris
    decl = next(r for r in listed.resources if r.uri == "jason://decl")
    assert decl.mime_type == resources.MIME and decl.annotations.last_modified == "2099-03-01"
    page = now.contents[0]
    assert page.mime_type == "text/markdown"
    text = page.text
    assert text.index("fifteen percent") < text.index("Address: `jason://decl/6.2(a)`")      # the words come first
    assert "_Covenants Section 6.2(a)" in text and "not an official restatement" in text
    assert "Permanent id: `decl@base/6.2(a)`" in text and "History: `jason://decl/history/6.2(a)`" in text
    assert "In force from: 2099-03-01" in text
    assert "ten percent" in base.contents[0].text and "fifteen" not in base.contents[0].text
    assert "ten percent" in before.contents[0].text and "fifteen percent" in after.contents[0].text
    h = history.contents[0].text
    assert "[@base 6.2(a)](jason://decl@base/6.2(a))" in h and "(jason://decl@2099-03-01/6.2(a))" in h
    assert "words changed" in h
    t = terms.contents[0].text
    assert "## Defined terms" in t and "**Rules** (Covenants Section 1.1, `jason://decl/1.1`)" in t
    assert t.index("poultry") < t.index("## Defined terms")


def test_a_miss_and_a_restricted_book_are_not_found_errors_with_the_reason(books):
    community, root = books
    miss, restricted, other = _ask(_server(community, root), ("read_resource", "jason://decl/9.9"),
                                   ("read_resource", "jason://exec/2099-01-01"),
                                   ("read_resource", "jason://decl@2099-01-02/6.2(a)"))
    from mcp.shared.exceptions import MCPError

    assert isinstance(miss, MCPError) and "not_in_document" in str(miss)
    assert isinstance(restricted, MCPError) and "restricted" in str(restricted) and "5215" in str(restricted)
    assert isinstance(other, MCPError) and "no_such_version" in str(other)
    with pytest.raises(resources.AddressNotFound) as found:
        resources.read("jason://ballots/2099-01-01", community=community, data_dir=root)
    assert found.value.reason == "restricted"


def test_the_resources_are_served_under_governance_and_all_not_the_board(books):
    community, root = books
    from jason.mcp.server import tools_for

    for profile, served in (("governance", True), ("", True), ("board", False)):
        (listed,) = _ask(_server(community, root, profile), ("list_resources", None))
        assert bool(listed.resources) is served
    assert len(tools_for("board")) == 45


def test_the_reader_writes_linked_pages_and_every_link_resolves_or_is_marked(books, tmp_path):
    community, root = books
    out = tmp_path / "reader"
    report = write(Shelf(community, root, repo=tmp_path / "no-repo"), out)
    assert (out / "index.html").is_file() and (out / "decl" / "6.2(a).html").is_file()
    assert (out / "decl" / "history" / "6.2(a).html").is_file()
    assert (out / "decl" / "@2099-03-01" / "6.2(a).html").is_file()
    assert not (out / "exec").exists() and "exec" in report.restricted
    assert report.missing.get("jason://decl/9.9", "").startswith("not_in_document")
    pages = list(out.rglob("*.html"))
    assert report.pages == len(pages)
    for page in pages:
        rel = page.relative_to(out).as_posix()
        for href in links_in(page.read_text(encoding="utf-8")):
            target = posixpath.normpath(posixpath.join(posixpath.dirname(rel), unquote(href)))
            assert (out / target).is_file(), f"{rel} links {href}"
    cited = (out / "decl" / "6.2(a).html").read_text(encoding="utf-8")
    assert cited.index("fifteen percent") < cited.index("Address <code>")
    assert 'href="6.3.html"' in cited                                  # what cites it, by its page
    citing = (out / "decl" / "6.3.html").read_text(encoding="utf-8")
    assert 'class="missing"' in citing and "9.9" in citing             # a cited section with no page is marked
    assert 'href="1.1.html"' in citing                                 # the defined term's definition
    parent = (out / "decl" / "6.2.html").read_text(encoding="utf-8")
    assert 'href="../rules.handbook/B-1.html"' in parent                # another document's section that cites it


def test_the_reader_writes_a_restricted_book_only_when_private(books, tmp_path):
    community, root = books
    out = tmp_path / "private"
    report = write(Shelf(community, root, repo=tmp_path / "no-repo", private=True), out, private=True)
    assert (out / "exec" / "index.html").is_file() and not report.restricted


def test_the_reader_names_case_apart_and_maps_versions_and_days_to_paths():
    from jason.tasks.reader import _path_for

    assert _path_for("jason://decl") == "decl/index.html"
    assert _path_for("jason://decl@2099-03-01") == "decl/@2099-03-01/index.html"
    assert _path_for("jason://decl:2099-03-01/6.2(a)") == "decl/in-force-2099-03-01/6.2(a).html"
    assert _path_for("jason://min/2099-01-01#item-4") == "min/2099-01-01/~item-4.html"
    assert _path_for("law:CIV 4920(a)") == "law/CIV-4920(a).html"
    assert ".." not in Path(_path_for("jason://decl/6.2..6.4")).parts
