# Responses 전시 검색 pending open_page 최소 호환 패치 v0.1

- 기준일: 2026-11-17 KST
- 패치 기준: `feat/responses-live-mvp-20261116` / `9735bf4d238058756b20e67740f76f39dbcd74b0`
- 범위: **전시용 6개 분야 Preview에 한정**. 기존 S0/S1/D0/D1 및 승인된 D2 전역 해석은 변경하지 않는다.
- 현재 상태: **원격 패치 작성됨, 회귀 테스트 실행 및 실제 유료 재검색 미검증**. 배포 승인 아님.

## 발견된 실패

실제 FOOD 단일 Responses 요청은 `max_tool_calls=1`로 직렬화되었으나, 반환된 output에
`web_search_call(search, completed)`와 `web_search_call(open_page, searching)` 두 항목이 포함됐다.
기존 D2 호환기는 두 항목 모두 `search`인 경우만 제한적으로 인정해 `TOOL_CALL_LIMIT_EXCEEDED`로 거부했다.

OpenAI API 문서상 `open_page`는 정상 웹 검색 action 종류이지만, 이 로그는 두 번째 도구 작업의 완료나 청구 가능 횟수를 증명하지 않는다.

## 최소 정책 선택

1. 서버 요청 상한 `max_tool_calls=1`, 재시도 0회, store/stream false, 기존 모델/토큰 상한은 변경하지 않는다.
2. **전시용 진입점에서만** 기존 D2 제한적 파서에 opt-in `allow_pending_open_page=True`를 전달한다.
3. 예외적으로 허용할 2개 도구 항목의 순서와 상태는 정확히
   `[(search, completed), (open_page, searching)]`로 제한한다.
4. 기존 `[(search, completed), (search, searching)]` 호환은 유지한다.
5. `open_page(completed)`, `open_page(failed)`, `find_in_page`, 역순, 3개 이상 도구, 미완료 전체 응답, 거부 메시지, malformed JSON, 상한 초과 본문은 기존처럼 거부한다.
6. 한정 허용도 `response_validation=PARTIAL`로 유지한다. 원출처에 대한 인용 검증은 별도로 수행하며, annotation 없는 후보는 `CITATION_URL_MISMATCH`로 **수동 검토 전용**으로 보존한다.
7. 사람 원문 검토, provenance, 검토 승인, 격리 DB Dry-run/개별 INSERT 승인, G5/G6 HOLD는 변경하지 않는다.

## 변경 파일

- `app/responses_web_search/live_compatibility.py`: 기본 false인 조건부 한정 허용
- `app/responses_web_search/d1_live_preview.py`: 전시용 provenance 진입점에서만 opt-in
- `tests/responses_web_search_c2/test_demo_search.py`: 정상/역순/실패/완료/찾기/세 번째 도구, citation mismatch, 기존 D2 차단 테스트

## 테스트 및 운영 Gate

- 필수 회귀: `backend/tests/responses_web_search_c2` 전체와 `backend/tests/responses_web_search_s1`, 기존 D1/D2 테스트, Reviewed Demo
- 합성 MockTransport에서 실제 요청 1회·안전 진단·비밀정보 미노출·원본 응답 불변 확인
- 다음 실제 유료 검색은 위 회귀 PASS **이후** 별도 명시 승인 하에 한 분야 1회만 수행하며 자동 재시도 금지
- 기존 FOOD 실패 JSON은 수정·재해석하지 않음. 해당 원본에는 후보가 보존되지 않았으므로 패치만으로 사후 복원 불가
- GitHub 별도 패치 브랜치에만 반영. `dev`/Lightsail/운영 DB 변경, Migration, 자동 INSERT/Publish, APK 변경 없음
