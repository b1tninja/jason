from datetime import date

import pytest

from jason.community.provisions import (
    Alignment,
    CitationEra,
    Provision,
    annotate,
    citation_era,
    citation_session,
)


def test_unread_annotation_names_the_current_statute_and_no_section():
    note = annotate(Provision.INSURANCE)
    assert note.alignment is Alignment.UNREAD
    assert note.section == ""
    assert note.prior_statute == ""
    assert note.statute == "CIV 5806"


def test_a_read_annotation_requires_the_instrument_section():
    with pytest.raises(ValueError):
        annotate(Provision.MAINTENANCE, alignment=Alignment.RESTRICTS)
    note = annotate(
        Provision.MAINTENANCE,
        alignment=Alignment.RESTRICTS,
        section="7.1",
        prior_statute="CIV 1364",
    )
    assert note.section == "7.1"
    assert note.prior_statute == "CIV 1364"
    assert note.statute == "CIV 4775"


def test_recording_date_selects_the_numbering_era():
    assert citation_era(None) is None
    assert citation_era(date(2013, 12, 31)) is CitationEra.PRIOR
    assert citation_era(date(2014, 1, 1)) is CitationEra.CURRENT
    assert citation_session(date(2007, 9, 12), ("2011",)) == "2011"
    assert citation_session(date(2007, 9, 12), ("2011", "2025")) == "2011"
    assert citation_session(date(2016, 1, 1), ("2011", "2025")) == "2025"
    assert citation_session(date(2007, 9, 12), ("2025",)) is None
