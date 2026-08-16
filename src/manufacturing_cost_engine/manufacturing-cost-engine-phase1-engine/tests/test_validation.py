from manufacturing_cost_engine.validation import (
    validate_period_rows, validate_gl_balance, validate_material_issues
)

def test_period_key_consistency():
    rows = [{"period_key": "2026-07", "year": 2026, "month": 7, "_source_row": 2}]
    assert validate_period_rows(rows) == []

def test_gl_balance_detects_unbalanced_document():
    rows = [
        {"document_no": "GL-1", "debit": "100", "credit": "0", "_source_row": 2},
        {"document_no": "GL-1", "debit": "0", "credit": "90", "_source_row": 3},
    ]
    issues = validate_gl_balance(rows)
    assert any(i.code == "GL_UNBALANCED_DOCUMENT" for i in issues)

def test_material_issue_target_required():
    rows = [{
        "material_code": "MAT-001", "wo_no": None, "cost_center_code": None,
        "issued_qty": "1", "unit_cost": "10", "amount": "10",
        "issue_type": "ISSUE", "_source_row": 2
    }]
    issues = validate_material_issues(
        rows,
        [{"material_code": "MAT-001"}],
        [],
        []
    )
    assert any(i.code == "ISSUE_TARGET_MISSING" for i in issues)
