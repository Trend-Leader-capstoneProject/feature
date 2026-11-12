# Responses Web Search S0 최소 계약 v0.1

> 기준일: 2026-11-12 KST
> 상태: 사용자 승인에 따른 **S0 Phase 1 테스트 명세 / Red Phase**.
> 상위 Final Review 전체의 FROZEN 선언이 아니다. Green 구현은 별도 승인 전 미착수.
> 범위: 합성 입력 → 모의 검색 흔적 판별 → 후보 파싱·문자열 검증 → 메모리 Preview.
> 실제 검색·출처 확인·DB 접근·파일 영속화·게시 권한은 제공하지 않는다.
>
> **Phase 2 추가 승인:** 아래 Phase 1 상태·승인 경계는 당시 기록으로 보존한다.
> 후속 사용자 승인에 따라 S0 로컬 Green 구현·검증까지 진행했으며 현재 결과는 §8과 Phase 2 보고서에 기록한다.

## 1. 기준과 문서 반영 경로

- 작업 브랜치: `feat/responses-web-search-s0-fixtures`.
- 시작점: 작업 직전 원격 조회로 확인한 `dev` 및 로컬 `origin/dev`의
  `5508b78b34658125ba3571662748d3a81e07bf52`.
- 앞선 조사 당시 원격 dev는 `b133b49…`였으나 이번 조회에서는 달라졌다.
  로컬 dev에서 추정 분기하지 않고 `git switch -c ... origin/dev`로 생성했다.
- 최신 dev에는 Phase4B2 코드가 이미 포함돼 있다. S0 작업에서 Phase4B2를
  merge/cherry-pick하거나 해당 코드를 호출·수정하지 않는다.
- 아래 세 문서는 기준 커밋에 이미 존재한다. 추가 복사/덮어쓰기 없이 working tree의
  blob SHA를 기준 커밋과 대조했다. 문서 상태를 변경하지 않는다.

기준 커밋: `5508b78b34658125ba3571662748d3a81e07bf52`.
경로는 이 문서와 같은 디렉터리 기준이다.

| 문서 | blob SHA | 유지 상태 |
|---|---|---|
| `Trend_Leader_Responses_Web_Search_Minimal_Implementation_Contract_Final_Review_v0.1_DRAFT_20261112.md` | `18de959fa7dda766ac489fd1ddafee0226690432` | FINAL REVIEW / NOT FROZEN |
| `Trend_Leader_Real_Data_Source_Selection_Final_Review_v0.1_DRAFT_20261112.md` | `a301b231c6c6cf51ea832f6a866decc9c3f7c497` | FINAL REVIEW / NOT FROZEN |
| `Trend_Leader_Real_Data_API_Pipeline_Design_First_Pass_v0.1_DRAFT_20261112.md` | `24105ea98d93839a69a39517e45bad3d64442f50` | DRAFT / NOT FROZEN |

## 2. 책임 분리와 내부 진입점

아래 명칭은 프로젝트의 로컬 테스트 계약이며 OpenAI SDK 타입·메서드가 아니다.

| 책임 | Green 단계의 예상 배치 | 입력 → 출력 |
|---|---|---|
| 설정 | `app/responses_web_search/types.py` | 명시 설정 → 검증된 `SearchRunConfig` |
| 합성 Adapter | 같은 패키지의 `fixture_adapter.py` | 합성 dictionary 또는 오류 종류 → 합성 결과 |
| Parser | 같은 패키지의 `parser.py` | 비신뢰 dictionary → 로컬 후보·인용·모의 검색 정보 |
| Validator | 같은 패키지의 `validator.py` | 후보·인용 → 남길 후보와 후보별 진단 |
| 조정·Preview | 같은 패키지의 `service.py` | 설정·Adapter → JSON 호환 dictionary |

배치는 구현 계획이며 Phase 1에서는 위 제품 파일을 생성하지 않는다.
독립 패키지 진입점 `app.responses_web_search`에서 다음 세 이름을 공개할 예정이다.

```python
SearchRunConfig(
    profile="IT_DIGITAL", lookback_days=7,
    max_candidates=3, max_tool_calls=1,
    fixture_reference_at_utc=None,
)
FixtureAdapter(response=synthetic_response)  # 또는 error_kind="429"
run_preview(*, config, adapter)  # JSON 호환 dictionary 반환
```

`SearchRunConfig`는 IT_DIGITAL, 7일 의도, 정수 후보 상한 1~3, 모의 tool 상한 1만 허용한다.
bool을 정수 상한으로 허용하지 않는다. 잘못된 설정은 `ValueError`다.
시각은 선택적으로 주입하는 고정 UTC Fixture 기준시각뿐이며 현재시각 취득은 필요 없다.
모델·키·전송 대상·비용·실제 요청 설정은 갖지 않는다.

Adapter는 메모리 입력만 반환한다. `run_preview`는 해당 입력을 한 번만 읽는다.
`adapter.calls`는 읽기 횟수이며 실제 API 요청 횟수가 아니다.
합성 오류 종류는 `401`, `403`, `429`, `5xx`, `timeout`이다. 재읽기·재시도는 없다.
SDK 예외나 HTTP 응답 객체를 임의로 만들어내지 않는다.

## 3. Fixture와 실제 응답의 검증 수준

- `fixtures.py`는 독립 작성한 합성 dictionary이며 실제 응답을 기록한 자료가 아니다.
- [공식 Web search 가이드](https://developers.openai.com/api/docs/guides/tools-web-search)에서
  확인한 `web_search_call`, `message.content`의 `output_text`, `url_citation`의
  제한된 형태를 사용한다.
- 완전한 Responses 명세, 특정 SDK 역직렬화, 모델 조합, Structured Outputs 지원,
  실제 응답에서 annotation offset이 갖는 의미는 미검증이다.
- Backend 의존성 정의와 가상환경에 openai SDK가 없다. S0에서는 추가하지 않는다.
- `output_text.text` 안의 `{"candidates": [...]}`는 **자체 후보 JSON 계약**이다.
  OpenAI가 이 JSON을 자동 제공한다는 가정이 아니다. 실제 생성 가능성은 S1 사항이다.
- S0는 단일 assistant message·단일 output_text를 다루는 제한된 프로필이다.
  여러 text block이나 알 수 없는 content는 부정 응답으로 처리해 후보 0건을 반환한다.
  실제 응답의 모든 형태와 호환된다고 주장하지 않는다.
- `action.sources`는 부가 메타데이터이며 후보와 인용의 연결을 대체하지 않는다.

## 4. 입력·출력과 안전 상태

후보 입력의 필수 값은 공백뿐이지 않은 문자열인
`topic_draft`, `source_url`, `source_title_reference`다.
`source_title_reference`는 합성 검토 자료이며 공개용 원제목이 아니다.
임의 추가 키에서 권한·시각·분류·인기도를 복사하지 않는다.

Preview의 필수 공통 값은 다음과 같다.

| 필드 | 값·의미 |
|---|---|
| `status` | 다음 절의 처리 결과이며 승인 상태와 별개 |
| `mode` | `FIXTURE_ONLY` |
| `review_status` | 항상 `REVIEW_REQUIRED` |
| `publication_status` | 항상 `NOT_FOR_PUBLICATION` |
| `publish_authorization` | 항상 `NONE` |
| `independent_source_verified` | 항상 false |
| `searched_at_utc` | 항상 null. 모의 검색을 실제 검색으로 표시하지 않음 |
| `fixture_reference_at_utc` | 설정한 고정 UTC 시각의 isoformat, 미설정은 null |
| `lookback_days` | 7. 검색 의도이며 최신성 검증 결과가 아님 |
| `simulated_web_search_executed` | 합성의 완료 search action을 인식했는지 여부 |
| `tool_calls_observed` | 입력의 web_search_call 수이며 실제 사용량이 아님 |
| `candidates` | 검토용 후보 list |
| `reason_codes` | 응답 전체 진단 코드 list |
| `issues` | 0부터 시작하는 `candidate_index`와 `code`의 list |

남긴 각 후보에도 `review_status`, `publication_status`, `publish_authorization`,
`independent_source_verified`를 위와 동일하게 고정한다.
후보는 검증된 문자열인 필수 값 3개와 `source_published_at=null`,
`proposed_category_ref="IT_DIGITAL"`을 가진다. Child Category의 DB 확인·확정이 아니다.
`observed_at`, `collected_at`, `rank`, `popularity_score`는 출력하지 않는다.
Preview는 로컬 등록 원장·A1 스냅샷·운영 Evidence가 아니다.
입력을 변경하지 않는다. 원 응답·refusal·예외 메시지를 진단에 전재하지 않는다.

## 5. 판정 순서와 실패 사유

1. 설정 검증 후 Adapter를 1회만 읽는다. 합성 오류는 `UPSTREAM_ERROR`,
   `reason_codes=[error_kind]`, 후보 0건이다.
2. 응답/출력 구조, 완료 상태, 전체 content의 refusal, 모의 tool 상한을 확인한다.
   부정·미완료·refusal은 `INVALID_OR_INCOMPLETE_RESPONSE`, 후보 0건이다.
   tool 초과는 `TOOL_CALL_LIMIT_EXCEEDED`를 전체 사유에 포함한다.
3. 완료 `web_search_call`의 `action.type="search"`가 없으면
   `SEARCH_NOT_EXECUTED`다. open_page나 모델 본문만으로 성공하지 않는다.
4. 자체 JSON을 파싱한다. object → candidates list → 각 object 구조를 요구한다.
   구조 오류·후보 상한 초과는 전체 실패다. 상한 초과는
   `CANDIDATE_LIMIT_EXCEEDED`를 포함한다. 말없이 3건으로 자르지 않는다.
5. 정상 빈 배열은 `EMPTY_RESULT`다. 검색 의도의 모의 결과가 0건인 경우다.
6. 개별 후보는 필수 필드 → URL → 동일 응답 내 인용 → 중복 순으로 검사한다.
   부정 후보는 제외하고 사유를 남긴다. 유효한 다른 후보를 함께 버리지 않는다.
7. 남은 후보가 있으면 `PREVIEW_READY`, 전부 탈락하면 `NO_VALID_CANDIDATES`다.
   전부 탈락한 결과와 정상 빈 배열을 구분한다.

| 개별 사유 | 조건 |
|---|---|
| `CANDIDATE_FIELDS_INVALID` | 필수 키 누락, 문자열 아님, 공백뿐인 값 |
| `SOURCE_URL_INVALID` | URL 문자열 검사 실패 |
| `CITATION_URL_MISMATCH` | 동일 응답에 후보 URL과 일치하는 url_citation이 없음 |
| `DUPLICATE_CANDIDATE` | 앞서 남긴 후보와 정규화 URL 또는 정규화 주제가 같음 |

URL은 절대 HTTP(S)만 허용한다. userinfo, 제어문자·공백·backslash, IP/localhost,
모호한 숫자 host, percent host, 끝 점, 빈 port, 기본값이 아닌 port를 제외한다.
인용 연결은 입력 URL 문자열의 일치이며 본문 내용·인용 위치의 진위를 증명하지 않는다.
중복 판정은 scheme/host 소문자화·기본 port 제거·fragment 제거 후 URL과,
NFC·공백 압축·ASCII 소문자화한 주제로 한다. path/query는 유지한다.
먼저 검증을 통과한 후보를 남긴다. 의미가 비슷한 사건의 동일성은 판정하지 않는다.
DNS·HTTP 도달성·redirect·권리·최신성은 검증하지 않는다.

## 6. 테스트 수용 기준과 실행 격리

대상은 `backend/tests/responses_web_search/`다. 제품 import를 각 테스트 실행 시점에
수행하여 제품 미구현에 따른 Red가 테스트 수집 전체를 중단하지 않게 한다.

| 수용 대상 | 관찰할 결과 |
|---|---|
| 정상 1~3건, 입력 불변 | PREVIEW_READY, 모든 후보의 비공개·미승인 고정값 |
| 설정 오류 | ValueError, bool 상한 거부 |
| 검색 없음/open_page만 존재 | SEARCH_NOT_EXECUTED |
| refusal/각 계층 incomplete/부정 구조 | 전체 실패, 후보 0건, 민감 원문 진단 전재 없음 |
| 모의 tool 상한·후보 상한 | 사유 명시, 후보 0건 |
| 인용 없음/불일치/sources만 존재 | 후보 제외와 사유 |
| 잘못된 URL/필수 항목 누락/혼재 | 개별 제외, 유지 가능한 후보 보존 |
| URL 또는 주제 중복 | 첫 유효 후보만 유지 |
| 빈 배열/전부 제외 | EMPTY_RESULT / NO_VALID_CANDIDATES |
| 합성 401/403/429/5xx/timeout | UPSTREAM_ERROR, Adapter 1회, 재시도 없음 |
| 권한·시각·인기도 추가 키 | 신뢰 경계를 넘어 출력에 승격하지 않음 |
| 테스트 격리 | 상위 conftest와 dotenv/DB/SDK 등을 로딩하지 않음 |

실행 시 `--confcutdir`, plugin 자동 로딩 금지, cacheprovider 금지, bytecode 금지를 적용한다.
수집 전부터 금지 import를 차단하고 각 제품 테스트의 import 전부터 socket/DNS,
하위 프로세스, 일반적인 파일 쓰기를 차단한다. 차단 예외를 제품이 무시하더라도
teardown에서 실패한다. 차단 장치 자체 테스트는 의도한 차단 probe를 별도로 센다.
이는 실제 통신·실제 파일 쓰기가 아니다.
`.env*` 파일 읽기와 OPENAI/DATABASE/TEST_DATABASE 접두사의 환경변수 값 조회도
원래 읽기 함수에 도달하기 전에 차단한다. 키 조회 차단 자체 테스트는 실제 값을 읽지 않는다.

가드는 Python의 일반 호출 경로 대상이며 OS sandbox나 악의적 native code까지
완전히 차단한다는 증명이 아니다. 제품 미구현 Red 단계에서는 향후 제품 동작이 미검증이다.

## 7. 유지할 경계와 S1 유보 사항

- RSS P0~P3 v1.1, Phase4A/4B-1/4B-2 FROZEN을 변경하지 않는다.
- G0~G6 승인을 대행하지 않는다. G5/G6 HOLD, P4 전체 NOT FROZEN을 유지한다.
- G4/A1/4A/4B-1/4B-2/P4 자동 연결이 없다.
- FastAPI Router, ORM, Schema, 기존 RSS 코드, Frontend, Seed 변경이 없다.
- DB session·DML, Redis, 파일 영속화, HTTP, SDK, API Key 사용·조회, 재시도가 없다.
- S1 별도 승인: SDK/HTTP 방식·고정 버전, 모델, 검색 prompt, 실제 응답 형식과 정합성,
  요금·사용량·권리, 키 환경, timeout, 실제 tool/요청 상한, 실제 연결 검증.
- S2 원출처 사람 확인과 이후 승인·게시는 S0 완료와 독립적이다.
- 이번 승인은 Phase 1 문서·Red 테스트까지다. Green, commit, push, PR,
  원격 쓰기, 실제 API 실행은 시작하지 않는다.

## 8. Phase 2 보완 및 로컬 구현 결과

사용자가 Phase 2의 R-01/R-02 테스트 보완과 S0 로컬 Green 구현·검증을 승인했다.
기존 세 공개 이름과 책임 경계를 유지하며 §2의 예상 파일 배치를 구현했다.
커밋·푸시·PR·원격 쓰기·실제 호출은 승인 범위에 포함되지 않는다.

- **R-01:** 세 필수 필드 각각의 None, 빈 문자열, 공백, 정수, 불리언을
  `CANDIDATE_FIELDS_INVALID`로 제외한다. 기존 빈 URL 테스트는 같은 계약의
  필수 필드 검증 테스트로 통합했다. R-01은 후보만 변경하고 인용 구조를 유지한다.
- **R-02:** annotations는 list이고 각 항목은 type이 `url_citation`이며
  비어 있지 않은 문자열 URL을 갖는 dictionary여야 한다. 구조 오류·비문자열 URL·
  알 수 없는 타입은 제한된 S0 응답 프로필의 구조 오류다. 유효 인용이 함께 있어도
  `INVALID_OR_INCOMPLETE_RESPONSE`이며 후보는 0건이다.
- 구조가 정상인 다른 URL 인용은 구조 오류가 아니다. 일치하는 인용도 있으면 후보를
  검토 대상으로 유지하고, 일치하는 인용이 전혀 없으면 `CITATION_URL_MISMATCH`다.
- 인용 title/offset 진위, 실제 원출처 내용·권리·최신성은 여전히 검증하지 않는다.
- 부가적인 내부 진단은 `RESPONSE_STRUCTURE_INVALID`,
  `ANNOTATION_STRUCTURE_INVALID`이며 원문·예외 내용을 출력하지 않는다.
- URL host는 ASCII DNS label 형태만 처리한다. Unicode 도메인 이름의 실응답 지원은
  이 S0 구현에서 보장하지 않는다. 기존 RSS 정규화 계약을 가져오거나 수정하지 않았다.
- 전체 S0 116 passed, 격리 테스트 단독 14 passed, 대상 Ruff PASS.
  이는 S0 Fixture-only 검증 결과이며 S1 실제 검색·S2 독립 확인·운영 승인과 별개다.
