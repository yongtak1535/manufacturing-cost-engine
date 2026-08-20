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
    calculate_ga_by_contract,
    calculate_contract_total_cost,
    calculate_budget_direct_expense_by_contract,
    calculate_ga_base_amount,
    resolve_ga_actual_rate,
    resolve_ga_ceiling_rate,
    calculate_regulatory_ga_by_contract,
    calculate_government_furnished_material_by_contract,
    calculate_actual_material_cost_excluding_gfm_by_contract,
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
           unit_cost="100", issue_type="ISSUE", supply_type=None):
    return {
        "wo_no": wo_no, "material_code": material_code, "issued_qty": issued_qty,
        "unit_cost": unit_cost, "issue_type": issue_type, "supply_type": supply_type,
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


# --- GFM/DM 정합성 검증 (Phase 2 9단계 후속) ---
#
# 목표: material_issue.supply_type으로 관급재료비(GFM)/사급재료비를 나눴을 때
# 기존 calculate_actual_material_cost()(보호 함수, 이 구획에서도 절대
# 수정하지 않는다)와의 관계를 명확히 한다. 아래 supply_type 값은 전부
# 합성 테스트 픽스처이며 실제 방산원가 데이터가 아니다.

def test_actual_material_cost_ignores_supply_type_includes_everything():
    # 현재 DM 집계는 supply_type을 전혀 참조하지 않는다 — GOVERNMENT/COMPANY
    # 태그와 무관하게 issued_qty x unit_cost를 모두 더한다. 즉 이 함수의
    # 결과는 "사급재료비만"이 아니라 "관급+사급을 합친 총 재료비"다.
    result = calculate_actual_material_cost(
        [_wo()],
        [
            _issue(issued_qty="10", unit_cost="100", supply_type="GOVERNMENT"),
            _issue(issued_qty="5", unit_cost="200", supply_type="COMPANY"),
        ],
        [_material()],
        [_product()],
    )
    government_only = Decimal("1000.00")  # 10 x 100
    company_only = Decimal("1000.00")     # 5 x 200

    assert result == {"WO-1": Decimal("2000.00")}
    assert result["WO-1"] == government_only + company_only
    # 핵심 확인: 기존 함수의 결과는 "사급재료비만"의 값과 다르다.
    assert result["WO-1"] != company_only

def test_gfm_function_isolates_government_amount_from_same_synthetic_split():
    # 위 테스트와 동일한 관급/사급 구성을 신규 GFM 함수에 넣으면 관급분만
    # 정확히 분리된다.
    result = calculate_government_furnished_material_by_contract(
        [{"contract_no": "CONTRACT-A"}],
        [{"wo_no": "WO-1", "contract_no": "CONTRACT-A"}],
        [
            _issue(issued_qty="10", unit_cost="100", supply_type="GOVERNMENT"),
            _issue(issued_qty="5", unit_cost="200", supply_type="COMPANY"),
        ],
    )
    entry = result["CONTRACT-A"]
    assert entry["calculable"] is True
    assert entry["gfm_amount"] == Decimal("1000.00")

def test_dm_component_already_contains_gfm_naive_addition_would_double_count():
    # calculate_actual_total_cost_by_contract()의 actual_material_cost는
    # calculate_actual_material_cost()를 그대로 재사용하므로, GOVERNMENT
    # 태그 재료비까지 이미 포함하고 있다. 따라서 이 값에
    # calculate_government_furnished_material_by_contract()의 gfm_amount를
    # 그대로 더하면 GOVERNMENT 금액이 두 번 계산된다 — 현재 어떤 함수도
    # 이렇게 더하도록 연결되어 있지는 않지만(코드 결합 없음, 별도 확인),
    # 향후 "제조원가(관급재료비 포함)" 공식을 구현할 때 이 함정을 피해야
    # 한다는 것을 명시적으로 확인해 둔다.
    work_orders = [
        {"wo_no": "WO-1", "product_code": "P-100", "period_key": "2026-07",
         "contract_no": "CONTRACT-A"},
    ]
    material_issues = [
        _issue(wo_no="WO-1", issued_qty="10", unit_cost="100", supply_type="GOVERNMENT"),
    ]

    actual_by_wo = calculate_actual_total_cost_by_wo(
        work_orders, material_issues, [], [_material()], [], [], [_product()],
    )
    actual_by_contract = calculate_actual_total_cost_by_contract(work_orders, actual_by_wo)
    dm_component = actual_by_contract["CONTRACT-A"]["actual_material_cost"]

    gfm_by_contract = calculate_government_furnished_material_by_contract(
        [{"contract_no": "CONTRACT-A"}], work_orders, material_issues,
    )
    gfm_amount = gfm_by_contract["CONTRACT-A"]["gfm_amount"]

    assert dm_component == Decimal("1000.00")
    assert gfm_amount == Decimal("1000.00")
    # dm_component + gfm_amount는 실제 재료비(1,000.00)의 두 배이며,
    # 이는 잘못된 계산이라는 것을 확인하기 위한 대조값이다.
    assert dm_component + gfm_amount == Decimal("2000.00")
    assert dm_component + gfm_amount != Decimal("1000.00")

def test_none_supply_type_included_in_existing_dm_but_blocks_gfm_calculation():
    # 미분류(supply_type=None) 행은 기존 DM 함수에는 그대로 포함되지만
    # (supply_type을 보지 않으므로), 신규 GFM 함수에서는 "계산 불가"로
    # 처리된다 — 두 함수가 미분류 행을 서로 다르게(그러나 각자 의도된 대로)
    # 다룬다는 것을 명확히 대조한다.
    work_orders = [
        {"wo_no": "WO-1", "product_code": "P-100", "period_key": "2026-07",
         "contract_no": "CONTRACT-A"},
    ]
    material_issues = [
        _issue(wo_no="WO-1", issued_qty="10", unit_cost="100", supply_type=None),
    ]

    dm = calculate_actual_material_cost(
        work_orders, material_issues, [_material()], [_product()],
    )
    assert dm == {"WO-1": Decimal("1000.00")}

    gfm = calculate_government_furnished_material_by_contract(
        [{"contract_no": "CONTRACT-A"}], work_orders, material_issues,
    )
    assert gfm["CONTRACT-A"]["calculable"] is False
    assert gfm["CONTRACT-A"]["gfm_amount"] is None
    # supply_type=None이 0이나 "COMPANY"로 암묵 처리되지 않았음을 재확인:
    # 만약 COMPANY로 간주됐다면 calculable=True, gfm_amount=0이 되었을 것이다.
    assert not (gfm["CONTRACT-A"]["calculable"] is True
                and gfm["CONTRACT-A"]["gfm_amount"] == Decimal("0"))

def test_real_dataset_actual_material_cost_unaffected_by_blank_supply_type_column():
    # supply_type 컬럼이 22_material_issue.xlsx에 추가되었지만 전부 None이므로,
    # 기존 calculate_actual_material_cost() 결과는 이전과 동일해야 한다 —
    # 이 함수는 supply_type을 아예 보지 않기 때문이다(회귀 없음의 직접 증거).
    import sys
    from pathlib import Path
    sys.path.insert(0, "src")
    from manufacturing_cost_engine.loader import load_dataset

    dataset = Path("hanbit_mvp_dataset_phase1")
    if not dataset.exists():
        return

    data = load_dataset(dataset)
    work_orders = data["20_work_order.xlsx::work_order"]
    material_issues = data["22_material_issue.xlsx::material_issue"]
    materials = data["08_material_master.xlsx::material"]
    products = data["07_product_master.xlsx::product"]

    assert all(r.get("supply_type") is None for r in material_issues)

    result = calculate_actual_material_cost(work_orders, material_issues, materials, products)
    # 기존(이전 라운드에서부터 계속 유지된) 실제 DM 실적 — CLI 출력과
    # 대사되는 CONTRACT-001의 work order 중 하나인 WO-2607-004의 DM 실적.
    # supply_type 컬럼 추가 여부와 무관하게 이 값은 변하지 않아야 한다.
    assert "WO-2607-004" in result
    assert result["WO-2607-004"] is not None


# --- calculate_actual_material_cost_excluding_gfm_by_contract ---
#
# calculate_actual_material_cost()(보호 함수, 수정하지 않음)와 나란히 존재
# 하는 "관급재료비 제외" 계약 단위 재료비 집계. 아래 supply_type 값은 전부
# 합성 테스트 픽스처이며 실제 방산원가 데이터가 아니다.

def _dm_excl_wo(wo_no="WO-1", contract_no="CONTRACT-A"):
    return {"wo_no": wo_no, "contract_no": contract_no}

def test_dm_excl_gfm_company_only():
    result = calculate_actual_material_cost_excluding_gfm_by_contract(
        [{"contract_no": "CONTRACT-A"}],
        [_dm_excl_wo("WO-1", "CONTRACT-A")],
        [_issue("WO-1", issued_qty="10", unit_cost="100", supply_type="COMPANY")],
    )
    entry = result["CONTRACT-A"]
    assert entry["calculable"] is True
    assert entry["dm_excluding_gfm"] == Decimal("1000.00")
    assert entry["company_issue_count"] == 1

def test_dm_excl_gfm_government_only_is_excluded_leaving_zero():
    result = calculate_actual_material_cost_excluding_gfm_by_contract(
        [{"contract_no": "CONTRACT-A"}],
        [_dm_excl_wo("WO-1", "CONTRACT-A")],
        [_issue("WO-1", issued_qty="10", unit_cost="100", supply_type="GOVERNMENT")],
    )
    entry = result["CONTRACT-A"]
    assert entry["calculable"] is True
    assert entry["dm_excluding_gfm"] == Decimal("0")
    assert entry["company_issue_count"] == 0

def test_dm_excl_gfm_mixed_company_and_government():
    result = calculate_actual_material_cost_excluding_gfm_by_contract(
        [{"contract_no": "CONTRACT-A"}],
        [_dm_excl_wo("WO-1", "CONTRACT-A")],
        [
            _issue("WO-1", issued_qty="10", unit_cost="100", supply_type="GOVERNMENT"),
            _issue("WO-1", issued_qty="5", unit_cost="200", supply_type="COMPANY"),
        ],
    )
    entry = result["CONTRACT-A"]
    assert entry["calculable"] is True
    assert entry["dm_excluding_gfm"] == Decimal("1000.00")  # COMPANY(5x200)만

def test_dm_excl_gfm_untagged_row_makes_contract_not_calculable():
    result = calculate_actual_material_cost_excluding_gfm_by_contract(
        [{"contract_no": "CONTRACT-A"}],
        [_dm_excl_wo("WO-1", "CONTRACT-A")],
        [_issue("WO-1", issued_qty="10", unit_cost="100", supply_type=None)],
    )
    entry = result["CONTRACT-A"]
    assert entry["calculable"] is False
    assert entry["dm_excluding_gfm"] is None
    assert entry["untagged_issue_count"] == 1

def test_dm_excl_gfm_zero_amount_is_valid_not_a_calculation_failure():
    # COMPANY로 명확히 분류됐지만 금액이 0인 경우(예: 환입으로 정확히
    # 상쇄)는 계산 불가가 아니라 정상적으로 계산된 0이다.
    result = calculate_actual_material_cost_excluding_gfm_by_contract(
        [{"contract_no": "CONTRACT-A"}],
        [_dm_excl_wo("WO-1", "CONTRACT-A")],
        [
            _issue("WO-1", issued_qty="10", unit_cost="100", issue_type="ISSUE",
                   supply_type="COMPANY"),
            _issue("WO-1", issued_qty="10", unit_cost="100", issue_type="RETURN",
                   supply_type="COMPANY"),
        ],
    )
    entry = result["CONTRACT-A"]
    assert entry["calculable"] is True
    assert entry["dm_excluding_gfm"] == Decimal("0.00")

def test_dm_excl_gfm_aggregates_per_contract_separately():
    result = calculate_actual_material_cost_excluding_gfm_by_contract(
        [{"contract_no": "CONTRACT-A"}, {"contract_no": "CONTRACT-B"}],
        [_dm_excl_wo("WO-1", "CONTRACT-A"), _dm_excl_wo("WO-2", "CONTRACT-B")],
        [
            _issue("WO-1", issued_qty="10", unit_cost="100", supply_type="COMPANY"),
            _issue("WO-2", issued_qty="3", unit_cost="50", supply_type="COMPANY"),
        ],
    )
    assert result["CONTRACT-A"]["dm_excluding_gfm"] == Decimal("1000.00")
    assert result["CONTRACT-B"]["dm_excluding_gfm"] == Decimal("150.00")

def test_dm_excl_gfm_plus_gfm_equals_total_material_cost_no_double_counting():
    # 모든 행이 분류되어 있을 때(미분류 없음), 신규 함수(사급만) + 기존 GFM
    # 함수(관급만)의 합은 그 계약에 귀속되는 material_issue 전체 순액과
    # 정확히 일치해야 한다 — 이중집계도, 누락도 없어야 한다.
    contracts = [{"contract_no": "CONTRACT-A"}]
    work_orders = [_dm_excl_wo("WO-1", "CONTRACT-A")]
    material_issues = [
        _issue("WO-1", issued_qty="10", unit_cost="100", issue_type="ISSUE",
               supply_type="GOVERNMENT"),
        _issue("WO-1", issued_qty="3", unit_cost="100", issue_type="RETURN",
               supply_type="GOVERNMENT"),
        _issue("WO-1", issued_qty="5", unit_cost="200", issue_type="ISSUE",
               supply_type="COMPANY"),
    ]

    dm_excl = calculate_actual_material_cost_excluding_gfm_by_contract(
        contracts, work_orders, material_issues,
    )["CONTRACT-A"]["dm_excluding_gfm"]
    gfm = calculate_government_furnished_material_by_contract(
        contracts, work_orders, material_issues,
    )["CONTRACT-A"]["gfm_amount"]

    # 전체 순액을 별도로 직접 계산(기존 calculate_actual_material_cost()를
    # 그대로 호출해 검증 기준으로 사용 — 보호 함수를 수정하지 않고 호출만 함).
    total_material_cost = calculate_actual_material_cost(
        [{"wo_no": "WO-1", "product_code": "P-100", "period_key": "2026-07"}],
        material_issues,
        [_material()],
        [_product()],
    )["WO-1"]

    assert dm_excl == Decimal("1000.00")  # COMPANY: 5 x 200
    assert gfm == Decimal("700.00")       # GOVERNMENT 순액: (10-3) x 100
    assert dm_excl + gfm == total_material_cost
    assert total_material_cost == Decimal("1700.00")  # 1000(COMPANY) + 700(GOV)

def test_dm_excl_gfm_seeds_all_contracts_from_master():
    result = calculate_actual_material_cost_excluding_gfm_by_contract(
        [{"contract_no": "CONTRACT-A"}, {"contract_no": "CONTRACT-EMPTY"}], [], [],
    )
    assert set(result.keys()) == {"CONTRACT-A", "CONTRACT-EMPTY"}
    for entry in result.values():
        assert entry["calculable"] is True
        assert entry["dm_excluding_gfm"] == Decimal("0")

def test_dm_excl_gfm_does_not_mutate_inputs():
    contracts = [{"contract_no": "CONTRACT-A"}]
    work_orders = [_dm_excl_wo("WO-1", "CONTRACT-A")]
    material_issues = [_issue("WO-1", supply_type="COMPANY")]

    import copy
    contracts_before = copy.deepcopy(contracts)
    work_orders_before = copy.deepcopy(work_orders)
    material_issues_before = copy.deepcopy(material_issues)

    calculate_actual_material_cost_excluding_gfm_by_contract(
        contracts, work_orders, material_issues,
    )

    assert contracts == contracts_before
    assert work_orders == work_orders_before
    assert material_issues == material_issues_before

def test_dm_excl_gfm_not_wired_into_regulatory_ga_by_contract():
    # calculate_regulatory_ga_by_contract()는 government_furnished_material_
    # by_contract와 dm_excluding_gfm_by_contract를 둘 다 "외부에서 이미 계산된
    # dict"로만 받는다 — 함수 내부에서
    # calculate_government_furnished_material_by_contract()나
    # calculate_actual_material_cost_excluding_gfm_by_contract()를 직접
    # 호출해 몰래 계산해주지 않는다는 것을 확인한다(호출자가 반드시 둘 다
    # 명시적으로 구해서 넘겨야 한다).
    result = calculate_regulatory_ga_by_contract(
        {"CONTRACT-A": {"actual_manufacturing_cost": Decimal("1000000.00")}},
        {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("2000000.00")}},
        {"CONTRACT-A": {"direct_expense_amount": Decimal("0")}},
        {"CONTRACT-A": {"calculable": True, "budget_direct_expense": Decimal("0")}},
        {},  # government_furnished_material_by_contract: 여전히 외부에서 받는 빈 dict
        [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026", rate_pct="8")],
        [_reg_contract("CONTRACT-A", plant_code="PL01", fiscal_year="2026")],
        "INCLUDE_GFM",
        _REF_DATE,
        _dm_excl_gfm("CONTRACT-A", "1000000.00"),
    )
    c = result["CONTRACT-A"]
    # INCLUDE_GFM인데 GFM dict에 이 계약 항목이 없으므로 여전히 계산 불가다 —
    # dm_excluding_gfm은 정상 제공됐지만 GFM 자체가 없어서 계산 불가가
    # 된다는 것을 확인한다(GFM과 DM 두 입력이 독립적으로 검사됨을 보임).
    assert c["calculable"] is False
    assert c["ga_base_amount_actual"] is None


# --- Budget 쪽 GFM 이중집계 여부 확인 ---
#
# calculate_standard_budget_by_contract()가 material_issue.supply_type과
# 무관한 완전히 다른 데이터(12_standard_cost.xlsx의 사전 산정 표준원가)를
# 쓰기 때문에, Actual 쪽과 동일한 "GFM이 이미 섞여 있다" 문제가 존재하지
# 않는다는 것을 코드/스키마로 확인한다. 근거가 없으므로 이 구획은 어떤
# 코드도 수정하지 않는다 — 확인만 한다.

def test_standard_budget_by_contract_does_not_reference_material_issue_or_supply_type():
    import inspect
    from manufacturing_cost_engine import cost_engine as ce

    source = inspect.getsource(ce.calculate_standard_budget_by_contract)
    assert "material_issue" not in source
    assert "supply_type" not in source

def test_standard_cost_schema_has_no_supply_type_or_gfm_concept():
    # 12_standard_cost.xlsx는 실제 자재불출 트랜잭션이 아니라 제품 1단위당
    # 사전 산정된 금액(standard_amount)만 가지고 있어, 관급/사급을 구분할
    # 데이터 자체가 없다 — Budget 쪽은 "이중집계"가 아니라 "구분 불가능한
    # 데이터 모델"이라는 다른 종류의 제약이다.
    import sys
    from pathlib import Path
    sys.path.insert(0, "src")
    from manufacturing_cost_engine.loader import load_dataset

    dataset = Path("hanbit_mvp_dataset_phase1")
    if not dataset.exists():
        return

    data = load_dataset(dataset)
    for sheet in ("standard_cost", "standard_cost_detail"):
        rows = data.get(f"12_standard_cost.xlsx::{sheet}", [])
        if not rows:
            continue
        assert "supply_type" not in rows[0]


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


# --- calculate_ga_by_contract (Phase 2 5단계) ---
#
# 32_cost_rate_rule.xlsx는 저장소에 실제로 존재하지 않는다. 아래 테스트에서
# rate_pct="8" 등을 쓰는 것은 전부 [TEST FIXTURE]이며 방산원가 법정 GA율이
# 아니다 — rate 선택 로직/계산 로직을 합성 데이터로만 검증한다.

def _ga_contract(contract_no="CONTRACT-A", contract_type="MULTI_PRODUCT",
                  start_date="2026-07-01"):
    return {
        "contract_no": contract_no, "contract_type": contract_type,
        "start_date": start_date,
    }

def _ga_actual_dict(contract_no="CONTRACT-A", amount="1000000.00"):
    return {contract_no: {"actual_manufacturing_cost": Decimal(amount)}}

def _ga_budget_dict(contract_no="CONTRACT-A", amount="2000000.00"):
    return {contract_no: {"budget_manufacturing_cost": Decimal(amount)}}

def _rate_rule(rule_id="RATE-1", contract_type=None, effective_from=None,
               effective_to=None, rate_pct="8", priority="10", rate_type="GA"):
    # rate_pct="8" 등은 [TEST FIXTURE] 값이다.
    return {
        "rule_id": rule_id, "rate_type": rate_type, "contract_type": contract_type,
        "effective_from": effective_from, "effective_to": effective_to,
        "rate_pct": rate_pct, "priority": priority,
    }

def test_ga_by_contract_pulls_manufacturing_cost_base_from_existing_dicts():
    # 1. 제조원가 기준액(DM+DL+OH) 계산 — 기존 함수 결과를 그대로 가져오는지 확인.
    result = calculate_ga_by_contract(
        _ga_actual_dict("CONTRACT-A", "1000000.00"),
        _ga_budget_dict("CONTRACT-A", "2000000.00"),
        [],
        [_ga_contract("CONTRACT-A")],
    )
    c = result["CONTRACT-A"]
    assert c["manufacturing_cost_actual"] == Decimal("1000000.00")
    assert c["manufacturing_cost_budget"] == Decimal("2000000.00")

def test_ga_by_contract_no_rate_rule_is_not_calculable_not_zero():
    # 2. rate rule이 전혀 없으면 calculable=False, ga_rate/ga_actual 등은 None
    #    (0%로 임의 처리하지 않는다).
    result = calculate_ga_by_contract(
        _ga_actual_dict(), _ga_budget_dict(), [], [_ga_contract()],
    )
    c = result["CONTRACT-A"]
    assert c["calculable"] is False
    assert c["ga_rate"] is None
    assert c["ga_actual"] is None
    assert c["ga_budget"] is None
    assert c["ga_variance"] is None
    assert "rate rule" in c["reason"] or "rule" in c["reason"]

def test_ga_by_contract_zero_percent_rule_is_calculable():
    # 3. [TEST FIXTURE] rate_pct=0인 rule이 실제로 존재하면 정상 처리(계산 불가 아님).
    result = calculate_ga_by_contract(
        _ga_actual_dict("CONTRACT-A", "1000000.00"),
        _ga_budget_dict("CONTRACT-A", "2000000.00"),
        [_rate_rule(rate_pct="0")],
        [_ga_contract("CONTRACT-A")],
    )
    c = result["CONTRACT-A"]
    assert c["calculable"] is True
    assert c["ga_rate"] == Decimal("0")
    assert c["ga_actual"] == Decimal("0.00")
    assert c["ga_budget"] == Decimal("0.00")

def test_ga_by_contract_exact_contract_type_beats_global_even_with_lower_priority():
    # 4. contract_type 정확 일치가 전체(fallback)보다 priority 수치와 무관하게
    #    항상 우선한다([TEST FIXTURE] rate 값).
    result = calculate_ga_by_contract(
        _ga_actual_dict("CONTRACT-A", "1000000.00"),
        _ga_budget_dict("CONTRACT-A", "0"),
        [
            _rate_rule("RATE-GLOBAL", contract_type=None, rate_pct="10", priority="99"),
            _rate_rule("RATE-EXACT", contract_type="MULTI_PRODUCT", rate_pct="8", priority="1"),
        ],
        [_ga_contract("CONTRACT-A", contract_type="MULTI_PRODUCT")],
    )
    c = result["CONTRACT-A"]
    assert c["rate_source"] == "RATE-EXACT"
    assert c["ga_rate"] == Decimal("8")

def test_ga_by_contract_falls_back_to_global_when_no_exact_match():
    # 5. 정확 일치가 없으면 전체(contract_type=None) rule로 fallback.
    result = calculate_ga_by_contract(
        _ga_actual_dict("CONTRACT-A", "1000000.00"),
        _ga_budget_dict("CONTRACT-A", "0"),
        [_rate_rule("RATE-GLOBAL", contract_type=None, rate_pct="8")],
        [_ga_contract("CONTRACT-A", contract_type="PROTOTYPE")],
    )
    c = result["CONTRACT-A"]
    assert c["calculable"] is True
    assert c["rate_source"] == "RATE-GLOBAL"

def test_ga_by_contract_prefers_higher_priority_within_same_specificity():
    # 6. 동일 구체성(둘 다 정확 일치) 내에서는 priority가 높은 쪽이 우선.
    result = calculate_ga_by_contract(
        _ga_actual_dict("CONTRACT-A", "1000000.00"),
        _ga_budget_dict("CONTRACT-A", "0"),
        [
            _rate_rule("RATE-LOW", contract_type="MULTI_PRODUCT", rate_pct="5", priority="1"),
            _rate_rule("RATE-HIGH", contract_type="MULTI_PRODUCT", rate_pct="8", priority="10"),
        ],
        [_ga_contract("CONTRACT-A", contract_type="MULTI_PRODUCT")],
    )
    c = result["CONTRACT-A"]
    assert c["rate_source"] == "RATE-HIGH"
    assert c["ga_rate"] == Decimal("8")

def test_ga_by_contract_effective_date_range_includes_reference_date():
    # 7. 계약 start_date가 effective_from~to 범위 안이면 적용된다.
    result = calculate_ga_by_contract(
        _ga_actual_dict("CONTRACT-A", "1000000.00"),
        _ga_budget_dict("CONTRACT-A", "0"),
        [_rate_rule(effective_from="2026-01-01", effective_to="2026-12-31", rate_pct="8")],
        [_ga_contract("CONTRACT-A", start_date="2026-07-01")],
    )
    assert result["CONTRACT-A"]["calculable"] is True

def test_ga_by_contract_excludes_rule_outside_effective_date_range():
    # 8. 계약 start_date가 범위 밖이면 그 rule은 후보에서 제외된다(다른 rule이
    #    없으므로 계산 불가).
    result = calculate_ga_by_contract(
        _ga_actual_dict("CONTRACT-A", "1000000.00"),
        _ga_budget_dict("CONTRACT-A", "0"),
        [_rate_rule(effective_from="2025-01-01", effective_to="2025-12-31", rate_pct="8")],
        [_ga_contract("CONTRACT-A", start_date="2026-07-01")],
    )
    c = result["CONTRACT-A"]
    assert c["calculable"] is False
    assert c["ga_rate"] is None

def test_ga_by_contract_ambiguous_when_tied_top_priority_candidates():
    # 9. 동일 구체성·동일 priority인 후보가 2건 이상이면 모호 상태로 처리한다.
    result = calculate_ga_by_contract(
        _ga_actual_dict("CONTRACT-A", "1000000.00"),
        _ga_budget_dict("CONTRACT-A", "0"),
        [
            _rate_rule("RATE-X", contract_type="MULTI_PRODUCT", rate_pct="8", priority="10"),
            _rate_rule("RATE-Y", contract_type="MULTI_PRODUCT", rate_pct="9", priority="10"),
        ],
        [_ga_contract("CONTRACT-A", contract_type="MULTI_PRODUCT")],
    )
    c = result["CONTRACT-A"]
    assert c["calculable"] is False
    assert "모호" in c["reason"] or "우선순위" in c["reason"]

def test_ga_by_contract_calculates_ga_actual_and_budget_and_variance():
    # 10/11/12. GA Actual, GA Budget, GA Variance 계산 ([TEST FIXTURE] rate=8%).
    result = calculate_ga_by_contract(
        _ga_actual_dict("CONTRACT-A", "1000000.00"),
        _ga_budget_dict("CONTRACT-A", "2000000.00"),
        [_rate_rule(rate_pct="8")],
        [_ga_contract("CONTRACT-A")],
    )
    c = result["CONTRACT-A"]
    assert c["ga_actual"] == Decimal("80000.00")
    assert c["ga_budget"] == Decimal("160000.00")
    assert c["ga_variance"] == Decimal("-80000.00")

def test_ga_by_contract_independent_of_contract_variance():
    # 13. calculate_contract_variance()의 DM/DL/OH variance/total_variance는
    #     GA 계산과 완전히 분리되어 서로 영향을 주지 않는다.
    actual_by_contract = {
        "CONTRACT-A": {
            "actual_material_cost": Decimal("100.00"), "actual_labor_cost": Decimal("50"),
            "actual_overhead_cost": Decimal("10.00"), "actual_manufacturing_cost": Decimal("160.00"),
            "work_orders": ["WO-1"],
        }
    }
    budget_by_contract = {
        "CONTRACT-A": {
            "budget_material_cost": Decimal("80.00"), "budget_labor_cost": Decimal("60"),
            "budget_overhead_cost": Decimal("15.00"), "budget_manufacturing_cost": Decimal("155.00"),
            "work_orders": ["WO-1"], "unpriced_work_orders": [],
        }
    }
    variance = calculate_contract_variance(
        [_ga_contract("CONTRACT-A")], actual_by_contract, budget_by_contract,
    )
    ga = calculate_ga_by_contract(
        actual_by_contract, budget_by_contract, [_rate_rule(rate_pct="8")],
        [_ga_contract("CONTRACT-A")],
    )
    # 기존 Contract Variance 필드는 GA 계산 호출 전후로 그대로다.
    assert variance["CONTRACT-A"]["total_variance"] == Decimal("5.00")
    assert "ga_variance" not in variance["CONTRACT-A"]
    assert "total_variance" not in ga["CONTRACT-A"]
    assert ga["CONTRACT-A"]["ga_variance"] == Decimal("0.40")


# --- 실제 Phase 2 데이터 기준 GA 검증 ---

def _load_real_ga():
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
    # 32_cost_rate_rule.xlsx는 저장소에 없다 — 실제 로더 호출 결과가 곧 빈 리스트다.
    rate_rules = rows("32_cost_rate_rule.xlsx", "cost_rate_rule")
    return calculate_ga_by_contract(actual_by_contract, budget_by_contract, rate_rules, contracts), \
        actual_by_contract, budget_by_contract

def test_real_dataset_ga_not_calculable_without_rate_rule_file():
    # 14. 실제 데이터에는 rate rule 파일이 없으므로 3개 계약 모두 calculable=False여야
    #     한다 — 제조원가 기준액 자체는 기존 함수 결과와 정확히 일치해야 한다.
    result = _load_real_ga()
    if result is None:
        return
    ga_by_contract, actual_by_contract, budget_by_contract = result

    assert set(ga_by_contract.keys()) == {"CONTRACT-001", "CONTRACT-002", "CONTRACT-003"}
    for contract_no in ga_by_contract:
        c = ga_by_contract[contract_no]
        assert c["calculable"] is False
        assert c["ga_rate"] is None
        assert c["ga_actual"] is None
        assert c["reason"] is not None

        assert c["manufacturing_cost_actual"] == actual_by_contract[contract_no]["actual_manufacturing_cost"]
        assert c["manufacturing_cost_budget"] == budget_by_contract[contract_no]["budget_manufacturing_cost"]

    # CONTRACT-001/002/003의 실제 제조원가 기준액(기존에 이미 검증된 값)까지 재확인.
    assert ga_by_contract["CONTRACT-001"]["manufacturing_cost_actual"] == Decimal("1817220.88")
    assert ga_by_contract["CONTRACT-001"]["manufacturing_cost_budget"] == Decimal("3372160.00")
    assert ga_by_contract["CONTRACT-002"]["manufacturing_cost_actual"] == Decimal("1257612.00")
    assert ga_by_contract["CONTRACT-002"]["manufacturing_cost_budget"] == Decimal("3487872.00")
    assert ga_by_contract["CONTRACT-003"]["manufacturing_cost_actual"] == Decimal("0")
    assert ga_by_contract["CONTRACT-003"]["manufacturing_cost_budget"] == Decimal("1596162.00")


# --- calculate_contract_total_cost (Phase 2 6단계, Actual만) ---

def _tc_contract(contract_no="CONTRACT-A"):
    return {"contract_no": contract_no}

def _tc_manufacturing(contract_no="CONTRACT-A", amount="1000000.00"):
    return {contract_no: {"actual_manufacturing_cost": Decimal(amount)}}

def _tc_de(contract_no="CONTRACT-A", amount="500000.00"):
    return {contract_no: {"direct_expense_amount": Decimal(amount)}}

def _tc_ga_calculable(contract_no="CONTRACT-A", ga_actual="80000.00"):
    return {contract_no: {"calculable": True, "ga_actual": Decimal(ga_actual), "reason": "OK"}}

def _tc_ga_not_calculable(contract_no="CONTRACT-A",
                           reason="[TEST FIXTURE] 적용 가능한 GA rate rule이 없습니다."):
    return {contract_no: {"calculable": False, "ga_actual": None, "reason": reason}}

def test_contract_total_cost_combines_manufacturing_and_direct_expense():
    result = calculate_contract_total_cost(
        _tc_manufacturing("CONTRACT-A", "1000000.00"),
        _tc_de("CONTRACT-A", "500000.00"),
        _tc_ga_not_calculable("CONTRACT-A"),
        [_tc_contract("CONTRACT-A")],
    )
    c = result["CONTRACT-A"]
    assert c["manufacturing_cost"] == Decimal("1000000.00")
    assert c["direct_expense"] == Decimal("500000.00")
    assert c["total_cost_excl_ga"] == Decimal("1500000.00")

def test_contract_total_cost_ga_calculable_adds_ga_to_total():
    result = calculate_contract_total_cost(
        _tc_manufacturing("CONTRACT-A", "1000000.00"),
        _tc_de("CONTRACT-A", "500000.00"),
        _tc_ga_calculable("CONTRACT-A", "80000.00"),
        [_tc_contract("CONTRACT-A")],
    )
    c = result["CONTRACT-A"]
    assert c["calculable"] is True
    assert c["ga_amount"] == Decimal("80000.00")
    assert c["total_cost"] == Decimal("1580000.00")
    assert c["reason"] == "OK"

def test_contract_total_cost_ga_not_calculable_total_cost_is_none():
    result = calculate_contract_total_cost(
        _tc_manufacturing("CONTRACT-A", "1000000.00"),
        _tc_de("CONTRACT-A", "500000.00"),
        _tc_ga_not_calculable("CONTRACT-A"),
        [_tc_contract("CONTRACT-A")],
    )
    c = result["CONTRACT-A"]
    assert c["calculable"] is False
    assert c["total_cost"] is None
    assert c["reason"] is not None
    # GA가 계산 불가여도 total_cost_excl_ga는 정상적으로 채워져 있어야 한다.
    assert c["total_cost_excl_ga"] == Decimal("1500000.00")

def test_contract_total_cost_never_treats_missing_ga_as_zero():
    # ga_amount가 None인지(0이 아닌지) 명시적으로 확인 — GA 부재를 0으로
    # 대체하지 않는다는 정책의 핵심 검증.
    result = calculate_contract_total_cost(
        _tc_manufacturing("CONTRACT-A", "1000000.00"),
        _tc_de("CONTRACT-A", "500000.00"),
        _tc_ga_not_calculable("CONTRACT-A"),
        [_tc_contract("CONTRACT-A")],
    )
    c = result["CONTRACT-A"]
    assert c["ga_amount"] is None
    assert c["ga_amount"] != Decimal("0")

def test_contract_total_cost_contract_with_no_direct_expense():
    # DE 결과 dict에 이 계약이 아예 없으면 direct_expense=0으로 취급한다
    # (DE 실적이 전혀 없는 계약과 동일 — 계산 불가가 아니라 실적 0).
    result = calculate_contract_total_cost(
        _tc_manufacturing("CONTRACT-A", "1000000.00"),
        {},
        _tc_ga_calculable("CONTRACT-A", "80000.00"),
        [_tc_contract("CONTRACT-A")],
    )
    c = result["CONTRACT-A"]
    assert c["direct_expense"] == Decimal("0")
    assert c["total_cost_excl_ga"] == Decimal("1000000.00")

def test_contract_total_cost_seeds_contract_with_no_data_at_all():
    result = calculate_contract_total_cost(
        {}, {}, {}, [_tc_contract("CONTRACT-EMPTY")],
    )
    c = result["CONTRACT-EMPTY"]
    assert c["manufacturing_cost"] == Decimal("0")
    assert c["direct_expense"] == Decimal("0")
    assert c["total_cost_excl_ga"] == Decimal("0")
    assert c["calculable"] is False
    assert c["total_cost"] is None
    assert c["reason"] is not None

def test_contract_total_cost_does_not_mutate_input_dicts():
    manufacturing = _tc_manufacturing("CONTRACT-A", "1000000.00")
    de = _tc_de("CONTRACT-A", "500000.00")
    ga = _tc_ga_calculable("CONTRACT-A", "80000.00")
    manufacturing_before = {k: dict(v) for k, v in manufacturing.items()}
    de_before = {k: dict(v) for k, v in de.items()}
    ga_before = {k: dict(v) for k, v in ga.items()}

    calculate_contract_total_cost(manufacturing, de, ga, [_tc_contract("CONTRACT-A")])

    assert manufacturing == manufacturing_before
    assert de == de_before
    assert ga == ga_before

def test_contract_total_cost_independent_of_contract_variance():
    actual_by_contract = {
        "CONTRACT-A": {
            "actual_material_cost": Decimal("100.00"), "actual_labor_cost": Decimal("50"),
            "actual_overhead_cost": Decimal("10.00"), "actual_manufacturing_cost": Decimal("160.00"),
            "work_orders": ["WO-1"],
        }
    }
    budget_by_contract = {
        "CONTRACT-A": {
            "budget_material_cost": Decimal("80.00"), "budget_labor_cost": Decimal("60"),
            "budget_overhead_cost": Decimal("15.00"), "budget_manufacturing_cost": Decimal("155.00"),
            "work_orders": ["WO-1"], "unpriced_work_orders": [],
        }
    }
    variance = calculate_contract_variance(
        [_tc_contract("CONTRACT-A")], actual_by_contract, budget_by_contract,
    )
    total_cost = calculate_contract_total_cost(
        actual_by_contract, _tc_de("CONTRACT-A", "40.00"),
        _tc_ga_not_calculable("CONTRACT-A"), [_tc_contract("CONTRACT-A")],
    )
    assert variance["CONTRACT-A"]["total_variance"] == Decimal("5.00")
    assert "total_cost_excl_ga" not in variance["CONTRACT-A"]
    assert "total_variance" not in total_cost["CONTRACT-A"]
    assert total_cost["CONTRACT-A"]["total_cost_excl_ga"] == Decimal("200.00")

def test_contract_total_cost_decimal_precision():
    result = calculate_contract_total_cost(
        _tc_manufacturing("CONTRACT-A", "100.015"),
        _tc_de("CONTRACT-A", "0.005"),
        _tc_ga_calculable("CONTRACT-A", "0.01"),
        [_tc_contract("CONTRACT-A")],
    )
    c = result["CONTRACT-A"]
    assert c["total_cost_excl_ga"] == Decimal("100.020")
    assert c["total_cost"] == Decimal("100.030")


# --- 실제 Phase 2 데이터 기준 Contract Total Cost 검증 ---

def _load_real_contract_total_cost():
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
    de_by_contract = calculate_actual_direct_expense_by_contract(
        contracts, work_orders, rows("31_direct_expense.xlsx", "direct_expense"),
    )
    rate_rules = rows("32_cost_rate_rule.xlsx", "cost_rate_rule")  # 저장소에 없음 -> []
    ga_by_contract = calculate_ga_by_contract(
        actual_by_contract, budget_by_contract, rate_rules, contracts,
    )
    return calculate_contract_total_cost(
        actual_by_contract, de_by_contract, ga_by_contract, contracts,
    )

def test_real_dataset_contract_total_cost_excl_ga_matches_expected_values():
    result = _load_real_contract_total_cost()
    if result is None:
        return

    assert result["CONTRACT-001"]["total_cost_excl_ga"] == Decimal("2567220.88")
    assert result["CONTRACT-002"]["total_cost_excl_ga"] == Decimal("2457612.00")
    assert result["CONTRACT-003"]["total_cost_excl_ga"] == Decimal("0.00")

def test_real_dataset_contract_total_cost_is_none_without_ga_rate():
    # 32_cost_rate_rule.xlsx가 없으므로 3개 계약 모두 total_cost=None,
    # calculable=False가 정상이다(0으로 대체되지 않는다).
    result = _load_real_contract_total_cost()
    if result is None:
        return

    for contract_no in ("CONTRACT-001", "CONTRACT-002", "CONTRACT-003"):
        c = result[contract_no]
        assert c["calculable"] is False
        assert c["total_cost"] is None
        assert c["ga_amount"] is None
        assert c["reason"] is not None


# --- calculate_budget_direct_expense_by_contract (Phase 2 7단계) ---
#
# 34_direct_expense_budget.xlsx는 저장소에 구조만 있고 실제 예산 행이 없다.
# 아래 테스트의 budget_amount 값들은 전부 [TEST FIXTURE]이며 실제 예산이 아니다.

def _bde_contract(contract_no="CONTRACT-A", start_date="2026-07-01"):
    return {"contract_no": contract_no, "start_date": start_date}

def _bde_row(contract_no="CONTRACT-A", budget_expense_id="BDE-1",
             expense_type="외주가공비", budget_amount="100000",
             effective_from=None, effective_to=None):
    return {
        "contract_no": contract_no, "budget_expense_id": budget_expense_id,
        "expense_type": expense_type, "budget_amount": budget_amount,
        "effective_from": effective_from, "effective_to": effective_to,
        "description": "[TEST FIXTURE]",
    }

def test_budget_de_by_contract_sums_multiple_rows_for_same_contract():
    result = calculate_budget_direct_expense_by_contract(
        [_bde_contract("CONTRACT-A")],
        [
            _bde_row("CONTRACT-A", "BDE-1", budget_amount="100000"),
            _bde_row("CONTRACT-A", "BDE-2", budget_amount="50000"),
        ],
    )
    c = result["CONTRACT-A"]
    assert c["calculable"] is True
    assert c["budget_direct_expense"] == Decimal("150000.00")
    assert c["reason"] == "OK"

def test_budget_de_by_contract_no_data_is_not_calculable_not_zero():
    result = calculate_budget_direct_expense_by_contract(
        [_bde_contract("CONTRACT-A")], [],
    )
    c = result["CONTRACT-A"]
    assert c["calculable"] is False
    assert c["budget_direct_expense"] is None
    assert c["budget_direct_expense"] != Decimal("0")
    assert c["reason"] is not None

def test_budget_de_by_contract_seeds_all_contracts_from_master():
    result = calculate_budget_direct_expense_by_contract(
        [_bde_contract("CONTRACT-A"), _bde_contract("CONTRACT-EMPTY")],
        [_bde_row("CONTRACT-A", budget_amount="100000")],
    )
    assert set(result.keys()) == {"CONTRACT-A", "CONTRACT-EMPTY"}
    assert result["CONTRACT-EMPTY"]["calculable"] is False
    assert result["CONTRACT-EMPTY"]["budget_direct_expense"] is None

def test_budget_de_by_contract_excludes_row_with_unknown_contract_reference():
    result = calculate_budget_direct_expense_by_contract(
        [_bde_contract("CONTRACT-A")],
        [_bde_row("CONTRACT-999", budget_amount="100000")],
    )
    assert set(result.keys()) == {"CONTRACT-A"}
    assert result["CONTRACT-A"]["calculable"] is False

def test_budget_de_by_contract_duplicate_budget_expense_id_still_both_summed():
    # 중복 budget_expense_id라도 별도 검증 없이 각 행을 그대로 합산한다
    # (이 함수는 단순 합산기이며, 중복 판정을 위한 새 오류 코드는 만들지 않는다).
    result = calculate_budget_direct_expense_by_contract(
        [_bde_contract("CONTRACT-A")],
        [
            _bde_row("CONTRACT-A", "BDE-DUP", budget_amount="100000"),
            _bde_row("CONTRACT-A", "BDE-DUP", budget_amount="20000"),
        ],
    )
    assert result["CONTRACT-A"]["budget_direct_expense"] == Decimal("120000.00")

def test_budget_de_by_contract_decimal_precision():
    result = calculate_budget_direct_expense_by_contract(
        [_bde_contract("CONTRACT-A")],
        [
            _bde_row("CONTRACT-A", "BDE-1", budget_amount="100.005"),
            _bde_row("CONTRACT-A", "BDE-2", budget_amount="0.005"),
        ],
    )
    # 100.005 + 0.005 = 100.010 -> ROUND_HALF_UP -> 100.01
    assert result["CONTRACT-A"]["budget_direct_expense"] == Decimal("100.01")

def test_budget_de_by_contract_negative_amount_is_summed_as_valid():
    # 음수 예산(축소 등)도 유효한 값으로 그대로 합산한다 — 거부하거나 별도
    # 취급하지 않는다(Actual DE의 환입 처리와 동일한 원칙).
    result = calculate_budget_direct_expense_by_contract(
        [_bde_contract("CONTRACT-A")],
        [
            _bde_row("CONTRACT-A", "BDE-1", budget_amount="100000"),
            _bde_row("CONTRACT-A", "BDE-2", budget_amount="-30000"),
        ],
    )
    c = result["CONTRACT-A"]
    assert c["calculable"] is True
    assert c["budget_direct_expense"] == Decimal("70000.00")

def test_budget_de_by_contract_effective_date_within_range_included():
    result = calculate_budget_direct_expense_by_contract(
        [_bde_contract("CONTRACT-A", start_date="2026-07-01")],
        [_bde_row("CONTRACT-A", budget_amount="100000",
                  effective_from="2026-01-01", effective_to="2026-12-31")],
    )
    assert result["CONTRACT-A"]["calculable"] is True

def test_budget_de_by_contract_effective_date_outside_range_excluded():
    result = calculate_budget_direct_expense_by_contract(
        [_bde_contract("CONTRACT-A", start_date="2026-07-01")],
        [_bde_row("CONTRACT-A", budget_amount="100000",
                  effective_from="2025-01-01", effective_to="2025-12-31")],
    )
    c = result["CONTRACT-A"]
    assert c["calculable"] is False
    assert c["budget_direct_expense"] is None

def test_budget_de_by_contract_multiple_expense_types_all_summed():
    result = calculate_budget_direct_expense_by_contract(
        [_bde_contract("CONTRACT-A")],
        [
            _bde_row("CONTRACT-A", "BDE-1", expense_type="외주가공비", budget_amount="100000"),
            _bde_row("CONTRACT-A", "BDE-2", expense_type="특허권사용료", budget_amount="50000"),
        ],
    )
    assert result["CONTRACT-A"]["budget_direct_expense"] == Decimal("150000.00")

def test_budget_de_by_contract_independent_of_actual_direct_expense():
    # Budget DE와 Actual DE는 서로 다른 함수/데이터라 한쪽 계산이 다른 쪽에
    # 영향을 주지 않는다.
    contracts = [_bde_contract("CONTRACT-A")]
    budget_result = calculate_budget_direct_expense_by_contract(
        contracts, [_bde_row("CONTRACT-A", budget_amount="100000")],
    )
    actual_result = calculate_actual_direct_expense_by_contract(
        contracts,
        [{"wo_no": "WO-1", "contract_no": "CONTRACT-A"}],
        [{"expense_id": "DE-1", "wo_no": "WO-1", "contract_no": None, "amount": "500000"}],
    )
    assert budget_result["CONTRACT-A"]["budget_direct_expense"] == Decimal("100000.00")
    assert actual_result["CONTRACT-A"]["direct_expense_amount"] == Decimal("500000.00")
    assert "budget_direct_expense" not in actual_result["CONTRACT-A"]
    assert "direct_expense_amount" not in budget_result["CONTRACT-A"]

def test_budget_de_by_contract_does_not_mutate_inputs():
    contracts = [_bde_contract("CONTRACT-A")]
    rows_in = [_bde_row("CONTRACT-A", budget_amount="100000")]
    contracts_before = [dict(c) for c in contracts]
    rows_before = [dict(r) for r in rows_in]

    calculate_budget_direct_expense_by_contract(contracts, rows_in)

    assert contracts == contracts_before
    assert rows_in == rows_before


# --- 실제 Phase 2 데이터 기준 Budget DE 검증 ---

def _load_real_budget_de():
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

    contracts = rows("30_contract.xlsx", "contract")
    budget_des = rows("34_direct_expense_budget.xlsx", "direct_expense_budget")
    return calculate_budget_direct_expense_by_contract(contracts, budget_des), budget_des

def test_real_dataset_budget_direct_expense_file_has_no_data_rows():
    result = _load_real_budget_de()
    if result is None:
        return
    _, budget_des = result
    assert budget_des == []

def test_real_dataset_budget_direct_expense_all_contracts_not_calculable():
    # 34_direct_expense_budget.xlsx에 실제 행이 없으므로 3개 계약 모두
    # calculable=False, budget_direct_expense=None이 정상이다(0 아님).
    result = _load_real_budget_de()
    if result is None:
        return
    budget_de_by_contract, _ = result

    assert set(budget_de_by_contract.keys()) == {"CONTRACT-001", "CONTRACT-002", "CONTRACT-003"}
    for contract_no in budget_de_by_contract:
        c = budget_de_by_contract[contract_no]
        assert c["calculable"] is False
        assert c["budget_direct_expense"] is None
        assert c["reason"] is not None


# --- calculate_ga_base_amount (Phase 2 8단계, 규정 정합 구조 준비) ---
#
# 이 구획 전체의 rate_pct/company_code/plant_code/industry_type/company_size
# 값은 전부 합성 테스트 픽스처이며 실제 방산원가 규정 수치가 아니다.
# 32_cost_rate_rule.xlsx 실제 데이터는 여전히 존재하지 않는다.

def test_ga_base_amount_include_gfm_sums_both():
    result = calculate_ga_base_amount(
        Decimal("1000000.00"), Decimal("50000.00"), "INCLUDE_GFM"
    )
    assert result == Decimal("1050000.00")

def test_ga_base_amount_include_gfm_none_is_not_zero():
    # 관급재료비 데이터가 없으면(None) 0으로 대체하지 않고 전체를 None으로 전파한다.
    result = calculate_ga_base_amount(Decimal("1000000.00"), None, "INCLUDE_GFM")
    assert result is None
    assert result != Decimal("0")

def test_ga_base_amount_exclude_gfm_ignores_gfm_value():
    # EXCLUDE_GFM은 관급재료비 값 자체를 쓰지 않으므로 None이어도 계산된다.
    result = calculate_ga_base_amount(Decimal("1000000.00"), None, "EXCLUDE_GFM")
    assert result == Decimal("1000000.00")

def test_ga_base_amount_unknown_basis_is_not_calculable():
    result = calculate_ga_base_amount(Decimal("1000000.00"), Decimal("0"), "SOMETHING_ELSE")
    assert result is None

def test_ga_base_amount_missing_manufacturing_cost_propagates_none():
    result = calculate_ga_base_amount(None, Decimal("50000.00"), "INCLUDE_GFM")
    assert result is None
    result2 = calculate_ga_base_amount(None, Decimal("50000.00"), "EXCLUDE_GFM")
    assert result2 is None


# --- resolve_ga_actual_rate / resolve_ga_ceiling_rate ---

# _REF_DATE는 아래 _reg_rate_rule()의 기본 effective_from~effective_to
# ("2026-01-01"~"2026-12-31") 구간 안에 드는 합성 기준일이다. 실제 방산원가
# 적용시점을 의미하지 않는다.
_REF_DATE = "2026-06-30"

def _reg_rate_rule(rule_id="RATE-1", rate_type="GA", rate_kind="ACTUAL",
                    company_code=None, plant_code=None, fiscal_year=None,
                    industry_type=None, company_size=None, rate_pct="8",
                    effective_from="2026-01-01", effective_to="2026-12-31"):
    return {
        "rule_id": rule_id, "rate_type": rate_type, "rate_kind": rate_kind,
        "company_code": company_code, "plant_code": plant_code,
        "fiscal_year": fiscal_year, "industry_type": industry_type,
        "company_size": company_size, "rate_pct": rate_pct,
        "effective_from": effective_from, "effective_to": effective_to,
    }

def test_resolve_ga_actual_rate_exact_match():
    rate_rules = [_reg_rate_rule("RATE-ACT", company_code="HB01", plant_code="PL01",
                                  fiscal_year="2026", rate_pct="8")]
    rate_pct, matched = resolve_ga_actual_rate(rate_rules, "HB01", "PL01", "2026", _REF_DATE)
    assert rate_pct == Decimal("8")
    assert matched["rule_id"] == "RATE-ACT"

def test_resolve_ga_actual_rate_no_match_is_none():
    rate_rules = [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026")]
    rate_pct, matched = resolve_ga_actual_rate(rate_rules, "HB01", "PL02", "2026", _REF_DATE)
    assert rate_pct is None
    assert matched is None

def test_resolve_ga_actual_rate_ambiguous_when_two_rows_match():
    rate_rules = [
        _reg_rate_rule("RATE-1", company_code="HB01", plant_code="PL01", fiscal_year="2026", rate_pct="8"),
        _reg_rate_rule("RATE-2", company_code="HB01", plant_code="PL01", fiscal_year="2026", rate_pct="9"),
    ]
    rate_pct, matched = resolve_ga_actual_rate(rate_rules, "HB01", "PL01", "2026", _REF_DATE)
    assert rate_pct is None
    assert matched is None

def test_resolve_ga_actual_rate_missing_key_input_is_none():
    rate_rules = [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026")]
    rate_pct, matched = resolve_ga_actual_rate(rate_rules, "HB01", None, "2026", _REF_DATE)
    assert rate_pct is None
    assert matched is None

def test_resolve_ga_actual_rate_missing_reference_date_is_none():
    # reference_date 자체가 없으면(호출자가 전달하지 않으면) 무조건 (None, None) —
    # 이 함수는 현재 날짜를 스스로 대신 채우지 않는다.
    rate_rules = [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026")]
    rate_pct, matched = resolve_ga_actual_rate(rate_rules, "HB01", "PL01", "2026", None)
    assert rate_pct is None
    assert matched is None

def test_resolve_ga_ceiling_rate_exact_match():
    rate_rules = [_reg_rate_rule("RATE-CEIL", rate_kind="CEILING",
                                  industry_type="ASSEMBLY_METAL", company_size="GENERAL",
                                  rate_pct="7")]
    rate_pct, matched = resolve_ga_ceiling_rate(rate_rules, "ASSEMBLY_METAL", "GENERAL", _REF_DATE)
    assert rate_pct == Decimal("7")
    assert matched["rule_id"] == "RATE-CEIL"

def test_resolve_ga_ceiling_rate_no_match_is_none():
    rate_rules = [_reg_rate_rule(rate_kind="CEILING", industry_type="ASSEMBLY_METAL", company_size="GENERAL")]
    rate_pct, matched = resolve_ga_ceiling_rate(rate_rules, "ASSEMBLY_METAL", "SME", _REF_DATE)
    assert rate_pct is None
    assert matched is None

def test_rate_kind_isolation_actual_and_ceiling_do_not_leak():
    # 동일한 company_code/plant_code/fiscal_year와 동일한 industry_type/company_size를
    # 가진 행이라도, rate_kind가 다르면 서로의 조회 결과에 나타나지 않는다.
    rate_rules = [
        _reg_rate_rule("RATE-ACT", rate_kind="ACTUAL", company_code="HB01",
                       plant_code="PL01", fiscal_year="2026",
                       industry_type="ASSEMBLY_METAL", company_size="GENERAL", rate_pct="8"),
        _reg_rate_rule("RATE-CEIL", rate_kind="CEILING", company_code="HB01",
                       plant_code="PL01", fiscal_year="2026",
                       industry_type="ASSEMBLY_METAL", company_size="GENERAL", rate_pct="7"),
    ]
    actual_rate, actual_rule = resolve_ga_actual_rate(rate_rules, "HB01", "PL01", "2026", _REF_DATE)
    ceiling_rate, ceiling_rule = resolve_ga_ceiling_rate(rate_rules, "ASSEMBLY_METAL", "GENERAL", _REF_DATE)
    assert actual_rate == Decimal("8")
    assert actual_rule["rule_id"] == "RATE-ACT"
    assert ceiling_rate == Decimal("7")
    assert ceiling_rule["rule_id"] == "RATE-CEIL"

def test_resolvers_do_not_mutate_rate_rules_input():
    rate_rules = [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026")]
    before = [dict(r) for r in rate_rules]
    resolve_ga_actual_rate(rate_rules, "HB01", "PL01", "2026", _REF_DATE)
    resolve_ga_ceiling_rate(rate_rules, "ASSEMBLY_METAL", "GENERAL", _REF_DATE)
    assert rate_rules == before


# --- effective_from/effective_to 기준일 필터링 (fiscal_year와는 별개 축) ---
#
# fiscal_year는 산정연도 식별자일 뿐이고 effective_from/effective_to는 그
# rule의 실제 효력기간이다 — 이 두 조건은 서로 대체 관계가 아니라 각각
# 독립적으로 만족되어야 한다. 아래 테스트들은 이 둘을 명확히 분리해서
# 검증한다.

def test_resolve_ga_actual_rate_effective_from_boundary_is_inclusive():
    rate_rules = [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026",
                                  rate_pct="8", effective_from="2026-01-01", effective_to="2026-12-31")]
    rate_pct, matched = resolve_ga_actual_rate(rate_rules, "HB01", "PL01", "2026", "2026-01-01")
    assert rate_pct == Decimal("8")
    assert matched is not None

def test_resolve_ga_actual_rate_effective_to_boundary_is_inclusive():
    rate_rules = [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026",
                                  rate_pct="8", effective_from="2026-01-01", effective_to="2026-12-31")]
    rate_pct, matched = resolve_ga_actual_rate(rate_rules, "HB01", "PL01", "2026", "2026-12-31")
    assert rate_pct == Decimal("8")
    assert matched is not None

def test_resolve_ga_actual_rate_before_effective_from_is_excluded():
    rate_rules = [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026",
                                  rate_pct="8", effective_from="2026-01-01", effective_to="2026-12-31")]
    rate_pct, matched = resolve_ga_actual_rate(rate_rules, "HB01", "PL01", "2026", "2025-12-31")
    assert rate_pct is None
    assert matched is None

def test_resolve_ga_actual_rate_after_effective_to_is_excluded():
    rate_rules = [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026",
                                  rate_pct="8", effective_from="2026-01-01", effective_to="2026-12-31")]
    rate_pct, matched = resolve_ga_actual_rate(rate_rules, "HB01", "PL01", "2026", "2027-01-01")
    assert rate_pct is None
    assert matched is None

def test_resolve_ga_actual_rate_selects_correct_non_overlapping_period():
    # 같은 company_code/plant_code/fiscal_year에 유효기간이 서로 겹치지 않는
    # 두 rule이 있어도, 기준일이 속한 쪽 하나만 정확히 선택된다.
    rate_rules = [
        _reg_rate_rule("RATE-H1", company_code="HB01", plant_code="PL01", fiscal_year="2026",
                       rate_pct="8", effective_from="2026-01-01", effective_to="2026-06-30"),
        _reg_rate_rule("RATE-H2", company_code="HB01", plant_code="PL01", fiscal_year="2026",
                       rate_pct="9", effective_from="2026-07-01", effective_to="2026-12-31"),
    ]
    rate_pct_h1, matched_h1 = resolve_ga_actual_rate(rate_rules, "HB01", "PL01", "2026", "2026-03-01")
    rate_pct_h2, matched_h2 = resolve_ga_actual_rate(rate_rules, "HB01", "PL01", "2026", "2026-09-01")
    assert rate_pct_h1 == Decimal("8")
    assert matched_h1["rule_id"] == "RATE-H1"
    assert rate_pct_h2 == Decimal("9")
    assert matched_h2["rule_id"] == "RATE-H2"

def test_resolve_ga_actual_rate_overlapping_periods_both_valid_is_ambiguous():
    # 사용자 예시: 두 rule 모두 fiscal_year=2026이고, 하나는
    # effective_from=2026-01-01~2026-12-31, 다른 하나는
    # effective_from=2026-07-01~2026-12-31이다. 기준일이 2026-08-01이면 두
    # rule 모두 동시에 유효 구간에 포함되므로, 임의로 하나를 고르지 않고
    # 모호(None, None)로 처리해야 한다.
    rate_rules = [
        _reg_rate_rule("RATE-FULL-YEAR", company_code="HB01", plant_code="PL01", fiscal_year="2026",
                       rate_pct="8", effective_from="2026-01-01", effective_to="2026-12-31"),
        _reg_rate_rule("RATE-H2-ONLY", company_code="HB01", plant_code="PL01", fiscal_year="2026",
                       rate_pct="9", effective_from="2026-07-01", effective_to="2026-12-31"),
    ]
    rate_pct, matched = resolve_ga_actual_rate(rate_rules, "HB01", "PL01", "2026", "2026-08-01")
    assert rate_pct is None
    assert matched is None

def test_resolve_ga_actual_rate_same_fiscal_year_but_effective_period_mismatch_is_excluded():
    # fiscal_year가 일치해도 effective_from/effective_to가 기준일을 포함하지
    # 않으면 매칭되지 않는다 — fiscal_year 일치가 effective 기간 검사를
    # 대체하지 않는다.
    rate_rules = [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026",
                                  rate_pct="8", effective_from="2026-07-01", effective_to="2026-12-31")]
    rate_pct, matched = resolve_ga_actual_rate(rate_rules, "HB01", "PL01", "2026", "2026-03-01")
    assert rate_pct is None
    assert matched is None

def test_resolve_ga_actual_rate_null_effective_bound_excludes_rule_not_unbounded():
    # effective_from 또는 effective_to가 None이면 "무기한 유효"로 간주하지
    # 않고 후보에서 제외한다 — validation.py의 _bom_date_ranges_overlap()과
    # 동일한 관례.
    rate_rules_null_from = [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026",
                                            rate_pct="8", effective_from=None, effective_to="2026-12-31")]
    rate_rules_null_to = [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026",
                                          rate_pct="8", effective_from="2026-01-01", effective_to=None)]
    rate_pct_1, matched_1 = resolve_ga_actual_rate(rate_rules_null_from, "HB01", "PL01", "2026", _REF_DATE)
    rate_pct_2, matched_2 = resolve_ga_actual_rate(rate_rules_null_to, "HB01", "PL01", "2026", _REF_DATE)
    assert rate_pct_1 is None and matched_1 is None
    assert rate_pct_2 is None and matched_2 is None

def test_resolve_ga_ceiling_rate_applies_same_effective_date_filter_as_actual():
    # CEILING 조회도 ACTUAL과 완전히 동일한 effective 기간 필터를 적용한다.
    rate_rules = [_reg_rate_rule(rate_kind="CEILING", industry_type="ASSEMBLY_METAL",
                                  company_size="GENERAL", rate_pct="7",
                                  effective_from="2026-01-01", effective_to="2026-06-30")]
    rate_pct_in, matched_in = resolve_ga_ceiling_rate(
        rate_rules, "ASSEMBLY_METAL", "GENERAL", "2026-06-30"
    )
    rate_pct_out, matched_out = resolve_ga_ceiling_rate(
        rate_rules, "ASSEMBLY_METAL", "GENERAL", "2026-07-01"
    )
    assert rate_pct_in == Decimal("7")
    assert matched_in is not None
    assert rate_pct_out is None
    assert matched_out is None

def test_resolve_ga_ceiling_rate_missing_reference_date_is_none():
    rate_rules = [_reg_rate_rule(rate_kind="CEILING", industry_type="ASSEMBLY_METAL", company_size="GENERAL")]
    rate_pct, matched = resolve_ga_ceiling_rate(rate_rules, "ASSEMBLY_METAL", "GENERAL", None)
    assert rate_pct is None
    assert matched is None

def test_resolve_ga_actual_rate_zero_percent_survives_effective_date_filtering():
    # rate_pct=0(유효한 0%)은 effective 기간 필터가 새로 추가된 뒤에도
    # "없음"과 계속 구분되어야 한다.
    rate_rules = [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026",
                                  rate_pct="0", effective_from="2026-01-01", effective_to="2026-12-31")]
    rate_pct_in_range, _ = resolve_ga_actual_rate(rate_rules, "HB01", "PL01", "2026", _REF_DATE)
    rate_pct_out_of_range, matched_out = resolve_ga_actual_rate(
        rate_rules, "HB01", "PL01", "2026", "2027-01-01"
    )
    assert rate_pct_in_range == Decimal("0")
    assert rate_pct_out_of_range is None
    assert matched_out is None
    assert rate_pct_in_range != rate_pct_out_of_range


# --- calculate_regulatory_ga_by_contract: 구조 검증 + 기존 함수와의 비교 ---

def _reg_contract(contract_no="CONTRACT-A", contract_type="MULTI_PRODUCT",
                   company_code="HB01", plant_code=None, fiscal_year=None,
                   industry_type=None, company_size=None):
    return {
        "contract_no": contract_no, "contract_type": contract_type,
        "company_code": company_code, "plant_code": plant_code,
        "fiscal_year": fiscal_year, "industry_type": industry_type,
        "company_size": company_size,
    }

def _dm_excl_gfm(contract_no="CONTRACT-A", amount="1000000.00"):
    # calculate_actual_material_cost_excluding_gfm_by_contract()의 출력
    # 형태를 흉내낸 테스트 픽스처. 기존(파라미터 추가 이전) 테스트들이
    # actual_by_contract["actual_manufacturing_cost"]에 넣었던 것과 동일한
    # 값을 그대로 dm_excluding_gfm에 옮겨서, actual_labor_cost/
    # actual_overhead_cost가 없는(0으로 처리되는) 상황에서 이전과 동일한
    # 합계가 나오도록 한다.
    if amount is None:
        return {contract_no: {"dm_excluding_gfm": None}}
    return {contract_no: {"dm_excluding_gfm": Decimal(amount)}}

def test_regulatory_ga_no_rate_rule_is_not_calculable_not_zero():
    result = calculate_regulatory_ga_by_contract(
        {"CONTRACT-A": {"actual_manufacturing_cost": Decimal("1000000.00")}},
        {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("2000000.00")}},
        {"CONTRACT-A": {"direct_expense_amount": Decimal("0")}},
        {"CONTRACT-A": {"calculable": True, "budget_direct_expense": Decimal("0")}},
        {},
        [],
        [_reg_contract("CONTRACT-A", plant_code="PL01", fiscal_year="2026")],
        "EXCLUDE_GFM",
        _REF_DATE,
        _dm_excl_gfm("CONTRACT-A", "1000000.00"),
    )
    c = result["CONTRACT-A"]
    assert c["calculable"] is False
    assert c["ga_actual"] is None
    assert c["reason"] is not None

def test_regulatory_ga_missing_gfm_under_include_basis_is_not_calculable():
    result = calculate_regulatory_ga_by_contract(
        {"CONTRACT-A": {"actual_manufacturing_cost": Decimal("1000000.00")}},
        {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("2000000.00")}},
        {"CONTRACT-A": {"direct_expense_amount": Decimal("0")}},
        {"CONTRACT-A": {"calculable": True, "budget_direct_expense": Decimal("0")}},
        {},  # government_furnished_material_by_contract 비어 있음 -> None
        [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026", rate_pct="8")],
        [_reg_contract("CONTRACT-A", plant_code="PL01", fiscal_year="2026")],
        "INCLUDE_GFM",
        _REF_DATE,
        _dm_excl_gfm("CONTRACT-A", "1000000.00"),
    )
    c = result["CONTRACT-A"]
    assert c["calculable"] is False
    assert c["ga_base_amount_actual"] is None
    assert c["ga_actual"] is None

def test_regulatory_ga_calculable_with_full_data_exclude_gfm():
    result = calculate_regulatory_ga_by_contract(
        {"CONTRACT-A": {"actual_manufacturing_cost": Decimal("1000000.00")}},
        {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("2000000.00")}},
        {"CONTRACT-A": {"direct_expense_amount": Decimal("500000.00")}},
        {"CONTRACT-A": {"calculable": True, "budget_direct_expense": Decimal("0")}},
        {},
        [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026", rate_pct="8")],
        [_reg_contract("CONTRACT-A", plant_code="PL01", fiscal_year="2026")],
        "EXCLUDE_GFM",
        _REF_DATE,
        _dm_excl_gfm("CONTRACT-A", "1000000.00"),
    )
    c = result["CONTRACT-A"]
    assert c["calculable"] is True
    # 기준액 = DM(관급제외, 1,000,000.00)+DL(0)+OH(0) + DE(500,000.00) = 1,500,000.00
    assert c["ga_base_amount_actual"] == Decimal("1500000.00")
    assert c["ga_actual"] == Decimal("120000.00")

def test_regulatory_ga_budget_de_not_calculable_makes_budget_base_none():
    result = calculate_regulatory_ga_by_contract(
        {"CONTRACT-A": {"actual_manufacturing_cost": Decimal("1000000.00")}},
        {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("2000000.00")}},
        {"CONTRACT-A": {"direct_expense_amount": Decimal("0")}},
        {"CONTRACT-A": {"calculable": False, "budget_direct_expense": None,
                         "reason": "[TEST FIXTURE] Budget DE 없음"}},
        {},
        [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026", rate_pct="8")],
        [_reg_contract("CONTRACT-A", plant_code="PL01", fiscal_year="2026")],
        "EXCLUDE_GFM",
        _REF_DATE,
        _dm_excl_gfm("CONTRACT-A", "1000000.00"),
    )
    c = result["CONTRACT-A"]
    # Actual 쪽은 계산되지만 Budget 쪽은 Budget DE가 없어 기준액 자체가 None.
    assert c["calculable"] is True
    assert c["ga_actual"] is not None
    assert c["ga_base_amount_budget"] is None
    assert c["ga_budget"] is None
    assert c["ga_variance"] is None

def test_regulatory_ga_exceeds_ceiling_flag_does_not_alter_ga_actual():
    result = calculate_regulatory_ga_by_contract(
        {"CONTRACT-A": {"actual_manufacturing_cost": Decimal("1000000.00")}},
        {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("0")}},
        {"CONTRACT-A": {"direct_expense_amount": Decimal("0")}},
        {"CONTRACT-A": {"calculable": True, "budget_direct_expense": Decimal("0")}},
        {},
        [
            _reg_rate_rule("RATE-ACT", rate_kind="ACTUAL", company_code="HB01",
                           plant_code="PL01", fiscal_year="2026", rate_pct="12"),
            _reg_rate_rule("RATE-CEIL", rate_kind="CEILING", industry_type="ASSEMBLY_METAL",
                           company_size="GENERAL", rate_pct="7"),
        ],
        [_reg_contract("CONTRACT-A", plant_code="PL01", fiscal_year="2026",
                        industry_type="ASSEMBLY_METAL", company_size="GENERAL")],
        "EXCLUDE_GFM",
        _REF_DATE,
        _dm_excl_gfm("CONTRACT-A", "1000000.00"),
    )
    c = result["CONTRACT-A"]
    # 상한(7%)보다 실적요율(12%)이 높다는 것을 인지만 하고, ga_actual 계산에는
    # 반영하지 않는다(상한 적용 정책은 아직 확정되지 않았다 — §C 미해결).
    assert c["exceeds_ceiling"] is True
    assert c["ga_actual"] == Decimal("120000.00")  # 1,000,000 x 12%, 상한으로 잘리지 않음

def test_regulatory_ga_seeds_all_contracts_from_master():
    result = calculate_regulatory_ga_by_contract(
        {}, {}, {}, {}, {}, [],
        [_reg_contract("CONTRACT-A"), _reg_contract("CONTRACT-EMPTY")],
        "EXCLUDE_GFM",
        _REF_DATE,
        {},
    )
    assert set(result.keys()) == {"CONTRACT-A", "CONTRACT-EMPTY"}

def test_regulatory_ga_does_not_mutate_inputs():
    actual = {"CONTRACT-A": {"actual_manufacturing_cost": Decimal("1000000.00")}}
    budget = {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("2000000.00")}}
    de_actual = {"CONTRACT-A": {"direct_expense_amount": Decimal("500000.00")}}
    de_budget = {"CONTRACT-A": {"calculable": True, "budget_direct_expense": Decimal("0")}}
    gfm = {}
    rate_rules = [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026", rate_pct="8")]
    contracts = [_reg_contract("CONTRACT-A", plant_code="PL01", fiscal_year="2026")]
    dm_excl = _dm_excl_gfm("CONTRACT-A", "1000000.00")

    import copy
    actual_before, budget_before = copy.deepcopy(actual), copy.deepcopy(budget)
    de_actual_before, de_budget_before = copy.deepcopy(de_actual), copy.deepcopy(de_budget)
    rate_rules_before, contracts_before = copy.deepcopy(rate_rules), copy.deepcopy(contracts)
    dm_excl_before = copy.deepcopy(dm_excl)

    calculate_regulatory_ga_by_contract(
        actual, budget, de_actual, de_budget, gfm, rate_rules, contracts, "EXCLUDE_GFM",
        _REF_DATE, dm_excl,
    )

    assert actual == actual_before
    assert budget == budget_before
    assert de_actual == de_actual_before
    assert de_budget == de_budget_before
    assert rate_rules == rate_rules_before
    assert contracts == contracts_before
    assert dm_excl == dm_excl_before


# --- 기존 calculate_ga_by_contract()와의 비교 테스트 ---

def test_regulatory_ga_matches_legacy_ga_when_de_is_zero():
    # DE=0이면 신규 기준액(DM+DL+OH+DE)이 기존 기준액(DM+DL+OH)과 같아지므로,
    # 동등한 rate를 적용했을 때 두 함수의 ga_actual이 일치해야 한다.
    actual_by_contract = {"CONTRACT-A": {"actual_manufacturing_cost": Decimal("1000000.00")}}
    budget_by_contract = {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("2000000.00")}}
    contracts_old = [{"contract_no": "CONTRACT-A", "contract_type": "MULTI_PRODUCT"}]

    legacy_result = calculate_ga_by_contract(
        actual_by_contract, budget_by_contract,
        [{"rule_id": "OLD-1", "rate_type": "GA", "contract_type": "MULTI_PRODUCT",
          "rate_pct": "8", "priority": "10"}],
        contracts_old,
    )

    new_result = calculate_regulatory_ga_by_contract(
        actual_by_contract, budget_by_contract,
        {"CONTRACT-A": {"direct_expense_amount": Decimal("0")}},
        {"CONTRACT-A": {"calculable": True, "budget_direct_expense": Decimal("0")}},
        {},
        [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026", rate_pct="8")],
        [_reg_contract("CONTRACT-A", plant_code="PL01", fiscal_year="2026")],
        "EXCLUDE_GFM",
        _REF_DATE,
        _dm_excl_gfm("CONTRACT-A", "1000000.00"),
    )

    assert legacy_result["CONTRACT-A"]["ga_actual"] == new_result["CONTRACT-A"]["ga_actual"]
    assert legacy_result["CONTRACT-A"]["ga_actual"] == Decimal("80000.00")

def test_regulatory_ga_diverges_from_legacy_when_de_is_nonzero():
    # DE>0이면 기존 함수(DM+DL+OH만)와 신규 함수(DM+DL+OH+DE)의 GA 기준액이
    # 벌어진다 — 이것이 바로 이전 조사에서 지적한 "기존 GA는 규정상 DE를
    # 빠뜨리고 있다"는 구조적 문제를 실제로 보여주는 테스트다.
    actual_by_contract = {"CONTRACT-A": {"actual_manufacturing_cost": Decimal("1000000.00")}}
    budget_by_contract = {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("2000000.00")}}
    contracts_old = [{"contract_no": "CONTRACT-A", "contract_type": "MULTI_PRODUCT"}]

    legacy_result = calculate_ga_by_contract(
        actual_by_contract, budget_by_contract,
        [{"rule_id": "OLD-1", "rate_type": "GA", "contract_type": "MULTI_PRODUCT",
          "rate_pct": "8", "priority": "10"}],
        contracts_old,
    )

    new_result = calculate_regulatory_ga_by_contract(
        actual_by_contract, budget_by_contract,
        {"CONTRACT-A": {"direct_expense_amount": Decimal("500000.00")}},  # DE = 500,000
        {"CONTRACT-A": {"calculable": True, "budget_direct_expense": Decimal("0")}},
        {},
        [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026", rate_pct="8")],
        [_reg_contract("CONTRACT-A", plant_code="PL01", fiscal_year="2026")],
        "EXCLUDE_GFM",
        _REF_DATE,
        _dm_excl_gfm("CONTRACT-A", "1000000.00"),
    )

    legacy_ga = legacy_result["CONTRACT-A"]["ga_actual"]
    new_ga = new_result["CONTRACT-A"]["ga_actual"]
    assert legacy_ga == Decimal("80000.00")       # 1,000,000 x 8%, DE 미반영
    assert new_ga == Decimal("120000.00")         # 1,500,000 x 8%, DE 반영
    # 차이는 정확히 DE x rate 만큼이다.
    assert new_ga - legacy_ga == Decimal("40000.00")


# --- 실제 Phase 2 데이터로 신규 구조도 계산 불가 상태인지 확인 ---

def _load_real_regulatory_ga():
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
    actual_de = calculate_actual_direct_expense_by_contract(
        contracts, work_orders, rows("31_direct_expense.xlsx", "direct_expense"),
    )
    budget_de = calculate_budget_direct_expense_by_contract(
        contracts, rows("34_direct_expense_budget.xlsx", "direct_expense_budget"),
    )
    # 32_cost_rate_rule.xlsx는 저장소에 없다 -> 빈 리스트.
    rate_rules = rows("32_cost_rate_rule.xlsx", "cost_rate_rule")
    # government_furnished_material_by_contract: 외부 입력, 현재 어떤 계약도 데이터 없음.
    gfm_by_contract = {}
    # dm_excluding_gfm_by_contract: 실제 material_issue의 supply_type이 전부
    # None이므로, material_issue가 존재하는 계약은 calculable=False가 된다.
    dm_excluding_gfm_by_contract = calculate_actual_material_cost_excluding_gfm_by_contract(
        contracts, work_orders, rows("22_material_issue.xlsx", "material_issue"),
    )
    # reference_date는 rate_rules가 이미 빈 리스트이므로 어떤 값을 넣어도
    # calculable=False로 남는다 — 실제 GA 적용일을 의미하지 않는 placeholder다.
    return calculate_regulatory_ga_by_contract(
        actual_by_contract, budget_by_contract, actual_de, budget_de,
        gfm_by_contract, rate_rules, contracts, "EXCLUDE_GFM", _REF_DATE,
        dm_excluding_gfm_by_contract,
    )

def test_real_dataset_regulatory_ga_all_contracts_not_calculable():
    # rate rule/관급재료비 실데이터가 전혀 없으므로 신규 구조도 기존과
    # 동일하게 3개 계약 모두 calculable=False여야 한다(0 아님).
    result = _load_real_regulatory_ga()
    if result is None:
        return
    assert set(result.keys()) == {"CONTRACT-001", "CONTRACT-002", "CONTRACT-003"}
    for contract_no in result:
        c = result[contract_no]
        assert c["calculable"] is False
        assert c["ga_actual"] is None
        assert c["reason"] is not None


# --- 추가 경계조건 (2차 검토에서 보강) ---
# 아래 rate_pct/company_size/industry_type 값은 전부 합성 테스트 픽스처이며
# 실제 방산원가 규정 수치가 아니다.

def test_ga_base_amount_negative_and_zero_are_valid_not_rejected():
    # 음수(예: 조정/환입)와 0은 기존 cost_engine 전반의 원칙과 동일하게
    # 거부되지 않고 그대로 합산된다 — None(미계산)과는 다른 상태다.
    assert calculate_ga_base_amount(
        Decimal("1000000.00"), Decimal("-50000.00"), "INCLUDE_GFM"
    ) == Decimal("950000.00")
    assert calculate_ga_base_amount(
        Decimal("1000000.00"), Decimal("0"), "INCLUDE_GFM"
    ) == Decimal("1000000.00")
    assert calculate_ga_base_amount(
        Decimal("-1000000.00"), None, "EXCLUDE_GFM"
    ) == Decimal("-1000000.00")

def test_ga_base_amount_preserves_decimal_precision_without_premature_rounding():
    # 다른 cost_engine 결합 함수(예: calculate_contract_total_cost)와 동일하게,
    # 이미 Decimal인 입력을 더할 때 중간에 임의로 quantize하지 않는다
    # (rate 적용 시점에만 round_amount()를 쓰는 것이 기존 패턴).
    result = calculate_ga_base_amount(
        Decimal("100.015"), Decimal("0.005"), "INCLUDE_GFM"
    )
    assert result == Decimal("100.020")

def test_ga_base_amount_gfm_zero_vs_none_side_by_side():
    # GFM=0(실제로 관급재료비가 0원이라고 확인된 값)과 GFM=None(데이터 자체가
    # 없음)은 명확히 다른 결과를 낸다.
    with_zero_gfm = calculate_ga_base_amount(Decimal("1000000.00"), Decimal("0"), "INCLUDE_GFM")
    with_none_gfm = calculate_ga_base_amount(Decimal("1000000.00"), None, "INCLUDE_GFM")
    assert with_zero_gfm == Decimal("1000000.00")
    assert with_none_gfm is None
    assert with_zero_gfm != with_none_gfm

def test_resolve_ga_actual_rate_zero_percent_distinct_from_not_found():
    rate_rules_with_zero = [_reg_rate_rule(company_code="HB01", plant_code="PL01",
                                            fiscal_year="2026", rate_pct="0")]
    rate_pct, matched = resolve_ga_actual_rate(rate_rules_with_zero, "HB01", "PL01", "2026", _REF_DATE)
    assert rate_pct == Decimal("0")
    assert matched is not None

    rate_pct_missing, matched_missing = resolve_ga_actual_rate([], "HB01", "PL01", "2026", _REF_DATE)
    assert rate_pct_missing is None
    assert matched_missing is None
    assert rate_pct != rate_pct_missing  # 0%와 "없음"은 다른 상태다(둘 다 falsy가 아님을 확인)

def test_resolve_ga_ceiling_rate_zero_percent_distinct_from_not_found():
    rate_rules_with_zero = [_reg_rate_rule(rate_kind="CEILING", industry_type="ASSEMBLY_METAL",
                                            company_size="GENERAL", rate_pct="0")]
    rate_pct, matched = resolve_ga_ceiling_rate(rate_rules_with_zero, "ASSEMBLY_METAL", "GENERAL", _REF_DATE)
    assert rate_pct == Decimal("0")
    assert matched is not None

    rate_pct_missing, matched_missing = resolve_ga_ceiling_rate([], "ASSEMBLY_METAL", "GENERAL", _REF_DATE)
    assert rate_pct_missing is None
    assert matched_missing is None

def test_resolve_ga_actual_rate_ignores_contract_type_field_on_rows():
    # rate rule 행에 contract_type이라는 (이 함수와 무관한) 필드가 섞여 있어도
    # 매칭 결과에 영향을 주지 않는다 — company_code/plant_code/fiscal_year만 본다.
    rate_rules = [
        {**_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026",
                           rate_pct="8"), "contract_type": "PROTOTYPE"},
    ]
    rate_pct, matched = resolve_ga_actual_rate(rate_rules, "HB01", "PL01", "2026", _REF_DATE)
    assert rate_pct == Decimal("8")

def test_resolve_ga_ceiling_rate_ignores_company_code_and_plant_code():
    # company_code/plant_code가 CEILING 행에 붙어 있어도(다른 값이라도)
    # industry_type/company_size만 일치하면 조회된다 — 상한 조회는 회사 단위가
    # 아니다.
    rate_rules = [
        {**_reg_rate_rule(rate_kind="CEILING", industry_type="ASSEMBLY_METAL",
                           company_size="GENERAL", rate_pct="7"),
         "company_code": "SOME-OTHER-COMPANY", "plant_code": "SOME-OTHER-PLANT"},
    ]
    rate_pct, matched = resolve_ga_ceiling_rate(rate_rules, "ASSEMBLY_METAL", "GENERAL", _REF_DATE)
    assert rate_pct == Decimal("7")

def test_resolve_ga_ceiling_rate_ambiguous_when_two_rows_match():
    rate_rules = [
        _reg_rate_rule("CEIL-1", rate_kind="CEILING", industry_type="ASSEMBLY_METAL",
                       company_size="GENERAL", rate_pct="7"),
        _reg_rate_rule("CEIL-2", rate_kind="CEILING", industry_type="ASSEMBLY_METAL",
                       company_size="GENERAL", rate_pct="9"),
    ]
    rate_pct, matched = resolve_ga_ceiling_rate(rate_rules, "ASSEMBLY_METAL", "GENERAL", _REF_DATE)
    assert rate_pct is None
    assert matched is None

def test_resolve_ga_actual_rate_not_confused_by_many_ceiling_rows_in_same_list():
    # 같은 rate_rules 리스트에 CEILING 행이 여러 개 있어도 ACTUAL 조회의
    # 후보 수(모호성 판정)에는 전혀 영향을 주지 않는다.
    rate_rules = [
        _reg_rate_rule("ACT-1", rate_kind="ACTUAL", company_code="HB01", plant_code="PL01",
                       fiscal_year="2026", rate_pct="8"),
        _reg_rate_rule("CEIL-1", rate_kind="CEILING", industry_type="ASSEMBLY_METAL",
                       company_size="GENERAL", rate_pct="7"),
        _reg_rate_rule("CEIL-2", rate_kind="CEILING", industry_type="CHEMICAL",
                       company_size="GENERAL", rate_pct="8"),
        _reg_rate_rule("CEIL-3", rate_kind="CEILING", industry_type="SERVICE",
                       company_size="SME", rate_pct="8"),
    ]
    rate_pct, matched = resolve_ga_actual_rate(rate_rules, "HB01", "PL01", "2026", _REF_DATE)
    assert rate_pct == Decimal("8")
    assert matched["rule_id"] == "ACT-1"

def test_regulatory_ga_actual_de_zero_vs_entirely_absent_both_treated_as_zero():
    # Actual DE는 calculate_actual_direct_expense_by_contract() 자체가 이미
    # 모든 계약을 0으로 pre-seed하므로, "행이 명시적으로 0"인 경우와 "그
    # 계약이 dict에 아예 없는" 경우가 동일하게 0으로 처리되어야 한다(missing과
    # 0을 구분하는 것은 계산 불가 상태가 있는 Budget DE 쪽 이야기이지, 이미
    # 실적 집계가 끝난 Actual DE 쪽은 "없으면 0"이 맞는 값이다).
    common_args = (
        {"CONTRACT-A": {"actual_manufacturing_cost": Decimal("1000000.00")}},
        {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("0")}},
    )
    de_explicit_zero = {"CONTRACT-A": {"direct_expense_amount": Decimal("0")}}
    de_entirely_absent = {}  # 이 계약이 dict에 없음

    budget_de = {"CONTRACT-A": {"calculable": True, "budget_direct_expense": Decimal("0")}}
    rate_rules = [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026", rate_pct="8")]
    contracts = [_reg_contract("CONTRACT-A", plant_code="PL01", fiscal_year="2026")]

    dm_excl = _dm_excl_gfm("CONTRACT-A", "1000000.00")

    result_explicit = calculate_regulatory_ga_by_contract(
        *common_args, de_explicit_zero, budget_de, {}, rate_rules, contracts, "EXCLUDE_GFM",
        _REF_DATE, dm_excl,
    )
    result_absent = calculate_regulatory_ga_by_contract(
        *common_args, de_entirely_absent, budget_de, {}, rate_rules, contracts, "EXCLUDE_GFM",
        _REF_DATE, dm_excl,
    )
    assert result_explicit["CONTRACT-A"]["ga_base_amount_actual"] == Decimal("1000000.00")
    assert result_absent["CONTRACT-A"]["ga_base_amount_actual"] == Decimal("1000000.00")
    assert result_explicit["CONTRACT-A"]["ga_actual"] == result_absent["CONTRACT-A"]["ga_actual"]

def test_regulatory_ga_budget_de_entirely_missing_vs_explicit_not_calculable_both_none():
    # Budget DE는 (Actual DE와 반대로) "없음"과 "calculable=False"가 같은
    # 의미(계산 불가)이지 0이 아니다 — 둘 다 예산 기준액을 None으로 만든다.
    common_args = (
        {"CONTRACT-A": {"actual_manufacturing_cost": Decimal("1000000.00")}},
        {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("2000000.00")}},
        {"CONTRACT-A": {"direct_expense_amount": Decimal("0")}},
    )
    rate_rules = [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026", rate_pct="8")]
    contracts = [_reg_contract("CONTRACT-A", plant_code="PL01", fiscal_year="2026")]

    dm_excl = _dm_excl_gfm("CONTRACT-A", "1000000.00")

    result_missing = calculate_regulatory_ga_by_contract(
        *common_args, {}, {}, rate_rules, contracts, "EXCLUDE_GFM", _REF_DATE,  # budget_de dict 자체가 비어있음
        dm_excl,
    )
    result_explicit_false = calculate_regulatory_ga_by_contract(
        *common_args,
        {"CONTRACT-A": {"calculable": False, "budget_direct_expense": None,
                         "reason": "[TEST FIXTURE] 없음"}},
        {}, rate_rules, contracts, "EXCLUDE_GFM", _REF_DATE, dm_excl,
    )
    assert result_missing["CONTRACT-A"]["ga_base_amount_budget"] is None
    assert result_explicit_false["CONTRACT-A"]["ga_base_amount_budget"] is None
    assert result_missing["CONTRACT-A"]["ga_budget"] is None
    assert result_explicit_false["CONTRACT-A"]["ga_budget"] is None

def test_regulatory_ga_budget_de_calculable_true_with_zero_amount_is_valid_base():
    # Budget DE가 "calculable=True, 금액=0"으로 명시된 경우는 계산 불가가
    # 아니라 정상적으로 0을 더한 유효한 기준액이 되어야 한다.
    result = calculate_regulatory_ga_by_contract(
        {"CONTRACT-A": {"actual_manufacturing_cost": Decimal("1000000.00")}},
        {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("2000000.00")}},
        {"CONTRACT-A": {"direct_expense_amount": Decimal("0")}},
        {"CONTRACT-A": {"calculable": True, "budget_direct_expense": Decimal("0")}},
        {},
        [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026", rate_pct="8")],
        [_reg_contract("CONTRACT-A", plant_code="PL01", fiscal_year="2026")],
        "EXCLUDE_GFM",
        _REF_DATE,
        _dm_excl_gfm("CONTRACT-A", "1000000.00"),
    )
    c = result["CONTRACT-A"]
    assert c["ga_base_amount_budget"] == Decimal("2000000.00")
    assert c["ga_budget"] == Decimal("160000.00")
    assert c["ga_variance"] is not None

def test_regulatory_ga_government_furnished_material_zero_vs_missing_under_include_basis():
    # 오케스트레이터 수준에서도 GFM=0(명시적으로 확인된 관급재료비 0원)과
    # GFM 자체가 dict에 없는 경우(데이터 미확보)를 구분해야 한다.
    common_args = (
        {"CONTRACT-A": {"actual_manufacturing_cost": Decimal("1000000.00")}},
        {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("0")}},
        {"CONTRACT-A": {"direct_expense_amount": Decimal("0")}},
        {"CONTRACT-A": {"calculable": True, "budget_direct_expense": Decimal("0")}},
    )
    rate_rules = [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026", rate_pct="8")]
    contracts = [_reg_contract("CONTRACT-A", plant_code="PL01", fiscal_year="2026")]

    dm_excl = _dm_excl_gfm("CONTRACT-A", "1000000.00")

    result_zero_gfm = calculate_regulatory_ga_by_contract(
        *common_args, {"CONTRACT-A": Decimal("0")}, rate_rules, contracts, "INCLUDE_GFM",
        _REF_DATE, dm_excl,
    )
    result_missing_gfm = calculate_regulatory_ga_by_contract(
        *common_args, {}, rate_rules, contracts, "INCLUDE_GFM", _REF_DATE, dm_excl,
    )
    assert result_zero_gfm["CONTRACT-A"]["calculable"] is True
    assert result_zero_gfm["CONTRACT-A"]["ga_base_amount_actual"] == Decimal("1000000.00")
    assert result_missing_gfm["CONTRACT-A"]["calculable"] is False
    assert result_missing_gfm["CONTRACT-A"]["ga_base_amount_actual"] is None

def test_regulatory_ga_exceeds_ceiling_is_false_when_actual_rate_within_ceiling():
    # exceeds_ceiling 플래그의 대조군: 실적요율이 상한보다 낮거나 같으면 False.
    result = calculate_regulatory_ga_by_contract(
        {"CONTRACT-A": {"actual_manufacturing_cost": Decimal("1000000.00")}},
        {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("0")}},
        {"CONTRACT-A": {"direct_expense_amount": Decimal("0")}},
        {"CONTRACT-A": {"calculable": True, "budget_direct_expense": Decimal("0")}},
        {},
        [
            _reg_rate_rule("RATE-ACT", rate_kind="ACTUAL", company_code="HB01",
                           plant_code="PL01", fiscal_year="2026", rate_pct="5"),
            _reg_rate_rule("RATE-CEIL", rate_kind="CEILING", industry_type="ASSEMBLY_METAL",
                           company_size="GENERAL", rate_pct="7"),
        ],
        [_reg_contract("CONTRACT-A", plant_code="PL01", fiscal_year="2026",
                        industry_type="ASSEMBLY_METAL", company_size="GENERAL")],
        "EXCLUDE_GFM",
        _REF_DATE,
        _dm_excl_gfm("CONTRACT-A", "1000000.00"),
    )
    assert result["CONTRACT-A"]["exceeds_ceiling"] is False
    assert result["CONTRACT-A"]["ga_actual"] == Decimal("50000.00")

def test_regulatory_ga_uses_shared_reference_date_for_actual_and_budget_rate_lookup():
    # calculate_regulatory_ga_by_contract()는 actual/budget 양쪽에 별도의
    # reference_date를 받지 않고 단일 reference_date를 공유한다(§구현 근거
    # 참고) — 기준일이 rate rule의 유효기간 밖이면 Actual/Budget 모두 함께
    # calculable=False가 되어야 한다(한쪽만 계산되는 일이 없어야 한다).
    rate_rules = [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026",
                                  rate_pct="8", effective_from="2026-01-01", effective_to="2026-06-30")]
    contracts = [_reg_contract("CONTRACT-A", plant_code="PL01", fiscal_year="2026")]

    dm_excl = _dm_excl_gfm("CONTRACT-A", "1000000.00")

    result_in_range = calculate_regulatory_ga_by_contract(
        {"CONTRACT-A": {"actual_manufacturing_cost": Decimal("1000000.00")}},
        {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("2000000.00")}},
        {"CONTRACT-A": {"direct_expense_amount": Decimal("0")}},
        {"CONTRACT-A": {"calculable": True, "budget_direct_expense": Decimal("0")}},
        {}, rate_rules, contracts, "EXCLUDE_GFM", "2026-03-01", dm_excl,
    )
    result_out_of_range = calculate_regulatory_ga_by_contract(
        {"CONTRACT-A": {"actual_manufacturing_cost": Decimal("1000000.00")}},
        {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("2000000.00")}},
        {"CONTRACT-A": {"direct_expense_amount": Decimal("0")}},
        {"CONTRACT-A": {"calculable": True, "budget_direct_expense": Decimal("0")}},
        {}, rate_rules, contracts, "EXCLUDE_GFM", "2026-09-01", dm_excl,
    )
    assert result_in_range["CONTRACT-A"]["calculable"] is True
    assert result_in_range["CONTRACT-A"]["ga_actual"] == Decimal("80000.00")
    assert result_in_range["CONTRACT-A"]["ga_budget"] == Decimal("160000.00")
    assert result_out_of_range["CONTRACT-A"]["calculable"] is False
    assert result_out_of_range["CONTRACT-A"]["ga_actual"] is None
    assert result_out_of_range["CONTRACT-A"]["ga_budget"] is None


# --- calculate_regulatory_ga_by_contract: dm_excluding_gfm_by_contract 연결 ---
#
# 이 구획은 신설한 dm_excluding_gfm_by_contract 파라미터가 오케스트레이터
# 안에서 실제로 이중집계 없이 동작하는지, GFM/DM 계산이 서로 올바르게
# 분리·재조합되는지를 검증한다. 아래 금액은 전부 합성 테스트 픽스처다.

def test_regulatory_ga_gfm_excluded_from_actual_base_when_company_and_government_mixed():
    # DM excluding GFM(=COMPANY만, 1000) + DL(200) + OH(300) + DE(100) = 1600.
    # EXCLUDE_GFM 기준에서는 GFM(500)이 전혀 더해지지 않아야 한다 — 관급재료비가
    # 섞여 있어도(별도 government_furnished_material_by_contract로 존재)
    # Actual 기준액에서 제외된 상태를 유지해야 한다.
    actual_by_contract = {
        "CONTRACT-A": {"actual_labor_cost": Decimal("200"), "actual_overhead_cost": Decimal("300")},
    }
    result = calculate_regulatory_ga_by_contract(
        actual_by_contract,
        {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("0")}},
        {"CONTRACT-A": {"direct_expense_amount": Decimal("100")}},
        {"CONTRACT-A": {"calculable": True, "budget_direct_expense": Decimal("0")}},
        {"CONTRACT-A": Decimal("500")},  # government_furnished_material_by_contract
        [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026", rate_pct="10")],
        [_reg_contract("CONTRACT-A", plant_code="PL01", fiscal_year="2026")],
        "EXCLUDE_GFM",
        _REF_DATE,
        _dm_excl_gfm("CONTRACT-A", "1000"),
    )
    c = result["CONTRACT-A"]
    assert c["manufacturing_cost_excluding_government_material_actual"] == Decimal("1600")
    assert c["ga_base_amount_actual"] == Decimal("1600")  # 500(GFM)이 포함되지 않음

def test_regulatory_ga_include_gfm_adds_gfm_exactly_once_no_double_counting():
    # 같은 구성에서 INCLUDE_GFM이면 GFM(500)이 정확히 한 번만 더해져야 한다
    # (1600 + 500 = 2100) — dm_excluding_gfm이 이미 관급재료비를 제외한
    # 값이므로, 관급분이 이미 섞여 있는 상태에서 또 더하는 이중집계가
    # 일어나지 않는다는 것을 오케스트레이터 수준에서 확인한다.
    actual_by_contract = {
        "CONTRACT-A": {"actual_labor_cost": Decimal("200"), "actual_overhead_cost": Decimal("300")},
    }
    result = calculate_regulatory_ga_by_contract(
        actual_by_contract,
        {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("0")}},
        {"CONTRACT-A": {"direct_expense_amount": Decimal("100")}},
        {"CONTRACT-A": {"calculable": True, "budget_direct_expense": Decimal("0")}},
        {"CONTRACT-A": Decimal("500")},
        [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026", rate_pct="10")],
        [_reg_contract("CONTRACT-A", plant_code="PL01", fiscal_year="2026")],
        "INCLUDE_GFM",
        _REF_DATE,
        _dm_excl_gfm("CONTRACT-A", "1000"),
    )
    c = result["CONTRACT-A"]
    assert c["ga_base_amount_actual"] == Decimal("2100")  # 1600 + 500, 딱 한 번만 더해짐

def test_regulatory_ga_dm_excluding_gfm_and_gfm_reconstruct_original_total_via_real_functions():
    # 실제 calculate_actual_material_cost_excluding_gfm_by_contract()와
    # calculate_government_furnished_material_by_contract()를 그대로 호출해
    # (합성 material_issue 기준) 얻은 두 결과를 오케스트레이터에 넣었을 때도
    # "DM excluding GFM + GFM = 원래 전체 재료비"라는 항등식이 orchestrator
    # 안에서도 깨지지 않는지 확인한다.
    contracts_ga = [_reg_contract("CONTRACT-A", plant_code="PL01", fiscal_year="2026")]
    work_orders = [{"wo_no": "WO-1", "contract_no": "CONTRACT-A"}]
    material_issues = [
        _issue("WO-1", issued_qty="10", unit_cost="100", supply_type="GOVERNMENT"),
        _issue("WO-1", issued_qty="5", unit_cost="200", supply_type="COMPANY"),
    ]
    dm_excl_by_contract = calculate_actual_material_cost_excluding_gfm_by_contract(
        contracts_ga, work_orders, material_issues,
    )
    gfm_by_contract_raw = calculate_government_furnished_material_by_contract(
        contracts_ga, work_orders, material_issues,
    )
    gfm_by_contract = {"CONTRACT-A": gfm_by_contract_raw["CONTRACT-A"]["gfm_amount"]}

    total_material_cost = calculate_actual_material_cost(
        [{"wo_no": "WO-1", "product_code": "P-100", "period_key": "2026-07"}],
        material_issues, [_material()], [_product()],
    )["WO-1"]

    result = calculate_regulatory_ga_by_contract(
        {"CONTRACT-A": {}},
        {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("0")}},
        {"CONTRACT-A": {"direct_expense_amount": Decimal("0")}},
        {"CONTRACT-A": {"calculable": True, "budget_direct_expense": Decimal("0")}},
        gfm_by_contract,
        [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026", rate_pct="10")],
        contracts_ga,
        "INCLUDE_GFM",
        _REF_DATE,
        dm_excl_by_contract,
    )
    assert total_material_cost == Decimal("2000.00")  # 10x100(GOV) + 5x200(COMPANY)
    assert result["CONTRACT-A"]["ga_base_amount_actual"] == total_material_cost

def test_regulatory_ga_dm_excluding_gfm_none_makes_actual_ga_not_calculable():
    result = calculate_regulatory_ga_by_contract(
        {"CONTRACT-A": {"actual_labor_cost": Decimal("200"), "actual_overhead_cost": Decimal("300")}},
        {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("2000000.00")}},
        {"CONTRACT-A": {"direct_expense_amount": Decimal("100")}},
        {"CONTRACT-A": {"calculable": True, "budget_direct_expense": Decimal("0")}},
        {},
        [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026", rate_pct="8")],
        [_reg_contract("CONTRACT-A", plant_code="PL01", fiscal_year="2026")],
        "EXCLUDE_GFM",
        _REF_DATE,
        {"CONTRACT-A": {"dm_excluding_gfm": None}},  # 관급/사급 미분류로 계산 불가
    )
    c = result["CONTRACT-A"]
    assert c["manufacturing_cost_excluding_government_material_actual"] is None
    assert c["ga_base_amount_actual"] is None
    assert c["calculable"] is False
    assert c["ga_actual"] is None
    assert c["reason"] is not None

def test_regulatory_ga_de_added_exactly_once_not_missing_not_doubled():
    result = calculate_regulatory_ga_by_contract(
        {"CONTRACT-A": {}},  # actual_labor_cost/actual_overhead_cost 없음 -> 0
        {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("0")}},
        {"CONTRACT-A": {"direct_expense_amount": Decimal("300")}},
        {"CONTRACT-A": {"calculable": True, "budget_direct_expense": Decimal("0")}},
        {},
        [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026", rate_pct="10")],
        [_reg_contract("CONTRACT-A", plant_code="PL01", fiscal_year="2026")],
        "EXCLUDE_GFM",
        _REF_DATE,
        _dm_excl_gfm("CONTRACT-A", "1000"),
    )
    c = result["CONTRACT-A"]
    # 1000(DM) + 0(DL) + 0(OH) + 300(DE) = 1300 — DE가 누락(1000)되거나
    # 두 번 더해지지(1600) 않았다.
    assert c["ga_base_amount_actual"] == Decimal("1300")

def test_regulatory_ga_gfm_zero_vs_missing_distinction_preserved_with_new_dm_input():
    # dm_excluding_gfm_by_contract가 새로 추가된 뒤에도, GFM=0(확인된 0원)과
    # GFM 자체가 없는 경우(dict에 항목 없음)의 구분이 여전히 유지되는지
    # 재확인한다.
    common_args = (
        {"CONTRACT-A": {}},
        {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("0")}},
        {"CONTRACT-A": {"direct_expense_amount": Decimal("0")}},
        {"CONTRACT-A": {"calculable": True, "budget_direct_expense": Decimal("0")}},
    )
    rate_rules = [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026", rate_pct="8")]
    contracts = [_reg_contract("CONTRACT-A", plant_code="PL01", fiscal_year="2026")]
    dm_excl = _dm_excl_gfm("CONTRACT-A", "1000")

    result_zero_gfm = calculate_regulatory_ga_by_contract(
        *common_args, {"CONTRACT-A": Decimal("0")}, rate_rules, contracts, "INCLUDE_GFM",
        _REF_DATE, dm_excl,
    )
    result_missing_gfm = calculate_regulatory_ga_by_contract(
        *common_args, {}, rate_rules, contracts, "INCLUDE_GFM", _REF_DATE, dm_excl,
    )
    assert result_zero_gfm["CONTRACT-A"]["calculable"] is True
    assert result_zero_gfm["CONTRACT-A"]["ga_base_amount_actual"] == Decimal("1000")
    assert result_missing_gfm["CONTRACT-A"]["calculable"] is False
    assert result_missing_gfm["CONTRACT-A"]["ga_base_amount_actual"] is None

def test_regulatory_ga_include_gfm_budget_side_double_counts_when_gfm_not_separable():
    # [알려진 위험을 재현·고정하는 테스트 — 현재 동작을 "정상 계산"으로
    # 승인하는 것이 아니다]
    #
    # Actual 쪽은 dm_excluding_gfm_by_contract가 실제로 관급재료비를 제외한
    # 값이라서 INCLUDE_GFM basis에서 gfm을 한 번 더하는 것이 올바르게
    # 성립한다(§test_regulatory_ga_include_gfm_adds_gfm_exactly_once_
    # no_double_counting). 하지만 Budget 쪽 budget_manufacturing_cost는
    # 12_standard_cost.xlsx에 supply_type 개념이 없어 관급/사급이 전혀
    # 분리되지 않은 값이다 — 즉 그 안에 관급재료비가 이미 포함되어 있을
    # 가능성을 배제할 수 없다. 그런데 calculate_regulatory_ga_by_contract()는
    # ga_base_amount_budget을 계산할 때도 basis와 무관하게 동일한
    # calculate_ga_base_amount() 경로를 타므로, INCLUDE_GFM이면 이미
    # 관급분이 섞여 있을 수 있는 budget_manufacturing_cost 위에 gfm을 또
    # 더한다.
    #
    # 이 테스트의 목적은 그 위험을 "여기서 실제로 재현되는지" 고정해 두는
    # 것이다 — budget_manufacturing_cost > 0, gfm > 0, calculation_basis=
    # INCLUDE_GFM인 지금 조건에서 결과는 (budget_manufacturing_cost +
    # budget_direct_expense + gfm)이 그대로 나온다. Budget 쪽 재료비에서
    # 관급분을 신뢰성 있게 분리할 데이터/로직(Budget GFM 분리, 여전히
    # 미구현)이 확보되면 이 assert는 반드시 바뀌어야 한다 — 지금 이 값을
    # "규정상 유효한 계산 결과"로 쓰면 안 된다는 경고로 이 테스트를 남겨
    # 둔다.
    result = calculate_regulatory_ga_by_contract(
        {"CONTRACT-A": {}},
        {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("5000")}},
        {"CONTRACT-A": {"direct_expense_amount": Decimal("0")}},
        {"CONTRACT-A": {"calculable": True, "budget_direct_expense": Decimal("0")}},
        {"CONTRACT-A": Decimal("500")},
        [_reg_rate_rule(company_code="HB01", plant_code="PL01", fiscal_year="2026", rate_pct="8")],
        [_reg_contract("CONTRACT-A", plant_code="PL01", fiscal_year="2026")],
        "INCLUDE_GFM",
        _REF_DATE,
        _dm_excl_gfm("CONTRACT-A", "1000"),
    )
    c = result["CONTRACT-A"]
    # budget_manufacturing_cost(5000, 관급 포함 여부 불명) + budget_de(0) +
    # gfm(500) = 5500 — budget_manufacturing_cost가 이미 그 500을 포함하고
    # 있다면 이 5500은 실제보다 500만큼 과대계산된 위험한 값이다.
    assert c["ga_base_amount_budget"] == Decimal("5500")

def test_legacy_calculate_ga_by_contract_result_unchanged_by_regulatory_function_changes():
    # calculate_ga_by_contract()(보호 함수)는 dm_excluding_gfm_by_contract
    # 파라미터 추가와 완전히 무관하다 — 이 회귀 테스트가 통과한다는 것은
    # 레거시 함수의 결과가 이번 변경으로 전혀 달라지지 않았다는 뜻이다.
    actual_by_contract = {"CONTRACT-A": {"actual_manufacturing_cost": Decimal("1000000.00")}}
    budget_by_contract = {"CONTRACT-A": {"budget_manufacturing_cost": Decimal("2000000.00")}}
    contracts_old = [{"contract_no": "CONTRACT-A", "contract_type": "MULTI_PRODUCT"}]

    result = calculate_ga_by_contract(
        actual_by_contract, budget_by_contract,
        [{"rule_id": "OLD-1", "rate_type": "GA", "contract_type": "MULTI_PRODUCT",
          "rate_pct": "8", "priority": "10"}],
        contracts_old,
    )
    c = result["CONTRACT-A"]
    assert c["calculable"] is True
    assert c["ga_rate"] == Decimal("8")
    assert c["ga_actual"] == Decimal("80000.00")
    assert c["ga_budget"] == Decimal("160000.00")
    assert c["ga_variance"] == Decimal("-80000.00")


# --- calculate_government_furnished_material_by_contract (Phase 2 9단계) ---
#
# 22_material_issue.xlsx에 이번 단계에서 추가한 supply_type 컬럼(관급/사급
# 구분)을 소비하는 결합형 함수. 아래 supply_type/issue_type 값은 전부
# 합성 테스트 픽스처이며 실제 관급재료비 수치가 아니다.

def _gfm_contract(contract_no="CONTRACT-A"):
    return {"contract_no": contract_no}

def _gfm_wo(wo_no="WO-1", contract_no="CONTRACT-A"):
    return {"wo_no": wo_no, "contract_no": contract_no}

def _gfm_issue(wo_no="WO-1", supply_type=None, issued_qty="10", unit_cost="100",
               issue_type="ISSUE"):
    return {
        "wo_no": wo_no, "supply_type": supply_type,
        "issued_qty": issued_qty, "unit_cost": unit_cost, "issue_type": issue_type,
    }

def test_gfm_seeds_all_contracts_from_master():
    result = calculate_government_furnished_material_by_contract(
        [_gfm_contract("CONTRACT-A"), _gfm_contract("CONTRACT-EMPTY")], [], [],
    )
    assert set(result.keys()) == {"CONTRACT-A", "CONTRACT-EMPTY"}
    for entry in result.values():
        assert entry["calculable"] is True
        assert entry["gfm_amount"] == Decimal("0")

def test_gfm_sums_government_tagged_rows_only():
    result = calculate_government_furnished_material_by_contract(
        [_gfm_contract("CONTRACT-A")],
        [_gfm_wo("WO-1", "CONTRACT-A")],
        [
            _gfm_issue("WO-1", supply_type="GOVERNMENT", issued_qty="10", unit_cost="100"),
            _gfm_issue("WO-1", supply_type="COMPANY", issued_qty="5", unit_cost="1000"),
        ],
    )
    entry = result["CONTRACT-A"]
    assert entry["calculable"] is True
    assert entry["gfm_amount"] == Decimal("1000.00")  # 10 x 100, COMPANY 행은 미포함
    assert entry["government_issue_count"] == 1

def test_gfm_untagged_row_makes_contract_not_calculable():
    result = calculate_government_furnished_material_by_contract(
        [_gfm_contract("CONTRACT-A")],
        [_gfm_wo("WO-1", "CONTRACT-A")],
        [_gfm_issue("WO-1", supply_type=None, issued_qty="10", unit_cost="100")],
    )
    entry = result["CONTRACT-A"]
    assert entry["calculable"] is False
    assert entry["gfm_amount"] is None
    assert entry["untagged_issue_count"] == 1
    assert entry["reason"] is not None

def test_gfm_return_issue_type_subtracts():
    result = calculate_government_furnished_material_by_contract(
        [_gfm_contract("CONTRACT-A")],
        [_gfm_wo("WO-1", "CONTRACT-A")],
        [
            _gfm_issue("WO-1", supply_type="GOVERNMENT", issued_qty="10", unit_cost="100",
                       issue_type="ISSUE"),
            _gfm_issue("WO-1", supply_type="GOVERNMENT", issued_qty="3", unit_cost="100",
                       issue_type="RETURN"),
        ],
    )
    entry = result["CONTRACT-A"]
    assert entry["calculable"] is True
    assert entry["gfm_amount"] == Decimal("700.00")  # (10 - 3) x 100

def test_gfm_company_tagged_rows_do_not_affect_calculable():
    result = calculate_government_furnished_material_by_contract(
        [_gfm_contract("CONTRACT-A")],
        [_gfm_wo("WO-1", "CONTRACT-A")],
        [_gfm_issue("WO-1", supply_type="COMPANY", issued_qty="10", unit_cost="100")],
    )
    entry = result["CONTRACT-A"]
    assert entry["calculable"] is True
    assert entry["gfm_amount"] == Decimal("0")

def test_gfm_mixed_untagged_and_government_still_not_calculable():
    # 같은 계약에 GOVERNMENT로 분류된 행이 있어도, 다른 행이 미분류(None)라면
    # 그 미분류 행이 실제로 관급인지 알 수 없으므로 계약 전체가 계산 불가다 —
    # GOVERNMENT 행만 부분적으로 합산해서 반환하지 않는다.
    result = calculate_government_furnished_material_by_contract(
        [_gfm_contract("CONTRACT-A")],
        [_gfm_wo("WO-1", "CONTRACT-A"), _gfm_wo("WO-2", "CONTRACT-A")],
        [
            _gfm_issue("WO-1", supply_type="GOVERNMENT", issued_qty="10", unit_cost="100"),
            _gfm_issue("WO-2", supply_type=None, issued_qty="5", unit_cost="50"),
        ],
    )
    entry = result["CONTRACT-A"]
    assert entry["calculable"] is False
    assert entry["gfm_amount"] is None
    assert entry["untagged_issue_count"] == 1

def test_gfm_unassigned_wo_or_missing_contract_skipped_silently():
    # wo_no가 work_orders에 없는 행, 그리고 wo_no는 있지만 그 WO의
    # contract_no가 contracts 마스터에 없는 경우 모두 조용히 제외된다
    # (계약 미배정 WO의 경비를 skip하는 기존 direct_expense 정책과 동일).
    result = calculate_government_furnished_material_by_contract(
        [_gfm_contract("CONTRACT-A")],
        [_gfm_wo("WO-UNKNOWN-CONTRACT", "CONTRACT-NOT-IN-MASTER")],
        [
            _gfm_issue("WO-NOT-A-REAL-WO", supply_type="GOVERNMENT"),
            _gfm_issue("WO-UNKNOWN-CONTRACT", supply_type="GOVERNMENT"),
        ],
    )
    entry = result["CONTRACT-A"]
    assert entry["calculable"] is True
    assert entry["gfm_amount"] == Decimal("0")
    assert entry["government_issue_count"] == 0

def test_gfm_does_not_mutate_inputs():
    contracts = [_gfm_contract("CONTRACT-A")]
    work_orders = [_gfm_wo("WO-1", "CONTRACT-A")]
    material_issues = [_gfm_issue("WO-1", supply_type="GOVERNMENT")]

    import copy
    contracts_before = copy.deepcopy(contracts)
    work_orders_before = copy.deepcopy(work_orders)
    material_issues_before = copy.deepcopy(material_issues)

    calculate_government_furnished_material_by_contract(
        contracts, work_orders, material_issues,
    )

    assert contracts == contracts_before
    assert work_orders == work_orders_before
    assert material_issues == material_issues_before

def test_real_dataset_gfm_not_calculable_where_material_issues_exist():
    # 실제 22_material_issue.xlsx에는 supply_type 값이 전혀 없으므로(스키마만
    # 추가), material_issue 행이 실제로 존재하는 계약은 전부 calculable=False
    # 여야 한다. 반면 material_issue 행이 하나도 없는 계약은(예:
    # CONTRACT-003 — 실적 자체가 0인 계약) "관급 여부를 알 수 없음"이 아니라
    # "발생한 재료가 아예 없음"이므로 정당하게 calculable=True, gfm_amount=0
    # 이다 — 이것은 계산 불가가 아니라 실제로 계산된 0이다.
    import sys
    from pathlib import Path
    sys.path.insert(0, "src")
    from manufacturing_cost_engine.loader import load_dataset

    dataset = Path("hanbit_mvp_dataset_phase1")
    if not dataset.exists():
        return

    data = load_dataset(dataset)

    def rows(file, sheet):
        return data.get(f"{file}::{sheet}", [])

    contracts = rows("30_contract.xlsx", "contract")
    work_orders = rows("20_work_order.xlsx", "work_order")
    material_issues = rows("22_material_issue.xlsx", "material_issue")

    result = calculate_government_furnished_material_by_contract(
        contracts, work_orders, material_issues,
    )

    assert set(result.keys()) == {"CONTRACT-001", "CONTRACT-002", "CONTRACT-003"}

    for contract_no in ("CONTRACT-001", "CONTRACT-002"):
        entry = result[contract_no]
        assert entry["calculable"] is False
        assert entry["gfm_amount"] is None
        assert entry["untagged_issue_count"] > 0
        assert entry["reason"] is not None

    contract_003 = result["CONTRACT-003"]
    assert contract_003["calculable"] is True
    assert contract_003["gfm_amount"] == Decimal("0")
    assert contract_003["untagged_issue_count"] == 0


# --- Phase 2 GA 규정 정합 구조: 코드 레벨 안전장치 회귀 테스트 ---
#
# 아래 2개 테스트는 실 데이터를 전혀 요구하지 않는 순수 코드 검증이다.
# GA 규정 정합 함수들이 (1) 아직 CLI에 연결되지 않았다는 것과, (2)
# reference_date를 계약의 특정 날짜 필드에서 스스로 만들어내지 않는다는
# 것은 지금까지 docstring 설명과 사람의 리뷰에만 의존해 왔다 — 이 두
# 테스트는 그 두 가지를 회귀로 고정한다.

def test_cli_does_not_import_or_call_regulatory_ga_functions():
    # calculate_regulatory_ga_by_contract 등 GA 규정 정합 함수는 아직
    # 준비 단계 코드이며 CLI에 연결하지 않기로 결정되어 있다(README.md에도
    # "아직 CLI에는 연결되지 않은 준비 단계 코드"로 명시됨). 누군가 실수로
    # cli.py에 import나 호출을 추가하면 이 테스트가 즉시 실패한다.
    #
    # 기존 legacy 함수(calculate_ga_by_contract, calculate_contract_total_cost
    # 등)가 cli.py에 연결되어 있는 것은 그대로 유지되어야 하며, 이 테스트는
    # 그 연결을 검사 대상으로 삼지 않는다 — 아래 5개 규정 정합 함수만
    # 검사한다.
    import inspect
    from manufacturing_cost_engine import cli

    source = inspect.getsource(cli)

    for name in (
        "calculate_regulatory_ga_by_contract",
        "resolve_ga_actual_rate",
        "resolve_ga_ceiling_rate",
        "calculate_government_furnished_material_by_contract",
        "calculate_actual_material_cost_excluding_gfm_by_contract",
    ):
        assert name not in source


def test_regulatory_ga_functions_do_not_read_start_end_or_agreement_date_fields():
    # resolve_ga_actual_rate/resolve_ga_ceiling_rate/
    # calculate_regulatory_ga_by_contract의 실행 코드가 contract.start_date/
    # end_date/contract_agreement_date를 reference_date 대신 읽지 않는다는
    # 것을 고정한다. 이 세 필드를 쓰지 않기로 한 결정은 조사로 이미 확인됐다
    # (방산원가규칙 제28조·시행세칙 제32조가 구분하는 4가지 법정 기준일 중
    # 어느 것도 이 필드명과 문언상 일치하지 않고, 30_contract.xlsx의
    # start_date/end_date가 실제로 무엇을 의미하는지도 미확인이다) — 하지만
    # 지금까지 이를 잠그는 회귀 테스트는 없었다.
    #
    # 세 함수의 docstring 프로즈 안에는 이 필드들을 실제 코드 문법처럼
    # 인용부호로 감싸 설명하는 문장이 존재한다(예: "...contract.get(
    # \"start_date\") 등을 내부에서 임의로 쓰지 않음..." — 이 문장 자체가
    # "쓰지 않는다"는 서술이라 docstring을 그대로 검사하면 오탐한다). 그래서
    # fn.__doc__로 docstring 문자열을 소스에서 먼저 제거한 뒤, 남은 실행
    # 코드에만 `"start_date"`처럼 인용부호를 포함한 딕셔너리 키 접근 패턴이
    # 있는지 확인한다 — docstring 안의 백틱(`contract.start_date`) 표기나
    # 일반 서술은 이 패턴과 겹치지 않는다
    # (test_contract_type_is_product_structure_axis_not_legal_pricing_method()
    # 에서 이미 검증해 쓰고 있는 것과 동일한 기법).
    import inspect
    from manufacturing_cost_engine import cost_engine as ce

    forbidden_fields = ("start_date", "end_date", "contract_agreement_date")

    for fn in (
        ce.resolve_ga_actual_rate,
        ce.resolve_ga_ceiling_rate,
        ce.calculate_regulatory_ga_by_contract,
    ):
        source = inspect.getsource(fn)
        code_only = source.replace(fn.__doc__, "", 1) if fn.__doc__ else source
        for field in forbidden_fields:
            assert f'"{field}"' not in code_only
