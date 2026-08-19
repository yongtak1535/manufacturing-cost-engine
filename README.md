# Manufacturing Cost Engine — Phase 1

한빛정밀공업 가상 제조기업 데이터셋을 대상으로 하는 원가관리 Rule Engine의 초기 구현입니다.

## 현재 구현 범위

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

## 다음 구현 순서

- BOM / Routing validation
- Account Mapping
- Standard Cost validation
- Actual Cost accumulation
- Overhead allocation
- Variance
- GL reconciliation
- expected_results 비교
- pytest 전체 시나리오 확장

## 실행

```bash
pip install -e .
python -m manufacturing_cost_engine.cli ./hanbit_mvp_dataset_phase1
pytest
```

`90_expected_results.xlsx`와 `91_error_catalog.xlsx`는 입력 데이터가 아니라 검증 픽스처이므로 로딩 대상에서 제외합니다.
