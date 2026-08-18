from decimal import Decimal

import pytest

from manufacturing_cost_engine.cost_engine import (
    calculate_material_cost,
    calculate_labor_cost,
    calculate_overhead_cost,
    calculate_total_cost,
    calculate_unit_cost,
    calculate_actual_material_cost,
    calculate_actual_labor_cost,
    calculate_actual_overhead_cost,
    calculate_actual_total_cost_by_wo,
    calculate_actual_unit_cost_by_wo,
    calculate_total_variance_by_wo,
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


def _wo(wo_no="WO-1", product_code="P-100", period_key="2026-07"):
    return {"wo_no": wo_no, "product_code": product_code, "period_key": period_key}

def _product(product_code="P-100"):
    return {"product_code": product_code}

def _material(material_code="MAT-001"):
    return {"material_code": material_code}

def _issue(wo_no="WO-1", material_code="MAT-001", issued_qty="10",
           unit_cost="100", issue_type="ISSUE"):
    return {
        "wo_no": wo_no, "material_code": material_code, "issued_qty": issued_qty,
        "unit_cost": unit_cost, "issue_type": issue_type,
    }

def _labor(wo_no="WO-1", actual_hours="1", actual_rate="24000", amount="24000",
           direct_indirect="DIRECT", work_center_code="WC-20", operation_seq=20,
           operation_code="OP-TRN"):
    return {
        "wo_no": wo_no, "actual_hours": actual_hours, "actual_rate": actual_rate,
        "amount": amount, "direct_indirect": direct_indirect,
        "work_center_code": work_center_code, "operation_seq": operation_seq,
        "operation_code": operation_code,
    }

def _work_center(work_center_code="WC-20", cost_center_code="CC-100"):
    return {"work_center_code": work_center_code, "cost_center_code": cost_center_code}

def _overhead_rate(period_key="2026-07", cost_center_code="CC-100",
                    rate_per_base="18000"):
    return {
        "period_key": period_key, "cost_center_code": cost_center_code,
        "rate_per_base": rate_per_base, "allocation_base": "DLH",
    }

def _production_output(wo_no="WO-1", good_qty="10"):
    return {"wo_no": wo_no, "good_qty": good_qty}

def _standard_cost(product_code="P-100", period_key="2026-07",
                    cost_element_code="DM", standard_amount="100"):
    return {
        "product_code": product_code, "period_key": period_key,
        "cost_element_code": cost_element_code, "standard_amount": standard_amount,
    }


# --- calculate_actual_material_cost ---

def test_actual_material_cost_sums_multiple_issue_lines():
    result = calculate_actual_material_cost(
        [_wo()],
        [_issue(issued_qty="10", unit_cost="100"), _issue(issued_qty="5", unit_cost="100")],
        [_material()],
        [_product()],
    )
    assert result == {"WO-1": Decimal("1500.00")}

def test_actual_material_cost_return_reduces_net():
    result = calculate_actual_material_cost(
        [_wo()],
        [
            _issue(issued_qty="10", unit_cost="100", issue_type="ISSUE"),
            _issue(issued_qty="2", unit_cost="100", issue_type="RETURN"),
        ],
        [_material()],
        [_product()],
    )
    assert result == {"WO-1": Decimal("800.00")}

def test_actual_material_cost_excludes_unknown_material():
    result = calculate_actual_material_cost(
        [_wo()],
        [_issue(material_code="MAT-999")],
        [_material("MAT-001")],
        [_product()],
    )
    assert result == {}

def test_actual_material_cost_excludes_unknown_wo():
    result = calculate_actual_material_cost(
        [_wo(wo_no="WO-1")],
        [_issue(wo_no="WO-9999")],
        [_material()],
        [_product()],
    )
    assert result == {}

def test_actual_material_cost_excludes_wo_with_unregistered_product():
    # 실제 WO-2607-020(product_code=P-999)처럼 WO는 있지만 product가 미등록인 경우.
    result = calculate_actual_material_cost(
        [_wo(wo_no="WO-1", product_code="P-999")],
        [_issue(wo_no="WO-1")],
        [_material()],
        [_product("P-100")],
    )
    assert result == {}

def test_actual_material_cost_excludes_unparseable_quantity():
    result = calculate_actual_material_cost(
        [_wo()],
        [_issue(issued_qty="1,2 3 4")],
        [_material()],
        [_product()],
    )
    assert result == {}


# --- calculate_actual_labor_cost ---

def test_actual_labor_cost_sums_valid_direct_rows():
    result = calculate_actual_labor_cost(
        [_wo()],
        [_labor(amount="24000"), _labor(amount="12000")],
        [_product()],
    )
    assert result == {"WO-1": Decimal("36000")}

def test_actual_labor_cost_excludes_negative_hours():
    result = calculate_actual_labor_cost(
        [_wo()],
        [_labor(actual_hours="-1", amount="-24000")],
        [_product()],
    )
    assert result == {}

def test_actual_labor_cost_excludes_zero_rate():
    # 실제 LB-2607-039(actual_rate=0)와 동일한 케이스: 설계문서상 "임률 결측".
    result = calculate_actual_labor_cost(
        [_wo()],
        [_labor(actual_rate="0", amount="0")],
        [_product()],
    )
    assert result == {}

def test_actual_labor_cost_includes_row_with_unknown_routing_operation():
    # 실제 LB-2607-036(operation_seq=99)와 동일: hours/rate가 유효하면 routing
    # 대사 실패와 무관하게 포함한다.
    result = calculate_actual_labor_cost(
        [_wo()],
        [_labor(operation_seq=99, operation_code="OP-XXX", amount="12000")],
        [_product()],
    )
    assert result == {"WO-1": Decimal("12000")}

def test_actual_labor_cost_includes_row_with_hours_sum_mismatch():
    # 실제 LB-2607-047과 동일: HOURS_SUM_MISMATCH만 있고 hours/rate/amount는 유효.
    result = calculate_actual_labor_cost(
        [_wo()],
        [_labor(actual_hours="1.5", amount="36000")],
        [_product()],
    )
    assert result == {"WO-1": Decimal("36000")}

def test_actual_labor_cost_excludes_indirect():
    result = calculate_actual_labor_cost(
        [_wo()],
        [_labor(direct_indirect="INDIRECT")],
        [_product()],
    )
    assert result == {}


# --- calculate_actual_overhead_cost ---

def test_actual_overhead_cost_applies_rate_by_cost_center():
    oh, unallocated = calculate_actual_overhead_cost(
        [_wo()],
        [_labor(actual_hours="1")],
        [_work_center("WC-20", "CC-100")],
        [_overhead_rate("2026-07", "CC-100", "18000")],
        [_product()],
    )
    assert oh == {"WO-1": Decimal("18000.00")}
    assert unallocated == {}

def test_actual_overhead_cost_not_allocated_when_rate_missing():
    # CC-300처럼 overhead_rate가 없는 cost_center는 임의 배분하지 않는다.
    oh, unallocated = calculate_actual_overhead_cost(
        [_wo()],
        [_labor(actual_hours="2", work_center_code="WC-50")],
        [_work_center("WC-50", "CC-300")],
        [_overhead_rate("2026-07", "CC-100", "18000")],
        [_product()],
    )
    assert oh == {}
    assert unallocated == {"WO-1": Decimal("2")}

def test_actual_overhead_cost_excludes_invalid_labor_rows():
    oh, unallocated = calculate_actual_overhead_cost(
        [_wo()],
        [_labor(actual_hours="-1")],
        [_work_center("WC-20", "CC-100")],
        [_overhead_rate("2026-07", "CC-100", "18000")],
        [_product()],
    )
    assert oh == {}
    assert unallocated == {}


# --- calculate_actual_total_cost_by_wo / calculate_actual_unit_cost_by_wo ---

def test_actual_total_cost_by_wo_combines_dm_dl_oh():
    result = calculate_actual_total_cost_by_wo(
        [_wo()],
        [_issue(issued_qty="10", unit_cost="100")],
        [_labor(actual_hours="1", amount="24000")],
        [_material()],
        [_work_center("WC-20", "CC-100")],
        [_overhead_rate("2026-07", "CC-100", "18000")],
        [_product()],
    )
    wo = result["WO-1"]
    assert wo["material_cost"] == Decimal("1000.00")
    assert wo["labor_cost"] == Decimal("24000")
    assert wo["overhead_cost"] == Decimal("18000.00")
    assert wo["total_cost"] == Decimal("43000.00")

def test_actual_unit_cost_by_wo_divides_by_good_qty():
    totals = {"WO-1": {"total_cost": Decimal("1000.00")}}
    result = calculate_actual_unit_cost_by_wo(totals, [_production_output(good_qty="10")])
    assert result == {"WO-1": Decimal("100.00")}

def test_actual_unit_cost_by_wo_excludes_zero_good_qty():
    # 실제 WO-2607-009(good_qty=0)와 동일한 케이스: 0으로 나누지 않고 결과에서 제외한다.
    totals = {"WO-1": {"total_cost": Decimal("1000.00")}}
    result = calculate_actual_unit_cost_by_wo(totals, [_production_output(good_qty="0")])
    assert result == {}

def test_actual_unit_cost_by_wo_excludes_wo_without_production_output():
    # 실제 WO-2607-017(산출 실적 없음)과 동일한 케이스.
    totals = {"WO-1": {"total_cost": Decimal("1000.00")}}
    result = calculate_actual_unit_cost_by_wo(totals, [])
    assert result == {}


# --- calculate_total_variance_by_wo ---

def test_total_variance_by_wo_combines_dm_dl_oh_elements():
    result = calculate_total_variance_by_wo(
        [_wo()],
        [_issue(issued_qty="10", unit_cost="100")],
        [_labor(actual_hours="1", actual_rate="600", amount="600")],
        [_material()],
        [_work_center("WC-20", "CC-100")],
        [_overhead_rate("2026-07", "CC-100", "200")],
        [_product()],
        [_production_output(good_qty="10")],
        [
            _standard_cost(cost_element_code="DM", standard_amount="80"),
            _standard_cost(cost_element_code="DL", standard_amount="50"),
            _standard_cost(cost_element_code="OH", standard_amount="30"),
        ],
    )
    wo = result["WO-1"]
    assert wo["flexed_standard_dm"] == Decimal("800.00")
    assert wo["flexed_standard_dl"] == Decimal("500.00")
    assert wo["flexed_standard_oh"] == Decimal("300.00")
    assert wo["flexed_standard_total"] == Decimal("1600.00")
    assert wo["actual_material_cost"] == Decimal("1000.00")
    assert wo["actual_labor_cost"] == Decimal("600")
    assert wo["actual_overhead_cost"] == Decimal("200.00")
    assert wo["actual_total_cost"] == Decimal("1800.00")
    assert wo["dm_variance"] == Decimal("200.00")
    assert wo["dl_variance"] == Decimal("100")
    assert wo["oh_variance"] == Decimal("-100.00")
    assert wo["total_variance"] == Decimal("200.00")

def test_total_variance_by_wo_dm_only_when_dl_oh_standard_missing():
    # 제품의 standard_cost에 DM만 있는 경우: 있는 요소만 계산하고 없는 요소는
    # 결과 dict에 키를 넣지 않는다(전부 없어야만 WO 전체를 생략한다).
    result = calculate_total_variance_by_wo(
        [_wo()],
        [_issue(issued_qty="10", unit_cost="100")],
        [],
        [_material()],
        [],
        [],
        [_product()],
        [_production_output(good_qty="10")],
        [_standard_cost(cost_element_code="DM", standard_amount="80")],
    )
    wo = result["WO-1"]
    assert wo["flexed_standard_dm"] == Decimal("800.00")
    assert wo["dm_variance"] == Decimal("200.00")
    assert "dl_variance" not in wo
    assert "oh_variance" not in wo
    assert wo["flexed_standard_total"] == Decimal("800.00")
    assert wo["total_variance"] == Decimal("200.00")

def test_total_variance_by_wo_excludes_wo_with_no_standard_cost_at_all():
    # 실제 WO-2607-020(product_code=P-999, standard_cost 자체가 없음)과 동일한 케이스.
    result = calculate_total_variance_by_wo(
        [_wo()],
        [_issue(issued_qty="10", unit_cost="100")],
        [],
        [_material()],
        [],
        [],
        [_product()],
        [_production_output(good_qty="10")],
        [],
    )
    assert result == {}

def test_total_variance_by_wo_excludes_zero_good_qty():
    # 실제 WO-2607-009(good_qty=0)와 동일한 케이스.
    result = calculate_total_variance_by_wo(
        [_wo()],
        [_issue(issued_qty="10", unit_cost="100")],
        [],
        [_material()],
        [],
        [],
        [_product()],
        [_production_output(good_qty="0")],
        [_standard_cost(cost_element_code="DM", standard_amount="80")],
    )
    assert result == {}

def test_total_variance_by_wo_no_actual_cost_defaults_to_zero():
    # 실적 거래가 전혀 없는 WO(예: WO-2607-018/019)도 Actual=0으로 계산되어야
    # 하며, calculate_actual_total_cost_by_wo() 결과에 아예 없다고 해서 제외하지
    # 않는다.
    result = calculate_total_variance_by_wo(
        [_wo()],
        [],
        [],
        [_material()],
        [],
        [],
        [_product()],
        [_production_output(good_qty="10")],
        [
            _standard_cost(cost_element_code="DM", standard_amount="80"),
            _standard_cost(cost_element_code="DL", standard_amount="50"),
            _standard_cost(cost_element_code="OH", standard_amount="30"),
        ],
    )
    wo = result["WO-1"]
    assert wo["actual_material_cost"] == Decimal("0")
    assert wo["actual_labor_cost"] == Decimal("0")
    assert wo["actual_overhead_cost"] == Decimal("0")
    assert wo["actual_total_cost"] == Decimal("0")
    assert wo["dm_variance"] == Decimal("-800.00")
    assert wo["dl_variance"] == Decimal("-500.00")
    assert wo["oh_variance"] == Decimal("-300.00")
    assert wo["total_variance"] == Decimal("-1600.00")

def test_total_variance_by_wo_decimal_precision():
    result = calculate_total_variance_by_wo(
        [_wo()],
        [_issue(issued_qty="1", unit_cost="100.015")],
        [],
        [_material()],
        [],
        [],
        [_product()],
        [_production_output(good_qty="3")],
        [_standard_cost(cost_element_code="DM", standard_amount="33.335")],
    )
    wo = result["WO-1"]
    # standard_amount(33.335) x good_qty(3) = 100.005 -> ROUND_HALF_UP -> 100.01
    assert wo["flexed_standard_dm"] == Decimal("100.01")
    # issued_qty(1) x unit_cost(100.015) = 100.015 -> ROUND_HALF_UP -> 100.02
    assert wo["actual_material_cost"] == Decimal("100.02")
    assert wo["dm_variance"] == Decimal("0.01")
