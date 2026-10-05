"""Topic phrases: the words that put a contract term on its review-checklist topic more precisely than one word can.

The contract reader places each term on a topic by single words ("breach", "notice", "$") read in rule order. A single
word is often right and sometimes badly wrong: "secure" holds "cure", "trees ... breach the safety height" holds
"breach", and a work list's "Reset and secure 3 loose tiles" is the scope of work, not breach and cure. This module
holds the phrases that settle a topic outright, and the look-alikes that rule a topic out, so the reader can ask here
first and fall back to its own rules on a miss.

Two kinds of row, each a new case as a new row:

- ``PHRASE_RULES``, in match order: the first whose pattern matches a term's words, else its section caption, names the
  topic. "breaches this Agreement" is breach and cure; "terminate this Agreement" is termination; "written notice" is
  notice; "Implementation Fee $350.00" is fees and price; "made this ____ day of" names the parties; a work item that
  opens with a work verb ("Remove and replace ...") is scope of work. Order is part of the rule: "materially breaches
  this Agreement and fails to cure ... after written notice ... may terminate this Agreement" is a breach term first.
- ``NOT_RULES``: (topic, pattern) rows for words that look like a topic and are not. A row vetoes its topic only when
  no phrase rule for that topic also matches, so "secure" never hides a real "in breach".

A miss is ``None``: the reader's own rules decide, and nothing here guesses. Topics are the reader's topic values as
plain strings, so this module stands alone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PhraseRule:
    """One phrase that settles a term's topic: the topic's value, the pattern (case-insensitive), and why it wins."""

    topic: str
    pattern: str
    why: str


# Work verbs that open a line of a work list. A line that starts with one is a work item, whatever words follow.
_WORK_VERBS = (r"reset|secure|remove|replace|reinstall|install|repair|patch|seal|clean|pressure[\s-]wash|paint|prime|"
               r"prune|trim|mow|edge|haul|dispose|furnish|apply|re-?roof|re-?caulk|caulk|flush|test|tighten|adjust")

PHRASE_RULES: tuple[PhraseRule, ...] = (
    PhraseRule("parties and authority",
               r"\b(?:is\s+)?(?:made|entered\s+into)\s+(?:and\s+entered\s+(?:into\s+)?)?(?:as\s+of\s+)?this\s+"
               r"(?:_+|\w+)\s*(?:\(\s*\w*\s*\)\s*)?day\s+of",
               "The opening recital that dates the agreement and names who makes it; its blanks are not a price."),
    PhraseRule("breach and cure",
               r"\bbreach(?:es|ed|ing)?\s+(?:of\s+)?(?:this|the|such|any)\s+(?:\w+\s+)?(?:agreement|contract)\b|"
               r"\bmaterially\s+breach\w*|\bmaterial\s+breach\b|\bin\s+(?:material\s+)?breach\b|"
               r"\bcur(?:e|es|ed|ing)\s+(?:the|such|any|a|its|that)\s+(?:\w+\s+)?(?:breach|default|failure)\b|"
               r"\bevent\s+of\s+default\b|\bin\s+default\b",
               "Breach of the agreement itself, or a cure of it; the bare word also means 'go past' and hides in "
               "'secure'."),
    PhraseRule("termination",
               r"\bterminat(?:e|es|ed|ing)\s+(?:this|the)\s+(?:\w+\s+)?(?:agreement|contract)\b|"
               r"\btermination\s+of\s+(?:this|the)\s+(?:\w+\s+)?(?:agreement|contract)\b",
               "Ending the agreement; 'terminate' alone also ends wires and conductors."),
    PhraseRule("statutory notice",
               r"\bnotice\s+to\s+owner\b(?!s)|\bmechanics['’]?\s+lien\s+law\b",
               "The notice the law makes a home improvement contract print, not a notice between the parties."),
    PhraseRule("notice",
               r"\bnotices?\s+to\s+(?:the\s+)?(?:other\s+)?(?:party|parties|association|contractor|vendor|manager|"
               r"company|customer|client|owner|board|us|you)\b|\bwritten\s+notice\b|\bnotices\s+(?:shall|will|must)\b|"
               r"\bnotice\s+(?:shall|must)\s+be\s+(?:given|delivered|sent|in\s+writing)",
               "How one party tells the other; 'notice' alone also means 'see'."),
    PhraseRule("renewal",
               r"\bautomatically\s+renew\w*|\bauto-?renew\w*|\brenew\w*\s+for\s+(?:an?\s+)?(?:additional|successive)",
               "A term that renews itself unless someone acts."),
    PhraseRule("payment",
               r"\b(?:charged|accrue|bear\s+interest)\s+(?:interest\s+)?at\s+(?:a|the)\s+rate\s+of\s+[\d.]+\s*%|"
               r"\b(?:overdue|past\s+due|unpaid)\s+(?:payments?|balances?|amounts?|invoices?)\b",
               "A late charge on an unpaid balance is when and how to pay, not the price."),
    PhraseRule("price changes",
               r"\bmay\s+(?:increase|raise|adjust)\s+(?:the\s+)?(?:\w+\s+){0,3}(?:fees?|charges?|prices?|rates?)\b",
               "The vendor's right to change the price."),
    PhraseRule("fees and price",
               r"\bfee\s*[:\-–]?\s*\$\s?\d|\bprice\s+includes\b|\bprice\s+(?:is|of)\s+\$\s?\d|"
               r"\$\s?\d[\d,]*(?:\.\d\d)?\s+(?:one-?time|per\s+(?:camera|unit|door|visit|hour|month|year|item))",
               "A priced line: a named fee with its amount, or what the price covers."),
    PhraseRule("scope of work",
               rf"^\s*(?:[-•*·]\s*|\(?\w\)\s*|\d+[.)]\s*)?(?:{_WORK_VERBS})\b(?:\s+(?:and|&)\s+(?:{_WORK_VERBS})\b)?\s+"
               r"(?:\(?\d+\)?|a|an|all|the|each|any|approximately|existing|new|damaged|loose|cracked)\b",
               "A line of a work list opens with a work verb; it is the work, whatever later words look like."),
    PhraseRule("scope of work",
               r"\bwork\s+(?:not\s+included|excluded)\b|\bexclusions?\s*:",
               "What the work leaves out is part of what the work is."),
)

_PHRASE_RE = tuple((r.topic, re.compile(r.pattern, re.I)) for r in PHRASE_RULES)

# Look-alikes: (topic, pattern). Each is a word one of the reader's single-word rules catches that is not that topic.
NOT_RULES: tuple[tuple[str, str], ...] = (
    # "trees ... breach the safety height": to go past a line, not to break the agreement.
    ("breach and cure", r"\bbreach\w*\s+(?:the|a|its)\s+(?!(?:\w+\s+)?(?:agreement|contract|terms?|covenants?|"
                        r"warrant(?:y|ies)|obligations?|duty|duties|representations?)\b)\w+"),
    # "cure" inside another word, and concrete that cures.
    ("breach and cure", r"\b(?:secur\w*|procur\w*|obscur\w*|manicur\w*)|\bcur(?:e|ed|ing)\s+(?:time|period\s+for\s+"
                        r"(?:concrete|sealant|coating)s?)\b|\bconcrete\s+(?:to\s+)?cur"),
    ("breach and cure", r"\bdefault\s+(?:settings?|values?|configuration|passwords?)\b|\bby\s+default\b"),
    ("fees and price", r"\bmade\s+(?:and\s+entered\s+(?:into\s+)?)?this\s+_*\s*day\s+of"),
    ("termination", r"\bterminat\w*\s+(?:the\s+)?(?:wires?|cables?|conductors?|bars?|blocks?|strips?|points?|"
                    r"resistors?)\b|\bterminations?\s+(?:at|in)\s+(?:the\s+)?(?:panel|box|junction)"),
    ("insurance", r"\bbond(?:ed|ing)?\s+(?:breakers?|primers?|coats?|beams?|agents?)\b|\bbond(?:ed|s)?\s+(?:to|with)\s+"
                  r"the\s+(?:existing|substrate|surface)"),
    ("assignment", r"\bassign(?:ed|s)?\s+(?:a\s+|an\s+)?(?:technicians?|crews?|staff|personnel|representatives?|"
                   r"parking|spaces?|stalls?)\b"),
    ("records", r"\bfiles?\s+(?:a\s+)?(?:liens?|complaints?|claims?|suits?|permits?)\b"),
    ("notice", r"\b(?:you|we|they|technicians?|crews?)\s+notices?\b|\bnoticeabl\w*"),
    ("meetings", r"\bmeet(?:s|ing)?\s+(?:the\s+|all\s+)?(?:minimum\s+)?(?:requirements|codes?|standards?|"
                 r"specifications?|needs)\b"),
    ("funds and accounts", r"\btakes?\s+into\s+account\b|\baccount\s+for\b|\bon\s+account\s+of\b|"
                           r"\breserves?\s+the\s+right\b"),
    ("price changes", r"\bincreas\w*\s+(?:the\s+)?(?:water\s+)?(?:pressure|flow|coverage|visibility|security|"
                      r"efficiency|lighting)\b"),
)

_NOT_RE = tuple((t, re.compile(p, re.I)) for t, p in NOT_RULES)


def topic_by_phrase(caption: str, quote: str) -> str | None:
    """The first phrase rule's topic that matches the term's words, else its caption; ``None`` leaves it to the reader.

    The words come before the caption here, the reverse of the reader's single-word rules: a phrase in the sentence
    is more precise than the heading over a whole section.
    """
    for words in (quote, caption):
        if not words:
            continue
        flat = " ".join(words.split())
        for topic, rx in _PHRASE_RE:
            if rx.search(flat):
                return topic
    return None


def vetoed(topic: str, quote: str) -> bool:
    """A look-alike row says this quote is not ``topic``, and no phrase rule for that topic says it is."""
    flat = " ".join((quote or "").split())
    if not any(t == topic and rx.search(flat) for t, rx in _NOT_RE):
        return False
    return not any(t == topic and rx.search(flat) for t, rx in _PHRASE_RE)


__all__ = ["NOT_RULES", "PHRASE_RULES", "PhraseRule", "topic_by_phrase", "vetoed"]
