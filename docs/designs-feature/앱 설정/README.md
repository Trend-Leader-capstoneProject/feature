# 앱 설정 — 화면 테마·앱 정보·도움말/문의

작성일: 2026-11-18

## 범위와 기준

사용자 요청은 앱 설정에 화면 테마, 앱 정보, 도움말/문의만 추가하는 것이다.
사용자가 이번 기능의 세부 결정은 구현자가 판단한 뒤 보고하도록 명시적으로 위임했다.
이 지시는 이전의 ‘설정 내용은 후속 기획’ 결정을 이번 세 범위에 한해 구체화한다.
계정 관리·인증 API와 DB 계약은 변경하지 않는다.

## 제공 동작

- 홈·내 정보의 톱니바퀴 → 앱 설정.
- 화면 테마: 기기 설정 따르기(기본), 라이트 모드, 다크 모드. 선택은 이 기기에만 저장한다.
- 홈·내 정보·관심사·로그인/가입·각종 팝업과 공통 버튼·입력, 네비게이션 배경, 상태바에 테마 적용.
- 앱 정보: 프로젝트 manifest의 앱 이름·버전, 서비스 소개, 프로젝트 페이지, 주요 오픈소스 라이선스 링크.
- 도움말/문의: 실제 기능에 맞는 FAQ, GitHub 공개 문의 작성 화면 연결.
- 문의는 브라우저를 열어 사용자가 GitHub에 로그인하고 직접 작성·전송한다. 앱이 문의를 자동 등록하지 않는다.
- 공개 게시판임을 표시한다. 문의 양식에 자동 포함하는 정보는 앱 버전·플랫폼뿐이며 계정 정보·인증 값은 포함하지 않는다.
- 문의 이메일·개인 연락처·스토어 주소는 임의로 만들지 않는다. 문의 게시판 활성 상태는 GitHub repository API에서 확인했다.
- 새로운 계정·알림 설정이나 하단 탭은 추가하지 않는다.

## 구현과 실패 처리

- ThemeProvider가 테마를 관리하고 createThemedStyles가 기존 의미별 색상 토큰의 밝은/어두운 팔레트를 연결한다.
- SecureStore의 별도 키 trend-leader.theme.v1에 SYSTEM/LIGHT/DARK를 저장한다. 인증 묶음·로그아웃 처리와 분리되어 로그아웃 후에도 유지한다.
- 저장 중 중복 선택을 막는다. 저장 실패 시 기존 선택을 유지하고 오류·재선택을 안내한다.
- 초기 읽기 실패는 기본 기기 테마로 앱 사용을 허용하며 설정 재조회 기능을 제공한다.
- 늦은 복구 응답이 새 선택을 덮어쓰지 않도록 처리한다. 저장된 알 수 없는 값은 SYSTEM으로 복구한다.
- 초기 복구를 기다린 후 앱을 열되 이후 재조회 중에는 네비게이션을 유지한다.
- React Native Appearance로 앱의 native 표시 스타일을 지정하고 SYSTEM 선택 시 unspecified로 해제한다. 설치된 RN 0.86.2의 API 형식을 따른다.
- app.json의 userInterfaceStyle을 automatic으로 변경했다. Android 빌드 지원을 위해 SDK57 호환 expo-system-ui만 추가했다.
- 설치 결과 expo-system-ui 57.0.4 및 하위 normalize-colors 0.86.3이 추가되었으며 기존 의존성 버전은 유지했다.
- 기존 native transitionEnd 기반 중복 이동·빠른 복귀 보호를 새 화면에도 적용한다.
- 외부 링크 실패 시 화면 안에 안내하고 다시 누르면 재시도한다.

## 검증

최종 검증 결과는 아래에 갱신한다.

- 설정 저장/시스템/복구·화면·외부 링크 테스트 13개 통과.
- 앱 시작·복구 중 네비게이션 유지 및 실제 Stack 하위 화면 복귀 회귀 추가.
- Expo Android 개발 번들 HTTP200 확인.
- 최종 npm run typecheck 통과, npm test -- --runInBand: 32 suites / 207 passed.
- 기존 useUpdateInterests 테스트에서 비동기 act 경고 1건이 출력되었으나 실패는 없었다.
- Backend/DB 변경이 없어 이번에는 서버 테스트를 재실행하지 않았다.

## 남은 수동 확인

- Expo Go에서 세 테마 선택, 홈/내 정보/로그인·팝업 대비, 앱 완전 종료 후 선택 유지.
- 기기 테마 변경 후 SYSTEM 동작과 수동 테마 → SYSTEM 복귀.
- 앱 정보·도움말 이동과 기기 뒤로가기, FAQ, 실제 브라우저 문의 양식 연결.
- 설치형 Android/iOS 빌드는 이번에 실행하지 않았다. app.json 변경과 새 native 모듈 반영에는 새 빌드가 필요하다.
- 기존 계정 관리의 미검증 기기 예외 항목은 이번 설정 구현으로 완료 처리하지 않는다.

## 참고

- [Expo 테마 구성](https://docs.expo.dev/develop/user-interface/color-themes/)
- [React Native Appearance](https://reactnative.dev/docs/0.86/appearance)
- [React Navigation 테마](https://reactnavigation.org/docs/themes/)
