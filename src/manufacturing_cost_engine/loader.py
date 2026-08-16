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
