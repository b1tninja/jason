"""How a broadcast looks, judged by the local vision model from screenshots of PayHOA's own rendering.

``jason broadcast FILE --preview --critique`` renders the body through PayHOA (``render_email_sample``, for the signed-in
admin; nothing is sent), lays it out as a mail client would (a white page, a 640 px column, system fonts), and takes two
screenshots with the installed Chrome or Edge in headless mode: desktop (640 px) and phone (390 px). Each is cropped to
its content. The local vision model (``qwen3.6:27b``, no thinking, temperature 0, under the GPU lock after the preflight)
sees both, with the letterhead's logo as the brand to match, and answers in ``CRITIQUE_SCHEMA``: what works, and
concrete changes the template's HTML can carry (headings, bold, lists, tables, the centered logo, rules). Whether the
words are right is ``jason review``'s question, not this one's. Nothing leaves the machine.
"""

from __future__ import annotations

import base64
import html
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

WIDTHS = {"desktop": 640, "phone": 390}
BROWSERS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)

CRITIQUE_PROMPT = """You are reviewing an email notice a homeowners association's volunteer board will send to owners.
Look at it twice: as an email designer, and as an owner reading it quickly on a phone.

The images are: 1) the email at desktop width, 2) the same email at phone width{logo_note}.

Judge only how it looks and reads, not whether its facts or law are right:
- first impression and hierarchy: is the purpose clear in the first lines, and do headings and bold lead the eye;
- readability: paragraph length, scannability, whether lists or a small table would read better;
- the phone layout: wrapping, tables that overflow, tap targets;
- branding: consistency with the association's letterhead (a centered logo over the name);
- accessibility: contrast, link text, image alt text;
- anything that looks broken: an image that did not load, odd spacing, placeholders or [FIELDS] left unfilled.

Suggest concrete changes the email can carry: headings, bold, bulleted or numbered lists, a simple table, a centered
logo, a horizontal rule, shorter paragraphs. Do not suggest colors, fonts, or layout features beyond those. Keep each
suggestion to one change. Answer as JSON matching the schema."""

CRITIQUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["summary", "strengths", "suggestions"],
    "properties": {
        "summary": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "suggestions": {"type": "array", "items": {"type": "object", "required": ["area", "issue", "change", "priority"], "properties": {
            "area": {"type": "string", "enum": ["hierarchy", "readability", "phone", "branding", "accessibility", "broken"]},
            "issue": {"type": "string"},
            "change": {"type": "string"},
            "priority": {"type": "string", "enum": ["high", "medium", "low"]}}}},
    },
}


def mail_page(subject: str, rendered: str, width: int = 640) -> str:
    """The rendered body as a mail client shows it: subject on top, a white column ``width`` px wide, system fonts.
    The column, not the browser window, sets the width: headless Chrome will not make a window as narrow as a phone."""
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{margin:0;background:#fff;color:#222;font:15px/1.5 Arial,Helvetica,sans-serif}}
.mail{{width:{width - 32}px;margin:0;padding:16px}} .subject{{font-size:18px;font-weight:bold;border-bottom:1px solid #ddd;padding-bottom:8px;margin-bottom:12px}}
img{{max-width:100%;height:auto}} table{{max-width:100%}}</style></head>
<body><div class="mail"><div class="subject">{html.escape(subject)}</div>{rendered}</div></body></html>"""


BODY_SLOT = "{BODY}"
WRAPPER_FILE = "brand/payhoa-wrapper.html"
_BODY_CELL = re.compile(r'(<td\s+valign="middle"\s+align="left"\s+style="line-height:\s*1\.4;?"\s*>)(.*?)'
                        r'(</td>\s*</tr>\s*</table>\s*</td>\s*<td\s+width="20")', re.S)
_PIXEL = re.compile(r'<img[^>]+(?:/wf/open|width="1" height="1")[^>]*>', re.I)


def payhoa_wrapper(email_html: str) -> str:
    """PayHOA's email layout taken from one email it sent: the association logo centered over a white 520 px card on a
    light grey page, with ``{BODY}`` where the message goes and the open-tracking pixel removed (a local preview must
    never count as an open). Raises ValueError when the email is not in PayHOA's layout."""
    if not _BODY_CELL.search(email_html):
        raise ValueError("not a PayHOA email: no message cell")
    return _PIXEL.sub("", _BODY_CELL.sub(lambda m: m.group(1) + BODY_SLOT + m.group(3), email_html, count=1))


def wrapped_page(wrapper: str, subject: str, rendered: str) -> str:
    """The rendered body inside PayHOA's own layout, under the subject line."""
    page = wrapper.replace(BODY_SLOT, rendered, 1)
    head = (f'<div style="font:bold 18px Arial,sans-serif;color:#222;padding:12px 16px;border-bottom:1px solid #ddd">'
            f"{html.escape(subject)}</div>")
    return re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + head, page, count=1) if "<body" in page else head + page


def browser() -> str:
    for path in BROWSERS:
        if Path(path).is_file():
            return path
    found = shutil.which("chrome") or shutil.which("msedge") or shutil.which("chromium")
    if not found:
        raise RuntimeError("no Chrome or Edge to take the screenshots with")
    return found


def crop(png: Path, margin: int = 16) -> Path:
    """Trim the white below the content (a headless window is taller than the page)."""
    from PIL import Image, ImageChops

    image = Image.open(png).convert("RGB")
    box = ImageChops.difference(image, Image.new("RGB", image.size, (255, 255, 255))).getbbox()
    if box:
        image.crop((0, 0, min(image.width, box[2] + margin), min(image.height, box[3] + margin))).save(png)
    return png


def screenshot(page: Path, out: Path, width: int, *, height: int = 3000, run: Callable[..., Any] = subprocess.run) -> Path:
    """One headless screenshot of a local page at ``width`` pixels, cropped to its content."""
    out = out.resolve()                              # Chrome writes a relative path into its own working directory
    with tempfile.TemporaryDirectory() as profile:
        run([browser(), "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={profile}",
             f"--window-size={width},{height}", f"--screenshot={out}", page.resolve().as_uri()],
            check=True, capture_output=True, timeout=120)
    if not out.is_file():
        raise RuntimeError(f"the browser wrote no screenshot for {page.name}")
    return crop(out)


def critique(images: list[Path], *, has_logo: bool, model: str = "",
             post: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None, timeout: int = 900) -> dict[str, Any]:
    """Ask the local vision model about the screenshots (and the logo, last, when given)."""
    from jason.community.ollama_extractor import DEFAULT_CONTEXT, DEFAULT_MODEL, OLLAMA_URL, _post

    name = model or DEFAULT_MODEL
    if post is None:
        from jason.community.retrieval import EMBED_MODEL
        from jason.local_ai import preflight, unload

        unload(EMBED_MODEL)
        preflight(name)
    prompt = CRITIQUE_PROMPT.format(logo_note=", 3) the association's letterhead logo, for reference" if has_logo else "")
    payload = {"model": name, "stream": False, "think": False, "format": CRITIQUE_SCHEMA,
               "options": {"temperature": 0, "num_ctx": DEFAULT_CONTEXT},
               "messages": [{"role": "user", "content": prompt,
                             "images": [base64.b64encode(p.read_bytes()).decode("ascii") for p in images]}]}
    answer = (post or (lambda url, body: _post(url, body, timeout)))(f"{OLLAMA_URL}/api/chat", payload)
    content = (answer.get("message") or {}).get("content", "") if isinstance(answer, dict) else ""
    try:
        data = json.loads(content)
    except ValueError:
        data = {}
    return data if isinstance(data, dict) else {}


def critique_lines(data: dict[str, Any]) -> list[str]:
    lines = [f"# How it looks", "", str(data.get("summary") or ""), ""]
    if data.get("strengths"):
        lines += ["## What works", ""] + [f"- {s}" for s in data["strengths"]] + [""]
    order = {"high": 0, "medium": 1, "low": 2}
    suggestions = sorted(data.get("suggestions") or [], key=lambda s: order.get(str(s.get("priority")), 3))
    if suggestions:
        lines += ["## Suggestions", "", "| Priority | Area | Issue | Change |", "|---|---|---|---|"]
        lines += [f"| {s.get('priority')} | {s.get('area')} | {s.get('issue')} | {s.get('change')} |" for s in suggestions]
    return lines


def pages(subject: str, rendered: str, base: Path, *, wrapper: str = "") -> dict[str, Path]:
    """The email as members see it, written beside ``base``: on desktop inside PayHOA's own layout when ``wrapper`` is
    known (``payhoa_wrapper``), else in a plain column; on a phone in a 390 px column."""
    out: dict[str, Path] = {}
    for name, width in WIDTHS.items():
        page = base.with_name(f"{base.stem}.{name}.html")
        text = wrapped_page(wrapper, subject, rendered) if wrapper and name == "desktop" else mail_page(subject, rendered, width)
        page.write_text(text, encoding="utf-8")
        out[name] = page
    return out


def review(subject: str, rendered: str, base: Path, *, logo: Path | None = None, model: str = "",
           wrapper: str = "") -> tuple[Path, dict[str, Any]]:
    """Screenshots of the rendered email and the model's critique, written beside ``base`` (FILE.desktop.png,
    FILE.phone.png, FILE.critique.md, FILE.critique.json)."""
    shots = []
    for name, page in pages(subject, rendered, base, wrapper=wrapper).items():
        width = WIDTHS[name]
        shots.append(screenshot(page, base.with_name(f"{base.stem}.{name}.png"), max(width, 800)))
    images = shots + ([logo] if logo and logo.is_file() else [])
    data = critique(images, has_logo=len(images) > len(shots), model=model)
    out = base.with_name(base.stem + ".critique.md")
    out.write_text("\n".join(critique_lines(data)) + "\n", encoding="utf-8")
    base.with_name(base.stem + ".critique.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return out, data
