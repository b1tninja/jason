from jason.community.living import Mark, Operation, Run, Verb, _before_changes
from jason.community.scan_marks import ScanChar, ScanLine, drop_furniture, styled_paragraphs


def _line(page, block, text, top=0.5, struck=(), bold=()):
    chars = tuple(ScanChar(c, i in struck, (6.0 if i in bold else 3.0) if c.strip() else 0.0) for i, c in enumerate(text))
    return ScanLine(page, block, top, top + 0.02, chars)


def test_running_footers_are_dropped_even_when_ocr_reads_them_differently():
    lines = [_line(0, 1, "the words of page one"), _line(0, 9, "Example Association  Second Amendment", top=0.95),
             _line(1, 1, "the words of page two"), _line(1, 9, "Examp1e Associafion  Second Amendmenl", top=0.95),
             _line(1, 2, "a one-off line in the margin", top=0.95)]
    kept = [line.text for line in drop_furniture(lines)]
    assert kept == ["the words of page one", "the words of page two", "a one-off line in the margin"]


def test_bold_is_judged_by_the_word_and_strike_by_the_character():
    text = "not more than ten fifteen units"
    struck = set(range(text.index("ten"), text.index("ten") + 3))
    bold = set(range(text.index("fifteen"), text.index("fifteen") + 7))
    (para,) = styled_paragraphs([_line(0, 1, text, struck=struck, bold=bold)])
    assert "".join(r.text for r in para if r.struck) == "ten"
    assert "".join(r.text for r in para if r.bold) == "fifteen"


def test_struck_words_read_by_ocr_do_not_count_against_the_base():
    op = Operation("1.1(a)", Verb.RESTATE, (Run("Not more than ", Mark.PLAIN), Run("tvventy-pcrcent", Mark.STRUCK),
                                            Run(" twenty-five", Mark.ADDED), Run(" of the Units may be leased.", Mark.PLAIN)),
                   struck_by_ocr=True)
    assert _before_changes("Not more than twenty percent of the Units may be leased.", op) == []
    assert _before_changes("Not more than twenty percent of the Units may be leased or rented.", op)
