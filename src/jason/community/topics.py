"""What a message or request is about: a closed set of topics, recognized by words in its subject.

A ``Topic`` is a subject the association hears about again and again (parking, bins, solar, insurance). A ``TopicRule``
names one topic and the words that recognize it in a subject line or an attachment's name; a message can carry several
topics. The rules are the association's (``Mystique.topic_rules()``); a subject no rule names has no topic, and a miss
stays a miss.

Counted over threads, the topics show what owners keep asking: a topic several units raise in a year is a candidate
for a notice, a rule clarification, or a page in the new-owner packet.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Topic(Enum):
    PARKING = "parking"
    BINS = "trash and bins"
    SOLAR = "solar"
    INSURANCE = "insurance"
    ASSESSMENTS = "assessments and payments"
    MAINTENANCE = "maintenance and repairs"
    LANDSCAPING = "landscaping"
    PESTS = "pests"
    ARCHITECTURE = "architectural changes"
    NEIGHBORS = "noise, pets, and neighbors"
    ESCROW = "escrow and resale"
    GOVERNANCE = "meetings, elections, and governing documents"
    SECURITY = "security and incidents"
    UTILITIES = "utilities"


@dataclass(frozen=True)
class TopicRule:
    topic: Topic
    words: tuple[str, ...]

    def matches(self, text: str) -> bool:
        return any(re.search(rf"(?i)\b{re.escape(word)}", text) for word in self.words)


class Intent(Enum):
    """What a message asks of the association, read from its subject."""

    COMPLAINT = "complaint"
    MAINTENANCE = "maintenance request"
    INFORMATION = "request for information or records"
    QUESTION = "question"
    BILLING = "billing or payment"
    ENFORCEMENT = "the association's own enforcement notice"


@dataclass(frozen=True)
class IntentRule:
    """An intent and the patterns (regular expressions, case ignored) that name it in a subject. Rules apply in order,
    and a subject can carry several intents."""

    intent: Intent
    patterns: tuple[str, ...]

    def matches(self, text: str) -> bool:
        return any(re.search(p, text, re.I) for p in self.patterns)


def intents_of(text: str, rules: tuple[IntentRule, ...]) -> tuple[Intent, ...]:
    found: list[Intent] = []
    for rule in rules:
        if rule.intent not in found and rule.matches(text):
            found.append(rule.intent)
    return tuple(found)


def topics_of(text: str, rules: tuple[TopicRule, ...]) -> tuple[Topic, ...]:
    """Every topic whose rule the text carries, in rule order."""
    found: list[Topic] = []
    for rule in rules:
        if rule.topic not in found and rule.matches(text):
            found.append(rule.topic)
    return tuple(found)


@dataclass(frozen=True)
class TopicSources:
    """Where the answer to a topic is likely written: a query for the governing documents' passages, the library's
    document kinds that speak to it, and the PayHOA violation titles that are its precedents (their notice text too)."""

    topic: Topic
    query: str
    kinds: tuple[str, ...] = ()
    violation_words: tuple[str, ...] = ()


__all__ = ["Topic", "TopicRule", "topics_of", "Intent", "IntentRule", "intents_of", "TopicSources"]
