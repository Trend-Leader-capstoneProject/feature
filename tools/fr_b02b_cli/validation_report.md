# FR-B02b CLI v0.3 — A1 원본 비교 검증 기록

> 기준일: 2026-11-09. **오프라인 구조 검증 전용 / G5·G6 HOLD / 실제 게시 불가.**
> 수행 환경: Python 3.13.5, 본 작업 컨테이너. 사용자의 Windows 실환경 검증은 별도.
> 원본 ZIP: `trend_leader_g5_p1_hold_gate_v01(2).zip` (재배포 산출물에 미포함). SHA-256: `b08eec2c1167bdbc55e4a8c3c1e82d6f62776d5ed6076c31245347e0c0f4c806`. 원본 ZIP 변경 없음.

## 검증 대상 원본

- `trend_leader_g5_a1_approval_reconcile_v02.py` SHA-256: `2f23da50d8d90ceef0e581c55f17a0ab08cae7e0277d929e69f37679dddaa6ed`
- `python315_approval_manifest_RECONFIRMED_v02.json` SHA-256: `79777fa611550226a1f1951994aa23ba574f55d476b7e4aaf666bfb68a1a596c`
- `python315_batch_candidate_REVIEW_ONLY_v02.json` SHA-256: `130fcd36ad454bcf77b7935e4c77d76495242a994992f217b824dfb689c65555`

## 원본/CLI 동일 입력 비교

| 검사 | 원본 A1 v0.2 | CLI v0.3 |
|---|---|---|
| Python 3.15 단일 후보 | `ELIGIBLE_FOR_REVIEW_ONLY` | `A1_STRUCTURE_MATCH_REVIEW_ONLY`, reason=`ELIGIBLE_FOR_REVIEW_ONLY` |
| 잠재 적격 | 1 | 1 |
| 게시 허가 | 0 | 0 / `NONE` |
| 콘텐츠 지문 | `canonical_ref()` 결과와 승인 장부값 동일 | 별도 계산 일치 |
| 원본 ZIP 직접 검사 | 원본 JSON 파일 분리 읽기 | `inspect-a1-zip` 동일 결과, 추출·쓰기 없음 |

지문 비교값: `sha256:4584222134c7a420dcfd929c1e03f0b715ba332a2ebc78d266e1843a2d34c28f`. 이 값은 **내용 동등성**을 나타낼 뿐 승인자의 실제 권한·제3자 이용 권리·관측 시각을 인증하지 않는다.

## 부적격 반례 비교

| 반례 (검사용 메모리 사본 변경, 원본 파일 변경 없음) | 원본 A1 판정 | CLI v0.3 대응 |
|---|---|---|
| `content_summary_changed` | `CONTENT_CHANGED_REVIEW_REQUIRED` | `BLOCKED` |
| `source_label_evidence_changed` | `CONTENT_CHANGED_REVIEW_REQUIRED` | `BLOCKED` |
| `approval_revoked` | `APPROVAL_REVOKED` | `BLOCKED` |
| `rights_checked_false` | `G4_CHECK_INCOMPLETE` | `BLOCKED` |
| `approved_at_missing` | `APPROVAL_EVIDENCE_INCOMPLETE` | `BLOCKED` |
| `batch_g6_pass_forged` | `BATCH_BLOCKED` | `BLOCKED` |
| `unknown_batch_item_field` | `BATCH_BLOCKED` | `BLOCKED` |

주의: CLI v0.3은 단일 항목에 대해서만 *적격 여부*를 확인하고 부적격이면 즉시 차단한다. 원본 A1은 다건 Batch에 대해 항목별 `EXCLUDE`도 보고한다. 차단/제외가 같은 *안전 방향*임을 확인했을 뿐, 모든 실패 사유·형식에서 완전한 출력 호환을 뜻하지 않는다.

## 변경 내용·검증 범위

- CLI v0.2에서 잘못 가정한 Batch item 내 `content_ref`, `review_evidence_id`를 제거하고 승인 레코드에서만 읽게 수정.
- 원본 A1 파일 최상위 키·17개 승인 레코드 필드·세 Batch item 필드·A1 SHA-256 정규화·오프셋 포함 승인 시각/필수 점검 필드에 맞추어 단일 후보 검사.
- `inspect-a1-zip`은 ZIP 내 두 특정 JSON만 읽음. 내부 `.py`는 실행하지 않음. 외부 요청·DB 접근·실제 관측 증거 생성 없음.
- 테스트에서 실제 사람의 승인·권리·출처 관측을 검증하지 않으며, G4/G5/G6 승인 상태는 변경하지 않음.

## 남은 범위

실제 원문에 대한 수동 확인 이벤트, 시스템 시각·검토 권한·보호 저장소와의 연결은 **별도 FR-B02b 작업**이다. 운영용 독립 A1 검증기, P4 Writer, G5/G6 PASS를 본 PoC가 대체하지 않는다.
