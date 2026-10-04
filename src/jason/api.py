"""jason's programmatic interface: the same functions ``jason-mcp`` serves, for Python callers.

Each returns a JSON-ready dict, reads the stores on disk, and decides nothing for the board. The three that write
(``answer_intake_question``, ``onboarding_confirm``, ``record_completion``) write only a person's record to ``data/``
and require ``by``.

    from jason import api

    api.governance_digest()["sections"]          # what needs attention, most urgent first
    api.member_requests(open_only=True)["requests"]
    api.living_document("ccrs", section="6.2(a)")["section"]["words"]
    api.document_conflicts(leads=True, since="2026-01-01")
    api.schedule_agenda(days=30, role="treasurer")
    api.answer_intake_question("c552e5c7c1", "contract", by="A Person")
    api.cite_document("Section 6.2(a) of the Declaration")["text"]     # the words, with the citation
    api.section_refs("Declaration 6.2(a)", hops=2, direction="both")
    api.read_record("jason://decl/6.2(a)")["text"]     # the MCP resource's Markdown: the recitation first
    api.record_resources()                              # what jason-mcp lists as resources

The MCP server's other tools (the PayHOA catalog, deeds, liens, finance, mail, meetings, the law) are importable from
``jason.mcp.county``, ``jason.mcp.index``, and ``jason.mcp.rolls`` the same way. ``docs/mcp.md`` lists every tool.
"""

from __future__ import annotations

from jason.mcp.governance import (
    TOOLS,
    acknowledgment_draft,
    approval_show,
    approvals_list,
    answer_intake_question,
    cite_document,
    document_conflicts,
    document_duties,
    embedded_copies,
    evidence,
    governance_digest,
    intake_questions,
    living_document,
    member_requests,
    next_questions,
    notice_delivery,
    notice_requirements,
    onboarding_confirm,
    onboarding_status,
    record_completion,
    request_kinds_measure,
    schedule_agenda,
    schedule_assignments,
    section_refs,
)



def record_resources(data_dir=None) -> list[dict]:
    """The record addresses ``jason-mcp`` lists as resources (``jason.mcp.resources.listing``): every book (a
    restricted one by name only), each part, and each living book's top-level articles or sections, capped."""
    from jason.mcp.resources import listing

    return listing(data_dir=data_dir)


def read_record(address: str, data_dir=None) -> dict:
    """One ``jason://`` address as the MCP resource reads it: ``{found, address, title, text (Markdown: the
    recitation first), lastModified}``, or ``{found: False, reason, detail}`` for a miss (a restricted book is
    ``restricted``; ``jason cite --private`` reads one locally)."""
    from jason.mcp.resources import AddressNotFound, read

    try:
        page = read(address, data_dir=data_dir)
    except AddressNotFound as exc:
        return {"found": False, "address": exc.address, "reason": exc.reason, "detail": exc.detail}
    return {"found": True, "address": page.address, "title": page.title, "text": page.text,
            "lastModified": page.last_modified}


__all__ = [t.__name__ for t in TOOLS] + ["read_record", "record_resources"]
