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

    # 25개 로딩 대상 Excel (Phase 2: 30_contract.xlsx, 31_direct_expense.xlsx,
    # 34_direct_expense_budget.xlsx, 32_cost_rate_rule.xlsx,
    # contract_material_supply_type.xlsx 추가)
    files = excel_files(DATASET_DIR)

    assert len(files) == 25

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
# 기존 계약 행의 신규 컬럼 값은 전부 비어 있어야 한다(None). 예외는
# plant_code 하나뿐이다 — 이 값은 "실제 GA 요율/GFM 데이터"가 아니라
# 20_work_order.xlsx(20건 전부 plant_code=PL01) +
# 01_company_plant.xlsx(회사 전체에 공장이 PL01 하나뿐)로 이미 확정되는
# 구조적 사실이라서 별도 조사 라운드에서 채워 넣었다(아래
# test_contract_plant_code_is_pl01_derived_from_work_order_and_plant_master
# 참고). fiscal_year/industry_type/company_size/contract_agreement_date는
# 여전히 채울 근거가 없어 비어 있다.

def test_contract_has_ga_regulatory_columns_but_fiscal_year_industry_company_size_still_blank():
    data = load_dataset(DATASET_DIR)
    rows = data["30_contract.xlsx::contract"]

    assert len(rows) == 3
    for r in rows:
        assert "plant_code" in r
        assert "fiscal_year" in r
        assert "industry_type" in r
        assert "company_size" in r
        assert r["fiscal_year"] is None
        assert r["industry_type"] is None
        assert r["company_size"] is None


def test_contract_plant_code_is_pl01_derived_from_work_order_and_plant_master():
    # plant_code="PL01"은 임의로 채운 추정값이 아니라, 이 데이터셋 안에서
    # 이미 확정되는 구조적 사실이다:
    #   1) 20_work_order.xlsx의 20건 전부(계약 연결 여부와 무관하게) plant_code
    #      가 "PL01" 하나뿐이다.
    #   2) 01_company_plant.xlsx의 plant 시트에는 회사(HB01) 전체에 공장이
    #      "PL01" 단 하나뿐이다 — 다른 값이 존재할 수 있는 여지 자체가 없다.
    # 이 두 사실을 함께 확인해, 이번에 넣은 값이 "그럴듯한 추정"이 아니라
    # 기존 마스터 데이터로부터 100% 확정 가능한 값이었음을 회귀로 고정한다.
    data = load_dataset(DATASET_DIR)
    contracts = data["30_contract.xlsx::contract"]
    work_orders = data["20_work_order.xlsx::work_order"]
    plants = data["01_company_plant.xlsx::plant"]

    assert len(contracts) == 3
    for r in contracts:
        assert r["plant_code"] == "PL01"

    assert len(work_orders) == 20
    assert all(w["plant_code"] == "PL01" for w in work_orders)

    assert len(plants) == 1
    assert plants[0]["plant_code"] == "PL01"


def test_contract_has_agreement_date_column_but_all_blank():
    # reference_date의 원칙적 소스(계약동의서 작성일자)를 위한 컬럼만 스키마로
    # 준비한다 — start_date 등을 대신 쓰지 않기로 한 결정에 따라, 실제 값은
    # 넣지 않고 전부 비워 둔다.
    data = load_dataset(DATASET_DIR)
    rows = data["30_contract.xlsx::contract"]

    assert len(rows) == 3
    for r in rows:
        assert "contract_agreement_date" in r
        assert r["contract_agreement_date"] is None


def test_contract_type_is_product_structure_axis_not_legal_pricing_method():
    # contract_type(MULTI_PRODUCT/SINGLE_PRODUCT/PROTOTYPE)은 제품 구성
    # 방식(다품종/단일품종/시제)을 나타내는 분류축이다. 방산원가규칙 제28조와
    # 시행세칙 제32조가 GA 기준일을 가르는 데 쓰는 "법정 계약방식"(확정계약/
    # 개산계약/중도확정계약/특정비목불확정계약)과는 서로 다른 축이며, 이
    # 사실을 조사에서 확인했다.
    #
    # 이 테스트는 딱 두 가지만 검증한다(전체 컬럼 집합은 고정하지 않는다 —
    # 법정 계약방식과 무관한 정상적인 스키마 확장까지 실패시키는 것은 이
    # 테스트의 목적을 벗어난다):
    #   1) 현재 관측되는 contract_type 값이 제품구성 축의 값들뿐이라는 것.
    #   2) 신규 GA 규정 정합 조회 함수(resolve_ga_actual_rate/
    #      resolve_ga_ceiling_rate)가 contract_type을 매칭 키로 읽지
    #      않는다는 것 — contract_type을 법정 계약방식인 것처럼 rate
    #      선택에 사용하는 코드가 생기면 이 조건이 깨져 테스트가 실패한다.
    #      (레거시 _resolve_ga_rate()는 원래부터 contract_type을 쓰는
    #      별도 축이라 이 검사 대상이 아니다 — 보호 대상이며 건드리지 않음.)
    data = load_dataset(DATASET_DIR)
    rows = data["30_contract.xlsx::contract"]

    assert len(rows) == 3
    observed_contract_types = {r["contract_type"] for r in rows}
    assert observed_contract_types == {"MULTI_PRODUCT", "SINGLE_PRODUCT", "PROTOTYPE"}

    import inspect
    from manufacturing_cost_engine import cost_engine as ce

    for fn in (ce.resolve_ga_actual_rate, ce.resolve_ga_ceiling_rate):
        source = inspect.getsource(fn)
        assert '"contract_type"' not in source


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


# --- Phase 2 9단계: Budget GFM grain(contract x material_code) 데이터 모델 ---
# contract_material_supply_type.xlsx는 헤더만 준비한 신규 파일이다. 실제
# GOVERNMENT/COMPANY 분류값은 어떤 계약·자재에도 입력하지 않았다 — 데이터
# 행이 0건이라는 사실 자체가 그 확인이다.

def test_contract_material_supply_type_file_exists_with_expected_columns_and_zero_rows():
    data = load_dataset(DATASET_DIR)
    key = "contract_material_supply_type.xlsx::contract_material_supply_type"

    assert key in data
    rows = data[key]
    assert rows == []


def test_contract_material_supply_type_key_columns_match_existing_master_naming():
    # contract_no/material_code라는 컬럼명이 기존 마스터(30_contract.xlsx,
    # 08_material_master.xlsx)의 동일한 키 컬럼명과 정확히 일치하는지
    # 확인한다 — grain(계약 x 자재) 조인이 향후 이름 불일치 없이 가능해야
    # 한다는 전제를 미리 검증해 둔다.
    data = load_dataset(DATASET_DIR)

    contracts = data["30_contract.xlsx::contract"]
    materials = data["08_material_master.xlsx::material"]

    assert contracts and "contract_no" in contracts[0]
    assert materials and "material_code" in materials[0]

    import openpyxl
    wb = openpyxl.load_workbook(DATASET_DIR / "contract_material_supply_type.xlsx")
    ws = wb.active
    headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    assert headers == ["contract_no", "material_code", "supply_type"]


# --- E-013/E-014/E-030 데이터 정정값 회귀 고정 ---
# 아래 2개 테스트는 특정 셀 값을 "그냥 이 값이니까" 고정하는 것이 아니다.
# phase1_dataset_build_spec.md가 명시한 조건(E-014: posting_date가 2026-06월,
# E-030: 이 행은 "1행만 의도적 불일치" 규정 밖이라 산술이 맞아야 함)을 만족시키기
# 위해 선택한 데이터 정정값이며, 그 조건이 다시 깨지지 않게 잠가 둔다.

def test_gl_transaction_e014_row_posting_date_satisfies_closed_period_condition():
    # build_spec.md:923 "posting_date가 2026-06인 행 1건(마감 기간, E-014)".
    # GL-260731-021 line 2는 이 조건을 만족시키기 위해 posting_date를
    # 2026-06-01로 정정했다(원본 저자가 실제로 쓴 값이라는 근거는 없음 —
    # 2026-06월 조건을 만족하는 대체값). 이 행의 period_key는 처음부터
    # "2026-06"으로 되어 있었으므로, posting_date만 그 기간과 일치시키면
    # validate_gl_period()가 PERIOD_CLOSED를 정확히 1건 발생시킨다(E-014).
    # posting_date가 다시 2026-07대로 되돌아가면 PERIOD_MISMATCH만 남고
    # PERIOD_CLOSED는 사라지므로, 이 회귀는 그 되돌림을 잡아낸다.
    data = load_dataset(DATASET_DIR)
    rows = data["24_gl_transaction.xlsx::gl_transaction"]

    target = [
        r for r in rows
        if r.get("document_no") == "GL-260731-021" and r.get("line_no") == 2
    ]
    assert len(target) == 1
    row = target[0]

    assert row["period_key"] == "2026-06"
    assert row["posting_date"] == "2026-06-01"


def test_labor_transaction_e030_sibling_row_hours_are_internally_consistent():
    # phase1_dataset_build_spec.md:882 "actual_hours = regular_hours +
    # overtime_hours — 1행만 의도적 불일치(E-030)". LB-2607-045는 그
    # "1행"이 아니다(그 자리는 LB-2607-047) — 이 행은 E-028(NEGATIVE_OVERTIME,
    # overtime_hours=-2)의 지정 행일 뿐이므로 산술은 맞아야 한다.
    # actual_hours를 -1.5로 정정한 것은 "regular_hours(0.5) + overtime_hours(-2)
    # = -1.5"를 맞추는 값이며, 원본 저자가 실제로 입력한 값이라는 근거는 없다
    # (조건 충족값). 이 값이 다시 산술과 어긋나면(예: 이전 값 -1로 되돌아가면)
    # validate_labor()가 이 행에 대해서도 HOURS_SUM_MISMATCH를 추가로
    # 발생시켜 E-030이 1건이 아니라 2건이 되므로, 이 회귀는 그 상태를 잡아낸다.
    data = load_dataset(DATASET_DIR)
    rows = data["23_labor_transaction.xlsx::labor_transaction"]

    target = [r for r in rows if r.get("labor_doc_no") == "LB-2607-045"]
    assert len(target) == 1
    row = target[0]

    assert row["regular_hours"] == 0.5
    assert row["overtime_hours"] == -2
    assert row["actual_hours"] == -1.5
    assert row["actual_hours"] == row["regular_hours"] + row["overtime_hours"]


def test_contract_material_supply_type_no_real_government_or_company_values():
    # 실제 관급/사급 분류값이 어떤 형태로도 들어있지 않은지 최종 확인한다.
    data = load_dataset(DATASET_DIR)
    rows = data["contract_material_supply_type.xlsx::contract_material_supply_type"]

    assert len(rows) == 0
    assert all(r.get("supply_type") in (None,) for r in rows)
