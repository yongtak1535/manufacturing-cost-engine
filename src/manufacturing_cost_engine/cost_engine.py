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
