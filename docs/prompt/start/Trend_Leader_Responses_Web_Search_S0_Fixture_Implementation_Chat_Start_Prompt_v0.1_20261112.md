# Trend Leader — Responses API `web_search` S0 Fixture-only 구현 채팅 시작 프롬프트 v0.1

> 상태: 새 구현 채팅에 붙여 넣는 시작 프롬프트. **S0만 적용**. 설계 문서 원격 기록은 S0 코드 구현·게시·유료 요청 승인과 별개.

이번 채팅은 **Trend Leader의 `OpenAI Responses API web_search` 기반 실데이터 후보 발굴 PoC 중 `S0 — Fixture-only 구현`**을 위한 전용 채팅입니다.

## 1. 기준과 우선순위

1. 현재 채팅의 명시적 결정과 관련 기능별 FROZEN 문서가 우선입니다.
2. 다음 원격 설계 문서들을 반드시 읽고 기준으로 삼아 주세요. 문서가 `FINAL REVIEW / NOT FROZEN`이면 해당 상태를 바꾸거나 설계 전체가 동결되었다고 가정하지 마세요.
   - `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_Responses_Web_Search_Minimal_Implementation_Contract_Final_Review_v0.1_DRAFT_20261112.md`
   - `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_Real_Data_Source_Selection_Final_Review_v0.1_DRAFT_20261112.md`
   - `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_Real_Data_API_Pipeline_Design_First_Pass_v0.1_DRAFT_20261112.md`
3. `docs/prompt/Trend_Leader_AI_Development_Guidelines.md`와 `docs/prompt/Trend_Leader_GitHub_Write_Safety_Policy.md`, 기존 P0~P3 RSS·Phase 4A/4B-1/4B-2 FROZEN, G0~G6 정책을 유지합니다. **G5/G6 HOLD**, P4 `NOT FROZEN` 유지.
4. 구현 착수 시 `dev`와 이 설계 문서가 있는 브랜치의 최신 HEAD, 관련 코드·테스트·의존성, 로컬 working tree를 실제로 확인하세요. **Phase4B2 기능 브랜치에 S0 코드를 무조건 섞지 말고**, 새 S0 기능 브랜치의 기준 및 문서 반영 경로를 우선 제안하세요. 사용자가 작업 중인 변경은 보존합니다.

## 2. 이번 작업의 목표

- 비용 0원의 합성 Fixtures로 **검색 실행 증거 → 후보 파싱 → URL/출처/중복 검증 → 검토용 Preview 생성**을 검증 가능한 작은 Backend 코드로 구현합니다.
- 최초 프로필은 `IT_DIGITAL`, 최근 7일 검색 의도, 후보 최대 3개입니다. 실제 급상승 순위나 인기도를 생성하거나 증명했다고 표기하지 않습니다.
- 실제 응답에 대한 구조적 가정은 공식 문서 및 프로젝트에 고정한 SDK 버전으로 검증할 수 있는 부분에만 적용합니다. SDK나 특정 응답 필드를 임의로 만들어내지 마세요.
- 출력의 모든 후보는 `REVIEW_REQUIRED`, `NOT_FOR_PUBLICATION`, `publish_authorization=NONE`입니다. 사람의 원 출처 확인과 G4/A1/4A/4B-2/P4 인계는 **미구현**입니다.

## 3. 포함 / 제외 범위

**S0 포함:**
- 현재 프로젝트 코드 구조와 책임 경계 리뷰
- 작고 명시적인 검색 설정값/후보·Preview 타입의 계약 정리
- Mock/Fixture 기반 Adapter 입력·파싱·검증·Preview 변환
- 검색하지 않은 응답, 출처 없는 후보, 잘못된 URL, 중복, 미완료/거절, 빈 결과, 오류 응답 등의 테스트
- 테스트 실행 결과와 변경 diff 리뷰, 테스트 실패의 원인 분석

**S0 제외:**
- 실제 Responses API 호출, 실제 `web_search`, API Key 사용, 과금, 외부 HTTP 요청 및 자동 재시도
- MariaDB/Redis/파일 영속화 또는 서비스 DB DML, Seed, 기존 `/api/trends*` 수정, Frontend 변경
- Google Trends RSS 호출, NAVER 내부 데이터의 모델 입력, 원문 스크래핑, 관리자 API/스케줄러/게시 Writer
- G4 승인, A1/4B-2 보호 등록, P4 Writer 연결, G5/G6 승인, 신규 정책 또는 FROZEN 계약 수정

## 4. 진행 방법

1. 먼저 **현재 코드·문서 정합성 조사**를 수행하고 설계 문서의 미동결 사항 중 S0 테스트에 영향을 주는 부분을 구분해 보고하세요.
2. 테스트로 관찰 가능한 **S0-only 최소 계약과 책임 분리**를 제시하세요. 기존 `backend/app/external_trends/`의 RSS 전용 타입/코드를 무리하게 재사용하거나 FROZEN 계약을 변경하지 마세요.
3. 의미 있는 설계 대안이 있으면 최소 두 가지를 비교하고, **작은 변경·명시적 의존성·유지보수성**을 기준으로 권고하세요.
4. 설계 충돌 또는 구현을 막는 미확정 사실이 있다면 먼저 보고하세요. 별도 결정이 필요한 사항을 추측으로 채우지 마세요.
5. 구현은 사용자 승인과 범위 확정 후에만 시작하고, 테스트를 먼저 작성한 뒤 작은 단위로 수정·검증하세요. **S0 테스트는 실제 API/웹/DB 호출이 0임을 검증**해야 합니다.
6. GitHub에 코드/테스트를 쓰기 전에는 대상 브랜치·변경 파일·diff·충돌 여부를 보고하고 쓰기 안전 정책을 준수하세요. 이 시작 프롬프트 자체는 원격 코드 작성이나 커밋/푸시를 승인하지 않습니다.

## 5. 완료 기준과 보고 형식

- S0 테스트에서 정상·오류 응답 분기, 검색 미실행, 출처/URL/중복, 0건, refusal/incomplete 등 핵심 Acceptance Criteria를 관찰할 수 있어야 합니다.
- OpenAI 실제 호출 0회, 외부 네트워크 호출 0회, DB DML 0회, 모바일 앱 변경 0건을 확인합니다.
- 테스트 명령은 **Windows PowerShell** 기준으로 제시합니다.
- 보고서에는 **실제 실행한 테스트만 PASS**, 미실행은 미검증으로 표시합니다.
- 마지막에 변경 파일, 코드 책임 경계, 검증 증거, 잔여 위험, S1 별도 승인 Gate를 구분해 정리합니다.

**이번 채팅은 S0에만 집중해 주세요.** 유료 Responses API 사용 모델·검색 프롬프트·비용·응답 라이선스·실제 연결 검증은 별도 `S1 Responses API 실제 호출 설계` 채팅에서 다룹니다.
