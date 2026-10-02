"""Generate a profile's letter template Docs from jason's base bodies, and tell who changed what since.

The base is the source: `templates.BODIES` names no association, and a profile's Docs are built from it on the profile's
letterhead (`letters.build_template`). ``data/templates/<profile>.json`` keeps, per template kind, the Doc id and two
hashes as jason last wrote them, of the base text and of the Doc's text, so a run can tell:

- no Doc yet: **create** it from the Letterhead;
- a Doc the profile names that jason never generated (built before the bases): **adopt** it, rewriting its body
  from the base; Drive's version history keeps what it said;
- the base changed and the Doc did not: **update** the Doc in place;
- a person edited the Doc and the base did not: **edited**, left alone. Fold the edit into the base if any
  association should have it, or keep it as this profile's own;
- both changed: **conflict**; nothing is written;
- neither: **unchanged**.

A filled letter is its own document once made; this is about the template Docs only (docs/base-templates.md).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from jason.community.templates import BODIES, CONTINUATION, DocumentTemplate, TemplateKind


class Action(Enum):
    CREATE = "create"
    ADOPT = "adopt"
    UPDATE = "update"
    UNCHANGED = "unchanged"
    EDITED = "edited"
    CONFLICT = "conflict"

    @property
    def writes(self) -> bool:
        return self in (Action.CREATE, Action.ADOPT, Action.UPDATE)


@dataclass(frozen=True)
class Step:
    kind: TemplateKind
    title: str
    action: Action
    doc_id: str = ""
    reason: str = ""

    def line(self) -> str:
        link = f"  https://docs.google.com/document/d/{self.doc_id}/edit" if self.doc_id else ""
        why = f" ({self.reason})" if self.reason else ""
        return f"{self.action.value:10} {self.kind.slug:16} {self.title}{why}{link}"


def sha(text: str) -> str:
    """A hash of text with its whitespace runs folded, so a Doc's paragraph breaks do not read as edits."""
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()


def base_sha(kind: TemplateKind) -> str:
    """The base body and its continuation header, as jason writes them."""
    return sha("\n".join(text for _, text in BODIES[kind]) + "\n" + CONTINUATION.get(kind, ""))


def _folded(text: str) -> str:
    return " ".join(text.replace("**", "").split())


def as_built(kind: TemplateKind, community: Any) -> str:
    """The body as jason would have built it for this profile: the base with the profile's values in place (a Doc
    built before the bases carries those values as text)."""
    from jason.community.template_values import profile_values

    values = profile_values(community) if hasattr(community, "identity") else {}
    text = "\n".join(line for _, line in BODIES[kind])
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return _folded(text)


def state_path(data_dir: Path, profile: str) -> Path:
    return Path(data_dir) / "templates" / f"{profile}.json"


def load_state(data_dir: Path, profile: str) -> dict[str, dict[str, Any]]:
    try:
        return json.loads(state_path(data_dir, profile).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(data_dir: Path, profile: str, state: dict[str, dict[str, Any]]) -> Path:
    path = state_path(data_dir, profile)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    return path


def record(kind: TemplateKind, doc_id: str, doc_text: str) -> dict[str, Any]:
    return {"docId": doc_id, "baseSha": base_sha(kind), "docSha": sha(doc_text),
            "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def templates(community: Any, state: dict[str, dict[str, Any]]) -> list[DocumentTemplate]:
    """The profile's template rows with each Doc id jason generated in place of the one the profile names."""
    out = []
    for template in community.document_templates():
        generated = (state.get(template.kind.slug) or {}).get("docId")
        out.append(replace(template, drive_id=generated) if generated else template)
    return out


def template_for(community: Any, kind: TemplateKind, data_dir: Path, profile: str) -> DocumentTemplate | None:
    """One template row, with its generated Doc id when there is one: what filling a letter copies."""
    return next((t for t in templates(community, load_state(data_dir, profile)) if t.kind is kind), None)


def plan(community: Any, state: dict[str, dict[str, Any]], doc_texts: dict[str, str | None]) -> list[Step]:
    """What a generation would do. ``doc_texts`` is each known Doc's current text, None when it is gone or trashed."""
    steps = []
    for template in community.document_templates():
        kind, entry = template.kind, state.get(template.kind.slug)
        if entry:
            doc_id = str(entry.get("docId") or "")
            text = doc_texts.get(doc_id)
            if text is None:
                steps.append(Step(kind, template.title, Action.CREATE, doc_id, "its Doc is gone or in the trash"))
                continue
            base_changed = base_sha(kind) != entry.get("baseSha")
            doc_changed = sha(text) != entry.get("docSha")
            if base_changed and doc_changed:
                steps.append(Step(kind, template.title, Action.CONFLICT, doc_id,
                                  "the base and the Doc both changed; fold the Doc's edit into the base or drop it"))
            elif base_changed:
                steps.append(Step(kind, template.title, Action.UPDATE, doc_id, "the base changed"))
            elif doc_changed:
                steps.append(Step(kind, template.title, Action.EDITED, doc_id,
                                  "a person edited the Doc; fold the edit into the base, or keep it as this profile's own"))
            else:
                steps.append(Step(kind, template.title, Action.UNCHANGED, doc_id))
        elif template.drive_id and doc_texts.get(template.drive_id) is not None:
            if as_built(kind, community) in _folded(doc_texts[template.drive_id]):
                why = "built before the bases and unchanged since; its body is rewritten from the base"
            else:
                why = ("built before the bases, and it no longer reads as built: a person may have edited it. Compare "
                       "before --yes; Drive's version history keeps what it says")
            steps.append(Step(kind, template.title, Action.ADOPT, template.drive_id, why))
        else:
            steps.append(Step(kind, template.title, Action.CREATE, reason="no Doc yet"))
    return steps


def generate(drive: Any, docs: Any, community: Any, steps: list[Step], state: dict[str, dict[str, Any]], *,
             folder_id: str) -> list[dict[str, Any]]:
    """Carry out the steps that write. ``state`` is updated in place; the caller saves it."""
    from jason.tasks.letters import build_template, document_text, rewrite_template

    head = community.letterhead()
    rows = {t.kind: t for t in community.document_templates()}
    done = []
    for step in steps:
        if not step.action.writes:
            continue
        template = rows[step.kind]
        if step.action is Action.CREATE:
            if not head.doc_id:
                raise ValueError("the profile's letterhead names no Doc to build templates from (Community.letterhead)")
            made = build_template(drive, docs, replace(template, drive_id=""), letterhead_id=head.doc_id,
                                  folder_id=folder_id, footer=head.footer)
            doc_id = made["id"]
        else:
            doc_id = rewrite_template(docs, replace(template, drive_id=step.doc_id))["id"]
        state[step.kind.slug] = record(step.kind, doc_id, document_text(docs.get(doc_id)))
        done.append({"kind": step.kind.slug, "action": step.action.value, "id": doc_id})
    return done
