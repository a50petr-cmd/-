from decimal import Decimal

import pytest

from kopilka.money import virtual_roundup


def test_roundup_examples():
    assert virtual_roundup(Decimal("180")) == (Decimal("200.00"), Decimal("20.00"))
    assert virtual_roundup(Decimal("450")) == (Decimal("500.00"), Decimal("50.00"))
    assert virtual_roundup(Decimal("100")) == (Decimal("100.00"), Decimal("0.00"))
    assert virtual_roundup(Decimal("200")) == (Decimal("200.00"), Decimal("0.00"))
    assert virtual_roundup(Decimal("1")) == (Decimal("100.00"), Decimal("99.00"))
    assert virtual_roundup(Decimal("100.01")) == (Decimal("200.00"), Decimal("99.99"))
    assert virtual_roundup(Decimal("250.50")) == (Decimal("300.00"), Decimal("49.50"))


def test_roundup_returns_decimal_not_float():
    _rounded, piggy = virtual_roundup(Decimal("180"))
    assert type(piggy) is Decimal


def test_roundup_rejects_non_positive():
    with pytest.raises(ValueError):
        virtual_roundup(Decimal("0"))
    with pytest.raises(ValueError):
        virtual_roundup(Decimal("-10"))
