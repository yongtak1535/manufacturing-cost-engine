from manufacturing_cost_engine.validation import (
    validate_period_rows, validate_gl_balance, validate_material_issues,
    validate_bom_issues, validate_routing, validate_account_mapping,
    validate_standard_cost, validate_actual_cost, validate_gl_reconciliation
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


def _wo(wo_no="WO-1", bom_version_id="BOM-1", planned_qty="10", product_code="P-100",
        period_key="2026-07", end_date=None, company_code="HB01"):
    return {
        "company_code": company_code, "wo_no": wo_no, "product_code": product_code,
        "period_key": period_key,
        "bom_version_id": bom_version_id, "planned_qty": planned_qty,
        "uom": "EA", "wo_status": "OPEN",
        "start_date": "2026-07-01", "end_date": end_date,
    }

def _bom_item(bom_version_id="BOM-1", line_no=1, material_code="MAT-001",
              standard_qty="2", uom="EA"):
    return {
        "bom_version_id": bom_version_id, "line_no": line_no,
        "material_code": material_code, "standard_qty": standard_qty, "uom": uom,
    }

def _issue_row(wo_no="WO-1", material_code="MAT-001", issued_qty="1", uom="EA",
               issue_type="ISSUE", source_row=2, unit_cost="10"):
    return {
        "issue_doc_no": "MI-1", "issue_line_no": source_row - 1, "wo_no": wo_no,
        "material_code": material_code, "issued_qty": issued_qty, "uom": uom,
        "unit_cost": unit_cost, "issue_type": issue_type, "_source_row": source_row,
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


def _gl_line(company_code="HB01", document_no="GL-1", line_no=1,
             gl_account_code="51100", debit="100000", credit="0",
             cost_center_code=None, source_row=2, period_key="2026-07"):
    return {
        "company_code": company_code, "period_key": period_key,
        "document_no": document_no, "line_no": line_no,
        "posting_date": "2026-07-31", "gl_account_code": gl_account_code,
        "debit": debit, "credit": credit, "cost_center_code": cost_center_code,
        "_source_row": source_row,
    }

def _account_mapping(company_code="HB01", gl_account_code="51100",
                      cost_center_code=None, cost_element_code="DM", priority=10):
    return {
        "company_code": company_code, "gl_account_code": gl_account_code,
        "cost_center_code": cost_center_code, "cost_element_code": cost_element_code,
        "priority": priority,
    }

def test_account_mapping_normal_no_issue():
    issues = validate_account_mapping(
        [_gl_line(gl_account_code="51100", debit="100000")],
        [_account_mapping(gl_account_code="51100")],
    )
    assert issues == []

def test_account_mapping_cost_center_specific_wins_at_same_priority():
    # 동일 priority에서는 cost_center_code가 NULL이 아닌 쪽을 우선한다 -> 모호하지 않다.
    issues = validate_account_mapping(
        [_gl_line(gl_account_code="60000", debit="1000", cost_center_code="CC-100")],
        [
            _account_mapping(gl_account_code="60000", cost_center_code="CC-100",
                              cost_element_code="OH", priority=10),
            _account_mapping(gl_account_code="60000", cost_center_code=None,
                              cost_element_code="DM", priority=10),
        ],
    )
    assert issues == []

def test_account_mapping_selects_highest_priority():
    # 실제 데이터의 53100(CC-100 priority=20 vs 전역 priority=10)과 동일한 구조.
    issues = validate_account_mapping(
        [_gl_line(gl_account_code="53100", debit="90000", cost_center_code="CC-100")],
        [
            _account_mapping(gl_account_code="53100", cost_center_code="CC-100",
                              cost_element_code="OH", priority=20),
            _account_mapping(gl_account_code="53100", cost_center_code=None,
                              cost_element_code="OH", priority=10),
        ],
    )
    assert issues == []

def test_account_mapping_unmapped_gl():
    issues = validate_account_mapping(
        [_gl_line(gl_account_code="53900", debit="30000")],
        [_account_mapping(gl_account_code="51100")],
    )
    assert len(issues) == 1
    assert issues[0].code == "UNMAPPED_GL"
    assert issues[0].severity == "WARNING"

def test_account_mapping_ambiguous():
    # 실제 데이터의 53500(전역, 동일 priority, 서로 다른 cost_element)과 동일한 구조.
    issues = validate_account_mapping(
        [_gl_line(gl_account_code="53500", debit="25000", cost_center_code=None)],
        [
            _account_mapping(gl_account_code="53500", cost_center_code=None,
                              cost_element_code="OH", priority=10),
            _account_mapping(gl_account_code="53500", cost_center_code=None,
                              cost_element_code="DM", priority=10),
        ],
    )
    assert len(issues) == 1
    assert issues[0].code == "MAPPING_AMBIGUOUS"
    assert issues[0].severity == "REVIEW_REQUIRED"

def test_account_mapping_excludes_credit_only_lines():
    # 대변(credit)만 있는 라인(예: 25100 원재료 상계)은 애초에 분류 대상이 아니다.
    issues = validate_account_mapping(
        [_gl_line(gl_account_code="25100", debit="0", credit="100000")],
        [],
    )
    assert issues == []

def test_account_mapping_clear_priority_normal_selection():
    issues = validate_account_mapping(
        [_gl_line(gl_account_code="70000", debit="500", cost_center_code="CC-900")],
        [
            _account_mapping(gl_account_code="70000", cost_center_code=None,
                              cost_element_code="OH", priority=5),
            _account_mapping(gl_account_code="70000", cost_center_code=None,
                              cost_element_code="GA", priority=10),
        ],
    )
    assert issues == []

def test_account_mapping_different_company_code_excluded():
    # 매핑이 다른 company_code에 대해서만 존재하면 후보에서 제외되어 UNMAPPED로 처리된다.
    issues = validate_account_mapping(
        [_gl_line(company_code="HB01", gl_account_code="51100", debit="1000")],
        [_account_mapping(company_code="HB02", gl_account_code="51100")],
    )
    assert len(issues) == 1
    assert issues[0].code == "UNMAPPED_GL"

def test_account_mapping_excludes_lines_with_both_debit_and_credit():
    # 실제 GL-260731-017(E-029 차대불균형)처럼 debit>0이면서 credit도 채워진 라인은
    # "소비 대체분개"의 순수 차변 라인이 아니므로 매핑 대상에서 제외한다.
    # (매핑되지 않은 계정이라도 UNMAPPED_GL을 만들지 않아야 한다.)
    issues = validate_account_mapping(
        [_gl_line(gl_account_code="25100", debit="500", credit="10000")],
        [],
    )
    assert issues == []


def _product(product_code="P-100", base_uom="EA", is_active="Y"):
    return {
        "company_code": "HB01", "product_code": product_code,
        "product_name": "테스트제품", "base_uom": base_uom,
        "product_group": "TEST", "is_active": is_active,
    }

def _cost_element(cost_element_code="DM", is_manufacturing="Y"):
    return {
        "cost_element_code": cost_element_code, "cost_element_name": "테스트",
        "is_manufacturing": is_manufacturing,
    }

def _std_cost_header(company_code="HB01", product_code="P-100", period_key="2026-07",
                      cost_element_code="DM", standard_qty="1",
                      standard_unit_price="1000", standard_amount="1000",
                      version="V1", source_row=2):
    return {
        "company_code": company_code, "product_code": product_code,
        "period_key": period_key, "cost_element_code": cost_element_code,
        "standard_qty": standard_qty, "standard_unit_price": standard_unit_price,
        "standard_amount": standard_amount, "version": version,
        "_source_row": source_row,
    }

def _std_cost_detail(company_code="HB01", product_code="P-100", period_key="2026-07",
                      cost_element_code="DM", ref_type="MATERIAL",
                      ref_material_code="MAT-001", routing_version_id=None,
                      ref_operation_seq=None, standard_qty="1",
                      standard_unit_price="1000", standard_amount="1000",
                      version="V1", source_row=2):
    return {
        "company_code": company_code, "product_code": product_code,
        "period_key": period_key, "cost_element_code": cost_element_code,
        "ref_type": ref_type, "ref_material_code": ref_material_code,
        "routing_version_id": routing_version_id,
        "ref_operation_seq": ref_operation_seq, "standard_qty": standard_qty,
        "standard_unit_price": standard_unit_price,
        "standard_amount": standard_amount, "version": version,
        "_source_row": source_row,
    }

def test_standard_cost_normal_header_no_issue():
    issues = validate_standard_cost(
        [_std_cost_header(standard_qty="1", standard_unit_price="1000",
                           standard_amount="1000")],
        [],
        [_product()],
        [_cost_element("DM")],
        [],
    )
    assert issues == []

def test_standard_cost_header_amount_mismatch():
    issues = validate_standard_cost(
        [_std_cost_header(standard_qty="1", standard_unit_price="1000",
                           standard_amount="1500")],
        [],
        [_product()],
        [_cost_element("DM")],
        [],
    )
    assert any(i.code == "AMOUNT_MISMATCH" for i in issues)

def test_standard_cost_header_natural_key_duplicate():
    issues = validate_standard_cost(
        [_std_cost_header(source_row=2), _std_cost_header(source_row=3)],
        [],
        [_product()],
        [_cost_element("DM")],
        [],
    )
    assert any(i.code == "DUPLICATE_NATURAL_KEY" for i in issues)

def test_standard_cost_unknown_product():
    issues = validate_standard_cost(
        [_std_cost_header(product_code="P-999")],
        [],
        [_product("P-100")],
        [_cost_element("DM")],
        [],
    )
    assert any(i.code == "UNKNOWN_PRODUCT" for i in issues)

def test_standard_cost_unknown_cost_element():
    issues = validate_standard_cost(
        [_std_cost_header(cost_element_code="XX")],
        [],
        [_product()],
        [_cost_element("DM")],
        [],
    )
    assert any(i.code == "UNKNOWN_COST_ELEMENT" for i in issues)

def test_standard_cost_detail_header_sum_matches():
    issues = validate_standard_cost(
        [_std_cost_header(standard_amount="1000")],
        [
            _std_cost_detail(standard_amount="600", source_row=2),
            _std_cost_detail(standard_amount="400", source_row=3),
        ],
        [_product()],
        [_cost_element("DM")],
        [_material("MAT-001")],
    )
    assert issues == []

def test_standard_cost_detail_header_sum_mismatch():
    issues = validate_standard_cost(
        [_std_cost_header(standard_amount="1000")],
        [_std_cost_detail(standard_amount="600")],
        [_product()],
        [_cost_element("DM")],
        [_material("MAT-001")],
    )
    assert any(i.code == "STD_DETAIL_SUM_MISMATCH" for i in issues)

def test_standard_cost_no_detail_skips_sum_check():
    # 실제 P-100/300/400처럼 detail이 전혀 없는 조합은 합계 검증 자체를 건너뛴다.
    issues = validate_standard_cost(
        [_std_cost_header(product_code="P-300", standard_amount="9999")],
        [],
        [_product("P-300")],
        [_cost_element("DM")],
        [],
    )
    assert not any(i.code == "STD_DETAIL_SUM_MISMATCH" for i in issues)

def test_standard_cost_missing_for_active_product():
    # 실제 P-900처럼: product master엔 있지만 standard_cost header가 전혀 없는 경우.
    issues = validate_standard_cost(
        [_std_cost_header(product_code="P-100")],
        [],
        [_product("P-100"), _product("P-900")],
        [_cost_element("DM")],
        [],
    )
    missing = [i for i in issues if i.code == "STANDARD_COST_MISSING"]
    assert len(missing) == 1
    assert missing[0].related_entity == "P-900"

def test_standard_cost_detail_unknown_material():
    issues = validate_standard_cost(
        [],
        [_std_cost_detail(ref_material_code="MAT-999")],
        [_product()],
        [_cost_element("DM")],
        [_material("MAT-001")],
    )
    assert any(i.code == "UNKNOWN_MATERIAL" for i in issues)

def test_standard_cost_decimal_boundary_within_tolerance():
    # diff가 정확히 0.01(허용오차)이면 초과가 아니므로 오류가 아니다(경계 포함).
    issues = validate_standard_cost(
        [_std_cost_header(standard_qty="1", standard_unit_price="1000",
                           standard_amount="1000.01")],
        [],
        [_product()],
        [_cost_element("DM")],
        [],
    )
    assert issues == []

def test_standard_cost_ga_not_required_for_completeness():
    # GA(is_manufacturing=N)는 completeness 판정에서 요구되지 않는다.
    # product가 DM 행 하나만 있어도 STANDARD_COST_MISSING이 아니다.
    issues = validate_standard_cost(
        [_std_cost_header(product_code="P-100", cost_element_code="DM")],
        [],
        [_product("P-100")],
        [_cost_element("DM"), _cost_element("GA", is_manufacturing="N")],
        [],
    )
    assert not any(i.code == "STANDARD_COST_MISSING" for i in issues)


def _po(wo_no="WO-1", good_qty="10", source_row=2):
    return {"wo_no": wo_no, "good_qty": good_qty, "_source_row": source_row}

def _labor_tx(wo_no="WO-1", direct_indirect="DIRECT", work_center_code="WC-20"):
    return {
        "wo_no": wo_no, "direct_indirect": direct_indirect,
        "work_center_code": work_center_code,
    }

def _oh_rate(period_key="2026-07", cost_center_code="CC-100", rate_per_base="18000"):
    return {
        "period_key": period_key, "cost_center_code": cost_center_code,
        "rate_per_base": rate_per_base,
    }

def test_actual_cost_normal_wo_no_issue():
    issues = validate_actual_cost(
        [_wo(wo_no="WO-1")],
        [_po(wo_no="WO-1", good_qty="10")],
        [_labor_tx(wo_no="WO-1", work_center_code="WC-20")],
        [_work_center("WC-20", "선삭", "CC-100")],
        [_oh_rate("2026-07", "CC-100", "18000")],
    )
    assert issues == []

def test_actual_cost_no_production_output():
    # 실제 WO-2607-017과 동일한 케이스: 산출 실적이 전혀 없음.
    issues = validate_actual_cost([_wo(wo_no="WO-1")], [], [], [], [])
    assert any(
        i.code == "NO_PRODUCTION_OUTPUT" and i.severity == "NOT_CALCULABLE"
        for i in issues
    )

def test_actual_cost_zero_good_qty():
    # 실제 WO-2607-009과 동일한 케이스: good_qty=0.
    issues = validate_actual_cost(
        [_wo(wo_no="WO-1")], [_po(wo_no="WO-1", good_qty="0")], [], [], []
    )
    assert any(
        i.code == "ZERO_DENOMINATOR" and i.severity == "NOT_CALCULABLE"
        for i in issues
    )

def test_actual_cost_overhead_not_allocated():
    # 실제 CC-300과 동일한 케이스: 해당 cost_center에 overhead_rate가 없음.
    issues = validate_actual_cost(
        [_wo(wo_no="WO-1")],
        [_po(wo_no="WO-1", good_qty="10")],
        [_labor_tx(wo_no="WO-1", work_center_code="WC-50")],
        [_work_center("WC-50", "검사", "CC-300")],
        [_oh_rate("2026-07", "CC-100", "18000")],
    )
    assert any(
        i.code == "OVERHEAD_NOT_ALLOCATED" and i.severity == "NOT_ALLOCATED"
        for i in issues
    )


def _period(period_key="2026-07", end_date="2026-07-31", company_code="HB01"):
    return {"company_code": company_code, "period_key": period_key, "end_date": end_date}

def _labor_row(wo_no="WO-1", actual_hours="1", actual_rate="24000", amount="24000",
               direct_indirect="DIRECT", work_center_code="WC-20"):
    return {
        "wo_no": wo_no, "actual_hours": actual_hours, "actual_rate": actual_rate,
        "amount": amount, "direct_indirect": direct_indirect,
        "work_center_code": work_center_code,
    }

def test_gl_recon_dm_within_tolerance_no_issue():
    # GL=100000, Actual=100050, diff=50, tolerance=max(10, 100050*0.001=100.05)=100.05
    issues = validate_gl_reconciliation(
        [_gl_line(gl_account_code="51100", debit="100000")],
        [_account_mapping(gl_account_code="51100", cost_element_code="DM")],
        [_wo()],
        [_issue_row(issued_qty="10005", unit_cost="10")],
        [],
        [_material()],
        [_product()],
        [_period()],
    )
    assert issues == []

def test_gl_recon_dm_exceeds_tolerance():
    # GL=100000, Actual=200000, diff=100000, tolerance=max(10, 200)=200 -> 초과
    issues = validate_gl_reconciliation(
        [_gl_line(gl_account_code="51100", debit="100000")],
        [_account_mapping(gl_account_code="51100", cost_element_code="DM")],
        [_wo()],
        [_issue_row(issued_qty="20000", unit_cost="10")],
        [],
        [_material()],
        [_product()],
        [_period()],
    )
    dm_issues = [i for i in issues if i.code == "GL_RECON_DIFFERENCE" and i.related_entity == "DM"]
    assert len(dm_issues) == 1
    assert dm_issues[0].severity == "ERROR"

def test_gl_recon_dl_within_tolerance_no_issue():
    issues = validate_gl_reconciliation(
        [_gl_line(gl_account_code="52100", debit="180000")],
        [_account_mapping(gl_account_code="52100", cost_element_code="DL")],
        [_wo()],
        [],
        [_labor_row(amount="180050")],
        [],
        [_product()],
        [_period()],
    )
    assert issues == []

def test_gl_recon_dl_exceeds_tolerance():
    issues = validate_gl_reconciliation(
        [_gl_line(gl_account_code="52100", debit="180000")],
        [_account_mapping(gl_account_code="52100", cost_element_code="DL")],
        [_wo()],
        [],
        [_labor_row(amount="500000")],
        [],
        [_product()],
        [_period()],
    )
    dl_issues = [i for i in issues if i.code == "GL_RECON_DIFFERENCE" and i.related_entity == "DL"]
    assert len(dl_issues) == 1

def test_gl_recon_dm_and_dl_both_exceed_are_independent_issues():
    # 실제 데이터처럼 DM/DL이 둘 다 초과하면 90_expected_results.xlsx의 expected_value=1에
    # 맞추기 위해 하나로 합치거나 임의로 제외하지 않고 각각 독립적으로 보고한다.
    issues = validate_gl_reconciliation(
        [
            _gl_line(document_no="GL-1", gl_account_code="51100", debit="100000"),
            _gl_line(document_no="GL-2", gl_account_code="52100", debit="180000"),
        ],
        [
            _account_mapping(gl_account_code="51100", cost_element_code="DM"),
            _account_mapping(gl_account_code="52100", cost_element_code="DL"),
        ],
        [_wo()],
        [_issue_row(issued_qty="20000", unit_cost="10")],
        [_labor_row(amount="500000")],
        [_material()],
        [_product()],
        [_period()],
    )
    gl_recon = [i for i in issues if i.code == "GL_RECON_DIFFERENCE"]
    assert len(gl_recon) == 2
    assert {i.related_entity for i in gl_recon} == {"DM", "DL"}

def test_gl_recon_excludes_oh_even_when_it_differs():
    # OH 계정(53100)은 실제 차이가 있어도 이번 GL Reconciliation 대상이 아니다(§7-7).
    issues = validate_gl_reconciliation(
        [_gl_line(gl_account_code="53100", debit="10000", cost_center_code="CC-100")],
        [_account_mapping(gl_account_code="53100", cost_center_code="CC-100",
                          cost_element_code="OH")],
        [_wo()],
        [],
        [],
        [],
        [_product()],
        [_period()],
    )
    assert issues == []

def test_gl_recon_actual_only_no_gl_entry_still_compared():
    # GL에 해당 cost_element 계정 자체가 없으면 GL=0으로 취급해 비교한다(스킵하지 않음).
    issues = validate_gl_reconciliation(
        [],
        [_account_mapping(gl_account_code="51100", cost_element_code="DM")],
        [_wo()],
        [_issue_row(issued_qty="20000", unit_cost="10")],
        [],
        [_material()],
        [_product()],
        [_period()],
    )
    assert any(
        i.code == "GL_RECON_DIFFERENCE" and i.related_entity == "DM" for i in issues
    )

def test_gl_recon_multiple_periods_compared_independently():
    issues = validate_gl_reconciliation(
        [
            _gl_line(document_no="GL-1", gl_account_code="51100", debit="100000",
                     period_key="2026-07"),
            _gl_line(document_no="GL-2", gl_account_code="51100", debit="500000",
                     period_key="2026-08"),
        ],
        [_account_mapping(gl_account_code="51100", cost_element_code="DM")],
        [
            _wo(wo_no="WO-1", period_key="2026-07"),
            _wo(wo_no="WO-2", period_key="2026-08"),
        ],
        [
            _issue_row(wo_no="WO-1", issued_qty="10005", unit_cost="10", source_row=2),
            _issue_row(wo_no="WO-2", issued_qty="20000", unit_cost="10", source_row=3),
        ],
        [],
        [_material()],
        [_product()],
        [_period(period_key="2026-07"), _period(period_key="2026-08", end_date="2026-08-31")],
    )
    gl_recon = [i for i in issues if i.code == "GL_RECON_DIFFERENCE"]
    assert len(gl_recon) == 1
    assert "period=2026-08" in gl_recon[0].message

def test_gl_recon_decimal_boundary_within_tolerance():
    # diff가 정확히 tolerance(10)와 같으면 초과가 아니므로 issue가 없다(경계 포함).
    issues = validate_gl_reconciliation(
        [],
        [_account_mapping(gl_account_code="51100", cost_element_code="DM")],
        [_wo()],
        [_issue_row(issued_qty="1", unit_cost="10")],
        [],
        [_material()],
        [_product()],
        [_period()],
    )
    assert issues == []

def test_gl_recon_excludes_period_spanning_wo_from_actual():
    # 실제 WO-2607-018/019와 동일한 구조: end_date가 period 종료일을 넘는 WO.
    issues = validate_gl_reconciliation(
        [_gl_line(gl_account_code="51100", debit="100000")],
        [_account_mapping(gl_account_code="51100", cost_element_code="DM")],
        [_wo(wo_no="WO-1", end_date="2026-08-05")],
        [_issue_row(wo_no="WO-1", issued_qty="10000", unit_cost="10")],
        [],
        [_material()],
        [_product()],
        [_period()],
    )
    gl_recon = [i for i in issues if i.code == "GL_RECON_DIFFERENCE"]
    assert len(gl_recon) == 1
    assert "excluded_wo_amount=100000" in gl_recon[0].message
    excluded = [i for i in issues if i.code == "EXCLUDED_WO"]
    assert len(excluded) == 1
    assert excluded[0].related_entity == "WO-1"

def test_gl_recon_excluded_wo_amount_only_counts_spanning_wo():
    issues = validate_gl_reconciliation(
        [_gl_line(gl_account_code="51100", debit="10000")],
        [_account_mapping(gl_account_code="51100", cost_element_code="DM")],
        [
            _wo(wo_no="WO-1", end_date=None),
            _wo(wo_no="WO-2", end_date="2026-08-05"),
        ],
        [
            _issue_row(wo_no="WO-1", issued_qty="1000", unit_cost="10", source_row=2),
            _issue_row(wo_no="WO-2", issued_qty="5000", unit_cost="10", source_row=3),
        ],
        [],
        [_material()],
        [_product()],
        [_period()],
    )
    # WO-2의 5만원이 제외되고 WO-1의 1만원만 남아 GL(1만원)과 정확히 일치한다.
    assert not any(i.code == "GL_RECON_DIFFERENCE" for i in issues)
    excluded = [i for i in issues if i.code == "EXCLUDED_WO"]
    assert len(excluded) == 1
    assert excluded[0].related_entity == "WO-2"

def test_gl_recon_open_wo_without_end_date_not_excluded():
    # end_date가 아예 없는(아직 진행 중인) WO는 기간 걸침 여부를 판단할 근거가 없어
    # EXCLUDED_WO 대상이 아니다.
    issues = validate_gl_reconciliation(
        [], [], [_wo(wo_no="WO-1", end_date=None)], [], [], [], [_product()], [_period()]
    )
    assert not any(i.code == "EXCLUDED_WO" for i in issues)

def test_gl_recon_ignores_ambiguous_mapped_gl_account():
    # 53500처럼 동순위 매핑이 모호한 계정은 UNMAPPED_GL/MAPPING_AMBIGUOUS로 이미
    # validate_account_mapping()이 보고하므로, 여기서는 조용히 집계에서 제외한다.
    issues = validate_gl_reconciliation(
        [_gl_line(gl_account_code="53500", debit="25000", cost_center_code=None)],
        [
            _account_mapping(gl_account_code="53500", cost_center_code=None,
                              cost_element_code="OH", priority=10),
            _account_mapping(gl_account_code="53500", cost_center_code=None,
                              cost_element_code="DM", priority=10),
        ],
        [_wo()],
        [],
        [],
        [],
        [_product()],
        [_period()],
    )
    assert issues == []

def test_gl_recon_ignores_unmapped_gl_account():
    issues = validate_gl_reconciliation(
        [_gl_line(gl_account_code="53900", debit="30000")],
        [],
        [_wo()],
        [],
        [],
        [],
        [_product()],
        [_period()],
    )
    assert issues == []
