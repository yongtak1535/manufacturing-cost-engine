from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


AMOUNT_QUANTUM = Decimal("0.01")


def to_decimal(value) -> Decimal:
    """Convert numeric input to Decimal safely."""
    if isinstance(value, Decimal):
        return value

    if value is None:
        return Decimal("0")

    return Decimal(str(value))


def round_amount(value) -> Decimal:
    """Round KRW amount using ROUND_HALF_UP."""
    return to_decimal(value).quantize(
        AMOUNT_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


def calculate_material_cost(quantity, unit_cost) -> Decimal:
    """Calculate material cost = quantity × unit cost."""
    return round_amount(
        to_decimal(quantity) * to_decimal(unit_cost)
    )


def calculate_labor_cost(hours, hourly_rate) -> Decimal:
    """Calculate labor cost = hours × hourly rate."""
    return round_amount(
        to_decimal(hours) * to_decimal(hourly_rate)
    )


def calculate_overhead_cost(base_amount, overhead_rate) -> Decimal:
    """Calculate overhead cost = allocation base × overhead rate."""
    return round_amount(
        to_decimal(base_amount) * to_decimal(overhead_rate)
    )


def calculate_total_cost(
    material_cost=0,
    labor_cost=0,
    overhead_cost=0,
) -> Decimal:
    """Calculate total manufacturing cost."""
    return round_amount(
        to_decimal(material_cost)
        + to_decimal(labor_cost)
        + to_decimal(overhead_cost)
    )


def calculate_unit_cost(total_cost, production_quantity) -> Decimal:
    """Calculate manufacturing unit cost."""
    quantity = to_decimal(production_quantity)

    if quantity == 0:
        raise ValueError("production_quantity must not be zero")

    return round_amount(
        to_decimal(total_cost) / quantity
    )
