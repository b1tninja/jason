"""A PayHOA broadcast drafted on disk, checked, and previewed through PayHOA's own renderer.

The body is the HTML PayHOA's composer sends (``<p>`` paragraphs, ``<span class="placeholder">{first name}</span>``).
Attachments are PayHOA library files, named by id or library path and resolved against the catalog on disk; a name
that matches nothing stays a miss. The preview renders the body for the signed-in admin's own membership, so no
other member's name is read. jason never sends the broadcast: a person sends it from PayHOA. A test copy goes only
to the signed-in admin, and only with ``--yes``.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from jason.community.library import LibraryDocument

# Placeholders PayHOA's composer wraps; the capture had {first name}. Others are flagged, not invented.
# Placeholders PayHOA's composer fills: {first name} from the member, {unit address} from the unit the member was
# chosen through (the send's ``unitIds``; seen in the saved flood template and its send, broadcast2.har).
KNOWN_PLACEHOLDERS = frozenset({"first name", "unit address"})
# A field left for a person to fill in a template: "[BUILDING]", "[START DATE]". Sending one unfilled is a mistake.
UNFILLED = re.compile(r"\[[A-Z][A-Z0-9 /&'-]{1,40}\]")
PLACEHOLDER = re.compile(r'<span class="placeholder">\{([^}<]+)\}</span>')
BARE_PLACEHOLDER = re.compile(r"\{(first name|last name|full name|unit address|address)\}", re.IGNORECASE)
LINK = re.compile(r'<a\s[^>]*href="([^"]+)"', re.IGNORECASE)
PREVIEW_PREFIX = "(Preview) "


@dataclass(frozen=True)
class Attachment:
    spec: str
    document: LibraryDocument | None

    @property
    def id(self) -> int | None:
        return int(self.document.id) if self.document else None


@dataclass
class Check:
    placeholders: list[str] = field(default_factory=list)
    unknown_placeholders: list[str] = field(default_factory=list)
    bare_placeholders: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    words: int = 0
    problems: list[str] = field(default_factory=list)


def body_of(text: str) -> str:
    """The message HTML: the ``<body>`` of a full page, else the text as given."""
    match = re.search(r"<body[^>]*>(.*)</body>", text, re.IGNORECASE | re.DOTALL)
    return (match.group(1) if match else text).strip()


def check(message: str, subject: str | None) -> Check:
    found = Check()
    found.placeholders = PLACEHOLDER.findall(message)
    found.unknown_placeholders = sorted({p for p in found.placeholders if p.casefold() not in KNOWN_PLACEHOLDERS})
    stripped = PLACEHOLDER.sub("", message)
    found.bare_placeholders = sorted({m.group(0) for m in BARE_PLACEHOLDER.finditer(stripped)})
    found.links = LINK.findall(message)
    found.words = len(re.sub(r"<[^>]+>", " ", html.unescape(message)).split())
    if not subject:
        found.problems.append("no subject (--subject)")
    unfilled = sorted(set(UNFILLED.findall(re.sub(r"<[^>]+>", " ", message) + " " + (subject or ""))))
    if unfilled:
        found.problems.append(f"fields not filled in: {', '.join(unfilled)}")
    if found.unknown_placeholders:
        found.problems.append(f"placeholders PayHOA may not fill: {', '.join(found.unknown_placeholders)}")
    if found.bare_placeholders:
        found.problems.append(f"placeholders not wrapped as PayHOA's composer wraps them: {', '.join(found.bare_placeholders)}")
    if re.search(r"<(script|style|iframe)\b", message, re.IGNORECASE):
        found.problems.append("script, style, or iframe tags: the composer drops them")
    for link in found.links:
        if not re.match(r"(https?|mailto):", link, re.IGNORECASE):
            found.problems.append(f"link that is not http(s) or mailto: {link}")
    return found


def resolve_attachments(specs: Iterable[str], library: Iterable[LibraryDocument]) -> list[Attachment]:
    """Each spec is a library id, a library path, or a file name that names exactly one file."""
    docs = list(library)
    by_id = {d.id: d for d in docs}
    by_path = {d.path.casefold(): d for d in docs}
    resolved: list[Attachment] = []
    for spec in specs:
        key = str(spec).strip()
        doc = by_id.get(key) or by_path.get(key.casefold())
        if doc is None:
            named = [d for d in docs if d.name.casefold() == key.casefold()]
            doc = named[0] if len(named) == 1 else None
        resolved.append(Attachment(key, doc))
    return resolved


def own_membership(people: Iterable[dict[str, Any]], user_id: int | None) -> int | None:
    """The signed-in user's membership id in this association (a people-list row's ``id`` by ``userId``)."""
    if user_id is None:
        return None
    for row in people:
        if row.get("userId") == user_id and row.get("id") is not None:
            return int(row["id"])
    return None


@dataclass
class Recipients:
    """Who a broadcast to some unit tags and member tags reaches: the units, their current owners' memberships, and
    the members tagged directly. ``invalid_email`` are memberships PayHOA marks as having no deliverable email; they
    need the notice another way (by mail, under the member's delivery choice)."""

    unit_tags: list[str] = field(default_factory=list)
    member_tags: list[str] = field(default_factory=list)
    unit_ids: list[int] = field(default_factory=list)
    unit_labels: list[str] = field(default_factory=list)
    membership_ids: list[int] = field(default_factory=list)
    invalid_email: list[int] = field(default_factory=list)
    other_tags: dict[str, int] = field(default_factory=dict)       # the recipients' units' other tags, by count
    unknown_tags: list[str] = field(default_factory=list)


def _tag_names(row: dict[str, Any]) -> list[str]:
    return [str(t.get("tag") if isinstance(t, dict) else t) for t in row.get("tags") or []]


def unit_tags(units: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Every unit tag in use, with how many units carry it."""
    counts: dict[str, int] = {}
    for unit in units:
        for name in _tag_names(unit):
            counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def recipients(units: Iterable[dict[str, Any]], people: Iterable[dict[str, Any]], *, tags: Iterable[str] = (),
               member_tags: Iterable[str] = ()) -> Recipients:
    """Resolve tags to recipients from the units list (each unit's ``tags`` and ``owners``) and the people list (each
    member's ``tags``). Tag names match without regard to case; a tag no unit or member carries is reported."""
    units, people = list(units), list(people)
    wanted_units = {t.casefold(): t for t in tags}
    wanted_members = {t.casefold(): t for t in member_tags}
    found = Recipients(unit_tags=list(wanted_units.values()), member_tags=list(wanted_members.values()))
    seen_unit: set[str] = set()
    seen_member: set[str] = set()
    members: dict[int, bool] = {}                                   # membership id -> email is invalid
    for unit in units:
        names = _tag_names(unit)
        hits = {n.casefold() for n in names} & set(wanted_units)
        if not hits or unit.get("deletedAt"):
            continue
        seen_unit |= hits
        found.unit_ids.append(int(unit["id"]))
        found.unit_labels.append(str(unit.get("title") or unit.get("address") or unit["id"]))
        for name in names:
            if name.casefold() not in wanted_units:
                found.other_tags[name] = found.other_tags.get(name, 0) + 1
        for owner in unit.get("owners") or []:
            if owner.get("deletedAt") or owner.get("membershipId") is None:
                continue
            mid = int(owner["membershipId"])
            members[mid] = members.get(mid, False) or bool(owner.get("hasInvalidEmailAddress"))
    for person in people:
        hits = {n.casefold() for n in _tag_names(person)} & set(wanted_members)
        if hits and not person.get("deletedAt") and person.get("id") is not None:
            seen_member |= hits
            members.setdefault(int(person["id"]), not bool(person.get("email")))
    found.membership_ids = sorted(members)
    found.invalid_email = sorted(m for m, bad in members.items() if bad)
    found.unknown_tags = [wanted_units[t] for t in wanted_units if t not in seen_unit] + \
                         [wanted_members[t] for t in wanted_members if t not in seen_member]
    return found


def live_rows(client: Any, org_id: int, *, tags: Iterable[str] = (), member_tags: Iterable[str] = ()) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The units carrying the tags, read now the way the composer reads them (``units?unitTags[]=``), and the people
    list when member tags are asked for. A send resolves its recipients from these, never from an old catalog."""
    tags, member_tags = list(tags), list(member_tags)
    units: list[dict[str, Any]] = []
    if tags:
        page = 1
        while True:
            body = client.list_units(org_id, page=page, unit_tags=tags)
            units.extend(body.get("data") or [])
            meta = body.get("meta") or {}
            if page >= int(meta.get("lastPage") or meta.get("last_page") or 1):
                break
            page += 1
    people = list(client.iter_people(org_id)) if member_tags else []
    return units, people


def catalog_rows(db: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    """The units and people as ``jason sync-catalog`` stored them, and when the units were synced."""
    import json
    import sqlite3

    if not Path(db).is_file():
        return [], [], ""
    conn = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
    try:
        units = [json.loads(r[0]) for r in conn.execute("SELECT raw_json FROM units")]
        people = [json.loads(r[0]) for r in conn.execute("SELECT raw_json FROM people")]
        synced = conn.execute("SELECT max(synced_at) FROM units").fetchone()[0] or ""
    finally:
        conn.close()
    return units, people, str(synced)


def template_lines(templates: Iterable[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for row in templates:
        if row.get("deletedAt"):
            continue
        names = ", ".join(str(a.get("fileName")) for a in row.get("attachments") or [])
        lines.append(f"{row.get('id')}  {str(row.get('updatedAt') or '')[:10]}  {row.get('subject')}")
        if names:
            lines.append(f"    attachments: {names}")
    return lines


def preview_page(subject: str, sender: str | None, rendered: str, attachments: list[Attachment], checked: Check) -> str:
    """A local page that shows the rendered message the way a member's mail client would frame it."""
    files = "".join(f"<li>{html.escape(a.document.path)} <small>(#{a.id})</small></li>" for a in attachments if a.document)
    notes = "".join(f"<li>{html.escape(p)}</li>" for p in checked.problems) or "<li>none</li>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Broadcast Preview</title>
<style>
:root {{ --bg:#f4f4f2; --card:#fff; --ink:#1d1d1b; --muted:#6b6b66; --line:#ddd; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#1b1b1a; --card:#262624; --ink:#ecebe6; --muted:#a3a29b; --line:#3a3a37; }} }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.55 system-ui, sans-serif; }}
main {{ max-width:760px; margin:24px auto; padding:0 16px; }}
.meta, .mail {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:16px 20px; margin-bottom:16px; }}
.meta dt {{ color:var(--muted); font-size:13px; }} .meta dd {{ margin:0 0 8px; }}
.mail a {{ color:inherit; }}
</style></head><body><main>
<dl class="meta"><dt>Subject</dt><dd>{html.escape(subject)}</dd><dt>From</dt><dd>{html.escape(sender or "(PayHOA's default)")}</dd>
<dt>Attachments</dt><dd><ul>{files or "<li>none</li>"}</ul></dd><dt>Checks</dt><dd><ul>{notes}</ul></dd>
<dt>Rendered by PayHOA for the signed-in admin; not sent</dt></dl>
<article class="mail">{rendered}</article>
</main></body></html>
"""


def save_preview(path: Path, page: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    return path


def recipients_plan(found: Recipients, *, rule: str = "", synced: str = "") -> dict[str, Any]:
    """Who the broadcast reaches, as a notice keeps it (``recipients.json``): ids only, no addresses. A member PayHOA
    marks as having no deliverable email is listed for a letter."""
    bad = set(found.invalid_email)
    return {"notice": rule, "unitTag": ", ".join(found.unit_tags), "memberTags": list(found.member_tags),
            "unitIds": list(found.unit_ids), "emailMembershipIds": [m for m in found.membership_ids if m not in bad],
            "mail": [{"membershipId": m, "why": "no deliverable email in PayHOA"} for m in sorted(bad)],
            "secondary": [], "catalogSynced": synced, "source": "jason broadcast --tag/--member-tag (the catalog)"}


def keep_notice(data_dir: Path, key: str, *, message: str, subject: str, refs: Iterable[Any] = (),
                found: Recipients | None = None, synced: str = "", state: str, by: str = "",
                attachments: Iterable[Attachment] = (), source: str = "") -> dict[str, Any]:
    """Keep a broadcast notice's words as rendered (``jason.tasks.notice_text``): the body jason hands PayHOA, its
    subject, the fill records of its references, and the recipients plan when tags named them. Only once it is saved
    for a person to send; never on a dry run."""
    from jason.tasks import notice_text
    from jason.tasks.notice_record import requirement_for

    row, _ = requirement_for(key)
    files = ", ".join(a.document.path for a in attachments if a.document)
    return notice_text.keep(data_dir, key, kind="broadcast", state=state + (f"; attachments: {files}" if files else ""),
                            body=message, body_name="message.html", subject=subject,
                            refs=notice_text.fill_records(refs),
                            recipients=recipients_plan(found, rule=row.key if row else "", synced=synced)
                            if found is not None else None, by=by, source=source)
