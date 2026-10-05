"""A paint palette as one printable page: each schedule color as the maker's true swatch, with what goes with it.

The swatch is the catalog's hex, never a color sampled from a scan or photo of the schedule (scans shift every color
and fade). Under each distinct color the page lists the maker's coordinating colors and its closest similar ones, from
the color's own page data. Screens differ from paint: the page says to confirm a color against a physical drawdown.
"""

from __future__ import annotations

import html
from typing import Any, Callable

from jason.community.paint import FindingKind, Maker, PaintSchedule, check, distinct_codes

CSS = """body{font:14px system-ui,sans-serif;margin:2em auto;max-width:1100px;color:#222}
h1{margin:0 0 .2em}h2{margin-top:2em;border-bottom:2px solid #222}.meta{color:#555}
table{border-collapse:collapse;width:100%}th,td{border:1px solid #bbb;padding:8px;vertical-align:top;text-align:left}
th{background:#f3f3f3;width:12%}.sw{height:84px;border-radius:4px;margin-bottom:6px;border:1px solid #0003;padding:6px;box-sizing:border-box;font-weight:600}
small,.note{color:#555}.flag{color:#a33;font-weight:600}.chips{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0 14px}
.chip{width:118px;font-size:12px}.chip .sw{height:46px;margin:0}.card{break-inside:avoid;margin:0 0 22px}
.lead{display:flex;gap:16px}.lead .sw{width:200px;height:110px;flex:none}.foot{margin-top:2em;color:#555;font-size:12px}
@media print{body{margin:.5em}.card{page-break-inside:avoid}}"""


def _ink(hex_: str) -> str:
    r, g, b = (int(hex_.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    return "#111" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#fff"


def _hex(value: str) -> str:
    return "#" + value.lstrip("#").upper()


def _swatch(hex_: str, text: str = "") -> str:
    return f'<div class="sw" style="background:{_hex(hex_)};color:{_ink(hex_)}">{html.escape(text)}</div>'


def _chip(item: dict[str, Any]) -> str:
    return (f'<div class="chip">{_swatch(item["hex"])}{html.escape(item["number"].replace("SW", "SW "))}<br>'
            f'{html.escape(item["name"])}</div>')


def page(schedules: tuple[PaintSchedule, ...], catalog: Any, detail: Callable[[str], dict[str, Any]], *, similar: int = 6) -> str:
    out = [f"<!doctype html><meta charset=utf-8><title>Paint palette</title><style>{CSS}</style>"]
    for schedule in schedules:
        findings = check(schedule, catalog)
        flag = {(f.surface, f.scheme, f.code): f for f in findings}
        out.append(f"<h1>{html.escape(schedule.title)}</h1><div class=meta>{html.escape(schedule.prepared)}<br>"
                   f"Original: {html.escape(schedule.source)}</div><h2>Schedule</h2><table><tr><th></th>")
        out += [f"<th>Scheme {n}</th>" for n in schedule.scheme_numbers()]
        out.append("</tr>")
        for row in schedule.rows:
            out.append(f"<tr><th>{html.escape(row.label)}<br><small>{html.escape(row.note)}</small></th>")
            for n in schedule.scheme_numbers():
                spec = row.spec(n)
                color = catalog.color(spec.code) if spec and spec.maker is Maker.SHERWIN_WILLIAMS else None
                if spec is None:
                    out.append("<td></td>")
                elif color is None:
                    out.append(f"<td>{html.escape(spec.code)}<br>{html.escape(spec.name)}<br><small>not a Sherwin-Williams color</small></td>")
                else:
                    f = flag[(row.label, n, spec.code)]
                    drift = (f'<br><span class=flag>printed as "{html.escape(spec.name)}"</span>'
                             if f.kind is FindingKind.RENAMED else '<br><span class=flag>discontinued</span>' if f.kind is FindingKind.ARCHIVED else "")
                    out.append(f"<td>{_swatch(color.hex, color.code)}<b>{html.escape(color.name)}</b><br>"
                               f"<small>{color.hex} · LRV {color.lrv:.0f} · RGB {color.red},{color.green},{color.blue}</small>{drift}</td>")
            out.append("</tr>")
        out.append("</table><h2 style=\"page-break-before:always\">Each color, and what goes with it</h2>")
        for code in distinct_codes((schedule,)):
            color = catalog.color(code)
            if color is None:
                continue
            d = detail(code)
            where = ", ".join(f"{r.label.lower()} (scheme {s.scheme})" for r, s in schedule.specs() if s.code == code)
            out.append(f'<div class="card"><div class="lead">{_swatch(color.hex, color.code)}<div><b>{html.escape(color.name)}</b> '
                       f"{color.hex}<br><small>{html.escape(', '.join(color.families))} · LRV {color.lrv:.1f}</small><br>"
                       f"{html.escape(' '.join(d.get('description') or ()))}<br><span class=note>Used on: {html.escape(where)}</span></div></div>")
            if d.get("coordinatingColors"):
                out.append("<small>Coordinating colors</small><div class=chips>" + "".join(map(_chip, d["coordinatingColors"])) + "</div>")
            if d.get("similarColors"):
                out.append("<small>Similar colors</small><div class=chips>" + "".join(map(_chip, d["similarColors"][:similar])) + "</div>")
            out.append("</div>")
    out.append('<div class=foot>Swatches are the maker\'s catalog colors (sherwin-williams.com), not a scan. Screens and printers shift color: '
               "confirm any color against a physical drawdown before painting. The number on the schedule governs; names have changed since printing.</div>")
    return "".join(out)


DOC_FONT = "Arial"


def _cell(hex_: str, lines: list[tuple[str, str]], *, height: int = 96, width: str = "") -> str:
    """A swatch as a table cell with a background color: the one form Google Docs keeps when it imports HTML. ``lines``
    are (font size, text) pairs, in the ink that reads on the swatch."""
    ink = _ink(hex_)
    body = "".join(f'<p style="margin:0;font-size:{size};color:{ink};font-family:{DOC_FONT}">{html.escape(text)}</p>'
                   for size, text in lines)
    wide = f"width:{width};" if width else ""
    return (f'<td bgcolor="{_hex(hex_)}" style="background-color:{_hex(hex_)};height:{height}px;{wide}'
            f'padding:8px;vertical-align:top">{body}</td>')


def doc_html(schedules: tuple[PaintSchedule, ...], catalog: Any, detail: Callable[[str], dict[str, Any]], *,
             similar: int = 6) -> str:
    """The palette as HTML that becomes a Google Doc with its swatches intact: the schedule laid out as the original is
    (each surface label down the left, each scheme across), every swatch the catalog's true color and captioned with its
    surface label, then each color with its coordinating and similar colors."""
    out = ['<html><body style="font-family:Arial">']
    for schedule in schedules:
        flags = {(f.surface, f.scheme, f.code): f for f in check(schedule, catalog)}
        out.append(f"<h1>{html.escape(schedule.title)}</h1><p>{html.escape(schedule.prepared)}<br>"
                   f"Original: {html.escape(schedule.source)}</p><h2>Color schedule</h2>"
                   '<table style="border-collapse:collapse;width:100%"><tr><td></td>')
        out += [f'<td style="padding:6px"><b>Scheme {n}</b></td>' for n in schedule.scheme_numbers()]
        out.append("</tr>")
        for row in schedule.rows:
            out.append(f'<tr><td style="padding:8px;vertical-align:top"><b>{html.escape(row.label)}</b>'
                       f'<br><span style="color:#666;font-size:9pt">{html.escape(row.note)}</span></td>')
            for n in schedule.scheme_numbers():
                spec = row.spec(n)
                color = catalog.color(spec.code) if spec and spec.maker is Maker.SHERWIN_WILLIAMS else None
                if spec is None:
                    out.append("<td></td>")
                elif color is None:
                    out.append(f'<td style="padding:8px;border:1px solid #bbb"><p style="margin:0">{html.escape(spec.code)}</p>'
                               f'<p style="margin:0">{html.escape(spec.name)}</p>'
                               '<p style="margin:0;color:#666;font-size:9pt">not paint</p></td>')
                else:
                    f = flags[(row.label, n, spec.code)]
                    drift = f"printed: {spec.name}" if f.kind is FindingKind.RENAMED else (
                        "discontinued" if f.kind is FindingKind.ARCHIVED else "")
                    lines = [("8pt", row.label), ("14pt", color.code), ("11pt", color.name),
                             ("8pt", f"{color.hex} · LRV {color.lrv:.0f}")]
                    if drift:
                        lines.append(("8pt", drift))
                    out.append(_cell(color.hex, lines, height=110))
            out.append("</tr>")
        out.append("</table><h2 style=\"page-break-before:always\">Each color, and what goes with it</h2>")
        for code in distinct_codes((schedule,)):
            color = catalog.color(code)
            if color is None:
                continue
            d = detail(code)
            where = ", ".join(f"{r.label.title()} (scheme {s.scheme})" for r, s in schedule.specs() if s.code == code)
            about = html.escape(" ".join(d.get("description") or ()))
            out.append(f"<h3>{html.escape(color.name)}, {html.escape(color.code)}</h3>"
                       '<table style="border-collapse:collapse;width:100%"><tr>'
                       + _cell(color.hex, [("8pt", where), ("14pt", color.code), ("9pt", color.hex)], height=80, width="30%")
                       + f'<td style="padding:8px;vertical-align:top"><p style="margin:0">{about}</p>'
                       f'<p style="margin:6px 0 0;color:#666;font-size:9pt">{html.escape(", ".join(color.families))} · '
                       f"LRV {color.lrv:.1f} · RGB {color.red},{color.green},{color.blue}</p></td></tr></table>")
            for title, items in (("Coordinating colors", d.get("coordinatingColors") or []),
                                 ("Similar colors", (d.get("similarColors") or [])[:similar])):
                if items:
                    chips = "".join(_cell(i["hex"], [("8pt", i["number"].replace("SW", "SW ")), ("8pt", i["name"])],
                                          height=56, width="110px") for i in items)
                    out.append(f'<p style="margin:8px 0 2px;color:#666;font-size:9pt">{title}</p>'
                               f'<table style="border-collapse:collapse"><tr>{chips}</tr></table>')
    out.append('<p style="color:#666;font-size:9pt">Swatches are the maker\'s catalog colors (sherwin-williams.com), not a scan. '
               "Screens and printers shift color: confirm any color against a physical drawdown before painting. The number "
               "on the schedule governs; names have changed since printing.</p></body></html>")
    return "".join(out)
