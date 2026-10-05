"""Classifying a document by its own words: phrase rules, record refinements, and a local model.

The name rules say what a file is called. The text says what it is. Three
steps read the text, in order:

- ``CONTENT_RULES`` name a kind from phrases near the top of the text, for a
  file the name rules missed. The first rule that matches wins.
- ``RECORD_RULES`` add a Civil Code 5200 record the kind alone does not
  give: a reserve account's statements, a balcony inspector's report, the
  board's written approval of a vendor's proposal in the minutes.
- ``ModelClassifier`` asks a local model through Ollama, with the kinds as a
  closed list, for what both leave. Its answer carries a confidence and a
  reason, and it never overrides a name or phrase rule.

The phrases are the documents' generic wording, not Mystique's; a fact
about Mystique (which bank account is the reserve) belongs in the
specification. Nothing here reads a file or calls a network except the
model, which fails fast when Ollama is not running.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from jason.community.symbols import AssociationRecord, DocumentKind


@dataclass(frozen=True)
class ContentRule:
    """A kind named by phrases in the first ``window`` characters. ``min_hits`` phrases must appear."""

    kind: DocumentKind
    phrases: tuple[str, ...]
    window: int = 3000
    min_hits: int = 1
    # Every one of these must also appear in the window: a recorded instrument's stamp, say.
    requires: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecordRule:
    """A 5200 record a document of ``kinds`` also is, when its text holds one of ``phrases``."""

    kinds: tuple[DocumentKind, ...]
    phrases: tuple[str, ...]
    record: AssociationRecord
    why: str
    # A regular expression over the case-folded text, for wording phrases cannot pin ("approved a $5,200 ... proposal").
    pattern: str = ""


# The title pass: what a document calls itself in its opening words. Order is the match order; a more specific
# title comes before the word it contains ("declaration of annexation" before "declaration").
TITLE = 450
TITLE_RULES: tuple[ContentRule, ...] = (
    # A meeting's agenda lists "Treasurer's Report" as an item; the report itself names it in its first line.
    ContentRule(DocumentKind.TREASURER_REPORT, ("treasurer's report", "treasurer report", "treasurers report"), 120),
    # Minutes and the agenda share a heading. The agenda says the meeting is "to be held"; minutes say it was
    # "held", or show it happening (a motion seconded and carried). Only then does the shared heading mean an agenda.
    ContentRule(DocumentKind.EXECUTIVE_SESSION, ("executive session",), 220),
    ContentRule(DocumentKind.AGENDA, ("to be held",), 220),
    ContentRule(DocumentKind.MINUTES, (" held on", " held at", " held ", "minutes of the", "meeting minutes", "draft minutes"), 220),
    ContentRule(DocumentKind.MINUTES, ("called to order", "motion", "seconded", "carried", "adjourned", "present:"), 8000, 3),
    ContentRule(DocumentKind.AGENDA, ("agenda", "regular meeting of the board", "special meeting of the board", "annual meeting of the members", "annual membership meeting"), 220),
    ContentRule(DocumentKind.ANNUAL_DISCLOSURE, ("annual disclosures", "annual disclosure", "insurance summary", "annual policy statement"), TITLE),
    ContentRule(DocumentKind.RESERVE_STUDY, ("reserve study",), TITLE),
    ContentRule(DocumentKind.BUDGET, ("pro forma budget", "budget summary", "annual budget report", "proposed budget"), TITLE),
    ContentRule(DocumentKind.FINANCIAL_REVIEW, ("independent accountant's review", "accountant's review report", "review report"), TITLE),
    ContentRule(DocumentKind.TAX_RETURN, ("form 1120-h", "form 1120h", "u.s. income tax return for homeowners associations"), TITLE),
    ContentRule(DocumentKind.TAX_BILL, ("parcel number bill number", "secured property tax bill", "property tax bill"), TITLE),
    # A carrier's claim papers, before the policy rule: a claim letter quotes its policy's conditions.
    ContentRule(DocumentKind.LOSS_RUN, ("claim detail report", "claim summary report", "loss run"), TITLE),
    ContentRule(DocumentKind.MANAGER_CASE_REPORT, ("cases currently open", "days solving cases", "case performance"), min_hits=2),
    ContentRule(DocumentKind.CLAIM_PAYMENT, ("statement of loss", "remittance advice", "net claim at"), TITLE),
    ContentRule(DocumentKind.CLAIM_AUTHORIZATION, ("work authorization", "certificate of satisfaction"), TITLE),
    ContentRule(DocumentKind.CLAIM_LETTER, ("claim number", "loss date", "location of loss", "date of loss", "policy number",
                                            "please include your claim"), TITLE, min_hits=3),
    ContentRule(DocumentKind.INSURANCE_POLICY, ("flood insurance policy", "policy declarations", "declarations page", "national flood insurance program"), TITLE),
    ContentRule(DocumentKind.EVIDENCE_OF_INSURANCE, ("certificate of liability insurance", "evidence of property insurance", "certificate of insurance"), TITLE),
    ContentRule(DocumentKind.DELINQUENCY_NOTICE, ("notice of default and demand", "pre-lien", "notice of intent to lien", "demand for payment"), TITLE),
    ContentRule(DocumentKind.RECORDED_LIEN, ("notice of delinquent assessment", "claim of mechanics lien", "mechanics lien", "release of lien"), TITLE),
    # A recorded governing instrument opens with the recorder's stamp; its title follows within a page.
    ContentRule(DocumentKind.ANNEXATION, ("declaration of annexation", "supplementary declaration", "annexation"), 2500, requires=("recording requested by",)),
    ContentRule(DocumentKind.AMENDMENT, ("amendment to", "amendment of", "certificate of amendment"), 2500, requires=("recording requested by",)),
    ContentRule(DocumentKind.DECLARATION, ("declaration of covenants", "declaration of restrictions", "covenants, conditions"), 2500, requires=("recording requested by",)),
    ContentRule(DocumentKind.ARTICLES, ("articles of incorporation",), TITLE),
    ContentRule(DocumentKind.BYLAWS, ("bylaws of", "by-laws of"), TITLE),
    ContentRule(DocumentKind.CONDOMINIUM_PLAN, ("condominium plan",), TITLE),
    ContentRule(DocumentKind.ELECTION_RULES, ("election rules", "election and voting rules"), TITLE),
    ContentRule(DocumentKind.ELECTION_RESULTS, ("election results", "inspector of elections report"), TITLE),
    ContentRule(DocumentKind.BALLOT, ("official ballot", "secret ballot"), TITLE),
    ContentRule(DocumentKind.OWNER_STATEMENT, ("all current charges due", "statement of account"), TITLE),
    ContentRule(DocumentKind.ESCROW_REQUEST, ("requestor information",), TITLE),
    ContentRule(DocumentKind.GRANT_DEED, ("grant deed",), TITLE),
    ContentRule(DocumentKind.RESOLUTION, ("resolution of the board", "board resolution"), TITLE),
    ContentRule(DocumentKind.OPERATING_RULES, ("owner's manual", "owner’s manual", "rules and regulations"), TITLE),
    ContentRule(DocumentKind.POLICY, ("collection policy", "enforcement policy", "ethics policy", "license plate reader policy", "investment policy", "policy and procedure"), TITLE),
    # A lawyer's letter marks itself privileged in its heading, before a "Re:" line that may name a notice or a contract.
    ContentRule(DocumentKind.LEGAL_CORRESPONDENCE, ("client privileged communication", "attorney-client privileged",
                                                    "privileged and confidential attorney"), TITLE),
    # A CPA's or vendor's engagement letter is the contract for its services.
    ContentRule(DocumentKind.CONTRACT, ("engagement letter", "terms of our engagement", "confirm our understanding of the services",
                                        "confirm our understanding of the terms", "confirm our acceptance and understanding",
                                        "you have requested that we perform"), 1500),
    ContentRule(DocumentKind.CONTRACT, ("agreement", "contract"), 150),
    # A preparer's package of the year's returns opens with a cover letter that lists the enclosed forms and says the filing
    # instructions follow; no single form's title is in its opening words.
    ContentRule(DocumentKind.TAX_RETURN, ("filing instructions for the", "return(s) for the year ended", "form 1120-h",
                                          "form 199", "form 100"), 1500, 2),
    # An owner's filled application (a parking variance, an architectural request) opens with the form's own title.
    ContentRule(DocumentKind.FORM, ("permit application", "application for", "improvement request", "request form"), TITLE),
    ContentRule(DocumentKind.NOTICE, ("disclosure of pending litigation", "notice of", "notice to", "nuisance alarm notice",
                                      "no vehicle access", "maintenance scheduled"), TITLE),
)

# The body pass, when no title decides: phrases anywhere in the first pages, most specific first.
BODY_RULES: tuple[ContentRule, ...] = (
    # Before the owner statement and the invoice: a utility bill also says "amount due".
    ContentRule(DocumentKind.UTILITY_BILL, ("your electric bill", "utility service bill", "total electric service charges", "electricity charges", "per cubic foot", "storm drainage", "meter summary"), min_hits=2),
    ContentRule(DocumentKind.OWNER_STATEMENT, ("all current charges due", "statement date", "previous balance", "amount due"), min_hits=2),
    ContentRule(DocumentKind.ESCROW_REQUEST, ("requestor information", "escrow", "resale", "demand", "projected closing date",
                                              "current owner", "new owner"), min_hits=2),
    ContentRule(DocumentKind.OWNER_HISTORY, ("owner history", "ownership history")),
    ContentRule(DocumentKind.GRANT_DEED, ("grant deed", "documentary transfer tax")),
    ContentRule(DocumentKind.MINUTES, ("held on", "called to order", "motion", "carried", "adjourned", "present:"), 6000, 3),
    ContentRule(DocumentKind.AGENDA, ("agenda", "call to order", "open forum", "adjournment"), min_hits=3),
    ContentRule(DocumentKind.BANK_STATEMENT, ("statement period", "beginning balance", "ending balance", "deposits and other credits", "account summary"), min_hits=2),
    ContentRule(DocumentKind.FINANCIAL_STATEMENT, ("balance sheet", "income statement", "statement of revenues", "budget comparison", "general ledger"), min_hits=2),
    ContentRule(DocumentKind.RESERVE_STUDY, ("reserve study", "percent funded", "component list"), min_hits=2),
    ContentRule(DocumentKind.INVOICE, ("invoice #", "invoice number", "amount due", "bill to", "make checks payable to",
                                       "invoice date"), min_hits=2),
    ContentRule(DocumentKind.PROPOSAL, ("proposal", "scope of work", "estimate", "quote"), min_hits=2),
    ContentRule(DocumentKind.BALLOT, ("ballot", "vote for", "secret ballot"), min_hits=2),
    ContentRule(DocumentKind.ELEVATED_ELEMENT_INSPECTION, ("exterior elevated element", "elevated elements", "5551", "sb 326", "sb326"), min_hits=2),
    ContentRule(DocumentKind.INSPECTION_REPORT, ("inspection report", "inspected", "observations", "recommendations"), min_hits=2),
    ContentRule(DocumentKind.SETTLEMENT, ("settlement agreement", "release of all claims", "mutual release")),
    ContentRule(DocumentKind.CONTRACT, ("this agreement", "the parties agree", "term of this agreement", "in witness whereof"), min_hits=2),
    ContentRule(DocumentKind.FORM, ("please print", "signature", "date:", "phone", "email"), min_hits=3),
    ContentRule(DocumentKind.NOTICE, ("notice is hereby given", "please be advised")),
)

CONTENT_RULES: tuple[ContentRule, ...] = TITLE_RULES + BODY_RULES


RECORD_RULES: tuple[RecordRule, ...] = (
    RecordRule((DocumentKind.BANK_STATEMENT,), ("reserve",), AssociationRecord.RESERVE_ACCOUNT,
               "the statement names a reserve account (5200(a)(7): reserve account balances and payments)"),
    RecordRule((DocumentKind.INSPECTION_REPORT,), ("5551", "exterior elevated element", "elevated elements", "balcon"),
               AssociationRecord.ELEVATED_ELEMENT_REPORT, "the report inspects exterior elevated elements (5200(a)(15), Civil Code 5551)"),
    RecordRule((DocumentKind.MINUTES,), (), AssociationRecord.VENDOR_APPROVAL,
               "the minutes record the board's written approval of a vendor's proposal, bid, invoice, or contract (5200(a)(5))",
               pattern=r"approv\w*[^.]{0,100}?\b(proposal|bid|contract|invoice|quote|estimate)s?\b"),
    RecordRule((DocumentKind.FINANCIAL_STATEMENT, DocumentKind.TREASURER_REPORT), ("check register", "check detail", "disbursements register"),
               AssociationRecord.CHECK_REGISTER, "the statement package carries a check register (5200(a)(10))"),
    RecordRule((DocumentKind.FINANCIAL_STATEMENT, DocumentKind.TREASURER_REPORT), ("reserve",),
               AssociationRecord.RESERVE_ACCOUNT, "the statement reports reserve balances (5200(a)(7))"),
)


def _hits(text: str, phrases: tuple[str, ...]) -> list[str]:
    folded = text.casefold()
    return [phrase for phrase in phrases if phrase in folded]


_EXTRACT_HEADER = re.compile(r"^(#[^\n]*|- (drive_id|mime|path|ocr|source|pages?)[^\n]*|\s*)$", re.I)


def body_of(text: str) -> str:
    """The document's own words: an extract's header (its file name, Drive id, mime, path) is dropped, and space collapsed.

    The header carries the file name, and a text rule that read it would be a
    name rule in disguise.
    """
    lines = text.splitlines()
    index = 0
    while index < len(lines) and index < 12 and _EXTRACT_HEADER.match(lines[index]):
        index += 1
    return " ".join(" ".join(lines[index:]).replace("\u200b", " ").split())


def classify_text(text: str, rules: tuple[ContentRule, ...] = CONTENT_RULES) -> tuple[DocumentKind | None, str]:
    """The first rule whose phrases appear in its window of the document's own words, with the phrases that decided it."""
    body = body_of(text)
    for rule in rules:
        window = body[: rule.window]
        if rule.requires and len(_hits(window, rule.requires)) < len(rule.requires):
            continue
        found = _hits(window, rule.phrases)
        if len(found) >= rule.min_hits:
            where = "title" if rule.window <= TITLE else "text"
            return rule.kind, f"{where}: " + ", ".join(f'"{phrase.strip()}"' for phrase in found)
    return None, ""


def records_from_text(kind: DocumentKind | None, text: str, rules: tuple[RecordRule, ...] = RECORD_RULES) -> tuple[tuple[AssociationRecord, str], ...]:
    """The extra 5200 records the text shows for a document of ``kind``, with why."""
    if kind is None or not text:
        return ()
    found: list[tuple[AssociationRecord, str]] = []
    folded = text.casefold()
    for rule in rules:
        if kind not in rule.kinds or any(rule.record is r for r, _ in found):
            continue
        if (rule.phrases and _hits(text, rule.phrases)) or (rule.pattern and re.search(rule.pattern, folded)):
            found.append((rule.record, rule.why))
    return tuple(found)


# Member-level detail a record carries, which the association may withhold or redact from members (Civil Code 5215):
# information whose release "is reasonably likely to compromise the privacy of an individual member" ((a)(4)) and
# "records of ... collection activities, or payment plans of members other than the member requesting the records"
# ((a)(5)(B)). The board reviews it monthly (5500) and discusses payment plans and foreclosure in executive session
# (4935(c), (d)). A file a rule matches is confidential wherever it is filed and whatever its name says.

_DAYS_PAST = re.compile(r"Days\s+Past", re.I)
_TABLE_TOTAL = re.compile(r"^\s*\|?\s*Totals?\b", re.I)


def aging_units(text: str) -> tuple[str, ...]:
    """The unit addresses an accounts-receivable aging table lists: from its first "Days Past Due" header to its Total row.

    PayHOA's treasurer's report prints one row per unit with its balance by age; the version shared with members
    leaves the units out and keeps the totals. A unit named elsewhere (a repair in the ledger) is not in the table.
    """
    from jason.community.models.legal_shared import site_addresses

    lines = (text or "").splitlines()
    start = next((i for i, line in enumerate(lines) if _DAYS_PAST.search(line)), None)
    if start is None:
        return ()
    found: list[str] = []
    for line in lines[start:]:
        if _TABLE_TOTAL.match(line) and not _DAYS_PAST.search(line):
            break
        for address in site_addresses(line):
            if address not in found:
                found.append(address)
    return tuple(found)


@dataclass(frozen=True)
class PrivateRule:
    """A kind whose text, when it carries member-level detail, makes the file confidential."""

    kinds: tuple[DocumentKind, ...]
    reason: str
    authority: str
    units: Any                 # text -> the units the detail names; any makes the file confidential


PRIVATE_RULES: tuple[PrivateRule, ...] = (
    PrivateRule((DocumentKind.TREASURER_REPORT, DocumentKind.FINANCIAL_STATEMENT),
                "the receivables aging lists units with their balances: members' collection status",
                "CIV 5215(a)(4), (a)(5)(B)", aging_units),
)


def private_content(kind: DocumentKind | None, text: str, rules: tuple[PrivateRule, ...] = PRIVATE_RULES) -> str:
    """Why the text makes a file of ``kind`` confidential (member-level detail), or "" when no rule applies."""
    if kind is None or not text:
        return ""
    for rule in rules:
        if kind in rule.kinds:
            units = rule.units(text)
            if units:
                return f"{rule.reason} ({len(units)} units; {rule.authority})"
    return ""


_MONTH = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
_LONG_DATE = re.compile(_MONTH + r"\s+(\d{1,2}),\s+(20\d\d)")
_MONTH_NUM = {m: i for i, m in enumerate(("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"), start=1)}


def period_from_text(text: str, window: int = 1500) -> str:
    """The first long-form date near the top ("January 31, 2025" as 2025-01-31), or ""."""
    match = _LONG_DATE.search(text[:window])
    if not match:
        return ""
    return f"{match[3]}-{_MONTH_NUM[match[1].lower()]:02d}-{int(match[2]):02d}"


# What each kind is, for the model; the enum values are the only answers it may give.
KIND_HINTS: dict[DocumentKind, str] = {
    # Every kind, with its near neighbors named, so the model reads a definition and not a bare label.
    DocumentKind.DECLARATION: "the recorded declaration of covenants, conditions, and restrictions (the CC&Rs) itself",
    DocumentKind.AMENDMENT: "a recorded amendment to the CC&Rs or bylaws",
    DocumentKind.ANNEXATION: "a recorded declaration of annexation adding a phase to the community",
    DocumentKind.BYLAWS: "the association's bylaws",
    DocumentKind.ARTICLES: "the articles of incorporation",
    DocumentKind.OPERATING_RULES: "the owner's manual or rules and regulations members must follow",
    DocumentKind.POLICY: "a board-adopted policy (assessment collection, enforcement, ethics, ALPR); not an insurance policy",
    DocumentKind.ELECTION_RULES: "the association's election rules",
    DocumentKind.RESOLUTION: "a board resolution",
    DocumentKind.MINUTES: "minutes of a meeting that was held: what happened, motions, votes",
    DocumentKind.AGENDA: "an agenda for a meeting to be held",
    DocumentKind.EXECUTIVE_SESSION: "an executive session agenda or minutes",
    DocumentKind.NOTICE: "a general notice to members (a meeting, an election, work, a litigation disclosure); not a demand for money owed",
    DocumentKind.COMMITTEE_REPORT: "a committee's report to the board",
    DocumentKind.BALLOT: "a ballot or voting instructions",
    DocumentKind.ELECTION_RESULTS: "the certified results or tally of an election",
    DocumentKind.TREASURER_REPORT: "a treasurer's report to the board",
    DocumentKind.FINANCIAL_STATEMENT: "the association's balance sheet, income statement, or budget comparison from the manager",
    DocumentKind.BANK_STATEMENT: "a bank's monthly account statement with beginning and ending balances",
    DocumentKind.BUDGET: "the association's annual or pro forma budget",
    DocumentKind.RESERVE_STUDY: "a reserve study of components, useful lives, and funding",
    DocumentKind.FINANCIAL_REVIEW: "an accountant's review or audit of the financial statements",
    DocumentKind.TAX_RETURN: "a state or federal tax return (Form 1120-H, Form 199)",
    DocumentKind.ANNUAL_DISCLOSURE: "the annual disclosures package or the insurance summary sent to members",
    DocumentKind.INVOICE: "a vendor's invoice or bill to the association",
    DocumentKind.UTILITY_BILL: "a utility's bill for electricity, water, fire service, storm drainage, or street sweeping (SMUD, the City of Sacramento)",
    DocumentKind.TAX_BILL: "a county property tax bill",
    DocumentKind.PROPOSAL: "a vendor's proposal, bid, estimate, or quote, not yet signed",
    DocumentKind.CONTRACT: "a signed agreement with a vendor or professional, including a monthly service agreement",
    DocumentKind.LEASE: "a lease of a unit",
    DocumentKind.INSPECTION_REPORT: "an inspector's or vendor's inspection report on the buildings",
    DocumentKind.ELEVATED_ELEMENT_INSPECTION: "the Civil Code 5551 (SB 326) inspection report on balconies and other exterior elevated elements",
    DocumentKind.INSURANCE_POLICY: "an insurance policy or its declarations pages (flood, master, liability)",
    DocumentKind.EVIDENCE_OF_INSURANCE: "a certificate or evidence of insurance issued to a lender or buyer; not the policy itself",
    DocumentKind.SETTLEMENT: "a signed settlement agreement and release",
    DocumentKind.LEGAL_CORRESPONDENCE: "a letter from the association or its attorney about a legal claim, warranty claim, or dispute",
    DocumentKind.LEGAL_BRIEF: "a mediation or court brief",
    DocumentKind.RECORDED_LIEN: "a lien recorded with the county: a notice of delinquent assessment, a mechanic's lien, a lien release or bond",
    DocumentKind.DELINQUENCY_NOTICE: "the association's letter demanding past-due assessments or warning of a lien (a pre-lien notice); not a general notice",
    DocumentKind.OWNER_HISTORY: "the manager's full history of one owner's account over time",
    DocumentKind.OWNER_STATEMENT: "a single current statement of one owner's charges due",
    DocumentKind.ESCROW_REQUEST: "an escrow or title company's request for a unit's resale documents",
    DocumentKind.MEMBERSHIP_LIST: "a list of the members",
    DocumentKind.FORM: "a blank or filled-in form (registration, request, application)",
    DocumentKind.TEMPLATE: "a blank template the software ships",
    DocumentKind.CORRESPONDENCE: "a letter, guide, newsletter, contact sheet, or a bank's notice letter",
    DocumentKind.VIOLATION_NOTICE: "a notice to an owner of a rule violation: a courtesy reminder, a hearing notice, or a fine",
    DocumentKind.RESALE_DISCLOSURE: "the association's resale certificate or a lender's questionnaire for a unit being sold (CIV 4525)",
    DocumentKind.SECURITY_REPORT: "a security patrol's daily report of the property",
    DocumentKind.AUDIO: "an audio recording, such as a reading of the governing documents",
    DocumentKind.SECURITY_AGREEMENT: "a DRE form security agreement and escrow instructions between the subdivider and the association (RE 613, 643, 643E)",
    DocumentKind.SUBSIDY_AGREEMENT: "the subdivider's agreement to subsidize the association's assessments or operating costs for a phase",
    DocumentKind.SURETY_BOND: "a surety bond naming the association as obligee for the subdivider's obligations (RE 611, 643J, 643K)",
    DocumentKind.BOND_RELEASE: "a letter or request releasing a subdivider's bond or security held in escrow",
    DocumentKind.CONDOMINIUM_PLAN: "a recorded condominium plan",
    DocumentKind.MAP: "a map or parcel map",
    DocumentKind.GRANT_DEED: "a recorded grant deed",
    DocumentKind.DRE_REPORT: "a Department of Real Estate public report",
    DocumentKind.PLAN_SET: "architectural or design review plans",
    DocumentKind.IMAGE: "a photo, screenshot, or search result with little text",
}


class ModelUnavailable(RuntimeError):
    """Ollama is not reachable, or the model is not pulled; nothing was classified."""


@dataclass(frozen=True)
class ModelAnswer:
    kind: DocumentKind | None
    confidence: float
    period: str
    reason: str


class ModelClassifier:
    """A local model over a document's name and text, answering one kind from the closed list.

    ``fetch(url, payload)`` replaces HTTP in tests. The text is cut to
    ``max_chars`` so a long statement does not crowd the prompt.
    """

    def __init__(self, *, model: str = "", base_url: str = "", fetch=None, timeout: int = 300, max_chars: int = 6000, keep_alive: str = "5m") -> None:
        from jason.community.ollama_extractor import DEFAULT_CONTEXT, DEFAULT_MODEL, OLLAMA_URL

        self.model = model or DEFAULT_MODEL
        self.num_ctx = DEFAULT_CONTEXT
        self.base_url = (base_url or OLLAMA_URL).rstrip("/")
        self._fetch = fetch
        self.timeout = timeout
        self.max_chars = max_chars
        # How long Ollama keeps the model loaded after the last call. The default model is the one the readers and OCR
        # also use, so a short keep_alive would only unload it from under them; five minutes is Ollama's own default.
        self.keep_alive = keep_alive

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._fetch is not None:
            return self._fetch(f"{self.base_url}{path}", payload)
        from urllib.error import URLError
        from urllib.request import Request, urlopen

        from jason.locks import Resource, ResourceBusy, hold

        request = Request(f"{self.base_url}{path}", data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        try:
            # One model request from jason at a time (jason.locks); a wait past the timeout is reported, not retried.
            with hold(Resource.GPU, timeout=self.timeout, purpose=f"{self.model} classify"), urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except ResourceBusy as exc:
            raise ModelUnavailable(f"the model server is busy with another jason process: {exc}") from exc
        except (URLError, OSError) as exc:
            raise ModelUnavailable(f"Ollama at {self.base_url} did not answer: {exc}") from exc

    def _preflight(self) -> None:
        """Once per classifier: refuse to start on the CPU or short of memory (jason.local_ai)."""
        if self._fetch is not None or getattr(self, "_checked", False):
            return
        from jason.local_ai import LocalAIUnavailable, preflight

        try:
            preflight(self.model, ollama_url=self.base_url)
        except LocalAIUnavailable as exc:
            raise ModelUnavailable(str(exc)) from exc
        self._checked = True

    def classify(self, name: str, text: str) -> ModelAnswer:
        self._preflight()
        kinds = [kind.value for kind in DocumentKind]
        schema = {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": kinds + ["unknown"]},
                "confidence": {"type": "number"},
                "period": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["kind", "confidence", "reason"],
        }
        hints = "\n".join(f"- {kind.value}: {KIND_HINTS.get(kind, kind.value.replace('_', ' '))}" for kind in DocumentKind)
        prompt = (
            "You classify one document from a California homeowners association's records. Answer with the single kind "
            "that fits best, or unknown when none fits. The kinds:\n"
            + f"{hints}\n"
            "Give confidence from 0 to 1, the period the document covers as YYYY-MM-DD or YYYY-MM or YYYY if it states one, "
            "and one short sentence of reason quoting the words that decided it. Do not guess from the file name alone.\n\n"
            f"File name: {name}\n\nText:\n{text[: self.max_chars]}"
        )
        data = self._post("/api/chat", {"model": self.model, "messages": [{"role": "user", "content": prompt}], "format": schema,
                                         "stream": False, "think": False, "keep_alive": self.keep_alive,
                                         "options": {"temperature": 0, "num_ctx": self.num_ctx}})
        return parse_model_answer(str((data.get("message") or {}).get("content") or data.get("response") or ""))


def parse_model_answer(raw: str) -> ModelAnswer:
    """The model's JSON as a ``ModelAnswer``; an answer outside the list is no kind."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ModelAnswer(None, 0.0, "", "the model did not answer in JSON")
    value = str(data.get("kind") or "")
    try:
        kind = DocumentKind(value)
    except ValueError:
        kind = None
    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence") or 0)))
    except (TypeError, ValueError):
        confidence = 0.0
    period = str(data.get("period") or "")
    if period and not re.fullmatch(r"20\d\d(-\d\d(-\d\d)?)?", period):
        period = ""
    return ModelAnswer(kind, confidence, period, str(data.get("reason") or "")[:300])
