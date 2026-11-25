# Trend Leader — SearchApi Related News Enhancement FROZEN v1.0

> 2026-11-25 KST / PR #140 / DEC-01~07 사용자 일괄 승인. 설계 승인과 실제 운영 적용은 별개.
> 기준: 실제 관심도 공급 COMMITTED (db39a7f), 기존 AP3C FROZEN DEC-12~13, SearchApi B v0.1 및 11-25 관심도 정책 결정. 본 문서가 관련 기사 참고자료 범위에서 기존 기사 필수 교차검증/2회 관심도 요청 계약을 대체한다. 기존 NewsSnapshot 사건 게시 경로는 HOLD 유지.

## 1. 기능 책임 및 불변조건
- 주제 선정/게시 근거는 기존 Catalog + Collector/Writer 독립 Trending Now 관측. 관련 기사는 부가 탐색 자료이며 검색 상승의 인과관계, 검증된 사건, 사실 요약으로 주장하지 않는다.
- Google Trends 관측 출처 및 원본 source identity/key/Journal/24h 노출 유지. 기사 조회 실패로 필수 관심도 검증을 우회하거나 DB 실패를 성공 처리하지 않는다.
- C(검색어 기반 통합 검색) + D-2(최대 2개의 적격 직접 기사 링크); D-2가 없으면 D-1(뉴스 검색). 관측 출처는 별도 버튼으로 유지. 클릭 시 추가 SearchApi 호출 없음.
- 신규 엔진/AI/본문 Reader/기사 이미지/자동 백필/별도 Scheduler 없음.

## 2. 확정 결정
| ID | 확정 정책 |
|---|---|
| DEC-01 | Collector Trending 1 + Writer Trending 1 + Writer의 독립 응답 news_token을 사용한 Related News 최대 1. 최대 3회/회차. 같은 token 응답 확인, DB 트랜잭션 밖, 재시도 없음. |
| DEC-02 | 이용 근거가 확인된 직접 HTTPS URL, 언론사명, 발행 시각. 제목은 별도 이용 근거 확인 때만, 기본 NULL. 응답 파싱용 제목은 일시 메모리 사용만; 본문/AI 요약/이미지/원본 JSON/토큰 영속 저장 금지. |
| DEC-03 | 정확한 token, 검색어 관련성, 발행 후 48시간 이내(미래 제외), 직접 URL·허용 발행사 경계, 중복 URL 제외. 최대 2개, 서로 다른 매체 우선, 후보 내 provider 순서. 1개도 허용. |
| DEC-04 | trend_related_articles 별도 테이블. trend_sources는 관측 출처 유지. |
| DEC-05 | 전체/개인화 목록에 related_articles 배열 추가, 없으면 []; latest_source 유지. 일괄 조회로 N+1 방지. |
| DEC-06 | 선택 기사 조회 실패/권리 미확보/0건/만료 → D-1. 필수 관측/DB/Journal 오류는 기존 HOLD. 429는 Retry-After 보존, 유효하지 않은 deadline은 자동 호출 중단, 이미 완료된 DB 결과를 미확정 재실행으로 바꾸지 않음. |
| DEC-07 | 부모 관심도 수집 후 24h 비노출. 기사도 부모 24h 상한 및 기사 발행 48h 적격 기간 안에서만 표시(보수적 상한). 기존 중복 SKIP, 과거 카드 백필 없음. 실제 삭제는 기존 종료/정정·삭제 정책 연계. |

## 3. 상세 구현 계약
- 신규 테이블 이름 trend_related_articles. PK article_id, FK trend_id → trends.trend_id ON DELETE CASCADE. article_url TEXT, url_key CHAR(64) (정확한 정규 URL의 SHA-256), publisher VARCHAR(255), title VARCHAR(255) NULL, published_at/collected_at UTC-naive DATETIME, selection_order SMALLINT (1 또는 2). UNIQUE(trend_id,url_key), UNIQUE(trend_id,selection_order). 실제 모델과 Alembic은 기존 naming convention/타입을 따라 일치시킨다. 0..2는 Writer와 응답 방어에서 유지.
- 승인된 링크 이용 범위는 관리자 보호 설정으로 주입하고 기본 비어 있음(실제 기사 저장/직접 링크 게시 불가). 임의 도메인, credential URL, IP/private/local, redirect/tracking 토큰, 비정상 URL은 제외. 공급자 metadata와 제목의 보수적 관련성은 참고 적격 판정일 뿐 기사 원문 검증이 아니다. 제목 저장 허용은 별도 근거, 기본 NULL. 승인 없는 링크를 채워 넣지 않는다.
- 기존 관심도 Snapshot과 선택적 기사 payload는 Writer 독립 조회를 거쳐 결합; 기사 필드 및 순서를 digest에 포함. 동일 DB 트랜잭션 내 기존 신규 trend/source/category INSERT 후 기사 0..2건 INSERT, Journal은 동일 batch 단위. 실제 INSERT 오류는 전체 rollback/HOLD. 기존 중복은 기존 데이터에 보강하지 않음.
- 기존 Writer의 최소 GRANT/검증과 운영 scope/profile(2→3 요청, 부가 링크 이용 근거)은 기존 환경과 별도로 변경 승인 후 적용. 기존 2회 프로필로 선택 News 호출 금지. API의 배치 조회와 부모 노출 방어, 만료 링크 제거 및 응답 배열 기본 [] 유지. source_url은 원래 관측 URL 보존. 새 API 필드는 additive; frontend는 과거 응답 필드 미존재도 []로 처리.
- 429 deadline이 알려졌으면 기존 6h 전역 cooldown과 deadline 중 늦은 시각을 적용(완료된 source rotation/Journal 보존); 모르는 deadline/반복 제한은 기존 조사 HOLD 의미를 보존하되 완료된 DB 기록 재생성 금지. 선택 조회와 필수 조회 실패 경로 구분. 별도 재시도 없음.
- Frontend C+D-1: 기존 정확한 관측 URL + ETC 식별, title URL 인코딩, 고정 Google/Google News 링크, 관측 출처 버튼 별도. IGDB/GitHub 출처 label은 정확한 기존 URL 패턴만, 다른 source/기존 원문 버튼 호환. C+D-2는 관련 배열에 적격 링크가 있을 때 기사 보기, 없으면 뉴스 검색. 허용 링크가 있어도 통합 검색 유지.
- 기존 Source URL은 증거 목록 링크이며 현재 방문 시 과거 관측을 재현하지 않을 수 있음.

## 4. 검증 및 운영 적용
- 필수: URL/권리/관련성/날짜/최대 2·중복·토큰/요청 수, 선택 실패 및 429, 신규/중복/rollback/Journal, Migration/최소 grant, 두 목록 API 빈 배열·관련 링크·만료·N+1, C+D-1/2 클릭·다른 소스 회귀.
- 실제 운영 적용 전 로컬 기존 DB/Journal/Timer 보존, 신규 schema/GRANT/profile 승인 범위 확인. 기존 실제 COMMITTED 증거는 유지. Lightsail/dev merge는 별도 승인. 반복 PoC/전체 과거 테스트 재실행 금지, 필요한 변경 영향만.
- 최종 산출물: 논리/물리 ERD, 테이블 명세, API 명세, 아키텍처/흐름도/테스트 및 운영 권한 문서에 실제 구현 및 Migration 대조 후 반영(사용자 명시 요청).

## 5. 출처 및 범위
- https://www.searchapi.io/docs/google-trends-trending-now-news-api
- https://www.searchapi.io/legal/terms
- https://support.google.com/trends/answer/4365538
- 데이터 반환 기능과 이용 권리는 별개. 직접 링크 제공의 근거가 없으면 C+D-1만 사용. 본 설계 승인으로 제3자 권리 또는 운영 프로필을 자동 발행하지 않는다.
