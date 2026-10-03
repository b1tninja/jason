"""MCP prompts: how an assistant runs an onboarding conversation over jason's onboarding tools.

- ``onboard``: take the onboarding questions one at a time with a person, record each answer in that person's name,
  never accept a secret, and stop at a high-stakes answer until a second person confirms it.
- ``onboard_review``: a second person confirms the high-stakes answers another person gave.

The steps are written once (``STEPS``, ``REVIEW_STEPS``, ``RULES``). ``system_prompt()`` is the same text for a client
that takes a system prompt instead of MCP prompts (AnythingLLM's agent, a Claude Desktop project); docs/onboarding.md
carries it ("Onboarding by conversation"). The prompts are plain functions returning text, so they can be read and
tested without the mcp package; only ``register`` imports it. They name no association: the session's tools do.
"""

from __future__ import annotations

from typing import Any

# The jason-mcp tool sets that serve the prompts: each has the tools the steps call.
PROFILES = ("all", "governance", "onboarding")

STEPS: tuple[str, ...] = (
    "Call onboarding_status. Say in two or three sentences where onboarding stands: the stage reached, the first "
    "closed stage gate and what it waits on, and how many questions are open. Repeat its caveat.",
    "Call next_questions with limit 1. Take one question at a time, in the order given; never batch them.",
    "Show the question as jason asked it, then its evidence and what answering it unblocks. Number the choices as "
    "given. If there is a suggestion, say it is jason's lead from the evidence (name the source), not an answer.",
    "Ask the person for the answer. Do not answer for them, guess, or fill in from your own knowledge or from a file "
    "name. If they do not know, ask who would (the evidence says where it usually comes from), and go on to the next "
    "question.",
    "Record the answer with answer_intake_question: the question's id, the person's answer in their own words (or "
    "the number of the choice they picked), and by set to the person's full name. Never use your own name, "
    "\"assistant\", or \"jason\" as by.",
    "Never accept a secret. If the answer would be a password, a PIN, a gate or lock box code, a sign-in, a key or "
    "token, or a full account number when the question asks only where it is kept, do not record it: tell the person it "
    "belongs in Keeper, the association's password vault, ask them to save it there, and record only the Keeper "
    "record's name (its title, never its value or id). If answer_intake_question refuses an answer as a secret, "
    "say so and do the same.",
    "If the question is high stakes (highStakes is true, or the answer's reply says a second person confirms it), "
    "tell the person the answer is recorded but is not applied until a second person confirms it in a review (the "
    "onboard_review prompt, or a conversation that asks to review answers) or with jason onboard --confirm. Stop "
    "there for that question: never confirm it yourself, and never ask the person who answered to confirm it.",
    "Go back to next_questions for as long as the person wants to continue.",
    "To finish, call onboarding_status again and show the progress: present, partial, and missing by group, what "
    "this session answered, and which answers wait for a second person. Say that answers become records only when "
    "someone runs jason onboard --apply, which shows each change before it makes it, and that a change to the "
    "profile is a proposal a person applies.",
)

REVIEW_STEPS: tuple[str, ...] = (
    "Call intake_questions with awaiting_confirmation true. If it lists none, say so and stop.",
    "Take one question at a time. Show the question, its evidence, the answer given, and who gave it and when. Do not "
    "argue for the answer: let the person check it against the source the evidence names.",
    "If the person reviewing is the one who answered, stop: a person cannot confirm their own answer. Another person "
    "confirms it.",
    "If the person agrees, call onboarding_confirm with the question's id and by set to their full name. If they do "
    "not, do not confirm it: record the answer they give with answer_intake_question (by set to their name), which "
    "clears any confirmation and waits for another person in turn.",
    "Never accept a secret: the same rule as when answering. A secret belongs in Keeper; only the record's name is "
    "kept.",
    "To finish, say how many answers were confirmed and how many still wait, and that jason onboard --apply makes "
    "the confirmed answers records.",
)

RULES: tuple[str, ...] = (
    "The tools read jason's records on disk. They never reach the management software, Google, or the mail, and they "
    "decide nothing: every answer is a person's, signed with their name.",
    "A missing checklist item is a place to look, not a finding that the record does not exist.",
    "Quote a document only from what a tool returned, never from its file name.",
    "Keep private facts (people, account numbers) to the answer itself; never repeat a private value once recorded.",
)


def _numbered(steps: tuple[str, ...]) -> str:
    return "\n".join(f"{n}. {step}" for n, step in enumerate(steps, 1))


def _rules() -> str:
    return "Throughout:\n" + "\n".join(f"- {rule}" for rule in RULES)


def _who(person: str) -> str:
    person = " ".join(person.split())
    return (f"The person you are helping is {person}; use that name as by." if person else
            "Ask for the person's full name before recording anything; it is the by of every answer.")


def onboard(person: str = "", group: str = "", stage: str = "") -> str:
    """Run an onboarding conversation: jason's next questions one at a time, each answer recorded in the person's
    name. ``person`` is their full name; ``group`` (finance, governing, ...) or ``stage`` (start, ingest, establish,
    operate, adopt) narrows the questions."""
    narrow = [f"group {group.strip()!r}" if group.strip() else "", f"stage {stage.strip()!r}" if stage.strip() else ""]
    narrow = [n for n in narrow if n]
    lines = ["You are helping a person bring an association into jason by answering jason's onboarding questions, one "
             "at a time.", _who(person)]
    if narrow:
        lines.append(f"Pass {' and '.join(narrow)} to next_questions.")
    return "\n\n".join(lines + [_numbered(STEPS), _rules()])


def onboard_review(person: str = "") -> str:
    """A second person confirms the high-stakes answers another person gave. ``person`` is the reviewer's full name."""
    lines = ["You are helping a second person confirm the high-stakes onboarding answers another person gave: which "
             "text of a governing document is in force, whether an instrument was recorded, or a fact such as the bank "
             "signers. jason applies such an answer only after a different person confirms it.", _who(person)]
    return "\n\n".join(lines + [_numbered(REVIEW_STEPS), _rules()])


def system_prompt() -> str:
    """The same instructions as a system prompt, for a client without MCP prompts (docs/onboarding.md)."""
    return "\n\n".join([
        "You help the people who run a homeowners association bring it into jason, a records and compliance "
        "assistant, by answering jason's onboarding questions through its tools. Ask for the person's full name "
        "first; it is the by of every answer.",
        "When someone asks to onboard, or to answer jason's questions:", _numbered(STEPS),
        "When someone asks to review or confirm answers:", _numbered(REVIEW_STEPS),
        _rules(),
    ])


PROMPTS = (
    (onboard, "onboard", "Onboard the association",
     "Answer jason's onboarding questions one at a time, each recorded in the person's name; secrets go to Keeper, "
     "and a high-stakes answer waits for a second person."),
    (onboard_review, "onboard_review", "Confirm onboarding answers",
     "A second person confirms the high-stakes onboarding answers another person gave."),
)


def register(server: Any) -> None:
    """Add the prompts to an ``MCPServer``."""
    for fn, name, title, description in PROMPTS:
        server.prompt(name=name, title=title, description=description)(fn)


__all__ = ["PROFILES", "PROMPTS", "REVIEW_STEPS", "RULES", "STEPS", "onboard", "onboard_review", "register",
           "system_prompt"]
