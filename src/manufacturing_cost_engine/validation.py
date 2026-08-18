from __future__ import annotations
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from datetime import date, datetime
from typing import Iterable

from .models import ValidationIssue

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
            amount = Decimal(str(r.get("amount")))
            unit = Decimal(str(r.get("unit_cost")))
        except (InvalidOperation, TypeError):
            continue
        if r.get("issue_type") == "ISSUE" and qty < 0:
            issues.append(_issue(
                "NEGATIVE_QUANTITY", "ERROR", file, sheet, r.get("_source_row"),
                "ISSUE의 issued_qty가 음수입니다.", r.get("issue_doc_no")
            ))
        expected = (unit * qty).quantize(Decimal("0.0001"))
        if amount != expected:
            issues.append(_issue(
                "AMOUNT_MISMATCH", "ERROR", file, sheet, r.get("_source_row"),
                f"amount={amount}, expected={expected}", r.get("issue_doc_no")
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
