from decimal import Decimal

import pytest

from marginmesh.models import LineItem


@pytest.fixture
def make_item():
    def _make(sku, qty, price, currency="USD", source="doc:row 2"):
        return LineItem(sku, "", Decimal(str(qty)), Decimal(str(price)), currency, source)

    return _make
