from manufacturing_cost_engine.validation import (
    validate_period_rows, validate_gl_balance, validate_material_issues,
    validate_bom_issues
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


def _wo(wo_no="WO-1", bom_version_id="BOM-1", planned_qty="10"):
    return {
        "wo_no": wo_no, "product_code": "P-100", "period": "2026-07",
        "bom_version_id": bom_version_id, "planned_qty": planned_qty,
        "uom": "EA", "wo_status": "OPEN",
        "start_date": "2026-07-01", "end_date": None,
    }

def _bom_item(bom_version_id="BOM-1", line_no=1, material_code="MAT-001",
              standard_qty="2", uom="EA"):
    return {
        "bom_version_id": bom_version_id, "line_no": line_no,
        "material_code": material_code, "standard_qty": standard_qty, "uom": uom,
    }

def _issue_row(wo_no="WO-1", material_code="MAT-001", issued_qty="1", uom="EA",
               issue_type="ISSUE", source_row=2):
    return {
        "issue_doc_no": "MI-1", "issue_line_no": source_row - 1, "wo_no": wo_no,
        "material_code": material_code, "issued_qty": issued_qty, "uom": uom,
        "unit_cost": "10", "issue_type": issue_type, "_source_row": source_row,
    }

def _material(material_code="MAT-001", base_uom="EA"):
    return {
        "material_code": material_code, "base_uom": base_uom,
        "standard_cost": "10", "is_active": "Y",
    }

def test_bom_issue_normal_quantity_no_issue():
    # expected = 2 * 10 = 20, actual = 20 -> exact match
    issues = validate_bom_issues(
        [_wo(planned_qty="10")],
        [_bom_item(standard_qty="2", uom="EA")],
        [_issue_row(issued_qty="20", uom="EA")],
        [_material()],
    )
    assert issues == []

def test_bom_issue_within_tolerance_no_issue():
    # expected = 20, tolerance = max(0.01, 20*0.02) = 0.4, diff = 0.3
    issues = validate_bom_issues(
        [_wo(planned_qty="10")],
        [_bom_item(standard_qty="2", uom="EA")],
        [_issue_row(issued_qty="20.3", uom="EA")],
        [_material()],
    )
    assert issues == []

def test_bom_issue_exceeds_tolerance_raises_error():
    # expected = 20, tolerance = 0.4, diff = 1.5
    issues = validate_bom_issues(
        [_wo(planned_qty="10")],
        [_bom_item(standard_qty="2", uom="EA")],
        [_issue_row(issued_qty="21.5", uom="EA")],
        [_material()],
    )
    assert len(issues) == 1
    assert issues[0].code == "BOM_ISSUE"
    assert issues[0].severity == "ERROR"
    assert issues[0].related_entity == "MAT-001"

def test_bom_issue_mat003_uses_override_tolerance():
    # expected = 3.2, diff = 0.06.
    # default tolerance would be max(0.01, 3.2*0.02) = 0.064 -> would NOT flag
    # MAT-003 override tolerance = max(0.05, 3.2*0.01) = 0.05 -> DOES flag
    issues = validate_bom_issues(
        [_wo(bom_version_id="BOM-2", planned_qty="1")],
        [_bom_item(bom_version_id="BOM-2", material_code="MAT-003",
                   standard_qty="3.2", uom="KG")],
        [_issue_row(material_code="MAT-003", issued_qty="3.26", uom="KG")],
        [_material(material_code="MAT-003", base_uom="KG")],
    )
    assert len(issues) == 1
    assert issues[0].code == "BOM_ISSUE"
    assert issues[0].related_entity == "MAT-003"

def test_bom_issue_sums_multiple_material_issue_lines():
    # two issue rows for the same wo+material must be summed: 11 + 11 = 22
    # expected = 20, tolerance = 0.4, diff = 2 -> BOM_ISSUE
    issues = validate_bom_issues(
        [_wo(planned_qty="10")],
        [_bom_item(standard_qty="2", uom="EA")],
        [
            _issue_row(issued_qty="11", uom="EA", source_row=2),
            _issue_row(issued_qty="11", uom="EA", source_row=3),
        ],
        [_material()],
    )
    bom_issues = [i for i in issues if i.code == "BOM_ISSUE"]
    assert len(bom_issues) == 1
    assert "expected=20" in bom_issues[0].message
    assert "actual=22" in bom_issues[0].message

def test_bom_issue_material_issue_return_reduces_net_quantity():
    # ISSUE 22 - RETURN 2 = net 20, matches expected exactly -> no issue
    issues = validate_bom_issues(
        [_wo(planned_qty="10")],
        [_bom_item(standard_qty="2", uom="EA")],
        [
            _issue_row(issued_qty="22", uom="EA", issue_type="ISSUE", source_row=2),
            _issue_row(issued_qty="2", uom="EA", issue_type="RETURN", source_row=3),
        ],
        [_material()],
    )
    assert issues == []

def test_bom_issue_missing_material_issue_treated_as_zero_actual():
    # BOM has material but no material_issue at all for this WO -> actual = 0
    issues = validate_bom_issues(
        [_wo(planned_qty="10")],
        [_bom_item(standard_qty="2", uom="EA")],
        [],
        [_material()],
    )
    assert len(issues) == 1
    assert issues[0].code == "BOM_ISSUE"
    assert "actual=0" in issues[0].message
    assert issues[0].source_row is None

def test_bom_issue_material_not_in_bom_flagged():
    # material_issue exists for a material with no BOM line -> expected = 0
    issues = validate_bom_issues(
        [_wo(bom_version_id="BOM-EMPTY", planned_qty="10")],
        [],
        [_issue_row(material_code="MAT-999", issued_qty="5", uom="EA")],
        [_material(material_code="MAT-999")],
    )
    assert len(issues) == 1
    assert issues[0].code == "BOM_ISSUE"
    assert issues[0].related_entity == "MAT-999"

def test_bom_issue_uom_mismatch_returns_review_issue_without_estimating():
    # BOM in KG, actual issued in EA, no conversion factor available -> can't estimate
    issues = validate_bom_issues(
        [_wo(bom_version_id="BOM-3", planned_qty="1")],
        [_bom_item(bom_version_id="BOM-3", material_code="MAT-004",
                   standard_qty="1.8", uom="KG")],
        [_issue_row(material_code="MAT-004", issued_qty="5", uom="EA")],
        [_material(material_code="MAT-004", base_uom="KG")],
    )
    assert len(issues) == 1
    assert issues[0].code == "UOM_CONVERSION_MISSING"
    assert issues[0].severity == "REVIEW_REQUIRED"

def test_bom_issue_uses_decimal_and_respects_tolerance_boundary():
    # expected = 1, tolerance = max(0.01, 1*0.02) = 0.02, diff exactly 0.02
    # boundary is inclusive (rule is strictly ">"), and float arithmetic
    # (1.02 - 1 == 0.020000000000000018) would wrongly exceed it.
    issues = validate_bom_issues(
        [_wo(planned_qty="1")],
        [_bom_item(standard_qty="1", uom="EA")],
        [_issue_row(issued_qty="1.02", uom="EA")],
        [_material()],
    )
    assert issues == []
