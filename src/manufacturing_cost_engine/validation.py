from __future__ import annotations
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from datetime import date, datetime
from typing import Iterable

from .models import ValidationIssue
from .cost_engine import calculate_actual_material_cost, calculate_actual_labor_cost

def _issue(code, severity, file, sheet, row, message, entity=None):
    return ValidationIssue(code, severity, file, sheet, row, message, entity)

def required_columns(rows, required, file, sheet):
    if not rows:
        return []
    missing = [c for c in required if c not in rows[0]]
    return [
        _issue("MISSING_REQUIRED_COLUMN", "CRITICAL", file, sheet, None,
               f"필수 컬럼 누락: {', '.join(missing)}")
    ] if missing else []

def duplicate_keys(rows, key_cols, file, sheet):
    seen = {}
    issues = []
    for r in rows:
        key = tuple(r.get(c) for c in key_cols)
        if any(v is None for v in key):
            continue
        if key in seen:
            issues.append(_issue(
                "DUPLICATE_NATURAL_KEY", "CRITICAL", file, sheet,
                r.get("_source_row"),
                f"자연키 중복: {key}"
            ))
        else:
            seen[key] = r.get("_source_row")
    return issues

def validate_period_rows(rows, file="02_period.xlsx", sheet="period"):
    issues = []
    for r in rows:
        pk = r.get("period_key")
        year, month = r.get("year"), r.get("month")
        if pk is None or year is None or month is None:
            continue
        expected = f"{int(year):04d}-{int(month):02d}"
        if str(pk) != expected:
            issues.append(_issue(
                "PERIOD_KEY_INCONSISTENT", "ERROR", file, sheet,
                r.get("_source_row"), f"period_key={pk}, expected={expected}", pk
            ))
    return issues

def validate_work_orders(rows, products, file="20_work_order.xlsx", sheet="work_order"):
    issues = []
    product_uom = {r["product_code"]: r["base_uom"] for r in products if r.get("product_code")}
    for r in rows:
        p = r.get("product_code")
        if p not in product_uom:
            issues.append(_issue(
                "UNKNOWN_PRODUCT", "CRITICAL", file, sheet, r.get("_source_row"),
                f"등록되지 않은 제품: {p}", p
            ))
            continue
        if r.get("uom") != product_uom[p]:
            issues.append(_issue(
                "WO_UOM_MISMATCH", "ERROR", file, sheet, r.get("_source_row"),
                f"WO UOM={r.get('uom')}, Product UOM={product_uom[p]}", r.get("wo_no")
            ))
    return issues

def validate_material_issues(rows, materials, work_orders, cost_centers,
                             file="22_material_issue.xlsx", sheet="material_issue"):
    """
    참고: 실제 22_material_issue.xlsx에는 amount 컬럼이 없다(issued_qty × unit_cost와
    대사할 실제 금액 자체가 존재하지 않음). 그래서 AMOUNT_MISMATCH는 이 함수에서
    검증하지 않는다 — 비교할 대상이 없는 상태를 억지로 만들지 않는다.
    """
    issues = []
    material_set = {r.get("material_code") for r in materials}
    wo_set = {r.get("wo_no") for r in work_orders}
    cc_set = {r.get("cost_center_code") for r in cost_centers}
    for r in rows:
        if r.get("material_code") not in material_set:
            issues.append(_issue(
                "UNKNOWN_MATERIAL", "CRITICAL", file, sheet, r.get("_source_row"),
                f"등록되지 않은 자재: {r.get('material_code')}", r.get("material_code")
            ))
        wo, cc = r.get("wo_no"), r.get("cost_center_code")
        if wo is None and cc is None:
            issues.append(_issue(
                "ISSUE_TARGET_MISSING", "CRITICAL", file, sheet, r.get("_source_row"),
                "wo_no와 cost_center_code가 모두 NULL입니다."
            ))
        if wo is not None and wo not in wo_set:
            issues.append(_issue(
                "UNKNOWN_WO", "CRITICAL", file, sheet, r.get("_source_row"),
                f"등록되지 않은 WO: {wo}", wo
            ))
        if cc is not None and cc not in cc_set:
            issues.append(_issue(
                "UNKNOWN_COST_CENTER", "CRITICAL", file, sheet, r.get("_source_row"),
                f"등록되지 않은 원가센터: {cc}", cc
            ))

        try:
            qty = Decimal(str(r.get("issued_qty")))
        except (InvalidOperation, TypeError):
            issues.append(_issue(
                "INVALID_DECIMAL", "CRITICAL", file, sheet, r.get("_source_row"),
                f"issued_qty를 숫자로 변환할 수 없습니다: {r.get('issued_qty')!r}",
                r.get("issue_doc_no")
            ))
            continue

        if r.get("issue_type") == "ISSUE" and qty < 0:
            issues.append(_issue(
                "NEGATIVE_QUANTITY", "ERROR", file, sheet, r.get("_source_row"),
                "ISSUE의 issued_qty가 음수입니다.", r.get("issue_doc_no")
            ))
    return issues

def validate_labor(rows, routing_index,
                   file="23_labor_transaction.xlsx", sheet="labor_transaction"):
    issues = []
    for r in rows:
        try:
            regular = Decimal(str(r.get("regular_hours")))
            overtime = Decimal(str(r.get("overtime_hours")))
            actual = Decimal(str(r.get("actual_hours")))
        except (InvalidOperation, TypeError):
            continue
        if overtime < 0:
            issues.append(_issue(
                "NEGATIVE_OVERTIME", "ERROR", file, sheet, r.get("_source_row"),
                f"overtime_hours={overtime}", r.get("labor_doc_no")
            ))
        if actual != regular + overtime:
            issues.append(_issue(
                "HOURS_SUM_MISMATCH", "ERROR", file, sheet, r.get("_source_row"),
                f"actual={actual}, regular+overtime={regular+overtime}",
                r.get("labor_doc_no")
            ))
        key = (r.get("wo_no"), r.get("operation_seq"))
        if key not in routing_index:
            issues.append(_issue(
                "UNKNOWN_ROUTING_OPERATION", "ERROR", file, sheet, r.get("_source_row"),
                f"라우팅 공정 없음: {key}", r.get("labor_doc_no")
            ))
        else:
            expected_code = routing_index[key].get("operation_code")
            if expected_code != r.get("operation_code"):
                issues.append(_issue(
                    "OPERATION_CODE_MISMATCH", "WARNING", file, sheet,
                    r.get("_source_row"),
                    f"operation_code={r.get('operation_code')}, expected={expected_code}",
                    r.get("labor_doc_no")
                ))
    return issues

def validate_gl_balance(rows, file="24_gl_transaction.xlsx", sheet="gl_transaction"):
    groups = defaultdict(lambda: [Decimal("0"), Decimal("0"), None])
    for r in rows:
        doc = r.get("document_no")
        if doc is None:
            continue
        try:
            d = Decimal(str(r.get("debit")))
            c = Decimal(str(r.get("credit")))
        except (InvalidOperation, TypeError):
            continue
        groups[doc][0] += d
        groups[doc][1] += c
        groups[doc][2] = r.get("_source_row")
    issues = []
    for doc, (debit, credit, row) in groups.items():
        if debit != credit:
            issues.append(_issue(
                "GL_UNBALANCED_DOCUMENT", "CRITICAL", file, sheet, row,
                f"{doc}: debit={debit}, credit={credit}", doc
            ))
    return issues

# BOM_ISSUE tolerance: max(abs_tolerance, abs(expected_qty) * pct_tolerance).
DEFAULT_BOM_TOLERANCE = {"abs": Decimal("0.01"), "pct": Decimal("0.02")}
BOM_TOLERANCE_OVERRIDES = {
    "MAT-003": {"abs": Decimal("0.05"), "pct": Decimal("0.01")},
}

def _to_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None

def _bom_tolerance(material_code, expected_qty):
    cfg = BOM_TOLERANCE_OVERRIDES.get(material_code, DEFAULT_BOM_TOLERANCE)
    return max(cfg["abs"], abs(expected_qty) * cfg["pct"])

def _index_bom_items(bom_items):
    """bom_version_id -> material_code -> {"qty": Decimal, "uom": str}"""
    index = defaultdict(dict)
    for item in bom_items:
        bom_version_id = item.get("bom_version_id")
        material_code = item.get("material_code")
        if bom_version_id is None or material_code is None:
            continue
        qty = _to_decimal(item.get("standard_qty"))
        if qty is None:
            continue
        entry = index[bom_version_id].setdefault(
            material_code, {"qty": Decimal("0"), "uom": item.get("uom")}
        )
        entry["qty"] += qty
        entry["uom"] = item.get("uom")
    return index

def _index_material_issues(material_issues):
    """wo_no -> material_code -> {"qty": Decimal, "uoms": set, "last_row": int|None}"""
    index = defaultdict(dict)
    for r in material_issues:
        wo_no = r.get("wo_no")
        material_code = r.get("material_code")
        if wo_no is None or material_code is None:
            continue
        qty = _to_decimal(r.get("issued_qty"))
        if qty is None:
            continue
        signed_qty = -qty if r.get("issue_type") == "RETURN" else qty
        entry = index[wo_no].setdefault(
            material_code, {"qty": Decimal("0"), "uoms": set(), "last_row": None}
        )
        entry["qty"] += signed_qty
        uom = r.get("uom")
        if uom is not None:
            entry["uoms"].add(uom)
        entry["last_row"] = r.get("_source_row")
    return index

def validate_bom_issues(work_orders, bom_items, material_issues, materials,
                        file="22_material_issue.xlsx", sheet="material_issue"):
    """
    WO의 bom_version_id 기준 BOM 표준투입량과 material_issue 순출고량(ISSUE-RETURN)을
    비교해 tolerance를 벗어나면 BOM_ISSUE를 생성한다.
    BOM 미등재 자재(expected=0)와 미출고 자재(actual=0)도 동일 경로로 판정한다.
    """
    issues = []
    bom_index = _index_bom_items(bom_items)
    issue_index = _index_material_issues(material_issues)
    material_uom = {
        m.get("material_code"): m.get("base_uom")
        for m in materials if m.get("material_code")
    }

    for wo in work_orders:
        wo_no = wo.get("wo_no")
        planned_qty = _to_decimal(wo.get("planned_qty"))
        if wo_no is None or planned_qty is None:
            continue

        bom_materials = bom_index.get(wo.get("bom_version_id"), {})
        issued_materials = issue_index.get(wo_no, {})

        for material_code in set(bom_materials) | set(issued_materials):
            bom_entry = bom_materials.get(material_code)
            issue_entry = issued_materials.get(material_code)

            bom_uom = bom_entry["uom"] if bom_entry else None
            issue_uoms = issue_entry["uoms"] if issue_entry else set()
            source_row = issue_entry["last_row"] if issue_entry else None

            if bom_uom is not None and issue_uoms and issue_uoms != {bom_uom}:
                base_uom = material_uom.get(material_code)
                issues.append(_issue(
                    "UOM_CONVERSION_MISSING", "REVIEW_REQUIRED", file, sheet,
                    source_row,
                    f"WO={wo_no}, material={material_code}: BOM UOM={bom_uom}, "
                    f"Issue UOM={','.join(sorted(issue_uoms))}, "
                    f"base_uom={base_uom} 기준 환산 불가",
                    material_code
                ))
                continue

            expected_qty = (bom_entry["qty"] * planned_qty) if bom_entry else Decimal("0")
            actual_qty = issue_entry["qty"] if issue_entry else Decimal("0")
            difference = actual_qty - expected_qty
            tolerance = _bom_tolerance(material_code, expected_qty)

            if abs(difference) > tolerance:
                issues.append(_issue(
                    "BOM_ISSUE", "ERROR", file, sheet, source_row,
                    f"WO={wo_no}, material={material_code}: expected={expected_qty}, "
                    f"actual={actual_qty}, diff={difference}, tolerance={tolerance}",
                    material_code
                ))

    return issues

def _index_routing_versions(routing_versions):
    """routing_version_id -> routing_version(header) row"""
    index = {}
    for h in routing_versions:
        rvid = h.get("routing_version_id")
        if rvid is not None:
            index[rvid] = h
    return index

def _index_routing_operations(routing_operations):
    """routing_version_id -> [routing_operation rows]"""
    index = defaultdict(list)
    for op in routing_operations:
        rvid = op.get("routing_version_id")
        if rvid is not None:
            index[rvid].append(op)
    return index

def validate_routing(work_orders, routing_versions, routing_operations, work_centers):
    """
    11_routing.xlsx(routing_version/routing_operation) 마스터 무결성과
    Work Order.product_code ↔ Routing 연결을 검증한다.

    참고: 실제 20_work_order.xlsx에는 routing_version_id 컬럼이 없다
    (bom_version_id와 달리 스냅샷 컬럼이 아직 없음). 따라서 WO는
    product_code를 통해서만 routing_version과 연결된다. WO 행에
    routing_version_id가 명시적으로 존재하는 경우(향후 스키마 확장 대비)에는
    그 값을 우선 사용해 header.product_code와 대사한다.
    """
    issues = []

    header_index = _index_routing_versions(routing_versions)
    operations_by_version = _index_routing_operations(routing_operations)
    work_center_codes = {
        wc.get("work_center_code") for wc in work_centers if wc.get("work_center_code")
    }

    # --- Work Order <-> Routing header 연결 (product_code 기준) ---
    for wo in work_orders:
        wo_no = wo.get("wo_no")
        product_code = wo.get("product_code")
        explicit_rvid = wo.get("routing_version_id")

        if explicit_rvid is not None:
            header = header_index.get(explicit_rvid)
            if header is None:
                issues.append(_issue(
                    "UNKNOWN_ROUTING", "CRITICAL", "20_work_order.xlsx", "work_order",
                    wo.get("_source_row"),
                    f"존재하지 않는 routing_version_id: {explicit_rvid}", wo_no
                ))
            elif header.get("product_code") != product_code:
                issues.append(_issue(
                    "ROUTING_PRODUCT_MISMATCH", "ERROR", "20_work_order.xlsx", "work_order",
                    wo.get("_source_row"),
                    f"WO product_code={product_code}, routing({explicit_rvid}) "
                    f"product_code={header.get('product_code')}", wo_no
                ))
            continue

        if not any(h.get("product_code") == product_code for h in routing_versions):
            issues.append(_issue(
                "UNKNOWN_ROUTING", "CRITICAL", "20_work_order.xlsx", "work_order",
                wo.get("_source_row"),
                f"product_code={product_code}에 대응하는 routing이 없습니다.", wo_no
            ))

    # --- Routing header <-> detail (routing_operation) 관계 ---
    known_versions = set(header_index)
    versions_with_ops = set(operations_by_version)

    for rvid in known_versions - versions_with_ops:
        header = header_index[rvid]
        issues.append(_issue(
            "ROUTING_OPERATION_MISSING", "ERROR", "11_routing.xlsx", "routing_version",
            header.get("_source_row"),
            f"routing_version_id={rvid}에 등록된 routing_operation이 없습니다.", rvid
        ))

    for rvid in versions_with_ops - known_versions:
        for op in operations_by_version[rvid]:
            issues.append(_issue(
                "UNKNOWN_ROUTING", "CRITICAL", "11_routing.xlsx", "routing_operation",
                op.get("_source_row"),
                f"존재하지 않는 routing_version_id를 참조하는 operation: {rvid}", rvid
            ))

    # --- Routing operation 행 단위 검증 ---
    for op in routing_operations:
        rvid = op.get("routing_version_id")
        row = op.get("_source_row")

        seq_value = _to_decimal(op.get("operation_seq"))
        if (
            seq_value is None
            or seq_value != seq_value.to_integral_value()
            or seq_value <= 0
        ):
            issues.append(_issue(
                "INVALID_ROUTING_OPERATION_SEQ", "CRITICAL", "11_routing.xlsx",
                "routing_operation", row,
                f"operation_seq가 유효하지 않습니다: {op.get('operation_seq')!r}", rvid
            ))

        if not op.get("operation_code"):
            issues.append(_issue(
                "ROUTING_OPERATION_CODE_MISSING", "ERROR", "11_routing.xlsx",
                "routing_operation", row,
                f"operation_code가 비어 있습니다 (routing_version_id={rvid}, "
                f"operation_seq={op.get('operation_seq')})", rvid
            ))

        work_center_code = op.get("work_center_code")
        if not work_center_code:
            issues.append(_issue(
                "ROUTING_WORK_CENTER_MISSING", "CRITICAL", "11_routing.xlsx",
                "routing_operation", row,
                f"work_center_code가 비어 있습니다 (routing_version_id={rvid}, "
                f"operation_seq={op.get('operation_seq')})", rvid
            ))
        elif work_center_code not in work_center_codes:
            issues.append(_issue(
                "UNKNOWN_WORK_CENTER", "CRITICAL", "11_routing.xlsx",
                "routing_operation", row,
                f"등록되지 않은 work_center: {work_center_code}", work_center_code
            ))

        hours = _to_decimal(op.get("standard_hours"))
        if hours is None:
            issues.append(_issue(
                "INVALID_STANDARD_HOURS", "ERROR", "11_routing.xlsx",
                "routing_operation", row,
                f"standard_hours가 유효하지 않습니다: {op.get('standard_hours')!r}", rvid
            ))
        elif hours < 0:
            issues.append(_issue(
                "INVALID_STANDARD_HOURS", "ERROR", "11_routing.xlsx",
                "routing_operation", row,
                f"standard_hours가 음수입니다: {hours}", rvid
            ))

    # --- routing_version_id + operation_seq 자연키 중복 (기존 헬퍼 재사용) ---
    issues += duplicate_keys(
        routing_operations, ["routing_version_id", "operation_seq"],
        "11_routing.xlsx", "routing_operation"
    )

    return issues

def _index_account_mappings(account_mappings):
    """company_code -> gl_account_code -> [account_mapping rows]"""
    index = defaultdict(lambda: defaultdict(list))
    for m in account_mappings:
        company_code = m.get("company_code")
        gl_account_code = m.get("gl_account_code")
        if company_code is None or gl_account_code is None:
            continue
        index[company_code][gl_account_code].append(m)
    return index

def _mapping_priority(mapping_row):
    priority = _to_decimal(mapping_row.get("priority"))
    return priority if priority is not None else Decimal("-Infinity")

def validate_account_mapping(gl_transactions, account_mappings,
                             file="24_gl_transaction.xlsx", sheet="gl_transaction"):
    """
    Phase 1 cost element classification 규칙 (일반 회계원칙이 아니라 이 데이터셋 전용 규칙):
    24_gl_transaction.xlsx는 "소비 대체분개" 구조라 차변(debit)이 실제 원가 발생,
    대변(credit)은 원재료 등 대차대조표 상계 계정이다. 따라서 순수 차변 라인
    (debit > 0 이고 credit == 0)만 account_mapping을 통해 cost_element로 분류하고,
    credit 라인은 대상에서 제외한다. debit/credit이 둘 다 채워진 라인(예: 차대불균형
    오류가 섞인 행)은 이 분류 대상이 아니며 GL_UNBALANCED_DOCUMENT 등 별도 검증이 다룬다.

    후보 = company_code + gl_account_code 일치 AND
           (mapping.cost_center_code == gl.cost_center_code OR mapping.cost_center_code IS NULL)
    선택 = priority DESC, 동일 priority면 cost_center_code가 NULL이 아닌 쪽 우선
    0건 -> UNMAPPED_GL(WARNING), 최종 동순위 후보 2개 이상 -> MAPPING_AMBIGUOUS(REVIEW_REQUIRED)
    """
    issues = []
    mapping_index = _index_account_mappings(account_mappings)

    for r in gl_transactions:
        debit = _to_decimal(r.get("debit"))
        credit = _to_decimal(r.get("credit"))
        if debit is None or debit <= 0:
            continue
        if credit is not None and credit != 0:
            continue

        company_code = r.get("company_code")
        gl_account_code = r.get("gl_account_code")
        cost_center_code = r.get("cost_center_code")
        row = r.get("_source_row")

        candidates = [
            m for m in mapping_index.get(company_code, {}).get(gl_account_code, [])
            if m.get("cost_center_code") == cost_center_code
            or m.get("cost_center_code") is None
        ]

        if not candidates:
            issues.append(_issue(
                "UNMAPPED_GL", "WARNING", file, sheet, row,
                f"매핑 없음: company_code={company_code}, gl_account_code={gl_account_code}",
                gl_account_code
            ))
            continue

        top_priority = max(_mapping_priority(m) for m in candidates)
        top_candidates = [m for m in candidates if _mapping_priority(m) == top_priority]

        if any(m.get("cost_center_code") is not None for m in top_candidates):
            top_candidates = [
                m for m in top_candidates if m.get("cost_center_code") is not None
            ]

        if len(top_candidates) > 1:
            issues.append(_issue(
                "MAPPING_AMBIGUOUS", "REVIEW_REQUIRED", file, sheet, row,
                f"동순위 매핑 {len(top_candidates)}건: company_code={company_code}, "
                f"gl_account_code={gl_account_code}, priority={top_priority}",
                gl_account_code
            ))

    return issues

# 14_tolerance_rule.xlsx AMOUNT_CHECK(abs_tolerance=0.01)와 동일한 허용오차를 재사용한다.
STANDARD_COST_AMOUNT_TOLERANCE = Decimal("0.01")

def _sum_standard_cost_detail(standard_cost_detail):
    """(company,product,period,element,version) -> Σ detail.standard_amount"""
    sums = {}
    for d in standard_cost_detail:
        key = (
            d.get("company_code"), d.get("product_code"), d.get("period_key"),
            d.get("cost_element_code"), d.get("version"),
        )
        if any(v is None for v in key):
            continue
        amount = _to_decimal(d.get("standard_amount"))
        if amount is None:
            continue
        sums[key] = sums.get(key, Decimal("0")) + amount
    return sums

def validate_standard_cost(standard_cost_header, standard_cost_detail, products,
                           cost_elements, materials):
    """
    12_standard_cost.xlsx(이미 확정된 표준원가 마스터)의 정합성만 검증한다.
    새 표준원가를 BOM/Routing으로부터 재계산하지 않는다 — standard_cost_detail이
    없는 제품(P-100/300/400)에 대해 BOM×material 단가로 역산한 값과 header가 달라도,
    그 차이를 검증 대상으로 삼을 근거(공식 detail)가 없으므로 다루지 않는다.

    - Header 자연키 중복은 기존 duplicate_keys() 재사용
    - Header 자체 검산(qty×price≈amount)은 기존 AMOUNT_MISMATCH 재사용
    - product/material FK 위반은 기존 UNKNOWN_PRODUCT/UNKNOWN_MATERIAL 재사용
    - Detail↔Header 합계는 detail이 실제 존재하는 조합에서만 검증(없으면 스킵)
    - GA(is_manufacturing=N)는 completeness 판정을 product 단위로만 하므로
      GA 행 부재를 별도로 오류 처리하지 않는다(현재 12_standard_cost.xlsx엔 GA 자체가 없음)
    """
    issues = []

    header_file, header_sheet = "12_standard_cost.xlsx", "standard_cost"
    detail_file, detail_sheet = "12_standard_cost.xlsx", "standard_cost_detail"

    product_codes = {p.get("product_code") for p in products}
    active_product_codes = {
        p.get("product_code") for p in products if p.get("is_active") == "Y"
    }
    cost_element_codes = {c.get("cost_element_code") for c in cost_elements}
    material_codes = {m.get("material_code") for m in materials}

    # A. Header 자연키 중복 (기존 헬퍼 재사용)
    issues += duplicate_keys(
        standard_cost_header,
        ["company_code", "product_code", "period_key", "cost_element_code", "version"],
        header_file, header_sheet,
    )

    # B. Header 자체 검산 + C. Header FK
    for h in standard_cost_header:
        row = h.get("_source_row")
        product_code = h.get("product_code")
        cost_element_code = h.get("cost_element_code")

        if product_code not in product_codes:
            issues.append(_issue(
                "UNKNOWN_PRODUCT", "CRITICAL", header_file, header_sheet, row,
                f"등록되지 않은 제품: {product_code}", product_code
            ))

        if cost_element_code not in cost_element_codes:
            issues.append(_issue(
                "UNKNOWN_COST_ELEMENT", "CRITICAL", header_file, header_sheet, row,
                f"등록되지 않은 cost_element: {cost_element_code}", cost_element_code
            ))

        qty = _to_decimal(h.get("standard_qty"))
        price = _to_decimal(h.get("standard_unit_price"))
        amount = _to_decimal(h.get("standard_amount"))
        if qty is None or price is None or amount is None:
            continue
        expected = qty * price
        if abs(amount - expected) > STANDARD_COST_AMOUNT_TOLERANCE:
            issues.append(_issue(
                "AMOUNT_MISMATCH", "ERROR", header_file, header_sheet, row,
                f"standard_amount={amount}, expected={expected} "
                f"(standard_qty={qty} x standard_unit_price={price})",
                product_code
            ))

    # D. Detail FK
    for d in standard_cost_detail:
        row = d.get("_source_row")
        product_code = d.get("product_code")
        cost_element_code = d.get("cost_element_code")
        ref_material_code = d.get("ref_material_code")

        if product_code not in product_codes:
            issues.append(_issue(
                "UNKNOWN_PRODUCT", "CRITICAL", detail_file, detail_sheet, row,
                f"등록되지 않은 제품: {product_code}", product_code
            ))

        if cost_element_code not in cost_element_codes:
            issues.append(_issue(
                "UNKNOWN_COST_ELEMENT", "CRITICAL", detail_file, detail_sheet, row,
                f"등록되지 않은 cost_element: {cost_element_code}", cost_element_code
            ))

        if ref_material_code is not None and ref_material_code not in material_codes:
            issues.append(_issue(
                "UNKNOWN_MATERIAL", "CRITICAL", detail_file, detail_sheet, row,
                f"등록되지 않은 자재: {ref_material_code}", ref_material_code
            ))

    # E. Detail -> Header 합계 (detail이 실제로 존재하는 조합만 검증)
    detail_sums = _sum_standard_cost_detail(standard_cost_detail)
    for h in standard_cost_header:
        key = (
            h.get("company_code"), h.get("product_code"), h.get("period_key"),
            h.get("cost_element_code"), h.get("version"),
        )
        if key not in detail_sums:
            continue
        header_amount = _to_decimal(h.get("standard_amount"))
        if header_amount is None:
            continue
        detail_sum = detail_sums[key]
        if abs(detail_sum - header_amount) > STANDARD_COST_AMOUNT_TOLERANCE:
            issues.append(_issue(
                "STD_DETAIL_SUM_MISMATCH", "ERROR", detail_file, detail_sheet,
                h.get("_source_row"),
                f"product={h.get('product_code')}, element={h.get('cost_element_code')}: "
                f"detail_sum={detail_sum}, header={header_amount}",
                h.get("product_code")
            ))

    # F. Standard Cost 완전성: active product인데 header가 아예 없는 제품
    products_with_header = {h.get("product_code") for h in standard_cost_header}
    for product_code in active_product_codes - products_with_header:
        product_row = next(
            (p for p in products if p.get("product_code") == product_code), None
        )
        issues.append(_issue(
            "STANDARD_COST_MISSING", "ERROR", "07_product_master.xlsx", "product",
            product_row.get("_source_row") if product_row else None,
            f"product_code={product_code}에 대한 standard_cost가 없습니다.",
            product_code
        ))

    return issues

def validate_actual_cost(work_orders, production_outputs, labor_transactions,
                         work_centers, overhead_rates):
    """
    Actual Cost 계산 자체가 아니라, 계산이 불가능하거나(NOT_CALCULABLE) 배부가
    되지 않는(NOT_ALLOCATED) 케이스를 보고한다. 실제 DM/DL/OH 금액 계산은
    cost_engine.calculate_actual_*() 쪽 책임이며 여기서는 재계산하지 않는다.

    - 산출 실적(production_output)이 전혀 없는 WO -> NO_PRODUCTION_OUTPUT
    - good_qty 합계가 0인 WO -> ZERO_DENOMINATOR (0%/0원 등 임의값 반환 금지)
    - DIRECT labor가 발생한 (period, cost_center)에 overhead_rate가 없으면
      -> OVERHEAD_NOT_ALLOCATED (임의로 다른 CC 요율을 대신 적용하지 않음)
    """
    issues = []

    good_qty_by_wo = {}
    has_output_row = set()
    for po in production_outputs:
        wo_no = po.get("wo_no")
        if wo_no is None:
            continue
        has_output_row.add(wo_no)
        qty = _to_decimal(po.get("good_qty"))
        if qty is None:
            continue
        good_qty_by_wo[wo_no] = good_qty_by_wo.get(wo_no, Decimal("0")) + qty

    for wo in work_orders:
        wo_no = wo.get("wo_no")
        if wo_no is None:
            continue

        if wo_no not in has_output_row:
            issues.append(_issue(
                "NO_PRODUCTION_OUTPUT", "NOT_CALCULABLE", "21_production_output.xlsx",
                "production_output", wo.get("_source_row"),
                f"WO={wo_no}: 산출 실적이 없어 단위원가를 계산할 수 없습니다.", wo_no
            ))
            continue

        if good_qty_by_wo.get(wo_no, Decimal("0")) == 0:
            issues.append(_issue(
                "ZERO_DENOMINATOR", "NOT_CALCULABLE", "21_production_output.xlsx",
                "production_output", wo.get("_source_row"),
                f"WO={wo_no}: good_qty 합계가 0이라 단위원가를 계산할 수 없습니다.", wo_no
            ))

    work_center_to_cc = {
        wc.get("work_center_code"): wc.get("cost_center_code")
        for wc in work_centers if wc.get("work_center_code")
    }
    rate_keys = {
        (r.get("period_key"), r.get("cost_center_code")) for r in overhead_rates
    }
    wo_period = {w.get("wo_no"): w.get("period_key") for w in work_orders}

    reported = set()
    for r in labor_transactions:
        if r.get("direct_indirect") != "DIRECT":
            continue
        wo_no = r.get("wo_no")
        if wo_no not in wo_period:
            continue

        cost_center_code = work_center_to_cc.get(r.get("work_center_code"))
        if cost_center_code is None:
            continue

        period_key = wo_period.get(wo_no)
        key = (period_key, cost_center_code)
        if key in rate_keys or key in reported:
            continue
        reported.add(key)

        issues.append(_issue(
            "OVERHEAD_NOT_ALLOCATED", "NOT_ALLOCATED", "13_overhead_rate.xlsx",
            "overhead_rate", None,
            f"cost_center={cost_center_code}, period={period_key}: "
            f"overhead_rate가 없어 OH가 배부되지 않습니다.",
            cost_center_code
        ))

    return issues

# GL Reconciliation은 phase1_dataset_build_spec.md §7-7 근거로 DM/DL만 비교한다.
# OH/GA는 발생주의 조정 계정 성격이라 원천 거래 대사가 원칙적으로 불가능하므로 제외한다.
RECONCILED_COST_ELEMENTS = ("DM", "DL")

# 14_tolerance_rule.xlsx GL_RECON: abs_tolerance=10, pct_tolerance=0.001, GREATER_OF.
GL_RECON_ABS_TOLERANCE = Decimal("10")
GL_RECON_PCT_TOLERANCE = Decimal("0.001")

def _resolve_gl_account_mapping(gl_line, mapping_index):
    """
    validate_account_mapping()과 동일한 우선순위/구체성 규칙으로 GL 라인 하나를 해석한다.
    성공하면 매핑 행(dict)을, 매핑이 없거나(0건) 모호하면(동순위 2건 이상) None을 반환한다.
    그 실패 케이스(UNMAPPED_GL/MAPPING_AMBIGUOUS)는 validate_account_mapping()이 이미
    보고하므로 여기서는 다시 issue를 만들지 않고 단순히 집계에서 제외한다.
    """
    candidates = [
        m for m in mapping_index.get(gl_line.get("company_code"), {}).get(
            gl_line.get("gl_account_code"), []
        )
        if m.get("cost_center_code") == gl_line.get("cost_center_code")
        or m.get("cost_center_code") is None
    ]
    if not candidates:
        return None

    top_priority = max(_mapping_priority(m) for m in candidates)
    top_candidates = [m for m in candidates if _mapping_priority(m) == top_priority]

    if any(m.get("cost_center_code") is not None for m in top_candidates):
        top_candidates = [
            m for m in top_candidates if m.get("cost_center_code") is not None
        ]

    if len(top_candidates) != 1:
        return None

    return top_candidates[0]

def _gl_dm_dl_totals(gl_transactions, account_mappings):
    """(company_code, period_key, cost_element_code) -> Σ debit. DM/DL만 집계한다."""
    mapping_index = _index_account_mappings(account_mappings)
    totals = {}

    for r in gl_transactions:
        debit = _to_decimal(r.get("debit"))
        credit = _to_decimal(r.get("credit"))
        if debit is None or debit <= 0:
            continue
        if credit is not None and credit != 0:
            continue

        mapping_row = _resolve_gl_account_mapping(r, mapping_index)
        if mapping_row is None:
            continue

        cost_element_code = mapping_row.get("cost_element_code")
        if cost_element_code not in RECONCILED_COST_ELEMENTS:
            continue

        key = (r.get("company_code"), r.get("period_key"), cost_element_code)
        totals[key] = totals.get(key, Decimal("0")) + debit

    return totals

def _period_end_dates(periods):
    """(company_code, period_key) -> end_date 문자열(YYYY-MM-DD, 문자열 비교로 충분)."""
    return {
        (p.get("company_code"), p.get("period_key")): p.get("end_date")
        for p in periods if p.get("period_key") is not None
    }

def _is_period_spanning(work_order, period_end_dates):
    """
    work_order.end_date가 소속 period의 종료일보다 늦으면 기간 걸침으로 본다
    (phase1_dataset_build_spec.md R-6/E-026). end_date가 없는(아직 진행 중인) WO는
    판단할 근거가 없으므로 걸침으로 간주하지 않는다.
    """
    end_date = work_order.get("end_date")
    if end_date is None:
        return False

    period_end = period_end_dates.get(
        (work_order.get("company_code"), work_order.get("period_key"))
    )
    if period_end is None:
        return False

    return str(end_date) > str(period_end)

def _actual_dm_dl_totals(work_orders, material_issues, labor_transactions, materials,
                         products, periods):
    """
    (company_code, period_key, cost_element_code) -> Σ Actual DM/DL.
    calculate_actual_material_cost()/calculate_actual_labor_cost()를 그대로 재사용해
    WO별 금액을 구한 뒤, 기간 걸침 WO(work_order.end_date > period.end_date)만
    집계에서 제외하고 그 금액을 별도로 모은다.

    Returns:
        (totals, excluded_wo_amount) — 둘 다 (company, period, element) 키의 dict
    """
    material_by_wo = calculate_actual_material_cost(
        work_orders, material_issues, materials, products
    )
    labor_by_wo = calculate_actual_labor_cost(work_orders, labor_transactions, products)
    period_end_dates = _period_end_dates(periods)
    wo_map = {w.get("wo_no"): w for w in work_orders}

    totals = {}
    excluded_wo_amount = {}

    for cost_element_code, amounts_by_wo in (("DM", material_by_wo), ("DL", labor_by_wo)):
        for wo_no, amount in amounts_by_wo.items():
            wo_row = wo_map.get(wo_no)
            if wo_row is None:
                continue

            key = (wo_row.get("company_code"), wo_row.get("period_key"), cost_element_code)
            if _is_period_spanning(wo_row, period_end_dates):
                excluded_wo_amount[key] = excluded_wo_amount.get(key, Decimal("0")) + amount
                continue

            totals[key] = totals.get(key, Decimal("0")) + amount

    return totals, excluded_wo_amount

def _gl_recon_tolerance(actual_amount):
    """
    GL_RECON(abs=10, pct=0.001, GREATER_OF)을 적용한다.
    pct의 기준(base)을 GL/Actual 중 어느 쪽으로 할지는 14_tolerance_rule.xlsx나
    설계 문서에 확정되어 있지 않다(phase1_dataset_build_spec.md §J-1-5,
    "GL_RECON 허용차이"는 미확정 항목으로 명시됨). 여기서는 Actual Cost 금액을
    기준으로 삼는다 — 이는 확정된 설계 규칙이 아니라 구현상의 선택이다.
    """
    return max(GL_RECON_ABS_TOLERANCE, abs(actual_amount) * GL_RECON_PCT_TOLERANCE)

def validate_gl_reconciliation(gl_transactions, account_mappings, work_orders,
                               material_issues, labor_transactions, materials,
                               products, periods):
    """
    (company_code, period_key, cost_element_code) 단위로 GL과 Actual Cost를 대사한다.

    확정된 범위:
      - DM/DL만 비교한다(§7-7). OH/GA는 다루지 않는다 — 실제로 OH도 tolerance를
        벗어나는 것이 확인되었지만, 설계 원칙(발생주의 조정 계정은 원천 거래로
        대사 불가)에 따라 이번 GL Reconciliation 대상에 포함하지 않는다.
      - GL 쪽은 debit>0 AND credit==0인 라인만, account_mapping으로 해석 가능한
        경우에만 집계한다. UNMAPPED_GL/MAPPING_AMBIGUOUS는 validate_account_mapping()
        이 이미 보고하므로 여기서는 조용히 제외한다.
      - WO별로 GL 금액을 임의 배분하지 않는다(GL에 wo_no가 없어 근거가 없음).
      - 기간을 넘겨 끝나는 WO는 Actual 집계에서 제외하고 excluded_wo_amount로
        메시지에 표시하며, 그 WO 자체는 EXCLUDED_WO로 별도 보고한다.

    90_expected_results.xlsx의 E-027(expected_value=1)과 91_error_catalog.xlsx의
    행 범위(30~44, 실제로는 DM/DL이 아니라 OH 계정)는 서로 맞지 않는 내부 불일치가
    있음이 확인되었다. 이 함수는 그 숫자를 맞추기 위해 DM 또는 DL을 임의로 제외하거나
    합치지 않으며, 실제 데이터 기준으로 DM/DL이 각각 tolerance를 초과하면 그대로
    2건의 GL_RECON_DIFFERENCE를 보고한다.
    """
    issues = []

    gl_totals = _gl_dm_dl_totals(gl_transactions, account_mappings)
    actual_totals, excluded_wo_amount = _actual_dm_dl_totals(
        work_orders, material_issues, labor_transactions, materials, products, periods
    )

    keys = set(gl_totals) | set(actual_totals)
    for key in keys:
        company_code, period_key, cost_element_code = key
        gl_amount = gl_totals.get(key, Decimal("0"))
        actual_amount = actual_totals.get(key, Decimal("0"))
        difference = gl_amount - actual_amount
        tolerance = _gl_recon_tolerance(actual_amount)

        if abs(difference) > tolerance:
            issues.append(_issue(
                "GL_RECON_DIFFERENCE", "ERROR", "24_gl_transaction.xlsx",
                "gl_transaction", None,
                f"company={company_code}, period={period_key}, "
                f"element={cost_element_code}: GL={gl_amount}, Actual={actual_amount}, "
                f"diff={difference}, tolerance={tolerance}, "
                f"excluded_wo_amount={excluded_wo_amount.get(key, Decimal('0'))}",
                cost_element_code
            ))

    period_end_dates = _period_end_dates(periods)
    for wo in work_orders:
        if _is_period_spanning(wo, period_end_dates):
            issues.append(_issue(
                "EXCLUDED_WO", "REVIEW_REQUIRED", "20_work_order.xlsx", "work_order",
                wo.get("_source_row"),
                f"WO={wo.get('wo_no')}: end_date={wo.get('end_date')}가 period "
                f"{wo.get('period_key')}의 종료일을 넘어 GL Reconciliation Actual "
                f"집계에서 제외됩니다.",
                wo.get("wo_no")
            ))

    return issues
