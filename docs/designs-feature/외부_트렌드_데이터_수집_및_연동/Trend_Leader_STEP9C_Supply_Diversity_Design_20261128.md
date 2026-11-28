# Trend Leader — STEP 9-C 공급 다양성 개선 설계

> 2026-11-28 KST / 9-C-2~5 사용자 동의 / 핵심 구현·Windows 변경 영향 검증 완료 / Linux 검증 대기 / 기준 dev ca1a0e0, PR #142 3389eb3. 운영 활성화 및 dev 통합 별도 승인.

## 확정 범위
- DEC-01~15 / CLS-01~14: 기존 정확 Catalog 보존, Hybrid Rule-first, 긍정적 주제 유형 및 외부 힌트 일치, 명확한 단일 Root의 적격 후보는 Child 불확실 시 기존 기타 사용. 개인·민감·미확인 주제와 해결되지 않은 Root 충돌 제외. 규칙은 코드 기반의 최소 초기 사전, 실제 공급 증거로 개선. 원문/이미지 부재는 필수 게시 조건이 아님.
- SEL-01~06: IGDB 복수 플랫폼의 적격 후보 GAME/기타, 실제 제외 사유 기반 개선, 기존 IGDB Cursor 및 SearchApi 후보 Cursor, 단건 Batch/중복 SKIP 유지. 동일 Cycle 복수 탐색은 필요 확인 후. IGDB 복수 플랫폼 변경 구현, PR #142의 cover scope와 통합 검증 필요.
- SRC-01~06: 기존 official_search / 링크 파서 활용, 공식 발표 및 개별 콘텐츠 소개 페이지를 선택적으로 검토, Google Search 최대 1회 추가는 별도 운영 승인. D-2 News 운영 HOLD. 구체 적격 원문 확보 전 범용 Reader/운영 배선 추가 없음. 9-B-3에서 승인 원문 og:image 및 공급원 이미지, 기존 fallback 연결.
- 기존 source ID, identity, DB/API, 24h 조회 TTL, Journal, 단일 대표 Child, 6h 전역 cooldown, 기존 운영 기간, AI 0 및 권리 검증 유지. 기존 레코드 자동 수정 금지. V1과 D-2 기존 경로 유지.

## 구현 및 검증 상태
- 신규 SEARCHAPI_KR_INTEREST_HYBRID_V1만 기존 보호 프로필을 통해 활성화 가능. 기본 V1 변경 없음. Collector/Writer 각 Trending 1회, 동일 정책의 catalog/rule fingerprint와 분류 결과, 독립 관측 재구성 비교.
- 관심도 전용 parser는 활성/24h/지원 Root 필터 후 기존 512,000바이트로 제한된 응답 전체를 탐색한다. 앞쪽 20건의 미분류 후보가 뒤쪽 적격 후보를 가리지 않도록 개선. 기존 V1/D-2 parser 상한 보존. News token 미필요.
- 순환은 기존 상태 파일의 선택적 interest_last_case_key로 구현. Writer의 확인된 COMMITTED/중복 SKIP만 갱신. 다른 공급원/HOLD에서 보존. 구버전 runtime으로 rollback 시 새 선택 필드 호환 여부 확인 필요(상태 초기화 금지).
- 초기 규칙은 전체 단어/승인된 문맥 위주로 시작. 임의 제품명/작품명은 여전히 누락될 수 있음. 긍정 규칙 기반 실제 표본 평가 및 확대 필요. 사유별 집계는 두 Adapter 및 Controller 출력에 연결, 사전 정의 코드/정수만 출력하며 Writer에는 진단 미전달. 명확하지 않은 Root 간 충돌을 기타로 우회하지 않는다.
- 신규 IGDB_VISITS_FACTS_LINK_DIVERSITY_V1 scope: 기존에 확인된 플랫폼의 복수 Child는 GAME/기타, 단일 Child는 유지. 기존 순위·등급·테마·플랫폼 검증, identity 및 3+3 요청 유지. 미확인 테마/플랫폼/GRAC ALL/동률은 실제 제외 사유를 확인한 뒤 필요 변경만 수행. 기존 IGDB-07의 복수 플랫폼 제외는 신규 scope에서만 대체. PR #142 cover scope와 동시 적용은 통합 시 연결 검증.
- 기존 probe_searchapi_kr에 --live --content-topic 옵션 추가. 운영과 독립된 수동 검토용으로 실제 관측된 비민감 작품/제품/서비스 주제를 지정해 Google 검색 1회(공식 발표 대신 공식 페이지까지 탐색), 링크 후보 최대 3개, Trending/Related News 요청 0회, publication_authorization=NONE. 자동 접근·권리·공식성 확인 및 이미지 연결을 의미하지 않는다. 실제 적격 원문 미확보 상태이므로 추가 운영 배선 없음.
- 검증: 1ffedf3의 SearchApi 집중 시험 사용자 보고 45 PASS/21 SKIP (0.62s), Ruff PASS; 로컬 HEAD 및 skip 사유 원문 미보고. 이후 0abfdac IGDB, db121b2 진단/탐색, 6a0cda6 원문 탐색 코드 및 테스트 원격 반영 완료, 실행 결과 미확보. 기존 통과 증거는 이전 코드 기준으로 보존. 변경 영향 pytest/Ruff 및 Linux 특화 SKIP, PR #142 통합 검증만 실시.
- 후속 사용자 보고: 210 PASS / 1 FAIL / 21 SKIP (2.48s), Ruff PASS. SKIP 21건 모두 test_auto_supply_control.py의 Linux durable state/child process 전용 조건. FAIL은 기존 IGDB CLI mock에 미지정 after_case_key=None을 전달한 호출 계약 회귀. 미지정 시 새 인자를 생략하도록 수정하고 Hybrid CLI cursor 유무 2건 추가; 기존 실패 시험 수정 없음. 수정 22341e2 및 사용자 b41aad8(import 정리만, 원격 diff 확인) 후 집중 시험 47 PASS (0.38s), Ruff PASS 사용자 보고. 기존 210 PASS 보존(중복 합산 금지). Windows 변경 영향 검증 완료. Linux 전용 SKIP 21건(durable state 17, child process 4) 별도 검증 대기.
- 신규 외부 호출, 운영 approval/profile 변경, 실제 DB DML, 배포, Timer/state 변경, dev merge 없음. 9-C-6 코드 반영 및 Windows 검증 완료, Linux scheduler 시험 및 PR #142 통합 검증 대기. 9-C-7 실제 공급 검증, 원문 적격성 판단 및 9-C-8 이미지 연계 인수인계 남음.
