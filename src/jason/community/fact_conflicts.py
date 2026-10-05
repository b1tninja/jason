"""Conflicts of fact across a set of documents: where two documents state different values for what looks like the
same fact, both are listed, each with its quote and its source, and neither is picked.

This is the narrow, rule-based part of the "Consistency" lens of docs/ingestion-and-review.md, over any slice of the
passage index (a ``passage_index.Scope`` and a title). A finding of fact rests on the record, and "two records that
disagree are both kept": so a conflict here is a lead for a careful reader, with every side shown and no score that
hides one. Each conflict names the rule that found it:

- ``stored-field``: the document readers' stored fields (``data/documents/readings.json``, written by ``jason
  models``). Two documents of one kind that are about the same thing, by a ``FieldRule`` row's ``same`` fields (the
  same coverage, building, and term start; the same fiscal year), and give different values for one of the row's
  ``compare`` fields. A kind may have several rows; one difference two rows find is listed once. A kind with no row
  is not compared, and the report says so. A reading belongs to the scope when
  its file is in it: an index row under the library's text folder is the library id (``library_id``), matched to the
  reading through the library's fold of a document's copies.
- ``identifier-amount``: within the text, two documents each have one statement that names the same labeled
  identifier ("Invoice 1042", "Policy No. 12-345"), carries exactly one dollar amount, and labels it with the same
  word ("total", "premium"); the amounts differ.
- ``identifier-date``: the same, for exactly one date with the same word before it ("dated", "recorded", "due").
- ``dated-statement-amount``: the same dated event with different amounts. Two documents carry the same sentence
  about the same date, word for word but for its one amount (eight words or more beside the date and the amount,
  every other number the same), and the amounts differ. Only a sentence counts (``is_prose``): a form's line or a
  table's row is the same words in every copy of the form, about a different parcel or month each time. A sentence
  addressed to "you" is left out (a form letter says the same words to each recipient about a different account),
  and so is one that a single document repeats with different amounts.

The text rules are narrow on purpose: a false conflict wastes a careful reader's time, so a statement with two
amounts, two identifiers, or no labeling word is left out. What they miss stays missed.

A stored field's value is the reader's reading, not the document's words. Its quote is the first place the document's
text prints the value, found by rule; when the text does not print it in a form the rule knows, the statement says
so and carries no quote. No model, no network; nothing is written without ``chronology.write_page``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

from jason.community import passage_index as pi
from jason.community import retrieval
from jason.community.chronology import (DATE_SPAN, FileLines, Place, SourceFile, clauses, date_spans, describe_scope,
                                        page_header, place_of, quote_of, source_files, sources_section, statement_at)
from jason.community.passage_index import Scope
from jason.community.passages import Passage
from jason.community.symbols import DocumentKind

CONFLICTS_PAGE = "conflicts.md"
READINGS = Path("documents") / "readings.json"
TEXT_SAME = 0.85                # two names are one when this share of the shorter's shingles sit in the longer
CUE_REACH_AMOUNT, CUE_REACH_DATE = 40, 25
STATEMENT_WORDS = 8             # a dated statement compared word for word has this many words beside its date and amount
PROSE_LOWER = 0.7               # ... and reads as a sentence: this share of its letters are lower case
AMOUNT_MARK, DATE_MARK = "xamountx", "xdatex"
_SECOND_PERSON = re.compile(r"\b(?:you|your|yours)\b", re.I)   # a letter to one recipient: the same words, another account

CAVEATS: tuple[str, ...] = (
    "A conflict is a lead: two documents that give different values for what a rule took to be the same fact. Read "
    "both. jason picks neither, and the order of the sides means nothing.",
    "A difference is not always an error: a later document can replace an earlier one (an endorsement, a revised "
    "report, a corrected instrument), and two documents can speak of different things under one number.",
    "A stored field is a reader's reading of the text, and OCR can misread a figure. Its quote is the first place the "
    "text prints the value; the reader may have read it elsewhere.",
    "The rules are narrow: a kind with no rule row is not compared, and a difference the rules do not look for is not "
    "here. No conflict listed is not a finding that the documents agree.",
)


class Rule(Enum):
    STORED_FIELD = "stored-field"
    IDENTIFIER_AMOUNT = "identifier-amount"
    IDENTIFIER_DATE = "identifier-date"
    DATED_STATEMENT_AMOUNT = "dated-statement-amount"


RULE_WORDS: dict[Rule, str] = {
    Rule.STORED_FIELD: "two documents of one kind, about the same thing by the rule row's fields, whose stored "
                       "readings give different values for one field",
    Rule.IDENTIFIER_AMOUNT: "two documents each state one amount, under the same word, for the same labeled identifier, "
                            "and the amounts differ",
    Rule.IDENTIFIER_DATE: "two documents each state one date, after the same word, for the same labeled identifier, "
                          "and the dates differ",
    Rule.DATED_STATEMENT_AMOUNT: "two documents carry the same sentence about the same date, word for word but for its "
                                 "one amount, and the amounts differ",
}


@dataclass(frozen=True)
class FieldRule:
    """When two stored readings speak of one thing, and what is then compared.

    ``same``: the fields that must all be present and equal. ``compare``: the fields compared; a field one reading
    lacks is not compared. ``money``: compared fields that are amounts in cents though the name does not end in
    ``_cents``. ``show``: fields printed beside each statement to help a reader tell the documents apart (a draft
    flag, a declaration type); they are never compared."""

    kinds: tuple[DocumentKind, ...]
    same: tuple[str, ...]
    compare: tuple[str, ...]
    money: tuple[str, ...] = ()
    show: tuple[str, ...] = ()


K = DocumentKind
_POLICY_MONEY = ("limit", "contents_limit", "deductible", "replacement_cost", "premium")
_POLICY_SHOW = ("declaration", "printed", "endorsement_effective")
# General rows: they name document kinds and the readers' field names, never an association's facts. ``same`` is what
# a document is about (the thing and its period); the compared fields are dates, amounts, counts, numbers, and the
# parties' names. A kind may have several rows: a policy is the same policy by its number and term, and two
# policies are about the same thing by what they cover, the building, and the term, so a second policy number for
# one building and term is found too. A profile passes its own rows to ``fact_conflicts``.
FIELD_RULES: tuple[FieldRule, ...] = (
    FieldRule((K.INSURANCE_POLICY,), ("coverage", "building", "term_start"),
              ("policy_number", "carrier", "named_insured", "term_end", "limit", "contents_limit", "deductible",
               "replacement_cost", "units", "flood_zone", "premium"), money=_POLICY_MONEY, show=_POLICY_SHOW),
    FieldRule((K.INSURANCE_POLICY,), ("policy_number", "term_start"),
              ("carrier", "named_insured", "property_location", "building", "term_end", "limit", "contents_limit",
               "deductible", "replacement_cost", "units", "flood_zone", "premium"),
              money=_POLICY_MONEY, show=_POLICY_SHOW),
    FieldRule((K.EVIDENCE_OF_INSURANCE,), ("certificate_number",), ("issued", "producer", "insured", "holder")),
    FieldRule((K.GRANT_DEED,), ("number",),
              ("recorded", "apn", "unit", "grantor", "grantee", "dated", "consideration_cents", "county_tax_cents",
               "city_tax_cents"), show=("deed_type",)),
    FieldRule((K.RECORDED_LIEN,), ("document_number",), ("recorded", "claimant", "amount", "dated", "apn", "property_address"),
              money=("amount",), show=("instrument",)),
    FieldRule((K.DECLARATION, K.AMENDMENT, K.ANNEXATION, K.CONDOMINIUM_PLAN), ("number",),
              ("recorded", "declarant", "phase", "first_unit", "last_unit", "units", "declaration_number", "plan_number"),
              show=("title",)),
    FieldRule((K.DRE_REPORT,), ("file_number",),
              ("issued", "expires", "phase", "first_unit", "last_unit", "units", "subdivider", "built_out_assessment_cents",
               "phase_assessment_cents", "built_out_reserve_cents", "phase_reserve_cents"), show=("report_type",)),
    FieldRule((K.MINUTES,), ("meeting_date", "body"),
              ("meeting_time", "meeting_type", "next_meeting", "called_to_order", "adjourned", "directors_count"),
              show=("draft",)),
    FieldRule((K.AGENDA,), ("meeting_date", "body"), ("meeting_time", "meeting_type", "meeting_id", "next_meeting"),
              show=("notice_sent",)),
    FieldRule((K.FINANCIAL_STATEMENT,), ("period_end",),
              ("operating_cash_cents", "reserve_cash_cents", "certificate_cents", "reserve_receivable_cents",
               "due_to_reserve_cents"), show=("preparer",)),
    FieldRule((K.TREASURER_REPORT,), ("balance_sheet_date", "pl_start", "pl_end"),
              ("total_bank_cents", "total_assets_cents", "total_liabilities_cents", "total_equity_cents", "reserve_cents",
               "receivable_cents", "income_cents", "expenses_cents", "net_cents"), show=("generated",)),
    FieldRule((K.BANK_STATEMENT,), ("account_last4", "period_start", "period_end"),
              ("beginning_cents", "ending_cents", "deposits_cents", "withdrawals_cents", "fees_cents")),
    FieldRule((K.BUDGET, K.ANNUAL_DISCLOSURE), ("fiscal_year",),
              ("total_income_cents", "total_revenue_cents", "total_expenses_cents", "net_cents", "assessments_cents",
               "monthly_assessments_cents", "monthly_assessment_cents", "annual_assessment_cents", "per_unit_monthly_cents",
               "reserve_transfer_cents"), show=("draft", "generated", "prepared")),
    FieldRule((K.RESERVE_STUDY,), ("fiscal_year", "preparer"),
              ("prepared", "level", "units", "components", "interest_rate", "inflation_rate")),
    FieldRule((K.FINANCIAL_REVIEW,), ("fiscal_year",), ("firm", "report_date", "gross_income_cents")),
    FieldRule((K.INVOICE,), ("vendor", "number"), ("invoice_date", "total_cents")),
    FieldRule((K.PROPOSAL,), ("vendor", "number"), ("proposal_date", "total", "valid_until"), money=("total",)),
    FieldRule((K.INSPECTION_REPORT,), ("inspection_date", "building", "system"),
              ("result", "devices_total", "devices_tested", "devices_passed", "devices_failed", "open_deficiencies",
               "technician", "inspector_firm")),
    FieldRule((K.ELECTION_RESULTS,), ("election_date",), ("ownership_units", "ballots_received", "seats", "quorum_achieved")),
    FieldRule((K.RESOLUTION,), ("number",), ("adopted_on", "attested_on", "subject")),
)


# --- the records ------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Statement:
    """What one document gives for the fact: the value, the document's words that carry it, and where."""

    value: str                              # the value, as shown
    quote: str                              # the document's own words; "" when the text does not print the value
    place: Place
    basis: str                              # how the value was read
    cut_before: bool = False
    cut_after: bool = False
    shown: tuple[tuple[str, str], ...] = ()  # the rule row's ``show`` fields for this document

    @property
    def quoted(self) -> str:
        if not self.quote:
            return ""
        return f"{'... ' if self.cut_before else ''}{self.quote}{' ...' if self.cut_after else ''}"

    def as_dict(self) -> dict[str, Any]:
        return {"value": self.value, "quote": self.quote, "cutBefore": self.cut_before, "cutAfter": self.cut_after,
                "basis": self.basis, "shown": dict(self.shown), **self.place.as_dict()}


@dataclass(frozen=True)
class Side:
    """One value, with every document that gives it."""

    value: str
    statements: tuple[Statement, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"value": self.value, "statements": [s.as_dict() for s in self.statements]}


@dataclass(frozen=True)
class FactConflict:
    """Two or more values for what a rule took to be one fact. Every side is kept; none is preferred."""

    rule: Rule
    subject: str                            # what the documents are about, by the rule
    what: str                               # the field, or the labeled value, that differs
    sides: tuple[Side, ...]

    @property
    def confidential(self) -> bool:
        return any(s.place.confidential for side in self.sides for s in side.statements)

    def as_dict(self) -> dict[str, Any]:
        return {"rule": self.rule.value, "ruleSays": RULE_WORDS[self.rule], "subject": self.subject, "what": self.what,
                "confidential": self.confidential, "sides": [side.as_dict() for side in self.sides]}


def conflict_lines(n: int, conflict: FactConflict, *, level: str = "##") -> list[str]:
    """One conflict as a generated page's lines: the rule, then each value with every document that gives it, its
    place, and its words. ``level`` is the heading's marks (a collection's summary page lists conflicts a level down)."""
    out = [f"{level} {n}. {conflict.subject}: {conflict.what}", "",
           f"- Rule: {conflict.rule.value} ({RULE_WORDS[conflict.rule]})."]
    for side in conflict.sides:
        out.append(f"- Value: {side.value}")
        for s in side.statements:
            flags = ", ".join(part for part in (s.place.standing.value, s.place.kind.replace("_", " "),
                                                "confidential" if s.place.confidential else "") if part)
            shown = "".join(f"; {k}: {v}" for k, v in s.shown)
            out.append(f"  - {s.place.document} [{flags}], {s.place.where}{shown}. Read from: {s.basis}.")
            if s.quote:
                out.append(f"    > {s.quoted}")
    return [*out, ""]


@dataclass
class ConflictReport:
    title: str
    scope: Scope
    conflicts: tuple[FactConflict, ...] = ()
    files: tuple[SourceFile, ...] = ()
    readings: int = 0                        # stored readings whose file is in the scope
    subjects: int = 0                        # groups of two or more readings about one thing that were compared
    not_compared: tuple[str, ...] = ()       # kinds with stored readings in the scope and no rule row
    caveats: tuple[str, ...] = CAVEATS

    @property
    def confidential(self) -> bool:
        return any(f.confidential for f in self.files)

    def counts(self) -> dict[str, Any]:
        return {"conflicts": len(self.conflicts), "files": len(self.files),
                "byRule": {rule.value: sum(1 for c in self.conflicts if c.rule is rule) for rule in Rule},
                "storedReadings": self.readings, "subjectsCompared": self.subjects, "kindsNotCompared": list(self.not_compared)}

    def as_dict(self) -> dict[str, Any]:
        return {"title": self.title, "generatedBy": "jason (rule-based; no model)", "confidential": self.confidential,
                "scope": describe_scope(self.scope), "counts": self.counts(),
                "conflicts": [c.as_dict() for c in self.conflicts], "files": [f.as_dict() for f in self.files],
                "caveats": list(self.caveats)}

    def lines(self) -> list[str]:
        out: list[str] = []
        for n, c in enumerate(self.conflicts, 1):
            out.append(f"{n}. [{c.rule.value}] {c.subject}: {c.what}")
            for side in c.sides:
                out.append(f"   {side.value}")
                for s in side.statements:
                    shown = "".join(f"; {k} {v}" for k, v in s.shown)
                    out.append(f"     {s.place.document} {s.place.where}{shown} ({s.basis})")
                    if s.quote:
                        out.append(f'       "{s.quoted}"')
        c = self.counts()
        out += ["", f"{c['conflicts']} conflicts ({', '.join(f'{k} {v}' for k, v in c['byRule'].items())}) in {c['files']} files; "
                    f"{c['storedReadings']} stored readings, {c['subjectsCompared']} subjects compared"]
        if self.not_compared:
            out.append("Kinds with stored readings and no rule row (not compared): " + ", ".join(self.not_compared))
        out += [f"Note: {caveat}" for caveat in self.caveats]
        return out

    def markdown(self, today: date | None = None) -> str:
        today = today or date.today()
        c = self.counts()
        extra = [f"Conflicts: {c['conflicts']} ({', '.join(f'{k} {v}' for k, v in c['byRule'].items())}); "
                 f"{c['storedReadings']} stored readings in the scope, {c['subjectsCompared']} subjects compared."]
        if self.not_compared:
            extra.append("Not compared (stored readings with no rule row): " + ", ".join(self.not_compared) + ".")
        out = page_header(f"Conflicts of fact: {self.title}", today=today, scope=self.scope, files=self.files,
                          what="Each conflict lists what each document says, quoted, with its source. It picks "
                               "neither side, and the order of the sides means nothing.", extra=extra)
        if not self.conflicts:
            out += ["No conflict was found by the rules. That is not a finding that the documents agree.", ""]
        for n, conflict in enumerate(self.conflicts, 1):
            out += conflict_lines(n, conflict)
        out += sources_section(self.files, "statements in a conflict")
        out += ["## Caveats", "", *[f"- {caveat}" for caveat in self.caveats], ""]
        return "\n".join(out)


# --- values -----------------------------------------------------------------------------------------------------------


class ValueType(Enum):
    MONEY = "money"
    DATE = "date"
    NUMBER = "number"
    FLAG = "flag"
    TEXT = "text"


def money(cents: int) -> str:
    return f"{'-' if cents < 0 else ''}${abs(cents) // 100:,}.{abs(cents) % 100:02d}"


def _typed(name: str, value: Any, rule: FieldRule) -> tuple[ValueType, Any, str] | None:
    """(type, the value to compare, the value as shown) for a stored field; None for a missing or a nested value."""
    if value is None or value == "" or isinstance(value, (list, dict, tuple)):
        return None
    if isinstance(value, bool):
        return ValueType.FLAG, value, "yes" if value else "no"
    if isinstance(value, (int, float)):
        if isinstance(value, int) and (name.endswith("_cents") or name in rule.money):
            return ValueType.MONEY, value, money(value)
        return ValueType.NUMBER, value, str(value)
    text = " ".join(str(value).split())
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            return ValueType.DATE, date.fromisoformat(text), text
        except ValueError:
            pass
    return (ValueType.TEXT, text, text) if text else None


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def same_text(a: str, b: str) -> bool:
    """Whether two names or phrases are one, loosely: the same letters and digits, every word of the shorter in the
    longer, or nearly all of the shorter's letters in the longer (an OCR slip, an abbreviation's stop)."""
    ca, cb = _compact(a), _compact(b)
    if ca == cb:
        return True
    ta, tb = set(re.findall(r"[a-z0-9]+", a.lower())), set(re.findall(r"[a-z0-9]+", b.lower()))
    if ta and tb and (ta <= tb or tb <= ta):
        return True
    return retrieval.containment(retrieval.shingles(a), retrieval.shingles(b)) >= TEXT_SAME


def _same(kind: ValueType, a: Any, b: Any) -> bool:
    return same_text(a, b) if kind is ValueType.TEXT else a == b


# --- finding a value's words in the text ------------------------------------------------------------------------------


def money_pattern(cents: int) -> re.Pattern[str]:
    """The ways a text prints an amount: "$1,301.00", "1301.00", "$1,301". A round amount under a thousand dollars
    must carry its dollar sign or its ".00", since a bare small number is too often something else."""
    dollars, part = abs(cents) // 100, abs(cents) % 100
    digits = str(dollars)
    groups = []
    while len(digits) > 3:
        groups.insert(0, digits[-3:])
        digits = digits[:-3]
    whole = ",?".join([digits, *groups])
    after = r"(?![\d,]|\.\d)"
    if part:
        return re.compile(rf"(?<![\d,.]){whole}\.{part:02d}{after}")
    if dollars < 1000:
        return re.compile(rf"(?:\$\s?{whole}(?:\.00)?|(?<![\d,.$]){whole}\.00){after}")
    return re.compile(rf"(?<![\d,.]){whole}(?:\.00)?{after}")


def locate(kind: ValueType, value: Any, passages: Sequence[Passage], *, today: date | None = None
           ) -> tuple[Passage, int, int] | None:
    """The first place a document's passages print ``value``: (passage, start, end), or None. A count or a yes/no is
    never located: its digits are everywhere."""
    if kind is ValueType.MONEY:
        pattern = money_pattern(value)
    elif kind is ValueType.TEXT:
        words = re.findall(r"[A-Za-z0-9]+", value)
        if len("".join(words)) < 3:
            return None
        pattern = re.compile(r"[^A-Za-z0-9]{0,3}".join(re.escape(w) for w in words), re.I)
    elif kind is ValueType.DATE:
        for passage in passages:
            for span in date_spans(passage.text, today=today):
                if span.day == value:
                    return passage, span.start, span.end
        return None
    else:
        return None
    for passage in passages:
        m = pattern.search(passage.text)
        if m:
            return passage, m.start(), m.end()
    return None


# --- the stored-field rule --------------------------------------------------------------------------------------------


def library_id(path: Path, data_dir: Path) -> str | None:
    """The library id of an index row's file: a file in the library's text folder is named by its id
    (``<id>.txt``, or ``<id>.vision.txt`` for a vision reading; ``tasks.library.text_path``). None for any other."""
    from jason.tasks.library import TEXT_DIR

    if Path(path).parent != Path(data_dir) / TEXT_DIR:
        return None
    name = Path(path).name
    for suffix in (".vision.txt", ".txt"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return None


def _library_keys(data_dir: Path) -> dict[str, str]:
    """Each library id's fold key (``tasks.library.distinct_key``): a document's copies share one, and the index and
    the readings may each name a different copy. Empty when there is no library store."""
    try:
        from jason.tasks.library import distinct_key, load

        return {str(row["id"]): distinct_key(row) for row in load(Path(data_dir))}
    except Exception:  # noqa: BLE001 - no store, or one that cannot be read: ids are then matched as they are
        return {}


def stored_readings(data_dir: Path) -> list[dict[str, Any]]:
    path = Path(data_dir) / READINGS
    if not path.is_file():
        return []
    try:
        return list(json.loads(path.read_text(encoding="utf-8")).get("readings", []))
    except (OSError, ValueError):
        return []


def _allowed(scope: Scope, catalog: str) -> bool:
    return scope.confidential or catalog in scope.confidential_in


def _subject_value(value: Any) -> Any:
    return _compact(value) if isinstance(value, str) else value


def _field_conflicts(data_dir: Path, scope: Scope, loaded: pi.Loaded, rules: Sequence[FieldRule],
                     readings: Sequence[dict[str, Any]], today: date | None) -> tuple[list[FactConflict], int, int, list[str]]:
    """The stored-field conflicts, with how many stored readings the scope holds, how many subjects (two or more
    readings about one thing, by a rule row) were compared, and the kinds with readings and no row."""
    by_path: dict[str, list[Passage]] = {}
    for passage in loaded.passages:
        by_path.setdefault(str(passage.path), []).append(passage)
    keys = _library_keys(data_dir)
    in_scope: dict[str, list[Passage]] = {}                     # fold key (or id) -> the document's passages
    for path, passages in by_path.items():
        doc_id = library_id(Path(path), data_dir)
        if doc_id is not None:
            in_scope.setdefault(keys.get(doc_id, doc_id), passages)
    ruled = {kind.value for rule in rules for kind in rule.kinds}
    held: list[tuple[dict[str, Any], list[Passage]]] = []
    seen: set[str] = set()
    unruled: set[str] = set()
    for reading in readings:
        fields = reading.get("fields")
        doc_id = str(reading.get("id") or "")
        key = keys.get(doc_id, doc_id)
        passages = in_scope.get(key)
        if not passages or not isinstance(fields, dict) or key in seen:
            continue
        row = loaded.rows[(str(passages[0].path), passages[0].index)]
        if reading.get("confidential") and not row.confidential and not _allowed(scope, row.catalog):
            continue                                            # the reading is held back though its index row is not
        seen.add(key)
        held.append((reading, passages))
        if str(reading.get("kind") or "") not in ruled:
            unruled.add(str(reading.get("kind") or ""))

    def statement_of(rule: FieldRule, name: str, reading: dict[str, Any], passages: list[Passage],
                     typed: tuple[ValueType, Any, str]) -> Statement:
        kind, value, shown_value = typed
        found = locate(kind, value, passages, today=today)
        basis = f"the {reading.get('model') or 'document'} reader's stored field {name}"
        shown = tuple((label, " ".join(str(reading["fields"][label]).split())) for label in rule.show
                      if reading["fields"].get(label) not in (None, "", []))
        if found is None:
            passage = passages[0]
            return Statement(shown_value, "", place_of(passage, loaded.rows[(str(passage.path), passage.index)]),
                             basis + "; the text does not print the value in a form the rule finds", shown=shown)
        passage, start, end = found
        bounds, _ = statement_at(passage.text, clauses(passage.text), start, end)
        quote, cut_before, cut_after, at = quote_of(passage.text, bounds, start, end)
        return Statement(shown_value, quote, place_of(passage, loaded.rows[(str(passage.path), passage.index)], at),
                         basis + "; the quote is the first place the text prints the value", cut_before, cut_after, shown)

    conflicts: list[FactConflict] = []
    compared: set[frozenset[str]] = set()
    listed: set[tuple] = set()
    for rule in rules:
        kinds = {kind.value for kind in rule.kinds}
        groups: dict[tuple, list[tuple[dict[str, Any], list[Passage]]]] = {}
        for reading, passages in held:
            if str(reading.get("kind") or "") not in kinds:
                continue
            subject = tuple(_subject_value(reading["fields"].get(name)) for name in rule.same)
            if any(value in (None, "", []) for value in subject):
                continue                                        # a missing identity is a miss, not a match
            groups.setdefault(subject, []).append((reading, passages))
        for members in groups.values():
            if len(members) < 2:
                continue
            compared.add(frozenset(str(passages[0].path) for _, passages in members))
            first = members[0][0]
            named = " / ".join(sorted({str(r["kind"]).replace("_", " ") for r, _ in members}))
            subject = f"{named} with " + ", ".join(f"{name} {' '.join(str(first['fields'][name]).split())}" for name in rule.same)
            for name in rule.compare:
                sides: list[tuple[ValueType, Any, str, list[Statement]]] = []
                for reading, passages in members:
                    typed = _typed(name, reading["fields"].get(name), rule)
                    if typed is None:
                        continue
                    statement = statement_of(rule, name, reading, passages, typed)
                    for side in sides:
                        if side[0] is typed[0] and _same(typed[0], side[1], typed[1]):
                            side[3].append(statement)
                            break
                    else:
                        sides.append((typed[0], typed[1], typed[2], [statement]))
                if len(sides) < 2:
                    continue
                # Two rows can find one difference (the same documents, by building and by policy number): list it once.
                mark = (name, frozenset((shown, s.place.path) for _, _, shown, found in sides for s in found))
                if mark in listed:
                    continue
                listed.add(mark)
                conflicts.append(FactConflict(Rule.STORED_FIELD, subject, name,
                                              tuple(Side(shown, tuple(found)) for _, _, shown, found in sides)))
    return conflicts, len(held), len(compared), sorted(kind for kind in unruled if kind)


# --- the text rules ---------------------------------------------------------------------------------------------------

_MARKLESS = "Invoice|Check|Policy|Claim|Permit|Resolution|Proposal|Estimate|Work Order|Purchase Order|Certificate"
_MARKED = "Case|File|Document|Instrument|Escrow|Loan|Contract|Account|Order"
_IDENTIFIER = re.compile(
    rf"\b(?P<label>{_MARKLESS}|{_MARKED})\s*(?P<mark>(?:(?:No\.?|Number|Num\.?|#|:)\s*)*)"
    r"(?P<number>[A-Z0-9][A-Z0-9./-]*\d[A-Z0-9./-]*)", re.I)
_MARKLESS_LABELS = frozenset(label.lower() for label in _MARKLESS.split("|"))
_AMOUNT = re.compile(r"\$\s?\d{1,3}(?:,\d{3})+(?:\.\d{2})?(?![\d,])|\$\s?\d+(?:\.\d{2})?(?![\d,])"
                     r"|(?<![\d.,$])\d{1,3}(?:,\d{3})+\.\d{2}(?![\d,])")
_AMOUNT_CUE = re.compile(r"\b(total|amount|balance|premium|deductible|limit|fee|payment|deposit|price|cost|sum|paid|due)\b", re.I)
_DATE_CUE = re.compile(r"\b(dated|recorded|issued|filed|signed|executed|adopted|approved|effective|due|paid|received|mailed|"
                       r"sent|expires|expired)\b", re.I)


def identifiers(text: str) -> list[tuple[str, str]]:
    """The labeled identifiers a statement names, each once: (label, number), the label in lower case and the number
    without its separators, three characters or more and never a date. A bare number after a label ("Invoice 1042",
    with no "No.", "#", or colon) counts only for the labels that take one, with four characters and three digits or
    more, and never a year."""
    out: list[tuple[str, str]] = []
    for m in _IDENTIFIER.finditer(text):
        label = " ".join(m.group("label").lower().split())
        raw = m.group("number").rstrip(".-/")
        number = re.sub(r"[^A-Z0-9]", "", raw.upper())
        if DATE_SPAN.fullmatch(raw) or len(number) < 3:
            continue
        if not m.group("mark").strip():
            if label not in _MARKLESS_LABELS or len(number) < 4 or sum(ch.isdigit() for ch in number) < 3:
                continue
            if re.fullmatch(r"(?:19|20)\d\d", number):
                continue
        if (label, number) not in out:
            out.append((label, number))
    return out


def _cue(pattern: re.Pattern[str], text: str, at: int, reach: int) -> str:
    """The last labeling word in the ``reach`` characters before ``at``, in lower case, or ""."""
    found = pattern.findall(text[max(0, at - reach): at])
    return found[-1].lower() if found else ""


def masked_words(clause: str, spans: Sequence[tuple[int, int, str]]) -> tuple[str, ...]:
    """A statement's words in lower case, with each (start, end, mark) span replaced by its mark: what two statements
    share when they differ only in a figure. Every other number stays, so "Unit 12" and "Unit 14" are not the same
    statement."""
    pieces: list[str] = []
    at = 0
    for start, end, mark in sorted(spans):
        if start < at:
            continue
        pieces += [clause[at:start], f" {mark} "]
        at = end
    pieces.append(clause[at:])
    return tuple(re.findall(r"[a-z0-9]+", "".join(pieces).lower()))


def is_prose(clause: str) -> bool:
    """Whether a statement reads as a sentence, not a form's or a table's line: it ends with a full stop, and most of
    its letters are lower case. A bill's stub and a report's row are the same words in every copy of the form, about a
    different parcel or month each time."""
    letters = [ch for ch in clause if ch.isalpha()]
    if not letters or not clause.rstrip().endswith((".", '."', ".)")):
        return False
    return sum(ch.islower() for ch in letters) / len(letters) >= PROSE_LOWER


def _text_conflicts(loaded: pi.Loaded, today: date | None) -> list[FactConflict]:
    from jason.community.document_models import cents

    found: dict[tuple, list[tuple[Any, str, Statement]]] = {}
    for passage in loaded.passages:
        text = passage.text
        named_here = bool(_IDENTIFIER.search(text))
        if not named_here and not _AMOUNT.search(text):
            continue
        row = loaded.rows[(str(passage.path), passage.index)]
        for start, end in clauses(text):
            clause = text[start:end]
            amounts = list(_AMOUNT.finditer(clause))
            values = {cents(m.group(0)) for m in amounts}
            one_amount = len(values) == 1 and None not in values
            named = identifiers(clause) if named_here else []
            if not one_amount and len(named) != 1:
                continue
            spans = date_spans(clause, today=today)

            def statement(value: str, at: int, upto: int) -> Statement:
                quote, before, after, char = quote_of(text, (start, end), start + at, start + upto)
                return Statement(value, quote, place_of(passage, row, char), "the text", before, after)

            if len(named) == 1:
                label, number = named[0]
                if one_amount:
                    cue = _cue(_AMOUNT_CUE, clause, amounts[0].start(), CUE_REACH_AMOUNT)
                    if cue:
                        value = next(iter(values))
                        found.setdefault((Rule.IDENTIFIER_AMOUNT, label, number, cue), []).append(
                            (value, money(value), statement(money(value), amounts[0].start(), amounts[0].end())))
                if len(spans) == 1:
                    cue = _cue(_DATE_CUE, clause, spans[0].start, CUE_REACH_DATE)
                    if cue:
                        day = spans[0].day
                        found.setdefault((Rule.IDENTIFIER_DATE, label, number, cue), []).append(
                            (day, day.isoformat(), statement(day.isoformat(), spans[0].start, spans[0].end)))
            if one_amount and len(spans) == 1 and is_prose(clause) and not _SECOND_PERSON.search(clause):
                words = masked_words(clause, [(m.start(), m.end(), AMOUNT_MARK) for m in amounts]
                                     + [(spans[0].start, spans[0].end, DATE_MARK)])
                if sum(1 for w in words if w not in (AMOUNT_MARK, DATE_MARK)) >= STATEMENT_WORDS:
                    value = next(iter(values))
                    found.setdefault((Rule.DATED_STATEMENT_AMOUNT, spans[0].day, words), []).append(
                        (value, money(value), statement(money(value), amounts[0].start(), amounts[0].end())))
    conflicts: list[FactConflict] = []
    for key, statements in found.items():
        rule = key[0]
        sides: dict[Any, list[Statement]] = {}
        shown: dict[Any, str] = {}
        for value, shown_value, held_statement in statements:
            held = sides.setdefault(value, [])
            shown[value] = shown_value
            if not any(s.place.path == held_statement.place.path and s.quote == held_statement.quote for s in held):
                held.append(held_statement)
        documents = {s.place.path for held in sides.values() for s in held}
        if len(sides) < 2 or len(documents) < 2:
            continue                                            # one value, or one document speaking twice
        if rule is Rule.DATED_STATEMENT_AMOUNT:
            by_document: dict[str, set[str]] = {}
            for value, held in sides.items():
                for s in held:
                    by_document.setdefault(s.place.path, set()).add(shown[value])
            if any(len(values) > 1 for values in by_document.values()):
                continue                                        # a form's line: one document repeats it with each amount
            subject, what = f"a statement about {key[1].isoformat()}", "the amount (every other word is the same)"
        else:
            subject = f"{key[1]} {key[2]}"
            what = f'the amount under "{key[3]}"' if rule is Rule.IDENTIFIER_AMOUNT else f'the date after "{key[3]}"'
        conflicts.append(FactConflict(rule, subject, what, tuple(Side(shown[value], tuple(held)) for value, held in sides.items())))
    return conflicts


# --- the lens ---------------------------------------------------------------------------------------------------------


def fact_conflicts(data_dir: Path | str, scope: Scope, title: str, *, rules: Sequence[FieldRule] = FIELD_RULES,
                   readings: Sequence[dict[str, Any]] | None = None, today: date | None = None) -> ConflictReport:
    """The conflicts of fact among the documents ``scope`` allows (``passage_index.load``), by the stored-field rule
    rows (``rules``) and the three text rules. ``readings`` defaults to the stored ones (``data/documents/readings.json``).
    Raises ``FileNotFoundError`` when there is no index."""
    data_dir = Path(data_dir)
    found = pi.load(data_dir, scope, vectors=False)
    lines = FileLines()                     # a passage cut as a window of words gets its file's line breaks back
    loaded = pi.Loaded(tuple(lines(p) for p in found.passages), found.rows, found.vectors)
    stored = stored_readings(data_dir) if readings is None else readings
    by_field, count, compared, unruled = _field_conflicts(data_dir, scope, loaded, rules, stored, today)
    conflicts = [*by_field, *_text_conflicts(loaded, today)]
    order = list(Rule)
    conflicts.sort(key=lambda c: (order.index(c.rule), c.subject, c.what))
    counts: dict[str, int] = {}
    for conflict in conflicts:
        for side in conflict.sides:
            for statement in side.statements:
                counts[statement.place.path] = counts.get(statement.place.path, 0) + 1
    return ConflictReport(title, scope, tuple(conflicts), source_files(loaded, counts), count, compared, tuple(unruled))


__all__ = ["CAVEATS", "CONFLICTS_PAGE", "ConflictReport", "FIELD_RULES", "FactConflict", "FieldRule", "RULE_WORDS", "Rule",
           "Side", "Statement", "ValueType", "conflict_lines", "fact_conflicts", "identifiers", "is_prose", "library_id", "locate", "money", "money_pattern",
           "masked_words", "same_text", "stored_readings"]
