"""One offline page for exploring the outlines and the references among them: ``data/reports/references.html``.

``write_viewer`` embeds the outlines (each section's number, title, place in the tree, and the start of its text) and the
resolved references as JSON in a single HTML file with its own script and styles. A board member picks a document, opens
its sections, and sees what each section cites (with the relation and the check's status) and what cites it; a graph
shows which documents cite which and the codes they cite; the findings link to the sections they concern; a search box
finds sections and targets ("4926", "7.2").

The page carries association records, so it loads nothing from the network: no CDN, no fonts, no images, and a content
security policy that refuses any fetch. Section text is trimmed (``TEXT_LIMIT``) rather than embedding each document
twice; the whole text stays in ``data/outlines/<key>.json``. Reading only, like the rest of ``jason outlines``.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from jason.community.outlines import DocumentOutline, Section

TEXT_LIMIT = 1500              # characters of a section's text the page carries
QUOTE_LIMIT = 400              # characters of a reference's sentence
KIND_ORDER = ["declaration", "amendment", "bylaws", "annexation", "operating_rules", "election_rules", "policy", "resolution"]
_CITES = re.compile(r"^(\S+)(?: \(in its section (.+?)\))? cites (\S+?)[,;]")
_PRINTED = re.compile(r"^resolution number (\S+) is printed by")


def _law_code(target: str) -> str:
    """The node a statute joins in the graph: its code ("CIV 4926(a)" is CIV), or CCR for a regulation."""
    return "CCR" if " CCR " in f" {target} " else target.split()[0]


def _parents(sections: list[Section]) -> list[int]:
    """Each section's parent as an index: the last earlier section that is shallower, or -1 at the top."""
    stack: list[int] = []
    out: list[int] = []
    for i, s in enumerate(sections):
        while stack and sections[stack[-1]].depth >= s.depth:
            stack.pop()
        out.append(stack[-1] if stack else -1)
        stack.append(i)
    return out


def _excerpt(text: str) -> tuple[str, bool]:
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text.strip())
    return (text[:TEXT_LIMIT].rstrip() + " \u2026", True) if len(text) > TEXT_LIMIT else (text, False)


def _target_doc(row: dict[str, Any]) -> str:
    if row["kind"] == "section":
        return row["target"].split("#")[0]
    return row["target"] if row["kind"] == "document" else ""


def _graph(outlines: list[DocumentOutline], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Nodes: every document and every code cited. Edges: references from a document to another document (a section,
    the document by name, or a resolution by number) and to a code, weighted by count. The same edges as the Mermaid
    diagram in references.md, except that every code edge is kept."""
    keys = [o.key for o in outlines]
    edges: Counter = Counter()
    laws: Counter = Counter()
    for r in rows:
        target = _target_doc(r)
        if target in keys and target != r["source"]:
            edges[(r["source"], target)] += 1
        elif r["kind"] == "resolution":
            for k in r.get("claimants", []):
                edges[(r["source"], k)] += 1
        elif r["kind"] == "statute":
            laws[(r["source"], _law_code(r["target"]))] += 1
    codes = sorted({c for _, c in laws})
    nodes = [{"id": k, "law": False} for k in keys] + [{"id": f"law:{c}", "law": True, "code": c} for c in codes]
    index = {n["id"]: i for i, n in enumerate(nodes)}
    out = [{"a": index[a], "b": index[b], "n": n, "law": False} for (a, b), n in sorted(edges.items()) if a in index and b in index]
    out += [{"a": index[a], "b": index[f"law:{c}"], "n": n, "law": True} for (a, c), n in sorted(laws.items()) if a in index]
    return {"nodes": nodes, "edges": out}


def _finding_links(text: str, rows: list[dict[str, Any]], outlines: list[DocumentOutline]) -> dict[str, Any]:
    """A finding with the sections it concerns: the citing section and the cited one (or its nearest parent), or the
    resolutions that print a number. A finding about many statutes filters the search by their status instead."""
    titles = {o.key: o.title for o in outlines}
    links: list[dict[str, str]] = []
    query = ""
    if m := _CITES.match(text):
        source, section, target = m.group(1), m.group(2) or "", m.group(3)
        row = next((r for r in rows if r["source"] == source and r["target"] == target), None)
        section = section or (row or {}).get("source_section", "")
        links.append({"d": source, "s": section, "label": f"{titles.get(source, source)} {section}".strip()})
        key, _, number = target.partition("#")
        cited = (row or {}).get("nearest") or number
        if key in titles:
            links.append({"d": key, "s": cited, "label": f"{titles[key]} {cited}".strip()})
    elif m := _PRINTED.match(text):
        links += [{"d": o.key, "s": "", "label": o.title} for o in outlines if m.group(1) in o.numbers]
    elif text.startswith("statutes cited by their pre-2014"):
        query = "prior numbering"
    elif text.startswith("resolutions cited that no resolution"):
        query = "no resolution prints it"
    return {"text": text, "links": links, "q": query}


def viewer_data(outlines: list[DocumentOutline], rows: list[dict[str, Any]], found: list[str]) -> dict[str, Any]:
    """What the page embeds. Short keys keep the file small; the page's script names them."""
    out_count = Counter(r["source"] for r in rows)
    in_count: Counter = Counter()
    for r in rows:
        target = _target_doc(r)
        if target and target != r["source"]:
            in_count[target] += 1
        for k in r.get("claimants", []) if r["kind"] == "resolution" else []:
            in_count[k] += 1
    docs = []
    for o in outlines:
        parents = _parents(o.sections)
        sections = []
        for i, s in enumerate(o.sections):
            excerpt, trimmed = _excerpt(o.text_of(s))
            sections.append([s.number, s.title[:240], s.depth, parents[i], excerpt, int(trimmed)])
        head, trimmed = _excerpt(o.text[: o.sections[0].start] if o.sections else o.text)
        docs.append({"k": o.key, "t": o.title, "kind": o.kind, "amends": o.amends, "numbers": o.numbers, "library": o.library,
                     "head": head, "headTrimmed": int(trimmed), "s": sections, "out": out_count[o.key], "in": in_count[o.key]})
    refs = []
    for r in rows:
        ref = {"s": r["source"], "ss": r.get("source_section", ""), "k": r["kind"], "t": r["target"], "r": r.get("relation", ""),
               "st": r.get("status", ""), "q": (r.get("quote") or "")[:QUOTE_LIMIT]}
        if r.get("nearest"):
            ref["n"] = r["nearest"]
        if r.get("claimants"):
            ref["c"] = r["claimants"]
        refs.append(ref)
    return {"generated": date.today().isoformat(), "kinds": KIND_ORDER, "docs": docs, "refs": refs,
            "findings": [_finding_links(f, rows, outlines) for f in found], "graph": _graph(outlines, rows)}


def _embed(data: dict[str, Any]) -> str:
    """JSON safe inside a script element: no "<" (so no "</script>" or "<!--"), ">" or "&" survives as itself."""
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def write_viewer(data_dir: Path, outlines: list[DocumentOutline], rows: list[dict[str, Any]], found: list[str]) -> Path:
    """Write ``data/reports/references.html`` and return its path."""
    path = Path(data_dir) / "reports" / "references.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PAGE.replace("__DATA__", _embed(viewer_data(outlines, rows, found))), encoding="utf-8")
    return path


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:">
<meta name="referrer" content="no-referrer">
<title>Document References</title>
<style>
:root {
  color-scheme: light dark;
  --bg: #f7f6f2; --panel: #ffffff; --text: #1f1f1c; --muted: #66655f; --line: #dfddd5;
  --accent: #2c5a86; --accent-soft: #e4edf6; --law: #4f7a2e; --law-soft: #e7f0de;
  --warn: #a3382b; --warn-soft: #f7e3df; --note: #85600f; --note-soft: #f5ecd6; --sel: #fff3c4;
  --mono: ui-monospace, "Cascadia Mono", Consolas, Menlo, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #15161a; --panel: #1d1f24; --text: #e8e6e0; --muted: #a09e96; --line: #34373e;
    --accent: #86b6e6; --accent-soft: #1e2d3c; --law: #a3cc7e; --law-soft: #22301a;
    --warn: #f0968a; --warn-soft: #3b221e; --note: #e3bd6f; --note-soft: #362b16; --sel: #3a3420;
  }
}
* { box-sizing: border-box; }
html, body { margin: 0; }
body { background: var(--bg); color: var(--text); font: 15px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
header { position: sticky; top: 0; z-index: 5; background: var(--bg); border-bottom: 1px solid var(--line); padding: 10px 16px; }
.bar { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; max-width: 1500px; margin: 0 auto; }
h1 { font-size: 1.15rem; margin: 0; }
.sub { color: var(--muted); font-size: .85rem; }
nav.tabs { display: flex; gap: 4px; }
nav.tabs button { border: 1px solid var(--line); background: var(--panel); color: var(--text); padding: 5px 12px; border-radius: 6px; cursor: pointer; font: inherit; }
nav.tabs button[aria-selected="true"] { background: var(--accent); border-color: var(--accent); color: var(--bg); }
input[type=search] { flex: 1 1 220px; min-width: 0; max-width: 420px; padding: 6px 10px; border: 1px solid var(--line); border-radius: 6px; background: var(--panel); color: var(--text); font: inherit; }
main { max-width: 1500px; margin: 0 auto; padding: 12px 16px 40px; }
.layout { display: grid; grid-template-columns: 260px minmax(260px, 1fr) minmax(300px, 1.3fr); gap: 12px; align-items: start; }
.pane { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 10px; min-width: 0; }
.scroll { max-height: calc(100vh - 110px); overflow: auto; position: sticky; top: 70px; }
.doclist h3 { font-size: .75rem; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); margin: 10px 4px 4px; }
.doclist button { display: block; width: 100%; text-align: left; border: 0; background: none; color: var(--text); padding: 5px 6px; border-radius: 5px; cursor: pointer; font: inherit; }
.doclist button:hover { background: var(--accent-soft); }
.doclist button.on { background: var(--accent-soft); font-weight: 600; }
.doclist .counts { display: block; color: var(--muted); font-size: .78rem; font-weight: 400; }
.tree { font-size: .9rem; }
.tree details > summary { list-style: none; cursor: pointer; display: flex; align-items: baseline; gap: 2px; }
.tree details > summary::-webkit-details-marker { display: none; }
.tree details > summary::before { content: "\25B8"; width: 1em; flex: none; color: var(--muted); text-align: center; }
.tree details[open] > summary::before { content: "\25BE"; }
.tree .leaf { display: flex; align-items: baseline; gap: 2px; }
.tree .leaf::before { content: ""; width: 1em; flex: none; }
.tree .kids { margin-left: 1em; border-left: 1px solid var(--line); padding-left: 2px; }
.sec { border: 0; background: none; color: var(--text); text-align: left; padding: 2px 4px; border-radius: 4px; cursor: pointer; font: inherit; flex: 1; min-width: 0; }
.sec:hover { background: var(--accent-soft); }
.sec.on { background: var(--sel); }
.num { font-family: var(--mono); font-size: .85em; color: var(--accent); margin-right: 4px; }
.tag { display: inline-block; font-size: .72rem; padding: 0 5px; border-radius: 9px; margin-left: 4px; background: var(--accent-soft); color: var(--accent); white-space: nowrap; }
.tag.warn { background: var(--warn-soft); color: var(--warn); }
.tag.note { background: var(--note-soft); color: var(--note); }
.tag.ok { background: var(--law-soft); color: var(--law); }
.detail h2 { font-size: 1.1rem; margin: 2px 0 4px; }
.detail h3 { font-size: .9rem; margin: 16px 0 6px; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }
.meta { color: var(--muted); font-size: .85rem; margin: 0 0 8px; }
.text { white-space: pre-wrap; font-size: .9rem; background: var(--bg); border: 1px solid var(--line); border-radius: 6px; padding: 8px 10px; max-height: 340px; overflow: auto; margin: 0; overflow-wrap: anywhere; }
ul.refs { list-style: none; padding: 0; margin: 0; }
ul.refs li { padding: 6px 0; border-top: 1px solid var(--line); overflow-wrap: anywhere; }
ul.refs li:first-child { border-top: 0; }
.quote { display: block; color: var(--muted); font-size: .84rem; margin-top: 2px; }
.rel { color: var(--muted); font-size: .84rem; }
a, .link { color: var(--accent); text-decoration: none; cursor: pointer; background: none; border: 0; padding: 0; font: inherit; text-align: left; }
a:hover, .link:hover { text-decoration: underline; }
.target { font-family: var(--mono); font-size: .88em; }
.empty { color: var(--muted); font-style: italic; }
.note-box { color: var(--muted); font-size: .85rem; }
svg.graph { width: 100%; height: auto; display: block; }
svg .edge { stroke: var(--accent); stroke-opacity: .45; fill: none; }
svg .edge.law { stroke: var(--law); stroke-dasharray: 4 3; }
svg .edge:hover { stroke-opacity: 1; }
svg .node circle { fill: var(--accent-soft); stroke: var(--accent); stroke-width: 1.5; }
svg .node.law rect { fill: var(--law-soft); stroke: var(--law); stroke-width: 1.5; }
svg .node { cursor: pointer; }
svg .node:hover circle, svg .node:hover rect { stroke-width: 3; }
svg .node text { font-size: 11px; fill: var(--text); paint-order: stroke; stroke: var(--panel); stroke-width: 3px; stroke-linejoin: round; }
svg .count { font-size: 10px; fill: var(--muted); paint-order: stroke; stroke: var(--panel); stroke-width: 3px; }
svg .arrow { fill: var(--accent); }
.legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: .84rem; color: var(--muted); margin: 6px 0 0; }
table { border-collapse: collapse; width: 100%; font-size: .88rem; }
th, td { text-align: left; padding: 4px 6px; border-top: 1px solid var(--line); vertical-align: top; }
th { color: var(--muted); font-weight: 600; }
td.n { text-align: right; font-variant-numeric: tabular-nums; }
.findings li { margin: 0 0 10px; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; align-items: start; }
@media (max-width: 1000px) {
  .layout { grid-template-columns: 220px 1fr; }
  .layout .detail { grid-column: 1 / -1; }
}
@media (max-width: 700px) {
  .layout, .two { grid-template-columns: 1fr; }
  .scroll { position: static; max-height: 45vh; }
  .doclist.scroll { max-height: 30vh; }
  body { font-size: 14px; }
}
</style>
</head>
<body>
<header>
  <div class="bar">
    <div><h1>Document references</h1><div class="sub" id="sub"></div></div>
    <nav class="tabs" role="tablist">
      <button role="tab" data-view="docs">Documents</button>
      <button role="tab" data-view="graph">Graph</button>
      <button role="tab" data-view="findings">Findings</button>
    </nav>
    <input type="search" id="q" placeholder="Search sections and targets: 4926, 7.2, quorum" aria-label="Search sections and targets">
  </div>
</header>
<main id="main"></main>
<script type="application/json" id="data">__DATA__</script>
<script>
"use strict";
const D = JSON.parse(document.getElementById("data").textContent);
const DOCS = new Map(D.docs.map(d => [d.k, d]));
const QUIET = new Set(["found", "law on disk"]);
const NOTE = new Set(["prior numbering", "law not on disk", "not checked"]);
const main = document.getElementById("main");
const qBox = document.getElementById("q");

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [a, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (a === "class") el.className = v;
    else if (a.startsWith("on")) el.addEventListener(a.slice(2), v);
    else el.setAttribute(a, v === true ? "" : v);
  }
  for (const k of kids.flat(Infinity)) if (k !== null && k !== undefined && k !== false) el.append(k.nodeType ? k : String(k));
  return el;
}
const title = k => (DOCS.get(k) || {}).t || k;
const secName = s => s[0] || s[1];
const targetDoc = r => r.k === "section" ? r.t.split("#")[0] : r.k === "document" ? r.t : "";
const targetNum = r => r.k === "section" ? r.t.split("#").slice(1).join("#") : "";
function under(num, n) { return !!n && (num === n || num.startsWith(n + "(") || num.startsWith(n + ".")); }
function findSection(d, name) {
  if (!d || !name) return -1;
  let i = d.s.findIndex(s => s[0] === name);
  if (i < 0) i = d.s.findIndex(s => !s[0] && s[1] === name);
  return i;
}
function statusTag(st) {
  if (!st) return null;
  return h("span", {class: "tag " + (QUIET.has(st) ? "ok" : NOTE.has(st) ? "note" : "warn")}, st);
}
function hashFor(k, i) { return "#doc/" + encodeURIComponent(k) + (i >= 0 ? "/" + i : ""); }
function docLink(k, name, label) {
  const d = DOCS.get(k);
  if (!d) return h("span", {class: "target"}, label || k);
  const i = findSection(d, name);
  return h("a", {href: hashFor(k, i)}, label || (title(k) + (name ? " " + name : "")));
}

// Indexes.
const outBySec = new Map();     // "key\u0000section" -> refs
const outByDoc = new Map();
const inByDoc = new Map();      // target document -> refs from any section, including its own
for (const r of D.refs) {
  const a = r.s + "\u0000" + r.ss;
  (outBySec.get(a) || outBySec.set(a, []).get(a)).push(r);
  (outByDoc.get(r.s) || outByDoc.set(r.s, []).get(r.s)).push(r);
  const t = targetDoc(r);
  const targets = t ? [t] : (r.k === "resolution" && r.c ? r.c : []);
  for (const k of targets) (inByDoc.get(k) || inByDoc.set(k, []).get(k)).push(r);
}
const children = new Map();
for (const d of D.docs) {
  const kids = d.s.map(() => []);
  const tops = [];
  d.s.forEach((s, i) => (s[3] >= 0 ? kids[s[3]] : tops).push(i));
  children.set(d.k, {kids, tops});
}
function incoming(d, i) {
  const s = d.s[i];
  return (inByDoc.get(d.k) || []).filter(r => r.k === "section" && under(targetNum(r), s[0]) && !(r.s === d.k && r.ss === secName(s)));
}

// Rendering: one reference.
function refOut(r) {
  let target;
  if (r.k === "section") {
    const [k, n] = [targetDoc(r), targetNum(r)];
    target = DOCS.has(k) ? h("a", {href: hashFor(k, findSection(DOCS.get(k), r.n || n)), class: "target"}, (k === r.s ? "" : title(k) + " ") + n) : h("span", {class: "target"}, r.t);
  } else if (r.k === "document") {
    target = DOCS.has(r.t) ? h("a", {href: hashFor(r.t, -1)}, title(r.t)) : h("span", {class: "target"}, r.t);
  } else if (r.k === "resolution" && r.c && r.c.length) {
    target = [h("span", {class: "target"}, r.t), " (", r.c.map((k, j) => [j ? ", " : "", h("a", {href: hashFor(k, -1)}, title(k))]), ")"];
  } else if (r.k === "statute") {
    const base = r.t.replace(/\(.*$/, "");
    target = h("button", {class: "link target", title: "Every document that cites " + base, onclick: () => setQuery(base)}, r.t);
  } else {
    target = h("span", {class: "target"}, r.t);
  }
  return h("li", {}, target, " ", h("span", {class: "rel"}, r.r), statusTag(r.st),
           r.n ? h("span", {class: "rel"}, " (nearest: " + r.n + ")") : null, r.q ? h("span", {class: "quote"}, "\u201c" + r.q + "\u201d") : null);
}
function refIn(r) {
  return h("li", {}, docLink(r.s, r.ss, title(r.s) + (r.ss ? " " + r.ss : "")), " ", h("span", {class: "rel"}, r.r + " " + r.t),
           statusTag(QUIET.has(r.st) ? "" : r.st), r.q ? h("span", {class: "quote"}, "\u201c" + r.q + "\u201d") : null);
}
function refList(rs, fn) { return rs.length ? h("ul", {class: "refs"}, rs.map(fn)) : h("p", {class: "empty"}, "nothing"); }

// Documents view.
let state = {view: "docs", doc: "", sec: -1};
let treeDoc = "";
function docList() {
  const box = h("nav", {class: "pane doclist scroll", "aria-label": "Documents"});
  const kinds = [...D.kinds, ...new Set(D.docs.map(d => d.kind).filter(k => !D.kinds.includes(k)))];
  for (const kind of kinds) {
    const ds = D.docs.filter(d => d.kind === kind);
    if (!ds.length) continue;
    box.append(h("h3", {}, kind.replace(/_/g, " ")));
    for (const d of ds) {
      box.append(h("button", {class: d.k === state.doc ? "on" : "", onclick: () => go(d.k, -1)}, d.t.replace(/\.pdf$/i, ""),
        h("span", {class: "counts"}, d.s.length + " sections \u00b7 " + d.out + " out \u00b7 " + d.in + " in")));
    }
  }
  return box;
}
function treeRow(d, i) {
  const s = d.s[i];
  const out = (outBySec.get(d.k + "\u0000" + secName(s)) || []);
  const inn = s[0] ? incoming(d, i).length : 0;
  const flagged = out.some(r => !QUIET.has(r.st) && !NOTE.has(r.st));
  const btn = h("button", {class: "sec", "data-i": i}, s[0] ? h("span", {class: "num"}, s[0]) : null, s[1],
    out.length ? h("span", {class: "tag" + (flagged ? " warn" : ""), title: "references out"}, "\u2197" + out.length) : null,
    inn ? h("span", {class: "tag", title: "cited by"}, "\u2199" + inn) : null);
  const {kids} = children.get(d.k);
  if (!kids[i].length) {
    btn.addEventListener("click", () => go(d.k, i));
    return h("div", {class: "leaf"}, btn);
  }
  const det = h("details", {"data-i": i}, h("summary", {}, btn), h("div", {class: "kids"}, kids[i].map(j => treeRow(d, j))));
  btn.addEventListener("click", e => { e.preventDefault(); det.open = true; go(d.k, i); });
  return det;
}
function tree(d) {
  const {tops} = children.get(d.k);
  const box = h("section", {class: "pane tree scroll", id: "tree", "aria-label": "Sections"},
    h("div", {class: "meta"}, h("a", {href: hashFor(d.k, -1)}, d.t), " \u00b7 " + d.s.length + " sections"));
  if (!d.s.length) box.append(h("p", {class: "empty"}, "No numbered sections; the document is read as a whole."));
  for (const i of tops) box.append(treeRow(d, i));
  return box;
}
function docDetail(d) {
  const mine = (outByDoc.get(d.k) || []);
  const whole = mine.filter(r => !r.ss);
  const inn = (inByDoc.get(d.k) || []).filter(r => r.s !== d.k);
  const byName = inn.filter(r => r.k !== "section");
  const bySection = new Map();
  for (const r of inn.filter(r => r.k === "section")) bySection.set(r.s, (bySection.get(r.s) || 0) + 1);
  const kinds = {};
  for (const r of mine) kinds[r.k] = (kinds[r.k] || 0) + 1;
  const flagged = mine.filter(r => !QUIET.has(r.st));
  return h("section", {class: "pane detail", "aria-label": "Document"},
    h("h2", {}, d.t),
    h("p", {class: "meta"}, [d.kind.replace(/_/g, " "), d.s.length + " sections", mine.length + " references out", d.in + " in from other documents"].join(" \u00b7 ")),
    d.amends ? h("p", {class: "meta"}, "Amends or supplements ", docLink(d.amends, "", title(d.amends))) : null,
    d.numbers && d.numbers.length ? h("p", {class: "meta"}, "Resolution numbers printed: " + d.numbers.join(", ")) : null,
    d.library ? h("p", {class: "meta"}, "Read from the library's text: " + d.library) : null,
    d.head ? [h("h3", {}, d.s.length ? "Before the first section" : "Text"), h("pre", {class: "text"}, d.head),
              d.headTrimmed ? h("p", {class: "note-box"}, "Trimmed; the whole text is in data/outlines/" + d.k + ".json.") : null] : null,
    h("h3", {}, "References out by kind"),
    h("p", {}, Object.entries(kinds).map(([k, n]) => k + " " + n).join(", ") || "none"),
    flagged.length ? [h("h3", {}, "Out references to check (" + flagged.length + ")"), refList(flagged, r => { const li = refOut(r); li.prepend(docLink(r.s, r.ss, r.ss || "(whole document)"), " \u2192 "); return li; })] : null,
    whole.length ? [h("h3", {}, "Cites, outside any section (" + whole.length + ")"), refList(whole, refOut)] : null,
    h("h3", {}, "Cited by other documents"),
    bySection.size ? h("ul", {class: "refs"}, [...bySection].sort((a, b) => b[1] - a[1]).map(([k, n]) =>
      h("li", {}, h("a", {href: hashFor(k, -1)}, title(k)), " cites " + n + " of its sections"))) : null,
    byName.length ? [h("p", {class: "meta"}, "By name or by resolution number:"), refList(byName, refIn)] : null,
    !bySection.size && !byName.length ? h("p", {class: "empty"}, "nothing") : null);
}
function secDetail(d, i) {
  const s = d.s[i];
  const out = outBySec.get(d.k + "\u0000" + secName(s)) || [];
  const inn = s[0] ? incoming(d, i) : [];
  const parent = s[3] >= 0 ? d.s[s[3]] : null;
  return h("section", {class: "pane detail", "aria-label": "Section"},
    h("h2", {}, s[0] ? h("span", {class: "num"}, s[0]) : null, s[1]),
    h("p", {class: "meta"}, h("a", {href: hashFor(d.k, -1)}, d.t),
      parent ? [" \u00b7 in ", h("a", {href: hashFor(d.k, s[3])}, (parent[0] ? parent[0] + " " : "") + parent[1].slice(0, 60))] : null),
    s[4] ? h("pre", {class: "text"}, s[4]) : h("p", {class: "empty"}, "no text"),
    s[5] ? h("p", {class: "note-box"}, "Trimmed to the first " + s[4].length + " characters; the whole text is in data/outlines/" + d.k + ".json.") : null,
    h("h3", {}, "Cites (" + out.length + ")"), refList(out, refOut),
    h("h3", {}, "Cited by (" + inn.length + ")"), refList(inn, refIn));
}
function renderDocs() {
  const d = DOCS.get(state.doc) || D.docs[0];
  if (!d) { main.replaceChildren(h("p", {class: "empty"}, "No outlines.")); return; }
  state.doc = d.k;
  let layout = main.querySelector(".layout");
  if (!layout || treeDoc !== d.k) {
    layout = h("div", {class: "layout"}, docList(), tree(d), h("section", {class: "pane detail"}));
    main.replaceChildren(layout);
    treeDoc = d.k;
  } else {
    layout.replaceChild(docList(), layout.children[0]);
  }
  const detail = state.sec >= 0 && state.sec < d.s.length ? secDetail(d, state.sec) : docDetail(d);
  layout.replaceChild(detail, layout.children[2]);
  const t = layout.querySelector("#tree");
  t.querySelectorAll(".sec.on").forEach(b => b.classList.remove("on"));
  if (state.sec >= 0) {
    const btn = t.querySelector('.sec[data-i="' + state.sec + '"]');
    if (btn) {
      btn.classList.add("on");
      for (let el = btn.parentElement; el && el !== t; el = el.parentElement) if (el.tagName === "DETAILS") el.open = true;
      const r = btn.getBoundingClientRect(), tr = t.getBoundingClientRect();
      // Scroll the tree pane only, not the page.
      if (r.top < tr.top || r.bottom > tr.bottom) t.scrollTop += r.top - tr.top - t.clientHeight / 2;
    }
  }
  if (window.innerWidth <= 1000 && state.sec >= 0) detail.scrollIntoView({block: "start"});
}

// Graph view: a small force layout, computed once.
let placed = null;
function layoutGraph() {
  const G = D.graph, N = G.nodes.length, W = 1000, H = 720;
  const P = G.nodes.map((n, i) => ({x: W / 2 + 320 * Math.cos(2 * Math.PI * i / N), y: H / 2 + 260 * Math.sin(2 * Math.PI * i / N), dx: 0, dy: 0}));
  const k = Math.sqrt(W * H / Math.max(N, 1)) * 0.8, g = Math.max(N, 1) / 60;
  // A well-connected document pushes harder, so the hubs spread apart and their citers keep room for labels.
  const mass = G.nodes.map(() => 1);
  for (const e of G.edges) { mass[e.a] += 0.25; mass[e.b] += 0.25; }
  let temp = W / 10;
  for (let it = 0; it < 600; it++) {
    for (const p of P) { p.dx = 0; p.dy = 0; }
    for (let i = 0; i < N; i++) for (let j = i + 1; j < N; j++) {
      let dx = P[i].x - P[j].x, dy = P[i].y - P[j].y;
      const d = Math.hypot(dx, dy) || 0.01, f = k * k * Math.sqrt(mass[i] * mass[j]) / d;
      dx /= d; dy /= d;
      P[i].dx += dx * f; P[i].dy += dy * f; P[j].dx -= dx * f; P[j].dy -= dy * f;
    }
    for (const e of G.edges) {
      const a = P[e.a], b = P[e.b];
      let dx = a.x - b.x, dy = a.y - b.y;
      const d = Math.hypot(dx, dy) || 0.01, f = d * d / k * (0.15 + 0.1 * Math.log(1 + e.n)) * (e.law ? 0.3 : 1);
      dx /= d; dy /= d;
      a.dx -= dx * f; a.dy -= dy * f; b.dx += dx * f; b.dy += dy * f;
    }
    for (const p of P) {
      p.dx += (W / 2 - p.x) * g; p.dy += (H / 2 - p.y) * g;
      const d = Math.hypot(p.dx, p.dy) || 0.01, m = Math.min(d, temp);
      p.x += p.dx / d * m; p.y += p.dy / d * m;
    }
    temp = Math.max(temp * 0.99, 0.5);
  }
  const xs = P.map(p => p.x), ys = P.map(p => p.y);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  // Labels run to the right of a node, so the right margin is the wider one.
  const sx = (W - 250) / Math.max(x1 - x0, 1), sy = (H - 70) / Math.max(y1 - y0, 1);
  return P.map(p => ({x: 40 + (p.x - x0) * sx, y: 35 + (p.y - y0) * sy}));
}
function nodeLabel(n) {
  if (n.law) return n.code;
  const t = title(n.id).replace(/\.pdf$/i, "").replace(/^Special Resolution - /, "SR: ").replace(/^Administrative Resolution - /, "AR: ").replace(/^Policy Resolution - /, "PR: ");
  return t.length > 30 ? t.slice(0, 29) + "\u2026" : t;
}
function renderGraph() {
  const G = D.graph;
  placed = placed || layoutGraph();
  const NS = "http://www.w3.org/2000/svg";
  const s = (tag, attrs, ...kids) => { const el = document.createElementNS(NS, tag); for (const [a, v] of Object.entries(attrs)) el.setAttribute(a, v); for (const k of kids) el.append(k); return el; };
  const svg = s("svg", {class: "graph", viewBox: "0 0 1000 720", role: "img", "aria-label": "Which documents cite which, and the codes they cite"});
  svg.append(s("defs", {}, s("marker", {id: "arrow", viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "9", markerHeight: "9", markerUnits: "userSpaceOnUse", orient: "auto-start-reverse"}, s("path", {d: "M0,0 L10,5 L0,10 z", class: "arrow"}))));
  const size = n => n.law ? 12 : 5 + Math.sqrt(DOCS.get(n.id).s.length + DOCS.get(n.id).in) * 0.7;
  for (const e of G.edges) {
    const a = placed[e.a], b = placed[e.b], dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 1, r = size(G.nodes[e.b]) + 3;
    const line = s("line", {class: "edge" + (e.law ? " law" : ""), x1: a.x, y1: a.y, x2: b.x - dx / d * r, y2: b.y - dy / d * r,
      "stroke-width": (0.8 + Math.log2(1 + e.n) * 0.9).toFixed(2), "marker-end": e.law ? "" : "url(#arrow)"});
    line.append(s("title", {}, nodeLabel(G.nodes[e.a]) + " \u2192 " + nodeLabel(G.nodes[e.b]) + ": " + e.n + " reference" + (e.n === 1 ? "" : "s")));
    svg.append(line);
    if (e.n >= 5 && !e.law) svg.append(s("text", {class: "count", x: (a.x + b.x) / 2, y: (a.y + b.y) / 2}, String(e.n)));
  }
  G.nodes.forEach((n, i) => {
    const p = placed[i], r = size(n);
    const g = s("g", {class: "node" + (n.law ? " law" : ""), transform: "translate(" + p.x.toFixed(1) + "," + p.y.toFixed(1) + ")", tabindex: "0"});
    g.append(n.law ? s("rect", {x: -r, y: -r * 0.7, width: 2 * r, height: 1.4 * r, rx: 4}) : s("circle", {r: r.toFixed(1)}));
    g.append(s("text", {x: n.law ? 0 : r + 4, y: n.law ? 4 : 4, "text-anchor": n.law ? "middle" : "start"}, nodeLabel(n)));
    g.append(s("title", {}, n.law ? n.code + ": click to list what cites it" : title(n.id) + " (" + DOCS.get(n.id).s.length + " sections)"));
    const open = () => n.law ? setQuery(n.code + " ") : go(n.id, -1);
    g.addEventListener("click", open);
    g.addEventListener("keydown", ev => { if (ev.key === "Enter") open(); });
    svg.append(g);
  });
  const rows = G.edges.filter(e => !e.law).sort((x, y) => y.n - x.n);
  const lawRows = G.edges.filter(e => e.law).sort((x, y) => y.n - x.n);
  const table = (es, head) => h("table", {}, h("tr", {}, h("th", {}, "From"), h("th", {}, head), h("th", {}, "Refs")),
    es.map(e => h("tr", {}, h("td", {}, h("a", {href: hashFor(G.nodes[e.a].id, -1)}, title(G.nodes[e.a].id))),
      h("td", {}, G.nodes[e.b].law ? h("button", {class: "link", onclick: () => setQuery(G.nodes[e.b].code + " ")}, G.nodes[e.b].code) : h("a", {href: hashFor(G.nodes[e.b].id, -1)}, title(G.nodes[e.b].id))),
      h("td", {class: "n"}, e.n))));
  main.replaceChildren(h("div", {class: "pane"}, svg,
    h("div", {class: "legend"}, h("span", {}, "\u25cf a document (size: sections and citations)"), h("span", {}, "\u25a0 a code of law"),
      h("span", {}, "solid arrow: cites the document (sections, by name, or by resolution number)"), h("span", {}, "dashed: cites the code"),
      h("span", {}, "click a node to open it"))),
    h("div", {class: "two", style: "margin-top:12px"}, h("div", {class: "pane"}, h("h3", {}, "Documents citing documents"), table(rows, "Cites")),
      h("div", {class: "pane"}, h("h3", {}, "Documents citing codes"), table(lawRows, "Code"))));
  treeDoc = "";
}

// Findings view.
function renderFindings() {
  main.replaceChildren(h("div", {class: "pane"}, h("p", {class: "note-box"}, "A finding is a lead for a person: a drafting gap, a section an outline missed, or a copied header."),
    D.findings.length ? h("ol", {class: "findings"}, D.findings.map(f => h("li", {}, f.text,
      f.links.length ? h("div", {class: "meta"}, "Open: ", f.links.map((l, j) => [j ? " \u00b7 " : "", docLink(l.d, l.s, l.label)])) : null,
      f.q ? h("div", {class: "meta"}, h("button", {class: "link", onclick: () => setQuery(f.q)}, "List them")) : null))) : h("p", {class: "empty"}, "No findings.")));
  treeDoc = "";
}

// Search view.
function renderSearch(q) {
  const needle = q.trim().toLowerCase();
  const secs = [];
  for (const d of D.docs) d.s.forEach((s, i) => {
    const num = (s[0] || "").toLowerCase(), hay = (num + " " + s[1]).toLowerCase();
    const score = num === needle ? 0 : num.startsWith(needle) ? 1 : hay.includes(needle) ? 2 : -1;
    if (score >= 0) secs.push([score, d, i]);
  });
  secs.sort((a, b) => a[0] - b[0]);
  const targets = new Map();
  for (const r of D.refs) {
    const hay = (r.t + " " + r.st + " " + r.k).toLowerCase();
    if (hay.includes(needle)) (targets.get(r.t) || targets.set(r.t, []).get(r.t)).push(r);
  }
  const tlist = [...targets].sort((a, b) => b[1].length - a[1].length);
  main.replaceChildren(h("div", {class: "two"},
    h("div", {class: "pane"}, h("h3", {}, "Sections (" + secs.length + ")"),
      secs.length ? h("ul", {class: "refs"}, secs.slice(0, 200).map(([, d, i]) => h("li", {},
        h("a", {href: hashFor(d.k, i)}, d.s[i][0] ? h("span", {class: "num"}, d.s[i][0]) : null, d.s[i][1].slice(0, 120)),
        h("span", {class: "quote"}, d.t)))) : h("p", {class: "empty"}, "none"),
      secs.length > 200 ? h("p", {class: "note-box"}, "The first 200 shown.") : null),
    h("div", {class: "pane"}, h("h3", {}, "Targets (" + tlist.length + ")"),
      tlist.length ? h("ul", {class: "refs"}, tlist.slice(0, 150).map(([t, rs]) => {
        const sts = [...new Set(rs.map(r => r.st))];
        return h("li", {}, h("details", {open: tlist.length <= 3 ? true : null},
          h("summary", {}, h("span", {class: "target"}, t), " \u00b7 " + rs.length + " reference" + (rs.length === 1 ? "" : "s"), sts.map(st => statusTag(st))),
          h("ul", {class: "refs"}, rs.map(refIn))));
      })) : h("p", {class: "empty"}, "none"))));
  treeDoc = "";
}

// Navigation.
function go(k, i) { location.hash = hashFor(k, i); }
function setQuery(q) { qBox.value = q; state.view = "search"; render(); window.scrollTo(0, 0); }
function readHash() {
  const m = location.hash.match(/^#doc\/([^/]+)(?:\/(\d+))?$/);
  if (m) return {view: "docs", doc: decodeURIComponent(m[1]), sec: m[2] ? +m[2] : -1};
  if (location.hash === "#graph") return {view: "graph", doc: state.doc, sec: state.sec};
  if (location.hash === "#findings") return {view: "findings", doc: state.doc, sec: state.sec};
  return {view: "docs", doc: state.doc, sec: state.sec};
}
function render() {
  document.querySelectorAll("nav.tabs button").forEach(b => b.setAttribute("aria-selected", String(b.dataset.view === state.view)));
  if (state.view === "search" && qBox.value.trim().length >= 1) renderSearch(qBox.value);
  else if (state.view === "graph") renderGraph();
  else if (state.view === "findings") renderFindings();
  else { state.view = "docs"; renderDocs(); }
}
document.querySelectorAll("nav.tabs button").forEach(b => b.addEventListener("click", () => {
  qBox.value = "";
  const v = b.dataset.view;
  const want = v === "docs" ? hashFor(state.doc || D.docs[0].k, state.sec) : "#" + v;
  if (location.hash === want) { state.view = v; render(); } else location.hash = want;
}));
let timer = 0;
qBox.addEventListener("input", () => {
  clearTimeout(timer);
  timer = setTimeout(() => { state.view = qBox.value.trim() ? "search" : readHash().view; render(); }, 150);
});
window.addEventListener("hashchange", () => { qBox.value = ""; state = readHash(); render(); });
const refs = D.refs.length, sections = D.docs.reduce((n, d) => n + d.s.length, 0);
document.getElementById("sub").textContent = D.docs.length + " documents \u00b7 " + sections + " sections \u00b7 " + refs + " references \u00b7 " +
  D.findings.length + " findings \u00b7 built " + D.generated + " \u00b7 offline; loads nothing";
state = readHash();
if (!state.doc && D.docs.length) state.doc = (D.docs.find(d => d.kind === "declaration") || D.docs[0]).k;
render();
</script>
</body>
</html>
"""


__all__ = ["write_viewer", "viewer_data", "TEXT_LIMIT"]
