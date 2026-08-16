from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: str
    file_name: str
    sheet_name: str | None
    source_row: int | None
    message: str
    related_entity: str | None = None

@dataclass
class LoadedSheet:
    file_name: str
    sheet_name: str
    rows: list[dict[str, Any]]
