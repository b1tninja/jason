"""Signature blocks: where they start, what they carry, and the role they point to; and the store keeps no body."""

from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import httpx

from jason.community.signatures import (LicenseKind, SignatureRole, html_to_text, parse_signature, read_signature,
                                        split_signature)
from jason.community.sources import Sender, SourceKind

PROPERTY_MANAGER = """Hi,

The tenant at the unit moves out on the 30th. Please send the move-out checklist.

Best regards,
Jordan Example
Property Manager
Example Property Management, Inc.
Office: (916) 555-0142 | Cell: (916) 555-0199
2100 Example Blvd, Suite 200, Sacramento, CA 95815
www.example.com
CA DRE #01234567
"""

TITLE_OFFICER = """Hello,

Attached is the demand request for the property. Please provide the payoff by Friday.

Thank you,

Casey Example | Escrow Officer
Example Title Company
Direct: 916.555.0123
1234 Example Way, Roseville, CA 95661

WIRE FRAUD ALERT: Never wire funds based on email instructions. Call our office to verify.
CONFIDENTIALITY NOTICE: This e-mail message is intended only for the person or entity to which it is addressed and may contain confidential information.
"""

CONTRACTOR = """Hi Board,

Our crew can start Monday. The estimate is attached.

--
Riley Example
Estimator
Example Roofing & Construction LLC
CSLB Lic. #123456
T: 916-555-0177
www.example.com
"""

OWNER = """The light by my garage is out again, and the neighbor's dog was barking all night.

Jane

Sent from my iPhone
"""

REALTOR_REPLY = """Sounds good, see you then.

Thanks,
Morgan Example
Example Realty | REALTOR®
DRE# 02345678
(916) 555-0100

On Tue, Sep 29, 2026 at 10:15 AM Mystique Board <board@example.com>
wrote:
> Can you confirm the closing date?
>
> Best regards,
> Pat Example
> Escrow Officer, Example Title
"""

OUTLOOK_REPLY = """Please see my answers below.

Regards,
Sam Example
Attorney at Law
Example Law Group, LLP
State Bar No. 123456

________________________________
From: Board <board@example.com>
Sent: Monday, September 28, 2026 9:00 AM
Subject: Owner dispute

Jordan Example
Property Manager
CA DRE #01234567
"""

INSURER_HTML = """<html><head><style>p {color: red}</style></head><body>
<div dir="ltr">Please see the attached renewal proposal.<br><br>Regards,<br></div>
<div class="gmail_signature"><b>Taylor Example</b><br>Account Executive<br>Example Insurance Services<br>CA Lic. #0C12345<br>
<a href="https://www.linkedin.com/in/example">LinkedIn</a> | <a href="https://calendly.com/example/30min">Book a call</a></div>
<div class="gmail_quote">On Mon, Sep 28, 2026 the board wrote:<blockquote>Old text from a Title Officer</blockquote></div>
</body></html>"""


def test_a_property_manager_with_a_dre_license() -> None:
    sig = read_signature(PROPERTY_MANAGER, address="jordan@example.com")
    assert sig.role is SignatureRole.PROPERTY_MANAGER and sig.role.source_kind is SourceKind.PROPERTY_MANAGER
    assert sig.name == "Jordan Example" and sig.title == "Property Manager"
    assert sig.company == "Example Property Management, Inc."
    assert [(lic.kind, lic.number) for lic in sig.licenses] == [(LicenseKind.DRE, "01234567")]
    # The office line is kept; the cell number is only counted.
    assert sig.has_phone and [(p.label, p.number) for p in sig.business_phones] == [("office", "(916) 555-0142")]
    assert sig.has_address and sig.website == "example.com"
    assert any(r.startswith("license:") for r in sig.reasons) and sig.confidence > 0.4


def test_a_title_officer_with_a_wire_fraud_disclaimer() -> None:
    body, block = split_signature(TITLE_OFFICER)
    assert "demand request" in body and "demand request" not in block
    assert block.startswith("Casey Example") and "CONFIDENTIALITY NOTICE" in block
    sig = parse_signature(block, address="casey@example.com")
    assert sig.role is SignatureRole.TITLE_ESCROW
    assert sig.name == "Casey Example" and sig.title == "Escrow Officer" and sig.company == "Example Title Company"
    assert sig.disclaimer and any(r.startswith("disclaimer:") for r in sig.reasons)
    assert [p.label for p in sig.business_phones] == ["direct"]


def test_a_contractor_with_a_cslb_license_after_a_dash_delimiter() -> None:
    body, block = split_signature(CONTRACTOR)
    assert body.endswith("The estimate is attached.") and block.startswith("Riley Example")
    sig = parse_signature(block, address="riley@example.com")
    assert sig.role is SignatureRole.VENDOR and sig.title == "Estimator"
    assert sig.company == "Example Roofing & Construction LLC"
    assert [(lic.kind, lic.number) for lic in sig.licenses] == [(LicenseKind.CSLB, "123456")]
    assert [p.label for p in sig.business_phones] == ["tel"]


def test_an_owner_on_gmail_with_a_first_name_and_sent_from_my_iphone() -> None:
    body, block = split_signature(OWNER)
    assert "garage" in body and "garage" not in block and block.startswith("Jane")
    sig = parse_signature(block, address="jane.example@gmail.com")
    assert sig.role is SignatureRole.INDIVIDUAL and sig.mobile and not sig.business_phones
    kept = sig.to_dict(private=True)
    # An individual's row keeps the role and the presence flags; no name and no words from the message.
    assert "name" not in kept and "Jane" not in json.dumps(kept) and "garage" not in json.dumps(kept)
    assert kept["role"] == "individual" and "consumer domain" in kept["reasons"]


def test_a_quoted_reply_chain_is_cut_before_the_signature_is_read() -> None:
    sig = read_signature(REALTOR_REPLY, address="morgan.example@gmail.com")
    assert sig.role is SignatureRole.REALTOR and sig.name == "Morgan Example"
    assert [(lic.kind, lic.number) for lic in sig.licenses] == [(LicenseKind.DRE, "02345678")]
    assert "Escrow" not in json.dumps(sig.to_dict())        # the quoted escrow officer is not read
    # An unlabeled number is counted, never kept.
    assert sig.has_phone and not sig.business_phones
    outlook = read_signature(OUTLOOK_REPLY, address="sam@example.com")
    assert outlook.role is SignatureRole.ATTORNEY and outlook.title == "Attorney at Law"
    assert [lic.kind for lic in outlook.licenses] == [LicenseKind.BAR]
    assert "Property Manager" not in json.dumps(outlook.to_dict())


def test_an_html_signature_keeps_its_links_by_kind_and_drops_the_quote() -> None:
    text = html_to_text(INSURER_HTML)
    assert "color: red" not in text and "Old text" not in text
    sig = read_signature(INSURER_HTML, address="taylor@example.com")
    assert sig.role is SignatureRole.INSURER and sig.name == "Taylor Example"
    assert sig.company == "Example Insurance Services" and sig.title == "Account Executive"
    assert [(lic.kind, lic.number) for lic in sig.licenses] == [(LicenseKind.INSURANCE, "0C12345")]
    assert set(sig.links) == {"linkedin", "calendly"} and sig.website == ""


def test_a_message_with_no_signature_reads_unknown_or_individual() -> None:
    body, block = split_signature("Can someone call me about the gate?")
    assert block == "" and body
    # A branded domain alone is a cue, not a role: an owner can write from work.
    bare = parse_signature("", address="x@example.com")
    assert bare.role is SignatureRole.UNKNOWN and bare.reasons == ("branded domain:example.com",)
    assert parse_signature("").role is SignatureRole.UNKNOWN
    # A "Thanks!" that opens a message does not make the message a signature.
    body, block = split_signature("Thanks!\nThe property manager will call you about the leak tomorrow, the plumber is booked.\nJane")
    assert "plumber" not in block


OUTLOOK_PLAIN_ADJUSTER = """Attached are the photos from today's inspection.

[Example Adjusting, LLC]<https://url.emailprotection.link/?abc>




Robin Example / Adjuster
robin@example.com<mailto:robin@example.com> / 530-555-0109
Example Adjusting, LLC
O: 800-555-0111 / F: 877-555-0112
5701 Example Boulevard, Suite 211
Rocklin, CA 95765
www.example.com<https://url.emailprotection.link/?def>
License: CA 2I12345


This e-mail message may contain confidential or legally privileged information and is intended only for the use of the intended recipient(s).

*** A long notice about office hours that runs well past any signature line and ends the message with a sentence. ***
Received via board@mystique.example.com shared inbox.
"""


def test_an_outlook_plain_signature_with_link_targets_slashes_and_a_list_footer() -> None:
    body, block = split_signature(OUTLOOK_PLAIN_ADJUSTER)
    assert "photos" in body and "photos" not in block and "shared inbox" not in block
    sig = parse_signature(block, address="robin@example.com")
    assert sig.role is SignatureRole.INSURER and sig.name == "Robin Example" and sig.title == "Adjuster"
    assert sig.company == "Example Adjusting, LLC" and sig.website == "example.com"       # not the link wrapper
    assert [(lic.kind, lic.number) for lic in sig.licenses] == [(LicenseKind.INSURANCE, "2I12345")]
    assert {p.label for p in sig.business_phones} == {"toll-free"} and sig.has_address


def test_a_bare_name_reads_as_a_person_only_from_a_personal_mailbox() -> None:
    text = "We can quote the cleaning next week.\n\nThanks,\nKit\n"
    assert read_signature(text, address="kit.example@gmail.com").role is SignatureRole.INDIVIDUAL
    assert read_signature(text, address="kit@example.com").role is SignatureRole.UNKNOWN
    owner_of = read_signature("Happy to quote it.\n\nLet me know,\nKit\n\nKit Example\nOwner, Example Clean Pro\n",
                              address="kit@example.com")
    assert owner_of.name == "Kit Example" and owner_of.title == "Owner" and owner_of.company == "Example Clean Pro"
    assert owner_of.role.professional


# --- the task: what is read, and what is kept ----------------------------------------------------------------------

def _store(tmp_path, messages: list[dict]) -> None:
    (tmp_path / "gmail").mkdir(exist_ok=True)
    (tmp_path / "gmail" / "correspondence.json").write_text(json.dumps({"messages": messages}), encoding="utf-8")


def _msg(mid: str, thread: str, at: str, *, people=(), parties=(), direction="in") -> dict:
    domains = sorted({p[1].rsplit("@", 1)[1] for p in people})
    return {"messageId": mid, "threadId": thread, "at": at, "direction": direction, "domains": domains,
            "parties": sorted(parties), "subject": "s", "people": [list(p) for p in people], "via": "", "groups": []}


class _Gmail:
    def __init__(self, bodies: dict[str, tuple[str, str]]) -> None:
        self.bodies = bodies
        self.read: list[str] = []

    def get_body(self, message_id: str) -> dict:
        self.read.append(message_id)
        sender, text = self.bodies[message_id]
        return {"id": message_id, "threadId": "t", "internalDate": "1790000000000", "labels": [],
                "headers": {"From": sender}, "plain": text, "html": ""}


def _community(senders=()) -> SimpleNamespace:
    return SimpleNamespace(email_domains=lambda: ("mystique.example.com",), senders=lambda: tuple(senders))


def test_the_plan_reads_the_latest_messages_per_sender_and_skips_owners_on_request(tmp_path) -> None:
    from jason.tasks.signatures import plan

    _store(tmp_path, [
        _msg("a1", "t1", "2026-09-01T00:00:00+00:00", people=[("Jordan", "jordan@pm.example.com", "from")], parties=["pm.example.com", "owner of 1 EXAMPLE WALK"]),
        _msg("a2", "t2", "2026-09-02T00:00:00+00:00", people=[("Jordan", "jordan@pm.example.com", "from")], parties=["pm.example.com"]),
        _msg("a3", "t3", "2026-09-03T00:00:00+00:00", people=[("Jordan", "jordan@pm.example.com", "from")], parties=["pm.example.com"]),
        _msg("n1", "t4", "2026-09-04T00:00:00+00:00", people=[("", "noreply@vendor.example.com", "from")], parties=["vendor.example.com"]),
        _msg("o1", "t5", "2026-09-05T00:00:00+00:00", parties=["owner of 1 EXAMPLE WALK", "association"]),
        _msg("p1", "t6", "2026-09-06T00:00:00+00:00", parties=["personal", "association"]),
        _msg("x1", "t7", "2026-09-07T00:00:00+00:00", people=[("Jordan", "jordan@pm.example.com", "to")], parties=["pm.example.com"], direction="out"),
    ])
    targets = plan(tmp_path, _community(), per_sender=2)
    keys = {t.key: t.messages for t in targets}
    assert keys["jordan@pm.example.com"] == ["a3", "a2"]                      # the latest two
    assert "noreply@vendor.example.com" not in keys                            # automated
    assert "owner of 1 EXAMPLE WALK" in keys and "personal:t6" in keys
    non_owner = {t.key for t in plan(tmp_path, _community(), non_owners=True)}
    assert "owner of 1 EXAMPLE WALK" not in non_owner and "personal:t6" in non_owner
    assert {t.key for t in plan(tmp_path, _community(), domains=("pm.example.com",))} == {"jordan@pm.example.com"}
    assert sum(len(t.messages) for t in plan(tmp_path, _community(), limit=2)) == 2


def test_fetch_keeps_signature_fields_only_and_no_personal_address(tmp_path) -> None:
    from jason.tasks.signatures import SIGNATURES, fetch, plan

    _store(tmp_path, [
        _msg("a1", "t1", "2026-09-01T00:00:00+00:00", people=[("Jordan", "jordan@pm.example.com", "from")],
             parties=["owner of 1 EXAMPLE WALK", "pm.example.com"]),
        _msg("o1", "t5", "2026-09-05T00:00:00+00:00", parties=["personal", "association"]),
        _msg("v1", "t8", "2026-09-06T00:00:00+00:00", people=[("Riley", "riley@roof.example.com", "from")], parties=["roof.example.com"]),
    ])
    gmail = _Gmail({
        "a1": ("Jordan Example <jordan@pm.example.com>", PROPERTY_MANAGER),
        "o1": ("Jane <jane.example@gmail.com>", OWNER),
        "v1": ("Riley Example <riley@roof.example.com>", CONTRACTOR),
    })
    known = Sender("Example Roofing", SourceKind.VENDOR, ("EXAMPLE ROOFING",), domains=("roof.example.com",))
    result = fetch(gmail, tmp_path, _community([known]), plan(tmp_path, _community([known])))
    assert sorted(gmail.read) == ["a1", "o1", "v1"] and result["read"] == 3
    raw = (tmp_path / "gmail" / SIGNATURES).read_text(encoding="utf-8")
    # No body text, and no personal address or name.
    for words in ("move-out checklist", "garage", "barking", "estimate is attached", "jane.example", "Jane"):
        assert words not in raw
    stored = json.loads(raw)
    rows = {r["sender"]: r for r in stored["rows"]}
    personal = next(r for k, r in rows.items() if k.startswith("personal:"))
    assert personal["role"] == "individual" and "name" not in personal and personal["provider"] == "gmail.com"
    assert rows["jordan@pm.example.com"]["role"] == "property manager"
    assert rows["jordan@pm.example.com"]["units"] == ["1 EXAMPLE WALK"]
    assert rows["riley@roof.example.com"]["directory"]["name"] == "Example Roofing"
    candidates = stored["summary"]["candidates"]
    assert [(c["role"], c["domain"]) for c in candidates] == [("property manager", "pm.example.com")]
    assert stored["summary"]["roles"] == {"individual": 1, "property manager": 1, "vendor or contractor": 1}
    # A second run reads nothing it already read.
    assert plan(tmp_path, _community([known])) == []


def test_the_gmail_client_decodes_the_text_parts_without_attachments() -> None:
    from jason.google.gmail import GoogleGmail

    def b64(s: str) -> str:
        return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")

    payload = {"id": "m", "threadId": "t", "internalDate": "1", "labelIds": ["INBOX"],
               "payload": {"mimeType": "multipart/mixed", "headers": [{"name": "From", "value": "a@example.com"}, {"name": "Subject", "value": "x"}],
                           "parts": [{"mimeType": "multipart/alternative", "parts": [
                               {"mimeType": "text/plain", "body": {"data": b64("hello\n-- \nA")}},
                               {"mimeType": "text/html", "body": {"data": b64("<p>hello</p>")}}]},
                               {"mimeType": "text/plain", "filename": "notes.txt", "body": {"attachmentId": "z"}}]}}

    class _Http:
        def __init__(self) -> None:
            self.params = None

        def get(self, url, *, params=None, headers=None):
            self.params = params
            return httpx.Response(200, content=json.dumps(payload).encode())

    http = _Http()
    got = GoogleGmail("token", http=http).get_body("m")
    assert got["plain"] == "hello\n-- \nA" and got["html"] == "<p>hello</p>"
    assert got["headers"] == {"From": "a@example.com"} and "Subject" not in got["headers"]
    assert http.params["format"] == "full"
