from __future__ import annotations
from hashlib import sha256
import json
from decimal import Decimal

def canonicalize(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {k: canonicalize(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [canonicalize(v) for v in value]
    return value

def input_hash(records_by_table: dict[str, list[dict]], mapping_version: str,
               rule_version: str, engine_version: str) -> str:
    payload = {
        "records": {
            table: sorted(
                [canonicalize(r) for r in rows],
                key=lambda r: json.dumps(r, ensure_ascii=False, sort_keys=True)
            )
            for table, rows in sorted(records_by_table.items())
        },
        "mapping_version": mapping_version,
        "rule_version": rule_version,
        "engine_version": engine_version,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return sha256(raw).hexdigest()
