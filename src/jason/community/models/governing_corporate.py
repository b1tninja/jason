"""The association's corporate instruments: the articles of incorporation and the bylaws.

The articles are a Secretary of State filing, not a recorded instrument. Besides the statement of purposes, an
association's articles identify it as an association formed to manage a common interest development under the
Davis-Stirling Act, state its business or corporate office (or, when that office is off the site, the development's
front street and nearest cross street), and name its managing agent, if any (CIV 4280(a)(1)-(3)); a filing made
before 2014 under former section 1363.5 is deemed to comply (4280(c)).

The bylaws are the association's own. Their election provisions answer to the Act: an election for each board seat
at the end of its term and at least once every four years (CIV 5100(a)(2)); a candidate may be disqualified only as
5105(b)-(e) allow, through the bylaws or the election rules. The model reads the board's size, the directors' terms,
the member and board quorums, cumulative voting, and the election provisions, and says when the extract stops short
of the pages its own contents list (the adoption certificate is often past that point).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from jason.community.document_models import DocumentModel, Finding, ModelContext, Severity, dates_in, register, squash
from jason.community.symbols import DocumentKind

from .governing_rules import RULE_NOTICE_DAYS, HearingTerms, hearing_findings, hearing_terms
from .governing_shared import READER, coverage_finding, number_word, page_coverage, repealed_finding, repealed_sections

ELECTION_CYCLE_YEARS = 4  # CIV 5100(a)(2)
_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "nine": 9, "eleven": 11}


@dataclass
class ArticlesRecord:
    name: str = ""
    corporation_type: str = ""          # "nonprofit mutual benefit corporation"
    filed: date | None = None           # the Secretary of State's endorsement
    signed: date | None = None          # the incorporator's date
    entity_number: str = ""             # the Secretary of State's number, when the copy prints it
    agent_for_service: str = ""
    davis_stirling_statement: bool = False   # CIV 4280(a)(1)
    office_or_streets: bool = False          # CIV 4280(a)(2)
    front_street: str = ""
    cross_street: str = ""
    managing_agent_statement: bool = False   # CIV 4280(a)(3)
    declaration_referenced: bool = False
    amendment_vote: str = ""


@dataclass
class BylawsRecord:
    title: str = ""
    version: str = ""                   # the drafter's footer ("9-17-07 v3")
    adopted: date | None = None
    certificate_of_adoption: bool = False    # the certificate's text, not just its line in the contents
    directors_initial: int | None = None
    directors_min: int | None = None
    directors_max: int | None = None
    term_years: int | None = None
    staggered_terms: bool = False
    term_limit: str = ""
    member_quorum: str = ""
    board_quorum: str = ""
    cumulative_voting: bool = False
    annual_meeting: bool = False
    secret_ballot: bool = False
    inspectors_of_election: bool = False
    nominations: bool = False
    proxies: bool = False
    rule_notice_days: int | None = None      # notice of a proposed rule change, days before the board decides (CIV 4360(a))
    rule_reversal_vote: str = ""             # the member vote that reverses a rule change (CIV 4365(d))
    suspends_voting_for_default: bool = False  # the board may suspend a member's vote while in default
    hearing: HearingTerms | None = None      # the discipline procedure (CIV 5855)
    certificate_page: int | None = None      # the page the contents give the certificate of adoption
    repealed_sections: tuple[str, ...] = ()
    toc_last_page: int | None = None
    last_page_seen: int | None = None
    sections: tuple[str, ...] = field(default_factory=tuple)   # article headings the text reaches


def _number(word: str) -> int | None:
    word = (word or "").strip().lower()
    if word.isdigit():
        return int(word)
    return _WORDS.get(word)


class ArticlesModel(DocumentModel):
    kind = DocumentKind.ARTICLES
    name = "articles-of-incorporation"
    required = ("name", "corporation_type", "filed", "agent_for_service")

    def parse(self, text: str, context: ModelContext) -> ArticlesRecord | None:
        flat = squash(text)
        if not re.search(r"ARTICLES\s+OF\s+INCORPORATION", flat[:3000], re.I):
            return None
        r = ArticlesRecord()
        hit = re.search(r"The\s+name\s+of\s+this\s+corporation\s+is\s+([^.]{3,120})\.", flat, re.I)
        r.name = hit.group(1).strip() if hit else ""
        hit = re.search(r"(nonprofit\s+(?:mutual|public)\s+benefit\s+corporation)", flat, re.I)
        r.corporation_type = " ".join(hit.group(1).lower().split()) if hit else ""
        hit = re.search(r"office\s+of\s+the\s+Secretary\s+of\s+State\s+of\s+the\s+State\s+of\s+California\s+(.{0,40})", flat, re.I)
        if hit:
            filed = dates_in(re.sub(r"(\d)\s(\d)(?=\s+\d{4})", r"\1\2", hit.group(1)))
            r.filed = filed[0] if filed else None
        hit = re.search(r"\bDate[d]?:?\s+((?:January|February|March|April|May|June|July|August|September|October|November|December)"
                        r"\s+\d{1,2},?\s+\d{4})", flat)
        r.signed = dates_in(hit.group(1))[0] if hit and dates_in(hit.group(1)) else None
        hit = re.search(r"(?:Entity|Corporate|File)\s+(?:No\.?|Number)\s*:?\s*([A-Z]?\d{6,8})", flat)
        r.entity_number = hit.group(1) if hit else ""
        hit = re.search(r"agent\s+for\s+service\s+of\s+process\s+(?:is|are)\s+([^.;]{3,120}?)(?:[.;]|\s\d)", flat, re.I)
        r.agent_for_service = hit.group(1).strip(" ,") if hit else ""
        r.davis_stirling_statement = bool(re.search(r"formed\s+to\s+manage\s+a\s+common\s+interest\s+development\s+under\s+the\s+Davis",
                                                    flat, re.I))
        hit = re.search(r"front\s+street\s+and\s+the\s+nearest\s+cross\s+street[^.]{0,60}?are\s+([A-Z][\w ]+?)\s+and\s+([A-Z][\w ]+?)\.", flat,
                        re.I)
        if hit:
            r.front_street, r.cross_street = hit.group(1).strip(), hit.group(2).strip()
        r.office_or_streets = bool(hit or re.search(r"(?:business|corporate)\s+(?:or\s+corporate\s+)?office", flat, re.I))
        r.managing_agent_statement = bool(re.search(r"managing\s+agent", flat, re.I))
        r.declaration_referenced = bool(re.search(r"Declaration\s+of\s+Covenants", flat, re.I))
        hit = re.search(r"amendment\s+of\s+these\s+Articles\s+shall\s+require\s+([^.]{10,300})", flat, re.I)
        r.amendment_vote = hit.group(1).strip() if hit else ""
        return r

    def check(self, r: ArticlesRecord, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        early = r.filed is not None and r.filed < date(2014, 1, 1)
        for flag, code, what, sub in (
                (r.davis_stirling_statement, "no-davis-stirling-statement", "identify the corporation as an association formed to manage a "
                 "common interest development under the Davis-Stirling Act", "(a)(1)"),
                (r.office_or_streets, "no-office-or-streets", "state the business office or the development's front and cross streets",
                 "(a)(2)"),
                (r.managing_agent_statement, "no-managing-agent-statement", "state the managing agent (or that there is none)", "(a)(3)")):
            if not flag:
                note = "; a filing before 2014 under former 1363.5 is deemed to comply" if early else ""
                found.append(Finding(code, f"the text does not {what}{note}", Severity.CHECK, f"CIV 4280{sub}" + (", (c)" if early else "")))
        corporate = str(getattr(context.community, "corporate_name", "") or "")
        if corporate and r.name and " ".join(r.name.upper().split()) != corporate.upper():
            found.append(Finding("name-differs", f"the articles name {r.name!r}; the specification's corporate name is {corporate!r}",
                                 Severity.CHECK))
        first = f" (the first was due {r.filed + timedelta(days=90)})" if r.filed else ""
        found.append(Finding("statement-of-information", "the Statement of Information filed with the Secretary of State must also "
                             "identify the corporation as a Davis-Stirling association, and the Statement by Common Interest Development "
                             f"Association (SI-CID) goes with it within 90 days after the articles{first} and every two years after; a "
                             "change of the managing agent's or responsible officer's address is reported within 60 days; the library holds "
                             "no filed statement, and the Secretary of State's records are the source", Severity.INFO,
                             "CIV 4280(b), 5405(a)-(c); CORP 8210"))
        return found


class BylawsModel(DocumentModel):
    kind = DocumentKind.BYLAWS
    name = "bylaws"
    required = ("title", "directors_min", "directors_max", "term_years", "member_quorum", "board_quorum")

    def parse(self, text: str, context: ModelContext) -> BylawsRecord | None:
        flat = squash(text)
        if not re.search(r"\bBY-?\s?LAWS\b", flat[:3000], re.I):
            return None
        r = BylawsRecord()
        hit = re.search(r"\b(BY-?\s?LAWS\s+OF\s+(?:THE\s+)?[A-Z][A-Z ,.&'-]{3,80}?ASSOCIATION)\b", flat[:3000])
        r.title = " ".join(hit.group(1).split()) if hit else (READER.read_title(text) or "BYLAWS")
        hit = re.search(r"\b(\d{1,2}-\d{1,2}-\d{2,4}\s+v\d+)\b", flat)
        r.version = hit.group(1) if hit else ""
        certificate = re.search(r"CERTIFICATE\s+OF\s+(?:ADOPTION|SECRETARY)[^.]{0,40}\s+(?:I|The\s+undersigned)\b[^.]{0,200}"
                                r"(?:certify|hereby)", flat, re.I)
        r.certificate_of_adoption = bool(certificate)
        if certificate:
            # The certificate itself, not its line in the contents; "duly adopted ... on <date>" is the adoption.
            tail = flat[certificate.start():certificate.start() + 1500]
            hit = re.search(r"adopted\b[^.]{0,120}?\bon\s+([A-Z][a-z]+\.?\s+\d{1,2},?\s+\d{4})", tail)
            dated = dates_in(hit.group(1)) if hit else dates_in(tail)
            r.adopted = dated[0] if dated else None
        hit = re.search(r"initial\s+Board\s+of\s+Directors\s+shall\s+be\s+comprised\s+of\s+(\w+)\s*\((\d+)\)", flat, re.I)
        r.directors_initial = int(hit.group(2)) if hit else None
        hit = re.search(r"consist\s*of\s*not\s+less\s+than\s+(\w+)\s*\((\d+)\)\s*nor\s+more\s+than\s+(\w+)\s*\((\d+)\)\s*Directors", flat, re.I)
        if hit:
            r.directors_min, r.directors_max = int(hit.group(2)), int(hit.group(4))
        else:
            hit = re.search(r"Board\s+of\s+Directors\s+shall\s+consist\s+of\s+(\w+)\s*(?:\((\d+)\))?\s*(?:Directors|persons|members)", flat, re.I)
            if hit:
                r.directors_min = r.directors_max = int(hit.group(2)) if hit.group(2) else _number(hit.group(1))
        hit = re.search(r"terms?\s+of\s+(\w+)\s*\((\d+)\)\s*years?", flat, re.I) or re.search(r"term\s+of\s+(\w+)\s+years?", flat, re.I)
        if hit:
            r.term_years = int(hit.group(2)) if hit.lastindex and hit.lastindex >= 2 and hit.group(2) else _number(hit.group(1))
        r.staggered_terms = bool(re.search(r"staggered\s+terms|alternating\s+years", flat, re.I))
        hit = re.search(r"(no\s+limitation\s+on\s+the\s+number\s+of\s+consecutive\s+terms|[^.]{0,80}term\s+limit[^.]{0,80})", flat, re.I)
        r.term_limit = hit.group(1).strip() if hit else ""
        hit = re.search(r"Members\s+entitled\s+to\s+cast\s+(?:at\s+least\s+)?([^.]{3,60}?)\s+of\s+the\s+Total\s+Voting\s+Power\s+shall\s+"
                        r"constitute\s+a\s+quorum", flat, re.I) or re.search(r"quorum[^.]{0,40}\b((?:one|two)-(?:third|half)[^.]{0,20}|\d{1,2}\s?%)", flat,
                                                                              re.I)
        r.member_quorum = hit.group(1).strip() if hit else ""
        hit = re.search(r"(A\s+majority\s+of\s+the\s+(?:number\s+of\s+)?Directors[^.]{0,80}?)\s+shall\s+constitute\s+a\s+quorum", flat, re.I)
        r.board_quorum = hit.group(1).strip() if hit else ""
        r.cumulative_voting = bool(re.search(r"Cumulative\s+Voting", flat, re.I))
        r.annual_meeting = bool(re.search(r"Annual\s+Meeting", flat, re.I))
        r.secret_ballot = bool(re.search(r"secret\s+ballot", flat, re.I))
        r.inspectors_of_election = bool(re.search(r"inspectors?\s+of\s+elections?", flat, re.I))
        r.nominations = bool(re.search(r"\bNomination", flat, re.I))
        r.proxies = bool(re.search(r"\bprox(?:y|ies)\b", flat, re.I))
        hit = re.search(r"Notice\s+of\s+Proposed\s+Rule\s+Change.{0,400}?at\s+least\s+([\w-]+(?:\s*\(\d+\))?)\s+days\s+before", flat, re.I)
        r.rule_notice_days = number_word(hit.group(1)) if hit else None
        hit = re.search(r"Rule\s+Change\s+adopted\s+by\s+the\s+Board\s+may\s+be\s+reversed\s+by\s+([^.]{5,120}?)\s*\.", flat, re.I)
        r.rule_reversal_vote = hit.group(1).strip() if hit else ""
        r.suspends_voting_for_default = bool(re.search(r"suspend\s+the\s+voting[^.]{0,200}(?:default|delinquen)", flat, re.I))
        r.hearing = hearing_terms(text)
        hit = re.search(r"CERTIFICATE\s+OF\s+ADOPTION\s*(?:\.\s?){3,}\s*(\d{1,3})\b", flat[:30000], re.I)
        r.certificate_page = int(hit.group(1)) if hit else None
        r.repealed_sections = repealed_sections(flat)
        r.toc_last_page, r.last_page_seen = page_coverage(text)
        r.sections = tuple(sorted(dict.fromkeys(m.group(1) for m in re.finditer(r"\bARTICLE\s+(\d{1,2})\s+[A-Z]{3}", flat)), key=int))
        return r

    def check(self, r: BylawsRecord, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if r.term_years and r.term_years > ELECTION_CYCLE_YEARS:
            found.append(Finding("term-exceeds-election-cycle", f"directors serve {r.term_years}-year terms; each seat must be elected at "
                                 f"least once every {ELECTION_CYCLE_YEARS} years", Severity.PROBLEM, "CIV 5100(a)(2)"))
        if not r.certificate_of_adoption:
            where = (f": the contents put it on page {r.certificate_page}, past page {r.last_page_seen}, where the extract stops"
                     if r.certificate_page and r.last_page_seen and r.last_page_seen < r.certificate_page
                     else " (it may be past the pages the extract reaches, or unsigned)")
            found.append(Finding("no-adoption-certificate-in-text", f"no certificate of adoption is printed in the text{where}; the "
                                 "adoption date is not in the text", Severity.CHECK))
        if r.directors_min and r.directors_max and r.directors_min > r.directors_max:
            found.append(Finding("board-size-inverted", f"the board's minimum ({r.directors_min}) exceeds its maximum ({r.directors_max})",
                                 Severity.PROBLEM))
        if not r.secret_ballot:
            found.append(Finding("no-secret-ballot-provision", "the text does not provide for secret-ballot elections of directors; the "
                                 "Act requires them regardless", Severity.INFO, "CIV 5100(a)(1), (c)"))
        if r.rule_notice_days is not None and r.rule_notice_days < RULE_NOTICE_DAYS:
            found.append(Finding("rule-notice-short", f"the bylaws give {r.rule_notice_days} days' notice of a proposed rule change; the "
                                 f"statute requires {RULE_NOTICE_DAYS}", Severity.PROBLEM, "CIV 4360(a)"))
        if r.suspends_voting_for_default:
            found.append(Finding("vote-suspension-for-default", "the bylaws let the board suspend a member's voting rights while in default; "
                                 "the election rules must deny a ballot only to a non-member, notwithstanding any other law",
                                 Severity.CHECK, "CIV 5105(h)(1)"))
        found += hearing_findings(r.hearing)
        found += repealed_finding(r.repealed_sections, context.data_dir)
        found += coverage_finding(r.toc_last_page, r.last_page_seen)
        return found


register(ArticlesModel())
register(BylawsModel())

__all__ = ["ArticlesRecord", "BylawsRecord", "ArticlesModel", "BylawsModel"]
