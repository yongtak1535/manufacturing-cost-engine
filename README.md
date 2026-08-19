# Manufacturing Cost Engine

한빛정밀공업 가상 제조기업 데이터셋을 대상으로 하는 원가관리 Rule Engine입니다.

## 현재 구현 범위

### 데이터 적재 및 검증

1. Excel 파일 로딩
2. 멀티시트 source_file / source_sheet_name / source_row 추적
3. 자연키 기반 중복 검증
4. 필수 컬럼 검증
5. Decimal / 날짜 / BOOL 기본 파싱
6. 주요 거래 검증
   - M-04 전표번호 + 행번호 자연키
   - M-09 Material Issue target 조건
   - M-14 WO UOM vs Product UOM
   - M-16 Labor hours 합계
   - M-19 Period key consistency
   - M-08 GL document balance
7. 파일 SHA-256 계산
8. 결정성 검증용 input hash 함수
9. BOM / Routing / Account Mapping / Standard Cost 검증, Actual Cost 집계, OH 배부, Variance, GL 대사

### Contract 단위 원가 (CLI 연결됨)

- Contract 기준 Actual Cost / Standard Budget / Contract Variance
- Contract 단위 직접경비(Direct Expense) 실적 집계
- 계약별 GA(일반관리비) — 계약유형 기반 rate 선택 방식. rate rule 데이터가 없어 현재는 계산 불가(calculable=False)로 표시됩니다.
- Contract Total Cost(Actual) — 위 GA가 계산 불가라 현재는 total_cost도 계산 불가로 표시됩니다.
- Budget Direct Expense — 구조만 준비되어 있고 실제 예산 데이터는 없습니다.

### Regulatory GA 구조 — 구조 구현 완료, 실제 데이터 부족으로 계산 비활성

방산원가 관련 규정에 맞춰, 계약유형이 아닌 업체×공장×연도 기준으로 GA 실적요율/상한율을 조회하고, 관급재료비(GFM)를 사급재료비와 분리해 이중집계 없이 GA 기준액을 구성하는 계산 구조를 준비했습니다.

- 아직 CLI에는 연결되지 않은 준비 단계 코드입니다.
- 실제 GA 요율, 관급/사급 구분(supply_type), 계약 기준일 데이터가 전혀 입력되어 있지 않아 실제 계산은 전부 비활성 상태입니다.
- Budget 쪽 GFM 분리는 미구현입니다(표준원가 데이터에서 관급재료비를 신뢰성 있게 분리할 근거가 없음).
- 제비율 미제출업체·신규업체에 대한 대체 적용(fallback) 규칙도 데이터 부족으로 미구현입니다.

## 다음 구현 순서

- Regulatory GA 활성화에 필요한 실제 데이터(GA 요율, supply_type, 계약 기준일 등) 확보
- Budget GFM 분리 방안 재검토
- Fallback 규칙(미제출업체·신규업체) 적용 여부 재검토
- expected_results 비교
- pytest 전체 시나리오 확장

## 실행

```bash
pip install -e .
python -m manufacturing_cost_engine.cli ./hanbit_mvp_dataset_phase1
pytest
```

`90_expected_results.xlsx`와 `91_error_catalog.xlsx`는 입력 데이터가 아니라 검증 픽스처이므로 로딩 대상에서 제외합니다.
