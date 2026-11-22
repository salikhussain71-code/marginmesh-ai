from decimal import Decimal

from marginmesh.models import (
    Severity,
    fmt_price,
    money,
    plain_money,
    plain_number,
    severity_for_ratio,
)


def test_money_rounds_half_up():
    assert money(Decimal("2.675")) == Decimal("2.68")
    assert money(Decimal("-2.675")) == Decimal("-2.68")


def test_plain_formats_have_no_exponent():
    assert plain_money(Decimal("1E+3")) == "1000.00"
    assert plain_number(Decimal("1E+3")) == "1000"
    assert plain_number(Decimal("2.50")) == "2.5"


def test_fmt_price_keeps_two_to_four_decimals():
    assert fmt_price(Decimal("5.3")) == "5.30"
    assert fmt_price(Decimal("5")) == "5.00"
    assert fmt_price(Decimal("0.0625")) == "0.0625"


def test_severity_bands():
    assert severity_for_ratio(Decimal("0.05")) is Severity.HIGH
    assert severity_for_ratio(Decimal("0.0499")) is Severity.MEDIUM
    assert severity_for_ratio(Decimal("0.01")) is Severity.MEDIUM
    assert severity_for_ratio(Decimal("0.0099")) is Severity.LOW
