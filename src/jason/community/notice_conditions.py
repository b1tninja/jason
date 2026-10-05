"""When the law requires a notice, or one of its elements: the conditions the notice catalog turns on, as data.

A ``NoticeRequirement`` (``jason.community.notice_catalog``) is required only for some events, and a ``Sign``
(``jason.community.notice_elements``) is an element only some notices need. Each such row carries one of the
conditions below as its ``applies``. A condition is written from the section's own words, quoted beside it, over the
event facet's closed sets (``jason.community.applicability``). Nothing is encoded that the words leave open: a row
whose section does not settle when it is required keeps its prose ``note`` and no condition.

Two kinds of fact decide them (``Fact.standing``):

- one event's facts (what the election decides, whether the rule change is an emergency one, how the meeting is
  held), which the caller that knows the event says;
- the association's standing facts (whether an election rule allows electronic secret ballots, whether the documents
  require a quorum for an election of directors, whether the association keeps acclamation available), which the
  profile states and, where it does not, a person is asked (``jason applies --questions``).

With no facts every condition is undetermined, which is never read as "not required". Pure: conditions only.
"""

from __future__ import annotations

from jason.community.applicability import (Acclamation, AllOf, BoardMeetingKind, Condition, DirectorQuorum,
                                           ElectionKind, ElectronicVoting, Except, Fact, In, Is, MeetingFormat,
                                           RuleChangeKind, RuleScope)

# --- Rule changes (Civil Code 4355, 4360, 4365) --------------------------------------------------------------------

# 4360(d): "it may make an emergency rule change, and no notice is required, as specified in subdivision (a)".
EMERGENCY_RULE_CHANGE: Condition = Is(Fact.RULE_CHANGE, RuleChangeKind.EMERGENCY)

# 4355(a): "Sections 4360 and 4365 only apply to an operating rule that relates to one or more of the following
# subjects"; 4355(b): "Sections 4360 and 4365 do not apply to the following actions by the board". Which side a rule
# change falls on is said by the caller; jason does not read it from the rule's words.
LISTED_RULE_CHANGE: Condition = Is(Fact.RULE_SCOPE, RuleScope.LISTED_SUBJECT)

# 4360(a): "Notice is not required under this subdivision if the board determines that an immediate rule change is
# necessary to address an imminent threat to public health or safety or imminent risk of substantial economic loss to
# the association." 4365(h): "This section does not apply to an emergency rule change made under subdivision (d) of
# Section 4360."
LISTED_RULE_CHANGE_NOT_EMERGENCY: Condition = Except(LISTED_RULE_CHANGE, EMERGENCY_RULE_CHANGE)

# --- Board meetings (Civil Code 4920, 4926) ------------------------------------------------------------------------

# 4920(a): "Except as provided in subdivision (b), the association shall give notice of the time and place of a board
# meeting at least four days before the meeting."
ORDINARY_BOARD_MEETING: Condition = Is(Fact.BOARD_MEETING, BoardMeetingKind.ORDINARY)

# 4920(b)(2): "If a nonemergency board meeting is held solely in executive session, the association shall give notice
# of the time and place of the meeting at least two days prior to the meeting."
EXECUTIVE_SESSION_ONLY_MEETING: Condition = Is(Fact.BOARD_MEETING, BoardMeetingKind.EXECUTIVE_SESSION_ONLY)

# 4920(b)(1): "If a board meeting is an emergency meeting held pursuant to Section 4923, the association is not
# required to give notice of the time and place of the meeting."
EMERGENCY_BOARD_MEETING: Condition = Is(Fact.BOARD_MEETING, BoardMeetingKind.EMERGENCY)

# 4926(a): "conducted entirely by teleconference, without any physical location being held open"; 4926(a)(1): "The
# notice for each meeting conducted under this section includes, in addition to other required content".
ENTIRELY_BY_TELECONFERENCE: Condition = Is(Fact.MEETING_FORMAT, MeetingFormat.ENTIRELY_BY_TELECONFERENCE)

# --- Elections (Civil Code 5103, 5105, 5115) -----------------------------------------------------------------------

# 5115(a): "This subdivision shall only apply to elections of directors and to recall elections." 5115(b): "For
# elections of directors and for recall elections, an association shall provide general notice of all of the
# following".
DIRECTOR_OR_RECALL_ELECTION: Condition = In(Fact.ELECTION, frozenset({ElectionKind.DIRECTORS, ElectionKind.RECALL}),
                                            "an election of directors or a recall election (5115(a), (b))")

# 5115(d)(2): "For an election of directors of an association, and in the absence of meeting a quorum ... the
# association may adjourn the meeting"; 5115(d)(3): "the reconvened meeting described in paragraph (2)".
DIRECTOR_ELECTION: Condition = Is(Fact.ELECTION, ElectionKind.DIRECTORS)

# 5115(g)(1): "in an election to approve an amendment of the governing documents, the text of the proposed amendment
# shall be delivered to the members with the ballot."
AMENDMENT_ELECTION: Condition = Is(Fact.ELECTION, ElectionKind.AMENDMENT)

# 5103: "the association may, but is not required to, consider the qualified candidates elected by acclamation if all
# of the following conditions have been met", among them the initial notice (b)(1), the reminder (b)(2), and the
# acknowledgments (c). The notices are conditions of acclamation, so they are required of an association that keeps
# it available. The election is one that fills seats on the board: 5103(b)(1)(A), "The number of board positions that
# will be filled at the election."
ACCLAMATION_KEPT_AVAILABLE: Condition = AllOf(DIRECTOR_ELECTION, Is(Fact.ACCLAMATION, Acclamation.AVAILABLE))

# 5105(i): "the association may adopt an election operating rule that allows an association ... to conduct an election
# by electronic secret ballot"; 5115(b)(2): "If the association allows for voting in an election by electronic secret
# ballot as provided for in Section 5105".
ELECTRONIC_VOTING_USED: Condition = In(Fact.ELECTRONIC_VOTING,
                                       frozenset({ElectronicVoting.OPT_OUT, ElectronicVoting.OPT_IN}),
                                       "used under an election operating rule (5105(i))")

# 5105(i)(3)(A): "The association shall deliver individual notice of the electronic secret ballot to each member 30
# days before the election". 5105(i): "except for an election regarding regular or special assessments".
ELECTRONIC_SECRET_BALLOT: Condition = Except(ELECTRONIC_VOTING_USED, Is(Fact.ELECTION, ElectionKind.ASSESSMENT))

# 5105(i)(4): "For an election operating rule where members are permitted to opt out of voting by electronic secret
# ballot to vote by written ballot, the association shall provide individual notice".
ELECTRONIC_VOTING_OPT_OUT: Condition = Is(Fact.ELECTRONIC_VOTING, ElectronicVoting.OPT_OUT)

# 5115(b)(6)(A): "If the association's governing documents require a quorum for an election of directors, a statement
# that the association may call a reconvened meeting"; (B): "This paragraph shall not apply if the governing documents
# of the association provide for a quorum lower than 20 percent."
DIRECTOR_QUORUM_STATEMENT: Condition = Except(
    In(Fact.DIRECTOR_QUORUM, frozenset({DirectorQuorum.AT_LEAST_20_PERCENT, DirectorQuorum.BELOW_20_PERCENT}),
       "required (5115(b)(6)(A))"),
    Is(Fact.DIRECTOR_QUORUM, DirectorQuorum.BELOW_20_PERCENT))


# The facts of one kind of event. A caller that says one of a group is describing that kind of event, so a row that
# turns on another fact of the group is about the same event and is asked (it comes back undetermined, with the fact
# to say). A row that turns only on another group's facts is about another kind of event.
SAME_EVENT: tuple[frozenset[Fact], ...] = (
    frozenset({Fact.MEETING_FORMAT, Fact.BOARD_MEETING}),
    frozenset({Fact.RULE_CHANGE, Fact.RULE_SCOPE}),
    frozenset({Fact.ELECTION}),
)
assert frozenset().union(*SAME_EVENT) == frozenset(f for f in Fact if f.per_event)


def same_event(said: frozenset[Fact]) -> frozenset[Fact]:
    """The facts said, with the other facts of each kind of event they describe."""
    return frozenset(said).union(*(group for group in SAME_EVENT if group & said))


__all__ = [
    "SAME_EVENT", "same_event",
    "EMERGENCY_RULE_CHANGE", "LISTED_RULE_CHANGE", "LISTED_RULE_CHANGE_NOT_EMERGENCY", "ORDINARY_BOARD_MEETING",
    "EXECUTIVE_SESSION_ONLY_MEETING", "EMERGENCY_BOARD_MEETING", "ENTIRELY_BY_TELECONFERENCE",
    "DIRECTOR_OR_RECALL_ELECTION", "DIRECTOR_ELECTION", "AMENDMENT_ELECTION", "ACCLAMATION_KEPT_AVAILABLE",
    "ELECTRONIC_VOTING_USED", "ELECTRONIC_SECRET_BALLOT", "ELECTRONIC_VOTING_OPT_OUT", "DIRECTOR_QUORUM_STATEMENT",
]
