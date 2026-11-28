# Trend Leader — STEP 9-C 공급 다양성 개선 설계

> 2026-11-28 KST / 9-C-2~5 사용자 동의 / 구현 진행 중 / 기준 dev ca1a0e0, PR #142 3389eb3. 운영 활성화 및 dev 통합 별도 승인.

## 확정 범위
- DEC-01~15 / CLS-01~14: 기존 정확 Catalog 보존, Hybrid Rule-first, 긍정적 주제 유형 및 외부 힌트 일치, 명확한 단일 Root의 적격 후보는 Child 불확실 시 기존 기타 사용. 개인·민감·미확인 주제와 해결되지 않은 Root 충돌 제외. 규칙은 코드 기반의 최소 초기 사전, 실제 공급 증거로 개선. 원문/이미지 부재는 필수 게시 조건이 아님.
- SEL-01~06: IGDB 복수 플랫폼의 적격 후보 GAME/기타, 실제 제외 사유 기반 개선, 기존 IGDB Cursor 및 SearchApi 후보 Cursor, 단건 Batch/중복 SKIP 유지. 동일 Cycle 복수 탐색은 필요 확인 후. IGDB 변경은 별도 구현 및 PR #142의 cover scope와 통합 검증 필요.
- SRC-01~06: 기존 official_search / 링크 파서 활용, 공식 발표 및 개별 콘텐츠 소개 페이지를 선택적으로 검토, Google Search 최대 1회 추가는 별도 운영 승인. D-2 News 운영 HOLD. 구체 적격 원문 확보 전 범용 Reader/운영 배선 추가 없음. 9-B-3에서 승인 원문 og:image 및 공급원 이미지, 기존 fallback 연결.
- 기존 source ID, identity, DB/API, 24h 조회 TTL, Journal, 단일 대표 Child, 6h 전역 cooldown, 기존 운영 기간, AI 0 및 권리 검증 유지. 기존 레코드 자동 수정 금지. V1과 D-2 기존 경로 유지.

## 구현 1차 (검증 대기)
- 신규 SEARCHAPI_KR_INTEREST_HYBRID_V1만 기존 보호 프로필을 통해 활성화 가능. 기본 V1 변경 없음. Collector/Writer 각 Trending 1회, 동일 정책의 catalog/rule fingerprint와 분류 결과, 독립 관측 재구성 비교.
- 관심도 전용 parser는 활성/24h/지원 Root 필터를 20건 상한 전에 적용. 기존 parser 기본값 보존. News token 미필요.
- 순환은 기존 상태 파일의 선택적 interest_last_case_key로 구현. Writer의 확인된 COMMITTED/중복 SKIP만 갱신. 다른 공급원/HOLD에서 보존. 구버전 runtime으로 rollback 시 새 선택 필드 호환 여부 확인 필요(상태 초기화 금지).
- 초기 규칙은 전체 단어/승인된 문맥 위주로 시작. 임의 제품명/작품명은 여전히 누락될 수 있음. 긍정 규칙 기반 실제 표본 평가 및 확대 필요. 사유별 집계는 Adapter 내부 구현; 운영 로그 노출은 후속.
- 추가 외부 요청, 승인 profile 변경, 배포, DB 변경, merge 미실행. 테스트 작성, 실행 증거 미확보. 9-C-6 미완료: IGDB 개선, 진단 연결, 통합 테스트 및 실제 원문 적격성 검토 남음.
