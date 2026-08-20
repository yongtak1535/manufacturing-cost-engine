# Phase 1 Validation Baseline

> 이 문서는 Phase 1 데이터셋/검증 로직에 대한 조사가 끝난 시점의 상태를 "검증 완료 기준선"으로
> 고정하기 위한 것이다. 목적은 32/32를 만드는 것이 아니라, 왜 25/32가 현재 증거로 정당화되는
> 결과인지 기록해서 이후 작업자가 같은 조사를 반복하지 않도록 하는 것이다.

## 1. Baseline commit

- commit: `c80bd3e`
- branch: `main`
- origin/main: `c80bd3e`
- pytest: 377 passed
- CLI exit: 0
- validation issues: 64
- expected result match: 25/32

## 2. Intentional dataset corrections already applied

### 23_labor_transaction.xlsx
- `LB-2607-045`
- `actual_hours`: `-1` → `-1.5`
- reason: `actual_hours = regular_hours + overtime_hours`
- `regular_hours = 0.5`
- `overtime_hours = -2`
- 주의: 원본 저자의 실제 원래 값이라는 근거가 아니라 설계 조건을 만족시키기 위한 정정값이다.

### 24_gl_transaction.xlsx
- `GL-260731-021` line 2
- `posting_date`: `2026-07-31` → `2026-06-01`
- reason: E-014의 "2026-06 closed period" 조건 충족
- 주의: 정확한 day는 설계 문서에 없으므로 원본 복원값이라고 주장하지 않는다.

### 30_contract.xlsx
- 3개 contract의 `plant_code`: `NULL` → `PL01`
- 근거:
  - `20_work_order.xlsx`의 `plant_code`가 20건 전부 `PL01`
  - `01_company_plant.xlsx`(company plant master)에 `PL01` 하나만 존재
- 이 값은 구조적으로 유도 가능한 값이다.

## 3. Seven unresolved expected mismatches

### E-002
- expected: `BOM_UNDER_ISSUE` = 1
- actual: 0
- classification: E
- reason:
  - `WO-2607-010`/`MAT-002`가 설계 대상이라는 것은 확정
  - `expected_qty = 14`
  - actual `issued_qty = 14`
  - `tolerance = 0.28`
  - 정확한 수정 `issued_qty`는 문서/Git history에서 결정되지 않음
- action: no modification

### E-003
- expected: `NOT_IN_BOM` = 1
- actual: 3
- classification: D
- reason:
  - design.md/build_spec.md에 모델 A/B 충돌
  - 모델 A: WO 연결 BOM 미등재
  - 모델 B: `wo_no NULL` + `cost_center_code` 간접자재
  - 정확한 원본 모델 결정 불가
- action: no modification

### E-011
- expected: `AMOUNT_MISMATCH` = 1
- actual: 0
- classification: E
- reason:
  - `amount` 컬럼은 설계 문서에는 필수지만 실제 Excel에는 최초 커밋부터 존재하지 않음
  - 과거 Git history에도 존재한 적 없음
  - 생성 스크립트도 없음
  - 어느 행이 오류 대상인지 특정 불가
- action: no modification

### E-016
- expected: `UOM_CONVERSION_MISSING` = 1
- actual: 14
- classification: E
- reason:
  - 설계상 MAT-004 EA→KG 미등록 시나리오는 존재
  - 그러나 P-900/BOM-P900-A를 사용하는 WO가 없음
  - 현재 14건은 MAT-009/MAT-010의 별도 데이터 갭
  - 정확한 P-900 WO와 issue 행 값을 결정할 근거 없음
- action: no modification

### E-018
- expected: `MISSING_MATERIAL_ISSUE` = 1
- actual: 13
- classification: E
- reason:
  - `WO-012`/`MAT-007` 1건은 설계와 정확히 일치
  - 나머지 12건은 WO-020 및 WO-017/018/019에서 발생
  - material_issue를 생성/삭제해야 한다는 명시적 근거 없음
- action: no modification

### E-024
- expected: `OVERHEAD_NOT_ALLOCATED` = 1
- actual: 0
- classification: E
- reason:
  - CC-300 overhead rate 없음은 설계상 확정
  - 하지만 WC-50 labor transaction 자체가 없음
  - 누락 행의 WO/hours/rate를 유일하게 결정할 근거 없음
- action: no modification

### E-027
- expected: `GL_RECON_DIFFERENCE` = 1
- actual: 2
- classification: C
- reason:
  - error catalog의 E-027 row 범위가 OH 계정 `53100`을 가리킴
  - `validate_gl_reconciliation()`은 DM/DL만 대상으로 함
  - validation 범위를 OH까지 변경해서는 안 됨
- action: no modification

## 4. Why 25/32 is the correct current baseline

25/32는 테스트 실패를 숨긴 결과가 아니다. 7개 불일치에 대해 코드 버그 여부와 원본 데이터 복원
가능성을 조사한 결과, 코드 버그는 확인되지 않았고 정확한 원본 복원값을 유일하게 결정할 수 있는
근거도 발견되지 않았다. 따라서 임의의 데이터 조작으로 32/32를 만드는 것보다 25/32를 유지하는
것이 현재 증거에 기반한 올바른 기준선이다.

## 5. What would be required to resolve the seven mismatches

- **E-002**: 원본 dataset generator 또는 원저자 지정 `issued_qty`
- **E-003**: 설계 원저자의 모델 A/B 선택 결정, 간접자재 스키마 및 validation 의도 확인
- **E-011**: `amount` 컬럼이 실제 생성됐던 원본 dataset 또는 생성 규칙, 오류 대상 행 및 amount 원본값
- **E-016**: P-900용 실제 WO 원본, MAT-004 EA→KG conversion 원본
- **E-018**: WO-020의 원래 BOM 의도, WO-017/018/019 material issue 생성 여부에 대한 원본 규칙
- **E-024**: WC-50 labor transaction 원본 1건 이상, 정확한 WO/operation/hours/rate
- **E-027**: error catalog 원저자가 의도한 DM/DL 대상 row 범위

## 6. Prohibited actions

다음은 명시적으로 금지한다:

- expected count를 맞추기 위한 임의 수량 변경
- 임의 WO 생성
- 임의 labor transaction 생성
- amount 컬럼 임의 생성
- 임의 UOM conversion 생성
- BOM version을 임의로 변경하여 MISSING_MATERIAL_ISSUE 제거
- OH까지 GL reconciliation 범위를 확장
- validation 로직을 expected fixture에 맞춰 변경
