"""Proposed changes to the association's operating rules (Civil Code 4340-4370), as data.

Each row is a ``RuleChange``: the rule it amends (an outline key in ``outlines.py``), the proposed words section by
section, the purpose and effect a member notice must describe, and what the board and counsel must decide first.
The current words are read from ``data/outlines/<document>.json`` when ``jason rule-change`` builds the notice; they
are not copied here. A ``[bracket]`` in proposed text is the board's choice, never jason's. These are DRAFTS for the
board and counsel: nothing here is adopted until the board decides it at a meeting.
"""

from __future__ import annotations

from datetime import date

from jason.community.record_stages import Outcome, RuleChangeRecord
from jason.community.rule_changes import RuleChange, SectionChange

# PayHOA is retiring the deposit lockbox (P.O. Box 981506, West Sacramento) that receives members' mailed checks. At the
# August 18, 2026 meeting the board discussed no longer accepting paper checks; the Secretary said the Assessment
# Collection Policy would have to change, with 28 days' notice to the members first (transcript 0:15:42 to 0:18:44).
COLLECTION_POLICY_PAYMENTS = RuleChange(
    key="collection-policy-payments",
    title="Assessment Collection Policy: payment methods after the lockbox closes",
    document="collection-policy",
    document_title="Assessment Collection Policy",
    purpose=(
        "PayHOA, the Association's payment processor and designated agent, is retiring the lockbox service that "
        "receives mailed checks at P.O. Box 981506, West Sacramento. Without the lockbox the Association has no "
        "service to receive, deposit, and credit paper checks to owners' accounts. The proposed change says how "
        "assessments are paid after the lockbox closes, what happens to a paper check received after that date, how "
        "long the transition lasts, and that a returned electronic payment is treated like a dishonored check."
    ),
    effect=(
        "Owners who now mail checks would pay through the Association's online payment portal (electronic check from "
        "a bank account, automatic recurring payment, or card, as the portal offers) beginning on [effective date]. "
        "A paper check received after that date would be handled as Section 20(b) provides. The charge for a "
        "dishonored check would also apply to a returned or reversed electronic or card payment. The Association "
        "would keep a mailing address for overnight payment of assessments, as Civil Code section 5655(c) requires. "
        "Nothing else in the policy changes: due dates, the delinquency date, late charges, interest, collection "
        "costs, receipts, payment plans, and the lien and foreclosure procedures stay as they are."
    ),
    sections=(
        SectionChange(
            "10", "Notice of Intent to Lien.",
            strike="Payment may be required in certified funds.",
            proposed=("Payment may be required in immediately available funds by a method accepted under Section 20 "
                      "that cannot be reversed for insufficient funds [such as a debit card payment, or a cashier's "
                      "check delivered to the overnight payment address]."),
            note="Certified funds are a paper instrument; the lockbox that would receive one is closing.",
        ),
        SectionChange(
            "14", "Returned or Dishonored Payments.",
            proposed=(
                "At any time that the Association or its agent receives a payment that is returned, reversed, or "
                "dishonored for any reason, including a paper check dishonored by the bank and an electronic check "
                "(ACH) or card payment returned for insufficient funds, a closed account, or a stop-payment, a charge "
                "of [returned payment charge, currently $25 for a dishonored check] shall be imposed. For a "
                "dishonored paper check, the Association may also seek damages in accordance with California Civil "
                "Code section 1719. After [number] returned payments within [period], the Association may require "
                "future payments to be made by a method that cannot be reversed for insufficient funds."
            ),
            note="Retitled from \"Dishonored Checks.\" An ACH return or card chargeback is not a check; Civil Code 1719 "
                 "speaks of checks, so its damages stay limited to paper checks.",
        ),
        SectionChange(
            "18(18)(c)", "Dispute of Charges, item (c).",
            strike="dates, names and check numbers",
            proposed="dates, names, check numbers, and payment confirmation numbers",
            note="Conforming: an online payment has a confirmation number, not a check number.",
        ),
        SectionChange(
            "18(18)(d)", "Dispute of Charges, item (d).",
            strike="Copies of checks, letters,",
            proposed="Copies of checks, payment confirmations, letters,",
            note="Conforming.",
        ),
        SectionChange(
            "20", "Methods of Payment; Address of the Association.",
            proposed=(
                "(a) Accepted methods. Beginning on [effective date], assessments and other charges shall be paid "
                "through the Association's online payment portal maintained by its designated agent, by any method "
                "the portal offers, which may include an electronic check (ACH) from a bank account, an automatic "
                "recurring payment, and a debit or credit card. Any processing fee the portal charges for a method is "
                "shown in the portal before the owner pays and is paid by [the owner / the Association]. [At least "
                "one method shall carry no processing fee to the owner.] An owner who cannot use the portal may "
                "contact the Association or its designated agent for [assisted payment option], and the Association "
                "will consider a reasonable accommodation on request.\n\n"
                "(b) Paper checks. The lockbox service that received mailed checks closes on [lockbox closing date]. "
                "A paper check the Association receives on or after [effective date] and before [transition end "
                "date] will be [deposited and credited, and the owner sent the accepted payment methods / returned "
                "to the owner uncashed with the accepted payment methods]. A paper check received on or after "
                "[transition end date] will be returned to the owner uncashed with the accepted payment methods. A "
                "returned check is not a payment; the assessment it was meant to pay is delinquent as provided in "
                "Section 5 unless it is paid by an accepted method. [No late charge will be imposed on an installment "
                "whose check is returned under this subsection if it is paid by an accepted method within [number] "
                "days after the check is returned.] Owners who pay through a bank's online bill-pay service should "
                "know that many such services mail a paper check, which is handled under this subsection.\n\n"
                "(c) Overnight payments. As Civil Code section 5655(c) requires, the Association provides the "
                "following mailing address for overnight payment of assessments: [overnight payment address]. "
                "[How a payment delivered to this address is accepted and credited, as counsel advises.]\n\n"
                "(d) Other mail. All other mail should be sent to: Mystique Community Association, [mailing address]."
            ),
            note=("The Drive copy and the Google Doc name the lockbox (P.O. Box 981506). The copy printed in the "
                  "2025-26 Annual Disclosures already reads differently: payments \"to the address directed by the "
                  "designated agent\", else 901 H St Ste 120 PMB 188, which it also gives for overnight payments. "
                  "Sections 1-19 and 21 are the same in both."),
        ),
    ),
    decisions=(
        "[effective date] and [lockbox closing date]: the date PayHOA stops the lockbox, and the date checks stop being accepted.",
        "[transition end date] and Section 20(b)'s choice for checks received in the transition: deposit and credit, or return uncashed.",
        "Whether to waive the late charge on an installment whose check is returned in the transition, and within [number] days.",
        "[returned payment charge]: the amount (the policy and the Annual Disclosures fee schedule say $25 for a returned check), "
        "and whether it applies to ACH returns and card chargebacks.",
        "Who pays the portal's processing fees, and whether at least one method must be free to the owner (counsel).",
        "[assisted payment option] for owners without internet access, and accommodations on request.",
        "[overnight payment address] under Civil Code 5655(c), and whether the Association may decline a check delivered there (counsel).",
        "[mailing address]: 901 H St Ste 120, or 901 H St Ste 120 PMB 188 as the 2025-26 Annual Disclosures print it.",
        "Which text of Section 20 is current: the Drive copy (lockbox) or the 2025-26 Annual Disclosures (address directed by the agent).",
        "Whether Civil Code 4360 binds this change: 4355(a) lists the subjects 4360 and 4365 apply to, and payment methods "
        "are not plainly among them. The Secretary asked for 28 days' notice; following 4360 is the safe course (counsel).",
        "Updating the annual policy statement (Civil Code 5310(a)(6), (7), (11)) and the Annual Disclosures' payment and fee pages.",
    ),
    caveats=(
        "DRAFT for the board and counsel. It is not legal advice and not a decision; the board decides at a meeting.",
        "Proposed wording is generic about PayHOA's options: the portal's own list of methods and fees governs.",
    ),
    authorities=("CIV 4340", "CIV 4355", "CIV 4360", "CIV 4365", "CIV 4041", "CIV 4045", "CIV 4920", "CIV 4925", "CIV 5310",
                 "CIV 5655", "CIV 5730"),
)

RULE_CHANGES: tuple[RuleChange, ...] = (COLLECTION_POLICY_PAYMENTS,)


# The association's own rule changes, made or proposed, whose stages ``jason record-stages`` reads from disk (Civil Code
# 4360). ``files`` matches each change's own notices and text by name on Drive and in the library; ``decided`` is the
# meeting whose minutes record the decision. The draft above (COLLECTION_POLICY_PAYMENTS) is read from the
# specification and needs no row until it is noticed.
RULE_CHANGE_RECORDS: tuple[RuleChangeRecord, ...] = (
    RuleChangeRecord(
        key="parking-fines-2022", title="Rules B-7 and B-12, and the fine schedule", document="owners-manual",
        document_title="Owner's Manual and Rules",
        files=r"^Notice of (Proposed|Adopted) (Rule )?Changes? B-7, B-12",
        words=("adopted the proposed rule changes", "B-7, B-12"),
        decided=date(2022, 8, 30),
        note="The minutes of 2022-08-30 record the adoption \"after ... discussion and comments from members\"; the "
             "fine schedule was adopted as amended at that meeting."),
    RuleChangeRecord(
        key="election-rules-2022", title="Election rules revised to conform to SB 323", document="election-rules",
        document_title="Election Rules",
        files=r"SB 323 Election Rules|Notice to Owners re Amendment to CCRs and Election Rules",
        words=("revised election rules", "SB 323 Election Rules"),
        decided=date(2022, 10, 24), notices=r"Notice to Owners re Amendment",
        note="Made \"to conform with new legislation, SB323\": whether the change was one the law required with no "
             "discretion (4355(b)(4), no 28-day notice) is for counsel. The notice to owners of 9/7/22 also covered a "
             "CC&R amendment."),
    RuleChangeRecord(
        key="owners-manual-2023", title="Owner's Manual and Rules (B-1 and others) and the Assessment Collection Policy",
        document="owners-manual", document_title="Owner's Manual and Rules",
        files=r"^Notice of Proposed Rule Changes?( B-1)?(\.pdf|\.docx)?$|^Notice of Adopted Rule Change( \d{6}\.pdf)?$",
        words=("Adoption of Proposed Rule Changes",),
        decided=date(2023, 4, 18),
        note="Whether the Assessment Collection Policy is a rule on a 4355(a) subject (payment plans, (a)(4)) is for "
             "counsel; it was noticed and adopted with the Owner's Manual."),
    RuleChangeRecord(
        key="election-rules-electronic-voting", title="Election Rules: electronic voting (AB 2159)",
        document="election-rules", document_title="Election Rules",
        files=r"^Notice of Proposed Rule Change - Electronic Voting",
        words=("Electronic Voting",),
        outcome=Outcome.PENDING, tasks=r"election rules",
        note="The proposed text is in the Election Rules Doc (outline key election-rules), which has changed since; its "
             "words at the notice are not kept apart. The minutes of 2024-12-17 record that the board would like to "
             "propose electronic voting rules."),
)

__all__ = ["COLLECTION_POLICY_PAYMENTS", "RULE_CHANGES", "RULE_CHANGE_RECORDS"]
