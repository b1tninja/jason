"""One form definition (``jason.community.forms.FormTemplate``), rendered for paper and for PayHOA's form builder.

The owner information form must be the same on paper and online, so neither is written by hand. ``paper_blocks`` lays
the paper form out once (the title, the description, each question numbered with its help, its boxes or lines, then the
signature line), and two renderers write it:

- ``paper_markdown``: Markdown for ``letters.markdown_doc``, a Doc on the Letterhead;
- ``paper_html``: HTML for a local PDF (``tasks.forms.form_pdf``), printed without a Doc.

Both print the same marks ``fillable.make_fillable`` reads: a bold numbered question, a box (☐) for each option, a line
of underscores to write on, and the signature label, so either one becomes a fillable PDF. ``{TOKENS}`` in the preamble
and closing carry what changes each year (the return date, the online form's address).

``payhoa_sheet`` writes the build sheet a person follows in PayHOA's form builder, question by question. PayHOA's
builder was seen with short text, paragraph, and file questions; a choice question is listed with its options, to be
built as a choice if the builder offers one and as a short answer naming the options if it does not.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any

from jason.community.forms import FormTemplate, QuestionKind, ReadAs

BOX = "☐"                                   # ☐, a box to check on paper
LINE = "_" * 60
# An address's second line, its parts labelled: each blank is a field of its own (fillable: ``#city``, ``#state``,
# ``#zip``), so the answer comes back in parts and nothing has to be parsed (October 1, 2026).
ADDRESS_ROW = "City " + "_" * 30 + "   State " + "_" * 8 + "   ZIP " + "_" * 12

PAYHOA_TYPE = {
    QuestionKind.SHORT: "Short text (input)",
    QuestionKind.PARAGRAPH: "Paragraph (textarea)",
    QuestionKind.CHOICE: "Choose one",
    QuestionKind.CHECKBOX: "Choose any",
    QuestionKind.DATE: "Short text (input): a date",
    QuestionKind.EMAIL: "Short text (input): an email address",
    QuestionKind.PHONE: "Short text (input): a phone number",
}
HINT = {QuestionKind.DATE: "Month/day/year.", QuestionKind.EMAIL: "", QuestionKind.PHONE: ""}


@dataclass(frozen=True)
class Block:
    """One piece of the paper form: ``kind`` is title, text (Markdown-light), question, help, choices, lines, or
    signature."""

    kind: str
    text: str = ""
    count: int = 0
    optional: bool = False


def fill(text: str, values: dict[str, str] | None) -> str:
    """``{TOKEN}`` filled from ``values``; with no values the tokens stay (a Doc fills them later)."""
    if not values:
        return text
    return re.sub(r"\{([A-Z][A-Z0-9_]*)\}", lambda m: values.get(m.group(1)) or m.group(0), text)


def help_line(q: Any) -> str:
    """A question's help, its kind's hint, and the law that asks for it."""
    text = " ".join(t for t in (q.help, HINT.get(q.kind, "")) if t)
    if q.authority:
        text = f"{text} ({q.authority})" if text else f"({q.authority})"
    return text


def paper_blocks(form: FormTemplate, *, preamble: list[str] = (), closing: list[str] = (),
                 values: dict[str, str] | None = None) -> list[Block]:
    blocks = [Block("title", form.title), Block("text", form.description),
              *(Block("text", fill(t, values)) for t in form.preamble), *(Block("text", t) for t in preamble if t)]
    for n, q in enumerate(form.questions, 1):
        if q.section:
            blocks.append(Block("section", q.section))
        blocks.append(Block("question", f"{n}. {q.title.replace(' (optional)', '')}", optional=not q.required))
        help_text = help_line(q)
        if help_text:
            blocks.append(Block("help", help_text))
        if q.kind in (QuestionKind.CHOICE, QuestionKind.CHECKBOX):
            pick = "Check one." if q.kind is QuestionKind.CHOICE else "Check all that apply."
            blocks.append(Block("choices", pick + "\t" + "\t".join(q.options)))
        else:
            if q.same_as:                     # the usual answer as one box; the lines are for anything else
                blocks.append(Block("choices", "\t" + q.same_as))
            blocks.append(Block("address") if q.in_parts else Block("lines", count=q.paper_lines))
    if form.attestation:
        blocks.append(Block("text", f"**Certification.** {form.attestation}"))
    if form.signature:
        blocks.append(Block("signature", form.signature, optional=not form.dated))
    blocks += [Block("text", t) for t in closing if t]
    return blocks


def paper_markdown(form: FormTemplate, *, preamble: list[str] = (), closing: list[str] = ()) -> list[str]:
    """The paper form as Markdown lines. ``preamble`` and ``closing`` are Markdown lines with the year's tokens."""
    lines: list[str] = []
    open_group = False

    def close() -> None:
        nonlocal open_group
        if open_group:
            lines.insert(len(lines) - (1 if lines and lines[-1] == "" else 0), r"\endkeep")
            open_group = False

    for b in paper_blocks(form, preamble=preamble, closing=closing):
        certifies = b.kind == "text" and b.text.startswith("**Certification.**")
        if b.kind in ("title", "text", "section", "question") or (b.kind == "signature" and not open_group):
            close()                           # a question stays on one page with its help and lines (``\keep``)
        if certifies or (b.kind == "signature" and not open_group):
            lines.append(r"\keep")            # the certification with the signature line under it
            open_group = True
        if b.kind == "title":
            lines += [f"# {b.text}", ""]
        elif b.kind == "text":
            lines += [b.text, ""]
        elif b.kind == "section":
            lines += [f"### {b.text}", ""]
        elif b.kind == "question":
            lines.append(r"\keep")
            open_group = True
            lines.append(f"**{b.text}**" + (" _(optional)_" if b.optional else ""))
        elif b.kind == "help":
            lines.append(f"_{b.text}_")
        elif b.kind == "choices":
            pick, *options = b.text.split("\t")
            lines += [f"{pick}   " + "     ".join(f"{BOX} {o}" for o in options), ""]
        elif b.kind == "lines":
            lines += [LINE] * b.count + [""]
        elif b.kind == "address":
            lines += [LINE, ADDRESS_ROW, ""]
        elif b.kind == "signature":
            date = "" if b.optional else "   **Date**  " + "_" * 14
            lines += [f"**{b.text}**  " + "_" * 34 + date, ""]
            close()
    close()
    return lines


def _inline(text: str) -> str:
    """Markdown-light to HTML: **bold** and _italic_, everything else escaped."""
    out = html.escape(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    return re.sub(r"(?<![A-Za-z0-9])_(.+?)_(?![A-Za-z0-9])", r"<em>\1</em>", out)


PAPER_STYLE = """<style>.form p{margin:0 0 5pt} .form .q{margin:9pt 0 2pt} .form .q em{font-weight:normal} .form .help{font-style:italic;
margin:0 0 3pt} .form .choices span{margin-right:14pt;white-space:nowrap} .form .line{margin:6pt 0 0;letter-spacing:0}
.form .sign{margin-top:16pt} .form .section{margin:14pt 0 2pt;padding-bottom:2pt;border-bottom:1px solid #999;
font-size:10pt;letter-spacing:.5px;text-transform:uppercase;color:#333;break-after:avoid;page-break-after:avoid}
.form .keep{break-inside:avoid;page-break-inside:avoid}</style>"""


def paper_html(form: FormTemplate, *, preamble: list[str] = (), closing: list[str] = (),
               values: dict[str, str] | None = None) -> str:
    """The paper form as HTML (the body under a page's title; the title block is the page's own heading). Its
    citations, web addresses, and email addresses are links (``links.linkify``): clickable in the PDF, the same in print."""
    from jason.community.links import linkify

    # the writing lines as the form's style draws them: room above each to write in, the line itself pale
    above, ink = max(0.0, form.style.write_height - 13.0), round(255 * form.style.line_gray)
    parts = [PAPER_STYLE, f"<style>.form .line{{margin:{above:g}pt 0 0;color:rgb({ink},{ink},{ink})}} "
                          f".form .blank{{color:rgb({ink},{ink},{ink})}} .form .sign{{margin-top:{max(16.0, above):g}pt}}"
                          "</style>", "<div class='form'>"]
    group = False                       # a question, or the certification with the signature, never splits a page

    def close() -> None:
        nonlocal group
        if group:
            parts.append("</div>")
            group = False

    for b in paper_blocks(form, preamble=preamble, closing=closing, values=values):
        certifies = b.kind == "text" and b.text.startswith("**Certification.**")
        if b.kind in ("text", "section", "question") or (b.kind == "signature" and not group):
            close()
        if b.kind == "question" or certifies or (b.kind == "signature" and not group):
            parts.append("<div class='keep'>")
            group = True
        if b.kind == "text":
            parts.append(f"<p>{linkify(_inline(b.text))}</p>")
        elif b.kind == "section":
            parts.append(f"<p class='section'>{html.escape(b.text)}</p>")
        elif b.kind == "question":
            # bold in the markup itself, not only by style: the fillable reader finds a question by its bold number
            parts.append(f"<p class='q'><strong>{html.escape(b.text)}</strong>" + (" <em>(optional)</em>" if b.optional
                                                                                    else "") + "</p>")
        elif b.kind == "help":
            parts.append(f"<p class='help'>{linkify(_inline(b.text))}</p>")
        elif b.kind == "choices":
            pick, *options = b.text.split("\t")
            parts.append(f"<p class='choices'>{html.escape(pick)} &nbsp; "
                         + " ".join(f"<span>{BOX} {html.escape(o)}</span>" for o in options) + "</p>")
        elif b.kind == "lines":
            parts += [f"<p class='line'>{LINE}</p>"] * b.count
        elif b.kind == "address":
            parts += [f"<p class='line'>{LINE}</p>",
                      "<p class='line'>" + re.sub(r"_{8,}", lambda m: f"<span class='blank'>{m.group(0)}</span>",
                                                  html.escape(ADDRESS_ROW)) + "</p>"]
        elif b.kind == "signature":
            date = "" if b.optional else f" &nbsp; <strong>Date</strong> <span class='blank'>{'_' * 14}</span>"
            parts.append(f"<p class='sign'><strong>{html.escape(b.text)}</strong> <span class='blank'>{'_' * 34}</span>"
                         f"{date}</p>")
            close()
    close()
    parts.append("</div>")
    return "\n".join(parts)


@dataclass(frozen=True)
class PayhoaQuestion:
    """One question of the definition as PayHOA's form builder takes it, with the field it answers. A "choose any"
    question becomes one ``checkbox`` a option (``<field>.<option>``), which is easier on a phone than a multi-select
    list; "choose one" becomes a single ``select`` (the builder has no radio); a date, email, or phone is short text
    with a hint."""

    field: str
    label: str
    kind: str                      # input, textarea, checkbox, select
    description: str = ""
    required: bool = False
    options: tuple[str, ...] = ()


ATTESTATION = "attestation"          # the field a PayHOA form's certification box answers


def payhoa_questions(form: FormTemplate, *, skip: set[str] | frozenset[str] = frozenset()) -> list[PayhoaQuestion]:
    """The definition in the builder's terms: each section a divider (``hr``) labelled with its heading, each question
    numbered in order with its help and the law that asks for it, and the certification a required box last. A field
    in ``skip`` is left out (a form that names its unit does not ask for the unit's address), and the numbers count
    only the questions shown."""
    from jason.community.forms import option_key

    out: list[PayhoaQuestion] = []
    shown = [q for q in form.questions if q.field not in skip]
    for n, q in enumerate(shown, 1):
        if q.section:
            out.append(PayhoaQuestion("", q.section, "hr"))
        help_text = help_line(q)
        title = f"{n}. {q.title}"
        if q.kind is QuestionKind.CHECKBOX:
            for i, option in enumerate(q.options):
                out.append(PayhoaQuestion(f"{q.field}.{option_key(option)}", f"{title}: {option}", "checkbox",
                                          help_text if i == 0 else ""))
        elif q.kind is QuestionKind.CHOICE:
            out.append(PayhoaQuestion(q.field, title, "select", help_text, q.required, q.options))
        elif q.kind is QuestionKind.PARAGRAPH:
            out.append(PayhoaQuestion(q.field, title, "textarea", help_text, q.required))
        elif q.same_as:                       # the usual answer as one box, then the line for anything else
            out.append(PayhoaQuestion(q.same_as_field, f"{title}: {q.same_as}", "checkbox", help_text))
            out.append(PayhoaQuestion(q.field, f"{title}: or another address", "input",
                                      "Street (with apt, suite, or PMB), city, state, and ZIP." if q.reads_as is ReadAs.ADDRESS else "",
                                      q.required))
        else:
            # online an address is one box: say what goes in it (on paper its parts are labelled instead)
            online = " ".join(x for x in ("Street (with apt, suite, or PMB), city, state, and ZIP." if q.reads_as is ReadAs.ADDRESS else "",
                                          help_text) if x)
            out.append(PayhoaQuestion(q.field, title, "input", online, q.required))
    if form.attestation:
        out.append(PayhoaQuestion("", "Certification", "hr"))
        out.append(PayhoaQuestion(ATTESTATION, form.attestation, "checkbox", "Required to submit.", True))
    return out


def payhoa_description(form: FormTemplate, values: dict[str, str] | None = None) -> str:
    """The form's description as the builder's HTML: its purpose, then the preamble's paragraphs with the year's
    values filled in (the return date)."""
    paragraphs = [form.description, *(fill(t, values) for t in form.preamble)]
    return "".join(f"<p>{_inline(t)}</p>" for t in paragraphs if t)


def payhoa_sheet(form: FormTemplate) -> list[str]:
    """The build sheet for PayHOA's form builder: one row a question, in order, with its type, whether it is required,
    its options, and its help text."""
    lines = [f"# PayHOA form: {form.title}", "", f"Form description (paste as the form's description): {form.description}",
             "", f"Authority: {form.authority}", "", "| # | Question | Type | Required | Options | Help text |",
             "|---|---|---|---|---|---|"]
    for n, q in enumerate(form.questions, 1):
        lines.append(f"| {n} | {q.title} | {PAYHOA_TYPE[q.kind]} | {'yes' if q.required else 'no'} | "
                     f"{'; '.join(q.options)} | {q.help} |")
    lines += ["", "If the builder has no choice question, use a short-text question and list the options in its help text.",
              "Send the form to every owner by email, and mail the paper form to owners without an email on file."]
    return lines


__all__ = ["ATTESTATION", "BOX", "Block", "PayhoaQuestion", "fill", "help_line", "paper_blocks", "paper_html", "paper_markdown", "payhoa_description",
           "payhoa_questions", "payhoa_sheet"]
