from pathlib import Path

from jason.community.parsing import (
    GrantDeedMixin,
    MarkdownExtract,
    TextLayer,
    apn_fields,
    identify,
)


_DEED = """
APN: 201-1170-026-0019
GRANT DEED
Documentary transfer tax is $550.00
FOR A VALUABLE CONSIDERATION, receipt of which is hereby acknowledged,
Watt Communities at Mystique LLC
hereby GRANT(S) to
Doe Jordan C
the following described real property
"""


def test_a_grant_deed_prints_its_assessor_number():
    found = identify(
        Path("GD 202111301835.pdf"),
        parsers=(TextLayer(pages=lambda _path: (_DEED,)),),
    )
    assert found is not None
    assert found.parser == "text"
    assert found.kind == "grant_deed"
    assert found.values("apn") == ("201-1170-026-0019",)
    assert found.fields[0].template == "apn"
    assert found.values("grantor") == ("Watt Communities at Mystique LLC",)
    assert found.values("grantee") == ("Doe Jordan C",)


def test_parcel_id_and_dotted_labels_are_the_same_template():
    text = "A.P.N.: 201-1170-022-0015\nAPN/Parcel ID(s): 201-1170-026-0023\nAPN/Parcel IO(s): 201-1170-027-0019"
    numbers = tuple(field.value for field in apn_fields(text))
    assert numbers == (
        "201-1170-022-0015",
        "201-1170-026-0023",
        "201-1170-027-0019",
    )
    assert {field.template for field in apn_fields(text)} == {"apn"}


def test_a_continued_subparcel_shares_the_block_just_read():
    text = "APN: 201-1170-022-0002, 0003, 0006 & 0007"
    assert tuple(field.value for field in apn_fields(text)) == (
        "201-1170-022-0002",
        "201-1170-022-0003",
        "201-1170-022-0006",
        "201-1170-022-0007",
    )
    assert [field.template for field in apn_fields(text)] == [
        "apn",
        "apn_suffix",
        "apn_suffix",
        "apn_suffix",
    ]


def test_noise_between_the_groups_uses_the_loose_template():
    fields = apn_fields("APN: 201-1170/023-0023")
    assert [(field.value, field.template) for field in fields] == [
        ("201-1170-023-0023", "apn_loose"),
    ]


def test_an_empty_text_layer_falls_through_to_the_extract(tmp_path: Path):
    extract = tmp_path / "GD 202412130194.pdf.md"
    extract.write_text("GRANT DEED\nAPN/Parcel ID(s): 201-1170-026-0023\n", encoding="utf-8")
    found = identify(
        tmp_path / "GD 202412130194.pdf",
        parsers=(TextLayer(pages=lambda _path: ("",)), MarkdownExtract()),
    )
    assert found is not None
    assert found.parser == "extract"
    assert found.kind == "grant_deed"
    assert found.values("apn") == ("201-1170-026-0023",)


def test_a_page_without_the_grant_deed_words_is_not_that_instrument():
    reading_text = "QUITCLAIM DEED\nAPN: 201-1170-017-0011\n"
    found = identify(
        Path("QC.pdf"),
        parsers=(TextLayer(pages=lambda _path: (reading_text,)),),
        mixins=(GrantDeedMixin(),),
    )
    assert found is not None
    assert found.kind == ""
    assert found.values("apn") == ()


_SAMPLE = """
SAMPLE
GRANT DEED
DOCUMENTARY TRANSFER TAX IS$ ----
Parcel No: _____________
FOR VALUABLE CONSIDERATION, receipt of which is hereby acknowledged,
WL HOMES, LLC, a Delaware limited liability company
hereby GRANTS to
JOHN BUYER
the following described real property
SEE EXHIBIT "A"
Unit ____ , consisting of certain air space
Building 3 = 12 units - Units 21 through 32, inclusive.
"""


def test_the_sample_grant_deed_is_the_form_and_its_blanks_stay_empty():
    found = identify(Path("Sample Grant Deed.pdf"), parsers=(TextLayer(pages=lambda _path: (_SAMPLE,)),))
    assert found is not None
    assert found.kind == "grant_deed"
    assert found.values("apn") == ()
    assert found.values("unit") == ()
    assert found.values("grantor") == ("WL HOMES, LLC, a Delaware limited liability company",)
    assert found.values("grantee") == ("JOHN BUYER",)


def test_a_scanned_deed_still_fills_the_sample_blanks():
    text = """
    GRANT D33D
    Parcel N0: 201-1170-026-0019
    hereby GRANTS to
    Unit 25, in Building 3
    """
    found = identify(Path("GD scanned.pdf"), parsers=(TextLayer(pages=lambda _path: (text,)),))
    assert found is not None
    assert found.kind == "grant_deed"
    assert [(field.value, field.template) for field in found.fields if field.name == "apn"] == [
        ("201-1170-026-0019", "parcel_no"),
    ]
    assert found.values("unit") == ("25",)
    assert found.values("building") == ("3",)


def test_a_garbled_legal_description_still_reads_the_unit_and_the_parcel():
    text = """
    GRANT DEED
    A.P.N.: 201-1170-026-0021
    PARCEL ONE:
    Unit 35 inclusive in Building 5 as depicted, described and defined in the Condominium Plan for Mystique
    BuildJog~ 1,2,-4, 5,ft aml7, r_ecordeg__.J~nuary .1--6_. 2018__. as Document Ng._2J)t9_Q_1j610Q2gfQfflciaLR.ecQrds
    Units 21 through 32, inclusive.
    """
    found = identify(Path("GD 202111301835.pdf"), parsers=(TextLayer(pages=lambda _path: (text,)),))
    assert found is not None
    assert found.values("apn") == ("201-1170-026-0021",)
    assert found.values("unit") == ("35",)
    assert found.values("building") == ("5",)
