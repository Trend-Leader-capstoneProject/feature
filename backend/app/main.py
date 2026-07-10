"""
Trend Leader FastAPI 애플리케이션 진입점.

주요 책임:
- FastAPI 애플리케이션 생성
- 공통 미들웨어 설정
- 통합 API Router 연결

개별 API 엔드포인트와 비즈니스 로직은 작성하지 않는다.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api.router import router as api_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

app.include_router(api_router)