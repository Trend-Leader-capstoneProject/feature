"""
Trend Leader 서버 상태 확인 API.

Liveness:
- FastAPI 프로세스 자체가 실행 중인지 확인한다.
- DB 연결 여부와 관계없이 200을 반환한다.

Readiness:
- 실제 서비스 요청을 처리할 준비가 되었는지 확인한다.
- DB에 SELECT 1을 실행한다.
- DB 연결 실패 시 503을 반환한다.
"""

import logging
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.utils.response import success_response


logger = logging.getLogger(__name__)
settings = get_settings()


root_router = APIRouter(
    tags=["Root"],
)

router = APIRouter(
    prefix="/health",
    tags=["health"],
)


@root_router.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="서버 기본 실행 확인",
)
async def root() -> dict[str, Any]:
    """
    Trend Leader API 서버의 기본 실행 상태를 반환한다.
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
    FastAPI 프로세스의 실행 상태를 확인한다.

    DB가 중단되어 있어도 API 프로세스가 실행 중이면 200을 반환한다.
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


@router.get(
    "/ready",
    status_code=status.HTTP_200_OK,
    summary="API 준비 상태 확인",
    response_model=None,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "데이터베이스 연결 불가",
        },
    },
)
def readiness_check(
    db: Annotated[Session, Depends(get_db)],
) -> Any:
    """
    DB에 SELECT 1을 실행하여 서비스 준비 상태를 확인한다.

    성공:
    - HTTP 200
    - database: available

    실패:
    - HTTP 503
    - database: unavailable
    
    async 없음 : 스레드풀 실행 / (이벤트 루프 방어 방지)
    """
    checked_at = datetime.now(UTC).isoformat()

    try:
        result = db.execute(text("SELECT 1")).scalar_one()

    except SQLAlchemyError:
        # 상세 DB 오류는 서버 로그에만 기록한다.
        # DB 주소, 사용자명 등의 내부 정보는 API 응답에 포함하지 않는다.
        logger.exception("Database readiness check failed")

        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False,
                "statusCode": status.HTTP_503_SERVICE_UNAVAILABLE,
                "message": "Trend Leader API is not ready",
                "data": {
                    "service": "trend-leader-api",
                    "environment": settings.app_env,
                    "status": "not_ready",
                    "database": "unavailable",
                    "checkedAt": checked_at,
                },
            },
        )

    if result != 1:
        logger.error(
            "Unexpected database readiness result: %r",
            result,
        )

        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False,
                "statusCode": status.HTTP_503_SERVICE_UNAVAILABLE,
                "message": "Trend Leader API is not ready",
                "data": {
                    "service": "trend-leader-api",
                    "environment": settings.app_env,
                    "status": "not_ready",
                    "database": "unexpected_response",
                    "checkedAt": checked_at,
                },
            },
        )

    return success_response(
        message="Trend Leader API is ready",
        data={
            "service": "trend-leader-api",
            "environment": settings.app_env,
            "status": "ready",
            "database": "available",
            "checkedAt": checked_at,
        },
        status_code=status.HTTP_200_OK,
    )