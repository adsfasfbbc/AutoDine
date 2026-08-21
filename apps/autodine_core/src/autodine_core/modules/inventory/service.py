from __future__ import annotations

from decimal import Decimal


def calculate_available_quantity(
    physical: Decimal,
    defective: Decimal,
    reserved: Decimal,
) -> Decimal:
    available = physical - defective - reserved
    if available < 0:
        return Decimal("0")
    return available
