from __future__ import annotations
import argparse
from pathlib import Path
from collections import Counter

from .loader import load_dataset
from .validation import (
    validate_period_rows, validate_work_orders, validate_material_issues,
    validate_labor, validate_gl_balance, validate_routing, validate_account_mapping,
    validate_standard_cost, validate_actual_cost, validate_gl_reconciliation
)
from .cost_engine import calculate_actual_total_cost_by_wo

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", help="Phase 1 Excel dataset directory")
    args = parser.parse_args()
    root = Path(args.dataset)

    data = load_dataset(root)

    def rows(file, sheet):
        return data.get(f"{file}::{sheet}", [])

    issues = []
    issues += validate_period_rows(rows("02_period.xlsx", "period"))

    products = rows("07_product_master.xlsx", "product")
    issues += validate_work_orders(rows("20_work_order.xlsx", "work_order"), products)

    issues += validate_material_issues(
        rows("22_material_issue.xlsx", "material_issue"),
        rows("08_material_master.xlsx", "material"),
        rows("20_work_order.xlsx", "work_order"),
        rows("03_cost_center.xlsx", "cost_center"),
    )

    issues += validate_routing(
        rows("20_work_order.xlsx", "work_order"),
        rows("11_routing.xlsx", "routing_version"),
        rows("11_routing.xlsx", "routing_operation"),
        rows("09_work_center.xlsx", "work_center"),
    )

    wo_map = {r.get("wo_no"): r for r in rows("20_work_order.xlsx", "work_order")}
    routing_index = {}
    for r in rows("11_routing.xlsx", "routing_operation"):
        # Routing operation is indexed by (routing_version_id, seq).
        routing_index[(r.get("routing_version_id"), r.get("operation_seq"))] = r

    # 20_work_order.xlsx에는 routing_version_id 컬럼이 없으므로, WO -> routing은
    # product_code를 통해 routing_version(header)에서 찾는다. WO 행에 routing_version_id가
    # 명시적으로 존재하면(향후 스키마 확장 대비) 그 값을 우선 사용한다.
    routing_version_by_product = {}
    for h in rows("11_routing.xlsx", "routing_version"):
        product_code = h.get("product_code")
        routing_version_id = h.get("routing_version_id")
        if product_code is not None and routing_version_id is not None:
            routing_version_by_product.setdefault(product_code, routing_version_id)

    def resolve_routing_version_id(wo_row):
        explicit = wo_row.get("routing_version_id")
        if explicit is not None:
            return explicit
        return routing_version_by_product.get(wo_row.get("product_code"))

    labor_rows = rows("23_labor_transaction.xlsx", "labor_transaction")
    labor_index = {}
    for r in labor_rows:
        wo = r.get("wo_no")
        wo_row = wo_map.get(wo)
        if not wo_row:
            continue
        routing_version_id = resolve_routing_version_id(wo_row)
        if routing_version_id is None:
            continue
        routing_row = routing_index.get((routing_version_id, r.get("operation_seq")))
        if routing_row is not None:
            labor_index[(wo, r.get("operation_seq"))] = routing_row
    issues += validate_labor(labor_rows, labor_index)
    issues += validate_gl_balance(rows("24_gl_transaction.xlsx", "gl_transaction"))
    issues += validate_account_mapping(
        rows("24_gl_transaction.xlsx", "gl_transaction"),
        rows("05_account_mapping.xlsx", "account_mapping"),
    )
    issues += validate_standard_cost(
        rows("12_standard_cost.xlsx", "standard_cost"),
        rows("12_standard_cost.xlsx", "standard_cost_detail"),
        products,
        rows("04_cost_element.xlsx", "cost_element"),
        rows("08_material_master.xlsx", "material"),
    )

    work_orders = rows("20_work_order.xlsx", "work_order")
    production_outputs = rows("21_production_output.xlsx", "production_output")
    work_centers = rows("09_work_center.xlsx", "work_center")
    overhead_rates = rows("13_overhead_rate.xlsx", "overhead_rate")

    issues += validate_actual_cost(
        work_orders, production_outputs, labor_rows, work_centers, overhead_rates,
    )

    actual_cost_by_wo = calculate_actual_total_cost_by_wo(
        work_orders,
        rows("22_material_issue.xlsx", "material_issue"),
        labor_rows,
        rows("08_material_master.xlsx", "material"),
        work_centers,
        overhead_rates,
        products,
    )

    issues += validate_gl_reconciliation(
        rows("24_gl_transaction.xlsx", "gl_transaction"),
        rows("05_account_mapping.xlsx", "account_mapping"),
        work_orders,
        rows("22_material_issue.xlsx", "material_issue"),
        labor_rows,
        rows("08_material_master.xlsx", "material"),
        products,
        rows("02_period.xlsx", "period"),
    )

    print(f"Loaded sheets: {len(data)}")
    print(f"Validation issues: {len(issues)}")
    for code, count in Counter(i.code for i in issues).most_common():
        print(f"  {code}: {count}")

    print(f"Actual Cost calculated for {len(actual_cost_by_wo)} work order(s)")
    total_actual_cost = sum(
        (v["total_cost"] for v in actual_cost_by_wo.values()), start=0
    )
    print(f"  Total Actual Cost (all WOs): {total_actual_cost}")

if __name__ == "__main__":
    main()
