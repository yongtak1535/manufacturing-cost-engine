from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


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


def _strict_decimal(value):
    """to_decimal()과 달리 None/파싱불가 값은 None으로 반환한다(누락과 0을 구분)."""
    if isinstance(value, Decimal):
        return value

    if value is None:
        return None

    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _valid_work_order_nos(work_orders, products):
    """product_code가 product master에 등록된 실제 WO만 원가 귀속 대상으로 본다."""
    product_codes = {p.get("product_code") for p in products}

    return {
        w.get("wo_no") for w in work_orders
        if w.get("wo_no") is not None and w.get("product_code") in product_codes
    }


def calculate_actual_material_cost(
    work_orders,
    material_issues,
    materials,
    products,
) -> dict[str, Decimal]:
    """
    Phase 1 Actual DM: wo_no별 Σ(issued_qty × unit_cost), ISSUE는 더하고 RETURN은 뺀다(순액).

    다음 material_issue 행은 원가 귀속이 불가능하므로 합계에서 제외한다:
      - wo_no가 없거나, work_order/product master에서 확인되지 않는 WO
      - material_code가 material master에 없는 자재
      - issued_qty 또는 unit_cost가 숫자로 변환되지 않는 행
    """
    valid_wo_nos = _valid_work_order_nos(work_orders, products)
    material_codes = {m.get("material_code") for m in materials}

    totals: dict[str, Decimal] = {}

    for r in material_issues:
        wo_no = r.get("wo_no")
        if wo_no not in valid_wo_nos:
            continue

        if r.get("material_code") not in material_codes:
            continue

        qty = _strict_decimal(r.get("issued_qty"))
        unit_cost = _strict_decimal(r.get("unit_cost"))
        if qty is None or unit_cost is None:
            continue

        line_amount = calculate_material_cost(qty, unit_cost)
        if r.get("issue_type") == "RETURN":
            line_amount = -line_amount

        totals[wo_no] = totals.get(wo_no, Decimal("0")) + line_amount

    return totals


def calculate_actual_labor_cost(
    work_orders,
    labor_transactions,
    products,
) -> dict[str, Decimal]:
    """
    Phase 1 Actual DL: 유효한 DIRECT labor transaction의 wo_no별 amount 합산.

    다음 labor_transaction 행은 제외한다:
      - direct_indirect != DIRECT
      - wo_no가 없거나, work_order/product master에서 확인되지 않는 WO
      - actual_hours 또는 actual_rate 또는 amount가 숫자로 변환되지 않는 행
      - actual_hours < 0
      - actual_rate <= 0 (0은 실제 무급노동이 아니라 임률 결측을 뜻하므로 제외)

    routing 대사 실패(UNKNOWN_ROUTING_OPERATION), operation_code 불일치,
    시간 합계 불일치(HOURS_SUM_MISMATCH) 등 참조/일관성 오류는 hours·rate 자체가
    유효하면 제외하지 않는다 — work_center_code가 행에 직접 존재해 OH 귀속에
    영향이 없고, 실제 발생한 노무비 금액 자체는 유효하기 때문이다.
    """
    valid_wo_nos = _valid_work_order_nos(work_orders, products)

    totals: dict[str, Decimal] = {}

    for r in labor_transactions:
        wo_no = r.get("wo_no")
        if wo_no not in valid_wo_nos:
            continue

        if r.get("direct_indirect") != "DIRECT":
            continue

        hours = _strict_decimal(r.get("actual_hours"))
        rate = _strict_decimal(r.get("actual_rate"))
        amount = _strict_decimal(r.get("amount"))
        if hours is None or rate is None or amount is None:
            continue

        if hours < 0 or rate <= 0:
            continue

        totals[wo_no] = totals.get(wo_no, Decimal("0")) + amount

    return totals


def calculate_actual_overhead_cost(
    work_orders,
    labor_transactions,
    work_centers,
    overhead_rates,
    products,
):
    """
    Phase 1 Actual OH: 유효한 DIRECT labor의 actual_hours를
    work_center_code → cost_center_code로 연결하고, 해당 (period_key, cost_center_code)의
    overhead_rate.rate_per_base(DLH)를 곱해 wo_no별로 배부한다.

    labor 쪽 유효성 기준은 calculate_actual_labor_cost와 동일하다(hours<0, rate<=0 등 제외).
    overhead_rate가 없는 cost_center(예: CC-300)로 귀속되는 시간은 배부하지 않고
    별도로 반환한다(NOT_ALLOCATED, 제품별 OH 미산출 — 임의로 배분/추정하지 않음).

    Returns:
        (wo_no별 OH 배부액 dict, wo_no별 미배부 시간 dict)
    """
    valid_wo_nos = _valid_work_order_nos(work_orders, products)
    wo_period = {w.get("wo_no"): w.get("period_key") for w in work_orders}
    work_center_to_cc = {
        wc.get("work_center_code"): wc.get("cost_center_code")
        for wc in work_centers if wc.get("work_center_code")
    }
    rate_by_key = {
        (r.get("period_key"), r.get("cost_center_code")): _strict_decimal(r.get("rate_per_base"))
        for r in overhead_rates
    }

    oh_totals: dict[str, Decimal] = {}
    unallocated_hours: dict[str, Decimal] = {}

    for r in labor_transactions:
        wo_no = r.get("wo_no")
        if wo_no not in valid_wo_nos:
            continue

        if r.get("direct_indirect") != "DIRECT":
            continue

        hours = _strict_decimal(r.get("actual_hours"))
        rate = _strict_decimal(r.get("actual_rate"))
        if hours is None or rate is None or hours < 0 or rate <= 0:
            continue

        cost_center_code = work_center_to_cc.get(r.get("work_center_code"))
        if cost_center_code is None:
            continue

        oh_rate = rate_by_key.get((wo_period.get(wo_no), cost_center_code))
        if oh_rate is None:
            unallocated_hours[wo_no] = unallocated_hours.get(wo_no, Decimal("0")) + hours
            continue

        oh_totals[wo_no] = oh_totals.get(wo_no, Decimal("0")) + calculate_overhead_cost(
            hours, oh_rate
        )

    return oh_totals, unallocated_hours


def calculate_actual_total_cost_by_wo(
    work_orders,
    material_issues,
    labor_transactions,
    materials,
    work_centers,
    overhead_rates,
    products,
) -> dict[str, dict]:
    """
    wo_no -> {"material_cost", "labor_cost", "overhead_cost", "total_cost",
    "unallocated_oh_hours"} 형태로 Phase 1 Actual Cost를 WO 단위로 집계한다.
    """
    material_costs = calculate_actual_material_cost(
        work_orders, material_issues, materials, products
    )
    labor_costs = calculate_actual_labor_cost(work_orders, labor_transactions, products)
    overhead_costs, unallocated_hours = calculate_actual_overhead_cost(
        work_orders, labor_transactions, work_centers, overhead_rates, products
    )

    wo_nos = set(material_costs) | set(labor_costs) | set(overhead_costs) | set(unallocated_hours)

    result: dict[str, dict] = {}
    for wo_no in wo_nos:
        material_cost = material_costs.get(wo_no, Decimal("0"))
        labor_cost = labor_costs.get(wo_no, Decimal("0"))
        overhead_cost = overhead_costs.get(wo_no, Decimal("0"))
        result[wo_no] = {
            "material_cost": material_cost,
            "labor_cost": labor_cost,
            "overhead_cost": overhead_cost,
            "total_cost": calculate_total_cost(material_cost, labor_cost, overhead_cost),
            "unallocated_oh_hours": unallocated_hours.get(wo_no, Decimal("0")),
        }

    return result


def calculate_actual_unit_cost_by_wo(
    actual_totals_by_wo,
    production_outputs,
) -> dict[str, Decimal]:
    """
    wo_no -> 단위원가(Decimal). production_output.good_qty를 wo_no별로 합산해 나눈다.
    good_qty 합계가 0이거나 산출 실적이 전혀 없는 WO는 결과에서 제외한다
    (0% 등 임의값을 반환하지 않고, 호출자가 NOT_CALCULABLE로 처리해야 한다).
    """
    good_qty_by_wo: dict[str, Decimal] = {}
    for po in production_outputs:
        wo_no = po.get("wo_no")
        if wo_no is None:
            continue

        qty = _strict_decimal(po.get("good_qty"))
        if qty is None:
            continue

        good_qty_by_wo[wo_no] = good_qty_by_wo.get(wo_no, Decimal("0")) + qty

    result: dict[str, Decimal] = {}
    for wo_no, totals in actual_totals_by_wo.items():
        good_qty = good_qty_by_wo.get(wo_no)
        if not good_qty:
            continue

        result[wo_no] = calculate_unit_cost(totals["total_cost"], good_qty)

    return result


def calculate_total_variance_by_wo(
    work_orders,
    material_issues,
    labor_transactions,
    materials,
    work_centers,
    overhead_rates,
    products,
    production_outputs,
    standard_cost_header,
) -> dict[str, dict]:
    """
    Phase 1 Total Variance: wo_no -> {"flexed_standard_dm/dl/oh/total",
    "actual_material_cost/labor_cost/overhead_cost/total_cost",
    "dm_variance/dl_variance/oh_variance", "total_variance"}.

    Total Variance = Actual Cost - Flexed Standard Cost
    Flexed Standard = standard_cost.standard_amount(제품 1단위당) × 해당 WO의
    good_qty 합계(production_output) — 표준을 실제 생산량에 맞춰 flex한다.

    Actual Cost는 calculate_actual_total_cost_by_wo()를 그대로 재사용한다(재계산하지
    않음). 이 WO가 그 결과에 아예 없으면(실적 거래가 전혀 없는 경우) Actual은 0으로
    취급한다 — 이것도 유효한 계산 결과이지 계산 불가 상태가 아니다.

    다음 WO는 결과에서 제외한다(새 오류 코드를 만들지 않고 생략만 한다 —
    이미 NO_PRODUCTION_OUTPUT/ZERO_DENOMINATOR/STANDARD_COST_MISSING이 별도로 보고함):
      - good_qty 합계가 없거나 0인 WO
      - 제품의 standard_cost header가 전혀 없는 WO(DM/DL/OH 전부 없음)

    DM/DL/OH 중 일부만 없는 경우는 있는 요소만 계산하고 없는 요소는 결과 dict에
    포함하지 않는다(전부 없어야만 WO 전체를 생략한다).

    기간을 넘겨 끝나는 WO(GL Reconciliation의 EXCLUDED_WO 대상)는 여기서는 별도로
    제외하지 않는다 — Total Variance는 기간 집계가 아니라 WO 단위 계산이라
    기간 걸침과 무관하다.
    """
    actual_totals_by_wo = calculate_actual_total_cost_by_wo(
        work_orders, material_issues, labor_transactions, materials,
        work_centers, overhead_rates, products,
    )

    good_qty_by_wo: dict[str, Decimal] = {}
    for po in production_outputs:
        wo_no = po.get("wo_no")
        qty = _strict_decimal(po.get("good_qty"))
        if wo_no is None or qty is None:
            continue
        good_qty_by_wo[wo_no] = good_qty_by_wo.get(wo_no, Decimal("0")) + qty

    standard_amount_by_key: dict[tuple, Decimal] = {}
    for h in standard_cost_header:
        product_code = h.get("product_code")
        period_key = h.get("period_key")
        cost_element_code = h.get("cost_element_code")
        amount = _strict_decimal(h.get("standard_amount"))
        if product_code is None or period_key is None or cost_element_code is None:
            continue
        if amount is None:
            continue
        standard_amount_by_key[(product_code, period_key, cost_element_code)] = amount

    zero = Decimal("0")
    result: dict[str, dict] = {}

    for wo in work_orders:
        wo_no = wo.get("wo_no")
        if wo_no is None:
            continue

        good_qty = good_qty_by_wo.get(wo_no)
        if not good_qty:
            continue

        product_code = wo.get("product_code")
        period_key = wo.get("period_key")

        dm_standard = standard_amount_by_key.get((product_code, period_key, "DM"))
        dl_standard = standard_amount_by_key.get((product_code, period_key, "DL"))
        oh_standard = standard_amount_by_key.get((product_code, period_key, "OH"))
        if dm_standard is None and dl_standard is None and oh_standard is None:
            continue

        actual = actual_totals_by_wo.get(wo_no, {
            "material_cost": zero, "labor_cost": zero,
            "overhead_cost": zero, "total_cost": zero,
        })

        entry: dict = {}
        flexed_amounts = []

        if dm_standard is not None:
            flexed_dm = round_amount(dm_standard * good_qty)
            entry["flexed_standard_dm"] = flexed_dm
            entry["actual_material_cost"] = actual["material_cost"]
            entry["dm_variance"] = round_amount(actual["material_cost"] - flexed_dm)
            flexed_amounts.append(flexed_dm)

        if dl_standard is not None:
            flexed_dl = round_amount(dl_standard * good_qty)
            entry["flexed_standard_dl"] = flexed_dl
            entry["actual_labor_cost"] = actual["labor_cost"]
            entry["dl_variance"] = round_amount(actual["labor_cost"] - flexed_dl)
            flexed_amounts.append(flexed_dl)

        if oh_standard is not None:
            flexed_oh = round_amount(oh_standard * good_qty)
            entry["flexed_standard_oh"] = flexed_oh
            entry["actual_overhead_cost"] = actual["overhead_cost"]
            entry["oh_variance"] = round_amount(actual["overhead_cost"] - flexed_oh)
            flexed_amounts.append(flexed_oh)

        flexed_total = round_amount(sum(flexed_amounts, Decimal("0")))
        entry["flexed_standard_total"] = flexed_total
        entry["actual_total_cost"] = actual["total_cost"]
        entry["total_variance"] = round_amount(actual["total_cost"] - flexed_total)

        result[wo_no] = entry

    return result


def _actual_material_qty_and_cost_by_wo_material(
    work_orders,
    material_issues,
    materials,
    products,
):
    """
    calculate_actual_material_cost()와 동일한 필터링 규칙(유효 WO/product,
    material master 등록 여부, issued_qty/unit_cost 파싱 가능 여부, RETURN 시
    net 처리)을 (wo_no, material_code) 단위로 적용한다 — DM PV/QV 분해를 위해
    자재별로 쪼갠 결과가 필요하므로, calculate_actual_material_cost() 자체는
    수정하지 않고 이 헬퍼를 별도로 둔다.
    """
    valid_wo_nos = _valid_work_order_nos(work_orders, products)
    material_codes = {m.get("material_code") for m in materials}

    totals: dict[tuple, dict] = {}

    for r in material_issues:
        wo_no = r.get("wo_no")
        if wo_no not in valid_wo_nos:
            continue

        material_code = r.get("material_code")
        if material_code not in material_codes:
            continue

        qty = _strict_decimal(r.get("issued_qty"))
        unit_cost = _strict_decimal(r.get("unit_cost"))
        if qty is None or unit_cost is None:
            continue

        line_amount = calculate_material_cost(qty, unit_cost)
        line_qty = qty
        if r.get("issue_type") == "RETURN":
            line_amount = -line_amount
            line_qty = -qty

        entry = totals.setdefault((wo_no, material_code), {"qty": Decimal("0"), "cost": Decimal("0")})
        entry["qty"] += line_qty
        entry["cost"] += line_amount

    return totals


def calculate_material_price_quantity_variance_by_wo(
    work_orders,
    material_issues,
    materials,
    products,
    production_outputs,
    standard_cost_detail,
) -> dict[str, dict]:
    """
    Phase 1 DM Price/Quantity Variance. `standard_cost_detail`의 `ref_type
    == "MATERIAL"` 행에 한정한다(현재 데이터에는 이 행이 P-200 DM 3건뿐).

    PV = Actual 자재비 − SP × AQ   (= (AP − SP) × AQ와 동치)
    QV = (AQ − SQ_flexed) × SP
    SQ_flexed = standard_cost_detail.standard_qty(제품 1단위당) × 해당 WO의
    good_qty 합계 — calculate_total_variance_by_wo()와 동일한 flex 방식.

    설계문서(§7-4)가 명시한 대로 PV + QV는 Total Variance(또는 DM Variance)와
    일치하지 않을 수 있다(교차항이 PV에 흡수됨 + standard_cost_detail 합계와
    header standard_amount의 기존 STD_DETAIL_SUM_MISMATCH 격차). 이 함수는
    그 값을 맞추기 위한 어떤 보정도 하지 않는다.

    다음은 결과에서 생략한다(0으로 채우지 않음 — 계산 불가와 0은 다르다):
      - 제품+기간에 ref_type=MATERIAL인 standard_cost_detail 행이 하나도
        없는 WO(자재별 표준 자체가 없어 구조적으로 계산 불가)
      - good_qty가 없거나 0인 WO

    standard_cost_detail에 없는 자재가 issue된 경우 그 자재는 breakdown에서
    제외되고(PV/QV 범위 밖), 표준이 있는 나머지 자재는 정상 계산된다.
    """
    good_qty_by_wo: dict[str, Decimal] = {}
    for po in production_outputs:
        wo_no = po.get("wo_no")
        qty = _strict_decimal(po.get("good_qty"))
        if wo_no is None or qty is None:
            continue
        good_qty_by_wo[wo_no] = good_qty_by_wo.get(wo_no, Decimal("0")) + qty

    standard_by_key: dict[tuple, dict] = {}
    for d in standard_cost_detail:
        if d.get("ref_type") != "MATERIAL":
            continue

        product_code = d.get("product_code")
        period_key = d.get("period_key")
        material_code = d.get("ref_material_code")
        if product_code is None or period_key is None or material_code is None:
            continue

        std_qty = _strict_decimal(d.get("standard_qty"))
        std_price = _strict_decimal(d.get("standard_unit_price"))
        if std_qty is None or std_price is None:
            continue

        standard_by_key[(product_code, period_key, material_code)] = {
            "standard_qty": std_qty,
            "standard_unit_price": std_price,
        }

    actual_by_wo_material = _actual_material_qty_and_cost_by_wo_material(
        work_orders, material_issues, materials, products,
    )

    zero = Decimal("0")
    result: dict[str, dict] = {}

    for wo in work_orders:
        wo_no = wo.get("wo_no")
        if wo_no is None:
            continue

        good_qty = good_qty_by_wo.get(wo_no)
        if not good_qty:
            continue

        product_code = wo.get("product_code")
        period_key = wo.get("period_key")

        material_standards = {
            key[2]: std for key, std in standard_by_key.items()
            if key[0] == product_code and key[1] == period_key
        }
        if not material_standards:
            continue

        materials_result = {}
        price_variances = []
        quantity_variances = []

        for material_code, std in material_standards.items():
            flexed_sq = std["standard_qty"] * good_qty
            sp = std["standard_unit_price"]

            actual = actual_by_wo_material.get(
                (wo_no, material_code), {"qty": zero, "cost": zero}
            )
            aq = actual["qty"]
            actual_cost = actual["cost"]

            price_variance = round_amount(actual_cost - sp * aq)
            quantity_variance = round_amount((aq - flexed_sq) * sp)

            materials_result[material_code] = {
                "actual_qty": aq,
                "actual_cost": actual_cost,
                "flexed_standard_qty": flexed_sq,
                "standard_unit_price": sp,
                "price_variance": price_variance,
                "quantity_variance": quantity_variance,
            }
            price_variances.append(price_variance)
            quantity_variances.append(quantity_variance)

        result[wo_no] = {
            "materials": materials_result,
            "price_variance_total": round_amount(sum(price_variances, Decimal("0"))),
            "quantity_variance_total": round_amount(sum(quantity_variances, Decimal("0"))),
        }

    return result


def calculate_applied_overhead_by_cost_center(
    work_orders,
    labor_transactions,
    work_centers,
    overhead_rates,
    products,
) -> dict[tuple, Decimal]:
    """
    (period_key, cost_center_code) -> Applied OH(Σ DIRECT actual_hours × rate_per_base).

    calculate_actual_overhead_cost()와 완전히 동일한 유효성 필터(유효 WO, DIRECT만,
    hours/rate 파싱 가능, hours<0/rate<=0 제외, work_center→cost_center 매핑,
    overhead_rate 존재 여부)를 적용하되, wo_no 대신 (period_key, cost_center_code)
    단위로 재집계한다 — OH Under/Over Applied는 WO 단위가 아니라 기간×CC 단위로만
    비교 가능하기 때문이다(GL 실제발생액에 wo_no가 없어 WO별 분해 근거가 없음).
    calculate_actual_overhead_cost() 자체는 수정하지 않는다.
    """
    valid_wo_nos = _valid_work_order_nos(work_orders, products)
    wo_period = {w.get("wo_no"): w.get("period_key") for w in work_orders}
    work_center_to_cc = {
        wc.get("work_center_code"): wc.get("cost_center_code")
        for wc in work_centers if wc.get("work_center_code")
    }
    rate_by_key = {
        (r.get("period_key"), r.get("cost_center_code")): _strict_decimal(r.get("rate_per_base"))
        for r in overhead_rates
    }

    applied_by_cc: dict[tuple, Decimal] = {}

    for r in labor_transactions:
        wo_no = r.get("wo_no")
        if wo_no not in valid_wo_nos:
            continue

        if r.get("direct_indirect") != "DIRECT":
            continue

        hours = _strict_decimal(r.get("actual_hours"))
        rate = _strict_decimal(r.get("actual_rate"))
        if hours is None or rate is None or hours < 0 or rate <= 0:
            continue

        cost_center_code = work_center_to_cc.get(r.get("work_center_code"))
        if cost_center_code is None:
            continue

        period_key = wo_period.get(wo_no)
        key = (period_key, cost_center_code)
        oh_rate = rate_by_key.get(key)
        if oh_rate is None:
            continue

        applied_by_cc[key] = applied_by_cc.get(key, Decimal("0")) + calculate_overhead_cost(
            hours, oh_rate
        )

    return applied_by_cc


def calculate_actual_total_cost_by_contract(
    work_orders,
    actual_totals_by_wo,
) -> dict[str, dict]:
    """
    Phase 2 1단계: contract_no -> {"actual_material_cost", "actual_labor_cost",
    "actual_overhead_cost", "actual_manufacturing_cost", "work_order_count",
    "work_orders"}.

    calculate_actual_total_cost_by_wo()가 이미 계산한 WO 단위 결과를 그대로
    재사용해 contract_no 기준으로 재집계한다 — 자재/노무/OH 필터링 로직을
    다시 구현하지 않는다.

    work_order.contract_no가 없는(None) WO는 집계에서 제외한다(계약 미배정
    WO를 오류로 취급하지 않고, 결과에서 조용히 빠질 뿐 — 기존 Actual Cost
    계산에는 전혀 영향을 주지 않는다).

    계약에 연결됐지만 실적 거래가 전혀 없어 actual_totals_by_wo에 없는 WO는
    0으로 취급한다 — calculate_total_variance_by_wo()가 이미 채택한 "실적
    없음은 0, 계산 불가와는 다르다" 정책과 동일하다.
    """
    zero = Decimal("0")
    result: dict[str, dict] = {}

    for wo in work_orders:
        contract_no = wo.get("contract_no")
        if contract_no is None:
            continue

        wo_no = wo.get("wo_no")
        actual = actual_totals_by_wo.get(wo_no, {
            "material_cost": zero, "labor_cost": zero, "overhead_cost": zero,
            "total_cost": zero,
        })

        entry = result.setdefault(contract_no, {
            "actual_material_cost": zero,
            "actual_labor_cost": zero,
            "actual_overhead_cost": zero,
            "actual_manufacturing_cost": zero,
            "work_order_count": 0,
            "work_orders": [],
        })
        entry["actual_material_cost"] += actual["material_cost"]
        entry["actual_labor_cost"] += actual["labor_cost"]
        entry["actual_overhead_cost"] += actual["overhead_cost"]
        entry["actual_manufacturing_cost"] += actual["total_cost"]
        entry["work_order_count"] += 1
        entry["work_orders"].append(wo_no)

    return result


def calculate_standard_budget_by_contract(
    contracts,
    work_orders,
    standard_cost_header,
    products,
) -> dict[str, dict]:
    """
    Phase 2 2단계: contract_no -> {
        "budget_material_cost", "budget_labor_cost", "budget_overhead_cost",
        "budget_manufacturing_cost", "work_order_count", "work_orders",
        "unpriced_work_orders", "work_order_budgets",
    }.

    Budget = standard_cost.standard_amount(제품 1단위당) × 해당 WO의 planned_qty.

    calculate_total_variance_by_wo()의 Flexed Standard(= standard_amount ×
    good_qty)와 개념적으로 다르다 — Total Variance는 "실제 생산량(good_qty)"
    기준이고, Contract Budget은 "계약상 계획 수량(planned_qty)" 기준이다. 이번
    데이터셋에서는 대부분 planned_qty == good_qty이지만(WO-2607-009는
    good_qty=0, WO-2607-017은 production_output 자체가 없음 — 둘 다
    planned_qty는 존재), 개념이 다르므로 이 함수는 production_output/good_qty를
    전혀 참조하지 않는다.

    다음 WO는 Budget 계산에서 제외한다(0으로 채우지 않음):
      - contract_no가 없는(None) WO — 오류 아님, 계약 미배정일 뿐.
      - product_code가 product master에 등록되지 않은 WO(기존 Actual Cost
        계열과 동일하게 _valid_work_order_nos()로 걸러낸다).
      - planned_qty가 없거나 0인 WO — "unpriced_work_orders"에 명시적으로
        남겨 계산 불가 상태를 드러낸다(생략 사유를 구분할 수 있도록).
      - 제품의 standard_cost가 DM/DL/OH 전부 없는 WO(예: P-900) — 역시
        "unpriced_work_orders"에 남긴다. STANDARD_COST_MISSING 검증과
        중복되지 않도록 여기서는 새 ValidationIssue를 만들지 않는다.

    good_qty=0이거나 production_output이 아예 없는 WO도 planned_qty만
    유효하면 정상적으로 Budget에 포함된다 — Total Variance와의 핵심 차이.

    DM/DL/OH 중 일부만 표준이 존재하면 있는 요소만 합산하고, 없는 요소는
    work_order_budgets의 해당 WO 항목에 포함하지 않는다(calculate_total_variance_by_wo와
    동일한 정책 — 임의로 0 처리하지 않는다).

    contracts에 등록됐지만 연결된 WO가 하나도 없거나 전부 계산 불가인 계약도
    결과에 0/빈 값으로 나타난다(조용히 사라지지 않는다).
    """
    standard_amount_by_key: dict[tuple, Decimal] = {}
    for h in standard_cost_header:
        product_code = h.get("product_code")
        period_key = h.get("period_key")
        cost_element_code = h.get("cost_element_code")
        amount = _strict_decimal(h.get("standard_amount"))
        if product_code is None or period_key is None or cost_element_code is None:
            continue
        if amount is None:
            continue
        standard_amount_by_key[(product_code, period_key, cost_element_code)] = amount

    valid_wo_nos = _valid_work_order_nos(work_orders, products)

    zero = Decimal("0")

    def _blank_entry():
        return {
            "budget_material_cost": zero,
            "budget_labor_cost": zero,
            "budget_overhead_cost": zero,
            "budget_manufacturing_cost": zero,
            "work_order_count": 0,
            "work_orders": [],
            "unpriced_work_orders": [],
            "work_order_budgets": {},
        }

    result: dict[str, dict] = {}
    for c in contracts:
        contract_no = c.get("contract_no")
        if contract_no is not None:
            result.setdefault(contract_no, _blank_entry())

    for wo in work_orders:
        contract_no = wo.get("contract_no")
        if contract_no is None:
            continue

        wo_no = wo.get("wo_no")
        if wo_no not in valid_wo_nos:
            continue

        entry = result.setdefault(contract_no, _blank_entry())

        planned_qty = _strict_decimal(wo.get("planned_qty"))
        if not planned_qty:
            entry["unpriced_work_orders"].append(wo_no)
            continue

        product_code = wo.get("product_code")
        period_key = wo.get("period_key")

        dm_standard = standard_amount_by_key.get((product_code, period_key, "DM"))
        dl_standard = standard_amount_by_key.get((product_code, period_key, "DL"))
        oh_standard = standard_amount_by_key.get((product_code, period_key, "OH"))
        if dm_standard is None and dl_standard is None and oh_standard is None:
            entry["unpriced_work_orders"].append(wo_no)
            continue

        wo_budget = {"planned_qty": planned_qty}
        wo_total = zero

        if dm_standard is not None:
            flexed_dm = round_amount(dm_standard * planned_qty)
            wo_budget["budget_material_cost"] = flexed_dm
            entry["budget_material_cost"] += flexed_dm
            wo_total += flexed_dm

        if dl_standard is not None:
            flexed_dl = round_amount(dl_standard * planned_qty)
            wo_budget["budget_labor_cost"] = flexed_dl
            entry["budget_labor_cost"] += flexed_dl
            wo_total += flexed_dl

        if oh_standard is not None:
            flexed_oh = round_amount(oh_standard * planned_qty)
            wo_budget["budget_overhead_cost"] = flexed_oh
            entry["budget_overhead_cost"] += flexed_oh
            wo_total += flexed_oh

        wo_budget["budget_manufacturing_cost"] = wo_total
        entry["budget_manufacturing_cost"] += wo_total
        entry["work_order_count"] += 1
        entry["work_orders"].append(wo_no)
        entry["work_order_budgets"][wo_no] = wo_budget

    return result


def calculate_contract_variance(
    contracts,
    actual_by_contract,
    budget_by_contract,
) -> dict[str, dict]:
    """
    Phase 2 3단계: contract_no -> {
        "dm_variance", "dl_variance", "oh_variance", "total_variance",
        "actual_manufacturing_cost", "budget_manufacturing_cost",
        "unpriced_work_orders", "mismatched_work_orders",
        "budget_coverage_complete",
    }.

    Variance = Actual − Budget. calculate_actual_total_cost_by_contract()와
    calculate_standard_budget_by_contract()가 이미 계산한 두 dict를 그대로
    받아 차감만 한다 — 두 함수 자체는 재계산하지도, 수정하지도 않는다.

    contracts 마스터에 등록된 모든 계약을 결과에 포함한다(WO가 하나도 연결되지
    않았거나 Actual/Budget 어느 한쪽에만 존재하는 계약도 포함). Actual 또는
    Budget 중 한쪽에 해당 contract_no가 없으면 그 쪽은 0으로 취급한다.

    calculate_actual_total_cost_by_contract()는 product 유효성을 검사하지
    않고 contract_no만으로 WO를 모으는 반면, calculate_standard_budget_by_contract()는
    _valid_work_order_nos()로 미등록 product WO를 완전히 제외한다(표준원가가
    없는 WO는 unpriced_work_orders에 남기지만, 미등록 product WO는 거기에도
    남지 않는다). 이 때문에 두 함수의 work_orders 집합이 어긋날 수 있으므로,
    Actual에는 있지만 Budget의 work_orders/unpriced_work_orders 어디에도
    없는 WO(또는 반대의 경우)를 "mismatched_work_orders"로 표시한다.

    budget_coverage_complete = unpriced_work_orders와 mismatched_work_orders가
    모두 비었을 때만 True — Total Variance 숫자가 Actual에 반영된 모든 WO에
    대해 빠짐없이 Budget이 계산된 상태에서 나온 값인지를 나타낸다. False이면
    이 계약의 Variance는 일부 WO의 Budget 누락으로 왜곡될 수 있다는 뜻이다.
    """
    zero = Decimal("0")

    def _blank_actual():
        return {
            "actual_material_cost": zero, "actual_labor_cost": zero,
            "actual_overhead_cost": zero, "actual_manufacturing_cost": zero,
            "work_orders": [],
        }

    def _blank_budget():
        return {
            "budget_material_cost": zero, "budget_labor_cost": zero,
            "budget_overhead_cost": zero, "budget_manufacturing_cost": zero,
            "work_orders": [], "unpriced_work_orders": [],
        }

    contract_nos = {c.get("contract_no") for c in contracts if c.get("contract_no") is not None}
    contract_nos |= set(actual_by_contract) | set(budget_by_contract)

    result: dict[str, dict] = {}
    for contract_no in contract_nos:
        actual = actual_by_contract.get(contract_no, _blank_actual())
        budget = budget_by_contract.get(contract_no, _blank_budget())

        actual_wos = set(actual.get("work_orders", []))
        unpriced_wos = list(budget.get("unpriced_work_orders", []))
        budget_known_wos = set(budget.get("work_orders", [])) | set(unpriced_wos)
        mismatched_wos = sorted(actual_wos.symmetric_difference(budget_known_wos))

        result[contract_no] = {
            "dm_variance": round_amount(
                actual["actual_material_cost"] - budget["budget_material_cost"]
            ),
            "dl_variance": round_amount(
                actual["actual_labor_cost"] - budget["budget_labor_cost"]
            ),
            "oh_variance": round_amount(
                actual["actual_overhead_cost"] - budget["budget_overhead_cost"]
            ),
            "total_variance": round_amount(
                actual["actual_manufacturing_cost"] - budget["budget_manufacturing_cost"]
            ),
            "actual_manufacturing_cost": actual["actual_manufacturing_cost"],
            "budget_manufacturing_cost": budget["budget_manufacturing_cost"],
            "unpriced_work_orders": unpriced_wos,
            "mismatched_work_orders": mismatched_wos,
            "budget_coverage_complete": not unpriced_wos and not mismatched_wos,
        }

    return result


def calculate_actual_direct_expense_by_contract(
    contracts,
    work_orders,
    direct_expenses,
) -> dict[str, dict]:
    """
    Phase 2 4단계: contract_no -> {"direct_expense_amount", "expense_count",
    "expense_ids"}.

    31_direct_expense.xlsx의 amount가 직접경비의 유일한 canonical source다.
    24_gl_transaction.xlsx의 금액은 여기서 다시 집계하지 않는다(이중집계 방지).
    direct_expense 행의 gl_account_code는 추적용 참조 메타데이터일 뿐이다.

    귀속 규칙(한 행은 wo_no 또는 contract_no 중 정확히 하나만 가진다):
      - wo_no만 있는 행: 그 WO의 work_order.contract_no로 귀속시킨다(행에
        계약을 중복 저장하지 않고 항상 WO를 통해 파생시킨다).
      - contract_no만 있는 행: 그 계약에 직접 귀속시킨다.

    다음 행은 집계에서 제외한다(0으로 채우지 않는다):
      - wo_no와 contract_no가 동시에 있는 행 — 귀속 대상이 모순이라
        어느 쪽으로도 계산하지 않는다. validate_direct_expense()가
        EXPENSE_TARGET_CONFLICT로 별도 보고한다.
      - wo_no와 contract_no가 모두 없는 행 — 귀속 대상이 없다.
      - wo_no가 work_order에 없거나, 그 WO에 contract_no가 없는 행
        (계약 미배정 WO의 경비) — 오류가 아니라 계약 집계 대상이 아닐 뿐이다.
      - contract_no가 contract master에 없는 행(UNKNOWN_CONTRACT로 별도 보고).
      - amount가 숫자로 변환되지 않는 행(INVALID_DECIMAL로 별도 보고).

    금액이 0이거나 음수(환입)인 행은 정상적으로 합산한다 — 0/음수는 유효한
    계산 결과이지 계산 불가 상태가 아니다.

    contracts 마스터에 등록된 모든 계약을 결과에 포함한다(직접경비가 하나도
    없는 계약도 0으로 나타난다 — calculate_standard_budget_by_contract()와
    동일한 pre-seeding 정책).
    """
    zero = Decimal("0")

    contract_nos = {
        c.get("contract_no") for c in contracts if c.get("contract_no") is not None
    }
    contract_no_by_wo = {
        w.get("wo_no"): w.get("contract_no")
        for w in work_orders if w.get("wo_no") is not None
    }

    result: dict[str, dict] = {
        contract_no: {
            "direct_expense_amount": zero,
            "expense_count": 0,
            "expense_ids": [],
        }
        for contract_no in contract_nos
    }

    for r in direct_expenses:
        wo_no = r.get("wo_no")
        contract_no = r.get("contract_no")

        if wo_no is not None and contract_no is not None:
            continue
        if wo_no is None and contract_no is None:
            continue

        if wo_no is not None:
            contract_no = contract_no_by_wo.get(wo_no)
            if contract_no is None:
                continue

        if contract_no not in contract_nos:
            continue

        amount = _strict_decimal(r.get("amount"))
        if amount is None:
            continue

        entry = result[contract_no]
        entry["direct_expense_amount"] += amount
        entry["expense_count"] += 1
        entry["expense_ids"].append(r.get("expense_id"))

    for entry in result.values():
        entry["direct_expense_amount"] = round_amount(entry["direct_expense_amount"])

    return result


def _resolve_ga_rate(contract, rate_rules):
    """
    계약 1건에 적용할 GA rate rule을 고른다. 우선순위(사용자 확정 정책):
      ① effective_from <= 기준일 <= effective_to (기준일 = contract.start_date)
      ② contract_type 정확 일치를 전체(contract_type=None) fallback보다 항상 우선
         (priority 수치보다 먼저 적용된다 — _resolve_gl_account_mapping()의
         "priority 먼저, 구체성은 동순위 타이브레이커"와는 다른, 이번에 명시적으로
         확정된 순서다)
      ③ 정확 일치가 하나도 없으면 전체(None) 후보로 fallback
      ④ 그 안에서 priority가 가장 높은 것 선택
      ⑤ 그래도 2건 이상 남으면 모호 상태

    rate_type == "GA"인 행만 후보로 본다(PROFIT 등 다른 rate_type은 이 단계의
    범위가 아니라 무시한다).

    Returns: (rate_pct: Decimal|None, status: "OK"|"NOT_FOUND"|"AMBIGUOUS", matched_rule: dict|None)
    rate_pct는 rule에 저장된 그대로의 퍼센트 값이다(예: 8 -> 8%, 100분율 변환은
    호출자가 한다).
    """
    contract_type = contract.get("contract_type")
    reference_date = contract.get("start_date")

    candidates = [r for r in rate_rules if r.get("rate_type") == "GA"]

    def _in_effective_range(r):
        if reference_date is None:
            return True
        effective_from = r.get("effective_from")
        effective_to = r.get("effective_to")
        if effective_from is not None and str(reference_date) < str(effective_from):
            return False
        if effective_to is not None and str(reference_date) > str(effective_to):
            return False
        return True

    candidates = [r for r in candidates if _in_effective_range(r)]
    if not candidates:
        return None, "NOT_FOUND", None

    exact_matches = [r for r in candidates if r.get("contract_type") == contract_type]
    pool = exact_matches if exact_matches else [
        r for r in candidates if r.get("contract_type") is None
    ]
    if not pool:
        return None, "NOT_FOUND", None

    def _priority(r):
        return _strict_decimal(r.get("priority")) or Decimal("0")

    top_priority = max(_priority(r) for r in pool)
    top = [r for r in pool if _priority(r) == top_priority]

    if len(top) != 1:
        return None, "AMBIGUOUS", None

    rate_pct = _strict_decimal(top[0].get("rate_pct"))
    if rate_pct is None:
        return None, "NOT_FOUND", None

    return rate_pct, "OK", top[0]


def calculate_ga_by_contract(
    actual_by_contract,
    budget_by_contract,
    rate_rules,
    contracts,
) -> dict[str, dict]:
    """
    Phase 2 5단계: contract_no -> {
        "contract_no", "manufacturing_cost_actual", "manufacturing_cost_budget",
        "ga_rate", "ga_actual", "ga_budget", "ga_variance", "rate_source",
        "calculable", "reason",
    }.

    GA 기준액은 DM+DL+OH(제조원가)만 사용한다 — Direct Expense는 포함하지
    않는다(사용자 확정 정책). calculate_actual_total_cost_by_contract()와
    calculate_standard_budget_by_contract()가 이미 계산한 결과 dict를 그대로
    받아 쓰기만 한다 — 두 함수 자체는 재계산하지도, 수정하지도 않는다.

    GA rate rule(예: 32_cost_rate_rule.xlsx)이 아직 저장소에 없으므로,
    rate_rules가 빈 리스트로 들어오면 모든 계약이 calculable=False,
    ga_rate=None으로 나온다 — 0%로 임의 처리하지 않는다("계산 불가"와
    "0%"는 다른 상태다). rate rule 선택 로직 자체는 _resolve_ga_rate()에
    있으며, 미래에 실제 rate rule 데이터가 추가되면 그대로 동작한다.

    GA Variance = GA Actual − GA Budget. 이번 단계에서 GA rate가 계약마다
    다르지 않다면(현재 rate_rules가 비어 있어 검증할 수 없지만, 향후 하나의
    rate만 있을 경우) 이 Variance는 결국 "동일 rate를 제조원가 차이(Actual−Budget)에
    곱한 값"과 같다 — 곧, 새로운 가격/능률 차이가 아니라 이미 계산된
    DM/DL/OH Variance에 비율을 적용한 결과라는 뜻이다. 이는
    calculate_contract_variance()의 DM/DL/OH variance/total_variance를
    대체하거나 합산하지 않고 완전히 별도 필드로만 제공한다(중복 없음).

    contracts 마스터에 등록된 모든 계약을 결과에 포함한다(calculate_standard_budget_by_contract()와
    동일한 pre-seeding 정책) — Actual/Budget 어느 쪽에도 없는 계약은 제조원가를
    0으로 취급한다.
    """
    zero = Decimal("0")
    hundred = Decimal("100")

    result: dict[str, dict] = {}
    for c in contracts:
        contract_no = c.get("contract_no")
        if contract_no is None:
            continue

        actual_mfg = actual_by_contract.get(contract_no, {}).get(
            "actual_manufacturing_cost", zero
        )
        budget_mfg = budget_by_contract.get(contract_no, {}).get(
            "budget_manufacturing_cost", zero
        )

        rate_pct, status, matched_rule = _resolve_ga_rate(c, rate_rules)

        entry = {
            "contract_no": contract_no,
            "manufacturing_cost_actual": actual_mfg,
            "manufacturing_cost_budget": budget_mfg,
            "ga_rate": rate_pct,
            "ga_actual": None,
            "ga_budget": None,
            "ga_variance": None,
            "rate_source": None,
            "calculable": False,
            "reason": None,
        }

        if status == "NOT_FOUND":
            entry["reason"] = (
                "적용 가능한 GA rate rule이 없습니다(rate rule 데이터 부재 또는 "
                "이 계약의 contract_type/기준일에 맞는 rule 없음)."
            )
        elif status == "AMBIGUOUS":
            entry["reason"] = (
                "동일 우선순위의 GA rate rule이 2건 이상이라 하나를 선택할 수 없습니다."
            )
        else:
            entry["calculable"] = True
            entry["rate_source"] = matched_rule.get("rule_id")
            rate_fraction = rate_pct / hundred
            ga_actual = round_amount(actual_mfg * rate_fraction)
            ga_budget = round_amount(budget_mfg * rate_fraction)
            entry["ga_actual"] = ga_actual
            entry["ga_budget"] = ga_budget
            entry["ga_variance"] = round_amount(ga_actual - ga_budget)
            entry["reason"] = "OK"

        result[contract_no] = entry

    return result


def calculate_contract_total_cost(
    actual_manufacturing_by_contract,
    direct_expense_by_contract,
    ga_by_contract,
    contracts,
) -> dict[str, dict]:
    """
    Phase 2 6단계: contract_no -> {
        "contract_no", "manufacturing_cost", "direct_expense",
        "total_cost_excl_ga", "ga_amount", "total_cost", "calculable", "reason",
    }.

    이번 단계는 Actual Contract Total Cost만 다룬다(Budget Total Cost는
    범위 밖 — Budget DE가 존재하지 않아 완전한 형태로 만들 수 없다는 사전조사
    결론에 따라 이번 함수는 Budget을 전혀 참조하지 않는다).

    calculate_actual_total_cost_by_contract(), calculate_actual_direct_expense_by_contract(),
    calculate_ga_by_contract()가 이미 계산한 결과 dict 3개만 받아 더한다 —
    세 함수 자체는 재계산하지도, 수정하지도 않는다.

    manufacturing_cost = DM+DL+OH(Actual), direct_expense = DE(Actual).
    total_cost_excl_ga = manufacturing_cost + direct_expense는 GA 상태와
    무관하게 항상 계산된다.

    GA가 calculable=True인 계약만 total_cost = total_cost_excl_ga + ga_amount로
    채워진다. GA가 calculable=False(또는 그 계약이 ga_by_contract에 아예 없는
    경우)면 ga_amount와 total_cost는 None으로 남고 calculable=False, reason에
    사유가 명시된다 — GA 부재를 0으로 대체하지 않는다(calculate_ga_by_contract()가
    이미 채택한 정책과 동일).

    contracts 마스터에 등록된 모든 계약을 결과에 포함한다(기존 함수들과 동일한
    pre-seeding 정책) — manufacturing_cost/direct_expense가 없는 계약은 0으로
    취급한다(둘 다 실적 기반 항목이라 "실적 없음=0"이 기존 정책과 일치한다).
    """
    zero = Decimal("0")

    result: dict[str, dict] = {}
    for c in contracts:
        contract_no = c.get("contract_no")
        if contract_no is None:
            continue

        manufacturing_cost = actual_manufacturing_by_contract.get(contract_no, {}).get(
            "actual_manufacturing_cost", zero
        )
        direct_expense = direct_expense_by_contract.get(contract_no, {}).get(
            "direct_expense_amount", zero
        )
        total_cost_excl_ga = manufacturing_cost + direct_expense

        ga_entry = ga_by_contract.get(contract_no)
        entry = {
            "contract_no": contract_no,
            "manufacturing_cost": manufacturing_cost,
            "direct_expense": direct_expense,
            "total_cost_excl_ga": total_cost_excl_ga,
            "ga_amount": None,
            "total_cost": None,
            "calculable": False,
            "reason": None,
        }

        if ga_entry is None:
            entry["reason"] = "이 계약의 GA 계산 결과가 없습니다(calculate_ga_by_contract() 결과 부재)."
        elif not ga_entry.get("calculable"):
            entry["reason"] = ga_entry.get("reason") or "GA를 계산할 수 없어 total_cost를 산출할 수 없습니다."
        else:
            ga_amount = ga_entry.get("ga_actual")
            entry["ga_amount"] = ga_amount
            entry["total_cost"] = total_cost_excl_ga + ga_amount
            entry["calculable"] = True
            entry["reason"] = "OK"

        result[contract_no] = entry

    return result


def calculate_budget_direct_expense_by_contract(
    contracts,
    budget_direct_expenses,
) -> dict[str, dict]:
    """
    Phase 2 7단계: contract_no -> {
        "contract_no", "budget_direct_expense", "calculable", "reason",
    }.

    34_direct_expense_budget.xlsx(Actual DE인 31_direct_expense.xlsx와는 완전히
    분리된 별도 파일 — 실적과 예산을 같은 행에 결합하지 않는다)의 행을
    contract_no 기준으로 합산한다. calculate_actual_direct_expense_by_contract()는
    수정하지 않으며, 그 함수의 WO 귀속 롤업 로직도 여기서는 재현하지 않는다 —
    Budget DE는 이번 단계에서 계약 단위 grain으로만 다룬다(WO 단위 예산이
    필요하다는 근거를 데이터/문서에서 찾지 못했다).

    각 행은 (contract_no, budget_expense_id, expense_type, budget_amount,
    effective_from, effective_to, description) 구조를 가진다고 가정한다.
    effective_from/effective_to가 있으면 해당 계약의 start_date가 그 범위
    안에 있을 때만 합산 대상으로 본다(GA rate 선택 때 쓴 것과 동일한 기준일
    관례 — contract.start_date). 범위가 없는 행(둘 다 None)은 항상 포함한다.
    이 함수는 "여러 행을 하나만 골라야 하는" GA rate 선택과 달리 "해당되는
    모든 행을 더하는" 단순 합산이라 priority/모호성 판정은 없다.

    존재하지 않는 contract_no를 참조하는 행은 조용히 제외한다(다른 계산
    함수들과 동일한 정책 — 새 오류를 만들지 않는다).

    이 계약에 해당하는 Budget DE 행이 하나도 없으면 budget_direct_expense는
    None, calculable=False로 남는다 — 0으로 채우지 않는다. 이번 데이터셋에는
    34_direct_expense_budget.xlsx에 실제 행이 전혀 없으므로(구조만 준비),
    실제 CLI에서는 3개 계약 모두 이 상태가 된다.

    음수 budget_amount(예산 축소 등)는 유효한 값으로 그대로 합산한다 —
    Actual DE의 환입(음수) 처리와 동일한 원칙이다.

    contracts 마스터에 등록된 모든 계약을 결과에 포함한다(기존 함수들과
    동일한 pre-seeding 정책).
    """
    contract_start_date = {
        c.get("contract_no"): c.get("start_date")
        for c in contracts if c.get("contract_no") is not None
    }
    contract_nos = set(contract_start_date)

    def _in_effective_range(row, contract_no):
        reference_date = contract_start_date.get(contract_no)
        if reference_date is None:
            return True
        effective_from = row.get("effective_from")
        effective_to = row.get("effective_to")
        if effective_from is not None and str(reference_date) < str(effective_from):
            return False
        if effective_to is not None and str(reference_date) > str(effective_to):
            return False
        return True

    sums: dict[str, Decimal] = {}
    counts: dict[str, int] = {}

    for row in budget_direct_expenses:
        contract_no = row.get("contract_no")
        if contract_no not in contract_nos:
            continue

        if not _in_effective_range(row, contract_no):
            continue

        amount = _strict_decimal(row.get("budget_amount"))
        if amount is None:
            continue

        sums[contract_no] = sums.get(contract_no, Decimal("0")) + amount
        counts[contract_no] = counts.get(contract_no, 0) + 1

    result: dict[str, dict] = {}
    for contract_no in contract_nos:
        if counts.get(contract_no, 0) > 0:
            result[contract_no] = {
                "contract_no": contract_no,
                "budget_direct_expense": round_amount(sums[contract_no]),
                "calculable": True,
                "reason": "OK",
            }
        else:
            result[contract_no] = {
                "contract_no": contract_no,
                "budget_direct_expense": None,
                "calculable": False,
                "reason": "이 계약에 대한 Budget DE 데이터가 없습니다(34_direct_expense_budget.xlsx에 해당 행 없음).",
            }

    return result


# ============================================================================
# Phase 2 8단계: GA 규정 정합 계산 구조 (준비 단계, 아직 활성화하지 않음)
#
# 이 구획의 함수들은 기존 calculate_ga_by_contract()/_resolve_ga_rate()를
# 대체하지 않는다 — 그 둘은 그대로 보존되며 CLI도 여전히 그 결과만 출력한다.
# 여기 함수들은 "규정에 맞는 계산 구조"만 준비하는 것이며, 아래는 전부
# 실제 rate/관급재료비 데이터가 없는 상태에서도 None/미계산으로 안전하게
# 동작하도록 설계했다 — 어떤 수치도 임의로 채우지 않는다.
# ============================================================================


def calculate_ga_base_amount(
    manufacturing_cost_excluding_government_material,
    government_furnished_material,
    calculation_basis,
):
    """
    GA 기준액(ga_base_amount)을 계산하는 순수 함수.

    제조원가는 반드시 DM+DL+DE+OH(관급재료비 제외)로 정의된 값을 받는다
    (이 함수 자체는 그 합산을 하지 않는다 — 호출자가 이미 합산해서 넘긴다).

    calculation_basis:
      - "EXCLUDE_GFM": 기준액 = manufacturing_cost_excluding_government_material 그대로.
        관급재료비 값을 아예 쓰지 않으므로 관급재료비가 None이어도 계산된다.
      - "INCLUDE_GFM": 기준액 = manufacturing_cost_excluding_government_material +
        government_furnished_material. 관급재료비가 None(데이터 없음)이면
        전체 결과도 None이다 — **0으로 대체하지 않는다**(관급재료비 데이터
        부재를 0원으로 취급하면 실제보다 기준액이 커져 GA가 과대/과소 계산될
        위험이 있다).
      - 그 외 알 수 없는 값: None(계산 불가) — 임의로 추정하지 않는다.

    manufacturing_cost_excluding_government_material 자체가 None이면 항상
    None을 반환한다(기준 자체가 없으므로 계산 불가 상태를 그대로 전파한다).
    """
    if manufacturing_cost_excluding_government_material is None:
        return None

    if calculation_basis == "EXCLUDE_GFM":
        return manufacturing_cost_excluding_government_material

    if calculation_basis == "INCLUDE_GFM":
        if government_furnished_material is None:
            return None
        return manufacturing_cost_excluding_government_material + government_furnished_material

    return None


def _in_ga_rate_effective_range(rule, reference_date):
    """
    기준일이 rule의 [effective_from, effective_to] 안(양끝 포함)에 있는지
    판정한다.

    effective_from 또는 effective_to 중 하나라도 None이면 이 rule을
    "무기한 유효"로 간주하지 않고 후보에서 제외한다(False를 반환) — 이는
    새로 지어낸 규칙이 아니라, 이미 이 코드베이스가 BOM 버전 유효기간
    비교(validation.py의 _bom_date_ranges_overlap())에서 쓰고 있는 것과
    동일한 방어적 관례다: 거기서도 두 구간 중 어느 한쪽 끝이라도 None이면
    "겹치지 않는다"고 보수적으로 판정하지, None을 무한대로 취급하지 않는다.
    실제 데이터에서 "무기한"을 표현하려면(예: 10_bom.xlsx의 ACTIVE 버전들이
    effective_to=2099-12-31처럼 먼 미래의 명시적 날짜를 쓰는 것) 이 프로젝트의
    기존 관례이며, None을 그 의미로 대신 쓰지 않는다.

    날짜는 이 프로젝트 전반의 관례(_bom_date_ranges_overlap(),
    _is_period_spanning() 등)와 동일하게 ISO 8601 문자열 그대로 비교한다.
    별도의 날짜 형식 검증/파싱 실패 처리는 기존 코드 어디에도 없어(전부
    문자열 비교로만 판정) 이번에도 새로 만들지 않는다 — 이 프로젝트는
    "형식이 잘못된 날짜"를 별도 invalid 상태로 다루는 선례가 없다.

    [알려진 한계 — 코드 변경 없이 기록만 해둠]
    - 이 null-bound-제외 정책은 32_cost_rate_rule.xlsx의 "공식" 데이터
      모델이 아직 존재하지 않는 상태에서 BOM 버전 유효기간(10_bom.xlsx)
      선례 하나에만 근거해 보수적으로 정한 것이다. GA rate rule의 실제
      스키마가 확정되면(예: "무기한"을 null이 아니라 BOM처럼 2099-12-31
      같은 명시적 far-future sentinel로 표현하는 관례를 그대로 따를지) 이
      정책을 재검토해야 한다.
    - 현재 실제 데이터셋의 모든 날짜 컬럼은 텍스트 셀(plain "YYYY-MM-DD"
      문자열)로 저장되어 있어 str() 비교가 안전하다(loader.py는 셀 값을
      변환 없이 그대로 통과시킨다). 그러나 만약 향후 32_cost_rate_rule.xlsx
      가 실제 Excel 날짜형 셀로 채워진다면 로더가 datetime 객체를 돌려줄
      수 있고, str(datetime(...))은 "2026-01-01 00:00:00"처럼 시간까지
      붙어 순수 "YYYY-MM-DD" 기준일 문자열과의 경계값(등호) 비교가 깨질
      수 있다 — 이 코드는 이 경우를 방어하지 않는다.
    """
    effective_from = rule.get("effective_from")
    effective_to = rule.get("effective_to")
    if effective_from is None or effective_to is None:
        return False
    return str(effective_from) <= str(reference_date) <= str(effective_to)


def resolve_ga_actual_rate(rate_rules, company_code, plant_code, fiscal_year, reference_date):
    """
    실적 기반 GA 요율(ACTUAL) 조회 — (company_code, plant_code, fiscal_year)
    정확 일치 + reference_date가 그 행의 [effective_from, effective_to]
    안에 있는 행만 후보로 삼는다. contract_type은 이 조회에 전혀 관여하지
    않는다(기존 _resolve_ga_rate()와 완전히 분리된 별도 축).

    reference_date는 호출자가 명시적으로 전달해야 한다 — 이 함수는 현재
    날짜를 스스로 조회하지 않는다(datetime.now() 등을 쓰지 않음). fiscal_year
    (산정연도 식별자)와 effective_from/effective_to(그 rule의 실제 효력기간)는
    서로 다른 개념이므로 섞어서 판단하지 않는다: fiscal_year는 정확 일치로만
    후보를 좁히고, 그 다음 완전히 별도로 effective 기간을 검사한다
    (_in_ga_rate_effective_range).

    [reference_date 생성에 대한 명시적 제약]
    이 함수는 물론이고 이 함수를 호출하는 어떤 코드도 `contract.start_date`
    /`contract.end_date`를 reference_date로 대신 사용해서는 안 된다. 조사
    결과 방산원가규칙 제28조와 시행세칙 제32조는 GA 기준일을 계약방식별로
    최소 4가지로 구분한다(확정계약 예정가격=계약동의서 서명날인 직전,
    개산계약 정산=납기·최종납품일 중 먼저 도래하는 날, 중도확정계약=
    중도확정일, 특정비목불확정계약=예정가격 결정 시점) — 이 중 어느 것도
    `start_date`/`end_date`라는 이름과 문언상 일치하지 않는다. 게다가
    30_contract.xlsx의 `start_date`/`end_date`가 실제로 이 4가지 법정
    기준일 중 무엇을 의미하는지조차 **확인되지 않았다**(Phase 1 설계
    문서·데이터 생성 스크립트 어디에도 정의가 없음). 따라서 그 법적 의미가
    밝혀지기 전까지는 두 필드를 reference_date로 쓸 근거가 없다.

    plant_code가 법적 "부문"과 동일하다고 이 함수가 단정하지 않는다 —
    현재 30_contract.xlsx에는 plant_code/fiscal_year 컬럼이 없어 실제
    데이터로 호출하면 사실상 항상 None이 들어와 조회 결과도 None이 된다.
    이는 이번 단계에서 새 컬럼을 추가하지 않기로 한 결정에 따른 의도된
    동작이며, 계산 비활성 상태를 그대로 반영한다.

    rate_type="GA", rate_kind="ACTUAL"인 행만 후보로 삼는다. priority가
    없으므로(이번 설계에서 제외) 정확히 1건만 매칭되어야 하며, 0건이거나
    2건 이상(모호 — 예: 유효기간이 겹치는 두 rule이 기준일에 동시에 유효한
    경우)이면 (None, None)을 반환한다 — 임의로 하나를 고르지 않는다.

    Returns: (rate_pct: Decimal|None, matched_rule: dict|None)
    """
    if (
        company_code is None or plant_code is None
        or fiscal_year is None or reference_date is None
    ):
        return None, None

    candidates = [
        r for r in rate_rules
        if r.get("rate_type") == "GA"
        and r.get("rate_kind") == "ACTUAL"
        and r.get("company_code") == company_code
        and r.get("plant_code") == plant_code
        and r.get("fiscal_year") == fiscal_year
        and _in_ga_rate_effective_range(r, reference_date)
    ]
    if len(candidates) != 1:
        return None, None

    rate_pct = _strict_decimal(candidates[0].get("rate_pct"))
    if rate_pct is None:
        return None, None

    return rate_pct, candidates[0]


def resolve_ga_ceiling_rate(rate_rules, industry_type, company_size, reference_date):
    """
    GA 상한율(CEILING) 조회 — (industry_type, company_size) 정확 일치 +
    reference_date가 그 행의 [effective_from, effective_to] 안에 있는 행만
    후보로 삼는다. company_code/plant_code/fiscal_year는 이 조회와 무관하다
    (실적요율 축과 완전히 분리된 별도 축 — 실적요율과 상한을 하나의
    contract_type 기반 매칭으로 뒤섞지 않는다).

    reference_date는 호출자가 명시적으로 전달해야 한다(resolve_ga_actual_rate와
    동일한 원칙). effective 기간 판정 규칙(None 처리, 문자열 비교)도
    resolve_ga_actual_rate와 완전히 동일하다(_in_ga_rate_effective_range 공유).

    [reference_date 생성에 대한 명시적 제약 — resolve_ga_actual_rate와 동일]
    `contract.start_date`/`contract.end_date`를 reference_date로 대신
    사용하지 않는다. 두 필드가 방산원가규칙 제28조·시행세칙 제32조가 구분하는
    4가지 법정 기준일(계약동의서 서명날인 직전/납기·최종납품일/중도확정일/
    예정가격 결정 시점) 중 무엇에 대응하는지 확인되지 않았기 때문이다(자세한
    근거는 resolve_ga_actual_rate() docstring 참고).

    현재 30_contract.xlsx에는 industry_type/company_size 컬럼이 없어
    실제 데이터로 호출하면 항상 None이 들어와 조회 결과도 None이 된다
    (의도된 동작 — §resolve_ga_actual_rate와 동일한 이유).

    rate_type="GA", rate_kind="CEILING"인 행만 후보로 삼는다. 정확히 1건만
    매칭되어야 하며, 0건이거나 2건 이상이면 (None, None)을 반환한다.

    Returns: (rate_pct: Decimal|None, matched_rule: dict|None)
    """
    if industry_type is None or company_size is None or reference_date is None:
        return None, None

    candidates = [
        r for r in rate_rules
        if r.get("rate_type") == "GA"
        and r.get("rate_kind") == "CEILING"
        and r.get("industry_type") == industry_type
        and r.get("company_size") == company_size
        and _in_ga_rate_effective_range(r, reference_date)
    ]
    if len(candidates) != 1:
        return None, None

    rate_pct = _strict_decimal(candidates[0].get("rate_pct"))
    if rate_pct is None:
        return None, None

    return rate_pct, candidates[0]


def calculate_regulatory_ga_by_contract(
    actual_by_contract,
    budget_by_contract,
    actual_direct_expense_by_contract,
    budget_direct_expense_by_contract,
    government_furnished_material_by_contract,
    rate_rules,
    contracts,
    calculation_basis,
    reference_date,
    dm_excluding_gfm_by_contract,
) -> dict[str, dict]:
    """
    calculate_ga_by_contract()와 나란히 존재하는 "규정 정합 구조" 버전이다
    (기존 함수는 수정하지 않았고, CLI도 여전히 기존 함수만 호출한다 — 이
    함수는 아직 어디에도 연결되지 않은 준비 단계 코드다).

    기존 함수와의 핵심 차이:
      1. Actual 쪽 제조원가는 더 이상 actual_by_contract의
         actual_manufacturing_cost(DM+DL+OH가 이미 합쳐진 값)를 쓰지 않는다.
         그 DM 성분은 calculate_actual_material_cost()(Phase 1 보호 함수)가
         supply_type을 구분하지 않고 관급+사급을 모두 합친 값이라서,
         여기에 관급재료비(government_furnished_material_by_contract)를
         또 더하면 관급분이 이중집계되기 때문이다(이전 라운드
         test_dm_excl_gfm_plus_gfm_equals_total_material_cost_no_double_counting
         에서 실제로 재현·확인됨). 대신 다음처럼 재구성한다:

           manufacturing_cost_excluding_government_material_actual =
               dm_excluding_gfm_by_contract[contract_no]["dm_excluding_gfm"]
             + actual_by_contract[contract_no]["actual_labor_cost"]
             + actual_by_contract[contract_no]["actual_overhead_cost"]
             + actual_direct_expense_by_contract[contract_no]["direct_expense_amount"]

         dm_excluding_gfm_by_contract는
         calculate_actual_material_cost_excluding_gfm_by_contract()의 출력을
         그대로 넣는 외부 입력이다(이 함수가 스스로 계산하지 않는다).
         그 계약의 dm_excluding_gfm이 None(예: material_issue 중 하나라도
         supply_type이 미분류라 "계산 불가"인 경우)이면, DL/OH/DE가 전부
         계산 가능하더라도 Actual 쪽 전체 제조원가와 ga_base_amount_actual,
         ga_actual까지 전부 None으로 남긴다 — 일부만이라도 더해서 부분
         합계를 만들지 않는다("계산 불가 ≠ 0" 원칙의 연장).
      2. Budget 쪽은 이번 변경과 무관하게 그대로 유지한다 — 여전히
         budget_by_contract의 budget_manufacturing_cost(DM+DL+OH 합계,
         관급/사급 구분 없음) + budget_direct_expense_by_contract를 쓴다.
         12_standard_cost.xlsx에는 supply_type에 대응하는 개념이 전혀 없어
         (이전 라운드에서 스키마로 확인됨) Budget 쪽에서 관급재료비를
         분리해낼 방법이 아직 없기 때문이다 — 근거 없이 임의로 Actual과
         똑같은 구조를 강제하지 않는다.
      3. 관급재료비(government_furnished_material_by_contract)를
         calculate_ga_base_amount()로 조합한다 — 외부에서 주어지는 dict이며
         이 함수는 관급재료비를 스스로 계산하지 않는다(§6 정책). Actual
         쪽 DM이 이제 실제로 관급재료비를 제외한 값이므로, INCLUDE_GFM
         basis에서 이 값을 다시 더하는 것이 처음으로 이중집계 없이
         올바르게 성립한다.

         [Budget 쪽 INCLUDE_GFM 이중집계 위험 — 명시적 경고, 아직 해결하지
         않음] 위 "이중집계 없음"은 Actual 쪽에만 성립한다. calculate_
         ga_base_amount()는 basis="INCLUDE_GFM"이면 무조건 government_
         furnished_material을 한 번 더한다 — 이는 이 함수를 어떤
         manufacturing_cost 값에 적용하든 동일하게 일어나는 무조건 동작이다.
         Budget 쪽 mfg_excl_gfm_budget(=budget_manufacturing_cost +
         budget_direct_expense)의 budget_manufacturing_cost는 §2에서 밝힌
         대로 12_standard_cost.xlsx에 supply_type 개념이 전혀 없어 관급/
         사급이 분리되지 않은 값이다 — 즉 그 안에 관급재료비가 이미
         포함되어 있을 가능성을 배제할 수 없다. 그런 상태에서 INCLUDE_GFM
         basis로 호출하면 ga_base_amount_budget이 government_furnished_
         material을 실질적으로 두 번 반영(이미 섞여 있는 budget_
         manufacturing_cost 값 + 별도로 더해진 gfm)하는 이중집계가 될
         위험이 있다. 이 위험은 코드로 아직 막지 않았다 — Budget 쪽
         재료비에서 관급분을 신뢰성 있게 분리할 데이터/로직이 아직 없기
         때문이다(Budget GFM 분리는 여전히 미구현). 따라서 현재
         ga_base_amount_budget/ga_budget이 INCLUDE_GFM basis로 계산해
         낸 값은 규정상 유효한 계산 결과로 간주하지 않는다 — Budget GFM
         원천 데이터(예: standard_cost_detail의 신뢰 가능한 supply_type
         분리, 또는 contract_material_supply_type.xlsx 같은 별도 grain의
         실제 값)가 확보되기 전까지 이 basis를 Budget 쪽 실제 계산에 쓰지
         않는다. (재현 테스트:
         test_regulatory_ga_include_gfm_budget_side_double_counts_when_
         gfm_not_separable — 이 테스트는 현재 동작을 "정상"으로 승인하는
         것이 아니라, Budget GFM이 실제로 분리되기 전까지 이 위험이 그대로
         남아 있음을 고정해 두는 것이다.)
      4. rate 조회를 resolve_ga_actual_rate()(실적, company+plant+fiscal_year+
         reference_date)와 resolve_ga_ceiling_rate()(상한, industry_type+
         company_size+reference_date)로 완전히 분리한다. 두 축의 매칭 키는
         contract 행에서 그대로 읽는다(contract.get("plant_code") 등) —
         현재 30_contract.xlsx에는 이 컬럼들이 없으므로 실제 데이터로는
         항상 None이 되어 두 조회 모두 (None, None)이 된다. 이는 §3에서
         이미 확인된 데이터 격차이며, 이번 단계에서 그 컬럼을 새로 추가하지
         않는다.
      5. reference_date는 이 함수가 스스로 정하지 않는다(현재 날짜나
         contract.get("start_date") 등을 내부에서 임의로 쓰지 않음) — 호출자가
         명시적으로 전달해야 한다. "언제를 기준으로 GA 요율을 조회할
         것인가"는 사전원가/확정원가 산정 시점처럼 업무 프로세스가 결정할
         문제이고, 계약 데이터의 특정 필드에서 자동으로 추론할 성격이
         아니라고 판단했다 — 이 판단의 근거는 이 함수 하단의 별도 설명을
         참고한다.

         Actual 쪽 GA(ga_actual)와 Budget 쪽 GA(ga_budget) 계산에는 동일한
         reference_date로 조회한 동일한 실적요율을 그대로 재사용한다(기존
         calculate_ga_by_contract()와 동일한 계산 패턴 유지). 즉: 현재
         규정 조사에서 Actual/Budget에 서로 다른 GA 적용시점을 확정할
         근거가 없어 동일 기준일을 사용한다 — 방산원가 규정/지침에서
         사전원가와 정산원가의 GA 적용시점이 실제로 다르다는 근거가 아직
         확보되지 않았기 때문이다. actual_rate_reference_date/
         budget_rate_reference_date처럼 두 시점을 분리하는 인터페이스로
         확장하는 방안을 검토했으나, 그 근거가 없는 현재로서는 단일
         reference_date를 두 계산에 공유하는 것으로 유지한다(이 함수
         하단의 별도 설명 참고). 이 함수는 아직 CLI에 연결되지 않았으므로
         향후 그 근거가 확보되면 기존 호출자를 깨지 않고(추가 파라미터로)
         확장할 수 있다.
      6. 상한 초과 여부(exceeds_ceiling)는 참고용으로만 계산해 노출한다 —
         "실적요율이 상한을 넘으면 상한으로 대체한다"는 식의 정책은 아직
         확정되지 않았으므로(§C, 미해결) ga_actual/ga_budget 계산에는
         반영하지 않는다.

    calculable=True는 GA 기준액(Actual)과 실적요율(ACTUAL) 둘 다 확보된
    경우에만 True다. 그 외에는 계산 불가로 남고 reason에 사유를 남긴다.
    """
    zero = Decimal("0")
    hundred = Decimal("100")

    result: dict[str, dict] = {}
    for c in contracts:
        contract_no = c.get("contract_no")
        if contract_no is None:
            continue

        actual_de = actual_direct_expense_by_contract.get(contract_no, {}).get(
            "direct_expense_amount", zero
        )
        dm_excluding_gfm = dm_excluding_gfm_by_contract.get(contract_no, {}).get(
            "dm_excluding_gfm"
        )
        if dm_excluding_gfm is None:
            mfg_excl_gfm_actual = None
        else:
            actual_dl = actual_by_contract.get(contract_no, {}).get(
                "actual_labor_cost", zero
            )
            actual_oh = actual_by_contract.get(contract_no, {}).get(
                "actual_overhead_cost", zero
            )
            mfg_excl_gfm_actual = dm_excluding_gfm + actual_dl + actual_oh + actual_de

        budget_mfg = budget_by_contract.get(contract_no, {}).get(
            "budget_manufacturing_cost", zero
        )
        budget_de_entry = budget_direct_expense_by_contract.get(contract_no, {})
        if budget_de_entry.get("calculable"):
            mfg_excl_gfm_budget = budget_mfg + budget_de_entry.get("budget_direct_expense")
        else:
            mfg_excl_gfm_budget = None

        gfm = government_furnished_material_by_contract.get(contract_no)

        ga_base_actual = calculate_ga_base_amount(
            mfg_excl_gfm_actual, gfm, calculation_basis
        )
        ga_base_budget = calculate_ga_base_amount(
            mfg_excl_gfm_budget, gfm, calculation_basis
        )

        actual_rate, actual_rule = resolve_ga_actual_rate(
            rate_rules,
            c.get("company_code"),
            c.get("plant_code"),
            c.get("fiscal_year"),
            reference_date,
        )
        ceiling_rate, _ = resolve_ga_ceiling_rate(
            rate_rules, c.get("industry_type"), c.get("company_size"), reference_date
        )

        exceeds_ceiling = None
        if actual_rate is not None and ceiling_rate is not None:
            exceeds_ceiling = actual_rate > ceiling_rate

        entry = {
            "contract_no": contract_no,
            "manufacturing_cost_excluding_government_material_actual": mfg_excl_gfm_actual,
            "manufacturing_cost_excluding_government_material_budget": mfg_excl_gfm_budget,
            "government_furnished_material": gfm,
            "calculation_basis": calculation_basis,
            "ga_base_amount_actual": ga_base_actual,
            "ga_base_amount_budget": ga_base_budget,
            "actual_rate": actual_rate,
            "rate_source": actual_rule.get("rule_id") if actual_rule else None,
            "ceiling_rate": ceiling_rate,
            "exceeds_ceiling": exceeds_ceiling,
            "ga_actual": None,
            "ga_budget": None,
            "ga_variance": None,
            "calculable": False,
            "reason": None,
        }

        if ga_base_actual is None:
            entry["reason"] = (
                "GA 기준액(Actual)을 계산할 수 없습니다 "
                "(관급재료비 제외 재료비(dm_excluding_gfm) 계산 불가, "
                "제조원가 데이터 부재, 또는 관급재료비 데이터 부재)."
            )
        elif actual_rate is None:
            entry["reason"] = (
                "적용 가능한 GA 실적요율(ACTUAL rate)이 없습니다 "
                "(rate rule 데이터 부재, company_code/plant_code/fiscal_year 불일치, "
                "또는 reference_date가 유효기간[effective_from, effective_to] 밖입니다)."
            )
        else:
            entry["calculable"] = True
            entry["reason"] = "OK"
            rate_fraction = actual_rate / hundred
            ga_actual = round_amount(ga_base_actual * rate_fraction)
            entry["ga_actual"] = ga_actual
            if ga_base_budget is not None:
                ga_budget = round_amount(ga_base_budget * rate_fraction)
                entry["ga_budget"] = ga_budget
                entry["ga_variance"] = round_amount(ga_actual - ga_budget)

        result[contract_no] = entry

    return result


def calculate_government_furnished_material_by_contract(
    contracts,
    work_orders,
    material_issues,
) -> dict[str, dict]:
    """
    Phase 2 GA 규정 정합 구조 준비: contract_no -> 관급재료비(GFM) 집계.

    22_material_issue.xlsx에 이번 단계에서 추가한 supply_type(관급/사급 구분)
    컬럼을 기준으로, wo_no -> work_order.contract_no 경로를 통해 계약 단위로
    집계한다. 현재 실제 데이터에는 supply_type 값이 전혀 채워져 있지 않으므로
    (이번 단계는 스키마 추가만 결정했고 임의로 GOVERNMENT/COMPANY 기본값을
    채우지 않았다), 실제 데이터로 호출하면 모든 계약이 calculable=False로
    남는다 — 이는 의도된 동작이며 계산 비활성 상태를 그대로 반영한다.

    "계산 불가 ≠ 0" 원칙: 어떤 계약에 귀속되는 material_issue 행 중 단 하나
    라도 supply_type이 None(미분류)이면, 그 행이 실제로 관급인지 사급인지
    알 수 없으므로 그 계약 전체의 GFM을 계산 불가(calculable=False,
    gfm_amount=None)로 남긴다 — 미분류 행을 "사급(관급 아님, 즉 0에 기여)"로
    임의 간주하지 않는다.

    supply_type == "GOVERNMENT"인 행만 금액에 더한다(issued_qty × unit_cost,
    issue_type == "RETURN"이면 차감 — calculate_actual_material_cost()와
    동일한 계산 규칙). "GOVERNMENT"가 아닌 다른 명시적 값(예: "COMPANY")은
    계산 불가 판정에 영향을 주지 않고 금액에는 0으로 기여한다.

    material_code가 material master에 등록되어 있는지, issued_qty/unit_cost가
    숫자로 파싱되는지는 이 함수의 관심사가 아니다(validate_material_issues()가
    UNKNOWN_MATERIAL/INVALID_DECIMAL로 이미 별도 검증한다) — 그런 행은
    supply_type 분류와 무관하게 금액 집계에서만 조용히 제외한다.

    contracts 마스터에 등록된 모든 계약을 결과에 포함한다(다른 결합형 함수와
    동일한 pre-seeding 정책).

    Returns:
        {contract_no: {
            "gfm_amount": Decimal|None,
            "government_issue_count": int,
            "untagged_issue_count": int,
            "calculable": bool,
            "reason": str,
        }}
    """
    zero = Decimal("0")

    contract_nos = {
        c.get("contract_no") for c in contracts if c.get("contract_no") is not None
    }
    contract_no_by_wo = {
        w.get("wo_no"): w.get("contract_no")
        for w in work_orders if w.get("wo_no") is not None
    }

    result: dict[str, dict] = {
        contract_no: {
            "gfm_amount": zero,
            "government_issue_count": 0,
            "untagged_issue_count": 0,
            "calculable": True,
            "reason": None,
        }
        for contract_no in contract_nos
    }

    for r in material_issues:
        wo_no = r.get("wo_no")
        if wo_no is None:
            continue

        contract_no = contract_no_by_wo.get(wo_no)
        if contract_no is None or contract_no not in contract_nos:
            continue

        entry = result[contract_no]
        supply_type = r.get("supply_type")

        if supply_type is None:
            entry["untagged_issue_count"] += 1
            entry["calculable"] = False
            continue

        if supply_type != "GOVERNMENT":
            continue

        qty = _strict_decimal(r.get("issued_qty"))
        unit_cost = _strict_decimal(r.get("unit_cost"))
        if qty is None or unit_cost is None:
            continue

        line_amount = calculate_material_cost(qty, unit_cost)
        if r.get("issue_type") == "RETURN":
            line_amount = -line_amount

        entry["gfm_amount"] += line_amount
        entry["government_issue_count"] += 1

    for entry in result.values():
        if entry["calculable"]:
            entry["gfm_amount"] = round_amount(entry["gfm_amount"])
            entry["reason"] = "OK"
        else:
            entry["gfm_amount"] = None
            entry["reason"] = (
                f"material_issue {entry['untagged_issue_count']}건의 supply_type이 "
                "분류되지 않아 관급재료비를 계산할 수 없습니다."
            )

    return result


def calculate_actual_material_cost_excluding_gfm_by_contract(
    contracts,
    work_orders,
    material_issues,
) -> dict[str, dict]:
    """
    Phase 2 GA 규정 정합 구조 준비: contract_no -> 관급재료비(GFM)를 제외한
    사급재료비만의 실적 재료비 집계.

    calculate_actual_material_cost()(Phase 1 보호 함수, 이 함수를 만들면서도
    수정하지 않았다)는 supply_type을 전혀 참조하지 않고 모든 material_issue
    행을 그대로 합산한다 — 그 결과는 "사급재료비만"이 아니라 "관급+사급을
    합친 총 재료비"다(이전 라운드에서 synthetic 테스트로 확인됨:
    test_actual_material_cost_ignores_supply_type_includes_everything).
    방산원가규칙 제6조의 제조원가 정의(관급재료비 제외)를 만족하는 별도
    계산 경로가 필요해 이 함수를 신설한다 — 기존 함수를 대체하지 않고
    나란히 존재하는 새 함수다.

    wo_no -> work_order.contract_no 귀속 방식은
    calculate_government_furnished_material_by_contract()와 완전히 동일하게
    유지한다(material master/product 등록 여부는 검사하지 않는다 — Phase 1
    DM 집계의 엄격한 유효성 검사와는 다른, GA 결합형 함수 계열의 기존
    스타일을 따른 것이다). 두 함수가 정확히 같은 wo_no->contract_no
    매핑을 쓰기 때문에, 모든 관련 행의 supply_type이 분류되어 있다면
    다음 항등식이 항상 성립한다(이중집계 없음의 근거):

        이 함수의 dm_excluding_gfm
      + calculate_government_furnished_material_by_contract()의 gfm_amount
      = 그 계약에 귀속되는 material_issue 전체 금액(순액, RETURN 반영)

    "계산 불가 ≠ 0" 원칙은 GFM 함수와 완전히 동일하게 적용한다: 어떤
    계약에 귀속되는 material_issue 행 중 하나라도 supply_type이
    None(미분류)이면, 그 행이 실제로 관급인지 사급인지 알 수 없으므로
    계약 전체를 계산 불가(calculable=False, dm_excluding_gfm=None)로
    남긴다 — 미분류 행을 "사급(그대로 포함)"으로 임의 간주하지 않는다.

    supply_type == "GOVERNMENT"인 행은 금액에서 제외한다. "GOVERNMENT"가
    아닌 다른 명시적 값(예: "COMPANY")만 금액에 더한다. issue_type이
    "RETURN"이면 차감한다(calculate_actual_material_cost()와 동일한
    계산 규칙).

    contracts 마스터에 등록된 모든 계약을 결과에 포함한다(다른 결합형
    함수와 동일한 pre-seeding 정책).

    이 함수는 아직 calculate_regulatory_ga_by_contract()에 연결되지
    않았다 — 준비 단계 코드다. CLI에도 연결되지 않는다.

    Returns:
        {contract_no: {
            "dm_excluding_gfm": Decimal|None,
            "company_issue_count": int,
            "untagged_issue_count": int,
            "calculable": bool,
            "reason": str,
        }}
    """
    zero = Decimal("0")

    contract_nos = {
        c.get("contract_no") for c in contracts if c.get("contract_no") is not None
    }
    contract_no_by_wo = {
        w.get("wo_no"): w.get("contract_no")
        for w in work_orders if w.get("wo_no") is not None
    }

    result: dict[str, dict] = {
        contract_no: {
            "dm_excluding_gfm": zero,
            "company_issue_count": 0,
            "untagged_issue_count": 0,
            "calculable": True,
            "reason": None,
        }
        for contract_no in contract_nos
    }

    for r in material_issues:
        wo_no = r.get("wo_no")
        if wo_no is None:
            continue

        contract_no = contract_no_by_wo.get(wo_no)
        if contract_no is None or contract_no not in contract_nos:
            continue

        entry = result[contract_no]
        supply_type = r.get("supply_type")

        if supply_type is None:
            entry["untagged_issue_count"] += 1
            entry["calculable"] = False
            continue

        if supply_type == "GOVERNMENT":
            continue

        qty = _strict_decimal(r.get("issued_qty"))
        unit_cost = _strict_decimal(r.get("unit_cost"))
        if qty is None or unit_cost is None:
            continue

        line_amount = calculate_material_cost(qty, unit_cost)
        if r.get("issue_type") == "RETURN":
            line_amount = -line_amount

        entry["dm_excluding_gfm"] += line_amount
        entry["company_issue_count"] += 1

    for entry in result.values():
        if entry["calculable"]:
            entry["dm_excluding_gfm"] = round_amount(entry["dm_excluding_gfm"])
            entry["reason"] = "OK"
        else:
            entry["dm_excluding_gfm"] = None
            entry["reason"] = (
                f"material_issue {entry['untagged_issue_count']}건의 supply_type이 "
                "분류되지 않아 관급재료비 제외 재료비를 계산할 수 없습니다."
            )

    return result
