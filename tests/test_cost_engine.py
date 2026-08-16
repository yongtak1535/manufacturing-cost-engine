from decimal import Decimal

import pytest

from manufacturing_cost_engine.cost_engine import (
    calculate_material_cost,
    calculate_labor_cost,
    calculate_overhead_cost,
    calculate_total_cost,
    calculate_unit_cost,
)


def test_material_cost():
    result = calculate_material_cost(10, 125.55)

    assert result == Decimal("1255.50")


def test_labor_cost():
    result = calculate_labor_cost(8, 15000)

    assert result == Decimal("120000.00")


def test_overhead_cost():
    result = calculate_overhead_cost(100000, 0.18)

    assert result == Decimal("18000.00")


def test_total_cost():
    result = calculate_total_cost(
        material_cost=1255.50,
        labor_cost=120000,
        overhead_cost=18000,
    )

    assert result == Decimal("139255.50")


def test_unit_cost():
    result = calculate_unit_cost(
        total_cost=139255.50,
        production_quantity=10,
    )

    assert result == Decimal("13925.55")


def test_unit_cost_zero_quantity():
    with pytest.raises(ValueError):
        calculate_unit_cost(
            total_cost=100000,
            production_quantity=0,
        )
def test_round_half_up():
    result = calculate_material_cost(3, "1.005")

    assert result == Decimal("3.02")


def test_material_cost_with_none_quantity():
    result = calculate_material_cost(None, 100)

    assert result == Decimal("0.00")


def test_labor_cost_decimal_input():
    result = calculate_labor_cost("1.005", "1")

    assert result == Decimal("1.01")


def test_overhead_cost_decimal_input():
    result = calculate_overhead_cost("100", "0.015")

    assert result == Decimal("1.50")
