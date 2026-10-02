from jason.community.consideration import deed_price, granting_clause


def test_county_and_city_tax_are_the_same_consideration():
    price = deed_price(
        "Documentary transfer tax is $363.00 City Transfer Tax: $907,50 "
        "computed on full value of property conveyed"
    )
    assert price is not None
    assert price.county_tax_cents == 36_300
    assert price.city_tax_cents == 90_750
    assert price.price_cents == 33_000_000
    assert price.exempt is False


def test_a_zero_tax_is_exempt():
    price = deed_price("documentary transfer tax is not payable. DOCUMENTARY TRANSFER TAX IS $-0-")
    assert price is not None
    assert price.exempt
    assert price.price_cents is None


def test_the_statute_number_is_not_the_tax():
    price = deed_price("DOCUMENTARY TRANSFER TAX IS$ 11911")
    assert price is not None
    assert price.county_tax_cents is None
    assert price.price_cents is None


def test_a_city_tax_that_disagrees_leaves_the_price_blank():
    price = deed_price("Documentary transfer tax is $110.00 City Tax $ 100.00")
    assert price is not None
    assert price.county_tax_cents == 11_000
    assert price.price_cents is None


def test_an_unchecked_exempt_line_does_not_hide_the_tax():
    price = deed_price(
        "This transfer is exempt from the documentary transfer tax. "
        "The documentary transfer tax is $506.00 and City $1,265.00 "
        "computed on the full value of the interest or property conveyed."
    )
    assert price is not None
    assert price.price_cents == 46_000_000
    assert price.exempt is False


def test_a_rounded_city_tax_still_confirms_the_price():
    price = deed_price("Documentary transfer tax is $416.35 City Tax $1,040.88 computed on full value")
    assert price is not None
    assert price.price_cents == 37_850_000


def test_the_granting_sentence_names_the_seller_and_the_buyer():
    seller, buyer = granting_clause(
        "FOR A VALUABLE CONSIDERATION, receipt of which is hereby acknowledged, "
        "Tressa Lune Penhallow and Ludo Severin Rookwood, as Trustees of the Penhallow Rookwood Trust "
        "hereby GRANT(S) to Sorrel V. Tamworth, an unmarried woman The land described herein"
    )
    assert seller.startswith("Tressa Lune Penhallow")
    assert buyer.startswith("Sorrel V. Tamworth")


def test_a_city_tax_rounded_by_the_title_company_still_computes_the_price():
    from jason.community.consideration import deed_price

    # 213,000 x 0.55 / 500 = 234.30; the city line prints 585.72 instead of 585.75.
    found = deed_price("DOCUMENTARY TRANSFER TAX $234.30; CITY TRANSFER TAX $585.72;")
    assert found is not None and found.price_cents == 21_300_000
    # A city amount a whole dollar off is a different dollar.
    assert deed_price("DOCUMENTARY TRANSFER TAX $234.30; CITY TRANSFER TAX $590.00;").price_cents is None


def test_an_ocr_slip_in_the_amount_is_repaired():
    from jason.community.consideration import deed_price

    found = deed_price("DOCUMENTARY TRANSFER TAX Sl49.60; CITY TRANSFER TAX $374.00;")
    assert found is not None
    assert found.county_tax_cents == 14_960
    assert found.price_cents == 13_600_000


def test_hyphens_for_an_underline_and_a_split_decimal_still_read():
    from jason.community.consideration import deed_price

    found = deed_price("Documentary transfer-tax--is $369.05 City Transfer Tax: $922.63 ( ) Unincorporated")
    assert found is not None and found.price_cents == 33_550_000
    found = deed_price("Documentary transfer tax is $359. 70 City Transfer Tax: $899.25")
    assert found is not None and found.county_tax_cents == 35_970 and found.price_cents == 32_700_000
