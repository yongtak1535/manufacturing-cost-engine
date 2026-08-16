# Phase 1 가상 제조기업 샘플 데이터셋 — 최종 데이터 설계서

**버전:** v1.0 (설계 확정용)
**작성 기준:** 개발 프롬프트 v1.0 + 1~2차 설계 검토
**상태:** 실제 데이터 미확보. 본 문서는 *데이터셋 제작 사양*이며, 데이터 생성 후 재검증 필요.

---

## 0. 본 문서의 전제와 한계

| 항목 | 내용 |
|---|---|
| 확정 대상 | 파일 구성 / 컬럼 / FK / 오류 시나리오 |
| 미확정 대상 | tolerance 수치, OH 배부율, unit_cost 산정방식 등 (§8 참조) |
| 금지 사항 | 본 문서의 예시 수치를 "실제 결과"로 인용하지 않음 |
| 법령 판단 | 없음. 방산원가·세무 규칙은 일절 포함하지 않음 |

본 문서에 등장하는 모든 수치(제품코드, 금액, 허용오차 등)는 **데이터셋 제작을 위한 예시**이며 실제 계산 결과가 아닙니다.

---

## 1. Entity 필수 / 선택 구분

### 1-1. 필수 (없으면 Phase 1 MVP 성립 불가)

| Entity | 필수 사유 | 비고 |
|---|---|---|
| Company | 모든 데이터의 격리 축 | Tenant 테이블은 불필요, `company_id` 컬럼만 |
| Plant | GL·CostCenter·WO의 물리 축 | 단일 공장이라도 마스터 유지 |
| Period | 기간 귀속 검증의 기준 | 마감 여부 포함 |
| CostElement | DM/DL/OH 분류의 기준 | `is_manufacturing` 필수 |
| CostCenter | GL 집계·OH 배부·매핑 조건 | 계층(parent) 포함 |
| AccountMapping | GL → CostElement 확정 | **없으면 GL 전량 UNMAPPED** |
| Product / Material | 모든 원가의 대상 | |
| UOM / UOMConversion | BOM vs Issue 비교 전제 | 자재별 환산 필요 |
| BOMVersion / BOMItem | 표준투입량 산출 | 버전 스냅샷 필수 |
| RoutingVersion / RoutingOperation / WorkCenter | 표준공수 산출 | |
| WorkOrder | Traceability 중심축 | |
| ProductionOutput | BOM 검증 분모 | |
| MaterialIssue | 실제 재료비 원천 | |
| LaborTransaction | 실제 노무비 원천 | |
| GLTransaction | Reconciliation 대상 | |
| StandardCost | Variance 기준 | |
| **ToleranceRule** | BOM/Labor 판정 임계치 | **신설** |
| **OverheadRate** | OH 배부 근거 | **신설**, 없으면 NOT_ALLOCATED |
| CostAccumulationRun | 계산 재현성 | engine/rule/mapping version |
| ActualCost | 누적 결과 | 원천 입력 아님 |
| VarianceResult / ReconciliationResult | 산출물 | |
| SourceFile | Traceability 기점 | hash 포함 |
| ValidationResult | 오류 영속화 | 응답 스키마 → 테이블 승격 |
| AuditLog | 완료 조건 항목 | Phase 1은 경량 구현 |

### 1-2. 선택 (Phase 1 제외 권장, 구조만 확보)

| Entity | 판단 | 사유 |
|---|---|---|
| Tenant (테이블) | 제외 | `company_id` 컬럼으로 충분 |
| Contract | 제외 | 방산·계약별 원가는 Phase 2 |
| **InventoryBalance** | **조건부 필요** | §7-9 참조. GL 재료비 계정 정의에 따라 필수가 될 수 있음 |
| WIPBalance | 제외 | 단, Recon 범위를 §7-8대로 한정하는 것이 전제 |
| OverheadApplication | 제외 | ActualCost(OH 행)에 흡수 가능 |
| ProductCostSummary | 제외 | 조회 시 산출 |
| User / Role | 제외 | 인증 미구현 |

### 1-3. 판단 보류

`InventoryBalance`는 Phase 1 필수/선택이 **GL 설계에 종속**됩니다. §7-9에서 상술합니다.

---

## 2. Excel 파일 목록 (제안)

기존 `00~10` 번호 체계는 마스터가 누락되어 있어 **재번호를 제안**합니다.

### 마스터 (14개)

| 파일 | 신규 여부 |
|---|---|
| `01_company_plant.xlsx` | 신규 |
| `02_period.xlsx` | 신규 |
| `03_cost_center.xlsx` | 신규 |
| `04_cost_element.xlsx` | 신규 |
| `05_account_mapping.xlsx` | **신규 (최우선)** |
| `06_uom_conversion.xlsx` | 신규 |
| `07_product_master.xlsx` | 기존 01 |
| `08_material_master.xlsx` | 기존 02 |
| `09_work_center.xlsx` | 신규 |
| `10_bom.xlsx` | 기존 03 (2 sheet) |
| `11_routing.xlsx` | 기존 04 (2 sheet) |
| `12_standard_cost.xlsx` | 기존 09 (2 sheet) |
| `13_overhead_rate.xlsx` | 신규 |
| `14_tolerance_rule.xlsx` | 신규 |

### 거래 (6개)

| 파일 | 신규 여부 |
|---|---|
| `20_work_order.xlsx` | 기존 05 |
| `21_production_output.xlsx` | 기존 06 |
| `22_material_issue.xlsx` | 기존 07 |
| `23_labor_transaction.xlsx` | 기존 08 |
| `24_gl_transaction.xlsx` | 기존 10 |
| `25_inventory_opening.xlsx` | 조건부 (§7-9) |

### 검증 (2개)

| 파일 | 용도 |
|---|---|
| `90_expected_results.xlsx` | **맨 마지막에 작성.** 정답이 아니라 *가설* |
| `91_error_catalog.xlsx` | 의도 삽입 오류 목록 (§6) |

**총 21~22개.** 마스터는 대부분 5~20행 규모입니다.

---

## 3. 파일별 컬럼 사양

공통 규약:

- `DECIMAL(18,6)` = 수량·시간 / `DECIMAL(18,4)` = 금액·단가
- `DATE` = `YYYY-MM-DD` 문자열
- 모든 거래 파일은 Excel 헤더 1행 + 데이터 2행부터 → `source_row`는 **Excel 실제 행번호**
- 모든 파일에 `company_code` 포함 (단일 회사라도)

---

### 01_company_plant.xlsx

- **목적:** 회사·공장 마스터
- **Sheet:** `company`, `plant`
- **필수 (company):** `company_code` STRING(20), `company_name` STRING(100), `currency_code` STRING(3)
- **필수 (plant):** `company_code`, `plant_code` STRING(20), `plant_name` STRING(100)
- **선택:** `address`, `is_active` BOOL
- **PK:** `company_code` / (`company_code`,`plant_code`)
- **FK:** plant.company_code → company
- **관계:** 전 파일의 상위 축

---

### 02_period.xlsx

- **목적:** 회계기간 정의 및 마감 상태
- **필수:** `company_code`, `period_key` STRING(7, `YYYY-MM`), `year` INT, `month` INT, `start_date` DATE, `end_date` DATE, `is_closed` BOOL
- **선택:** `closed_at` DATE
- **PK:** (`company_code`,`period_key`)
- **관계:** WO / GL / StandardCost / ActualCost가 참조
- **제작 지침:** `2026-06`(is_closed=TRUE), `2026-07`(FALSE), `2026-08`(FALSE) 3개 생성. 06을 마감 상태로 두어야 E-013 테스트 가능.

---

### 03_cost_center.xlsx

- **목적:** 원가중심점 마스터
- **필수:** `company_code`, `plant_code`, `cost_center_code` STRING(20), `cost_center_name` STRING(100), `cc_type` ENUM(`PRODUCTION`,`SERVICE`,`ADMIN`), `is_active` BOOL
- **선택:** `parent_cost_center_code` (self-FK)
- **PK:** (`company_code`,`cost_center_code`)
- **FK:** plant, self
- **제작 지침:** 생산 CC 3개(가공/조립/검사), 서비스 CC 1개(생산관리), 관리 CC 1개(본사). 관리 CC는 제조원가에서 배제되어야 함.

---

### 04_cost_element.xlsx

- **목적:** 원가요소 정의
- **필수:** `cost_element_code` ENUM(`DM`,`DL`,`OH`,`GA`), `cost_element_name`, `is_manufacturing` BOOL
- **PK:** `cost_element_code`
- **제작 지침:** `GA`의 `is_manufacturing = FALSE`. 이 플래그가 제조원가 집계 필터의 유일한 근거.

---

### 05_account_mapping.xlsx ★최우선

- **목적:** GL 계정 → 원가요소 확정 매핑 (keyword 추정 금지의 전제)
- **필수:** `company_code`, `gl_account_code` STRING(20), `cost_element_code`, `effective_from` DATE, `effective_to` DATE, `priority` INT, `is_active` BOOL
- **선택:** `cost_center_code`(조건부 매핑), `contract_no`(Phase 2용, 빈칸)
- **PK:** 대리키 `mapping_id`
- **FK:** company, cost_element, cost_center
- **관계:** GLTransaction과 (account + date + cost_center) 조인
- **제작 지침 (중요):**
  - `cost_center_code`가 채워진 행이 **더 높은 priority**를 갖도록 설계
  - GL 계정 중 **최소 1개는 의도적으로 매핑에서 제외** (E-012)
  - effective 구간이 겹치면서 priority가 같은 행을 **1쌍** 삽입 (E-023 변형)

---

### 06_uom_conversion.xlsx

- **목적:** 단위 환산
- **필수:** `from_uom` STRING(10), `to_uom` STRING(10), `conversion_factor` DECIMAL(18,6), `effective_from` DATE, `effective_to` DATE
- **선택:** `material_code` (자재별 환산 시)
- **PK:** 대리키
- **FK:** material (nullable)
- **제작 지침:**
  - 전역: `KG→G = 1000`, `M→MM = 1000`
  - 자재별: 원소재를 KG로 구매해 EA로 투입하는 자재 1~2개에 대해 `material_code` 채운 행
  - **환산 정보가 없는 UOM 조합을 1건 의도적으로 남길 것** (E-015)

---

### 07_product_master.xlsx

- **목적:** 완제품 마스터
- **필수:** `company_code`, `product_code` STRING(20), `product_name` STRING(100), `base_uom` STRING(10), `is_active` BOOL
- **선택:** `product_group`, `plant_code`
- **PK:** (`company_code`,`product_code`)
- **관계:** BOM / Routing / WO / StandardCost / ProductionOutput

---

### 08_material_master.xlsx

- **목적:** 원부자재 마스터
- **필수:** `company_code`, `material_code` STRING(20), `material_name`, `base_uom`, `material_type` ENUM(`RAW`,`SUB`,`CONSUMABLE`), `is_active`
- **선택:** `standard_price` DECIMAL(18,4), `procurement_type`
- **PK:** (`company_code`,`material_code`)
- **관계:** BOMItem / MaterialIssue / UOMConversion
- **제작 지침:** `CONSUMABLE` 1~2개를 두어 "BOM에 없는 간접자재" 시나리오(E-003) 구분에 사용.

---

### 10_bom.xlsx (2 sheet)

**Sheet `bom_version`**
- **필수:** `company_code`, `bom_version_id` STRING(30), `product_code`, `revision` STRING(10), `effective_from` DATE, `effective_to` DATE, `status` ENUM(`ACTIVE`,`INACTIVE`)
- **PK:** `bom_version_id`
- **FK:** product

**Sheet `bom_item`**
- **필수:** `bom_version_id`, `line_no` INT, `material_code`, `standard_qty` DECIMAL(18,6), `uom`
- **선택:** `scrap_factor` DECIMAL(9,6)
- **PK:** (`bom_version_id`,`line_no`)
- **FK:** bom_version, material

**제작 지침 (중요):**
- `standard_qty`는 **완제품 1단위당 투입량**으로 고정 (총량 아님)
- `scrap_factor`는 **전 행 공란 권장**. 값이 있으면 실적 scrap과 이중계상 위험 (§7-1)
- 제품 1개에 대해 effective 구간이 겹치는 버전 2개를 삽입 (E-023)

---

### 11_routing.xlsx (2 sheet)

**Sheet `routing_version`**
- **필수:** `company_code`, `routing_version_id` STRING(30), `product_code`, `revision`, `effective_from`, `effective_to`, `status`
- **PK:** `routing_version_id`

**Sheet `routing_operation`**
- **필수:** `routing_version_id`, `operation_seq` INT, `operation_code` STRING(20), `operation_name`, `work_center_code`, `standard_hours` DECIMAL(18,6)
- **선택:** `setup_hours`
- **PK:** (`routing_version_id`,`operation_seq`)
- **FK:** routing_version, work_center

**제작 지침:** `standard_hours`도 **완제품 1단위당**으로 고정.

---

### 09_work_center.xlsx

- **필수:** `company_code`, `plant_code`, `work_center_code` STRING(20), `work_center_name`, `cost_center_code`, `is_active`
- **선택:** `standard_rate` DECIMAL(18,4) — 표준임률
- **PK:** (`company_code`,`work_center_code`)
- **FK:** plant, cost_center
- **주의:** WorkCenter별 `standard_rate`와 StandardCost의 DL 단가가 불일치하면 Labor Variance가 두 기준을 갖게 됨 (§7-5). **어느 쪽을 표준임률로 쓸지 데이터셋에서 일관되게 정할 것.**

---

### 12_standard_cost.xlsx (2 sheet)

**Sheet `standard_cost`** (요소 레벨)
- **필수:** `company_code`, `product_code`, `period_key`, `cost_element_code`, `standard_qty` DECIMAL(18,6), `standard_unit_price` DECIMAL(18,4), `standard_amount` DECIMAL(18,4), `version` STRING(10), `effective_from`, `effective_to`
- **PK:** (`company_code`,`product_code`,`period_key`,`cost_element_code`,`version`)

**Sheet `standard_cost_detail`** (자재/공정 레벨) — **Price/Qty Variance를 원하면 필수**
- **필수:** `company_code`, `product_code`, `period_key`, `cost_element_code`, `ref_type` ENUM(`MATERIAL`,`OPERATION`), `ref_code`, `standard_qty`, `standard_unit_price`, `standard_amount`, `version`
- **FK:** material 또는 routing_operation

**제작 지침:**
- 모든 `standard_qty`는 **제품 1단위당**
- `standard_amount = standard_qty × standard_unit_price` 검산 가능하게 작성
- detail 합계 = 요소 레벨 금액과 **일치**하도록 작성 (불일치 1건은 의도 오류로 삽입 가능)
- 제품 1개는 StandardCost를 **의도적으로 누락** (E-014)

---

### 13_overhead_rate.xlsx

- **목적:** OH 배부 근거 (없으면 제품별 OH = NOT_ALLOCATED)
- **필수:** `company_code`, `period_key`, `cost_center_code`, `allocation_base` ENUM(`DLH`), `rate_per_base` DECIMAL(18,4), `effective_from`, `effective_to`
- **PK:** (`company_code`,`period_key`,`cost_center_code`)
- **제작 지침:** Phase 1은 **DLH 1종만**. 생산 CC 3개 중 **1개는 배부율 미제공** → 해당 CC 귀속 OH는 NOT_ALLOCATED로 남아야 함(정상 동작 확인용).

---

### 14_tolerance_rule.xlsx

- **목적:** 판정 임계치 외부화
- **필수:** `company_code`, `rule_scope` ENUM(`BOM_ISSUE`,`LABOR_HOURS`,`GL_RECON`,`AMOUNT_CHECK`), `abs_tolerance` DECIMAL(18,6), `pct_tolerance` DECIMAL(9,6), `apply_rule` ENUM(`GREATER_OF`,`ABS_ONLY`,`PCT_ONLY`), `severity` ENUM(`WARNING`,`ERROR`)
- **선택:** `material_code`, `product_code` (override)
- **PK:** 대리키
- **제작 지침:** 값은 **사용자가 지정**. 제가 제시한 ±3% 등은 근거 없는 임의값이므로 귀사 기준이 있으면 그것을 사용.

---

### 20_work_order.xlsx

- **목적:** 원가 추적 중심축
- **필수:** `company_code`, `plant_code`, `wo_no` STRING(30), `product_code`, `period_key`, `bom_version_id`, `routing_version_id`, `planned_qty` DECIMAL(18,6), `uom`, `wo_status` ENUM(`OPEN`,`CLOSED`), `start_date` DATE, `end_date` DATE
- **선택:** `cost_center_code`, `contract_no`(공란)
- **PK:** (`company_code`,`wo_no`)
- **FK:** product, bom_version, routing_version, period, plant
- **제작 지침 (중요):**
  - `bom_version_id` / `routing_version_id`를 **명시적으로 기입** (마스터 변경 영향 차단)
  - `end_date`가 다음 달로 넘어가는 WO를 **2건** 삽입 (E-025, Recon 제외 대상)
  - 마스터에 없는 `product_code`를 가진 WO **1건** (E-005)

---

### 21_production_output.xlsx

- **필수:** `company_code`, `wo_no`, `product_code`, `production_date` DATE, `good_qty` DECIMAL(18,6), `scrap_qty`, `rework_qty`, `uom`
- **PK:** 대리키 (`output_id`)
- **FK:** work_order, product
- **제작 지침:**
  - `scrap_qty > 0`인 WO 3건 이상 (BOM 검증 분모 검증용)
  - `rework_qty > 0`인 WO 1건 → **REVIEW_REQUIRED가 나와야 정상** (§7-2)
  - 산출 실적이 **아예 없는 WO** 1건 (E-022 → NOT_CALCULABLE)
  - `good_qty = 0`인 WO 1건 (E-026 → 분모 0)

---

### 22_material_issue.xlsx

- **필수:** `company_code`, `wo_no`, `material_code`, `issue_date` DATE, `issued_qty` DECIMAL(18,6), `uom`, `unit_cost` DECIMAL(18,4), `amount` DECIMAL(18,4), `issue_type` ENUM(`ISSUE`,`RETURN`)
- **선택:** `cost_center_code` (간접출고 시), `document_no`
- **PK:** 대리키 (`issue_id`)
- **FK:** work_order(nullable), material
- **제작 지침 (중요):**
  - `issue_type = RETURN` 행을 **2건** 삽입. 순액 기준 판정이 되는지 확인 (§7-1)
  - `wo_no` 공란 + `cost_center_code`만 있는 간접출고 1건 → 제품원가에서 제외되어야 함
  - `unit_cost` 산정방식(표준단가/이동평균)을 데이터셋 README에 **명시**
  - `amount ≠ unit_cost × issued_qty` 인 행 1건 (E-011)

---

### 23_labor_transaction.xlsx

- **필수:** `company_code`, `wo_no`, `operation_code`, `work_center_code`, `labor_date` DATE, `regular_hours` DECIMAL(18,6), `overtime_hours`, `actual_hours`, `actual_rate` DECIMAL(18,4), `amount` DECIMAL(18,4), `direct_indirect` ENUM(`DIRECT`,`INDIRECT`)
- **선택:** `employee_id`, `routing_version_id`
- **PK:** 대리키
- **FK:** work_order, routing_operation (via routing_version + operation_code), work_center
- **제작 지침:**
  - `actual_rate`에 **잔업할증 포함 여부를 README에 명시** (§7-6)
  - `actual_hours ≠ regular + overtime` 인 행 1건
  - routing에 없는 `operation_code` 1건 (E-006)
  - `overtime_hours < 0` 1건 (E-008)

---

### 24_gl_transaction.xlsx

- **필수:** `company_code`, `plant_code`, `period_key`, `document_no` STRING(30), `line_no` INT, `transaction_date` DATE, `posting_date` DATE, `gl_account_code`, `gl_account_name`, `debit` DECIMAL(18,4), `credit` DECIMAL(18,4), `cost_center_code`, `description`
- **선택:** `reversal_of_document_no`
- **PK:** (`document_no`,`line_no`)
- **FK:** period, cost_center, plant
- **제작 지침 (가장 중요 — §7-9 참조):**
  - **재료비 계정은 "소비 대체분개" 구조로 작성** (차변 재료비 / 대변 원재료). 매입액으로 작성하면 MaterialIssue와 원리적으로 대사 불가
  - **직접노무비 계정과 간접노무비 계정을 분리** (§7-6)
  - `gl_account_name`은 존재하되 **매핑 근거로 사용 금지** (표시 전용)
  - 매핑에 없는 계정 1개 (E-012)
  - `transaction_date`와 `posting_date`의 period가 다른 행 1건 (E-013)
  - 환입 전표 쌍 1건 (`reversal_of_document_no` 채움)

---

### 25_inventory_opening.xlsx (조건부)

- **필수:** `company_code`, `plant_code`, `period_key`, `material_code`, `opening_qty`, `opening_amount`
- **판단:** GL을 소비 대체분개로 작성하면 **Phase 1에서 생략 가능**. 매입 기준으로 작성한다면 **필수**.

---

### 90_expected_results.xlsx

- **작성 시점:** 모든 거래 파일 완성 **후 마지막**
- **Sheet:** `product_cost`, `variance`, `gl_recon`, `validation_summary`
- **필수 컬럼 (공통):** `assertion_id`, `scope`, `expected_value`, `expected_status`, `basis` (근거 설명), `confidence` ENUM(`ASSERTED`,`DERIVED`)
- **원칙:** 이 파일은 **정답이 아니라 가설**입니다. Rule Engine 결과와 불일치할 경우 어느 쪽이 틀렸는지 조사 대상이며, 자동으로 엔진을 맞추지 않습니다.

---

## 4. FK 관계도

### 4-1. 마스터 계층

```
company
 ├── plant
 │    ├── cost_center ──(self: parent_cost_center)
 │    │    └── work_center
 │    └── work_order
 ├── period
 ├── product
 │    ├── bom_version ── bom_item ──→ material
 │    ├── routing_version ── routing_operation ──→ work_center
 │    └── standard_cost ── standard_cost_detail ──→ material | routing_operation
 ├── material ──→ uom_conversion (material_code nullable)
 ├── cost_element
 ├── account_mapping ──→ cost_element, cost_center
 ├── overhead_rate ──→ cost_center, period
 └── tolerance_rule ──→ material?, product?
```

### 4-2. 거래 계층 (WorkOrder 중심)

```
work_order (PK: company_code + wo_no)
 ├─→ product_code            [FK] product
 ├─→ period_key              [FK] period
 ├─→ plant_code              [FK] plant
 ├─→ bom_version_id          [FK] bom_version   ※스냅샷, 재계산 금지
 ├─→ routing_version_id      [FK] routing_version ※스냅샷
 │
 ├─← production_output   (wo_no)  1:N
 ├─← material_issue      (wo_no)  1:N   ※wo_no NULL 허용 = 간접출고
 └─← labor_transaction   (wo_no)  1:N
```

### 4-3. 핵심 조인 규칙

**BOM 검증 경로**
```
work_order.bom_version_id
  → bom_item (material_code, standard_qty, uom)
  → × production_output.(good_qty + scrap_qty)      ← rework 제외
  → uom_conversion (필요 시, material_code 우선)
  ↔ material_issue Σ(ISSUE) − Σ(RETURN)             ← 순액
  → tolerance_rule (BOM_ISSUE) 적용
  → NORMAL | OVER_ISSUE | UNDER_ISSUE | NOT_IN_BOM | MISSING_ISSUE | REVIEW_REQUIRED
```

**Labor 검증 경로**
```
work_order.routing_version_id
  → routing_operation (operation_code, standard_hours, work_center)
  ↔ labor_transaction.operation_code
  → 미존재 시 ERROR (UNKNOWN_ROUTING_OPERATION)
  → 표준공수 = standard_hours × production_output.good_qty
```

**GL → CostElement 경로**
```
gl_transaction (gl_account_code, cost_center_code, posting_date)
  → account_mapping
       WHERE company_code 일치
         AND gl_account_code 일치
         AND (cost_center_code 일치 OR mapping.cost_center_code IS NULL)
         AND posting_date BETWEEN effective_from AND effective_to
         AND is_active
       ORDER BY priority DESC, cost_center_code NULLS LAST
       LIMIT 1
  → 0건: UNMAPPED
  → 동순위 2건 이상: MAPPING_AMBIGUOUS → REVIEW_REQUIRED
  → cost_element.is_manufacturing = FALSE: 제조원가 집계 제외
```

**OH 배부 경로 (조건부)**
```
gl_transaction(OH) → cost_center 별 집계
  → overhead_rate (period_key, cost_center_code) 존재?
       YES → 배부액 = Σ(labor_transaction.actual_hours WHERE DIRECT) × rate_per_base
       NO  → NOT_ALLOCATED (제품별 OH 미산출)
  → 실제발생액 vs 배부액 차이 = under/over applied → 표시만, 배분하지 않음
```

**Cost Accumulation 경로**
```
cost_accumulation_run (run_id)
  ├─ DM ← material_issue (wo_no NOT NULL) 순액
  ├─ DL ← labor_transaction (direct_indirect = DIRECT)
  └─ OH ← overhead_rate 배부 결과 (있을 때만)
       → actual_cost (company, period, product, wo_no, cost_element, run_id)
```

**Traceability 역방향**
```
actual_cost.run_id + product_code + cost_element
  → work_order
  → material_issue / labor_transaction
  → source_file_id + source_row
  → source_file.file_name
```

### 4-4. Inventory / WIP 연결 (Phase 1 미구현, 구조만)

```
inventory_balance : company + plant + period + material
   ↑ 연결 예정: material_issue(out), 매입 GL(in)

wip_balance : company + wo_no + period
   ↑ 연결 예정: material_issue / labor_transaction / OH 배부 / 완성품 대체
```

**Phase 1에서는 이 두 테이블에 값을 채우지 않습니다.** 대신 Recon 범위를 기간 내 완결 WO로 한정합니다(§7-8).

---

## 5~6. 테스트 시나리오

### 5-1. 정상 데이터 (오탐 검증용) — 최소 6건

오류만 있는 데이터셋은 **false positive를 검증할 수 없습니다.** 다음은 반드시 `NORMAL`이 나와야 합니다.

| ID | 내용 | 기대 |
|---|---|---|
| N-001 | BOM 정확 일치 (scrap=0) | NORMAL |
| N-002 | scrap 존재하나 (good+scrap) 기준 일치 | NORMAL (분모 검증) |
| N-003 | KG↔G 환산 후 일치 | NORMAL |
| N-004 | tolerance 이내 미세 차이 | NORMAL (WARNING 아님) |
| N-005 | RETURN 반영 후 순액 일치 | NORMAL |
| N-006 | GL ↔ ActualCost 완전 일치 (DM+DL) | MATCHED |

### 5-2. 의도 삽입 오류 — 22건

| 오류 ID | 발생 파일 | 관련 데이터 | 예상 오류 | 탐지 Rule | 예상 결과 |
|---|---|---|---|---|---|
| E-001 | 22_material_issue | BOM 존재 자재 | 과다 출고 | `순출고 > 예상투입 + tolerance` | `BOM_OVER_ISSUE` / ERROR |
| E-002 | 22_material_issue | BOM 존재 자재 | 과소 출고 | `순출고 < 예상투입 − tolerance` | `BOM_UNDER_ISSUE` / ERROR |
| E-003 | 22_material_issue | CONSUMABLE 자재 | BOM 미등재 자재 출고 | BOMItem 조인 0건 | `NOT_IN_BOM` / WARNING |
| E-004 | 22_material_issue | 미등록 자재코드 | Master FK 위반 | material 조인 0건 | `UNKNOWN_MATERIAL` / CRITICAL |
| E-005 | 20_work_order | 미등록 제품코드 | Master FK 위반 | product 조인 0건 | `UNKNOWN_PRODUCT` / CRITICAL |
| E-006 | 23_labor_transaction | routing 미등재 공정 | 공정코드 불일치 | routing_operation 조인 0건 | `UNKNOWN_ROUTING_OPERATION` / ERROR |
| E-007 | 22_material_issue | issued_qty = −5 | 음수 수량 | `issued_qty < 0 AND issue_type='ISSUE'` | `NEGATIVE_QUANTITY` / ERROR |
| E-008 | 23_labor_transaction | overtime_hours = −2 | 음수 잔업 | `overtime_hours < 0` | `NEGATIVE_OVERTIME` / ERROR |
| E-009 | 23_labor_transaction | 표준공수 대비 과다 | 공수 이상치 | `actual_hours > 표준공수 × (1+tol)` | `EXCESSIVE_LABOR_HOURS` / WARNING |
| E-010 | 23_labor_transaction | actual_rate = 0 | 임률 결측 | `actual_rate <= 0` | `INVALID_LABOR_RATE` / ERROR |
| E-011 | 22_material_issue | amount 불일치 | 금액 검산 실패 | `amount ≠ unit_cost × qty` (tol 내) | `AMOUNT_MISMATCH` / ERROR **보정 금지** |
| E-012 | 24_gl_transaction | 매핑 없는 계정 | 원가요소 미확정 | account_mapping 0건 | `UNMAPPED` / WARNING + Recon에 `unmapped_gl_amount` |
| E-013 | 24_gl_transaction | posting_date ≠ period | 기간 귀속 불일치 | `posting_date NOT BETWEEN period 범위` | `PERIOD_MISMATCH` / ERROR |
| E-014 | 12_standard_cost | 제품 1개 표준 누락 | 기준 부재 | StandardCost 조인 0건 | `STANDARD_COST_MISSING` → Variance `NOT_CALCULABLE` |
| E-015 | 06_uom_conversion | 환산 정보 부재 | 단위 비교 불가 | conversion 조인 0건 | `UOM_CONVERSION_NOT_FOUND` → `REVIEW_REQUIRED` **추정 금지** |
| E-016 | 22_material_issue | `"1,2 3 4"` | 파싱 불가 | Decimal 변환 실패 | `INVALID_DECIMAL` / CRITICAL |
| E-017 | 21_production_output | `2026-13-01` | 날짜 오류 | 날짜 파싱 실패 | `INVALID_DATE` / CRITICAL |
| E-018 | 별도 변형 파일 | 필수 컬럼 삭제 | 스키마 불일치 | canonical 필드 매핑 실패 | `MISSING_REQUIRED_COLUMN` / CRITICAL, 적재 중단 |
| E-019 | 22_material_issue 사본 | 동일 hash 재업로드 | 중복 적재 | file_hash 일치 | `DUPLICATE_SOURCE_FILE` / WARNING, 적재 거부 |
| E-020 | 22_material_issue | BOM 자재 출고 없음 | 누락 | BOMItem 있으나 Issue 0건 | `MISSING_ISSUE` / ERROR |
| E-021 | 22_material_issue | 미등록 wo_no | WO 연결 불가 | work_order 조인 0건 | `WO_NOT_FOUND` / CRITICAL |
| E-022 | 21_production_output | 산출 실적 없는 WO | 분모 부재 | ProductionOutput 0건 | BOM 검증 `NOT_CALCULABLE` |
| E-023 | 10_bom | effective 구간 중복 | 버전 모호 | 동일 시점 ACTIVE 2건 | `BOM_VERSION_AMBIGUOUS` / `REVIEW_REQUIRED` |
| E-024 | 24 vs 22/23 | 금액 차이 | GL/원가 불일치 | `|차이| > tolerance` | `DIFFERENCE` |
| E-025 | 20_work_order | 8월 완료 WO | 기간 걸침 | `end_date > period.end_date` | Recon 대상 제외 + `excluded_wo_amount` 표시 |
| E-026 | 21_production_output | good_qty = 0 | 분모 0 | 생산량 0 | variance_rate `NOT_CALCULABLE` **0% 반환 금지** |

**총 22건 + 정상 6건 = 28 시나리오.**

### 6-1. 데이터 오류 vs 의도 오류 구분

`91_error_catalog.xlsx`에 각 오류의 **삽입 위치(파일명 + 행번호)**를 기록해 두십시오. 이것이 없으면 "데이터셋 자체 결함"과 "테스트 대상 오류"를 구분할 수 없습니다 (프롬프트 §36).

---

## 7. 회계적 위험 재검토 (공격적)

### 7-1. BOM 투입량 — 위험 4가지

| # | 위험 | 결과 | 대응 |
|---|---|---|---|
| a | **`scrap_factor` + 실적 `scrap_qty` 이중 적용** | 예상투입 과대 → UNDER_ISSUE 오탐 | 둘 중 **하나만** 적용. 데이터셋은 scrap_factor 공란 권장 |
| b | **반납(RETURN)을 출고로 계상** | OVER_ISSUE 오탐 | `issue_type` 필수, **순액 기준** 판정 |
| c | **최소 출고 로트(MOQ)** | 소량 WO는 상시 OVER | Phase 1 미대응. 해당 자재는 tolerance override로 흡수하거나 REVIEW |
| d | **공통자재 일괄 출고 후 WO 미배분** | 특정 WO만 OVER, 나머지 MISSING | `wo_no` NULL 간접출고로 분리, 제품원가 제외 |

### 7-2. Scrap / Rework — **지난 제안 정정**

`rework_qty`를 예상투입 분모에 더하는 것은 **오류**입니다. 재작업품은 최초 투입에 이미 계상되어 있고, 추가 투입은 일부 공정·일부 자재에만 발생합니다. 더하면 이중계상입니다.

**확정 규칙:**
```
예상투입량 = BOMItem.standard_qty × (good_qty + scrap_qty)
rework_qty > 0  →  해당 WO는 REVIEW_REQUIRED (자동 판정 안 함)
```

또한 `scrap_qty`가 **공정 중 발생인지 최종검사 불량인지** 구분되지 않으면, 전량 투입 가정 자체가 틀립니다(후공정 scrap은 전공정 자재만 소비). Phase 1은 **전공정 투입 가정**을 쓰되, 이 가정을 문서에 명시해야 합니다.

### 7-3. Standard vs Actual Variance

**위험:** 표준을 실제 생산량으로 flex하지 않으면 조업도차이가 섞입니다.

```
비교 기준 = standard_amount(단위당) × good_qty      ← flexed budget
        vs actual_amount

standard_amount를 "기간 총액"으로 잘못 해석하면 전량 오류
```

→ `12_standard_cost`의 `standard_qty`가 **단위당**임을 데이터셋에 명시. 이것이 모호하면 Variance 전체가 무의미해집니다.

### 7-4. Price / Quantity Variance

**위험 a — 분해 순서 규약 부재.** 다음을 고정해야 합니다.
```
PV = (AP − SP) × AQ
QV = (AQ − SQ) × SP
PV + QV ≠ 총차이   (교차항 (AP−SP)×(AQ−SQ)가 PV에 흡수됨)
```
합계가 안 맞는 것이 **정상**입니다. 억지로 맞추면 회계적으로 틀립니다.

**위험 b — 구매가격차이(PPV) 혼입.** `MaterialIssue.unit_cost`가 이동평균이면 가격차이는 이미 구매·입고 단계에서 발생했고, 제조에서 잡히는 것은 사용시점 차이뿐입니다. 표준단가로 출고하면 PV는 항상 0이 됩니다.
→ **데이터셋에서 `unit_cost` 산정방식을 하나로 고정하고 명시.** 미명시 시 PV 해석 불가.

**위험 c — 자재별 표준 부재.** `standard_cost_detail` 없이는 PV/QV 계산 불가 → `NOT_CALCULABLE`.

### 7-5. Labor Variance

| 위험 | 내용 |
|---|---|
| 표준임률 출처 이원화 | `work_center.standard_rate` vs `standard_cost(DL).standard_unit_price` — 둘이 다르면 RV가 두 값을 가짐. **하나로 통일 필수** |
| 표준공수 산정 | `SH = routing_operation.standard_hours × good_qty`. scrap분 공수는? 후공정 scrap이면 공수는 이미 투입됨 → Phase 1은 good_qty 기준으로 하되 **차이가 EV로 흡수됨을 인지** |
| 잔업할증 | `actual_rate`에 할증 포함 시 RV가 부풀려짐. §14는 자동 OH 분류를 금지 → **RV에 남되, 할증분을 별도 표시** 권장 |
| 간접노무 혼입 | `direct_indirect = INDIRECT`를 DL에 넣으면 이중계상 (GL OH와 중복) |

### 7-6. Overhead Allocation

| 위험 | 대응 |
|---|---|
| 배부율 없이 실제발생액을 제품에 안분 | **금지.** NOT_ALLOCATED |
| 예정배부 시 under/over applied 발생 | Phase 1은 **차이 표시만**, 제품에 재배부하지 않음 |
| 관리 CC(ADMIN) OH 혼입 | `cost_element.is_manufacturing = FALSE` + `cc_type = ADMIN` 이중 필터 |
| 배부기준(DLH)에 INDIRECT 노무시간 포함 | 배부기준은 **DIRECT만** |

### 7-7. GL Reconciliation — **최대 위험 구간**

**위험 a (치명적): GL 재료비 계정의 의미.**
- GL이 **매입액** 기준이면 → `매입 ≠ 소비`. 기초·기말 재고 없이는 절대 대사 불가. `25_inventory_opening` 필수화.
- GL이 **소비 대체분개**(차변 재료비 / 대변 원재료) 기준이면 → MaterialIssue와 직접 대사 가능.

→ **데이터셋을 소비 대체분개 구조로 만들 것을 강력히 권장.** 이 선택이 Phase 1 성립 여부를 좌우합니다.

**위험 b: 노무비 계정 총액.** GL 급여 계정은 직접+간접+사무직 총액입니다. LaborTransaction은 직접노무만 담습니다. 계정을 분리하지 않으면 항상 차이가 납니다.
→ 데이터셋에서 **직접노무비 / 간접노무비 계정을 분리**.

**위험 c: 발생주의 조정.** 미지급비용, 감가상각 등은 GL에만 존재하고 거래 원천이 없습니다. 이런 계정은 OH로 매핑되며 MaterialIssue/Labor와 대사되지 않습니다 — **정상**입니다. Recon 비교 대상을 DM·DL로 한정해야 하는 이유입니다.

**위험 d: 차대 순액.** `net = debit − credit`. 환입 전표를 별도 차감하면 이중 차감됩니다. **순액 계산만 하고 reversal은 식별 표시용**으로만 씁니다.

### 7-8. WIP

기초 WIP가 있으면 기간 원가가 성립하지 않습니다.

**데이터셋 설계 조건 (필수):**
```
2026-07을 시스템 최초 기간으로 설정
기초 WIP = 0
2026-06 데이터는 period 마스터에만 존재(마감), 거래 없음
```
이 조건을 지키면 Phase 1에서 WIP 없이도 Recon이 성립합니다. 조건을 깨면 성립하지 않습니다.

기간 걸친 WO(E-025)는 **집계 제외 + 별도 표시**로 처리하며, 이것을 "차이"로 보고하지 않습니다.

### 7-9. Inventory

`InventoryBalance` 필요 여부 = §7-7(a) 선택에 종속됩니다.

| GL 재료비 정의 | InventoryBalance |
|---|---|
| 소비 대체분개 | **Phase 1 생략 가능** |
| 매입 기준 | **필수** |

권장: 소비 대체분개 → 생략.

### 7-10. Period

| 위험 | 대응 |
|---|---|
| `transaction_date` vs `posting_date` 귀속 불일치 | **GL은 `posting_date` 기준 귀속**으로 고정. 거래일은 참조 정보 |
| 생산·출고·노무는 각각 다른 날짜 필드 | 각 거래는 **자체 일자** 기준 귀속, WO의 period와 다를 수 있음 → 불일치 시 WARNING (ERROR 아님) |
| 마감 기간(is_closed) 전표 | `PERIOD_CLOSED` ERROR |

### 7-11. Account Mapping

| 위험 | 대응 |
|---|---|
| effective 구간 중복 + 동일 priority | `MAPPING_AMBIGUOUS` → REVIEW_REQUIRED. **임의 선택 금지** |
| CC 조건부 매핑 vs 전역 매핑 우선순위 | `priority DESC, cost_center NOT NULL 우선` 고정 |
| `gl_account_name` 사용 유혹 | **표시 전용.** 매핑 근거로 절대 사용 금지 (§0-7) |
| 매핑 버전 추적 | `mapping_version`을 run에 기록. 매핑 변경 후 재계산 시 결과 차이 설명 가능해야 함 |

### 7-12. UOM

| 위험 | 대응 |
|---|---|
| KG↔EA 전역 환산 불가 | `material_code` 지정 환산 필수 |
| 환산 없는 조합 | `REVIEW_REQUIRED`. **1:1 가정 절대 금지** |
| 연쇄 환산(KG→G→MG) 정밀도 | Phase 1은 **1단계 직접 환산만** 지원. 다단계는 미지원 명시 |
| 역방향 환산 자동 생성 | `1/factor` 자동 생성은 허용하되, 반올림 오차 주의. Decimal 나눗셈 정밀도 28자리 유지 |

### 7-13. Work Order Traceability

| 위험 | 대응 |
|---|---|
| `wo_no` NULL 거래 | 제품 추적 단절. 간접비로 분류하고 제품원가에서 제외 |
| BOM/Routing 버전 미기입 | effective date 추론 시 기준일 모호 → **WO에 명시 기입 필수** |
| 한 WO에 복수 제품 | Phase 1 미지원. 1 WO = 1 제품 |
| WO 분할·병합 | Phase 1 미지원 |

---

## 8. 확정 가능 Rule vs 데이터 확인 후 확정

### 8-1. 지금 확정 가능 (데이터 무관)

| # | Rule |
|---|---|
| 1 | 모든 금액·수량은 Decimal. float 금지. SQLite는 TypeDecorator로 차단 |
| 2 | 반올림: `ROUND_HALF_UP`. **중간계산 반올림 금지**, 최종 저장 시점만 |
| 3 | 저장 정밀도: 금액 `DECIMAL(18,4)`, 수량·시간 `DECIMAL(18,6)` |
| 4 | 모든 거래에 `source_file_id` + `source_row` 필수 |
| 5 | 상태 체계: `NORMAL` / `WARNING` / `ERROR` / `CRITICAL` / `UNMAPPED` / `REVIEW_REQUIRED` / `NOT_CALCULABLE` / `NOT_ALLOCATED` |
| 6 | 분모 0 → `NOT_CALCULABLE`. 0% 반환 금지 |
| 7 | FK 미존재 → CRITICAL, 자동 생성 금지 |
| 8 | 음수 검증 (수량·시간·임률) |
| 9 | 파싱 실패 → ValidationError. **자동 보정 금지** |
| 10 | 파일 hash 중복 → 적재 거부 |
| 11 | `gl_account_name` 매핑 사용 금지 |
| 12 | GL 귀속 = `posting_date` |
| 13 | 매핑 우선순위 = `priority DESC, cost_center NOT NULL 우선`, 동순위 → AMBIGUOUS |
| 14 | 예상투입 = `standard_qty × (good + scrap)`, rework 제외 |
| 15 | MaterialIssue 순액 = `Σ ISSUE − Σ RETURN` |
| 16 | `is_manufacturing = FALSE`는 제조원가 집계 제외 |
| 17 | 배부율 없으면 OH `NOT_ALLOCATED` |
| 18 | UOM 환산 불가 → `REVIEW_REQUIRED` |
| 19 | 1 WO = 1 제품 |
| 20 | 헤더 정규화 사전은 명시적 매핑 테이블. 유사도 추정 금지 |

### 8-2. 데이터 확인 후 확정 (지금 정하면 근거 없는 규칙이 됨)

| # | 미확정 항목 | 확정에 필요한 것 |
|---|---|---|
| 1 | tolerance 수치 | 귀사 공차 정책 또는 데이터 분포 |
| 2 | Price/Qty Variance 계산 가능 여부 | `standard_cost_detail` 존재 여부 |
| 3 | OH 배부율 값 | 예산 데이터 |
| 4 | `unit_cost` 산정방식 | 데이터셋 정의 |
| 5 | 잔업할증 포함 여부 | 데이터셋 정의 |
| 6 | 표준임률 출처 (WC vs SC) | 데이터셋 정의 |
| 7 | GL 재료비 계정 의미 (매입/소비) | **데이터셋 정의 — 최우선** |
| 8 | InventoryBalance 필요 여부 | 7번에 종속 |
| 9 | scrap 발생 공정 | 미확보 시 전공정 투입 가정 명시 |
| 10 | Excessive Labor Hours 임계치 | tolerance 정책 |
| 11 | GL Recon 허용차이 | 실무 기준 |
| 12 | 헤더 한국어 표기 실제형 | 실제 Excel 파일 |

**8-2 항목을 확정하지 않은 채 구현하면 §0-15(근거 없는 계산 규칙 생성 금지) 위반입니다.**

---

## 9. 업종 선택 제안

### 권장: 금속 기계가공 부품 (예: 유압 밸브 바디, 감속기 하우징)

| 평가 항목 | 적합도 | 사유 |
|---|---|---|
| BOM 깊이 | ★★★ | 1~2 레벨. Phase 1이 다단계 BOM을 지원하지 않으므로 적합 |
| UOM 다양성 | ★★★ | 원소재 KG 구매 → EA 절단 투입. **자재별 환산 테스트가 자연스럽게 발생** |
| Routing 명확성 | ★★★ | 절단→선삭→밀링→열처리→검사. 공정별 표준공수 산정이 직관적 |
| Scrap 발생 | ★★★ | 절삭칩·치수불량이 자연 발생 → scrap 시나리오에 억지가 없음 |
| 자재 종류 수 | ★★★ | 10~15개면 충분. 데이터 제작 부담 적음 |
| Phase 2 확장 | ★★★ | 방산 부품(정밀가공)으로 자연 확장. 업종 변경 불필요 |

### 비권장

| 업종 | 사유 |
|---|---|
| 전자부품 (PCBA) | BOM 수백 라인. 샘플로 과도. Mix Variance 유혹 발생 |
| 자동차 부품 | 고객 지정 단가·수급 정산 등 Phase 1 외 요소 |
| 복합소재 | Yield Variance가 본질적 → Phase 1 제외 항목과 충돌 |
| 화학·식품 | 연산품(Joint Product) 원가배분 필요 → Phase 1 범위 초과 |

### 권장 데이터 규모

| 대상 | 수량 |
|---|---|
| 제품 | 4개 (P-100 ~ P-400) |
| 자재 | 12개 (RAW 8, SUB 2, CONSUMABLE 2) |
| WorkCenter | 4개 |
| CostCenter | 5개 (PRODUCTION 3, SERVICE 1, ADMIN 1) |
| WorkOrder | 20개 (정상 12, 오류 8) |
| MaterialIssue | 약 60행 |
| LaborTransaction | 약 50행 |
| GLTransaction | 약 40행 |
| 대상 기간 | **2026-07 단일** (기초 WIP = 0) |

---

## 10. 최종 평가 — 이 데이터셋으로 구현 가능한가?

### 10-1. 구현 가능 항목 (본 설계대로 제작 시)

| Phase 1 완료 조건 | 가능 여부 |
|---|---|
| Excel Upload / Header 정규화 / Decimal Parsing | ✅ |
| Row-Level Validation | ✅ |
| Master Validation | ✅ |
| Cost Center / Period / Product / Material | ✅ |
| Account Mapping | ✅ (05 파일 제공 시) |
| BOM / Routing Version | ✅ |
| Work Order / Production Output | ✅ |
| Material Issue / Labor Transaction | ✅ |
| Standard Cost / Actual Cost / Cost Accumulation | ✅ |
| Variance — **Total** | ✅ |
| Variance — **Price/Qty, Rate/Efficiency** | ⚠️ `standard_cost_detail` 제작 시에만 |
| GL Reconciliation | ⚠️ §7-7(a) 소비 대체분개 채택 시에만 |
| Traceability / Source Row | ✅ |
| Calculation Run / Audit Log | ✅ |
| API / pytest / README | ✅ |

### 10-2. 여전히 부족한 데이터 — 추가 필요

| # | 항목 | 없으면 | 조치 |
|---|---|---|---|
| 1 | **tolerance 실제 수치** | 판정 임계치 없음 → 판정 불가 | `14_tolerance_rule` 값을 사용자가 지정 |
| 2 | **GL 재료비 계정 정의 문서** | Recon 원리적 불가 | 데이터셋 README에 1줄 명시 |
| 3 | **`unit_cost` 산정방식** | PV 해석 불가 | 데이터셋 README에 명시 |
| 4 | **표준임률 단일 출처** | RV 이중 기준 | WC 또는 SC 중 택1 |
| 5 | **잔업할증 포함 여부** | RV 왜곡 | README 명시 |
| 6 | **헤더 한국어 실제 표기** | 정규화 사전 작성 불가 | 실제 Excel 확인 필요 |
| 7 | **`91_error_catalog.xlsx`** | 의도 오류/데이터 결함 구분 불가 | 필수 제작 |
| 8 | **데이터셋 README** | 위 2~5의 전제 유실 | 필수 제작 |

### 10-3. 종합 판단

**조건부 가능.** 다음 3가지가 충족되면 Rule Engine을 결정론적으로 구현할 수 있습니다.

1. `05_account_mapping.xlsx` 제공
2. GL을 **소비 대체분개** 구조로 작성 (§7-7a)
3. **기초 WIP = 0** 조건 유지 (§7-8)

이 3가지 중 하나라도 빠지면, GL Reconciliation과 OH 집계는 **구조적으로 성립하지 않으며**, 억지로 구현할 경우 근거 없는 회계처리가 됩니다.

### 10-4. 데이터셋 README 최소 기재 항목

```
1. 업종 / 가상 회사 개요
2. 대상 기간 및 기초 WIP = 0 선언
3. GL 재료비 계정의 의미 (매입 / 소비)
4. MaterialIssue.unit_cost 산정방식
5. 표준임률의 출처
6. 잔업할증 포함 여부
7. scrap 발생 공정 가정
8. 의도 삽입 오류 목록 참조 (91_error_catalog)
9. 90_expected_results는 "가설"이며 정답이 아님을 명시
```

---

## 부록 A. 다음 단계

| 순서 | 작업 | 담당 |
|---|---|---|
| 1 | 본 설계서 검토·확정 | 사용자 |
| 2 | §8-2 미확정 12항목 결정 | 사용자 |
| 3 | 마스터 14개 파일 제작 | 사용자 |
| 4 | 거래 6개 파일 제작 | 사용자 |
| 5 | `91_error_catalog` 작성 | 사용자 |
| 6 | 데이터셋 README 작성 | 사용자 |
| 7 | 데이터셋 무결성 검증 (FK/UOM/Period) | Claude |
| 8 | `90_expected_results` 가설 작성 | 공동 |
| 9 | Data Dictionary 확정 | Claude |
| 10 | DB Model 구현 착수 | Claude |

**7번 이전에는 코드를 작성하지 않습니다.**
