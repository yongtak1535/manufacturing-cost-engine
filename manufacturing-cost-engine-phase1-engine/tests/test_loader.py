from pathlib import Path
from manufacturing_cost_engine.loader import excel_files, load_dataset

def test_loader_excludes_expected_and_catalog(tmp_path):
    (tmp_path / "01_test.xlsx").touch()
    (tmp_path / "90_expected_results.xlsx").touch()
    (tmp_path / "91_error_catalog.xlsx").touch()
    files = excel_files(tmp_path)
    assert [p.name for p in files] == ["01_test.xlsx"]

def test_load_real_dataset_if_present():
    dataset = Path("hanbit_mvp_dataset_phase1")
    if not dataset.exists():
        return
    data = load_dataset(dataset)
    assert "01_company_plant.xlsx::company" in data
    assert "90_expected_results.xlsx::product_cost" not in data
