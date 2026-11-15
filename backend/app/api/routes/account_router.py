from fastapi import APIRouter, Request, Response
from starlette.concurrency import run_in_threadpool

from app.api.dependencies.account_dependency import AccountServiceDep
from app.api.dependencies.auth_dependency import AuthContextDep, SessionServiceDep
from app.schemas.account_schema import (
    Nickname,
    NicknameAvailability,
    NicknameRequest,
    PasswordChangeRequest,
    ProfileData,
    VerifyPasswordRequest,
)
from app.schemas.common_schema import CommonResponse
from app.services.image_service import MAX_IMAGE_BYTES, process_image
from app.utils.response import success_response

router = APIRouter(prefix="/users", tags=["account"])
public_router = APIRouter(prefix="/auth", tags=["auth"])


def _success(data, message="처리했습니다."):
    return success_response(message=message, data=data, status_code=200)


@public_router.get(
    "/check-nickname", response_model=CommonResponse[NicknameAvailability]
)
def check_signup_nickname(nickname: Nickname, service: AccountServiceDep):
    return _success(service.availability(nickname))


@router.get("/me/check-nickname", response_model=CommonResponse[NicknameAvailability])
def check_own_nickname(
    nickname: Nickname, context: AuthContextDep, service: AccountServiceDep
):
    return _success(service.availability(nickname, context.user.user_id))


@router.get("/me", response_model=CommonResponse[ProfileData])
def get_profile(context: AuthContextDep, service: AccountServiceDep):
    return _success(service.profile(context.user.user_id))


@router.patch("/me/nickname", response_model=CommonResponse[ProfileData])
def save_nickname(
    request: NicknameRequest, context: AuthContextDep, service: AccountServiceDep
):
    return _success(service.save_nickname(context, request.nickname))


@router.put(
    "/me/profile-image",
    response_model=CommonResponse[ProfileData],
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["image"],
                        "properties": {"image": {"type": "string", "format": "binary"}},
                    }
                }
            },
        }
    },
)
async def save_image(
    request: Request, context: AuthContextDep, service: AccountServiceDep
):
    from starlette.datastructures import UploadFile
    from starlette.exceptions import HTTPException as StarletteHTTPException

    from app.core.exceptions import ApplicationException
    from app.services.image_service import image_error

    def invalid_form():
        error = ApplicationException(
            data={
                "errors": [
                    {
                        "field": "body.image",
                        "message": "사진 한 장이 필요합니다.",
                        "type": "value_error",
                    }
                ]
            }
        )
        error.status_code = 422
        return error

    try:
        form = await request.form(max_files=1, max_fields=0)
    except StarletteHTTPException as exc:
        raise invalid_form() from exc
    try:
        items = list(form.multi_items())
        if (
            len(items) != 1
            or items[0][0] != "image"
            or not isinstance(items[0][1], UploadFile)
        ):
            raise invalid_form()
        raw = await items[0][1].read(MAX_IMAGE_BYTES + 1)
        if len(raw) > MAX_IMAGE_BYTES:
            raise image_error(413, "PROFILE_IMAGE_TOO_LARGE")
        data, extension = await run_in_threadpool(process_image, raw)
        result = await run_in_threadpool(service.save_image, context, data, extension)
        return _success(result)
    finally:
        await form.close()


@router.delete("/me/profile-image", response_model=CommonResponse[ProfileData])
def reset_image(context: AuthContextDep, service: AccountServiceDep):
    return _success(service.reset_image(context))


@router.get("/{user_id}/profile-image/{image_id}")
def get_image(
    user_id: int, image_id: str, context: AuthContextDep, service: AccountServiceDep
):
    data, content_type = service.image(user_id, image_id)
    return Response(
        data, media_type=content_type, headers={"Cache-Control": "private, no-store"}
    )


@router.put("/me/password", response_model=CommonResponse[None])
def change_password(
    request: PasswordChangeRequest, context: AuthContextDep, service: SessionServiceDep
):
    service.change_password(context, request)
    return _success(None, "비밀번호를 변경했습니다.")


@router.post(
    "/me/withdrawal/verify-password", response_model=CommonResponse[dict[str, bool]]
)
def verify_withdrawal(
    request: VerifyPasswordRequest, context: AuthContextDep, service: AccountServiceDep
):
    service.verify_withdrawal(context, request.current_password.get_secret_value())
    return _success({"verified": True})


@router.post("/me/withdrawal", response_model=CommonResponse[None])
def withdraw(
    request: VerifyPasswordRequest, context: AuthContextDep, service: AccountServiceDep
):
    service.withdraw(context, request.current_password.get_secret_value())
    return _success(None, "회원 탈퇴가 완료되었습니다.")
