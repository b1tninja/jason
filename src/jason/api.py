"""jason's programmatic interface: the same functions ``jason-mcp`` serves, for Python callers.

Each returns a JSON-ready dict, reads the stores on disk, and decides nothing for the board. The two that write
(``answer_intake_question``, ``record_completion``) write only a person's record to ``data/`` and require ``by``.

    from jason import api

    api.governance_digest()["sections"]          # what needs attention, most urgent first
    api.member_requests(open_only=True)["requests"]
    api.living_document("ccrs", section="6.2(a)")["section"]["words"]
    api.document_conflicts(leads=True, since="2026-01-01")
    api.schedule_agenda(days=30, role="treasurer")
    api.answer_intake_question("c552e5c7c1", "contract", by="A Person")
    api.cite_document("Section 6.2(a) of the Declaration")["text"]     # the words, with the citation
    api.section_refs("Declaration 6.2(a)", hops=2, direction="both")

The MCP server's other tools (the PayHOA catalog, deeds, liens, finance, mail, meetings, the law) are importable from
``jason.mcp.county``, ``jason.mcp.index``, and ``jason.mcp.rolls`` the same way. ``docs/mcp.md`` lists every tool.
"""

from __future__ import annotations

from jason.mcp.governance import (
    TOOLS,
    acknowledgment_draft,
    answer_intake_question,
    cite_document,
    document_conflicts,
    document_duties,
    embedded_copies,
    governance_digest,
    intake_questions,
    living_document,
    member_requests,
    notice_delivery,
    notice_requirements,
    record_completion,
    request_kinds_measure,
    schedule_agenda,
    schedule_assignments,
    section_refs,
)

__all__ = [t.__name__ for t in TOOLS]
