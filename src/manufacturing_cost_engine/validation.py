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
