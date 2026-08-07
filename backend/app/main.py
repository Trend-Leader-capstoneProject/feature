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

from app.api.exception_handler import register_exception_handlers
from app.api.router import api_router, root_router
from app.core.config import get_settings

settings = get_settings()


def create_app() -> FastAPI:
    """
    FastAPI 애플리케이션을 생성하고 공통 설정을 적용한다.

    Returns:
        설정이 완료된 FastAPI 애플리케이션
    """
    application = FastAPI(
        title=settings.app_name,
        description=(
            "사용자의 관심사를 기반으로 맞춤형 트렌드를 제공하는 "
            "Trend Leader 백엔드 API입니다."
        ),
        version="0.1.0",
        debug=settings.debug,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    
    register_exception_handlers(
        application,
    )
    
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 서버 기본 진입점: GET /
    application.include_router(
        root_router,
    )

    # 실제 서비스 API: /api/*
    application.include_router(
        api_router,
        prefix=settings.api_prefix,
    )

    return application


app = create_app()
