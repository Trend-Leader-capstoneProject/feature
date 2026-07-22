# Trend Leader

<div align="center">

## 관심사 기반 개인화 트렌드 큐레이션 앱

**Trend Leader**는 사용자가 선택한 관심 분야를 기준으로 최신 트렌드를 선별해 제공하고,  
AI 기반 요약과 유행 이유 분석을 통해 트렌드의 맥락을 빠르게 이해할 수 있도록 돕는 모바일 앱입니다.

</div>

---

### Backend, Frontend, Platform

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=flat-square&logo=fastapi&logoColor=blue" />
  <img src="https://img.shields.io/badge/React%20Native-Frontend-61DAFB?style=flat-square&logo=react&logoColor=cyan" />
  <img src="https://img.shields.io/badge/Expo-Mobile-3DDC84?style=flat-square&logo=expo&logoColor=white" />
  <img src="https://img.shields.io/badge/Python-3.14-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/TypeScript-Strict-3178C6?style=flat-square&logo=typescript&logoColor=white" />
  <img src="https://img.shields.io/badge/MySQL%20%2F%20MariaDB-Database-4479A1?style=flat-square&logo=mysql&logoColor=white" />
</p>



---

## 1. 프로젝트 개요

Trend Leader는 여러 플랫폼에 흩어진 트렌드 정보를 한곳에서 확인하고,  
사용자의 관심 카테고리에 맞는 트렌드를 우선적으로 탐색할 수 있도록 설계된 졸업작품 프로젝트입니다.

초기 목표는 단순한 최신 이슈 제공 앱이었으나, 기획을 구체화하면서 **사용자 관심사 기반 맞춤형 트렌드 제공 서비스**로 방향을 확장했습니다.

### 핵심 가치

- 관심 분야 중심의 트렌드 탐색
- 최신 이슈와 개인 관심 트렌드의 분리 제공
- AI 기반 트렌드 요약, 유행 이유, 관련 키워드 제공
- 저장/북마크를 통한 관심 트렌드 재확인
- 향후 사용자 행동 기반 추천 고도화 확장

---

## 2. 주요 기능

### 2.1 사용자 / 인증

- 회원가입
- 로그인
- 구글 OAuth 로그인
- 로그아웃
- 내 정보 조회
- 회원 정보 수정
- 비밀번호 변경
- 회원 탈퇴

### 2.2 관심사

- 카테고리 목록 조회
- 회원가입 후 관심사 선택
- 기존 관심사 조회
- 관심사 수정

### 2.3 트렌드

- 관심사 기반 맞춤 트렌드 목록 조회
- 전체 최신 이슈 목록 조회
- 트렌드 상세 조회
- AI 요약, 유행 이유, 관련 키워드 조회
- 트렌드 출처 정보 조회

### 2.4 북마크

- 트렌드 저장
- 트렌드 저장 해제
- 저장한 트렌드 목록 조회

### 2.5 검색

- 트렌드 검색
- 최근 검색어 조회
- 검색 기록 삭제

---

## 3. 기술 스택

### Frontend

| 구분 | 기술 |
|---|---|
| Framework | React Native |
| Runtime / Tooling | Expo |
| Language | TypeScript |
| Package Manager | npm |
| Target | Android 중심 모바일 앱 |

### Backend

| 구분 | 기술 |
|---|---|
| Framework | FastAPI |
| Language | Python |
| Server | Uvicorn |
| Validation | Pydantic |
| ORM | SQLAlchemy |
| Migration | Alembic |
| Auth | JWT Bearer Token |
| Password Hashing | passlib[bcrypt] |

### Database

| 구분 | 기술 |
|---|---|
| RDBMS | MySQL 또는 MariaDB |
| Driver | PyMySQL |
| Charset | utf8mb4 |

### AI / External

| 구분 | 내용 |
|---|---|
| AI Provider | 초기 mock 기반, 이후 OpenAI/Gemini 등 확장 가능 |
| OAuth | Google OAuth 연동 예정 |

---

## 4. Repository 구성

본 프로젝트는 기능 구현 레포지토리와 디자인 산출물 레포지토리를 분리해 관리합니다.

| Repository | 역할 |
|---|---|
| [`feature`](https://github.com/Trend-Leader-capstoneProject/feature) | Frontend / Backend 실제 기능 구현 |
| [`design`](https://github.com/Trend-Leader-capstoneProject/design) | 문서, 발표자료, Figma, 로고, 스토리보드 등 디자인 산출물 관리 |

---

## 5. 현재 프로젝트 구조

```text
feature/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── router.py
│   │   │   └── routes/
│   │   │       └── health.py
│   │   ├── core/
│   │   │   └── config.py
│   │   ├── db/
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── resources/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── utils/
│   │   │   └── response.py
│   │   └── main.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   └── navigation/
│   │   │       └── RootNavigator.tsx
│   │   └── assets/
│   ├── App.tsx
│   ├── index.ts
│   ├── app.json
│   ├── package.json
│   ├── package-lock.json
│   └── tsconfig.json
│
├── .gitignore
└── README.md
```

---

## 6. 권장 구조

Trend Leader는 백엔드와 프론트엔드의 책임을 분리하고,  
각 기능의 위치를 쉽게 찾을 수 있도록 계층형·기능 중심 구조를 사용합니다.

---

### Backend

```text
backend/
├── app/
│   ├── api/             # FastAPI Router
│   ├── core/            # 환경변수 및 애플리케이션 설정
│   ├── db/              # DB 연결 및 세션 관리
│   ├── models/          # SQLAlchemy ORM Model
│   ├── schemas/         # API 요청·응답 Schema
│   ├── services/        # 비즈니스 로직
│   ├── repositories/    # DB 접근 로직
│   ├── resources/       # 프롬프트, Seed, 샘플 데이터
│   ├── utils/           # 공통 유틸리티
│   └── main.py          # FastAPI 애플리케이션 진입점
├── alembic/             # DB Migration
├── tests/               # 테스트 코드
├── .env.example
└── README.md
```

백엔드의 기본 처리 흐름은 다음과 같습니다.

```text
Client
  ↓
Router
  ↓
Service
  ↓
Repository
  ↓
Database
```

- `Router`: HTTP 요청 및 응답 처리
- `Service`: 기능의 핵심 비즈니스 로직 처리
- `Repository`: 데이터베이스 조회·저장·수정·삭제
- `Model`: 데이터베이스 테이블 매핑
- `Schema`: API 요청 및 응답 데이터 검증

---

### Frontend

```text
frontend/
├── assets/                # 이미지, 아이콘, 폰트
├── src/
│   ├── app/
│   │   ├── navigation/    # 화면 이동 및 Navigation 타입
│   │   ├── providers/     # React Query 등 전역 Provider
│   │   └── config/        # 앱 환경 설정
│   │
│   ├── features/
│   │   ├── auth/          # 로그인 및 회원가입
│   │   ├── user/          # 사용자 정보 및 마이페이지
│   │   ├── interest/      # 관심사 선택 및 수정
│   │   ├── trend/         # 트렌드 목록 및 상세
│   │   ├── bookmark/      # 저장 트렌드
│   │   └── search/        # 트렌드 검색
│   │
│   └── shared/
│       ├── api/           # 공통 API Client
│       ├── components/    # 공통 UI Component
│       ├── constants/     # 색상, 간격 등 공통 상수
│       ├── hooks/         # 공통 Custom Hook
│       ├── storage/       # 토큰 등 로컬 저장소
│       ├── types/         # 공통 Type
│       └── utils/         # 공통 유틸리티
│
├── App.tsx
├── index.ts
├── .env.example
└── README.md
```

각 Feature는 필요한 범위에서 다음 구조를 사용합니다.

```text
feature/
├── api/          # FastAPI 서버 통신
├── components/   # 기능 전용 UI Component
├── hooks/        # API 요청 및 상태 관리
├── screens/      # 화면 구성
└── types/        # 요청·응답 및 기능 Type
```

프론트엔드의 기본 처리 흐름은 다음과 같습니다.

```text
User
  ↓
Screen
  ↓
Custom Hook
  ↓
API Function
  ↓
FastAPI Backend
```

- `Screen`: 화면 구성, 사용자 이벤트, Navigation 처리
- `Hook`: React Query 기반 API 상태 관리
- `API Function`: 서버 요청 및 응답 반환
- `Component`: 재사용 가능한 UI
- `Type`: API 요청·응답 데이터 구조 정의

---

## 구조 관리 원칙

- 백엔드는 `Router → Service → Repository` 책임을 분리합니다.
- 프론트엔드는 API를 Screen에서 직접 호출하지 않고 Hook을 사용합니다.
- 여러 기능에서 사용하는 코드는 `shared`에 배치합니다.
- 특정 기능에만 사용되는 코드는 해당 `features` 내부에 배치합니다.
- 빈 폴더를 모두 미리 생성하지 않고 실제 코드가 필요할 때 추가합니다.

---

## 상세 코딩 컨벤션

세부 파일명, 함수명, API 작성 규칙은 별도 컨벤션 문서를 따릅니다.

- Backend 코딩 컨벤션
- Frontend 코딩 컨벤션

---

## 환경변수 관리

환경변수는 프로젝트 루트의 `.env` 파일에서 관리합니다.

```env
EXPO_PUBLIC_API_BASE_URL=http://localhost:8000/api
```

실제 환경변수 파일은 Git에 포함하지 않습니다.

```text
.env          → 실제 개발 환경값, Git 제외
.env.example  → 팀 공유용 예시값, Git 포함
```

클라이언트에 포함되는 환경변수에는 JWT Secret, DB Password, 외부 API Secret 등 서버 비밀값을 작성하지 않습니다.
---

## 7. 개발 환경 준비

다음 도구가 설치되어 있어야 합니다.

- Git
- Node.js LTS
- npm
- Python 3.12 권장
- MySQL 또는 MariaDB
- Android Studio 또는 Expo Go
- VS Code

---

## 8. Frontend 실행 방법

```bash
cd frontend
npm install
npx expo start -c
```

Expo Go를 사용하는 경우 터미널에 표시되는 QR 코드를 모바일 기기로 스캔합니다.

Android Emulator 또는 개발 빌드를 사용하는 경우 다음 명령을 사용할 수 있습니다.

```bash
npm run android
```

### Expo 관련 주의사항

- Expo Go 앱 버전과 `package.json`의 Expo SDK 계열이 맞아야 합니다.
- `package.json`과 `package-lock.json`의 Expo 관련 버전이 어긋나면 `node_modules`와 `package-lock.json`을 정리한 뒤 다시 설치합니다.
- 캐시 문제 발생 시 `npx expo start -c`를 사용합니다.

Windows PowerShell에서 정리할 경우:

```powershell
Remove-Item -Recurse -Force node_modules
Remove-Item -Force package-lock.json
npm install
npx expo start -c
```

---

## 9. Backend 실행 방법

### 9.1 가상환경 생성

```bash
cd backend
python -m venv venv
```

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Windows CMD:

```cmd
venv\Scripts\activate
```

macOS / Linux:

```bash
source venv/bin/activate
```

### 9.2 의존성 설치

```bash
pip install -r requirements.txt
```

### 9.3 환경 변수 설정

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

`.env` 예시:

```env
APP_NAME=Trend Leader API
APP_ENV=local
DEBUG=true
API_PREFIX=/api

DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=trend_leader
DB_USER=trend_user
DB_PASSWORD=trend_pass
DATABASE_URL=

JWT_SECRET_KEY=change_this_secret_key_min_16_chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

AI_PROVIDER=mock
OPENAI_API_KEY=
GEMINI_API_KEY=

CORS_ORIGINS=http://localhost:8081
```

> 실제 API Key, OAuth Secret, 운영 DB 비밀번호는 절대 Git에 커밋하지 않습니다.

### 9.4 서버 실행

```bash
uvicorn app.main:app --reload
```

또는 FastAPI CLI를 사용하는 경우:

```bash
fastapi dev app/main.py
```

### 9.5 서버 확인

```text
http://127.0.0.1:8000/
```

Swagger 문서:

```text
http://127.0.0.1:8000/docs
```

---

## 10. Docker 실행

현재 Dockerfile은 FastAPI 서버 실행을 위한 최소 구성입니다.

```bash
cd backend
docker build -t trend-leader-backend .
docker run -p 8000:8000 trend-leader-backend
```

추후 DB까지 함께 실행하려면 `docker-compose.yml` 구성을 추가합니다.

권장 구성:

```text
docker-compose.yml
- backend: FastAPI
- db: MySQL 또는 MariaDB
```

---

## 11. 주요 API 설계

공통 응답 구조:

```json
{
  "success": true,
  "statusCode": 200,
  "message": "요청에 성공했습니다.",
  "data": {}
}
```

### Auth API

| Method | Endpoint | 설명 |
|---|---|---|
| POST | `/api/auth/signup` | 회원가입 |
| GET | `/api/auth/check-login-id` | 아이디 중복 확인 |
| POST | `/api/auth/login` | 로그인 |
| POST | `/api/auth/google-login` | 구글 로그인 |
| POST | `/api/auth/logout` | 로그아웃 |

### User API

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/api/users/me` | 내 정보 조회 |
| PATCH | `/api/users/me` | 회원 정보 수정 |
| PATCH | `/api/users/me/password` | 비밀번호 변경 |
| DELETE | `/api/users/me` | 회원 탈퇴 |

### Interest API

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/api/categories` | 카테고리 목록 조회 |
| POST | `/api/users/me/interests` | 관심사 저장 |
| GET | `/api/users/me/interests` | 기존 관심사 조회 |
| PUT | `/api/users/me/interests` | 관심사 수정 |

### Trend API

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/api/trends/recommended` | 맞춤 트렌드 목록 조회 |
| GET | `/api/trends` | 전체 트렌드 목록 조회 |
| GET | `/api/trends/{trend_id}` | 트렌드 상세 조회 |

### Bookmark API

| Method | Endpoint | 설명 |
|---|---|---|
| POST | `/api/trends/{trend_id}/bookmark` | 트렌드 저장 |
| DELETE | `/api/trends/{trend_id}/bookmark` | 트렌드 저장 해제 |
| GET | `/api/users/me/bookmarks` | 저장 트렌드 목록 조회 |

### Search API

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/api/trends/search` | 트렌드 검색 |
| GET | `/api/users/me/search-logs` | 최근 검색어 조회 |
| DELETE | `/api/users/me/search-logs/{search_log_id}` | 검색 기록 삭제 |

---

## 12. Database 주요 테이블

| 테이블 | 설명 |
|---|---|
| `users` | 사용자 계정 정보 |
| `user_profiles` | 사용자 프로필 |
| `oauth_accounts` | OAuth 계정 연동 정보 |
| `categories` | 관심 카테고리 |
| `user_interest_categories` | 사용자 관심 카테고리 |
| `user_interest_keywords` | 사용자 관심 키워드 |
| `trends` | 트렌드 기본 정보 |
| `trend_category_map` | 트렌드-카테고리 매핑 |
| `trend_rank_snapshots` | 플랫폼별 트렌드 순위 기록 |
| `trend_ai_analyses` | AI 요약, 유행 이유, 상세 설명 |
| `trend_sources` | 트렌드 출처 |
| `trend_related_keywords` | 관련 키워드 |
| `user_trend_bookmarks` | 사용자 저장 트렌드 |
| `search_logs` | 검색 기록 |

---

## 13. Design Repository 구조

디자인 레포지토리는 기능 구현 레포지토리와 분리되어 있으며, 발표자료와 UI/UX 산출물 관리에 사용합니다.

```text
design/
└── designs/
    ├── docs/
    │   ├── temp/
    │   ├── idea/
    │   ├── output/
    │   ├── presentation/
    │   └── UI_UX/
    ├── figma_UI_UX/
    │   ├── figma_img/
    │   └── source/
    ├── logos/
    ├── storyboard/
    └── README.md
```

### 산출물 관리 기준

| 폴더 | 용도 |
|---|---|
| `docs/idea` | 초기 아이디어, 기획 메모 |
| `docs/output` | 최종 산출 문서 |
| `docs/presentation` | 발표자료 |
| `docs/UI_UX` | UI/UX 문서 |
| `figma_UI_UX/figma_img` | Figma 화면 이미지 |
| `figma_UI_UX/source` | UI 제작에 필요한 원본 이미지 |
| `logos` | 로고 및 브랜드 이미지 |
| `storyboard` | 사용자 시나리오, 스토리보드 |

---

## 14. 개발 우선순위

현재 프로젝트는 초기 구조 정리 단계이므로 다음 순서로 구현합니다.

### 1단계: 기반 안정화

- Frontend Expo 실행 안정화
- Backend `/api` prefix 적용
- CORS 설정
- 공통 응답/예외 처리 구조 정리
- README와 `.env.example` 최신화

### 2단계: 관심사 기능

- `GET /api/categories`
- `POST /api/users/me/interests`
- `GET /api/users/me/interests`
- `PUT /api/users/me/interests`

### 3단계: 트렌드 조회

- `GET /api/trends/recommended`
- `GET /api/trends`
- `GET /api/trends/{trend_id}`

### 4단계: 북마크 / 검색

- 트렌드 저장/해제
- 저장 트렌드 목록 조회
- 트렌드 검색
- 최근 검색어 관리

### 5단계: AI 분석

- 초기 mock 응답
- AI 요약 프롬프트 정리
- 외부 AI API 연동
- 분석 결과 저장/조회

---

## 15. Git 협업 규칙

### Branch 전략

권장 브랜치 구조:

```text
main
└── dev
    ├── feature/frontend-init
    ├── feature/backend-init
    ├── feature/auth-api
    ├── feature/interest-api
    └── feature/trend-screen
```

### Commit Message 예시

```text
[init] 프로젝트 초기 구조 생성
[feat] 관심사 카테고리 조회 API 구현
[fix] Expo SDK 버전 불일치 수정
[docs] README 실행 방법 추가
[refactor] 라우터 구조 분리
[test] 관심사 저장 서비스 테스트 추가
```

### Pull Request 기준

PR 작성 시 다음 내용을 포함합니다. (예시이기에 참고만!!)

```text
## 작업 내용
-

## 확인 방법
-

## 관련 이슈
-

## 비고
-
```

---

## 16. 코드 작성 원칙

### Backend

- `main.py`에는 API 로직을 직접 작성하지 않습니다.
- Router는 요청과 응답만 담당합니다.
- 핵심 판단은 Service에서 처리합니다.
- DB 접근은 Repository에서 처리합니다.
- Request / Response는 Pydantic Schema로 정의합니다.
- 공통 응답 구조를 유지합니다.
- 민감 정보는 `.env`로 분리합니다.

### Frontend

- 화면 단위 코드는 `screens`에 둡니다.
- 재사용 UI는 `components`에 둡니다.
- API 호출 코드는 `services`에 둡니다.
- 타입은 `types`에 분리합니다.
- 화면 이동 구조는 `navigation`에 둡니다.
- API 응답 로딩, 실패, 빈 상태를 반드시 고려합니다.

---

## 17. 자주 발생할 수 있는 문제

### 17.1 Expo 앱이 강제 종료되는 경우

확인할 것:

- Expo Go 앱 버전과 프로젝트 Expo SDK 버전이 맞는지 확인
- `package.json`과 `package-lock.json` 버전이 일치하는지 확인
- `node_modules` 재설치
- Metro 캐시 삭제

```bash
npx expo start -c
```

### 17.2 npm install 중 패키지 버전 오류가 나는 경우

```bash
rm -rf node_modules package-lock.json
npm install
```

Windows PowerShell:

```powershell
Remove-Item -Recurse -Force node_modules
Remove-Item -Force package-lock.json
npm install
```

### 17.3 Backend에서 환경 변수 오류가 나는 경우

`backend/.env` 파일이 있는지 확인합니다.

```bash
cp .env.example .env
```

`JWT_SECRET_KEY`는 최소 16자 이상이어야 합니다.

### 17.4 DB 연결 오류가 나는 경우

확인할 것:

- MySQL/MariaDB 서버 실행 여부
- `.env`의 DB 계정 정보
- `DATABASE_URL`
- DB 이름 `trend_leader` 생성 여부
- DB 사용자 권한

---

## 18. 참고 문서

| 문서 | 설명 |
|---|---|
| API 구성표 | API Endpoint, 요청/응답, 화면 흐름 정리 |
| ERD / SQL | DB 테이블 구조 |
| 코드 컨벤션 | Backend / Frontend 폴더 구조 및 작성 규칙 |
| Design Repository | Figma, 발표자료, 로고, 스토리보드 |
| 기능 상세 명세서 | 화면/기능별 세부 구현 기준 |

---

## 19. 프로젝트 상태 메모

현재 프로젝트는 초기화 및 구조 설계 단계입니다.

우선 목표는 다음 세로 흐름을 완성하는 것입니다.

```text
회원가입/로그인
→ 관심사 선택
→ 맞춤 트렌드 목록 조회
→ 트렌드 상세 조회
→ 북마크 저장
```

이 흐름이 완성되면 Trend Leader의 핵심 서비스 구조가 작동하기 시작합니다.

---

## 20. License

본 프로젝트는 강남대학교 컴퓨터공학부 졸업작품 팀 프로젝트로 진행 중입니다.  
라이선스 정책은 추후 팀 내부 협의 후 결정합니다.
