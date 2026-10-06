"""A document defined once: a layout apart from its blocks, rendered to many outputs (docs/document-templates.md).

The form engine writes one ``FormTemplate`` as paper, a fillable PDF, a Google Form, and a PayHOA sheet. This module does
the same for a whole document. A ``DocumentDefinition`` is an ordered list of items:

- ``ProseBlock``: words written once, with ``{TOKENS}`` from the value layers;
- ``ManualBlock``: the owner's manual's own tokens (``{PART:slot}``, ``{INCLUDE:book}``, ``{EXCERPTS}``, ``{LAW:...}``,
  ``{ADOPTION_HISTORY}``), read through ``manual.fill_token``, the same function ``manual.render`` calls;
- ``FormBlock``: a ``FormTemplate`` rendered as its paper form, by ``form_render.paper_markdown``, so the form in a
  document and the live form are one definition;
- ``DirectoryBlock``: roles and contact fields, each field printed only if its own publish flag is set;
- ``QuoteBlock``: a passage read from the stored authority;
- ``ComputedBlock``: a table a function of the stores;
- ``EmbeddedBlock``: another document by reference (a nested definition, or a stored file attached as it is), with a gap
  line, never a silent skip, when a part is missing or stale.

Every block names its source and an as-of day and is rendered, never copied. ``assemble`` renders the blocks and knows no
layout; a ``Layout`` (headings, numbering, header, footer, contents, separators, style tokens) is applied by a renderer
(``MarkdownRenderer``, ``HtmlRenderer``) to the finished blocks and never reads a block's source. A second layout
therefore changes how the same blocks look and not one word they say.

Every rendered piece is a ``manual.Chunk``: the words it stands for, the span of its source, or a label. ``check`` reports
a block that is missing, a gap, an unlabeled piece, and a token left open. This module is pure: the disk is in
``jason.tasks.document_templates``.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Callable, Mapping, Protocol, Sequence

from jason.community.manual import EDITORIAL, NAME, TOKEN, Chunk, ManualError, concordance, fill_token


class DocumentError(ManualError):
    """A definition cannot be filled: a source is missing, a token has no value, a block is unknown. Every problem is
    listed; nothing is rendered half."""


# ---------------------------------------------------------------------------------------------------------------------
# The layout


@dataclass(frozen=True)
class Layout:
    """How a document looks, and nothing it says. Every field's default does nothing, so the plain layout leaves the
    blocks' Markdown as it is.

    ``heading_shift`` moves every heading down that many levels; ``numbered`` numbers the headings (1, 1.1); ``header`` and
    ``footer`` are running lines (tokens: ``{DOCUMENT_TITLE}``, ``{AS_OF}``, and the document's values); ``contents``
    lists the headings to ``contents_depth``; ``title_heading`` prints the title first; ``cover`` is lines printed before
    it; ``separator`` is a line between blocks; ``page_break_before`` is the heading levels that start a page (HTML and
    PDF); ``styles`` are named style tokens, written as CSS variables in HTML."""

    key: str = "plain"
    heading_shift: int = 0
    numbered: bool = False
    header: str = ""
    footer: str = ""
    contents: bool = False
    contents_depth: int = 2
    title_heading: bool = False
    cover: tuple[str, ...] = ()
    separator: str = ""
    page_break_before: tuple[int, ...] = ()
    styles: tuple[tuple[str, str], ...] = ()


PLAIN = Layout()
GUIDE = Layout("guide", heading_shift=0, numbered=True, header="{DOCUMENT_TITLE}", footer="As of {AS_OF}",
               contents=True, title_heading=True, separator="---", page_break_before=(2,),
               styles=(("font", "Georgia, serif"), ("size", "11pt"), ("accent", "#1f3a5f"), ("rule", "#bbbbbb")))
LAYOUTS = {PLAIN.key: PLAIN, GUIDE.key: GUIDE}


# ---------------------------------------------------------------------------------------------------------------------
# Context and results


@dataclass(frozen=True)
class ContactField:
    """One contact detail of a person (``email``, ``phone``, ``address``), printed only when ``publish`` is set."""

    kind: str
    value: str
    publish: bool = False


@dataclass(frozen=True)
class DirectoryEntry:
    """A person in a role. ``publish`` is the person's own confirmation that the role and name may be printed in a
    document that goes to owners; each contact field has its own flag. All of it is private data (``data/spec``)."""

    role: str
    name: str
    publish: bool = False
    contacts: tuple[ContactField, ...] = ()


@dataclass(frozen=True)
class Embedded:
    """What an embedded block finds: a nested definition to render, or a stored file to attach as it is (its stable
    ``address``, its ``pages``), and the day it is as of."""

    definition: DocumentDefinition | None = None
    address: str = ""
    pages: int = 0
    as_of: date | None = None
    title: str = ""


@dataclass
class ManualContext:
    """What the manual's tokens read: the classification, the profile's spec, the source, the manual's text."""

    classification: Any
    spec: Any
    source: Any
    text: str
    passages: list = field(default_factory=list)
    current: bool = False
    rows: list = field(default_factory=list)


@dataclass
class Context:
    values: dict[str, str] = field(default_factory=dict)
    as_of: date | None = None
    audience: str = "owners"                       # "owners" prints only what is published; "board" prints all
    manual: ManualContext | None = None
    forms: Mapping[str, Any] = field(default_factory=dict)
    directory: Sequence[DirectoryEntry] = ()
    documents: Mapping[str, Embedded] = field(default_factory=dict)
    quote: Callable[[str], str] | None = None
    computed: Mapping[str, Callable[[Context], list[list[str]]]] = field(default_factory=dict)


def manual_context(classification: Any, spec: Any, source: Any, text: str, *, values: dict[str, str] | None = None,
                   passages: Sequence[Any] = (), current: bool = False, as_of: date | None = None) -> Context:
    """A context for the owner's manual: the values ``manual.render`` sets, and the concordance its history reads."""
    vals = dict(values or {})
    vals.setdefault("RULES_TITLE", spec.rules_title)
    vals.setdefault("MANUAL_TITLE", spec.manual_title)
    return Context(vals, as_of, manual=ManualContext(classification, spec, source, text, list(passages), current,
                                                     concordance(classification, text)))


@dataclass
class BlockResult:
    """One block rendered: the Markdown it contributes, its chunks, the gaps it found, and its place in the part map."""

    id: str
    kind: str
    markdown: str
    chunks: list[Chunk] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    title: str = ""
    source: str = ""
    as_of: date | None = None
    required: bool = False
    authority: str = ""
    fields: tuple[str, ...] = ()                    # a form block's question ids, unchanged from the form
    address: str = ""                               # an attached file's stable address
    pages: int = 0
    prose: bool = False


def fill_values(text: str, values: Mapping[str, str]) -> str:
    return NAME.sub(lambda n: values.get(n.group(1), n.group(0)), text)


# ---------------------------------------------------------------------------------------------------------------------
# Blocks


@dataclass(frozen=True)
class Block:
    """A content block: its ``id`` (stable in the document), its ``source`` (named, never copied), and the day it is read as
    of. ``required`` and ``authority`` say the law asks for it."""

    id: str
    source: str = ""
    as_of: date | None = None
    required: bool = False
    authority: str = ""
    kind = "block"

    def render(self, ctx: Context) -> BlockResult:                            # pragma: no cover - overridden
        raise NotImplementedError

    def _result(self, markdown: str, chunks: list[Chunk], **kw: Any) -> BlockResult:
        return BlockResult(self.id, kw.pop("kind", self.kind), markdown, chunks, source=kw.pop("source", self.source),
                           as_of=self.as_of, required=self.required, authority=self.authority, **kw)


@dataclass(frozen=True)
class ProseBlock(Block):
    """Words written once. ``text`` keeps its own whitespace, so a definition read from a template joins as the
    template does."""

    text: str = ""
    kind = "prose"

    def render(self, ctx: Context) -> BlockResult:
        filled = fill_values(self.text, ctx.values)
        chunks = [Chunk(filled.strip(), kind=EDITORIAL, label="the template's own words")] if filled.strip() else []
        return self._result(filled, chunks, prose=True, source=self.source or "the definition")


@dataclass(frozen=True)
class ManualBlock(Block):
    """One of the owner's manual's tokens, read through ``manual.fill_token`` (the words ``manual.render`` prints)."""

    verb: str = "PART"
    arg: str = ""
    flags: tuple[str, ...] = ()

    @property
    def kind(self) -> str:                                                    # type: ignore[override]
        return {"PART": "part", "INCLUDE": "rule-book", "EXCERPTS": "excerpts", "LAW": "law",
                "ADOPTION_HISTORY": "history"}.get(self.verb, "manual")

    @property
    def token(self) -> str:
        return "{" + self.verb + (":" + self.arg if self.arg else "") + "".join(" " + f for f in self.flags) + "}"

    def render(self, ctx: Context) -> BlockResult:
        if ctx.manual is None:
            raise DocumentError(f"{self.token}: the context has no manual to read")
        m = ctx.manual
        made = fill_token(self.token, self.verb, self.arg, set(self.flags), m.classification, m.spec, m.source, m.text,
                          m.rows, m.passages, m.current)
        return self._result("\n\n".join(c.markdown for c in made if c.markdown), made,
                            source=self.source or self.token, title=self.arg)


@dataclass(frozen=True)
class QuoteBlock(Block):
    """A passage of a governing document or a statute, by its reference (``decl#4.15``, ``CIV 5730(a)``), with the words
    read from the stored authority."""

    ref: str = ""
    kind = "quote"

    def render(self, ctx: Context) -> BlockResult:
        if ctx.quote is None:
            raise DocumentError(f"{self.id}: no authority to quote {self.ref!r} from")
        words = ctx.quote(self.ref)
        return self._result(words, [Chunk(words, words, kind="quote", label=f"quoted from {self.ref}")],
                            source=self.source or self.ref, title=self.ref)


@dataclass(frozen=True)
class FormBlock(Block):
    """A form by its key, printed as its paper form: one definition shared with the live form. Its question ids come
    through unchanged. The Doc editor's keep-together marks are layout, not words, and are left out here."""

    form: str = ""
    kind = "form"

    def render(self, ctx: Context) -> BlockResult:
        from jason.community.form_render import fill, paper_markdown

        template = ctx.forms.get(self.form)
        if template is None:
            gap = f"The form {self.form!r} is not defined."
            return self._result(f"_[{gap}]_", [Chunk(f"_[{gap}]_", kind=EDITORIAL, label="a gap")], gaps=[gap],
                                source=self.source or f"form:{self.form}", title=self.form)
        lines = [ln for ln in paper_markdown(template) if ln not in (r"\keep", r"\endkeep")]
        text = fill("\n".join(lines).strip(), ctx.values)
        return self._result(text, [Chunk(text, kind="form", label=f"form {self.form}, rendered from its definition")],
                            source=self.source or f"form:{self.form}", title=template.title,
                            fields=tuple(q.field for q in template.questions))


@dataclass(frozen=True)
class DirectoryBlock(Block):
    """A table of roles and the contact fields the people published. ``roles`` are the roles listed, in order; a role
    nobody holds is a visible line, not a dropped row. In an owners' document a name prints only when the person
    published it, and a contact field only when its own flag is set; an unpublished field is a miss."""

    roles: tuple[str, ...] = ()
    fields: tuple[str, ...] = ("email", "phone")
    kind = "directory"

    def render(self, ctx: Context) -> BlockResult:
        owners = ctx.audience != "board"
        wanted = self.roles or tuple(dict.fromkeys(e.role for e in ctx.directory))
        rows: list[list[str]] = []
        gaps: list[str] = []
        for role in wanted:
            held = [e for e in ctx.directory if e.role == role]
            if not held:
                rows.append([role, "(vacant)", *[""] * len(self.fields)])
                gaps.append(f"No one holds the role {role}.")
                continue
            for e in held:
                if owners and not e.publish:
                    rows.append([role, "(not published)", *[""] * len(self.fields)])
                    continue
                cells = []
                for kind in self.fields:
                    got = [c.value for c in e.contacts if c.kind == kind and (c.publish or not owners)]
                    cells.append("; ".join(got))
                rows.append([role, e.name, *cells])
        head = ["Role", "Name", *[f.title() for f in self.fields]]
        lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
        lines += ["| " + " | ".join(r) + " |" for r in rows]
        text = "\n".join(lines)
        label = "published fields only" if owners else "every field: a draft for the board, not for owners"
        return self._result(text, [Chunk(text, kind="directory", label=label)], gaps=gaps,
                            source=self.source or "the association's directory (private facts)", title="Directory")


@dataclass(frozen=True)
class ComputedBlock(Block):
    """A table computed from the stores by a named function in the context: a head and rows, with the inputs it read
    named in ``source``."""

    name: str = ""
    head: tuple[str, ...] = ()
    kind = "computed"

    def render(self, ctx: Context) -> BlockResult:
        fn = ctx.computed.get(self.name)
        if fn is None:
            gap = f"No computation {self.name!r}."
            return self._result(f"_[{gap}]_", [Chunk(f"_[{gap}]_", kind=EDITORIAL, label="a gap")], gaps=[gap],
                                title=self.name)
        rows = fn(ctx)
        lines = ["| " + " | ".join(self.head) + " |", "|" + "---|" * len(self.head)]
        lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
        text = "\n".join(lines)
        return self._result(text, [Chunk(text, kind="computed", label=f"computed by {self.name}")],
                            source=self.source or self.name, title=self.name)


@dataclass(frozen=True)
class EmbeddedBlock(Block):
    """Another document by reference. A nested definition renders in place (its headings one level down); a stored file
    prints an attachment line with its address and page count, for the PDF output to splice. A part that is missing, or
    older than the block's as-of day, prints a visible gap line and is reported, never skipped."""

    ref: str = ""
    title: str = ""
    kind = "embedded"

    def render(self, ctx: Context) -> BlockResult:
        found = ctx.documents.get(self.ref)
        name = self.title or (found.title if found else "") or self.ref
        why = f" (required by {self.authority})" if self.authority else ""
        if found is None or (found.definition is None and not found.address):
            return self._gap(f"{name}{why}: not on file.", name)
        if self.as_of and found.as_of and found.as_of < self.as_of:
            return self._gap(f"{name}{why}: the copy on file is as of {found.as_of.isoformat()}, not {self.as_of.isoformat()}.",
                             name)
        if found.definition is not None:
            inner_ctx = replace(ctx, as_of=self.as_of or ctx.as_of)
            inner = assemble(found.definition, inner_ctx)
            body = shift_headings(MarkdownRenderer().body(inner, PLAIN), 1)
            chunks = [c for r in inner.results for c in r.chunks]
            res = self._result(body, chunks, source=self.source or f"document:{found.definition.key}", title=name,
                               gaps=[g for r in inner.results for g in r.gaps])
            return res
        line = f"_[Attached: {name} ({found.address}{', ' + str(found.pages) + ' pages' if found.pages else ''}"
        line += f"{', as of ' + found.as_of.isoformat() if found.as_of else ''}).]_"
        return self._result(line, [Chunk(line, kind="attachment", label="a stored file attached as it is")],
                            source=self.source or found.address, title=name, address=found.address, pages=found.pages)

    def _gap(self, text: str, name: str) -> BlockResult:
        line = f"_[Missing: {text}]_"
        return self._result(line, [Chunk(line, kind=EDITORIAL, label="a gap")], gaps=[text], title=name)


# ---------------------------------------------------------------------------------------------------------------------
# The definition and assembling it


@dataclass(frozen=True)
class DocumentDefinition:
    """One document: its key and title, the layout it prints in by default, and its blocks in order."""

    key: str
    title: str
    items: tuple[Block, ...]
    layout: Layout = PLAIN
    kind: str = ""
    authority: str = ""

    def block(self, id_: str) -> Block:
        return next(b for b in self.items if b.id == id_)


@dataclass
class Assembly:
    definition: DocumentDefinition
    results: list[BlockResult]
    values: dict[str, str]
    as_of: date | None

    @property
    def chunks(self) -> list[Chunk]:
        return [c for r in self.results for c in r.chunks]

    @property
    def gaps(self) -> list[str]:
        return [g for r in self.results for g in r.gaps]


def assemble(definition: DocumentDefinition, ctx: Context) -> Assembly:
    """Render every block, in order. No layout is read here: this is the definition's content."""
    ids = [b.id for b in definition.items]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise DocumentError("block ids used twice: " + ", ".join(dupes))
    results: list[BlockResult] = []
    problems: list[str] = []
    for b in definition.items:
        try:
            results.append(b.render(ctx))
        except ManualError as exc:
            problems.append(str(exc))
    if problems:
        raise DocumentError("; ".join(problems))
    return Assembly(definition, results, dict(ctx.values), ctx.as_of)


def definition_from_template(template: str, key: str, title: str, layout: Layout = PLAIN, *, kind: str = "",
                             authority: str = "") -> DocumentDefinition:
    """A definition read from a base template that uses the manual's tokens: each token a ``ManualBlock``, the words
    between them a ``ProseBlock`` (their whitespace kept). The base's header comment is not part of the document."""
    body = re.sub(r"^<!--.*?-->\s*", "", template, flags=re.S)
    items: list[Block] = []
    seen: dict[str, int] = {}

    def ident(base: str) -> str:
        seen[base] = seen.get(base, 0) + 1
        return base if seen[base] == 1 else f"{base}-{seen[base]}"

    at = 0
    for m in TOKEN.finditer(body):
        lead = body[at:m.start()]
        if lead:
            items.append(ProseBlock(ident("prose"), text=lead))
        verb, arg, flags = m.group("verb"), m.group("arg") or "", tuple((m.group("flags") or "").split())
        base = (verb.lower().replace("_", "-") + ("-" + re.sub(r"[^a-z0-9]+", "-", arg.lower()).strip("-") if arg else ""))
        items.append(ManualBlock(ident(base), verb=verb, arg=arg, flags=flags))
        at = m.end()
    if body[at:]:
        items.append(ProseBlock(ident("prose"), text=body[at:]))
    return DocumentDefinition(key, title, tuple(items), layout, kind, authority)


# ---------------------------------------------------------------------------------------------------------------------
# Renderers


class Renderer(Protocol):
    """One finished assembly and a layout in, one output out. A renderer never reads a block's source."""

    def render(self, assembly: Assembly, layout: Layout) -> str: ...


HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def shift_headings(markdown: str, by: int) -> str:
    if not by:
        return markdown
    return "\n".join(f"{'#' * min(6, len(m.group(1)) + by)} {m.group(2)}" if (m := HEADING.match(ln)) else ln
                     for ln in markdown.split("\n"))


def headings_of(markdown: str, depth: int = 6) -> list[tuple[int, str]]:
    return [(len(m.group(1)), m.group(2)) for ln in markdown.split("\n") if (m := HEADING.match(ln))
            and len(m.group(1)) <= depth]


def number_headings(markdown: str) -> str:
    counts = [0] * 7
    out = []
    for ln in markdown.split("\n"):
        m = HEADING.match(ln)
        if not m:
            out.append(ln)
            continue
        level = len(m.group(1))
        if level < 2:
            out.append(ln)
            continue
        counts[level] += 1
        for deeper in range(level + 1, 7):
            counts[deeper] = 0
        label = ".".join(str(counts[k]) for k in range(2, level + 1) if counts[k]) or str(counts[level])
        out.append(f"{m.group(1)} {label}. {m.group(2)}")
    return "\n".join(out)


def _tokens(layout_text: str, assembly: Assembly) -> str:
    values = dict(assembly.values)
    values["DOCUMENT_TITLE"] = assembly.definition.title
    values["AS_OF"] = assembly.as_of.isoformat() if assembly.as_of else "the day it was made"
    return fill_values(layout_text, values)


class MarkdownRenderer:
    """The Markdown output. With the plain layout it is exactly the blocks' words joined as the template joined them."""

    def body(self, assembly: Assembly, layout: Layout) -> str:
        pieces: list[str] = []
        for r in assembly.results:
            pieces.append(r.markdown)
            if layout.separator and not r.prose and r.markdown:
                pieces.append(f"\n\n{layout.separator}\n\n")
        out = "".join(pieces)
        out = re.sub(r"\n{3,}", "\n\n", out).strip()
        return shift_headings(out, layout.heading_shift)

    def render(self, assembly: Assembly, layout: Layout) -> str:
        body = self.body(assembly, layout)
        if layout.numbered:
            body = number_headings(body)
        top: list[str] = []
        if layout.header:
            top.append(f"_{_tokens(layout.header, assembly)}_")
        top += [_tokens(c, assembly) for c in layout.cover]
        if layout.title_heading:
            top.append(f"# {assembly.definition.title}")
        if layout.contents:
            heads = [(lv, t) for lv, t in headings_of(body, layout.contents_depth + layout.heading_shift) if lv >= 2]
            if heads:
                base = min(lv for lv, _ in heads)
                top.append("## Contents\n\n" + "\n".join(f"{'  ' * (lv - base)}- {t}" for lv, t in heads))
        tail = [f"_{_tokens(layout.footer, assembly)}_"] if layout.footer else []
        out = "\n\n".join([*top, body, *tail] if body else [*top, *tail])
        return re.sub(r"\n{3,}", "\n\n", out).strip() + "\n"


def _inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"(?<![\w])_(.+?)_(?![\w])", r"<em>\1</em>", text)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def markdown_to_html(markdown: str, *, break_before: Sequence[int] = ()) -> str:
    """The subset of Markdown the blocks write (headings, paragraphs, bullets, tables, rules, bold, italic) as HTML."""
    out: list[str] = []
    lines = markdown.split("\n")
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = HEADING.match(ln)
        if m:
            level = len(m.group(1))
            cls = ' class="break"' if level in break_before else ""
            out.append(f'<h{level} id="{_slug(m.group(2))}"{cls}>{_inline(m.group(2))}</h{level}>')
        elif ln.strip() == "---":
            out.append("<hr>")
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows if not re.fullmatch(r"[|\-\s:]+", r)]
            tr = ["<table>"]
            for n, row in enumerate(cells):
                tag = "th" if n == 0 else "td"
                tr.append("<tr>" + "".join(f"<{tag}>{_inline(c)}</{tag}>" for c in row) + "</tr>")
            tr.append("</table>")
            out.append("".join(tr))
            continue
        elif re.match(r"^\s*[-*]\s+", ln):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append(f"<li>{_inline(re.sub(r'^\s*[-*]\s+', '', lines[i]))}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif ln.strip():
            para = [ln.strip()]
            while i + 1 < len(lines) and lines[i + 1].strip() and not HEADING.match(lines[i + 1]) \
                    and not lines[i + 1].startswith("|") and lines[i + 1].strip() != "---":
                i += 1
                para.append(lines[i].strip())
            out.append("<p>" + "<br>".join(_inline(p) for p in para) + "</p>")
        i += 1
    return "\n".join(out)


class HtmlRenderer:
    """The HTML output: the Markdown output's body in a page whose style tokens are CSS variables and whose header and
    footer are the layout's. Printed to PDF by the installed Chrome or Edge, as the packets' generated parts are."""

    def render(self, assembly: Assembly, layout: Layout) -> str:
        md = MarkdownRenderer().render(assembly, replace(layout, header="", footer=""))
        body = markdown_to_html(md, break_before=tuple(lv + layout.heading_shift for lv in layout.page_break_before))
        styles = dict(layout.styles)
        root = "".join(f"--{k}:{v};" for k, v in styles.items())
        header = f'<div class="running header">{html.escape(_tokens(layout.header, assembly))}</div>' if layout.header else ""
        footer = f'<div class="running footer">{html.escape(_tokens(layout.footer, assembly))}</div>' if layout.footer else ""
        css = (f":root{{{root}}}body{{font-family:var(--font,serif);font-size:var(--size,11pt);color:#111}}"
               "h1,h2,h3,h4{color:var(--accent,#000)}hr{border:0;border-top:1px solid var(--rule,#999)}"
               "table{border-collapse:collapse}td,th{border:1px solid var(--rule,#999);padding:2px 6px}"
               ".running{position:fixed;left:0;right:0;font-size:9pt;color:#555}.header{top:0}.footer{bottom:0}"
               "@media print{h2.break,h3.break,h4.break{page-break-before:always}}")
        return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
                f"<title>{html.escape(assembly.definition.title)}</title><style>{css}</style></head>"
                f"<body>{header}{body}{footer}</body></html>\n")


# ---------------------------------------------------------------------------------------------------------------------
# The check, and the part map


@dataclass(frozen=True)
class Requirement:
    """Something the law asks the document to include: a block id that must be placed, with its authority."""

    block: str
    authority: str = ""


@dataclass
class DocumentCheck:
    placed: list[str]
    unplaced: list[str]                # blocks the definition names that were not rendered (never, after assemble)
    uncovered: list[str]               # requirements no block covers (a part shown as a gap is covered: it is visible)
    gaps: list[str]                    # parts missing, stale, or vacant, shown in the document as a visible line
    unlabeled: list[str]               # pieces with neither a source span nor a label: a defect
    open_tokens: list[str]             # {TOKENS} left in the output

    @property
    def clean(self) -> bool:
        return not (self.unplaced or self.uncovered or self.unlabeled or self.open_tokens)


def check(assembly: Assembly, output: str = "", requirements: Sequence[Requirement] = ()) -> DocumentCheck:
    """Every block placed, every requirement covered or shown as a gap, every piece labeled, no token left open."""
    placed = [r.id for r in assembly.results]
    unplaced = [b.id for b in assembly.definition.items if b.id not in placed]
    uncovered = [f"{q.block} ({q.authority})" if q.authority else q.block for q in requirements if q.block not in placed]
    unlabeled = [f"{r.id}: {c.markdown[:40]!r}" for r in assembly.results for c in r.chunks
                 if c.start < 0 and not c.label and not c.words]
    open_tokens = sorted(set(re.findall(r"\{[A-Z][A-Z0-9_]+\}", output))) if output else []
    return DocumentCheck(placed, unplaced, uncovered, assembly.gaps, unlabeled, open_tokens)


def part_map(assembly: Assembly) -> dict[str, Any]:
    """The document's known structure, written beside a generated PDF: each block's id, kind, title, source, as-of day,
    standing, and (when the output is a PDF) its first and last page. A later segmentation of the PDF is checked
    against it. ``pages`` is null until a renderer that paginates fills it."""
    parts = []
    for r in assembly.results:
        if r.prose and not r.chunks:
            continue
        parts.append({"id": r.id, "kind": r.kind, "title": r.title or r.id, "source": r.source,
                      "asOf": r.as_of.isoformat() if r.as_of else (assembly.as_of.isoformat() if assembly.as_of else None),
                      "standing": "required" if r.required else "included", "authority": r.authority,
                      "gap": bool(r.gaps and r.kind in ("embedded", "form")), "fields": list(r.fields),
                      "address": r.address, "attachedPages": r.pages or None, "pages": None})
    return {"document": assembly.definition.key, "title": assembly.definition.title,
            "asOf": assembly.as_of.isoformat() if assembly.as_of else None, "parts": parts}


__all__ = ["Assembly", "Block", "BlockResult", "ComputedBlock", "ContactField", "Context", "DirectoryBlock",
           "DirectoryEntry", "DocumentCheck", "DocumentDefinition", "DocumentError", "Embedded", "EmbeddedBlock",
           "FormBlock", "GUIDE", "HtmlRenderer", "LAYOUTS", "Layout", "ManualBlock", "ManualContext", "MarkdownRenderer",
           "PLAIN", "ProseBlock", "QuoteBlock", "Renderer", "Requirement", "assemble", "check", "definition_from_template",
           "manual_context", "markdown_to_html", "number_headings", "part_map", "shift_headings"]
