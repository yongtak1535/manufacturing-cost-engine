from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pandas as pd


EXCLUDED_PREFIXES = ("90_", "91_")


def file_sha256(path: Path) -> str:
    h = sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()


def excel_files(dataset_dir: str | Path) -> list[Path]:
    root = Path(dataset_dir)

    return sorted(
        p
        for p in root.glob("*.xlsx")
        if not p.name.startswith(EXCLUDED_PREFIXES)
    )


def duplicate_file_groups(
    dataset_dir: str | Path,
) -> list[tuple[str, list[str]]]:
    """
    로딩 대상 Excel 파일들을 SHA-256으로 비교해 내용이 동일한 파일 그룹을 찾는다.
    파일명이 같은지가 아니라 파일 내용(해시)이 같은지로만 판정한다.

    파일 시스템 접근은 이 loader 계층에서 끝내고, validation 계층에는 순수한
    (해시, 파일명 목록) 데이터만 넘긴다.

    Returns:
        [(sha256, [파일명, ...]), ...] — 같은 해시를 가진 파일이 2개 이상인 그룹만,
        해시 기준으로 정렬해서 반환한다(결정적 순서).
    """
    by_hash: dict[str, list[str]] = {}

    for path in excel_files(dataset_dir):
        by_hash.setdefault(file_sha256(path), []).append(path.name)

    return sorted(
        (file_hash, sorted(names))
        for file_hash, names in by_hash.items()
        if len(names) > 1
    )


def load_workbook(path: Path) -> dict[str, pd.DataFrame]:
    return pd.read_excel(
        path,
        sheet_name=None,
        dtype=object,
    )


def normalize_sheet(df: pd.DataFrame) -> list[dict]:
    """
    Excel 첫 번째 행을 컬럼명으로 사용하고,
    실제 데이터 행에는 원본 Excel 행 번호를 추가한다.
    """

    df = df.where(pd.notna(df), None)

    rows = []

    for idx, row in df.iterrows():
        record = row.to_dict()
        record["_source_row"] = int(idx) + 2
        rows.append(record)

    return rows


def load_dataset(
    dataset_dir: str | Path,
) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}

    for path in excel_files(dataset_dir):
        for sheet, df in load_workbook(path).items():
            key = f"{path.name}::{sheet}"
            result[key] = normalize_sheet(df)

    return result


def load_excel_file(
    file_path: str | Path,
) -> dict[str, list[dict]]:
    """
    단일 Excel 파일을 읽는다.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Excel file not found: {path}"
        )

    result: dict[str, list[dict]] = {}

    for sheet, df in load_workbook(path).items():
        result[sheet] = normalize_sheet(df)

    return result
