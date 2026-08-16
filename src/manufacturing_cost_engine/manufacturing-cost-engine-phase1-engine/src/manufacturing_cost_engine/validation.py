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
