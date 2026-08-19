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
    calculate_material_price_quantity_variance_by_wo,
    calculate_applied_overhead_by_cost_center,
    calculate_actual_total_cost_by_contract,
    calculate_standard_budget_by_contract,
    calculate_contract_variance,
    calculate_actual_direct_expense_by_contract,
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

def _standard_cost_detail(product_code="P-100", period_key="2026-07", ref_type="MATERIAL",
                           ref_material_code="MAT-001", standard_qty="1",
                           standard_unit_price="100"):
    return {
        "product_code": product_code, "period_key": period_key, "ref_type": ref_type,
        "ref_material_code": ref_material_code, "standard_qty": standard_qty,
        "standard_unit_price": standard_unit_price,
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


# --- calculate_material_price_quantity_variance_by_wo (DM PV/QV) ---

def test_pv_qv_zero_when_actual_matches_standard():
    # 실제 WO-2607-005/010/013과 동일한 패턴: AP=SP, AQ=flexed SQ -> PV=QV=0.
    result = calculate_material_price_quantity_variance_by_wo(
        [_wo()],
        [_issue(material_code="MAT-001", issued_qty="10", unit_cost="100")],
        [_material("MAT-001")],
        [_product()],
        [_production_output(good_qty="10")],
        [_standard_cost_detail(ref_material_code="MAT-001", standard_qty="1", standard_unit_price="100")],
    )
    wo = result["WO-1"]
    assert wo["price_variance_total"] == Decimal("0.00")
    assert wo["quantity_variance_total"] == Decimal("0.00")
    mat = wo["materials"]["MAT-001"]
    assert mat["actual_qty"] == Decimal("10")
    assert mat["flexed_standard_qty"] == Decimal("10")

def test_pv_qv_price_variance_only():
    # 실제 WO-2607-004/MAT-009와 동일한 패턴: 수량은 표준과 같지만 단가만 다름.
    result = calculate_material_price_quantity_variance_by_wo(
        [_wo()],
        [_issue(material_code="MAT-001", issued_qty="10", unit_cost="90")],
        [_material("MAT-001")],
        [_product()],
        [_production_output(good_qty="10")],
        [_standard_cost_detail(ref_material_code="MAT-001", standard_qty="1", standard_unit_price="100")],
    )
    wo = result["WO-1"]
    assert wo["price_variance_total"] == Decimal("-100.00")
    assert wo["quantity_variance_total"] == Decimal("0.00")

def test_pv_qv_no_actual_defaults_to_zero_and_reports_unfavorable_qv():
    # 실제 WO-2607-019와 동일한 패턴: 실적 거래가 전혀 없는 WO도 Actual=0으로
    # 계산되고(제외되지 않음) QV는 flexed 표준 전체만큼 불리하게 나온다.
    result = calculate_material_price_quantity_variance_by_wo(
        [_wo()],
        [],
        [_material("MAT-001")],
        [_product()],
        [_production_output(good_qty="10")],
        [_standard_cost_detail(ref_material_code="MAT-001", standard_qty="1", standard_unit_price="100")],
    )
    wo = result["WO-1"]
    assert wo["price_variance_total"] == Decimal("0.00")
    assert wo["quantity_variance_total"] == Decimal("-1000.00")
    mat = wo["materials"]["MAT-001"]
    assert mat["actual_qty"] == Decimal("0")
    assert mat["actual_cost"] == Decimal("0")

def test_pv_qv_excludes_wo_with_no_material_detail_at_all():
    # 실제 P-100/P-300/P-400/P-900처럼 ref_type=MATERIAL detail이 전혀 없는
    # 제품은 0으로 채우지 않고 결과에서 제외한다.
    result = calculate_material_price_quantity_variance_by_wo(
        [_wo()],
        [_issue(material_code="MAT-001", issued_qty="10", unit_cost="100")],
        [_material("MAT-001")],
        [_product()],
        [_production_output(good_qty="10")],
        [],
    )
    assert result == {}

def test_pv_qv_excludes_zero_good_qty():
    result = calculate_material_price_quantity_variance_by_wo(
        [_wo()],
        [_issue(material_code="MAT-001", issued_qty="10", unit_cost="100")],
        [_material("MAT-001")],
        [_product()],
        [_production_output(good_qty="0")],
        [_standard_cost_detail(ref_material_code="MAT-001", standard_qty="1", standard_unit_price="100")],
    )
    assert result == {}

def test_pv_qv_ignores_non_material_ref_type():
    # standard_cost_detail에 ref_type=OPERATION만 있으면(자재별 표준 없음)
    # ref_type=MATERIAL 한정 원칙에 따라 계산 대상이 아니다.
    result = calculate_material_price_quantity_variance_by_wo(
        [_wo()],
        [_issue(material_code="MAT-001", issued_qty="10", unit_cost="100")],
        [_material("MAT-001")],
        [_product()],
        [_production_output(good_qty="10")],
        [_standard_cost_detail(ref_type="OPERATION", ref_material_code="MAT-001",
                                standard_qty="1", standard_unit_price="100")],
    )
    assert result == {}

def test_pv_qv_excludes_material_without_standard_but_keeps_others():
    # standard_cost_detail에 없는 자재(MAT-002)가 issue되어도 그 자재는
    # breakdown에서 제외되고, 표준이 있는 MAT-001은 정상 계산된다.
    result = calculate_material_price_quantity_variance_by_wo(
        [_wo()],
        [
            _issue(material_code="MAT-001", issued_qty="10", unit_cost="100"),
            _issue(material_code="MAT-002", issued_qty="5", unit_cost="50"),
        ],
        [_material("MAT-001"), _material("MAT-002")],
        [_product()],
        [_production_output(good_qty="10")],
        [_standard_cost_detail(ref_material_code="MAT-001", standard_qty="1", standard_unit_price="100")],
    )
    wo = result["WO-1"]
    assert set(wo["materials"].keys()) == {"MAT-001"}
    assert wo["price_variance_total"] == Decimal("0.00")
    assert wo["quantity_variance_total"] == Decimal("0.00")

def test_pv_qv_return_issue_nets_quantity_and_cost():
    # RETURN 행이 수량과 금액 모두에서 순액으로 반영되는지 확인한다
    # (calculate_actual_material_cost()의 net 처리 규칙과 동일해야 함).
    result = calculate_material_price_quantity_variance_by_wo(
        [_wo()],
        [
            _issue(material_code="MAT-001", issued_qty="15", unit_cost="100", issue_type="ISSUE"),
            _issue(material_code="MAT-001", issued_qty="2", unit_cost="100", issue_type="RETURN"),
        ],
        [_material("MAT-001")],
        [_product()],
        [_production_output(good_qty="10")],
        [_standard_cost_detail(ref_material_code="MAT-001", standard_qty="1", standard_unit_price="100")],
    )
    mat = result["WO-1"]["materials"]["MAT-001"]
    assert mat["actual_qty"] == Decimal("13")
    assert mat["actual_cost"] == Decimal("1300.00")
    # flexed_standard_qty = 1 x good_qty(10) = 10 -> QV = (13-10) x 100 = 300.00 (불리)
    assert mat["quantity_variance"] == Decimal("300.00")
    # AP=SP(100)이므로 PV=0
    assert mat["price_variance"] == Decimal("0.00")

def test_pv_qv_decimal_precision():
    result = calculate_material_price_quantity_variance_by_wo(
        [_wo()],
        [_issue(material_code="MAT-001", issued_qty="3", unit_cost="33.335")],
        [_material("MAT-001")],
        [_product()],
        [_production_output(good_qty="3")],
        [_standard_cost_detail(ref_material_code="MAT-001", standard_qty="1", standard_unit_price="33.34")],
    )
    mat = result["WO-1"]["materials"]["MAT-001"]
    # issued_qty(3) x unit_cost(33.335) = 100.005 -> ROUND_HALF_UP -> 100.01
    assert mat["actual_cost"] == Decimal("100.01")
    # PV = 100.01 - (33.34 x 3 = 100.02) = -0.01
    assert mat["price_variance"] == Decimal("-0.01")
    assert mat["quantity_variance"] == Decimal("0.00")


# --- calculate_applied_overhead_by_cost_center ---

def test_applied_overhead_by_cost_center_sums_multiple_wo_into_one_cc():
    result = calculate_applied_overhead_by_cost_center(
        [_wo(wo_no="WO-1"), _wo(wo_no="WO-2")],
        [
            _labor(wo_no="WO-1", actual_hours="1", work_center_code="WC-20"),
            _labor(wo_no="WO-2", actual_hours="2", work_center_code="WC-20"),
        ],
        [_work_center("WC-20", "CC-100")],
        [_overhead_rate("2026-07", "CC-100", "18000")],
        [_product()],
    )
    assert result == {("2026-07", "CC-100"): Decimal("54000.00")}

def test_applied_overhead_by_cost_center_tracks_multiple_cc_independently():
    result = calculate_applied_overhead_by_cost_center(
        [_wo(wo_no="WO-1"), _wo(wo_no="WO-2")],
        [
            _labor(wo_no="WO-1", actual_hours="1", work_center_code="WC-20"),
            _labor(wo_no="WO-2", actual_hours="2", work_center_code="WC-30"),
        ],
        [_work_center("WC-20", "CC-100"), _work_center("WC-30", "CC-200")],
        [
            _overhead_rate("2026-07", "CC-100", "18000"),
            _overhead_rate("2026-07", "CC-200", "10000"),
        ],
        [_product()],
    )
    assert result == {
        ("2026-07", "CC-100"): Decimal("18000.00"),
        ("2026-07", "CC-200"): Decimal("20000.00"),
    }

def test_applied_overhead_by_cost_center_excludes_cc_without_rate():
    # 실제 CC-300과 동일한 케이스: overhead_rate가 없으면 임의 배분하지 않고 제외한다.
    result = calculate_applied_overhead_by_cost_center(
        [_wo()],
        [_labor(actual_hours="1", work_center_code="WC-50")],
        [_work_center("WC-50", "CC-300")],
        [_overhead_rate("2026-07", "CC-100", "18000")],
        [_product()],
    )
    assert result == {}

def test_applied_overhead_by_cost_center_excludes_invalid_labor_rows():
    # calculate_actual_overhead_cost()와 동일한 필터: INDIRECT/음수 시간/rate<=0 제외.
    result = calculate_applied_overhead_by_cost_center(
        [_wo()],
        [
            _labor(direct_indirect="INDIRECT", actual_hours="1"),
            _labor(actual_hours="-1"),
            _labor(actual_rate="0"),
        ],
        [_work_center("WC-20", "CC-100")],
        [_overhead_rate("2026-07", "CC-100", "18000")],
        [_product()],
    )
    assert result == {}


# --- calculate_actual_total_cost_by_contract (Phase 2 1단계) ---

def _wo_with_contract(wo_no, contract_no, product_code="P-100"):
    return {**_wo(wo_no=wo_no, product_code=product_code), "contract_no": contract_no}

def test_actual_total_cost_by_contract_aggregates_multiple_wo():
    # CONTRACT-A에 WO-1, WO-2 두 건이 연결된 경우, 두 WO의 Actual 합계가
    # 계약 합계와 정확히 일치해야 한다(테스트 A와 동일한 패턴, 합성 데이터).
    actual_totals_by_wo = {
        "WO-1": {"material_cost": Decimal("100.00"), "labor_cost": Decimal("50"),
                  "overhead_cost": Decimal("10.00"), "total_cost": Decimal("160.00")},
        "WO-2": {"material_cost": Decimal("200.00"), "labor_cost": Decimal("70"),
                  "overhead_cost": Decimal("20.00"), "total_cost": Decimal("290.00")},
    }
    result = calculate_actual_total_cost_by_contract(
        [
            _wo_with_contract("WO-1", "CONTRACT-A"),
            _wo_with_contract("WO-2", "CONTRACT-A"),
        ],
        actual_totals_by_wo,
    )
    c = result["CONTRACT-A"]
    assert c["actual_material_cost"] == Decimal("300.00")
    assert c["actual_labor_cost"] == Decimal("120")
    assert c["actual_overhead_cost"] == Decimal("30.00")
    assert c["actual_manufacturing_cost"] == Decimal("450.00")
    assert c["work_order_count"] == 2
    assert c["work_orders"] == ["WO-1", "WO-2"]

def test_actual_total_cost_by_contract_excludes_wo_without_contract_no():
    # contract_no가 None인 WO는 어떤 계약에도 집계되지 않고 결과에서도 나타나지 않는다.
    actual_totals_by_wo = {
        "WO-1": {"material_cost": Decimal("100.00"), "labor_cost": Decimal("50"),
                  "overhead_cost": Decimal("10.00"), "total_cost": Decimal("160.00")},
    }
    result = calculate_actual_total_cost_by_contract(
        [_wo_with_contract("WO-1", None)],
        actual_totals_by_wo,
    )
    assert result == {}

def test_actual_total_cost_by_contract_defaults_missing_actual_to_zero():
    # 계약에 연결됐지만 실적 거래가 전혀 없어 actual_totals_by_wo에 없는 WO는
    # 0으로 집계되고, work_order_count에는 그대로 포함된다(생략되지 않음).
    result = calculate_actual_total_cost_by_contract(
        [_wo_with_contract("WO-1", "CONTRACT-A")],
        {},
    )
    c = result["CONTRACT-A"]
    assert c["actual_material_cost"] == Decimal("0")
    assert c["actual_labor_cost"] == Decimal("0")
    assert c["actual_overhead_cost"] == Decimal("0")
    assert c["actual_manufacturing_cost"] == Decimal("0")
    assert c["work_order_count"] == 1
    assert c["work_orders"] == ["WO-1"]


# --- 실제 Phase 1 데이터 기준 Contract 검증 (테스트 A/B, 데이터셋 존재 시에만 실행) ---

def _load_real_contract_scenario():
    import sys
    from pathlib import Path
    sys.path.insert(0, "src")
    from manufacturing_cost_engine.loader import load_dataset

    dataset = Path("hanbit_mvp_dataset_phase1")
    if not dataset.exists():
        return None

    data = load_dataset(dataset)

    def rows(file, sheet):
        return data.get(f"{file}::{sheet}", [])

    work_orders = rows("20_work_order.xlsx", "work_order")
    actual_by_wo = calculate_actual_total_cost_by_wo(
        work_orders,
        rows("22_material_issue.xlsx", "material_issue"),
        rows("23_labor_transaction.xlsx", "labor_transaction"),
        rows("08_material_master.xlsx", "material"),
        rows("09_work_center.xlsx", "work_center"),
        rows("13_overhead_rate.xlsx", "overhead_rate"),
        rows("07_product_master.xlsx", "product"),
    )
    return calculate_actual_total_cost_by_contract(work_orders, actual_by_wo)

def test_real_dataset_contract_001_matches_wo_001_002_003_sum():
    result = _load_real_contract_scenario()
    if result is None:
        return

    c = result["CONTRACT-001"]
    assert c["work_order_count"] == 3
    assert set(c["work_orders"]) == {"WO-2607-001", "WO-2607-002", "WO-2607-003"}
    assert c["actual_material_cost"] == Decimal("704220.88")
    assert c["actual_labor_cost"] == Decimal("636000")
    assert c["actual_overhead_cost"] == Decimal("477000.00")
    assert c["actual_manufacturing_cost"] == Decimal("1817220.88")

def test_real_dataset_contract_002_matches_wo_004_005_010_013_sum():
    result = _load_real_contract_scenario()
    if result is None:
        return

    c = result["CONTRACT-002"]
    assert c["work_order_count"] == 4
    assert set(c["work_orders"]) == {"WO-2607-004", "WO-2607-005", "WO-2607-010", "WO-2607-013"}
    assert c["actual_material_cost"] == Decimal("1089612.00")
    assert c["actual_labor_cost"] == Decimal("96000")
    assert c["actual_overhead_cost"] == Decimal("72000.00")
    assert c["actual_manufacturing_cost"] == Decimal("1257612.00")

def test_real_dataset_contract_003_has_zero_actual_cost_no_transactions_yet():
    # WO-2607-018/019은 OPEN 상태이며 실적 거래가 전혀 없다 — 0으로 집계되어야
    # 하며(생략되지 않음), 계약 미배정 WO는 이 결과에 전혀 나타나지 않아야 한다.
    result = _load_real_contract_scenario()
    if result is None:
        return

    c = result["CONTRACT-003"]
    assert c["work_order_count"] == 2
    assert set(c["work_orders"]) == {"WO-2607-018", "WO-2607-019"}
    assert c["actual_material_cost"] == Decimal("0")
    assert c["actual_labor_cost"] == Decimal("0")
    assert c["actual_overhead_cost"] == Decimal("0")
    assert c["actual_manufacturing_cost"] == Decimal("0")

    assert set(result.keys()) == {"CONTRACT-001", "CONTRACT-002", "CONTRACT-003"}


# --- calculate_standard_budget_by_contract (Phase 2 2단계) ---

def _budget_contract(contract_no="CONTRACT-A"):
    return {"company_code": "HB01", "contract_no": contract_no}

def _budget_wo(wo_no, contract_no, product_code="P-100", planned_qty="10",
               period_key="2026-07", wo_status="CLOSED"):
    return {
        "wo_no": wo_no, "product_code": product_code, "period_key": period_key,
        "planned_qty": planned_qty, "contract_no": contract_no,
        "wo_status": wo_status,
    }

def test_standard_budget_by_contract_aggregates_multiple_wo_same_product():
    # 테스트 A: 계약 1개에 WO 2건(동일 제품) 연결 -> planned_qty x 표준원가 합산.
    result = calculate_standard_budget_by_contract(
        [_budget_contract("CONTRACT-A")],
        [
            _budget_wo("WO-1", "CONTRACT-A", "P-100", "10"),
            _budget_wo("WO-2", "CONTRACT-A", "P-100", "5"),
        ],
        [
            _standard_cost("P-100", cost_element_code="DM", standard_amount="100"),
            _standard_cost("P-100", cost_element_code="DL", standard_amount="50"),
            _standard_cost("P-100", cost_element_code="OH", standard_amount="30"),
        ],
        [_product("P-100")],
    )
    c = result["CONTRACT-A"]
    # WO-1: DM=1000,DL=500,OH=300 / WO-2: DM=500,DL=250,OH=150 -> 합계 DM=1500,DL=750,OH=450
    assert c["budget_material_cost"] == Decimal("1500.00")
    assert c["budget_labor_cost"] == Decimal("750.00")
    assert c["budget_overhead_cost"] == Decimal("450.00")
    assert c["budget_manufacturing_cost"] == Decimal("2700.00")
    assert c["work_order_count"] == 2
    assert c["work_orders"] == ["WO-1", "WO-2"]

def test_standard_budget_by_contract_aggregates_different_products():
    # 테스트 B: 동일 계약에 서로 다른 제품(P-100, P-300)이 섞여도 정확히 합산.
    result = calculate_standard_budget_by_contract(
        [_budget_contract("CONTRACT-A")],
        [
            _budget_wo("WO-1", "CONTRACT-A", "P-100", "10"),
            _budget_wo("WO-2", "CONTRACT-A", "P-300", "4"),
        ],
        [
            _standard_cost("P-100", cost_element_code="DM", standard_amount="100"),
            _standard_cost("P-300", cost_element_code="DM", standard_amount="200"),
        ],
        [_product("P-100"), _product("P-300")],
    )
    c = result["CONTRACT-A"]
    # WO-1: DM=100x10=1000.00, WO-2: DM=200x4=800.00 -> 합계 1800.00
    assert c["budget_material_cost"] == Decimal("1800.00")
    assert c["work_order_count"] == 2
    assert set(c["work_orders"]) == {"WO-1", "WO-2"}

def test_standard_budget_by_contract_excludes_wo_without_contract_no():
    result = calculate_standard_budget_by_contract(
        [_budget_contract("CONTRACT-A")],
        [_budget_wo("WO-1", None, "P-100", "10")],
        [_standard_cost("P-100", cost_element_code="DM", standard_amount="100")],
        [_product("P-100")],
    )
    # contract_no가 없는 WO는 어떤 계약 결과에도 나타나지 않는다.
    c = result["CONTRACT-A"]
    assert c["work_order_count"] == 0
    assert c["work_orders"] == []
    assert c["budget_material_cost"] == Decimal("0")

def test_standard_budget_by_contract_no_standard_cost_marked_unpriced_not_zero():
    # P-900처럼 standard_cost가 전혀 없는 제품 -> 0으로 채우지 않고 명시적으로
    # unpriced_work_orders에 남긴다.
    result = calculate_standard_budget_by_contract(
        [_budget_contract("CONTRACT-A")],
        [_budget_wo("WO-1", "CONTRACT-A", "P-900", "10")],
        [],
        [_product("P-900")],
    )
    c = result["CONTRACT-A"]
    assert c["work_order_count"] == 0
    assert c["unpriced_work_orders"] == ["WO-1"]
    assert c["budget_material_cost"] == Decimal("0")

def test_standard_budget_by_contract_partial_standard_cost_only_includes_present_elements():
    # DM만 표준이 있는 경우 DL/OH는 work_order_budgets에 키 자체가 없어야 한다.
    result = calculate_standard_budget_by_contract(
        [_budget_contract("CONTRACT-A")],
        [_budget_wo("WO-1", "CONTRACT-A", "P-100", "10")],
        [_standard_cost("P-100", cost_element_code="DM", standard_amount="100")],
        [_product("P-100")],
    )
    c = result["CONTRACT-A"]
    wo_budget = c["work_order_budgets"]["WO-1"]
    assert wo_budget["budget_material_cost"] == Decimal("1000.00")
    assert "budget_labor_cost" not in wo_budget
    assert "budget_overhead_cost" not in wo_budget
    assert c["budget_material_cost"] == Decimal("1000.00")
    assert c["budget_labor_cost"] == Decimal("0")

def test_standard_budget_by_contract_period_key_must_match_wo_period():
    # standard_cost가 다른 period_key로만 존재하면(하드코딩 매칭이 아니라 실제
    # WO의 period_key와 일치해야 함) 계산 불가로 처리한다.
    result = calculate_standard_budget_by_contract(
        [_budget_contract("CONTRACT-A")],
        [_budget_wo("WO-1", "CONTRACT-A", "P-100", "10", period_key="2026-07")],
        [_standard_cost("P-100", period_key="2026-08", cost_element_code="DM", standard_amount="100")],
        [_product("P-100")],
    )
    c = result["CONTRACT-A"]
    assert c["unpriced_work_orders"] == ["WO-1"]

def test_standard_budget_by_contract_zero_or_missing_planned_qty_marked_unpriced():
    result = calculate_standard_budget_by_contract(
        [_budget_contract("CONTRACT-A")],
        [_budget_wo("WO-1", "CONTRACT-A", "P-100", "0")],
        [_standard_cost("P-100", cost_element_code="DM", standard_amount="100")],
        [_product("P-100")],
    )
    c = result["CONTRACT-A"]
    assert c["work_order_count"] == 0
    assert c["unpriced_work_orders"] == ["WO-1"]

def test_standard_budget_by_contract_open_wo_with_planned_qty_is_calculated():
    # OPEN 상태(기간걸침 포함)인 WO도 planned_qty만 있으면 Budget 계산이 되어야 한다
    # (Total Variance/Actual Cost와 달리 wo_status나 실적 유무와 무관).
    result = calculate_standard_budget_by_contract(
        [_budget_contract("CONTRACT-A")],
        [_budget_wo("WO-1", "CONTRACT-A", "P-100", "10", wo_status="OPEN")],
        [_standard_cost("P-100", cost_element_code="DM", standard_amount="100")],
        [_product("P-100")],
    )
    c = result["CONTRACT-A"]
    assert c["work_order_count"] == 1
    assert c["budget_material_cost"] == Decimal("1000.00")

def test_standard_budget_by_contract_independent_of_good_qty_or_production_output():
    # 함수 시그니처 자체가 production_output/good_qty를 전혀 받지 않는다 —
    # good_qty=0이나 산출 실적 없음과 무관하게 planned_qty만으로 계산됨을 증명한다.
    result = calculate_standard_budget_by_contract(
        [_budget_contract("CONTRACT-A")],
        [_budget_wo("WO-1", "CONTRACT-A", "P-100", "10")],
        [_standard_cost("P-100", cost_element_code="DM", standard_amount="100")],
        [_product("P-100")],
    )
    assert result["CONTRACT-A"]["budget_material_cost"] == Decimal("1000.00")

def test_standard_budget_by_contract_decimal_precision():
    result = calculate_standard_budget_by_contract(
        [_budget_contract("CONTRACT-A")],
        [_budget_wo("WO-1", "CONTRACT-A", "P-100", "3")],
        [_standard_cost("P-100", cost_element_code="DM", standard_amount="33.335")],
        [_product("P-100")],
    )
    # 33.335 x 3 = 100.005 -> ROUND_HALF_UP -> 100.01
    assert result["CONTRACT-A"]["budget_material_cost"] == Decimal("100.01")

def test_standard_budget_by_contract_seeds_contract_with_no_linked_wo():
    # contracts에 등록됐지만 연결된 WO가 하나도 없는 계약도 0/빈 값으로 나타난다
    # (조용히 사라지지 않는다).
    result = calculate_standard_budget_by_contract(
        [_budget_contract("CONTRACT-EMPTY")],
        [],
        [],
        [],
    )
    c = result["CONTRACT-EMPTY"]
    assert c["work_order_count"] == 0
    assert c["work_orders"] == []
    assert c["budget_manufacturing_cost"] == Decimal("0")

def test_standard_budget_by_contract_excludes_wo_with_unregistered_product():
    # product_code가 product master에 없는 WO는(기존 Actual Cost 계열과 동일하게)
    # 제외된다.
    result = calculate_standard_budget_by_contract(
        [_budget_contract("CONTRACT-A")],
        [_budget_wo("WO-1", "CONTRACT-A", "P-999", "10")],
        [],
        [_product("P-100")],
    )
    c = result["CONTRACT-A"]
    assert c["work_order_count"] == 0
    assert c["unpriced_work_orders"] == []
    assert c["work_orders"] == []


# --- 실제 Phase 1 데이터 기준 Contract Budget 검증 ---

def _load_real_contract_budget():
    import sys
    from pathlib import Path
    sys.path.insert(0, "src")
    from manufacturing_cost_engine.loader import load_dataset

    dataset = Path("hanbit_mvp_dataset_phase1")
    if not dataset.exists():
        return None

    data = load_dataset(dataset)

    def rows(file, sheet):
        return data.get(f"{file}::{sheet}", [])

    return calculate_standard_budget_by_contract(
        rows("30_contract.xlsx", "contract"),
        rows("20_work_order.xlsx", "work_order"),
        rows("12_standard_cost.xlsx", "standard_cost"),
        rows("07_product_master.xlsx", "product"),
    )

def test_real_dataset_budget_contract_001():
    result = _load_real_contract_budget()
    if result is None:
        return
    c = result["CONTRACT-001"]
    assert c["work_order_count"] == 3
    assert c["budget_material_cost"] == Decimal("908440.00")
    assert c["budget_labor_cost"] == Decimal("1407840.00")
    assert c["budget_overhead_cost"] == Decimal("1055880.00")
    assert c["budget_manufacturing_cost"] == Decimal("3372160.00")

def test_real_dataset_budget_contract_002():
    result = _load_real_contract_budget()
    if result is None:
        return
    c = result["CONTRACT-002"]
    assert c["work_order_count"] == 4
    assert c["budget_material_cost"] == Decimal("1108992.00")
    assert c["budget_labor_cost"] == Decimal("1359360.00")
    assert c["budget_overhead_cost"] == Decimal("1019520.00")
    assert c["budget_manufacturing_cost"] == Decimal("3487872.00")

def test_real_dataset_budget_contract_003_open_wo_still_budgeted():
    # WO-2607-018/019은 OPEN 상태로 실적이 없지만 planned_qty가 있으므로
    # Budget은 정상 계산되어야 한다(Actual Cost=0인 것과는 별개).
    result = _load_real_contract_budget()
    if result is None:
        return
    c = result["CONTRACT-003"]
    assert c["work_order_count"] == 2
    assert c["budget_material_cost"] == Decimal("485682.00")
    assert c["budget_labor_cost"] == Decimal("634560.00")
    assert c["budget_overhead_cost"] == Decimal("475920.00")
    assert c["budget_manufacturing_cost"] == Decimal("1596162.00")


# --- calculate_contract_variance (Phase 2 3단계) ---

def _variance_contract(contract_no):
    return {"contract_no": contract_no}

def _actual_entry(material="0", labor="0", overhead="0", total="0", work_orders=None):
    return {
        "actual_material_cost": Decimal(material), "actual_labor_cost": Decimal(labor),
        "actual_overhead_cost": Decimal(overhead), "actual_manufacturing_cost": Decimal(total),
        "work_orders": work_orders or [],
    }

def _budget_entry(material="0", labor="0", overhead="0", total="0", work_orders=None,
                   unpriced=None):
    return {
        "budget_material_cost": Decimal(material), "budget_labor_cost": Decimal(labor),
        "budget_overhead_cost": Decimal(overhead), "budget_manufacturing_cost": Decimal(total),
        "work_orders": work_orders or [], "unpriced_work_orders": unpriced or [],
    }

def test_contract_variance_computes_actual_minus_budget_per_element():
    result = calculate_contract_variance(
        [_variance_contract("CONTRACT-A")],
        {"CONTRACT-A": _actual_entry("100.00", "50", "10.00", "160.00", ["WO-1"])},
        {"CONTRACT-A": _budget_entry("80.00", "60", "15.00", "155.00", ["WO-1"])},
    )
    c = result["CONTRACT-A"]
    assert c["dm_variance"] == Decimal("20.00")
    assert c["dl_variance"] == Decimal("-10.00")
    assert c["oh_variance"] == Decimal("-5.00")
    assert c["total_variance"] == Decimal("5.00")
    assert c["actual_manufacturing_cost"] == Decimal("160.00")
    assert c["budget_manufacturing_cost"] == Decimal("155.00")
    assert c["unpriced_work_orders"] == []
    assert c["mismatched_work_orders"] == []
    assert c["budget_coverage_complete"] is True

def test_contract_variance_includes_all_contracts_from_master():
    # 4번 정책: contracts 마스터의 모든 계약이 결과에 포함된다(WO가 없어도).
    result = calculate_contract_variance(
        [_variance_contract("CONTRACT-A"), _variance_contract("CONTRACT-EMPTY")],
        {"CONTRACT-A": _actual_entry("100.00", "50", "10.00", "160.00", ["WO-1"])},
        {"CONTRACT-A": _budget_entry("100.00", "50", "10.00", "160.00", ["WO-1"])},
    )
    assert set(result.keys()) == {"CONTRACT-A", "CONTRACT-EMPTY"}
    empty = result["CONTRACT-EMPTY"]
    assert empty["total_variance"] == Decimal("0")
    assert empty["budget_coverage_complete"] is True

def test_contract_variance_missing_from_budget_treated_as_zero_budget():
    # 5번 정책: Budget 쪽에 계약이 없으면 0으로 취급한다.
    result = calculate_contract_variance(
        [_variance_contract("CONTRACT-A")],
        {"CONTRACT-A": _actual_entry("100.00", "50", "10.00", "160.00", ["WO-1"])},
        {},
    )
    c = result["CONTRACT-A"]
    assert c["total_variance"] == Decimal("160.00")
    # budget 쪽 work_orders가 비어 있으니 WO-1은 mismatched로 표시된다.
    assert c["mismatched_work_orders"] == ["WO-1"]
    assert c["budget_coverage_complete"] is False

def test_contract_variance_missing_from_actual_treated_as_zero_actual():
    # 5번 정책: Actual 쪽에 계약이 없으면 0으로 취급한다.
    result = calculate_contract_variance(
        [_variance_contract("CONTRACT-A")],
        {},
        {"CONTRACT-A": _budget_entry("100.00", "50", "10.00", "160.00", ["WO-1"])},
    )
    c = result["CONTRACT-A"]
    assert c["total_variance"] == Decimal("-160.00")
    assert c["mismatched_work_orders"] == ["WO-1"]
    assert c["budget_coverage_complete"] is False

def test_contract_variance_unpriced_work_orders_passthrough_and_coverage_flag():
    # 7번 정책: unpriced_work_orders가 그대로 전달되고 budget_coverage_complete=False.
    result = calculate_contract_variance(
        [_variance_contract("CONTRACT-A")],
        {"CONTRACT-A": _actual_entry("100.00", "0", "0", "100.00", ["WO-1", "WO-2"])},
        {"CONTRACT-A": _budget_entry("80.00", "0", "0", "80.00", ["WO-1"], unpriced=["WO-2"])},
    )
    c = result["CONTRACT-A"]
    assert c["unpriced_work_orders"] == ["WO-2"]
    # WO-2는 actual/budget(unpriced 포함) 양쪽에 다 있으므로 mismatched는 아니다.
    assert c["mismatched_work_orders"] == []
    assert c["budget_coverage_complete"] is False
    assert c["total_variance"] == Decimal("20.00")

def test_contract_variance_flags_wo_present_in_actual_but_absent_from_budget_entirely():
    # 6번 정책: Actual/Budget의 WO 집합이 불일치하면(unpriced에도 없는 경우)
    # mismatched_work_orders로 표시한다 — 미등록 product WO 비대칭 케이스를 흉내낸다.
    result = calculate_contract_variance(
        [_variance_contract("CONTRACT-A")],
        {"CONTRACT-A": _actual_entry("100.00", "0", "0", "100.00", ["WO-1", "WO-999"])},
        {"CONTRACT-A": _budget_entry("100.00", "0", "0", "100.00", ["WO-1"])},
    )
    c = result["CONTRACT-A"]
    assert c["mismatched_work_orders"] == ["WO-999"]
    assert c["budget_coverage_complete"] is False

def test_contract_variance_decimal_precision():
    result = calculate_contract_variance(
        [_variance_contract("CONTRACT-A")],
        {"CONTRACT-A": _actual_entry("100.015", "0", "0", "100.015", ["WO-1"])},
        {"CONTRACT-A": _budget_entry("100.005", "0", "0", "100.005", ["WO-1"])},
    )
    # 100.015 - 100.005 = 0.01 정확히, ROUND_HALF_UP 경계 확인은 별도 값으로.
    c = result["CONTRACT-A"]
    assert c["dm_variance"] == Decimal("0.01")


# --- 실제 Phase 1 데이터 기준 Contract Variance 검증 ---

def _load_real_contract_variance():
    import sys
    from pathlib import Path
    sys.path.insert(0, "src")
    from manufacturing_cost_engine.loader import load_dataset

    dataset = Path("hanbit_mvp_dataset_phase1")
    if not dataset.exists():
        return None

    data = load_dataset(dataset)

    def rows(file, sheet):
        return data.get(f"{file}::{sheet}", [])

    work_orders = rows("20_work_order.xlsx", "work_order")
    products = rows("07_product_master.xlsx", "product")
    contracts = rows("30_contract.xlsx", "contract")

    actual_by_wo = calculate_actual_total_cost_by_wo(
        work_orders,
        rows("22_material_issue.xlsx", "material_issue"),
        rows("23_labor_transaction.xlsx", "labor_transaction"),
        rows("08_material_master.xlsx", "material"),
        rows("09_work_center.xlsx", "work_center"),
        rows("13_overhead_rate.xlsx", "overhead_rate"),
        products,
    )
    actual_by_contract = calculate_actual_total_cost_by_contract(work_orders, actual_by_wo)
    budget_by_contract = calculate_standard_budget_by_contract(
        contracts, work_orders, rows("12_standard_cost.xlsx", "standard_cost"), products,
    )
    return calculate_contract_variance(contracts, actual_by_contract, budget_by_contract)

def test_real_dataset_contract_variance_001():
    result = _load_real_contract_variance()
    if result is None:
        return
    c = result["CONTRACT-001"]
    assert c["dm_variance"] == Decimal("-204219.12")
    assert c["dl_variance"] == Decimal("-771840.00")
    assert c["oh_variance"] == Decimal("-578880.00")
    assert c["total_variance"] == Decimal("-1554939.12")
    assert c["budget_coverage_complete"] is True

def test_real_dataset_contract_variance_002():
    result = _load_real_contract_variance()
    if result is None:
        return
    c = result["CONTRACT-002"]
    assert c["dm_variance"] == Decimal("-19380.00")
    assert c["dl_variance"] == Decimal("-1263360.00")
    assert c["oh_variance"] == Decimal("-947520.00")
    assert c["total_variance"] == Decimal("-2230260.00")
    assert c["budget_coverage_complete"] is True

def test_real_dataset_contract_variance_003():
    result = _load_real_contract_variance()
    if result is None:
        return
    c = result["CONTRACT-003"]
    assert c["dm_variance"] == Decimal("-485682.00")
    assert c["dl_variance"] == Decimal("-634560.00")
    assert c["oh_variance"] == Decimal("-475920.00")
    assert c["total_variance"] == Decimal("-1596162.00")
    assert c["budget_coverage_complete"] is True


# --- calculate_actual_direct_expense_by_contract (Phase 2 4단계) ---

def _de_contract(contract_no):
    return {"contract_no": contract_no}

def _de_work_order(wo_no, contract_no):
    return {"wo_no": wo_no, "contract_no": contract_no}

def _de_row(expense_id="DE-1", contract_no=None, wo_no=None, amount="1000"):
    return {
        "expense_id": expense_id, "contract_no": contract_no,
        "wo_no": wo_no, "amount": amount,
    }

def test_direct_expense_by_contract_wo_attributed_rolls_up_through_work_order():
    result = calculate_actual_direct_expense_by_contract(
        [_de_contract("CONTRACT-A")],
        [_de_work_order("WO-1", "CONTRACT-A")],
        [_de_row("DE-1", wo_no="WO-1", amount="500000")],
    )
    c = result["CONTRACT-A"]
    assert c["direct_expense_amount"] == Decimal("500000.00")
    assert c["expense_count"] == 1
    assert c["expense_ids"] == ["DE-1"]

def test_direct_expense_by_contract_contract_attributed_directly():
    result = calculate_actual_direct_expense_by_contract(
        [_de_contract("CONTRACT-A")],
        [],
        [_de_row("DE-1", contract_no="CONTRACT-A", amount="1200000")],
    )
    assert result["CONTRACT-A"]["direct_expense_amount"] == Decimal("1200000.00")

def test_direct_expense_by_contract_mixes_wo_and_contract_attributed_rows():
    result = calculate_actual_direct_expense_by_contract(
        [_de_contract("CONTRACT-A")],
        [_de_work_order("WO-1", "CONTRACT-A")],
        [
            _de_row("DE-1", wo_no="WO-1", amount="500000"),
            _de_row("DE-2", contract_no="CONTRACT-A", amount="300000"),
        ],
    )
    c = result["CONTRACT-A"]
    assert c["direct_expense_amount"] == Decimal("800000.00")
    assert c["expense_count"] == 2

def test_direct_expense_by_contract_excludes_dual_attributed_row():
    # wo_no와 contract_no가 동시에 있는 행은 어느 쪽으로도 집계하지 않는다
    # (validate_direct_expense가 EXPENSE_TARGET_CONFLICT로 별도 보고).
    result = calculate_actual_direct_expense_by_contract(
        [_de_contract("CONTRACT-A")],
        [_de_work_order("WO-1", "CONTRACT-A")],
        [_de_row("DE-1", contract_no="CONTRACT-A", wo_no="WO-1", amount="500000")],
    )
    c = result["CONTRACT-A"]
    assert c["direct_expense_amount"] == Decimal("0.00")
    assert c["expense_count"] == 0

def test_direct_expense_by_contract_excludes_row_with_no_target():
    result = calculate_actual_direct_expense_by_contract(
        [_de_contract("CONTRACT-A")],
        [],
        [_de_row("DE-1", amount="500000")],
    )
    assert result["CONTRACT-A"]["expense_count"] == 0

def test_direct_expense_by_contract_excludes_expense_on_unassigned_wo():
    # 계약이 배정되지 않은 WO의 경비는 어떤 계약에도 귀속되지 않는다(오류 아님).
    result = calculate_actual_direct_expense_by_contract(
        [_de_contract("CONTRACT-A")],
        [_de_work_order("WO-9", None)],
        [_de_row("DE-1", wo_no="WO-9", amount="200000")],
    )
    assert result["CONTRACT-A"]["direct_expense_amount"] == Decimal("0.00")

def test_direct_expense_by_contract_excludes_unknown_contract_reference():
    result = calculate_actual_direct_expense_by_contract(
        [_de_contract("CONTRACT-A")],
        [],
        [_de_row("DE-1", contract_no="CONTRACT-999", amount="500000")],
    )
    assert set(result.keys()) == {"CONTRACT-A"}
    assert result["CONTRACT-A"]["expense_count"] == 0

def test_direct_expense_by_contract_negative_amount_nets_down():
    result = calculate_actual_direct_expense_by_contract(
        [_de_contract("CONTRACT-A")],
        [_de_work_order("WO-1", "CONTRACT-A")],
        [
            _de_row("DE-1", wo_no="WO-1", amount="500000"),
            _de_row("DE-2", wo_no="WO-1", amount="-50000"),
        ],
    )
    c = result["CONTRACT-A"]
    assert c["direct_expense_amount"] == Decimal("450000.00")
    assert c["expense_count"] == 2

def test_direct_expense_by_contract_zero_amount_counted_but_adds_nothing():
    result = calculate_actual_direct_expense_by_contract(
        [_de_contract("CONTRACT-A")],
        [],
        [_de_row("DE-1", contract_no="CONTRACT-A", amount="0")],
    )
    c = result["CONTRACT-A"]
    assert c["direct_expense_amount"] == Decimal("0.00")
    assert c["expense_count"] == 1

def test_direct_expense_by_contract_seeds_contract_with_no_expenses():
    result = calculate_actual_direct_expense_by_contract(
        [_de_contract("CONTRACT-A"), _de_contract("CONTRACT-EMPTY")],
        [],
        [_de_row("DE-1", contract_no="CONTRACT-A", amount="1000")],
    )
    assert set(result.keys()) == {"CONTRACT-A", "CONTRACT-EMPTY"}
    assert result["CONTRACT-EMPTY"]["direct_expense_amount"] == Decimal("0.00")
    assert result["CONTRACT-EMPTY"]["expense_ids"] == []

def test_direct_expense_by_contract_excludes_unparseable_amount():
    result = calculate_actual_direct_expense_by_contract(
        [_de_contract("CONTRACT-A")],
        [],
        [_de_row("DE-1", contract_no="CONTRACT-A", amount="1,2 3 4")],
    )
    assert result["CONTRACT-A"]["expense_count"] == 0

def test_direct_expense_by_contract_decimal_precision():
    result = calculate_actual_direct_expense_by_contract(
        [_de_contract("CONTRACT-A")],
        [],
        [
            _de_row("DE-1", contract_no="CONTRACT-A", amount="100.005"),
            _de_row("DE-2", contract_no="CONTRACT-A", amount="0.005"),
        ],
    )
    # 100.005 + 0.005 = 100.010 -> ROUND_HALF_UP -> 100.01
    assert result["CONTRACT-A"]["direct_expense_amount"] == Decimal("100.01")


# --- 실제 Phase 2 데이터 기준 Direct Expense 검증 ---

def _load_real_direct_expense():
    import sys
    from pathlib import Path
    sys.path.insert(0, "src")
    from manufacturing_cost_engine.loader import load_dataset

    dataset = Path("hanbit_mvp_dataset_phase1")
    if not dataset.exists():
        return None

    data = load_dataset(dataset)

    def rows(file, sheet):
        return data.get(f"{file}::{sheet}", [])

    return calculate_actual_direct_expense_by_contract(
        rows("30_contract.xlsx", "contract"),
        rows("20_work_order.xlsx", "work_order"),
        rows("31_direct_expense.xlsx", "direct_expense"),
    )

def test_real_dataset_direct_expense_contract_001_rolls_up_via_work_orders():
    # DE-2607-001(500,000, WO-2607-001) + DE-2607-003(300,000, WO-2607-003)
    # + DE-2607-004(-50,000 환입, WO-2607-001) = 750,000
    result = _load_real_direct_expense()
    if result is None:
        return
    c = result["CONTRACT-001"]
    assert c["direct_expense_amount"] == Decimal("750000.00")
    assert c["expense_count"] == 3

def test_real_dataset_direct_expense_contract_002_direct_attribution():
    result = _load_real_direct_expense()
    if result is None:
        return
    c = result["CONTRACT-002"]
    assert c["direct_expense_amount"] == Decimal("1200000.00")
    assert c["expense_count"] == 1

def test_real_dataset_direct_expense_contract_003_zero_amount_row():
    result = _load_real_direct_expense()
    if result is None:
        return
    c = result["CONTRACT-003"]
    assert c["direct_expense_amount"] == Decimal("0.00")
    assert c["expense_count"] == 1

def test_real_dataset_direct_expense_excludes_unassigned_wo_expense():
    # DE-2607-005는 WO-2607-006(계약 미배정) 소속이라 어떤 계약에도 잡히지 않는다.
    result = _load_real_direct_expense()
    if result is None:
        return
    all_ids = {eid for c in result.values() for eid in c["expense_ids"]}
    assert "DE-2607-005" not in all_ids
    assert set(result.keys()) == {"CONTRACT-001", "CONTRACT-002", "CONTRACT-003"}
