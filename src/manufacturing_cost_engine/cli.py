from __future__ import annotations
import argparse
from pathlib import Path
from collections import Counter

from .loader import load_dataset, duplicate_file_groups
from .validation import (
    validate_period_rows, validate_work_orders, validate_material_issues,
    validate_labor, validate_gl_balance, validate_routing, validate_account_mapping,
    validate_standard_cost, validate_actual_cost, validate_gl_reconciliation,
    validate_bom_issues, validate_gl_period, validate_tolerance_rules,
    validate_bom_version, validate_labor_hours, validate_duplicate_files,
    calculate_oh_under_over_applied, validate_contract, validate_direct_expense,
)
from .cost_engine import (
    calculate_actual_total_cost_by_wo, calculate_total_variance_by_wo,
    calculate_material_price_quantity_variance_by_wo,
    calculate_actual_total_cost_by_contract,
    calculate_standard_budget_by_contract,
    calculate_contract_variance,
    calculate_actual_direct_expense_by_contract,
    calculate_ga_by_contract,
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
    issues += validate_duplicate_files(duplicate_file_groups(root))
    issues += validate_period_rows(rows("02_period.xlsx", "period"))

    products = rows("07_product_master.xlsx", "product")
    issues += validate_work_orders(rows("20_work_order.xlsx", "work_order"), products)

    contracts = rows("30_contract.xlsx", "contract")
    issues += validate_contract(contracts, rows("20_work_order.xlsx", "work_order"))

    direct_expenses = rows("31_direct_expense.xlsx", "direct_expense")
    issues += validate_direct_expense(
        direct_expenses, contracts, rows("20_work_order.xlsx", "work_order")
    )

    issues += validate_material_issues(
        rows("22_material_issue.xlsx", "material_issue"),
        rows("08_material_master.xlsx", "material"),
        rows("20_work_order.xlsx", "work_order"),
        rows("03_cost_center.xlsx", "cost_center"),
    )

    issues += validate_bom_issues(
        rows("20_work_order.xlsx", "work_order"),
        rows("10_bom.xlsx", "bom_item"),
        rows("22_material_issue.xlsx", "material_issue"),
        rows("08_material_master.xlsx", "material"),
        rows("06_uom_conversion.xlsx", "uom_conversion"),
    )

    issues += validate_bom_version(rows("10_bom.xlsx", "bom_version"))

    issues += validate_tolerance_rules(rows("14_tolerance_rule.xlsx", "tolerance_rule"))

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
    issues += validate_labor_hours(
        rows("20_work_order.xlsx", "work_order"),
        labor_rows,
        rows("21_production_output.xlsx", "production_output"),
        rows("11_routing.xlsx", "routing_operation"),
        rows("11_routing.xlsx", "routing_version"),
    )
    issues += validate_gl_balance(rows("24_gl_transaction.xlsx", "gl_transaction"))
    issues += validate_gl_period(
        rows("24_gl_transaction.xlsx", "gl_transaction"),
        rows("02_period.xlsx", "period"),
    )
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

    variance_by_wo = calculate_total_variance_by_wo(
        work_orders,
        rows("22_material_issue.xlsx", "material_issue"),
        labor_rows,
        rows("08_material_master.xlsx", "material"),
        work_centers,
        overhead_rates,
        products,
        production_outputs,
        rows("12_standard_cost.xlsx", "standard_cost"),
    )
    print(f"Total Variance calculated for {len(variance_by_wo)} work order(s)")
    for wo_no in sorted(variance_by_wo):
        v = variance_by_wo[wo_no]
        print(f"  {wo_no}: total_variance={v['total_variance']}")

    pv_qv_by_wo = calculate_material_price_quantity_variance_by_wo(
        work_orders,
        rows("22_material_issue.xlsx", "material_issue"),
        rows("08_material_master.xlsx", "material"),
        products,
        production_outputs,
        rows("12_standard_cost.xlsx", "standard_cost_detail"),
    )
    print(f"DM Price/Quantity Variance calculated for {len(pv_qv_by_wo)} work order(s)")
    for wo_no in sorted(pv_qv_by_wo):
        v = pv_qv_by_wo[wo_no]
        print(f"  {wo_no}: price_variance={v['price_variance_total']}, quantity_variance={v['quantity_variance_total']}")

    oh_under_over_by_cc = calculate_oh_under_over_applied(
        rows("24_gl_transaction.xlsx", "gl_transaction"),
        rows("05_account_mapping.xlsx", "account_mapping"),
        work_orders,
        labor_rows,
        work_centers,
        overhead_rates,
        products,
    )
    print(f"OH Under/Over Applied calculated for {len(oh_under_over_by_cc)} (period, cost_center)")
    for key in sorted(oh_under_over_by_cc, key=str):
        v = oh_under_over_by_cc[key]
        print(f"  {key}: actual_oh={v['actual_oh']}, applied_oh={v['applied_oh']}, "
              f"difference={v['difference']}, no_labor_data={v['no_labor_data']}")

    actual_cost_by_contract = calculate_actual_total_cost_by_contract(
        work_orders, actual_cost_by_wo,
    )
    print(f"Contract Actual Cost calculated for {len(actual_cost_by_contract)} contract(s)")
    for contract_no in sorted(actual_cost_by_contract):
        v = actual_cost_by_contract[contract_no]
        print(f"  {contract_no}: work_orders={v['work_order_count']}, "
              f"DM={v['actual_material_cost']}, DL={v['actual_labor_cost']}, "
              f"OH={v['actual_overhead_cost']}, Total={v['actual_manufacturing_cost']}")

    budget_by_contract = calculate_standard_budget_by_contract(
        contracts, work_orders,
        rows("12_standard_cost.xlsx", "standard_cost"),
        products,
    )
    print(f"Contract Budget calculated for {len(budget_by_contract)} contract(s)")
    for contract_no in sorted(budget_by_contract):
        v = budget_by_contract[contract_no]
        print(f"  {contract_no}: work_orders={v['work_order_count']}, "
              f"DM={v['budget_material_cost']}, DL={v['budget_labor_cost']}, "
              f"OH={v['budget_overhead_cost']}, Total={v['budget_manufacturing_cost']}")

    contract_variance = calculate_contract_variance(
        contracts, actual_cost_by_contract, budget_by_contract,
    )
    print(f"Contract Variance calculated for {len(contract_variance)} contract(s)")
    for contract_no in sorted(contract_variance):
        v = contract_variance[contract_no]
        print(f"  {contract_no}: DM={v['dm_variance']}, DL={v['dl_variance']}, "
              f"OH={v['oh_variance']}, Total={v['total_variance']}, "
              f"budget_coverage_complete={v['budget_coverage_complete']}")

    de_by_contract = calculate_actual_direct_expense_by_contract(
        contracts, work_orders, direct_expenses,
    )
    print(f"Contract Direct Expense calculated for {len(de_by_contract)} contract(s)")
    for contract_no in sorted(de_by_contract):
        v = de_by_contract[contract_no]
        print(f"  {contract_no}: expenses={v['expense_count']}, "
              f"DE={v['direct_expense_amount']}")

    # 32_cost_rate_rule.xlsx는 아직 저장소에 없다 — 있으면 그대로 읽힌다(하드코딩 없음).
    rate_rules = rows("32_cost_rate_rule.xlsx", "cost_rate_rule")
    ga_by_contract = calculate_ga_by_contract(
        actual_cost_by_contract, budget_by_contract, rate_rules, contracts,
    )
    print(f"Contract GA calculated for {len(ga_by_contract)} contract(s)")
    for contract_no in sorted(ga_by_contract):
        v = ga_by_contract[contract_no]
        if v["calculable"]:
            print(f"  {contract_no}: rate={v['ga_rate']}%, GA_actual={v['ga_actual']}, "
                  f"GA_budget={v['ga_budget']}, GA_variance={v['ga_variance']}")
        else:
            print(f"  {contract_no}: calculable=False, reason={v['reason']}")

if __name__ == "__main__":
    main()
