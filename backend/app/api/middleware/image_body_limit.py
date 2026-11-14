from app.services.image_service import MAX_MULTIPART_BYTES, image_error
from app.utils.response import error_response


class ImageBodyLimitMiddleware:
    """Content-Length가 없거나 거짓이어도 해당 upload의 수신량을 제한한다."""

    def __init__(self, app, path: str):
        self.app, self.path = app, path

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope["method"] != "PUT"
            or scope["path"] != self.path
        ):
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = 0
        if declared > MAX_MULTIPART_BYTES:
            response = error_response(
                message="사진 용량 제한을 초과했습니다.",
                status_code=413,
                data={"reason": "PROFILE_IMAGE_TOO_LARGE"},
            )
            await response(scope, receive, send)
            return
        total = 0

        async def limited_receive():
            nonlocal total
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > MAX_MULTIPART_BYTES:
                    raise image_error(413, "PROFILE_IMAGE_TOO_LARGE")
            return message

        await self.app(scope, limited_receive, send)
