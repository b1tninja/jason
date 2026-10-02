"""Board resolutions: the association's special and administrative resolutions and their action records.

The board acts only at a meeting (Civil Code 4910(a)) on an item its agenda noticed (4930(a)); a resolution is the
written act, and its action record is the vote. A resolution that moves reserve money shapes to the law: a temporary
transfer to operating needs an agenda notice stating the reasons, repayment options, and whether a special assessment
may be considered (5515(a), (b)), a written finding in the minutes of why and when and how the money is repaid
(5515(c)), and restoration within a year (5515(d)); a withdrawal from a reserve account takes two signers (5510(a)).

The association's resolutions are one template signed through Adobe Acrobat Sign: a title block ("SPECIAL RESOLUTION
[NUMBER n]", "Relating to ..."), WHEREAS recitals, a NOW, THEREFORE, BE IT RESOLVED clause, an IN WITNESS WHEREOF
block signed by the President and Treasurer, and a RESOLUTION ACTION RECORD page (type, number, pertaining to, motion,
second, each director's YES/NO/ABSTAIN, the Secretary's attestation). The e-signature stamps print as
"Name (Mon d, yyyy hh:mm PST)". The form's filled values print either in place ("X YES") or after the page, in form
order (type, number, pertaining to, mover, seconder, then one mark per director).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from jason.community.document_models import (
    DocumentModel,
    Finding,
    ModelContext,
    Severity,
    dates_in,
    first,
    register,
    squash,
)
from jason.community.invoices import parse_date
from jason.community.models.meetings import AgendaModel, dollars, library_text, meeting_files, normalize, walk
from jason.community.symbols import DocumentKind


class ResolutionType(Enum):
    SPECIAL = "special"
    ADMINISTRATIVE = "administrative"
    POLICY = "policy"
    EMERGENCY = "emergency"


class ResolutionSubject(Enum):
    BORROW_RESERVES = "borrow_reserves"
    INVEST_RESERVES = "invest_reserves"
    MEETING_SCHEDULE = "meeting_schedule"
    FORECLOSURE = "foreclosure"
    EXCESS_INCOME = "excess_income"      # IRS Revenue Ruling 70-604
    OTHER = "other"


class Vote(Enum):
    YES = "yes"
    NO = "no"
    ABSTAIN = "abstain"


OFFICES = ("President", "Vice President", "Treasurer", "Secretary", "Member at large", "Director")


@dataclass(frozen=True)
class DirectorVote:
    office: str
    name: str = ""
    vote: Vote | None = None


@dataclass(frozen=True)
class Signature:
    name: str
    title: str = ""
    signed_on: date | None = None


@dataclass
class Resolution:
    association: str = ""
    resolution_type: ResolutionType | None = None
    number: str = ""
    title: str = ""
    subject: ResolutionSubject | None = None
    whereas: tuple[str, ...] = ()
    resolved: tuple[str, ...] = ()
    amounts: tuple[int, ...] = ()                   # cents, in the resolved clauses
    statutes: tuple[str, ...] = ()                  # the Civil Code sections the recitals cite
    adopted_on: date | None = None
    signers: tuple[Signature, ...] = ()             # the signature blocks and the e-signature each carries
    e_signatures: tuple[Signature, ...] = ()
    action_record: bool = False
    motion_by: str = ""
    seconded_by: str = ""
    votes: tuple[DirectorVote, ...] = ()
    vote_marks: int = 0                             # marks printed after the page, not tied to a column in the text
    attested_by: str = ""
    attested_on: date | None = None
    attestation_signed: bool = False
    exhibits: tuple[str, ...] = ()


_ESIGN = re.compile(r"^\s*([A-Z][\w.'-]+(?: [A-Z][\w.'-]+){1,3}) \(([A-Z][a-z]{2} \d{1,2}, \d{4}) \d{1,2}:\d{2} [A-Z]{2,4}\)", re.M)
_BLOCK = re.compile(r"_{8,}\s*\n\s*([A-Z][\w.'-]+(?: [A-Z][\w.'-]+){1,3})\s*\n\s*(" + "|".join(OFFICES) + r")\b", re.I)
_TYPE_WORDS = {"special": ResolutionType.SPECIAL, "administrative": ResolutionType.ADMINISTRATIVE, "policy": ResolutionType.POLICY,
               "emergency": ResolutionType.EMERGENCY}


def _same_person(a: str, b: str) -> bool:
    x, y = a.lower().split(), b.lower().split()
    return bool(x and y) and (x[-1] == y[-1] or x[0] == y[0] and x[-1][:4] == y[-1][:4])


def _date_from_number(number: str) -> date | None:
    digits = re.sub(r"\D", "", number)[:8]
    if len(digits) == 8:
        try:
            return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
        except ValueError:
            return None
    return None


def _subject(text: str) -> ResolutionSubject:
    t = text.lower()
    for subject, pattern in ((ResolutionSubject.BORROW_RESERVES, r"borrow"), (ResolutionSubject.INVEST_RESERVES, r"invest"),
                             (ResolutionSubject.MEETING_SCHEDULE, r"schedul\w* (?:of )?meetings|meeting schedule"),
                             (ResolutionSubject.FORECLOSURE, r"foreclos"), (ResolutionSubject.EXCESS_INCOME, r"70-604|excess (?:income|assessments)")):
        if re.search(pattern, t):
            return subject
    return ResolutionSubject.OTHER


class ResolutionModel(DocumentModel):
    kind = DocumentKind.RESOLUTION
    name = "board-resolution"
    required = ("resolution_type", "title", "resolved", "adopted_on")

    def parse(self, text: str, context: ModelContext) -> Resolution | None:
        t = normalize(text)
        t = re.sub(r"\A#[^\n]*\n(?:\s*\n|- \w+: [^\n]*\n)*", "", t)  # the library's Markdown header
        if not re.search(r"\bRESOLUTION\b", t, re.I) or not re.search(r"WHEREAS|RESOLVED", t):
            return None
        flat = squash(t)
        r = Resolution()
        r.association = first(r"^\s*([A-Z][A-Z .]+ASSOCIATION)\s*$", t, flags=re.M).title()
        m = re.search(r"\b(SPECIAL|ADMINISTRATIVE|POLICY|EMERGENCY)\s+RESOLUTION", t, re.I)
        r.resolution_type = _TYPE_WORDS.get(m.group(1).lower()) if m else None
        r.number = first(r"RESOLUTION\s+(?:NUMBER|NO\.?|#)\s*([\w-]*\d[\w-]*)", t)
        r.title = first(r"^\s*(Relating to [^\n]+)", t, flags=re.M)
        body = flat.split("RESOLUTION ACTION RECORD")[0]
        recitals = re.split(r"\bWHEREAS,?\s*", body.split("NOW, THEREFORE")[0])[1:]
        r.whereas = tuple(squash(w) for w in recitals if squash(w))
        resolved = re.findall(r"(?:BE IT (?:FURTHER )?RESOLVED)\s*,?\s*(.*?)(?=BE IT (?:FURTHER )?RESOLVED|IN WITNESS WHEREOF|$)", body)
        r.resolved = tuple(squash(re.sub(r"\s\d\s*$", "", x)) for x in resolved if squash(x))
        r.amounts = tuple(a for a in (dollars(x) for clause in r.resolved for x in re.findall(r"\$\s?[\d,]+(?:\.\d\d)?", clause)) if a is not None)
        r.statutes = tuple(dict.fromkeys(re.findall(r"(?:Section|§)\s*(\d{4})\b", body)))
        r.subject = _subject(" ".join([r.title, *r.resolved]))
        r.e_signatures = tuple(Signature(m.group(1), "", parse_date(m.group(2))) for m in _ESIGN.finditer(t))
        head = t.split("RESOLUTION ACTION RECORD")[0]
        blocks = []
        for m in _BLOCK.finditer(head):
            signed = next((s.signed_on for s in r.e_signatures if _same_person(s.name, m.group(1))), None)
            blocks.append(Signature(m.group(1), m.group(2).title(), signed))
        r.signers = tuple(blocks)
        r.exhibits = tuple(dict.fromkeys(re.findall(r"^\s*(EXHIBIT [A-Z])\s*$", t, re.M)))
        if "RESOLUTION ACTION RECORD" in t:
            self._action_record(t, r)
        held = first(r"adopted at a meeting of the Board of Directors held:?\s*([^\n]+)", t)
        r.adopted_on = parse_date(held) if held else None
        if r.adopted_on is None:
            r.adopted_on = _date_from_number(r.number)
        if r.adopted_on is None:
            dated = re.search(r"DATED:\s*_+,\s*(\d{4})", t)
            if dated:
                m = re.search(r"^\s*((?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2})\s*$", t, re.M)
                r.adopted_on = parse_date(f"{m.group(1)}, {dated.group(1)}") if m else None
        return r

    def _action_record(self, t: str, r: Resolution) -> None:
        r.action_record = True
        page = t.split("RESOLUTION ACTION RECORD", 1)[1]
        votes = []
        for office in OFFICES:
            m = re.search(r"(?:([A-Z][\w.'-]+(?: [A-Z][\w.'-]+){1,3})\s*\n\s*)?" + office + r"\s*\n((?:\s*(?:X\s*|☒\s*|☐\s*)?(?:YES|NO|ABSTAIN)\s*\n?){1,3})",
                          page, re.I)
            if not m:
                continue
            marked = re.search(r"(?:X|☒)\s*(YES|NO|ABSTAIN)", m.group(2))
            name = squash(m.group(1) or "")
            votes.append(DirectorVote(office, "" if re.search(r"\bVote\b", name) else name,
                                      Vote(marked.group(1).lower()) if marked else None))
        r.votes = tuple(votes)
        m = re.search(r"ATTESTATION:.*?_{5,}\s*\n\s*([A-Z][\w.'-]+(?: [A-Z][\w.'-]+){1,3})\s*\n\s*Secretary", page, re.S)
        r.attested_by = squash(m.group(1)) if m else ""
        tail = page.split("Date", 1)[1] if re.search(r"_{5,}\s*\n\s*Date", page) else ""
        tail = re.split(r"\n\s*(?:EXHIBIT [A-Z]|[A-Z][A-Za-z ]+ Resolution\s*\n\s*[A-Z ]+ASSOCIATION)", tail)[0]
        lines = [squash(x) for x in tail.splitlines() if squash(x) and not re.fullmatch(r"\d{1,2}", squash(x))]
        rest = lines
        if lines and lines[0].lower() in _TYPE_WORDS:
            if r.resolution_type is None:
                r.resolution_type = _TYPE_WORDS[lines[0].lower()]
            rest = lines[1:]
            if rest and re.fullmatch(r"[\d-]{6,}", rest[0]):
                r.number = r.number or rest[0]
                rest = rest[1:]
            if rest and not _ESIGN.match(rest[0]):
                rest = rest[1:]  # "Pertaining to"
        if rest:
            names = []
            for x in rest:
                if not re.fullmatch(r"[A-Z][\w.'-]+(?: [A-Z][\w.'-]+){1,3}", x) or _ESIGN.match(x):
                    break
                names.append(x)
            # The filled fields print in form order: mover and seconder, then the directors' names where the form left
            # them blank. Two names are the mover and seconder; five are the directors; seven are both.
            offices = len(r.votes)
            if len(names) == 2 or (offices and len(names) == offices + 2):
                r.motion_by, r.seconded_by = names[0], names[1]
                names = names[2:]
            if offices and len(names) >= offices and not any(v.name for v in r.votes):
                r.votes = tuple(DirectorVote(v.office, n, v.vote) for v, n in zip(r.votes, names))
        r.vote_marks = sum(1 for x in lines if re.fullmatch(r"[XI☒✓]", x))
        signed = [s for s in r.e_signatures if r.attested_by and _same_person(s.name, r.attested_by)]
        after = dates_in(" ".join(lines[-2:])) if lines else []
        r.attestation_signed = bool(signed)
        r.attested_on = signed[-1].signed_on if signed else (after[-1] if after else None)

    def check(self, r: Resolution, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        unsigned = [s for s in r.signers if s.signed_on is None]
        if not r.signers and not r.e_signatures:
            found.append(Finding("unsigned", "the resolution has no signature block or signature in the text", Severity.CHECK))
        elif r.signers and len(unsigned) == len(r.signers):
            found.append(Finding("unsigned", "no signature block carries a signature in the text (a wet or image signature may exist)",
                                 Severity.CHECK))
        elif unsigned:
            found.append(Finding("signature-missing", "no signature in the text for " + ", ".join(f"{s.name} ({s.title})" for s in unsigned),
                                 Severity.CHECK))
        if not r.action_record:
            found.append(Finding("no-vote-record", "the resolution has no action record of the directors' votes", Severity.CHECK, "CIV 4910(a)"))
        else:
            marked = [v for v in r.votes if v.vote is not None]
            if marked:
                yes = sum(1 for v in marked if v.vote is Vote.YES)
                found.append(Finding("vote", f"{yes} of {len(r.votes)} directors voted yes", Severity.INFO))
                if yes * 2 <= len(r.votes):
                    found.append(Finding("vote-short", "yes votes are not a majority of the directors listed", Severity.CHECK))
            elif r.vote_marks:
                found.append(Finding("vote-marks", f"{r.vote_marks} vote marks, which the text does not tie to a YES, NO, or ABSTAIN column",
                                     Severity.CHECK))
            else:
                found.append(Finding("no-votes-marked", "the action record's vote boxes are empty in the text", Severity.CHECK))
            if not (r.motion_by and r.seconded_by):
                found.append(Finding("no-mover", "the action record does not name who moved and seconded", Severity.INFO))
            if not r.attestation_signed:
                found.append(Finding("attestation-unsigned", "the Secretary's attestation carries no signature in the text", Severity.CHECK))
        if r.subject is ResolutionSubject.BORROW_RESERVES:
            found += self._borrowing(r)
        found += self._against_meeting(r, context)
        return found

    def _borrowing(self, r: Resolution) -> list[Finding]:
        text = " ".join(r.whereas + r.resolved)
        found = []
        for code, label, pattern in (("borrowing-reasons", "the reasons the transfer is needed", r"cash ?flow|because|result in|due to|in order to"),
                                     ("borrowing-repayment", "when and how the money will be repaid", r"restor|repa(?:y|id)")):
            if not re.search(pattern, text, re.I):
                found.append(Finding(code, f"the resolution does not state {label}; the board's written finding must, in its minutes",
                                     Severity.CHECK, "CIV 5515(c)"))
        if not re.search(r"special assessment", text, re.I):
            found.append(Finding("borrowing-special-assessment", "the resolution does not say whether a special assessment may be considered",
                                 Severity.CHECK, "CIV 5515(b)"))
        if not re.search(r"Notice of Intent to Borrow|notice of the intent|4920", text, re.I):
            found.append(Finding("borrowing-notice", "the resolution does not recite the meeting notice of the intent to transfer",
                                 Severity.CHECK, "CIV 5515(a)"))
        if r.adopted_on:
            due = r.adopted_on + timedelta(days=365)
            found.append(Finding("restore-reserves", f"restore the transferred money to reserves by {due}, or delay it only on a documented "
                                 "finding after the same notice", Severity.INFO, "CIV 5515(d)"))
        return found

    def _against_meeting(self, r: Resolution, context: ModelContext) -> list[Finding]:
        """The meeting that adopted it: its agenda in the library should carry the item."""
        if context.data_dir is None or r.adopted_on is None:
            return []
        agendas = meeting_files(context, DocumentKind.AGENDA, r.adopted_on)
        if not agendas:
            return [Finding("no-agenda-on-file", f"the library has no agenda for the {r.adopted_on} meeting that adopted it", Severity.CHECK,
                            "CIV 4930(a), 5200(a)(8)")]
        agenda = AgendaModel().parse(library_text(context, agendas[0]), context)
        words = {"borrow_reserves": r"borrow", "invest_reserves": r"invest", "meeting_schedule": r"schedul|calendar",
                 "foreclosure": r"foreclos", "excess_income": r"70-604", "other": re.escape(r.title[11:30]) if r.title else r"resolution"}
        pattern = words[r.subject.value] if r.subject else r"resolution"
        hits = [i for i in walk(agenda.items) if re.search(pattern, " ".join([i.title, i.notes, *i.attachments]), re.I)] if agenda else []
        if hits:
            return [Finding("on-agenda", f"the {r.adopted_on} agenda carries it ('{hits[0].title}')", Severity.INFO, "CIV 4930(a)")]
        return [Finding("not-on-agenda", f"the {r.adopted_on} agenda in the library has no item for this resolution", Severity.CHECK, "CIV 4930(a)")]


register(ResolutionModel())

__all__ = ["Resolution", "ResolutionType", "ResolutionSubject", "Vote", "DirectorVote", "Signature", "ResolutionModel"]
