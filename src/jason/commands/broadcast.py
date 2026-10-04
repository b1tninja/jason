"""``jason broadcast``: draft a PayHOA broadcast on disk, check it, and preview it through PayHOA's renderer.

A dry run by default: the body and its attachments are checked against the catalog on disk and nothing is called.
``--preview`` asks PayHOA to render the body for the signed-in admin and writes a local page beside the file.
``--upload`` puts a local PDF in the library's private Email Attachments folder, and ``--send-sample`` emails a test
copy to the signed-in admin only; both need ``--yes``. jason never sends the broadcast to members.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Callable


def _data_dir(args: argparse.Namespace) -> Path:
    from jason.config import Settings

    return Settings.load(args.env).payhoa_catalog.parent


def _upload_spec(spec: str) -> tuple[Path, str]:
    """``PATH`` or ``PATH=Library Name.pdf``: the local file and the name it gets in the library."""
    path, _, name = spec.partition("=")
    return Path(path), (name.strip() or Path(path).name)


def _templates(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.tasks.broadcast import template_lines

    with agent_factory(args) as agent:
        rows = agent.payhoa().list_email_templates(agent.org_id)
    if args.template is None:
        for line in template_lines(rows):
            print(line)
        return 0
    row = next((r for r in rows if r.get("id") == args.template), None)
    if row is None:
        print(f"no template {args.template}", file=sys.stderr)
        return 1
    if not args.save:
        print(f"subject: {row.get('subject')}")
        print(row.get("message") or "")
        return 0
    dest = Path(args.save)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(str(row.get("message") or ""), encoding="utf-8")
    print(f"saved template {args.template} ({row.get('subject')}) to {dest}")
    return 0


def _doc_shas(drive: Any, doc_id: str) -> tuple[str, str] | None:
    """The hash of a Doc's body as rich composer HTML, and as the first form (``rich=False``) the sync state's older
    hashes were taken of; None when the Doc is gone or in the trash."""
    from jason.google.docs_html import document_html
    from jason.google.errors import GoogleError
    from jason.tasks.template_docs import sha

    try:
        if drive._get(f"/files/{doc_id}", {"fields": "id,trashed", "supportsAllDrives": True}).get("trashed"):
            return None
        doc = drive.docs().get(doc_id)
        return sha(document_html(doc)), sha(document_html(doc, rich=False))
    except GoogleError:
        return None


def _doc_sha(drive: Any, doc_id: str) -> str | None:
    """The hash of a Doc's body as composer HTML; None when the Doc is gone or in the trash."""
    found = _doc_shas(drive, doc_id)
    return found[0] if found else None


def _carry_forward(state: dict[str, dict[str, Any]], drive: Any) -> dict[str, str | None]:
    """Each Doc's current hash; an entry whose stored hash is the first form's, for a Doc unchanged since, is moved to
    the rich form's hash, so a change of form is not taken for a person's edit."""
    shas: dict[str, str | None] = {}
    for entry in state.values():
        doc_id = str(entry.get("docId") or "")
        if not doc_id:
            continue
        found = _doc_shas(drive, doc_id)
        shas[doc_id] = found[0] if found else None
        if found and entry.get("docSha") == found[1] and found[0] != found[1]:
            entry["docSha"] = found[0]
    return shas


def _body_only(message: str) -> str:
    """A template's body without the letterhead frame: the Doc holds the body; jason adds the frame (--letterhead)."""
    from jason.community import community as active
    from jason.community.email_html import strip_letterhead

    letterhead = active().email_letterhead()
    return strip_letterhead(message, letterhead)[0] if letterhead else message


def _sync_docs(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.community.spec import spec_module
    from jason.google.drive import GOOGLE_DOC_MIME_TYPE
    from jason.tasks.template_docs import (APP_KEY, Action, description, doc_name, format_doc, import_html, load_state,
                                           plan, record, save_state, step_line)

    from jason.community.profile import load_profile

    home = load_profile().drive_home()
    data_dir = _data_dir(args)
    state = load_state(data_dir)
    with agent_factory(args) as agent:
        templates = agent.payhoa().list_email_templates(agent.org_id)
        drive = agent.drive()
        shas = _carry_forward(state, drive)
        save_state(data_dir, state)                  # local bookkeeping: hashes carried to the rich form
        steps = plan(templates, state, shas)
        for step in steps:
            print(step_line(step))
        writes = [s for s in steps if s.action.writes]
        if not writes:
            return 0
        if not args.yes:
            print(f"{len(writes)} Docs to create or update; --yes writes them")
            return 0
        folder = (home.broadcasts or drive.child_folder(home.templates, home.broadcasts_name)
                  or drive.create_folder(home.broadcasts_name, home.templates))
        rows = {int(r["id"]): r for r in templates}
        for step in writes:
            row = rows[step.template_id]
            if step.action is Action.CREATE:
                doc_id = drive.upload_bytes(doc_name(row), import_html(_body_only(str(row.get("message") or ""))), mime_type="text/html",
                                            parent_id=folder, convert_to=GOOGLE_DOC_MIME_TYPE, description=description(row),
                                            app_properties={APP_KEY: str(step.template_id)})
            else:
                doc_id = step.doc_id
                drive.replace_content(doc_id, import_html(_body_only(str(row.get("message") or ""))), mime_type="text/html")
                drive.update_metadata(doc_id, name=doc_name(row), description=description(row))
            format_doc(drive.docs(), doc_id, row)       # header and highlights; neither is the body's HTML
            state[str(step.template_id)] = record(row, doc_id, _doc_sha(drive, doc_id) or "")
            print(f"{step.action.value}: {doc_name(row)}  https://docs.google.com/document/d/{doc_id}/edit")
    save_state(data_dir, state)
    if not home.broadcasts:
        print(f"record BROADCASTS_FOLDER = \"{folder}\" in mystique/templates.py")
    return 0


def _format_docs(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    """Give every synced template Doc its header (template, subject, attachments) and placeholder highlights."""
    from jason.tasks.template_docs import format_doc, load_state

    state = load_state(_data_dir(args))
    with agent_factory(args) as agent:
        rows = {str(r["id"]): r for r in agent.payhoa().list_email_templates(agent.org_id)}
        docs = agent.drive().docs()
        for key, entry in state.items():
            row = rows.get(key)
            if row is None or not entry.get("docId"):
                continue
            if not args.yes:
                print(f"would format {entry['docId']} ({row.get('subject')})")
                continue
            print(f"formatted {row.get('subject')}: {format_doc(docs, entry['docId'], row)} changes")
    if not args.yes:
        print("dry run; --yes formats the Docs (header and highlights only; the body's text is not changed)")
    return 0


def _from_doc(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> tuple[Path, str, list[str]] | None:
    """Write a Doc's body as composer HTML; return the file, the subject, and the template's attachments."""
    from jason.google.docs_html import document_html
    from jason.tasks.template_docs import composer_html, load_state, subject_of

    data_dir = _data_dir(args)
    entry = next((e for e in load_state(data_dir).values() if e.get("docId") == args.from_doc), {})
    with agent_factory(args) as agent:
        doc = agent.drive().docs().get(args.from_doc)
    title = str(doc.get("title") or args.from_doc)
    body = composer_html(document_html(doc))
    slug = "-".join(re.findall(r"[a-z0-9]+", subject_of(title).casefold()))[:60] or args.from_doc
    dest = Path(args.file) if args.file else data_dir / "drafts" / f"{slug}.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(body + "\n", encoding="utf-8")
    print(f"wrote the Doc's body to {dest}")
    return dest, subject_of(title), [str(a["id"]) for a in entry.get("attachments") or []]


def _draft_doc(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    """Keep a local draft as a Google Doc (--to-doc) or bring a person's edits in the Doc back (--pull-doc), pictures
    included (``draft_docs``)."""
    from jason.community import community as active
    from jason.community.spec import spec_module
    from jason.tasks import draft_docs

    if not args.file:
        print("give the draft file (HTML)", file=sys.stderr)
        return 2
    draft = Path(args.file).resolve()
    state = draft_docs.load_state(draft.parent)
    entry = state.get(draft.name) or {}
    if draft.suffix.lower() == ".md":
        # a Markdown draft is the source: its Doc is set on the letterhead from it, and is not pulled back
        if args.pull_doc:
            print(f"{draft.name} is the source of its Doc: edit the Markdown, then --to-doc", file=sys.stderr)
            return 2
        title = f"Draft - {args.subject or entry.get('title', '').removeprefix('Draft - ') or draft.stem}"
        if not args.yes:
            print(f"would {'rewrite' if entry.get('docId') else 'make'} {title!r} on the letterhead from {draft.name}; "
                  "--yes does it")
            return 0
        from jason.community.profile import load_profile

        home, head = load_profile().drive_home(), load_profile().letterhead()
        with agent_factory(args) as agent:
            client = agent.payhoa()
            made = draft_docs.push_markdown(
                agent.drive(), draft, name=title, folder=home.broadcasts, letterhead_id=head.doc_id,
                footer=head.footer, state=state, articles=active().help_articles(),
                picture_link=lambda path: client.upload_file(path, filename=path.name, content_type="image/png",
                                                             context="communication")["viewUrl"])
        draft_docs.save_state(draft.parent, state)
        print(f"{title}: {made['url']}")
        return 0
    if args.pull_doc and not entry.get("docId"):
        print(f"{draft.name} has no Doc yet: --to-doc makes one", file=sys.stderr)
        return 2
    title = f"Draft - {args.subject or entry.get('title', '').removeprefix('Draft - ') or draft.stem}"
    if not args.yes:
        what = (f"would pull {entry.get('docId')} over {draft} (kept as .bak)" if args.pull_doc else
                f"would {'refresh' if entry.get('docId') else 'make'} the Doc \"{title}\" from {draft}"
                + (", replacing edits made in the Doc since (pull them first)" if entry.get("docId") else ""))
        print(what + "; --yes does it")
        return 0
    with agent_factory(args) as agent:
        drive = agent.drive()
        if args.pull_doc:
            import httpx

            token = drive._headers() if hasattr(drive, "_headers") else {}
            added = draft_docs.pull(drive, draft, state=state,
                                    fetch=lambda uri: httpx.get(uri, headers=token, timeout=60).content)
            print(f"pulled the Doc into {draft}" + (f"; pictures added in the Doc: {', '.join(added)}" if added else ""))
        else:
            client = agent.payhoa()
            from jason.community.profile import load_profile

            home, head = load_profile().drive_home(), load_profile().letterhead()
            doc_id = draft_docs.push(drive, draft, title=title, folder=home.broadcasts, state=state,
                                     picture_link=lambda path: client.upload_file(
                                         path, filename=path.name, content_type="image/png",
                                         context="communication")["viewUrl"])
            print(f"{title}: https://docs.google.com/document/d/{doc_id}/edit")
    draft_docs.save_state(draft.parent, state)
    return 0


def _list_tags(args: argparse.Namespace) -> int:
    from jason.tasks.broadcast import catalog_rows, unit_tags

    units, people, synced = catalog_rows(_data_dir(args) / "payhoa.db")
    if not units:
        print("no catalog; run jason sync-catalog", file=sys.stderr)
        return 1
    print(f"unit tags (catalog synced {synced[:10]}):")
    for name, count in unit_tags(units).items():
        print(f"  {name:28} {count:3} units")
    print("member tags:")
    for name, count in unit_tags(people).items():
        print(f"  {name:28} {count:3} members")
    return 0


def _show_recipients(args: argparse.Namespace):
    """Print who the tags reach; return the ``Recipients`` (None when a tag matches nothing or there is no catalog)."""
    import json

    from jason.tasks.broadcast import catalog_rows, recipients

    units, people, synced = catalog_rows(_data_dir(args) / "payhoa.db")
    if not units:
        print("no catalog; run jason sync-catalog", file=sys.stderr)
        return None
    found = recipients(units, people, tags=args.tag or [], member_tags=args.member_tag or [])
    if found.unknown_tags:
        print(f"no unit or member carries: {', '.join(found.unknown_tags)} (jason broadcast --tags)", file=sys.stderr)
        return None
    print(f"recipients (catalog synced {synced[:10]}; jason sync-catalog refreshes it): {len(found.unit_ids)} units, "
          f"{len(found.membership_ids)} members")
    if found.invalid_email:
        print(f"  {len(found.invalid_email)} of them have no deliverable email in PayHOA; mail them the notice")
    if found.other_tags:
        print("  their units also carry: " + ", ".join(f"{t} ({n})" for t, n in sorted(found.other_tags.items())))
    args.catalog_synced = synced
    if args.recipients_out:
        out = Path(args.recipients_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"unitTags": found.unit_tags, "memberTags": found.member_tags, "unitIds": found.unit_ids,
                                   "units": found.unit_labels, "membershipIds": found.membership_ids,
                                   "invalidEmail": found.invalid_email, "catalogSynced": synced}, indent=2), encoding="utf-8")
        print(f"  written to {out} (local only; it holds unit addresses)")
    return found


def cmd_broadcast(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.community import community as active
    from jason.community.library import LibraryDocument, payhoa_documents
    from jason.community.symbols import PayhoaFolder
    from jason.tasks.broadcast import (PREVIEW_PREFIX, Attachment, body_of, check, own_membership, preview_page,
                                       resolve_attachments, save_preview)

    if args.templates or args.template is not None:
        return _templates(args, agent_factory)
    if args.format_docs:
        return _format_docs(args, agent_factory)
    if args.sync_docs:
        return _sync_docs(args, agent_factory)
    if args.to_doc or args.pull_doc:
        return _draft_doc(args, agent_factory)
    if args.list_tags:
        return _list_tags(args)
    if (args.tag or args.member_tag) and not (args.file or args.from_doc):
        return 0 if _show_recipients(args) else 1
    if args.from_doc:
        made = _from_doc(args, agent_factory)
        if made is None:
            return 1
        args.file = str(made[0])
        args.subject = args.subject or made[1]
        # Saving a template keeps the attachments it has in PayHOA now; the sync state's list may be older.
        args.attach = args.attach if args.attach is not None else ([] if args.save_template is not None else made[2])
    if not args.file:
        print("give the message file (HTML), or --templates", file=sys.stderr)
        return 2
    source = Path(args.file)
    from jason.community.links import fill_help_tokens, linkify

    from jason.community.markdown_html import message_html_records

    if args.notice:
        from jason.tasks.notice_text import NoticeKeyError, check_key

        try:
            check_key(args.notice)
        except NoticeKeyError as exc:
            print(exc, file=sys.stderr)
            return 2
    filled, refs = message_html_records(source.read_text(encoding="utf-8"), source.suffix)
    message, no_help = fill_help_tokens(body_of(filled), active().help_articles())
    if no_help:
        print(f"no help article for {', '.join(no_help)} (mystique/help.py)", file=sys.stderr)
    message = linkify(message)                                          # citations, addresses, and emails as links
    if args.letterhead:
        from jason.community.email_html import with_letterhead

        letterhead = active().email_letterhead()
        message = with_letterhead(message, letterhead)
        print("letterhead: name banner and address footer" + (" with the logo" if letterhead.logo_url else
                                                               " (PayHOA's layout shows the logo above the message)"))
    from jason.community.email_html import email_tables

    message = email_tables(message)                  # last: mail clients keep inline table borders, not stylesheets
    subject = args.subject or ""
    attachments = resolve_attachments(args.attach or [], payhoa_documents(_data_dir(args) / "payhoa.db"))
    checked = check(message, subject)

    print(f"subject: {subject or '(none)'}")
    print(f"body: {checked.words} words, placeholders {checked.placeholders or 'none'}, {len(checked.links)} links")
    for a in attachments:
        print(f"attach: {a.spec} -> " + (f"#{a.id} {a.document.path}" + ("" if a.document.public is None else
              " (public)" if a.document.public else " (private)") if a.document else "NOT FOUND in the catalog"))
    uploads = [_upload_spec(p) for p in args.upload or []]
    for path, name in uploads:
        print(f"upload: {path} -> Email Attachments/{name}" + ("" if args.yes else " (dry run; --yes uploads)"))
        if not path.is_file():
            print(f"  missing file {path}", file=sys.stderr)
            return 1
    for problem in checked.problems:
        print(f"check: {problem}")
    found = None
    if args.tag or args.member_tag:
        found = _show_recipients(args)
        if found is None:
            return 1
    missing = [a.spec for a in attachments if a.document is None]
    if missing:
        print(f"attachments not found: {', '.join(missing)} (jason library --sync refreshes the catalog)", file=sys.stderr)
        return 1
    if args.critique:
        args.preview = True                          # the critique looks at PayHOA's own rendering
    keep = lambda state: _keep_notice(args, message, subject, refs, found, attachments, checked, state)  # noqa: E731
    composer = ("kept for a person to send from PayHOA's composer (jason does not send broadcasts); not a record that "
                "it was sent")
    if not (args.preview or args.send_sample or (uploads and args.yes) or args.save_template is not None):
        print("local check only; --preview renders it through PayHOA, --send-sample --yes emails you a test copy")
        if args.notice and keep(composer) is None:
            return 1
        return 1 if checked.problems else 0

    with agent_factory(args) as agent:
        client = agent.payhoa()
        org = agent.org_id
        if uploads and args.yes and args.save_template is None:
            folder = active().library_folder(PayhoaFolder.EMAIL_ATTACHMENTS)
            for path, name in uploads:
                row = client.create_document(org, folder.payhoa_id, path, file_name=name)
                doc = LibraryDocument("payhoa", str(row["id"]), str(row.get("path") or folder.path + name), name,
                                      folder.path, public=False)
                attachments.append(Attachment(str(path), doc))
                print(f"uploaded {name} as #{doc.id} ({doc.path})")
        me = args.me or own_membership(client.iter_people(org), client.user_id)
        if me is None:
            print("could not find your own membership; pass --me MEMBERSHIP_ID", file=sys.stderr)
            return 1
        sender = args.sender or client.reply_email(org)
        if args.preview:
            rendered = client.render_email_sample(org, me, message)
            dest = source.with_name(source.stem + ".preview.html")
            save_preview(dest, preview_page(subject, sender, rendered, attachments, checked))
            print(f"preview (rendered by PayHOA for membership {me}, not sent): {dest}")
            if args.critique:
                from jason.tasks.email_review import review

                from jason.tasks.email_review import WRAPPER_FILE

                logo = active().letterhead().logo_path(_data_dir(args))
                wrapper_file = _data_dir(args) / WRAPPER_FILE
                wrapper = wrapper_file.read_text(encoding="utf-8") if wrapper_file.is_file() else ""
                out, data = review(subject, rendered, source, logo=logo, model=args.model or "", wrapper=wrapper)
                print(f"critique ({len(data.get('suggestions') or [])} suggestions, local vision model): {out}")
        if args.send_sample:
            if not args.yes:
                print(f"would email a test copy to your own membership {me} from {sender}; --yes sends it")
            elif checked.problems:
                print("not sending a test copy until the checks pass", file=sys.stderr)
                return 1
            else:
                client.send_email_sample(org, me, message=message, subject=PREVIEW_PREFIX + subject, to=[me],
                                         from_email=sender or "", attachments=[a.id for a in attachments if a.id])
                print(f"sent a test copy to your own membership {me}")
        if args.save_template is not None:
            code = _save_template(args, agent, subject, message, uploads)
            if code == 0 and args.yes and args.notice:
                keep(f"saved as PayHOA template {args.save_template} for a person to send")
            return code
    if args.notice and keep(composer) is None:
        return 1
    print("jason does not send broadcasts: send it from PayHOA's composer")
    return 0


def _keep_notice(args: argparse.Namespace, message: str, subject: str, refs: list[Any], found: Any,
                 attachments: list[Any], checked: Any, state: str) -> dict[str, Any] | None:
    """--notice KEY: keep the words as rendered in data/notices/KEY/ (jason.tasks.notice_text), only with --yes and
    only when the checks pass; a dry run says what it would keep. None when the checks stop it."""
    from jason.tasks.broadcast import keep_notice

    where = _data_dir(args) / "notices" / args.notice
    if checked.problems:
        print(f"not keeping the notice's text until the checks pass ({where})", file=sys.stderr)
        return None
    if not args.yes:
        print(f"would keep the text as rendered, its subject, {len(refs)} fill records"
              + (", and the recipients plan" if found is not None else "") + f" in {where} (--yes keeps them)")
        return {}
    # The message as written in the PayHOA layout jason hands over; PayHOA fills each member's placeholders.
    entry = keep_notice(_data_dir(args), args.notice, message=message, subject=subject, refs=refs, found=found,
                        synced=getattr(args, "catalog_synced", ""), state=state, by=args.by or "",
                        attachments=attachments, source=str(args.file))
    print(f"kept the notice's text in {where} (sha256 {entry['files'][0]['sha256'][:16]}): {state}")
    return entry


def _save_template(args: argparse.Namespace, agent: Any, subject: str, message: str, uploads: list[tuple[Path, str]]) -> int:
    """Replace a PayHOA template's subject, body, and attachments (``PUT /email-templates/{id}``), with --yes. A
    template may keep [FIELDS] for the person who uses it; nothing is sent.

    A save keeps only the files sent in ``attachments``, each a fresh upload (``context=communication``): the template's
    current attachments are dropped (seen October 1, 2026, when an org-file id in ``attachmentIds`` did not keep one). So
    each file the template should carry is given again with --upload, and a template that has attachments is not saved
    without them unless --drop-attachments says so."""
    client, org = agent.payhoa(), agent.org_id
    rows = client.list_email_templates(org)
    current = next((r for r in rows if r.get("id") == args.save_template), None)
    if current is None:
        print(f"no template {args.save_template}", file=sys.stderr)
        return 1
    have = [str(a.get("fileName")) for a in current.get("attachments") or []]
    subject = subject or str(current.get("subject") or "")
    from jason.community import community as active
    from jason.community.email_html import strip_letterhead, with_letterhead

    letterhead = active().email_letterhead()
    if letterhead and strip_letterhead(str(current.get("message") or ""), letterhead)[1] and not args.letterhead:
        message = with_letterhead(message, letterhead)          # the template had the frame; keep it
        print("keeping the letterhead frame the template has")
    print(f"template {args.save_template}: subject {subject!r}; attachments now {have or 'none'}; "
          f"after saving {[name for _, name in uploads] or 'none'}")
    if have and not uploads and not args.drop_attachments:
        print("a save drops the template's attachments: give each again with --upload PDF=Name.pdf, or pass "
              "--drop-attachments", file=sys.stderr)
        return 1
    if not args.yes:
        print("dry run; --yes saves the template in PayHOA")
        return 0
    files = []
    for path, name in uploads:
        files.append(int(client.upload_file(path, filename=name, content_type="application/pdf", context="communication")["id"]))
    saved = client.update_email_template(org, args.save_template, subject=subject, message=message, attachments=files)
    after = [str(a.get("fileName")) for a in saved.get("attachments") or []]
    print(f"saved template {args.save_template} (updated {saved.get('updatedAt')}); attachments {after or 'none'}")
    if len(after) != len(files):
        print("  PayHOA's attachments differ from the uploads; check the template in PayHOA", file=sys.stderr)
    if args.from_doc:
        from jason.tasks.template_docs import load_state, record, save_state

        data_dir = _data_dir(args)
        state = load_state(data_dir)
        with_doc = _doc_sha(agent.drive(), args.from_doc)
        state[str(args.save_template)] = record(saved, args.from_doc, with_doc or "")
        save_state(data_dir, state)
        print("  the Doc and the template are in step again (template-docs.json)")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("broadcast", help="Check and preview a PayHOA broadcast drafted on disk (never sends to members)")
    add_common(p)
    p.add_argument("file", nargs="?", help="the message body (HTML, as PayHOA's composer writes it)")
    p.add_argument("--subject", help="the broadcast's subject")
    p.add_argument("--attach", action="append", metavar="ID|PATH",
                   help="a PayHOA library file by id, library path, or unique file name (repeatable)")
    p.add_argument("--upload", action="append", metavar="PDF",
                   help="upload a local PDF (PATH or PATH=Name.pdf) to the private Email Attachments folder and attach it (needs --yes)")
    p.add_argument("--preview", action="store_true", help="render through PayHOA for your own membership; writes FILE.preview.html")
    p.add_argument("--send-sample", action="store_true", help="email a test copy to your own membership (needs --yes)")
    p.add_argument("--sender", metavar="EMAIL", help="the From address (default: PayHOA's reply-to address)")
    p.add_argument("--me", type=int, metavar="MEMBERSHIP_ID", help="your own membership id, if jason cannot find it")
    p.add_argument("--save-template", type=int, metavar="ID",
                   help="replace this PayHOA template's subject and body with the file's; give its attachments again with "
                        "--upload (a save drops the old ones) (needs --yes)")
    p.add_argument("--drop-attachments", action="store_true", help="with --save-template: save without attachments")
    p.add_argument("--critique", action="store_true",
                   help="screenshot PayHOA's rendering (desktop and phone) and ask the local vision model how it looks")
    p.add_argument("--model", help="with --critique: the local vision model (default qwen3.6:27b)")
    p.add_argument("--letterhead", action="store_true",
                   help="frame the body with the letterhead (centered logo and name, address footer) for --preview, "
                        "--send-sample, and --save-template")
    p.add_argument("--format-docs", action="store_true",
                   help="give the template Docs a header (template, subject, attachments) and highlight placeholders (--yes)")
    p.add_argument("--tags", dest="list_tags", action="store_true", help="list the unit and member tags in the catalog")
    p.add_argument("--tag", action="append", metavar="NAME",
                   help="send to the owners of units with this tag, e.g. 'Building 3' (repeatable; read from the catalog)")
    p.add_argument("--member-tag", action="append", metavar="NAME", help="send to members with this tag, e.g. 'Board Member'")
    p.add_argument("--recipients-out", metavar="JSON", help="write the resolved unit and membership ids here")
    p.add_argument("--templates", action="store_true", help="list PayHOA's saved broadcast templates")
    p.add_argument("--template", type=int, metavar="ID", help="print one template (with --save, write its body to a file)")
    p.add_argument("--save", metavar="PATH", help="with --template: write the template's HTML here to edit")
    p.add_argument("--sync-docs", action="store_true",
                   help="keep each PayHOA template as a Google Doc in My Drive/Templates/PayHOA Broadcasts (--yes writes)")
    p.add_argument("--to-doc", action="store_true",
                   help="make or refresh FILE's Google Doc (pictures included) in My Drive/Templates/PayHOA Broadcasts "
                        "(--yes writes; replaces edits made in the Doc since)")
    p.add_argument("--pull-doc", action="store_true",
                   help="write FILE's Google Doc back over FILE, pictures included (--yes writes; the old file kept as .bak)")
    p.add_argument("--from-doc", metavar="DOC_ID",
                   help="turn a Doc into the body (written to FILE or data/drafts/), then check it as usual")
    p.add_argument("--notice", metavar="KEY",
                   help="the notice's ledger key (it starts with the requirement's key: board-meeting-2099-01-14); with "
                        "--yes, keep the text as rendered, its subject, fill records, and recipients plan in "
                        "data/notices/KEY/ once it is saved for sending (--save-template) or handed to the composer")
    p.add_argument("--by", metavar="NAME", help="with --notice: who saved it for sending")
    p.add_argument("--yes", action="store_true", help="write the Docs, upload, and send the test copy (default: dry run)")
    p.set_defaults(func=lambda a: cmd_broadcast(a, agent_factory))
