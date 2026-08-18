from manufacturing_cost_engine.validation import (
    validate_period_rows, validate_gl_balance, validate_material_issues,
    validate_bom_issues, validate_routing
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


def _wo(wo_no="WO-1", bom_version_id="BOM-1", planned_qty="10", product_code="P-100"):
    return {
        "wo_no": wo_no, "product_code": product_code, "period_key": "2026-07",
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


def _routing_version(routing_version_id="RTG-P100-A", product_code="P-100",
                      revision="A", source_row=2):
    return {
        "routing_version_id": routing_version_id, "product_code": product_code,
        "revision": revision, "_source_row": source_row,
    }

def _routing_operation(routing_version_id="RTG-P100-A", operation_seq=10,
                        operation_code="OP-CUT", operation_name="소재준비",
                        work_center_code="WC-10", standard_hours="0.1",
                        source_row=2):
    return {
        "routing_version_id": routing_version_id, "operation_seq": operation_seq,
        "operation_code": operation_code, "operation_name": operation_name,
        "work_center_code": work_center_code, "standard_hours": standard_hours,
        "_source_row": source_row,
    }

def _work_center(work_center_code="WC-10", work_center_name="절단",
                  cost_center_code="CC-100"):
    return {
        "company_code": "HB01", "plant_code": "PL01",
        "work_center_code": work_center_code,
        "work_center_name": work_center_name,
        "cost_center_code": cost_center_code,
    }

def test_routing_normal_no_issue():
    issues = validate_routing(
        [_wo(product_code="P-100")],
        [_routing_version()],
        [
            _routing_operation(operation_seq=10, operation_code="OP-CUT",
                                work_center_code="WC-10", source_row=2),
            _routing_operation(operation_seq=20, operation_code="OP-TRN",
                                work_center_code="WC-20", standard_hours="0.45",
                                source_row=3),
        ],
        [_work_center("WC-10"), _work_center("WC-20", "선삭")],
    )
    assert issues == []

def test_routing_unknown_routing_version_id_on_work_order():
    # WO가 명시적으로 존재하지 않는 routing_version_id를 참조하는 경우
    wo = _wo(product_code="P-100")
    wo["routing_version_id"] = "RTG-NOPE"
    issues = validate_routing(
        [wo],
        [_routing_version()],
        [_routing_operation()],
        [_work_center()],
    )
    assert any(i.code == "UNKNOWN_ROUTING" for i in issues)

def test_routing_unknown_product_code_has_no_routing():
    # 이 product_code에 대응하는 routing이 아예 없는 경우
    issues = validate_routing(
        [_wo(product_code="P-999")],
        [_routing_version(product_code="P-100")],
        [_routing_operation()],
        [_work_center()],
    )
    assert any(i.code == "UNKNOWN_ROUTING" for i in issues)

def test_routing_product_mismatch():
    # WO가 명시적으로 참조하는 routing_version_id는 존재하지만 product_code가 다름
    wo = _wo(product_code="P-200")
    wo["routing_version_id"] = "RTG-P100-A"
    issues = validate_routing(
        [wo],
        [_routing_version(routing_version_id="RTG-P100-A", product_code="P-100")],
        [_routing_operation()],
        [_work_center()],
    )
    assert any(i.code == "ROUTING_PRODUCT_MISMATCH" for i in issues)

def test_routing_header_without_detail():
    issues = validate_routing(
        [_wo(product_code="P-200")],
        [_routing_version(routing_version_id="RTG-P200-A", product_code="P-200")],
        [],
        [],
    )
    assert any(i.code == "ROUTING_OPERATION_MISSING" for i in issues)

def test_routing_detail_without_header():
    issues = validate_routing(
        [],
        [],
        [_routing_operation(routing_version_id="RTG-GHOST")],
        [_work_center()],
    )
    assert any(i.code == "UNKNOWN_ROUTING" for i in issues)

def test_routing_duplicate_operation_seq():
    issues = validate_routing(
        [],
        [_routing_version()],
        [
            _routing_operation(operation_seq=10, source_row=2),
            _routing_operation(operation_seq=10, operation_code="OP-DUP", source_row=3),
        ],
        [_work_center()],
    )
    assert any(i.code == "DUPLICATE_NATURAL_KEY" for i in issues)

def test_routing_missing_operation_code():
    issues = validate_routing(
        [],
        [_routing_version()],
        [_routing_operation(operation_code=None)],
        [_work_center()],
    )
    assert any(i.code == "ROUTING_OPERATION_CODE_MISSING" for i in issues)

def test_routing_missing_work_center_code():
    issues = validate_routing(
        [],
        [_routing_version()],
        [_routing_operation(work_center_code=None)],
        [_work_center()],
    )
    assert any(i.code == "ROUTING_WORK_CENTER_MISSING" for i in issues)

def test_routing_unknown_work_center():
    issues = validate_routing(
        [],
        [_routing_version()],
        [_routing_operation(work_center_code="WC-999")],
        [_work_center("WC-10")],
    )
    assert any(i.code == "UNKNOWN_WORK_CENTER" for i in issues)

def test_routing_negative_standard_hours():
    issues = validate_routing(
        [],
        [_routing_version()],
        [_routing_operation(standard_hours="-0.1")],
        [_work_center()],
    )
    assert any(i.code == "INVALID_STANDARD_HOURS" for i in issues)

def test_routing_invalid_standard_hours_string():
    issues = validate_routing(
        [],
        [_routing_version()],
        [_routing_operation(standard_hours="abc")],
        [_work_center()],
    )
    assert any(i.code == "INVALID_STANDARD_HOURS" for i in issues)

def test_routing_zero_standard_hours_is_currently_allowed():
    # 0시간을 금지할 근거가 없으므로 정책상 허용한다.
    issues = validate_routing(
        [],
        [_routing_version()],
        [_routing_operation(standard_hours="0")],
        [_work_center()],
    )
    assert not any(i.code == "INVALID_STANDARD_HOURS" for i in issues)

def test_routing_same_operation_code_different_seq_is_normal():
    # RTG-P300-A 실제 데이터처럼 OP-TRN이 seq 20/40에 각각 존재해도 정상이다.
    issues = validate_routing(
        [],
        [_routing_version()],
        [
            _routing_operation(operation_seq=20, operation_code="OP-TRN", source_row=2),
            _routing_operation(operation_seq=40, operation_code="OP-TRN", source_row=3),
        ],
        [_work_center()],
    )
    assert issues == []

def test_routing_decimal_boundary_values():
    # 아주 작은 음수 standard_hours도 float 오차 없이 Decimal로 정확히 걸러야 한다.
    issues = validate_routing(
        [],
        [_routing_version()],
        [_routing_operation(standard_hours="-0.0000001")],
        [_work_center()],
    )
    assert any(i.code == "INVALID_STANDARD_HOURS" for i in issues)

def test_routing_operation_seq_must_be_a_whole_number():
    issues = validate_routing(
        [],
        [_routing_version()],
        [_routing_operation(operation_seq="10.5")],
        [_work_center()],
    )
    assert any(i.code == "INVALID_ROUTING_OPERATION_SEQ" for i in issues)
