# Phase 1 가상 제조기업 샘플 Excel 데이터셋 — 제작 사양서

**버전:** v2.0
**선행 문서:** `phase1_dataset_design.md` (v1.0)
**상태:** 코드 미작성. 본 문서는 Excel 파일 제작 사양이며, 생성 후 무결성 재검증 필요.

> 본 문서의 모든 수치(제품명, 수량, 단가, 공수 등)는 **가상 데이터셋 제작을 위한 설계값**입니다.
> 실제 계산 결과나 실무 기준이 아니며, 법령·회계기준에서 도출된 값이 아닙니다.

---

# A. 데이터 모델 수정사항

v1.0 설계서를 재검토한 결과 **20건의 수정 필요 사항**을 확인했습니다. 이 중 M-01 ~ M-09는 Excel 생성 전 반드시 반영해야 합니다.

## A-1. Critical — Excel 컬럼 구성이 바뀜

### M-01. PK 체계가 파일마다 불일치 (제 v1.0 설계의 결함)

v1.0은 자연키 복합PK(`company_code + product_code`)와 대리키(`issue_id`, `mapping_id`)를 혼용했습니다. 로딩 규칙이 파일마다 달라져 파서·FK 해석이 복잡해집니다.

**수정: 2계층 키 체계로 통일**

| 계층 | 정의 |
|---|---|
| **Excel(외부키)** | 자연키만 사용. 대리키 컬럼을 Excel에 넣지 않음 |
| **DB(내부키)** | 전 테이블 `id BIGINT` 대리 PK + 자연키에 `UNIQUE` 제약 |

Excel 제작자는 대리키를 신경 쓰지 않고, 로딩 시 시스템이 부여합니다.

### M-02. RoutingOperation FK가 `operation_code`만으로는 유일하지 않음

`routing_operation`의 자연키는 `(routing_version_id, operation_seq)`이며 `operation_code`에는 UNIQUE 제약이 없습니다. **동일 공정코드가 한 라우팅 내 2회 등장 가능**합니다(예: 중간검사·최종검사 모두 `OP-40`).

**수정:**
- `23_labor_transaction`에 **`operation_seq` 컬럼 필수 추가**
- 조인: `work_order.routing_version_id + labor.operation_seq`
- `operation_code`는 **검증용 보조 컬럼**(불일치 시 `OPERATION_CODE_MISMATCH` WARNING)
- `routing_operation`에 `(routing_version_id, operation_code)` UNIQUE를 걸지 **않음**

### M-03. StandardCostDetail의 다형 FK(`ref_type` + `ref_code`)는 FK 제약 불가

DB에서 참조 무결성을 강제할 수 없습니다.

**수정: 컬럼 분리 + CHECK 제약**

| 컬럼 | 조건 |
|---|---|
| `ref_material_code` | `ref_type = MATERIAL`일 때만 채움 |
| `ref_operation_seq` | `ref_type = OPERATION`일 때만 채움 |
| CHECK | 정확히 하나만 NOT NULL |

`ref_operation_seq`는 해당 제품의 **StandardCost 기준 routing_version**과 결합해야 하므로, `standard_cost_detail`에 **`routing_version_id` 컬럼 추가** 필요.

### M-04. 거래 파일에 자연키가 없어 중복 계상 검출 불가

`material_issue` / `labor_transaction` / `production_output`을 대리키만으로 두면, 같은 거래가 2번 들어와도 **중복인지 분할 계상인지 구분 불가**합니다. 원가가 조용히 2배가 됩니다.

**수정: 전표번호 + 행번호를 필수 자연키로**

| 파일 | 자연키 |
|---|---|
| `21_production_output` | `company_code + output_doc_no + output_line_no` |
| `22_material_issue` | `company_code + issue_doc_no + issue_line_no` |
| `23_labor_transaction` | `company_code + labor_doc_no + labor_line_no` |
| `24_gl_transaction` | `company_code + document_no + line_no` (v1.0에 `company_code` 누락) |

### M-05. `source_file_id` / `source_row`를 Excel 컬럼에 넣으면 안 됨

시스템이 부여해야 할 값입니다. Excel에 두면 위조 가능하고 Traceability 신뢰성이 무너집니다.

**수정:**
- Excel에 해당 컬럼 **없음**
- 파서가 Excel 실제 행번호를 `source_row`로 부여
- **`source_sheet_name` 컬럼을 DB 거래 테이블에 추가** (v1.0 누락). 멀티시트 파일(`10_bom`, `11_routing`, `12_standard_cost`)은 시트명 없이는 추적 불가

### M-06. ToleranceRule에 우선순위·유효기간 없음

전역 룰과 자재별 override가 충돌하면 판정이 비결정적이 됩니다.

**수정 — 컬럼 추가:** `priority` INT, `effective_from` DATE, `effective_to` DATE, `is_active` BOOL

**선택 규칙 (확정):**
```
1) rule_scope 일치 AND effective 범위 내 AND is_active
2) 구체성 순: material_code 지정 > product_code 지정 > 전역
3) 동일 구체성이면 priority DESC
4) 그래도 동순위 2건 이상 → TOLERANCE_AMBIGUOUS → REVIEW_REQUIRED
```

### M-07. `period_key`와 `effective_from/to`의 이중 기간 정의

`12_standard_cost`와 `13_overhead_rate`가 기간을 두 방식으로 갖고 있어 어느 쪽이 우선인지 미정의입니다.

**수정: `period_key` 단독 기준으로 통일. `effective_from/to` 컬럼 삭제.**
(BOM·Routing·AccountMapping·UOMConversion은 effective 방식 유지 — 이들은 기간 마스터에 종속되지 않음)

### M-08. GL 전표 차대 균형 검증 규칙 누락

v1.0에 없던 항목입니다. 전표 단위로 `Σdebit = Σcredit`이 아니면 GL 자체가 무효인데, 검증 룰이 없었습니다.

**수정: `GL_UNBALANCED_DOCUMENT` 규칙 추가 (CRITICAL).** `document_no` 단위 집계 후 검증.

### M-09. MaterialIssue의 `wo_no` NULL 허용 조건이 미정의

**수정 — CHECK 제약:**
```
wo_no IS NOT NULL  OR  cost_center_code IS NOT NULL
둘 다 NULL → ISSUE_TARGET_MISSING (CRITICAL)
둘 다 NOT NULL → wo_no 우선, cost_center는 참조 정보
```

## A-2. High — 규칙 명확화 (컬럼 변경 없음)

### M-10. WorkOrder 스냅샷의 실질적 보장

`bom_version_id` FK만으로는 BOMItem 내용이 사후 변경되면 스냅샷이 깨집니다.

**수정: BOMVersion / RoutingVersion을 immutable로 규정.**
```
status = ACTIVE 인 버전의 item은 수정 금지
변경 필요 시 새 revision 생성 (예: REV-A → REV-B)
이 규칙 하에서만 version FK가 스냅샷으로 성립
```
Phase 1에서 item 레벨 복사는 하지 않습니다.

### M-11. GL의 `cost_center_code`가 NULL인 경우 매핑 후보

**수정:** GL 행의 `cost_center_code`가 NULL이면 **CC 조건부 매핑(`mapping.cost_center_code` NOT NULL)은 후보에서 제외**하고 전역 매핑만 적용.

### M-12. CostCenter 자기참조 순환

**수정:** 생성 시 계층 depth ≤ 2. 로딩 시 순환 검출 → `COST_CENTER_CYCLE` CRITICAL.

### M-13. `CostAccumulationRun.input_hash` 정의 부재

**수정 — 확정 정의:**
```
input_hash = SHA256(
  정규화 직렬화(
    대상 period의 material_issue / labor_transaction / gl_transaction /
    production_output 의 (자연키 + 금액 + 수량) 정렬 목록
    + mapping_version + rule_version + engine_version
  )
)
```
동일 input_hash → 동일 결과가 나와야 함(결정성 검증).

### M-14. WorkOrder의 `uom`과 `product.base_uom` 불일치

**수정:** 불일치 시 `WO_UOM_MISMATCH` ERROR. 자동 환산하지 않음.

### M-15. UOMConversion 중복 방지 제약 없음

**수정:** UNIQUE `(company_code, material_code, from_uom, to_uom, effective_from)`. `material_code` NULL은 전역 룰.

### M-16. `actual_hours` vs `regular + overtime` 검증 규칙 미정의

**수정:** `HOURS_SUM_MISMATCH` ERROR. 어느 쪽도 자동 보정하지 않음.

### M-17. AuditLog의 다형 참조

**수정:** `entity_type` STRING + `entity_id` **STRING**(자연키 문자열). FK 제약 없음 — 감사 로그의 일반적 설계이며 Phase 1에서 허용.

### M-18. `90_expected_results` / `91_error_catalog`가 로딩 대상으로 오인될 위험

**수정:** 두 파일은 **데이터 로딩 파이프라인에서 명시적으로 제외**. 테스트 픽스처 전용. 파일명 접두 `9x`가 제외 규칙의 근거.

### M-19. Period의 `year`/`month`가 `period_key`와 중복 저장

**수정:** 파생 컬럼으로 유지하되 로딩 시 `period_key == f"{year}-{month:02d}"` 검증. 불일치 → `PERIOD_KEY_INCONSISTENT` ERROR.

### M-20. ActualCost가 Excel 파일 목록에 없음 (의도된 것임을 명문화)

**확정:** `ActualCost`는 **원천 입력이 아니라 `CostAccumulationRun`의 산출물**입니다. 따라서 Excel 파일이 존재하지 않으며, 존재해서도 안 됩니다. `90_expected_results`에 기대값이 들어가지만 이는 **assertion**이지 입력 데이터가 아닙니다.

## A-3. 원칙 반영 확인

| 사용자 지정 원칙 | 반영 위치 |
|---|---|
| ActualCost = Rule Engine 산출물 | M-20 |
| CostAccumulationRun이 ActualCost 생성 | M-13, D-5 |
| StandardCostDetail의 operation FK | M-03 |
| ToleranceRule에 priority + effective | M-06 |
| 기초 WIP = 0은 **샘플 조건**, 시스템 원칙 아님 | I-2 (README 문구 확정) |
| GL 소비 대체분개는 **샘플 구조**, 보편 구조 아님 | I-3 (README 문구 확정) |
| 방산원가 자동판정 미구현 | 전 구간 미포함 |

---

# B. 최종 Excel 파일 목록

**총 22개 파일 / 로딩 대상 20개.**

## 마스터 (14)

| # | 파일명 | Sheet | 예상 행수 |
|---|---|---|---|
| 01 | `01_company_plant.xlsx` | `company`, `plant` | 1 / 1 |
| 02 | `02_period.xlsx` | `period` | 3 |
| 03 | `03_cost_center.xlsx` | `cost_center` | 5 |
| 04 | `04_cost_element.xlsx` | `cost_element` | 4 |
| 05 | `05_account_mapping.xlsx` | `account_mapping` | 12 |
| 06 | `06_uom_conversion.xlsx` | `uom_conversion` | 6 |
| 07 | `07_product_master.xlsx` | `product` | 5 |
| 08 | `08_material_master.xlsx` | `material` | 12 |
| 09 | `09_work_center.xlsx` | `work_center` | 5 |
| 10 | `10_bom.xlsx` | `bom_version`, `bom_item` | 6 / 15 |
| 11 | `11_routing.xlsx` | `routing_version`, `routing_operation` | 4 / 18 |
| 12 | `12_standard_cost.xlsx` | `standard_cost`, `standard_cost_detail` | 9 / 24 |
| 13 | `13_overhead_rate.xlsx` | `overhead_rate` | 2 |
| 14 | `14_tolerance_rule.xlsx` | `tolerance_rule` | 6 |

## 거래 (6)

| # | 파일명 | Sheet | 예상 행수 |
|---|---|---|---|
| 20 | `20_work_order.xlsx` | `work_order` | 20 |
| 21 | `21_production_output.xlsx` | `production_output` | 19 |
| 22 | `22_material_issue.xlsx` | `material_issue` | 62 |
| 23 | `23_labor_transaction.xlsx` | `labor_transaction` | 54 |
| 24 | `24_gl_transaction.xlsx` | `gl_transaction` | 44 |
| 25 | `25_material_issue_dup.xlsx` | `material_issue` | 62 |

> `25`는 `22`의 **바이트 단위 완전 복제본**(파일명만 변경). DUPLICATE_FILE 테스트용.
> §7-7(a) 결정에 따라 GL을 소비 대체분개로 작성하므로 `inventory_opening`은 **제작하지 않습니다.**

## 검증 (2) — 로딩 제외

| # | 파일명 | Sheet |
|---|---|---|
| 90 | `90_expected_results.xlsx` | `product_cost`, `variance`, `gl_recon`, `validation_summary` |
| 91 | `91_error_catalog.xlsx` | `error_catalog` |

## 부속

`README.md` — §I의 가정 14항목 기재 (필수)

---

# C. 파일별 상세 컬럼 사양

**공통 규약**
- 1행 = 헤더, 2행부터 데이터 → `source_row`는 **Excel 실제 행번호**
- 날짜: `YYYY-MM-DD` 문자열
- 금액 `DECIMAL(18,4)` / 수량·시간 `DECIMAL(18,6)` / 비율 `DECIMAL(9,6)`
- BOOL: `Y` / `N`
- 빈 셀 = NULL. 문자열 `"NULL"` 사용 금지
- `company_code`는 전 파일 `HB01` 고정

---

## 01_company_plant.xlsx

**Sheet `company`** (1행)

| 컬럼 | 타입 | NULL | 규칙 |
|---|---|---|---|
| `company_code` | STRING(20) | N | `HB01` |
| `company_name` | STRING(100) | N | `한빛정밀공업(주)` |
| `currency_code` | STRING(3) | N | `KRW` |

- **PK:** `company_code`

**Sheet `plant`** (1행)

| 컬럼 | 타입 | NULL | 규칙 |
|---|---|---|---|
| `company_code` | STRING(20) | N | FK → company |
| `plant_code` | STRING(20) | N | `PL01` |
| `plant_name` | STRING(100) | N | `화성공장` |
| `is_active` | BOOL | Y | `Y` |

- **PK:** `company_code + plant_code`

---

## 02_period.xlsx (3행)

| 컬럼 | 타입 | NULL | 규칙 |
|---|---|---|---|
| `company_code` | STRING(20) | N | |
| `period_key` | STRING(7) | N | `YYYY-MM` |
| `year` | INT | N | period_key와 일치 (M-19) |
| `month` | INT | N | 1~12 |
| `start_date` | DATE | N | 월 1일 |
| `end_date` | DATE | N | 월 말일 |
| `is_closed` | BOOL | N | |

**데이터:**

| period_key | start | end | is_closed |
|---|---|---|---|
| 2026-06 | 2026-06-01 | 2026-06-30 | `Y` |
| 2026-07 | 2026-07-01 | 2026-07-31 | `N` |
| 2026-08 | 2026-08-01 | 2026-08-31 | `N` |

- **PK:** `company_code + period_key`
- **연결:** work_order, gl_transaction, standard_cost, overhead_rate

---

## 03_cost_center.xlsx (5행)

| 컬럼 | 타입 | NULL |
|---|---|---|
| `company_code` | STRING(20) | N |
| `plant_code` | STRING(20) | N |
| `cost_center_code` | STRING(20) | N |
| `cost_center_name` | STRING(100) | N |
| `cc_type` | ENUM | N |
| `parent_cost_center_code` | STRING(20) | **Y** |
| `is_active` | BOOL | N |

**데이터:**

| code | name | type | parent |
|---|---|---|---|
| CC-100 | 가공1팀 | PRODUCTION | (NULL) |
| CC-200 | 가공2팀 | PRODUCTION | (NULL) |
| CC-300 | 검사팀 | PRODUCTION | (NULL) |
| CC-900 | 생산관리 | SERVICE | (NULL) |
| CC-990 | 본사관리 | ADMIN | (NULL) |

- **PK:** `company_code + cost_center_code`
- **FK:** plant, self(parent)
- **주의:** depth ≤ 2 (M-12)

---

## 04_cost_element.xlsx (4행)

| 컬럼 | 타입 | NULL |
|---|---|---|
| `cost_element_code` | ENUM(DM/DL/OH/GA) | N |
| `cost_element_name` | STRING(50) | N |
| `is_manufacturing` | BOOL | N |

**데이터:** DM=`Y`, DL=`Y`, OH=`Y`, **GA=`N`**

- **PK:** `cost_element_code`

---

## 05_account_mapping.xlsx (12행) ★

| 컬럼 | 타입 | NULL |
|---|---|---|
| `company_code` | STRING(20) | N |
| `gl_account_code` | STRING(20) | N |
| `cost_center_code` | STRING(20) | **Y** (NULL=전역) |
| `cost_element_code` | ENUM | N |
| `effective_from` | DATE | N |
| `effective_to` | DATE | N |
| `priority` | INT | N |
| `is_active` | BOOL | N |

**데이터:**

| 행 | gl_account | cc | element | priority | 비고 |
|---|---|---|---|---|---|
| 2 | 51100 원재료비 | NULL | DM | 10 | |
| 3 | 51200 부재료비 | NULL | DM | 10 | |
| 4 | 52100 직접노무비 | NULL | DL | 10 | |
| 5 | 52200 간접노무비 | NULL | OH | 10 | |
| 6 | 53100 감가상각비-기계 | CC-100 | OH | 20 | CC 조건부 |
| 7 | 53100 감가상각비-기계 | NULL | OH | 10 | 전역 fallback |
| 8 | 53200 전력비 | NULL | OH | 10 | |
| 9 | 53300 수선비 | NULL | OH | 10 | |
| 10 | 53400 소모공구비 | NULL | OH | 10 | |
| 11 | 54100 급여-관리 | NULL | GA | 10 | is_manufacturing=N |
| 12 | 53500 운반비 | NULL | OH | 10 | **E-023: 아래와 동순위 중복** |
| 13 | 53500 운반비 | NULL | DM | 10 | **E-023: MAPPING_AMBIGUOUS 유발** |

> **`53900 외주가공비`는 이 파일에 넣지 않습니다** → E-012 UNMAPPED_GL 유발
> 12·13행은 동일 계정 / 동일 기간 / 동일 priority → 매핑 모호

- **PK:** `company + gl_account + COALESCE(cc,'*') + effective_from`
- **연결:** gl_transaction, cost_element, cost_center

---

## 06_uom_conversion.xlsx (6행)

| 컬럼 | 타입 | NULL |
|---|---|---|
| `company_code` | STRING(20) | N |
| `material_code` | STRING(20) | **Y** (NULL=전역) |
| `from_uom` | STRING(10) | N |
| `to_uom` | STRING(10) | N |
| `conversion_factor` | DECIMAL(18,6) | N |
| `effective_from` | DATE | N |
| `effective_to` | DATE | N |

**데이터:**

| material | from | to | factor | 비고 |
|---|---|---|---|---|
| NULL | KG | G | 1000 | 전역 |
| NULL | M | MM | 1000 | 전역 |
| NULL | L | ML | 1000 | 전역 |
| MAT-003 | EA | KG | 12.500000 | 정척 환봉 1본 = 12.5KG |
| MAT-005 | EA | KG | 8.400000 | 강판 1매 = 8.4KG |
| NULL | KG | EA | — | **작성 금지** |

> **MAT-004(스테인리스 환봉)의 EA→KG 환산은 의도적으로 미등록** → E-016 UOM_CONVERSION_MISSING

- **UNIQUE:** `company + COALESCE(material,'*') + from + to + effective_from` (M-15)
- **Phase 1은 1단계 직접 환산만 지원** (KG→G→MG 연쇄 미지원)

---

## 07_product_master.xlsx (5행)

| 컬럼 | 타입 | NULL |
|---|---|---|
| `company_code` | STRING(20) | N |
| `product_code` | STRING(20) | N |
| `product_name` | STRING(100) | N |
| `base_uom` | STRING(10) | N |
| `product_group` | STRING(50) | Y |
| `is_active` | BOOL | N |

**데이터:**

| code | name | uom | group |
|---|---|---|---|
| P-100 | 유압 밸브 바디 | EA | VALVE |
| P-200 | 감속기 하우징 | EA | HOUSING |
| P-300 | 스핀들 샤프트 | EA | SHAFT |
| P-400 | 플랜지 커플링 | EA | COUPLING |
| P-900 | 시험용 브래킷 | EA | TEST |

> `P-900`은 마스터에 **존재**하되 StandardCost를 누락시켜 E-014에 사용
> E-005(UNKNOWN_PRODUCT)는 마스터에 **없는** `P-999`를 WO에 기입

- **PK:** `company_code + product_code`

---

## 08_material_master.xlsx (12행)

| 컬럼 | 타입 | NULL |
|---|---|---|
| `company_code` | STRING(20) | N |
| `material_code` | STRING(20) | N |
| `material_name` | STRING(100) | N |
| `base_uom` | STRING(10) | N |
| `material_type` | ENUM(RAW/SUB/CONSUMABLE) | N |
| `standard_price` | DECIMAL(18,4) | Y |
| `is_active` | BOOL | N |

**데이터:**

| code | name | uom | type | std_price |
|---|---|---|---|---|
| MAT-001 | 주철 주조소재 GC250 | EA | RAW | 18,500 |
| MAT-002 | 알루미늄 다이캐스팅소재 | EA | RAW | 12,400 |
| MAT-003 | 탄소강 환봉 SCM440 | KG | RAW | 3,200 |
| MAT-004 | 스테인리스 환봉 SUS304 | KG | RAW | 7,800 |
| MAT-005 | 열연강판 SS400 | KG | RAW | 1,450 |
| MAT-006 | 볼트세트 M10 | EA | RAW | 850 |
| MAT-007 | O-Ring NBR 40 | EA | RAW | 320 |
| MAT-008 | 베어링 6205 | EA | RAW | 4,600 |
| MAT-009 | 방청 도장재 | L | SUB | 9,200 |
| MAT-010 | 방청유 | L | SUB | 6,700 |
| MAT-011 | 초경 절삭공구 | EA | CONSUMABLE | 42,000 |
| MAT-012 | 수용성 절삭유 | L | CONSUMABLE | 5,300 |

> `MAT-011`, `MAT-012`는 **BOM에 등재하지 않음** → E-003 NOT_IN_BOM
> E-004(UNKNOWN_MATERIAL)는 마스터에 없는 `MAT-999` 사용

- **PK:** `company_code + material_code`

---

## 09_work_center.xlsx (5행)

| 컬럼 | 타입 | NULL |
|---|---|---|
| `company_code` | STRING(20) | N |
| `plant_code` | STRING(20) | N |
| `work_center_code` | STRING(20) | N |
| `work_center_name` | STRING(100) | N |
| `cost_center_code` | STRING(20) | N |
| `is_active` | BOOL | N |

**데이터:**

| code | name | cost_center |
|---|---|---|
| WC-10 | 절단 | CC-100 |
| WC-20 | CNC 선삭 | CC-100 |
| WC-30 | MCT 밀링 | CC-200 |
| WC-40 | 열처리 | CC-200 |
| WC-50 | 최종검사 | CC-300 |

> **`standard_rate` 컬럼을 두지 않습니다.** 표준임률 출처는 `12_standard_cost`의 DL 단가로 **일원화** (§7-5 이중 기준 제거)

- **PK:** `company_code + work_center_code`

---

## 10_bom.xlsx

**Sheet `bom_version`** (6행)

| 컬럼 | 타입 | NULL |
|---|---|---|
| `company_code` | STRING(20) | N |
| `bom_version_id` | STRING(30) | N |
| `product_code` | STRING(20) | N |
| `revision` | STRING(10) | N |
| `effective_from` | DATE | N |
| `effective_to` | DATE | N |
| `status` | ENUM(ACTIVE/INACTIVE) | N |

**데이터:**

| bom_version_id | product | rev | from | to | status |
|---|---|---|---|---|---|
| BOM-P100-A | P-100 | A | 2026-01-01 | 2099-12-31 | ACTIVE |
| BOM-P200-A | P-200 | A | 2026-01-01 | 2099-12-31 | ACTIVE |
| BOM-P300-A | P-300 | A | 2026-01-01 | 2099-12-31 | ACTIVE |
| BOM-P400-A | P-400 | A | 2026-01-01 | 2026-06-30 | INACTIVE |
| BOM-P400-B | P-400 | B | 2026-06-01 | 2099-12-31 | ACTIVE |
| BOM-P900-A | P-900 | A | 2026-01-01 | 2099-12-31 | ACTIVE |

> **P-400의 A/B가 2026-06-01~06-30 구간에서 중첩** → E-022 BOM_VERSION_AMBIGUOUS
> (해당 WO가 이 구간을 참조하도록 설계)

**Sheet `bom_item`** (15행)

| 컬럼 | 타입 | NULL |
|---|---|---|
| `bom_version_id` | STRING(30) | N |
| `line_no` | INT | N |
| `material_code` | STRING(20) | N |
| `standard_qty` | DECIMAL(18,6) | N |
| `uom` | STRING(10) | N |
| `scrap_factor` | DECIMAL(9,6) | **Y — 전 행 공란** |

**데이터 (완제품 1EA당):**

| bom_version | line | material | qty | uom |
|---|---|---|---|---|
| BOM-P100-A | 1 | MAT-001 | 1.000000 | EA |
| BOM-P100-A | 2 | MAT-006 | 4.000000 | EA |
| BOM-P100-A | 3 | MAT-007 | 2.000000 | EA |
| BOM-P100-A | 4 | MAT-009 | 0.080000 | L |
| BOM-P200-A | 1 | MAT-002 | 1.000000 | EA |
| BOM-P200-A | 2 | MAT-008 | 2.000000 | EA |
| BOM-P200-A | 3 | MAT-009 | 0.120000 | L |
| BOM-P300-A | 1 | MAT-003 | 3.200000 | **KG** |
| BOM-P300-A | 2 | MAT-008 | 1.000000 | EA |
| BOM-P300-A | 3 | MAT-010 | 0.050000 | L |
| BOM-P400-A | 1 | MAT-005 | 2.400000 | KG |
| BOM-P400-A | 2 | MAT-006 | 6.000000 | EA |
| BOM-P400-B | 1 | MAT-005 | 2.200000 | KG |
| BOM-P400-B | 2 | MAT-006 | 6.000000 | EA |
| BOM-P900-A | 1 | MAT-004 | 1.800000 | **KG** |

> **P-300**: BOM 단위 KG, 출고 단위 EA(정척 봉) → **자재별 환산 필수** (정상 동작 확인)
> **P-900**: BOM 단위 KG, 출고 단위 EA, **MAT-004 환산 미등록** → E-016

- **PK:** `bom_version_id + line_no`
- **불변 규칙:** ACTIVE 버전의 item 수정 금지 (M-10)

---

## 11_routing.xlsx

**Sheet `routing_version`** (4행)

| 컬럼 | 타입 | NULL |
|---|---|---|
| `company_code` / `routing_version_id` / `product_code` / `revision` / `effective_from` / `effective_to` / `status` | — | N |

| routing_version_id | product | rev |
|---|---|---|
| RTG-P100-A | P-100 | A |
| RTG-P200-A | P-200 | A |
| RTG-P300-A | P-300 | A |
| RTG-P400-A | P-400 | A |

**Sheet `routing_operation`** (18행)

| 컬럼 | 타입 | NULL |
|---|---|---|
| `routing_version_id` | STRING(30) | N |
| `operation_seq` | INT | N |
| `operation_code` | STRING(20) | N |
| `operation_name` | STRING(100) | N |
| `work_center_code` | STRING(20) | N |
| `standard_hours` | DECIMAL(18,6) | N |

**데이터 (완제품 1EA당 시간):**

| routing | seq | op_code | name | WC | std_hrs |
|---|---|---|---|---|---|
| RTG-P100-A | 10 | OP-CUT | 소재준비 | WC-10 | 0.100000 |
| RTG-P100-A | 20 | OP-TRN | 선삭 | WC-20 | 0.450000 |
| RTG-P100-A | 30 | OP-MIL | 밀링 | WC-30 | 0.620000 |
| RTG-P100-A | 40 | OP-INS | 중간검사 | WC-50 | 0.080000 |
| RTG-P100-A | 50 | OP-INS | **최종검사** | WC-50 | 0.120000 |
| RTG-P200-A | 10 | OP-CUT | 소재준비 | WC-10 | 0.080000 |
| RTG-P200-A | 20 | OP-MIL | 밀링 | WC-30 | 0.700000 |
| RTG-P200-A | 30 | OP-TRN | 보링 | WC-20 | 0.300000 |
| RTG-P200-A | 40 | OP-INS | 최종검사 | WC-50 | 0.100000 |
| RTG-P300-A | 10 | OP-CUT | 절단 | WC-10 | 0.150000 |
| RTG-P300-A | 20 | OP-TRN | 황삭 | WC-20 | 0.400000 |
| RTG-P300-A | 30 | OP-HTR | 열처리 | WC-40 | 0.250000 |
| RTG-P300-A | 40 | OP-TRN | 정삭 | WC-20 | 0.350000 |
| RTG-P300-A | 50 | OP-MIL | 키홈가공 | WC-30 | 0.180000 |
| RTG-P300-A | 60 | OP-INS | 최종검사 | WC-50 | 0.110000 |
| RTG-P400-A | 10 | OP-CUT | 절단 | WC-10 | 0.090000 |
| RTG-P400-A | 20 | OP-MIL | 밀링 | WC-30 | 0.380000 |
| RTG-P400-A | 30 | OP-INS | 최종검사 | WC-50 | 0.070000 |

> **RTG-P100-A의 seq 40·50이 동일 `operation_code` = `OP-INS`**
> **RTG-P300-A의 seq 20·40이 동일 `operation_code` = `OP-TRN`**
> → M-02의 근거. `operation_code` 단독 조인은 반드시 실패해야 함

- **PK:** `routing_version_id + operation_seq`
- **`operation_code`에 UNIQUE 걸지 않음**

---

## 12_standard_cost.xlsx

**Sheet `standard_cost`** (9행) — 완제품 1EA당

| 컬럼 | 타입 | NULL |
|---|---|---|
| `company_code` | STRING(20) | N |
| `product_code` | STRING(20) | N |
| `period_key` | STRING(7) | N |
| `cost_element_code` | ENUM | N |
| `standard_qty` | DECIMAL(18,6) | N |
| `standard_unit_price` | DECIMAL(18,4) | N |
| `standard_amount` | DECIMAL(18,4) | N |
| `version` | STRING(10) | N |

> `effective_from/to` **삭제** (M-07)

**데이터 (period_key = 2026-07, version = V1):**

| product | element | std_qty | std_price | std_amount |
|---|---|---|---|---|
| P-100 | DM | 1.000000 | 25,540.0000 | 25,540.0000 |
| P-100 | DL | 1.370000 | 24,000.0000 | 32,880.0000 |
| P-100 | OH | 1.370000 | 18,000.0000 | 24,660.0000 |
| P-200 | DM | 1.000000 | 22,904.0000 | 22,904.0000 |
| P-200 | DL | 1.180000 | 24,000.0000 | 28,320.0000 |
| P-200 | OH | 1.180000 | 18,000.0000 | 21,240.0000 |
| P-300 | DM | 1.000000 | 15,275.0000 | 15,275.0000 |
| P-300 | DL | 1.440000 | 24,000.0000 | 34,560.0000 |
| P-300 | OH | 1.440000 | 18,000.0000 | 25,920.0000 |

> **P-400은 이 시트에 포함** (별도 3행 추가 가능) / **P-900은 의도적 누락** → E-015 STANDARD_COST_MISSING
> DM의 `standard_qty=1`은 "완제품 1EA"를 의미. 자재별 수량은 detail 시트에 있음
> DL/OH의 `standard_qty` = 표준 총공수(routing standard_hours 합계와 일치해야 함)

**검산 요구:** P-100 DL `1.37` = 0.10+0.45+0.62+0.08+0.12 ✓

**Sheet `standard_cost_detail`** (24행)

| 컬럼 | 타입 | NULL |
|---|---|---|
| `company_code` | STRING(20) | N |
| `product_code` | STRING(20) | N |
| `period_key` | STRING(7) | N |
| `cost_element_code` | ENUM | N |
| `ref_type` | ENUM(MATERIAL/OPERATION) | N |
| `ref_material_code` | STRING(20) | **Y** |
| `routing_version_id` | STRING(30) | **Y** |
| `ref_operation_seq` | INT | **Y** |
| `standard_qty` | DECIMAL(18,6) | N |
| `standard_unit_price` | DECIMAL(18,4) | N |
| `standard_amount` | DECIMAL(18,4) | N |
| `version` | STRING(10) | N |

> M-03 반영. **CHECK:** `ref_material_code`가 NOT NULL이면 `routing_version_id`·`ref_operation_seq`는 NULL, 그 역도 성립

**데이터 예 (P-100 DM):**

| ref_type | material | qty | price | amount |
|---|---|---|---|---|
| MATERIAL | MAT-001 | 1.000000 | 18,500 | 18,500 |
| MATERIAL | MAT-006 | 4.000000 | 850 | 3,400 |
| MATERIAL | MAT-007 | 2.000000 | 320 | 640 |
| MATERIAL | MAT-009 | 0.080000 | 9,200 | 736 |
| | | | **합계** | **23,276** |

> ⚠️ **위 합계 23,276 ≠ 요약 시트 25,540.** 이는 **의도적 불일치가 아니라 제작 시 반드시 맞춰야 할 값**입니다.
> 제작자는 detail 합계를 먼저 확정하고 요약 시트를 **그 합계로 채워야** 합니다.
> (`standard_cost_detail` 합계 = `standard_cost` 금액이 성립하지 않으면 Variance 분해가 무의미)

**필수 검산 규칙:**
```
Σ standard_cost_detail.standard_amount (product, period, element)
  = standard_cost.standard_amount (동일 키)
불일치 → STD_DETAIL_SUM_MISMATCH (ERROR)
```

- **PK:** `company + product + period + element + ref_type + COALESCE(material, operation_seq) + version`
- **FK:** material / (routing_version_id + operation_seq)

---

## 13_overhead_rate.xlsx (2행)

| 컬럼 | 타입 | NULL |
|---|---|---|
| `company_code` | STRING(20) | N |
| `period_key` | STRING(7) | N |
| `cost_center_code` | STRING(20) | N |
| `allocation_base` | ENUM(DLH) | N |
| `rate_per_base` | DECIMAL(18,4) | N |

> `effective_from/to` **삭제** (M-07)

**데이터:**

| period | cost_center | base | rate |
|---|---|---|---|
| 2026-07 | CC-100 | DLH | 18,000.0000 |
| 2026-07 | CC-200 | DLH | 18,000.0000 |

> **CC-300(검사팀) 배부율 미제공** → E-024 OVERHEAD_NOT_ALLOCATED
> CC-900(SERVICE) / CC-990(ADMIN)은 제조 배부 대상 아님

- **PK:** `company + period + cost_center`
- **배부기준 DLH = `direct_indirect = DIRECT`인 노무시간만**

---

## 14_tolerance_rule.xlsx (6행)

| 컬럼 | 타입 | NULL |
|---|---|---|
| `company_code` | STRING(20) | N |
| `rule_scope` | ENUM | N |
| `material_code` | STRING(20) | **Y** |
| `product_code` | STRING(20) | **Y** |
| `abs_tolerance` | DECIMAL(18,6) | N |
| `pct_tolerance` | DECIMAL(9,6) | N |
| `apply_rule` | ENUM(GREATER_OF/ABS_ONLY/PCT_ONLY) | N |
| `severity` | ENUM(WARNING/ERROR) | N |
| `priority` | INT | N |
| `effective_from` | DATE | N |
| `effective_to` | DATE | N |
| `is_active` | BOOL | N |

> M-06 반영 (priority / effective / is_active 추가)

**⚠️ 아래 수치는 미확정입니다.** §J-1에서 사용자 결정이 필요합니다.

| rule_scope | material | abs | pct | apply | severity | priority |
|---|---|---|---|---|---|---|
| BOM_ISSUE | NULL | ? | ? | GREATER_OF | ERROR | 10 |
| BOM_ISSUE | MAT-003 | ? | ? | GREATER_OF | ERROR | 20 |
| LABOR_HOURS | NULL | ? | ? | PCT_ONLY | WARNING | 10 |
| AMOUNT_CHECK | NULL | ? | ? | ABS_ONLY | ERROR | 10 |
| GL_RECON | NULL | ? | ? | GREATER_OF | ERROR | 10 |
| BOM_ISSUE | NULL | ? | ? | GREATER_OF | ERROR | 10 |

> 마지막 행은 1행과 **동일 scope·동일 구체성·동일 priority** → E-025 TOLERANCE_AMBIGUOUS 유발용
> (이 행을 넣을지는 선택. 넣으면 룰 선택 로직 검증 가능)

---

## 20_work_order.xlsx (20행)

| 컬럼 | 타입 | NULL |
|---|---|---|
| `company_code` | STRING(20) | N |
| `plant_code` | STRING(20) | N |
| `wo_no` | STRING(30) | N |
| `product_code` | STRING(20) | N |
| `period_key` | STRING(7) | N |
| `bom_version_id` | STRING(30) | N |
| `routing_version_id` | STRING(30) | N |
| `planned_qty` | DECIMAL(18,6) | N |
| `uom` | STRING(10) | N |
| `wo_status` | ENUM(OPEN/CLOSED) | N |
| `start_date` | DATE | N |
| `end_date` | DATE | **Y** (OPEN이면 NULL) |
| `cost_center_code` | STRING(20) | Y |

**생성 규칙:**
- `wo_no` = `WO-2607-nnn` (nnn = 001~020)
- `bom_version_id` / `routing_version_id` **명시 기입 필수** (추론 금지)
- 정상 WO 12건, 오류 관련 WO 8건
- WO-2607-018, 019 → `end_date = 2026-08-05` (기간 걸침, E-026)
- WO-2607-020 → `product_code = P-999` (E-005)

- **PK:** `company_code + wo_no`
- **FK:** product, period, plant, bom_version, routing_version

---

## 21_production_output.xlsx (19행)

| 컬럼 | 타입 | NULL |
|---|---|---|
| `company_code` | STRING(20) | N |
| `output_doc_no` | STRING(30) | N |
| `output_line_no` | INT | N |
| `wo_no` | STRING(30) | N |
| `product_code` | STRING(20) | N |
| `production_date` | DATE | N |
| `good_qty` | DECIMAL(18,6) | N |
| `scrap_qty` | DECIMAL(18,6) | N |
| `rework_qty` | DECIMAL(18,6) | N |
| `uom` | STRING(10) | N |

> M-04 반영 (자연키 추가)

**생성 규칙:**
- `output_doc_no` = `PO-2607-nnn`
- 정상 WO는 `scrap_qty = 0` 또는 소량(1~3)
- `rework_qty > 0` 1건 → E-020 REWORK_REVIEW_REQUIRED
- `good_qty = 0` 1건 → E-021 ZERO_DENOMINATOR
- **WO-2607-017은 이 파일에 행이 없음** → E-019 NO_PRODUCTION_OUTPUT

- **PK:** `company_code + output_doc_no + output_line_no`
- **FK:** work_order, product

---

## 22_material_issue.xlsx (62행)

| 컬럼 | 타입 | NULL |
|---|---|---|
| `company_code` | STRING(20) | N |
| `issue_doc_no` | STRING(30) | N |
| `issue_line_no` | INT | N |
| `wo_no` | STRING(30) | **Y** (M-09) |
| `cost_center_code` | STRING(20) | **Y** (M-09) |
| `material_code` | STRING(20) | N |
| `issue_date` | DATE | N |
| `issued_qty` | DECIMAL(18,6) | N |
| `uom` | STRING(10) | N |
| `unit_cost` | DECIMAL(18,4) | N |
| `amount` | DECIMAL(18,4) | N |
| `issue_type` | ENUM(ISSUE/RETURN) | N |

**생성 규칙:**
- `amount = unit_cost × issued_qty` (반올림 후) — **1행만 의도적 불일치** (E-011)
- `unit_cost` = `material_master.standard_price` **고정** (§I-4 결정에 따름)
- `RETURN` 2건: 순액 판정 검증용 (`issued_qty`는 양수, `issue_type`으로 구분)
- `wo_no` NULL + `cost_center_code` 채움: 2건 (간접자재 MAT-011, MAT-012)
- P-300 관련 출고는 `uom = EA` (BOM은 KG → 환산 필요)
- P-900 관련 출고는 `uom = EA` (MAT-004 환산 미등록 → E-016)

- **PK:** `company_code + issue_doc_no + issue_line_no`
- **FK:** work_order(nullable), material, cost_center(nullable)

---

## 23_labor_transaction.xlsx (54행)

| 컬럼 | 타입 | NULL |
|---|---|---|
| `company_code` | STRING(20) | N |
| `labor_doc_no` | STRING(30) | N |
| `labor_line_no` | INT | N |
| `wo_no` | STRING(30) | N |
| `operation_seq` | INT | **N — M-02 필수 추가** |
| `operation_code` | STRING(20) | N |
| `work_center_code` | STRING(20) | N |
| `labor_date` | DATE | N |
| `regular_hours` | DECIMAL(18,6) | N |
| `overtime_hours` | DECIMAL(18,6) | N |
| `actual_hours` | DECIMAL(18,6) | N |
| `actual_rate` | DECIMAL(18,4) | N |
| `amount` | DECIMAL(18,4) | N |
| `direct_indirect` | ENUM(DIRECT/INDIRECT) | N |

**생성 규칙:**
- `actual_hours = regular_hours + overtime_hours` — **1행만 의도적 불일치** (E-030)
- `amount = actual_hours × actual_rate`
- `actual_rate`는 **잔업할증 미포함 기본임률** (§I-6 결정에 따름)
- `direct_indirect = INDIRECT` 3건 (DL 집계에서 제외되어야 함)
- P-100 WO의 `operation_seq` 40·50은 둘 다 `OP-INS` → 코드 단독 조인 시 중복 매칭 확인

- **PK:** `company_code + labor_doc_no + labor_line_no`
- **FK:** work_order, (work_order.routing_version_id + operation_seq) → routing_operation, work_center

---

## 24_gl_transaction.xlsx (44행)

| 컬럼 | 타입 | NULL |
|---|---|---|
| `company_code` | STRING(20) | N |
| `plant_code` | STRING(20) | N |
| `period_key` | STRING(7) | N |
| `document_no` | STRING(30) | N |
| `line_no` | INT | N |
| `transaction_date` | DATE | N |
| `posting_date` | DATE | N |
| `gl_account_code` | STRING(20) | N |
| `gl_account_name` | STRING(100) | N |
| `debit` | DECIMAL(18,4) | N |
| `credit` | DECIMAL(18,4) | N |
| `cost_center_code` | STRING(20) | **Y** |
| `description` | STRING(200) | Y |
| `reversal_of_document_no` | STRING(30) | **Y** |

**생성 규칙 (중요):**
- **재료비는 소비 대체분개 구조**
  ```
  차변 51100 원재료비  /  대변 14100 원재료
  ```
  금액 = 해당 기간 `material_issue` 순액 합계 (E-018 대상 제외)
- **직접노무비(52100)와 간접노무비(52200)를 분리** 기표
- 52100 금액 = `labor_transaction(DIRECT)` 합계
- **전표 단위 차대 균형 필수** (M-08). 1건만 의도적 불균형 (E-029)
- `53900 외주가공비` 1건 → 매핑 없음 (E-012)
- `53500 운반비` 1건 → 매핑 동순위 중복 (E-023)
- `posting_date`가 2026-06인 행 1건 (마감 기간, E-014)
- `posting_date`와 `period_key` 불일치 1건 (E-013)
- 환입 전표 쌍 1건 (`reversal_of_document_no` 기입)
- `gl_account_name`은 기입하되 **매핑에 사용 금지**

- **PK:** `company_code + document_no + line_no` (M-04)
- **FK:** period, cost_center(nullable), plant

---

## 25_material_issue_dup.xlsx

`22_material_issue.xlsx`의 **바이트 단위 완전 복제**. 파일명만 상이.
→ 동일 `file_hash` → E-017 DUPLICATE_FILE

---

# D. Entity / FK 관계

## D-1. 키 체계 (M-01 확정)

```
Excel  : 자연키만 기재 (대리키 컬럼 없음)
DB     : id BIGINT 대리 PK + 자연키 UNIQUE
로딩   : 자연키 → 대리키 해석. 미해석 시 FK 오류로 보고 (자동 생성 금지)
```

## D-2. 마스터 계층

```
company (HB01)
 ├── plant (PL01)
 │    ├── cost_center (CC-100..990)  ─self→ parent (depth ≤ 2)
 │    │      └── work_center (WC-10..50)
 │    └── work_order
 ├── period (2026-06/07/08)
 ├── cost_element (DM/DL/OH/GA)
 ├── account_mapping ──→ cost_element, cost_center?
 ├── overhead_rate ──→ cost_center, period
 ├── tolerance_rule ──→ material?, product?
 ├── product (P-100..900)
 │    ├── bom_version ── bom_item ──→ material
 │    ├── routing_version ── routing_operation ──→ work_center
 │    └── standard_cost
 │           └── standard_cost_detail
 │                  ├──→ material                       (ref_type=MATERIAL)
 │                  └──→ routing_version + operation_seq (ref_type=OPERATION)
 ├── material (MAT-001..012)
 └── uom_conversion ──→ material?
```

## D-3. 거래 계층

```
work_order  [PK: company + wo_no]
 ├─→ product_code          FK product
 ├─→ period_key            FK period
 ├─→ bom_version_id        FK bom_version      ※immutable 스냅샷 (M-10)
 ├─→ routing_version_id    FK routing_version  ※immutable 스냅샷
 │
 ├─← production_output   [company + output_doc_no + output_line_no]
 ├─← material_issue      [company + issue_doc_no + issue_line_no]
 └─← labor_transaction   [company + labor_doc_no + labor_line_no]
        └─→ routing_operation
              via (work_order.routing_version_id + labor.operation_seq)   ※M-02

gl_transaction [company + document_no + line_no]
 ├─→ period, cost_center?, plant
 └─→ account_mapping (조인 조건은 D-4)
```

## D-4. 매핑 해석 규칙 (확정)

```sql
SELECT * FROM account_mapping m
WHERE m.company_code = gl.company_code
  AND m.gl_account_code = gl.gl_account_code
  AND m.is_active = 'Y'
  AND gl.posting_date BETWEEN m.effective_from AND m.effective_to
  AND (
        m.cost_center_code IS NULL
     OR (gl.cost_center_code IS NOT NULL AND m.cost_center_code = gl.cost_center_code)
      )                                              -- M-11
ORDER BY (m.cost_center_code IS NOT NULL) DESC, m.priority DESC
```
- 0건 → `UNMAPPED`
- 최상위 동순위 2건 이상 → `MAPPING_AMBIGUOUS` → `REVIEW_REQUIRED`
- `cost_element.is_manufacturing = 'N'` → 제조원가 집계 제외

## D-5. 산출물 계층 (Excel 없음)

```
cost_accumulation_run [run_id]
  input: material_issue + labor_transaction + gl_transaction + production_output
       + mapping_version + rule_version + engine_version
  input_hash = SHA256(정규화 직렬화)                    ※M-13
        │
        ├──→ actual_cost      (company, period, product, wo_no?, cost_element, run_id)
        ├──→ variance_result
        └──→ reconciliation_result
```

**ActualCost는 이 경로로만 생성됩니다. 어떤 Excel 파일에서도 직접 적재하지 않습니다.** (M-20)

## D-6. Traceability 역경로

```
actual_cost (run_id, product, cost_element)
  → work_order (wo_no)
  → material_issue / labor_transaction
  → source_file_id + source_sheet_name + source_row     ※M-05
  → source_file.file_name + file_hash
```

## D-7. Inventory / WIP

Phase 1에서 **테이블을 만들지 않습니다.** 기초 WIP = 0 조건(§I-2)과 기간 걸침 WO 제외 규칙으로 대체합니다.

---

# E. 데이터 생성 규칙

## E-1. 생성 순서 (역순 생성 금지)

```
1) 마스터 01~09  (company → period → cost_center → cost_element →
                  account_mapping → uom_conversion → product →
                  material → work_center)
2) 10_bom / 11_routing
3) 12_standard_cost  ※ detail 먼저 확정 → 요약 시트를 합계로 채움
4) 13_overhead_rate / 14_tolerance_rule
5) 20_work_order
6) 21_production_output
7) 22_material_issue   ※ BOM × 생산량 기준으로 역산 생성
8) 23_labor_transaction ※ Routing × 생산량 기준으로 역산 생성
9) 24_gl_transaction   ※ 22·23의 집계 결과로 기표
10) 25 복제본
11) 91_error_catalog
12) 90_expected_results  ※ 반드시 마지막
```

## E-2. 정상 데이터 생성 공식

```
예상투입량 = bom_item.standard_qty × (good_qty + scrap_qty)     ※rework 제외
표준공수   = routing_operation.standard_hours × good_qty
issued_qty = 예상투입량 (환산 적용 후)
actual_hours ≈ 표준공수 × (0.95 ~ 1.05)   ← tolerance 이내
amount = 수량 × 단가 (ROUND_HALF_UP)
```

## E-3. 반올림

```
금액   : 소수 4자리 저장, ROUND_HALF_UP
수량   : 소수 6자리
중간계산 반올림 금지 — 최종 저장 시점에만 적용
```

## E-4. 날짜 분포

| 항목 | 규칙 |
|---|---|
| WO start_date | 2026-07-01 ~ 2026-07-20 |
| production_date | start_date + 3~10일 |
| issue_date | start_date ~ production_date |
| labor_date | issue_date ~ production_date |
| GL posting_date | 2026-07-31 (월말 일괄 기표) |

## E-5. 코드 체계

| 대상 | 형식 |
|---|---|
| WO | `WO-2607-001` |
| 생산실적 | `PO-2607-001` |
| 자재출고 | `MI-2607-001` |
| 노무 | `LB-2607-001` |
| GL 전표 | `GL-260731-001` |

## E-6. GL 기표 규칙 (소비 대체분개)

```
[재료비]  차) 51100 원재료비  xxx   /  대) 14100 원재료  xxx
[노무비]  차) 52100 직접노무비 xxx  /  대) 25100 미지급급여 xxx
         차) 52200 간접노무비 xxx  /  대) 25100 미지급급여 xxx
[경비]    차) 531xx~534xx     xxx  /  대) 각 상대계정   xxx
```
- 상대계정(14100, 25100 등)은 `account_mapping`에 **넣지 않음** → 제조원가 집계 대상 아님
- 전표 단위 차대 균형 필수

---

# F. 정상 테스트 시나리오 (10개)

| ID | WO | 대상 | 검증 내용 | 기대 결과 |
|---|---|---|---|---|
| N-001 | WO-2607-001 | P-100 | BOM 정확 일치, scrap=0 | `NORMAL` |
| N-002 | WO-2607-002 | P-100 | scrap>0, (good+scrap) 기준 일치 | `NORMAL` (분모 검증) |
| N-003 | WO-2607-003 | P-300 | MAT-003 EA→KG 자재별 환산 후 일치 | `NORMAL` |
| N-004 | WO-2607-004 | P-200 | tolerance 이내 미세 차이 | `NORMAL` (WARNING 아님) |
| N-005 | WO-2607-005 | P-200 | RETURN 2건 반영 후 순액 일치 | `NORMAL` |
| N-006 | WO-2607-006 | P-100 | 동일 op_code(OP-INS) 2공정 정상 매칭 | `NORMAL` (M-02 검증) |
| N-007 | WO-2607-007 | P-300 | 동일 op_code(OP-TRN) 2공정 + 열처리 | `NORMAL` |
| N-008 | WO-2607-008 | P-400 | BOM-P400-B (7월 시점 단일 ACTIVE) | `NORMAL` |
| N-009 | 전사 | GL vs 원가 | DM+DL 대사 일치 | `MATCHED` |
| N-010 | CC-100/200 | OH | 배부율 존재 CC의 OH 배부 성공 | `ALLOCATED` |

> **N-001 ~ N-008에서 오류가 하나라도 발생하면 오탐(false positive)입니다.**
> 오류 시나리오보다 이쪽이 더 중요한 검증입니다.

---

# G. 오류 테스트 시나리오 (32개)

**컬럼:** `error_id` / `file_name` / `sheet_name` / `planned_row` / `related_entity` / `error_description` / `expected_behavior` / `expected_status`

> ⚠️ `planned_row`는 **설계 목표값**입니다. Excel 생성 후 **실제 행번호로 `91_error_catalog`를 갱신해야 합니다.** 생성 전 행번호를 확정된 사실로 취급하지 마십시오.

## G-1. BOM / 자재 (7)

| error_id | file | sheet | planned_row | entity | 설명 | 기대 동작 | 기대 상태 |
|---|---|---|---|---|---|---|---|
| E-001 | 22_material_issue | material_issue | 20 | WO-2607-009 / MAT-001 | 예상투입 대비 과다 출고 | 순출고 > 예상+tol 검출 | `BOM_OVER_ISSUE` / ERROR |
| E-002 | 22_material_issue | material_issue | 23 | WO-2607-010 / MAT-002 | 예상투입 대비 과소 출고 | 순출고 < 예상−tol 검출 | `BOM_UNDER_ISSUE` / ERROR |
| E-003 | 22_material_issue | material_issue | 27 | WO-2607-011 / MAT-011 | BOM 미등재 자재 출고 | BOMItem 조인 0건 | `NOT_IN_BOM` / WARNING |
| E-004 | 22_material_issue | material_issue | 30 | MAT-999 | 마스터 미등록 자재 | material FK 실패 | `UNKNOWN_MATERIAL` / CRITICAL |
| E-005 | 20_work_order | work_order | 21 | P-999 | 마스터 미등록 제품 | product FK 실패 | `UNKNOWN_PRODUCT` / CRITICAL |
| E-006 | 22_material_issue | material_issue | 33 | WO-9999 | 미등록 WO 참조 | work_order FK 실패 | `UNKNOWN_WO` / CRITICAL |
| E-018 | 22_material_issue | material_issue | — | WO-2607-012 / MAT-007 | BOM 자재의 출고 행 자체가 없음 | BOMItem 있으나 Issue 0건 | `MISSING_MATERIAL_ISSUE` / ERROR |

## G-2. 노무 (5)

| error_id | file | sheet | planned_row | entity | 설명 | 기대 동작 | 기대 상태 |
|---|---|---|---|---|---|---|---|
| E-007 | 23_labor_transaction | labor_transaction | 36 | seq=99 | Routing 미등재 공정 | routing_operation 조인 0건 | `UNKNOWN_ROUTING_OPERATION` / ERROR |
| E-009 | 23_labor_transaction | labor_transaction | 39 | actual_rate=0 | 임률 결측 | `actual_rate <= 0` | `INVALID_LABOR_RATE` / ERROR |
| E-010 | 23_labor_transaction | labor_transaction | 42 | actual_hours 과다 | 표준공수 대비 초과 | `> 표준 × (1+tol)` | `EXCESSIVE_LABOR_HOURS` / WARNING |
| E-028 | 23_labor_transaction | labor_transaction | 45 | overtime=−2 | 음수 잔업 | `overtime_hours < 0` | `NEGATIVE_OVERTIME` / ERROR |
| E-030 | 23_labor_transaction | labor_transaction | 47 | 합계 불일치 | `actual ≠ regular+overtime` | 검산 실패, 보정 금지 | `HOURS_SUM_MISMATCH` / ERROR |

## G-3. 수량 / 금액 (3)

| error_id | file | sheet | planned_row | entity | 설명 | 기대 동작 | 기대 상태 |
|---|---|---|---|---|---|---|---|
| E-008 | 22_material_issue | material_issue | 36 | issued_qty=−5 | 음수 출고 (ISSUE 타입) | `qty<0 AND type=ISSUE` | `NEGATIVE_QUANTITY` / ERROR |
| E-011 | 22_material_issue | material_issue | 39 | amount 불일치 | `amount ≠ unit_cost×qty` | 검산 실패, **보정 금지** | `AMOUNT_MISMATCH` / ERROR |
| E-021 | 21_production_output | production_output | 18 | good_qty=0 | 생산량 0 | variance 분모 0 | `ZERO_DENOMINATOR` / `NOT_CALCULABLE` |

## G-4. GL / 매핑 (6)

| error_id | file | sheet | planned_row | entity | 설명 | 기대 동작 | 기대 상태 |
|---|---|---|---|---|---|---|---|
| E-012 | 24_gl_transaction | gl_transaction | 38 | 53900 외주가공비 | 매핑 마스터 미등록 | account_mapping 0건 | `UNMAPPED_GL` / WARNING + `unmapped_gl_amount` |
| E-013 | 24_gl_transaction | gl_transaction | 40 | posting≠period | 기간 귀속 불일치 | posting_date가 period 범위 밖 | `PERIOD_MISMATCH` / ERROR |
| E-014 | 24_gl_transaction | gl_transaction | 42 | posting=2026-06 | 마감 기간 전표 | `period.is_closed = Y` | `PERIOD_CLOSED` / ERROR |
| E-023 | 24_gl_transaction | gl_transaction | 44 | 53500 운반비 | 동순위 매핑 2건 | 최상위 동순위 복수 | `MAPPING_AMBIGUOUS` / `REVIEW_REQUIRED` |
| E-027 | 24_gl_transaction | gl_transaction | 30~44 | DM/DL 총액 | 원가 대비 GL 차이 | `|차이| > GL_RECON tol` | `GL_RECON_DIFFERENCE` / `DIFFERENCE` |
| E-029 | 24_gl_transaction | gl_transaction | 34~35 | GL-260731-012 | 전표 차대 불균형 | `Σdebit ≠ Σcredit` | `GL_UNBALANCED_DOCUMENT` / CRITICAL |

## G-5. 마스터 / 기준정보 (6)

| error_id | file | sheet | planned_row | entity | 설명 | 기대 동작 | 기대 상태 |
|---|---|---|---|---|---|---|---|
| E-015 | 12_standard_cost | standard_cost | — | P-900 | 표준원가 미등록 | StandardCost 조인 0건 | `STANDARD_COST_MISSING` / `NOT_CALCULABLE` |
| E-016 | 06_uom_conversion | uom_conversion | — | MAT-004 EA→KG | 환산 정보 부재 | conversion 조인 0건 | `UOM_CONVERSION_MISSING` / `REVIEW_REQUIRED` |
| E-022 | 10_bom | bom_version | 5~6 | BOM-P400-A/B | effective 구간 중첩 | 동일 시점 ACTIVE 2건 | `BOM_VERSION_AMBIGUOUS` / `REVIEW_REQUIRED` |
| E-024 | 13_overhead_rate | overhead_rate | — | CC-300 | 배부율 미제공 | overhead_rate 조인 0건 | `OVERHEAD_NOT_ALLOCATED` / `NOT_ALLOCATED` |
| E-025 | 14_tolerance_rule | tolerance_rule | 2, 7 | BOM_ISSUE 전역 | 동일 구체성·동일 priority | 룰 선택 불가 | `TOLERANCE_AMBIGUOUS` / `REVIEW_REQUIRED` |
| E-031 | 12_standard_cost | standard_cost_detail | — | P-200 DM | detail 합계 ≠ 요약 금액 | 검산 실패 | `STD_DETAIL_SUM_MISMATCH` / ERROR |

## G-6. 파일 / 파싱 (5)

| error_id | file | sheet | planned_row | entity | 설명 | 기대 동작 | 기대 상태 |
|---|---|---|---|---|---|---|---|
| E-017 | 25_material_issue_dup | material_issue | (전체) | 파일 | 동일 hash 재업로드 | file_hash 일치 검출 | `DUPLICATE_FILE` / WARNING, **적재 거부** |
| E-019 | 21_production_output | production_output | — | WO-2607-017 | 생산실적 행 없음 | ProductionOutput 0건 | `NO_PRODUCTION_OUTPUT` / `NOT_CALCULABLE` |
| E-020 | 21_production_output | production_output | 15 | rework_qty=4 | 재작업 발생 | 자동 판정 금지 | `REWORK_REVIEW_REQUIRED` / `REVIEW_REQUIRED` |
| E-026 | 20_work_order | work_order | 19~20 | WO-2607-018/019 | end_date가 8월 | 기간 걸침 | Recon 제외 + `excluded_wo_amount` |
| E-032 | 22_material_issue | material_issue | 52 | issued_qty=`"1,2 3 4"` | Decimal 파싱 불가 | 변환 실패, 보정 금지 | `INVALID_DECIMAL` / CRITICAL |

## G-7. 별도 변형 파일 (2) — 선택

| error_id | 방법 | 기대 상태 |
|---|---|---|
| E-033 | `22`에서 `issued_qty` 컬럼 삭제한 변형본 | `MISSING_REQUIRED_COLUMN` / CRITICAL, 적재 중단 |
| E-034 | `21`의 `production_date`에 `2026-13-01` 기입 | `INVALID_DATE` / CRITICAL |

**사용자 요구 25개 오류 유형 전부 포함 + 추가 7개 = 32개.**

---

# H. Expected Result 구조

## 90_expected_results.xlsx — 4 Sheet

### 공통 컬럼

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `assertion_id` | STRING(20) | `A-001` 형식 |
| `scope` | ENUM | `PRODUCT_COST` / `VARIANCE` / `GL_RECON` / `VALIDATION` |
| `scope_key` | STRING(100) | 대상 식별자 (예: `P-100/2026-07/DM`) |
| `expected_status` | STRING(30) | `NORMAL`, `NOT_CALCULABLE`, `REVIEW_REQUIRED` 등 |
| `expected_value` | STRING | **문자열로 기재** (float 변환 방지) |
| `calculation_basis` | STRING(300) | 산출 근거 — 어떤 파일·행·공식에서 나왔는지 |
| `confidence` | ENUM | `ASSERTED` / `DERIVED` |
| `note` | STRING(200) | 비고 |

### confidence 정의 (중요)

| 값 | 의미 |
|---|---|
| `ASSERTED` | **설계 의도.** "이 오류를 넣었으니 이 상태가 나와야 한다" — 오류 시나리오는 전부 이것 |
| `DERIVED` | **수기 계산.** 사람이 Excel/전자계산기로 계산한 값. **틀렸을 수 있음** |

### Sheet 구성

| Sheet | 내용 | 예상 행수 |
|---|---|---|
| `product_cost` | 제품×기간×원가요소 표준/실제 금액 | 약 15 |
| `variance` | 제품별 총차이, 분해 가능 여부 | 약 12 |
| `gl_recon` | GL vs 실제원가, unmapped 금액, 제외 WO | 약 6 |
| `validation_summary` | 오류코드별 발생 건수 | 약 32 |

### 사용 원칙 (확정)

```
1. 90_expected_results는 Rule Engine의 정답이 아니다.
2. 엔진 결과와 불일치 시 → 조사 대상이지 엔진 수정 근거가 아니다.
3. confidence=DERIVED 항목의 불일치는 expected 쪽 오류 가능성을 먼저 검토한다.
4. confidence=ASSERTED 항목의 불일치는 엔진 결함 가능성이 높다.
5. 이 파일은 데이터 로딩 파이프라인에서 제외한다. (M-18)
```

## 91_error_catalog.xlsx — 1 Sheet

| 컬럼 | 타입 | 필수 |
|---|---|---|
| `error_id` | STRING(10) | N |
| `file_name` | STRING(100) | N |
| `sheet_name` | STRING(50) | N |
| `row_number` | INT | **Y** (행 단위가 아닌 오류는 공란) |
| `related_entity` | STRING(100) | N |
| `error_description` | STRING(300) | N |
| `expected_behavior` | STRING(300) | N |
| `expected_status` | STRING(30) | N |
| `injection_type` | ENUM(`INTENTIONAL`/`ARTIFACT`) | N |
| `injected_by` | STRING(50) | N |
| `injected_at` | DATE | N |

### `injection_type` — §7 요구사항의 핵심

| 값 | 의미 |
|---|---|
| `INTENTIONAL` | 테스트 목적 의도 삽입 |
| `ARTIFACT` | 생성 과정 실수로 발견된 것. **발견 즉시 이 값으로 등재하거나 데이터를 수정** |

**규칙:** 엔진이 검출한 오류 중 `91_error_catalog`에 없는 것이 있으면, 그것은
(a) 데이터 생성 실수 또는 (b) 엔진의 오탐 입니다. **둘을 구분하기 전까지 어느 쪽도 수정하지 않습니다.**

---

# I. README에 기록할 가정 (14항목)

`data/sample/hanbit_mvp_dataset/README.md`에 아래를 **그대로** 기재합니다.

| # | 항목 | 확정 내용 |
|---|---|---|
| 1 | **대상 기간** | `2026-07` 단일. `2026-06`은 마감 상태로만 존재(거래 없음), `2026-08`은 기간 걸침 WO 검증용 |
| 2 | **기초 WIP 조건** | 본 **샘플 데이터셋에 한해** 2026-07을 최초 기간으로 보아 기초 WIP = 0으로 설정. **이는 시스템의 회계 원칙이 아니며**, 실제 도입 시 기초 WIP는 반드시 존재한다고 가정해야 함 |
| 3 | **GL 재료비 계정의 의미** | `51100 원재료비`는 **소비 대체분개**(차변 재료비 / 대변 원재료). 매입액이 아님. **이는 본 샘플의 구조일 뿐, 모든 기업의 GL 구조를 의미하지 않음.** 매입 기준 GL을 쓰는 기업은 재고 잔액 데이터가 추가로 필요 |
| 4 | **Material Issue unit_cost 산정방식** | `material_master.standard_price` 고정(표준단가법). → **Price Variance는 구조상 0에 수렴**. 이동평균/실제원가를 쓰면 결과가 달라짐 ※§J-2 확정 필요 |
| 5 | **표준임률의 출처** | `12_standard_cost`의 DL `standard_unit_price` **단일 출처**. `work_center`에는 임률 컬럼을 두지 않음 (이중 기준 제거) |
| 6 | **잔업할증 포함 여부** | `actual_rate`는 **기본임률(할증 미포함)**. `overtime_hours`는 시간만 별도 기록. → 할증분은 본 샘플의 원가에 포함되지 않음 ※§J-3 확정 필요 |
| 7 | **Scrap 처리 가정** | 전 자재가 **전공정에서 투입**된다고 가정. 예상투입 분모에 `scrap_qty` 포함. 후공정 scrap의 전공정 자재만 소비되는 실제 상황은 Phase 1 미반영 |
| 8 | **Rework 처리** | `rework_qty`는 예상투입 계산에 **포함하지 않음**(이중계상 방지). `rework_qty > 0`인 WO는 자동 판정하지 않고 `REVIEW_REQUIRED` |
| 9 | **BOM standard_qty 의미** | **완제품 1단위당** 투입량. 기간 총량이 아님. `scrap_factor`는 전 행 공란(실적 scrap과 이중적용 방지) |
| 10 | **Routing standard_hours 의미** | **완제품 1단위당** 표준공수. setup 시간 미포함 |
| 11 | **UOM 환산 정책** | 1단계 직접 환산만 지원(연쇄 환산 미지원). 자재별 환산이 전역 환산보다 우선. 환산 정보 없으면 `REVIEW_REQUIRED` (1:1 가정 금지) |
| 12 | **OH 배부 기준** | 배부기준 `DLH`(`direct_indirect = DIRECT`인 노무시간만). 예정배부율 사용. 배부율 미제공 CC는 `NOT_ALLOCATED`. under/over applied는 **표시만 하고 재배부하지 않음** |
| 13 | **tolerance 적용 방식** | scope 일치 → 구체성(material > product > 전역) → priority DESC. 동순위 복수 시 `REVIEW_REQUIRED`. 수치는 **본 가상 회사의 정책값**이며 실무 기준이 아님 ※§J-1 확정 필요 |
| 14 | **반올림 정책** | `ROUND_HALF_UP`. 금액 소수 4자리, 수량·시간 소수 6자리. **중간계산 반올림 금지**, 최종 저장 시점에만 적용 |

**추가 기재 항목**
- 15. 통화: `KRW`
- 16. 방산원가·세무 판단은 본 데이터셋에 일절 포함되지 않음
- 17. `90` / `91` 파일은 로딩 대상이 아님
- 18. 모든 수치는 **가상값**이며 실제 기업 데이터가 아님

---

# J. 사람의 결정이 필요한 항목

## J-1. 반드시 사람이 결정 (5건)

이 값들은 **회사 정책**이므로 제가 만들어내면 근거 없는 규칙이 됩니다.

| # | 항목 | 필요한 결정 | 미결정 시 |
|---|---|---|---|
| **J-1-1** | **tolerance 수치** | `14_tolerance_rule`의 abs/pct 값 (5행) | BOM/Labor 판정 자체가 비결정적 |
| **J-1-2** | **unit_cost 산정방식** | 표준단가법 / 이동평균법 / 실제원가법 | Price Variance 해석 불가 |
| **J-1-3** | **잔업할증 포함 여부** | `actual_rate`에 할증 포함? 별도 관리? | Rate Variance 왜곡 |
| **J-1-4** | **OH 예정배부율 수치** | `13_overhead_rate`의 `rate_per_base` | OH 배부 불가 |
| **J-1-5** | **GL_RECON 허용차이** | 대사 차이의 허용 한계 | Recon 상태 판정 불가 |

> **가상 회사 정책으로 정하는 것은 회계규칙 창작이 아닙니다.** 다만 그 값이 **귀사 실무 기준과 다를 수 있음**을 인지한 상태에서 승인해 주셔야 합니다.
> 참고로 제 초안(§C의 `?` 자리)에 넣을 값을 제안드릴 수는 있으나, **승인 없이 채우지 않겠습니다.**

## J-2. Claude가 합리적 가정으로 결정 가능 (7건)

| # | 항목 | 근거 |
|---|---|---|
| J-2-1 | 가상 회사명·제품명·자재명·코드체계 | 순수 가상 설정 |
| J-2-2 | BOM 구성 자재·수량 | 기계가공 업종 상식 범위. 회계규칙 아님 |
| J-2-3 | Routing 공정 구성·표준공수 | 위와 동일 |
| J-2-4 | 표준단가 수치 | 가상값. **단, BOM×단가 = 표준금액 일관성은 필수** |
| J-2-5 | 거래 건수·날짜 분포 | 데이터 볼륨 설계 |
| J-2-6 | UOM 환산계수 | `1KG = 1000G`는 물리 상수. 자재별 환산(12.5KG/본)은 가상 설정 |
| J-2-7 | 오류 삽입 위치·행번호 | 테스트 설계 영역 |

## J-3. 이미 결정된 항목 (사용자 지시로 확정)

| 항목 | 결정 |
|---|---|
| 업종 | 정밀 금속 기계가공 부품 제조 |
| 제품 수 | 4개 (+ 테스트용 P-900) |
| GL 구조 | 소비 대체분개 (샘플 한정) |
| 기초 WIP | 0 (샘플 한정) |
| 방산원가 | 미구현 |
| 표준임률 출처 | `standard_cost` 단일화 (§7-5 해소) |

---

# K. 데이터셋 생성 가능 여부

## K-1. 판정

**조건부 가능.** J-1의 5개 값이 결정되면 **22개 파일 전부 생성 가능**합니다.

## K-2. 항목별 가능 여부

| Phase 1 완료 조건 | 본 사양으로 | 비고 |
|---|---|---|
| Excel Upload / Header 정규화 / Decimal Parsing | ✅ | E-032, E-033 포함 |
| Row-Level Validation | ✅ | |
| Master Validation | ✅ | |
| Cost Center / Period / Product / Material | ✅ | |
| Account Mapping | ✅ | 05 파일 + E-012, E-023 |
| BOM Version / Routing Version | ✅ | E-022 + M-02 검증 |
| Work Order / Production Output | ✅ | |
| Material Issue / Labor Transaction | ✅ | |
| Standard Cost | ✅ | detail 시트 포함 |
| Actual Cost / Cost Accumulation | ✅ | 산출물, Excel 없음 |
| Variance — **Total** | ✅ | |
| Variance — **Quantity / Efficiency** | ✅ | `standard_cost_detail` 제작 시 |
| Variance — **Price** | ⚠️ | J-1-2가 표준단가법이면 **PV는 구조상 0**. 검증 의미가 약함 |
| Variance — **Rate** | ⚠️ | J-1-3에 종속 |
| GL Reconciliation | ✅ | 소비 대체분개 + 기초 WIP=0 조건 하에서 |
| Traceability / Source Row | ✅ | M-05 반영 시 |
| Calculation Run / Audit Log | ✅ | |
| API / pytest / README | ✅ | |

## K-3. 남은 위험

| # | 위험 | 영향 | 완화 |
|---|---|---|---|
| R-1 | **Price Variance 검증 불가** | J-1-2를 표준단가법으로 하면 `AP = SP`이므로 PV가 항상 0. 공식 구현은 되나 값으로 검증 불가 | 일부 자재(2~3종)만 `unit_cost`를 표준단가와 다르게 설정하고 그 사유를 README에 명시 |
| R-2 | **표준원가 내부 정합성** | detail 합계 ≠ 요약 금액이면 Variance 전체가 무의미 | E-031 외 전 행 검산 필수. 생성 순서 §E-1 준수 |
| R-3 | **오류 간 간섭** | 한 WO에 오류 2개 이상 겹치면 어느 룰이 먼저 발동하는지 비결정적 | **오류 1개당 WO 1개 원칙.** 부득이한 경우 `91_error_catalog`에 상호작용 명시 |
| R-4 | **planned_row와 실제 행번호 불일치** | Traceability 테스트가 통째로 실패 | 생성 후 `91_error_catalog` **필수 갱신** |
| R-5 | **GL 금액 역산 순서** | 24를 22·23보다 먼저 만들면 대사가 맞지 않음 | §E-1 생성 순서 엄수 |
| R-6 | **기간 걸침 WO의 GL 처리** | 018·019의 자재·노무가 GL에 포함되면 Recon 차이 발생 | GL에서 해당 WO분을 **포함**시키고, Recon에서 `excluded_wo_amount`로 설명 가능한지 확인 (이것이 E-026의 실질 검증) |

## K-4. 다음 단계

| 순서 | 작업 | 담당 |
|---|---|---|
| 1 | A절 수정사항 20건 검토·승인 | 사용자 |
| 2 | **J-1 5개 값 결정** | 사용자 |
| 3 | 마스터 14개 파일 생성 | 사용자 또는 Claude |
| 4 | 거래 6개 파일 생성 (§E-1 순서) | 사용자 또는 Claude |
| 5 | `91_error_catalog` 작성 + 실제 행번호 확정 | 생성자 |
| 6 | `README.md` 작성 (§I 18항목) | 생성자 |
| 7 | `90_expected_results` 작성 | 생성자 |
| 8 | **데이터셋 무결성 검증** (FK / UOM / Period / 검산) | Claude |
| 9 | Data Dictionary 확정 | Claude |
| 10 | DB Model 구현 착수 | Claude |

**8번 이전에는 애플리케이션 코드를 작성하지 않습니다.**

---

## 부록. 본 문서에서 확정하지 않은 것

- tolerance / OH 배부율 / GL_RECON 허용차이의 **구체적 수치** (§J-1)
- Excel 파일의 **실제 행번호** (생성 후 확정)
- `90_expected_results`의 **모든 값** (데이터 생성 후 계산)
- 헤더의 **한국어 실제 표기** (Excel 생성 시 결정 → 정규화 사전 입력)

이 항목들을 확정된 사실로 인용하지 마십시오.
