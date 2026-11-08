# Trend Leader — 게시 운영 문서

> **2026-11-08 문서 복원 1차 (부분 반영)** · [전체 문서 및 미반영 후보](documents-index.md)

## 기준 정책 및 운영 상태

- 정책 원본: [Google Trends RSS 운영 Gate v0.3](policy/Google_Trends_RSS_%EC%9A%B4%EC%98%81_Gate_%ED%86%B5%EA%B3%BC%EA%B8%B0%EC%A4%80_%EA%B2%80%EC%A6%9D%EC%A6%9D%EA%B1%B0_v0.3_POLICY_CONFIRMED.md). `POLICY_CONFIRMED`는 사용자의 운영 정책 결정 확정이며 **G0~G6 증거 충족이나 실제 게시 승인이 아닙니다**.
- **MVP-A**: 권리를 확인한 자체 작성 콘텐츠를 개별 G4 검토·승인한 뒤 적격 Batch 후보로 구성합니다. 개별 G4 승인·G6 운영 프로필 승인·실제 Batch 게시는 별도입니다.
- **G6 HOLD**: 게시 실행을 허용하지 않습니다. G4/A1 검증이 PASS 또는 REVIEW_ONLY라도 게시 허가가 아닙니다.
- **RSS-OPS HOLD**: Google RSS 자동 접근·DB 보존·앱 공개 권한은 아직 확인되지 않았습니다. 합성 XML 기반 PoC PASS는 운영 권한 증거가 아닙니다.

## 관련 기술 설계와 우선순위

- RSS 기술 PoC의 최신 계약은 기존 `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_RSS_P0-P3_PoC_Implementation_Contract_v1.1_FROZEN.md`에 그대로 있습니다.
- P4 최신 검토 문서는 기존 같은 폴더의 `Trend_Leader_P4_Final_Review_Addendum_v0.2_A1_Aligned_DRAFT_20261108.md`이며 **P4 NOT FROZEN**입니다.
- 기존 G5 A1 검증 체크포인트도 기존 기술 설계 폴더에서 유지합니다.
- 이 폴더에 복원된 문서는 **작성 당시의 검토·시험 상태**를 보존하며 최신 DB/운영 설정의 실측 증명이 아닙니다. 기능별 확정 계약이 변경된 경우 먼저 충돌을 기록하고 재판정해야 합니다.


## G5 문서의 버전·적용 범위

- [A1 v0.2 출처 안내 조건부 허용 설계·검증](g5-publish-control/Trend_Leader_MVP_A_G5_A1_%EC%B6%9C%EC%B2%98%EC%95%88%EB%82%B4_%EC%98%88%EC%99%B8%EA%B3%84%EC%95%BD_v0.2_DESIGN_REVIEW.md): `EDITORIAL_LABEL`은 검토 증거가 있는 자체 작성 안내 문구만 허용하며 외부 원제목 재사용이나 실제 게시를 허용하지 않습니다. `DESIGN_REVIEW`이며 G5/G6 HOLD입니다.
- [P1 HOLD 경계 최소 계약](g5-publish-control/Trend_Leader_MVP_A_G5_P1_%EC%B5%9C%EC%86%8C%EC%8B%A4%ED%96%89%EA%B3%84%EC%95%BD_%ED%99%95%EC%A0%95_HOLD_%EC%B0%A8%EB%8B%A8%EC%8B%9C%ED%97%98_v0.1.md): 2026-11-04 시점 `HOLD` 차단만 범위 제한 확정. 실제 게시 `APPLY` 미구현; P4 전체를 확정하거나 운영 PASS한 문서가 아닙니다.
- [A1 v0.1 대조 검증안](archive/g5-a1/Trend_Leader_MVP_A_G5_A1_%EC%8A%B9%EC%9D%B8%EC%A6%9D%EA%B1%B0_Batch_%EB%8C%80%EC%A1%B0_%EA%B2%80%EC%A6%9D%EC%95%88_v0.1.md): `source_title=null`만 허용했던 **초기 규칙**으로, v0.2 조건부 출처 안내 계약의 현재 범위를 덮어쓰지 않습니다.
- [G5·G6 Batch 기록표 v0.1](archive/g5-templates/Trend_Leader_MVP_A_G5_G6_Batch_%EC%8A%B9%EC%9D%B8_%EA%B2%8C%EC%8B%9C_%EA%B8%B0%EB%A1%9D%ED%91%9C_%ED%85%9C%ED%94%8C%EB%A6%BF_v0.1.md): 과거 양식의 `PARTIAL` 분기는 **확정된 P4 Batch 전체 Commit/Rollback** 결정을 대체하지 않습니다. 확정 Batch 구성 전 적격 후보 제외와 확정 Batch 실행의 원자성을 구별합니다. 이 양식을 실제 실행 기록에 적용하려면 P4 정합성 재검토가 필요합니다.

## 안내

[문서 인덱스](documents-index.md) · [1차 복원 검토 기록](reviews/2026-11-08-document-restoration-review.md) · [증거 보존 기준](evidence/README.md)

현재 확인된 원문 **11개**를 반영했으며, 나머지 G5/P4 후보 **16개**는 이번 PR에서 미반영 상태입니다. 이전 버전과 단순 시험 기록은 현행 계약으로 자동 복원하지 않습니다.
