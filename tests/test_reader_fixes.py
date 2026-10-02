"""Rule-reader fixes the question sets pointed to (September 30, 2026)."""

from __future__ import annotations

import pytest

from jason.community.models.contracts_agreements import _LICENSE, _is_bill
from jason.community.models.contracts_ins_package import _form_values


@pytest.mark.parametrize("text,number", [
    ("California Contractors License No. 979670-B", "979670-B"),
    ("CSLB# 1119271", "1119271"),
    ("CSLB NO. 845123", "845123"),
    ("License #: PR6993", "PR6993"),
])
def test_a_contractors_license_is_read_in_the_forms_bids_print_it(text, number) -> None:
    assert _LICENSE.search(text).group(1) == number


def test_a_bill_is_not_an_offer_but_a_proposal_that_names_a_balance_is() -> None:
    assert _is_bill("Amazon Web Services\nInvoice Number: 1234567\nAmount Due $12.00")
    assert not _is_bill("PROPOSAL #4514-1\nEstimate total $4,216\nBalance due upon completion")


def test_a_filled_forms_values_are_read_apart_from_its_labels() -> None:
    text = ("POLICY NUMBER:\nPRODUCER:\nLIMIT OF LIABILITY:\n____ in the aggregate\nRETENTION:\n____\n"
            "1-SKN-CA-01524174-01\n9/28/2025\n$1,292.95\n$1,000,000\n$1,000\n$1,292.95\n1-SKN-CA-01524174-01")
    assert _form_values(text) == {"number": "1-SKN-CA-01524174-01", "limit": 100_000_000, "retention": 100_000}


def test_the_insureds_mailing_address_is_the_associations_among_the_pages_addresses() -> None:
    from jason.community.models.contracts_insurance import mailing_address

    known = ("901 H ST", "PMB 188", "901 H STREET", "BOLLINGER CANYON")
    page = ("\nCOMPANY MAILING ADDRESS\n30 ENTERPRISE, SUITE 180\nALISO VIEJO, CA 92656\nMYSTIQUE COMMUNITY ASSOCIATION\n"
            "901 H STREET STE 120\nPMB 188\nSACRAMENTO, CA 95814\n")
    assert mailing_address(page, known) == "901 H STREET STE 120, PMB 188, SACRAMENTO, CA 95814"
    assert mailing_address("\n901H STREET STE 120\nSACRAMENTO, CA 95814\n", known) == "901H STREET STE 120, SACRAMENTO, CA 95814"
    assert mailing_address("\n30 ENTERPRISE, SUITE 180\nALISO VIEJO, CA 92656\n", known) == ""        # the insurer's, not ours


def test_the_current_street_without_its_box_is_a_finding() -> None:
    from types import SimpleNamespace

    from jason.community.models.contracts_insurance import mailing_findings

    current = SimpleNamespace(kind=SimpleNamespace(name="CURRENT"), words=("901 H ST", "PMB 188", "901 H STREET"))
    context = SimpleNamespace(community=SimpleNamespace(mail_addresses=lambda: (current,)))
    assert mailing_findings("901 H STREET STE 120, PMB 188, SACRAMENTO, CA 95814", context, "the flood policy") == []
    found = mailing_findings("901H STREET STE 120, SACRAMENTO, CA 95814", context, "the flood policy")
    assert found and "without its box (PMB 188)" in found[0].message


def test_the_current_street_and_box_with_another_zip_is_a_finding() -> None:
    from types import SimpleNamespace

    from jason.community.models.contracts_insurance import mailing_address, mailing_findings

    current = SimpleNamespace(kind=SimpleNamespace(name="CURRENT"), words=("901 H ST", "PMB 188", "901 H STREET"),
                              requires=("PMB 188", "PMB188"), zip="95814")
    context = SimpleNamespace(community=SimpleNamespace(mail_addresses=lambda: (current,)))
    address = mailing_address("\n901 H ST STE 120 PMB 188\nSacramento, CA, 95835\n", ("901 H ST",))
    assert address == "901 H ST STE 120 PMB 188, Sacramento, CA, 95835"
    found = mailing_findings(address, context, "the umbrella policy")
    assert found and "ZIP 95835, not 95814" in found[0].message


def test_an_invoice_names_where_the_work_was_what_it_bills_against_and_the_license() -> None:
    from datetime import date
    from pathlib import Path

    from jason.community import mystique
    from jason.community.document_models import ModelContext
    from jason.community.models.invoices import read_record

    text = ("GoodLife Construction\nCSLB# 1119271\nINVOICE # 92514\nDate: 06/02/2026\nBill To: Mystique Community Association\n"
            "Job site: 3022 Enchanted Walk\nPer Proposal #6021-1\nGarage door replacement 1 $4,216.00 $4,216.00\n"
            "Total $4,216.00\nBalance Due $4,216.00\n")
    r = read_record(text, ModelContext(mystique(), Path("."), date(2026, 9, 30), "inv.pdf", ""))
    assert r.service_address == "3022 ENCHANTED WALK" and r.building is not None
    assert r.reference == "Proposal 6021-1" and r.license == "1119271"
