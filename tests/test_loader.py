from pathlib import Path
from manufacturing_cost_engine.loader import (
    excel_files, load_dataset, duplicate_file_groups
)

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


def test_duplicate_file_groups_detects_identical_content(tmp_path):
    # 파일명은 다르지만 내용이 같은 두 파일 -> 한 그룹으로 묶여야 한다.
    (tmp_path / "22_source.xlsx").write_bytes(b"same-bytes")
    (tmp_path / "25_copy.xlsx").write_bytes(b"same-bytes")
    (tmp_path / "20_other.xlsx").write_bytes(b"different-bytes")

    groups = duplicate_file_groups(tmp_path)

    assert len(groups) == 1
    _, names = groups[0]
    assert names == ["22_source.xlsx", "25_copy.xlsx"]

def test_duplicate_file_groups_empty_when_all_unique(tmp_path):
    (tmp_path / "01_a.xlsx").write_bytes(b"a")
    (tmp_path / "02_b.xlsx").write_bytes(b"b")

    assert duplicate_file_groups(tmp_path) == []

def test_duplicate_file_groups_same_name_different_dirs_not_relevant(tmp_path):
    # 같은 이름이 아니라 같은 "내용"이 판정 기준임을 확인한다.
    (tmp_path / "01_a.xlsx").write_bytes(b"content-1")
    (tmp_path / "02_a_copy.xlsx").write_bytes(b"content-2")

    assert duplicate_file_groups(tmp_path) == []

def test_duplicate_file_groups_ignores_fixture_files(tmp_path):
    # 90_/91_ 픽스처는 적재 대상이 아니므로 중복 판정에서도 제외된다.
    (tmp_path / "90_expected_results.xlsx").write_bytes(b"same")
    (tmp_path / "91_error_catalog.xlsx").write_bytes(b"same")

    assert duplicate_file_groups(tmp_path) == []

def test_duplicate_file_groups_on_real_dataset():
    dataset = Path("hanbit_mvp_dataset_phase1")
    if not dataset.exists():
        return

    groups = duplicate_file_groups(dataset)

    # 실제 데이터에는 22_material_issue.xlsx와 25_material_issue_dup.xlsx가
    # 바이트 단위로 동일하다.
    assert len(groups) == 1
    _, names = groups[0]
    assert names == ["22_material_issue.xlsx", "25_material_issue_dup.xlsx"]
