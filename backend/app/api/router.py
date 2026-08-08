"""
Trend Leader 통합 API Router.

각 기능별 Router를 하나로 모아 main.py에 전달한다.
이 파일에는 엔드포인트 구현이나 비즈니스 로직을 작성하지 않는다.
"""

from fastapi import APIRouter

from app.api.routes import category_router, health, interest_router

# GET / 등 API prefix를 사용하지 않는 기본 라우터
root_router = APIRouter()

# /api prefix 아래에 포함될 서비스 API 라우터
api_router = APIRouter()

root_router.include_router(health.root_router)

api_router.include_router(health.router)
api_router.include_router(category_router.router)
api_router.include_router(interest_router.router)
