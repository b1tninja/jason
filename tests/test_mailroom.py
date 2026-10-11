"""The Mailroom task: units resolve by address or id; preparing previews and mails nothing; sending logs the batch."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pymupdf
import pytest

from jason.tasks.mailroom import prepare, resolve_units, send, status


def _data(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    with sqlite3.connect(data / "payhoa.db") as conn:
        conn.execute("CREATE TABLE units (org_id, id, label, balance, past_due_balance, address_line1, city, state, postal_code, raw_json, synced_at)")
        conn.executemany("INSERT INTO units (org_id, id, address_line1) VALUES (?, ?, ?)",
                         [(1, 101, "3024 MACON DR"), (1, 102, "5627 WHIMSICAL LN"), (2, 999, "3024 MACON DR")])
    return data


class FakeClient:
    def __init__(self):
        self.sent, self.batches = [], [{"id": 1, "totalCost": 145, "mailOptions": "{}"}]

    def mail_recipients(self, org_id, unit_ids, *, send_to, sending_invoice):
        return [{"unitIds": [u], "ownerId": u + 1000, "unitTitles": f"unit {u}", "address": "A\nB", "isIncluded": True} for u in unit_ids]

    def mail_preview(self, org_id, pdf, dest, *, unit_ids, owner_id, invoice):
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"%PDF-preview")
        return Path(dest)

    def send_mail_pdf(self, org_id, pdf, **kw):
        self.sent.append(kw)
        self.batches.append({"id": 2, "totalCost": 290, "sentCount": 2, "mailOptions": json.dumps({"num_pages": 2})})
        return []

    def mail_pdf_batches(self, org_id):
        return list(self.batches)

    def mail_batch(self, org_id, batch_id):
        return [{"id": 7, "commActivityId": 70, "totalCost": 145, "status": "processing"},
                {"id": 8, "commActivityId": 80, "totalCost": 145, "status": "processing"}]

    def mail_invoice_batches(self, org_id):
        return []

    def mail_verify(self, org_id):
        return {"hasAddress": True, "hasPayment": True}

    def paper_mail_counts(self, org_id, *, start_date, end_date):
        return {"letters": 5}


def _letter(tmp_path: Path) -> Path:
    doc = pymupdf.open()
    doc.new_page()
    doc.new_page()
    path = tmp_path / "notice.pdf"
    doc.save(path)
    return path


def test_units_resolve_by_address_or_id_within_the_organization(tmp_path: Path):
    data = _data(tmp_path)
    units, missing = resolve_units(data, ["3024 Macon Drive", "102", "1 Nowhere St"], org_id=1)
    assert [u.id for u in units] == [101, 102] and missing == ["1 Nowhere St"]
    assert [u.id for u in resolve_units(data, ["all"], org_id=1)[0]] == [101, 102]


def test_preparing_previews_and_mails_nothing_then_sending_logs_the_batch(tmp_path: Path, monkeypatch):
    import jason.tasks.mailroom as mailroom

    monkeypatch.setattr(mailroom, "READ_BACK", (0.0,))
    data, client = _data(tmp_path), FakeClient()
    prepared = prepare(client, 1, data, _letter(tmp_path), ["3024 Macon Dr", "5627 Whimsical Ln"])
    assert prepared.pages == 2 and prepared.unit_ids == [101, 102] and prepared.owner_ids == [1101, 1102]
    assert Path(prepared.preview).read_bytes() == b"%PDF-preview" and client.sent == []
    record = send(client, 1, data, prepared, double_sided=True)
    assert client.sent[0]["unit_ids"] == [101, 102] and client.sent[0]["owner_ids"] == [1101, 1102]
    assert client.sent[0]["num_pages"] == 2 and client.sent[0]["double_sided"] is True
    assert [b["id"] for b in record["batches"]] == [2] and record["batches"][0]["costCents"] == 290
    assert [x["communication"] for x in record["letters"]] == [70, 80] and record["guideCents"] == 145   # 3 billed pages
    assert json.loads((data / "mailroom" / "sent.jsonl").read_text(encoding="utf-8").splitlines()[0])["units"] == [101, 102]
    assert status(client, 1, data)["verify"]["hasPayment"]


def test_the_address_page_is_printed_and_billed_and_a_sixth_page_costs_postage():
    from jason.tasks.mailroom import printed

    four = printed(4, double_sided=True)              # the owner-information packet: 4 pages and the address page
    assert (four.pages, four.sheets, four.blank_back, four.cents, four.heavy) == (5, 3, True, 185, False)
    five = printed(5, double_sided=True)              # one page more fills the blank back and costs $2.45
    assert (five.pages, five.sheets, five.blank_back, five.cents, five.heavy) == (6, 3, False, 430, True)
    assert printed(4, double_sided=False).cents == 185                                 # two sides save paper, not money


def test_charged_letters_are_checked_against_the_pricing_guide():
    import json

    from jason.tasks.mailroom import charged_letters

    def letter(id, created, pages, cost, *, standard=True, color=False, cancelled=None, certified=False):
        return {"id": id, "createdAt": created, "totalCost": cost, "cancelledAt": cancelled,
                "mailOptions": json.dumps({"num_pages": pages, "is_standard_mail": standard, "is_colored_mail": color,
                                           "is_certified_mail": certified, "two_sided": True})}

    rows = charged_letters([
        letter(1, "2026-09-03 10:00:00", 3, 185, standard=False),            # first class: 125 + 3 x 20
        letter(2, "2026-07-14 10:00:00", 4, 305, standard=False, color=True),  # + 5 pages of color
        letter(3, "2025-11-30 10:00:00", 60, 1510),                          # billed before the address page was
        letter(4, "2026-10-01 20:53:09", 4, 185, cancelled="2026-10-01"),    # cancelled: not a charge
        letter(5, "2024-09-08 05:02:46", 5, 1550, standard=False, color=True, certified=True),
        letter(6, "2026-01-01 00:00:00", 2, 999),
    ])
    assert [(r.id, r.matches) for r in rows] == [(1, "guide"), (2, "guide"), (3, "guide, address page not billed"),
                                                 (6, "differs")]


def test_mail_options_follow_the_rules_on_payhoas_own_page():
    from jason.tasks.mailroom import check_options

    assert check_options("standard") == "standard" and check_options("first-class") == "first class"
    assert check_options("first-class", tracking="certified", double_sided=True) == "first class"
    for bad in (dict(mail_class="standard", tracking="certified"), dict(mail_class="standard", with_invoices=True),
                dict(mail_class="first-class", with_invoices=True, double_sided=True),
                dict(mail_class="first-class", tracking="express"), dict(mail_class="priority")):
        with pytest.raises(ValueError):
            check_options(**bad)


def test_certified_and_registered_mail_are_priced_by_the_guide():
    from jason.tasks.mailroom import printed

    base = printed(4, double_sided=False, first_class=True).cents
    assert base == 125 + 20 * 4                                           # first class; 5 billed pages
    assert printed(4, double_sided=False, first_class=True, tracking="certified").cents == base + 1000
    assert printed(4, double_sided=False, first_class=True, tracking="registered").cents == base + 2500
    assert printed(4, double_sided=False, first_class=True, color=True).cents == base + 20 * 5


def test_a_first_class_certified_send_passes_its_options_and_logs_them(tmp_path: Path, monkeypatch):
    import jason.tasks.mailroom as mailroom

    monkeypatch.setattr(mailroom, "READ_BACK", (0.0,))
    data, client = _data(tmp_path), FakeClient()
    prepared = prepare(client, 1, data, _letter(tmp_path), ["3024 Macon Dr"])
    record = send(client, 1, data, prepared, mail_class="first-class", tracking="certified", color="color", by="A. Manager")
    assert client.sent[0]["mail_class"] == "first class" and client.sent[0]["tracking"] == "certified"
    assert client.sent[0]["color"] == "color"
    logged = json.loads((data / "mailroom" / "sent.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert (logged["mailClass"], logged["tracking"], logged["by"]) == ("first class", "certified", "A. Manager")
    assert record["guideCents"] == mailroom.printed(prepared.pages, double_sided=False, first_class=True, color=True,
                                                    tracking="certified").cents
    with pytest.raises(ValueError):                                       # refused before anything is mailed
        send(client, 1, data, prepared, mail_class="standard", tracking="registered")
    assert len(client.sent) == 1


def test_a_notice_letter_defaults_to_first_class_and_any_other_to_standard():
    from jason.tasks.mailroom import check_options, default_mail_class

    assert default_mail_class("owner-info-2099") == "first-class" and default_mail_class("") == "standard"
    assert check_options(default_mail_class("owner-info-2099")) == "first class"


def test_a_standard_send_carries_the_note_about_the_statutes_methods():
    from jason.tasks.mailroom import STANDARD_NOTE

    assert "CIV 4040(a)(2)" in STANDARD_NOTE and "--mail-class first-class" in STANDARD_NOTE


# -- the preview record, the fingerprint, and --expect ---------------------------------------------------------------------

from contextlib import contextmanager  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402
from types import SimpleNamespace  # noqa: E402

from mailroom_support import ORG, FakeMailClient, kept, make_data, make_letter, options  # noqa: E402

UNITS = "123 Example Rd,125 Example Rd"


@pytest.fixture
def quick(monkeypatch):
    import jason.tasks.mailroom as mailroom

    monkeypatch.setattr(mailroom, "READ_BACK", (0.0,))


def cli_run(monkeypatch, capsys, world, *argv):
    """Run ``jason mailroom ...`` against the fake client: (exit code, stdout, stderr)."""
    from jason import cli

    @contextmanager
    def agent(args):
        yield SimpleNamespace(settings=SimpleNamespace(ownership_db=world.data / "ownership.db"),
                              payhoa=lambda: world.client, org_id=ORG)

    monkeypatch.setattr(cli, "_agent", agent)
    args = cli.build_parser().parse_args(["mailroom", *argv])
    code = args.func(args)
    out = capsys.readouterr()
    return code, out.out, out.err


def new_world(tmp_path: Path):
    return SimpleNamespace(data=make_data(tmp_path), client=FakeMailClient(), pdf=make_letter(tmp_path))


def test_the_preview_record_keeps_ids_and_words_and_no_name_or_address(tmp_path: Path):
    world = kept(tmp_path, notice="mailing-notice-2099-10", double_sided=True)
    text = world.path.read_text(encoding="utf-8")
    for private in ("A. Owner", "B. Owner", "Example City", "95000"):
        assert private not in text
    record = json.loads(text)
    assert world.path.parent == world.data / "mailroom" / "previews" and world.path.stem == record["id"]
    assert {"id", "read", "by", "pdf", "options", "named", "missing", "units", "recipients", "printed", "lettersExpected",
            "totalCents", "fingerprint", "notice"} <= set(record)
    assert set(record["pdf"]) == {"name", "path", "sha256", "pages"} and record["pdf"]["pages"] == 2
    assert set(record["recipients"][0]) == {"ownerId", "unitTitles", "resolved", "isIncluded", "isDuplicate"}
    assert [r["resolved"] for r in record["recipients"]] == ["mailing = unit address"] * 2
    assert record["units"] == [{"id": 101, "title": "123 Example Rd"}, {"id": 102, "title": "125 Example Rd"}]
    assert record["lettersExpected"] == 2 and record["by"] == "A. Manager" and record["notice"] == "mailing-notice-2099-10"
    assert record["printed"]["pages"] == 3 and record["printed"]["sheets"] == 2     # the address page first, two-sided
    assert record["totalCents"] == 2 * record["printed"]["centsEach"] == 2 * 165  # first class: 125 + 2 x 20
    assert record["options"]["mailClass"] == "first class" and len(record["fingerprint"]) == 64


def test_a_resolution_word_says_where_the_address_came_from_and_is_never_the_address(tmp_path: Path):
    client = FakeMailClient()
    client.rows[102]["address"] = "9 Other Rd\nExample City, CA 95000"                  # an owner's own mailing address
    client.rows[101]["address"] = ""
    world = kept(tmp_path, client)
    assert [r["resolved"] for r in world.record["recipients"]] == ["no address", "mailing address"]
    assert "9 Other" not in world.path.read_text(encoding="utf-8")


def test_the_fingerprint_is_stable_and_changes_with_each_input(tmp_path: Path):
    base = kept(tmp_path).record["fingerprint"]
    assert kept(tmp_path, FakeMailClient()).record["fingerprint"] == base          # same inputs, a new read, the same hash

    def fp(client=None, **kw):
        return kept(tmp_path, client, **kw).record["fingerprint"]

    moved, renamed, relocated, left_out, duplicate = (FakeMailClient() for _ in range(5))
    moved.rows[101]["ownerId"] = 2001
    renamed.rows[101]["name"] = "C. Owner"
    relocated.rows[101]["address"] = "9 Other Rd\nExample City, CA 95000"
    left_out.rows[101]["isIncluded"] = False
    duplicate.rows[101]["isDuplicate"] = True
    differs = {
        "double-sided": fp(double_sided=True), "standard class": fp(mail_class="standard"),
        "certified": fp(tracking="certified"), "color": fp(color="color"), "unit address": fp(send_to="unit"),
        "invoices": fp(with_invoices=True), "one unit": fp(wanted=("123 Example Rd",)), "pages": fp(pages=3),
        "owner id": fp(moved), "owner name": fp(renamed), "address": fp(relocated), "left out": fp(left_out),
        "duplicate": fp(duplicate),
    }
    assert all(v != base for v in differs.values()), [k for k, v in differs.items() if v == base]
    assert len(set(differs.values())) == len(differs)                      # and no two changes give the same one


def test_a_changed_file_changes_the_fingerprint(tmp_path: Path):
    import jason.tasks.mailroom as mailroom

    world = kept(tmp_path)
    world.pdf.write_bytes(world.pdf.read_bytes() + b"\n% edited")
    facts = mailroom.describe(world.pdf, world.prepared.pages, options(), world.prepared.units, world.prepared.recipients)
    assert facts["pdf"]["sha256"] != world.record["pdf"]["sha256"] and facts["fingerprint"] != world.record["fingerprint"]
    assert mailroom.changes(world.record, facts)[0].startswith("the PDF changed")


def test_staleness_names_the_pdf_the_units_the_owners_the_cost_and_the_age(tmp_path: Path):
    import jason.tasks.mailroom as mailroom

    world = kept(tmp_path)

    def live():
        return mailroom.live_facts(world.client, ORG, world.data, world.record)[0]

    assert mailroom.stale_reasons(world.record, live()) == []
    old = datetime.now(timezone.utc) + timedelta(hours=mailroom.PREVIEW_MAX_AGE_HOURS + 1)
    assert "24-hour limit" in mailroom.stale_reasons(world.record, live(), now=old)[0]
    assert mailroom.stale_reasons(world.record, live(), now=old, check_age=False) == []
    world.client.rows[101]["ownerId"] = 2001
    reasons = mailroom.stale_reasons(world.record, live())
    assert any("different owners (1 added, 1 removed" in r and "1101" in r and "2001" in r for r in reasons)
    world.client.rows[102]["address"] = "9 Other Rd\nExample City, CA 95000"
    world.pdf.write_bytes(world.pdf.read_bytes() + b"\n% edited")
    reasons = mailroom.stale_reasons(world.record, live())
    assert any(r.startswith("the PDF changed") for r in reasons) and not any("9 Other" in r for r in reasons)
    world.pdf.unlink()
    assert "gone" in mailroom.changes(world.record, live())[0]


def test_a_preview_is_found_by_id_prefix_or_fingerprint(tmp_path: Path):
    import jason.tasks.mailroom as mailroom

    world = kept(tmp_path)
    for ref in (world.record["id"], world.record["id"][:8], world.record["fingerprint"][:6]):
        assert mailroom.load_preview(world.data, ref)["id"] == world.record["id"]
    with pytest.raises(KeyError, match="no saved preview"):
        mailroom.load_preview(world.data, "nothing")


def test_jason_mailroom_pdf_saves_the_record_and_json_prints_it(tmp_path: Path, monkeypatch, capsys):
    world = new_world(tmp_path)
    code, out, err = cli_run(monkeypatch, capsys, world, "--pdf", str(world.pdf), "--units", UNITS, "--json", "--by", "A. Manager")
    shown = json.loads(out)
    assert code == 0 and shown["mailed"] is None and world.client.sent == []
    saved = Path(shown["saved"])
    assert json.loads(saved.read_text(encoding="utf-8"))["fingerprint"] == shown["preview"]["fingerprint"]
    assert "A. Owner" not in out and "Example City" not in out and shown["preview"]["by"] == "A. Manager"
    code, out, _ = cli_run(monkeypatch, capsys, world, "--pdf", str(world.pdf), "--units", UNITS)
    assert f"fingerprint {shown['preview']['fingerprint'][:12]}" in out and "--expect" in out and "not mailed" in out


def test_a_send_with_expect_refuses_a_changed_letter_and_mails_nothing(tmp_path: Path, monkeypatch, capsys, quick):
    world = new_world(tmp_path)
    _, out, _ = cli_run(monkeypatch, capsys, world, "--pdf", str(world.pdf), "--units", UNITS, "--json")
    fp = json.loads(out)["preview"]["fingerprint"]
    send_args = ("--pdf", str(world.pdf), "--units", UNITS, "--send", "--yes", "--expect", fp[:12])
    world.client.rows[101]["ownerId"] = 2001                                  # the owners PayHOA names changed
    code, out, err = cli_run(monkeypatch, capsys, world, *send_args)
    assert code == 2 and world.client.sent == [] and "nothing mailed" in err and "different owners" in err
    assert "mailed:" not in out and not (world.data / "mailroom" / "sent.jsonl").exists()
    world.client.rows[101]["ownerId"] = 1101
    world.pdf.write_bytes(world.pdf.read_bytes() + b"\n% edited")             # the file changed after the preview
    code, out, err = cli_run(monkeypatch, capsys, world, *send_args)
    assert code == 2 and world.client.sent == [] and "the PDF changed" in err
    # no saved preview carries a made-up fingerprint: refused, and it says it cannot name what changed
    code, _, err = cli_run(monkeypatch, capsys, world, "--pdf", str(world.pdf), "--units", UNITS, "--send", "--yes",
                           "--expect", "ab" * 6)
    assert code == 2 and world.client.sent == [] and "cannot be named" in err
    code, _, err = cli_run(monkeypatch, capsys, world, "--pdf", str(world.pdf), "--units", UNITS, "--send", "--yes",
                           "--expect", "abc")
    assert code == 2 and world.client.sent == [] and "hex characters" in err


def test_a_send_with_the_right_expect_mails_and_logs_the_fingerprint(tmp_path: Path, monkeypatch, capsys, quick):
    world = new_world(tmp_path)
    _, out, _ = cli_run(monkeypatch, capsys, world, "--pdf", str(world.pdf), "--units", UNITS, "--json",
                        "--mail-class", "first-class")
    preview = json.loads(out)["preview"]
    code, out, err = cli_run(monkeypatch, capsys, world, "--pdf", str(world.pdf), "--units", UNITS, "--mail-class",
                             "first-class", "--send", "--yes", "--expect", preview["fingerprint"][:12], "--by", "A. Manager")
    assert code == 0, err
    assert len(world.client.sent) == 1 and world.client.sent[0]["owner_ids"] == [1101, 1102]
    assert "not a promise" not in out
    logged = json.loads((world.data / "mailroom" / "sent.jsonl").read_text(encoding="utf-8").splitlines()[0])
    import jason.tasks.mailroom as mailroom

    assert logged["fingerprint"] == preview["fingerprint"]
    assert mailroom.load_preview(world.data, logged["previewId"])["fingerprint"] == preview["fingerprint"]   # this run's own record
    assert logged["by"] == "A. Manager" and "approval" not in logged


def test_a_send_without_expect_works_as_before_and_says_a_preview_is_not_a_promise(tmp_path: Path, monkeypatch, capsys, quick):
    world = new_world(tmp_path)
    code, out, err = cli_run(monkeypatch, capsys, world, "--pdf", str(world.pdf), "--units", UNITS, "--send", "--yes")
    assert code == 0 and len(world.client.sent) == 1
    assert "a preview is not a promise" in out and "--expect" in out
    logged = json.loads((world.data / "mailroom" / "sent.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert len(logged["fingerprint"]) == 64


def test_preview_shows_a_saved_preview_current_or_stale_and_sends_exactly_it(tmp_path: Path, monkeypatch, capsys, quick):
    world = new_world(tmp_path)
    _, out, _ = cli_run(monkeypatch, capsys, world, "--pdf", str(world.pdf), "--units", UNITS, "--json",
                        "--mail-class", "first-class")
    preview = json.loads(out)["preview"]
    code, out, _ = cli_run(monkeypatch, capsys, world, "--preview", preview["fingerprint"][:8])
    assert code == 0 and "current" in out and "STALE" not in out and "Nothing is mailed" in out and world.client.sent == []
    assert "A. Owner" not in out
    world.client.rows[102]["address"] = "9 Other Rd\nExample City, CA 95000"
    code, out, err = cli_run(monkeypatch, capsys, world, "--preview", preview["id"])
    assert code == 1 and "STALE" in out and "an address, a name, or a flag" in out
    code, out, err = cli_run(monkeypatch, capsys, world, "--preview", preview["id"], "--send", "--yes")
    assert code == 2 and world.client.sent == [] and "stale" in err
    world.client.rows[102]["address"] = "125 Example Rd\nExample City, CA 95000"
    code, out, err = cli_run(monkeypatch, capsys, world, "--preview", preview["id"], "--send", "--yes")
    assert code == 0, err
    assert len(world.client.sent) == 1 and world.client.sent[0]["mail_class"] == "first class"
    code, out, err = cli_run(monkeypatch, capsys, world, "--preview", "nothing-like-it")
    assert code == 2 and "no saved preview" in err


def test_an_old_preview_is_stale_by_age(tmp_path: Path, monkeypatch, capsys):
    world = new_world(tmp_path)
    _, out, _ = cli_run(monkeypatch, capsys, world, "--pdf", str(world.pdf), "--units", UNITS, "--json")
    saved = Path(json.loads(out)["saved"])
    record = json.loads(saved.read_text(encoding="utf-8"))
    record["read"] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(timespec="seconds")
    saved.write_text(json.dumps(record), encoding="utf-8")
    code, out, _ = cli_run(monkeypatch, capsys, world, "--preview", record["id"])
    assert code == 1 and "24-hour limit" in out


def test_a_read_back_that_fails_still_logs_the_mailing(tmp_path: Path, quick):
    import jason.tasks.mailroom as mailroom

    world = kept(tmp_path)

    class Broken(FakeMailClient):
        def mail_pdf_batches(self, org_id):
            if self.sent:
                raise RuntimeError("PayHOA did not answer")
            return super().mail_pdf_batches(org_id)

    client = Broken()
    prepared = mailroom.prepare(client, ORG, world.data, world.pdf, ["123 Example Rd"])
    record = mailroom.send(client, ORG, world.data, prepared, by="A. Manager")
    assert len(client.sent) == 1 and record["batches"] == [] and "did not answer" in record["readBackError"]
    assert (world.data / "mailroom" / "sent.jsonl").read_text(encoding="utf-8").count("readBackError") == 1
