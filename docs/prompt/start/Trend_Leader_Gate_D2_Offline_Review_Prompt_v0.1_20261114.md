# Trend Leader — Gate D2 오프라인 설계 리뷰 시작 프롬프트 v0.1

이번 채팅은 **Responses Web Search Gate D2 실응답 재관찰 설계 리뷰**입니다. 실행 채팅이 아니며 **유료 API 요청과 코드·GitHub 쓰기는 승인되지 않았습니다.**

## 기준

- 저장소: `Trend-Leader-capstoneProject/feature`
- 작업 브랜치: `feat/responses-web-search-gate-c1`
- 설계 작성 시 확인 HEAD: `3086f366a44fb6032d13ebb4d108fd91a95203c2`
- 최신 HEAD 및 Git worktree는 리뷰 시작 시 재확인.
- 첨부 `Trend_Leader_Gate_D2_Live_Reobservation_Design_v0.1_DRAFT_20261114.md`는 **검토안**이며 FROZEN이 아니다.
- 프로젝트 AI 개발 가이드라인, GitHub Write Safety Policy, S1 Gate A/B Frozen v0.2.2, C1/C2/D0/D1-B.1 실제 코드가 우선 적용된다.

## 문제와 목표

2026-11-14 첫 실제 Responses API 실험에서 `response_status=completed`, `web_search_call=2`, `TOOL_CALL_LIMIT_EXCEEDED`, `candidates=[]`가 관찰되었다. 두 항목 각각의 상태·동작, 처리·청구 횟수는 당시 기록되지 않았다.

D1-B.1은 `web_search_call_details=[{output_index,status,action_type}]` 진단을 구현했고 D1 테스트 `96 passed`는 사용자 실행 보고다.

**목표:** 기존 자료와 공식 문서만으로 재관찰 계획의 필요성·충분성·한계를 검토하고, 추가 유료 요청이 별도 승인될 경우 무엇을 판단할지 검증 가능한 AC와 중단 조건으로 정리한다.

## 필수 검토 관점

1. OpenAI `max_tool_calls`의 처리 상한과 S1/S0의 `web_search_call` 출력 항목 수 제한은 구별되는가?
2. 첫 실험의 관찰값만으로 실제 완료 검색 2회·청구 2회를 주장하지 않는가?
3. `search + open_page`, `search + failed/incomplete`, `search + search`, `find_in_page`만 있는 반례가 Frozen A-04/P-06/X-01/X-06 및 S0 검색 판정과 일치하는가?
4. D1-B.1의 진단값만으로 아직 확인할 수 없는 후보 JSON·인용·비용·원출처 의미를 분리했는가?
5. 실제 실행 없이 확인 가능한 사항을 유료 요청의 성공 조건으로 잘못 두지 않았는가?
6. 단일 요청 시 날짜 구간 변화와 모델 비결정성으로 인해 완전 재현이 불가능하다는 점을 설명했는가?
7. 요청 1회·재시도 0·비게시·API Key 비노출·DB/Writer 차단 및 별도 운영 승인 경계가 유지되는가?
8. 최신 dev와 기능 브랜치 차이를 인지하되 AWS B-2, P4 코드를 변경 범위에 끌어들이지 않는가?

## 금지 사항

- `--execute-live`, `EXECUTE ONE LIVE SEARCH`를 실제 실행하는 행위
- 외부 OpenAI API 접근 및 유료 서비스 사용
- API Key 조회·로그·파일 영속화
- S0/S1/C2/D0/D1 구현 수정, Frozen AC 변경
- DB, Redis, Writer, P4, G5/G6 및 AWS 배포 작업
- 커밋·푸시·PR·병합
- 관찰하지 못한 응답 원문, 두 검색 항목 상태, 실제 청구액을 추측하여 확정

## 최종 결과 형식

- 최신 HEAD와 읽은 소스·버전
- 확인된 사실 / 추론 / 확인 불가능 사항
- 시나리오별 현재 계약과 설계 보완 필요성
- 설계서 v0.1에 대한 Critical/High/Medium/Low 리뷰
- 변경이 필요하다면 정확한 문서 변경안(제안만, 쓰기 금지)
- 별도 실호출 승인 전에 반드시 필요한 확인 사항
- `DESIGN REVIEW PASS / CHANGES REQUESTED / INCONCLUSIVE` 판정

**코드 변경 없이 설계 리뷰 결과만 보고하고 중단해주세요.**
