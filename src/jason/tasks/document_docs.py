"""The Rules document and the owner's manual template as Google Docs: a dry-run plan, and the write behind ``--yes``.

A definition (``jason.community.document_templates``) becomes one Doc on the association's Letterhead
(``letters.build_template``'s path: a copy of the Letterhead, its body replaced), written by ``doc_output.build`` with
the Doc's real named styles. ``plan_docs`` says what each Doc would be: the name, the folder, the requests, the headings, the
tables, the tokens left open, and the link between the two Docs. It reads Drive only to find out whether a person edited a
Doc jason made earlier, and it writes nothing. ``generate`` writes, and is called only with ``--yes``.

``data/templates/<profile>.json`` keeps, per Doc (key ``document:<definition key>``), the Doc id and two hashes as jason
last wrote them, of the rendered text and of the Doc's text, in the states of ``template_gen``:

- no Doc yet: **create** it (the Rules document first, so the manual template can link it by its id);
- the document changed and the Doc did not: **update** the Doc in place (its id, header, and footer stay);
- a person edited the Doc and the document did not: **edited**, left alone;
- both changed: **conflict**, nothing written;
- neither: **unchanged**.

Nothing is shared, sent, exported, or deleted; a Doc is never trashed.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jason.community import doc_output
from jason.community.document_templates import LAYOUTS, Assembly, DirectoryBlock, assemble
from jason.community.rules_document import MANUAL_TEMPLATE_KEY, RULES_KEY, ManualDocument
from jason.tasks import rules_documents as rd
from jason.tasks.template_gen import Action, load_state, save_state, sha

PREFIX = "document:"
NOT_READ = object()
DOC_URL = "https://docs.google.com/document/d/{}/edit"
PLACEHOLDER_ID = "RULES_DOC_ID"                  # printed in a dry run before the Rules Doc has an id
CHUNK = 400


@dataclass
class Job:
    key: str
    document: ManualDocument
    assembly: Assembly
    plan: doc_output.DocPlan
    base: str
    rules_url: str = ""

    @property
    def layout(self) -> Any:
        return self.assembly.definition.layout


@dataclass
class Step:
    key: str
    name: str
    action: Action
    doc_id: str = ""
    reason: str = ""
    folder: str = ""
    job: Job | None = None

    def line(self) -> str:
        link = f"  {DOC_URL.format(self.doc_id)}" if self.doc_id else ""
        why = f" ({self.reason})" if self.reason else ""
        return f"{self.action.value:10} {self.key:24} {self.name}{why}{link}"


def document_for(prepared: rd.Prepared, key: str) -> ManualDocument:
    """The profile's row for a definition, or a row with the definition's own title."""
    row = next((d for d in prepared.documents if d.key == key), None)
    if row is not None:
        return row
    return ManualDocument(key, rd.definition(prepared, key).title)


def make_job(prepared: rd.Prepared, key: str, state: dict[str, dict[str, Any]], *, with_rules: bool = False,
             rules_id: str = "") -> Job:
    """One Doc's content. The manual template is in its template form (the association's name stays a ``{TOKEN}``) and
    links the Rules document by its Doc id (from ``rules_id``, else the one in the state, else a placeholder); its rules
    are an index unless ``with_rules``. The Rules document itself is filled."""
    d = rd.definition(prepared, key)
    roles = rd.roles_of(prepared)
    if roles:
        d = replace(d, items=tuple(replace(b, roles=roles) if isinstance(b, DirectoryBlock) else b for b in d.items))
    known = rules_id or str((state.get(PREFIX + RULES_KEY) or {}).get("docId") or "")
    url = DOC_URL.format(known or PLACEHOLDER_ID)
    full = key == RULES_KEY or with_rules
    ctx = rd.context(prepared, mode="full" if full else "index", rules_url=url, template_form=key == MANUAL_TEMPLATE_KEY)
    assembly = assemble(d, ctx)
    plan = doc_output.build(assembly, d.layout)
    return Job(key, document_for(prepared, key), assembly, plan, sha(plan.text + "\n" + (url if key != RULES_KEY else "")), url)


def jobs_for(prepared: rd.Prepared, keys: tuple[str, ...], state: dict[str, dict[str, Any]], *,
             with_rules: bool = False) -> list[Job]:
    return [make_job(prepared, k, state, with_rules=with_rules) for k in keys]


def plan_docs(prepared: rd.Prepared, jobs: list[Job], state: dict[str, dict[str, Any]],
              doc_texts: dict[str, str | None]) -> list[Step]:
    """What a generation would do. ``doc_texts`` is each known Doc's current text, None when it is gone or in the trash;
    a Doc not in the map was not read (a dry run with no Google access), and then an unchanged base is reported
    unchanged and a changed one as an update that needs the Doc read first."""
    home = prepared.community.drive_home()
    steps = []
    for job in jobs:
        row = job.document
        folder = row.folder_id or getattr(home, "templates", "") or "Templates (found or made under My Drive)"
        entry = state.get(PREFIX + job.key)
        if entry:
            doc_id = str(entry.get("docId") or "")
            text = doc_texts.get(doc_id, NOT_READ)
            changed = job.base != entry.get("baseSha")
            if text is None:
                steps.append(Step(job.key, row.name, Action.CREATE, doc_id, "its Doc is gone or in the trash", folder, job))
            elif text is NOT_READ:
                steps.append(Step(job.key, row.name, Action.UPDATE if changed else Action.UNCHANGED, doc_id,
                                  "the document changed; the Doc was not read, so whether a person edited it is not known"
                                  if changed else "the Doc was not read", folder, job))
            else:
                edited = sha(text) != entry.get("docSha")
                if changed and edited:
                    steps.append(Step(job.key, row.name, Action.CONFLICT, doc_id,
                                      "the document and the Doc both changed; fold the Doc's edit into the definition or drop it",
                                      folder, job))
                elif changed:
                    steps.append(Step(job.key, row.name, Action.UPDATE, doc_id, "the document changed", folder, job))
                elif edited:
                    steps.append(Step(job.key, row.name, Action.EDITED, doc_id,
                                      "a person edited the Doc; left alone", folder, job))
                else:
                    steps.append(Step(job.key, row.name, Action.UNCHANGED, doc_id, "", folder, job))
        elif row.drive_id:
            steps.append(Step(job.key, row.name, Action.EDITED, row.drive_id,
                              "the profile names a Doc that jason did not generate; left alone", folder, job))
        else:
            steps.append(Step(job.key, row.name, Action.CREATE, "", "no Doc yet", folder, job))
    return steps


def describe(step: Step, state: dict[str, dict[str, Any]]) -> list[str]:
    """The lines a dry run prints for one step: exactly what would be written."""
    out = [step.line()]
    job = step.job
    if job is None:
        return out
    p = job.plan
    styles = ", ".join(f"{k} x{v}" for k, v in sorted(p.styles().items()))
    contents = "then one contents pass of links to the headings" if p.contents_depth else "no contents"
    own = "(the Letterhead's own)"
    out.append(f"           folder: {step.folder}")
    out.append(f"           requests: {p.count} in the body pass (+1 clears the Letterhead's sample text), {contents}; "
               f"{len(p.named_ranges)} named ranges (one per block, by its id)")
    out.append(f"           styles: {styles}")
    out.append(f"           tables: {len(p.tables)}; page breaks: {p.page_breaks}")
    out.append(f"           header: {p.header or own}; footer: {p.footer or own}")
    out.append("           tokens left open: " + (", ".join(p.tokens) if p.tokens else "none"))
    for words_, url in p.links:
        shown = url.replace(PLACEHOLDER_ID, "<the Rules Doc's id, known once it is created>")
        out.append(f"           link: {words_!r} -> {shown}")
    return out


def _body_end(doc: dict[str, Any]) -> int:
    tabs = doc.get("tabs")
    tab = (tabs[0].get("documentTab") or {}) if isinstance(tabs, list) and tabs else doc
    content = (tab.get("body") or {}).get("content") or []
    return int(content[-1].get("endIndex", 1)) if content else 1


def _clear_ranges(doc: dict[str, Any]) -> list[dict[str, Any]]:
    tabs = doc.get("tabs")
    tab = (tabs[0].get("documentTab") or {}) if isinstance(tabs, list) and tabs else doc
    return [{"deleteNamedRange": {"name": name}} for name in (tab.get("namedRanges") or doc.get("namedRanges") or {})]


def _send(docs: Any, doc_id: str, requests: list[dict[str, Any]]) -> None:
    """Send requests in order, a batch at a time: each request's indices assume the ones before it applied."""
    for k in range(0, len(requests), CHUNK):
        docs.batch_update(doc_id, requests[k:k + CHUNK])


def generate(drive: Any, docs: Any, prepared: rd.Prepared, steps: list[Step], state: dict[str, dict[str, Any]], *,
             letterhead_id: str, footer: str, with_rules: bool = False) -> list[dict[str, Any]]:
    """Carry out the steps that write. ``state`` is updated in place; the caller saves it. The Rules document is written
    first, and the manual template is built after, with the link to the Rules Doc's id."""
    from jason.tasks.letters import banner_requests, document_text, format_requests

    done: list[dict[str, Any]] = []
    order = sorted(steps, key=lambda s: 0 if s.key == RULES_KEY else 1)
    for step in order:
        if not step.action.writes:
            continue
        rules_id = str((state.get(PREFIX + RULES_KEY) or {}).get("docId") or "")
        job = make_job(prepared, step.key, state, with_rules=with_rules, rules_id=rules_id)
        created = step.action is Action.CREATE
        if created:
            if not letterhead_id:
                raise ValueError("the profile's letterhead names no Doc to build from (Community.letterhead)")
            doc_id = drive.copy(letterhead_id, job.document.name, _folder(drive, prepared, job.document))
            doc = docs.get(doc_id)
            before: list[dict[str, Any]] = []
            after = banner_requests(doc)
            if "LETTERHEAD" in document_text(doc):
                after.append({"replaceAllText": {"containsText": {"text": " - LETTERHEAD", "matchCase": True},
                                                 "replaceText": f" · {footer}"}})
        else:
            doc_id = step.doc_id
            doc = docs.get(doc_id)
            before, after = _clear_ranges(doc), []
        reqs = before + doc_output.build(job.assembly, job.layout, doc_end=_body_end(doc)).requests + after
        _send(docs, doc_id, reqs)
        fresh = docs.get(doc_id)
        furniture = format_requests(fresh, job.plan.header) + doc_output.footer_requests(fresh, job.plan.footer)
        if furniture:
            docs.batch_update(doc_id, furniture)
        links = doc_output.contents_requests(docs.get(doc_id), job.plan.contents_depth)
        if links:
            docs.batch_update(doc_id, links)
        final = docs.get(doc_id)
        problems = doc_output.verify(final, job.plan)
        state[PREFIX + step.key] = {
            "docId": doc_id, "baseSha": job.base, "docSha": sha(document_text(final)), "name": job.document.name,
            "rulesUrl": job.rules_url if step.key != RULES_KEY else "",
            "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        done.append({"key": step.key, "action": step.action.value, "id": doc_id, "url": DOC_URL.format(doc_id),
                     "requests": len(reqs), "problems": problems})
    return done


def _folder(drive: Any, prepared: rd.Prepared, row: ManualDocument) -> str:
    home = prepared.community.drive_home()
    if row.folder_id:
        return row.folder_id
    if getattr(home, "templates", ""):
        return home.templates
    return drive.child_folder(home.my_drive, "Templates") or drive.create_folder("Templates", home.my_drive)


__all__ = ["Job", "NOT_READ", "PREFIX", "Step", "describe", "document_for", "generate", "jobs_for", "load_state",
           "make_job", "plan_docs", "save_state"]
