from typing import Any

def success_response(
    message: str,
    data: Any = None,
    status_code: int = 200,
) -> dict[str, Any]:
    return {
        "success": True,
        "statusCode": status_code,
        "message": message,
        "data": data,
    }