# Trend Leader — 6개 분야 Responses 전시 검색 최소 확장 설계 v0.1

> 작성: 2026-11-16 KST
> 기준: \`feat/responses-live-mvp-20261116\` / HEAD \`9981232339d4e9de549fb31a0c61bc45ca74b76a\` (작성 시점 조회)
> 단계: **Implementation Handoff — 실행 검증 전**. 이 문서 작성으로 신규 코드·라이브 검색·DB 등록이 완료되는 것은 아님.
> 일정: 11/17 최소 구현·Mock 회귀·명시 승인된 실측 1회, 11/18~19 전시
> 별도 기반: Codex 2026-11-16 \`6개 분야 Responses 단발성 검색 및 Windows 실행 메뉴 설계 검토\`

## 1. 범위와 설계 결정

**선택: A안 — 별도 전시 검색 진입점**, 기존 IT_DIGITAL D0/D1/S0/S1 고정 계약 보존.

- 기존 S0 \`SearchRunConfig(profile="IT_DIGITAL")\`, D0 \`GateDConfig\`, D1 진입점 및 기존 ICT 단일 등록 Service/CLI/JSON **의미와 기대 동작을 유지**한다.
- 신규 전시 진입점은 \`FASHION\`, \`BEAUTY\`, \`GAME\`, \`FOOD\`, \`ENTERTAINMENT\`, \`IT_DIGITAL\` 중 **한 분야만 명시적으로 선택**해 **한 번의 요청**을 수행한다.
- 7일(Asia/Seoul), 후보 최대 3건, \`max_tool_calls=1\`, \`max_retries=0\`, \`store=False\`, \`stream=False\` 및 기존 모델·timeout·출력 토큰 상한을 기존 승인 경계에서 유지한다. 도구 항목 관측값은 요청 상한과 혼동하지 않는다.
- \`Responses 후보 발견 → 미승인 JSON 초안 → 사람 최소 검토 → 기존 Daily Dry-run → 별도 승인 등록\`으로 연결한다. **검색 결과를 자동 승인·자동 INSERT하지 않는다.**
- 신규 Scheduler, 운영 Writer, Schema/Migration, 공개 API, TrendCard, AWS/Lightsail 운영 DML 및 G5/G6 변경 없음.
- S0/S1 FROZEN과 Phase 4B-2 보호 등록·철회 FROZEN은 그대로 유지한다. 시연용 별도 CLI의 검토·DB 입력은 그 운영 승인/보호 등록과 구분한다.

## 2. 기존 코드와 충돌하는 계약

1. \`gate_d_preflight.py\`의 \`GateDConfig\`는 기본값과 정확히 동일한 \`profile=IT_DIGITAL\`만 허용한다.
2. \`types.py\`의 \`SearchRunConfig\`도 \`IT_DIGITAL\`만 허용한다.
3. \`d1_live_preview.py\`의 \`_valid_plan()\`은 GateD 계획의 정확한 재생성을 요구한다.
4. \`validator.py\`의 direct-citation 일치가 후보 수용 조건이다. \`manual_review.py\`는 \`CITATION_URL_MISMATCH\` 검토 자료만 제한적으로 추출한다.
5. 현재 Daily \`validate_batch()\`는 \`OPENAI_RESPONSES_WEB_SEARCH_LIVE\`인 후보의 \`original_failure\`를 \`CITATION_URL_MISMATCH\` 또는 \`NOT_VALIDATED\`만 허용하므로 **실제 \`MATCHED\` 상태를 표현할 수 없다**.

금지: 기존 IT_DIGITAL인 척 요청하고 최종 \`parent_code\`만 바꾸기; \`MATCHED\`를 \`NOT_VALIDATED\`로 위장하기; \`CITATION_URL_MISMATCH\`를 PASS로 승격하기.

## 3. 단계별 최소 구현

### P0-A: 새 전시 검색 진입점 — 오프라인/Mock 우선

- 전시 전용 6개 분야 설정, 고정된 범위 문구 및 단일 공통 프롬프트를 신규 \`demo_search.py\`에서 구성한다. 기존 S0/D0 계획을 임의 변경하지 않는다.
- 별도 계획 타입 및 유효성 검사로 분야·시각·요청 설정·미승인 상태를 고정한다. 기존 D1 코드의 **실행 검증·출력 처리만** 공통화하되, SDK transport/adapter/parser/validator 및 D2 호환성·진단·비밀 억제 경계 유지.
- 변경이 필요한 타입 주석은 실제 의존 및 테스트 결과를 확인하고 최소화한다. \`SearchRunConfig\` 기존 유효성 검사를 완화하지 않는다.
- 신규 \`demo_cli.py\`에서 **오프라인 계획/준비 확인이 기본 동작**이다. 유료 전송은 분야 선택 + 명시적 실행 플래그 + TTY + 기존 사람 확인 문구에서만 한 번 수행한다. PowerShell 파이프, 출력 캡처, 자동 확인 입력은 사용하지 않는다.
- 출처의 안전한 URL 형식과 인용 연결 검사를 통과해도 **사람의 원문 검증과 동일하지 않음**. 정상 후보/제한적 mismatch 검토 후보를 구분한다.
- 비용 실패·timeout·429·5xx·후보 부족·중복에서 자동 재호출 없음. 오류의 \`exit code = 0\`을 등록 허가로 쓰지 않는다.

### P0-B: provenance 및 미승인 JSON 초안

- 검색 결과를 하루치 Reviewed 배치 입력에 이어 붙이기 쉬운 JSON 초안으로 내보낸다.
- 초안에는 검토 전임을 명시: \`source_review=NOT_REVIEWED\`, \`operator_approved=false\`, \`approved_record_count=0\`. 따라서 기존 Daily 등록기에 넣으면 의도대로 BLOCKED이다.
- 자동 매핑 가능: 검색 분야→\`parent_code\`, AI 주제 초안→\`title\`, 출처 제목 참고→\`source_title\`, 원래 AI 후보 URL→\`original_ai_source_url\`, \`discovery_method=OPENAI_RESPONSES_WEB_SEARCH_LIVE\`.
- 사람이 확인해야 함: 실제 원출처 URL/\`source_title\`/\`title\`과 핵심 주장, \`child_name\`(자동 선택 안 함), 짧은 \`review_note\`, 개별 \`operator_approved\`, 전체 \`approved_record_count\`.
- 원본 URL과 채택 URL은 별도 보존한다. 모델이 제시한 URL을 자동으로 최종 원출처로 신뢰하지 않는다.
- **후보별 인용 상태**와 **검색 응답 전체 인용 상태**를 혼합하지 않는다. 필드 제안: \`original_citation_validation\`(후보 \`MATCHED|MISMATCH|NOT_EVALUATED\`, 실제 검사 결과에 따라), \`original_failure\`(정상 \`MATCHED\`면 \`null\`, 인용 불일치면 \`CITATION_URL_MISMATCH\`; \`NOT_VALIDATED\`는 실제 미검증 시만), \`search_run_id\`, \`candidate_index\`, \`search_evidence_sha256\`. 정확한 후보 index/해시 근거가 없으면 생성하지 말고 BLOCKED 또는 해당 항목 누락 사유를 표시한다.
- 기존 Daily 입력/영수증의 이전 \`CITATION_URL_MISMATCH\` 및 \`NOT_VALIDATED\` 기록을 호환 유지한다. 정상 \`MATCHED\`는 신규 필드와 \`original_failure=null\`의 조합으로만 허용하고, 원출처 사람 검토가 완료되기 전에는 등록 불가.
- 검색과 입력 초안/영수증은 저장소 밖의 **명시적 로컬 보존 디렉터리**에 저장한다. 모델 응답 전체·API Key·credential·원시 요청/개인정보를 무심코 JSON에 보존하지 않는다.
- 별도 파일명으로 쓰고 기존 파일 덮어쓰기 금지. 요청 전에 대상 경로 및 쓰기 가능 여부를 검사하되, 실제 검색이 실패하거나 결과 저장이 실패해도 **자동 유료 재호출 금지**.

### P0-C: 최소 검증

필수 변경 반례:
1. 6개 분야 각각 계획 성공, 잘못된 분야·변조·오래된 실시간 계획 차단.
2. 비TTY/미승인/확인 문구 불일치 시 외부 호출 0.
3. 유료 전송은 명시적 1회만, timeout/429/5xx/invalid output/후보 없음 시 자동 재호출 0.
4. \`max_tool_calls=1\`, 후보 최대 3, 기존 D2 PARTIAL/거부/모델 일치 검증과 비밀로그 억제.
5. citation \`MATCHED\`/candidate \`MISMATCH\` 구분, 검토 초안은 자동 승인 0.
6. 기존 Daily 입력/영수증 기존 기록 불변 + 정상 MATCHED 새 표현과 실패 사유 보존.
7. 기존 ICT D1, S0/S1, C1/C2, Reviewed Demo 관련 테스트 회귀. 실제 DB DML fixture는 실행하지 않도록 구분.

실제 OpenAI 유료 전송과 새로운 자료 DB INSERT는 각기 **별도 명시 승인** 후 수행한다. 유료 검색의 실제 후보 품질은 Mock 테스트만으로 판정하지 않는다.

## 4. Windows 실행 메뉴 — P1 (검색 경로 안정화 이후)

권장: \`tools/demo_menu.bat\` + \`tools/demo_menu.ps1\`. BAT는 위치 기준으로 PS를 실행하고, PS가 실제 Python CLI를 직접 실행한다.

1. 계획·준비 상태 (오프라인)
2. 분야 선택 및 단발성 Responses 검색 (매번 TTY 확인)
3. 기존 Daily JSON Dry-run (쓰기 0)
4. 별도 승인 후 기존 Daily \`--execute\` 등록 (등록 건수 TTY 확인)
5. 영수증·API 조회 상태 확인 (읽기 전용)

- 무인 API 호출/무인 등록 버튼 금지. 메뉴 실행만으로 유료 요청 또는 INSERT 없음.
- API Key와 DB 비밀번호를 BAT/PS에 넣지 않는다. CLI 인수에는 비밀 원문 대신 저장소 외부 password-file 경로만 사용.
- 경로는 실제 설치된 venv/Worktree를 확인하고 보존 가능한 사용자 설정으로 지정; 임시 폴더 \`CreatorTemp\`를 영구 데이터 보관 위치로 전제하지 않는다.
- 기존 CLI는 TTY를 확인하므로 \`Tee-Object\`, \`Start-Process\`의 입출력 리다이렉션 등으로 확인을 우회하지 않는다.
- 서버가 중지돼 있으면 자동 검색·DB 초기화 대신 별도 재시작 지침을 보여준다.
- 결과 재조회 별도 스크립트는 기존 post-commit verification/SQL SELECT로 목표가 충족되는지 검토하고, 11/17 납기를 막지 않는 경우에만 추가한다.

## 5. 목표 수량 및 완료 의미

- 이미 검증된 ICT 데이터 1건을 보존하면 24건 목표에 신규 23건, 36건 목표에 신규 35건 필요.
- 분야별 후보 상한 3건이 모두 유효하다는 **이론적 낙관치**: 24건까지 추가 호출 최소 11회(다른 5개 분야 각각 2회 + ICT 1회); 36건까지 최소 12회(모든 분야 2회). 실제 호출 수는 실패·중복·검토 탈락으로 증가.
- 단계별 결과를 \`DESIGN\`, \`MOCK_TESTED\`, \`LIVE_REQUEST_VERIFIED\`, \`LOCAL_DB_VERIFIED\`, \`DEVICE_VERIFIED\`로 구분한다.
- \`P0\` 검색과 미승인 Draft 검증이 완료되어야 실제 유료 1회 테스트 진행. 이후 신규 실자료 1건 승인·격리 DB 등록·API/Android 검증을 완료하고 소규모 단위로 수량을 확충한다.

## 6. 실행 전 재확인 및 HOLD

- 원격 최신 HEAD, 로컬 clean Worktree, 현재 설치 버전, GitHub 파일 blob SHA, 관련 확정안의 최신 상태 확인 후 구현.
- 운영 API 접근·예산·모델 권한은 \`--check-readiness\`만으로 확정할 수 없음.
- 신규 \`source_review\`·\`operator_approved\` 값은 사람이 실제 확인 후 변경. 자동 승인 금지.
- 사용자의 개별 유료 실행·실제 DB 등록 승인 전에는 \`--execute-live\`와 \`--execute\` 수행 금지.
- 기존 ICT 단일 경로, S0/S1 FROZEN, G5/G6 HOLD, dev 및 기존 개발·테스트 DB 보호.
