"""Mystique's response clocks: the governing documents' own, and policies jason proposes where they are silent.

The statute's clocks are jason's (``jason.community.responses.RESPONSE_RULES``). These add what the CC&Rs and bylaws
set (a rental application within 30 days, a variance hearing within 45, a hearing after emergency action within 30),
and, marked ``POLICY``, the clocks jason proposes for the kinds no law or document times (maintenance, questions,
complaints, internal dispute resolution). A proposed clock is the board's to adopt; until then it is a target, not a
rule. The architectural procedure is a gap the law requires filled: Civil Code 4765(a) has the documents state the
maximum time for a response, and they state none.
"""

from __future__ import annotations

from jason.community.responses import ClockSource, ResponseKind, ResponseRule

RESPONSE_RULES = (
    ResponseRule(ResponseKind.RENTAL, ClockSource.DOCUMENTS, days=30, authority="CC&Rs 4.15(e)",
                 assignment="rentals", first_step="The board reviews the application at its next meeting; the cap is "
                 "25 percent (4.15(a) as amended).", acknowledge_days=2),
    ResponseRule(ResponseKind.VARIANCE, ClockSource.DOCUMENTS, days=45, authority="CC&Rs 4.20",
                 assignment="hearings", first_step="Notice the variance hearing to all members at least 15 days before; "
                 "decide and notify the applicant within 30 days of the decision."),
    ResponseRule(ResponseKind.HEARING_REQUEST, ClockSource.DOCUMENTS, days=30, authority="Bylaws 8.5(e)(ii)",
                 assignment="hearings", first_step="Schedule the hearing (jason hearing) with 10 days' notice (5855)."),
    ResponseRule(ResponseKind.ARCHITECTURAL, ClockSource.POLICY, days=30, authority="proposed policy; CIV 4765(a) "
                 "requires the documents to state the maximum time, and they state none",
                 assignment="architecture", first_step="Put it on the next board agenda; the decision in writing, with "
                 "the reasons and the reconsideration procedure for a denial (4765(a)(4), (5)).", acknowledge_days=2,
                 note="Adopting the time is an architectural-review rule: 28 days' notice (4355(a)(5), 4360)."),
    ResponseRule(ResponseKind.MAINTENANCE, ClockSource.POLICY, days=10, business_days=True,
                 authority="proposed policy", assignment="maintenance",
                 first_step="Triage: an emergency at once; else inspect or send to the vendor and tell the owner the plan.",
                 acknowledge_days=2),
    ResponseRule(ResponseKind.DISPUTE, ClockSource.POLICY, days=30, authority="proposed policy; CIV 5915 sets no time",
                 assignment="disputes", first_step="Name the director to meet and confer, and offer dates.",
                 acknowledge_days=2),
    ResponseRule(ResponseKind.COMPLAINT, ClockSource.POLICY, days=10, business_days=True,
                 authority="proposed policy", assignment="hearings",
                 first_step="Acknowledge; check the governing documents and precedents (jason case / email_intents); "
                 "a courtesy notice or a hearing is the board's decision.", acknowledge_days=2),
    ResponseRule(ResponseKind.QUESTION, ClockSource.POLICY, days=10, business_days=True,
                 authority="proposed policy", assignment="records-requests",
                 first_step="Answer from the documents, citing them; a question for the board goes on the agenda.",
                 acknowledge_days=2),
    ResponseRule(ResponseKind.OTHER, ClockSource.POLICY, days=10, business_days=True, authority="proposed policy",
                 assignment="records-requests", first_step="Read it and classify it; then its kind's clock applies.",
                 acknowledge_days=2),
)
