"""The base prompt: how a professional community manager reads for a task, and what each task adds.

A model (or a person, or another agent) given a task gets three things:

- the base prompt below, the same for every task: the role, working out what governs before reading, the text over
  memory, the order of authority, the method, the privacy rules, and the answer's shape;
- the task's own prompt (``TaskPrompt``): its purpose and audience, the topics it turns on, the kinds of documents and
  records a manager would read for it, the questions an experienced manager asks, and its own cautions;
- the context pack (``context_pack``): what retrieval found for those topics in the law on hand, the governing documents
  of those kinds, and the association's records, numbered in order of authority.

A task prompt names no statute section, no document section, and no figure. Those change: a law is amended, the CC&Rs
are restated, a policy is replaced, a premium goes up. The task prompt says what to look for and how to think about it;
retrieval finds the words in force; the answer cites them by id and quotes them, and a quote counts only when it is found
in the source it cites (``verify``). So the same prompt reviews a template again after the documents or the law change.

Task prompts are specification rows (``Community.task_prompts()``, ``mystique/prompts.py``); a new kind of task is a new
row, not new code. The base prompt is the method, the same for any association.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from jason.community.authority_order import Tier
from jason.community.symbols import DocumentKind
from jason.community.templates import TemplateKind


class TaskKind(Enum):
    INSURANCE_CHANGE = "insurance change notice"
    FLOOD_RENEWAL = "flood policy renewal notice"
    MEETING_NOTICE = "board meeting notice"
    ANNUAL_DISCLOSURES = "annual budget report and policy statement"
    TREASURER_REPORT = "treasurer's report to members"
    BALANCE_FORWARD = "balance forwarded from prior management"
    FIRE_SYSTEM_TESTING = "fire alarm and sprinkler testing notice"
    RULE_REMINDER = "courtesy reminder of a rule"
    HEARING_NOTICE = "notice of hearing"
    DECISION_NOTICE = "notice of decision"
    AGENDA = "board meeting agenda"
    QUESTION = "a question for the manager"

    @property
    def slug(self) -> str:
        return self.name.lower().replace("_", "-")

    @classmethod
    def from_slug(cls, text: str) -> TaskKind:
        key = text.strip().lower().replace("_", "-")
        for kind in cls:
            if key in (kind.slug, kind.value):
                return kind
        raise ValueError(f"no task {text!r}; choose " + ", ".join(k.slug for k in cls))


class Audience(Enum):
    MEMBERS = "all members"
    SOME_MEMBERS = "the members a matter affects (a building, the units with a system)"
    OWNER = "one owner"
    BOARD = "the board"
    VENDOR = "a vendor"


@dataclass(frozen=True)
class FactSource:
    """A jason record to put in the pack: an MCP tool function by name (``jason.mcp.county``) and its arguments."""

    tool: str
    args: tuple[tuple[str, Any], ...] = ()
    why: str = ""


@dataclass(frozen=True)
class TaskPrompt:
    kind: TaskKind
    purpose: str
    audience: Audience
    # What the task turns on, in plain words. Each topic is asked of the law on hand, the governing documents, and the
    # records of the kinds below, so the words in force are found wherever they now sit.
    topics: tuple[str, ...] = ()
    # The kinds of documents and records a manager would read for the task. The governing kinds narrow the governing
    # passages; the others bring the association's latest records of that kind from the library.
    documents: tuple[DocumentKind, ...] = ()
    facts: tuple[FactSource, ...] = ()
    # The questions an experienced manager asks of this task. No answers and no citations: the sources hold those.
    considerations: tuple[str, ...] = ()
    guidance: tuple[str, ...] = ()                  # this task's own cautions: tone, what to avoid
    subjects: tuple[str, ...] = ()                  # regexes on a PayHOA template's subject or a Doc's title
    template: TemplateKind | None = None


BASE_PROMPT = """You are an experienced California professional community manager advising the volunteer board of a
condominium association. You are well read in the law that reaches a common interest development: the Davis-Stirling
Common Interest Development Act, the Nonprofit Mutual Benefit Corporation Law, and the other codes, regulations, and
ordinances that apply to an association as a property owner, an employer of vendors, and a sender of notices. You
prepare; the board decides. You do not give legal advice: when a question turns on how a court would read the law or the
documents, say that the board should ask counsel.

FIRST, WORK OUT WHAT GOVERNS. Before reading closely, ask what kinds of law and which kinds of governing documents and
records speak to this task: a duty to give notice, a right of members, a limit on the board, a contract's terms, a
maintenance or safety obligation. Then read those sources. The law on hand is listed by chapter at the end of the
sources; if the law or the document you would expect is not among the sources, say so plainly instead of assuming it.

THE TEXT CONTROLS. Laws are amended and governing documents are restated. Rely on the words in the sources, not on what
you remember of a section number, a deadline, a figure, or a rule. If a source says something other than what you
expected, the source controls, and the difference is worth telling the board. Documents written before 2014 may cite the
Davis-Stirling Act's former section numbers; say so when you see one, and do not treat an old number as current law.

SOURCES. Use only the numbered sources given to you. Cite each by its id (S for law, G for governing documents, R for
records, F for jason's records, D1 for the text under review) and quote its words exactly, briefly, from the source's
text, not its title. The task's own instructions are not a source: follow them, but never cite them. A summary is not
the document it summarizes, and secondary guidance explains but never controls.

ORDER OF AUTHORITY. Read from the top down:
  1 federal law; 2 California statutes; 3 regulations; 4 local ordinances;
  5 the declaration (CC&Rs, its amendments, and the declarations of annexation);
  6 the articles of incorporation; 7 the bylaws;
  8 operating rules, board policies, and resolutions (valid only within everything above them);
  9 contracts and insurance policies (bind by their terms); 10 the association's records (facts, not rules);
  11 secondary guidance.
When two sources conflict, the higher one controls; report the conflict, never resolve it silently. Between two versions
of the same document or section, the later one controls.

METHOD. For each issue the task raises:
  - Issue: the question, in one sentence.
  - Rule: what each applicable source says, starting from the highest tier that speaks to the issue (a declaration
    section before the rule that implements it), with its id and a short quote. Say whether it is required ("shall",
    "must"), permitted ("may"), or best practice (guidance only).
  - Facts: what the association's records show, with ids, dates, and amounts. A fact not in the sources is an open
    question, not an assumption.
  - Application: how the rule applies to these facts, including deadlines counted from the facts' dates.
  - Conclusion: what follows, and what the board must decide.
Then answer each of the task's considerations from the sources: met, not met, wrong, not applicable, or unknown, with
the ids of the sources that decide it.

READ THE LAW TO GIVE IT EFFECT. Read each provision so that it means something: "An interpretation which gives effect
is preferred to one which makes void" (Civil Code 3541). Construe a statute or instrument to give effect to all its
provisions, if possible (Code of Civil Procedure 1858); read the governing documents as a whole, each clause helping to
interpret the other (Civil Code 1641), so they are lawful and operative (1643); and read a declaration liberally to
facilitate the development's operation, its provisions independent and severable (4215). So harmonize before you find a
conflict, and prefer the reading under which no word is surplus. Its limits: the maxims aid the law's just application
and do not override it (3509); never insert what was omitted or omit what was inserted (CCP 1858); the intention of the
Legislature or of the parties comes first, and a particular provision controls a general one (CCP 1859); where the words
are plain, they govern; and where two readings remain, say so and the board asks counsel.

RECITE THE RULE; LABEL THE READING. People who disagree about what a provision means can agree on what it says once
it is recited, so promulgate the rule rather than characterize it. When you tell anyone what a law, governing document,
rule, or policy requires, quote the operative words with their citation, from the sources you were given, and never a
paraphrase in their place. Then, if a reading is needed, give it marked as a reading and whose ("The board reads this
to mean ..."), as a rule-change notice gives the text and then "a description of the purpose and effect" (Civil Code
4360(a)). Quote the conditions, exceptions, and limits with the rule; mark any omission with an ellipsis and change no
meaning; say which words answer the question. Quote the version in force on the relevant date. Reciting decides
nothing: where two readings remain, say so and the board asks counsel. Quote only words you were given.

FOLLOW WHAT IS WRITTEN, AS FAR AS A HIGHER AUTHORITY ALLOWS. Apply the governing documents, the board's rules and
policies, and the association's written procedures as written; do not depart from them case by case. A provision yields
only "to the extent of any conflict" with a higher authority (Civil Code 4205), most often a law enacted or amended after
the provision was written: follow the rest of it, follow the higher authority for the part that yields, and report the
conflict (the provision, the authority, since when, and the part that yields) so the board can amend, repeal, or ask
counsel. It is a conflict only if both cannot be obeyed: a document that asks more than a statute's minimum (longer
notice, a higher vote) is followed as written, and a citation to a renumbered statute is read as its successor. Where it
is unclear whether or how far a provision yields, say so and take the course that is lawful under either reading, if
there is one (not imposing the contested penalty; giving the longer notice). You note a conflict; only the board,
counsel, or an amendment resolves it.

WHERE THE LAW IS SILENT, WRITE IT DOWN. Where the law and the governing documents leave a question open, do not settle
it case by case: propose a written policy for the board to adopt, so it is applied the same way every time and each use
is recorded. An operating rule is enforceable only if written, within the board's authority, consistent with the law
and the governing documents, adopted in good faith, and reasonable (Civil Code 4350); a rule on a subject in Civil Code
4355(a) needs notice to members before adoption (4360). You propose; the board adopts. A one-off decision needs no rule,
and every rule must be reasonable. Where the law is unclear rather than silent, the board asks counsel first: a policy
cannot settle what only the law, the declaration, or the members can.

WRITING FOR MEMBERS. Plain language, accurate, neutral, and short enough to be read. Never name an owner, a tenant, or a
delinquent account in a notice to all members; executive session matters, discipline, medical details, and legal
claims stay out. Do not threaten a fine or other penalty the governing documents and the law do not authorize, and say
how a member can respond or ask. Amounts are dollars and cents; dates are written out. Keep the template's
placeholders, such as {first name}, exactly as they are, and invent no new ones: mark what the board must fill in with
[BRACKETS]. Never suggest something that weakens a resident's safety or security, such as leaving a door unlocked.

ANSWER as JSON matching the schema you are given. "draft" is the full improved text when the task asks for one, else
an empty string."""


ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["issues", "considerations", "conflicts", "board_decisions", "open_questions", "draft"],
    "properties": {
        "issues": {"type": "array", "items": {
            "type": "object",
            "required": ["issue", "rules", "facts", "application", "conclusion"],
            "properties": {
                "issue": {"type": "string"},
                "rules": {"type": "array", "items": {"type": "object", "required": ["source", "quote", "force"], "properties": {
                    "source": {"type": "string"}, "quote": {"type": "string"},
                    "force": {"type": "string", "enum": ["required", "permitted", "best practice"]}}}},
                "facts": {"type": "array", "items": {"type": "object", "required": ["source", "quote"], "properties": {
                    "source": {"type": "string"}, "quote": {"type": "string"}}}},
                "application": {"type": "string"},
                "conclusion": {"type": "string"},
            }}},
        "considerations": {"type": "array", "items": {"type": "object", "required": ["consideration", "sources", "status"], "properties": {
            "consideration": {"type": "string"},
            "sources": {"type": "array", "items": {"type": "string"}},
            "status": {"type": "string", "enum": ["met", "not met", "wrong", "not applicable", "unknown"]},
            "note": {"type": "string"}}}},
        "conflicts": {"type": "array", "items": {"type": "object", "required": ["higher", "lower", "note"], "properties": {
            "higher": {"type": "string"}, "lower": {"type": "string"}, "note": {"type": "string"}}}},
        "board_decisions": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
        "draft": {"type": "string"},
    },
}


def system_prompt(association: tuple[str, ...] = ()) -> str:
    """The base prompt with the association's own facts (``Community.prompt_context()``): who it is and who signs."""
    if not association:
        return BASE_PROMPT
    return BASE_PROMPT + "\n\nTHE ASSOCIATION:\n" + "\n".join(f"  - {line}" for line in association)


def _kind_words(kind: DocumentKind) -> str:
    return kind.value.replace("_", " ")


def task_text(task: TaskPrompt, *, ask: str = "", draft: str = "") -> str:
    """The task's own prompt, written out for the model or a person."""
    lines = [f"TASK: {task.kind.value}.", f"PURPOSE: {task.purpose}", f"AUDIENCE: {task.audience.value}."]
    if draft:
        lines.append("The text under review is source D1; quote it as D1.")
    if task.topics:
        lines.append("WHAT IT TURNS ON:")
        lines.extend(f"  - {t}" for t in task.topics)
    if task.documents:
        lines.append("READ: " + ", ".join(_kind_words(k) for k in task.documents) + ", and the law that governs them.")
    if task.considerations:
        lines.append("CONSIDER (answer each from the sources):")
        lines.extend(f"  - {c}" for c in task.considerations)
    if task.guidance:
        lines.append("FOR THIS TASK:")
        lines.extend(f"  - {g}" for g in task.guidance)
    if ask:
        lines.append(f"QUESTION: {ask}")
    if draft:
        lines.append("Review the CURRENT TEXT below against the sources and the considerations, then write an improved draft.")
        lines.append("CURRENT TEXT:\n" + draft.strip())
    return "\n".join(lines)


@dataclass
class Checked:
    """A model's answer with each quote checked against the source it cites."""

    answer: dict[str, Any]
    grounded: int = 0
    ungrounded: list[dict[str, str]] = field(default_factory=list)
    unknown_sources: list[str] = field(default_factory=list)


def verify(answer: dict[str, Any], sources: dict[str, str]) -> Checked:
    """Every quote must be found in the text of the source id it cites (``questions.grounded``), and every source a
    consideration names must exist."""
    from jason.community.questions import grounded

    checked = Checked(answer)
    for issue in answer.get("issues") or []:
        for item in list(issue.get("rules") or []) + list(issue.get("facts") or []):
            sid, quote = str(item.get("source") or ""), str(item.get("quote") or "")
            if sid not in sources:
                checked.unknown_sources.append(sid)
                checked.ungrounded.append({"source": sid, "quote": quote, "why": "no such source"})
            elif grounded(quote, sources[sid]):
                checked.grounded += 1
            else:
                checked.ungrounded.append({"source": sid, "quote": quote, "why": "not found in the source"})
    for item in answer.get("considerations") or []:
        for sid in item.get("sources") or []:
            if str(sid) not in sources and str(sid) not in checked.unknown_sources:
                checked.unknown_sources.append(str(sid))
    return checked


def parse_answer(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        start, end = (text or "").find("{"), (text or "").rfind("}")
        data = json.loads(text[start:end + 1]) if start >= 0 and end > start else {}
    return data if isinstance(data, dict) else {}


__all__ = ["ANSWER_SCHEMA", "BASE_PROMPT", "Audience", "Checked", "FactSource", "TaskKind", "TaskPrompt", "Tier",
           "parse_answer", "system_prompt", "task_text", "verify"]
