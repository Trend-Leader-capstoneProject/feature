from fastapi import APIRouter, status

from app.utils.response import success_response

router = APIRouter(
    tags=["Health"],
)


@router.get("/", status_code=status.HTTP_200_OK)
async def root():
    return success_response(
        message="Trend Leader API is running",
        data={
            "service": "trend-leader-api",
            "status": "running",
        },
        status_code=200,
    )