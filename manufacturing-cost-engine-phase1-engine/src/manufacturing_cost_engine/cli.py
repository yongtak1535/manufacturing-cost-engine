from __future__ import annotations
import argparse
from pathlib import Path
from collections import Counter

from .loader import load_dataset
from .validation import (
    validate_period_rows, validate_work_orders, validate_material_issues,
    validate_labor, validate_gl_balance
)

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

    wo_map = {r.get("wo_no"): r for r in rows("20_work_order.xlsx", "work_order")}
    routing_index = {}
    for r in rows("11_routing.xlsx", "routing_operation"):
        # Routing operation is indexed by (routing_version_id, seq).
        routing_index[(r.get("routing_version_id"), r.get("operation_seq"))] = r
    labor_rows = rows("23_labor_transaction.xlsx", "labor_transaction")
    labor_index = {}
    for r in labor_rows:
        wo = r.get("wo_no")
        wo_row = wo_map.get(wo)
        if wo_row:
            labor_index[(wo, r.get("operation_seq"))] = routing_index.get(
                (wo_row.get("routing_version_id"), r.get("operation_seq"))
            )
    issues += validate_labor(labor_rows, labor_index)
    issues += validate_gl_balance(rows("24_gl_transaction.xlsx", "gl_transaction"))

    print(f"Loaded sheets: {len(data)}")
    print(f"Validation issues: {len(issues)}")
    for code, count in Counter(i.code for i in issues).most_common():
        print(f"  {code}: {count}")

if __name__ == "__main__":
    main()
