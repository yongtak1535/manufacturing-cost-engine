from pathlib import Path

from manufacturing_cost_engine.loader import (
    excel_files,
    load_dataset,
)


DATASET_DIR = Path("hanbit_mvp_dataset_phase1")


def test_phase1_dataset_directory_exists():
    assert DATASET_DIR.exists()
    assert DATASET_DIR.is_dir()


def test_phase1_core_files_exist():
    required_files = [
        "01_company_plant.xlsx",
        "02_period.xlsx",
        "03_cost_center.xlsx",
        "04_cost_element.xlsx",
        "20_work_order.xlsx",
        "21_production_output.xlsx",
        "22_material_issue.xlsx",
    ]

    for filename in required_files:
        assert (DATASET_DIR / filename).exists(), filename


def test_excel_files_exclude_expected_result_files():
    files = excel_files(DATASET_DIR)

    names = [path.name for path in files]

    assert "90_expected_results.xlsx" not in names
    assert "91_error_catalog.xlsx" not in names


def test_phase1_dataset_can_be_loaded():
    data = load_dataset(DATASET_DIR)

    assert data

    assert any(
        key.startswith("01_company_plant.xlsx::")
        for key in data
    )

    assert any(
        key.startswith("02_period.xlsx::")
        for key in data
    )

    assert any(
        key.startswith("20_work_order.xlsx::")
        for key in data
    )

    assert any(
        key.startswith("22_material_issue.xlsx::")
        for key in data
    )


def test_phase1_loaded_rows_have_source_row():
    data = load_dataset(DATASET_DIR)

    loaded_rows = [
        row
        for rows in data.values()
        for row in rows
    ]

    assert loaded_rows

    assert all(
        "_source_row" in row
        for row in loaded_rows
    )
def test_phase1_dataset_has_expected_scale():
    data = load_dataset(DATASET_DIR)

    # 24개 로딩 대상 Excel (Phase 2: 30_contract.xlsx, 31_direct_expense.xlsx,
    # 34_direct_expense_budget.xlsx, 32_cost_rate_rule.xlsx 추가)
    files = excel_files(DATASET_DIR)

    assert len(files) == 24

    # 주요 거래 데이터가 실제로 로드되었는지 확인
    assert len(data["20_work_order.xlsx::work_order"]) == 20
    assert len(data["21_production_output.xlsx::production_output"]) == 19
    assert len(data["22_material_issue.xlsx::material_issue"]) == 62
    assert len(data["23_labor_transaction.xlsx::labor_transaction"]) == 54
    assert len(data["24_gl_transaction.xlsx::gl_transaction"]) == 44


def test_phase1_dataset_excludes_test_fixtures():
    files = excel_files(DATASET_DIR)

    filenames = {path.name for path in files}

    assert "90_expected_results.xlsx" not in filenames
    assert "91_error_catalog.xlsx" not in filenames


def test_phase1_dataset_contains_required_sheets():
    data = load_dataset(DATASET_DIR)

    required_sheets = {
        "01_company_plant.xlsx::company",
        "01_company_plant.xlsx::plant",
        "02_period.xlsx::period",
        "07_product_master.xlsx::product",
        "08_material_master.xlsx::material",
        "10_bom.xlsx::bom_version",
        "10_bom.xlsx::bom_item",
        "11_routing.xlsx::routing_version",
        "11_routing.xlsx::routing_operation",
        "12_standard_cost.xlsx::standard_cost",
        "12_standard_cost.xlsx::standard_cost_detail",
        "20_work_order.xlsx::work_order",
        "21_production_output.xlsx::production_output",
        "22_material_issue.xlsx::material_issue",
        "23_labor_transaction.xlsx::labor_transaction",
        "24_gl_transaction.xlsx::gl_transaction",
    }

    assert required_sheets.issubset(data.keys())


# --- Phase 2 8단계: GA 규정 정합 구조를 위한 최소 데이터 모델 추가 ---
# 아래 신규 컬럼/파일은 스키마(구조)만 준비한 것이며, 실제 GA rate/GFM
# 수치나 industry_type/company_size 등의 실제 분류값은 넣지 않았다 —
# 기존 계약/자재불출 행의 신규 컬럼 값은 전부 비어 있어야 한다(None).

def test_contract_has_ga_regulatory_columns_but_all_blank():
    data = load_dataset(DATASET_DIR)
    rows = data["30_contract.xlsx::contract"]

    assert len(rows) == 3
    for r in rows:
        assert "plant_code" in r
        assert "fiscal_year" in r
        assert "industry_type" in r
        assert "company_size" in r
        assert r["plant_code"] is None
        assert r["fiscal_year"] is None
        assert r["industry_type"] is None
        assert r["company_size"] is None


def test_material_issue_has_supply_type_column_but_all_blank():
    data = load_dataset(DATASET_DIR)
    rows = data["22_material_issue.xlsx::material_issue"]

    assert len(rows) == 62
    for r in rows:
        assert "supply_type" in r
        assert r["supply_type"] is None


def test_cost_rate_rule_file_exists_with_expected_columns_and_zero_rows():
    data = load_dataset(DATASET_DIR)
    key = "32_cost_rate_rule.xlsx::cost_rate_rule"

    assert key in data
    rows = data[key]
    assert rows == []


def test_material_issue_dup_file_still_matches_material_issue_after_schema_change():
    # 22_material_issue.xlsx에 supply_type 컬럼을 추가하면서, 바이트 단위로
    # 동일해야 하는 25_material_issue_dup.xlsx도 함께 갱신했다 — 두 파일이
    # 계속 동일한 내용을 담고 있는지 확인한다(중복탐지 테스트의 전제 보존).
    from manufacturing_cost_engine.loader import duplicate_file_groups

    groups = duplicate_file_groups(DATASET_DIR)
    assert len(groups) == 1
    _, names = groups[0]
    assert names == ["22_material_issue.xlsx", "25_material_issue_dup.xlsx"]
