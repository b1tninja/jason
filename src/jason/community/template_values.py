"""Where a template's tokens get their values: the profile first, then the run.

A base template names no association. Its tokens are filled in layers, later layers winning:

1. ``profile``: who the association is (`Community.identity()`): ``{ASSOCIATION_NAME}``, ``{SIGNATURE}``, ...
2. ``cite``: the association's own governing-document section for a purpose (`Community.citations()`), as
   ``{CITE_<PURPOSE>}``. A purpose the profile does not cite gets the purpose's general wording, never a guess.
3. ``computed``, ``statute``, ``standing``, ``run``: whatever the caller adds (a packet's fiscal year, the statute
   passages, a packet's standing values, a letter's own facts).

`resolve` keeps which layer gave each value, so `lint` can say what a template takes from the profile, what falls back
to general wording, and what is left for the run (docs/base-templates.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping


class CitationPurpose(Enum):
    """Why a notice cites the association's own documents."""

    CONTINUING_FINES = "continuing-fines"
    HEARING_EVIDENCE = "hearing-evidence"
    FINES_NOT_LIENS = "fines-not-liens"
    DIRECTOR_QUORUM = "director-quorum"
    ENFORCEMENT_POLICY = "enforcement-policy"
    FINE_SCHEDULE = "fine-schedule"
    ARCHITECTURAL_REVIEW = "architectural-review"
    ELECTION_RULES = "election-rules"

    @property
    def token(self) -> str:
        return f"CITE_{self.name}"

    @property
    def general(self) -> str:
        """The wording a notice prints when the profile names no section for this purpose."""
        return _GENERAL[self]


_GENERAL = {
    CitationPurpose.CONTINUING_FINES: "the association's governing documents",
    CitationPurpose.HEARING_EVIDENCE: "the association's enforcement policy",
    CitationPurpose.FINES_NOT_LIENS: "the association's governing documents",
    CitationPurpose.DIRECTOR_QUORUM: "the bylaws",
    CitationPurpose.ENFORCEMENT_POLICY: "the association's enforcement policy",
    CitationPurpose.FINE_SCHEDULE: "the association's schedule of fines",
    CitationPurpose.ARCHITECTURAL_REVIEW: "the association's architectural review procedure",
    CitationPurpose.ELECTION_RULES: "the association's election rules",
}


@dataclass(frozen=True)
class Layer:
    name: str
    values: Mapping[str, str]


@dataclass
class Resolved:
    """The values for a template, and the layer each came from."""

    values: dict[str, str] = field(default_factory=dict)
    source: dict[str, str] = field(default_factory=dict)

    def get(self, token: str, default: str = "") -> str:
        return self.values.get(token, default)


def citation_values(community: Any) -> dict[str, str]:
    """``{CITE_<PURPOSE>}`` for every purpose: the profile's section, else the purpose's general wording."""
    own = dict(getattr(community, "citations", lambda: {})() or {})
    return {purpose.token: str(own.get(purpose) or purpose.general) for purpose in CitationPurpose}


def profile_layers(community: Any) -> list[Layer]:
    """The layers a profile gives every template: its identity, then its citations."""
    return [Layer("profile", community.identity().values()), Layer("cite", citation_values(community))]


def profile_values(community: Any) -> dict[str, str]:
    """The profile's layers flattened: the values every template may use before a run adds its own."""
    return resolve(*profile_layers(community)).values


def resolve(*layers: Layer) -> Resolved:
    """Merge layers in order; an empty value never overrides a filled one."""
    out = Resolved()
    for layer in layers:
        for token, value in layer.values.items():
            if value in (None, ""):
                continue
            out.values[token] = str(value)
            out.source[token] = layer.name
    return out


@dataclass(frozen=True)
class Lint:
    """One template's tokens by where they come from for a profile."""

    template: str
    profile: tuple[str, ...]
    general: tuple[str, ...]        # citation tokens filled with the general wording: the profile cites no section
    run: tuple[str, ...]            # left for the run to supply (the letter's own facts)

    def as_dict(self) -> dict[str, Any]:
        return {"template": self.template, "profile": list(self.profile), "general": list(self.general), "run": list(self.run)}


def lint(name: str, tokens: Iterable[str], community: Any) -> Lint:
    """Sort a template's tokens: the profile fills them, a citation falls back to general wording, or the run must."""
    own = {purpose.token for purpose, section in (getattr(community, "citations", lambda: {})() or {}).items() if section}
    filled = profile_values(community)
    profile, general, run = [], [], []
    for token in dict.fromkeys(tokens):
        if token.startswith("CITE_") and token in filled and token not in own:
            general.append(token)
        elif token in filled:
            profile.append(token)
        else:
            run.append(token)
    return Lint(name, tuple(profile), tuple(general), tuple(run))
