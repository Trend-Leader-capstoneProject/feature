"""
Trend Leader 서버 상태 확인 API.

DB나 외부 API 연결 여부와 관계없이
FastAPI 애플리케이션 자체가 정상 실행 중인지 확인한다.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, status

from app.core.config import get_settings
from app.utils.response import success_response

settings = get_settings()



root_router = APIRouter(
    tags=["Root"],
)

router = APIRouter(
    prefix="/health",
    tags=["health"],
)


@root_router.get("/",
    status_code=status.HTTP_200_OK,
    summary="서버 기본 실행 확인",
)
async def root():
    """
    Trend Leader API 서버의 기본 실행 상태를 반환한다.

    브라우저 또는 개발자가 서버가 실행 중인지
    간단히 확인하기 위한 엔드포인트이다.
    """
    return success_response(
        message="Trend Leader API is running",
        data={
            "service": "trend-leader-api",
            "environment": settings.app_env,
            "status": "running",
        },
        status_code=status.HTTP_200_OK,
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="API 상태 확인",
)
async def health_check() -> dict[str, Any]:
    """
    API 애플리케이션의 상태 정보를 반환한다.

    이 단계에서는 FastAPI 서버 프로세스의 실행 여부만 확인한다.
    DB 및 외부 서비스 연결 상태 확인은 별도 readiness API로 확장한다.
    """
    
    return success_response(
        message="Trend Leader API is healthy",
        data={
            "service": "trend-leader-api",
            "environment": settings.app_env,
            "status": "healthy",
            "checkedAt": datetime.now(UTC).isoformat(),
        },
        status_code=status.HTTP_200_OK,
    )