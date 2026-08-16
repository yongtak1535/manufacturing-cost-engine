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
